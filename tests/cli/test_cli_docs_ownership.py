from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_ROOT = REPO_ROOT / "docs" / "cli"


def read_doc(*parts: str) -> str:
    return DOC_ROOT.joinpath(*parts).read_text(encoding="utf-8")


def read_contract(*parts: str) -> str:
    return REPO_ROOT.joinpath("docs", "contracts", *parts).read_text(encoding="utf-8")


def test_cli_docs_are_package_local_and_contracts_are_root_level():
    assert (DOC_ROOT / "README.md").exists()

    for path in (
        "cli-integration.md",
    ):
        assert (DOC_ROOT / path).exists()

    assert not (DOC_ROOT / f"README_CLI_{'EN'}.md").exists()

    removed_contracts = (
        f"docs/cli-{'jsonl'}-contract.md",
        f"docs/cli-{'orchestrator'}-workflows.md",
        f"docs/common-{'worker'}-protocol.md",
        f"docs/worker-{'contract'}.md",
    )
    for removed_contract in removed_contracts:
        assert not (DOC_ROOT / removed_contract).exists()

    for contract in (
        "common-worker-protocol.md",
        "common-cli-jsonl-contract.md",
        "meters-cli-jsonl-contract.md",
        "common-orchestrator-workflows.md",
        "meters-orchestrator-workflows.md",
        "meters-worker-contract.md",
    ):
        assert (REPO_ROOT / "docs" / "contracts" / contract).exists()

    assert not (DOC_ROOT / f"Webui-{'README'}.md").exists()


def test_cli_integration_keeps_cli_fields_out_of_core_schema():
    text = read_doc("cli-integration.md")

    assert "measurement_cli_name" in text
    assert "argparse.Namespace" in text
    assert "docs/core/integration.md" in text


def test_cli_integration_uses_package_boundaries():
    text = read_doc("cli-integration.md")

    assert "meters_tool_cli" in text
    assert "docs/core/integration.md" in text

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
            ("cli-integration.md",),
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


def test_cli_user_guides_do_not_depend_on_developer_or_webui_docs():
    forbidden_paths = (
        "README.md",
        "README.zh-TW.md",
        "cli-integration.md",
        "../core/integration.md",
        "../contracts/",
        "../webui/",
        "../../CHANGELOG.md",
    )

    for filename in ("USER_GUIDE.md", "USER_GUIDE.zh-TW.md"):
        text = read_doc(filename)
        for path in forbidden_paths:
            assert path not in text


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
    assert "common-worker-protocol.md" in text
    assert "GET /status" in text
    assert "POST /command" in text
    assert "POST /stop" in text


def test_cli_jsonl_contract_documents_v3_worker_and_independent_cli_machine_fields():
    text = read_contract("meters-cli-jsonl-contract.md")

    for metadata in (
        "Worker schema version: `3`",
        "Independent single-response CLI schema version: `2`",
        "Compatibility policy: `v3-only`",
        "Runtime contract revision: `v3.0`",
    ):
        assert metadata in text

    assert "`schema_version: 2`" in text
    for field in (
        "schema_version",
        "event",
        "summary",
        "ok",
        "fatal_error",
        "client_command",
        "request_sent",
        "elapsed_ms",
        "endpoint",
        "command",
        "job_id",
        "reason",
        "error",
        "message",
        "csv_enabled",
        "csv_path",
        "dry_run_writes_csv",
        "capability_profile",
        "runtime_identity",
        "available_profiles",
        "transport_scope",
        "feature_kind",
    ):
        assert field in text


def test_orchestrator_contract_documents_owned_complete_run_history():
    text = read_contract("meters-orchestrator-workflows.md")

    for artifact in (
        "request.json",
        "stdout.jsonl",
        "stderr.txt",
        "result.json",
        "samples.csv",
    ):
        assert artifact in text
    for result_input in ("scheduler job", "run_id", "summary", "process exit code"):
        assert result_input in text
    assert "orchestrator-owned examples" in text
    assert "not Meters Worker artifact names" in text


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
    assert "instrument I/O" in worker_contract
    assert "Status reads perform no instrument I/O" in worker_contract


def test_meters_contracts_link_common_contracts():
    cli_contract = read_contract("meters-cli-jsonl-contract.md")
    workflow_contract = read_contract("meters-orchestrator-workflows.md")
    worker_contract = read_contract("meters-worker-contract.md")

    assert "common-cli-jsonl-contract.md" in cli_contract
    assert "common-orchestrator-workflows.md" in workflow_contract
    assert "common-worker-protocol.md" in worker_contract
