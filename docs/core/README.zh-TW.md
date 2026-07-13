# Meters Tool Core

Core 提供 CLI 與 WebUI 元件整合支援數位萬用電表時使用的公開 API 與採集執行期合約。

Core 負責 Meters Tool 採集執行期的共用請求模型、驗證、預演（dry-run）規劃、執行期工作階段協調、事件與結果類型、控制面介面、設定檔中繼資料及安全規則。Core 隨單一 `meters-tool` 發行套件提供，同時保留 `meters_tool_core` 的獨立匯入邊界。

Core 可透過 `StartRequest` 與 `InstrumentConfig` 攜帶選用的 `visa_library` 值。未設定時，實體 VISA 工作階段會使用 `pyvisa.ResourceManager()`，也就是系統預設的 VISA 執行期。CLI 診斷工具可以傳入 `@py` 等值；WebUI 執行則維持未設定。目前已驗證的 34461A 傳輸／後端範圍包括 USB／系統 VISA、LAN/TCPIP／系統 VISA，以及僅限 CLI 選用的 LAN/TCPIP／pyvisa-py `@py`。目前可用的 34460A 儀器尚未開放 LAN/TCPIP 範圍。

對於 CLI 或 WebUI 啟動，`StartRequest.instrument_model = None` 表示自動偵測實體儀器。配接器會先透過僅查詢 IDN 的預檢流程解析已連線儀器的設定檔，再進行驗證與規劃。預演與模擬啟動必須明確指定模型，除非模擬器資源本身已明確包含模型，例如 `SIM::34460A` 或 `SIM::34461A`。

CLI 與 WebUI 元件各自負責命令列、網頁、包裝器與序列化層。Core 不得匯入 `meters_tool_cli` 或 `meters_tool_webui`。

## 驗證

無硬體 Core 驗證：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/core -q -p no:cacheprovider
```

除非測試本身明確檢查元件邊界，否則 Core 驗證不應需要匯入 CLI 或 WebUI。

## 文件

- [Core 整合](integration.md)
- [支援的模型](supported-models.md)
- [變更日誌](CHANGELOG.md)
