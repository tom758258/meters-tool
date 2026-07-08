# Meters Tool CLI

## 文件集

- [CLI 使用者指南](USER_GUIDE.zh-TW.md) - 操作人員工作流程與常見設定指引。
- [CLI README](README.zh-TW.md) - 詳細的 CLI 參考、驗證與自動化指南。
- [Changelog](CHANGELOG.md) - 版本發布說明與歷史紀錄。
- [CLI 整合](cli-integration.md) - CLI 配接器維護邊界。
- [通用 CLI JSON / JSONL 合約](../contracts/common-cli-jsonl-contract.md) - 共享命令列 JSON 外殼規則。
- [Meters CLI JSON / JSONL 合約](../contracts/meters-cli-jsonl-contract.md) - Meters 命令列 JSON schema 與別名規則。
- [通用協調器工作流程](../contracts/common-orchestrator-workflows.md) - 共享子程序生命週期指引。
- [Meters 協調器工作流程](../contracts/meters-orchestrator-workflows.md) - 用於 Agent 和自動化的 Meters 子程序範例。
- [Meters Worker 合約](../contracts/meters-worker-contract.md) - 用於 Agent 和協調器的 Meters 工作器控制面、JSONL 與產物合約。

適用於 Keysight 34460A 與 34461A Truevolt 數位萬用電表的 CLI 優先 Python 記錄器，支援透過 VISA 進行 DC/AC 電流、DC/AC 電壓、DCV 比率、頻率、週期以及 2 線式或 4 線式電阻量測。
它為每個擷取的樣本記錄一列 CSV，並支援軟體、外接硬體和即時觸發模式。

對於標準操作人員的工作流程，請從 [CLI 使用者指南](USER_GUIDE.zh-TW.md) 開始。本 README 則將詳細的指令參考、驗證路徑、JSON/JSONL 合約、範例及維護人員導向的 CLI 行為彙整於一處。

`meters-tool` 是目前的單一 distribution 基準。其套件版本是 root `pyproject.toml` 內的 `[project].version`。CLI 保留其匯入套件、主控台指令、JSON/JSONL 合約、包裝器腳本和測試，同時與 Core 和 WebUI 共享同一個版本號。它繼續透過 CLI 公開 Core 量測欄位：
`voltage-dc-ratio`、`frequency`、`period`、`--auto-zero once`、`--ac-bandwidth-hz`、`--gate-time-s`、`--freq-period-timeout` 和 `--current-terminal`。Core 的啟動驗證、dry-run 規劃、執行階段協調、公開整合匯出以及量測命名，仍與僅限配接器的 CLI 事務保持分離。此基準也保留了舊版根目錄層級匯入清除、CLI 合約診斷、無硬體發布驗證、包裝器報告 metadata 以及 Core/CLI 邊界防護。

Python 整合應從 `meters_tool_core` 或 `meters_tool_core.*` 匯入共享的 API。不再支援舊的根層級 Core 模組匯入，例如 `meters_tool.measurement` 和 `meters_tool.instrument`。

## 目前範圍

已實現：

- 透過 PyVISA 偵測到的 USB 和 LAN 資源的 VISA 資源列表。
- DC 電流、DC 電壓、DCV 比率、AC 電流、AC 電壓、頻率、週期以及 2 線或 4 線電阻量測記錄。
- 透過本機 HTTP 端點實現的軟體觸發模式。
- 透過 `GET /status` 實現的本機工作器狀態端點。
- 軟體計時器擷取（作為軟體觸發模式的一部分）。
- 外接硬體觸發模式。
- 即時擷取模式。
- 透過 `--max-samples` 限制樣本數的執行。
- 透過 HTTP、Ctrl+C、Ctrl+Break 或 `q` 進行正常停止。
- 軟體觸發 metadata 儲存至 CSV 中的 `trigger_metadata`。
- 當省略 `--csv` 時，選用的 UTC+8 時間戳記 CSV 輸出路徑。
- 透過 `list-resources --verify` 進行選用的資源驗證。
- 透過 `list-resources --live-only` 進行選用的作用中資源篩選。
- 選用的量測控制項：量測類型、自動範圍、手動範圍、DCV 輸入阻抗、包含 `once` 在內的自動歸零（Auto Zero）、NPLC、AC 頻寬/濾波器、頻率/週期閘門時間（gate time）、頻率逾時（timeout）、電流端子選擇、硬體觸發延遲、硬體觸發斜率與 VM Comp 斜率。
- 每筆擷取樣本後立即排空（flush）CSV。

重要限制：

- 本專案目前支援 Keysight 34460A 與 34461A 的電流、電壓、DCV 比率、頻率、週期以及 2 線或 4 線電阻記錄。
- AC、頻率與週期模式透過 `--ac-bandwidth-hz` 公開 34461A 的 `3`、`20` 和 `200` Hz 頻寬/濾波器設定。在實際投入生產使用前，請使用操作者提供的 VISA 資源執行低風險的實際資源基本功能驗證（即快速健檢），並將 CLI 資料列與 34461A 前面板讀數進行對比。
- `--nplc` 和 `--auto-zero` 是 DC/電阻控制項。AC 電流、AC 電壓、頻率與週期僅接受中性預設值 `--nplc 1.0`；任何其他 NPLC 值都將被拒絕，因為這些模式不會寫入 NPLC SCPI。它們也不會寫入 Auto Zero SCPI 指令。
- 不支援在同一次執行中混合使用軟體和硬體擷取。
- 單純呼叫 `list-resources` 會直接調用 VISA 探測，可能會顯示 VISA 執行階段快取的過期資源。使用 `list-resources --verify` 開啟每個資源並查詢 `*IDN?`；驗證成功的資源會在關閉前盡力釋放回本機狀態。當您只需要有回應的資源時，請使用 `list-resources --live-only`。
- `immediate`（即時）模式可以連續且快速地進行擷取。除非您刻意需要連續執行，否則請使用 `--max-samples`。

## 系統需求

- Python 3.10 或更新版本。
- VISA 執行階段，例如 Keysight IO Libraries Suite 或 NI-VISA。
- 透過 USB 或 LAN 對 VISA 可見的 Keysight Truevolt DMM。

## 開發

在 PowerShell 中，切換到專案目錄，建立或重複使用本機虛擬環境，安裝包含開發相依套件的套件，然後執行預設測試：

```powershell
cd path\to\meters-tool
uv venv .venv
uv pip install -e ".[all,dev]"
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

如果 `uv` 警告硬連結（hardlinking）失敗並降級為複製檔案，該警告通常不代表安裝失敗。對於跨磁碟結帳或不支援硬連結的環境，請使用以下命令安裝：

```powershell
uv pip install -e ".[all,dev]" --link-mode=copy
```

在 Windows 上，完整的 pytest 執行可能需要系統管理員權限的 PowerShell 視窗，因為 VISA 相關的探測或本機環境存取可能需要系統管理員權限。

安裝後，使用 `meters-tool` 主控台指令來執行專案命令：

```powershell
.\.venv\Scripts\meters-tool.exe <command> [options]
```

`.venv\Scripts\meters-tool.exe` 是安裝時產生的，並非受版本控制的專案檔案。如果遺失，請重新執行 `uv pip install -e ".[all,dev]"`。如果 PowerShell 因執行原則限制而阻擋啟用，請繼續使用本指南中顯示的明確 `.\.venv\Scripts\...` 命令。

也支援將明確的模組形式作為開發/後備替代方案：

```powershell
.\.venv\Scripts\python.exe -m meters_tool_cli <command> [options]
```

選用的環境啟用：

```powershell
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 因執行原則限制而阻擋啟用，請使用上方顯示的明確 `.\.venv\Scripts\python.exe` 指令。

## 獨立 EXE 建置

安裝的 `.venv\Scripts\meters-tool.exe` 是一個 virtualenv 主控台包裝器。對於沒有專案環境的機器，它並非獨立的執行檔。

若要建置選用的獨立主控台 exe，請在已安裝 `meters-tool` 的環境中使用 PyInstaller。PyInstaller 是本機版本建置工具，而非 CLI 執行階段相依套件，因此在全新機器上重新建置之前，請將其安裝到 venv 中：

