# Meters Tool WebUI 說明文件

本文件是 WebUI 元件的 WebUI 行為、API、驗證與維護者指南。對於一般的操作人員工作流程與欄位說明，請參閱 [WebUI 使用者指南](USER_GUIDE.zh-TW.md)。

關於版本發佈說明，請參閱套件變更日誌 (changelog)。關於 Core API 和擁有權規則，請參閱 Core 整合指南。請將本指南專注於長期的公開 WebUI 行為與維護者邊界。

## 目的

WebUI 配接器 (adapter) 圍繞 `meters_tool_core` 中共享的 Core 執行階段 (runtime)，提供本機 FastAPI 和瀏覽器介面。

WebUI 擁有以下內容的擁有權：

- 位於 `src/meters_tool_webui/static/` 的瀏覽器介面。
- 位於 `src/meters_tool_webui/web_ui.py` 的 FastAPI 路由結構。
- 面向瀏覽器的請求和回應序列化 (serialization)。
- 從 Core 樣本事件衍生而來的即時數據 (Live data) 顯示狀態。
- 資源掃描顯示。
- 開啟 CSV 行為。
- 開始 (Start)、觸發 (Trigger)、停止 (Stop) 和狀態輪詢 (polling) 的 UI 行為。

Core 擁有以下內容的擁有權：

- 請求驗證。
- Dry-run (預演/模擬執行) 規劃。
- 擷取執行階段。
- 觸發路由。
- 停止控制器行為。
- 寫入 CSV。
- 量測與儀器 metadata。
- SCPI 指令產生與儀器 I/O。
- 釋放至本機 (Release-to-local)、關閉、清除釋放 (cleanup release) 以及控制面 (control-plane) 關閉順序。

WebUI 必須使用 Core 的公開 API，不可依賴 CLI 配接器程式碼或直接存取擷取引擎內部運作。

Core 會驗證量測請求並保護儀器端的限制。WebUI 使用者指南以 UI 術語說明各個欄位；本 README 則將 WebUI 行為、API、驗證與維護者邊界集中整理於一處。

## 套件與進入點 (Entry Point)

WebUI 隨附於單一發行套件 (distribution) 中：

```text
meters-tool
```

Windows 主控台包裝器 (wrapper) 為：

```powershell
.\.venv\Scripts\meters-tool-webui.exe
```

Windows GUI 啟動器包裝器為：

```powershell
.\.venv\Scripts\meters-tool-webui-launcher.exe
```

預設的本機伺服器為：

```text
http://127.0.0.1:8767/
```

該伺服器是一個 Uvicorn/FastAPI 程序。終端機按鍵 `q` 無法停止它。請使用 `Ctrl+C`；如果終端機沒有傳送 SIGINT，請透過 PID 停止監聽中的 `python.exe` 程序。

## 安裝或重新載入

在 repository 根目錄下執行：

```powershell
uv pip install -e ".[all,dev]" --link-mode=copy
```

檢查包裝器：

```powershell
.\.venv\Scripts\meters-tool-webui.exe --version
```

預期版本格式：

```text
meters-tool-webui <package-version>
```

啟動伺服器：

```powershell
.\.venv\Scripts\meters-tool-webui.exe --port 8767
```

或啟動雙擊執行的啟動器：

```powershell
.\.venv\Scripts\meters-tool-webui-launcher.exe
```

啟動器預設為 `127.0.0.1:8767`，當勾選 `Use default port 8767` 時，會停用連接埠 (port) 欄位，並在點擊 Start (啟動) 後開啟瀏覽器，且保持視窗可用，以便透過 Quit 離開以停止本機 Uvicorn 伺服器。

開啟：

```text
http://127.0.0.1:8767/
```

選用的 host 與 port 旗標：

```powershell
.\.venv\Scripts\meters-tool-webui.exe --host 127.0.0.1 --port 8767
```

除非有刻意的原因需要將伺服器公開至本機以外，否則請保持預設的 host 為 `127.0.0.1`。

## 瀏覽器版面配置

目前的 WebUI 版面是一個直接的擷取主控台，而非登陸頁面 (landing page)。

主要區域：

