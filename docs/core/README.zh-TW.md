# Meters Tool Core

Core 包含供 CLI 與 WebUI 元件整合支援的數位萬用電表時使用的公開 API 與擷取執行階段合約。它會隨單一的 `meters-tool` 發行套件一同提供，同時保留 `meters_tool_core` 的 import 邊界。

## 用途與權責

Core 負責共享請求模型、請求驗證、dry-run 規劃、執行階段工作階段協調、儀器設定檔 metadata、實機支援政策、執行階段事件與結果、控制面介面，以及擷取安全規則。

CLI 與 WebUI 負責各自的輸入解析、顯示文字、在地化、終端機與瀏覽器工作流程、序列化、HTTP/SSE payload，以及其他配接器專屬合約。Core 不得 import `meters_tool_cli` 或 `meters_tool_webui`。

Core 可以透過 `StartRequest` 與 `InstrumentConfig` 傳遞選用的 `visa_library` 值。未設定時，live VISA 工作階段會使用 `pyvisa.ResourceManager("@ivi")`，明確要求 System VISA，不會自動退回 `@py`，也不會由 `PYVISA_LIBRARY` 改用其他 backend。CLI、WebUI 與 Desktop 可選擇隨程式提供的 `@py`，但正式支援僅限已註冊的 34461A TCPIP scope。

進行支援政策比對時，未設定或空白 selector 對應 `system_visa`，`@py` 對應 `pyvisa_py`，`@bt` 則保留為獨立的 `pyvisa_bt` identity，其他 selector 仍對應 `custom_visa`。Backend identity 本身不代表 Product support；實機擷取需要符合 [Supported Models](supported-models.zh-TW.md) 中已註冊的 Product-open scope。未註冊的 backend selector 會在一般支援政策規則下 fail closed。WebUI 僅接受未設定／空白的 System VISA selector 或 `@py`。

## 請求准入與配接器邊界

`StartRequest` 是 Core 供驗證、dry-run 規劃、模擬與執行階段工作階段設定共用的請求邊界。配接器必須先將自己的輸入轉換為 Core 擁有的值，再送出請求。

建立 `StartRequest` 前，配接器應：

- 將空白的選用欄位轉換為 `None`；
- 將數值輸入轉換為 `int` 或 `float`；
- 將切換選項轉換為布林值或文件定義的 Core 語意值；
- 正規化配接器擁有的 alias；
- 將在地化標籤與顯示選項對應至 canonical Core 值；
- 將終端機格式、在地化字串、瀏覽器標籤、HTTP/SSE payload 細節、wrapper 相容欄位及其他配接器 schema 保留在 Core 之外。

CLI 的 `argparse.Namespace` 與 WebUI 的表單或 JSON 物件不得直接成為 Core 驗證合約。它們必須先轉換為 `StartRequest`。

即使配接器已停用或過濾某個選項，Core 驗證仍是權威邊界。不受支援的設定檔組合、無效的請求值與缺少的實機支援 scope 都必須 fail closed。`run_start_session()` 會解析執行階段設定檔，並在連接 backend 與設定儀器之前再次執行最終請求驗證與支援政策閘門，因此直接呼叫 Core 的程式也不能繞過 CLI 與 WebUI 使用的相同邊界。

