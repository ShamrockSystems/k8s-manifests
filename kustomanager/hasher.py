import hashlib
import logging
from pathlib import Path

from _hashlib import HASH  # type: ignore
from gitignore_parser import (
    IgnoreRule,  # type: ignore
    rule_from_pattern,  # type: ignore
)
from gitignore_parser import handle_negation as evaluate_rules

from kustomanager.meta import DEFAULT_HASH_TYPE, IGNOREFILES, LOG_HASH
from kustomanager.util import normalize_line_endings

logger = logging.getLogger("hasher")


def directory_hash(path: Path, relative_to=None) -> str:
    """
    Compute the hash of a directory and its files, taking into account ignorefiles.

    relative_to: directory to start acquiring ignorefiles and file paths from (usually repo root)
    """
    if relative_to is None:
        relative_to = path.cwd()

    logger.log(
        LOG_HASH,
        f"Collecting initial IgnoreRule list for {path} relative to {relative_to}",
    )

    ignorerules: list[IgnoreRule] = []
    path = path.absolute()
    relative_to = relative_to.absolute()
    relative_path = path.relative_to(relative_to)
    for directory in reversed(relative_path.parents):
        ignorerules.extend(get_ignores(Path(relative_to, directory)))
    ignorerules.extend(get_ignores(Path(relative_to, relative_path)))

    logger.log(LOG_HASH, f"Starting hashing for {path}")

    return str(
        _directory_hash(
            path, hashlib.new(DEFAULT_HASH_TYPE), ignorerules, relative_to
        ).hexdigest()
    )


def _directory_hash(
    to_hash: Path, hashed: HASH, ignorerules: list[IgnoreRule], relative_to: Path
) -> HASH:
    """
    Recursively hashes directories, pushing and popping IgnoreRule objects
    """
    assert Path(to_hash).is_dir()
    for path in sorted(Path(to_hash).iterdir(), key=lambda p: str(p).lower()):
        # If the file matches an ignorefile rule, skip hashing
        if evaluate_rules(path.absolute(), ignorerules):
            logger.log(LOG_HASH, f"{path.absolute()} matches, skipping")
            continue
        if path.is_file():
            # Only add hashes for filenames, as empty directories will not be tracked in VCS.
            hashed.update(path.relative_to(relative_to).as_posix().encode())
            with open(path, "rb") as f:
                content = f.read()
                try:
                    # Git will checkout with different line endings depending on the system.
                    # These need to be normalized for consistent hashing.
                    decoded_content = content.decode("utf-8")
                    normalized_content = normalize_line_endings(decoded_content)
                    hashed.update(normalized_content.encode())
                except UnicodeDecodeError:
                    hashed.update(content)
        elif path.is_dir():
            # Recursive hash step, descend into directory, acquire additional IgnoreRule objects
            # Push
            new_ignorerules = get_ignores(path)
            new_len = len(new_ignorerules)
            ignorerules.extend(new_ignorerules)

            # Work
            hashed = _directory_hash(path, hashed, ignorerules, relative_to)

            # Pop
            if new_len != 0:
                logger.log(
                    LOG_HASH,
                    f"POP {path} off of the ignorerule stack ({new_len} rules)",
                )
                del ignorerules[-new_len:]
    return hashed


def get_ignores(directory) -> list[IgnoreRule]:
    """
    Dis-integrated version of `parse_gitignore` from `gitignore_parser` to allow for traversal
    """
    ignorerules: list[IgnoreRule] = []
    absolute_directory: Path = directory.resolve()
    for ignorefile in IGNOREFILES:
        ignorefile_path = Path(absolute_directory, ignorefile)
        if ignorefile_path.exists():
            with open(ignorefile_path, "r") as f:
                num_rules = 0
                for idx, line in enumerate(f.readlines(), start=1):
                    line = line.rstrip("\n")
                    rule = rule_from_pattern(
                        line,
                        base_path=absolute_directory,
                        source=(ignorefile_path, idx),
                    )
                    if rule is not None:
                        ignorerules.append(rule)
                        num_rules += 1
                logger.log(
                    LOG_HASH,
                    f"PUSH {ignorefile_path} exists, added ({num_rules} rules)",
                )
    return ignorerules