- 標頭：`Meters Tool` 和 `Local acquisition console`。
- `Device / Resource` 列：`VISA resource`、`Live resource`、`Scan Device`，以及 `Device options` 齒輪中的 `Expected model` 選擇器與型號支援摘要。此列預設展開，可收合成資源/型號摘要。
- `Expected model` 選擇器預設為 `Auto-detect`，會在 Start 時使用連接中的儀器 IDN。若明確選擇 `Require 34460A` 或 `Require 34461A`，仍會讀取 IDN，只有在符合時才啟動。偵測到的 IDN 選擇設定檔仍為實機執行階段設定檔。
- 型號支援摘要顯示來自 `/api/capabilities` 的驗證狀態、開啟工作流程群組、型號限制以及傳輸/後端範圍狀態。這僅供操作人員檢視；Core 仍會透過支援原則與執行器最終關卡拒絕不支援的直接後端提交。
- 狀態列 (Status strip)：`State`、`Captured`、`Errors` 和 `CSV`。
- 動作按鈕：`Start`、`Trigger`、`Stop` 和 `Open CSV`。
- 用於裝置/資源設定、執行設定 (run configuration)、量測設定、觸發設定、即時數據 (Live data) 與狀態詳細資料的可摺疊設定面板。
- 即時數據面板包含最新數值、樣本時間、觸發來源、趨勢圖表、統計資料、最近樣本表格以及所選樣本的 metadata。

此 UI 刻意不設計前端建置步驟、Node 套件管理器、外部 CDN 或框架執行階段。靜態資產皆為純 HTML、CSS 和原生的 JavaScript 模組。

## 基本工作流程

1. 啟動 WebUI 伺服器。
2. 開啟 `http://127.0.0.1:8767/`。
3. 手動輸入 VISA 資源或點擊 `Scan Device`。
4. 除非需要強制指定 34460A 或 34461A，否則請在 `Device options` 中將 `Expected model` 保持在 Auto-detect，然後選擇量測與觸發設定。
5. 首次接觸真實儀器時，請保持低風險的預設值：啟用自動範圍 (Auto Range on)、即時觸發 (immediate trigger)，以及較小的 `max_samples` 值。
6. 點擊 `Start`。
7. 觀察狀態列與即時數據面板。
8. 若為手動軟體觸發模式，請在準備就緒時點擊 `Trigger`。
9. 點擊 `Stop` 以請求經由 Core 路由的停止動作。
10. 當執行停止 (inactive) 且 CSV 存在後，點擊 `Open CSV`。

WebUI 每個後端程序僅允許一個作用中的執行 (run)。

## 資源掃描

`Scan Device` 會呼叫：

```text
GET /api/resources?verify=true&live_only=true
```

後端會使用 Core 的資源列表行為。啟用驗證時，它會開啟每個候選資源並查詢 `*IDN?`。當 `live_only=true` 時，它僅會傳回有回應且為作用中 (live) 裝置的資源。

驗證的掃描結果在傳回的 IDN 與支援的 Core 設定檔匹配時，包含可為空的型號 metadata。34460A IDN 傳回 `instrument_model: "34460A"`，而 34461A IDN 則傳回 `instrument_model: "34461A"`。未知的即時 IDN 仍保留在資源列表中，其型號 metadata 為 null，以便操作人員仍能檢查或輸入資源，而不會導致列表失敗。

選擇作用中的資源會將其複製到 `VISA resource` 輸入欄位中。當掃描推斷出支援的型號且 `Expected model` 仍為 Auto-detect 時，瀏覽器可能會載入 `/api/capabilities?model=<model>` 以顯示選項，但仍會將 `Expected model` 保持在 Auto-detect。Start 一律會先執行新的後端 IDN preflight。

使用者仍然可以手動輸入資源，並在掃描後於 `Device options` 中要求特定的 `Expected model`。

WebUI 使用 Core 預設的系統 VISA 執行階段。瀏覽器中不提供 PyVISA backend 選擇器。34461A LAN/TCPIP 已透過此預設系統 VISA 路徑進行驗證。只有在需要可選的 pyvisa-py 診斷時，才使用 CLI 專用的 `--visa-library` 進階選項；已驗證的選用 `@py` 擷取範圍是 34461A LAN/TCPIP。

