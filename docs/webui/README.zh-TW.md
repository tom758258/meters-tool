# Meters Tool WebUI 說明文件

本文件是 WebUI 元件的 WebUI 行為與 API 指南。對於一般的操作人員工作流程與欄位說明，請參閱 [WebUI／Desktop 使用者指南](USER_GUIDE.zh-TW.md)。

關於版本發佈說明，請參閱套件變更日誌 (changelog)。關於 Core API 和擁有權規則，請參閱 Core 整合指南。請將本指南專注於長期的公開 WebUI 行為與整合邊界。

[WebUI 本地化合約](localization-contract.md) 定義瀏覽器呈現的本地化。WebUI 使用不依賴套件的語系 runtime、English fallback、English／繁體中文語系目錄、靜態與動態瀏覽器呈現，以及安全的命名插值。右上角永久顯示的地球與文字按鈕可切換 English 與繁體中文。有效的已儲存語系優先於瀏覽器偵測與 English fallback；手動選擇使用 `meters-tool.webui.locale` 儲存鍵。切換會立即更新頁面，不重新載入或呼叫 runtime/API，並從快取狀態重新轉譯，同時保留表單值、作用中的作業、面板、狀態日誌、Live 取樣、圖表設定、資源 metadata 與支援摘要。未知的 Core/backend/status 診斷、原始 status JSON、取樣 metadata 與 schema 保持原始內容。Core、HTTP API 端點與狀態碼、現有回應欄位、表單值、支援政策、儀器執行階段，以及 CSV/JSON/JSONL schema 都不變。繁體中文語系目錄術語與瀏覽器呈現使用共用的欄位標題配置。

## 目的

WebUI 配接器 (adapter) 圍繞 `meters_tool_core` 中共享的 Core 執行階段 (runtime)，提供本機 FastAPI 和瀏覽器介面。

WebUI 擁有以下內容的擁有權：

- 位於 `src/meters_tool_webui/static/` 的瀏覽器介面。
- 位於 `src/meters_tool_webui/web_ui.py` 的 FastAPI 路由結構。
- 面向瀏覽器的請求和回應序列化 (serialization)。
- 從 Core 取樣事件衍生而來的即時資料 (Live data) 顯示狀態。
- 資源掃描顯示。
- 開啟 CSV 行為。
- 開始 (Start)、觸發 (Trigger)、停止 (Stop) 和 SSE 狀態串流與輪詢備援的 UI 行為。

Core 擁有以下內容的擁有權：

- 請求驗證。
- Dry-run (預演/模擬執行) 規劃。
- 擷取執行階段。
- 觸發路由。
- 停止控制器行為。
- 寫入 CSV。
- 量測與儀器 metadata。
- SCPI 指令產生與儀器 I/O。
- 釋放回本機控制 (release-to-local)、關閉、清理釋放 (cleanup release) 以及控制面 (control-plane) 關閉順序。

WebUI 必須使用 Core 的公開 API，不可依賴 CLI 配接器程式碼或直接存取擷取引擎內部運作。

Core 會驗證量測請求並保護儀器端的限制。WebUI／Desktop 使用者指南以 UI 術語說明各個欄位；本 README 則將 WebUI 行為、API 與整合邊界集中整理於一處。

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

PyInstaller launcher 執行檔位於共用 Windows onedir bundle 內：

```text
dist\meters-tool\meters-tool-webui-launcher.exe
```

