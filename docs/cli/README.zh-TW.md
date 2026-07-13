# Meters Tool CLI

## 文件組

- [CLI 使用指南](USER_GUIDE.zh-TW.md) - 操作員工作流程與常用設定指引。
- [CLI README](README.zh-TW.md) - 詳細的 CLI 參考、驗證以及自動化指南。
- [變更日誌](CHANGELOG.md) - 版本發行說明與歷史紀錄。
- [CLI 整合](cli-integration.md) - CLI 配接器維護邊界。
- [共用 CLI JSON / JSONL 合約](../contracts/common-cli-jsonl-contract.md) - 共享命令列 JSON 封裝規則。
- [Meters CLI JSON / JSONL 合約](../contracts/meters-cli-jsonl-contract.md) - Meters 命令列 JSON 結構描述與別名規則。
- [共用協調器工作流程](../contracts/common-orchestrator-workflows.md) - 共享子程序生命週期指引。
- [Meters 協調器工作流程](../contracts/meters-orchestrator-workflows.md) - 為代理人（Agent）與自動化設計的 Meters 子程序範例。
- [Meters Worker 合約](../contracts/meters-worker-contract.md) - 為代理人與協調器設計的 Meters worker 控制面、JSONL 與成品合約。

這是支援之數位萬用電表的主要 Python CLI 記錄器，涵蓋透過 VISA 進行的 DC／AC 電流、DC／AC 電壓、DC 電壓比例（DCV Ratio）、頻率、週期，以及 2 線或 4 線電阻測量。每個擷取樣本都會寫入一筆 CSV 資料列，並支援軟體、外部硬體與立即觸發模式。

對於一般操作員工作流程，請先閱讀 [CLI 使用指南](USER_GUIDE.zh-TW.md)。
本 README 則將詳細的命令參考、驗證路徑、JSON/JSONL 合約、範例以及面向維護者的 CLI 行為集中於此。

`meters-tool` 是單一發行套件，其版本由根目錄 `pyproject.toml` 中的 `[project].version` 定義。CLI 保留其獨立的匯入套件、主控台命令、JSON/JSONL 合約、包裝器腳本與測試，同時與 Core 和 WebUI 共享該單一版本號。它繼續透過 CLI 暴露 Core 測量欄位：`voltage-dc-ratio`、`frequency`、`period`、`--auto-zero once`、`--ac-bandwidth-hz`、`--gate-time-s`、`--freq-period-timeout` 與 `--current-terminal`。Core 的啟動驗證、預演（乾跑）規劃、執行期工作階段協調、公開整合匯出以及測量命名，依然與僅限配接器的 CLI 職責保持分離。此基準亦保留了舊版的根層級匯入清理、CLI 合約診斷、無硬體發行驗證、包裝器報告中繼資料，以及 Core／CLI 邊界防護。

Python 整合應自 `meters_tool_core` 或 `meters_tool_core.*` 匯入共享的 API。不再支援舊版根層級的 Core 模組匯入，例如 `meters_tool.measurement` 與 `meters_tool.instrument`。

## 目前範圍

已實作：

- 經由 PyVISA 偵測到的 USB 與 LAN 資源之 VISA 資源列舉。
- DC 電流、DC 電壓、DCV 比例、AC 電流、AC 電壓、頻率、週期以及 2 線或 4 線電阻測量記錄。
- 透過本機 HTTP 端點實作的軟體觸發模式。
- 透過 `GET /status` 提供的本機 worker 狀態端點。
- 軟體計時器擷取（屬於軟體觸發模式的一部分）。
- 外部硬體觸發模式。
- 立即擷取模式。
- 使用 `--max-samples` 進行受限執行。
- 透過 HTTP、Ctrl+C、Ctrl+Break 或 `q` 進行安全停止。
- 將軟體觸發中繼資料寫入 CSV 的 `trigger_metadata` 欄位。
- 省略 `--csv` 時，自動產生具有 UTC+8 時間戳記的 CSV 輸出路徑。
- 選用的資源驗證（使用 `list-resources --verify`）。
- 選用的實體資源過濾（使用 `list-resources --live-only`）。
- 選用的僅限 CLI 的 PyVISA 程式庫/後端選擇（在開啟 VISA 命令時使用 `--visa-library`，接受 `--backend` 作為別名）。
- 選用的測量控制項：測量類型、自動量程、手動量程、DCV 輸入阻抗、自動歸零（包括 `once`）、NPLC、AC 頻寬/濾波器、頻率/週期閘窗時間、頻率逾時、電流端子選擇、硬體觸發延遲、硬體觸發斜率以及 VM Comp 斜率。
- 每次擷取樣本後，立即將緩衝資料寫入 CSV（flush）。

