from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote


REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_HEADING_PATTERN = re.compile(r"v([0-9]+\.[0-9]+\.[0-9]+)")
UNRELEASED_TARGET_PATTERN = re.compile(
    r"Unreleased — target v([0-9]+\.[0-9]+\.[0-9]+)"
)
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
TRADITIONAL_MARKDOWN_PATHS = (
    "README.zh-TW.md",
    "docs/cli/README.zh-TW.md",
    "docs/cli/USER_GUIDE.zh-TW.md",
    "docs/core/README.zh-TW.md",
    "docs/skill/EXAMPLES.zh-TW.md",
    "docs/skill/README.zh-TW.md",
    "docs/webui/README.zh-TW.md",
    "docs/webui/USER_GUIDE.zh-TW.md",
)
TRADITIONAL_MARKDOWN_TOKEN_REQUIREMENTS = {
    "docs/cli/README.zh-TW.md": (
        "keysight-34460a",
        "keysight-34461a",
        "USB/system-VISA",
        "LAN/TCPIP",
        "live_validated_full_suite",
        "transport_pending",
        "--visa-library",
        "--validation-allow-pending-live-support",
        "private/",
        "shareable/",
    ),
    "docs/webui/README.zh-TW.md": (
        "keysight-34460a",
        "keysight-34461a",
        "USB/system-VISA",
        "LAN/TCPIP",
        "live_validated_full_suite",
        "transport_pending",
    ),
}


def read_project_version() -> str:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', text, re.MULTILINE)
    assert match is not None
    return match.group(1)


def parse_semver_tuple(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)", value)
    assert match is not None
    return tuple(int(part) for part in match.groups())


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
    assert 'version = "2.0.0"' in text
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


def test_changelog_release_direction_matches_package_metadata():
    current_version = read_project_version()
    changelogs = (
        REPO_ROOT / "CHANGELOG.md",
        REPO_ROOT / "docs" / "core" / "CHANGELOG.md",
        REPO_ROOT / "docs" / "cli" / "CHANGELOG.md",
        REPO_ROOT / "docs" / "webui" / "CHANGELOG.md",
    )

    release_headings = []
    for changelog in changelogs:
        text = changelog.read_text(encoding="utf-8")
        headings = re.findall(r"^## (.+)$", text, re.MULTILINE)
        assert headings, changelog
        if headings[0] == "Unreleased":
            headings = headings[1:]
            assert headings, changelog
        release_headings.append(headings[0])

    assert len(set(release_headings)) == 1
    first_heading = release_headings[0]

    released_match = RELEASE_HEADING_PATTERN.fullmatch(first_heading)
    if released_match:
        assert released_match.group(1) == current_version
        return

    target_match = UNRELEASED_TARGET_PATTERN.fullmatch(first_heading)
    assert target_match is not None
    target_version = target_match.group(1)
    assert parse_semver_tuple(target_version) > parse_semver_tuple(current_version)


