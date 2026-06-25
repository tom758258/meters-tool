from __future__ import annotations

import importlib.metadata
from pathlib import Path

import keysight_logger_core._version as package_version


def test_read_project_version_reads_project_table(tmp_path: Path):
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        '[project]\nname = "example"\nversion = "9.8.7"\n',
        encoding="utf-8",
    )

    assert package_version.read_project_version(pyproject_path) == "9.8.7"


def test_distribution_version_uses_project_version_without_metadata(monkeypatch):
    def missing_metadata(_name: str) -> str:
        raise importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(importlib.metadata, "version", missing_metadata)
    monkeypatch.setattr(package_version, "read_project_version", lambda: "2.3.4")

    assert package_version.get_distribution_version() == "2.3.4"


def test_distribution_version_uses_fallback_when_sources_are_unavailable(monkeypatch):
    def missing_metadata(_name: str) -> str:
        raise importlib.metadata.PackageNotFoundError

    def missing_project() -> str:
        raise FileNotFoundError("pyproject.toml")

    monkeypatch.setattr(importlib.metadata, "version", missing_metadata)
    monkeypatch.setattr(package_version, "read_project_version", missing_project)

    assert package_version.get_distribution_version(fallback="0.0.0") == "0.0.0"
