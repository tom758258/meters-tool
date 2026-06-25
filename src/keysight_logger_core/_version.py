from __future__ import annotations

import importlib.metadata
from pathlib import Path


DISTRIBUTION_NAME = "keysight-logger"
FALLBACK_PACKAGE_VERSION = "1.4.0"


def read_project_version(pyproject_path: Path | None = None) -> str:
    path = pyproject_path or Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        import tomllib
    except ModuleNotFoundError:
        tomllib = None

    if tomllib is not None:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
        return str(data["project"]["version"])

    in_project = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_project = line == "[project]"
            continue
        if in_project and line.startswith("version") and "=" in line:
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError(f"Could not read project version from {path}")


def get_distribution_version(
    *,
    distribution_name: str = DISTRIBUTION_NAME,
    fallback: str = FALLBACK_PACKAGE_VERSION,
) -> str:
    try:
        return importlib.metadata.version(distribution_name)
    except importlib.metadata.PackageNotFoundError:
        pass

    try:
        return read_project_version()
    except (OSError, KeyError, RuntimeError, ValueError):
        return fallback