虛擬環境 wrapper 需要已安裝的專案環境；`dist\meters-tool\` 資料夾則是共用
Windows onedir 建置產物（詳情請參閱根目錄 [README Build 說明](../../README.zh-TW.md#建置)）。

預設的本機伺服器為：

```text
http://127.0.0.1:8767/
```

該伺服器是一個 Uvicorn/FastAPI 程序。終端機按鍵 `q` 無法停止它。請使用
`Ctrl+C` 進行正常關閉。如果終端機沒有傳送 SIGINT，請先停止作用中的執行
並等待清理完成，再透過 PID 終止監聽程序。強制終止只是最後的復原方式，可能
會略過儀器的正常清理。

## 私有 Desktop Host 整合邊界

`meters_tool_webui._desktop_host` 是供本機 desktop shell 使用的私有整合
邊界。若要在 source environment 中直接啟動或診斷此 private host，請使用
repository virtual environment：

```powershell
.\.venv\Scripts\python.exe -m meters_tool_webui._desktop_host
```

這個直接命令不是 user-facing entry point，也不是另一個 WebUI Launcher。一般
Electron Desktop source development 應從 `desktop/` 啟動 Electron：

```powershell
cd desktop
npm start
```

此 host 僅繫結至 `127.0.0.1` 並使用 Port `0`，從已繫結的 socket 取得作業
系統配置的 ephemeral port，再將同一個 socket 傳給 Uvicorn。它重用既有的
FastAPI application、WebUI static assets、HTTP API 與 `WebRunManager`，沒有
另一套 WebUI implementation，也不會開啟 system browser 或使用 Tkinter。

此 host 透過 stdin/stdout JSONL 提供私有 lifecycle boundary。Stdout 僅供
lifecycle events 使用，包括帶有實際本機 URL 的 `ready` event；Python 與
Uvicorn diagnostics 一律使用 stderr。收到 `{"command":"shutdown"}` stdin
message 時，會先執行既有的 `WebRunManager.shutdown()` cleanup。只有 cleanup
成功後才停止 Uvicorn 並關閉已繫結的 socket；若 cleanup 未完成，host 會輸出
`shutdown_incomplete` event 並保持執行。

`desktop/` 中的 Electron shell 會啟動這個 private host 並使用既有 JSONL
lifecycle。Development mode 透過 repository virtual environment 啟動 host；
packaged Windows directory 則啟動與 Electron executable 位於同一目錄的共用
`meters-tool-webui-host.exe`。Shell 會等待 `ready`、從該 event 取得 loopback
URL、在 sandboxed BrowserWindow 載入同一套既有 WebUI，並在關閉前要求同一套
graceful shutdown。它不擁有另一套 FastAPI application、frontend、HTTP API、
Python runtime 或 run cleanup implementation。

## 安裝或重新載入

主要專案設定請遵循根目錄 [README 安裝](../../README.zh-TW.md#安裝) 章節。
該流程會建立專案虛擬環境，並使用 copy link mode 同步 all-extras 環境。

如果既有虛擬環境缺少一個或多個 WebUI console wrapper，請使用根 README 的 console-wrapper 疑難排解流程。

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

主控台伺服器支援 `--host` 與 `--port`。啟動器一律繫結至 `127.0.0.1`，
未提供參數時會從 `8767` 開始，透過實際 socket bind 最多嘗試到 `8866`。
成功 bind 後會將同一個 socket 直接交給 Uvicorn，等待
`/api/capabilities` 回傳 `meters-tool-webui` identity，再以實際 Port 開啟
瀏覽器。其他已執行的 Meters Tool WebUI 與任何其他 Port 擁有者相同，都不會
被重用。

可指定固定 Port，或指定自動搜尋起點：

```powershell
.\.venv\Scripts\meters-tool-webui-launcher.exe --port 9000
.\.venv\Scripts\meters-tool-webui-launcher.exe --port 9000 --auto-port
```

`--port 9000` 只嘗試 `9000`。加上 `--auto-port` 時，最多嘗試
`9000` 到 `9099` 共 100 個 Port。單獨使用 `--auto-port` 會採用預設起點；
接近 `65535` 時則於合法 Port 上限停止。

正常啟動期間不會顯示 Port 控制項。瀏覽器開啟後，Launcher 只顯示實際 URL
與 `Quit`。只有全部自動候選都被占用時才顯示完整 Port 視窗；此後每次手動
Start／Retry 都只嘗試輸入的 Port 一次。

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

目前的 WebUI 版面是一個直接的擷取主控台，而非著陸頁面 (landing page)。

主要區域：

- 右上角工具列：語言、主題與 `說明`（英文介面為 `Help`）控制項。
- 標頭：`Meters Tool` 和 `Local acquisition console`。
- `Device / Resource` 列：`VISA resource`、`Live resource`（實機資源）、`Scan Device`、`支援裝置` 清單，以及 `Device options` 齒輪中的執行模式、型號選擇器與型號支援摘要。此列預設展開，可收合成包含目前執行模式的資源/型號摘要。
- `Expected model` 選擇器預設為 `Auto-detect`，會在 Start 時使用連接中的儀器 IDN。若明確選擇 `Require 34460A` 或 `Require 34461A`，仍會讀取 IDN，只有在符合時才啟動。偵測到的 IDN 選擇設定檔仍為實機執行階段設定檔。
- 型號支援摘要顯示來自 `/api/capabilities` 的驗證狀態、開啟工作流程群組、型號限制以及傳輸/後端範圍狀態。這僅供操作人員檢視；Core 仍會透過支援原則與執行器最終關卡拒絕不支援的直接後端提交。
- 狀態列 (Status strip)：`State`、`Captured`、`Errors` 和 `CSV`。
- 動作按鈕：`Start`、`Trigger`、`Stop` 和 `Open CSV`。
- 用於裝置/資源設定、執行設定 (run configuration)、量測設定、觸發設定、即時資料 (Live data) 與狀態詳細資料的可摺疊設定面板。
- 即時資料面板包含最新讀值、取樣時間、觸發來源、趨勢圖表、統計資料、最近取樣表格以及所選取樣的 metadata。

`支援裝置` 按鈕會開啟一個精簡的 WebUI 連線清單，僅顯示目前 WebUI 正式支援的連線方式（由 Core 能力 metadata 衍生）。如需操作人員所見之連線清單，請參閱 [WebUI／Desktop 使用者指南](USER_GUIDE.zh-TW.md)；確切的產品支援型號與連線範圍請參閱 [支援型號](../core/supported-models.md)。

### 瀏覽器語言

右上角永久顯示的地球與文字按鈕可在 English 與繁體中文之間切換。可見標籤顯示目前語系：English 介面顯示 `English`，繁體中文介面顯示 `繁體中文`；無障礙名稱則描述點擊後的目的地語言。語言與外觀控制以各自帶標籤的設定項並排於右上角。首次載入時，WebUI 依序使用有效的已儲存語系、瀏覽器語言偵測，最後才使用 English。手動選擇會儲存在 `meters-tool.webui.locale`；偵測到的語系不會自動寫入。切換會改變 `<html lang>`，但不重新載入或呼叫 runtime endpoint，並保留目前的表單、作用中的作業、面板、狀態、Live data、圖表、資源與支援摘要狀態。未知的診斷文字保持原始內容。

English／繁體中文呈現使用以下術語規則。繁體中文的 Measurement options 控制項顯示 `自動量程（Auto range）`；精簡摘要繼續使用 `自動量程`。選用標記與欄位標題保持同一行，包括 AC filter 與 Current terminal，僅在 viewport 太窄時自然換行。

此 UI 刻意不設計前端建置步驟、Node 套件管理器、外部 CDN 或框架執行階段。靜態資產皆為純 HTML、CSS 和原生的 JavaScript 模組。

### 內建說明

`說明` 位於右上角工具列。在瀏覽器 WebUI 中，點擊後會在新的瀏覽器分頁
開啟隨附的 WebUI／Desktop 使用者指南；在 Electron Desktop 中，指南會使用
系統預設瀏覽器開啟。開啟的指南會依目前選取的 WebUI 語言顯示，支援 English
與繁體中文。兩種入口使用相同的隨附說明內容，且不依賴外部文件網站。

## 執行模式

`Device options` 提供三種僅限目前頁面的執行模式：

- `Real` 是每次載入頁面的預設值，維持既有的 VISA resource、掃描、IDN preflight、支援原則、擷取、觸發、CSV、Stop 與清理行為。
- `Simulate` 必須明確選擇 34460A 或 34461A，並使用 Core 的 deterministic simulator 完整執行 acquisition runtime。它不會掃描、開啟、查詢真實 VISA resource，也不會向其送出指令。模擬 sample 會使用一般 status/event 路徑，因此最新讀值、圖表、統計資料、最近 sample、Stop 與正常 CSV 行為都可使用。
- `Dry-run` 必須明確選擇 34460A 或 34461A planning model，且只建立 Core execution plan。它不建立 active run、不執行 acquisition 或真實 VISA I/O，也不產生 Live data sample。計畫會顯示於 Status details，包括 SCPI commands、read path、cleanup steps 與 option summary。開始 preview 時會清除上一次 runtime 留在畫面上的 Live data。

Execution mode 不會儲存於 local storage、cookie 或其他持久化設定；Start／Preview request pending 或 active run 期間不可切換，重新載入頁面一律回到 `Real`。Simulation 與 Dry-run 結果都不能作為實機驗證成功的證據。

## 基本工作流程

1. 啟動 WebUI 伺服器。
2. 開啟 `http://127.0.0.1:8767/`。
3. 手動輸入 VISA 資源或點擊 `Scan Device`。
4. 除非需要強制指定 34460A 或 34461A，否則請在 `Device options` 中將 `Expected model` 保持在 Auto-detect，然後選擇量測與觸發設定。
5. 首次接觸實機硬體時，請保持低風險的預設值：啟用自動量程 (Auto Range on)、立即觸發 (immediate trigger)，以及較小的 `max_samples` 值。
6. 點擊 `Start`。
7. 觀察狀態列與即時資料面板。
8. 若為手動軟體觸發模式，請在準備就緒時點擊 `Trigger`。
9. 點擊 `Stop` 以請求經由 Core 路由的停止動作。
10. 啟用 CSV 的執行停止 (inactive) 且 CSV 存在後，點擊 `Open CSV`。

