from __future__ import annotations

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
        "docs/hardware-test-plan.md",
        "docs/session-handoff.md",
        "docs/validation-history.md",
        "docs/supported-models.md",
    ):
        assert (PACKAGE_ROOT / path).exists()

    for adapter_doc in (
        "docs/cli-integration.md",
        "docs/cli-jsonl-contract.md",
        "docs/Webui-README.md",
    ):
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
            ("docs", "hardware-test-plan.md"),
            ("docs", "session-handoff.md"),
            ("docs", "validation-history.md"),
            ("docs", "supported-models.md"),
        )
    )

    assert "CLI JSONL" not in core_docs
    assert "wrapper artifacts" not in core_docs
    assert "keysight-logger.exe" not in core_docs
    assert "measurement_cli_name" not in core_docs
