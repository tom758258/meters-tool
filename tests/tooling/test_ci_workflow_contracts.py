"""Protect CI responsibilities and conservative Windows change detection."""

from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"


def change_filters(workflow: str) -> dict[str, list[str]]:
    match = re.search(r"(?m)^\s{10}filters: \|\n((?:\s{12,}.*\n)+)", workflow)
    assert match, "Change detection filters missing"
    filters: dict[str, list[str]] = {}
    group = ""
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if line.endswith(":"):
            group = line[:-1]
            filters[group] = []
        elif line.startswith("- '") and line.endswith("'"):
            filters[group].append(line[3:-1])
    return filters


def affected(filters: dict[str, list[str]], path: str, category: str) -> bool:
    return any(fnmatchcase(path, pattern) for pattern in filters[category])


def test_ci_separates_windows_validation_and_real_packaging_from_release_acceptance():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for job in (
        "quality-webui:",
        "pytest-linux:",
        "pytest-windows:",
        "detect-validation-changes:",
        "windows-validation:",
        "windows-packaging-smoke:",
    ):
        assert f"  {job}" in workflow
    assert "needs: detect-validation-changes" in workflow
    assert "steps.filter.outputs.validation" in workflow
    assert "steps.filter.outputs.packaging" in workflow
    assert "steps.filter.outputs.release_layout" in workflow
    assert "scripts\\release-acceptance.ps1" not in workflow
    assert r".\scripts\build_desktop.ps1" in workflow
    assert r".\scripts\build_release.ps1" in workflow
    assert "tests/packaging/test_release_acceptance.py" in workflow
    assert '-m "not hardware and windows_powershell"' in workflow
    assert "-m frontend_node" in workflow


def test_path_filters_cover_safety_changes_without_building_for_simple_docs():
    filters = change_filters(WORKFLOW.read_text(encoding="utf-8"))
    assert set(filters) == {"validation", "packaging", "release_layout"}
    expected = {
        "README.md": (False, False, False),
        "src/meters_tool_core/acquisition.py": (True, True, False),
        "src/meters_tool_cli/_parser.py": (True, True, False),
        "src/meters_tool_cli/help/cli.html": (False, True, False),
        "src/meters_tool_webui/server.py": (False, True, False),
        "src/meters_tool_cli/cli.py": (True, True, False),
        "src/meters_tool_webui/static/app.js": (False, True, False),
        "desktop/main.cjs": (False, True, False),
        "desktop/package.json": (False, True, True),
        "scripts/_artifact_privacy.ps1": (True, False, False),
        "scripts/_frequency_period_scpi_probe.py": (True, False, False),
        "scripts/_validation_helpers.ps1": (True, False, False),
        "scripts/live-cli-check.ps1": (True, False, False),
        "scripts/check_text_hygiene.py": (False, False, False),
        "scripts/release-acceptance.ps1": (True, False, False),
        "scripts/build_desktop.ps1": (False, True, False),
        "scripts/build_release.ps1": (False, True, True),
        "scripts/meters-tool-windows.spec": (False, True, False),
        "tests/cli/test_live_artifact_privacy.py": (True, False, False),
        "tests/packaging/test_validation_helpers.py": (True, False, False),
        "tests/packaging/test_release_acceptance.py": (True, False, False),
        "docs/help/README.md": (False, True, False),
        "pyproject.toml": (True, True, True),
        ".github/workflows/tests.yml": (True, True, False),
    }
    for path, flags in expected.items():
        actual = tuple(affected(filters, path, category) for category in filters)
        assert actual == flags, (path, actual, flags)
