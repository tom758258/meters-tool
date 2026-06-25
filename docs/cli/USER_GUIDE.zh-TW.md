# Keysight Logger CLI 使用者指南

本指南適用於收到已建置之 CLI 執行檔或已安裝之 `keysight-logger` 指令，並使用它來記錄 Keysight 34461A 測量數據的操作人員。本指南專注於標準的測量工作流程與常見設定。如需開發人員設定、驗證腳本、JSON/JSONL 輸出與自動化合約，請參閱 [CLI README](README.zh-TW.md)。

## 啟動 CLI

在包含 CLI 執行檔的資料夾下開啟 PowerShell，並檢查它：

```powershell
.\keysight-logger.exe --version
```

發布資料夾可能包含帶有版本號的執行檔名稱，例如：

```text
keysight-logger-<version>.exe
```

如果您的發布資料夾使用帶有版本號的執行檔，請在下方的指令中替換為該檔案名稱。開發人員或從原始碼簽出 (source-checkout) 的使用者，應參閱 [CLI README](README.zh-TW.md) 以取得虛擬環境、模組、驗證與建置指令。

## 首次即時執行 (First Live Run)

在檢查新的電腦、VISA 執行環境、連線或儀器設定時，請使用此流程。

1. 開啟 Keysight 34461A 電源並將其連接至電腦。
2. 列出目前能回應 `*IDN?` 指令的資源：

```powershell
.\keysight-logger.exe list-resources --live-only
```

3. 複製 34461A 的資源字串。
4. 執行一次有上限的立即模式 (immediate-mode) 採樣：

```powershell
.\keysight-logger.exe start-trigger-record `
  --resource "<VISA_RESOURCE>" `
  --measurement voltage-dc `
  --trigger-mode immediate `
  --max-samples 1 `
  --csv ".\data\cli_smoke.csv"
