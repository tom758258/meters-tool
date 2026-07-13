# Meters Tool WebUI README

本文件說明 WebUI 元件的行為、API、驗證方式與維護者邊界。有關一般操作員工作流程與欄位說明，請參閱 [WebUI 使用指南](USER_GUIDE.zh-TW.md)。

對於發行說明，請參閱套件變更日誌。對於 Core API 與擁有權規則，請參閱 Core 整合指南。本指南主要著重於 WebUI 的長期公開行為與維護者邊界。

[WebUI 在地化合約](localization-contract.md) 定義瀏覽器端的 v2 在地化方案。P2.1 建立免相依性的瀏覽器多語系（i18n）基礎；P2.2 至 P2.5 涵蓋靜態與動態表單、應用程式與資源、狀態記錄、即時資料、ARIA、瀏覽器錯誤及支援摘要。P2.6 透過右上角永久顯示的地球圖示與文字按鈕，啟用英文／繁體中文切換。已儲存的有效語系（locale）優先於瀏覽器自動偵測與英文預設值；手動選擇會儲存在 `meters-tool.webui.locale`。切換會立即重新呈現快取狀態，不需重新整理網頁，也不會傳送背景或 API 請求；表單數值、執行中狀態、面板、狀態記錄、即時樣本、圖表設定、資源中繼資料與支援摘要都會保留。未知的 Core、後端與狀態診斷文字、原始狀態 JSON、樣本中繼資料及結構描述會維持原樣。Core、HTTP API 端點與狀態碼、既有回應欄位、表單數值、支援政策、儀器執行期，以及 CSV／JSON／JSONL 結構描述都不受影響。P2.7 完成最終語系檔案品質與術語審查、跨階段整合驗證、操作員文件，以及特定標籤的細部調整，且不改變上述邊界。

## 目的

WebUI 配接器圍繞 `src/meters_tool_core/` 中共享的 Core 執行期，提供本地的 FastAPI 與瀏覽器介面。

WebUI 負責：

- `src/meters_tool_webui/static/` 中的瀏覽器介面。
- `src/meters_tool_webui/web_ui.py` 中的 FastAPI 路由。
- 面向瀏覽器的請求與回應序列化。
- 基於 Core 樣本事件派生的即時資料顯示狀態。
- 資源掃描顯示。
- 開啟 CSV 行為（Open CSV）。
- 啟動、觸發、停止與狀態輪詢 UI 行為。

Core 負責：

- 請求驗證。
- 預演（乾跑）規劃。
- 採集執行期。
- 觸發路由。
- 停止控制器行為。
- CSV 寫入。
- 測量與儀器中繼資料。
- SCPI 命令產生與儀器 I/O。
- 釋放至本地、關閉、清理釋放與控制面關閉順序。

WebUI 必須使用 Core 的公開 API，而非依賴 CLI 配接器程式碼或直接存取採集引擎的內部機制。

Core 驗證測量請求並保護儀器端限制。WebUI 使用指南以 UI 術語解釋了各個欄位；本 README 則將 WebUI 的行為、API、驗證與維護者邊界集中於此。

## 套件與進入點

WebUI 包含在單一 `meters-tool` 發行套件中：

```text
meters-tool
```

Windows 主控台包裝器為：

```powershell
.\.venv\Scripts\meters-tool-webui.exe
```

Windows GUI 啟動器包裝器為：

```powershell
.\.venv\Scripts\meters-tool-webui-launcher.exe
```

預設本地伺服器為：

```text
http://127.0.0.1:8767/
```

伺服器為 Uvicorn/FastAPI 處理程序。終端機按鍵 `q` 無法停止它。請使用 `Ctrl+C`；若終端機未傳遞 SIGINT，請透過 PID 停止監聽的 `python.exe` 處理程序。

## 安裝或重新整理

自儲存庫根目錄：

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

或啟動雙擊啟動器：

```powershell
.\.venv\Scripts\meters-tool-webui-launcher.exe
```

啟動器預設為 `127.0.0.1:8767`，在勾選 `Use default port 8767` 時停用連接埠輸入欄位，按下 `Start` 後開啟瀏覽器，並保持視窗可用，讓 `Quit` 可以停止本地的 Uvicorn 伺服器。

開啟：

```text
http://127.0.0.1:8767/
```

選用的主機與連接埠旗標：

```powershell
.\.venv\Scripts\meters-tool-webui.exe --host 127.0.0.1 --port 8767
```

除非有刻意對外公開伺服器的理由，否則請保持預設主機為 `127.0.0.1`。

## 瀏覽器版面配置

