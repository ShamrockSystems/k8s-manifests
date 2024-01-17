import logging
import sys
import time
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

TIMESTAMP = int(time.time())
logger = logging.getLogger("cli")


def main():
    cli.add_command(add)
    cli.add_command(build)
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


def load_lockfile(yaml: YAML) -> tuple[Any, dict]:
    LOCKFILE_PATH = Path(Path.cwd(), LOCKFILE_NAME)

    lockfile = yaml.load(LOCKFILE_PATH)

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
