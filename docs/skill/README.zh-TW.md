# Meters Tool CLI 調度 Skill (Orchestration Skill)

此目錄發佈了適用於 Meters Tool 專案的 Codex Skill 範本。此 Skill 可協助 Codex 遵循已文件化的 Meters CLI / worker 子程序生命週期、JSON/JSONL 合約、試執行 (dry-run) 與模擬器驗證順序、`run_id` 關聯規則，以及實機 VISA 資源安全限制。

`docs/skill/SKILL.md` 是一個範本。只要它仍位於此文件目錄中，Codex 就不會自動發現或載入它。若要使用，請將其複製到 Codex Skill 目錄中，例如 `.agents/skills/meters-tool-cli-orchestration/` 或 `~/.agents/skills/meters-tool-cli-orchestration/`。

## 適用範圍 (Scope)

這項 Skill 是 Meters Tool 的專案輔助工具。它不是儀器驅動程式，不會取代 CLI，也不會自動控制硬體。

當您要求 Codex 修改、審查、測試、除錯或調度涉及以下項目的工作時，請使用此 Skill：

- Meters CLI 與 worker 的生命週期行為。
- `start-trigger-record`、`dry-run`、`simulate`、`wait-ready`、`status`、`send-command` 及 `stop`。
- 執行階段的 JSONL 事件與單一回應 JSON 的客戶端命令。
- 本機控制端點 (local control endpoints)：`POST /command`、`POST /stop` 及 `GET /status`。
- 標準輸出 (stdout) JSONL、`/status`、CSV 與 `report.json` 之間的 `run_id` 關聯性。
- 調度器 (orchestrator) 工作流程與實機資源安全性。

請勿將其用於純 CSS 的 UI 樣式設計、無關的 README 措辭變更，或不影響 CLI/worker 合約介面的常規重構。

## 合約檔案 (Contract files)

此 Skill 預期能從上游儲存庫或本機的 `references/` 快照中取得下列合約檔案：

- `common-worker-protocol.md`
- `common-cli-jsonl-contract.md`
- `common-orchestrator-workflows.md`
- `meters-worker-contract.md`
- `meters-cli-jsonl-contract.md`
- `meters-orchestrator-workflows.md`

當此 Skill 在 Meters Tool 儲存庫內使用時，`docs/contracts/` 是上游的 source of truth。當此 Skill 為獨立安裝時，請將合約檔案複製到已安裝 Skill 的 `references/` 目錄中。

獨立的 `references/` 目錄是合約快照。每當上游的 `docs/contracts/` 發生變更時，請同步更新該目錄。

## 儲存庫層級安裝 (Repo-level installation)

當您希望此 Skill 僅在 Meters Tool 的特定 checkout 或 fork 內可用時，請使用儲存庫層級安裝。

預期的安裝目錄結構：

```text
meters-tool/
  .agents/
    skills/
      meters-tool-cli-orchestration/
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

從儲存庫根目錄執行 PowerShell：

```powershell
$skill = ".agents\skills\meters-tool-cli-orchestration"
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

從儲存庫根目錄執行 Bash：

```bash
skill=".agents/skills/meters-tool-cli-orchestration"
mkdir -p "$skill/references" "$skill/scripts"

cp docs/skill/SKILL.md "$skill/SKILL.md"
cp docs/skill/scripts/run_meter_sim_workflow.mjs "$skill/scripts/"
cp docs/contracts/common-worker-protocol.md "$skill/references/"
cp docs/contracts/common-cli-jsonl-contract.md "$skill/references/"
cp docs/contracts/common-orchestrator-workflows.md "$skill/references/"
cp docs/contracts/meters-worker-contract.md "$skill/references/"
cp docs/contracts/meters-cli-jsonl-contract.md "$skill/references/"
cp docs/contracts/common-orchestrator-workflows.md "$skill/references/"
cp docs/contracts/meters-orchestrator-workflows.md "$skill/references/"
```