目前的 WebUI 版面配置是一個直接的採集主控台，而非入口頁面（landing page）。

主要區域：

- 頁首：`Meters Tool` 與 `Local acquisition console`。
- 裝置 / 資源列：`VISA resource`、`Live resource`、`Scan Device` 以及一個用於 `Expected model` 選擇器與模型支援摘要的 `Device options` 齒輪。此列預設展開，並可折疊為資源/模型摘要。
- 預期模型選擇器預設為 `Auto-detect`（自動偵測），它會在啟動時使用連線儀器的 IDN 來比對設定檔。明確要求的設定檔（`34460A` 或 `34461A`）會被當作預期模型防護（expected-model guard），在 IDN 不相符時，會在傳送設定 SCPI 之前中斷。
- 執行設定（Run Setup）：`CSV output path`（預設為 `./data/YYYY-MM-DD-HH-MM-SS.csv`）、`Select` 按鈕（用於選擇 Windows 資料夾並產生時間戳記檔名）、`Open CSV`（用於使用系統預設應用程式開啟已完成的 CSV 檔案）以及執行限制。
- 測量（Measurement）面板：測量類型選擇器（DC/AC 電壓、電壓比例、DC/AC 電流、頻率、週期、2/4 線電阻）及對應的選用測量參數（NPLC、自動歸零、自動量程、手動量程、AC 濾波器、閘窗時間、頻率逾時、DCV 輸入阻抗與電流端子）。
- 觸發（Trigger）面板：觸發模式（立即、軟體、外部、立即自訂、軟體自訂、外部自訂）及相關設定（觸發次數、樣本次數、軟體最小間隔、計時器間隔、外部延遲、外部斜率與 VM Comp 斜率）。
- 狀態（Status）列：顯示目前背景狀態（未連接、正在初始化、等待觸發、正在錄製、正在釋放、致命錯誤）及目前執行的統計資料。
- 狀態記錄（Status log）：時間戳記記錄，顯示來自背景處理程序、FastAPI 回應、驗證不符或連線中斷的重大進展與錯誤診斷。
- 即時資料（Live data）面板：顯示最新讀數（帶有大字體、工程單位與樣本中繼資料）、10 點趨勢圖表（帶有自動絕對、手動跨度與範圍階梯 Y 軸縮放模式）、最近 10 點樣本表格，以及供代理人或自動化審查的所選樣本詳細中繼資料。

## 基本工作流程

1. 開啟萬用電表電源。
2. 啟動 WebUI（雙擊啟動器或使用命令列）。
3. 按一下 `Scan Device` 偵測 VISA 資源。
4. 選擇偵測到的資源，或手動貼上 VISA 資源字串。
5. 在 `Run Setup` 中，按一下 `Select` 選擇輸出資料夾並產生時間戳記 CSV 路徑。
6. 設定測量類型，例如 DC 電壓、自動量程與適用的 NPLC 設定。
7. 設定觸發模式，例如立即模式。
8. 按一下 `Start` 啟動採集。背景會啟動，開啟 VISA 工作階段，並在每次擷取後立即將緩衝資料寫入 CSV（flush）。
9. 在 `Live data` 中檢視折線圖、統計資料與最新數值。
10. 按一下 `Stop`。背景會完成剩餘樣本，執行釋放並關閉工作階段。
11. 按一下 `Open CSV` 檢視錄製的資料檔案。

## 資源掃描

按一下 `Scan Device` 會呼叫 API `/api/scan_resources`。後端使用 PyVISA 尋找可用的 USB 與 TCPIP 資源，對每個資源開啟工作階段，查詢 `*IDN?`，並傳回有回應的實體資源清單。

為了避免網頁停頓，掃描在背景以非同步方式執行。若未發現任何資源，網頁會允許操作員手動輸入已知的資源字串。

## 測量模式

WebUI 將所選的測量類型映射至 Core 所支援的實體測量：