```

5. 確認指令正常結束、CSV 檔案已建立，且 CSV 包含一筆數據列。
6. 在進行較長時間的數據擷取前，請先核對 CSV 的數值與儀器前面板的讀值是否一致。

進行即時擷取時請使用明確的資源字串。請勿依賴腳本或無人值守的工作流程來猜測應使用哪台儀器。

## 選擇測量類型

請選擇與儀器接線及待測訊號相符的測量類型：

- `voltage-dc`：直流電壓。
- `voltage-dc-ratio`：直流電壓比。
- `current-dc`：直流電流。
- `voltage-ac`：交流電壓。
- `current-ac`：交流電流。
- `resistance-2w`：2 線電阻。
- `resistance-4w`：4 線電阻。

測量電流或 4 線電阻前，請先確認輸入端子是否正確。
使用交流 (AC) 模式時，請先執行低風險的快速測試 (smoke test)，並將 CSV 數值與前面板讀值進行比對，確認無誤後再使用該設定進行較長時間的擷取。

## 選擇觸發模式

`--trigger-mode immediate` 適用於最簡單的工作流程。作業一啟動，儀器就會開始擷取數據。除非您刻意要進行連續測量，否則請加上 `--max-samples` 限制次數。

當作業需要等待軟體觸發指令時，請使用 `--trigger-mode software`。在一個終端機啟動 logger，然後從另一個終端機發送觸發訊號：

```powershell
.\keysight-logger.exe send-command
```

當作業需要按排程進行軟體觸發讀取時，請使用計時器擷取 (timer capture)。請明確設定計時器間隔，並在驗證設定時保持作業的有界性 (bounded，即設定次數上限)。

只有在已連接物理觸發訊號，且操作人員了解觸發邊緣 (trigger edge) 與延遲 (delay) 設定的情況下，才使用外部或硬體觸發模式。硬體觸發超時 (timeout) 是一種保護性的重新準備 (re-arm) 條件，並不自動代表測量失敗。

## 常見設定

`--resource` 是儀器的 VISA 位址。請使用 `list-resources --live-only` 回傳的值，或由操作人員提供的已知資源。

`--csv` 是輸出檔案路徑。若省略此項，CLI 會自動產生一個帶有時間戳記的 CSV 路徑。當您需要可預測的檔案位置以便進行檢閱或自動化處理時，請使用明確的路徑。

`--max-samples` 用來限制簡單作業的執行次數。在進行快速測試與驗證時請使用它，讓指令能自行停止。

`--auto-range` (自動換檔) 讓儀器自行選擇測量範圍。除非測量設定要求固定範圍，否則請保持啟用。

當自動換檔停用時，使用 `--range` 來選擇手動範圍。請選擇一個能安全涵蓋預期訊號的範圍。

`--nplc` 控制直流與電阻測量的積分時間。較高的數值速度較慢，但可能更穩定。交流模式只接受中立的預設值，因為它們不會寫入 NPLC 的 SCPI 指令。

`--auto-zero` (自動歸零) 控制直流與電阻測量的偏移處理。它可以提高精確度，但可能會減慢讀取速度。交流模式不會寫入 Auto Zero 的 SCPI 指令。

`--ac-bandwidth-hz` (交流頻寬/濾波器) 適用於交流電壓、交流電流、頻率與週期。頻率與週期省略此選項時預設為 `20` Hz。

`--gate-time-s` 適用於頻率與週期。可選 `0.01`、`0.1` 或 `1` 秒，預設為 `0.1` 秒。

`--freq-period-timeout` 僅適用於頻率，可選 `auto` 或 `1s`，預設為 `auto`。週期不會送出 timeout SCPI；若搭配週期明確指定此選項，CLI 會在開啟 VISA 前拒絕。

`--current-terminal` (電流端子) 適用於電流測量。請與儀器上實際使用的電流端子保持一致。

`--trigger-timeout-ms` (觸發超時) 控制觸發工作流程在進入保護性超時機制前的等待時間。只有在測量設定有意等待更長時間時，才調高此值。

有關完整的可接受值與驗證限制，請參閱 [驗證參數限制](README.zh-TW.md#已驗證引數限制)。

## CSV 輸出

每個擷取到的樣本都會被寫成 CSV 檔案中的一列 (row)。在進行快速測試後，請檢查 CSV 檔案以確認：

- 至少有一筆數據列；
- 預期的 `measurement_type` (測量類型)；
- 預期的 `unit` (單位)；
- 預期的 `trigger_source` (觸發來源)；
- 一個與前面板顯示足夠接近，且符合測試設定預期的數值。

每擷取一個樣本後，CSV 都會立即刷新 (flush) 寫入磁碟，因此即使在較長時間的作業中，也隨時能查看已完成的數據列。

## 停止作業

對於有界的驗證作業，建議使用 `--max-samples` 讓作業自行停止。

若要停止正在執行中的 worker 程式，請使用下列其中一種停止方法：

- 在 logger 終端機按下 `q` 鍵；
- 按下 `Ctrl+C` 或 `Ctrl+Break`；
- 從另一個終端機執行 stop 指令：

```powershell
.\keysight-logger.exe stop
```

停止後，請確認指令已乾淨結束，並且 CSV 中包含預期的數據列。

## 常見問題

如果缺少 `keysight-logger.exe`，請確認您正處於包含 CLI 執行檔的發布資料夾中。如果您的發布版本使用帶有版本號的名稱，如 `keysight-logger-<version>.exe`，請在指令中使用該檔案名稱。

如果 `list-resources` 顯示過時失效的資源，請使用 `list-resources --verify` 來查看哪些資源有回應，以及其他資源失敗的原因。如果您只想要對 `*IDN?` 做出回應的資源，請使用 `--live-only`。

如果找不到任何即時連線的資源，請檢查儀器電源、USB/LAN/GPIB 連線、VISA 驅動程式是否能識別儀器，以及是否有其他程式正在佔用該儀器。

如果在開啟儀器前作業就被阻擋，請閱讀驗證錯誤訊息，並調整其指出的選項設定。CLI 會在進行實體 I/O 之前驗證常見設定。

如果硬體觸發作業似乎卡在等待狀態，請確認物理觸發訊號、斜率 (slope)、延遲 (delay) 與超時 (timeout) 設定。若遺失觸發邊緣 (trigger edges) 訊號，會導致作業根據設定的超時行為繼續等待或重新準備 (re-arm)。

## 更多 CLI 文件

- [CLI README](README.zh-TW.md)：完整的指令參考、驗證腳本、範例、參數限制與自動化工作流程。
- [CLI Integration](cli-integration.md)：CLI 轉接器 (adapter) 的維護邊界說明。
- [Meters CLI JSON / JSONL Contract](../contracts/meters-cli-jsonl-contract.md)：用於自動化的結構化輸出 schema。
- [Meters Worker Contract](../contracts/meters-worker-contract.md)：worker 控制平面 (control plane) 與產出物合約。