WebUI 每個後端程序僅允許一個作用中的執行 (run)。

## 資源掃描

`Scan Device` 會呼叫：

```text
GET /api/resources?verify=true&live_only=true
```

後端會使用 Core 的資源列表行為。啟用驗證時，它會開啟每個候選資源並查詢 `*IDN?`。當 `live_only=true` 時，它僅會傳回有回應且為作用中 (live) 裝置的資源。

驗證的掃描結果在傳回的 IDN 與支援的 Core 設定檔匹配時，包含可為空的型號 metadata。34460A IDN 傳回 `instrument_model: "34460A"` 與 `instrument_model_id: "keysight-34460a"`；34461A IDN 則傳回對應的 `34461A` 與 `keysight-34461a` 值。巢狀的 `matched_profile` 包含 `vendor`、`model` 與 `model_id`。未知或空白的實機 IDN 仍保留在資源列表中，並將 `instrument_model`、`instrument_model_id` 與 `matched_profile` 設為 null，因此後端不會從備援功能設定檔猜測偵測到的身份。

選擇實機資源會將其複製到 `VISA resource` 輸入欄位中。當掃描推斷出支援的型號且 `Expected model` 仍為 Auto-detect 時，瀏覽器可能會載入 `/api/capabilities?model=<model>` 以顯示選項，但仍會將 `Expected model` 保持在 Auto-detect。Start 一律會先執行新的後端 IDN preflight。

