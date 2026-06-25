# Keysight Logger WebUI 說明文件

本文件是 WebUI 元件的 WebUI 行為、API、驗證與維護者指南。對於一般的操作人員工作流程與欄位說明，請參閱 [WebUI 使用者指南](USER_GUIDE.zh-TW.md)。

關於版本發布說明，請參閱套件變更日誌。關於 Core API 和擁有權規則，請參閱 Core 整合指南。本指南將專注於長期的公開 WebUI 行為與維護者邊界。

## 目的

WebUI 配接器（adapter）圍繞 `keysight_logger_core` 中共享的 Core 執行階段，提供本機 FastAPI 和瀏覽器介面。

WebUI 擁有以下內容的擁有權：

- 位於 `src/keysight_logger_webui/static/` 的瀏覽器介面。
- 位於 `src/keysight_logger_webui/web_ui.py` 的 FastAPI 路由結構。
- 面向瀏覽器的請求和回應序列化。
- 從 Core 樣本事件衍生而來的即時數據顯示狀態。
- 資源掃描顯示。
- 開啟 CSV 行為。
- 開始、觸發、停止和狀態輪詢的 UI 行為。

Core 擁有以下內容的擁有權：

- 請求驗證。
- Dry-run（模擬執行）規劃。
- 擷取執行階段。
- 觸發路由。
- 停止控制器行為。
- 寫入 CSV。
- 量測與儀器 metadata。
- SCPI 命令產生與儀器 I/O。
- 釋放至本機（release-to-local）、關閉、清除釋放以及控制面關閉順序。

WebUI 必須使用 Core 的公用 API，而不是依賴 CLI 配接器程式碼或直接存取擷取引擎內部運作。

Core 會驗證量測請求並保護儀器端的限制。WebUI 使用者指南以 UI 術語說明各個欄位；本 README 則集中整理 WebUI 行為、API、驗證與維護者邊界。

## 套件與進入點（Entry Point）

WebUI 隨附於單一 distribution 中：

```text
keysight-logger
```

Windows 主控台包裝器（wrapper）為：

```powershell
.\.venv\Scripts\keysight-logger-webui.exe
```

Windows GUI 啟動器包裝器為：

```powershell
.\.venv\Scripts\keysight-logger-webui-launcher.exe
```

預設的本機伺服器為：

```text
http://127.0.0.1:8767/
```

伺服器是一個 Uvicorn/FastAPI 程序。終端機按鍵 `q` 無法停止它。請使用 `Ctrl+C`；如果終端機沒有傳送 SIGINT，請透過 PID 停止監聽中的 `python.exe` 程序。

## 安裝或重新載入

在 repository 根目錄下執行：

```powershell
uv pip install -e ".[all,dev]" --link-mode=copy
```

檢查包裝器：

```powershell
.\.venv\Scripts\keysight-logger-webui.exe --version
```

預期版本格式：

```text
keysight-logger-webui <package-version>
```

啟動伺服器：

```powershell
.\.venv\Scripts\keysight-logger-webui.exe --port 8767
```

或啟動按兩下執行的啟動器：

```powershell
.\.venv\Scripts\keysight-logger-webui-launcher.exe
```

啟動器預設為 `127.0.0.1:8767`。當勾選 `Use default port 8767` 時，會停用連接埠（port）欄位，並在啟動後開啟瀏覽器，且保持視窗可用，以便透過 Quit 停止本機 Uvicorn 伺服器。

開啟：

```text
http://127.0.0.1:8767/
```

選用的 host 與 port 旗標：

```powershell
.\.venv\Scripts\keysight-logger-webui.exe --host 127.0.0.1 --port 8767
```

除非有刻意的原因需要將伺服器公開至本機以外，否則請保持預設的 host 為 `127.0.0.1`。

## 瀏覽器版面配置

目前的 WebUI 版面是一個直接的擷取主控台，而非登入頁面。

主要區域：

- 標頭：`Keysight Meters` 和 `Local acquisition console`。
- 資源列：`VISA resource`、`Live resource` 和 `Scan Device`。
- 狀態量條：`State`、`Captured`、`Errors` 和 `CSV`。
- 動作按鈕：`Start`、`Trigger`、`Stop` 和 `Open CSV`。
- 用於執行設定、量測設定、觸發設定、即時數據（Live data）與狀態詳細資料的可摺疊設定面板。
- 即時數據面板包含最新數值、樣本時間、觸發來源、趨勢圖表、統計資料、最近樣本表格以及所選樣本的 metadata。