WebUI 不公開驗證模式。待定的傳輸/後端範圍以及待定的量測或觸發模式功能將在瀏覽器啟動時被封鎖，直到經審核的產物透過精確範圍的 Core 支援 metadata 與說明文件提升為公開支援。瀏覽器會停用產品不可用的功能選項，但該狀態僅為 UX；Core 驗證、支援原則關卡以及 `run_start_session()` 最終關卡仍是安全邊界。34460A LAN/TCPIP 待定範圍僅為未來驗證路徑，在 WebUI 中保持關閉。

## 量測模式

量測選項是透過以下方式自 Core 載入：

```text
GET /api/capabilities
GET /api/capabilities?model=34460A
GET /api/capabilities?model=34461A
```

當省略 `model` 時，`/api/capabilities` 會傳回具有 `defaults.instrument_model = null` 與 `model_resolution.resolved = false` 的相容 34461A 形狀能力表。瀏覽器在 Auto 時不送出 `instrument_model`；明確的 Expected model 選擇會送出 `"34460A"` 或 `"34461A"`。在 Auto-detect 模式下，能力控制項與支援摘要會使用該後備能力檢視，直到 Start 或 Scan 偵測到 IDN。此顯示上下文不會選擇實機驅動程式；實機執行仍使用偵測到的 IDN 選擇設定檔作為執行階段驅動程式。

`/api/capabilities` 也包含額外的支援 metadata。每個確切的實機連線範圍保留其現有的 `validation_status`、`transport_scope` 與 `backend_scope` 欄位，並新增 `features.measurement` 與 `features.trigger_mode` 對照表。功能項目公開其自身的 `validation_status`；量測鍵使用現有的配接器端名稱，例如 `voltage-dc-ratio`。現有的回應欄位不會被移除或重新命名。

瀏覽器使用此 metadata 來顯示型號的實機支援，並停用對目前資源傳輸與 WebUI 固定系統-VISA 後端而言非產品開放的功能。它能區分待定實機驗證、型號不支援以及確切範圍不可用。在資源已知之前，Auto-detect 保持現有的後備能力檢視，且僅使用後備設定檔宣告的產品範圍；它絕不會推廣待定功能。對於 34461A，該 metadata 包含驗證過的 USB/system-VISA、LAN/system-VISA 以及選用的 CLI 專用 LAN/pyvisa-py `@py` 範圍。對於 34460A，DCV Ratio 在 USB/system-VISA 上為 `feature_pending`，而 LAN/TCPIP 範圍則保持 `transport_pending`。現有的量測、觸發、範圍與限制欄位仍是控制項定義的 source of truth。

Expected model 檢查是選用的。Core 會在 Start 時驗證連接儀器的識別資訊。若明確指定的預期型號與新的 IDN preflight 不符，WebUI 會回報選取的型號以及 IDN 中找到的支援型號。

選取的 WebUI 型號不得被視為功能解鎖。停用或隱藏的控制項僅為 UX；Core 支援原則與 `run_start_session()` 最終關卡仍是 WebUI 後端提交的安全邊界。WebUI 不應將 pyvisa-py 後端選擇器作為驗證工具的一部分加入；後端診斷保持 CLI 專用，除非未來的產品決策變更該邊界。

目前呈現的量測模式包括：

- `current-dc`
- `voltage-dc`
- `voltage-dc-ratio`
- `current-ac`
- `voltage-ac`
- `frequency`
- `period`
- `resistance-2w`
- `resistance-4w`

前端絕不可自行發明/虛構量測選項。它應該從 `/api/capabilities` 填入選項、預設值、範圍、NPLC 選項、AC 頻寬/濾波器選項、頻率/週期閘門時間 (gate-time) 選項、頻率逾時 (timeout) 選項、電流端子選項以及量測特有的控制項。

量測特有的 UI 行為：

