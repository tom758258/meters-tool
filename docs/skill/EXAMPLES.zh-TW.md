# Keysight Meters CLI Orchestration Skill 範例

此文件提供可直接複製的 prompt 範例，用於
`keysight-meters-cli-orchestration` Codex Skill。這些範例示範如何要求 agent 遵循 Meters CLI/worker 合約，而不是猜測資源或把人類可讀文字當成機器合約。

這些範例假設您已經將 `docs/skill/SKILL.md` 安裝到 Codex Skill 目錄，且相關合約檔案可從 `docs/contracts/` 或已安裝 Skill 的 `references/` 目錄取得。

## 如何選擇範例

此文件包含三種 prompt：

- **引導型範例 (Guided examples)**：適合規劃、審查與理解流程。當您希望 agent 說明 workflow、提出合理假設，並在採取動作前詢問必要釐清問題時，請使用這類範例。
- **執行型範例 (Direct-run examples)**：適合使用安全預設值進行無硬體驗證或立即審查。當您希望 agent 讀取 Skill 與合約、從 repository 確認實際 CLI 旗標拼法，並在環境缺失、CLI 無法使用、合約與 CLI help 不一致，或動作可能碰到實機硬體之外的情況下不要一直詢問確認時，請使用這類範例。
- **明確授權的實機執行範例 (Explicit live execution examples)**：可能會碰到真實儀器。只有在您提供精確 VISA resource，並明確授權該 resource 可進行 live execution 時，才使用這類範例。

如果您還在決定要量測什麼，或想先理解 workflow 的嚴謹程度，請使用引導型範例。如果您想測試 agent 是否能遵循合約，並用較少來回執行安全的無硬體路徑，請使用執行型範例。只有當您已準備好讓 agent 在 dry-run 與 simulator validation 後操作真實儀器時，才使用明確授權的實機執行範例。

## 執行範例前 (Before running executable examples)

對於會執行或準備 `start-trigger-record` 的範例，在選擇 CLI 旗標、resource 字串或 process-launch 行為前，請先讀取 orchestrator workflow contracts。請將 `common-orchestrator-workflows.md` 與 `meters-orchestrator-workflows.md` 視為 measurement names、trigger mode 拼法、simulator resource strings、JSONL mode、software-trigger sequencing 與 subprocess orchestration 的 source of truth。

對於 software-trigger workflows，不要把 worker 當成 blocking foreground command 執行後等待它自己結束，再送 trigger。應將它作為可觀測的 subprocess 啟動，stream stdout JSONL 直到 `ready`，再透過文件化的 client 或 endpoint 送出剛好一個 `software_trigger` command，接著繼續讀取 JSONL 直到 `summary`，最後檢查 CSV、適用時的 `report.json`、`run_id` 與 exit code。

優先使用 Python `subprocess.Popen` 或 repository 已文件化的 orchestrator pattern。不要使用 PowerShell `Start-Process` 或 `cmd /c start /B` 這類 detached shell launch，除非 repository 明確文件化這種 pattern，因為 detached launch 可能隱藏 stdout JSONL、exit code、cleanup state 與 `run_id` correlation。

不要自行發明 CLI flags、measurement values、simulator resource aliases 或 worker launch patterns。CLI help 僅用於確認合約未涵蓋的行為，或診斷 installed CLI 與 documented contract 之間的不一致。

## 引導型範例 (Guided examples)

### 引導型範例 1：模擬器 software-trigger 工作流程

#### 目標

在沒有實機硬體的情況下驗證 Meters CLI 調度流程。這個範例會要求 Codex 先使用已文件化的無硬體路徑，再執行有明確結束條件的模擬器工作流程，捕捉剛好一筆 software-triggered sample。

#### 使用者 prompt

```text
Use $keysight-meters-cli-orchestration.

I want to validate the Meters CLI orchestration flow without hardware.
Plan and run a simulator software-trigger workflow that captures exactly one
sample. Use dry-run first, then simulate with a finite bound. Wait for ready,
send one software trigger, verify run_id correlation, and report which JSONL
events and artifacts should be checked.

Before choosing CLI flags or launch behavior, read the common and Meters
orchestrator workflow contracts. Use their documented subprocess orchestration
pattern for the software-trigger worker instead of detached shell launch.
```

