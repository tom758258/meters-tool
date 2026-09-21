# Meters Tool WebUI / Desktop 使用者指南

本指南適用於使用 `Meters Tool.exe` 或 `meters-tool-webui-launcher.exe`，
記錄支援數位萬用電表量測資料的操作人員。兩者提供相同的本機擷取介面與
一般量測工作流程。

## WebUI / Desktop 介面的功能

Meters Tool 在 Desktop 應用程式視窗或透過 WebUI launcher 開啟的一般瀏覽器中，
提供相同的本機擷取介面。其功能包含：

- 尋找已連線的 VISA 儀器。
- 每次啟動一個量測作業。
- 將讀值記錄到 CSV 檔案中。
- 在作業執行期間顯示最新與最近的讀值。
- 當所選的觸發模式需要時，發送軟體觸發訊號。
- 停止目前的作業並開啟已完成 CSV 檔案。

WebUI 執行於與儀器連接的同一台 Windows 電腦上。它不是一項雲端服務。

## 選擇 Desktop 或瀏覽器 WebUI

### Desktop 應用程式

使用發佈版本時，請解壓縮 `meters-tool-<version>-windows-x64.zip`，開啟
解壓縮後的 `meters-tool-<version>` 應用程式資料夾，然後雙擊：

```text
Meters Tool.exe
```

Desktop 會在應用程式視窗中開啟共用的 WebUI。不需要另外啟動 WebUI
Launcher、不需要選擇 Port，也不需要手動在瀏覽器輸入 URL。啟動後，請使用
下方相同的畫面總覽與操作流程。

### 瀏覽器 WebUI

使用發佈版本時，請解壓縮 `meters-tool-<version>-windows-x64.zip`，開啟
`meters-tool-<version>` 資料夾，然後雙擊：

```text
meters-tool-webui-launcher.exe
```

版本號位於 bundle 資料夾名稱中；資料夾內的執行檔名稱不含版本號。

Launcher 會自動啟動。它會從 `8767` 開始，必要時最多嘗試 100 個本機
Port，等待 WebUI ready 後，再以實際成功 bind 的 Port 開啟瀏覽器。其他已
執行的 Meters Tool WebUI 會被視為 Port 擁有者，不會被重用。

正常啟動期間不需要 Port 視窗或 Start 操作。啟動後會顯示一個包含實際 URL
與 `Quit` 的小視窗。使用完畢時請按 `Quit`，讓作用中 run 的清理完成後再
關閉本機伺服器。

只有全部自動候選都被占用時，才會顯示完整 Port 視窗。請輸入 `1` 到
`65535` 的其他 Port 並按 `Start`。每次手動重試只會嘗試該 Port 一次；
失敗時視窗會保留，供您修改後重試。

如果瀏覽器沒有自動開啟，請手動開啟此網址：

```text
http://127.0.0.1:8767/
```

實際 Port 可能較高；請以 Launcher 視窗顯示的 URL 為準。

## 畫面總覽

WebUI / Desktop 介面在兩種入口中都是相同的本機擷取主控台。主要區域包含：

- 右上角工具列：語言、主題與 `說明`（英文介面為 `Help`）控制項。
- `說明`：開啟隨附的使用指南。
- `Device / Resource` (裝置/資源列)：儀器位址、最近一次掃描回應的實機資源、`Scan Device` 按鈕、`支援裝置` 清單，以及 `Device options` 齒輪中的執行模式與型號選擇器。此列預設展開，可收合成能辨識目前執行模式的摘要。
- `Run Setup` (作業設定)：CSV 輸出路徑與執行次數設定。
- `Measurement` (量測)：量測類型與相關選項。
- `Trigger` (觸發)：觸發模式與觸發相關選項。
- `Status` (狀態)：目前的作業狀態、擷取到的樣本數、錯誤、CSV 路徑與日誌。
- `Live data`（即時資料）：最新讀值、趨勢圖表、最近取樣與所選取樣的詳細資訊。

點擊 `支援裝置` 可查看 WebUI 支援連線清單。此清單由 Core capability 與支援元資料衍生，會反映目前支援的連線範圍，而不會硬編一份暫時的 USB/LAN support matrix。精確的目前 Product support scope 請見 [Supported Models](../core/supported-models.zh-TW.md)。