使用者仍然可以手動輸入資源，並在掃描後於 `Device options` 中要求特定的 `Expected model`。

WebUI 與 Desktop 可在裝置選項中選擇 System VISA（預設）或隨程式提供的 PyVISA-py（`@py`）。資源掃描 query、Start 與 Plan payload 的 `visa_library` 僅接受未設定／空白或 `@py`；其他值回傳 422。掃描與驗證會將選擇傳入 Core。切換後會清除資源及掃描 metadata、忽略過期掃描與功能回應，並重新計算功能可用性。Start／Preview 處理中及執行中會鎖定後端。支援裝置面板的獨立切換僅篩選 Core metadata 產生的型號／連線清單，不會修改執行後端。`@py` 僅支援 34461A LAN/TCPIP；System VISA 支援 34461A USB/system-VISA 與 LAN/TCPIP，以及 34460A USB/system-VISA；詳見 [支援型號](../core/supported-models.zh-TW.md)。

`live_validated_full_suite` 與 `transport_pending` 是 Core-owned machine-readable status。WebUI 不公開 Validation mode；normal browser starts 只允許 Product-open scopes/features，non-Product-open 仍被封鎖。瀏覽器會停用產品不可用的功能選項，但該狀態僅為 UX；Core 驗證、支援原則關卡以及 `run_start_session()` 最終關卡仍是安全邊界。