#### 預期 agent 行為

Codex 應該：

- 在規劃工作流程前，先讀取 Skill 與相關 Meters 合約，包含 common 與 Meters orchestrator workflow contracts。
- 避免實機硬體，並避免 VISA 資源探索。
- 使用文件化的 CLI 拼法與 simulator resource strings，而不是自行發明 flags 或 aliases。
- 先以 `start-trigger-record --dry-run --status-format jsonl` 建立計畫。
- 使用模擬器模式，例如 `--resource SIM::34461A --simulate`。
- 使用明確結束條件，例如 `--max-samples 1`，讓工作流程可以結束。
- 對於 software-trigger simulate runs，將 worker 作為可觀測的 subprocess 啟動，stream stdout JSONL 直到 `ready`，然後才送 trigger。
- 在送出命令前，等待 `ready` JSONL event，或使用 `wait-ready --json`。
- 透過 `send-command --json` 或 `POST /command` 送出一個 `software_trigger` 命令。
- 避免使用 PowerShell `Start-Process` 或 `cmd /c start /B` 這類 detached shell launch，除非 repository 明確文件化。
- 驗證 stdout JSONL、status response 與產生 artifacts 之間的 `run_id` 一致。
- 將 `summary.ok: true`、預期 captured count、零 errors，以及 process exit code 為零視為成功完成訊號。
- 在適用時提到 CSV 與 `report.json` 或 wrapper artifacts。

#### 預期結果

agent 應該產生或描述一個無硬體驗證流程。最後回答應清楚說明檢查了哪些結構化輸出，且不應只根據人類可讀文字宣稱成功。

這個範例可證明 Skill 能引導 Codex 走過安全的合約路徑：dry-run、simulator、readiness、command、status、summary 與 artifact checks。

### 引導型範例 2：使用 explicit resource 規劃 live 工作流程

#### 目標

在不讓 agent 猜測或掃描實機 VISA 資源的情況下，準備安全的 live measurement 工作流程。這個範例要求 Codex 規劃 live path，但在使用者提供明確 `--resource` 前，不執行任何 live command。

#### 使用者 prompt

```text
Use $keysight-meters-cli-orchestration.

Prepare a live one-sample voltage_dc measurement workflow for my Keysight
34461A. Do not guess, scan, rotate, or substitute VISA resources. Ask me to
provide the explicit --resource before any live command. Use dry-run and
simulator validation first, then show the exact live command that would be run
after I confirm the resource.

Before choosing CLI flags or launch behavior, read the common and Meters
orchestrator workflow contracts. Use their documented subprocess orchestration
pattern for any software-trigger worker instead of detached shell launch.
```

#### 預期 agent 行為

Codex 應該：

- 在規劃 live 工作前，先讀取 Skill 與相關 Meters 合約，包含 common 與 Meters orchestrator workflow contracts。
- 拒絕在 acquisition workflow 內猜測、掃描、輪換或替換實機 VISA 資源。
- 使用文件化的 CLI 拼法與 resource strings，而不是自行發明 flags、SCPI-form measurement values 或 simulator aliases。
- 如果使用者尚未提供，要求使用者提供明確的 `--resource`。
- 在任何 live command 前，先規劃 dry-run 與 simulator validation。
- 對於 software-trigger validation，使用 repository 已文件化的 subprocess orchestration，而不是 detached shell launch。
- 將 `ready` 與 `wait-ready` 視為 control-plane readiness，而不是 measurement completion。
- 僅在使用者確認且明確 resource 可用後，才把 live command 作為可執行命令展示。
- 說明 live run 後應檢查的結構化輸出：JSONL events、`run_id`、status responses、CSV、`report.json`、final summary 與 process exit code。

#### 預期結果

agent 應該產生安全的 live-workflow plan，且除非使用者提供明確 resource 並要求 live execution，否則不應啟動實機硬體操作。

這個範例可證明 Skill 會保留 live resource safety boundary，同時仍協助使用者準備實用的 live measurement workflow。

