# Keysight Logger Core

Core 包含供 CLI 與 WebUI 元件在整合 Keysight 34461A 時所使用的公開 API 與擷取執行階段合約 (acquisition runtime contract)。

Core 負責處理共享的請求模型、驗證、dry-run 規劃、執行階段工作階段協調 (runtime session orchestration)、事件/結果類型、控制面介面 (control-plane interfaces)、設定檔 metadata，以及 Keysight 34461A 擷取執行階段的安全規則。它內建於單一的 `keysight-logger` 發行套件中，同時保留了 `keysight_logger_core` 的 import 邊界。

CLI 與 WebUI 元件各自負責其命令列、網頁、包裝器 (wrapper) 與序列化層。Core 絕不可 import `keysight_logger_cli` 或 `keysight_logger_webui`。

## 驗證

無硬體 Core 驗證：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/core -q -p no:cacheprovider
```

除了明確檢查元件邊界的測試之外，Core 驗證不應需要 import CLI 或 WebUI。

## 文件

- [Core 整合](integration.md)
- [支援的型號](supported-models.md)
- [變更日誌](CHANGELOG.md)
