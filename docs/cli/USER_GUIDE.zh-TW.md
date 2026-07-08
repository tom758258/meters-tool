# Meters Tool CLI 使用者指南

本指南適用於取得已建置之 CLI 執行檔或已安裝的 `meters-tool` 指令，並使用它來記錄支援的 Keysight Truevolt DMM 量測數據的操作人員。本指南專注於正常的量測工作流程與常見設定。如需開發人員設定、驗證腳本、JSON/JSONL 輸出與自動化合約，請參閱 [CLI README](README.zh-TW.md)。

## 啟動 CLI

在包含 CLI 執行檔的資料夾下開啟 PowerShell，並檢查它：

```powershell
.\meters-tool.exe --version
```

發佈資料夾可能包含帶有版本號的執行檔名稱，例如：

```text
meters-tool-<version>.exe
```

如果您的發佈資料夾使用帶有版本號的執行檔，請在下方的指令中使用該檔案名稱。開發人員或從原始碼簽出 (source-checkout) 的使用者，應參閱 [CLI README](README.zh-TW.md) 以取得虛擬環境、模組、驗證與建置指令。

## 首次實機執行 (First Live Run)

在檢查新的電腦、VISA 執行階段、連線或儀器設定時，請使用此流程。

1. 開啟 Keysight 34460A 或 34461A 電源並將其連接至電腦。
2. 列出目前能回應 `*IDN?` 指令的資源：

```powershell
.\meters-tool.exe list-resources --live-only
```

3. 複製儀器的資源字串。
4. 執行一次有界限的即時模式 (immediate-mode) 樣本：

```powershell
.\meters-tool.exe start-trigger-record `
  --resource "<VISA_RESOURCE>" `
  --measurement voltage-dc `
  --trigger-mode immediate `
  --max-samples 1 `
  --csv ".\data\cli_smoke.csv"
