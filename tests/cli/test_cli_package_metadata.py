from __future__ import annotations

from pathlib import Path

from keysight_logger_cli.cli import FALLBACK_CLI_VERSION, get_cli_version, main


def _read_pyproject(pyproject_path: Path) -> dict:
    try:
        import tomllib
    except ModuleNotFoundError:
        tomllib = None

    if tomllib is not None:
        with pyproject_path.open("rb") as fh:
            return tomllib.load(fh)

    project: dict[str, object] = {}
    scripts: dict[str, str] = {}
    section = None
    active_array: tuple[dict[str, object], str] | None = None

    for raw_line in pyproject_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if active_array is not None:
            target, key = active_array
            if line == "]":
                active_array = None
                continue
            target[key].append(line.rstrip(",").strip('"'))  # type: ignore[index, union-attr]
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line.strip("[]")
            continue
        if "=" not in line:
            continue

        name, value = line.split("=", 1)
        value = value.strip()
        if section == "project":
            key = name.strip()
            if value == "[":
                project[key] = []
                active_array = (project, key)
            else:
                project[key] = value.strip('"')
        elif section == "project.scripts":
            scripts[name.strip()] = value.strip('"')

    return {"project": project, "project.scripts": scripts}


def test_keysight_logger_console_script_points_to_cli_main():
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"

    pyproject = _read_pyproject(pyproject_path)
    project = pyproject["project"]
    scripts = pyproject.get("project.scripts", project.get("scripts", {}))
    dependencies = project["dependencies"]

    assert project["name"] == "keysight-logger"
    assert project["version"] == FALLBACK_CLI_VERSION
    assert scripts["keysight-logger"] == "keysight_logger_cli.cli:main"
    assert "pyvisa>=1.14.1" in dependencies
    assert not any(str(item).startswith("keysight-logger-core") for item in dependencies)
    assert callable(main)


def test_cli_version_uses_fallback_when_metadata_and_pyproject_are_unavailable(monkeypatch):
    import importlib.metadata

    def missing_metadata(_name: str) -> str:
        raise importlib.metadata.PackageNotFoundError

    def missing_project() -> str:
        raise FileNotFoundError("pyproject.toml")

    monkeypatch.setattr(importlib.metadata, "version", missing_metadata)
    monkeypatch.setattr("keysight_logger_cli.cli._read_project_version", missing_project)

    assert get_cli_version() == FALLBACK_CLI_VERSION
