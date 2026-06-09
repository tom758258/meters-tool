from __future__ import annotations

import re
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]


def read_doc(*parts: str) -> str:
    return PACKAGE_ROOT.joinpath(*parts).read_text(encoding="utf-8")


def read_contract(*parts: str) -> str:
    return REPO_ROOT.joinpath("docs", "contracts", *parts).read_text(encoding="utf-8")


def test_cli_docs_are_package_local_and_contracts_are_root_level():
    assert (PACKAGE_ROOT / "README.md").exists()
    assert (PACKAGE_ROOT / "CHANGELOG.md").exists()

    for path in (
        "docs/cli-integration.md",
    ):
        assert (PACKAGE_ROOT / path).exists()

    assert not (PACKAGE_ROOT / "docs" / f"README_CLI_{'EN'}.md").exists()

    removed_contracts = (
        f"docs/cli-{'jsonl'}-contract.md",
        f"docs/cli-{'orchestrator'}-workflows.md",
        f"docs/common-{'worker'}-protocol.md",
        f"docs/worker-{'contract'}.md",
    )
    for removed_contract in removed_contracts:
        assert not (PACKAGE_ROOT / removed_contract).exists()

    for contract in (
        "common-worker-protocol.md",
        "common-cli-jsonl-contract.md",
        "meters-cli-jsonl-contract.md",
        "common-orchestrator-workflows.md",
        "meters-orchestrator-workflows.md",
        "meters-worker-contract.md",
    ):
        assert (REPO_ROOT / "docs" / "contracts" / contract).exists()

    assert not (PACKAGE_ROOT / "docs" / f"Webui-{'README'}.md").exists()


def test_cli_integration_keeps_cli_fields_out_of_core_schema():
    text = read_doc("docs", "cli-integration.md")

    assert "measurement_cli_name" in text
    assert "not Core schema" in text
    assert "argparse.Namespace" in text
    assert "`--enable-hw-trigger` was removed" in text
    assert "packages/core/docs/integration.md" in text


def test_cli_integration_uses_package_boundary_wording():
    text = read_doc("docs", "cli-integration.md")

    assert "The CLI package owns" in text
    assert "packages/core/docs/integration.md" in text

    obsolete_branch_terms = (
        "Core branch",
        "CLI branch",
        "Adapter branches",
        "adapter branches",
        "merge Core",
        "on this branch",
        "This CLI branch",
    )
    for term in obsolete_branch_terms:
        assert term not in text


def test_cli_docs_do_not_link_removed_or_webui_guides():
    text = "\n".join(
        read_doc(*path)
        for path in (
            ("README.md",),
            ("docs", "cli-integration.md"),
        )
    )

    forbidden = (
        f"README_CLI_{'EN'}.md",
        f"README_CLI_{'ZH-TW'}.md",
        f"README_UI_{'EN'}.md",
        f"README_UI_{'ZH-TW'}.md",
        f"Webui-{'README'}.md",
        f"docs/{'webui'}-integration.md",
        "packages/webui/README.md",
        "packages/webui/docs/",
    )
    for value in forbidden:
        assert value not in text


def test_cli_changelog_contains_only_cli_release_headings():
    text = read_doc("CHANGELOG.md")
    headings = re.findall(r"^## (.+)$", text, re.MULTILINE)

    for heading in headings:
        if heading == "Unreleased":
            continue
        assert heading.startswith("cli-v")
        assert not heading.startswith("core-v")
        assert not heading.startswith("webui-v")


def test_common_worker_protocol_is_lifecycle_only():
    text = read_contract("common-worker-protocol.md")

    assert "lifecycle-only" in text
    assert "GET /status" in text
    assert "POST /command" in text
    assert "POST /stop" in text
    assert "does not define `POST /start`" in text
    assert "`command`" in text
    assert "`arguments`" in text
    assert "`job_id`" in text
    assert "Meters" not in text
    assert "Keysight" not in text
    assert "34461A" not in text


def test_worker_contract_documents_cross_instrument_boundary():
    text = read_contract("meters-worker-contract.md")

    assert "Cross-Instrument Compatibility" in text
    assert "Common Worker Protocol" in text
    assert "Meters worker contract only" in text
    assert "GET /status" in text
    assert "`GET /status`, `POST /command`, `POST /stop`" in text
    assert "does not change state" in text
    assert "mutate queues" in text


def test_cli_jsonl_contract_documents_v16_command_and_status_clients():
    text = read_contract("meters-cli-jsonl-contract.md")

    assert "Runtime contract revision: `v1.6`" in text
    assert "tracks this document's evolution only" in text
    assert "must use the JSON `schema_version` field" in text
    assert "must not use the document revision for runtime negotiation" in text
    assert "`summary`:" in text
    assert "`ok`" in text
    assert "optional `fatal_error`" in text
    assert "`summary.ok` is `true`" in text
    assert "status" in text
    assert "wait-ready" in text
    assert "client `--timeout-ms`" in text
    assert "Consumers must ignore unknown fields" in text
    assert "client_command" in text
    assert "request_sent" in text
    assert "elapsed_ms" in text
    assert "endpoint" in text
    assert "invalid or empty" in text
    assert "`command`, `job_id`, `reason`, `error`, and `message`" in text


def test_common_contracts_stay_instrument_neutral():
    text = "\n".join(
        read_contract(path)
        for path in (
            "common-worker-protocol.md",
            "common-cli-jsonl-contract.md",
            "common-orchestrator-workflows.md",
        )
    )

    for forbidden in ("Meters", "Keysight", "34461A", "VISA", "SCPI", "acquisition"):
        assert forbidden not in text


def test_meters_contracts_preserve_meters_specific_safety_semantics():
    cli_contract = read_contract("meters-cli-jsonl-contract.md")
    worker_contract = read_contract("meters-worker-contract.md")

    assert "fatal acquisition failures" in cli_contract
    assert "must exit `3`" in cli_contract
    assert "GET /status" in worker_contract
    assert "trigger measurement" in worker_contract
    assert "touch VISA" in worker_contract


def test_meters_contracts_link_common_contracts():
    cli_contract = read_contract("meters-cli-jsonl-contract.md")
    workflow_contract = read_contract("meters-orchestrator-workflows.md")
    worker_contract = read_contract("meters-worker-contract.md")

    assert "common-cli-jsonl-contract.md" in cli_contract
    assert "common-orchestrator-workflows.md" in workflow_contract
    assert "common-worker-protocol.md" in worker_contract
