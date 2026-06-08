[English](README.md)

# Keysight Logger

Keysight Logger 是一套以 Python 為基礎的資料擷取與記錄應用程式，適用於 Keysight 34461A 數位萬用電表。

它支援透過 VISA 進行 DC 與 AC 電流、DC 與 AC 電壓、DC 電壓比，以及 2 線式或 4 線式電阻量測。每一筆擷取到的樣本都會連同時間戳記、量測類型、單位、觸發來源與相關中繼資料，寫成 CSV 檔案中的一列。

本專案同時提供命令列介面與本機 WebUI，並支援軟體、計時器、外部硬體、立即，以及緩衝自訂觸發模式。

## 功能

* 使用 VISA 透過 USB 或 LAN 控制 Keysight 34461A
* 量測：

  * DC 電流
  * AC 電流
  * DC 電壓
  * AC 電壓
  * DC 電壓比
  * 2 線式電阻
  * 4 線式電阻
* 為每一筆擷取樣本記錄一列 CSV
* 設定量測範圍、NPLC、Auto Zero、AC 頻寬、電流端子，以及 DC 電壓輸入阻抗
* 支援軟體、計時器、外部硬體、立即，以及緩衝觸發工作流程
* 使用 dry-run 模式預覽儀器命令
* 使用內建模擬器在沒有硬體的情況下測試工作流程
* 可透過 CLI 或本機 WebUI 操作
* 產生 JSON 與 JSONL 輸出，供自動化、代理程式與協調器使用

## 介面

Keysight Logger 提供兩個面向使用者的介面：

### 命令列介面

CLI 適合用於指令碼、可重複測試、自動化擷取，以及與代理程式或協調工具整合。

```powershell
keysight-logger start-trigger-record `
  --resource "SIM::34461A" `
  --measurement voltage-dc `
  --trigger-mode immediate `
  --max-samples 10 `
  --csv data/voltage.csv
```

### WebUI

WebUI 提供本機瀏覽器介面，可用於設定量測、啟動與停止擷取、送出軟體觸發、檢視即時樣本，以及開啟完成的 CSV 檔案。

WebUI 在本機執行，並與 CLI 使用相同的共用擷取核心通訊。

## 專案結構

此儲存庫採用 monorepo 結構，包含三個可分別安裝的套件：

* `packages/core`: `keysight-logger-core` `1.2.1`，匯入名稱為 `keysight_logger_core`，負責儀器通訊、量測設定、觸發、擷取、驗證、模擬與 CSV 儲存
* `packages/cli`: `keysight-logger-cli` `1.3.2`，匯入名稱為 `keysight_logger_cli`，提供命令列介面與機器可讀的 JSON/JSONL 整合
* `packages/webui`: `keysight-logger-webui` `1.2.2`，匯入名稱為 `keysight_logger_webui`，提供本機 WebUI、HTTP API、即時狀態與擷取控制

根目錄的 `pyproject.toml` 僅用於 workspace 工具設定。套件中繼資料維護於各套件目錄內。

## 安裝

```powershell
uv venv .venv
uv pip install -e "packages/core[dev]" -e "packages/cli[dev]" -e "packages/webui[dev]" --link-mode=copy
```

安裝後，Windows 會建立 virtualenv console wrappers，例如
`.\.venv\Scripts\keysight-logger.exe`、
`.\.venv\Scripts\keysight-logger-webui.exe`，以及
`.\.venv\Scripts\keysight-logger-webui-launcher.exe`。這些 wrappers 需要
專案虛擬環境。需要 `dist\` 底下的 standalone executable 時，請使用下方的 PyInstaller 步驟。

## 建置 EXE

將 PyInstaller 安裝到已安裝 Core、CLI 與 WebUI 的同一個虛擬環境：

```powershell
uv pip install pyinstaller
```

建置 standalone CLI executable：

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --onefile --console --name keysight-logger --paths packages\cli\src --paths packages\core\src packages\cli\src\keysight_logger_cli\cli.py
```

結果：

```text
dist\keysight-logger.exe
```

建置 standalone WebUI launcher executable：

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --onefile --windowed --name keysight-logger-webui-launcher --paths packages\webui\src --paths packages\core\src --add-data "packages\webui\src\keysight_logger_webui\static;keysight_logger_webui\static" packages\webui\src\keysight_logger_webui\launcher.py
```

結果：

```text
dist\keysight-logger-webui-launcher.exe
```

重新建置後，執行不需硬體的 smoke checks：

```powershell
.\dist\keysight-logger.exe --version
.\dist\keysight-logger.exe --help
.\dist\keysight-logger.exe list-resources --dry-run --json
```

PyInstaller 會在本機寫入 `.spec`、`build\` 與 `dist\` artifacts。除非專案刻意改用
checked-in PyInstaller build recipe，否則不要 commit 產生的 `.spec` 檔案。

## 測試

```powershell
.\.venv\Scripts\python.exe -m pytest packages/core/tests -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest packages/cli/tests -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest packages/webui/tests -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest packages tests -q -p no:cacheprovider
```

如果 Windows 暫存目錄權限阻擋 pytest，請改用儲存庫本機暫存目錄重新執行：

```powershell
.\.venv\Scripts\python.exe -m pytest packages tests -q -p no:cacheprovider --basetemp .tmp_tests\pytest_tmp
```

## 文件

### 使用者與整合文件

* [Core README](packages/core/README.md)
* [CLI README](packages/cli/README.md)
* [CLI Guide](packages/cli/docs/README_CLI_EN.md)
* [WebUI README](packages/webui/README.md)
* [WebUI Guide](packages/webui/docs/Webui-README.md)
* [WebUI User Guide](packages/webui/docs/USER_GUIDE.md)

### 架構與自動化

* [Monorepo Architecture](docs/architecture/monorepo-layout.md)
* [Public Contracts](docs/contracts)
* [Meters CLI JSONL Contract](docs/contracts/meters-cli-jsonl-contract.md)
* [Meters Worker Contract](docs/contracts/meters-worker-contract.md)

## 授權與免責聲明

本專案採用 MIT License 授權。請參閱 [LICENSE](LICENSE)。

本專案是獨立的非官方軟體，未與 Keysight Technologies 關聯，亦未獲其背書或贊助。

使用者須自行遵守所有適用的 Keysight 軟體、驅動程式、儀器與文件授權條款及相關規範。
