from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_ROOT = REPO_ROOT / "docs" / "webui"
UNRELEASED_TARGET_PATTERN = re.compile(
    r"Unreleased — target v[0-9]+\.[0-9]+\.[0-9]+"
)
RELEASE_HEADING_PATTERN = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+")


def read_doc(*parts: str) -> str:
    return DOC_ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_webui_docs_are_package_local():
    assert (DOC_ROOT / "README.md").exists()
    assert (DOC_ROOT / "CHANGELOG.md").exists()

    for path in (
        "USER_GUIDE.md",
        "localization-contract.md",
        "web-ui-change-rules.md",
    ):
        assert (DOC_ROOT / path).exists()

    assert not (DOC_ROOT / f"Webui-{'README'}.md").exists()
    assert not (DOC_ROOT / f"web-ui-{'ai'}-change-rules.md").exists()

    cli_docs = (
        "docs/cli-integration.md",
        f"docs/cli-{'jsonl'}-contract.md",
        f"docs/common-cli-{'jsonl'}-contract.md",
        f"docs/meters-cli-{'jsonl'}-contract.md",
        f"docs/common-{'worker'}-protocol.md",
        f"docs/meters-worker-{'contract'}.md",
        f"docs/common-{'orchestrator'}-workflows.md",
        f"docs/meters-{'orchestrator'}-workflows.md",
        f"docs/worker-{'contract'}.md",
        f"docs/README_CLI_{'EN'}.md",
    )
    for cli_doc in cli_docs:
        assert not (DOC_ROOT / cli_doc).exists()


def test_webui_readme_uses_webui_entrypoint_not_cli_workflow():
    text = read_doc("README.md")

    assert "meters-tool.exe" not in text
    assert "python -m meters_tool_cli" not in text
    assert "python -m meters_tool_webui.web_ui" not in text
    assert "pip install -r" not in text
    assert "requirements.txt" not in text
    assert "uv sync" not in text
    assert "start-trigger-record" not in text
    assert "meters-tool-webui" in text


def test_webui_docs_point_to_new_import_and_static_paths():
    text = "\n".join(
        read_doc(*path)
        for path in (
            ("README.md",),
            ("web-ui-change-rules.md",),
        )
    )

    assert "meters_tool_webui" in text
    assert "meters_tool_core" in text
    assert "src/meters_tool_webui/static" in text


def test_webui_changelog_contains_only_webui_release_headings():
    text = read_doc("CHANGELOG.md")
    headings = re.findall(r"^## (.+)$", text, re.MULTILINE)

    for heading in headings:
        if heading == "Unreleased":
            continue
        if UNRELEASED_TARGET_PATTERN.fullmatch(heading):
            continue
        assert RELEASE_HEADING_PATTERN.fullmatch(heading)
        assert not heading.startswith("webui-v")
        assert not heading.startswith("core-v")
        assert not heading.startswith("cli-v")


def test_webui_maintainer_docs_link_to_localization_contract():
    link = "[WebUI Localization Contract](localization-contract.md)"

    assert link in read_doc("README.md")
    assert link in read_doc("web-ui-change-rules.md")


def test_webui_localization_contract_records_stable_locale_decisions():
    text = read_doc("localization-contract.md")
    normalized = " ".join(text.lower().split())

    assert "`en`" in text
    assert "`zh-TW`" in text
    assert "English fallback" in text
    assert "meters-tool.webui.locale" in text
    assert "raw machine values" in text
    assert "display-only" in text
    assert "p2.6 activates browser locale selection" in normalized
    assert "p2.7 completes the final translation-quality review" in normalized
    assert "| Auto range control label | 自動量程（Auto range） |" in text
    assert "| Auto range in prose and compact summaries | 自動量程 |" in text


def test_webui_localization_contract_protects_machine_contracts_and_part_ownership():
    text = read_doc("localization-contract.md")

    for protected_contract in (
        "API fields",
        "canonical values",
        "runtime schemas",
    ):
        assert protected_contract in text

    for part in range(1, 8):
        assert f"P2.{part}" in text