重要限制：

- 本專案支援 Keysight 34460A 與 34461A Truevolt 數位萬用電表記錄。省略 `--model` 時，實體啟動會根據已連線儀器的 IDN 自動偵測模型。
- 當啟動必須符合 34460A IDN 時，請選擇 `--model 34460A`。在實體模式中，這只作為預期模型防護；絕不會覆寫依 IDN 選取的設定檔。在預演（乾跑）或模擬模式中，它會選擇 34460A 的設定檔限制：不提供 10 A 電流量程或電流端子選擇、1000 點讀數記憶體，且不支援基礎設定檔外部觸發模式。
- 當啟動必須符合 34461A IDN 時，請選擇 `--model 34461A`。若實體模型明確不符，程式會在設定 SCPI 前拒絕啟動。模型名稱由 Core 設定檔邏輯標準化與驗證，未知的模型會驗證失敗並顯示支援的模型。
- 實體產品支援會依功能與精確範圍判定：連線、測量與有效觸發模式都必須處於 `live_validated_full_suite`，否則實體工作流程會顯示不支援，並依 fail-closed（失敗即關閉）原則安全拒絕執行。
- 預演、模擬與不建立實體 VISA 連線的 dry-run 規劃不受此限。

## 環境需求

- 本專案支援 Python `>=3.10`。
- 本機安裝有相容的 VISA 執行期軟體（如 Keysight IO Libraries Suite 或 NI-VISA）。
- 需要 Windows 環境以執行封裝的自動化驗證腳本與啟動器執行檔。

## 開發

請先進入專案目錄並設定虛擬環境：

```powershell
uv venv .venv
uv sync --all-extras --link-mode=copy
```

若您在不支援硬連結的跨磁碟區環境中遇到警告，請加入選用的連結模式複製：

```powershell
uv sync --all-extras --locked --link-mode=copy
```

## 獨立執行檔建置（Standalone EXE Build）

本專案支援利用 PyInstaller 將 CLI 封裝成單一獨立的 Windows 執行檔，不需要在目標主機上預先安裝 Python。
建置指令檔：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_cli_exe.ps1
```

這會在 `dist\` 資料夾下產生 `dist\meters-tool.exe`。此建置程序會自動包含 Core 的測量限制與 CLI 邏輯。

## 無硬體驗證（No-Hardware Validation）

在未連接實體儀器的情況下，執行完整的 CLI 測試套件：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/cli -q -p no:cacheprovider
```

或者使用模擬器對特定工作流程進行快速測試：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --simulate `
  --resource "SIM::34461A" `
  --measurement voltage-dc `
  --max-samples 5
```

## 實體儀器驗證（Live Instrument Validation）

實體儀器驗證必須明確選用並受到限制。絕不要猜測或掃描不熟悉的資源位址。

在連線真實儀器進行較大規模的擷取前，務必進行最窄範圍的實體驗證：
- 開啟儀器電源，確認連接。
- 執行單一樣本立即模式：`--max-samples 1`、自動量程啟用。
- 檢查產生的 CSV 值是否與前置面板顯示一致。

## CLI 驗證指令碼

本專案提供三個包裝器指令碼，以自動化多種測試路徑：

| 指令碼 | 硬體使用 | 目的 |
| --- | --- | --- |
| `scripts\preflight-cli.ps1` | 無硬體 | 執行目標感知的預演（乾跑）、模擬器、用戶端預演、Mock 的資源列舉，以及包裝器合約檢查。在進行實體工作前，建議執行此指令碼。 |
| `scripts\live-cli-check.ps1` | 實體硬體（除非指定 `-PlanOnly`） | 執行實體包裝器計劃，並在取得互動式確認後，針對指定的實體 `-Resource` 執行有限的實體驗證案例。頻率與週期案例會先執行單一命令的 SCPI 錯誤診斷。測試套件包括 `minimal`、`basic`、`frequency-period`、`external` 與 `full`；34460A 會拒絕 `external` 測試套件，且其 `full` 測試套件不包含外部觸發案例。 |
| `scripts\release-cli-check.ps1` | 預設無硬體 | 執行發行關卡檢查，包含完整的 pytest、preflight 檢查以及 `live-cli-check.ps1 -PlanOnly`。其預設驗證模式為 `release_no_hardware`。 |