此 UI 刻意不設計前端建置步驟、Node 套件管理器、外部 CDN 或框架執行階段。靜態資產皆為純 HTML、CSS 和 JavaScript。

## 基本工作流程

1. 啟動 WebUI 伺服器。
2. 開啟 `http://127.0.0.1:8767/`。
3. 手動輸入 VISA 資源或按一下 `Scan Device`。
4. 選擇量測與觸發設定。
5. 首次接觸真實儀器時，請保持低風險的預設值：啟用自動範圍（Auto Range on）、即時觸發（immediate trigger），以及設定較小的 `max_samples` 值。
6. 按一下 `Start`。
7. 觀察狀態量條與即時數據面板。
8. 若為手動軟體觸發模式，請在準備就緒時按一下 `Trigger`。
9. 按一下 `Stop` 以請求經由 Core 路由的停止動作。
10. 當執行停止（inactive）且 CSV 存在後，按一下 `Open CSV`。

WebUI 每個後端程序僅允許一個作用中的執行（run）。

## 資源掃描

`Scan Device` 會呼叫：

```text
GET /api/resources?verify=true&live_only=true
```

後端會使用 Core 的資源列表行為。啟用驗證時，它會開啟每個候選資源並查詢 `*IDN?`。當 `live_only=true` 時，它僅會傳回有回應且為作用中裝置的資源。

選擇作用中的資源會將其複製到 `VISA resource` 輸入欄位中。使用者仍然可以手動輸入資源。

## 量測模式

量測選項是透過以下方式自 Core 載入：

```text
GET /api/capabilities
```

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

前端絕不可自行虛構量測選項。它應該從 `/api/capabilities` 填入選項、預設值、範圍、NPLC 選項、AC 頻寬/濾波器選項、頻率/週期閘門時間、僅限頻率的 timeout 選項、電流端子選項以及量測特有的控制項。

量測特有的 UI 行為：

- NPLC 僅出現在支援的量測中。
- AC、頻率和週期量測不顯示 NPLC。
- AC 頻寬/濾波器會在支援的 AC 電流、AC 電壓、頻率和週期中顯示。
- AC 電流和 AC 電壓可選擇 `Keep current setting`，此選項不會送出 AC
  filter payload；頻率和週期則直接選取預設的 `20 Hz`。
- 頻率和週期會顯示閘門時間；只有頻率會顯示 Timeout。
- 週期的 timeout capability 為空，因此 UI 會隱藏並停用 Timeout，也不會送出該 payload。
- 電流端子選擇僅在支援的電流量測中顯示。
- DCV Input Z（輸入阻抗）僅在 `voltage-dc` 中顯示。
- 在 Core 支援的情況下，VM Comp 仍會作為量測選項。
- 透過 Core 功能，支援的 DC/電阻量測可使用 Auto Zero Once。

## 觸發模式

觸發選項同樣自 `/api/capabilities` 載入。

目前呈現的觸發模式包括：

- `immediate`
- `software`
- `external`
- `immediate-custom`
- `software-custom`
- `external-custom`

簡單的即時觸發與軟體觸發讀取，會使用 Core 的 `READ?` 路徑。
硬體觸發的簡單讀取，則會在觸發配接器 arm（準備就緒）並完成量測後，使用 Core 的 `FETC?` 路徑。

UI 行為：

- 非自訂（non-custom）觸發模式會顯示 `max_samples`。
- `software` 模式可以使用選用的軟體計時器。
- 手動軟體觸發模式會顯示 `Trigger` 按鈕。
- 自訂觸發模式會顯示觸發計數（trigger count）、樣本計數（sample count）、緩衝區排空大小（buffer drain size）以及緩衝區溢位風險（buffer overflow risk）。
- 外接觸發模式會顯示硬體斜率（hardware slope）、硬體延遲（hardware delay）與觸發逾時。
- 硬體觸發逾時是一種保護性的重新 arm 條件，其本身並非擷取錯誤。

