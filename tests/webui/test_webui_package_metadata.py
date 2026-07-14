from __future__ import annotations

import importlib.util
from pathlib import Path

from meters_tool_webui.web_ui import FALLBACK_WEBUI_VERSION


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
            if value == "[":
                package_data[key] = []
                active_array = (package_data, key)
            else:
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
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"

    pyproject = _read_pyproject(pyproject_path)
    project = pyproject["project"]
    scripts = pyproject.get("project.scripts", project.get("scripts", {}))
    dependencies = project["dependencies"]
    webui_dependencies = pyproject["project"]["optional-dependencies"]["webui"]
    dev_dependencies = pyproject["project"]["optional-dependencies"]["dev"]
    all_dependencies = pyproject["project"]["optional-dependencies"]["all"]

    assert project["name"] == "meters-tool"
    assert project["version"] == "2.0.0"
    assert project["version"] == FALLBACK_WEBUI_VERSION
    assert "WebUI" in project["description"]
    assert "pyvisa>=1.14.1" in dependencies
    assert not any(str(item).startswith("meters-tool-core") for item in dependencies)
    assert any(str(item).startswith("fastapi") for item in webui_dependencies)
    assert any(str(item).startswith("uvicorn") for item in webui_dependencies)
    assert all_dependencies == webui_dependencies
    assert any(str(item).startswith("httpx") for item in dev_dependencies)
    assert scripts["meters-tool"] == "meters_tool_cli.cli:main"
    assert scripts["meters-tool-webui"] == "meters_tool_webui.web_ui:main"
    assert scripts["meters-tool-webui-launcher"] == "meters_tool_webui.launcher:main"
    assert pyproject["tool"]["setuptools"]["package-data"] == {
        "meters_tool_webui": ["static/*.html", "static/*.css", "static/*.js"]
    }
    assert importlib.util.find_spec("meters_tool") is None
    assert importlib.util.find_spec("meters_tool_webui") is not None
