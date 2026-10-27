[English](README.md)

# Meters Tool

Meters Tool 是供支援的數位萬用電表使用的 Python 資料擷取與紀錄工具，涵蓋 Keysight 34460A 與 34461A；確切的產品支援範圍請參閱 [支援型號](docs/core/supported-models.zh-TW.md)。單一發行套件 `meters-tool` 包含獨立的 Core、CLI 與 WebUI 套件。

支援 VISA 的 DC／AC 電壓與電流、DC 電壓比、頻率、週期，以及 2 線式／4 線式電阻量測。預設每筆樣本輸出時間戳記、數值及單位的精簡 `data` CSV；若需保留觸發與量測 metadata，可用 CLI `--csv-format full` 或 WebUI/Desktop `Full`，並可附加 elapsed 與 sample interval 欄位。CLI `--no-csv` 或 WebUI `CSV 輸出` 可停用 CSV；CLI `--streaming --json` 預設不儲存 CSV，需指定 `--csv PATH` 才會儲存。

System VISA 需要另行安裝執行環境；隨附的 PyVISA-py 可用於正式支援的 34461A TCPIP 連線。dry-run 與模擬模式不需要 VISA 執行環境。

## 功能特性

* 透過 VISA 控制支援的數位萬用電表
* 設定量測範圍 (range)、NPLC、Auto Zero、AC 頻寬、電流端子及 DC 電壓輸入阻抗
* 執行 immediate、software（可用 `--timer-interval-s` 計時）、external hardware 與 custom/buffered 觸發工作流程
* 透過 dry-run 預覽儀器命令
* 使用內建模擬器在無硬體環境測試工作流程
* 透過 CLI 或本機 WebUI 操作
* 使用 CLI 與 WebUI/Desktop 提供的英文、繁體中文內建離線說明／使用指南
* 在瀏覽器 WebUI 即時切換英文與繁體中文，不重新載入頁面或重設執行、表單、樣本、圖表及 UI 狀態，並記住語言選擇
* 輸出 JSON 與 JSONL，供自動化、agent 及 orchestrator 使用
* 預設輸出含時間戳記的 CSV，可用 CLI `--no-csv` 或 WebUI `CSV 輸出` 核取方塊停用

實機啟動透過 `*IDN?` 偵測型號；手動指定的型號僅用於預期型號比對，不能解鎖其他儀器功能。Core 依型號、傳輸方式、Backend、量測與觸發模式執行 fail-closed 支援檢查；詳見 [支援型號](docs/core/supported-models.zh-TW.md)。

## 專案結構

`meters-tool` 是單一發行套件，`<version>` 取自根目錄 `pyproject.toml` 的 `[project].version`：

* 發行套件 (Distribution)：`meters-tool` `<version>`
* Core import：`meters_tool_core`
* CLI import：`meters_tool_cli`
* WebUI import：`meters_tool_webui`

import 路徑彼此獨立。請不要使用 `meters_tool.*` namespace package。

```text
src/
  meters_tool_core/
  meters_tool_cli/
  meters_tool_webui/
desktop/
tests/
  core/
  cli/
  help/
  packaging/
  webui/
docs/
  architecture/
  cli/
  contracts/
  core/
  help/
  webui/
scripts/
```

## 安裝

在 PowerShell 進入專案根目錄：

```powershell
cd path\to\meters-tool
```

安裝 uv（若尚未安裝），並確認可執行：

```powershell
py -m pip install --user uv
```

```powershell
uv --version
```

建立虛擬環境，並依 `uv.lock` 同步開發與測試相依套件：

```powershell
uv venv .venv
```

```powershell
uv sync --all-extras --link-mode=copy
```

CI 或嚴格本機驗證使用鎖定模式：

```powershell
uv sync --all-extras --locked --link-mode=copy
```

支援 Python `>=3.10`。`uv venv` 會選擇相容版本，也可明確指定：

```powershell
uv venv .venv --python 3.12
```

