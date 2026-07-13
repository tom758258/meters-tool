[English](README.md)

# Meters Tool

Meters Tool 是供支援的數位萬用電表使用的 Python 資料擷取與紀錄工具。目前版本支援 Keysight 34460A 與 34461A；確切的驗證範圍請參閱 [支援型號文件](docs/core/supported-models.md)。專案提供單一可安裝發行套件 `meters-tool`，其套件版本由根目錄 `pyproject.toml` 定義，同時保留三個獨立的 import package：`meters_tool_core`、`meters_tool_cli` 與 `meters_tool_webui`。

本專案支援透過 VISA 進行 DC 與 AC 電流、DC 與 AC 電壓、DC 電壓比、頻率、週期，以及 2 線式或 4 線式電阻量測。每筆擷取的樣本都會寫入 CSV 的一行，包含時間戳記、量測類型、單位、觸發來源與相關 metadata。

## 功能特性

* 透過 VISA 控制支援的數位萬用電表
* 設定量測範圍 (range)、NPLC、Auto Zero、AC 頻寬 (bandwidth)、電流端子 (current terminal) 與 DC 電壓輸入阻抗 (input impedance)
* 支援 software、timer、external hardware、immediate 與 buffered 觸發工作流程
* 使用 dry-run 模式預覽儀器命令
* 使用內建模擬器在沒有硬體的情況下測試工作流程
* 透過 CLI 或本機 WebUI 進行操作
* 產生 JSON 與 JSONL 輸出，供自動化、agent 與 orchestrator 使用

實機啟動時會透過 `*IDN?` 自動偵測已連接的型號；明確選擇的型號僅作為預期型號防護 (expected-model guard)，並不會為另一台儀器解鎖功能。精確的實機支援採用 fail-closed (預設關閉) 原則；關於型號、傳輸/後端、量測與觸發模式的狀態，請參閱 [支援型號](docs/core/supported-models.md) 與各元件說明文件。

## 專案結構

此 repository 現在使用單一發行套件與單一版本號。在範例中，`<version>` 代表根目錄 `pyproject.toml` 中的 `[project].version`：

* 發行套件 (Distribution)：`meters-tool` `<version>`
* Core import：`meters_tool_core`
* CLI import：`meters_tool_cli`
* WebUI import：`meters_tool_webui`

import 路徑彼此獨立。請不要使用 `meters_tool.*` namespace package。

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

如果尚未安裝 uv，請先安裝：

```powershell
py -m pip install --user uv
```

驗證 uv：

```powershell
uv --version
```

在專案資料夾中建立虛擬環境：

```powershell
uv venv .venv
```

依照 `uv.lock` 同步可重現的開發與測試環境：

```powershell
uv sync --all-extras --link-mode=copy
```

針對 CI 或嚴格的本機檢查，可要求已提交的 lock 檔案保持不變：

```powershell
uv sync --all-extras --locked --link-mode=copy
```

本專案支援 Python `>=3.10`。`uv venv .venv` 會使用可用的相容 Python。如果您需要特定的 Python 版本，請明確指定：

```powershell
uv venv .venv --python 3.12
```

`uv.lock` 檔案用於 uv 的開發與 CI 可重現環境。`pip install .` 讀取的是 `pyproject.toml`，不會讀取 `uv.lock`。未使用 uv 的使用者若要使用鎖定環境，必須先安裝 uv。

如果需要直接使用 pip，請使用虛擬環境中的 Python：

```powershell
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe -m pip install ".[webui]"
.\.venv\Scripts\python.exe -m pip install -e ".[all,dev]"
```

Windows 會建立 virtualenv console wrappers，例如
`.\.venv\Scripts\meters-tool.exe`、
`.\.venv\Scripts\meters-tool-webui.exe` 與
`.\.venv\Scripts\meters-tool-webui-launcher.exe`。

## 建置

準備發布時，請在建置發布產物之前先執行無硬體發布門檻檢查：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\release-cli-check.ps1 -Target keysight-34461a
```

預設 target 為 `keysight-34461a`。只有在發布變更明確與 34460A 型號相關時，才改用 `keysight-34460a`。此包裝器負責驗證發布就緒狀態，但不會建置發布產物。

建置 wheel 與 source distribution。這會使用上面安裝的 `dev` extra 中的 `build` 套件：

```powershell
.\.venv\Scripts\python.exe -m build
```

這只會產生一個 Python 發行套件：

```text
dist\meters_tool-<version>-py3-none-any.whl
dist\meters_tool-<version>.tar.gz
```

獨立執行檔有分開的 PyInstaller 工作流程。在建置 exe 產物之前，請先安裝 PyInstaller：

```powershell
uv pip install pyinstaller --python .\.venv\Scripts\python.exe
```

如果您的虛擬環境直接使用 pip：

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
```

建置獨立的 CLI 和 WebUI 啟動器執行檔：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_cli_exe.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_webui_exe.ps1
```

預設情況下，這些命令會產生：

```text
dist\meters-tool.exe
dist\meters-tool-webui-launcher.exe
```

建置包含 wheel、sdist、獨立執行檔與檢查碼 (checksums) 的發佈資料夾：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_release.ps1
```

這會產生帶有版本號的發佈產物：

```text
release\<version>\meters-tool-<version>.exe
release\<version>\meters-tool-webui-launcher-<version>.exe
release\<version>\meters_tool-<version>-py3-none-any.whl
release\<version>\meters_tool-<version>.tar.gz
release\<version>\checksums.txt
```

## 測試

開發迭代時可先跑 focused tests：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\core -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\cli -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests\webui -q -p no:cacheprovider
```

執行靜態檢查：

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests
```

執行完整無硬體測試套件：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

如果 Windows 系統暫存目錄權限阻擋了 pytest，請改用 repository-local 暫存目錄重新執行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --basetemp .tmp_tests\pytest_tmp
```

## Codex / Agent Skill

本專案提供選用的 Codex Skill 範本，供想要要求 Codex 或其他 agents
安全遵循 Meters CLI/worker 合約的使用者使用。安裝與使用方式請參考
[Codex Skill 範本](docs/skill/README.zh-TW.md)。

## 文件

* [Core README](docs/core/README.zh-TW.md)
* [支援型號](docs/core/supported-models.md)
* [CLI 使用者指南](docs/cli/USER_GUIDE.zh-TW.md)
* [CLI README](docs/cli/README.zh-TW.md)
* [WebUI README](docs/webui/README.zh-TW.md)
* [WebUI 使用者指南](docs/webui/USER_GUIDE.zh-TW.md)
* [Monorepo 架構](docs/architecture/monorepo-layout.md)
* [測試指南](docs/testing-guidelines.md)
* [貢獻指南](docs/CONTRIBUTING.md)
* [Codex Skill 範本](docs/skill/README.zh-TW.md)
* [公開合約](docs/contracts)
* [Meters CLI JSONL 合約](docs/contracts/meters-cli-jsonl-contract.md)
* [Meters Worker 合約](docs/contracts/meters-worker-contract.md)

## 貢獻

歡迎提交貢獻。在提交 pull request 之前，請閱讀 [貢獻指南](docs/CONTRIBUTING.md)。對儀器支援或實機行為的變更，在適用時需要提供實體儀器驗證證據。

## 授權條款與免責聲明

本專案採用 MIT License。詳見 [LICENSE](LICENSE)。

本專案是獨立且非官方的專案，未與 Keysight Technologies 建立從屬、背書或贊助關係。

使用者需自行遵守所有適用的 Keysight 軟體、driver、儀器與文件授權條款。
