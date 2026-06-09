from __future__ import annotations

from pathlib import Path


RUNNABLE_MODULE_PATTERNS = (
    r".\.venv\Scripts\python.exe -m keysight_logger_cli ",
    "python -m keysight_logger_cli ",
)


def test_active_docs_prefer_console_script_for_runnable_cli_examples():
    repo_root = Path(__file__).resolve().parents[1]
    forbidden_docs = [
        repo_root / "docs" / "cli-integration.md",
    ]

    for path in forbidden_docs:
        text = path.read_text(encoding="utf-8")
        for pattern in RUNNABLE_MODULE_PATTERNS:
            assert pattern not in text, f"{path} contains runnable module-form CLI example"


def test_cli_guide_module_form_only_appears_as_explicit_alternative():
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "README.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    context_terms = ("fallback", "alternative", "development")
    for line_number, line in enumerate(lines):
        if not any(pattern in line for pattern in RUNNABLE_MODULE_PATTERNS):
            continue

        window = "\n".join(lines[max(0, line_number - 4) : line_number + 5]).lower()
        assert any(term in window for term in context_terms), (
            "module-form CLI examples must be framed as fallback, alternative, "
            f"or development usage near line {line_number + 1}"
        )
