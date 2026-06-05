from __future__ import annotations

from pathlib import Path

import keysight_logger.core as core


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_doc(*parts: str) -> str:
    return REPO_ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_webui_docs_index_core_contract_and_adapter_docs():
    readme = read_doc("README.md")
    project_plan = read_doc("docs", "project-plan.md")
    indexed_text = readme + "\n" + project_plan

    for doc in (
        "docs/core-integration.md",
        "docs/Webui-README.md",
        "docs/web-ui-ai-change-rules.md",
        "docs/web-ui-session-handoff.md",
        "docs/hardware-test-plan.md",
        "docs/session-handoff.md",
        "docs/validation-history.md",
        "docs/supported-models.md",
        "docs/project-plan.md",
    ):
        assert doc in indexed_text

    for removed_doc in (
        "docs/cli-integration.md",
        "docs/cli-jsonl-contract.md",
        "docs/worker-contract.md",
        "docs/README_CLI_EN.md",
    ):
        assert removed_doc not in indexed_text
        assert not REPO_ROOT.joinpath(removed_doc).exists()


def test_core_integration_names_public_core_api():
    text = read_doc("docs", "core-integration.md")

    for name in core.__all__:
        assert name in text

    assert "package-root imports from `keysight_logger.core`" in text


def test_core_contract_stays_separate_from_webui_adapter_docs():
    core_docs = "\n".join(
        read_doc(*path)
        for path in (
            ("docs", "core-integration.md"),
            ("docs", "supported-models.md"),
        )
    )

    assert "CLI JSONL" not in core_docs
    assert "wrapper artifacts" not in core_docs
    assert "keysight-logger" + ".exe" not in core_docs
    assert "measurement_cli" + "_name" not in core_docs

    core_contract = read_doc("docs", "core-integration.md")
    assert "outside the Core schema" in core_contract


def test_webui_readme_uses_webui_entrypoint_not_cli_workflow():
    text = read_doc("README.md")

    assert "keysight-logger" + ".exe" not in text
    assert "python -m keysight_logger" + ".cli" not in text
    assert "python -m keysight_logger" + ".web_ui" not in text
    assert "pip install -r" not in text
    assert "requirements.txt" not in text
    assert "uv sync" not in text
    assert "start-trigger-record" not in text
    assert 'uv pip install -e ".[dev]" --link-mode=copy' in text
    assert ".venv\\Scripts\\keysight-logger-webui.exe" in text
