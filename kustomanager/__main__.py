import logging
import subprocess
import sys
import time
from io import BytesIO
from pathlib import Path
from typing import Any

import click
from ruamel.yaml import YAML

from kustomanager.builder import build_from_source
from kustomanager.data import Build, Lockfile, get_yaml
from kustomanager.hasher import directory_hash
from kustomanager.meta import (
    APPLICATION_NAME,
    APPLICATION_VERSION,
    DEFAULT_HASH_TYPE,
    LOCKFILE_NAME,
    LOG_HASH,
    LOG_HASH_NAME,
)
from kustomanager.template import j2_env
from kustomanager.util import normalize_line_endings

TIMESTAMP = int(time.time())
logger = logging.getLogger("cli")


def main():
    cli.add_command(add)
    cli.add_command(build)
    cli.add_command(localdev)
    cli()


@click.group()
@click.option(
    "-v",
    "--verbosity",
    type=int,
    default=20,  # INFO
)
def cli(verbosity):
    formatter = MultiLineFormatter(
        fmt="[%(asctime)s][%(levelname)s][%(name)s] - %(message)s",
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.setStream(sys.stdout)
    logging.basicConfig(level=verbosity, handlers=[handler])
    logging.addLevelName(LOG_HASH, LOG_HASH_NAME)
    logger.info(f"{APPLICATION_NAME} {APPLICATION_VERSION} at {TIMESTAMP}")


@click.command()
@click.argument("cluster")
@click.argument("project")
def add(cluster: str, project: str):
    yaml = get_yaml()
    lockfile = load_lockfile(yaml=yaml)
    lockfile_data = Lockfile.from_yaml(constructor=yaml.constructor, node=lockfile)

    # Retrieve path of provided cluster

    cluster_data, cluster_builds = lockfile_data.STRUCTURE[cluster]
    cluster_directory: Path = cluster_data.DIRECTORY

    # Ensure that cluster name project name combination does not already exist
    assert project not in cluster_builds.keys()

    source_path = Path(cluster_directory, project)
    assert source_path.is_dir()

    logger.info("Hashing source")
    source_hash = directory_hash(source_path)

    build_path = Path(lockfile_data.BUILD_DIR, cluster, project)
    logger.info("Building source")
    build_from_source(source_path, build_path)
    logger.info("Hashing build")
    build_hash = directory_hash(build_path)

    logger.info("Reconciling lockfile")
    lockfile["builds"].append(
        Build(
            timestamp=TIMESTAMP,
            source_hash=source_hash,
            source_hash_type=DEFAULT_HASH_TYPE,
            source_path=source_path,
            build_hash=build_hash,
            build_hash_type=DEFAULT_HASH_TYPE,
            build_path=build_path,
            CLUSTER_NAME=cluster,
            NAME=project,
        )
    )

    save_lockfile(yaml, lockfile)


@click.command()
def build():
    yaml = get_yaml()
    lockfile = load_lockfile(yaml=yaml)

    lockfile_data = Lockfile.from_yaml(constructor=yaml.constructor, node=lockfile)

    logger.info(f"Checking source hashes of {len(lockfile_data.BUILDS)} builds")
    mismatched_builds: list[Build] = []
    for build in lockfile_data.BUILDS:
        source_hash = directory_hash(build.source_path)
        if source_hash != build.source_hash:
            build.source_hash = source_hash
            mismatched_builds.append(build)

    logger.info(f"Found {len(mismatched_builds)} mismatched hashes needing rebuild")

    for mismatched_build in mismatched_builds:
        logger.info(
            f"Rebuilding cluster={mismatched_build.CLUSTER_NAME} project={mismatched_build.NAME}"
        )
        build_from_source(
            kustomization_directory=mismatched_build.source_path,
            target_directory=mismatched_build.build_path,
        )
        mismatched_build.build_hash = directory_hash(mismatched_build.build_path)
        mismatched_build.timestamp = TIMESTAMP
        logger.debug(
            "New hashes, "
            + f"source:{mismatched_build.source_hash_type}={mismatched_build.source_hash} "
            + f"build:{mismatched_build.build_hash_type}={mismatched_build.build_hash}"
        )

    logger.info("Reconciling lockfile")
    for mismatched_build in mismatched_builds:
        idx = next(
            i
            for i, lockfile_build in enumerate(lockfile["builds"])
            if lockfile_build["cluster"] == mismatched_build.CLUSTER_NAME
            and lockfile_build["name"] == mismatched_build.NAME
        )
        del lockfile["builds"][idx]
        lockfile["builds"].append(mismatched_build)

    save_lockfile(yaml, lockfile)


@click.command()
def localdev():
    k3d_template = j2_env.get_template("cluster-local.localgen.yaml.j2")
    with open("cluster-local.localgen.yaml", "w", encoding="utf-8") as f:
        f.write(k3d_template.render(repo_path=str(Path.cwd().absolute())))
    args: list[str] = [
        "k3d",
        "cluster",
        "create",
        "--config",
        "cluster-local.localgen.yaml",
    ]
    logger.debug(f"Running {args}")
    result = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        text=True,
        universal_newlines=True,
    )
    if result.returncode != 0:
        logger.error(result.stderr)
        raise ChildProcessError
    if len(result.stderr):
        logger.warn(result.stderr)


def load_lockfile(yaml: YAML) -> tuple[Any, dict]:
    LOCKFILE_PATH = Path(Path.cwd(), LOCKFILE_NAME)

    # ruamel.yaml comment attachment does not behave consistently if line endings are not translated beforehand.
    # Therefore, load the file first,
    with open(LOCKFILE_PATH, "r", encoding="utf-8") as f:
        # translate
        converted = BytesIO()
        converted.write(normalize_line_endings(f.read()).encode("utf-8"))
        converted.seek(0)
    # and provide ruamel.yaml a BytesIO
    lockfile = yaml.load(converted)

    return lockfile


def save_lockfile(yaml: YAML, lockfile):
    LOCKFILE_PATH = Path(Path.cwd(), LOCKFILE_NAME)

    with open(LOCKFILE_PATH, "w") as f:
        yaml.dump(lockfile, f)


class MultiLineFormatter(logging.Formatter):
    def format(self, record):
        header: str = super().format(
            logging.LogRecord(
                name=record.name,
                level=record.levelno,
                pathname=record.pathname,
                lineno=record.lineno,
                msg="",  # omit record.msg
                args=(),  # omit record.args
                exc_info=None,  # omit record.exc_info
            )
        )
        first, *trailing = super().format(record).splitlines(keepends=False)
        return (
            first
            + ("\n" if len(trailing) else "")
            + "".join(f"{header[0:-2]}  {line}\n" for line in trailing)[0:-1]
        )


if __name__ == "__main__":
    main()
