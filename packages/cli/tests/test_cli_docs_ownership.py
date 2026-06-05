from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def read_doc(*parts: str) -> str:
    return PACKAGE_ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_cli_docs_are_package_local():
    assert (PACKAGE_ROOT / "README.md").exists()
    assert (PACKAGE_ROOT / "CHANGELOG.md").exists()

    for path in (
        "docs/cli-integration.md",
        "docs/cli-jsonl-contract.md",
        "docs/cli-orchestrator-workflows.md",
        "docs/common-worker-protocol.md",
        "docs/worker-contract.md",
        "docs/README_CLI_EN.md",
        "docs/session-handoff.md",
        "docs/validation-history.md",
    ):
        assert (PACKAGE_ROOT / path).exists()

    assert not (PACKAGE_ROOT / "docs/Webui-README.md").exists()


def test_cli_integration_keeps_cli_fields_out_of_core_schema():
    text = read_doc("docs", "cli-integration.md")

    assert "measurement_cli_name" in text
    assert "not Core schema" in text
    assert "argparse.Namespace" in text
    assert "`--enable-hw-trigger` was removed" in text


def test_common_worker_protocol_is_lifecycle_only():
    text = read_doc("docs", "common-worker-protocol.md")

    assert "lifecycle-only" in text
    assert "GET /status" in text
    assert "POST /trigger" in text
    assert "POST /stop" in text
    assert "does not define `POST /start`" in text
    assert "does not define" in text and "generic" in text and "`POST /command`" in text


def test_worker_contract_documents_cross_instrument_boundary():
    text = read_doc("docs", "worker-contract.md")

    assert "Cross-Instrument Compatibility" in text
    assert "Common Worker Protocol" in text
    assert "Meters worker contract only" in text
    assert "GET /status" in text
    assert "does not change state" in text
    assert "mutate queues" in text


def test_cli_jsonl_contract_documents_v15_status_clients():
    text = read_doc("docs", "cli-jsonl-contract.md")

    assert "Runtime contract revision: `v1.5`" in text
    assert "`summary`:" in text
    assert "`ok`" in text
    assert "optional `fatal_error`" in text
    assert "`summary.ok` is `true`" in text
    assert "soft-status" in text
    assert "wait-ready" in text
    assert "client `--timeout-ms`" in text
    assert "Consumers must ignore unknown fields" in text
    assert "client_command" in text
    assert "request_sent" in text
    assert "elapsed_ms" in text
    assert "endpoint" in text