WebUI 的觸發按鈕會將 metadata 傳送（POST）至後端。空白的觸發 metadata 會傳送：

```json
{ "source": "web-ui" }
```

非空白的 metadata 必須為有效的 JSON，且會與該預設物件合併。

## 開始、停止與清除

開始（Start）會呼叫：

```text
POST /api/runs
```

後端會將瀏覽器傳送的資料（payload）轉換為 Core 的 `StartRequest`，透過 Core 進行驗證，建立配接器可見的狀態，並在背景工作執行緒上啟動 Core 的 `run_start_session()`。

停止（Stop）會呼叫：

```text
POST /api/runs/current/stop
```

停止動作會經由 Core 的控制面進行路由。WebUI 程式碼絕不可直接關閉 VISA 控制代碼（handles）、呼叫擷取引擎內部運作或重組清除順序。

保留的清除順序：

1. 等待背景工作執行緒（worker）。
2. 將儀器釋放至本機狀態（release to local）。
3. 關閉儀器/工作階段資源。
4. 清除釋放。
5. 停止 HTTP/控制面路徑。

## 即時數據（Live Data）

即時數據與狀態更新主要由伺服器傳送事件（Server-Sent Events, SSE）驅動：

```text
GET /api/runs/current/events
```

這會傳回一個 `text/event-stream`，其中包含含有目前狀態快照的 `run-status` 事件。
如果 SSE 連線失敗，前端會自動降級（fallback）為標準的輪詢方式：

```text
GET /api/runs/current
```

狀態回應中包含了由 WebUI 擁有的即時數據欄位：

- `latest_sample`
- `recent_samples`
- `sample_capacity`

樣本視窗（sample window）被限制在最新的 5000 筆樣本內。

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

即時數據是從 `run_start_session()` 發出的 Core `sample` 事件中衍生的。WebUI 絕不可執行額外的 VISA 讀取或讀取 CSV 檔案來更新即時面板。

已停止的執行會保留最後的樣本視窗供操作者檢視。啟動新的執行會建立一個全新的樣本視窗。

瀏覽器端的趨勢圖表會將該次執行中的第一個數值樣本做為基準線（baseline），並在每次轉譯（render）時重新縮放，使得最大可見偏差對應到偏離中心線的四個網格步長。這僅影響圖表顯示，不影響原始樣本值、統計資料、CSV 輸出或 API 樣本資料。

## CSV 輸出、選擇與開啟 CSV

執行傳送的資料中可包含選用的 `csv` 路徑。若省略，則由 Core/預設行為來選擇 CSV 輸出路徑。

`CSV path` 欄位旁還有一個 `Select` 按鈕。它會呼叫：

```text
POST /api/csv/select-folder
```

後端行為：

- 在執行 WebUI 後端的電腦上開啟資料夾選擇器。
- 選擇後傳回：

```json
{
  "selected": true,
  "folder_path": "C:\\path\\to\\folder",
  "csv_path": "C:\\path\\to\\folder\\2026-06-01-14-30-05.csv"
}
```

- 取消時傳回：

```json
{ "selected": false, "folder_path": null, "csv_path": null }
```

- 若資料夾選擇器無法使用，則傳回 `503`。

前端行為：

- 選擇的資料夾會用傳回的附帶時間戳記 `.csv` 路徑，填入既有的 `CSV path` 輸入欄位中。
- 操作者仍然可以手動編輯或清除 CSV 路徑。
- `Start` 會使用按一下當下輸入欄位中的值。

Open CSV 按鈕會呼叫：

```text
POST /api/runs/current/open-csv
```

後端行為：

- 僅從管理器狀態開啟目前或最新已完成執行的 CSV。
- 不接受前端提供的檔案路徑。
- 若執行仍處於作用中狀態，則傳回 `409` 與 `run is still active`。
- 若無已完成的 CSV 路徑可用，則傳回 `409` 與 `no completed CSV available`。
- 若記錄的 CSV 路徑不存在，則傳回 `404` 與 `CSV file not found`。
- 成功時，使用 Windows 預設應用程式開啟器開啟並傳回：

```json
{ "opened": true, "csv_path": "..." }
```

前端行為：