```powershell
uv pip install pyinstaller
```

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_cli_exe.ps1
```

輸出為：

```text
dist\meters-tool.exe
```

重新建置後執行無硬體的快速功能健檢：

```powershell
.\dist\meters-tool.exe --version
.\dist\meters-tool.exe --help
.\dist\meters-tool.exe list-resources --dry-run --json
.\dist\meters-tool.exe start-trigger-record --resource SIM::34461A --simulate --measurement voltage-dc --trigger-mode immediate --max-samples 1 --csv .tmp_tests\cli_exe_smoke.csv --status-format jsonl
```

PyInstaller 會將產生的檔案寫入本機 `build\` 和 `dist\` 目錄。除非專案刻意切換為簽入的 PyInstaller spec，否則請勿提交產生的 `.spec` 檔案。

## 無硬體驗證

在進行實體儀器工作前執行此配方：

```powershell
uv pip install -e ".[all,dev]"
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\preflight-cli.ps1 -Target keysight-34461a
.\.venv\Scripts\meters-tool.exe list-resources --dry-run --json
```

`list-resources --dry-run` 不會建立 VISA 資源管理員、列出 VISA 資源、開啟資源、查詢 `*IDN?` 或執行發布/本機清除。如果主控台指令尚未產生，請先安裝套件；上述的模組形式仍可作為開發後備方案。

## 實體儀器驗證路徑

當搬移到新電腦、新的 VISA 執行階段或不同的 34461A 時，請使用本段落。先從無硬體驗證開始，然後探測作用中的資源，接著在允許包裝器接觸儀器前，執行僅限規劃的實際包裝器。

1. 執行上方的無硬體配方。
2. 探測目前有回應 `*IDN?` 的資源：

```powershell
.\.venv\Scripts\meters-tool.exe list-resources --live-only --json
```

3. 從 JSON 輸出中複製一個資源字串。在下方的命令中使用該精確值。實際包裝器絕不會自行掃描或猜測資源。

4. 產生實際規劃，而不開啟 VISA 或變更儀器：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\live-cli-check.ps1 `
  -Target keysight-34461a `
  -Connection usb `
  -Resource "<VISA_RESOURCE>" `
  -Suite minimal `
  -PlanOnly
```

5. 如果規劃看起來正確，請執行最小限度的實際功能驗證（快速健檢）。包裝器會先執行 preflight，列印規劃的儀器狀態變更，並在實際擷取前要求互動式的 Enter 確認：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\live-cli-check.ps1 `
  -Target keysight-34461a `
  -Connection usb `
  -Resource "<VISA_RESOURCE>" `
  -Suite minimal
```

最小套件會擷取一個受限的即時模式樣本。它會將 `report.json`、`summary.md`、指令 stdout/stderr 檔案以及測試案例 CSV 寫入 `.tmp_tests\cli_live\...`。請先檢查 `summary.md`；通過的測試案例應顯示 `captured=1`、`errors=0`，且至少有一列 CSV 數據。在信任較長期的擷取之前，請將 CSV 數值與 34461A 前面板進行對比。

若要獲得更廣泛的實際覆蓋範圍，請在最小套件通過後使用 `-Suite basic`。該套件涵蓋即時量測和軟體觸發路徑。當連接了穩定的輸入訊號，且頻率（Frequency）與週期（Period）各需要擷取一個即時自動範圍（Auto Range）樣本時，請使用 `-Suite frequency-period`。僅當操作者可以安全提供所需的外接觸發邊緣時，才使用 `-Suite external`。僅當同時需要 basic、Frequency/Period 與 external 覆蓋範圍時，才使用 `-Suite full`。

在不開啟 VISA 的情況下預覽頻率/週期（Frequency/Period）實機套件：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\live-cli-check.ps1 `
  -Target keysight-34461a `
  -Connection usb `
  -Resource "<VISA_RESOURCE>" `
  -Suite frequency-period `
  -PlanOnly
```