## 語言

右上角的外觀與語言控制是各自帶標籤的設定項。使用地球與文字按鈕，在 English 與繁體中文之間切換。該按鈕會顯示目前語言：English 顯示 `English`，繁體中文顯示 `繁體中文`；螢幕閱讀器標籤則描述切換後的目的地語言。

首次載入時，頁面會依序使用有效的已儲存語系、瀏覽器語言，最後才使用 English。手動選擇會儲存在 `meters-tool.webui.locale`；瀏覽器偵測結果不會自動儲存。切換會立即生效，不重新載入頁面，也不會呼叫 runtime API。表單目前的值、作用中的作業、面板、狀態日誌、Live data 選取項目、圖表設定、資源掃描與支援摘要都會保留。未知的診斷文字保持不變。

在繁體中文中，Measurement options 控制項顯示 `自動量程（Auto range）`；摘要使用較短的 `自動量程`。選用標記在一般桌面寬度下會與欄位標題保持在一起，包括 AC filter 與 Current terminal；在非常窄的螢幕上會自然換行。

## 說明

點擊右上角工具列的 `說明`（英文介面為 `Help`）。在瀏覽器 WebUI 中，隨附的
使用指南會在新的瀏覽器分頁開啟；在 Desktop 中，則會使用系統預設瀏覽器開啟。
指南會依目前選取的 WebUI 語言顯示，兩種入口使用相同的隨附說明內容。若要使用
不同語言，請先切換 WebUI 語言，再開啟說明。

## 主題

使用語言按鈕旁的主題按鈕，依序切換 `系統`、`淺色` 與 `深色`。`系統` 會跟隨瀏覽器或作業系統的色彩配置，並在設定變更時同步更新。選取的偏好會儲存於介面中，之後再次開啟瀏覽器或啟動 Desktop 時會自動還原。切換主題會立即生效，不會重新載入頁面，也不會重設目前的表單、作業、Live data 或狀態。

在 Electron Desktop 中，`系統` 也會讓原生視窗介面跟隨作業系統外觀。選取 `淺色` 或 `深色` 時，該偏好也會套用至原生視窗介面，並在之後啟動 Desktop 時還原。

## 選擇執行模式

開啟 `Device options` 並選擇一種模式：

- `Real` 使用設定的 VISA resource，並維持一般的掃描、identity check、擷取、觸發、CSV、Stop 與清理工作流程。
- `Simulate` 必須選擇 `34460A` 或 `34461A`，且不使用或查詢真實 VISA hardware。Deterministic simulated instrument 會完整執行 acquisition runtime，因此 Live data 的最新讀值、圖表、統計資料、最近 sample、Stop 與正常 CSV 輸出都可運作。
- `Dry-run` 必須選擇 planning model，並將 Start 改為 `Preview plan`。它只驗證 Core plan 並顯示於 Status details，不啟動 acquisition、不建立 active run、不執行真實 VISA I/O，也不產生 Live data sample。Preview plan 會清除前一次 runtime 留在畫面上的 sample。

Execution mode 僅存在於目前頁面，Start／Preview request pending 或 active run 期間不可切換，而且不會持久化；重新載入頁面一律回到 `Real`。Simulation 與 Dry-run 可用於無硬體檢查，但都不能當作實機驗證證據。

## 首次執行

進行基本的立即量測 (immediate measurement)，請採用以下流程：

進行實機執行前，請確認沒有其他 Meters CLI、WebUI、logger、測試程序或外部 VISA 應用程式正在控制同一台實體儀器。同時控制可能干擾 SCPI 回應或儀器狀態。Meters Tool 不會以自動鎖定強制此前提。