- `voltage-dc`（DC 電壓）→ 支援量程限制、`nplc`、`auto_zero` 以及選用的 `dcv_input_impedance`（僅在 DC 電壓或比例下顯示，其他模式隱藏）。
- `voltage-dc-ratio`（DC 電壓比例）→ 支援量程限制、`nplc`、`auto_zero` 以及 `dcv_input_impedance`。
- `current-dc`（DC 電流）→ 支援量程限制、`nplc`、`auto_zero` 以及選用的 `current_terminal`（34461A 支援 `3A` 或 `10A`，34460A 僅支援 `3A`，且不提供切換）。
- `voltage-ac`（AC 電壓）→ 支援量程限制與 `ac_bandwidth_hz` 濾波器（3 Hz、20 Hz、200 Hz），不提供 NPLC。
- `current-ac`（AC 電流）→ 支援量程限制與 `ac_bandwidth_hz` 濾波器。
- `frequency`（頻率）→ 支援 `gate_time_s`（0.01 s、0.1 s、1 s）、選用的 `freq_period_timeout`（auto、1 s），以及 `ac_bandwidth_hz`。
- `period`（週期）→ 支援 `gate_time_s` 以及 `ac_bandwidth_hz`。不支援 `freq_period_timeout`。
- `resistance-2w`（2 線電阻）→ 支援量程限制、`nplc`、`auto_zero`。
- `resistance-4w`（4 線電阻）→ 支援量程限制、`nplc`、`auto_zero`。

## 觸發模式

WebUI 支援與 CLI 相同的完整觸發設定：

- `immediate`（立即）→ 啟動後直接連續採集，通常受限於 `max_samples`。
- `software`（軟體觸發）→ 等待 WebUI 傳送軟體觸發訊號。按一下 `Trigger` 將會向 `/api/trigger` 傳送請求。支援選用的 `timer_interval_s` 自動計時器觸發。
- `external`（外部觸發）→ 等待萬用電表後方的實體外部觸發訊號。
- 自訂硬體序列模式（立即自訂 `immediate-custom`、軟體自訂 `software-custom`、外部自訂 `external-custom`）→ 必須指定 `trigger_count`（觸發次數）與 `sample_count`（樣本次數）。多個測量值會暫存在儀器記憶體中，最後一次讀出，以支援較高頻率或特定硬體序列的採集。

## 啟動、停止與清理

- **啟動**：按一下 `Start` 會向 `/api/start` 傳送包含目前表單數值的 JSON 請求內容。後端驗證通過後，在背景非同步啟動 Core 引擎。
- **停止**：按一下 `Stop` 會向 `/api/stop` 傳送請求。背景處理程序被通知停止，完成目前的工作，執行必要的清理動作（釋放至本地、關閉 VISA 連線、釋放資源），然後宣告狀態為 inactive。
- **清理順序**：WebUI 遵循 Core 定義的安全清理順序：首先停止計時器與背景 worker，通知儀器釋放回本地控制面板，然後關閉工作階段，最後重置狀態，確保即使在發生異常時也不會損及實體儀器。

## 即時資料

網頁會以 `250 ms` 的間隔定期向 `/api/status` 進行輪詢。傳回的 JSON 包含目前執行的統計（captured 數、errors 數、狀態字串）、最近 10 筆樣本資料列與最近 10 個快照。

趨勢折線圖使用 HTML5 Canvas 或是輕量 SVG 動態繪製。在接收到新樣本時更新最新讀數、圖表資料與最近樣本。為確保瀏覽器效能，僅快取並顯示最近 100 筆樣本。

## CSV 輸出、選擇與開啟 CSV

- **輸出儲存**：所有測量都會即時寫入主機上的 CSV 檔案。
- **Select 資料夾**：按一下 `Select` 會向 `/api/select_folder` 傳送請求，後端會在 Windows 上開啟原生資料夾選擇器。操作員選擇資料夾後，路徑會傳回網頁，並自動組合成具有時間戳記的預設 CSV 檔名（例如 `data/2026-07-13-14-30-00.csv`）。
- **Open CSV**：按一下 `Open CSV` 會向 `/api/open_csv` 傳送包含目前 CSV 路徑的請求，後端會透過 Windows 原生 `ShellExecute`，使用系統預設程式（如 Excel 或記事本）開啟此檔案。只有在執行停止且 CSV 檔案實際產生時才可開啟。

## HTTP API 摘要

- `GET /` → 傳回靜態首頁 `static/index.html`。
- `GET /api/scan_resources` → 掃描 VISA 資源並查詢 IDN。
- `POST /api/start` → 以傳遞的表單 JSON 參數啟動背景採集執行。
- `POST /api/stop` → 停止目前的採集執行。
- `POST /api/trigger` → 對於軟體觸發模式傳送一次軟體觸發（BUS trigger）。
- `GET /api/status` → 輪詢目前執行狀態、統計資料與最近樣本。
- `GET /api/select_folder` → 在主機上開啟資料夾選擇視窗。
- `POST /api/open_csv` → 在主機上開啟目前的 CSV 檔案。

## 前端請求欄位

