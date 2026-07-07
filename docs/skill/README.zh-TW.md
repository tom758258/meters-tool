# Keysight Meters CLI Orchestration Skill

此目錄發佈了適用於 Keysight_Meters_Logger 專案的 Codex skill 範本。此 skill 可協助 Codex 遵循已文件化的 Meters CLI/worker 子程序生命週期、JSON/JSONL 合約、dry-run 與 simulator 驗證順序、`run_id` 關聯規則，以及 live resource 安全限制。

`docs/skill/SKILL.md` 是一個範本。只要它仍位於此文件目錄中，Codex 就不會自動發現或載入它。若要使用，請將其複製到 Codex skill 目錄中，例如 `.agents/skills/keysight-meters-cli-orchestration/` 或 `~/.agents/skills/keysight-meters-cli-orchestration/`。

## 適用範圍

這項 skill 是 Keysight_Meters_Logger 的專案輔助工具。它不是 Keysight driver，不會取代 CLI，也不會自動控制硬體。

當您要求 Codex 修改、審查、測試、除錯或調度涉及以下項目的工作時，請使用此 skill：

- Meters CLI 與 worker 的生命週期行為。
- `start-trigger-record`、`dry-run`、`simulate`、`wait-ready`、`status`、`send-command` 及 `stop`。
- 執行階段的 JSONL 事件與單一回應 JSON client commands。
- 本機控制端點：`POST /command`、`POST /stop` 及 `GET /status`。
- stdout JSONL、`/status`、CSV 與 `report.json` 之間的 `run_id` 關聯性。
- Orchestrator workflows 與 live resource 安全性。

請勿將其用於純 CSS 的 UI 樣式設計、無關的 README 措辭變更，或不影響 CLI/worker 合約介面的常規重構。

## 合約檔案

此 skill 預期能從 upstream repository 或本機的 `references/` snapshot 中取得下列合約檔案：

- `common-worker-protocol.md`
- `common-cli-jsonl-contract.md`
- `common-orchestrator-workflows.md`
- `meters-worker-contract.md`
- `meters-cli-jsonl-contract.md`
- `meters-orchestrator-workflows.md`

當此 skill 在 Keysight_Meters_Logger repository 內使用時，`docs/contracts/` 是 upstream source of truth。當此 skill 為獨立安裝時，請將合約檔案複製到已安裝 skill 的 `references/` 目錄中。

獨立的 `references/` 目錄是合約 snapshot。每當 upstream `docs/contracts/` 變更時，請同步更新該目錄。

## Repository-level installation

當您希望此 skill 僅在 Keysight_Meters_Logger 的特定 checkout 或 fork 內可用時，請使用 repository-level installation。

預期的安裝 layout：

```text
Keysight_Meters_Logger/
  .agents/
    skills/
      keysight-meters-cli-orchestration/
        SKILL.md
        references/
          common-worker-protocol.md
          common-cli-jsonl-contract.md
          common-orchestrator-workflows.md
          meters-worker-contract.md
          meters-cli-jsonl-contract.md
          meters-orchestrator-workflows.md
        scripts/
          run_meter_sim_workflow.mjs
```

從 repository root 執行 PowerShell：

```powershell
$skill = ".agents\skills\keysight-meters-cli-orchestration"
New-Item -ItemType Directory -Force "$skill\references", "$skill\scripts" | Out-Null

Copy-Item "docs\skill\SKILL.md" "$skill\SKILL.md"
Copy-Item "docs\skill\scripts\run_meter_sim_workflow.mjs" "$skill\scripts\"
Copy-Item "docs\contracts\common-worker-protocol.md" "$skill\references\"
Copy-Item "docs\contracts\common-cli-jsonl-contract.md" "$skill\references\"
Copy-Item "docs\contracts\common-orchestrator-workflows.md" "$skill\references\"
Copy-Item "docs\contracts\meters-worker-contract.md" "$skill\references\"
Copy-Item "docs\contracts\meters-cli-jsonl-contract.md" "$skill\references\"
Copy-Item "docs\contracts\meters-orchestrator-workflows.md" "$skill\references\"
```

從 repository root 執行 Bash：

```bash
skill=".agents/skills/keysight-meters-cli-orchestration"
mkdir -p "$skill/references" "$skill/scripts"

cp docs/skill/SKILL.md "$skill/SKILL.md"
cp docs/skill/scripts/run_meter_sim_workflow.mjs "$skill/scripts/"
cp docs/contracts/common-worker-protocol.md "$skill/references/"
cp docs/contracts/common-cli-jsonl-contract.md "$skill/references/"
cp docs/contracts/common-orchestrator-workflows.md "$skill/references/"
cp docs/contracts/meters-worker-contract.md "$skill/references/"
cp docs/contracts/meters-cli-jsonl-contract.md "$skill/references/"
cp docs/contracts/meters-orchestrator-workflows.md "$skill/references/"
```

如果 Codex 在此 repository 內執行並且能讀取 `docs/contracts/`，這些檔案仍是首選的 upstream source of truth。當已安裝的 skill 在原始 repository 環境之外被重複使用或審查時，複製到 `references/` 的檔案就會發揮作用。

## User-level installation

當您希望此 skill 可跨多個 workspace 使用時，請使用 user-level installation。

預期的安裝 layout：