- NPLC 僅出現在支援的量測中。
- AC、頻率和週期量測不顯示 NPLC。
- AC 濾波器會在支援的 AC 電流、AC 電壓、頻率和週期中顯示。
- AC 電流和 AC 電壓可選擇 `Keep current setting`，此選項不會送出 AC filter payload；頻率和週期則直接選取其預設的 `20 Hz`。
- 閘門時間 (Gate Time) 僅出現在頻率和週期，預設值為 `0.1` 秒。逾時 (Timeout) 僅出現在頻率，預設為 `auto`；週期會隱藏它且不送出逾時 payload。
- 電流端子選擇僅在支援的電流量測中顯示。
- 在 34460A 設定檔選定時，電流範圍排除 10 A 且電流端子選擇會被隱藏，因為基礎 34460A 設定檔沒有 10 A 端子/路徑。自訂模式讀數記憶體限制為 1000 筆。
- 在 34460A USB/system-VISA 範圍下，`voltage-dc-ratio` 仍顯示為已知能力，但被停用，因為其即時狀態為 `feature_pending`。直接 WebUI 啟動保持產品限制，並會拒絕 Ratio 請求。
- DCV Input Z (輸入阻抗) 僅在 `voltage-dc` 與 `voltage-dc-ratio` 中顯示。
- 在 Core 支援的情況下，VM Comp 仍會作為量測選項。
- 透過 Core 能力 (capabilities)，支援的 DC/電阻量測可使用 Auto Zero Once。

## 觸發模式

觸發選項同樣自 `/api/capabilities` 載入。

目前呈現的觸發模式包括：

- `immediate`
- `software`
- `external`
- `immediate-custom`
- `software-custom`
- `external-custom`

確切列表為設定檔專屬。34460A 基礎設定檔隱藏 `external` 與 `external-custom`，因為 LAN/LXI/外接觸發能力為選用且非假設擁有。不支援的 34460A 選項會透過 `/api/capabilities?model=34460A` 予以排除；前端不會維護一個分開的手寫 34460A 選項清單。

對於設定檔清單中保留的觸發模式，瀏覽器也會套用確切範圍的功能狀態。`feature_pending` 與 `not_supported_by_model` 選項將被停用，而 `live_validated_full_suite` 選項則保持可選。不提供驗證模式切換或後端選擇器。

簡單的即時與軟體觸發讀取使用 Core 的 `READ?` 路徑。硬體觸發的簡單讀取在觸發配接器裝載並完成量測後，使用 Core 的 `FETC?` 路徑。

UI 行為：

- 非自訂的觸發模式顯示 `max_samples`。
- `software` 模式可使用選用的軟體計時器。
- 手動軟體觸發模式顯示 `Trigger` 按鈕。
- 自訂觸發模式顯示觸發次數、樣本數、緩衝區排空大小與緩衝區溢位風險。
- 外接觸發模式顯示硬體斜率、硬體延遲與觸發逾時。
- 硬體觸發逾時是保護性的重新準備條件，本身不是擷取錯誤。

WebUI 觸發按鈕將 metadata 發送到後端。空白的觸發 metadata 會送出：

```json
{ "source": "web-ui" }
```

非空白的 metadata 必須是有效的 JSON，且會合併到該預設物件中。

## 開始、停止與清除

Start 呼叫：

```text
POST /api/runs
```

後端將瀏覽器 payload 轉換為 Core `StartRequest`，透過 Core 進行驗證，建立配接器可見的狀態，並在背景工作器上啟動 Core `run_start_session()`。

Stop 呼叫：

```text
POST /api/runs/current/stop
```

停止動作會經由 Core 控制面進行路由。WebUI 程式碼絕不可直接關閉 VISA 握把、呼叫擷取引擎內部或重新排列清除順序。

保留的清除順序：

1. 等待工作器。
2. 釋放儀器回本機。
3. 關閉儀器/工作階段資源。
4. 清除釋放。
5. 停止 HTTP/控制面路徑。

## 即時數據 (Live Data)

即時數據與狀態更新主要由伺服器傳送事件 (SSE) 驅動：

```text
GET /api/runs/current/events
```

這會傳回包含目前狀態快照的 `run-status` 事件的 `text/event-stream`。若 SSE 連線失敗，前端會自動降級為標準輪詢：

```text
GET /api/runs/current
```

狀態回應包含 WebUI 擁有的即時數據欄位：

- `latest_sample`
- `recent_samples`
- `sample_capacity`

樣本視窗限制為最新的 5000 筆樣本。

樣本欄位包含：

- `sequence`
- `timestamp_utc_plus_8`
- `measurement_type`
- `value`
- `unit`
- `trigger_id`
- `trigger_source`
- `trigger_metadata`
- `measurement_metadata`
- `resource_id`
- `status`

即時數據衍生自 `run_start_session()` 發送的 Core `sample` 事件。WebUI 絕不可執行額外的 VISA 讀取或讀取 CSV 檔案來更新即時面板。