def test_readme_markdown_links_point_to_existing_local_targets():
    readmes = (
        REPO_ROOT / "README.md",
        REPO_ROOT / "README.zh-TW.md",
        REPO_ROOT / "docs" / "core" / "README.md",
        REPO_ROOT / "docs" / "cli" / "README.md",
        REPO_ROOT / "docs" / "webui" / "README.md",
        REPO_ROOT / "docs" / "CONTRIBUTING.md",
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


def test_expected_traditional_chinese_markdown_inventory_has_english_pairs():
    tracked = set(
        subprocess.run(
            ["git", "ls-files", "*.zh-TW.md"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    )

    assert tracked == set(TRADITIONAL_MARKDOWN_PATHS)
    for relative in TRADITIONAL_MARKDOWN_PATHS:
        translated = REPO_ROOT / relative
        source = REPO_ROOT / relative.replace(".zh-TW.md", ".md")
        assert translated.exists()
        assert source.exists()


def _markdown_heading_slugs(text: str) -> set[str]:
    slugs = set()
    for line in text.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match is None:
            continue
        heading = re.sub(r"[`*_]", "", match.group(1)).lower()
        heading = re.sub(r"[^\w\-\u4e00-\u9fff ]", "", heading)
        slugs.add(re.sub(r"\s+", "-", heading))
    return slugs


def test_traditional_chinese_markdown_links_and_anchors_are_valid():
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    missing = []

    for relative in TRADITIONAL_MARKDOWN_PATHS:
        path = REPO_ROOT / relative
        text = path.read_text(encoding="utf-8")
        for match in link_pattern.finditer(text):
            target = match.group(1).strip()
            if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE):
                continue

            path_part, separator, fragment = target.partition("#")
            candidate = (
                path
                if not path_part
                else (path.parent / unquote(path_part)).resolve()
            )
            try:
                candidate.relative_to(REPO_ROOT)
            except ValueError:
                missing.append(f"{relative}: escapes repo: {target}")
                continue
            if not candidate.exists():
                missing.append(f"{relative}: missing {target}")
                continue
            if separator and candidate.suffix.lower() == ".md":
                headings = _markdown_heading_slugs(candidate.read_text(encoding="utf-8"))
                if unquote(fragment).lower() not in headings:
                    missing.append(f"{relative}: missing heading anchor {target}")

    assert not missing, "\n".join(missing)


def test_traditional_chinese_docs_preserve_high_risk_canonical_tokens():
    for translated_relative, tokens in TRADITIONAL_MARKDOWN_TOKEN_REQUIREMENTS.items():
        translated = (REPO_ROOT / translated_relative).read_text(encoding="utf-8")
        source_relative = translated_relative.replace(".zh-TW.md", ".md")
        source = (REPO_ROOT / source_relative).read_text(encoding="utf-8")
        for token in tokens:
            assert token in source, f"English source lost required token {token}: {source_relative}"
            assert token in translated, (
                f"Traditional Chinese translation lost required token {token}: "
                f"{translated_relative}"
            )


def test_traditional_chinese_docs_preserve_current_support_and_runtime_boundaries():
    webui_readme = (REPO_ROOT / "docs" / "webui" / "README.zh-TW.md").read_text(
        encoding="utf-8"
    )
    assert "34460A，DCV Ratio 在 USB/system-VISA 上為 `Product-open`" in webui_readme
    assert "34460A LAN/TCPIP system-VISA" in webui_readme
    assert "LAN/TCPIP pyvisa-py `@py`" in webui_readme
    assert "`transport_pending`" in webui_readme
    assert "12-case wrapper full suite" in webui_readme
    assert "不延伸至 LAN 或 pyvisa-py" in webui_readme
    assert not re.search(r"34460A[^\n。]*DCV Ratio[^\n。]*feature_pending", webui_readme)

    cli_user_guide = (REPO_ROOT / "docs" / "cli" / "USER_GUIDE.zh-TW.md").read_text(
        encoding="utf-8"
    )
    assert "連接儀器的 `*IDN?` 決定 runtime profile" in cli_user_guide
    assert "只是 expected-model guard" in cli_user_guide
    assert "selected model 絕不會覆寫 IDN-selected profile" in cli_user_guide
    assert "live mismatch 會在 setup SCPI 前失敗" in cli_user_guide
    assert "dry-run 或 simulator" in cli_user_guide
    assert "selected model 選擇 profile" in cli_user_guide

    webui_user_guide = (REPO_ROOT / "docs" / "webui" / "USER_GUIDE.zh-TW.md").read_text(
        encoding="utf-8"
    )
    assert "baseline +/- span` 的值會被裁切到圖表邊界" in webui_user_guide
    assert "不會另外顯示 `clipped indicator`" in webui_user_guide
    assert "baseline +/- selected Range` 的值可能會被裁切到圖表邊界" in webui_user_guide


def test_traditional_chinese_markdown_has_no_bom():
    violations = []
    for relative in TRADITIONAL_MARKDOWN_PATHS:
        if (REPO_ROOT / relative).read_bytes().startswith(b"\xef\xbb\xbf"):
            violations.append(relative)
    assert not violations, "UTF-8 BOM found in Traditional Chinese Markdown:\n" + "\n".join(
        violations
    )


def test_root_readme_links_to_the_contributor_guide():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    guide = REPO_ROOT / "docs" / "CONTRIBUTING.md"

    assert guide.exists()
    assert "[Contributing Guide](docs/CONTRIBUTING.md)" in readme
    assert "--validation-allow-pending-live-support" not in readme


def test_english_support_docs_cover_feature_pending_policy():
    paths = (
        REPO_ROOT / "docs" / "core" / "integration.md",
        REPO_ROOT / "docs" / "core" / "supported-models.md",
        REPO_ROOT / "docs" / "cli" / "cli-integration.md",
        REPO_ROOT / "docs" / "cli" / "README.md",
        REPO_ROOT / "docs" / "webui" / "README.md",
        REPO_ROOT / "docs" / "CONTRIBUTING.md",
    )

    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "feature_pending" in text, path

    contributing = (REPO_ROOT / "docs" / "CONTRIBUTING.md").read_text(
        encoding="utf-8"
    )
    assert "--validation-allow-pending-live-support" in contributing
    assert "Missing feature metadata is not `feature_pending`" in contributing