## 量測模式

量測選項是透過以下方式自 Core 載入：

```text
GET /api/capabilities
GET /api/capabilities?model=34460A
GET /api/capabilities?model=34461A
GET /api/capabilities?model=keysight-34461a
```

當省略 `model` 時，`/api/capabilities` 會傳回具有 `defaults.instrument_model = null` 與 `model_resolution.resolved = false` 的相容 34461A 形狀能力表。瀏覽器在 Auto 時不送出 `instrument_model`；明確的 Expected model 選擇會送出 `"34460A"` 或 `"34461A"`。在 Auto-detect 模式下，能力控制項與支援摘要會使用該備援功能檢視，直到 Start 或 Scan 偵測到 IDN。此顯示上下文不會選擇實機驅動程式；實機執行仍使用偵測到的 IDN 選擇設定檔作為執行階段驅動程式。

型號身份 metadata 是附加內容；現有型號欄位保留原本的值與意義：

| 欄位 | 範例 | 意義 |
| --- | --- | --- |
| `model` | `34461A` | 標準化的儀器型號 token，以及既有的公開型號合約。 |
| `model_id` | `keysight-34461a` | 穩定且可供機器讀取的設定檔識別碼。 |
| `display_model` | `Auto-detect` 或 `34461A` | 供 UI 顯示的文字。 |
| `capability_profile` | `34461A` | 目前顯示能力所使用的設定檔。 |
| `capability_profile_id` | `keysight-34461a` | 顯示中能力設定檔的穩定 ID。 |
| `instrument_model` | `34461A` | 依所屬 payload 而定的既有選定或偵測型號欄位。 |
| `instrument_model_id` | `keysight-34461a` | 只有在資源 IDN 與設定檔匹配後才會有值的穩定 ID。 |

`instrument_profile` 與每個 `available_profiles` 項目都包含 `model` 與 `model_id`。`support_summary.model_id` 對應其既有的 `model`，而 `capability_profile_id` 對應 `capability_profile`。對尚未解析的 Auto-detect，兩個 ID 都描述顯示中的 34461A 備援能力設定檔：`display_model` 保持 `Auto-detect`、`defaults.instrument_model` 保持 null，且 `model_resolution` 保持未解析，同時增加 `fallback_profile_id: "keysight-34461a"`。此 fallback ID 不代表已偵測到實機儀器。明確的設定檔查詢則讓兩個 fallback 欄位保持 null。

`support_summary` 保留既有的 English 呈現欄位，並新增下列同層級的語意鍵 metadata：

```text
status_key
runtime_driver_note_key
open_workflow_keys
limit_keys
pending_keys
```

純量鍵分別對應 `status_text` 與 `runtime_driver_note`；鍵列表則依位置對應 `open_workflows`、`limits` 與 `pending`。瀏覽器在可用時使用已識別的鍵。遺失、格式錯誤、未知、較短或較長的鍵列表都不能移除、重新排序或增加文字項目：既有的文字列表仍是權威的顯示項目與備援內容。這些鍵只是呈現 metadata，不會影響支援原則的執行。原始的 `validation_status`、傳輸、後端、型號與設定檔身份值仍是機器值。最新的原始摘要可從記憶體重新轉譯，不需再次要求 capability。語系切換使用此快取，且不會將瀏覽器語系傳給 API。

標準型號名稱仍可供一般使用，穩定的型號 ID 也可作為設定檔查詢輸入。選定的型號仍是預期型號防護；從 live `*IDN?` 偵測到的設定檔仍是執行階段驅動程式。型號 ID 不代表支援狀態或生命週期狀態。

`/api/capabilities` 也包含額外的支援 metadata。每個確切的實機連線範圍保留其現有的 `validation_status`、`transport_scope` 與 `backend_scope` 欄位，並新增 `features.measurement` 與 `features.trigger_mode` 對照表。功能項目公開其自身的 `validation_status`；量測鍵使用現有的配接器端名稱，例如 `voltage-dc-ratio`。現有的回應欄位不會被移除或重新命名。

