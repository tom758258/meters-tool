# Meters Tool CLI

## 文件集

- [CLI 使用者指南](USER_GUIDE.zh-TW.md) - 操作人員工作流程與常見設定指引。
- [CLI README](README.zh-TW.md) - 詳細的 CLI 參考與自動化指南。
- [支援型號](../core/supported-models.md) - 目前型號與確切範圍的支援狀態。
- [變更日誌](../../CHANGELOG.md) - 版本發佈說明與歷史紀錄。
- [CLI 整合](cli-integration.md) - CLI 配接器維護邊界。
- [通用 CLI JSON / JSONL 合約](../contracts/common-cli-jsonl-contract.md) - 共享命令列 JSON 外殼規則。
- [Meters CLI JSON / JSONL 合約](../contracts/meters-cli-jsonl-contract.md) - Meters 命令列 JSON schema 與別名規則。
- [通用協調器工作流程](../contracts/common-orchestrator-workflows.md) - 共享子程序生命週期指引。
- [Meters 協調器工作流程](../contracts/meters-orchestrator-workflows.md) - 用於 Agent 和自動化的 Meters 子程序範例。
- [Meters Worker 合約](../contracts/meters-worker-contract.md) - 用於 Agent 和協調器的 Meters 工作器控制面、JSONL 與產物合約。

適用於支援的數位萬用電表的 CLI 優先 Python 記錄器，支援透過 VISA 進行 DC/AC 電流、DC/AC 電壓、DCV 比率、頻率、週期以及 2 線式或 4 線式電阻量測。
它預設為每個擷取樣本記錄一列 CSV，並支援軟體、外接硬體、立即與自訂/緩衝觸發
工作流程。CSV 可透過 `--no-csv` 停用。透過 `--timer-interval-s` 可在軟體模式中啟用軟體計時器擷取。

對於標準操作人員的工作流程，請從 [CLI 使用者指南](USER_GUIDE.zh-TW.md) 開始。本 README 則將詳細的指令參考、JSON/JSONL 合約、範例及 CLI 特有的行為彙整於一處。

## 內建使用指南

在預設瀏覽器中開啟隨附的離線 CLI 操作使用指南：

```powershell
meters-tool user-guide
meters-tool user-guide --lang en
meters-tool user-guide --lang zh-TW
```

預設指南語言為 English。使用 `--lang en` 或 `--lang zh-TW` 可明確選擇指南語言。指南隨 CLI 一起提供，不需要連線至網路上的文件網站。

`meters-tool <command> --help` 是 CLI 指令與選項參考；`meters-tool user-guide` 則會開啟操作工作流程指南。

`meters-tool` 是目前的單一 distribution 基準。其套件版本是 root `pyproject.toml` 內的 `[project].version`。CLI 保留其匯入套件、主控台指令、JSON/JSONL 合約、包裝器腳本和測試，同時與 Core 和 WebUI 共享同一個版本號。它繼續透過 CLI 公開 Core 量測欄位：
`voltage-dc-ratio`、`frequency`、`period`、`--auto-zero once`、`--ac-bandwidth-hz`、`--gate-time-s`、`--freq-period-timeout` 和 `--current-terminal`。Core 的啟動驗證、dry-run 規劃、執行階段協調、公開整合匯出以及量測命名，仍與僅限配接器的 CLI 事務保持分離。

Python 整合應從 `meters_tool_core` 或 `meters_tool_core.*` 匯入共享的 API。不再支援舊的根層級 Core 模組匯入，例如 `meters_tool.measurement` 和 `meters_tool.instrument`。

## 目前範圍

已實現：

- 透過 PyVISA 偵測到的 USB 和 LAN 資源的 VISA 資源列表。
- DC 電流、DC 電壓、DCV 比率、AC 電流、AC 電壓、頻率、週期以及 2 線或 4 線電阻量測記錄。
- 透過本機 HTTP 端點實現的軟體觸發模式。
- 透過 `GET /status` 實現的本機工作器狀態端點。
- 軟體計時器擷取（作為軟體觸發模式的一部分）。
- 外接硬體觸發模式。
- 立即擷取模式。
- 透過 `--max-samples` 限制樣本數的執行。
- 透過 HTTP、Ctrl+C、Ctrl+Break 或 `q` 進行正常停止。
- 軟體觸發 metadata 儲存至 CSV 中的 `trigger_metadata`。
- 預設產生 UTC+8 時間戳記 CSV，並可透過 `--no-csv` 明確停用。
- 透過 `list-resources --verify` 進行選用的資源驗證。
- 透過 `list-resources --live-only` 進行選用的作用中資源篩選。
- 在開發或已安裝的 Python 環境中，對會開啟 VISA 的 CLI 指令透過 `--visa-library` 提供選用的 PyVISA library/backend 選擇，並以 `--backend` 作為別名。
- 選用的量測控制項：量測類型、自動量程、手動量程、DCV 輸入阻抗、包含 `once` 在內的自動歸零（Auto Zero）、NPLC、AC 頻寬/濾波器、頻率/週期閘門時間（gate time）、頻率逾時（timeout）、電流端子選擇、硬體觸發延遲、硬體觸發斜率與 VM Comp 斜率。
- CSV 啟用時，每筆擷取樣本後立即排空（flush）。

重要限制：

- 本專案目前支援 Keysight 34460A 與 34461A Truevolt DMM 記錄。若省略 `--model`，實機啟動將從已連接之儀器的 IDN 自動偵測型號。
- 當 Start 必須要求 34460A IDN 相符時，請選擇 `--model 34460A`。在實機模式下，這僅作為預期型號防護 (expected-model guard)，並不會覆寫由 IDN 決定的設定檔。在 dry-run 或模擬模式下，它會選擇 34460A 的設定檔限制：無 10 A 電流範圍或電流端子選擇、1000 筆讀值的記憶體，且無基礎設定檔外接觸發模式。
- 當 Start 必須要求 34461A IDN 相符時，請選擇 `--model 34461A`。明確的實機不符會在 setup SCPI 之前失敗。型號名稱由 Core 設定檔邏輯進行標準化與驗證；未知的型號驗證會失敗，並列出支援的型號。
- 實機產品支援具備功能感知與範圍精確性；確切的型號、傳輸與功能支援矩陣請參閱 [支援型號](../core/supported-models.md)。缺少的功能 metadata 會以預設關閉 (fail-closed) 處理，而非繼承其他範圍的支援。
- 34460A 的最大讀值速率低於 34461A，但 CLI 在此版本中不會主動控制高速讀值速率。
- AC、頻率與週期模式透過 `--ac-bandwidth-hz` 公開 34461A 的 `3`、`20` 和 `200` Hz 頻寬/濾波器設定。在實際投入生產使用前，請使用操作人員提供的 VISA 資源執行低風險的實機資源快速功能健檢 (smoke test)，並將 CLI 記錄列與 34461A 前面板讀值進行對比。
- `--nplc` 和 `--auto-zero` 是 DC/電阻控制項。AC 電流、AC 電壓、頻率與週期僅接受中性預設值 `--nplc 1.0`；任何其他 NPLC 值都將被拒絕，因為這些模式不會寫入 NPLC SCPI。它們也不會寫入 Auto Zero SCPI 指令。
- 不支援在同一次執行中混合使用軟體和硬體擷取。
- 單純呼叫 `list-resources` 會列出由探測傳回的 VISA 資源，可能包含過期的快取項目。使用 `list-resources --verify` 開啟每個資源、查詢 `*IDN?`，然後關閉工作階段而不執行清理命令。當您只需要有回應的資源時，請使用 `list-resources --live-only`。ASRL/RS-232 驗證使用短暫的有界限開啟與查詢逾時，因此過期的序列埠項目不會阻擋後續的 USB 或 TCPIP 資源。
- `immediate`（立即）模式可以連續且快速地進行擷取。除非您刻意需要連續執行，否則請使用 `--max-samples`。

## 系統需求