完整的欄位正規化與驗證流程請參閱 [Core 整合](integration.md#request-boundary)。

## 實體身份與設定檔邊界

`InstrumentProfile.model` 是既有 request、expected-model、IDN、CLI、WebUI 與 runtime 合約使用的 canonical 儀器型號 token：

| 儀器 | Canonical 型號 | 穩定型號 ID |
| --- | --- | --- |
| Keysight 34461A | `34461A` | `keysight-34461a` |
| Keysight 34460A | `34460A` | `keysight-34460a` |

Canonical 型號與穩定型號 ID 彼此相關，但用途不同。像 `Keysight 34461A` 這類顯示文字只屬於 presentation。穩定型號 ID 由 Core 設定檔明確宣告，不會在執行時由在地化文字或顯示文字產生。

對 live 啟動而言：

- 省略 `StartRequest.instrument_model` 代表由 Core 透過 `*IDN?` 解析已連接的設定檔；
- 明確選擇的型號只作為 expected-model guard；
- 透過 `*IDN?` 偵測到的身份仍是權威來源；
- 選擇值與偵測值不一致時，必須在任何會影響儀器的設定或 write SCPI 前失敗；
- 選擇型號或穩定型號 ID 絕不會為不同硬體解鎖支援。

對 dry-run 與模擬而言，選擇的型號是無硬體規劃設定檔。除非 simulator 資源已確定地命名型號，例如 `SIM::34460A` 或 `SIM::34461A`，否則必須提供明確型號。

配接器必須使用 Core 的設定檔查找與正規化功能，不得維護另一份互相競爭的型號或型號 ID registry。

完整身份合約請參閱 [Core 整合](integration.md#profile-identity)。

## 實機支援政策

一般 CLI、WebUI 與直接 Core 啟動使用 Product mode。Product mode 要求確切偵測到的型號、連線 scope 與請求功能必須一起 Product-open。實機政策評估包含：

1. 偵測到的型號設定檔；
2. 確切的 transport 與 VISA backend scope；
3. 正規化後的 measurement feature；
4. 有效的 trigger-mode feature。

某個連線 scope 的支援不會自動開放另一個 scope。例如，USB/system-VISA 的支援不會自動開放 LAN/system-VISA 或 LAN/pyvisa-py。

Core 是配接器與直接呼叫端的最終支援與安全閘門。`run_start_session()` 會在連接 backend 與設定儀器前，再次執行最終請求驗證與支援政策檢查。不受支援或非 Product-open 的確切 scope 必須 fail closed。Simulator 只驗證確定性的無硬體合約與工作流程，不代表實機量測準確度或硬體支援。

使用者可閱讀的支援矩陣請參閱 [支援的型號](supported-models.zh-TW.md)；支援政策的 machine contract 與 policy mode 請參閱 [Core 整合](integration.md)；contributor validation 與 promotion 請參閱 [貢獻指南](../CONTRIBUTING.md)。

## 公開套件介面

使用端應優先從 `meters_tool_core` package root import。Package root 的 `__all__` 清單是穩定的公開 import 邊界。以下模組提供該邊界背後的主要公開領域：

| 模組 | 公開職責 |
| --- | --- |
| `meters_tool_core.capabilities` | 提供配接器使用的量測與設定檔 capability projection |
| `meters_tool_core.models` | `StartRequest`、儀器設定檔、型號正規化與設定檔解析 |
| `meters_tool_core.run_plan` | 建立 dry-run `StartPlan` |
| `meters_tool_core.validation` | 請求驗證、觸發模式解析與 buffer overflow 警告 |
| `meters_tool_core.support_policy` | 確切實機支援查找、feature requirements、metadata 驗證與政策執行閘門 |
| `meters_tool_core.session` | 執行階段事件、結果、控制面介面與停止控制 |
| `meters_tool_core.runner` | 透過 `run_start_session()` 進行最終執行階段協調 |

這些模組用來說明權責；下游配接器仍應優先使用文件定義的 package-root import，不應依賴 submodule 中只供實作使用的 helper。

不得將內部 helper、測試 hook 或相容 alias 描述為公開 API。確切的 package-root export 清單由 `src/meters_tool_core/__init__.py` 定義，並記錄於 [Core 整合](integration.md#public-imports)。


## 驗證

無硬體 Core 驗證：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/core -q -p no:cacheprovider
```

除了明確檢查元件邊界的測試之外，Core 驗證不應需要 import CLI 或 WebUI。

## 文件

- [Core 整合](integration.md)
- [支援的型號](supported-models.zh-TW.md)
- [變更日誌](../../CHANGELOG.md)
