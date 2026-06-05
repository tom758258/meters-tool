from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_root_has_no_legacy_source_package():
    assert not (REPO_ROOT / "src" / "keysight_logger").exists()


def test_legacy_import_package_is_absent():
    assert importlib.util.find_spec("keysight_logger") is None


def test_new_import_packages_are_discoverable():
    assert importlib.util.find_spec("keysight_logger_core") is not None
    assert importlib.util.find_spec("keysight_logger_cli") is not None
    assert importlib.util.find_spec("keysight_logger_webui") is not None


def test_root_pyproject_is_tooling_only():
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "[project]" not in text
    assert "[tool.pytest.ini_options]" in text


def test_package_pyprojects_define_distribution_boundaries():
    for path in (
        REPO_ROOT / "packages" / "core" / "pyproject.toml",
        REPO_ROOT / "packages" / "cli" / "pyproject.toml",
        REPO_ROOT / "packages" / "webui" / "pyproject.toml",
    ):
        assert path.exists()


def test_root_docs_are_indexes_not_package_status_logs():
    for relative in (
        "README.md",
        "CHANGELOG.md",
        "docs/session-handoff.md",
        "docs/validation-history.md",
        "docs/project-plan.md",
    ):
        text = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert "packages/core" in text or "packages/cli" in text or "packages/webui" in text
        assert "## Current Status" not in text
        assert "## Active Risks" not in text
        assert "## Next Work" not in text