將狀態從 `transport_pending` 或 `feature_pending` 提升至 `live_validated_full_suite` 需要經過審查的測試成品，以及明確更新的支援中繼資料。請勿在僅啟用驗證模式執行的變更中，將未決的範圍或功能標記為公開實體支援。

## 基本工作流程

如需詳細的操作員手冊與設定欄位說明，請參閱 [CLI 使用指南](USER_GUIDE.zh-TW.md)。簡短的工作流程參考如下：

1. 列出 VISA 資源並取得位址。
2. 將位址儲存至環境變數：`$env:METER_RESOURCE = "USB0::...::INSTR"`
3. 在一個終端機中開啟 `start-trigger-record` 記錄。
4. 在另一個終端機中使用 `send-command` 傳送觸發，或等待實體外部觸發訊號，或直接使用立即模式。
5. 透過 `stop` 命令、Ctrl+C、Ctrl+Break、`q` 按鍵或 `--max-samples` 來結束記錄。
6. 檢查產生的 CSV 輸出檔案。

### 34460A 設定檔範例

在對實體 34460A 進行實體啟動時，請使用 `--model 34460A` 預期模型防護。在預演與模擬中，同樣使用此值以載入其設定檔：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --model 34460A `
  --resource "$env:METER_RESOURCE" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --max-samples 1
```

對於 34460A 自訂模式，若預期讀數次數超出其 1000 點記憶體極限，需要加入 `--allow-buffer-overflow-risk` 旗標：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --model 34460A `
  --resource "$env:METER_RESOURCE" `
  --trigger-mode immediate-custom `
  --measurement voltage-dc `
  --trigger-count 2 `
  --sample-count 1000 `
  --allow-buffer-overflow-risk
```

此旗標只表示操作員接受 `trigger_count * sample_count` 超出讀值記憶體容量的風險，但絕不允許使用 10 A 電流量程、`current_terminal=10`、未支援的觸發模式，或設定超出限制的 `--buffer-drain-size`。

### 選用的 PyVISA 後端（Optional PyVISA Backend Selection）

預設情況下，`meters-tool` 使用電腦的系統 VISA 執行期（如 Keysight IO Libraries 或 NI-VISA）。
對於使用 pyvisa-py 的進階測試，可安裝選用的後端套件，並將 `--visa-library "@py"` 傳遞給開啟 VISA 資源的 CLI 命令：

```powershell
uv pip install pyvisa-py pyserial psutil zeroconf

uv run meters-tool list-resources --visa-library "@py" --verify

uv run meters-tool start-trigger-record `
  --model 34461A `
  --visa-library "@py" `
  --resource "$env:METER_RESOURCE" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --max-samples 1
```

別名 `--backend "@py"` 同樣被接受。此選項專為 CLI 診斷與選用後端驗證設計。WebUI 使用預設系統 VISA，且不提供後端選擇。

LAN/TCPIP 是目前唯一通過 34461A pyvisa-py 驗證的路徑；USBTMC 於 Windows 下可能需要 WinUSB/libusb 設定，且通常不比官方 VISA 工具簡單。

## 命令說明（Command Reference）

Meters Tool 提供六個主要 CLI 子命令：

- `list-resources`：探索並驗證可用的 VISA 儀器資源。
- `start-trigger-record`：啟動採集 worker，在指定連接埠監聽控制指令，並將測量資料寫入 CSV。
- `send-command`：對執行中的採集 worker 傳送觸發或其他採集指令。
- `stop`：通知執行中的採集 worker 停止採集、進行清理、將儀器釋放回本地控制面板並退出。
- `status`：輪詢目前採集 worker 的狀態與統計。
- `wait-ready`：等待採集 worker 成功啟動並準備好接收指令。

## 觸發模式（Trigger Modes）

