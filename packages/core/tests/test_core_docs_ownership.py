from __future__ import annotations

import re
from pathlib import Path

import keysight_logger_core as core


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def read_doc(*parts: str) -> str:
    return PACKAGE_ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_core_docs_are_package_local():
    assert (PACKAGE_ROOT / "README.md").exists()
    assert (PACKAGE_ROOT / "CHANGELOG.md").exists()

    for path in (
        "docs/integration.md",
        "docs/supported-models.md",
    ):
        assert (PACKAGE_ROOT / path).exists()

    adapter_docs = (
        "docs/cli-integration.md",
        f"docs/cli-{'jsonl'}-contract.md",
        f"docs/common-cli-{'jsonl'}-contract.md",
        f"docs/meters-cli-{'jsonl'}-contract.md",
        f"docs/common-{'worker'}-protocol.md",
        f"docs/meters-worker-{'contract'}.md",
        f"docs/common-{'orchestrator'}-workflows.md",
        f"docs/meters-{'orchestrator'}-workflows.md",
        "docs/Webui-README.md",
    )
    for adapter_doc in adapter_docs:
        assert not (PACKAGE_ROOT / adapter_doc).exists()


def test_core_integration_names_public_core_api():
    text = read_doc("docs", "integration.md")

    for name in core.__all__:
        assert name in text

    assert "keysight_logger_core" in text


def test_core_docs_do_not_document_adapter_schema_as_core_contract():
    core_docs = "\n".join(
        read_doc(*path)
        for path in (
            ("README.md",),
            ("docs", "integration.md"),
            ("docs", "supported-models.md"),
        )
    )

    assert "CLI JSONL" not in core_docs
    assert "wrapper artifacts" not in core_docs
    assert "keysight-logger.exe" not in core_docs
    assert "measurement_cli_name" not in core_docs


def test_core_changelog_contains_only_core_release_headings():
    text = read_doc("CHANGELOG.md")
    headings = re.findall(r"^## (.+)$", text, re.MULTILINE)

    for heading in headings:
        if heading == "Unreleased":
            continue
        assert heading.startswith("core-v")
        assert not heading.endswith("-cli")
        assert not heading.endswith("-webui")