Windows 會在 `.venv\Scripts\` 建立 `meters-tool.exe`、`meters-tool-webui.exe` 及 `meters-tool-webui-launcher.exe`。若既有環境缺少這些命令入口，可只重新安裝專案套件：

```powershell
uv sync --all-extras --link-mode=copy --reinstall-package meters-tool
```

此修復通常不適用於新建的虛擬環境，也不需要另行使用 pip。

## 快速開始

先以模擬器安全測試 CLI（不需要硬體）：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource SIM::34461A `
  --simulate `
  --measurement voltage-dc `
  --trigger-mode immediate `
  --max-samples 1 `
  --csv .tmp_tests\quick-start-simulator.csv `
  --status-format jsonl
```

啟動 WebUI 主控台伺服器：

```powershell
.\.venv\Scripts\meters-tool-webui.exe --host 127.0.0.1 --port 8767
```

或使用 WebUI Launcher：

```powershell
.\.venv\Scripts\meters-tool-webui-launcher.exe
```

Launcher 僅繫結本機 loopback，預設從 Port `8767` 搜尋最多 100 個可用 Port，確認 WebUI capabilities identity 後開啟瀏覽器。`--port 9000` 固定 Port；`--port 9000 --auto-port` 從 `9000` 開始搜尋。

開發 Desktop shell 時，從 `desktop/` 啟動 Electron：

```powershell
cd desktop
npm ci
npm start
```

Desktop 開發模式透過專案 `.venv` 使用同一個私有 FastAPI/WebUI host；Electron 不另建 frontend。

實機預設透過 `pyvisa.ResourceManager("@ivi")` 使用 System VISA；CLI 可指定 `--visa-library "@py"`，WebUI/Desktop 可在「裝置選項 > VISA 後端」選擇 PyVISA-py。沒有自動 fallback，也不會依 `PYVISA_LIBRARY` 改選後端。`@py` 僅正式支援 34461A TCPIP；System VISA 支援 34461A USB／TCPIP 與 34460A USB 已登錄的功能。Windows 封裝隨附 PyVISA-py，以及用於 LAN 資源探索的 `psutil`／`zeroconf`；不含額外 USB 驅動。詳細操作請參閱 [CLI README](docs/cli/README.zh-TW.md) 與 [WebUI README](docs/webui/README.zh-TW.md)。

## 建置

使用 `dev` extra 的 `build` 套件產生單一 Python distribution 的 wheel 與 sdist：

```powershell
.\.venv\Scripts\python.exe -m build
```

輸出：

```text
dist\meters_tool-<version>-py3-none-any.whl
dist\meters_tool-<version>.tar.gz
```

Windows `dev` 相依套件包含 PyInstaller。以 onedir 模式建立共用 CLI、WebUI Launcher 與私有 Desktop host：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_windows_bundle.ps1
```

輸出：

```text
dist\meters-tool\
  meters-tool.exe
  meters-tool-webui-launcher.exe
  meters-tool-webui-host.exe
  _internal\
```

建置共用 Windows onedir 與 Electron Desktop 目錄：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_desktop.ps1
```

輸出：

```text
dist\desktop\win-unpacked\
  Meters Tool.exe
  meters-tool.exe
  meters-tool-webui-launcher.exe
  meters-tool-webui-host.exe
  _internal\
  resources\
  locales\
  ... Electron runtime files
```

Desktop 的 `Meters Tool.exe` 使用旁邊的私有 host，並與 CLI／Launcher 共用唯一的 `_internal`；無須系統 Python，也無須每次啟動時解壓 Electron。

組裝 wheel、sdist、統一 Windows ZIP 與 checksums：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_release.ps1
```

版本化產物：

```text
release\<version>\meters-tool-<version>-windows-x64.zip
release\<version>\meters_tool-<version>-py3-none-any.whl
release\<version>\meters_tool-<version>.tar.gz
release\<version>\checksums.txt
```

Windows ZIP 解壓一次後，即可從單一 `meters-tool-<version>` 目錄執行 Desktop、CLI 或 WebUI Launcher，並包含共享 `_internal` 與 Electron runtime。

從乾淨、已提交的 Git 工作樹在專案根目錄執行正式無硬體 Release Acceptance：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\release-acceptance.ps1
```

