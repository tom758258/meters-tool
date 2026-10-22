# 支援型號

本文件說明 Meters Tool 使用者目前可用的 Product-open 支援範圍。
它是支援型號、連線、backend、量測、觸發與重要限制的共用使用者參考文件。

## 型號設定檔

Meters Tool 目前支援以下儀器型號：

| Model ID | 儀器 | 讀值記憶體 | 最大電流 | 外部觸發 |
| --- | --- | ---: | ---: | --- |
| `keysight-34461a` | Keysight 34461A | 10000 | 使用 10A terminal 時最高 10 A | 支援 |
| `keysight-34460a` | Keysight 34460A | 1000 | 3 A | base scope 不支援 |

CLI 與 WebUI 的 live 執行在未指定 model 時，會依連接儀器身分偵測 34460A/34461A。
明確選擇 model 只是 expected-model check：不一致時會在設定前失敗，不會解鎖其他支援範圍。
Dry-run 與 simulation 可使用所選的 planning model。

## 精確範圍實機支援

live Product 支援採精確範圍制。Meters 目前提供一個獨立支援的 Product workflow，`start-trigger-record`。
只有在偵測到的 model、workflow、精確 transport/backend 連線範圍、量測、觸發模式與要求的 Custom acquisition 功能同時受支援時，live 執行才是 Product-open。
支援不會在 USB/system-VISA、TCPIP/system-VISA 與 TCPIP/pyvisa-py 之間轉移。
硬性 model/profile 限制仍會強制執行。

不在目前 Product-open matrix 內的要求，包括未知 model、不支援的連線或功能組合，以及硬性安全限制，都會 fail closed。

在 live 模式中，CLI `--model` 與 WebUI `Expected model` 只是 expected-model guard。
runtime driver/profile 由連接儀器 `*IDN?` 決定。selected/detected 不一致會在儀器設定前失敗。
Dry-run 與 simulator 執行使用 selected/no-hardware planning profile，不查詢實機。

| 能力 / workflow | 34461A | 34460A |
| --- | --- | --- |
| 立即 DC/AC 電壓/電流 | 支援 | USB/system-VISA 範圍支援 |
| 2W/4W 電阻 | 支援 | USB/system-VISA 範圍支援 |
| Software trigger/timer | 支援 | USB/system-VISA 範圍支援 |
| Custom buffered workflows | 下列連線範圍支援 | USB/system-VISA 範圍支援，受限於 1000-reading memory |
| Frequency | 支援 | USB/system-VISA 範圍支援 |
| Period | 支援，不提供 Period timeout 選項 | 支援，不提供 Period timeout 選項 |
| External simple/custom | 支援 | base 34460A profile 未支援 |
| DCV Ratio | 支援 | 僅 USB/system-VISA 支援 |
| 10 A / current-terminal | 支援，需操作人員確認接線 | 不支援 |
| 超過 model memory 的 buffer drain | 最高 10000 readings | 超過 1000 不支援 |
| LAN/TCPIP 搭配 system VISA | 34461A 支援 | 目前不支援 |
| LAN/TCPIP 搭配 pyvisa-py `@py` | CLI、WebUI 與 Desktop 支援 34461A | 目前不支援 |

### 精確範圍詳細資訊

- **接線安全與 10 A 路徑**：選擇 10 A current terminal 需要操作人員手動確認實體導線接線，以避免硬體損壞。
- **讀值記憶體限制**：34461A custom runs 超過 10,000 readings、34460A custom runs 超過 1,000 readings 時，都需要明確確認 overflow-risk。Buffer drain 仍受限於 model reading-memory limit。
- **Fail-Closed Policy**：上方 matrix 中未明確標示為 open 的任何 model、transport、backend、量測或觸發組合，均為未支援並 fail closed。

### Custom Acquisition

Custom acquisition 在以下精確連線範圍為 Product-open：

| Model | Transport | Backend | Custom 觸發模式 |
| --- | --- | --- | --- |
| 34460A | USB | System VISA | Immediate / Software Custom |
| 34461A | USB | System VISA | Immediate / Software / External Custom |
| 34461A | TCPIP | System VISA | Immediate / Software / External Custom |
| 34461A | TCPIP | PyVISA-py（`@py`） | Immediate / Software / External Custom |

每個列出的 Custom 觸發模式皆支援 Finite 與 Infinite 計數，搭配 Monitor 或
Stop-on-Overflow。34460A TCPIP 無論使用 System VISA 或 PyVISA-py，
在 Product mode 仍不可用，包含 Custom acquisition。
Streaming 沿用相同 workflow 與精確範圍支援規則。

Infinite Custom 需要明確確認 overflow-risk 並指定 sample count。
Finite 執行超過 model reading-memory limit 時，也需要該確認，
但不會提高 buffer-drain limit。Monitor 觀察 overflow；Stop-on-Overflow
在偵測到 overflow 時要求停止。兩者都不保證擷取過程完全沒有資料遺失。

## VISA Backend 支援

VISA backend 支援是精確連線範圍的一部分，而不是 model capability。
除非介面明確提供另一個受支援 backend，正常 Product 作業使用電腦的 System VISA runtime。
選用 backend scopes 互相獨立：選擇另一個 backend 不會解鎖未支援的 model、transport、量測或其他 Product 支援。
WebUI 與 Desktop 可在裝置設定選擇 System VISA（預設）或 PyVISA-py（`@py`）。
PyVISA-py 預設安裝並隨 Windows 成品提供，僅支援 34461A TCPIP；
USB/`@py`、34460A TCPIP 及其他 backend 不在正式支援範圍。
System VISA 明確載入 `@ivi`；即使設定 `PYVISA_LIBRARY`，也不會自動改用其他 backend。