1. 開啟 Keysight 34460A 或 34461A 電源並將其連接至電腦。
2. 啟動 Desktop 或瀏覽器 WebUI。
3. 點擊 `Scan Device`。
4. 選取或將偵測到的 VISA 資源複製到 `VISA resource` 欄位中。
5. 只有在需要強制指定型號時，才在 `Device options` 中將 `Expected model` 改選 `Require 34460A` 或 `Require 34461A`；否則請維持 `Auto-detect`。
6. 選擇量測類型，例如直流電壓 (DC voltage) 或直流電流 (DC current)。
7. 在 `Run Setup` 中，選擇 CSV 檔案位置。使用 `Select` (選擇) 挑選一個資料夾，讓系統產生帶有時間戳記的 CSV 路徑。
8. 除非您特別需要軟體或外部觸發，否則請將觸發模式保持在立即／預設模式 (immediate/default mode)。
9. 檢閱反白顯示的設定。
10. 點擊 `Start` (啟動)。
11. 觀察 `Captured` (已擷取)、`Status` (狀態) 及 `Live data`（即時資料）。
12. 當需要結束作業時，點擊 `Stop` (停止)。
13. 啟用 CSV 的作業停止後，點擊 `Open CSV` (開啟 CSV) 以開啟已完成的 CSV 檔案。

一次只能執行一個作業。啟動新作業將會清除畫面上前次作業的最近樣本。

## 選擇觸發模式

選擇觸發模式時，先判斷**由什麼事件開始擷取**，再判斷需要一般讀值，還是
buffered custom acquisition。

| 模式 | 適用情境 | 執行方式 |
| --- | --- | --- |
| `Immediate` | 按下 Start 後立即開始取得讀值。 | 一般讀值，由作業的 sample limit 控制。 |
| `Software` | 由操作人員決定每次何時取樣，或由計時器發送軟體觸發。 | Timer trigger 關閉時使用 `Trigger` 按鈕；開啟時依設定間隔自動觸發。 |
| `External` | 由治具、DUT、PLC 或其他硬體訊號同步量測。 | 等待實體外部觸發邊緣。 |
| `Immediate Custom` | Start 後立即依指定數量將一批讀值擷取到儀器讀值記憶體。 | Buffered custom acquisition。 |
| `Software Custom` | 每次 WebUI 軟體觸發都啟動一組指定的 buffered acquisition。 | 由 `Trigger` 按鈕控制的 buffered custom acquisition。 |
| `External Custom` | 每個實體觸發事件都驅動一組指定的 buffered acquisition。 | 由外部觸發控制的 buffered custom acquisition。 |

第一次操作時，Immediate mode 是最簡單的選擇。

### 軟體觸發控制項

在 `Software` mode 且未勾選 `Timer trigger` 時，作業啟動後點擊
`Trigger` 即可送出每次軟體觸發。勾選 `Timer trigger` 後，工作流程會改成
排程式軟體觸發；請用 `Timer interval s` 設定間隔。Timer 是 Software mode
的一部分，不是另一個 trigger mode。

在手動軟體觸發模式中，`SW min interval ms` 可限制軟體觸發被接受的最快間隔，
`SW queue max` 則限制排隊等待處理的觸發工作。除非觸發來源或測試程序需要明確
節流或 queue 控制，否則保持預設值。

`Trigger metadata JSON` 可為手動軟體觸發附加選用的 JSON object。例如：

```json
{"batch":"A1"}
```

可用 metadata 標示 DUT、batch 或測試 step。它是觸發的 metadata，不是儀器
command，也不是可執行 script。

### Custom / Buffered 觸發控制項

選擇任何 `* Custom` 模式後，畫面會顯示 `Trigger count`、
`Sample count`、`Buffer drain size` 與 `Allow buffer risk`。

`Trigger count` 是 custom sequence 中的儀器 trigger event 數量；
`Sample count` 是每次 trigger 取得的 readings 數量。因此預期讀值總數為：

```text
trigger count x sample count
```

例如，Trigger count 為 `10`、Sample count 為 `100` 時，預期為 1000 筆讀值。

`Buffer drain size` 控制每次從儀器讀值記憶體取回多少筆 buffered readings。
除非測試程序需要特定 drain size，否則保持預設值。

如果預期讀值總數超過所選型號的 reading memory，`Allow buffer risk` 是繼續
執行前所需的明確確認。它**不會**增加儀器記憶體，也不會解除 buffer drain 的
硬限制。目前 34461A 的 reading memory 為 10000 筆，34460A 為 1000 筆。
精確的目前支援與限制請參閱 [支援型號](../core/supported-models.zh-TW.md)。