已停止的執行保持最新的樣本視窗供操作人員檢閱。啟動新的執行會建立一個新的樣本視窗。

瀏覽器端趨勢圖具有三種僅限前端的縮放模式：

- `Auto deviation` 是預設值，並保留原本的圖表行為。它將執行中的第一個數值樣本保持為基線，並在每次轉譯時重新縮放，使得最大可見偏差對應到中心線往外四個網格步長。
- `Auto absolute` 使用最近可見數值樣本的實際最小值和最大值，並帶有微小襯墊，使線條不會貼在圖表邊界上。
- `Manual span` 將第一個數值樣本保持為中心，並使用操作人員輸入的正數原始單位跨度作為固定的 `baseline +/- span` 範圍。此範圍外的數值會被裁切到圖表邊界。

這些模式僅影響圖表顯示，不影響原始樣本值、統計數據、CSV 輸出、API 樣本 payload、儀器設定或 SCPI 指令。圖表縮放控制項不包含在 `POST /api/runs` 中。

## CSV 輸出、選擇與開啟 CSV

執行 payload 可包含選用的 `csv` 路徑。若省略，Core/預設行為會選擇 CSV 輸出路徑。

`CSV path` 欄位也有一個 `Select` 按鈕。它呼叫：

```text
POST /api/csv/select-folder
```

後端行為：

- 在執行 WebUI 後端的機器上開啟資料夾選擇器。
- 選擇後，傳回：

```json
{
  "selected": true,
  "folder_path": "C:\\path\\to\\folder",
  "csv_path": "C:\\path\\to\\folder\\2026-06-01-14-30-05.csv"
}
```

- 取消時，傳回：

```json
{ "selected": false, "folder_path": null, "csv_path": null }
```

- 如果資料夾選擇器不可用，傳回 `503`。

前端行為：

- 選取的資料夾會在現有的 `CSV path` 輸入欄位中填入傳回的帶有時間戳記的 `.csv` 路徑。
- 操作人員仍可手動編輯或清除 CSV 路徑。
- `Start` 會在點擊時使用輸入欄位中的值。

Open CSV 按鈕呼叫：

```text
POST /api/runs/current/open-csv
```

後端行為：

- 僅開啟管理程式狀態中的目前或上一次完成執行的 CSV。
- 不接受前端提供的檔案路徑。
- 當執行仍為 active 時傳回 `409` 伴隨 `run is still active`。
- 如果沒有可用的已完成 CSV 路徑，傳回 `409` 伴隨 `no completed CSV available`。
- 如果記錄的 CSV 路徑遺失，傳回 `404` 伴隨 `CSV file not found`。
- 成功時，使用 Windows 預設應用程式開啟器並傳回：

```json
{ "opened": true, "csv_path": "..." }
```

前端行為：

- 預設停用。
- 在執行為作用中時停用。
- 當執行為 inactive 且 `csv_path` 存在時啟用。
- 將成功與失敗訊息附加到 Status 日誌中。

## HTTP API 摘要

面向瀏覽器的 API 介面為：

- `GET /`：提供 `index.html`。
- `GET /api/capabilities`：傳回 Core 支援的量測與觸發能力。選用的 `model=34460A` 或 `model=34461A` 選擇設定檔；省略型號會傳回未解析的自動 metadata 以及相容的 34461A 形狀能力表。確切的實機支援範圍新增量測與觸發模式功能狀態對照表，而不移除現有欄位。
- `GET /api/resources?verify=true&live_only=true`：掃描 VISA 資源，且對於驗證過支援的 IDN，包含可為空的 `instrument_model` 與 `matched_profile` metadata。
- `POST /api/runs`：驗證並啟動執行。
- `GET /api/runs/current`：傳回目前或最新的執行狀態。
- `GET /api/runs/current/events`：傳回執行狀態變更的伺服器傳送事件 (SSE) 串流。
- `POST /api/runs/current/command`：為支援的模式排入軟體觸發。傳回常見命令回應外殼：`202` 接受、`400` 驗證錯誤、`429` 佇列/速率拒絕，或在無執行為作用中或執行未就緒時傳回 `409`。
- `POST /api/runs/current/stop`：要求透過 Core 控制面停止。
- `POST /api/runs/current/open-csv`：開啟最新完成的 CSV。
- `POST /api/csv/select-folder`：開啟本機資料夾選擇器，並為現有的 CSV 輸入欄位傳回帶有時間戳記的 CSV 路徑。

