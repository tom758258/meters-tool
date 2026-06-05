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

    project: dict[str, object] = {}
    scripts: dict[str, str] = {}
    optional_dependencies: dict[str, list[str]] = {}
    package_data: dict[str, list[str]] = {}
    section = None
    active_array: tuple[dict[str, object] | dict[str, list[str]], str] | None = None

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
        key = name.strip()
        value = value.strip()
        if section == "project":
            if value == "[":
                project[key] = []
                active_array = (project, key)
            else:
                project[key] = value.strip('"')
        elif section == "project.optional-dependencies":
            if value == "[":
                optional_dependencies[key] = []
                active_array = (optional_dependencies, key)
        elif section == "project.scripts":
            scripts[key] = value.strip('"')
        elif section == "tool.setuptools.package-data":
            package_data[key] = [
                item.strip().strip('"')
                for item in value.strip("[]").split(",")
                if item.strip()
            ]

    return {
        "project": {**project, "optional-dependencies": optional_dependencies},
        "project.scripts": scripts,
        "tool": {"setuptools": {"package-data": package_data}},
    }


def test_webui_distribution_uses_adapter_metadata_and_console_script():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"

    pyproject = _read_pyproject(pyproject_path)
    project = pyproject["project"]
    scripts = pyproject.get("project.scripts", project.get("scripts", {}))
    dependencies = project["dependencies"]
    dev_dependencies = pyproject["project"]["optional-dependencies"]["dev"]

    assert project["name"] == "keysight-logger-webui"
    assert project["version"] == "1.1.0"
    assert "FastAPI" in project["description"] or "Web UI" in project["description"]
    assert "keysight-logger-core>=1.1.1,<1.2" in dependencies
    assert any(str(item).startswith("fastapi") for item in dependencies)
    assert any(str(item).startswith("uvicorn") for item in dependencies)
    assert any(str(item).startswith("httpx") for item in dev_dependencies)
    assert scripts == {"keysight-logger-webui": "keysight_logger_webui.web_ui:main"}
    assert pyproject["tool"]["setuptools"]["package-data"] == {
        "keysight_logger_webui": ["static/*"]
    }
    assert importlib.util.find_spec("keysight_logger") is None
    assert importlib.util.find_spec("keysight_logger_webui") is not None
