from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import meters_tool_webui._desktop as desktop_module
from meters_tool_webui._run_manager import CsvFolderSelectionUnavailable


def _fake_picker_owner():
    owner = MagicMock()
    owner.winfo_screenwidth.return_value = 1920
    owner.winfo_screenheight.return_value = 1080
    return owner


@pytest.mark.parametrize("selected", (r"C:\Meter Data", ""))
def test_csv_folder_picker_uses_foreground_native_dialog(monkeypatch, selected) -> None:
    monkeypatch.setattr(desktop_module, "_is_windows", lambda: True)
    owner = _fake_picker_owner()
    with (
        patch("tkinter.Tk", return_value=owner),
        patch("tkinter.filedialog.askdirectory", return_value=selected) as picker,
    ):
        assert desktop_module.select_directory_with_dialog() == (
            Path(selected) if selected else None
        )

    owner.withdraw.assert_called_once_with()
    owner.overrideredirect.assert_called_once_with(True)
    owner.attributes.assert_any_call("-alpha", 0.0)
    owner.attributes.assert_any_call("-topmost", True)
    owner.geometry.assert_called_once_with("1x1+960+540")
    owner.deiconify.assert_called_once_with()
    owner.update.assert_called_once_with()
    owner.lift.assert_called_once_with()
    owner.focus_force.assert_called_once_with()
    picker.assert_called_once_with(
        parent=owner, title="Select CSV output folder", mustexist=True
    )
    owner.destroy.assert_called_once_with()
    assert not desktop_module._FOLDER_PICKER_LOCK.locked()


@pytest.mark.parametrize("fail_on_creation", (False, True))
def test_csv_folder_picker_cleans_up_on_native_failure(monkeypatch, fail_on_creation) -> None:
    monkeypatch.setattr(desktop_module, "_is_windows", lambda: True)
    owner = _fake_picker_owner()
    with (
        patch(
            "tkinter.Tk",
            side_effect=RuntimeError("Tk unavailable") if fail_on_creation else None,
            return_value=owner,
        ),
        patch("tkinter.filedialog.askdirectory", side_effect=RuntimeError("dialog failed")),
    ):
        with pytest.raises(CsvFolderSelectionUnavailable, match="dialog is unavailable") as exc:
            desktop_module.select_directory_with_dialog()

    assert isinstance(exc.value.__cause__, RuntimeError)
    if not fail_on_creation:
        owner.destroy.assert_called_once_with()
    assert not desktop_module._FOLDER_PICKER_LOCK.locked()


def test_csv_folder_picker_rejects_unsupported_platform(monkeypatch) -> None:
    monkeypatch.setattr(desktop_module, "_is_windows", lambda: False)
    with patch.object(desktop_module, "_ask_directory") as picker:
        with pytest.raises(CsvFolderSelectionUnavailable, match="dialog is unavailable"):
            desktop_module.select_directory_with_dialog()
    picker.assert_not_called()


def test_csv_folder_picker_prevents_overlapping_dialogs(monkeypatch) -> None:
    monkeypatch.setattr(desktop_module, "_is_windows", lambda: True)
    with desktop_module._FOLDER_PICKER_LOCK:
        with patch.object(desktop_module, "_ask_directory") as picker:
            with pytest.raises(CsvFolderSelectionUnavailable, match="already open"):
                desktop_module.select_directory_with_dialog()
        picker.assert_not_called()


def test_csv_folder_picker_button_is_disabled_while_waiting() -> None:
    source = (
        Path(__file__).parents[2] / "src" / "meters_tool_webui" / "static" / "app.js"
    ).read_text(encoding="utf-8")
    assert "let csvFolderPickerPending = false;" in source
    assert "if (csvFolderPickerPending) return;" in source
    assert "csvFolderPickerPending = true;" in source
    assert "if (csvFolderPickerPending) selectCsvFolderButton.disabled = true;" in source
    assert "csvFolderPickerPending = false;" in source