在檢閱規劃後，移除 `-PlanOnly` 以執行這兩個有界限的實機案例。此套件使用 Auto Range（自動範圍）、`20` Hz AC 濾波器、`0.1` 秒閘門時間（gate time）、自動頻率逾時（automatic Frequency timeout）、無週期逾時指令，以及每個量測各一個樣本。
在每個正式的 CLI 案例之前，一個私有的診斷工作階段會傳送規劃的 SCPI 指令，並在每個指令後及 `READ?` 後檢查 `SYST:ERR?`。報告包含 IDN、韌體版本、個別指令的錯誤回應，以及診斷的 JSON 路徑。探測（probe）錯誤會使該案例失敗並跳過其重複的正式執行，同時允許診斷另一個量測。請將報告的數值和 CSV 資料列與 34461A 前面板進行對比。在韌體版本為 A.03.03 的 34461A 上，這兩個探測皆在沒有 SCPI 錯誤的情況下完成，且在省略週期逾時指令後，每個正式案例都產生了一個樣本和 CSV 資料列。[Keysight Truevolt Series DMM Operating and Service Guide](https://www.keysight.com/us/en/assets/9018-03876/service-manuals/9018-03876.pdf)，第 10 版，2024 年 5 月，包含了模糊的逾時語法；對於不支援的 Period 標頭，應以觀察到的儀器行為為準。

如果 stdin 被重新導向且未設定 `-PlanOnly`，`live-cli-check.ps1` 將拒絕實際擷取並寫入 `confirmation_required` 報告。這是預期行為：實際儀器執行需要互動式確認。

## CLI 驗證指令腳本

CLI 套件有三個包裝器腳本：

| 腳本 | 硬體使用 | 目的 |
| --- | --- | --- |
| `scripts\preflight-cli.ps1` | 無硬體 | 執行 dry-run、模擬器、用戶端 dry-run、模擬的 `list-resources` 以及包裝器合約檢查。在實際工作前使用。 |
| `scripts\live-cli-check.ps1` | 實體硬體（除非設定了 `-PlanOnly`） | 執行實際包裝器規劃，並在互動確認後，針對明確的 `-Resource` 執行有限的實際驗證案例（快速健檢）。頻率/週期案例會先執行個別指令的 SCPI 錯誤診斷。套件包含 `minimal`, `basic`, `frequency-period`, `external`, 和 `full`。 |
| `scripts\release-cli-check.ps1` | 預設無硬體 | 執行發布門檻檢查，包括完整 pytest、preflight 和 `live-cli-check.ps1 -PlanOnly`。其預設驗證模式為 `release_no_hardware`。 |

## 基本工作流程

對於包含常見設定說明的引導式操作人員路徑，請參閱 [CLI 使用者指南](USER_GUIDE.zh-TW.md)。簡要參考流程如下：

1. 列出 VISA 資源。
2. 選擇資源字串。
3. 在一個終端機中啟動 `start-trigger-record`。
4. 傳送觸發、等待外接觸發邊緣，或使用即時模式。
5. 透過 `stop`、Ctrl+C、Ctrl+Break、`q` 或 `--max-samples` 停止。
6. 檢查 CSV 輸出。

## 指令參考

使用已安裝的主控台指令：

```powershell
.\.venv\Scripts\meters-tool.exe <command> [options]
```

模組形式仍可作為明確的開發/後備替代方案：

```powershell
.\.venv\Scripts\python.exe -m meters_tool_cli <command> [options]
```

| 指令 | 目的 | 典型用法 |
| --- | --- | --- |
| `list-resources` | 列印由 PyVISA 偵測到的 VISA 資源。 | 尋找 USB 或 LAN 資源字串。加入 `--verify` 以查詢 `*IDN?`；加入 `--live-only` 以隱藏過期的快取資源；加入 `--dry-run` 以預覽探測動作而不接觸 VISA。 |
| `start-trigger-record` | 連接到儀器並記錄樣本到 CSV。 | 主要記錄指令。 |
| `send-command` | 將一個 `software_trigger` 指令 POST 到本機指令端點。 | 與 `--trigger-mode software` 配合使用。 |
| `stop` | 將正常停止請求 POST 到本機停止端點。 | 從另一個終端機停止執行中的記錄器。 |
| `status` | GET 本機狀態端點並正規化工作器狀態。 | 檢查工作器健康狀態並關聯 `run_id` 而不變更狀態。 |
| `wait-ready` | 輪詢本機狀態端點，直到工作器控制面可供連接。 | 觸發/停止/狀態呼叫前的協調器準備就緒門檻。 |

根選項：

| 選項 | 說明 |
| --- | --- |
| `--version` | 列印 `meters-tool <package-version>`並退出，不需要子指令。 |

`list-resources` 選項：

| 選項 | 說明 |
| --- | --- |
| 無 | 列印由 PyVISA 傳回的原始 VISA 資源。這可能包含過期的快取資源，且不會開啟資源或執行釋放回本機清除。 |
| `--verify` | 開啟每個偵測到的資源並查詢 `*IDN?`。文字輸出將資料列標記為 `live`（作用中）或 `stale`（過期）；JSON 輸出包含 `live`、`status` 和 `detail`。成功的作用中檢查會在關閉前盡力執行釋放回本機狀態。 |
| `--live-only` | 驗證資源並僅列印有回應的資料列。成功的作用中檢查會在關閉前盡力執行釋放回本機狀態。如果沒有連接或可連線的資源，文字輸出會列印 `no live VISA resources found`。 |
| `--dry-run` | 列印資源探測合約並以 0 退出，而不建立 VISA 資源管理員、列出資源、開啟資源、查詢 `*IDN?` 或執行發布/本機清除。可與 `--verify`、`--live-only` 和 `--json` 結合使用。 |
| `--format json` | 為腳本發出一個 JSON 物件。可與 `--verify` 或 `--live-only` 結合使用。 |
| `--json` | `--format json` 的別名。 |

`send-command` 選項：

| 選項 | 預設值 | 說明 |
| --- | --- | --- |
| `--port N` | `8765` | 本機指令端點連接埠。支援範圍：`1` 到 `65535`。 |
| `--timeout-ms N` | `3000` | HTTP 用戶端逾時（毫秒）。支援範圍：`100` 到 `600000`。 |
| `--command NAME` | `software_trigger` | Meters 指令名稱。此版本僅支援 `software_trigger`。 |
| `--arguments-json JSON` | `{}` | 完整的 JSON 指令引數物件。使用 `{"metadata":{...}}` 來附加寫入 CSV 中 `trigger_metadata` 欄位的觸發 metadata。無效的 JSON、非物件的 metadata 以及其他指令驗證失敗將在傳送請求前被拒絕。 |
| `--job-id TEXT` | 未設置 | 選用的用戶端產生工作識別碼，僅由指令外殼回應。 |
| `--format text\|json` | `text` | 回應輸出格式。`json` 為 Agent 呼叫端發出一個結構化物件。 |
| `--json` | 否 | `--format json` 的別名。 |
| `--dry-run` | 否 | 在本機預覽請求而不傳送 HTTP。 |

`stop` 選項：

| 選項 | 預設值 | 說明 |
| --- | --- | --- |
| `--port N` | `8765` | 本機停止端點連接埠。支援範圍：`1` 到 `65535`。 |
| `--timeout-ms N` | `3000` | HTTP 用戶端逾時（毫秒）。支援範圍：`100` 到 `600000`。 |
| `--format text\|json` | `text` | 回應輸出格式。`json` 為 Agent 呼叫端發出一個結構化物件。 |
| `--json` | 否 | `--format json` 的別名。 |
| `--dry-run` | 否 | 在本機預覽請求而不傳送 HTTP。 |

`status` 選項：

| 選項 | 預設值 | 說明 |
| --- | --- | --- |
| `--port N` | `8765` | 本機狀態端點連接埠。支援範圍：`1` 到 `65535`。 |
| `--timeout-ms N` | `3000` | HTTP 用戶端逾時（毫秒）。支援範圍：`100` 到 `600000`。 |
| `--format text\|json` | `text` | 回應輸出格式。`json` 發出一個正規化的狀態物件。 |
| `--json` | 否 | `--format json` 的別名。 |
| `--dry-run` | 否 | 在本機預覽非變更性的 GET 請求而不傳送 HTTP。 |

`wait-ready` 選項：

| 選項 | 預設值 | 說明 |
| --- | --- | --- |
| `--port N` | `8765` | 本機狀態端點連接埠。支援範圍：`1` 到 `65535`。 |
| `--timeout-ms N` | `10000` | 整體準備就緒期限（毫秒）。支援範圍：`100` 到 `600000`。 |
| `--format text\|json` | `text` | 回應輸出格式。`json` 發出正規化狀態加上準備就緒計時欄位。 |
| `--json` | 否 | `--format json` 的別名。 |

## 觸發模式

| 模式 | 擷取如何開始 | 讀取路徑 | CSV `trigger_source` | 備註 |
| --- | --- | --- | --- | --- |
| `software` | `send-command` 發送至本機 HTTP 端點，或 `--timer-interval-s` 建立自動計時器事件。 | `READ?` | `software` 或 `timer` | 省略 `--trigger-mode` 時的預設值。計時器模式在每次擷取嘗試後使用固定延遲間隔。 |
| `external` | 儀器接收到外接硬體觸發邊緣。 | `FETC?` | `hardware` | 使用 `--trigger-mode external`。 |
| `immediate` | 工作器直接擷取而不等待觸發事件。 | `READ?` | `immediate` | 使用 `--max-samples` 來限制執行樣本數。 |
| `immediate-custom` | 儀器執行明確的即時觸發/樣本序列並將讀數儲存在記憶體中。 | `INIT` + `DATA:POINts?` / `DATA:REMove?` | `immediate-custom` | 需要 `--trigger-count` 和 `--sample-count`；`--max-samples` 無效。 |
| `software-custom` | 儀器準備接收匯流排觸發；每個接受的 `send-command` 會傳送 `*TRG`。 | `INIT` + `*TRG` + `DATA:POINts?` / `DATA:REMove?` | `software-custom` | 需要 `--trigger-count` 和 `--sample-count`；`--max-samples` 和 `--timer-interval-s` 無效。 |
| `external-custom` | 儀器準備接收外接觸發邊緣並將讀數儲存在記憶體中。 | `INIT` + 外接邊緣 + `DATA:POINts?` / `DATA:REMove?` | `external-custom` | 需要 `--trigger-count` 和 `--sample-count`；`--max-samples` 和 `--timer-interval-s` 無效。 |

在 `external` 模式下，意外的軟體觸發會被忽略，且不應中斷硬體觸發流程。在 `immediate` 模式下，軟體觸發同樣會被忽略。

當 `--timer-interval-s` 作用中時，一般的 `send-command` 請求會被忽略，而 `stop` 仍可停止執行。當記錄開始時會擷取第一個計時器樣本；後續的每個計時器樣本會在前一次擷取嘗試完成後，至少等待設定的間隔時間。計時器模式是簡單的軟體模式擷取路徑，因此 `--max-samples` 有效，並會在達到該數量成功的計時器 CSV 資料列後停止執行。

## `start-trigger-record` 選項

| 選項 | 是否必要 | 預設值 | 說明 |
| --- | --- | --- | --- |
| `--resource RESOURCE` | 是 | 無 | VISA 資源字串，例如 USB 或 TCPIP HiSLIP。 |
| `--csv PATH` | 否 | `data/YYYY-MM-DD-HH-MM-SS.csv` | CSV 輸出路徑。若省略，則在 `data` 下建立帶有 UTC+8 時間戳記的檔案。父目錄會自動建立。 |
| `--status-format text\|jsonl` | 否 | `text` | 執行階段狀態輸出格式。`jsonl` 為 Agent 呼叫端每行發出一個 JSON 物件。 |
| `--dry-run` | 否 | 關閉 | 驗證引數並列印規劃的量測、SCPI、讀取路徑和清除合約，而不開啟 VISA、寫入 CSV 或啟動 HTTP 伺服器。 |
| `--simulate` | 否 | 關閉 | 針對確定的模擬儀器後端執行，而不開啟實際的 VISA 工作階段。簡單模式需要有界限的執行，例如 `--max-samples`。 |
| `--json` | 否 | 關閉 | `--status-format jsonl` 的別名。 |
| `--timeout-ms N` | 否 | `5000` | VISA 工作階段逾時（毫秒）。支援範圍：`100` 到 `600000`。 |
| `--trigger-timeout-ms N` | 否 | `10000` | 外接/自訂觸發等待逾時。支援範圍：`500` 到 `600000`。逾時會重新 arm 硬體模式，其本身並非擷取錯誤。對於預期的外接邊緣時間而言太短的值將會重複 arm 而不進行擷取。 |
| `--sw-trigger-port N` | 否 | `8765` | 用於 `/command`、`/stop` 和 `/status` 的本機 HTTP 連接埠。使用 `0` 讓伺服器選擇連接埠，或使用 `1024` 到 `65535`。 |
| `--sw-min-interval-ms N` | 否 | `0` | 接受的軟體觸發之間的最小間隔。使用 `0` 停用速率限制，或使用 `50` 到 `600000`。 |
| `--sw-queue-max N` | 否 | `0` | 佇列軟體觸發的最大數量。支援範圍：`0` 到 `10000`；`0` 使用預設的安全限制。 |
| `--trigger-mode software\|external\|immediate\|immediate-custom\|software-custom\|external-custom` | 否 | `software` | 精確選擇一種擷取模式。 |
| `--max-samples N` | 僅限簡單模式 | 無 | 在成功取得 N 個 CSV 樣本後自動停止簡單模式。支援範圍：`1` 到 `1000000`。與自訂模式不相容。 |
| `--trigger-count N` | 僅限自訂模式 | 無 | 儀器觸發計數。支援範圍：`1` 到 `1000000`。自訂模式下必要；與簡單模式不相容。 |
| `--sample-count N` | 僅限自訂模式 | 無 | 每次觸發的儀器樣本計數。支援範圍：`1` 到 `1000000`。自訂模式下必要；與簡單模式不相容。 |
| `--timer-interval-s SECONDS` | 否 | 無 | 啟用固定延遲的軟體計時器擷取。支援範圍：`0.5` 到 `86400` 秒。僅在 `--trigger-mode software` 時有效；當省略 `--trigger-mode` 時也有效（因為預設為 software）。可與 `--max-samples` 結合以限制計時器執行次數。 |
| `--buffer-drain-size N` | 僅限自訂模式 | 無 | 每次緩衝區排空移除的最大讀數。支援範圍：`1` 到 `10000`，受儀器設定檔讀取記憶體限制。進階選項，僅在自訂模式下有效；不會變更 `TRIG:COUNT`、`SAMP:COUNT` 或儀器讀取記憶體容量。 |
| `--allow-buffer-overflow-risk` | 否 | 關閉 | 允許自訂模式請求超過 34461A 的 10,000 個讀數記憶體限制。這取決於排空讀數的速度是否夠快，可能會遺失數據或產生 SCPI 錯誤。 |
| `--hw-trigger-slope pos\|neg` | 否 | `neg` | 外接觸發邊緣極性。 |
| `--hw-trigger-delay-s SECONDS` | 否 | `0.0` | 硬體觸發延遲，對應到 `TRIG:DEL`。支援範圍：`0` 到 `3600` 秒。 |
| `--measurement current-dc\|voltage-dc\|voltage-dc-ratio\|current-ac\|voltage-ac\|frequency\|period\|resistance-2w\|resistance-4w` | 否 | `current-dc` | 量測類型。 |
| `--nplc VALUE` | 否 | `1.0` | 用於 DC 電流、DC 電壓、DCV 比率和電阻的電源線週期積分時間。DC/電阻/比率的允許值：`0.02`、`0.2`、`1`、`10`、`100`。AC 電流、AC 電壓、頻率與週期僅接受中性預設值 `1.0`。 |
| `--auto-zero on\|off\|once` | 否 | `on` | 支援量測的自動歸零（Auto Zero）。`once` 在 DC 電流、DC 電壓和 2 線電阻下有效。DCV 比率僅接受預設/啟用（on）行為且不寫入 Auto Zero SCPI；4 線電阻、AC 量測、頻率與週期則將 Auto Zero 交給儀器處理。 |
| `--auto-range on\|off` | 否 | `on` | 啟用或停用自動範圍（Auto Range）。 |
| `--range VALUE` | 當 `--auto-range off` 時必要 | 無 | 所選量測的手動範圍。電流為安培；電壓、頻率與週期的輸入範圍為伏特；電阻為歐姆。 |
| `--current-range VALUE` | 僅限 DC 電流 | 無 | 與 `current-dc` 的 `--range` 相容的別名。不可與 `--range` 同時使用；在 AC 電流、電壓和電阻量測下無效。 |
| `--ac-bandwidth-hz 3\|20\|200` | 僅限 AC/頻率/週期 | 依量測而定 | AC 頻寬/濾波器設定。AC 電流/電壓省略時保持目前設定；頻率和週期省略時預設為 `20` Hz。 |
| `--gate-time-s 0.01\|0.1\|1` | 僅限頻率/週期 | `0.1` | 頻率/週期孔徑或閘門時間（gate time），單位為秒。 |
| `--freq-period-timeout auto\|1s` | 僅限頻率 | `auto` | 使用自動頻率逾時（timeout），或停用自動逾時以使用固定 1 秒行為。週期不支援此選項，也不會送出逾時 SCPI。 |
| `--current-terminal 3\|10` | 僅限電流 | `3` | 電流輸入端子。10 A 範圍需要 `--current-terminal 10`；`--current-terminal 10` 僅在 10 A 範圍下有效。 |
| `--dcv-input-impedance default\|10m\|auto` | 僅限 DC 電壓或 DCV 比率 | `default` | DC 電壓輸入阻抗。`default` 不寫入阻抗指令；`10m` 強制為 10 MOhm；`auto` 啟用儀器自動（Auto）模式（在較低的 DC 電壓範圍下可能會顯示 HighZ）。 |
| `--vm-comp-slope pos\|neg` | 否 | 無 | 設定後面板 VM Comp 輸出脈衝斜率。省略以保持 VM Comp 不變。 |

`--measurement` 預設為 `current-dc`，因此現有的電流量測記錄指令不需要特別指定。新指令應偏好使用 `--range`；`--current-range` 繼續適用於現有的 DC 電流腳本。對於 `current-ac`、`voltage-dc`、`voltage-dc-ratio`、`voltage-ac`、`frequency`、`period`、`resistance-2w` 和 `resistance-4w` 請使用 `--range`；`--current-range` 在這些量測下會被拒絕。
`--dcv-input-impedance` 僅在 `--measurement voltage-dc` 或 `--measurement voltage-dc-ratio` 時有效。使用 `default` 以保持儀器目前的 Input Z 設定不變，`10m` 強制為 10 MOhm，或 `auto` 啟用 34461A 的 Auto Input Z 行為。當 Auto 作用於較低 DC 電壓範圍時，儀器可能會顯示 HighZ。

## 友善 Agent 的 CLI 工作流程

使用 `--dry-run` 來驗證命令並檢查規劃的 SCPI/讀取路徑，而不接觸實體儀器：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --max-samples 1 `
  --dry-run `
  --status-format jsonl
```

使用 `--simulate` 進行工作流程檢查，而不需要實際的 VISA 工作階段：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "SIM::34461A" `
  --csv ".\data\simulate.csv" `
  --trigger-mode immediate `
  --measurement current-dc `
  --max-samples 2 `
  --simulate `
  --status-format jsonl
```

JSONL 輸出是每行一個 JSON 物件。這是專為 Agent 和腳本設計的；預設的文字輸出仍然是面向人類的介面。模擬器數值是確定的工作流程資料，並非真實的 34461A 量測驗證。

自動化呼叫端應解析 JSONL、單一回應 JSON、CSV 檔案以及包裝器 `report.json` 產物來做出決策。人類文字訊息僅用於診斷，且可能會因可讀性而有所變更。

有關目前的 schema 和別名規則，請參閱 [Meters CLI JSON / JSONL 合約](../../docs/contracts/meters-cli-jsonl-contract.md)。

有關 Meters 工作器模式、本機控制端點、狀態 payload 以及包裝器產物/報告 schema，請參閱 [Meters Worker 合約](../../docs/contracts/meters-worker-contract.md)。

當工作器執行中，`status` 會包裝非變更性的 `GET /status` 並傳回正規化 JSON 以供協調器健康檢查：

```powershell
.\.venv\Scripts\meters-tool.exe status --port 8765 --json
```

推薦的協調器流程：

1. 執行 `start-trigger-record --dry-run --status-format jsonl` 並驗證規劃（plan）物件。
2. 以相同的命令搭配 `--simulate --status-format jsonl` 與有限範圍（如 `--max-samples`）執行。
3. 對於實際擷取，使用明確的 `--resource` 啟動工作器；在無人值守的實際執行中，絕不可掃描、推斷或猜測 VISA 資源。
4. 等待 JSONL 的 `ready` 事件，或執行 `wait-ready --port 8765 --json`，然後呼叫 `status --port 8765 --json` 來驗證 `run_id`。
5. 僅在軟體觸發模式下使用 `POST /command`，並使用 `POST /stop` 進行正常停止。
6. 讀取 stdout 的 JSONL、CSV 以及例如 `report.json` 的包裝器產物以做出成功/失敗的決策。

請參閱 [Meters 協調器工作流程](../../docs/contracts/meters-orchestrator-workflows.md) 了解完整的 Python 子程序工作流程。

`ready` 事件與 `wait-ready` 代表本機控制面可以接受 `/command`、`/stop` 與 `/status` 請求。它們並不代表第一個樣本已經擷取。使用 JSONL `run_id` 作為同一次執行的 stdout 執行階段事件、`status` 或直接 `GET /status` 以及包裝器產物之間的關聯鍵。

### send-command --format json

```powershell
.\.venv\Scripts\meters-tool.exe send-command --port 8765 --format json
```

輸出：

```json
{"command": "software_trigger", "event": "send-command", "http_status": 202,
 "job_id": null, "message": "command accepted", "schema_version": 1,
 "status": "accepted", "timestamp_utc": "2026-05-18T..."}
```

本機驗證和工作器 HTTP `400` 回應會以代碼 2 退出。HTTP `409`、`429`、連線/請求失敗，以及無效或空的成功回應主體會以代碼 3 退出。結構化 JSON 診斷會合併工作器的 `command`、`job_id`、`reason`、`error` 和 `message` 欄位（如果可用）。

### stop --format json

```powershell
.\.venv\Scripts\meters-tool.exe stop --port 8765 --format json
```

輸出：

```json
{"event": "stop", "http_status": 202, "message": "stop accepted",
 "schema_version": 1, "status": "accepted", "timestamp_utc": "2026-05-18T..."}
```

如果端點未在監聽（程序已停止），則以代碼 0 退出，並發出 `{"status": "already_stopped", ...}`。

### status --format json

```powershell
.\.venv\Scripts\meters-tool.exe status --port 8765 --format json
```

輸出包含 `event: "status"`、`reachable`、`ok`、`running`、`stopping`、`run_id`、工作器 URL、佇列欄位、`captured`（已擷取數）、`errors`（錯誤數）以及 `fatal_error`。`ok` 是工作器健康狀態：僅在端點可連線且 `fatal_error` 為 `null` 時才為 `true`。

### wait-ready --format json

```powershell
.\.venv\Scripts\meters-tool.exe wait-ready --port 8765 --timeout-ms 10000 --format json
```

`wait-ready` 在收到來自 `/status` 的任何有效 `200` JSON 回應時成功，並將 `attempts`、`elapsed_ms` 和 `timeout_ms` 加入正規化的狀態物件中。逾時或無效狀態 JSON 將以代碼 3 退出。

### 結束代碼 (Exit Codes)

| 代碼 | 意義 |
| --- | --- |
| `0` | 成功，包括含有 `fatal_error` 的可連線 `status`，以及當端點已停止時的 `stop`。 |
| `2` | 在請求的操作執行前的驗證或使用錯誤。 |
| `3` | 執行階段、連線、HTTP 請求失敗、無效的 `/status` JSON，或 `wait-ready` 逾時。 |

## 已驗證引數限制

CLI 在開啟儀器前會驗證使用者輸入。超出這些範圍的值將快速失敗並顯示明確的錯誤。

| 引數 | 接受值 |
| --- | --- |
| `--measurement` | `current-dc`, `voltage-dc`, `voltage-dc-ratio`, `current-ac`, `voltage-ac`, `frequency`, `period`, `resistance-2w`, `resistance-4w` |
| `--auto-zero` | `on`, `off` 或 `once`（依量測而有不同限制） |
| `--auto-range` | `on` 或 `off` |
| `--ac-bandwidth-hz` | `3`, `20` 或 `200`（僅限 AC 電流/電壓與頻率/週期） |
| `--gate-time-s` | `0.01`, `0.1` 或 `1`（僅限頻率/週期） |
| `--freq-period-timeout` | `auto` 或 `1s`（僅限頻率） |
| `--current-terminal` | `3` 或 `10`（僅限電流量測） |
| `--status-format` | `text` 或 `jsonl` |
| `--timeout-ms` | `100` 到 `600000` |
| `--trigger-timeout-ms` | `500` 到 `600000` |
| `--sw-trigger-port` | `0` 或 `1024` 到 `65535`；`0` 讓伺服器自行選擇 |
| `--sw-min-interval-ms` | `0` 或 `50` 到 `600000`；`0` 停用節流 |
| `--sw-queue-max` | `0` 到 `10000`；`0` 使用預設安全限制 |
| `--max-samples` | `1` 到 `1000000`（僅限簡單模式） |
| `--trigger-count`, `--sample-count` | `1` 到 `1000000`（僅限自訂模式） |
| `--timer-interval-s` | `0.5` 到 `86400` 秒（僅限軟體模式） |
| `--buffer-drain-size` | `1` 到 `10000`（僅限自訂模式且受讀取記憶體限制） |
| `--hw-trigger-delay-s` | `0` 到 `3600` 秒 |
| `send-command --port`, `stop --port`, `status --port`, `wait-ready --port` | `1` 到 `65535` |
| `send-command --timeout-ms`, `stop --timeout-ms`, `status --timeout-ms`, `wait-ready --timeout-ms` | `100` 到 `600000` |
| `send-command --format`, `stop --format`, `status --format`, `wait-ready --format` | `text` 或 `json` |

對於 Agent 或自動化使用，`start-trigger-record --status-format jsonl` 和 `--json` 別名會在控制面啟動後發出一個 `ready` 事件。該事件包含 `command_url`、`stop_url` 和 `status_url`。請將其視為可以傳送 `/command`、`/stop` 和非變更性 `/status` 請求的訊號；這不是第一個樣本或量測完成的訊號。

`--trigger-timeout-ms` 對於外接硬體觸發模式最為重要。如果它短於外接邊緣之間的預期時間，主控台將會一直列印硬體觸發逾時/重新 arm 狀態，且在逾時視窗內有新的邊緣到達前不會進行任何擷取。在軟體模式下，此值僅用於工作器輪詢步調，並在內部限制為每次等待最多 200 ms；這不是量測完成的逾時。

對於 Agent 或自動化使用，請保守分類觸發等待結果：尚未到達的外接觸發邊緣是正常等待狀態，而非錯誤。在簡單的外接模式中，重複的 PyVISA 狀態位元組輪詢逾時只會發出診斷，不會成為致命的擷取失敗：第 5 次連續逾時會發出警告，第 25 次連續逾時會增加 `errors` 數並發出降級狀態，之後每增加 25 次連續逾時會再次增加 `errors` 數。成功讀取狀態位元組會重設連續逾時次數。實際的 `READ?`、`FETC?`、連線、識別或 SCPI 指令失敗則是擷取錯誤且可能是致命的。

手動範圍值針對每種量測類型進行白名單管理：

| 量測類型 | 允許的 `--range` 值 |
| --- | --- |
| `current-dc` | `0.0001`, `0.001`, `0.01`, `0.1`, `1`, `3`, `10` A |
| `current-ac` | `0.0001`, `0.001`, `0.01`, `0.1`, `1`, `3`, `10` A |
| `voltage-dc` | `0.1`, `1`, `10`, `100`, `1000` V |
| `voltage-dc-ratio` | `0.1`, `1`, `10`, `100`, `1000` V |
| `voltage-ac` | `0.1`, `1`, `10`, `100`, `750` V |
| `frequency` | `0.1`, `1`, `10`, `100`, `750` V 輸入範圍 |
| `period` | `0.1`, `1`, `10`, `100`, `750` V 輸入範圍 |
| `resistance-2w` | `100`, `1000`, `10000`, `100000`, `1000000`, `10000000`, `100000000` Ohm |
| `resistance-4w` | `100`, `1000`, `10000`, `100000`, `1000000`, `10000000`, `100000000` Ohm |

額外驗證規則：

- `--auto-range off` 需要手動範圍。對於 `current-dc`，接受 `--range` 或相容別名 `--current-range`。對於所有其他量測，請使用 `--range`。
- `--range` 和 `--current-range` 不能同時使用。
- `--current-range` 僅在 `--measurement current-dc` 下有效。
- 除了 `default` 之外的 `--dcv-input-impedance` 值僅在 `--measurement voltage-dc` 或 `--measurement voltage-dc-ratio` 下有效。
- DC、DCV 比率和電阻量測僅接受以下 NPLC 值：`0.02`, `0.2`, `1`, `10`, `100`。
- AC 電流、AC 電壓、頻率和週期拒絕非預設的 NPLC 值。請省略 `--nplc` 或傳送 `--nplc 1.0`。
- `--auto-zero once` 僅在 `current-dc`, `voltage-dc` 和 `resistance-2w` 下有效。
- `voltage-dc-ratio` 僅接受預設/啟用（on）的 Auto Zero 行為。
- `--ac-bandwidth-hz` 僅在 `current-ac`、`voltage-ac`、`frequency` 或 `period` 下有效。
- `--gate-time-s` 僅在 `frequency` 或 `period` 下有效。
- `--freq-period-timeout` 僅在 `frequency` 下有效。
- `--current-terminal` 僅在電流量測下有效。10 A 範圍需要 `--current-terminal 10`，而 `--current-terminal 10` 需要 10 A 範圍。
- 自訂模式需要同時提供 `--trigger-count` 和 `--sample-count`；簡單模式會拒絕這兩個選項。
- 自訂模式拒絕 `--max-samples`；簡單模式使用 `--max-samples` 進行有限的執行。
- `--buffer-drain-size` 和 `--allow-buffer-overflow-risk` 僅在自訂模式下有效。
- 除非設定了 `--allow-buffer-overflow-risk`，否則自訂模式拒絕 `trigger_count * sample_count > 10000`。
- `--timer-interval-s` 需要軟體模式。它在預設觸發模式下有效（因為省略 `--trigger-mode` 會解析為 `software`）。可與 `--max-samples` 結合使用。

## 範例

這些範例依照實用驗證路徑排序：先確認作用中資源，然後執行單一樣本快速功能健檢，最後使用符合實驗設計的觸發模式。下方顯示的 USB 資源是專案驗證時使用的 34461A；請替換為適合您儀器和測試執行的資源字串與 CSV 路徑。

### 列出 VISA 資源

```powershell
.\.venv\Scripts\meters-tool.exe list-resources
```

驗證哪些資源是作用中（live）的：

```powershell
.\.venv\Scripts\meters-tool.exe list-resources --verify
```

成功驗證的作用中資源會在掃描工作階段關閉前盡力釋放回本機狀態。未通過 IDN 查詢的過期資源將在不執行釋放 SCPI 的情況下關閉。

僅顯示作用中資源並隱藏過期的 VISA 快取項目：

```powershell
.\.venv\Scripts\meters-tool.exe list-resources --live-only
```

在腳本中使用 JSON 輸出：

```powershell
.\.venv\Scripts\meters-tool.exe list-resources --verify --format json
```

預覽探測合約而不接觸 VISA：

```powershell
.\.venv\Scripts\meters-tool.exe list-resources --dry-run --live-only --json
```

驗證後的文字輸出以 tab 分隔：

```text
live    USB0::<vendor_id>::<product_id>::<serial>::0::INSTR    Keysight Technologies,34461A,...
stale   USB0::OLD::RESOURCE::INSTR                     VisaIOError: ...
```

`--live-only` 仍會驗證每個資源，但會隱藏過期（stale）的資料列。如果沒有資源回應，文字輸出會列印：

```text
no live VISA resources found
```

驗證後的 JSON 輸出為單一物件：

```json
{
  "resources": [
    {
      "detail": "Keysight Technologies,34461A,...",
      "live": true,
      "resource": "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR",
      "status": "live"
    }
  ],
  "verify": true
}
```

`--live-only --format json` 保留相同的資源記錄格式，篩選掉過期的項目，並加入 `live_only`：

```json
{
  "live_only": true,
  "resources": [
    {
      "detail": "Keysight Technologies,34461A,...",
      "live": true,
      "resource": "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR",
      "status": "live"
    }
  ],
  "verify": true
}
```

資源字串範例：

```text
USB0::<vendor_id>::<product_id>::<serial>::0::INSTR
TCPIP0::<host>::hislip0::INSTR
```

### 真實儀器驗證路徑

在檢查環境設定時，請使用此順序：

1. 執行 `list-resources --live-only` 並選擇作用中的資源。當需要診斷過期的 VISA 快取項目時，請改用 `list-resources --verify`。
2. 以 `--trigger-mode immediate` 與 `--max-samples 1` 執行單一樣本的電流、電壓、頻率、週期或電阻快速功能健檢。
3. 執行實驗所需的特定觸發模式：軟體、計時器、外接、即時或自訂/緩衝。
4. 確認 CSV 中的 `measurement_type`、`unit`、`trigger_source` 與列數。
5. 在信賴長期無人值守執行前，先用 `stop`、Ctrl+C、Ctrl+Break 或 `q` 確認正常停止行為。

在進行無人值守擷取前，請使用操作者提供的 Keysight 34461A VISA 資源來驗證工作流程。從即時模式、自動範圍開啟以及 `--max-samples 1` 開始，然後擴展至預期的量測、觸發模式與緩衝模式。對於 AC 電流、AC 電壓、頻率與週期，請在快速功能健檢期間將 CLI CSV 資料列與 34461A 前面板讀數進行對比。

### DC 電流快速功能健檢

單一即時電流樣本：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\current_smoke.csv" `
  --trigger-mode immediate `
  --measurement current-dc `
  --auto-range off `
  --range 0.1 `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

對於電流列，預期 CSV 中的 `measurement_type=current_dc` 且 `unit=A`。

Dry-run 10 A 端子檢查：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --trigger-mode immediate `
  --measurement current-dc `
  --auto-range off `
  --range 10 `
  --current-terminal 10 `
  --max-samples 1 `
  --dry-run `
  --status-format jsonl
```

模擬 10 A 端子工作流程檢查：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "SIM::34461A" `
  --csv ".\data\simulate_current_10a_terminal.csv" `
  --trigger-mode immediate `
  --measurement current-dc `
  --auto-range off `
  --range 10 `
  --current-terminal 10 `
  --max-samples 1 `
  --simulate `
  --status-format jsonl
```

實際 10 A 端子快速功能健檢。僅在操作者確認電流路徑對 10 A 輸入端子和預期電流安全後才可執行：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\current_10a_terminal_smoke.csv" `
  --trigger-mode immediate `
  --measurement current-dc `
  --auto-range off `
  --range 10 `
  --current-terminal 10 `
  --auto-zero once `
  --nplc 1.0 `
  --max-samples 1 `
  --status-format jsonl
```

### 軟體觸發，限制樣本執行

終端機 1，開始記錄並等待五次軟體觸發：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\software_5.csv" `
  --trigger-mode software `
  --max-samples 5 `
  --measurement current-dc `
  --auto-range off `
  --range 0.1 `
  --auto-zero on `
  --nplc 1.0
```

終端機 2，傳送一次軟體觸發：

```powershell
.\.venv\Scripts\meters-tool.exe send-command --port 8765
```

執行 `send-command` 指令五次。記錄器會因為 `--max-samples 5` 而在成功取得五個樣本後自動停止。

### 驗證過的 DC 電壓基本功能健檢

這兩個電壓指令在真實的 34461A 上回報正常：自動範圍、手動 10 V 範圍，且 CSV 欄位/數值看起來都很正常。

在相同的儀器上，額外的電壓觸發檢查也回報正常：軟體觸發 (1-2 列)、軟體計時器 (2-3 列) 以及外接觸發 (單一外接邊緣)。搭配 `voltage-dc` 的 `immediate-custom`、`software-custom` 和 `external-custom` 粗略檢查也正常。

Dry-run Auto Zero once 檢查：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --auto-zero once `
  --max-samples 1 `
  --dry-run `
  --status-format jsonl
```

模擬 Auto Zero once 工作流程檢查：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "SIM::34461A" `
  --csv ".\data\simulate_voltage_auto_zero_once.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --auto-zero once `
  --max-samples 1 `
  --simulate `
  --status-format jsonl
```

自動範圍，單一即時電壓樣本：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\voltage_auto_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --auto-range on `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

手動 10 V 範圍，單一即時電壓樣本：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\voltage_range10_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --auto-range off `
  --range 10 `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

實際 Auto Zero once 快速功能健檢：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\voltage_auto_zero_once_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --auto-range on `
  --auto-zero once `
  --nplc 1.0 `
  --max-samples 1 `
  --status-format jsonl
```

對於電壓列，預期 CSV 中的 `measurement_type=voltage_dc` 且 `unit=V`。電壓也可以透過 `--measurement voltage-dc` 來配合自訂/緩衝模式使用；這些路徑使用相同的量測設定以及現有的自訂模式觸發/讀取流程。在信賴電壓緩衝擷取以進行生產前，請先使用操作者提供的 VISA 資源執行較長期的緩衝驗證。

DCV Input Z 快速功能健檢，自動模式：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\voltage_dcv_input_z_auto_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --auto-range on `
  --dcv-input-impedance auto `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

DCV Input Z 快速功能健檢，固定 10 MOhm：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\voltage_dcv_input_z_10m_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --auto-range on `
  --dcv-input-impedance 10m `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

對於這些檢查，請確認前面板 Input Z 狀態是否符合預期變更：`auto` 應選擇自動並在較低的 DC 電壓範圍顯示 HighZ，而 `10m` 應選擇固定的 10 MOhm。這兩個 DCV Input Z 快速功能健檢在 `v1.0.0-cli` 基準前於真實 34461A 上回報正常。

### DCV 比率 (Ratio) 快速功能驗證

DCV 比率使用 34461A 的 `VOLT:DC:RAT` 功能。在進行實際操作前，請依照儀器手冊連接信號和參考導線；錯誤連接的比率量測可能數值看起來合理，但量測的卻是錯誤的關係。

Dry-run DCV Ratio 檢查：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --trigger-mode immediate `
  --measurement voltage-dc-ratio `
  --max-samples 1 `
  --dry-run `
  --status-format jsonl
```

模擬 DCV Ratio 工作流程檢查：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "SIM::34461A" `
  --csv ".\data\simulate_voltage_dc_ratio.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc-ratio `
  --max-samples 1 `
  --simulate `
  --status-format jsonl
```

實際 DCV Ratio 快速功能健檢：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\voltage_dc_ratio_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc-ratio `
  --auto-range on `
  --nplc 1.0 `
  --max-samples 1 `
  --status-format jsonl
```

對於 DCV 比率資料列，預期 `measurement_type=voltage_dc_ratio` 且 `unit=ratio`，若後端支援 `DATA2?`，則 CSV/JSONL `measurement_metadata` 會包含信號/參考電壓欄位。

### AC 電流與電壓快速功能驗證

AC 電流與 AC 電壓使用與其他純量（scalar）量測相同的觸發/讀取流程。它們設定 34461A 的 AC 功能、自動/手動範圍與選用的 AC 頻寬。對於 AC 量測，CLI 不會寫入 NPLC 或 Auto Zero SCPI。在實際驗證時，請從即時模式、自動範圍開啟與 `--max-samples 1` 開始，然後對照 CLI CSV 欄位與 34461A 前面板讀數。

Dry-run AC 頻寬檢查：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --trigger-mode immediate `
  --measurement voltage-ac `
  --ac-bandwidth-hz 20 `
  --max-samples 1 `
  --dry-run `
  --status-format jsonl
```

模擬 AC 頻寬工作流程檢查：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "SIM::34461A" `
  --csv ".\data\simulate_voltage_ac_bw20.csv" `
  --trigger-mode immediate `
  --measurement voltage-ac `
  --ac-bandwidth-hz 20 `
  --max-samples 1 `
  --simulate `
  --status-format jsonl
```

建議的自動範圍 AC 電壓快速功能健檢：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\voltage_ac_auto_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-ac `
  --ac-bandwidth-hz 20 `
  --auto-range on `
  --max-samples 1
```

建議的手動範圍 AC 電流快速功能健檢：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\current_ac_range100ma_smoke.csv" `
  --trigger-mode immediate `
  --measurement current-ac `
  --auto-range off `
  --range 0.1 `
  --max-samples 1
```

對於 AC 資料列，預期 `measurement_type=voltage_ac` 且 `unit=V`，或 `measurement_type=current_ac` 且 `unit=A`。在實機快速功能驗證期間，請對照 CLI CSV 資料列與 34461A 前面板讀數，確認無誤後再依賴較長期的擷取。

### 頻率與週期快速功能驗證

頻率（Frequency）與週期（Period）共用純量（scalar）`READ?`、硬體觸發 `FETC?` 以及緩衝擷取路徑。它們的有效預設值為自動範圍（Auto Range）、`20` Hz AC 濾波器與 `0.1` 秒閘門時間（gate time）。頻率預設為自動逾時。週期不會傳送逾時 SCPI，並保持儀器現有的週期逾時狀態不變。

在實機 I/O 前預覽各個設定：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "<VISA_RESOURCE>" `
  --measurement frequency `
  --trigger-mode immediate `
  --max-samples 1 `
  --dry-run `
  --status-format jsonl

.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "<VISA_RESOURCE>" `
  --measurement period `
  --trigger-mode immediate `
  --max-samples 1 `
  --dry-run `
  --status-format jsonl
```

檢閱規劃後，一個有界限的自動範圍實機快速功能健檢將使用相同的指令，但不加上 `--dry-run`，並提供明確的 `--csv` 路徑。請分別執行頻率與週期，各擷取一個樣本，並將 CSV 數值與前面板進行對比。頻率的資料列使用 `measurement_type=frequency`, `unit=Hz`；週期的資料列使用 `measurement_type=period`, `unit=s`。

透過 `scripts\live-cli-check.ps1 -Suite frequency-period` 可執行相同的一對檢查。包裝器會先執行行前檢查（preflight）與 dry-run 規劃，在實機 I/O 前需要互動式確認，在每個規劃的頻率/週期指令後檢查 SCPI 錯誤佇列，並將診斷結果及每個量測值和單位記錄在 `report.json` 與 `summary.md` 中。`-PlanOnly` 保持為無硬體模式且不會執行 SCPI 探測。

### 驗證過的 2 線式電阻快速功能健檢

這兩個電阻指令在真實 34461A 上回報正常：自動範圍、手動 1000 Ohm 範圍，且 CSV 欄位/數值看起來都很正常。

自動範圍，單一即時電阻樣本：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\resistance_2w_auto_smoke.csv" `
  --trigger-mode immediate `
  --measurement resistance-2w `
  --auto-range on `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

手動 1000 Ohm 範圍，單一即時電阻樣本：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\resistance_2w_range1000_smoke.csv" `
  --trigger-mode immediate `
  --measurement resistance-2w `
  --auto-range off `
  --range 1000 `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

對於電阻列，預期 CSV 中的 `measurement_type=resistance_2w` 且 `unit=Ohm`。量測值應對於連接的電阻或開路/治具狀態是合理的。`resistance-2w` 也支援現有的軟體、計時器、外接和自訂/緩衝模式；在生產環境使用這些觸發路徑前，請先執行專注的實體儀器檢查。

### 4 線式電阻快速功能健檢

這些指令使用與其他純量（scalar）量測相同的觸發/讀取流程，但 4 線式 SCPI 功能為 `FRES`。CLI 不會寫入 `FRES:ZERO:AUTO`，因為 34461A 在內部處理 4 線電阻的 Auto Zero。移除 `FRES:ZERO:AUTO` 後，這些快速功能健檢在真實的 34461A 上回報正常。

自動範圍，單一即時 4 線電阻樣本：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\resistance_4w_auto_smoke.csv" `
  --trigger-mode immediate `
  --measurement resistance-4w `
  --auto-range on `
  --nplc 1.0 `
  --max-samples 1
```

手動 1000 Ohm 範圍，單一即時 4 線電阻樣本：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\resistance_4w_range1000_smoke.csv" `
  --trigger-mode immediate `
  --measurement resistance-4w `
  --auto-range off `
  --range 1000 `
  --nplc 1.0 `
  --max-samples 1
```

對於 4 線電阻列，預期 CSV 中的 `measurement_type=resistance_4w` 且 `unit=Ohm`。請根據所選的前面板或後面板端子，使用 Kelvin 導線或適當的 HI/LO Sense 接線。

### 軟體觸發附帶 Metadata

```powershell
.\.venv\Scripts\meters-tool.exe send-command `
  --port 8765 `
  --arguments-json "{""metadata"":{""batch"":""A1"",""operator"":""lab""}}"
```

命令端點接受此 metadata，並以 JSON 物件字串形式寫入 CSV 的 `trigger_metadata` 欄位。

### 軟體觸發速率限制與佇列限制

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\software_limited.csv" `
  --trigger-mode software `
  --sw-min-interval-ms 250 `
  --sw-queue-max 10 `
  --max-samples 10
```

如果觸發送達的速度快於 `--sw-min-interval-ms`，或者軟體佇列已滿，HTTP 端點將會回報 `429`。

### 軟體計時器，限制樣本執行

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\software_timer_100.csv" `
  --trigger-mode software `
  --timer-interval-s 1.0 `
  --max-samples 100 `
  --auto-range off `
  --range 0.1 `
  --auto-zero off `
  --nplc 1.0
```

此模式由電腦控制並使用 `READ?`。它被設計為一個便利型的記錄器，而非無損的精密計時模式。

### 外接硬體觸發，限制樣本執行

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\external_10.csv" `
  --trigger-mode external `
  --max-samples 10 `
  --hw-trigger-slope neg `
  --trigger-timeout-ms 10000 `
  --auto-range off `
  --range 0.1 `
  --auto-zero on `
  --nplc 1.0
```

每個被接受的外接觸發邊緣都會產生一列 `trigger_source=hardware` 的 CSV。硬體觸發逾時被視為正常的保護性重新 arm 條件；它本身不會被計為錯誤。

### 即時模式，限制樣本執行

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\immediate_100.csv" `
  --trigger-mode immediate `
  --max-samples 100 `
  --auto-range off `
  --range 0.1 `
  --auto-zero off `
  --nplc 1.0
```

即時模式不等待 `send-command` 或外接觸發邊緣。請使用 `--max-samples` 以避免意外的長時間連續執行。

### 即時自訂（Immediate Custom）模式

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\immediate_custom_1000.csv" `
  --trigger-mode immediate-custom `
  --trigger-count 1 `
  --sample-count 1000 `
  --auto-range off `
  --range 0.1 `
  --auto-zero off `
  --nplc 1.0
```

此模式使用 34461A 讀取記憶體來減少每個樣本 `READ?` 通訊的開銷。這不是儀器的內部定時模式：樣本步調仍由量測速度、DC/電阻的 NPLC 與 Auto Zero、自動範圍、範圍安定（range settling）以及儀器觸發/樣本行為決定。CSV 的 `trigger_metadata` 會將自訂列標記為 `time_basis=pc_data_remove_time_not_instrument_sample_time`。預期列數為 `trigger_count * sample_count`。除非設定了 `--allow-buffer-overflow-risk`，否則超過 34461A 的 10,000 筆記憶體限制的請求將會被拒絕。

### 軟體自訂（Software Custom）模式

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\software_custom_20.csv" `
  --trigger-mode software-custom `
  --trigger-count 2 `
  --sample-count 10 `
  --auto-range off `
  --range 0.1 `
  --auto-zero off `
  --nplc 1.0
```

從另一個 PowerShell 視窗，為每次請求的觸發發送一次匯流排觸發：

```powershell
.\.venv\Scripts\meters-tool.exe send-command
.\.venv\Scripts\meters-tool.exe send-command
```

此模式透過 `TRIG:SOUR BUS`、`TRIG:COUNT` 和 `SAMP:COUNT` 來 arm 萬用電表。每個被接受 HTTP `send-command` 會傳送一個 `*TRG`。預期列數仍為 `trigger_count * sample_count`；`trigger_count=2` 且 `sample_count=10` 會產生 20 列 CSV。

### 外接自訂（External Custom）模式

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\external_custom_10.csv" `
  --trigger-mode external-custom `
  --trigger-count 1 `
  --sample-count 10 `
  --hw-trigger-slope neg `
  --hw-trigger-delay-s 0 `
  --auto-range off `
  --range 0.1 `
  --auto-zero off `
  --nplc 1.0
```

此模式以 `TRIG:SOUR EXT`、`TRIG:SLOP`、`TRIG:COUNT`、`SAMP:COUNT` 與 `TRIG:DEL` 來 arm 萬用電表，然後以 `DATA:POINts?` / `DATA:REMove?` 從記憶體中排空已完成的讀數。每個外接觸發邊緣都會推進萬用電表的觸發序列。預期列數為 `trigger_count * sample_count`；在一次外接邊緣後，`trigger_count=1` 且 `sample_count=10` 應產生 10 列 CSV。

### LAN 資源範例

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "TCPIP0::<host>::hislip0::INSTR" `
  --csv ".\data\lan_software.csv" `
  --trigger-mode software `
  --max-samples 5
```

如果拔除 USB 後 `list-resources` 仍顯示舊的 USB 資源，請用以下指令僅顯示有回應的資源：

```powershell
.\.venv\Scripts\meters-tool.exe list-resources --live-only
```

當您需要檢視過期資源的錯誤以進行診斷時，請使用 `list-resources --verify`。

### 較慢的高精度 DC/電阻設定

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\software_high_accuracy.csv" `
  --trigger-mode software `
  --auto-range off `
  --range 0.1 `
  --auto-zero on `
  --nplc 10.0
```

`--nplc 10.0` 搭配 `--auto-zero on` 對於 DC/電阻量測而言十分緩慢。若需要較快的外接觸發步調，請考慮使用較低的 NPLC 和關閉 Auto Zero（例如 `--nplc 1.0 --auto-zero off`）。AC、頻率與週期量測不使用 Auto Zero，且僅接受中性 `--nplc 1.0`。

### VM Comp 斜率

除非您需要設定後面板 VM Comp 輸出脈衝斜率，否則請省略 `--vm-comp-slope`。

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "USB0::<vendor_id>::<product_id>::<serial>::0::INSTR" `
  --csv ".\data\vm_comp_pos.csv" `
  --trigger-mode software `
  --max-samples 5 `
  --vm-comp-slope pos
```

## 停止執行

記錄器啟動時會印出本機控制端點：

```text
command endpoint: http://127.0.0.1:8765/command
software stop endpoint: http://127.0.0.1:8765/stop
software status endpoint: http://127.0.0.1:8765/status
local stop keys: Ctrl+C, Ctrl+Break, q
```

從另一個終端機停止：

```powershell
.\.venv\Scripts\meters-tool.exe stop --port 8765
```

其他支援的停止方法：

- 在記錄終端機中按 `Ctrl+C`。
- 在記錄終端機中按 `Ctrl+Break`。
- 在記錄終端機中按 `q`。
- 使用 `--max-samples N` 讓工作器在取得 N 次成功擷取後自動停止。

預期的清除輸出包含：

```text
stop request received
recording stopped
release_to_local: ...
cleanup_release_to_local: ...
software trigger server stopped
```

如果在記錄器已經退出後傳送 `stop`，可能會印出：

```text
already stopped (endpoint not listening)
```

這會被視為成功。

## 主控台狀態輸出

在軟體觸發的執行期間，對於每個連續的等待期間僅會印出一次 `waiting trigger`，而不會在每次短時間輪詢逾時都重複列印。`software-custom` 模式也會對 `waiting software custom trigger` 執行相同的規則。

對於 Agent 自動化，人類易讀的狀態列可以幫助診斷等待和輪詢行為，但穩定的成功/失敗決策仍應依賴程序結束代碼、CSV 列數、`captured=X errors=Y` 以及明確的致命錯誤文字。

成功擷取會列印計數與最新顯示數值，例如：

```text
[status] captured=1 value=12.3 mA
[status] captured=2 value=1.23 kOhm
```

像是 `mA`, `mV`, `kOhm`, `MOhm` 的顯示字首僅用於主控台。CSV 資料列會繼續以量測的基本單位（`A`, `V`, `ratio`, `Hz`, `s`, 或 `Ohm`）儲存原始數值。自訂/緩衝模式可能會一次排空多個讀數；主控台狀態會顯示該次排空批次中的最後一個樣本。

## CSV 輸出

如果省略 `--csv`，記錄器會寫入 `data` 下的 UTC+8 時間戳記檔案，例如 `data/2026-05-11-14-30-05.csv`。傳送 `--csv PATH` 會繼續寫入該確切路徑。

CSV 欄位：

| 欄位 | 說明 |
| --- | --- |
| `timestamp_utc_plus_8` | 讀取樣本時的 UTC+8 時間戳記，序列化為 ISO 8601，帶有 `+08:00` 偏移量。 |
| `measurement_type` | 選取的量測類型，例如 `current_dc`、`voltage_dc`、`voltage_dc_ratio`、`current_ac`、`voltage_ac`、`frequency`、`period`、`resistance_2w` 或 `resistance_4w`。 |
| `value` | 量測數值。 |
| `unit` | 單位，電流為 `A`，電壓為 `V`，DCV 比率為 `ratio`，頻率為 `Hz`，週期為 `s`，電阻為 `Ohm`。 |
| `trigger_id` | 指派給觸發事件的 UUID。 |
| `trigger_source` | `software`, `timer`, `hardware`, `immediate`, `immediate-custom`, `software-custom`, 或 `external-custom`。 |
| `trigger_metadata` | 來自 `send-command --arguments-json` 的 JSON 物件字串，或 `{}`。 |
| `measurement_metadata` | 量測特定內容的 JSON 物件字串，或 `{}`。DCV Ratio 可包含來自 `DATA2?` 的信號/參考電壓欄位。 |
| `resource_id` | 此執行所使用的 VISA 資源。 |
| `status` | 樣本狀態，成功擷取目前為 `ok`。 |

## 疑難排解

- 如果 `uv` 警告硬連結失敗並降級為複製檔案，安裝通常仍已成功。對於跨磁碟或受硬連結限制的環境，請使用 `uv pip install -e ".[all,dev]" --link-mode=copy` 重新執行安裝。
- 如果缺少 `.\.venv\Scripts\meters-tool.exe`，請重新執行 `uv pip install -e ".[all,dev]"`。主控台指令是安裝產物，而非版本控制下的專案檔案。
- 如果 PowerShell 啟用受阻，請繼續使用明確的 `.\.venv\Scripts\python.exe` 或 `.\.venv\Scripts\meters-tool.exe` 指令，而非啟用虛擬環境。
- 如果未出現 VISA 資源，請確認 VISA 執行階段已安裝，且儀器在廠商連線工具中是可見的。
- 如果 `list-resources` 顯示過期的快取資源，請執行 `list-resources --live-only` 來隱藏過期的項目。當需要檢查過期資源錯誤時，請使用 `list-resources --verify`。
- 如果 CLI 指示無法開啟 CSV 輸出檔案，請關閉 Excel 或任何其他程序中的該檔案，或選擇不同的 `--csv` 路徑。
- 如果使用 `--auto-range off`，則必須提供 `--range` 或 `--current-range`。
- 如果 `--dcv-input-impedance` 用於 `--measurement voltage-dc` 或 `--measurement voltage-dc-ratio` 以外的任何量測，CLI 將會拒絕該指令。
- 如果在高精度 DC/電阻設定下遺失外接觸發邊緣，請在變更觸發行為前嘗試 `--nplc 1.0 --auto-zero off`。
- 如果長時間執行的 Windows 主控台看起來像凍結了，請確認 QuickEdit/文字選擇沒有暫停終端機執行。

## 測試

在執行測試前，請依「開發」段落所示，使用 `uv pip install -e ".[all,dev]"` 安裝開發相依套件。

預設 pytest 執行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

與 GitHub Actions 一致的單元測試搜集與執行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```