請勿重新命名、移除或修改這些端點，否則必須同時更新前端程式碼、測試與文件。

在接受命令回應後，前端會擷取 `GET /api/runs/current` 以更新顯示的執行狀態。命令回應不嵌入完整的執行狀態。

## 前端 Payload 欄位

WebUI 傳送的重要欄位包括：

- `resource`
- `instrument_model`
- `csv`
- `timeout_ms`
- `trigger_timeout_ms`
- `trigger_mode`
- `measurement`
- `nplc`
- `auto_zero`
- `auto_range`
- `measurement_range`
- `dcv_input_impedance`
- `vm_comp_slope`
- `max_samples`
- `timer_interval_s`
- `trigger_count`
- `sample_count`
- `buffer_drain_size`
- `allow_buffer_overflow_risk`
- `hw_trigger_slope`
- `hw_trigger_delay_s`
- `sw_min_interval_ms`
- `sw_queue_max`
- `ac_bandwidth_hz`
- `gate_time_s`
- `freq_period_timeout`
- `current_terminal`

隱藏的控制項必須停用，以防送出非作用中模式的過期值。

頻率與週期 payload 保持原始數值：AC Filter `20 Hz` 以 `ac_bandwidth_hz: 20` 傳送，閘門時間為秒，逾時為 `auto` 或 `1s`。即時數據將頻率顯示為 `Hz`，週期顯示為 `s`，而不進行自動單位縮放。

## 安全規則

將所有影響儀器的變更視為高風險。

未經使用者明確核准，請勿變更以下任何內容：

- SCPI 指令或指令順序。
- VISA 逾時行為。
- 觸發等待策略。
- `TRIG:DEL`。
- NPLC 行為。
- Auto Zero 行為。
- Auto Range 行為。
- VM Comp 行為。
- DCV Input Z 行為。
- 停止行為。
- 釋放/本機行為。
- 清除順序。
- 硬體觸發逾時處理。
- 硬體觸發讀取是否使用 `FETC?`。
- 軟體觸發或即時讀取是否使用 `READ?`。

對於首次真實儀器快速功能健檢，請使用低風險的即時模式、啟用自動範圍與較小的 bounded 樣本數。

## 開發邊界

偏好的 WebUI 前端檔案：

- `src/meters_tool_webui/static/index.html`
- `src/meters_tool_webui/static/styles.css`
- `src/meters_tool_webui/static/*.js`

後端配接器檔案：

- `src/meters_tool_webui/web_ui.py`
- `src/meters_tool_webui/launcher.py`

測試：

- `tests/webui/test_webui_api.py`
- `tests/webui/test_webui_static.py`
- `tests/webui/test_launcher.py`
- 下方驗證指令中列出的 Core 合約與套件邊界測試。

未經使用者明確核准，請勿變更 `pyproject.toml` 中的根套件 metadata。套件名稱、版本、相依套件、主控台指令、建置系統、pytest/ruff/mypy 設定以及 Core/CLI/WebUI 的擁有權皆為產品邊界決策。

## 驗證

優先執行窄範圍的相關檢查。

編輯前端模組後的 JavaScript 語法檢查：

```powershell
Get-ChildItem src\meters_tool_webui\static\*.js |
  ForEach-Object { node --check $_.FullName }
```

針對 WebUI/Core 的無硬體驗證：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/webui/test_webui_package_metadata.py tests/webui/test_webui_api.py tests/webui/test_webui_static.py tests/webui/test_launcher.py -q -p no:cacheprovider
```

在已安裝 `meters-tool` 的環境中，使用 PyInstaller 建置選用的本機啟動器 exe。PyInstaller 是本機版本建置工具，非 WebUI 執行階段相依套件，因此在全新機器上重新建置之前，請將其安裝到 venv 中：

```powershell
uv pip install pyinstaller
```

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_webui_exe.ps1
```

可行時執行更廣泛的無硬體驗證：

```powershell
uv run pytest tests -q -p no:cacheprovider
```