如果 Codex 在此儲存庫內執行並且能夠讀取 `docs/contracts/`，這些檔案仍是首選的上游 source of truth。當已安裝的 Skill 在原始儲存庫環境之外被重複使用或審查時，複製到 `references/` 的檔案就會發揮作用。

## 使用者層級安裝 (User-level installation)

當您希望此 Skill 可跨多個工作區使用時，請使用使用者層級安裝。

預期的安裝目錄結構：

```text
~/.agents/
  skills/
    meters-tool-cli-orchestration/
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

從 Meters Tool checkout 目錄執行 PowerShell：

```powershell
$skill = Join-Path $HOME ".agents\skills\meters-tool-cli-orchestration"
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

從 Meters Tool checkout 目錄執行 Bash：

```bash
skill="$HOME/.agents/skills/meters-tool-cli-orchestration"
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

對於使用者層級安裝，請保持 `references/` 檔案與 Meters Tool 儲存庫中上游的 `docs/contracts/` 檔案同步。

## 內建模擬器 helper (Bundled simulator helper)

此 Skill 也提供 `scripts/run_meter_sim_workflow.mjs`，可在有 Node.js 的環境中進行不需硬體的模擬器快速檢查。此 helper 會執行一次 dry-run，並另外啟動一次模擬器 `start-trigger-record` 軟體觸發流程，接著輸出可由機器判讀的 artifacts；若證據不符合合約，會以非零結束代碼失敗。請勿將此 helper 用於 live resources；把 `--resource` 改成 `USB0::...` 這類 live VISA address，並不會讓它成為 live validation path。

以下範例適用於包含 `meters-tool*.exe` 執行檔的工作區：

```powershell
node .agents\skills\meters-tool-cli-orchestration\scripts\run_meter_sim_workflow.mjs `
  --exe .\meters-tool-<version>.exe `
  --out .tmp_tests\meter_sim_software_trigger `
  --resource SIM::34461A `
  --measurement current-dc `
  --max-samples 1 `
  --port 18765
```

helper 會在指定輸出目錄中寫入 `dry_run.jsonl`、`sim_worker_stdout.jsonl`、`sim_worker_stderr.txt`、`sim_samples.csv` 與 `sim_report.json`。成功執行需要 dry-run 安全欄位、必要時透過 `wait-ready --json` 確認控制平面就緒、一次 accepted software trigger、JSONL/client responses/artifacts 之間的 `run_id` 相符、一筆 CSV row、`summary.ok: true`、符合預期的 captured count、零 errors，以及 worker exit code `0`。

## 使用範例 (Usage examples)

請參考 [EXAMPLES.md](EXAMPLES.md)（或適用時為 [EXAMPLES.zh-TW.md](EXAMPLES.zh-TW.md)），其中提供可直接複製的 prompt，示範如何要求 Codex 驗證模擬器工作流程、準備安全的 live 工作流程，以及根據 Meters CLI/worker 合約審查 orchestrator 變更。

當任務涉及合約敏感內容時，請明確呼叫此 Skill：

```text
使用 $meters-tool-cli-orchestration 對照 Meters JSONL 合約來審查此變更。
```

```text
使用 $meters-tool-cli-orchestration 為 start-trigger-record 規劃模擬器驗證。
```

```text
使用 $meters-tool-cli-orchestration 檢查此調度器工作流程是否遵守 run_id 關聯性與實機資源安全性。
```

## 安全注意事項 (Safety notes)

- 在實際操作硬體之前，優先使用試執行 (dry-run) 與模擬器 (simulator) 進行驗證。
- 實機模式 (live mode) 需要使用者明確選定 `--resource`。
- 在擷取工作流程中，請勿掃描、猜測、輪換、暴力破解或暗中替換實機 VISA 資源。
- 請將 `ready` 與 `wait-ready` 僅視為控制平面 (control plane) 的就緒狀態，而非量測完成。
- 請使用結構化的 JSON/JSONL、CSV、`report.json` 及結束代碼 (exit codes) 來進行機器決策。人類可讀的文字僅供診斷使用。
