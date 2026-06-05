from __future__ import annotations

import importlib.util
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_project_version(package: str) -> str:
    text = (REPO_ROOT / "packages" / package / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', text, re.MULTILINE)
    assert match is not None
    return match.group(1)


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
        "docs/architecture/monorepo-layout.md",
        "docs/contracts/meters-cli-jsonl-contract.md",
        "docs/contracts/meters-worker-contract.md",
    ):
        text = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert "## Current Status" not in text
        assert "## Active Risks" not in text
        assert "## Next Work" not in text


def test_public_markdown_avoids_local_private_context():
    public_roots = (
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "README.md",
        REPO_ROOT / "CHANGELOG.md",
        REPO_ROOT / "docs",
        REPO_ROOT / "packages",
    )
    public_markdown = []
    for root in public_roots:
        if root.is_file():
            public_markdown.append(root)
            continue
        public_markdown.extend(root.rglob("*.md"))

    forbidden_patterns = {
        "personal Windows user path": re.compile(r"C:\\Users\\tom", re.IGNORECASE),
        "personal drive path": re.compile(r"(?:D:\\Tom|E:\\Git)", re.IGNORECASE),
        "pytest user temp path": re.compile(r"pytest-of-tom", re.IGNORECASE),
        "real 34461A serial": re.compile(r"\bMY\d{8}\b"),
        "concrete USB VISA resource": re.compile(r"USB0::0x[0-9A-Fa-f]+"),
        "link-local lab IP": re.compile(r"\b169\.254\.\d+\.\d+\b"),
        "local notes path": re.compile(r"Local[\\/]"),
        "session handoff filename": re.compile(r"session-handoff", re.IGNORECASE),
        "validation history filename": re.compile(r"validation-history", re.IGNORECASE),
        "hardware test plan filename": re.compile(r"hardware-test-plan", re.IGNORECASE),
        "project plan filename": re.compile(r"project-plan", re.IGNORECASE),
        "private note reference": re.compile(r"private local", re.IGNORECASE),
        "handoff notes reference": re.compile(r"handoff notes", re.IGNORECASE),
        "handoff routing reference": re.compile(r"handoff routing", re.IGNORECASE),
        "historical AC sanity status": re.compile(r"real-signal sanity checks", re.IGNORECASE),
        "historical live instrument status": re.compile(
            r"checked on a real instrument", re.IGNORECASE
        ),
        "rough live instrument status": re.compile(r"rough real-instrument", re.IGNORECASE),
    }

    violations = []
    for path in sorted(public_markdown):
        text = path.read_text(encoding="utf-8")
        for label, pattern in forbidden_patterns.items():
            for match in pattern.finditer(text):
                line_number = text.count("\n", 0, match.start()) + 1
                relative = path.relative_to(REPO_ROOT).as_posix()
                violations.append(f"{relative}:{line_number}: {label}: {match.group(0)!r}")

    assert not violations, "\n".join(violations)


def test_public_package_versions_match_package_metadata():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    architecture = (REPO_ROOT / "docs" / "architecture" / "monorepo-layout.md").read_text(
        encoding="utf-8"
    )

    packages = {
        "core": ("Core", "keysight-logger-core", "keysight_logger_core"),
        "cli": ("CLI", "keysight-logger-cli", "keysight_logger_cli"),
        "webui": ("WebUI", "keysight-logger-webui", "keysight_logger_webui"),
    }
    for package, (label, distribution, import_name) in packages.items():
        version = read_project_version(package)

        assert (
            f"`packages/{package}`: `{distribution}` `{version}`, imported as `{import_name}`"
            in readme
        )
        assert f"| {label} | `{distribution}` | `{import_name}` | `{version}` |" in architecture
