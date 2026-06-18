# Keysight Logger Core

Core（核心）包含公用 API 以及 CLI 和 WebUI 元件在整合 Keysight 34461A 時所使用的擷取執行階段合約。

Core 擁有共享的請求模型、驗證、dry-run（模擬執行）規劃、執行階段工作階段協調、事件/結果類型、控制面介面、設定檔 metadata，以及 Keysight 34461A 擷取執行階段的安全規則。它被包裝在單一的 `keysight-logger` distribution 中發布，同時保留了 `keysight_logger_core` 的匯入（import）邊界。

CLI 和 WebUI 元件則各自擁有其命令列、網頁、包裝器（wrapper）和序列化層。Core 絕不可匯入 `keysight_logger_cli` 或 `keysight_logger_webui`。

## 驗證

無硬體的 Core 驗證：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/core -q -p no:cacheprovider
```

除了明確檢查元件邊界的測試之外，Core 驗證不應需要匯入 CLI 或 WebUI。

## 文件

- [Core 整合](integration.md)
- [支援的型號](supported-models.md)
- [變更日誌](CHANGELOG.md)