| 模式 | 採集如何啟動 | 讀取路徑 | CSV `trigger_source` | 備註 |
| --- | --- | --- | --- | --- |
| `software` | `send-command` 傳送請求至本地 HTTP 端點，或透過 `--timer-interval-s` 自動產生定時事件。 | `READ?` | `software` 或 `timer` | 省略 `--trigger-mode` 時的預設模式。計時器模式在每次採集結束後加入固定的延遲間隔。 |
| `external` | 儀器接收到實體外部硬體觸發邊緣（slope）。 | `FETC?` | `hardware` | 使用 `--trigger-mode external`。 |
| `immediate` | Worker 會持續取得樣本，不等待任何觸發。 | `READ?` | `immediate` | 使用 `--max-samples` 來指定受限執行。 |
| `immediate-custom` | 儀器執行明確的立即觸發/樣本序列，並將測量值儲存在儀器記憶體中。 | `INIT` + `DATA:POINts?` / `DATA:REMove?` | `immediate-custom` | 需要提供 `--trigger-count` 與 `--sample-count`；不支援 `--max-samples`。 |
| `software-custom` | 儀器配置為匯流排（bus）觸發；每次接收到 `/trigger` 都會傳送 `*TRG` | `INIT` + `*TRG` + `DATA:POINts?` / `DATA:REMove?` | `software-custom` | 需要提供 `--trigger-count` 與 `--sample-count`；不支援 `--max-samples` 與 `--timer-interval-s`。 |
| `external-custom` | 儀器配置為外部觸發邊緣，並將測量值儲存在記憶體中。 | `INIT` + 外部邊緣 + `DATA:POINts?` / `DATA:REMove?` | `external-custom` | 需要提供 `--trigger-count` 與 `--sample-count`；不支援 `--max-samples` 與 `--timer-interval-s`。 |

在 `external` 外部觸發模式下，意外傳送的軟體觸發將會被忽視，不會影響硬體觸發的工作流程。在 `immediate` 立即模式下，軟體觸發同樣被忽視。

當啟用 `--timer-interval-s` 時，一般的 `send-command` 觸發請求將被忽視，但 `stop` 仍可停止執行。第一個計時器樣本會在採集開始時擷取，其後的樣本會在上一個採集嘗試結束後，等待設定的間隔時間。計時器模式是軟體模式採集路徑的簡化，因此 `--max-samples` 依然有效，並在收集到足夠 CSV 資料列後停止。

## `start-trigger-record` 選項

| 選項 | 必要 | 預設 | 說明 |
| --- | --- | --- | --- |
| `--resource RESOURCE` | 是 | 無 | VISA 資源字串，例如 USB 或 TCPIP HiSLIP。 |
| `--model MODEL`, `--instrument-model MODEL` | 否 | 實體執行為 auto；對於非確定性的預演或模擬為必要 | 實體執行的預期模型防護網；預演/模擬的模型設定檔選擇器。Core 邏輯標準化與驗證模型名稱（如 `34460A`、`34461A`），並對不支援的模型報錯。 |
| `--visa-library TEXT`, `--backend TEXT` | 否 | 系統預設 | 選用的 PyVISA 程式庫/後端引數（例如 `@py`）。預演與模擬接受此引數，但不會開啟 VISA 連線。 |
| `--csv PATH` | 否 | `data/YYYY-MM-DD-HH-MM-SS.csv` | CSV 輸出路徑。若省略，會在 `data` 下建立帶有 UTC+8 時間戳記的檔案。父資料夾會自動建立。 |
| `--status-format text|jsonl` | 否 | `text` | 執行期狀態輸出格式。`jsonl` 格式會為代理人呼叫端逐行輸出 JSON 物件。 |
| `--dry-run` | 否 | 關閉 | 驗證引數並輸出計劃的測量、SCPI 命令、讀取路徑與清理合約，而不實際開啟 VISA 工作階段、寫入 CSV 或啟動 HTTP 伺服器。 |
| `--simulate` | 否 | 關閉 | 使用模擬儀器後端執行，而非開啟真實的 VISA 工作階段。簡單模式下需要指定受限執行（如 `--max-samples`）。 |
| `--json` | 否 | 關閉 | `--status-format jsonl` 的別名。 |
| `--timeout-ms N` | 否 | `5000` | VISA 工作階段逾時（毫秒）。支援範圍：`100` 至 `600000`。 |
| `--trigger-timeout-ms N` | 否 | `10000` | 外部/自訂觸發等待逾時。支援範圍：`500` 至 `600000`。硬體模式下的逾時是保護性的重新配置，而非採集錯誤。若此值設定得比外部實體邊緣訊號間隔短，將會導致重複的重新配置而非擷取。 |
| `--sw-trigger-port N` | 否 | `8765` | `/command`、`/stop` 與 `/status` 的本地 HTTP 連接埠。設定 `0` 代表由系統隨機指派，亦可指定 `1024` 至 `65535`。 |
| `--sw-min-interval-ms N` | 否 | `0` | 兩次被接受的軟體觸發之間的最小時間間隔。 |

