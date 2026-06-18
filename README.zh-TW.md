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

首先開啟 PowerShell 並進入專案根目錄：

```powershell
cd path\to\Keysight_Meters_Logger
```

如果尚未安裝 uv，請先安裝 uv：

```powershell
py -m pip install --user uv
```

驗證 uv：

```powershell
uv --version
```

在專案資料夾中建立專案虛擬環境：

```powershell
uv venv .venv
```

從 `uv.lock` 同步可重現的開發和測試環境：

```powershell
uv sync --all-extras --link-mode=copy
```

若用於 CI 或嚴格的本機檢查，要求已提交的 lock 檔案保持不變：

```powershell
uv sync --all-extras --locked --link-mode=copy
```

本專案支援 Python `>=3.10`。`uv venv .venv` 會使用目前可用的相容 Python。如果您需要特定的 Python 版本，請明確要求：

```powershell
uv venv .venv --python 3.12
```

`uv.lock` 檔案是供 uv 用於開發與 CI 的重現性。`pip install .` 讀取的是 `pyproject.toml` 而非 `uv.lock`。未使用 uv 的使用者若要使用鎖定環境，必須先安裝 uv。

如果您直接需要使用 pip，請使用虛擬環境中的 Python：

```powershell
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe -m pip install ".[webui]"
.\.venv\Scripts\python.exe -m pip install -e ".[all,dev]"
```

Windows 會建立 virtualenv console wrappers，例如
`.\.venv\Scripts\keysight-logger.exe`、
`.\.venv\Scripts\keysight-logger-webui.exe`、以及
`.\.venv\Scripts\keysight-logger-webui-launcher.exe`。

## 建置

建置 wheel 與 source distribution。這會使用上面安裝的 `dev` 額外相依套件中的 `build` 套件：

```powershell
.\.venv\Scripts\python.exe -m build
```

這會產生僅一個 Python distribution：

```text
dist\keysight_logger-1.4.0-py3-none-any.whl
dist\keysight_logger-1.4.0.tar.gz
```

獨立執行檔是獨立的 PyInstaller 工作流程。在建置 exe 產物之前，請先安裝 PyInstaller：

```powershell
uv pip install pyinstaller --python .\.venv\Scripts\python.exe
```

如果您的虛擬環境直接使用 pip：

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
```

建置獨立的 CLI 和 WebUI 啟動器執行檔：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_cli_exe.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_webui_exe.ps1
```

預設情況下，這些命令會產生：

```text
dist\keysight-logger.exe
dist\keysight-logger-webui-launcher.exe
```

建置包含 wheel、sdist、獨立執行檔與總和檢查碼（checksums）的 release 資料夾：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_release.ps1
```

這會產生帶有版本號的 release 產物：

```text
release\1.4.0\keysight-logger-1.4.0.exe
release\1.4.0\keysight-logger-webui-launcher-1.4.0.exe
release\1.4.0\keysight_logger-1.4.0-py3-none-any.whl
release\1.4.0\keysight_logger-1.4.0.tar.gz
release\1.4.0\checksums.txt
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

* [Core README](docs/core/README.zh-TW.md)
* [CLI README](docs/cli/README.zh-TW.md)
* [WebUI README](docs/webui/README.zh-TW.md)
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
