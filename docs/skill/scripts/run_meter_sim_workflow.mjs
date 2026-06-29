#!/usr/bin/env node
import { spawn } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { isAbsolute, join, resolve } from "node:path";

const DEFAULTS = {
  out: ".tmp_tests/meter_sim_software_trigger",
  resource: "SIM::34461A",
  measurement: "current-dc",
  port: "18765",
  maxSamples: "1",
  readyTimeoutMs: "5000",
  waitReadyTimeoutMs: "10000",
  summaryTimeoutMs: "20000",
  clientTimeoutMs: "3000",
};

function usage() {
  return [
    "Usage: node run_meter_sim_workflow.mjs [options]",
    "",
    "Options:",
    "  --exe <path>                 keysight-logger executable; default: one keysight-logger*.exe in cwd",
    "  --out <dir>                  artifact directory; default: .tmp_tests/meter_sim_software_trigger",
    "  --resource <string>          simulator resource; default: SIM::34461A",
    "  --measurement <name>         measurement; default: current-dc",
    "  --port <number>              software trigger port; default: 18765",
    "  --max-samples <n>            finite bound; default: 1",
    "  --ready-timeout-ms <n>       stdout ready wait before wait-ready fallback; default: 5000",
    "  --wait-ready-timeout-ms <n>  wait-ready fallback deadline; default: 10000",
    "  --summary-timeout-ms <n>     summary wait after trigger; default: 20000",
    "  --client-timeout-ms <n>      CLI client timeout-ms; default: 3000",
  ].join("\n");
}

function parseArgs(argv) {
  const options = { ...DEFAULTS };
  const keyMap = {
    "--exe": "exe",
    "--out": "out",
    "--resource": "resource",
    "--measurement": "measurement",
    "--port": "port",
    "--max-samples": "maxSamples",
    "--ready-timeout-ms": "readyTimeoutMs",
    "--wait-ready-timeout-ms": "waitReadyTimeoutMs",
    "--summary-timeout-ms": "summaryTimeoutMs",
    "--client-timeout-ms": "clientTimeoutMs",
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--help" || arg === "-h") {
      console.log(usage());
      process.exit(0);
    }
    const key = keyMap[arg];
    if (!key) {
      throw new Error(`unknown argument: ${arg}\n${usage()}`);
    }
    const value = argv[index + 1];
    if (!value || value.startsWith("--")) {
      throw new Error(`missing value for ${arg}`);
    }
    options[key] = value;
    index += 1;
  }
  return options;
}

function toAbsolute(path) {
  return isAbsolute(path) ? path : resolve(process.cwd(), path);
}

function positiveInteger(name, value) {
  if (!/^\d+$/.test(String(value))) {
    throw new Error(`${name} must be a positive integer`);
  }
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 1) {
    throw new Error(`${name} must be a positive integer`);
  }
  return parsed;
}

function nonNegativeInteger(name, value) {
  if (!/^\d+$/.test(String(value))) {
    throw new Error(`${name} must be a non-negative integer`);
  }
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed)) {
    throw new Error(`${name} must be a non-negative integer`);
  }
  return parsed;
}

function findExe(explicitExe) {
  if (explicitExe) {
    const exe = toAbsolute(explicitExe);
    if (!existsSync(exe)) {
      throw new Error(`executable not found: ${exe}`);
    }
    return exe;
  }

  const candidates = readdirSync(process.cwd())
    .filter((name) => /^keysight-logger.*\.exe$/i.test(name))
    .map((name) => join(process.cwd(), name));
  if (candidates.length === 1) {
    return candidates[0];
  }
  if (candidates.length === 0) {
    throw new Error("no keysight-logger*.exe found in cwd; pass --exe");
  }
  throw new Error(`multiple keysight-logger executables found; pass --exe: ${candidates.join(", ")}`);
}