## 適合代理人使用的 CLI 工作流程（Agent-Friendly CLI Workflows）

為了方便自動化程式或 AI 代理人整合，CLI 的子命令（`send-command`、`stop`、`status`、`wait-ready`）均支援傳遞 `--format json` 或 `--json` 旗標，這將會輸出結構化的單行 JSON 字串，便於整合與解析。

### send-command --format json
對正在執行的 worker 傳送軟體觸發：
```json
{"status": "ok", "message": "trigger sent"}
```

### stop --format json
通知並停止 worker 運作：
```json
{"status": "ok", "message": "stop request received"}
```

### status --format json
取得目前 worker 狀態：
```json
{"status": "ok", "recording": true, "captured": 12, "errors": 0, "port": 8765}
```

### wait-ready --format json
等待 worker 初始化完畢並準備好接收控制請求：
```json
{"status": "ok", "ready": true, "elapsed_ms": 150}
```

### 結束碼（Exit Codes）
- `0`：成功退出。
- `1`：一般錯誤。
- `2`：命令列語法/引數錯誤。
- `10`：驗證失敗（例如引數超出儀器設定檔極限、DCV 輸入阻抗套用於不正確的測量模式等）。
- `20`：VISA 錯誤（例如無法開啟儀器、連線中斷、VISA 逾時）。
- `30`：執行期/背景錯誤（例如無法啟動 Uvicorn 伺服器）。

## 驗證的引數限制（Validated Argument Limits）

為了保障實體儀器的安全並防範錯誤設定，Meters Tool 會在實體通訊開始前，對引數進行靜態驗證。
- **NPLC**：DC 與電阻測量支援 `0.02`、`0.2`、`1`、`10`、`100`。
- **AC Bandwidth**：AC 測量支援 `3`、`20`、`200`（對應儀器的 AC 濾波器：3 Hz–300 kHz、20 Hz–300 kHz、200 Hz–300 kHz）。
- **DCV Input Impedance**：`10M`（固定阻抗）或 `auto`（自動高阻抗，> 10 GΩ）。僅可用於 `voltage-dc` 或 `voltage-dc-ratio` 測量，否則會被拒絕。
- **Current Terminal**：`3A`（預設，所有型號均支援）與 `10A`（僅 34461A 支援）。若對 34460A 請求使用 `10A`，會被拒絕。

## 範例（Examples）

### 列出 VISA 資源
```powershell
.\.venv\Scripts\meters-tool.exe list-resources --live-only
```

### 實體儀器驗證路徑
在預演（dry-run）模式下測試引數，並輸出預計傳送的 SCPI：
```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --dry-run `
  --resource "USB0::0x2A8D::0x1301::MY12345678::INSTR" `
  --measurement voltage-dc
```

### DC 電流煙霧測試（Current DC Smoke Test）
```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --simulate `
  --resource "SIM::34461A" `
  --measurement current-dc `
  --max-samples 1
```

### 軟體觸發，受限執行（Software Trigger, Bounded Run）
```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --simulate `
  --resource "SIM::34461A" `
  --measurement voltage-dc `
  --trigger-mode software `
  --max-samples 3
```

然後在另一個終端機傳送觸發：
```powershell
.\.venv\Scripts\meters-tool.exe send-command
```

### 電壓比例煙霧測試（DCV Ratio Smoke Tests）
```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --simulate `
  --resource "SIM::34461A" `
  --measurement voltage-dc-ratio `
  --max-samples 2
```

