# Meters Tool CLI 使用者指南

本指南適用於取得已建置之 CLI 執行檔或已安裝的 `meters-tool` 指令，並使用它來記錄支援的數位萬用電表量測資料的操作人員。本指南專注於正常的量測工作流程與常見設定。

## 啟動 CLI

使用發佈版本時，請解壓縮 `meters-tool-<version>-windows-x64.zip`，在解壓後的
`meters-tool-<version>` 資料夾中開啟 PowerShell，並檢查 CLI：

```powershell
.\meters-tool.exe --version
```

版本號位於 bundle 資料夾名稱中；資料夾內的執行檔名稱不含版本號。

## 開啟使用指南

發佈版本的 CLI 可以在預設瀏覽器中開啟隨附的離線使用指南：

```powershell
.\meters-tool.exe user-guide
.\meters-tool.exe user-guide --lang en
.\meters-tool.exe user-guide --lang zh-TW
```

預設指南語言為 English。若要開啟繁體中文，請使用 `--lang zh-TW`。指南隨 CLI 一起提供，不需要線上文件網站。若需要確切的 CLI 指令選項、可接受值、範圍或預設值，請使用 `.\meters-tool.exe <command> --help`。

## 首次實機執行

在檢查新的電腦、VISA 執行階段、連線或儀器設定時，請使用此流程。

進行實機執行前，請確認沒有其他 Meters CLI、WebUI、logger、測試程序或外部 VISA 應用程式正在控制同一台實體儀器。同時控制可能干擾 SCPI 回應或儀器狀態。Meters Tool 不會以自動鎖定強制此前提。

1. 開啟 Keysight 34460A 或 34461A 電源並將其連接至電腦。
2. 列出目前能回應 `*IDN?` 指令的資源：

```powershell
.\meters-tool.exe list-resources --live-only
```

3. 複製儀器的資源字串並在目前的 PowerShell 工作階段中設定一次：

```powershell
$env:METER_RESOURCE = "USB0::...::INSTR"
```

   此值可以是任何由探測傳回的作用中 VISA 資源，包括 USB 或 TCPIP/LAN 資源。

4. 執行一次有界限的立即模式 (immediate mode) 取樣：

```powershell
.\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --measurement voltage-dc `
  --trigger-mode immediate `
  --max-samples 1 `
  --csv ".\data\cli_smoke.csv"
```

5. 確認指令正常退出、CSV 檔案已存在，且 CSV 包含一筆資料列。
6. 在信任較長期的擷取之前，請將 CSV 數值與前面板讀值進行對比。

進行實機擷取時請使用明確的 `--resource` 值。傳遞 `"$env:METER_RESOURCE"` 仍會為 CLI 提供明確的資源；請勿依賴腳本或無人值守的工作流程來猜測應使用哪台儀器。

live 啟動省略 `--model` 時，連接儀器的 `*IDN?` 決定 runtime profile。明確指定 `--model 34460A` 或 `--model 34461A` 只是 expected-model guard；selected model 絕不會覆寫 IDN-selected profile。`--model` 也接受穩定 model ID：`keysight-34460a` 與 `keysight-34461a`。在 live 模式中，任何 model 值仍只是 expected-model guard，不會解鎖其他支援範圍。live mismatch 會在 setup SCPI 前失敗。dry-run 或 simulator 才由 selected model 選擇 profile，除非 simulator resource 已確定型號，例如 `SIM::34460A` 或 `SIM::34461A`。型號名稱由 Core 設定檔邏輯進行標準化與驗證，因此未知的型號會以清楚的驗證錯誤失敗。

## 實機支援範圍提醒

某個 VISA resource 能回應 `*IDN?` 或出現在 `list-resources` 中，本身不代表所有型號與 transport/backend 組合都已 Product-open。型號、transport、backend、量測與觸發支援都是精確範圍，且必須符合 Core policy。未列出的組合會 fail closed，而不是透過 `--model` 或掃描結果被解鎖。

精確的目前支援矩陣，請參閱 [支援型號](../core/supported-models.zh-TW.md)。

CLI 預設使用電腦的 System VISA runtime，例如 Keysight IO Libraries Suite 或 NI-VISA。backend 選擇不會改變或擴充 Product 支援。Windows 發佈版 CLI 執行檔只支援固定的 System VISA 路徑，不會 bundle 選用 backend。

## 不連接硬體先檢查設定

第一次操作實機前，可以先用相同的請求檢查設定，而不控制實體儀器。

使用 `--dry-run` 可驗證請求並顯示執行計畫，不會啟動擷取，也不會執行實機
VISA I/O。若資源本身沒有指定 simulator 型號，請提供
`--model 34460A` 或 `--model 34461A`。

使用 `--simulate` 搭配 `SIM::34461A` 這類 deterministic simulator resource，
可在沒有真實硬體的情況下執行 acquisition workflow。模擬作業也應像第一次實機
作業一樣保持有界限。

例如：

```powershell
.\meters-tool.exe start-trigger-record `
  --resource SIM::34461A `
  --simulate `
  --measurement voltage-dc `
  --trigger-mode immediate `
  --max-samples 3 `
  --no-csv