- 預設停用。
- 在執行處於作用中狀態時停用。
- 當執行處於停止狀態且 `csv_path` 存在時啟用。
- 將成功與失敗訊息附加到 Status 記錄中。

## HTTP API 摘要

面向瀏覽器的 API 介面為：

- `GET /`：提供 `index.html`。
- `GET /api/capabilities`：傳回由 Core 支援的量測與觸發能力。
- `GET /api/resources?verify=true&live_only=true`：掃描 VISA 資源。
- `POST /api/runs`：驗證並啟動一次執行。
- `GET /api/runs/current`：傳回目前或最新的執行狀態。
- `GET /api/runs/current/events`：傳回執行狀態變更的伺服器傳送事件（SSE）串流。
- `POST /api/runs/current/command`：為支援的模式將軟體觸發加入佇列。傳回通用命令回應外殼：`202` 接受、`400` 驗證錯誤、`429` 佇列/速率拒絕，或當無執行處於作用中或執行尚未就緒時傳回 `409`。
- `POST /api/runs/current/stop`：要求經由 Core 控制面停止。
- `POST /api/runs/current/open-csv`：開啟最新已完成的 CSV。
- `POST /api/csv/select-folder`：開啟本機資料夾選擇器，並為既有的 CSV 輸入傳回附帶時間戳記的 CSV 路徑。

請勿在未同時更新前端程式碼、測試與文件的情況下，重新命名、移除或變更這些端點的用途。

在接受命令回應後，前端會擷取 `GET /api/runs/current` 以更新顯示的執行狀態。命令回應本身不包含完整的執行狀態。

## 前端資料欄位（Payload Fields）

由 WebUI 傳送的重要欄位包括：

- `resource`
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
- `current_terminal`

隱藏的控制項 must be disabled so stale values are not submitted from inactive modes.

## 安全規則

請將所有影響儀器的變更視為高風險。

未經使用者明確同意，請勿變更以下任一項目：

- SCPI 命令或命令順序。
- VISA 逾時行為。
- 觸發等待策略。
- `TRIG:DEL`。
- NPLC 行為。
- Auto Zero（自動歸零）行為。
- Auto Range（自動範圍）行為。
- VM Comp 行為。
- DCV Input Z（輸入阻抗）行為。
- 停止（Stop）行為。
- 釋放/本機（Release/local）行為。
- 清除順序。
- 硬體觸發逾時處理。
- 硬體觸發的讀取是否使用 `FETC?`。
- 軟體觸發或即時讀取是否使用 `READ?`。

對於首次真實儀器的基本功能驗證（smoke tests，即快速健檢），請使用低風險的即時（immediate）模式、啟用自動範圍（Auto Range on），以及設定較小的限制樣本數。

## 開發邊界

偏好的 WebUI 前端檔案：

- `src/keysight_logger_webui/static/index.html`
- `src/keysight_logger_webui/static/styles.css`
- `src/keysight_logger_webui/static/app.js`

後端配接器檔案：

- `src/keysight_logger_webui/web_ui.py`
- `src/keysight_logger_webui/launcher.py`

測試：

- `tests/webui/test_web_ui.py`
- `tests/webui/test_launcher.py`
- 下方驗證指令中列出的 Core 合約與套件邊界測試。

未經使用者明確同意，請勿變更 `pyproject.toml` 中的根套件 metadata。套件名稱、版本、相依套件、主控台指令指令、建置系統、pytest/ruff/mypy 設定，以及 Core/CLI/WebUI 的擁有權劃分，皆屬於產品邊界決策。

## 驗證

請先執行最窄的相關檢查。

編輯 `app.js` 後的 JavaScript 語法檢查：

```powershell
node --check src\keysight_logger_webui\static\app.js
```

針對 WebUI/Core 的無硬體專注驗證：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/webui/test_webui_package_metadata.py tests/webui/test_web_ui.py tests/webui/test_launcher.py -q -p no:cacheprovider
```

在使用已安裝 `keysight-logger` 的環境中，使用 PyInstaller 建置選用的本機啟動器執行檔（launcher exe）。PyInstaller 是本機版本建置工具，並非 WebUI 執行階段的相依套件，因此在全新機器上重建前，請先將其安裝至 venv：

```powershell
uv pip install pyinstaller
```

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_webui_exe.ps1
```

