from __future__ import annotations

from pathlib import Path


RUNNABLE_MODULE_PATTERNS = (
    r".\.venv\Scripts\python.exe -m keysight_logger_cli ",
    "python -m keysight_logger_cli ",
)


def test_active_docs_prefer_console_script_for_runnable_cli_examples():
    repo_root = Path(__file__).resolve().parents[1]
    forbidden_docs = [
        repo_root / "README.md",
        repo_root / "docs" / "cli-integration.md",
    ]

    for path in forbidden_docs:
        text = path.read_text(encoding="utf-8")
        for pattern in RUNNABLE_MODULE_PATTERNS:
            assert pattern not in text, f"{path} contains runnable module-form CLI example"


def test_cli_guide_module_form_only_appears_as_explicit_alternative():
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "docs" / "README_CLI_EN.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    module_lines = [
        line
        for line in lines
        if any(pattern in line for pattern in RUNNABLE_MODULE_PATTERNS)
    ]

    assert module_lines == [
        r".\.venv\Scripts\python.exe -m keysight_logger_cli <command> [options]",
        r".\.venv\Scripts\python.exe -m keysight_logger_cli <command> [options]",
    ]