34461A TCPIP 使用 PyVISA-py 時，`control_ren(6)` 與 `control_ren(0)`
可能因已知相容性限制而發生 `VisaIOError`。Cleanup 結果會保留原始錯誤；
這些結果不代表 REN 控制成功，也無法獨立確認儀器實際的 Local 狀態。
需要手動操作時，請先在儀器上確認 Local 狀態。

## 量測能力

34460A 與 34461A profiles 目前提供相同的量測名稱，順序如下：

- `current-dc`
- `voltage-dc`
- `voltage-dc-ratio`
- `current-ac`
- `voltage-ac`
- `frequency`
- `period`
- `resistance-2w`
- `resistance-4w`

每個受支援量測都有下表列出的 model-specific 範圍與限制。

| Measurement | 34461A 範圍選項 | 34460A 範圍選項 | NPLC 選項 | AC filter | Gate time | Frequency timeout | Current terminal | DCV input Z | Auto Zero |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `current-dc` | 0.0001, 0.001, 0.01, 0.1, 1, 3, 10 A | 0.0001, 0.001, 0.01, 0.1, 1, 3 A | 0.02, 0.2, 1, 10, 100 | none | none | none | 34461A: 3, 10; 34460A: none | none | on, off, once |
| `voltage-dc` | 0.1, 1, 10, 100, 1000 V | 同 34461A | 0.02, 0.2, 1, 10, 100 | none | none | none | none | default, 10m, auto | on, off, once |
| `voltage-dc-ratio` | 0.1, 1, 10, 100, 1000 V | 同 34461A | 0.02, 0.2, 1, 10, 100 | none | none | none | none | default, 10m, auto | on/default only |
| `current-ac` | 0.0001, 0.001, 0.01, 0.1, 1, 3, 10 A | 0.0001, 0.001, 0.01, 0.1, 1, 3 A | none | 3, 20, 200 Hz | none | none | 34461A: 3, 10; 34460A: none | none | none |
| `voltage-ac` | 0.1, 1, 10, 100, 750 V | 同 34461A | none | 3, 20, 200 Hz | none | none | none | none | none |
| `frequency` | 0.1, 1, 10, 100, 750 V | 同 34461A | none | 3, 20, 200 Hz; default 20 | 0.01, 0.1, 1 s; default 0.1 | auto, 1s; default auto | none | none | none |
| `period` | 0.1, 1, 10, 100, 750 V | 同 34461A | none | 3, 20, 200 Hz; default 20 | 0.01, 0.1, 1 s; default 0.1 | none | none | none | none |
| `resistance-2w` | 100, 1000, 10000, 100000, 1000000, 10000000, 100000000 Ohm | 同 34461A | 0.02, 0.2, 1, 10, 100 | none | none | none | none | none | on, off, once |
| `resistance-4w` | 100, 1000, 10000, 100000, 1000000, 10000000, 100000000 Ohm | 同 34461A | 0.02, 0.2, 1, 10, 100 | none | none | none | none | none | none |

Auto Zero 支援 `current-dc`、`voltage-dc` 與 `resistance-2w` 的 `on`、`off`、`once`。
`voltage-dc-ratio` 的 Auto Zero 僅接受 `default`／`on` 狀態。
AC、Frequency 與 Period 量測不使用 NPLC 或 Auto Zero。Resistance 4-wire 拒絕 once Auto Zero 選項。

DCV input impedance 適用於 voltage-dc 與 voltage-dc-ratio。允許值為 default、10m、auto；default 保留目前儀器設定狀態。

AC bandwidth/filter selection 適用於 `current-ac`、`voltage-ac`、`frequency` 與 `period`。允許值為 `3`、`20`、`200` Hz。
未設定時保留既有 AC current/voltage 行為。Frequency 與 Period 則套用有效 default `20` Hz filter。

Frequency 與 Period 使用電壓範圍選項 `0.1`、`1`、`10`、`100`、`750` V。Auto Range 是 default。
Gate time 可選 `0.01`、`0.1` 或 `1.0` 秒，default 為 `0.1`。
Frequency timeout 可選 `auto` 或 `1s`，default 為 `auto`。Period 不提供 timeout 選項。明確指定 Period timeout 值會被拒絕。

DCV Ratio 讀值單位為 `ratio`。Frequency 讀值使用 `Hz`，Period 使用 `s`。

Current terminal selection 僅適用於 34461A current profiles。
選擇 10 A range 需要使用 10 A terminal；在 manual range 下選擇 10 A terminal 則需要 10 A range。
操作人員必須確認 range、terminal 與實體導線接線，以避免硬體損壞。
34460A current profiles 最高僅支援 3 A，且沒有 34461A 式的 10 A terminal 路徑。

## 觸發能力

34461A 支援：

- software
- software timer
- external
- immediate
- immediate-custom
- software-custom
- external-custom

34460A base scope 支援：

- software
- software timer
- immediate
- immediate-custom
- software-custom

34460A base scope 不支援外部觸發模式，因為該型號的 LAN/LXI/external trigger 能力為選配。

## 讀值記憶體

Custom runs 會比較要求的 reading count 與 model reading-memory limit。

- 34461A custom runs 超過 10000 readings 時，需要明確確認 overflow-risk。
- 34460A custom runs 超過 1000 readings 時，需要明確確認 overflow-risk。
- Buffer drain 仍受限於 model reading-memory limit，不會因該確認而放寬。

## 未支援範圍

本文件未列出的 model 目前不支援 Product mode。
未列為 Product-open 的 model、connection/backend、量測、trigger mode 或 workflow 組合均為未支援。
未支援組合會被拒絕，而不是被隱式啟用。
