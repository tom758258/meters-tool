[English](README.md)

# Keysight Logger

Keysight Logger 是給 Keysight 34461A 數位萬用電表使用的 Python 資料擷取與紀錄工具。此專案現在只發布一個 distribution：`keysight-logger` `1.4.0`，但仍保留三個既有 Python import package：`keysight_logger_core`、`keysight_logger_cli`、`keysight_logger_webui`。

它支援透過 VISA 進行 DC/AC 電流、DC/AC 電壓、DC 電壓比，以及 2 線式或 4 線式電阻量測。每筆樣本都會寫入 CSV，包含時間戳、量測類型、單位、觸發來源與相關 metadata。

## 功能

* 透過 USB 或 LAN 使用 VISA 控制 Keysight 34461A
* 設定量測 range、NPLC、Auto Zero、AC bandwidth、current terminal 與 DC voltage input impedance
* 支援 software、timer、external hardware、immediate 與 buffered trigger workflows
* 使用 dry-run 預覽儀器命令
* 使用內建 simulator 在沒有硬體時測試 workflow
* 可透過 CLI 或本機 WebUI 操作
* 提供 JSON 與 JSONL 輸出，方便自動化、agent 與 orchestrator 整合

## 專案結構

此 repository 現在只有一個 distribution 與一個版本號：

* Distribution：`keysight-logger` `1.4.0`
* Core import：`keysight_logger_core`
* CLI import：`keysight_logger_cli`
* WebUI import：`keysight_logger_webui`

三個 import path 仍彼此獨立，不使用 `keysight_logger.*` namespace package。

```text
src/
  keysight_logger_core/
  keysight_logger_cli/
  keysight_logger_webui/
tests/
  core/
  cli/
  webui/
docs/
  core/
  cli/
  webui/
scripts/
```

## 安裝

開發安裝，包含 CLI、WebUI、測試與 build 工具：

```powershell
uv venv .venv
uv pip install -e ".[all,dev]" --link-mode=copy
```

只安裝基本 Core/CLI：

```powershell
pip install .
```

安裝 WebUI dependencies：

```powershell
pip install ".[webui]"
```

Windows 會建立 virtualenv console wrappers，例如
`.\.venv\Scripts\keysight-logger.exe`、
`.\.venv\Scripts\keysight-logger-webui.exe`、以及
`.\.venv\Scripts\keysight-logger-webui-launcher.exe`。

## 建置

建置 wheel 與 source distribution：

```powershell
.\.venv\Scripts\python.exe -m build
```

輸出會是一個 Python distribution：

```text
dist\keysight_logger-1.4.0-py3-none-any.whl
dist\keysight_logger-1.4.0.tar.gz
```

Standalone executable 是獨立的 PyInstaller 流程：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_cli_exe.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_webui_exe.ps1
```

建立 release 資料夾，包含 wheel、sdist、standalone executable 與 checksums：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_release.ps1
```

## 測試

迭代時可先跑 focused tests：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\core -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\cli -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\webui -q -p no:cacheprovider
```

完整 no-hardware suite：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

如果 Windows 暫存目錄權限阻擋 pytest，請改用 repository-local 暫存目錄：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --basetemp .tmp_tests\pytest_tmp
```

## 文件

* [Core README](docs/core/README.md)
* [CLI README](docs/cli/README.md)
* [WebUI README](docs/webui/README.md)
* [WebUI User Guide](docs/webui/USER_GUIDE.md)
* [Monorepo Architecture](docs/architecture/monorepo-layout.md)
* [Testing Guidelines](docs/testing-guidelines.md)
* [Public Contracts](docs/contracts)
* [Meters CLI JSONL Contract](docs/contracts/meters-cli-jsonl-contract.md)
* [Meters Worker Contract](docs/contracts/meters-worker-contract.md)

## 授權與聲明

本專案採用 MIT License，請見 [LICENSE](LICENSE)。

本專案是獨立且非官方的專案，並非 Keysight Technologies 所屬、背書或贊助。

使用者需自行遵守所有適用的 Keysight 軟體、driver、儀器與文件授權條款。