只有在實體觸發訊號已連接且儀器設定完成時，才使用 External 或 External Custom。
`External trigger slope` 選擇實體觸發邊緣，`Trigger delay` 設定觸發後到量測前
的延遲，`Trigger timeout` 則控制保護性的等待／re-arm 路徑。硬體觸發逾時並不
自動代表量測失敗。

除非量測設定有此需求，且操作人員了解對儀器造成的影響，否則請勿更改觸發時序、
觸發延遲、NPLC、自動量程 (Auto Range)、自動歸零 (Auto Zero)、VM Comp 或
電流端子的設定。

## 設定參考

WebUI 會在啟動作業前檢查各項設定。如果 `Start` 被封鎖無法點擊，請閱讀 Status 日誌並調整其指出的欄位。

`VISA resource` (VISA 資源) 是作業將使用的儀器位址。建議使用透過 `Scan Device` 找到的資源，或手動輸入由操作人員或測試程序提供的已知資源。當可能連接多台儀器時，請勿用猜測的方式填寫資源。

WebUI 使用電腦固定的預設 System VISA runtime。它不提供 PyVISA backend 選擇器，resource scan 與 run API 也不接受 backend override。精確的實機型號與連線支援由 Core policy 決定，並記載於 [Supported Models](../core/supported-models.zh-TW.md)。

`Live resource`（實機資源）顯示最後一次掃描回應的結果。請先用它確認是哪台儀器回應，再複製或選取資源以進行作業。當掃描辨識出支援的 34460A 或 34461A IDN 時，WebUI 可能會載入特定型號的選項以供顯示，同時保持 `Expected model` 在 `Auto-detect`。

`CSV 輸出` 預設為勾選。啟用時，`CSV path` (CSV 路徑) 是讀值寫入的位置。請使用 `Select` 選擇資料夾並讓 WebUI 產生帶有時間戳記的檔案名稱，或在點擊 `Start` 前手動輸入特定的檔案路徑。

**執行次數與取樣限制**欄位用來控制作業可以持續多久。在檢查接線、量測類型與觸發行為時，請為新的設定保持有界限 (bounded，即設定次數上限)。

`Expected model`（預期型號）是 `Device options` 中的選用檢查。Auto-detect 在 Start 時使用最新的 IDN preflight 來解析連接的儀器。只有當您希望 Start 讀取 IDN，且在連接的儀器不回報該支援型號就失敗時，才選擇 `Require 34460A` 或 `Require 34461A`。若要求 34460A，WebUI 會隱藏 10 A 電流量程、電流端子選擇與外接觸發模式；自訂模式的讀值記憶體為 1000 筆。這些停用的控制項僅供指引。選取的型號是預期型號防護與顯示上下文；它不會覆寫偵測到的 IDN、解鎖另一台儀器的功能，或取代 Core 的安全檢查。

`Measurement type` (量測類型) 用來選擇儀器要量測的項目：直流或交流電壓、直流或交流電流、直流電壓比、頻率、週期，或是 2 線/4 線式電阻。在啟動作業前，請確保這與儀器的實體接線相符。

`Auto Range`（自動量程）讓儀器自行選擇量測量程。除非量測程序要求固定量程，否則首次執行時請保持啟用。

當自動量程停用時會使用**手動量程**欄位。請選擇一個能安全涵蓋預期訊號的量程。

`NPLC` 控制直流與電阻量測的積分時間。較高的數值速度較慢，但可能更穩定。AC、頻率與週期模式則改用其 AC 濾波器設定。

`Auto Zero` (自動歸零) 控制直流與電阻量測的偏移處理。它可以提高精確度，但可能會減慢讀取速度。除非量測程序要求更改，否則請保持在正常的設定值。

`AC filter` (AC 濾波器) 適用於交流電壓、交流電流、頻率與週期。對於交流電壓與交流電流，`Keep current setting` (保持目前設定) 不會改變儀器目前的濾波器設定；頻率與週期預設選取 `20 Hz`，摘要中可能會顯示為 `>20 Hz`。

`Gate time` (閘門時間) 僅適用於頻率與週期。預設為 `0.1 s`；可選項為 `0.01`、`0.1` 與 `1 s`。

量測選項中的 `Timeout` (逾時) 僅適用於頻率。除非程序要求 `1 s` 行為，否則請保持 `Auto`。週期會隱藏此控制項，且不會傳送逾時指令。