未指定 `-Release` 時使用 `pyproject.toml` 的版本。驗收在未變動的提交上執行完整無硬體測試（含 wrapper）、單次 Release 建置、wheel/sdist/Windows ZIP 與 SHA-256 驗證、乾淨安裝、CLI／Launcher smoke、preflight 及 PlanOnly。通過後會輸出可供發布的版本化產物路徑，但不會自動發布，也不會自動執行 Electron GUI smoke 或實機測試。最後的 `live-cli-check.ps1 -Suite minimal -PlanOnly -SkipPreflight` 只產生計畫，不開啟 VISA。詳細流程見 [測試指南](docs/testing-guidelines.md) 與 [貢獻指南](docs/CONTRIBUTING.md)。

## 測試

`scripts/preflight-cli.ps1` 執行無硬體檢查；`scripts/live-cli-check.ps1` 僅用於操作人員明確核准的實機驗證。Suite 包含 `full`（Finite Custom：34460A 16 案例、34461A 20 案例），以及分開執行的 `infinite-custom`、`overflow` 和 `worker-streaming`（使用 `--streaming --json` 檢查 Active 邊界）。詳見 [CLI 驗證 Suite 矩陣](docs/cli/README.zh-TW.md#cli-驗證腳本)。`-PlanOnly` 不開啟 VISA；實機測試必須提供明確 Resource 並完成人工確認。

開發時先執行各元件的 focused tests：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\core -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\cli -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\webui -q -p no:cacheprovider
```

執行 Ruff 靜態檢查：

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests
```

執行每日快速無硬體測試：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --ignore=tests\cli\test_cli_wrappers.py
```

Windows CI 會另行執行 `tests\cli\test_cli_wrappers.py`；完整 `release-acceptance.ps1` 只在正式發布前執行。

若 pytest 遇到 Windows 暫存目錄權限問題，改用專案內 `.tmp_tests`：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --ignore=tests\cli\test_cli_wrappers.py --basetemp .tmp_tests\pytest_tmp
```

## 文件

* [版本紀錄](CHANGELOG.md)
* [Core README](docs/core/README.zh-TW.md)
* [支援型號](docs/core/supported-models.zh-TW.md)
* [CLI 使用者指南](docs/cli/USER_GUIDE.zh-TW.md)
* [CLI README](docs/cli/README.zh-TW.md)
* [WebUI README](docs/webui/README.zh-TW.md)
* [WebUI／Desktop 使用者指南](docs/webui/USER_GUIDE.zh-TW.md)
* [Monorepo 架構](docs/architecture/monorepo-layout.md)
* [測試指南](docs/testing-guidelines.md)
* [貢獻指南](docs/CONTRIBUTING.md)
* [公開合約](docs/contracts)
* [Meters CLI JSONL 合約](docs/contracts/meters-cli-jsonl-contract.md)
* [Meters Worker 合約](docs/contracts/meters-worker-contract.md)

## 貢獻

歡迎提交貢獻。在提交 pull request 之前，請閱讀 [貢獻指南](docs/CONTRIBUTING.md)。對儀器支援或實機行為的變更，在適用時需要提供實體儀器驗證證據。

## 授權條款與免責聲明

本專案採用 MIT License。詳見 [LICENSE](LICENSE)。

應用程式圖示：Meters Tool 應用程式圖示使用 ChatGPT 中的 OpenAI 圖像生成功能
產生，並由專案維護者審閱及選定。

本專案是獨立且非官方的專案，未與 Keysight Technologies 建立從屬、背書或贊助關係。

使用者需自行遵守所有適用的 Keysight 軟體、driver、儀器與文件授權條款。
