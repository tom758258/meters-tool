# Meters Tool CLI 使用指南

本指南適用於已取得建置完成的 CLI 執行檔，或已安裝 `meters-tool` 命令，並使用它擷取與記錄支援之數位萬用電表測量資料的操作員。本指南著重於一般的測量工作流程與常用設定。若要了解開發人員設定、驗證指令碼、JSON/JSONL 輸出以及自動化合約，請參閱 [CLI README](README.zh-TW.md)。

## 啟動 CLI

在包含 CLI 執行檔的資料夾中開啟 PowerShell，並檢查版本：

```powershell
.\meters-tool.exe --version
```

發行套件資料夾可能包含帶有版本號的執行檔名稱，例如：

```text
meters-tool-<version>.exe
```

若您的發行套件資料夾使用帶有版本號的執行檔，請在下方的命令中替換為該檔名。開發人員或自原始碼簽出（source checkout）的使用者，應參閱 [CLI README](README.zh-TW.md) 以取得虛擬環境、模組、驗證以及建置命令。

## 首次實體執行

在檢查新電腦、VISA 執行期、連線或儀器設定時，請使用以下工作流程。

1. 開啟 Keysight 34460A 或 34461A 的電源，並將其連接至電腦。
2. 列出目前可回應 `*IDN?` 查詢的資源：

```powershell
.\meters-tool.exe list-resources --live-only
```

3. 複製儀器的資源字串，並在目前的 PowerShell 工作階段中設定一次：

```powershell
$env:METER_RESOURCE = "USB0::...::INSTR"
```

   此值可以是探索所傳回的任何實體 VISA 資源，包括 USB 或 TCPIP/LAN 資源。

4. 執行一次受限的立即模式（immediate-mode）樣本擷取：

```powershell
.\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --measurement voltage-dc `
  --trigger-mode immediate `
  --max-samples 1 `
  --csv ".\data\cli_smoke.csv"
