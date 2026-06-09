from __future__ import annotations

import re
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def read_doc(*parts: str) -> str:
    return PACKAGE_ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_webui_docs_are_package_local():
    assert (PACKAGE_ROOT / "README.md").exists()
    assert (PACKAGE_ROOT / "CHANGELOG.md").exists()

    for path in (
        "docs/USER_GUIDE.md",
        "docs/web-ui-ai-change-rules.md",
    ):
        assert (PACKAGE_ROOT / path).exists()

    assert not (PACKAGE_ROOT / "docs" / f"Webui-{'README'}.md").exists()

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
        assert not (PACKAGE_ROOT / cli_doc).exists()


def test_webui_readme_uses_webui_entrypoint_not_cli_workflow():
    text = read_doc("README.md")

    assert "keysight-logger.exe" not in text
    assert "python -m keysight_logger_cli" not in text
    assert "python -m keysight_logger_webui.web_ui" not in text
    assert "pip install -r" not in text
    assert "requirements.txt" not in text
    assert "uv sync" not in text
    assert "start-trigger-record" not in text
    assert "keysight-logger-webui" in text


def test_webui_docs_point_to_new_import_and_static_paths():
    text = "\n".join(
        read_doc(*path)
        for path in (
            ("README.md",),
            ("docs", "web-ui-ai-change-rules.md"),
        )
    )

    assert "keysight_logger_webui" in text
    assert "keysight_logger_core" in text
    assert "packages/webui/src/keysight_logger_webui/static" in text


def test_webui_changelog_contains_only_webui_release_headings():
    text = read_doc("CHANGELOG.md")
    headings = re.findall(r"^## (.+)$", text, re.MULTILINE)

    for heading in headings:
        if heading == "Unreleased":
            continue
        assert heading.startswith("webui-v")
        assert not heading.startswith("core-v")
        assert not heading.startswith("cli-v")