- Python 3.10 或更新版本。
- VISA 執行階段，例如 Keysight IO Libraries Suite 或 NI-VISA。
- 透過 VISA 可見的支援數位萬用電表；目前支援的型號與連線範圍請參閱支援型號文件。34460A 基礎設定檔不假設具備選用的 LAN/LXI 或外接觸發支援。

CLI 在開發／已安裝 Python 環境中，可在 pyvisa-py 已安裝且可載入時傳遞選用的 `@py` backend selector。這只代表 PyVISA 可承接該 selector；實機擷取還另外需要符合已註冊的 Product-open support scope（請參閱 [支援型號](../core/supported-models.md)）。僅安裝 backend 套件不會在未註冊 Product-open scope 下開放 `start-trigger-record` 實機執行。Backend selector 不會改變 SCPI 設定或 Core 驗證。`@bt` selector 保留給未來獨立的 `pyvisa_bt` backend identity；本專案未實作或未提供 pyvisa_bt，沒有 Product-open 的 `@bt` 實機支援 scope，以 `@bt` 進行的 live 使用仍會 fail closed。若要測試 pyvisa-py，僅在需要時安裝其選用套件：

```powershell
uv pip install pyvisa-py pyserial psutil zeroconf
```

System VISA（例如 USB/system-VISA 或 LAN/TCPIP）與選用的 CLI `@py` backend 目前 Product-open 的連線範圍記載於 [支援型號](../core/supported-models.md)。Support-policy validation status 不代表 distribution 已包含該 backend 套件。目前隨附於 Windows 發佈 bundle 的 CLI 執行檔只支援預設 System VISA 路徑；`@py` 未被 bundle，也不屬於 Windows 發佈 bundle 的內容。

## 開發