```

5. 確認指令正常退出、CSV 檔案已存在，且 CSV 包含一筆資料列。
6. 在信任較長期的擷取之前，請將 CSV 數值與前面板讀數進行對比。

Live 啟動在省略 `--model` 時會透過已連接儀器的 IDN 自動偵測 34460A 或 34461A。只有在 Start 必須要求該 IDN 相符時，才加入 `--model 34460A` 或 `--model 34461A`；明確的 live 不符會在 setup SCPI 之前失敗。Dry-run 指令需要 `--model`，除非資源是可確定型號的 simulator resource，例如 `SIM::34460A` 或 `SIM::34461A`。

CLI 預設使用電腦的系統 VISA 執行階段，例如 Keysight IO Libraries Suite 或 NI-VISA。進階的 pyvisa-py LAN 診斷可以安裝可選的 backend 套件，並在 `list-resources` 或 `start-trigger-record` 中加入 `--visa-library "@py"`；`--backend "@py"` 也接受作為別名。一般 WebUI 執行則使用預設的系統 VISA 執行階段。

進行實機擷取時請使用明確的資源字串。請勿依賴腳本或無人值守的工作流程來猜測應使用哪台儀器。

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
對於 AC、頻率與週期模式，請先執行低風險的快速功能健檢 (smoke test)，並將 CSV 數值與前面板讀數進行對比，確認無誤後再將該設定用於較長期的擷取。

## 選擇觸發模式

`--trigger-mode immediate` 適用於最簡單的工作流程。作業一啟動，儀器就會開始擷取數據。除非您刻意要進行連續執行，否則請加上 `--max-samples`。

當作業需要等待軟體觸發指令時，請使用 `--trigger-mode software`。在一個終端機啟動記錄器 (logger)，然後從另一個終端機發送觸發訊號：

```powershell
.\meters-tool.exe send-command
```

當作業需要按排程進行軟體觸發讀取時，請使用計時器擷取 (timer capture)。請明確設定計時器間隔，並在驗證設定時保持作業具備有界限 (bounded) 的特性。

只有在實體觸發訊號已連接，且操作人員了解觸發邊緣 (trigger edge) 與延遲 (delay) 設定的情況下，才使用外部或硬體觸發模式。硬體觸發逾時 (timeout) 是一種保護性的重新準備 (re-arm) 條件，並非自動代表量測失敗。

## 常見設定

`--resource` 是儀器的 VISA 位址。請使用 `list-resources --live-only` 回傳的值，或由操作人員提供的已知資源。

`--visa-library` 是進階 CLI 專用的 PyVISA backend 選擇器。一般情況下請省略它。只有在刻意使用可選的 pyvisa-py backend 測試時，才使用 `--visa-library "@py"`；LAN/TCPIP 通常是最先嘗試的最佳路徑。

`--csv` 是輸出檔案路徑。若省略此項，CLI 會自動建立一個帶有時間戳記的 CSV 路徑。當您需要可預測的檔案位置以便進行檢閱或自動化處理時，請使用明確的路徑。

`--max-samples` 用來限制簡單作業的執行次數。在進行快速功能健檢與驗證時請使用它，讓指令能自行停止。

`--auto-range` (自動範圍) 讓儀器自行選擇範圍。除非量測設定要求固定範圍，否則請保持啟用自動範圍。

當自動範圍停用時，使用 `--range` 來選擇手動範圍。請選擇一個能安全涵蓋預期訊號的範圍。

`--nplc` 控制直流與電阻量測的積分時間。較高的數值速度較慢，但可能更穩定。AC、頻率與週期模式只接受中性的預設值，因為它們不會寫入 NPLC SCPI 指令。

`--auto-zero` (自動歸零) 控制直流與電阻量測的偏移處理。它可以提高精確度，但可能會減慢讀取速度。AC、頻率與週期模式不會寫入 Auto Zero SCPI 指令。

`--ac-bandwidth-hz` (交流頻寬/濾波器) 適用於交流電壓、交流電流、頻率與週期。頻率與週期省略此選項時預設為 `20` Hz。

`--gate-time-s` 僅適用於頻率與週期。可選 `0.01`、`0.1` 或 `1` 秒；預設為 `0.1` 秒。

`--freq-period-timeout` 僅適用於頻率。除非量測程序要求 `1s` 行為，否則請保持預設的 `auto`。週期不會傳送逾時指令；搭配週期明確指定此選項將被拒絕。

`--current-terminal` (電流端子) 適用於電流量測。請與儀器上實際使用的電流端子保持一致。

`--trigger-timeout-ms` (觸發逾時) 控制觸發工作流程在進入保護性逾時路徑前的等待時間。只有在量測設定刻意要等待更長時間時，才調高此值。

有關完整的可接受值與驗證限制，請參閱 [已驗證引數限制](README.zh-TW.md#已驗證引數限制)。

## CSV 輸出

每筆擷取的樣本都會被寫成 CSV 檔案中的一列。在快速功能健檢後，請檢查 CSV 檔案以確認：

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

如果缺少 `meters-tool.exe`，請確認您正處於包含 CLI 執行檔的發佈資料夾中。如果您的發佈版本使用帶有版本號的名稱，如 `meters-tool-<version>.exe`，請在指令中使用該檔案名稱。

如果 `list-resources` 顯示過期的資源，請使用 `list-resources --verify` 來查看哪些資源有回應，以及其他資源失敗的原因。如果您只想要對 `*IDN?` 做出回應的資源，請使用 `--live-only`。

如果找不到任何作用中 (live) 的資源，請檢查儀器電源、USB/LAN/GPIB 連線、VISA 驅動程式的可見度，以及是否有其他程式正在佔用該儀器。

如果在開啟儀器前作業就被阻擋，請閱讀驗證錯誤訊息，並調整其指出的選項設定。CLI 會在進行實機 I/O 之前驗證常見設定。

如果硬體觸發作業似乎在等待，請確認實體觸發訊號、斜率 (slope)、延遲 (delay) 與逾時 (timeout) 設定。遺失觸發邊緣 (trigger edges) 訊號會導致作業根據設定的逾時行為繼續等待或重新準備 (re-arm)。

## 更多 CLI 文件

- [CLI README](README.zh-TW.md)：完整的指令參考、驗證腳本、範例、引數限制與自動化工作流程。
- [CLI 整合](cli-integration.md)：CLI 配接器的維護邊界說明。
- [Meters CLI JSON / JSONL 合約](../contracts/meters-cli-jsonl-contract.md)：用於自動化的結構化輸出 schema。
- [Meters Worker 合約](../contracts/meters-worker-contract.md)：工作器控制面與產物合約。