function runCommand(exe, args, timeoutMs) {
  return new Promise((resolveCommand) => {
    const started = Date.now();
    const child = spawn(exe, args, { cwd: process.cwd(), windowsHide: true });
    let stdout = "";
    let stderr = "";
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      child.kill();
    }, timeoutMs);

    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      const trimmed = stdout.trim();
      let parsed = null;
      let parseError = null;
      if (trimmed) {
        try {
          parsed = JSON.parse(trimmed);
        } catch (error) {
          parseError = String(error?.message ?? error);
        }
      }
      resolveCommand({
        args,
        exit_code: timedOut ? 3 : code,
        timed_out: timedOut,
        elapsed_ms: Date.now() - started,
        stdout,
        stderr,
        json: parsed,
        parse_error: parseError,
      });
    });
  });
}

function parseJsonLines(text) {
  const events = [];
  const errors = [];
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      events.push(JSON.parse(trimmed));
    } catch (error) {
      errors.push({ line: trimmed, message: String(error?.message ?? error) });
    }
  }
  return { events, errors };
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];
    if (inQuotes) {
      if (char === '"' && next === '"') {
        field += '"';
        index += 1;
      } else if (char === '"') {
        inQuotes = false;
      } else {
        field += char;
      }
    } else if (char === '"') {
      inQuotes = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else if (char !== "\r") {
      field += char;
    }
  }

  if (field.length > 0 || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  if (rows.length < 2) return [];
  const headers = rows[0];
  return rows.slice(1).map((values) =>
    Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ""])),
  );
}