```

Dry-run 與 simulation 適合在操作前檢查設定，但兩者都不能當作真實儀器與連線範圍
已完成實機驗證的證據。

## 選擇量測類型

請選擇與儀器接線及待測訊號相符的量測類型：

- `voltage-dc`：直流電壓。
- `voltage-dc-ratio`：直流電壓比。
- `current-dc`：直流電流。
- `voltage-ac`：交流電壓。
- `current-ac`：交流電流。
- `frequency`：訊號頻率 (Hz)。
- `period`：訊號週期 (秒)。
- `resistance-2w`：2 線式電阻。
- `resistance-4w`：4 線式電阻。

測量電流或 4 線式電阻前，請先確認輸入端子是否正確。
對於 AC、頻率與週期模式，請先執行低風險的快速功能健檢 (smoke test)，並將 CSV 數值與前面板讀值進行對比，確認無誤後再將該設定用於較長期的擷取。

## 選擇觸發模式

選擇觸發模式時，先判斷**由什麼事件開始擷取**，再判斷需要一般讀值流程，還是
buffered custom acquisition。

| 模式 | 適用情境 | 擷取行為 |
| --- | --- | --- |
| `immediate` | 作業啟動後立即開始取得讀值。 | 一般讀值；除非刻意要連續擷取，否則使用 `--max-samples` 設定上限。 |
| `software` | 由操作人員或其他程式決定每次何時取樣。 | 等待接受到的軟體觸發指令。 |
| `external` | 由治具、DUT、PLC 或其他硬體訊號同步量測。 | 等待實體外部觸發邊緣。 |
| `immediate-custom` | 作業開始後立即依指定數量將一批讀值擷取到儀器讀值記憶體。 | Buffered custom acquisition。 |
| `software-custom` | 每次接受到軟體觸發時，啟動一組指定的 buffered acquisition。 | 由軟體觸發控制的 buffered custom acquisition。 |
| `external-custom` | 每個實體觸發事件都驅動一組指定的 buffered acquisition。 | 由外部觸發控制的 buffered custom acquisition。 |

最簡單的工作流程請使用 `--trigger-mode immediate`，並加上
`--max-samples`。

若要手動軟體觸發，請在一個終端機啟動 `software` 或
`software-custom` 作業，再從另一個終端機發送觸發：

```powershell
.\meters-tool.exe send-command
```

Software mode 也可以依計時器自動觸發。Timer capture 並不是另一個
`--trigger-mode timer` 值；請使用 `--trigger-mode software` 搭配
`--timer-interval-s`。例如，下列設定每 1 秒取得一次軟體觸發讀值，並在
60 筆後停止：

```powershell
.\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --measurement voltage-dc `
  --trigger-mode software `
  --timer-interval-s 1 `
  --max-samples 60
```

### Custom / Buffered 觸發模式

三種 `*-custom` 模式使用 buffered acquisition，而不是一般
`--max-samples` 工作流程。它們都需要 `--trigger-count` 與
`--sample-count`。

