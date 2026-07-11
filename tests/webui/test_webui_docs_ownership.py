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
