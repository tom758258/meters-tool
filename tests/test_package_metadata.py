from __future__ import annotations

from pathlib import Path

from keysight_logger.cli import main


def _read_pyproject(pyproject_path: Path) -> dict:
    try:
        import tomllib
    except ModuleNotFoundError:
        tomllib = None

    if tomllib is not None:
        with pyproject_path.open("rb") as fh:
            return tomllib.load(fh)

    project: dict[str, str] = {}
    scripts: dict[str, str] = {}
    section = None

    for raw_line in pyproject_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line.strip("[]")
            continue
        if "=" not in line:
            continue

        name, value = line.split("=", 1)
        value = value.strip().strip('"')
        if section == "project":
            project[name.strip()] = value
        elif section == "project.scripts":
            scripts[name.strip()] = value

    return {"project": project, "project.scripts": scripts}


def test_keysight_logger_console_script_points_to_cli_main():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"

    pyproject = _read_pyproject(pyproject_path)
    project = pyproject["project"]
    scripts = pyproject.get("project.scripts", project.get("scripts", {}))

    assert project["name"] == "keysight-logger"
    assert project["version"] == "1.1.6"
    assert scripts["keysight-logger"] == "keysight_logger.cli:main"
    assert callable(main)