### 引導型範例 3：以合約為基準審查 orchestrator 變更

#### 目標

在不執行硬體的情況下，審查 orchestrator 或 wrapper 變更是否符合合約。

#### 使用者 prompt

```text
Use $keysight-meters-cli-orchestration.

Review this orchestrator change against the Meters CLI/worker contracts. Focus
on JSONL parsing, ready/status handling, POST /command behavior, cooperative
stop, run_id correlation, final summary handling, exit codes, and whether the
change avoids guessing live VISA resources.
```

#### 預期 agent 行為

Codex 應該：

- 讀取相關 common 與 Meters-specific contracts。
- 檢查機器決策是否使用 JSON/JSONL、structured artifacts 與 exit codes，而不是人類可讀文字。
- 檢查 `GET /status` 是否被視為 non-mutating。
- 檢查 `POST /command` 是否只在 readiness 之後使用。
- 檢查 cleanup 是否使用 `POST /stop` 或已文件化的 CLI stop client。
- 檢查 missing `ready`、malformed JSON、non-zero exit、missing summary、`summary.ok: false` 與 `fatal_error` 是否被視為 failed 或 incomplete。
- 標記 live acquisition workflow 中任何 resource scanning、guessing、rotation 或 silent substitution。

#### 預期結果

agent 應該回傳以合約為核心的 review，包含具體 findings，並說明每個問題影響哪個 contract boundary，以及此變更對 no-hardware validation、simulator validation 或 live execution 是否安全。

## 執行型範例 (Direct-run examples)

### 執行型範例 1：無硬體 simulator software-trigger 驗證

#### 目標

使用固定預設值執行安全的無硬體驗證流程。這個 prompt 適合用來降低來回詢問，測試 agent 是否能遵循合約並執行 dry-run 加 simulator 路徑。

#### 使用者 prompt

```text
Use $keysight-meters-cli-orchestration.

Run the no-hardware simulator software-trigger validation workflow now.

Use these defaults unless the repository contracts or CLI help require a
different spelling:

- measurement type: current-dc
- simulator resource: SIM::34461A
- trigger mode: software
- finite sample bound: exactly one sample
- output directory: .tmp_tests/skill_examples/simulator_software_trigger/
- worker observation output: JSONL
- client command output: JSON
- software-trigger port: choose an unused localhost port, or use 8765 if it is
  available

Steps:

1. Read the skill and the relevant common and Meters-specific contracts,
   including common-orchestrator-workflows.md and
   meters-orchestrator-workflows.md.
2. Confirm the exact CLI flag spelling from the contracts before using CLI help.
3. Run dry-run first.
4. Run simulator mode with a finite bound using the documented software-trigger
   subprocess orchestration pattern.
5. Start the worker as an observable subprocess, stream stdout JSONL until the
   ready event, and do not use detached shell launch such as PowerShell
   Start-Process or cmd /c start /B unless the repository documents it.
6. Wait for the ready JSONL event or use wait-ready --json.
7. Send exactly one software_trigger command after readiness.
8. Check run_id correlation across stdout JSONL, status response, CSV, and
   report.json if present.
9. Continue reading worker JSONL until summary, then report the JSONL events,
   artifacts, exit codes, summary.ok, captured count, errors, and any contract
   mismatch.

Do not ask for a live VISA resource. Do not ask for confirmation before running
dry-run or simulator commands. Do not invent CLI flags, measurement values,
simulator resource aliases, or worker launch patterns. Only stop to ask me a
question if the CLI cannot be invoked, dependencies are missing, the contracts
and CLI help disagree, the current-dc measurement cannot be expressed safely, or
the command would touch live hardware.
```

#### 預期 agent 行為

Codex 應該：

- 直接進行 dry-run 與 simulator validation，而不是詢問是否要執行。
- 使用固定的無硬體預設值，除非 repository 內容與其矛盾。
- 在做出合約敏感決策前先讀取合約，包含在選擇 flags 或 launch behavior 前讀取 orchestrator workflow contracts。
- 從 repository 確認真正的 CLI 拼法，而不是自行發明旗標。
- 對於 software-trigger runs，使用 repository 已文件化的 subprocess orchestration，而不是 detached shell launch。
- 因為 workflow 已明確指定無硬體，所以避免詢問 live VISA resource。
- 只有在環境、dependency、contract、CLI 或 live-hardware safety 出現阻礙時才停下詢問。

