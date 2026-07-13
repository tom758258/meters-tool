[English](README.md)

# Meters Tool

Meters Tool 是一個為支援的數位萬用電表所設計的 Python 資料擷取與記錄工具包。目前版本支援 Keysight 34460A 與 34461A；有關確切的驗證範圍，請參閱 [支援的模型](docs/core/supported-models.md)。它提供可安裝的 `meters-tool` 發行套件，其套件版本由根目錄的 `pyproject.toml` 定義，同時保留了三個獨立的匯入套件：`meters_tool_core`、`meters_tool_cli` 與 `meters_tool_webui`。

本專案支援透過 VISA 進行 DC 與 AC 電流、DC 與 AC 電壓、DC 電壓比例（DCV Ratio）、頻率、週期，以及 2 線或 4 線電阻測量。每個擷取樣本都會寫成一筆 CSV 資料列，其中包含時間戳記、測量類型、單位、觸發源以及相關的中繼資料。

## 功能特點

* 透過 VISA 控制支援的數位萬用電表
* 設定測量量程、NPLC、自動歸零（Auto Zero）、AC 頻寬、電流端子以及 DC 電壓輸入阻抗
* 支援軟體、計時器、外部硬體、立即與緩衝觸發工作流程
* 使用預演（乾跑）模式預覽儀器命令
* 使用內建模擬器在無硬體的情況下測試工作流程
* 透過 CLI 或本機 WebUI 進行操作
* 為自動化、代理人（Agent）及協調器提供 JSON 與 JSONL 格式輸出

實體啟動會在省略 `--model` 時，透過 `*IDN?` 自動偵測連線的模型；明確選擇的模型僅作為預期模型防護（expected-model guard），並不會解鎖另一個儀器的功能。確切的實體支援採用「失敗即關閉」（fail-closed）策略；有關模型、傳輸/後端、測量以及觸發模式的狀態，請參閱 [支援的模型](docs/core/supported-models.md) 以及各元件之說明文件。

## 專案結構

正要從 pre-v2 的 `keysight-logger` 命名升級嗎？請參閱 [遷移至 Meters Tool v2](docs/migration-v2.md)。

本儲存庫現在僅有一個發行套件與一個版本號。在範例中，`<version>` 代表根目錄 `pyproject.toml` 中的 `[project].version`：

* 發行套件：`meters-tool` `<version>`
* Core 匯入路徑：`meters_tool_core`
* CLI 匯入路徑：`meters_tool_cli`
* WebUI 匯入路徑：`meters_tool_webui`

匯入路徑保持獨立。請勿使用 `meters_tool.*` 命名空間套件。

```text
src/
  meters_tool_core/
  meters_tool_cli/
  meters_tool_webui/
tests/
  core/
  cli/
  webui/
docs/
  core/
  cli/
  webui/
scripts/
```

## 安裝

首先開啟 PowerShell 並進入專案根目錄：

```powershell
cd path\to\meters-tool
```

如果尚未安裝 uv，請先安裝 uv：

```powershell
py -m pip install --user uv
```

驗證 uv：

```powershell
uv --version
```

在專案資料夾中建立專案虛擬環境：

```powershell
uv venv .venv
```

從 `uv.lock` 同步可重現的開發與測試環境：

```powershell
uv sync --all-extras --link-mode=copy
```

在 CI 或嚴格的本機檢查中，要求已鎖定的 `uv.lock` 保持不變：

```powershell
uv sync --all-extras --locked --link-mode=copy
```

本專案支援 Python `>=3.10`。`uv venv .venv` 會自動使用可用的相容 Python 版本。如果您需要特定的 Python 版本，請明確指定：

```powershell
uv venv .venv --python 3.12
```

`uv.lock` 由 uv 用來確保開發與 CI 環境可重現。`pip install .` 讀取的是 `pyproject.toml` 而非 `uv.lock`。未使用 uv 的使用者在安裝鎖定環境前必須先安裝 uv。