已註冊但尚未對產品開放的 scope，可能仍保留 machine-readable
`transport_pending` 狀態。瀏覽器會將這些 scope 視為一般 Product 啟動不可用；
此狀態不代表執行授權。

關於型號、傳輸、後端與量測功能支援矩陣，請參閱 [支援型號](../core/supported-models.md)。現有的量測、觸發、範圍與限制欄位仍是控制項定義的 source of truth。Product-open support-policy 範圍不代表每個 distribution 都已 bundle 該 backend 套件。

Expected model 檢查是選用的。Core 會在 Start 時驗證連接儀器的識別資訊。若明確指定的預期型號與新的 IDN preflight 不符，WebUI 會回報選取的型號以及 IDN 中找到的支援型號。

選取的 WebUI 型號不得被視為功能解鎖。停用或隱藏的控制項僅為 UX；Core 支援原則與 `run_start_session()` 最終關卡仍是 WebUI 後端提交的安全邊界。後端選擇不會改變 Expected model 的 IDN 防護或 Core 支援政策。`@bt` 及其他 WebUI backend selector 仍不受支援。

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
- 在 34460A 設定檔選定時，電流量程排除 10 A 且電流端子選擇會被隱藏，因為基礎 34460A 設定檔沒有 10 A 端子/路徑。自訂模式讀值記憶體限制為 1000 筆。
- 在 34460A 設定檔選定時，`voltage-dc-ratio` 的可用性取決於已註冊的 Product-open scope（請參閱 [支援型號](../core/supported-models.md)）。Backend／transport 可用性來自 Core 支援 metadata。
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

對於設定檔清單中保留的觸發模式，瀏覽器也會套用確切範圍的功能狀態。`feature_pending` 與 `not_supported_by_model` 選項將被停用，而 `live_validated_full_suite` 選項則保持可選。不提供驗證模式切換。

簡單的立即與軟體觸發讀取使用 Core 的 `READ?` 路徑。硬體觸發的簡單讀取在觸發配接器裝載並完成量測後，使用 Core 的 `FETC?` 路徑。

UI 行為：

- 非自訂的觸發模式顯示 `max_samples`。
- `software` 模式可使用選用的軟體計時器。
- 手動軟體觸發模式顯示 `Trigger` 按鈕。
- 自訂觸發模式顯示觸發次數、取樣數、緩衝區排空大小與緩衝區溢位風險。
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

當主控台伺服器收到離開訊號時，會先要求 manager 關閉，再允許 Uvicorn
停止。Launcher 的 Quit 會先停止作用中的執行並等待 Core 清理完成，然後才
停止 Uvicorn。如果清理逾時或失敗，launcher 會顯示 `Shutdown incomplete`
並保持開啟，讓操作人員可以重試。

一旦開始關閉，`WebRunManager` 會拒絕新的執行啟動，以避免啟動與終止競態。
如果執行仍在啟動且 Core control plane 尚未 ready 時收到 stop request，該
請求會被保留，待 control plane ready 後傳遞，不會遺失。

## 即時資料 (Live Data)

即時資料與狀態更新主要由伺服器傳送事件 (SSE) 驅動：

```text
GET /api/runs/current/events
```

這會傳回包含目前狀態快照的 `run-status` 事件的 `text/event-stream`。若 SSE 連線失敗，前端會自動降級為標準輪詢：

```text
GET /api/runs/current
```

狀態回應包含 WebUI 擁有的即時資料欄位：

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

即時資料衍生自 `run_start_session()` 發送的 Core `sample` 事件。WebUI 絕不可執行額外的 VISA 讀取或讀取 CSV 檔案來更新即時面板。

已停止的執行保持最新的樣本視窗供操作人員檢閱。啟動新的執行會建立一個新的樣本視窗。

瀏覽器端趨勢圖具有三種僅限前端的縮放模式：

- `Auto deviation` 是預設值，並保留原本的圖表行為。它將執行中的第一個數值樣本保持為基線，並在每次轉譯時重新縮放，使得最大可見偏差對應到中心線往外四個網格步長。
- `Auto absolute` 使用最近可見數值樣本的實際最小值和最大值，並帶有微小襯墊，使線條不會貼在圖表邊界上。
- `Manual span` 將第一個數值取樣保持為中心，並使用操作人員輸入的正數原始單位跨度作為固定的 `baseline +/- span` 範圍。此範圍外的數值會被裁切到圖表邊界，且目前版本不會另外顯示 `clipped indicator`。