頻率數值會以 `Hz` 顯示與儲存。週期數值會以 `s` 顯示與儲存；WebUI 不會自動縮放這些單位。

`Current terminal` (電流端子) 適用於電流量測。啟動作業前，請確認實體導線已連接至相符的電流端子。

`DCV input Z` 會出現在直流電壓與直流電壓比。`Default` 會保留儀器目前設定，`10M` 選擇 10 MOhm，`Auto` 則啟用儀器的自動／高輸入阻抗行為。除非量測程序要求其他輸入阻抗，否則保持 `Default`。

**直流電壓比 (DC voltage ratio)** 是特殊的量測模式。只有當測試設定明確要求比值量測時才使用。

`VM Comp slope` 控制後面板 VM Comp 輸出脈衝的斜率。`Leave unchanged` 會保留目前設定；只有測試設定明確使用 VM Comp 輸出時，才選擇 `Pos` 或 `Neg`。

`Trigger mode` (觸發模式) 控制取樣的時間點。前面的「選擇觸發模式」章節說明了一般與 Custom 工作流程，以及各模式會顯示的設定欄位。

`Trigger delay` (觸發延遲) 在外部觸發後會等待一段時間才進行量測。除非外部設定需要延遲，否則請保持不變。

`Trigger timeout` (觸發逾時) 控制觸發工作流程在進入保護性逾時路徑前的等待時間。只有在量測設定刻意要等待更長時間時，才調高此值。

`External trigger slope` (外部觸發斜率) 用於選擇實體觸發的邊緣 (edge)。請與連接到儀器的訊號源保持一致。

## 即時資料圖表縮放 (Live Data Chart Scale)

`Live data`（即時資料）面板在 `Trend` 區域有圖表縮放控制項。這些設定僅影響介面圖表顯示。它們不影響儀器設定、SCPI 指令、CSV 輸出或記錄的數值。

趨勢圖表使用作用中的縮放模式，在每條網格線的左側顯示 Y 軸標籤。

`Auto deviation`（自動偏差）是預設值。它將圖表中心定位在執行中的第一個數值樣本上，並將後續樣本顯示為與第一個樣本的差異。這最適合觀察微小漂移或穩定性變化。它不是絕對 Y 軸圖表。如果第一個樣本是 `5.0000 V`，後續樣本是 `5.0002 V` 和 `4.9998 V`，則圖表顯示相對於第一個樣本的 `+0.0002 V` 和 `-0.0002 V`。

`Auto absolute`（自動絕對值）使用可見的最近樣本的實際最小值和最大值。這最適合觀察量測範圍。如果樣本範圍從 `4.9998 V` 到 `5.0004 V`，圖表範圍將基於這些實際值。極端值可能會縮放圖表，使微小變化看起來更平坦。

`Manual span`（手動跨度）使用第一個數值取樣為中心，以及操作人員輸入的固定正數跨度。跨度使用原始量測單位：`V` 代表伏特，`A` 代表安培，`Ohm` 代表歐姆，`Hz` 代表赫茲，`s` 代表秒。對於電壓，`0.01` 代表 `0.01 V`，而不是 `0.01 mV`。如果第一個取樣是 `5.000 V` 且手動跨度是 `0.010 V`，則圖表顯示 `4.990 V` 到 `5.010 V`。超出 `baseline +/- span` 的值會被裁切到圖表邊界，目前版本不會另外顯示 `clipped indicator`。

`Range step`（量程步進）使用手動選取的 `Range` 作為圖表顯示跨度。僅在 `Auto Range` 關閉且選取手動量程時可用。它不反映儀器的實際自動選擇量程，因為在啟用自動量程時 WebUI 無法得知該硬體量程。如果第一個取樣是 `5.000 V` 且選取的手動 Range 是 `0.010 V`，則圖表顯示 `4.990 V` 到 `5.010 V`。超出 `baseline +/- selected Range` 的值可能會被裁切到圖表邊界。與其他圖表縮放模式一樣，Range step 僅影響介面圖表顯示，不會改變儀器設定、SCPI 指令、CSV 輸出或記錄的數值。

## CSV 輸出