如果您需要直接使用 pip，請使用虛擬環境的 Python 執行檔：

```powershell
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe -m pip install ".[webui]"
.\.venv\Scripts\python.exe -m pip install -e ".[all,dev]"
```

Windows 會建立虛擬環境主控台包裝器，例如：
`.\.venv\Scripts\meters-tool.exe`、
`.\.venv\Scripts\meters-tool-webui.exe` 與
`.\.venv\Scripts\meters-tool-webui-launcher.exe`。

## 建置

建置 wheel 與來源發行套件（sdist）。這會使用上面安裝的 `dev` 額外相依性中的 `build` 套件：

```powershell
.\.venv\Scripts\python.exe -m build
```

這只會產生一組 Python 發行套件：

```text
dist\meters_tool-<version>-py3-none-any.whl
dist\meters_tool-<version>.tar.gz
```

獨立執行檔採用另一套 PyInstaller 工作流程。在建置 exe 成品之前，請先安裝 PyInstaller：

```powershell
uv pip install pyinstaller --python .\.venv\Scripts\python.exe
```

如果您的虛擬環境直接使用 pip：

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
```

建置獨立的 CLI 與 WebUI 啟動器執行檔：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_cli_exe.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_webui_exe.ps1
```

預設情況下，這些命令會產生：

```text
dist\meters-tool.exe
dist\meters-tool-webui-launcher.exe
```

建置包含 wheel、sdist、獨立執行檔與校驗碼（checksums）的發行套件資料夾：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_release.ps1
```

這會產生帶有版本號的發行成品：

```text
release\<version>\meters-tool-<version>.exe
release\<version>\meters-tool-webui-launcher-<version>.exe
release\<version>\meters_tool-<version>-py3-none-any.whl
release\<version>\meters_tool-<version>.tar.gz
release\<version>\checksums.txt
```

## 測試

開發期間可先執行針對性的測試：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\core -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\cli -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\webui -q -p no:cacheprovider
```

執行靜態檢查：

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests
```

執行完整的無硬體測試套件：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

如果 Windows 暫存目錄權限阻擋了 pytest，請使用儲存庫本地的暫存目錄重新執行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --basetemp .tmp_tests\pytest_tmp
```

## Codex / 代理人技能（Agent Skill）

本專案為希望要求 Codex 或其他代理人安全地遵循 Meters CLI/worker 合約的使用者提供選用的 Codex 技能範本。請參閱 [Codex 技能範本](docs/skill/README.md) 以取得安裝與使用指南。

## 說明文件

* [Core README](docs/core/README.zh-TW.md)
* [支援的模型](docs/core/supported-models.md)
* [CLI 使用指南](docs/cli/USER_GUIDE.zh-TW.md)
* [CLI README](docs/cli/README.zh-TW.md)
* [WebUI README](docs/webui/README.zh-TW.md)
* [WebUI 使用指南](docs/webui/USER_GUIDE.zh-TW.md)
* [Monorepo 架構](docs/architecture/monorepo-layout.md)
* [測試指南](docs/testing-guidelines.md)
* [貢獻指南](docs/CONTRIBUTING.md)
* [Codex 技能範本](docs/skill/README.md)
* [公開合約](docs/contracts)
* [Meters CLI JSONL 合約](docs/contracts/meters-cli-jsonl-contract.md)
* [Meters Worker 合約](docs/contracts/meters-worker-contract.md)

## 貢獻

歡迎任何貢獻。在開啟 Pull Request 之前，請先閱讀 [貢獻指南](docs/CONTRIBUTING.md)。對儀器支援或實體行為的變更在適用時需要提供實體儀器的驗證證據。

## 授權與免責聲明

本專案採用 MIT 授權條款。請參閱 [LICENSE](LICENSE)。

本專案為獨立且非官方專案。它與 Keysight Technologies 沒有任何關聯、背書或贊助關係。

使用者有責任遵守所有適用的 Keysight 軟體、驅動程式、儀器與說明文件的授權條款。
