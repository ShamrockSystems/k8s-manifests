from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML

from kustomanager.meta import API_KIND, API_VERSION


@dataclass(slots=True, frozen=True)
class Lockfile:
    REPO_URL: str
    REPO_REVISION: str
    BUILD_DIR: Path
    APPLICATIONSET_DIR: Path
    CLUSTERS: list[Cluster]
    BUILDS: list[Build]
    STRUCTURE: map[str, tuple[Cluster, map[str, Build]]]

    @classmethod
    def from_yaml(cls, constructor, node):
        assert node["apiVersion"] == API_VERSION
        assert node["kind"] == API_KIND

        LOCK_REPO_URL = node["repo"]["url"]
        LOCK_REPO_REVISION = node["repo"]["revision"]
        LOCK_BUILD_DIR = Path(node["buildDir"])
        LOCK_APPLICATIONSET_DIR = Path(node["applicationsetDir"])

        LOCK_CLUSTERS = [
            Cluster.from_yaml(constructor, entry) for entry in node["clusters"]
        ]

        LOCK_BUILDS = [Build.from_yaml(constructor, entry) for entry in node["builds"]]

        LOCK_STRUCTURE = {
            cluster.NAME: (
                cluster,
                {
                    build.NAME: build
                    for build in LOCK_BUILDS
                    if build.CLUSTER_NAME == cluster.NAME
                },
            )
            for cluster in LOCK_CLUSTERS
        }

        return Lockfile(
            REPO_URL=LOCK_REPO_URL,
            REPO_REVISION=LOCK_REPO_REVISION,
            BUILD_DIR=LOCK_BUILD_DIR,
            APPLICATIONSET_DIR=LOCK_APPLICATIONSET_DIR,
            CLUSTERS=LOCK_CLUSTERS,
            BUILDS=LOCK_BUILDS,
            STRUCTURE=LOCK_STRUCTURE,
        )


@dataclass(slots=True)
class Build:
    timestamp: int
    source_hash: str
    source_hash_type: str
    source_path: Path
    build_hash: str
    build_hash_type: str
    build_path: Path
    CLUSTER_NAME: str
    NAME: str

    @classmethod
    def from_yaml(cls, constructor, node):
        return Build(
            timestamp=int(node["timestamp"]),
            source_hash=node["sourceHash"],
            source_hash_type=node["sourceHashType"],
            source_path=Path(node["sourcePath"]),
            build_hash=node["buildHash"],
            build_hash_type=node["buildHashType"],
            build_path=Path(node["buildPath"]),
            CLUSTER_NAME=node["cluster"],
            NAME=node["name"],
        )

    @classmethod
    def to_yaml(cls, representer, node: Build):
        return representer.represent_dict(
            {
                "timestamp": node.timestamp,
                "sourceHash": node.source_hash,
                "sourceHashType": node.source_hash_type,
                "sourcePath": node.source_path.as_posix(),
                "buildHash": node.build_hash,
                "buildHashType": node.build_hash_type,
                "buildPath": node.build_path.as_posix(),
                "cluster": node.CLUSTER_NAME,
                "name": node.NAME,
            }
        )


@dataclass(slots=True, frozen=True)
class Cluster:
    NAME: str
    DIRECTORY: Path
    DESTINATION: ArgoDestination

    @classmethod
    def from_yaml(cls, constructor, node) -> Cluster:
        CLUSTER_NAME = node["name"]
        CLUSTER_DIRECTORY = Path(node["directory"])
        ENTRY_DESTINATION = node["destination"]

        assert ("server" in ENTRY_DESTINATION.keys()) != (
            "name" in ENTRY_DESTINATION.keys()
        )
        CLUSTER_DESTINATION: ArgoDestination = (
            ArgoClusterServer(ENTRY_DESTINATION["server"])
            if "server" in ENTRY_DESTINATION.keys()
            else ArgoClusterName(ENTRY_DESTINATION["name"])
        )

        return Cluster(
            NAME=CLUSTER_NAME,
            DIRECTORY=CLUSTER_DIRECTORY,
            DESTINATION=CLUSTER_DESTINATION,
        )


@dataclass(slots=True, frozen=True)
class ArgoClusterServer:
    SERVER: str


@dataclass(slots=True, frozen=True)
class ArgoClusterName:
    NAME: str


ArgoDestination = ArgoClusterServer | ArgoClusterName


def get_yaml() -> YAML:
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.register_class(Build)
    yaml.register_class(Cluster)
    yaml.register_class(Lockfile)
    return yaml