#### 預期結果

agent 應該執行或嘗試執行 dry-run 與 simulator validation 路徑，並產生結構化報告。如果無法執行，應說明精確 blocker，而不是詢問可自行預設的偏好。

### 執行型範例 2：安全準備 live 工作流程但不執行

#### 目標

使用安全預設值準備 live workflow，但不執行 live hardware commands。這個 prompt 適合在仍要保留 explicit-resource safety boundary 的前提下，要求 agent 準備 live path。

#### 使用者 prompt

```text
Use $keysight-meters-cli-orchestration.

Prepare the safe live one-sample measurement workflow now, but do not execute
any live hardware command.

Use these defaults for no-hardware validation before preparing the live command:

- measurement type: voltage-dc
- simulator resource: SIM::34461A
- trigger mode: software
- finite sample bound: exactly one sample
- output directory: .tmp_tests/skill_examples/live_preparation/
- worker observation output: JSONL
- client command output: JSON

For any dry-run or simulator command, read common-orchestrator-workflows.md and
meters-orchestrator-workflows.md before choosing CLI flags or launch behavior.
Use the documented software-trigger subprocess orchestration pattern. Do not use
detached shell launch such as PowerShell Start-Process or cmd /c start /B unless
the repository documents it.

After dry-run and simulator validation are planned or run, prepare the live
command as a template that uses this placeholder resource:

<USER_SELECTED_VISA_RESOURCE>

Do not scan, guess, rotate, or substitute VISA resources. Do not ask me for the
real live resource in this prompt. Do not execute the live command. Only stop to
ask me a question if the CLI cannot be invoked, dependencies are missing, the
contracts and CLI help disagree, or a planned command would touch live hardware
before I provide an explicit resource and request live execution.

Report:

1. The dry-run and simulator validation result or the blocker that prevented it.
2. The exact live command template using <USER_SELECTED_VISA_RESOURCE>.
3. The structured outputs that must be checked after a future live run.
4. The explicit user confirmation required before live execution.
```

#### 預期 agent 行為

Codex 應該：

- 在準備 live template 前，先使用 dry-run 與 simulator validation。
- 透過 placeholder resource 保留 live safety boundary。
- 因為此 prompt 沒有要求 live execution，所以避免詢問實際 live resource。
- 避免掃描或猜測 VISA resources。
- 使用文件化的 CLI 拼法、simulator resource strings 與 subprocess orchestration，而不是自行發明 flags 或使用 detached shell launch。
- 明確說明 live execution 需要 explicit user-selected resource 與另一個使用者要求。

#### 預期結果

agent 應該產生 live-workflow preparation result 與精確的 live command template，同時確認未執行任何 live hardware command。

### 執行型範例 3：立即進行合約導向審查

#### 目標

不需要再次確認，直接根據 Meters contracts 審查目前 repository changes。

#### 使用者 prompt

```text
Use $keysight-meters-cli-orchestration.

Review the current repository changes against the Meters CLI/worker contracts
now. Use the current git diff, staged changes, or changed files available in the
workspace. If there are no changed files, report that there is no diff to
review.

Read the relevant common and Meters-specific contracts first. Focus on JSONL
parsing, ready/status handling, POST /command behavior, cooperative stop,
run_id correlation, final summary handling, exit codes, artifact decisions, and
whether the change avoids guessing live VISA resources.

Do not ask for confirmation before reviewing. Do not run live hardware. Only
stop to ask me a question if the changed files cannot be read, the contract
files are missing, or the available diff is ambiguous enough that a contract
review would be misleading.

Return concrete findings, affected contract boundaries, severity, and whether
the change is safe for no-hardware validation, simulator validation, or live
execution.
```

#### 預期 agent 行為

Codex 應該：