function waitForCondition(predicate, timeoutMs) {
  return new Promise((resolveWait) => {
    const deadline = Date.now() + timeoutMs;
    const timer = setInterval(() => {
      const value = predicate();
      if (value) {
        clearInterval(timer);
        resolveWait(value);
      } else if (Date.now() >= deadline) {
        clearInterval(timer);
        resolveWait(null);
      }
    }, 50);
  });
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const exe = findExe(options.exe);
  const out = toAbsolute(options.out);
  const port = positiveInteger("--port", options.port);
  const maxSamples = positiveInteger("--max-samples", options.maxSamples);
  const readyTimeoutMs = nonNegativeInteger("--ready-timeout-ms", options.readyTimeoutMs);
  const waitReadyTimeoutMs = positiveInteger("--wait-ready-timeout-ms", options.waitReadyTimeoutMs);
  const summaryTimeoutMs = positiveInteger("--summary-timeout-ms", options.summaryTimeoutMs);
  const clientTimeoutMs = positiveInteger("--client-timeout-ms", options.clientTimeoutMs);
  const commandTimeoutMs = Math.max(clientTimeoutMs + 5000, 15000);

  mkdirSync(out, { recursive: true });
  const dryRunJsonlPath = join(out, "dry_run.jsonl");
  const csvPath = join(out, "sim_samples.csv");
  const reportPath = join(out, "sim_report.json");
  const stderrPath = join(out, "sim_worker_stderr.txt");
  const stdoutJsonlPath = join(out, "sim_worker_stdout.jsonl");
  for (const path of [dryRunJsonlPath, csvPath, reportPath, stderrPath, stdoutJsonlPath]) {
    if (existsSync(path)) rmSync(path);
  }

  const baseArgs = [
    "--resource",
    options.resource,
    "--trigger-mode",
    "software",
    "--max-samples",
    String(maxSamples),
    "--measurement",
    options.measurement,
    "--sw-trigger-port",
    String(port),
  ];
  const dryRunArgs = [
    "start-trigger-record",
    ...baseArgs,
    "--dry-run",
    "--status-format",
    "jsonl",
    "--csv",
    join(out, "dry_run_samples.csv"),
  ];
  const dryRun = await runCommand(exe, dryRunArgs, commandTimeoutMs);
  writeFileSync(dryRunJsonlPath, dryRun.stdout, "utf8");
  const dryRunParsed = parseJsonLines(dryRun.stdout);
  const dryRunEvent = dryRunParsed.events.find((event) => event.event === "dry_run") ?? null;

  const events = [];
  const parseErrors = [];
  const stderrChunks = [];
  const workerArgs = [
    "start-trigger-record",
    "--resource",
    options.resource,
    "--simulate",
    "--trigger-mode",
    "software",
    "--max-samples",
    String(maxSamples),
    "--measurement",
    options.measurement,
    "--status-format",
    "jsonl",
    "--sw-trigger-port",
    String(port),
    "--csv",
    csvPath,
  ];
  const worker = spawn(exe, workerArgs, { cwd: process.cwd(), windowsHide: true });
  worker.stdout.setEncoding("utf8");
  worker.stderr.setEncoding("utf8");

  let stdoutBuffer = "";
  worker.stdout.on("data", (chunk) => {
    stdoutBuffer += chunk;
    while (stdoutBuffer.includes("\n")) {
      const index = stdoutBuffer.indexOf("\n");
      const line = stdoutBuffer.slice(0, index).trim();
      stdoutBuffer = stdoutBuffer.slice(index + 1);
      if (!line) continue;
      try {
        events.push(JSON.parse(line));
      } catch (error) {
        parseErrors.push({ line, message: String(error?.message ?? error) });
      }
    }
  });
  worker.stderr.on("data", (chunk) => {
    stderrChunks.push(chunk);
  });
  const workerClosed = new Promise((resolveClosed) => {
    worker.on("close", (code) => resolveClosed(code));
  });

  const clients = {};
  let readyEvent = await waitForCondition(
    () => events.find((event) => event.event === "ready") ?? null,
    readyTimeoutMs,
  );
  if (!readyEvent && worker.exitCode === null) {
    clients.wait_ready_after_missing_stdout_ready = await runCommand(
      exe,
      [
        "wait-ready",
        "--port",
        String(port),
        "--json",
        "--timeout-ms",
        String(waitReadyTimeoutMs),
      ],
      waitReadyTimeoutMs + 5000,
    );
    if (clients.wait_ready_after_missing_stdout_ready.exit_code === 0) {
      readyEvent = clients.wait_ready_after_missing_stdout_ready.json;
    }
  }

  clients.wait_ready = await runCommand(
    exe,
    ["wait-ready", "--port", String(port), "--json", "--timeout-ms", String(waitReadyTimeoutMs)],
    waitReadyTimeoutMs + 5000,
  );
  clients.status_before_trigger = await runCommand(
    exe,
    ["status", "--port", String(port), "--json", "--timeout-ms", String(clientTimeoutMs)],
    commandTimeoutMs,
  );
  clients.send_command = await runCommand(
    exe,
    [
      "send-command",
      "--port",
      String(port),
      "--json",
      "--timeout-ms",
      String(clientTimeoutMs),
      "--job-id",
      "meter-sim-one-sample",
      "--arguments-json",
      '{"metadata":{"requested_by":"codex","sample_goal":"one"}}',
    ],
    commandTimeoutMs,
  );

  let summaryEvent = await waitForCondition(
    () => events.find((event) => event.event === "summary") ?? null,
    summaryTimeoutMs,
  );
  let workerExitCode = null;
  const closeTimeout = new Promise((resolveClose) => {
    setTimeout(() => resolveClose("timeout"), 10000);
  });
  const closeResult = await Promise.race([workerClosed, closeTimeout]);
  if (closeResult === "timeout") {
    clients.stop_cleanup = await runCommand(
      exe,
      ["stop", "--port", String(port), "--json", "--timeout-ms", String(clientTimeoutMs)],
      commandTimeoutMs,
    );
    const secondCloseResult = await Promise.race([workerClosed, closeTimeout]);
    if (secondCloseResult === "timeout") {
      worker.kill();
      workerExitCode = await workerClosed;
    } else {
      workerExitCode = secondCloseResult;
    }
  } else {
    workerExitCode = closeResult;
  }

  if (stdoutBuffer.trim()) {
    for (const { events: tailEvents, errors } of [parseJsonLines(stdoutBuffer)]) {
      events.push(...tailEvents);
      parseErrors.push(...errors);
    }
  }
  summaryEvent = events.find((event) => event.event === "summary") ?? summaryEvent;
  const workerStderr = stderrChunks.join("");
  writeFileSync(stderrPath, workerStderr, "utf8");
  writeFileSync(
    stdoutJsonlPath,
    events.map((event) => JSON.stringify(event)).join("\n") + (events.length ? "\n" : ""),
    "utf8",
  );

  const csvRows = existsSync(csvPath) ? parseCsv(readFileSync(csvPath, "utf8")) : [];
  const stdoutRunIds = [...new Set(events.map((event) => event.run_id).filter(Boolean))].sort();
  const runIds = {
    stdout: stdoutRunIds,
    wait_ready: clients.wait_ready?.json?.run_id ?? null,
    status_before_trigger: clients.status_before_trigger?.json?.run_id ?? null,
    sample: events.find((event) => event.event === "sample")?.run_id ?? null,
    summary: summaryEvent?.run_id ?? null,
  };
  const eventSequence = events.map((event) => event.event);
  const runIdCorrelated =
    stdoutRunIds.length === 1 &&
    runIds.wait_ready === stdoutRunIds[0] &&
    runIds.status_before_trigger === stdoutRunIds[0] &&
    runIds.sample === stdoutRunIds[0] &&
    runIds.summary === stdoutRunIds[0];

  const checks = {
    dry_run_exit_code_zero: dryRun.exit_code === 0,
    dry_run_single_event: dryRunParsed.events.length === 1,
    dry_run_event: dryRunEvent?.event === "dry_run",
    dry_run_no_run_id: dryRunEvent ? !Object.hasOwn(dryRunEvent, "run_id") : false,
    dry_run_no_visa_io: dryRunEvent?.dry_run_performs_visa_io === false,
    dry_run_no_http_server: dryRunEvent?.dry_run_starts_http_server === false,
    dry_run_no_csv_write: dryRunEvent?.dry_run_writes_csv === false,
    dry_run_parse_ok: dryRunParsed.errors.length === 0,
    ready_observed: Boolean(readyEvent),
    wait_ready_ok: clients.wait_ready?.exit_code === 0 && clients.wait_ready?.json?.ok === true,
    status_ok: clients.status_before_trigger?.exit_code === 0 && clients.status_before_trigger?.json?.ok === true,
    send_command_accepted:
      clients.send_command?.exit_code === 0 &&
      clients.send_command?.json?.status === "accepted" &&
      clients.send_command?.json?.command === "software_trigger",
    stdout_has_ready: eventSequence.includes("ready"),
    stdout_has_sample: eventSequence.includes("sample"),
    stdout_has_summary: eventSequence.includes("summary"),
    summary_ok: summaryEvent?.ok === true,
    captured_expected: summaryEvent?.captured === maxSamples,
    errors_zero: summaryEvent?.errors === 0,
    worker_exit_code_zero: workerExitCode === 0,
    csv_one_row: csvRows.length === maxSamples,
    run_id_correlated: runIdCorrelated,
    worker_jsonl_parse_ok: parseErrors.length === 0,
  };
  const ok = Object.values(checks).every(Boolean);
  const report = {
    schema_version: 1,
    ok,
    generated_at: new Date().toISOString(),
    executable: exe,
    artifact_paths: {
      dry_run_jsonl: dryRunJsonlPath,
      worker_stdout_jsonl: stdoutJsonlPath,
      worker_stderr: stderrPath,
      csv: csvPath,
      report: reportPath,
    },
    dry_run: dryRun,
    dry_run_event: dryRunEvent,
    worker_args: [exe, ...workerArgs],
    port,
    resource: options.resource,
    measurement: options.measurement,
    max_samples: maxSamples,
    clients,
    events,
    event_sequence: eventSequence,
    parse_errors: parseErrors,
    run_ids: runIds,
    run_id_correlated: runIdCorrelated,
    csv_exists: existsSync(csvPath),
    csv_row_count: csvRows.length,
    csv_rows: csvRows,
    summary: summaryEvent,
    worker_stderr: workerStderr,
    worker_exit_code: workerExitCode,
    checks,
  };

  writeFileSync(reportPath, JSON.stringify(report, null, 2), "utf8");
  console.log(JSON.stringify(report, null, 2));
  return ok ? 0 : 3;
}

main()
  .then((code) => {
    process.exitCode = code;
  })
  .catch((error) => {
    console.error(error?.stack ?? String(error));
    process.exitCode = 3;
  });