在 PowerShell 中，切換到專案目錄，建立或重複使用本機虛擬環境，並依照根目錄
[README 安裝](../../README.zh-TW.md#安裝) 章節同步 all-extras 開發環境：

```powershell
cd path\to\meters-tool
uv venv .venv
uv sync --all-extras --link-mode=copy
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --ignore=tests\cli\test_cli_wrappers.py
```

對於 CI 或嚴格的 lock 檔案驗證，可在 sync 命令中加入 `--locked`。一般開發請依照根 README 的普通 `uv sync` 流程。若既有虛擬環境已完成同步，但仍缺少 console wrapper，或需要重建專案安裝 metadata，才使用：

```powershell
uv sync --all-extras --link-mode=copy --reinstall-package meters-tool
```

這個針對性的重新安裝不需要每次開發都執行，也不需要 pip。

在 Windows 上，如果 pytest 遇到暫存目錄權限問題，請使用根 README 所述的 repository-local `.tmp_tests` fallback，例如 `--basetemp .tmp_tests\pytest_tmp`。

安裝後，使用 `meters-tool` 主控台指令來執行專案命令：

```powershell
.\.venv\Scripts\meters-tool.exe <command> [options]
```

`.venv\Scripts\meters-tool.exe` 是安裝時產生的，並非受版本控制的專案檔案。如果遺失，請先依照根目錄 [README 安裝](../../README.zh-TW.md#安裝) 流程使用普通的 `uv sync --all-extras --link-mode=copy`。如果普通同步完成後 wrapper 仍然遺失，請強制 uv 只重新安裝本專案套件：

```powershell
uv sync --all-extras --link-mode=copy --reinstall-package meters-tool
```

這會重建 console wrapper，不需要 pip。如果 PowerShell 因執行原則限制而阻擋啟用，請繼續使用本指南中顯示的明確 `.\.venv\Scripts\...` 命令。

也支援將明確的模組形式作為開發／備援替代方案：

```powershell
.\.venv\Scripts\python.exe -m meters_tool_cli <command> [options]
```

選用的環境啟用：

```powershell
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 因執行原則限制而阻擋啟用，請使用上方顯示的明確 `.\.venv\Scripts\python.exe` 指令。

## Windows bundle 建置

安裝的 `.venv\Scripts\meters-tool.exe` 是一個 virtualenv 主控台包裝器。對於沒有專案環境的機器，它並非獨立的執行檔。

若要建置共用 Windows onedir bundle，請使用根 README 所述的 all-extras 開發環境。完成標準的 `uv sync --all-extras --link-mode=copy` 後，執行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_windows_bundle.ps1
```

輸出為：

```text
dist\meters-tool\
  meters-tool.exe
  meters-tool-webui-launcher.exe
  meters-tool-webui-host.exe
  _internal\
```

重新建置後執行無硬體的快速功能健檢：

```powershell
.\dist\meters-tool\meters-tool.exe --version
.\dist\meters-tool\meters-tool.exe --help
.\dist\meters-tool\meters-tool.exe list-resources --dry-run --json
.\dist\meters-tool\meters-tool.exe start-trigger-record --resource SIM::34461A --simulate --measurement voltage-dc --trigger-mode immediate --max-samples 1 --csv .tmp_tests\cli_exe_smoke.csv --status-format jsonl
```

PyInstaller 會將產生的檔案寫入本機 `build\` 和 `dist\` 目錄。維護中的 bundle 定義是 `scripts\meters-tool-windows.spec`。

## 建置腳本

建置腳本：

| 腳本 | 目的 |
| --- | --- |
| `scripts\build_windows_bundle.ps1` | 建置共用 Windows onedir CLI、WebUI Launcher 與 private Desktop host bundle。 |
| `scripts\build_release.ps1` | 組合 Windows bundle ZIP、wheel、sdist 與 checksums。 |

## CLI 驗證腳本

Repository 提供兩個維護中的 PowerShell CLI 驗證入口：

- `scripts\preflight-cli.ps1`：執行不需要實機的 CLI preflight，涵蓋
  dry-run、simulator、本機控制 client、資源探測 contract 與 mocked pytest
  檢查。
- `scripts\live-cli-check.ps1`：由操作人員執行的實機 CLI 驗證 wrapper。
  它要求明確提供 target、connection 類型與 VISA resource，不會自行掃描、
  推斷或猜測儀器 resource。

### CLI Preflight

進行實機驗證前，先執行 preflight：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\preflight-cli.ps1
```

預設 `-Target` 為 `all`，因此會驗證所有已註冊的 CLI validation target。
若只要驗證單一型號：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\preflight-cli.ps1 `
  -Target keysight-34461a
```

列出目前接受的 target ID：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\preflight-cli.ps1 `
  -ListTargets
```

目前 target ID 為：

```text
keysight-34461a
keysight-34460a
```

Preflight artifact 預設寫入 `.tmp_tests\cli_preflight`。可透過
`-OutputRoot` 指定其他位置，但該路徑必須仍位於 `.tmp_tests` 之下。

Preflight 不需要實體儀器。它會檢查 CLI dry-run 與 simulator 路徑、
software-trigger client dry-run、`list-resources` dry-run contract，以及
mocked CLI resource-discovery tests。每個 target 都會在選定的 preflight
output root 下產生 `report.json` 與 `summary.md`。

### 實機 CLI 驗證

使用 live wrapper 前，先依照本 README 其他實機範例的方式，把操作人員
選定的確切 VISA resource 放入 PowerShell 文件變數：

```powershell
$env:METER_RESOURCE = "USB0::...::INSTR"
```

`METER_RESOURCE` 只是方便文件範例使用的 PowerShell 變數。
Validation wrapper 不會自行尋找或自動讀取這個變數；仍需明確以
`-Resource "$env:METER_RESOURCE"` 傳入。

建議先執行 plan-only：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\live-cli-check.ps1 `
  -Target keysight-34461a `
  -Connection usb `
  -Resource "$env:METER_RESOURCE" `
  -Suite minimal `
  -PlanOnly
```

`-PlanOnly` 會產生並驗證該 suite 的 CLI dry-run plan，不會開啟 VISA
resource。不過 `-Resource` 仍然是必要參數，讓產生的 command 與 artifact
能精確代表預計驗證的 connection。Plan-only 預設仍會先執行 preflight。

如果已經另外執行過 preflight，只想產生 live plan，可在
`-PlanOnly` 下搭配 `-SkipPreflight`：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\live-cli-check.ps1 `
  -Target keysight-34461a `
  -Connection usb `
  -Resource "$env:METER_RESOURCE" `
  -Suite minimal `
  -PlanOnly `
  -SkipPreflight
```

`-SkipPreflight` 刻意不允許用於真正的實機執行。

開始真正的實機驗證前，請確認沒有其他 Meters CLI、WebUI、logger、測試程序或
外部 VISA 應用程式正在使用同一個實體儀器。獨立的並行 client 可能干擾 SCPI
指令/回應順序或儀器狀態。這是操作人員的前置條件；Meters Tool 不會以自動
lock 強制執行此條件。

檢查 plan 後，移除 `-PlanOnly` 即可執行真正的 minimal suite：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\live-cli-check.ps1 `
  -Target keysight-34461a `
  -Connection usb `
  -Resource "$env:METER_RESOURCE" `
  -Suite minimal
```

實機執行會先跑 preflight，並為 suite 中每個 case 產生 dry-run plan。
接著 wrapper 會列出可能對儀器造成的狀態變更，並要求操作人員互動式按下
Enter，之後才會開始真正的 acquisition。若 stdin 被重新導向，
wrapper 不會把它視為實機執行授權。

支援參數：

- `-Target`（別名：`-Model`、`-Profile`）：`keysight-34461a` 或
  `keysight-34460a`。
- `-Connection`（別名：`-Transport`）：`usb` 或 `local` 代表 USB/local
  connection class；`lan` 或 `network` 代表 LAN/network connection class。
- `-Resource`：操作人員選定的確切 VISA resource。即使在 plan-only
  模式下也必須提供。
- `-VisaLibrary`（別名：`-Backend`、`-visa-library`）：選用的 PyVISA
  library/backend selector，例如 `@py`。省略時使用 System VISA。
- `-Suite`：`minimal`、`basic`、`frequency-period`、`external` 或
  `full`。
- `-PlanOnly`：只驗證並寫出 dry-run plan，不開啟 VISA。
- `-SkipPreflight`：僅在 `-PlanOnly` 模式下略過獨立 preflight。

各 suite 範圍：

- `minimal`：執行一個有界限的 immediate DC current case。
- `basic`：涵蓋有界限的 immediate DC/AC 電流與電壓、2 線與 4 線電阻、
  software trigger、software timer、immediate custom 與 software custom
  路徑。
- `frequency-period`：驗證 Frequency 與 Period 的 immediate acquisition
  以及預期 SCPI setup。真正實機執行時，formal CLI case 前還會執行隔離的
  SCPI diagnostic session。
- `external`：涵蓋 simple 與 custom external-trigger acquisition；
  34460A base profile 不支援此 suite。
- `full`：組合適用的 basic、Frequency/Period 與 external suites。
  對 `keysight-34460a` 而言，因 base profile 不支援 external trigger，
  因此會排除 external cases。

驗證 LAN 前，先把 `METER_RESOURCE` 設成操作人員選定的確切 LAN VISA
resource：

```powershell
$env:METER_RESOURCE = "TCPIP0::...::hislip0::INSTR"
```

接著同樣使用明確 resource：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\live-cli-check.ps1 `
  -Target keysight-34461a `
  -Connection lan `
  -Resource "$env:METER_RESOURCE" `
  -Suite minimal
```

若驗證已安裝的選用 backend，例如 pyvisa-py，請明確傳入 backend selector：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\live-cli-check.ps1 `
  -Target keysight-34461a `
  -Connection lan `
  -Resource "$env:METER_RESOURCE" `
  -VisaLibrary "@py" `
  -Suite minimal
```

Live-validation 輸出位於：

```text
.tmp_tests\cli_live\<target>\<connection>\<suite>\<timestamp>\
```

每次執行會將 private raw validation material 與 shareable artifact set
分開保存，完成時會印出 shareable summary 路徑。Validation report 會記錄
target、connection、backend、suite、package version、Git HEAD、dry-run
plans、實際執行 cases 與結果狀態。

成功完成 live validation 只代表取得驗證證據。執行
`live-cli-check.ps1` 本身不會自動把 pending support entry 提升為
Product-open，也不會自動修改 supported-model matrix；support metadata
與文件的變更仍必須由專案明確進行。

## 基本工作流程

對於包含常見設定說明的引導式操作人員路徑，請參閱 [CLI 使用者指南](USER_GUIDE.zh-TW.md)。簡要參考流程如下：

1. 列出 VISA 資源。
2. 選擇資源字串。
3. 在一個終端機中啟動 `start-trigger-record`。
4. 傳送觸發、等待外接觸發邊緣，或使用立即模式。
5. 透過 `stop`、Ctrl+C、Ctrl+Break、`q` 或 `--max-samples` 停止。
6. 檢查預設 CSV 輸出；使用 `--no-csv` 時則讀取 JSONL `sample` events。

### 34460A 設定檔範例

以 34460A 進行實機啟動時，使用 34460A 預期型號防護。同一個 `--model` 值也會在 dry-run 與模擬規劃中選擇 34460A 設定檔：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --model 34460A `
  --resource "$env:METER_RESOURCE" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --max-samples 1
```

對 34460A 自訂模式而言，若預期讀值超過其 1000 筆記憶體限制，需使用 `--allow-buffer-overflow-risk`：

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

此旗標只接受 `trigger_count * sample_count` 超過讀值記憶體的風險；不會允許 10 A 電流範圍、`current_terminal=10`、不支援的觸發模式，或超過選定設定檔讀值記憶體的 `--buffer-drain-size`。

### 已安裝 Python 環境中的選用 PyVISA backend

預設情況下，`meters-tool` 使用 `pyvisa.ResourceManager()`，因此使用系統 VISA 執行階段，例如 Keysight IO Libraries Suite 或 NI-VISA。

在 source checkout、虛擬環境或已安裝的 Python 環境中，CLI 可在 backend 已安裝且可載入時傳遞選用 selector；實機擷取仍另外需要符合已註冊的 Product-open support scope（請參閱 [支援型號](../core/supported-models.md)）。僅安裝其 backend 不會開放 `start-trigger-record`。若要使用 pyvisa-py 進行進階測試，請安裝其選用套件，並在會開啟 VISA 資源的 CLI 指令中傳入 `--visa-library "@py"`：

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

`--backend "@py"` 可作為 `--visa-library "@py"` 的別名。此選項供 CLI 診斷與已安裝環境中的選用 backend 檢查使用。目前隨附於 Windows 發佈 bundle 的 CLI 執行檔只支援預設 System VISA 路徑，且不 bundle `@py`。WebUI 同樣使用固定的預設 System VISA runtime，且不接受 backend override。`@bt` selector 僅保留給未來的 `pyvisa_bt` identity；本專案不提供該 backend，以 `@bt` 進行的 live 使用仍會 fail closed。

pyvisa-py 的 Product-open 範圍記載於 [支援型號](../core/supported-models.md)；這項 validation metadata 不表示特定 distribution 已包含 pyvisa-py。Windows 上的 USBTMC 可能需要 WinUSB/libusb 設定，通常不比 Keysight IO Libraries Suite 或 NI-VISA 簡單。使用 pyvisa-py 與 pyserial 的 RS-232/ASRL 在支援序列 I/O 的儀器上通常直接，但目前 Meters 設定檔以 USB/LAN Truevolt DMM 為目標。`PYVISA_LIBRARY="@py"` 仍會直接影響 PyVISA，但本專案建議在 CLI 指令中明確使用 `--visa-library "@py"`，讓測試可重現。

## 指令參考

使用已安裝的主控台指令：

```powershell
.\.venv\Scripts\meters-tool.exe <command> [options]
```

模組形式仍可作為明確的開發／備援替代方案：

```powershell
.\.venv\Scripts\python.exe -m meters_tool_cli <command> [options]
```

| 指令 | 目的 | 典型用法 |
| --- | --- | --- |
| `capabilities` | 列印由 Core 管理的儀器能力與產品支援中繼資料，不執行儀器 I/O。 | 讓腳本在建構請求前檢查設定檔、量測、觸發模式、限制與精確支援範圍。 |
| `manifest` | 列印靜態工具 manifest，包含工具識別與 worker protocol 相容性，不執行儀器或執行階段 I/O。 | 讓 orchestrator 在啟動 worker 前檢視 `tool_id`、`tool_version` 與支援的 worker schema 版本。 |
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

`capabilities` 選項：

| 選項 | 預設值 | 說明 |
| --- | --- | --- |
| `--model MODEL`、`--instrument-model MODEL` | Core 備援設定檔 | 透過 Core 型號解析選擇離線能力設定檔。這不會執行實機偵測，也不會覆寫後續實機執行所偵測到的型號。 |
| `--format text\|json` | `text` | 輸出精簡的人類可讀摘要，或單一可供機器讀取的能力物件。 |
| `--json` | 關閉 | `--format json` 的別名。 |

`manifest` 選項：

| 選項 | 預設值 | 說明 |
| --- | --- | --- |
| `--format text\|json` | `text` | 輸出精簡的人類可讀摘要，或單一可供機器讀取的 manifest 物件。 |
| `--json` | 關閉 | `--format json` 的別名。 |

`manifest --json` 會發出一個 `event: tool_manifest` 物件並以 `0` 結束。它不會執行 VISA I/O、不啟動執行階段工作階段或 HTTP 伺服器、不建立檔案，也不變更設定。它描述工具本身而非儀器能力；型號／功能探索仍由 `capabilities` 負責。

```json
{
  "event": "tool_manifest",
  "schema_version": 2,
  "tool_id": "meters",
  "tool_version": "3.1.2",
  "worker_protocol": {
    "compatibility_policy": "v2-only",
    "schema_versions": [2]
  }
}
```

`worker_protocol` 欄位回報支援的 Common worker schema 版本與相容性政策。Orchestrator 必須將非 v2 的 schema 視為不支援，而不是進行協商。

`list-resources` 選項：

| 選項 | 說明 |
| --- | --- |
| 無 | 列印由 PyVISA 傳回的原始 VISA 資源。這可能包含過期的快取資源，且不會開啟資源或執行釋放回本機清除。 |
| `--verify` | 開啟每個偵測到的資源、查詢 `*IDN?`，然後關閉工作階段與資源管理員。不執行擷取清理，也不傳送 release-to-local SCPI。文字輸出將資料列標記為 `live`（作用中）或 `stale`（過期）；JSON 輸出包含 `live`、`status` 和 `detail`。ASRL/RS-232 檢查使用短暫的有界限逾時。 |
| `--live-only` | 驗證資源並僅列印有回應的資料列。這隱含 `--verify`，會隱藏過期資源，並在 ASRL 過期逾時後繼續執行。驗證會在 `*IDN?` 查詢後關閉每個工作階段與資源管理員，不執行擷取清理或 release-to-local SCPI。如果沒有連接或可連線的資源，文字輸出會列印 `no live VISA resources found`。 |
| `--dry-run` | 列印資源探測合約並以 0 退出，而不建立 VISA 資源管理員、列出資源、開啟資源、查詢 `*IDN?` 或執行釋放回本機控制／清理。可與 `--verify`、`--live-only` 和 `--json` 結合使用。 |
| `--visa-library TEXT`、`--backend TEXT` | 已安裝環境中的選用 PyVISA library/backend 引數，例如 `@py`；backend 套件必須已安裝且可載入。省略時，透過 `pyvisa.ResourceManager()` 使用系統預設 VISA 執行階段。 |
| `--serial-read-termination VALUE` | 僅適用於 ASRL 資源的 CLI 探測/驗證相容性設定。接受 `CRLF`、`LF`、`CR` 與 `NONE`。查詢 `*IDN?` 前會將它映射到 PyVISA session 的 `read_termination`；不是擷取設定。 |
| `--serial-write-termination VALUE` | 僅適用於 ASRL 資源的 CLI 探測/驗證相容性設定。接受 `CRLF`、`LF`、`CR` 與 `NONE`。查詢 `*IDN?` 前會將它映射到 PyVISA session 的 `write_termination`；不是擷取設定。 |
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
| `--json` | 關閉 | `--format json` 的別名。 |
| `--dry-run` | 關閉 | 在本機預覽請求而不傳送 HTTP。 |

`stop` 選項：

| 選項 | 預設值 | 說明 |
| --- | --- | --- |
| `--port N` | `8765` | 本機停止端點連接埠。支援範圍：`1` 到 `65535`。 |
| `--timeout-ms N` | `3000` | HTTP 用戶端逾時（毫秒）。支援範圍：`100` 到 `600000`。 |
| `--format text\|json` | `text` | 回應輸出格式。`json` 為 Agent 呼叫端發出一個結構化物件。 |
| `--json` | 關閉 | `--format json` 的別名。 |
| `--dry-run` | 關閉 | 在本機預覽請求而不傳送 HTTP。 |

`status` 選項：

| 選項 | 預設值 | 說明 |
| --- | --- | --- |
| `--port N` | `8765` | 本機狀態端點連接埠。支援範圍：`1` 到 `65535`。 |
| `--timeout-ms N` | `3000` | HTTP 用戶端逾時（毫秒）。支援範圍：`100` 到 `600000`。 |
| `--format text\|json` | `text` | 回應輸出格式。`json` 發出一個正規化的狀態物件。 |
| `--json` | 關閉 | `--format json` 的別名。 |
| `--dry-run` | 關閉 | 在本機預覽非變更性的 GET 請求而不傳送 HTTP。 |

`wait-ready` 選項：

| 選項 | 預設值 | 說明 |
| --- | --- | --- |
| `--port N` | `8765` | 本機狀態端點連接埠。支援範圍：`1` 到 `65535`。 |
| `--timeout-ms N` | `10000` | 整體準備就緒期限（毫秒）。支援範圍：`100` 到 `600000`。 |
| `--format text\|json` | `text` | 回應輸出格式。`json` 發出正規化狀態加上準備就緒計時欄位。 |
| `--json` | 關閉 | `--format json` 的別名。 |

## 觸發模式

| 模式 | 擷取如何開始 | 讀取路徑 | CSV `trigger_source` | 備註 |
| --- | --- | --- | --- | --- |
| `software` | `send-command` 發送至本機 HTTP 端點，或 `--timer-interval-s` 建立自動的計時軟體事件。 | `READ?` | `software` 或 `timer` | 省略 `--trigger-mode` 時的預設值。計時軟體路徑在每次擷取嘗試後使用固定延遲間隔。 |
| `external` | 儀器接收到外接硬體觸發邊緣。 | `FETC?` | `hardware` | 使用 `--trigger-mode external`。 |
| `immediate` | 工作器直接擷取而不等待觸發事件。 | `READ?` | `immediate` | 使用 `--max-samples` 來限制執行樣本數。 |
| `immediate-custom` | 儀器執行明確的立即觸發/取樣序列並將讀值儲存在記憶體中。 | `INIT` + `DATA:POINts?` / `DATA:REMove?` | `immediate-custom` | 需要 `--trigger-count` 和 `--sample-count`；`--max-samples` 無效。 |
| `software-custom` | 儀器準備接收匯流排觸發；每個接受的 `send-command` 會傳送 `*TRG`。 | `INIT` + `*TRG` + `DATA:POINts?` / `DATA:REMove?` | `software-custom` | 需要 `--trigger-count` 和 `--sample-count`；`--max-samples` 和 `--timer-interval-s` 無效。 |
| `external-custom` | 儀器準備接收外接觸發邊緣並將讀值儲存在記憶體中。 | `INIT` + 外接邊緣 + `DATA:POINts?` / `DATA:REMove?` | `external-custom` | 需要 `--trigger-count` 和 `--sample-count`；`--max-samples` 和 `--timer-interval-s` 無效。 |

在 `external` 模式下，意外的軟體觸發會被忽略，且不應中斷硬體觸發流程。在 `immediate` 模式下，軟體觸發同樣會被忽略。

當 `--timer-interval-s` 作用中時，一般的 `send-command` 請求會被忽略，而 `stop` 仍可停止執行。當記錄開始時會擷取第一個計時器樣本；後續的每個計時器樣本會在前一次擷取嘗試完成後，至少等待設定的間隔時間。這是簡單的軟體模式擷取路徑，因此 `--max-samples` 有效，並會在達到該數量成功的計時軟體樣本後停止執行。

## `start-trigger-record` 選項

| 選項 | 是否必要 | 預設值 | 說明 |
| --- | --- | --- | --- |
| `--resource RESOURCE` | 是 | 無 | VISA 資源字串，例如 USB 或 TCPIP HiSLIP。 |
| `--model MODEL`、`--instrument-model MODEL` | 否 | live 為 auto；非確定性 dry-run/simulate 必要 | 接受 canonical model token 或已註冊的穩定型號 ID。它是 live 執行的預期型號防護，也是 dry-run/simulate 的規劃設定檔選擇器。Core 設定檔邏輯會標準化並驗證 `34460A`、`34461A`、`keysight-34460a` 與 `keysight-34461a` 等值。 |
| `--visa-library TEXT`、`--backend TEXT` | 否 | 系統預設 | 已安裝環境中的選用 PyVISA library/backend 引數，例如 `@py`；backend 套件必須已安裝且可載入。Dry-run 與 simulator 執行會接受此選項，但不會開啟 VISA。 |
| `--csv PATH` | 否 | `data/YYYY-MM-DD-HH-MM-SS.csv` | CSV 輸出路徑。若省略，則在 `data` 下建立帶有 UTC+8 時間戳記的檔案。父目錄會自動建立。 |
| `--no-csv` | 否 | 關閉 | 當外部 orchestrator 保存 JSONL `sample` events 時，停用本次執行的 CSV 輸出。不可與 `--csv` 同時使用。 |
| `--status-format text\|jsonl` | 否 | `text` | 執行階段狀態輸出格式。`jsonl` 為 Agent 呼叫端每行發出一個 JSON 物件。 |
| `--dry-run` | 否 | 關閉 | 驗證引數並列印規劃的量測、SCPI、讀取路徑和清除合約，而不開啟 VISA、寫入 CSV 或啟動 HTTP 伺服器。 |
| `--simulate` | 否 | 關閉 | 針對確定的模擬儀器後端執行，而不開啟實機 VISA 工作階段。簡單模式需要有界限的執行，例如 `--max-samples`。 |
| `--json` | 否 | 關閉 | `--status-format jsonl` 的別名。 |
| `--timeout-ms N` | 否 | `5000` | VISA 工作階段逾時（毫秒）。支援範圍：`100` 到 `600000`。 |
| `--trigger-timeout-ms N` | 否 | `10000` | 外接/自訂觸發等待逾時。支援範圍：`500` 到 `600000`。逾時會重新 arm 硬體模式，其本身並非擷取錯誤。對於預期的外接邊緣時間而言太短的值將會重複 arm 而不進行擷取。 |
| `--sw-trigger-port N` | 否 | `8765` | 用於 `/command`、`/stop` 和 `/status` 的本機 HTTP 連接埠。使用 `0` 讓伺服器選擇連接埠，或使用 `1024` 到 `65535`。 |
| `--sw-min-interval-ms N` | 否 | `0` | 接受的軟體觸發之間的最小間隔。使用 `0` 停用速率限制，或使用 `50` 到 `600000`。 |
| `--sw-queue-max N` | 否 | `0` | 佇列軟體觸發的最大數量。支援範圍：`0` 到 `10000`；`0` 使用預設的安全限制。 |
| `--trigger-mode software\|external\|immediate\|immediate-custom\|software-custom\|external-custom` | 否 | `software` | 精確選擇一種擷取模式。支援選項依設定檔而定；34460A 基礎設定檔排除 `external` 與 `external-custom`。 |
| `--max-samples N` | 僅限簡單模式 | 無 | 在成功取得 N 個樣本後自動停止簡單模式。支援範圍：`1` 到 `1000000`。與自訂模式不相容。 |
| `--trigger-count N` | 僅限自訂模式 | 無 | 儀器觸發計數。支援範圍：`1` 到 `1000000`。自訂模式下必要；與簡單模式不相容。 |
| `--sample-count N` | 僅限自訂模式 | 無 | 每次觸發的儀器樣本計數。支援範圍：`1` 到 `1000000`。自訂模式下必要；與簡單模式不相容。 |
| `--timer-interval-s SECONDS` | 否 | 無 | 啟用固定延遲的軟體計時器擷取。支援範圍：`0.5` 到 `86400` 秒。僅在 `--trigger-mode software` 時有效；當省略 `--trigger-mode` 時也有效（因為預設為 software）。可與 `--max-samples` 結合以限制計時器執行次數。 |
| `--buffer-drain-size N` | 僅限自訂模式 | 無 | 每次緩衝區排空移除的最大讀值。支援範圍：`1` 到 `10000`，受儀器設定檔讀值記憶體限制。進階選項，僅在自訂模式下有效；不會變更 `TRIG:COUNT`、`SAMP:COUNT` 或儀器讀值記憶體容量。 |
| `--allow-buffer-overflow-risk` | 否 | 關閉 | 允許自訂模式請求超過選定設定檔的讀值記憶體。這取決於排空讀值的速度是否夠快，可能會遺失資料或產生 SCPI 錯誤；不會允許不支援的範圍、端子、觸發模式，或超過讀值記憶體的 `--buffer-drain-size`。 |
| `--hw-trigger-slope pos\|neg` | 否 | `neg` | 外接觸發邊緣極性。 |
| `--hw-trigger-delay-s SECONDS` | 否 | `0.0` | 硬體觸發延遲，對應到 `TRIG:DEL`。支援範圍：`0` 到 `3600` 秒。 |
| `--measurement current-dc\|voltage-dc\|voltage-dc-ratio\|current-ac\|voltage-ac\|frequency\|period\|resistance-2w\|resistance-4w` | 否 | `current-dc` | 量測類型。 |
| `--nplc VALUE` | 否 | `1.0` | 用於 DC 電流、DC 電壓、DCV 比率和電阻的電源線週期積分時間。DC/電阻/比率的允許值：`0.02`、`0.2`、`1`、`10`、`100`。AC 電流、AC 電壓、頻率與週期僅接受中性預設值 `1.0`。 |
| `--auto-zero on\|off\|once` | 否 | `on` | 支援量測的自動歸零（Auto Zero）。`once` 在 DC 電流、DC 電壓和 2 線電阻下有效。DCV 比率僅接受預設/啟用（on）行為且不寫入 Auto Zero SCPI；4 線電阻、AC 量測、頻率與週期則將 Auto Zero 交給儀器處理。 |
| `--auto-range on\|off` | 否 | `on` | 啟用或停用自動量程（Auto Range）。 |
| `--range VALUE` | 當 `--auto-range off` 時必要 | 無 | 所選量測的手動量程。電流為安培；電壓、頻率與週期的輸入量程為伏特；電阻為歐姆。 |
| `--current-range VALUE` | 僅限 DC 電流 | 無 | 與 `current-dc` 的 `--range` 相容的別名。不可與 `--range` 同時使用；在 AC 電流、電壓和電阻量測下無效。 |
| `--ac-bandwidth-hz 3\|20\|200` | 僅限 AC/頻率/週期 | 依量測而定 | AC 頻寬/濾波器設定。AC 電流/電壓省略時保持目前設定；頻率和週期省略時預設為 `20` Hz。 |
| `--gate-time-s 0.01\|0.1\|1` | 僅限頻率/週期 | `0.1` | 頻率/週期孔徑或閘門時間（gate time），單位為秒。 |
| `--freq-period-timeout auto\|1s` | 僅限頻率 | `auto` | 使用自動頻率逾時（timeout），或停用自動逾時以使用固定 1 秒行為。週期不支援此選項，也不會送出逾時 SCPI。 |
| `--current-terminal 3\|10` | 僅限電流 | 無 | 對公開端子選擇的設定檔而言的電流輸入端子。34461A 的 10 A 範圍需要 `--current-terminal 10`；`--current-terminal 10` 僅在 10 A 範圍下有效。34460A 設定檔拒絕電流端子選擇。 |
| `--dcv-input-impedance default\|10m\|auto` | 僅限 DC 電壓或 DCV 比率 | `default` | DC 電壓輸入阻抗。`default` 不寫入阻抗指令；`10m` 強制為 10 MOhm；`auto` 啟用儀器自動（Auto）模式（在較低的 DC 電壓範圍下可能會顯示 HighZ）。 |
| `--vm-comp-slope pos\|neg` | 否 | 無 | 設定後面板 VM Comp 輸出脈衝斜率。省略以保持 VM Comp 不變。 |

`--measurement` 預設為 `current-dc`，因此現有的電流量測記錄指令不需要特別指定。新指令應偏好使用 `--range`；`--current-range` 繼續適用於現有的 DC 電流腳本。對於 `current-ac`、`voltage-dc`、`voltage-dc-ratio`、`voltage-ac`、`frequency`、`period`、`resistance-2w` 和 `resistance-4w` 請使用 `--range`；`--current-range` 在這些量測下會被拒絕。
`--dcv-input-impedance` 僅在 `--measurement voltage-dc` 或 `--measurement voltage-dc-ratio` 時有效。使用 `default` 以保持儀器目前的 Input Z 設定不變，`10m` 強制為 10 MOhm，或 `auto` 啟用 34461A 的 Auto Input Z 行為。當 Auto 作用於較低 DC 電壓範圍時，儀器可能會顯示 HighZ。

## 友善 Agent 的 CLI 工作流程

在不開啟 VISA 或建立產物的情況下檢查靜態工具 manifest 與能力：

```powershell
.\.venv\Scripts\meters-tool.exe manifest --json
.\.venv\Scripts\meters-tool.exe capabilities --json
```

`manifest` 僅回報工具識別與 worker protocol 相容性。確切 payload 請參閱「指令參考」一節中的 `manifest` 條目。

在不開啟 VISA 或建立產物的情況下，先檢查能力再建構排程器請求：

```powershell
.\.venv\Scripts\meters-tool.exe capabilities --json
.\.venv\Scripts\meters-tool.exe capabilities --model 34461A --json
```

省略 `--model` 時，回應會識別 Core 的備援能力設定檔，並另行指出未執行執行階段身分偵測。判斷實機產品支援是否開放時，必須同時檢查精確的傳輸／後端範圍、要求的量測與觸發模式；不能只依賴彙總的實機驗證狀態。

使用 `--dry-run` 來驗證命令並檢查規劃的 SCPI/讀取路徑，而不接觸實體儀器：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --max-samples 1 `
  --dry-run `
  --status-format jsonl
```

使用 `--simulate` 進行工作流程檢查，而不需要實機 VISA 工作階段：

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

JSONL 輸出是每行一個 JSON 物件。這是專為 Agent 和腳本設計的；預設的文字輸出仍然是面向人類的介面。模擬器數值是確定的工作流程資料，並非真實的 34461A 量測。

自動化呼叫端應解析 JSONL、單一回應 JSON 與 CSV 檔案來做出決策。人類文字訊息僅用於診斷，且可能會因可讀性而有所變更。

有關目前的 schema 和別名規則，請參閱 [Meters CLI JSON / JSONL 合約](../../docs/contracts/meters-cli-jsonl-contract.md)。

有關 Meters 工作器模式、本機控制端點、狀態 payload 以及包裝器產物/報告 schema，請參閱 [Meters Worker 合約](../../docs/contracts/meters-worker-contract.md)。

當工作器執行中，`status` 會包裝非變更性的 `GET /status` 並傳回正規化 JSON 以供協調器健康檢查：

```powershell
.\.venv\Scripts\meters-tool.exe status --port 8765 --json
```

推薦的協調器流程：

1. 執行 `start-trigger-record --dry-run --status-format jsonl` 並驗證規劃（plan）物件。
2. 以相同的命令搭配 `--simulate --status-format jsonl` 與有限範圍（如 `--max-samples`）執行。
3. 對於實機擷取，使用明確的 `--resource` 啟動工作器；在無人值守的實機執行中，絕不可掃描、推斷或猜測 VISA 資源。
4. 等待 JSONL 的 `ready` 事件，或執行 `wait-ready --port 8765 --json`，然後呼叫 `status --port 8765 --json` 來確認 `run_id`。
5. 僅在軟體觸發模式下使用 `POST /command`，並使用 `POST /stop` 進行正常停止。
6. 讀取 stdout 的 JSONL 與預設 CSV 輸出以取得執行結果。使用 `--no-csv` 時，改由 orchestrator 保存 JSONL `sample` events。

請參閱 [Meters 協調器工作流程](../../docs/contracts/meters-orchestrator-workflows.md) 了解完整的 Python 子程序工作流程。

`ready` 事件與 `wait-ready` 代表本機控制面可以接受 `/command`、`/stop` 與 `/status` 請求。它們並不代表第一個樣本已經擷取。使用 JSONL `run_id` 作為同一次執行的 stdout 執行階段事件與 `status` 或直接 `GET /status` 回應之間的關聯鍵。

### send-command --format json

```powershell
.\.venv\Scripts\meters-tool.exe send-command --port 8765 --format json
```

輸出：

```json
{"command": "software_trigger", "event": "send-command", "http_status": 202,
 "job_id": null, "message": "command accepted", "schema_version": 2,
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
 "schema_version": 2, "status": "accepted", "timestamp_utc": "2026-05-18T..."}
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

手動量程值針對每種量測類型進行白名單管理：

| 量測類型 | 允許的 `--range` 值 |
| --- | --- |
| `current-dc` | 34461A：`0.0001`, `0.001`, `0.01`, `0.1`, `1`, `3`, `10` A；34460A：最高 `3` A |
| `current-ac` | 34461A：`0.0001`, `0.001`, `0.01`, `0.1`, `1`, `3`, `10` A；34460A：最高 `3` A |
| `voltage-dc` | `0.1`, `1`, `10`, `100`, `1000` V |
| `voltage-dc-ratio` | `0.1`, `1`, `10`, `100`, `1000` V |
| `voltage-ac` | `0.1`, `1`, `10`, `100`, `750` V |
| `frequency` | `0.1`, `1`, `10`, `100`, `750` V 輸入範圍 |
| `period` | `0.1`, `1`, `10`, `100`, `750` V 輸入範圍 |
| `resistance-2w` | `100`, `1000`, `10000`, `100000`, `1000000`, `10000000`, `100000000` Ohm |
| `resistance-4w` | `100`, `1000`, `10000`, `100000`, `1000000`, `10000000`, `100000000` Ohm |

額外驗證規則：

- `--auto-range off` 需要手動量程。對於 `current-dc`，接受 `--range` 或相容別名 `--current-range`。對於所有其他量測，請使用 `--range`。
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
- `--current-terminal` 僅在公開端子選擇的設定檔之電流量測下有效。34461A 的 10 A 範圍需要 `--current-terminal 10`，而 `--current-terminal 10` 需要 10 A 範圍。34460A 設定檔拒絕電流端子選擇。
- 34460A 基礎設定檔拒絕 `external` 與 `external-custom` 觸發模式。
- 自訂模式需要同時提供 `--trigger-count` 和 `--sample-count`；簡單模式會拒絕這兩個選項。
- 自訂模式拒絕 `--max-samples`；簡單模式使用 `--max-samples` 進行有限的執行。
- `--buffer-drain-size` 和 `--allow-buffer-overflow-risk` 僅在自訂模式下有效。
- 除非設定了 `--allow-buffer-overflow-risk`，否則自訂模式拒絕超過選定設定檔讀值記憶體的 `trigger_count * sample_count`；34461A 的限制為 10000，34460A 的限制為 1000。
- `--timer-interval-s` 需要軟體模式。它在預設觸發模式下有效（因為省略 `--trigger-mode` 會解析為 `software`），也可與 `--max-samples` 結合，在固定數量的計時器資料列後停止。

## 範例

這些範例依照實用操作路徑排序：先確認作用中資源，然後執行單一樣本快速功能健檢，最後使用符合實驗設計的觸發模式。下方的資源字串皆為示意遮蔽值。請使用 VISA discovery 回傳的確切資源，並使用適合您的儀器與測試執行的 CSV 路徑。

在執行下方的實機範例前，從 `list-resources --live-only` 的輸出複製一個確切的資源字串，並在目前的 PowerShell 工作階段中設定一次：

```powershell
$env:METER_RESOURCE = "USB0::...::INSTR"
```

`METER_RESOURCE` 只是 PowerShell 文件範例。CLI 不會自動讀取或搜尋這個環境變數；請透過 `--resource "$env:METER_RESOURCE"` 明確傳入選定的資源。下方 dry-run 範例也使用相同的明確變數以保持一致。請勿猜測、掃描後自動選擇或硬編碼實機硬體資源。

### 列出 VISA 資源

```powershell
.\.venv\Scripts\meters-tool.exe list-resources
```

驗證哪些資源是作用中（live）的：

```powershell
.\.venv\Scripts\meters-tool.exe list-resources --verify
```

驗證只會開啟每個資源、查詢 `*IDN?`，再關閉工作階段與資源管理員。不會執行擷取清理或 release-to-local SCPI。ASRL/RS-232 驗證使用短暫的有界限逾時，並簡潔回報過期的序列埠逾時。

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
live    USB0::...::INSTR    Keysight Technologies,34461A,...
stale   USB0::OLD::RESOURCE::INSTR                     VisaIOError: ...
stale   ASRL6::INSTR                                   ASRL 驗證在 1000 ms 後逾時
```

`--live-only` 仍會驗證每個資源，但會隱藏過期（stale）的資料列。如果沒有資源回應，文字輸出會列印：

```text
no live VISA resources found
```

縮寫的 schema 2 JSON 範例（時間戳記與資源細節僅供說明）：

```json
{
  "count": 1,
  "diagnostic_hints": [],
  "event": "list-resources",
  "live_count": 1,
  "resources": [
    {
      "detail": "Keysight Technologies,34461A,...",
      "live": true,
      "resource": "USB0::...::INSTR",
      "status": "live"
    }
  ],
  "schema_version": 2,
  "stale_count": 0,
  "timestamp_utc": "2026-05-18T...",
  "visa_library": null,
  "verify": true
}
```

`--live-only --format json` 保留相同的資源記錄格式，篩選掉過期的項目，並加入 `live_only`：

```json
{
  "count": 1,
  "diagnostic_hints": [],
  "event": "list-resources",
  "live_count": 1,
  "live_only": true,
  "resources": [
    {
      "detail": "Keysight Technologies,34461A,...",
      "live": true,
      "resource": "USB0::...::INSTR",
      "status": "live"
    }
  ],
  "schema_version": 2,
  "stale_count": 0,
  "timestamp_utc": "2026-05-18T...",
  "visa_library": null,
  "verify": true
}
```

資源字串範例：

```text
USB0::...::INSTR
TCPIP0::...::hislip0::INSTR
```

請直接從 VISA 探測輸出複製實際值，不要手動組合資源字串。


### 實機擷取路徑

在準備實機擷取時，請使用此順序：

1. 執行 `list-resources --live-only` 並選擇作用中的資源。當需要診斷過期的 VISA 快取項目時，請改用 `list-resources --verify`。
2. 以 `--trigger-mode immediate` 與 `--max-samples 1` 執行單一樣本的電流、電壓、頻率、週期或電阻快速功能健檢。
3. 執行實驗所需的特定觸發模式：軟體（可選擇計時）、外接、立即或自訂/緩衝。
4. 確認 CSV 中的 `measurement_type`、`unit`、`trigger_source` 與列數。
5. 在信賴長期無人值守執行前，先用 `stop`、Ctrl+C、Ctrl+Break 或 `q` 確認正常停止行為。

在進行無人值守擷取前，請使用操作人員提供、連接至支援型號的 VISA 資源，以及 Product-open 的確切傳輸/後端範圍。從立即模式、自動量程開啟以及 `--max-samples 1` 開始，然後擴展至預期的量測、觸發模式與緩衝模式。在適用時，請將 CLI CSV 資料列與連接型號的前面板讀值進行對比。請保留型號專屬限制，包括 34460A 的 USB/system-VISA 範圍、1000 筆讀值限制，以及基礎設定檔不支援外接觸發。

### DC 電流快速功能健檢

單一立即電流取樣：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
  --resource "$env:METER_RESOURCE" `
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

實機 10 A 端子快速功能健檢。僅在操作者確認電流路徑對 10 A 輸入端子和預期電流安全後才可執行：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
  --resource "$env:METER_RESOURCE" `
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

### DC 電壓快速功能健檢

Dry-run Auto Zero once 檢查：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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

自動量程，單一立即電壓取樣：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --csv ".\data\voltage_auto_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --auto-range on `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

手動 10 V 量程，單一立即電壓取樣：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --csv ".\data\voltage_range10_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --auto-range off `
  --range 10 `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

實機 Auto Zero once 快速功能健檢：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --csv ".\data\voltage_auto_zero_once_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --auto-range on `
  --auto-zero once `
  --nplc 1.0 `
  --max-samples 1 `
  --status-format jsonl
```

對於電壓列，預期 CSV 中的 `measurement_type=voltage_dc` 且 `unit=V`。電壓也可以透過 `--measurement voltage-dc` 來配合自訂/緩衝模式使用；這些路徑使用相同的量測設定以及現有的自訂模式觸發/讀取流程。在信賴電壓緩衝擷取以進行生產前，請先使用操作者提供的 VISA 資源執行較長期的緩衝檢查。

DCV Input Z 快速功能健檢，自動模式：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
  --resource "$env:METER_RESOURCE" `
  --csv ".\data\voltage_dcv_input_z_10m_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-dc `
  --auto-range on `
  --dcv-input-impedance 10m `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

對於這些檢查，請確認前面板 Input Z 狀態是否符合預期變更：`auto` 應選擇自動並可能在較低的 DC 電壓範圍顯示 HighZ，而 `10m` 應選擇固定的 10 MOhm。

### DCV 比率 (Ratio) 快速功能健檢

DCV 比率 (Ratio) 使用現有的 `VOLT:DC:RAT` 實作。它已對支援的 34461A scope 開放，且 34460A 僅在 USB/system-VISA 上為 `Product-open`。進行實機操作前，請依照儀器手冊連接信號和參考導線；錯誤連接的比率量測可能數值看起來合理，但量測的卻是錯誤的關係。

Dry-run DCV Ratio 檢查：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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

34461A 支援 scope 或 34460A USB/system-VISA 的 Product-open 實機 DCV Ratio 快速功能健檢：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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

AC 電流與 AC 電壓使用與其他純量（scalar）量測相同的觸發/讀取流程。它們設定 34461A 的 AC 功能、自動/手動量程與選用的 AC 頻寬。對於 AC 量測，CLI 不會寫入 NPLC 或 Auto Zero SCPI。在實機驗證時，請從立即模式、自動量程開啟與 `--max-samples 1` 開始，然後對照 CLI CSV 欄位與 34461A 前面板讀值。

Dry-run AC 頻寬檢查：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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

建議的自動量程 AC 電壓快速功能健檢：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --csv ".\data\voltage_ac_auto_smoke.csv" `
  --trigger-mode immediate `
  --measurement voltage-ac `
  --ac-bandwidth-hz 20 `
  --auto-range on `
  --max-samples 1
```

建議的手動量程 AC 電流快速功能健檢：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --csv ".\data\current_ac_range100ma_smoke.csv" `
  --trigger-mode immediate `
  --measurement current-ac `
  --auto-range off `
  --range 0.1 `
  --max-samples 1
```

對於 AC 資料列，預期 `measurement_type=voltage_ac` 且 `unit=V`，或 `measurement_type=current_ac` 且 `unit=A`。在實機快速功能驗證期間，請對照 CLI CSV 資料列與 34461A 前面板讀值，確認無誤後再依賴較長期的擷取。

### 頻率與週期快速功能驗證

頻率（Frequency）與週期（Period）共用純量（scalar）`READ?`、硬體觸發 `FETC?` 以及緩衝擷取路徑。它們的有效預設值為自動量程（Auto Range）、`20` Hz AC 濾波器與 `0.1` 秒閘門時間（gate time）。頻率預設為自動逾時。週期不會傳送逾時 SCPI，並保持儀器現有的週期逾時狀態不變。

在實機 I/O 前預覽各個設定：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --measurement frequency `
  --trigger-mode immediate `
  --max-samples 1 `
  --dry-run `
  --status-format jsonl

.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --measurement period `
  --trigger-mode immediate `
  --max-samples 1 `
  --dry-run `
  --status-format jsonl
```

檢閱規劃後，一個有界限的自動量程實機快速功能健檢將使用相同的指令，但不加上 `--dry-run`，並提供明確的 `--csv` 路徑。請分別執行頻率與週期，各擷取一個取樣，並將 CSV 數值與前面板進行對比。頻率的資料列使用 `measurement_type=frequency`, `unit=Hz`；週期的資料列使用 `measurement_type=period`, `unit=s`。

### 2 線式電阻快速功能健檢

自動量程，單一立即電阻取樣：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --csv ".\data\resistance_2w_auto_smoke.csv" `
  --trigger-mode immediate `
  --measurement resistance-2w `
  --auto-range on `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

手動 1000 Ohm 量程，單一立即電阻取樣：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --csv ".\data\resistance_2w_range1000_smoke.csv" `
  --trigger-mode immediate `
  --measurement resistance-2w `
  --auto-range off `
  --range 1000 `
  --auto-zero off `
  --nplc 1.0 `
  --max-samples 1
```

對於電阻列，預期 CSV 中的 `measurement_type=resistance_2w` 且 `unit=Ohm`。量測值應對於連接的電阻或開路/治具狀態是合理的。`resistance-2w` 也支援現有的軟體（可選擇計時）、外接和自訂/緩衝模式；在生產環境使用這些觸發路徑前，請先執行專注的實體儀器檢查。

### 4 線式電阻快速功能健檢

這些指令使用與其他純量（scalar）量測相同的觸發/讀取流程，但 4 線式 SCPI 功能為 `FRES`。CLI 不會寫入 `FRES:ZERO:AUTO`，因為 34461A 在內部處理 4 線電阻的 Auto Zero。

自動量程，單一立即 4 線電阻取樣：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --csv ".\data\resistance_4w_auto_smoke.csv" `
  --trigger-mode immediate `
  --measurement resistance-4w `
  --auto-range on `
  --nplc 1.0 `
  --max-samples 1
```

手動 1000 Ohm 量程，單一立即 4 線電阻取樣：

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
  --resource "$env:METER_RESOURCE" `
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
  --resource "$env:METER_RESOURCE" `
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
  --resource "$env:METER_RESOURCE" `
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

### 立即模式，限制取樣執行

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --csv ".\data\immediate_100.csv" `
  --trigger-mode immediate `
  --max-samples 100 `
  --auto-range off `
  --range 0.1 `
  --auto-zero off `
  --nplc 1.0
```

立即模式不等待 `send-command` 或外接觸發邊緣。請使用 `--max-samples` 以避免意外的長時間連續執行。

### 立即自訂（Immediate Custom）模式

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --csv ".\data\immediate_custom_1000.csv" `
  --trigger-mode immediate-custom `
  --trigger-count 1 `
  --sample-count 1000 `
  --auto-range off `
  --range 0.1 `
  --auto-zero off `
  --nplc 1.0
```

此模式使用 34461A 讀值記憶體來減少每個取樣 `READ?` 通訊的開銷。這不是儀器的內部定時模式：取樣步調仍由量測速度、DC/電阻的 NPLC 與 Auto Zero、自動量程、量程安定（range settling）以及儀器觸發/取樣行為決定。CSV 的 `trigger_metadata` 會將自訂列標記為 `time_basis=pc_data_remove_time_not_instrument_sample_time`。預期列數為 `trigger_count * sample_count`。除非設定了 `--allow-buffer-overflow-risk`，否則超過 34461A 的 10,000 筆記憶體限制的請求將會被拒絕。

### 軟體自訂（Software Custom）模式

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
  --resource "$env:METER_RESOURCE" `
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

此模式以 `TRIG:SOUR EXT`、`TRIG:SLOP`、`TRIG:COUNT`、`SAMP:COUNT` 與 `TRIG:DEL` 來 arm 萬用電表，然後以 `DATA:POINts?` / `DATA:REMove?` 從記憶體中排空已完成的讀值。每個外接觸發邊緣都會推進萬用電表的觸發序列。預期列數為 `trigger_count * sample_count`；在一次外接邊緣後，`trigger_count=1` 且 `sample_count=10` 應產生 10 列 CSV。

### LAN 資源範例

```powershell
.\.venv\Scripts\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
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
  --resource "$env:METER_RESOURCE" `
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
  --resource "$env:METER_RESOURCE" `
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

像是 `mA`, `mV`, `kOhm`, `MOhm` 的顯示字首僅用於主控台。CSV 資料列會繼續以量測的基本單位（`A`, `V`, `ratio`, `Hz`, `s`, 或 `Ohm`）儲存原始數值。自訂/緩衝模式可能會一次排空多個讀值；主控台狀態會顯示該次排空批次中的最後一個取樣。

## CSV 輸出

如果省略 `--csv`，記錄器會寫入 `data` 下的 UTC+8 時間戳記檔案，例如 `data/2026-05-11-14-30-05.csv`。傳送 `--csv PATH` 會繼續寫入該確切路徑。傳送 `--no-csv` 會明確停用 CSV writer、CSV 檔案及僅供 CSV 使用的父目錄建立；此選項不可與 `--csv` 同時使用。

CSV 是 Meters-specific artifact，預設仍會產生。當外部 orchestrator 統一保存資料時，請搭配 `--no-csv` 與 `--status-format jsonl`，並保存輸出的 `sample` events。這不會改變量測、status、summary、exit code、HTTP control 或 cleanup。

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

- 如果缺少 `.\.venv\Scripts\meters-tool.exe`，請先依照根目錄 [README 安裝](../../README.zh-TW.md#安裝) 流程使用普通的 `uv sync --all-extras --link-mode=copy`。如果普通同步完成後 wrapper 仍然遺失，請使用：

  ```powershell
  uv sync --all-extras --link-mode=copy --reinstall-package meters-tool
  ```

  這會重建 console wrapper，不需要 pip。
- 如果 PowerShell 啟用受阻，請繼續使用明確的 `.\.venv\Scripts\python.exe` 或 `.\.venv\Scripts\meters-tool.exe` 指令，而非啟用虛擬環境。
- 如果未出現 VISA 資源，請確認 VISA 執行階段已安裝，且儀器在廠商連線工具中是可見的。
- 如果量測或 query 收到預期外的 identity-like 回應、回應在不同指令之間看起來
  錯配或錯位，或執行期間儀器狀態非預期地改變，請先確認是否有其他 Meters CLI、
  WebUI、logger、測試程序或外部 VISA 應用程式正在存取同一個實體儀器。先停止
  競爭中的 controller，再調查其他原因。
- 如果 `list-resources` 顯示過期的快取資源，請執行 `list-resources --live-only` 來隱藏過期的項目。當需要檢查過期資源錯誤時，請使用 `list-resources --verify`。
- 如果 CLI 指示無法開啟 CSV 輸出檔案，請關閉 Excel 或任何其他程序中的該檔案，或選擇不同的 `--csv` 路徑。
- 如果使用 `--auto-range off`，則必須提供 `--range` 或 `--current-range`。
- 如果 `--dcv-input-impedance` 用於 `--measurement voltage-dc` 或 `--measurement voltage-dc-ratio` 以外的任何量測，CLI 將會拒絕該指令。
- 如果在高精度 DC/電阻設定下遺失外接觸發邊緣，請在變更觸發行為前嘗試 `--nplc 1.0 --auto-zero off`。
- 如果長時間執行的 Windows 主控台看起來像凍結了，請確認 QuickEdit/文字選擇沒有暫停終端機執行。
