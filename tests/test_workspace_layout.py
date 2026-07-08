from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote


REPO_ROOT = Path(__file__).resolve().parents[1]
TEXT_FILE_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


def read_project_version() -> str:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', text, re.MULTILINE)
    assert match is not None
    return match.group(1)


def test_root_has_no_legacy_source_package():
    assert not (REPO_ROOT / "src" / "meters_tool").exists()


def test_legacy_import_package_is_absent():
    assert importlib.util.find_spec("meters_tool") is None


def test_old_keysight_import_packages_are_absent():
    assert importlib.util.find_spec("keysight_logger") is None
    assert importlib.util.find_spec("keysight_logger_core") is None
    assert importlib.util.find_spec("keysight_logger_cli") is None
    assert importlib.util.find_spec("keysight_logger_webui") is None


def test_new_import_packages_are_discoverable():
    assert importlib.util.find_spec("meters_tool_core") is not None
    assert importlib.util.find_spec("meters_tool_cli") is not None
    assert importlib.util.find_spec("meters_tool_webui") is not None


def test_root_pyproject_defines_single_distribution():
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'name = "meters-tool"' in text
    assert 'version = "1.6.0"' in text
    assert 'meters-tool = "meters_tool_cli.cli:main"' in text
    assert 'meters-tool-webui = "meters_tool_webui.web_ui:main"' in text
    assert "[tool.pytest.ini_options]" in text
    assert 'pythonpath = ["src"]' in text


def test_package_pyprojects_are_removed():
    for path in (
        REPO_ROOT / "packages" / "core" / "pyproject.toml",
        REPO_ROOT / "packages" / "cli" / "pyproject.toml",
        REPO_ROOT / "packages" / "webui" / "pyproject.toml",
    ):
        assert not path.exists()


def test_component_layout_is_rooted():
    for path in (
        REPO_ROOT / "src" / "meters_tool_core",
        REPO_ROOT / "src" / "meters_tool_cli",
        REPO_ROOT / "src" / "meters_tool_webui",
        REPO_ROOT / "tests" / "core",
        REPO_ROOT / "tests" / "cli",
        REPO_ROOT / "tests" / "webui",
        REPO_ROOT / "docs" / "core",
        REPO_ROOT / "docs" / "cli",
        REPO_ROOT / "docs" / "webui",
        REPO_ROOT / "scripts",
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


def test_tracked_text_files_are_utf8_without_bom():
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    violations = []
    for relative in result.stdout.splitlines():
        path = REPO_ROOT / relative
        if not path.exists():
            continue
        if path.suffix.lower() not in TEXT_FILE_SUFFIXES:
            continue
        if path.read_bytes().startswith(b"\xef\xbb\xbf"):
            violations.append(relative)

    assert not violations, "UTF-8 BOM found in tracked text files:\n" + "\n".join(violations)


def test_public_package_versions_match_package_metadata():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    architecture = (REPO_ROOT / "docs" / "architecture" / "monorepo-layout.md").read_text(
        encoding="utf-8"
    )
    version = read_project_version()

    assert "`meters-tool` `<version>`" in readme
    assert "`[project].version`" in readme
    for import_name in (
        "meters_tool_core",
        "meters_tool_cli",
        "meters_tool_webui",
    ):
        assert f"`{import_name}`" in readme
        assert f"`{import_name}`" in architecture
    assert version
    assert "`[project].version`" in architecture
    assert "| Distribution | `meters-tool` | `<version>` |" in architecture
    assert "distribution version" in architecture


def test_current_version_is_latest_release_in_all_changelogs():
    version = read_project_version()
    changelogs = (
        REPO_ROOT / "CHANGELOG.md",
        REPO_ROOT / "docs" / "core" / "CHANGELOG.md",
        REPO_ROOT / "docs" / "cli" / "CHANGELOG.md",
        REPO_ROOT / "docs" / "webui" / "CHANGELOG.md",
    )

    for changelog in changelogs:
        text = changelog.read_text(encoding="utf-8")
        headings = re.findall(r"^## (v\d+\.\d+\.\d+)$", text, re.MULTILINE)
        assert headings, changelog
        assert headings[0] == f"v{version}", changelog


def test_readme_markdown_links_point_to_existing_local_targets():
    readmes = (
        REPO_ROOT / "README.md",
        REPO_ROOT / "README.zh-TW.md",
        REPO_ROOT / "docs" / "core" / "README.md",
        REPO_ROOT / "docs" / "cli" / "README.md",
        REPO_ROOT / "docs" / "webui" / "README.md",
    )
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    missing = []

    for readme in readmes:
        text = readme.read_text(encoding="utf-8")
        for match in link_pattern.finditer(text):
            target = match.group(1).strip()
            if (
                not target
                or target.startswith("#")
                or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE)
            ):
                continue

            path_part = unquote(target.split("#", 1)[0])
            if not path_part:
                continue
            candidate = (readme.parent / path_part).resolve()
            try:
                candidate.relative_to(REPO_ROOT)
            except ValueError:
                missing.append(f"{readme.relative_to(REPO_ROOT).as_posix()}: escapes repo: {target}")
                continue
            if not candidate.exists():
                missing.append(f"{readme.relative_to(REPO_ROOT).as_posix()}: missing {target}")

    assert not missing, "\n".join(missing)