- 立即檢查可用的 changed files 或 diffs。
- 在判斷行為前先讀取相關 contract files。
- 審查 machine-output handling、lifecycle ordering、status semantics、command/stop behavior、`run_id` correlation、artifacts 與 live resource safety。
- 除非無法存取 diff 或 contracts，否則不要要求再次確認。
- 不執行 live hardware。

#### 預期結果

agent 應該回傳以合約為核心、可行動的 findings。如果沒有 diff 或無法讀取 diff，應清楚報告該 blocker。

## 明確授權的實機執行範例 (Explicit live execution examples)

這些範例可能會碰到真實儀器。只有在操作人員已選定精確 VISA resource，並明確授權該 resource 可以進行 live execution 時才使用。不要使用這些 prompt 來 discover、scan、guess、rotate 或 substitute live VISA resources。

### 明確實機範例 1：指定 resource 的 one-sample live validation

#### 目標

使用明確提供的 VISA resource，對真實 Keysight 34461A 執行完整 dry-run、simulator 與 live validation 流程，並只擷取剛好一筆 sample。

#### 使用者 prompt

```text
Use $keysight-meters-cli-orchestration.

Run an explicit-resource live one-sample validation workflow.

I authorize live execution for this exact VISA resource only:

<PASTE_EXPLICIT_VISA_RESOURCE_HERE>

Use these defaults unless the repository contracts or CLI help require a
different spelling:

- measurement type: voltage-dc
- trigger mode: software
- finite sample bound: exactly one sample
- output directory: .tmp_tests/skill_examples/live_one_sample/
- worker observation output: JSONL
- client command output: JSON

Steps:

1. Read the skill and the relevant common and Meters-specific contracts,
   including common-orchestrator-workflows.md and
   meters-orchestrator-workflows.md.
2. Confirm the exact CLI flag spelling from the contracts before using CLI help.
3. Run dry-run first.
4. Run simulator validation with SIM::34461A and a finite bound using the
   documented software-trigger subprocess orchestration pattern.
5. Start the worker as an observable subprocess, stream stdout JSONL until the
   ready event, and do not use detached shell launch such as PowerShell
   Start-Process or cmd /c start /B unless the repository documents it.
6. Only after dry-run and simulator validation pass, run live using exactly the
   VISA resource provided above.
7. Wait for the ready JSONL event or use wait-ready --json.
8. Send exactly one software_trigger command after readiness.
9. Check run_id correlation across stdout JSONL, status response, CSV, and
   report.json if present.
10. Continue reading worker JSONL until summary, then report the JSONL events,
    artifacts, exit codes, summary.ok, captured count, errors, and any contract
    mismatch.

Do not scan, guess, rotate, brute-force, or substitute VISA resources. Do not
use any live resource other than the one explicitly provided above. Do not invent
CLI flags, measurement values, simulator resource aliases, or worker launch
patterns. If the resource is missing, ambiguous, unavailable, or does not match
the intended Keysight 34461A, fail closed and do not run live.
```

#### 預期 agent 行為

Codex 應該：

- 只有在使用者明確授權 live execution，並提供由操作人員替換的具體 resource placeholder 後，才把這視為 real-instrument workflow。
- 在任何 live command 前，先執行或嘗試執行 dry-run 與 simulator validation。
- 使用文件化的 CLI 拼法、simulator resource strings 與 subprocess orchestration，而不是自行發明 flags 或使用 detached shell launch。
- 只使用提供的 live resource，絕不 scan、guess、rotate 或 substitute 其他 resource。
- 若 resource 缺失、模糊、不可用，或不符合預期的 Keysight 34461A，應在 live execution 前 fail closed。
- 將 `ready` 與 `wait-ready` 視為 control-plane readiness，而不是 measurement completion。
- 以 structured JSON/JSONL、CSV、適用時的 `report.json` 與 process exit codes 作為 pass/fail 依據，而不是人類可讀文字。

#### 預期結果

agent 應該執行完整 dry-run、simulator 與 explicit-resource live sequence，或是在 live execution 前因明確的安全或環境 blocker 停下。最後報告應清楚說明是否碰到 live hardware、使用了哪個 exact resource，以及檢查了哪些 structured outputs。