可行時進行更廣泛的無硬體驗證：

```powershell
uv run pytest tests -q -p no:cacheprovider
```

真實儀器驗證需要操作者提供 VISA 資源。在開始使用其他觸發模式或進行較長期的擷取之前，請先使用低風險的即時（immediate）模式進行基本功能驗證（快速健檢），並啟用自動範圍（Auto Range on）與 `max_samples=1`。

完整測試執行可能會遇到本機 Windows 暫存或 pytest 快取權限警告。請清楚回報此類警告，並在廣泛測試套件因環境權限受阻時，依賴專注測試與真實儀器驗證。

## 手動 UI 快速健檢檢核表

無硬體的 UI 快速功能驗證：

- 網頁可在 `http://127.0.0.1:8767/` 正常載入。
- 首次載入時沒有出現瀏覽器主控台錯誤。
- `Scan Device` 能更新作用中資源選取器，或乾淨地回報無作用中資源。
- 變更量測模式能更新範圍單位、範圍選項以及 NPLC 的顯示狀態。
- `voltage-dc` 顯示 DCV Input Z；其他量測模式則隱藏它。
- AC 量測在支援處顯示 AC 頻寬並隱藏 NPLC。
- 電流量測在支援處顯示電流端子。
- 變更觸發模式僅顯示和隱藏相關欄位。
- `Trigger` 按鈕僅在手動軟體觸發模式下顯示。
- Status 記錄附加有意義的訊息，且不重複洗板輪詢狀態。
- `Show Details` 能切換顯示致命錯誤、清除狀態與原始狀態。
- 在擷取到模擬或真實樣本後，即時數據能呈現最新數值、圖表、統計資料、表格以及所選樣本的 metadata。
- 行動版寬度約 390 px 時，文字或控制項無重疊。
- 桌上版寬度約 1280 px 時，維持緊湊但易於閱讀。

針對真實儀器的基本功能驗證（快速健檢），除非操作者明確要求，否則請勿進行高風險的觸發實驗。請先以即時（immediate）模式、啟用自動範圍（Auto Range on）與 `max_samples=1` 開始。

## 疑難排解

包裝器（Wrapper）遺失：

- 重新執行 `uv pip install -e ".[all,dev]" --link-mode=copy`。
- 確認 `.venv\Scripts\keysight-logger-webui.exe` 存在。

連接埠（Port）已被佔用：

- 使用其他連接埠啟動，例如 `--port 8768`。
- 或者停止目前正在監聽的程序。

按 `q` 無法停止伺服器：

- 此為正常現象。請使用 `Ctrl+C`，或透過 PID 停止監聽中的 `python.exe`。

掃描找不到作用中的資源：

- 確認儀器已連接並開啟電源。
- 確認已安裝 VISA 驅動程式，且資源可在應用程式外部被偵測到。
- 嘗試手動輸入已知的 VISA 資源。
- 在進行真實擷取前，先以低風險的即時模式、啟用自動範圍與 `max_samples=1` 進行快速功能驗證。

開啟 CSV 遭停用（Open CSV is disabled）：

- 等待執行轉為停止狀態。
- 確認執行有產生 `csv_path`。
- 在執行完成後重新整理瀏覽器仍可顯示 `Open CSV`，因為後端會保留最後一次完成的 CSV 路徑。

觸發按鈕被隱藏：

- 該按鈕僅在手動軟體觸發模式下顯示：不含計時器觸發的 `software` 模式，以及 `software-custom` 模式。

即時面板沒有樣本：

- 確認執行已擷取樣本。
- 確認狀態輪詢正在進行。
- 該面板僅使用 Core 樣本事件；它不會獨立查詢儀器或解析 CSV 檔案。

## 文件地圖

- [WebUI 使用者指南](USER_GUIDE.zh-TW.md)：面向操作者的 WebUI 使用指南。
- [WebUI README](README.zh-TW.md)：本 WebUI 行為、API、驗證與維護者指南。
- [WebUI 變更規則](web-ui-change-rules.md)：面向維護者與 Agent 的 UI 變更規則。
- [WebUI 變更日誌](CHANGELOG.md)：套件版本發布說明。
