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
        "docs/cli-jsonl-contract.md",
        "docs/worker-contract.md",
        "docs/hardware-test-plan.md",
        "docs/session-handoff.md",
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