這些模式僅影響圖表顯示，不影響原始樣本值、統計數據、CSV 輸出、API 樣本 payload、儀器設定或 SCPI 指令。圖表縮放控制項不包含在 `POST /api/runs` 中。

## CSV 輸出、選擇與開啟 CSV

CSV 輸出預設啟用。瀏覽器會在 `POST /api/runs` 傳送選用的 `csv_enabled` boolean；舊 API caller 省略此欄位時預設為 `true`。`csv_enabled=true` 時可提供選用的 `csv` 路徑，省略則使用預設時間戳記路徑。`csv_enabled=false` 時，後端會忽略殘留的 `csv` 值，Core 不會建立 CSV writer、檔案或僅供 CSV 使用的父目錄。

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

- `CSV 輸出` checkbox 預設為勾選。
- 取消勾選會停用 `CSV path` 與 `Select`，但不清空目前的路徑；重新勾選後可繼續編輯該值。
- 選取的資料夾會在現有的 `CSV path` 輸入欄位中填入傳回的帶有時間戳記的 `.csv` 路徑。
- 操作人員仍可手動編輯或清除 CSV 路徑。
- `Start` 會傳送 `csv_enabled`，且只有啟用 CSV 時才傳送正規化後的路徑。

目前或最新執行的 status 包含 `csv_enabled`。CSV 啟用時 `csv_path` 是 resolved path string；停用時則為 `null`。即時資料、已擷取樣本、status、Stop、summary 與 cleanup 不依賴 CSV 輸出。

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
- no-CSV 執行完成後停用。
- 當執行為 inactive 且 `csv_path` 存在時啟用。
- 將成功與失敗訊息附加到 Status 日誌中。

## HTTP API 摘要

面向瀏覽器的 API 介面為：

- `GET /`：提供 `index.html`。
- `GET /api/capabilities`：傳回 Core 支援的量測與觸發能力。選用的標準型號或已註冊穩定型號 ID 可選擇設定檔；省略型號會傳回未解析的自動 metadata 以及相容的 34461A 形狀能力表。設定檔身份與確切的實機支援範圍新增 metadata，而不移除現有欄位。
- `GET /api/resources?verify=true&live_only=true`：掃描 VISA 資源，且對於驗證過支援的 IDN，包含可為空的 `instrument_model`、`instrument_model_id` 與 `matched_profile` metadata。
- `POST /api/runs`：驗證並啟動執行。
- `POST /api/plan`：驗證 dry-run request，並在不開啟 VISA 或建立 active run 的情況下傳回 Core execution plan。
- `GET /api/runs/current`：傳回目前或最新的執行狀態。
- `GET /api/runs/current/events`：傳回執行狀態變更的伺服器傳送事件 (SSE) 串流。
- `POST /api/runs/current/command`：為支援的模式排入軟體觸發。接受 WebUI 私有的 `{ "metadata": {} }` payload；接受時傳回 `202`，驗證錯誤傳回 `400`，佇列/速率拒絕傳回 `429`，沒有作用中的執行或執行尚未 ready 時傳回 `409`。
- `POST /api/runs/current/stop`：要求透過 Core 控制面停止。
- `POST /api/runs/current/open-csv`：開啟最新完成的 CSV。
- `POST /api/csv/select-folder`：開啟本機資料夾選擇器，並為現有的 CSV 輸入欄位傳回帶有時間戳記的 CSV 路徑。

請勿重新命名、移除或修改這些端點，否則必須同時更新前端程式碼、測試與文件。

在接受命令回應後，前端會擷取 `GET /api/runs/current` 以更新顯示的執行狀態。命令回應不嵌入完整的執行狀態。

## 前端 Payload 欄位

WebUI 傳送的重要欄位包括：

- `resource`
- `instrument_model`
- `instrument_model_id`
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

