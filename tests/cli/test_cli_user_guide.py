from __future__ import annotations

import io
from contextlib import redirect_stderr
from unittest.mock import Mock

import pytest

import meters_tool_cli
from meters_tool_cli.cli import _resolve_user_guide_path, main


@pytest.mark.parametrize(
    ("argv", "filename"),
    [
        (["user-guide"], "cli.html"),
        (["user-guide", "--lang", "zh-TW"], "cli.zh-TW.html"),
    ],
)
def test_user_guide_opens_expected_local_file(monkeypatch, argv, filename) -> None:
    expected_path = _resolve_user_guide_path("zh-TW" if "zh-TW" in argv else "en")
    assert expected_path.name == filename
    assert expected_path.is_file()

    opener = Mock(return_value=True)
    monkeypatch.setattr("meters_tool_cli.cli.webbrowser.open_new_tab", opener)

    stderr = io.StringIO()
    with redirect_stderr(stderr):
        rc = main(argv)

    assert rc == 0
    opener.assert_called_once()
    assert opener.call_args.args[0] == expected_path.as_uri()


@pytest.mark.parametrize(
    ("language", "filename"),
    [("en", "cli.html"), ("zh-TW", "cli.zh-TW.html")],
)
def test_user_guide_uses_package_location_in_packaged_layout(
    monkeypatch, tmp_path, language, filename
) -> None:
    import meters_tool_cli.cli as cli_module

    package_dir = tmp_path / "_internal" / "meters_tool_cli"
    help_dir = package_dir / "help"
    help_dir.mkdir(parents=True)
    (help_dir / filename).write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(meters_tool_cli, "__file__", str(package_dir / "__init__.py"))
    monkeypatch.setattr(cli_module, "__file__", str(tmp_path / "_internal" / "cli.py"))

    opener = Mock(return_value=True)
    monkeypatch.setattr(cli_module.webbrowser, "open_new_tab", opener)
    assert main(["user-guide", "--lang", language]) == 0
    opener.assert_called_once_with((help_dir / filename).as_uri())


def test_user_guide_browser_failure_returns_non_zero(monkeypatch) -> None:
    expected_path = _resolve_user_guide_path("en")
    assert expected_path.is_file()

    opener = Mock(return_value=False)
    monkeypatch.setattr("meters_tool_cli.cli.webbrowser.open_new_tab", opener)

    stderr = io.StringIO()
    with redirect_stderr(stderr):
        rc = main(["user-guide"])

    assert rc == 1
    opener.assert_called_once_with(expected_path.as_uri())
    assert str(expected_path) in stderr.getvalue()