### 軟體計時器，受限執行（Software Timer, Bounded Run）
每 1.5 秒自動擷取一次，共擷取 3 個樣本：
```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --simulate `
  --resource "SIM::34461A" `
  --measurement voltage-dc `
  --trigger-mode software `
  --timer-interval-s 1.5 `
  --max-samples 3
```

### 外部硬體觸發，受限執行（External Hardware Trigger, Bounded Run）
```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --simulate `
  --resource "SIM::34461A" `
  --measurement voltage-dc `
  --trigger-mode external `
  --max-samples 5
```

## 停止執行（Stopping a Run）

您可以使用以下任一方式安全停止背景中的採集 worker：
- 在記錄終端機中按下 `q`。
- 在記錄終端機中按下 `Ctrl+C` 或 `Ctrl+Break`。
- 從另一個命令列終端機傳送停止命令：
```powershell
.\.venv\Scripts\meters-tool.exe stop --port 8765
```

正常的清理輸出包含：
```text
stop request received
recording stopped
release_to_local: ...
cleanup_release_to_local: ...
software trigger server stopped
```

## 主控台狀態輸出（Console Status Output）

在軟體觸發執行期間，主控台會在一整段連續等待期間僅輸出一次 `waiting trigger` 或 `waiting software custom trigger`，避免每次短暫輪詢逾時都重複輸出相同訊息。

成功擷取樣本時，主控台會輸出目前的擷取計數與最新顯示值：
```text
[status] captured=1 value=12.3 mA
[status] captured=2 value=1.23 kOhm
```
主控台顯示的單位（`mA`、`mV`、`kOhm`、`MOhm`）僅供人類閱讀，CSV 中儲存的值依然是原始數值與基本測量單位（`A`、`V`、`ratio`、`Hz`、`s`、`Ohm`）。

## CSV 輸出

若省略了 `--csv` 引數，記錄器會在 `data` 目錄下自動建立一個 UTC+8 時間戳記的 CSV 檔案，例如 `data/2026-05-11-14-30-05.csv`。

CSV 欄位定義：
- `timestamp_utc_plus_8`：讀取樣本時的 UTC+8 時間戳記，格式為符合 ISO 8601 帶有 `+08:00` 偏移的字串。
- `measurement_type`：所選測量類型（如 `voltage_dc`、`current_dc`、`resistance_2w` 等）。
- `value`：測量讀數。
- `unit`：測量單位（如 `A`、`V`、`ratio`、`Hz`、`s`、`Ohm`）。
- `trigger_id`：指派給此次觸發事件的唯一 UUID。
- `trigger_source`：觸發源（如 `software`、`timer`、`hardware`、`immediate`、`immediate-custom` 等）。
- `trigger_metadata`：來自 `send-command --arguments-json` 的 JSON 物件字串，或 `{}`。
- `measurement_metadata`：特定測量的中繼資料 JSON 字串，或 `{}`。對於 DCV 比例，可以包含來自 `DATA2?` 的訊號與參考電壓。
- `resource_id`：此次執行所使用的 VISA 資源位址。
- `status`：樣本狀態（成功擷取時為 `ok`）。

## 疑難排解（Troubleshooting）

- **找不到可執行的 `meters-tool.exe`**：請確認您處於包含執行檔的發行套件目錄中。或者在原始碼簽出中重新執行安裝命令。
- **偵測不到任何 VISA 資源**：確認儀器已開機並連接， VISA 驅動程式執行期已安裝，且沒有其他程式佔用儀器。
- **`list-resources` 顯示失效或快取中的舊資源**：執行 `list-resources --live-only` 隱藏失效項目，或執行 `list-resources --verify` 查看失效資源的開啟錯誤。
- **無法開啟 CSV 檔案進行寫入**：檢查該 CSV 是否已被 Excel 或其他程式開啟並鎖定，或變更 `--csv` 的輸出路徑。
- **直流或電阻的高精確度設定導致外部觸發遺漏**：嘗試在啟用觸發前先設定為較短的整合時間與停用自動歸零，例如 `--nplc 1.0 --auto-zero off`。

## 測試（Tests）

在執行測試前，確認您已依據「開發」部分安裝了開發環境相依套件。

預設的 pytest 執行：
```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

執行與 GitHub Actions 相同的 unittest 探索：
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```