預期讀值總數為：

```text
trigger count x sample count
```

例如，`--trigger-count 10 --sample-count 100` 代表預期 1000 筆讀值。
Custom mode 不使用 `--max-samples`。

`--buffer-drain-size` 控制每次從儀器讀值記憶體取回多少筆 buffered readings。
除非測試程序需要特定 drain size，否則保持未指定即可。

如果 `trigger count x sample count` 超過該型號的 reading memory，Core 會要求
明確加入 `--allow-buffer-overflow-risk` 後才允許 custom run 啟動。這項確認
**不會**增加儀器記憶體，也不會解除 buffer drain 的硬限制。目前 34461A 的
reading memory 為 10000 筆，34460A 為 1000 筆；精確的目前限制與支援範圍請參閱
[支援型號](../core/supported-models.zh-TW.md)。

只有在實體觸發訊號已連接，且操作人員了解觸發邊緣與延遲設定時，才使用
`external` 或 `external-custom`。硬體觸發逾時是一種保護性的重新準備
(re-arm) 條件，並非自動代表量測失敗。

## 常見設定

`--resource` 是儀器的 VISA 位址。請使用 `list-resources --live-only` 回傳的值，或由操作人員提供的已知資源。在 PowerShell 範例中，設定一次 `$env:METER_RESOURCE` 並傳遞 `--resource "$env:METER_RESOURCE"`，以便複製的命令能繼續使用選定的儀器。

`--visa-library` 是進階 CLI backend 選擇器。一般 Product 使用請省略它並使用 System VISA。選擇 backend 不會解鎖未支援的型號、transport、量測或其他 Product 支援。

`list-resources --verify` 會開啟偵測到的 VISA 資源並查詢 `*IDN?`。`list-resources --live-only` 暗示了驗證並隱藏過期的項目。ASRL/RS-232 驗證使用短暫的有界限逾時，因此過期的序列埠項目不會阻擋後續的 USB 或 TCPIP 資源。序列埠結束字元選項 `--serial-read-termination` 與 `--serial-write-termination` 是僅用於 ASRL 驗證的 CLI 偵測相容性設定；它們不是擷取設定。

`--csv` 是輸出檔案路徑。若省略此項，CLI 會自動建立一個帶有時間戳記的 CSV 路徑。當您需要可預測的檔案位置以便進行檢閱或自動化處理時，請使用明確的路徑。可使用 `--no-csv` 停用本次 CSV 輸出；`--csv` 與 `--no-csv` 不可同時使用。

`--max-samples` 用來限制簡單作業的執行次數。在進行快速功能健檢與驗證時請使用它，讓指令能自行停止。

`--auto-range`（自動量程）讓儀器自行選擇量程。除非量測設定要求固定量程，否則請保持啟用自動量程。

當自動量程停用時，使用 `--range` 來選擇手動量程。請選擇一個能安全涵蓋預期訊號的量程。

`--nplc` 控制直流與電阻量測的積分時間。較高的數值速度較慢，但可能更穩定。AC、頻率與週期模式僅接受中性的預設值，因為它們不會寫入 NPLC SCPI 指令。

`--auto-zero` (自動歸零) 控制直流與電阻量測的偏移處理。它可以提高精確度，但可能會減慢讀取速度。AC、頻率與週期模式不會寫入 Auto Zero SCPI 指令。

`--ac-bandwidth-hz` (交流頻寬/濾波器) 適用於交流電壓、交流電流、頻率與週期。頻率與週期省略此選項時預設為 `20` Hz。

`--gate-time-s` 僅適用於頻率與週期。可選 `0.01`、`0.1` 或 `1` 秒；預設為 `0.1` 秒。

`--freq-period-timeout` 僅適用於頻率。除非量測程序要求 `1s` 行為，否則請保持預設的 `auto`。週期不會傳送逾時指令；搭配週期明確指定此選項將被拒絕。

`--current-terminal` (電流端子) 適用於電流量測。請與儀器上實際使用的電流端子保持一致。

