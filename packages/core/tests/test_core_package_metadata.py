from __future__ import annotations

import importlib.util
from pathlib import Path


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


def test_core_distribution_has_no_console_script():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"

    pyproject = _read_pyproject(pyproject_path)
    project = pyproject["project"]
    scripts = pyproject.get("project.scripts", project.get("scripts", {}))

    assert project["name"] == "keysight-logger-core"
    assert project["version"] == "1.1.1"
    assert scripts == {}
    assert importlib.util.find_spec("keysight_logger") is None


def test_core_source_does_not_import_adapters():
    source_root = Path(__file__).resolve().parents[1] / "src" / "keysight_logger_core"
    forbidden = ("keysight_logger_cli", "keysight_logger_webui")
    violations = []

    for path in source_root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in forbidden:
            if term in text:
                violations.append(f"{path.name} imports {term}")

    assert violations == []
