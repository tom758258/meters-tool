from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def test_traditional_chinese_public_docs_use_quick_check_terminology():
    paths = (
        "README.zh-TW.md",
        "docs/cli/README.zh-TW.md",
        "docs/cli/USER_GUIDE.zh-TW.md",
        "docs/webui/README.zh-TW.md",
        "docs/webui/USER_GUIDE.zh-TW.md",
        "docs/skill/README.zh-TW.md",
    )
    forbidden = ("煙霧測試", "冒煙測試", "smoke validation")
    for relative in paths:
        text = read(relative)
        for term in forbidden:
            assert term not in text, f"{relative}: unexpected {term!r}"


def test_traditional_chinese_docs_preserve_current_public_contracts():
    root_readme = read("README.zh-TW.md")
    assert "docs/skill/README.zh-TW.md" in root_readme

    cli_readme = read("docs/cli/README.zh-TW.md")
    assert "34460A 的 DC 電壓比例" in cli_readme
    assert "USB／系統 VISA" in cli_readme
    assert "不延伸至 34460A LAN/TCPIP 或 pyvisa-py" in cli_readme

    webui_readme = read("docs/webui/README.zh-TW.md")
    for endpoint in (
        "GET /api/resources?verify=true&live_only=true",
        "POST /api/runs",
        "GET /api/runs/current",
        "GET /api/runs/current/events",
        "POST /api/runs/current/command",
        "POST /api/runs/current/stop",
        "POST /api/runs/current/open-csv",
        "POST /api/csv/select-folder",
    ):
        assert endpoint in webui_readme
    for obsolete in (
        "/api/scan_resources",
        "/api/start",
        "/api/stop",
        "/api/trigger",
        "/api/status",
        "/api/select_folder",
        "/api/open_csv",
    ):
        assert obsolete not in webui_readme

    webui_guide = read("docs/webui/USER_GUIDE.zh-TW.md")
    assert "共有四種模式" in webui_guide
    assert "Auto deviation" in webui_guide