`--dcv-input-impedance` 適用於直流電壓與直流電壓比。`default` 會保留儀器目前設定，`10m` 選擇 10 MOhm，`auto` 則啟用儀器的自動／高輸入阻抗行為。除非量測程序要求其他輸入阻抗，否則保持 `default`。

`--vm-comp-slope` 控制後面板 VM Comp 輸出脈衝的斜率。省略此選項會保持 VM Comp 不變；只有測試設定明確使用該輸出時，才選擇 `pos` 或 `neg`。

對外部觸發模式而言，`--hw-trigger-delay-s` 設定觸發後的延遲，`--hw-trigger-slope` 選擇實體觸發邊緣。請與實際連接的觸發訊號源保持一致。

對手動軟體觸發作業而言，`--sw-min-interval-ms` 可限制軟體觸發被接受的最快間隔，`--sw-queue-max` 則限制排隊等待處理的觸發工作。除非觸發來源或測試程序需要明確的節流或 queue 控制，否則保持預設值。軟體觸發也可以攜帶 metadata；這些 metadata 會隨觸發／sample 輸出記錄，適合標示 DUT、batch 或 step 等識別資訊。

`--trigger-timeout-ms` (觸發逾時) 控制觸發工作流程在進入保護性逾時路徑前的等待時間。只有在量測設定刻意要等待更長時間時，才調高此值。

若需要指令選項及 CLI 層級的可接受值、範圍與預設值，請執行 `meters-tool <command> --help`（例如 `.\meters-tool.exe start-trigger-record --help`）。型號特定的支援與限制仍以 Core 驗證及前述「支援型號」範圍為準。

## CSV 輸出

預設 CSV 輸出啟用時，每筆擷取樣本都會寫成一列。在快速功能健檢後，請檢查 CSV 檔案以確認：

- 至少有一筆資料列；
- 預期的 `measurement_type` (量測類型)；
- 預期的 `unit` (單位)；
- 預期的 `trigger_source` (觸發來源)；
- 一個與前面板顯示足夠接近，且符合測試設定的數值。

每擷取一個樣本後，CSV 都會立即排空 (flush) 並寫入磁碟，因此即使在較長時間的執行中，也隨時能取得已完成的資料列。

## 停止執行

對於有界限的驗證作業，建議使用 `--max-samples` 讓作業自行停止。

若要停止正在執行中的工作器 (worker)，請使用下列其中一種停止路徑：

- 在 logger 終端機按下 `q` 鍵；
- 按下 `Ctrl+C` 或 `Ctrl+Break`；
- 從另一個終端機執行 stop 指令：

```powershell
.\meters-tool.exe stop
```

停止後，請確認指令已乾淨地退出，並且 CSV 中包含預期的資料列。

## 常見問題

如果找不到 `meters-tool.exe`，請完整解壓縮 ZIP，開啟版本化發佈資料夾，並確認其中存在 `meters-tool.exe`。

如果 `list-resources` 顯示過期的資源，請使用 `list-resources --verify` 來查看哪些資源有回應，以及其他資源失敗的原因。如果您只想要對 `*IDN?` 做出回應的資源，請使用 `--live-only`。如果 ASRL/RS-232 資源回報了與結束字元相關的過期結果，請使用 `--serial-read-termination` 或 `--serial-write-termination` 重試偵測；這些選項僅影響 ASRL 驗證。

如果找不到任何作用中 (live) 的資源，請檢查儀器電源、USB/LAN/GPIB 連線、VISA 驅動程式的可見度，以及是否有其他程式正在佔用該儀器。

如果在開啟儀器前作業就被阻擋，請閱讀驗證錯誤訊息，並調整其指出的選項設定。CLI 會在進行實機 I/O 之前驗證常見設定。

如果硬體觸發作業似乎在等待，請確認實體觸發訊號、斜率 (slope)、延遲 (delay) 與逾時 (timeout) 設定。遺失觸發邊緣 (trigger edges) 訊號會導致作業根據設定的逾時行為繼續等待或重新準備 (re-arm)。