在向 `/api/start` 傳送的請求中，表單參數會序列化成 JSON 請求內容。對應 Core 的參數：
- `resource`：VISA 資源位址。
- `instrument_model`：預期模型限制 (`None`、`34460A`、`34461A`)。
- `measurement`：測量類型。
- `range_auto`：布林值，是否啟用自動量程。
- `manual_range`：浮點數，指定的手動量程。
- `nplc`：整合時間 NPLC 值。
- `auto_zero`：自動歸零設定 (`off`、`on`、`once`)。
- `ac_bandwidth_hz`：AC 濾波器頻寬。
- `gate_time_s`：閘窗時間。
- `freq_period_timeout`：頻率逾時設定。
- `dcv_input_impedance`：DCV 輸入阻抗。
- `current_terminal`：電流端子設定。
- `trigger_mode`：觸發模式。
- `trigger_count` / `sample_count`：自訂模式所需的計數器。
- `csv_path`：寫入的 CSV 目標路徑。

## 安全規則

- **失敗即關閉（fail-closed）**：不支援或未經授權的儀器在預檢階段會直接被 Core 拒絕，不允許對實體儀器傳送設定命令。
- **儀器防護**：WebUI 會在使用者選擇不當設定時（例如為 AC 測量設定 NPLC，或為 DC 測量設定閘窗時間），自動隱藏或停用不相符的欄位，防止錯誤的 SCPI 命令傳送。
- **連線逾時防護**：所有的實體通訊均受到設定的 `timeout_ms` 保護，避免因為實體連線中斷而造成背景死鎖。

## 開發邊界

- WebUI 僅作為 `meters_tool_core` 執行期的配接器（Adapter），絕不能與 `meters_tool_cli` 發生任何直接相依關係或相互匯入。
- 所有對儀器的實體 SCPI 讀寫、VISA 控制、多重設定檔的規格極限，均交由 Core 處理，WebUI 絕不自行實作任何 SCPI 命令或儀器硬體極限邏輯。

## 驗證

網頁前端 JavaScript 語法檢查：

```powershell
Get-ChildItem src\meters_tool_webui\static\*.js |
  ForEach-Object { node --check $_.FullName }
```

無硬體 FastAPI API 整合驗證：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/webui/test_webui_package_metadata.py tests/webui/test_webui_api.py tests/webui/test_webui_static.py tests/webui/test_launcher.py -q -p no:cacheprovider
```

利用 PyInstaller 建置選用的本地啟動器執行檔：

```powershell
uv pip install pyinstaller
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_webui_exe.ps1
```

執行完整的無硬體測試：

```powershell
uv run pytest tests -q -p no:cacheprovider
```

## 手動 UI 快速檢查清單

為確保 WebUI 的功能無損，開發人員在變更後應逐項檢查：
- 首頁在瀏覽器中正常開啟且無任何 Console 錯誤。
- 地球按鈕可正常在英文與繁體中文之間即時切換。
- `Scan Device` 可正確完成非同步資源檢索。
- 變更測量類型可自動更新測量參數面板隱藏與顯示狀態。
- 變更觸發模式可正確更新對應的參數欄位（如自訂模式下的觸發計數）。
- 在軟體觸發模式下能正確顯示 `Trigger` 按鈕，而在其他模式下隱藏。
- 折線趨勢圖在接收到模擬或實體樣本後，可正確依據 `Auto absolute`、`Manual span`、`Range step` 等模式調整 Y 軸縮放並正確繪製。
- 狀態記錄（Status log）可以持續加入狀態、警告與錯誤，且不會重複顯示輪詢訊息。
- 頁面在手機寬度（~390px）下不會有文字、按鈕重疊，在桌面寬度（~1280px）下緊湊且易於閱讀。

## 疑難排解

- **找不到包裝器**：重新執行 `uv pip install -e ".[all,dev]" --link-mode=copy`。
- **連接埠已被佔用**：使用 `--port 8768` 或結束佔用連接埠的處理程序。
- **無法用 `q` 停止**：此為預期行為，請在主控台使用 `Ctrl+C`。
- **Scan Device 找不到任何裝置**：確認儀器已開機並連接，VISA 驅動程式可辨識，或者嘗試手動輸入已知位址。
- **即時資料沒有樣本**：狀態輪詢可能因網頁異常而中斷，請重新整理網頁，或確認背景執行狀態是否處於 active。

## 相關文件

- [WebUI 使用指南](USER_GUIDE.zh-TW.md)：操作員導向的使用說明。
- [WebUI README](README.zh-TW.md)：本技術、維護與 API 行為指南。
- [WebUI 變更規則](web-ui-change-rules.md)：維護者與代理人變更 UI 靜態檔案時的變更限制。
- [WebUI 變更日誌](CHANGELOG.md)：發行說明。
