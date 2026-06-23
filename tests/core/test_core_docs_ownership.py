from __future__ import annotations

import re
from pathlib import Path

import keysight_logger_core as core


REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_ROOT = REPO_ROOT / "docs" / "core"


def read_doc(*parts: str) -> str:
    return DOC_ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_core_docs_are_package_local():
    assert (DOC_ROOT / "README.md").exists()
    assert (DOC_ROOT / "CHANGELOG.md").exists()

    for path in (
        "integration.md",
        "supported-models.md",
    ):
        assert (DOC_ROOT / path).exists()

    adapter_docs = (
        "docs/cli-integration.md",
        f"docs/cli-{'jsonl'}-contract.md",
        f"docs/common-cli-{'jsonl'}-contract.md",
        f"docs/meters-cli-{'jsonl'}-contract.md",
        f"docs/common-{'worker'}-protocol.md",
        f"docs/meters-worker-{'contract'}.md",
        f"docs/common-{'orchestrator'}-workflows.md",
        f"docs/meters-{'orchestrator'}-workflows.md",
        f"docs/Webui-{'README'}.md",
    )
    for adapter_doc in adapter_docs:
        assert not (DOC_ROOT / adapter_doc).exists()


def test_core_integration_names_public_core_api():
    text = read_doc("integration.md")

    for name in core.__all__:
        assert name in text

    assert "keysight_logger_core" in text


def test_core_integration_uses_package_boundary_wording():
    text = read_doc("integration.md")

    assert "Core package public contract" in text
    assert "keysight_logger_core" in text

    obsolete_branch_terms = (
        "Core branch",
        "CLI branch",
        "Adapter branches",
        "adapter branches",
        "merge Core",
        "on this branch",
    )
    for term in obsolete_branch_terms:
        assert term not in text


def test_core_docs_do_not_document_adapter_schema_as_core_contract():
    core_docs = "\n".join(
        read_doc(*path)
        for path in (
            ("README.md",),
            ("integration.md",),
            ("supported-models.md",),
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
        assert re.fullmatch(r"v\d+\.\d+\.\d+", heading)
        assert not heading.startswith("core-v")
        assert not heading.startswith("cli-v")
        assert not heading.startswith("webui-v")