```

5. 確認命令已結束、CSV 檔案已存在，且 CSV 包含一筆資料列。
6. 在進行更長時間的擷取前，先比對 CSV 中的數值與儀器前置面板的讀數。

對於實體採集，請使用明確的 `--resource` 值。傳遞 `"$env:METER_RESOURCE"` 可使 CLI 獲得明確的資源；請勿依賴腳本或無人值守的工作流程來猜測該使用哪台儀器。

當省略 `--model` 時，實體啟動會透過連線儀器的 IDN 自動偵測 34460A 或 34461A。僅在啟動時需要強制符合該 IDN 時，才加入 `--model 34460A` 或 `--model 34461A`；實體不符會在設定前宣告失敗，且選擇的模型絕不會覆寫 IDN 選擇的設定檔。預演（乾跑）與模擬命令使用所選模型的設定檔，且需要 `--model`，除非資源是確定的模擬器資源 `SIM::34460A` 或 `SIM::34461A`。模型名稱由 Core 設定檔邏輯進行標準化與驗證，因此未知的模型將會失敗並顯示明確的驗證錯誤。

預設情況下，CLI 使用電腦的系統 VISA 執行期，例如 Keysight IO Libraries Suite 或 NI-VISA。進行進階 pyvisa-py LAN 診斷時，操作員可以安裝選用的後端套件，並將 `--visa-library "@py"` 加入至 `list-resources` 或 `start-trigger-record`。同樣也接受別名 `--backend "@py"`。已驗證的選用 `@py` 採集範圍為經由 LAN/TCPIP 連線的 34461A；34460A LAN/`@py` 對於目前可用的儀器尚未開放。一般的 WebUI 執行會使用預設的系統 VISA 執行期。

## 選擇測量類型

選擇與儀器接線及被測量訊號相符的測量類型：

- `voltage-dc`：DC 電壓。
- `voltage-dc-ratio`：DC 電壓比例。
- `current-dc`：DC 電流。
- `voltage-ac`：AC 電壓。
- `current-ac`：AC 電流。
- `frequency`：訊號頻率（Hz）。
- `period`：訊號週期（秒）。
- `resistance-2w`：2 線電阻。
- `resistance-4w`：4 線電阻。

在測量電流或 4 線電阻前，請確認輸入端子接線。對於 AC、頻率與週期模式，在將設定用於更長時間的採集之前，請先執行低風險的煙霧測試（smoke test）並比對 CSV 數值與前置面板讀數。

## 選擇觸發模式

對於最簡單的工作流程，請使用 `--trigger-mode immediate`。執行開始後，儀器便會開始擷取。除非您有意進行持續執行，否則請加入 `--max-samples`。

當執行需要等待來自 WebUI 的軟體觸發命令時，請使用 `--trigger-mode software`。在一個終端機中啟動記錄器，然後從另一個終端機傳送觸發：

```powershell
.\meters-tool.exe send-command
```

當執行需要按照排程進行軟體觸發的讀數時，請使用計時器擷取。明確設定計時器間隔，並在驗證設定時保持受限執行。

僅在已連接實體觸發訊號且操作員理解觸發邊緣（slope）與延遲設定時，才使用外部或硬體觸發模式。硬體觸發逾時是一種保護性的重新配置（re-arm）狀態，不一定代表測量失敗。

## 常用設定

`--resource` 為儀器的 VISA 位址。請使用由 `list-resources --live-only` 所傳回的值，或由操作員明確提供的已知資源。在 PowerShell 工作階段中，您可以將其儲存在環境變數中：

```powershell
$env:METER_RESOURCE = "USB0::0x2A8D::0x1301::MY12345678::INSTR"
```

通常，您可以省略 `--visa-library` 以在一般操作中使用系統 VISA。僅在有意使用選用 pyvisa-py 後端進行測試時，才使用 `--visa-library "@py"`；目前驗證的 `@py` 路徑為 34461A LAN/TCPIP。

`list-resources --verify` 會開啟偵測到的 VISA 資源並查詢 `*IDN?`。`list-resources --live-only` 隱含了驗證並隱藏失效項目。ASRL/RS-232 驗證使用短暫且受限的逾時，因此失效的序列埠項目不會阻擋後續的 USB 或 TCPIP 資源。序列埠結束字元選項 `--serial-read-termination` 與 `--serial-write-termination` 為僅用於 ASRL 驗證的 CLI 偵測相容性設定；它們並非採集設定。

`--csv` 為輸出檔案路徑。若省略，CLI 會建立具有時間戳記的 CSV 路徑。當您在檢視或自動化中需要可預測的檔案位置時，請使用明確的路徑。

`--max-samples` 限制簡單執行的次數。在煙霧測試與驗證期間使用它，使命令能自行停止。

`--auto-range` 允許儀器自動選擇量程。除非測量設定需要固定量程，否則請保持自動量程啟用。

`--range` 在停用自動量程時選擇手動量程。請選擇能安全涵蓋預期訊號的量程。

`--nplc` 控制 DC 與電阻測量的整合時間。較高的值較慢，但能提供更穩定的讀數。AC、頻率與週期模式只接受不會產生 NPLC SCPI 命令的中性預設值。

`--auto-zero` 控制 DC 與電阻測量的偏壓處理。它可以提高精確度，但可能會減慢讀數。AC、頻率與週期模式不寫入自動歸零 SCPI 命令。

`--ac-bandwidth-hz` 適用於 AC 電壓、AC 電流、頻率與週期。頻率與週期預設為 `20` Hz。

`--gate-time-s` 僅適用於頻率與週期。可選擇 `0.01`、`0.1` 或 `1` 秒；預設為 `0.1` 秒。

`--freq-period-timeout` 僅適用於頻率。除非測量程序需要 `1s` 行為，否則請保持預設的 `auto`。週期模式不傳送逾時命令；指定此選項於週期模式將會被拒絕。

`--current-terminal` 適用於電流測量。請選擇與儀器實際接線相符的電流端子。

`--trigger-timeout-ms` 控制觸發工作流程在進入保護性逾時路徑前的等待時間。僅在測量設定有意等待更長時間時才增加此值。

如需完整的可接受值與驗證限制，請參閱 [驗證的引數限制](README.zh-TW.md#驗證的引數限制validated-argument-limits)。

## CSV 輸出

每個擷取樣本都會寫成一筆 CSV 資料列。在執行煙霧測試後，請檢查 CSV 以確認：

- 至少包含一筆資料列；
- 相符的 `measurement_type`；
- 相符的 `unit`；
- 相符的 `trigger_source`；
- 與前置面板讀數足夠接近的數值。

每次擷取樣本後，程式都會立即將緩衝資料寫入 CSV（flush），因此即使執行時間較長，已完成的資料列也能立即使用。

## 停止執行

對於受限的驗證執行，建議使用 `--max-samples` 以讓執行自行停止。

對於執行中的背景工作（worker），請使用以下停止路徑之一：

- 在記錄終端機中按下 `q`；
- 在記錄終端機中按下 `Ctrl+C` 或 `Ctrl+Break`；
- 從另一個終端機執行停止命令：

```powershell
.\meters-tool.exe stop
```

停止後，確認命令已正常結束，且 CSV 包含預期的資料列。

## 常見問題

若缺少 `meters-tool.exe`，請確認您處於包含 CLI 執行檔的發行套件資料夾中。若您的發行套件使用帶有版本號的名稱（例如 `meters-tool-<version>.exe`），請在命令中使用該檔名。

若 `list-resources` 顯示失效資源，請使用 `list-resources --verify` 查看哪些資源有回應，以及其他資源失敗的原因。若您只需要回應了 `*IDN?` 的資源，請使用 `--live-only`。若 ASRL/RS-232 資源回報與結束字元相關的失效結果，請使用 `--serial-read-termination` 或 `--serial-write-termination` 重試偵測；這些選項僅會影響 ASRL 驗證。

若找不到實體資源，請檢查儀器電源、USB/LAN/GPIB 連線、VISA 驅動程式可視性，以及是否有其他程式佔用了儀器。

若執行在開啟儀器前被阻擋，請閱讀驗證錯誤並調整其指定的設定。CLI 會在進行實體 I/O 之前驗證常用設定。

若硬體觸發執行似乎在等待，請確認實體觸發訊號、斜率、延遲與逾時。遺漏觸發邊緣可能會使執行依據所設定的逾時行為繼續等待或重新進入待命狀態。

## 更多 CLI 說明文件

- [CLI README](README.zh-TW.md)：完整的命令參考、驗證指令碼、範例、引數限制以及自動化工作流程。
- [CLI 整合](cli-integration.md)：CLI 配接器維護邊界。
- [Meters CLI JSON / JSONL 合約](../contracts/meters-cli-jsonl-contract.md)：自動化的結構化輸出格式與結構描述。
- [Meters Worker 合約](../contracts/meters-worker-contract.md)：worker 控制面與成品合約。
