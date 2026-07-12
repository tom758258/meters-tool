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


@pytest.mark.skipif(NODE is None, reason="Node.js is required for status runtime tests")
def test_status_and_live_data_render_translations_without_changing_raw_identity():
    script = r"""
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
  appendChild(child) { this.children.push(child); return child; }
  replaceChildren(...children) { this.children = children; }
  querySelector(selector) {
    if (selector === ".live-detail-button") {
      return this.children
        .flatMap((child) => [child, ...child.children])
        .find((child) => child.className === "live-detail-button") ?? null;
    }
    return null;
  }
  querySelectorAll(selector) {
    if (selector === "tr[data-sequence]") {
      return this.children.filter((child) => child.dataset.sequence !== undefined);
    }
    return [];
  }
  click() { this.listeners.get("click")?.({ target: this }); }
}

const elements = new Map();
function element(selector) {
  if (!elements.has(selector)) elements.set(selector, new FakeElement());
  return elements.get(selector);
}
const windowListeners = new Map();
globalThis.document = {
  querySelector: element,
  querySelectorAll() { return []; },
  createElement(tagName) { return new FakeElement(tagName); },
  createElementNS(_namespace, tagName) { return new FakeElement(tagName); },
};
globalThis.window = {
  addEventListener(name, listener) { windowListeners.set(name, listener); },
  setInterval() { return 1; },
  clearInterval() {},
};

element("#trigger-mode").value = "software";
const status = await import(statusUrl);
status.initializeStatusUi();

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

assert.equal(element("#status-state").textContent, "Running");
assert.equal(element("#status-state").getAttribute("data-i18n"), "status.running");
assert.equal(element("#fatal-error").textContent, "raw fatal TYPE_X");
assert.equal(element("#cleanup-status").textContent, "raw cleanup CODE_Y");
assert.equal(element("#raw-status").textContent, JSON.stringify(running, null, 2));
assert.equal(element("#live-data-summary").textContent, "1/5000 recent samples");
assert.equal(
  element("#live-data-summary").getAttribute("data-i18n"),
  "live_data.recent_sample_summary"
);

const latestLines = () => element("#latest-status").children;
assert.equal(latestLines().at(-1).textContent, "Ready");
assert.equal(latestLines().at(-1).getAttribute("data-i18n"), "status.ready");

const row = element("#live-samples-body").children[0];
assert.equal(row.children[5].textContent, "vendor-sample-status");
const detailsButton = row.children[6].children[0];
assert.equal(detailsButton.value, "");
assert.equal(detailsButton.textContent, "Details");
assert.equal(detailsButton.getAttribute("data-i18n"), "live_data.column_details");
assert.equal(
  detailsButton.getAttribute("data-i18n-aria-label"),
  "accessibility.toggle_sample_details"
);
detailsButton.click();
assert.equal(element("#live-selected-sample").textContent, "Sample #7");
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

status.renderStatus({ ...running, active: true });
const unloadEvent = { preventDefaultCalled: false, returnValue: "", preventDefault() {
  this.preventDefaultCalled = true;
} };
windowListeners.get("beforeunload")(unloadEvent);
assert.equal(unloadEvent.preventDefaultCalled, true);
assert.equal(
  unloadEvent.returnValue,
  "A measurement run is active. Refreshing or closing the page will not stop it."
);
process.stdout.write(JSON.stringify({ ok: true }));
"""
    completed = subprocess.run(
        [NODE, "--input-type=module", "--eval", script, (STATIC_DIR / "status.js").resolve().as_uri()],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, (
        "Node status/live-data localization contract failed\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert completed.stdout == '{"ok":true}'


def test_p24_production_sources_do_not_activate_locale_selection():
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
        "setLocale(",
        "navigator.language",
        "navigator.languages",
        "localStorage",
        "LOCALE_STORAGE_KEY",
        "status_key",
        "runtime_driver_note_key",
        "open_workflow_keys",
        "limit_keys",
        "pending_keys",
    ):
        assert forbidden not in sources