實機驗證需要操作人員提供 VISA 資源。在進行觸發模式或更長期的擷取前，先從低風險的即時模式快速功能健檢、啟用自動範圍且 `max_samples=1` 開始。

完整的測試執行可能會遇到本機 Windows 暫存或 pytest 快取權限警告。請清楚報告這些警告，並在更廣泛的測試套件被環境權限阻擋時，依賴針對性測試與實際儀器驗證。

## 手動 UI 快速健檢清單

無硬體 UI 快速健檢：

- 頁面可在 `http://127.0.0.1:8767/` 載入。
- 首次載入時沒有出現瀏覽器主控台錯誤。
- `Scan Device` 乾淨地更新即時資源選擇器或回報沒有即時資源。
- 量測變更會更新範圍單位、範圍選擇與 NPLC 可見度。
- `voltage-dc` 與 `voltage-dc-ratio` 顯示 DCV Input Z；其他量測會隱藏它。
- AC 量測在支援處顯示 AC 濾波器並隱藏 NPLC。
- 頻率與週期顯示 AC 濾波器與閘門時間。頻率也顯示逾時；週期與其他量測會隱藏並停用它。
- 電流量測在支援處顯示電流端子。
- 觸發模式變更僅顯示與隱藏相關欄位。
- 觸發按鈕僅在手動軟體觸發模式下出現。
- Status log 附加具體訊息，而不洗版重複的輪詢狀態。
- `Show Details` 可切換致命錯誤、清除狀態與原始狀態。
- 在擷取到模擬或真實樣本後，即時數據會轉譯最新值、圖表、統計、表格與選定樣本的 metadata。
- 行動裝置寬度（約 390 像素）沒有文字或控制項重疊。
- 桌面寬度（約 1280 像素）保持密集但易讀。

對於真實儀器快速健檢，除非操作人員明確要求，否則請勿執行高風險的觸發實驗。從即時模式、啟用自動範圍且 `max_samples=1` 開始。

頻率與週期真實儀器檢查：

- 連接 34461A 前面板可量測的穩定訊號。
- 選擇頻率，確認自動範圍、`20 Hz` AC 濾波器、`0.1 s` 閘門時間與 `Auto` 逾時，然後擷取一個即時樣本。
- 確認即時數據值使用原始 `Hz` 並與前面板對比。
- 重複週期步驟，確認原始單位為 `s`。
- 在變更量測類型前停止執行，並在每次量測後檢查產生的 CSV 列。

## 疑難排解

包裝器遺失：

- 重新執行 `uv pip install -e ".[all,dev]" --link-mode=copy`。
- 確認 `.venv\Scripts\meters-tool-webui.exe` 存在。

連接埠已被使用：

- 使用其他連接埠啟動，例如 `--port 8768`。
- 或者停止現有的監聽程序。

`q` 無法停止伺服器：

- 這是預期行為。使用 `Ctrl+C`，或透過 PID 停止監聽中的 `python.exe`。

掃描找不到即時資源：

- 確認儀器已開啟且已連接。
- 確認已安裝 VISA 驅動程式且資源出現在應用程式之外。
- 嘗試手動輸入已知的 VISA 資源。
- 在實機擷取前，從即時模式、啟用自動範圍且 `max_samples=1` 的 smoke 測試開始。

Open CSV 按鈕被停用：

- 等待執行變為 inactive。
- 確認執行產生了 `csv_path`。
- 執行完成後重新整理瀏覽器仍可顯示 `Open CSV`，因為後端會保留最新的已完成 CSV 路徑。

觸發按鈕被隱藏：

- 該按鈕僅針對手動軟體觸發模式顯示：無計時器觸發的 `software` 以及 `software-custom`。

即時面板沒有樣本：

- 確認執行已擷取到樣本。
- 確認狀態輪詢正常。
- 面面板僅使用 Core 樣本事件；它不獨立查詢儀器或解析 CSV 檔案。

## 說明文件地圖

- [WebUI 使用者指南](USER_GUIDE.zh-TW.md)：面向操作人員的 WebUI 使用指南。
- [WebUI README](README.zh-TW.md)：本 WebUI 行為、API、驗證與維護者指南。
- [WebUI 變更規則](web-ui-change-rules.md)：維護者與面向 Agent 的 UI 變更規則。
- [WebUI 變更日誌](CHANGELOG.md)：套件發佈說明。
