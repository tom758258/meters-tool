from __future__ import annotations

from pathlib import Path

import keysight_logger.core as core


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_doc(*parts: str) -> str:
    return (REPO_ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def test_integration_docs_are_indexed():
    readme = read_doc("README.md")
    project_plan = read_doc("docs", "project-plan.md")
    indexed_text = readme + "\n" + project_plan

    for doc in (
        "docs/core-integration.md",
        "docs/cli-integration.md",
        "docs/webui-integration.md",
        "docs/common-worker-protocol.md",
        "docs/cli-jsonl-contract.md",
        "docs/cli-orchestrator-workflows.md",
        "docs/worker-contract.md",
        "docs/hardware-test-plan.md",
        "docs/session-handoff.md",
        "docs/cli-session-handoff.md",
        "docs/validation-history.md",
    ):
        assert doc in indexed_text


def test_core_integration_names_public_core_api():
    text = read_doc("docs", "core-integration.md")

    for name in core.__all__:
        assert name in text

    assert "package-root imports from `keysight_logger.core`" in text or (
        "Prefer package-root imports from `keysight_logger.core`" in text
    )


def test_cli_integration_keeps_cli_fields_out_of_core_schema():
    text = read_doc("docs", "cli-integration.md")

    assert "measurement_cli_name" in text
    assert "not Core schema" in text
    assert "argparse.Namespace" in text
    assert "`--enable-hw-trigger` was removed" in text


def test_webui_integration_forbids_cli_json_scraping():
    text = read_doc("docs", "webui-integration.md")

    assert "Do not scrape CLI" in text
    assert "CLI JSON/JSONL is not the required WebUI wire format" in text
    assert "measurement_cli_name" in text


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


def test_legacy_root_core_shim_modules_are_absent():
    deleted_shims = {
        "acquisition.py",
        "capabilities.py",
        "instrument.py",
        "instrument_backend.py",
        "measurement.py",
        "models.py",
        "run_plan.py",
        "runner.py",
        "session.py",
        "simulator.py",
        "storage.py",
        "trigger.py",
        "validation.py",
    }

    package_root = REPO_ROOT / "src" / "keysight_logger"
    existing = {path.name for path in package_root.glob("*.py")}

    assert deleted_shims.isdisjoint(existing)


def test_core_files_do_not_depend_on_cli_concerns():
    forbidden_terms = {
        "argparse",
        "measurement_cli_name",
        "status_format",
        "enable_hw_trigger",
        "exit_code",
        "keysight_logger.cli",
    }
    core_root = REPO_ROOT / "src" / "keysight_logger" / "core"

    violations = []
    for path in core_root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for term in forbidden_terms:
            if term in text:
                violations.append(f"{path.relative_to(REPO_ROOT)} contains {term}")

    assert violations == []
