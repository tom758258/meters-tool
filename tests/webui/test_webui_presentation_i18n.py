from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "src" / "meters_tool_webui" / "static"
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="Node.js is required for presentation runtime tests")
def test_presentation_mapping_is_exact_and_has_no_browser_side_effects():
    script = r"""
import assert from "node:assert/strict";

const moduleUrl = process.argv[1];
const guarded = [
  "document", "window", "navigator", "localStorage", "fetch", "EventSource",
];
const accesses = [];
for (const name of guarded) {
  Object.defineProperty(globalThis, name, {
    configurable: true,
    get() {
      accesses.push(name);
      throw new Error(`unexpected global access: ${name}`);
    },
  });
}

const presentation = await import(moduleUrl);
const { createI18n } = await import(new URL("./i18n.js", moduleUrl));
const { EN_MESSAGES } = await import(new URL("./locale_en.js", moduleUrl));
const { ZH_TW_MESSAGES } = await import(new URL("./locale_zh_tw.js", moduleUrl));
const translator = createI18n({ catalogs: { en: EN_MESSAGES, "zh-TW": ZH_TW_MESSAGES } });

assert.deepEqual(
  presentation.runStatePresentation("RUNNING"),
  { kind: "translated", key: "status.running", params: {} }
);
assert.deepEqual(
  presentation.latestStatusPresentation(" waiting trigger "),
  { kind: "translated", key: "status.waiting_trigger", params: {} }
);
assert.deepEqual(
  presentation.latestStatusPresentation("vendor diagnostic: waiting trigger soon"),
  { kind: "raw", text: "vendor diagnostic: waiting trigger soon" }
);
// Cover lifecycle families and parameter preservation without freezing Chinese copy.
for (const [raw, tokens] of [
  ["recording started", []],
  ["hardware trigger wait timed out; re-armed and waiting for next edge", []],
  ["software trigger ignored while software timer is enabled", []],
  ["software custom capture armed", []],
  ["overflow detected: questionable status bit 0x4000", ["0x4000"]],
  ["main cleanup starting", []],
  ["waiting worker to fully stop...", []],
  ["software trigger server stopped", []],
  ["software timer enabled interval_s=1e-05", ["interval_s=1e-05"]],
  ["max samples reached: 12", ["12"]],
  ["hardware trigger configured slope=NEG delay_s=0.0", ["slope=NEG", "delay_s=0.0"]],
  ["immediate custom capture configured trigger_count=2 sample_count=3 expected_readings=6", ["trigger_count=2", "sample_count=3", "expected_readings=6"]],
  ["software custom capture configured trigger_count=infinity sample_count=4 expected_readings=unbounded", ["trigger_count=infinity", "sample_count=4", "expected_readings=unbounded"]],
  ["external custom capture configured trigger_count=3 sample_count=4 expected_readings=12 slope=POS delay_s=1e-06", ["trigger_count=3", "sample_count=4", "expected_readings=12", "slope=POS", "delay_s=1e-06"]],
  ["software custom trigger sent=2/infinity", ["sent=2/infinity"]],
  ["expected readings reached: 12", ["12"]],
]) {
  const mapped = presentation.latestStatusPresentation(raw);
  assert.equal(mapped.kind, "translated", raw);
  translator.setLocale("en");
  const english = translator.t(mapped.key, mapped.params);
  assert.equal(english.toLowerCase(), raw.toLowerCase());
  translator.setLocale("zh-TW");
  const chinese = translator.t(mapped.key, mapped.params);
  assert.match(chinese, /\p{Script=Han}/u);
  for (const token of tokens) {
    assert.ok(english.includes(token), `${raw}: missing ${token}`);
    assert.ok(chinese.includes(token), `${raw}: missing ${token}`);
  }
  for (const nearMatch of [`prefix ${raw}`, `${raw}; vendor detail`]) {
    assert.deepEqual(presentation.latestStatusPresentation(nearMatch), { kind: "raw", text: nearMatch });
  }
}
const path = "C:\\meter\\MixedCase.csv";
const csvPath = presentation.latestStatusPresentation(`csv output path: ${path}`);
assert.equal(csvPath.kind, "translated");
for (const locale of ["en", "zh-TW"]) {
  translator.setLocale(locale);
  assert.ok(translator.t(csvPath.key, csvPath.params).includes(path));
}
for (const raw of [
  "captured=7 1.25 V",
  "software timer enabled interval_s=0.5 ms",
  "hardware trigger configured slope=VENDOR delay_s=0.0",
  "release_to_local: SYST:LOC:failed vendor detail",
  "overflow monitoring failed type=VisaIOError: raw detail",
]) {
  assert.deepEqual(presentation.latestStatusPresentation(raw), { kind: "raw", text: raw });
}
assert.deepEqual(
  presentation.resourceStatusPresentation("live"),
  { kind: "translated", key: "resource.status.live", params: {} }
);
assert.deepEqual(
  presentation.resourceStatusPresentation("vendor-live"),
  { kind: "raw", text: "vendor-live" }
);
assert.deepEqual(
  presentation.resourceStatusPresentation("LIVE"),
  { kind: "raw", text: "LIVE" }
);

assert.deepEqual(
  presentation.browserErrorPresentation("resource is required"),
  { kind: "translated", key: "error.resource_required", params: {} }
);
assert.deepEqual(
  presentation.browserErrorPresentation("resource is required: USB0"),
  { kind: "raw", text: "resource is required: USB0" }
);
assert.deepEqual(
  presentation.browserErrorPresentation(
    "Selected model 34460A does not match the connected instrument IDN 34461A. Select 34461A or rescan the device."
  ),
  {
    kind: "translated",
    key: "error.model_idn_mismatch",
    params: { selected: "34460A", connected: "34461A" },
  }
);
for (const malformed of [
  "Selected model 34460A does not match the connected instrument IDN 34461A.",
  "Selected model 34460A does not match the connected instrument IDN 34461A. Select 34460A or rescan the device.",
  "prefix Selected model 34460A does not match the connected instrument IDN 34461A. Select 34461A or rescan the device.",
]) {
  assert.deepEqual(
    presentation.browserErrorPresentation(malformed),
    { kind: "raw", text: malformed }
  );
}
assert.deepEqual(accesses, []);
process.stdout.write(JSON.stringify({ ok: true }));
"""
    completed = subprocess.run(
        [
            NODE,
            "--input-type=module",
            "--eval",
            script,
            (STATIC_DIR / "presentation_i18n.js").resolve().as_uri(),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, (
        "Node presentation mapping contract failed\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert completed.stdout == '{"ok":true}'


STATUS_TEST_SETUP = r"""
import assert from "node:assert/strict";

const statusUrl = process.argv[1];

class FakeClassList {
  constructor() { this.values = new Set(); }
  add(name) { this.values.add(name); }
  remove(name) { this.values.delete(name); }
  contains(name) { return this.values.has(name); }
  toggle(name, force) {
    const enabled = force === undefined ? !this.values.has(name) : Boolean(force);
    if (enabled) this.values.add(name);
    else this.values.delete(name);
    return enabled;
  }
}

function hasClass(element, className) {
  return String(element.className || "")
    .split(/\s+/)
    .filter(Boolean)
    .includes(className);
}

class FakeElement {
  constructor(tagName = "div") {
    this.tagName = tagName;
    this.textContent = "";
    this.value = "";
    this.disabled = false;
    this.checked = false;
    this.children = [];
    this.dataset = {};
    this.attributes = new Map();
    this.listeners = new Map();
    this.classList = new FakeClassList();
    this.clientWidth = 640;
    this.clientHeight = 760;
  }
  get options() { return this.children; }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  removeAttribute(name) { this.attributes.delete(name); }
  addEventListener(name, listener) { this.listeners.set(name, listener); }
  appendChild(child) { return this.insertBefore(child, null); }
  prepend(...children) {
    const reference = this.children[0] ?? null;
    for (const child of children) this.insertBefore(child, reference);
  }
  insertBefore(child, reference) {
    child.remove();
    const index = reference === null ? this.children.length : this.children.indexOf(reference);
    assert.ok(index >= 0);
    this.children.splice(index, 0, child);
    child.parentNode = this;
    return child;
  }
  remove() {
    if (this.parentNode) {
      const siblings = this.parentNode.children;
      siblings.splice(siblings.indexOf(this), 1);
      this.parentNode = null;
    }
  }
  replaceChildren(...children) {
    for (const child of this.children) child.parentNode = null;
    this.children = children;
    for (const child of children) child.parentNode = this;
  }
  querySelector(selector) {
    if (selector === ".live-detail-button") {
      return this.children
        .flatMap((child) => [child, ...child.children])
        .find((child) => hasClass(child, "live-detail-button")) ?? null;
    }
    return null;
  }
  querySelectorAll(selector) {
    if (selector === "tr[data-sequence]") {
      return this.children.filter((child) => child.dataset.sequence !== undefined);
    }
    const descendants = this.children.flatMap((child) => [child, ...child.querySelectorAll(selector)]);
    return descendants.filter((child) => selector.split(",").some((binding) =>
      child.getAttribute(binding.slice(1, -1)) !== null
    ));
  }
  click() { this.listeners.get("click")?.({ target: this }); }
}

const elements = new Map();
function element(selector) {
  if (!elements.has(selector)) elements.set(selector, new FakeElement());
  return elements.get(selector);
}
const executionModeInputs = [new FakeElement("input"), new FakeElement("input")];
function descendantByClass(root, className) {
  const pending = [...root.children];
  while (pending.length > 0) {
    const child = pending.shift();
    if (hasClass(child, className)) return child;
    pending.push(...child.children);
  }
  return null;
}
const clock = {
  now: 0,
  nextId: 1,
  timers: new Map(),
  intervals: new Map(),
  advance(ms) {
    const target = this.now + ms;
    while (true) {
      const next = [...this.timers.entries()]
        .filter(([, timer]) => timer.at <= target)
        .sort((a, b) => a[1].at - b[1].at)[0];
      if (!next) break;
      this.now = next[1].at;
      this.timers.delete(next[0]);
      next[1].callback();
    }
    this.now = target;
  },
};
globalThis.performance = { now: () => clock.now };
const windowListeners = new Map();
let fetchCalls = 0;
globalThis.fetch = async () => {
  fetchCalls += 1;
  throw new Error("unexpected fetch during presentation refresh");
};
globalThis.document = {
  querySelector: element,
  querySelectorAll(selector) {
    return selector === "[name='execution-mode']" ? executionModeInputs : [];
  },
  createElement(tagName) { return new FakeElement(tagName); },
  createElementNS(_namespace, tagName) { return new FakeElement(tagName); },
};
globalThis.window = {
  addEventListener(name, listener) { windowListeners.set(name, listener); },
  setTimeout(callback, delay) {
    const id = clock.nextId++;
    clock.timers.set(id, { callback, at: clock.now + Math.trunc(delay) });
    return id;
  },
  clearTimeout(id) { clock.timers.delete(id); },
  setInterval(callback, delay) {
    const id = clock.nextId++;
    clock.intervals.set(id, { callback, delay });
    return id;
  },
  clearInterval(id) { clock.intervals.delete(id); },
};

globalThis.setTimeout = window.setTimeout;
globalThis.clearTimeout = window.clearTimeout;

element("#trigger-mode").value = "software";
const status = await import(statusUrl);
const i18n = await import(new URL("./i18n.js", statusUrl));
status.initializeStatusUi();

"""


@pytest.mark.frontend_node
@pytest.mark.skipif(NODE is None, reason="Node.js is required for status runtime tests")
def test_status_and_live_data_render_translations_without_changing_raw_identity():
    script = STATUS_TEST_SETUP + r"""

const sample = {
  sequence: 7,
  timestamp_utc_plus_8: "2026-07-13T10:11:12+08:00",
  value: 1.25,
  unit: "V",
  trigger_source: "software-custom",
  status: "vendor-sample-status",
  trigger_metadata: { source: "web-ui", batch: "A1" },
  measurement_metadata: { measurement: "voltage-dc" },
};
const running = {
  run_id: "run-1",
  state: "running",
  active: false,
  captured: 1,
  errors: 0,
  csv_path: "C:\\meter\\out.csv",
  latest_status: "ready",
  fatal_error: "raw fatal TYPE_X",
  cleanup_status: "raw cleanup CODE_Y",
  trigger_mode: "software",
  recent_samples: [sample],
  latest_sample: sample,
  sample_capacity: 5000,
};
status.renderStatus(running);

for (const [monitoring, detected, english, chinese] of [
  ["failed", true, "Overflow detected; subsequent monitoring failed", "已偵測到溢位；後續監測失敗"],
  ["active", true, "Overflow detected", "已偵測到溢位"],
  ["failed", null, "Monitoring failed", "監測失敗"],
  ["active", false, "No overflow detected", "未偵測到溢位"],
]) {
  const raw = { ...running, overflow_monitoring: monitoring, overflow_detected: detected };
  const before = JSON.stringify(raw);
  status.renderStatus(raw);
  for (const [locale, expected] of [["zh-TW", chinese], ["en", english]]) {
    i18n.setLocale(locale);
    status.refreshStatusPresentation();
    assert.equal(element("#status-overflow").textContent, expected);
    assert.equal(JSON.stringify(raw), before);
    assert.equal(element("#raw-status").textContent, JSON.stringify(raw, null, 2));
  }
}
status.renderStatus(running);

assert.equal(element("#status-state").getAttribute("data-i18n"), "status.running");
assert.equal(element("#fatal-error").textContent, "raw fatal TYPE_X");
assert.equal(element("#cleanup-status").textContent, "raw cleanup CODE_Y");
assert.equal(element("#raw-status").textContent, JSON.stringify(running, null, 2));

status.renderPlanPreview({
  dry_run: true,
  simulate: false,
  scpi_commands: ["CONF:VOLT:DC"],
  read_path: "READ?",
  cleanup_steps: ["wait for worker"],
  option_summary: { auto_range: true },
});
assert.equal(element("#live-data-summary").getAttribute("data-i18n"), "live_data.no_samples");
assert.equal(element("#live-latest-value").textContent, "--");
assert.match(element("#dry-run-plan").textContent, /"dry_run": true/);
assert.equal(element("#dry-run-plan-result").classList.contains("is-hidden"), false);
status.renderStatus(running);
assert.equal(element("#live-data-summary").getAttribute("data-i18n"), "live_data.no_samples");
status.clearPlanPreview();
assert.equal(
  element("#live-data-summary").getAttribute("data-i18n"),
  "live_data.recent_sample_summary"
);

const latestLines = () => element("#latest-status").children;
assert.equal(latestLines().at(-1).getAttribute("data-i18n"), "execution.plan_completed");

const row = element("#live-samples-body").children.find(
  (candidate) => candidate.dataset.sequence === String(sample.sequence)
);
assert.notEqual(row, undefined);
assert.notEqual(
  row.children.find((child) => child.textContent === sample.status),
  undefined
);
const detailsButton = descendantByClass(row, "live-detail-button");
assert.notEqual(detailsButton, null);
assert.equal(detailsButton.value, "");
assert.equal(detailsButton.getAttribute("data-i18n"), "live_data.column_details");
assert.equal(
  detailsButton.getAttribute("data-i18n-aria-label"),
  "accessibility.toggle_sample_details"
);
detailsButton.click();
assert.equal(
  element("#live-selected-sample").getAttribute("data-i18n"),
  "live_data.selected_sample"
);
assert.equal(
  element("#live-sample-details").textContent,
  JSON.stringify({
    sequence: 7,
    trigger_metadata: sample.trigger_metadata,
    measurement_metadata: sample.measurement_metadata,
  }, null, 2)
);
assert.equal(element("#live-sample-details").getAttribute("data-i18n"), null);

element("#toggle-status-details").click();
element("#toggle-status-details").click();
const rawStatusBeforeLocaleRefresh = element("#raw-status").textContent;
const rawSampleDetailsBeforeLocaleRefresh = element("#live-sample-details").textContent;
const statusLogCountBeforeLocaleRefresh = latestLines().length;
i18n.setLocale("zh-TW");
status.refreshStatusPresentation();
assert.equal(element("#status-state").getAttribute("data-i18n"), "status.running");
assert.equal(
  element("#toggle-status-details").getAttribute("data-i18n"),
  "status.hide_details"
);
assert.equal(element("#status-details").classList.contains("is-hidden"), false);
assert.equal(element("#raw-status").textContent, rawStatusBeforeLocaleRefresh);
assert.equal(element("#live-sample-details").textContent, rawSampleDetailsBeforeLocaleRefresh);
assert.equal(
  element("#live-data-summary").getAttribute("data-i18n"),
  "live_data.recent_sample_summary"
);
assert.equal(
  element("#live-selected-sample").getAttribute("data-i18n"),
  "live_data.selected_sample"
);
assert.equal(latestLines().length, statusLogCountBeforeLocaleRefresh);
assert.equal(latestLines().at(-1).getAttribute("data-i18n"), "execution.plan_completed");
assert.equal(fetchCalls, 0);
i18n.setLocale("en");
status.refreshStatusPresentation();
assert.equal(
  element("#toggle-status-details").getAttribute("data-i18n"),
  "status.hide_details"
);
assert.equal(element("#status-details").classList.contains("is-hidden"), false);

const unknown = {
  ...running,
  state: "VendorState-X",
  latest_status: "Backend diagnostic FIELD_Z",
  recent_samples: [],
  latest_sample: null,
};
status.renderStatus(unknown);
assert.equal(element("#status-state").textContent, "VendorState-X");
assert.equal(element("#status-state").getAttribute("data-i18n"), null);
assert.equal(latestLines().at(-1).textContent, "Backend diagnostic FIELD_Z");
assert.equal(latestLines().at(-1).getAttribute("data-i18n"), null);
assert.equal(element("#live-data-summary").getAttribute("data-i18n"), "live_data.no_samples");

status.appendBrowserError(new Error("resource is required"));
assert.equal(latestLines().at(-1).getAttribute("data-i18n"), "error.resource_required");
status.appendBrowserError(new Error("raw backend error FIELD_A"));
status.appendBrowserError(new Error("raw backend error FIELD_A"));
assert.equal(
  latestLines().filter((line) => line.textContent === "raw backend error FIELD_A").length,
  1
);
assert.equal(latestLines().at(-1).getAttribute("data-i18n"), null);

const waiting = {
  ...unknown,
  state: "running",
  latest_status: "waiting trigger",
  run_id: "raw-run-id",
};
status.renderStatus(waiting);
status.renderStatus(waiting);
assert.equal(
  latestLines().filter((line) => line.getAttribute("data-i18n") === "status.waiting_trigger").length,
  1
);

const queued = { ...waiting, latest_status: "software trigger queued" };
status.renderStatus(queued);
assert.equal(
  latestLines().some((line) => line.getAttribute("data-i18n") === "status.software_trigger_queued"),
  false
);
for (let index = 0; index < 5; index += 1) status.markSoftwareTriggerQueuedForLog();
status.renderStatus({ ...queued, latest_status: "ready" });
status.renderStatus(queued);
assert.equal(latestLines().at(-1).getAttribute("data-i18n"), "status.software_trigger_queued");

const noCsv = { ...running, csv_enabled: false, csv_path: null };
status.renderStatus(noCsv);
assert.equal(element("#status-csv").getAttribute("data-i18n"), "common.off");
assert.equal(element("#open-csv").disabled, true);

const lifecycle = {
  ...running, active: true,
  fatal_error: "recording started",
  cleanup_status: "main cleanup starting; release_to_local: SYST:LOC:ok",
};
const messages = [
  "recording started",
  "software timer enabled interval_s=0.125",
  "main cleanup starting",
  "waiting for measurement worker to stop",
  "unknown diagnostic: SCPI READ? VISA CODE_X",
];
for (const latest_status of messages) status.renderStatus({ ...lifecycle, latest_status });
const finalSnapshot = { ...lifecycle, latest_status: messages.at(-1) };
const controlsBeforeSwitch = [
  element("#start-run").disabled, element("#stop-run").disabled,
  element("#trigger-mode").value, element("#refresh-resources").disabled,
];
let englishLog;
for (const locale of ["en", "zh-TW", "en"]) {
  i18n.setLocale(locale);
  status.refreshStatusPresentation();
  const log = latestLines().map((line) => line.textContent);
  if (locale === "en") {
    assert.deepEqual(log, messages.map((text, index) => index < 4 ? text[0].toUpperCase() + text.slice(1) : text));
    englishLog = log;
  } else {
    for (const text of log.slice(0, 4)) assert.match(text, /\p{Script=Han}/u);
    assert.ok(log[1].includes("interval_s=0.125"));
    assert.equal(log.at(-1), messages.at(-1));
    assert.notDeepEqual(log, englishLog);
  }
  assert.equal(element("#fatal-error").textContent, lifecycle.fatal_error);
  assert.equal(element("#cleanup-status").textContent, lifecycle.cleanup_status);
  assert.equal(element("#raw-status").textContent, JSON.stringify(finalSnapshot, null, 2));
  assert.equal(status.isRunActive(), true);
  assert.deepEqual([
    element("#start-run").disabled, element("#stop-run").disabled,
    element("#trigger-mode").value, element("#refresh-resources").disabled,
  ], controlsBeforeSwitch);
  status.renderStatus(finalSnapshot);
  assert.deepEqual(latestLines().map((line) => line.textContent), log);
  assert.equal(fetchCalls, 0);
}

status.renderStatus({ ...running, active: true });
assert.equal(executionModeInputs.every((input) => input.disabled), true);
const unloadEvent = { preventDefaultCalled: false, returnValue: "", preventDefault() {
  this.preventDefaultCalled = true;
} };
windowListeners.get("beforeunload")(unloadEvent);
assert.equal(unloadEvent.preventDefaultCalled, true);
// This warning is a safety contract: it tells operators that closing the page
// does not stop an active measurement run.
assert.equal(
  unloadEvent.returnValue,
  "A measurement run is active. Refreshing or closing the page will not stop it."
);
process.stdout.write(JSON.stringify({ ok: true }));
"""
    run_status_script(script)


def run_status_script(script):
    completed = subprocess.run(
        [NODE, "--input-type=module", "--eval", script, (STATIC_DIR / "status.js").resolve().as_uri()],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, (
        "Node status/live-data behavior contract failed\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert completed.stdout == '{"ok":true}'


LIVE_TEST_SETUP = STATUS_TEST_SETUP + r"""
const live = await import(new URL("./live_data.js", statusUrl));
live.initializeLiveDataUi();
const sample = (sequence) => ({
  sequence,
  timestamp_utc_plus_8: `2026-07-13T10:11:${String(sequence % 60).padStart(2, "0")}+08:00`,
  value: sequence,
  unit: "V",
  trigger_source: "software",
  status: "ok",
  trigger_metadata: { batch: sequence },
  measurement_metadata: { measurement: "voltage-dc" },
});
const snapshot = (first, last, runId = "run-1", active = true) => {
  const samples = Array.from({ length: last - first + 1 }, (_, index) => sample(first + index));
  return {
    run_id: runId, active, state: active ? "running" : "stopped",
    captured: last, errors: 0, latest_status: active ? "ready" : "completed",
    recent_samples: samples, latest_sample: samples.at(-1) || null, sample_capacity: 5000,
  };
};
const body = element("#live-samples-body");
const sequences = () => body.children.map((row) => Number(row.dataset.sequence));
const rowFor = (sequence) => body.children.find((row) => row.dataset.sequence === String(sequence));
const buttonFor = (sequence) => rowFor(sequence).querySelector(".live-detail-button");
const polyline = () => element("#live-trend-chart").children.find((child) => child.tagName === "polyline");
function assertFrame(first, last) {
  assert.equal(element("#live-latest-value").textContent, `${last} V`);
  assert.equal(element("#live-latest-time").textContent, sample(last).timestamp_utc_plus_8.replace("T", " ").slice(0, 19));
  assert.equal(element("#live-latest-trigger").textContent, "software");
  assert.equal(element("#live-stat-sample").textContent, `#${last}`);
  assert.equal(element("#live-stat-min").textContent, `${first} V`);
  assert.equal(element("#live-stat-max").textContent, `${last} V`);
  assert.equal(element("#live-stat-average").textContent, `${(first + last) / 2} V`);
  assert.deepEqual(sequences(), Array.from({ length: last - first + 1 }, (_, index) => last - index));
  if (last > first) assert.equal(polyline().getAttribute("points").split(" ").length, last - first + 1);
}
"""


@pytest.mark.frontend_node
@pytest.mark.skipif(NODE is None, reason="Node.js is required for LIVE UI runtime tests")
def test_live_updates_coalesce_and_preserve_controls_user_actions_and_run_boundaries():
    script = LIVE_TEST_SETUP + r"""
let source;
globalThis.EventSource = class {
  constructor(url) {
    assert.equal(url, "/api/runs/current/events");
    this.listeners = new Map();
    source = this;
  }
  addEventListener(name, callback) { this.listeners.set(name, callback); }
};
status.startStatusUpdates();
assert.equal([...clock.intervals.values()][0].delay, 1000);
source.onopen();
assert.equal(clock.intervals.size, 0);
const send = (value) => source.listeners.get("run-status")({ data: JSON.stringify(value) });

send(snapshot(1, 1, "fractional-clock"));
clock.advance(0.5);
send(snapshot(1, 2, "fractional-clock"));
clock.advance(99);
assertFrame(1, 1); // Browser timeouts truncate fractional delays; never paint early.
clock.advance(1);
assertFrame(1, 2);
const streamStart = clock.now;
send(snapshot(1, 0));
send(snapshot(1, 1)); // The first sample is immediate, even after an empty frame.
assertFrame(1, 1);
const firstRow = rowFor(1);
buttonFor(1).click();
for (let sequence = 2; sequence <= 36; sequence += 1) {
  clock.advance(10);
  send(snapshot(1, sequence));
  const visibleLast = Math.max(1, Math.floor((clock.now - streamStart) / 100) * 10);
  assertFrame(1, visibleLast);
  assert.strictEqual(rowFor(1), firstRow);
  assert.equal(buttonFor(1).getAttribute("aria-expanded"), "true");
}
// Run state, errors and controls change immediately while LIVE waits for its trailing frame.
send({ ...snapshot(1, 36, "run-1", false), errors: 1, fatal_error: "raw failure" });
assert.equal(status.isRunActive(), false);
assert.equal(element("#status-state").getAttribute("data-i18n"), "status.stopped");
assert.equal(element("#status-captured").textContent, "36");
assert.equal(element("#status-errors").textContent, "1");
assert.equal(element("#fatal-error").textContent, "raw failure");
assert.equal(executionModeInputs.every((input) => !input.disabled), true);
clock.advance(49);
assertFrame(1, 30);
clock.advance(1);
assertFrame(1, 36); // No subsequent status is needed to display the last snapshot.
clock.advance(200);
assertFrame(1, 36);

send(snapshot(1, 37));
assertFrame(1, 37);
clock.advance(10);
send(snapshot(1, 38));
assertFrame(1, 37);
element("#live-chart-scale-mode").value = "manual-span";
element("#live-chart-manual-span").value = "100";
element("#live-chart-scale-mode").listeners.get("change")();
element("#live-chart-manual-span").listeners.get("input")();
assert.equal(element("#live-chart-scale-info").getAttribute("data-i18n"), "live_data.scale_info.manual_span");
element("#live-chart-manual-span").value = "200";
element("#live-chart-manual-span").listeners.get("input")();
assert.equal(JSON.parse(element("#live-chart-scale-info").getAttribute("data-i18n-params")).span, "200 V");
assertFrame(1, 37);
// Retained row listeners and Close still act synchronously during a pending update.
buttonFor(2).click();
assert.equal(JSON.parse(element("#live-sample-details").textContent).sequence, 2);
assert.equal(buttonFor(1).getAttribute("aria-expanded"), "false");
assert.equal(buttonFor(2).getAttribute("aria-expanded"), "true");
element("#close-live-sample-details").click();
assert.equal(element("#live-sample-metadata").classList.contains("is-hidden"), true);
const rowsBeforeLocaleRefresh = [...body.children];
const sourceBeforeLocaleRefresh = source;
const pollingBeforeLocaleRefresh = [...clock.intervals.entries()];
for (const locale of ["zh-TW", "en"]) {
  i18n.setLocale(locale);
  status.refreshStatusPresentation();
  assertFrame(1, 38);
  assert.equal(element("#live-sample-metadata").classList.contains("is-hidden"), true);
  assert.equal(element("#live-sample-details").textContent, "");
  for (const row of body.children) {
    const sequence = Number(row.dataset.sequence);
    assert.equal(row.classList.contains("is-selected"), false);
    assert.equal(buttonFor(sequence).getAttribute("aria-expanded"), "false");
    assert.equal(buttonFor(sequence).textContent, i18n.t("live_data.column_details"));
    assert.equal(buttonFor(sequence).getAttribute("aria-label"), i18n.t("accessibility.toggle_sample_details", { sequence }));
  }
  for (const row of rowsBeforeLocaleRefresh) assert.strictEqual(rowFor(Number(row.dataset.sequence)), row);
  assert.equal(fetchCalls, 0);
  assert.strictEqual(source, sourceBeforeLocaleRefresh);
  assert.deepEqual([...clock.intervals.entries()], pollingBeforeLocaleRefresh);
  assert.equal(status.isRunActive(), true);
}
buttonFor(2).click();
const detailsBeforeLocaleRefresh = element("#live-sample-details").textContent;
for (const locale of ["zh-TW", "en"]) {
  i18n.setLocale(locale);
  status.refreshStatusPresentation();
  assertFrame(1, 38);
  assert.strictEqual(rowFor(1), firstRow);
  assert.equal(buttonFor(2).textContent, i18n.t("live_data.column_details"));
  assert.equal(buttonFor(2).getAttribute("aria-label"), i18n.t("accessibility.toggle_sample_details", { sequence: 2 }));
  assert.equal(JSON.parse(element("#live-sample-details").textContent).sequence, 2);
  assert.equal(element("#live-sample-details").textContent, detailsBeforeLocaleRefresh);
  assert.equal(element("#live-sample-metadata").classList.contains("is-hidden"), false);
  for (const row of body.children) {
    const selected = row.dataset.sequence === "2";
    assert.equal(row.classList.contains("is-selected"), selected);
    assert.equal(buttonFor(Number(row.dataset.sequence)).getAttribute("aria-expanded"), String(selected));
  }
  assert.equal(fetchCalls, 0);
  assert.strictEqual(source, sourceBeforeLocaleRefresh);
  assert.deepEqual([...clock.intervals.entries()], pollingBeforeLocaleRefresh);
}

clock.advance(10);
send(snapshot(1, 39));
status.beginPlanPreview();
assert.equal(element("#live-latest-value").textContent, "--");
clock.advance(100);
assert.equal(element("#live-latest-value").textContent, "--");
status.renderPlanPreview({ dry_run: true });
send(snapshot(1, 40)); // An old run status cannot fill a plan preview.
clock.advance(100);
assert.equal(element("#live-latest-value").textContent, "--");
status.clearPlanPreview();
assertFrame(1, 40);
clock.advance(10);
send(snapshot(1, 41));
send(snapshot(1, 1, "run-2")); // Same sequence, different run: never reuse the old row.
const newRunRow = rowFor(1);
assert.notStrictEqual(newRunRow, firstRow);
assertFrame(1, 1);
clock.advance(100);
assertFrame(1, 1);
clock.advance(10);
send(snapshot(1, 2, "run-2"));
send(snapshot(1, 0, "run-2")); // Clearing the current run also cancels its pending frame.
clock.advance(100);
assert.equal(element("#live-latest-value").textContent, "--");
assert.equal(body.children.length, 1);
assert.equal(body.children[0].children[0].colSpan, 7);

// The unchanged SSE fallback still polls the same endpoint every second.
source.onerror();
const polling = [...clock.intervals.values()][0];
assert.equal(polling.delay, 1000);
globalThis.fetch = async (url) => {
  assert.equal(url, "/api/runs/current");
  return { ok: true, async text() { return JSON.stringify(snapshot(1, 3, "run-2", false)); } };
};
await polling.callback();
assertFrame(1, 3);
assert.equal(status.isRunActive(), false);
process.stdout.write(JSON.stringify({ ok: true }));
"""
    run_status_script(script)


@pytest.mark.frontend_node
@pytest.mark.skipif(NODE is None, reason="Node.js is required for LIVE UI runtime tests")
def test_live_table_reuses_rows_across_batches_and_5000_sample_windows():
    script = LIVE_TEST_SETUP + r"""
status.renderStatus(snapshot(1, 3));
const retained = rowFor(2);
buttonFor(2).click();
clock.advance(100);
status.renderStatus(snapshot(1, 6));
assertFrame(1, 6);
assert.strictEqual(rowFor(2), retained);
assert.equal(retained.classList.contains("is-selected"), true);
assert.equal(buttonFor(2).getAttribute("aria-expanded"), "true");
assert.equal(retained.children.length, 7);
assert.deepEqual(retained.children.slice(0, 6).map((cell) => cell.textContent), [
  "2", "2026-07-13 10:11:02", "2", "V", "software", "ok",
]);
const row4 = rowFor(4);
clock.advance(100);
status.renderStatus(snapshot(4, 12)); // Intermediate SSE snapshots were skipped.
assertFrame(4, 12);
assert.strictEqual(rowFor(4), row4);
assert.equal(retained.parentNode, null);
assert.equal(JSON.parse(element("#live-sample-details").textContent).sequence, 12);
assert.equal(buttonFor(12).getAttribute("aria-expanded"), "true");

status.renderStatus(snapshot(1, 5000, "large-run"));
const initialRows = new Map(body.children.map((row) => [row.dataset.sequence, row]));
buttonFor(2500).click();
clock.advance(100);
status.renderStatus(snapshot(4, 5003, "large-run"));
assert.deepEqual(sequences(), Array.from({ length: 5000 }, (_, index) => 5003 - index));
for (let sequence = 4; sequence <= 5000; sequence += 1) {
  assert.strictEqual(rowFor(sequence), initialRows.get(String(sequence)));
}
for (const sequence of [1, 2, 3]) assert.equal(initialRows.get(String(sequence)).parentNode, null);
assert.equal(JSON.parse(element("#live-sample-details").textContent).sequence, 2500);
assert.equal(buttonFor(2500).getAttribute("aria-expanded"), "true");
buttonFor(2500).click(); // The original retained button still closes the details.
assert.equal(element("#live-sample-metadata").classList.contains("is-hidden"), true);
clock.advance(100);
status.renderStatus(snapshot(6004, 11003, "large-run")); // Fully disjoint window.
assert.deepEqual(sequences(), Array.from({ length: 5000 }, (_, index) => 11003 - index));
assert.equal(initialRows.get("2500").parentNode, null);
buttonFor(11003).click();
assert.equal(JSON.parse(element("#live-sample-details").textContent).sequence, 11003);
assert.equal(body.children.every((row) => row.children.length === 7), true);
process.stdout.write(JSON.stringify({ ok: true }));
"""
    run_status_script(script)


def test_production_sources_keep_locale_out_of_runtime_contracts():
    sources = "\n".join(
        (STATIC_DIR / name).read_text(encoding="utf-8")
        for name in (
            "app.js",
            "status.js",
            "live_data.js",
            "presentation_i18n.js",
        )
    )
    for forbidden in (
        "status_key",
        "runtime_driver_note_key",
        "open_workflow_keys",
        "limit_keys",
        "pending_keys",
    ):
        assert forbidden not in sources