頻率與週期 payload 保持原始數值：AC Filter `20 Hz` 以 `ac_bandwidth_hz: 20` 傳送，閘門時間為秒，逾時為 `auto` 或 `1s`。即時資料將頻率顯示為 `Hz`，週期顯示為 `s`，而不進行自動單位縮放。

## 安全規則

將所有影響儀器的變更視為高風險。

WebUI 實機執行的前提是，選定的實體儀器沒有同時受到其他 Meters CLI、WebUI、
logger、測試程序或外部 VISA 應用程式控制。並行控制可能干擾 SCPI 回應或儀器
狀態。這是操作人員的前置條件，不是 Meters Tool 自動強制的 lock。

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
- 釋放回本機控制行為。
- 清除順序。
- 硬體觸發逾時處理。
- 硬體觸發讀取是否使用 `FETC?`。
- 軟體觸發或立即讀取是否使用 `READ?`。

對於首次實機硬體快速功能健檢，請使用低風險的立即模式、啟用自動量程與較小的 bounded 取樣數。

## 開發邊界

偏好的 WebUI 前端檔案：

- `src/meters_tool_webui/static/index.html`
- `src/meters_tool_webui/static/styles.css`
- `src/meters_tool_webui/static/*.js`

後端配接器檔案：

- `src/meters_tool_webui/web_ui.py`
- `src/meters_tool_webui/launcher.py`

未經使用者明確核准，請勿變更 `pyproject.toml` 中的根套件 metadata。套件名稱、版本、相依套件、主控台指令、建置系統、pytest/ruff/mypy 設定以及 Core/CLI/WebUI 的擁有權皆為產品邊界決策。

## 疑難排解

包裝器遺失：

- 請使用根 README 的 console-wrapper 疑難排解流程。
- 確認 `.venv\Scripts\meters-tool-webui.exe` 存在。

連接埠已被使用：

- 預設 Launcher 模式會自動嘗試下一個 Port，不論占用者是另一個 Meters Tool WebUI 或其他服務。
- 固定的 `--port` 只會嘗試一次，若被占用則顯示錯誤。
- 若全部自動候選都被占用，請在 fallback 視窗輸入其他合法 Port 並選擇 Start；每次手動重試只嘗試該 Port。
- 對主控台伺服器，請選擇其他連接埠，例如 `--port 8768`，或停止現有的監聽程序。

`q` 無法停止伺服器：

- 這是預期行為。使用 `Ctrl+C` 進行正常關閉；如果無法傳送 SIGINT，請依照上方先清理再透過 PID 終止程序的指引操作。

掃描找不到實機資源：

- 確認儀器已開啟且已連接。
- 確認已安裝 VISA 驅動程式且資源出現在應用程式之外。
- 嘗試手動輸入已知的 VISA 資源。
- 在實機擷取前，從立即模式、啟用自動量程且 `max_samples=1` 的 smoke 測試開始。

Open CSV 按鈕被停用：

- 等待執行變為 inactive。
- 確認執行產生了 `csv_path`。
- 執行完成後重新整理瀏覽器仍可顯示 `Open CSV`，因為後端會保留最新的已完成 CSV 路徑。

觸發按鈕被隱藏：

- 該按鈕僅針對手動軟體觸發模式顯示：無計時器觸發的 `software` 以及 `software-custom`。

即時面板沒有取樣：

- 確認執行已擷取到樣本。
- 確認 SSE 狀態串流正常，或輪詢備援正在運作。
- 面板僅使用 Core 取樣事件；它不獨立查詢儀器或解析 CSV 檔案。
- 如果即時讀值或儀器行為看起來無法解釋地不一致，請先確認是否有其他 Meters
  CLI、WebUI、logger、測試程序或外部 VISA 應用程式正在存取同一個實體儀器。

## 說明文件地圖

- [WebUI／Desktop 使用者指南](USER_GUIDE.zh-TW.md)：面向操作人員的 WebUI／Desktop 使用指南。
- [WebUI README](README.zh-TW.md)：本 WebUI 行為、API 與整合指南。
- [WebUI 變更規則](web-ui-change-rules.md)：維護者與面向 Agent 的 UI 變更規則。
- [WebUI 變更日誌](../../CHANGELOG.md)：專案版本發佈說明。