```text
~/.agents/
  skills/
    keysight-meters-cli-orchestration/
      SKILL.md
      references/
        common-worker-protocol.md
        common-cli-jsonl-contract.md
        common-orchestrator-workflows.md
        meters-worker-contract.md
        meters-cli-jsonl-contract.md
        meters-orchestrator-workflows.md
      scripts/
        run_meter_sim_workflow.mjs
```

從 Keysight_Meters_Logger checkout 執行 PowerShell：

```powershell
$skill = Join-Path $HOME ".agents\skills\keysight-meters-cli-orchestration"
New-Item -ItemType Directory -Force (Join-Path $skill "references"), (Join-Path $skill "scripts") | Out-Null

Copy-Item "docs\skill\SKILL.md" (Join-Path $skill "SKILL.md")
Copy-Item "docs\skill\scripts\run_meter_sim_workflow.mjs" (Join-Path $skill "scripts")
Copy-Item "docs\contracts\common-worker-protocol.md" (Join-Path $skill "references")
Copy-Item "docs\contracts\common-cli-jsonl-contract.md" (Join-Path $skill "references")
Copy-Item "docs\contracts\common-orchestrator-workflows.md" (Join-Path $skill "references")
Copy-Item "docs\contracts\meters-worker-contract.md" (Join-Path $skill "references")
Copy-Item "docs\contracts\meters-cli-jsonl-contract.md" (Join-Path $skill "references")
Copy-Item "docs\contracts\meters-orchestrator-workflows.md" (Join-Path $skill "references")
```

從 Keysight_Meters_Logger checkout 執行 Bash：

```bash
skill="$HOME/.agents/skills/keysight-meters-cli-orchestration"
mkdir -p "$skill/references" "$skill/scripts"

cp docs/skill/SKILL.md "$skill/SKILL.md"
cp docs/skill/scripts/run_meter_sim_workflow.mjs "$skill/scripts/"
cp docs/contracts/common-worker-protocol.md "$skill/references/"
cp docs/contracts/common-cli-jsonl-contract.md "$skill/references/"
cp docs/contracts/common-orchestrator-workflows.md "$skill/references/"
cp docs/contracts/meters-worker-contract.md "$skill/references/"
cp docs/contracts/meters-cli-jsonl-contract.md "$skill/references/"
cp docs/contracts/meters-orchestrator-workflows.md "$skill/references/"
```

對於 user-level installation，請保持 `references/` 檔案與 Keysight_Meters_Logger repository 中 upstream `docs/contracts/` 檔案同步。

## Bundled simulator helper

此 skill 也提供 `scripts/run_meter_sim_workflow.mjs`，可在有 Node.js 的環境中進行 no-hardware simulator smoke validation。此 helper 會執行一次 dry-run，並另外啟動一次 simulator `start-trigger-record` software-trigger workflow，接著輸出 machine-readable artifacts；若 evidence contract 不符合，會以非零結束碼失敗。請勿將此 helper 用於 live resources；把 `--resource` 改成 `USB0::...` 這類 live VISA address，並不會讓它成為 live validation path。

以下範例適用於包含 `keysight-logger*.exe` executable 的 workspace：

```powershell
node .agents\skills\keysight-meters-cli-orchestration\scripts\run_meter_sim_workflow.mjs `
  --exe .\keysight-logger-<version>.exe `
  --out .tmp_tests\meter_sim_software_trigger `
  --resource SIM::34461A `
  --measurement current-dc `
  --max-samples 1 `
  --port 18765
```

helper 會在指定輸出目錄中寫入 `dry_run.jsonl`、`sim_worker_stdout.jsonl`、`sim_worker_stderr.txt`、`sim_samples.csv` 與 `sim_report.json`。成功執行需要 dry-run 安全欄位、必要時透過 `wait-ready --json` 確認 control-plane readiness、一次 accepted software trigger、JSONL/client responses/artifacts 之間的 `run_id` 相符、一筆 CSV row、`summary.ok: true`、符合預期的 captured count、零 errors，以及 worker exit code `0`。

## 使用範例

請參考 [EXAMPLES.md](EXAMPLES.md)，其中提供可直接複製的 prompts，示範如何要求 Codex 驗證 simulator workflow、準備安全的 live workflow，以及根據 Meters CLI/worker contracts 審查 orchestrator change。

當任務涉及合約敏感內容時，請明確呼叫此 skill：

```text
Use $keysight-meters-cli-orchestration to review this change against the Meters JSONL contract.
```

```text
Use $keysight-meters-cli-orchestration to plan simulator validation for start-trigger-record.
```

```text
Use $keysight-meters-cli-orchestration to check whether this orchestrator workflow respects run_id correlation and live resource safety.
```

## 安全注意事項

- 在實際操作硬體之前，優先使用 dry-run 與 simulator 進行驗證。
- Live mode 需要使用者明確選定 `--resource`。
- 在 acquisition workflow 中，請勿掃描、猜測、輪換、暴力破解或暗中替換 live VISA resources。
- 請將 `ready` 與 `wait-ready` 僅視為 control-plane readiness，而非 measurement completion。
- 請使用結構化的 JSON/JSONL、CSV、`report.json` 及 exit codes 來進行 machine decisions。Human-readable text 僅供診斷使用。
