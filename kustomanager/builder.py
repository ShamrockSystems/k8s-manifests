import logging
import shutil
import subprocess
from pathlib import Path

from kustomanager.template import j2_env

logger = logging.getLogger("builder")


def build_from_source(kustomization_directory: Path, target_directory: Path):
    build_data = invoke_kustomize(kustomization_directory)

    if target_directory.exists():
        shutil.rmtree(target_directory)
    target_directory.mkdir(parents=True, exist_ok=True)

    kustomization_template = j2_env.get_template("kustomization.build.yaml.j2")

    with open(Path(target_directory, "build.yaml"), "w", encoding="utf-8") as f:
        f.write(build_data)
    with open(Path(target_directory, "kustomization.yaml"), "w", encoding="utf-8") as f:
        f.write(kustomization_template.render())


def invoke_kustomize(
    path: Path,
    command: str = "kustomize",
    enable_helm: bool = True,
    enable_alpha_plugins: bool = True,
    enable_network: bool = True,
) -> str:
    args: list[str] = []
    args.append(command)
    args.append("build")
    args.append(path.absolute().as_posix())
    if enable_helm:
        args.append("--enable-helm")
    if enable_alpha_plugins:
        args.append("--enable-alpha-plugins")
    if enable_network:
        args.append("--network")
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
    return result.stdout