在 `Run Setup` 中顯示的 CSV 路徑就是當點擊 `Start` 時將寫入資料的檔案。

`Select` 會在執行 WebUI 的 Windows 電腦上開啟一個資料夾選擇器。選擇資料夾後，WebUI 會在該資料夾內填入帶有時間戳記的 CSV 檔案路徑。您也可以在點擊 `Start` 之前手動編輯該路徑。

`CSV 輸出` 預設為勾選。取消勾選會停用 `CSV path` 與 `Select`，但保留目前的路徑值；重新勾選後可繼續使用。停用 CSV 不影響即時資料、已擷取樣本、狀態、Stop 或 cleanup。

`Open CSV` 僅在作業停止且產生 CSV 路徑時可用。它會使用 Windows 的預設應用程式開啟上一次完成作業的 CSV。在作業執行期間或停用 CSV 的作業完成後，此按鈕會處於停用狀態。

## 停止與離開

### Desktop 應用程式

使用 `Stop` 來有意結束目前的擷取作業。完成 Desktop 操作後，請正常關閉
Desktop 應用程式視窗。Desktop 會在離開前要求優雅關閉並完成清理。如果 Desktop
顯示清理尚未完成，請等待清理完成後，再次關閉視窗。

### 瀏覽器 WebUI

使用 `Stop` 來停止目前的擷取作業。WebUI 會在作業停止後保留畫面上最新的讀值，
以供您檢視。接著在 Launcher 的 Running／Quit 小視窗中使用 `Quit`，以停止
本機 WebUI 伺服器並關閉 Launcher。僅關閉瀏覽器分頁不會停止伺服器。

## 常見問題

### 瀏覽器 WebUI 未開啟

請手動開啟 Launcher 視窗顯示的執行中 URL。預設起始網址為：

```text
http://127.0.0.1:8767/
```

如果頁面仍然無法載入，請回到啟動器並檢查是否顯示啟動錯誤。

### 啟動器顯示連接埠已被佔用

預設 Launcher 模式會自動嘗試下一個 Port。即使占用者是另一個 Meters Tool
WebUI，也會採用相同行為，因為不同儀器可能需要不同的 WebUI 執行個體。
固定的 `--port` 會回報衝突而不遞增。若 100 個自動候選全部用完，請在
fallback 視窗輸入其他合法 Port；每次手動重試只會嘗試該 Port。

### Scan Device 找不到任何裝置

請檢查：

- 儀器電源已開啟。
- 已經接上 USB/LAN/GPIB 連線。
- VISA 驅動程式能看見該儀器。
- 沒有其他程式正在佔用該儀器的連線。

您仍然可以手動輸入已知的 VISA 資源。

### Scan Device 無法推斷型號

將 `Expected model` 保持在 Auto-detect 並點擊 `Start`；後端會執行新的 IDN preflight。只有當您希望在連接的儀器不回報 34460A 或 34461A 時就使 Start 失敗，才強制要求型號。

### Start 顯示選取的型號與 IDN 不符

從 `Device options` 選擇訊息中命名的型號，或將 `Expected model` 設回 Auto-detect。這表示連接的儀器 IDN 明確匹配了與 WebUI 要求不同的支援型號。

### Start 被封鎖

請確保已填寫 `VISA resource`，且反白顯示的設定皆具有有效值。Status 日誌會顯示需要注意的設定。

### Open CSV 按鈕被停用

`Open CSV` 將被停用，直到啟用 CSV 的作業停止並產生完整的 CSV 路徑為止。在作業執行期間或取消勾選 `CSV 輸出` 時，它也會保持停用狀態。

### 硬體觸發作業似乎在等待

外部觸發模式會等待實體觸發訊號。如果觸發訊號遺失，作業可能會依照設定的逾時行為繼續等待或重新準備 (re-arm)。

## 操作人員安全注意事項

- 在量測電流之前，請先確認儀器的輸入接線與電流端子。
- 檢查新的設定時，請先使用立即模式 (immediate mode)。
- 除非需要固定量程，否則請保持啟用自動量程 (Auto Range)。
- 請將外部觸發的接線與極性視為量測設定的一部分。
- 在可行的情況下，請在斷開儀器連接前先停止測量作業。
