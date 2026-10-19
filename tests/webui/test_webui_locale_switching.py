from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "src" / "meters_tool_webui" / "static"
NODE = shutil.which("node")


def run_node(script: str, *modules: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            NODE,
            "--input-type=module",
            "-",
            *(module.resolve().as_uri() for module in modules),
        ],
        cwd=REPO_ROOT,
        input="process.argv.splice(1, 1);\n" + script,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


APPLICATION_TEST_SETUP = r'''
import assert from "node:assert/strict";

const [appUrl] = process.argv.slice(1);

class FakeClassList {
  constructor() { this.values = new Set(); }
  add(name) { this.values.add(name); }
  remove(name) { this.values.delete(name); }
  toggle(name, force) {
    const enabled = force === undefined ? !this.values.has(name) : Boolean(force);
    if (enabled) this.values.add(name);
    else this.values.delete(name);
  }
  contains(name) { return this.values.has(name); }
}

class FakeElement {
  constructor() {
    this.value = "";
    this.textContent = "";
    this.checked = false;
    this.disabled = false;
    this.required = false;
    this.children = [];
    this.attributes = new Map();
    this.listeners = new Map();
    this.classList = new FakeClassList();
    this.dataset = {};
    this.clientWidth = 640;
    this.clientHeight = 760;
  }
  get options() { return this.children; }
  get selectedOptions() { return this.children.filter((child) => child.value === this.value); }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  removeAttribute(name) { this.attributes.delete(name); }
  addEventListener(name, listener) { this.listeners.set(name, listener); }
  appendChild(child) { this.children.push(child); return child; }
  replaceChildren(...children) { this.children = children; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  contains() { return false; }
  closest() { return null; }
  setCustomValidity(message) { this.validationMessage = message; }
  checkValidity() { return true; }
  reportValidity() { return true; }
  focus() { this.focused = true; }
  click() { this.listeners.get("click")?.({ target: this }); }
}

const elements = new Map();
function element(selector) {
  if (!elements.has(selector)) elements.set(selector, new FakeElement());
  return elements.get(selector);
}
function option(value, text, disabled = false) {
  const item = new FakeElement();
  item.value = value;
  item.textContent = text;
  item.disabled = disabled;
  return item;
}
function response(payload, ok = true, statusText = "OK") {
  return { ok, statusText, async text() { return JSON.stringify(payload); } };
}
function selectState(select) {
  return {
    count: select.options.length,
    values: select.options.map((item) => item.value),
    selected: select.value,
    disabled: select.options.map((item) => item.disabled),
  };
}
function optionByValue(select, value) {
  return select.options.find((item) => item.value === value);
}

const documentElement = new FakeElement();
const documentListeners = new Map();
const windowListeners = new Map();
const executionModeInputs = ["real", "simulate", "dry-run"].map((value) => {
  const input = new FakeElement();
  input.value = value;
  input.checked = value === "real";
  return input;
});
let intervalCalls = 0;
let eventSourceCalls = 0;
let reloadCalls = 0;
globalThis.document = {
  documentElement,
  querySelector: element,
  querySelectorAll(selector) {
    return selector === "[name='execution-mode']" ? executionModeInputs : [];
  },
  createElement: () => new FakeElement(),
  createElementNS: () => new FakeElement(),
  addEventListener(name, listener) { documentListeners.set(name, listener); },
};
globalThis.window = {
  localStorage: null,
  location: { reload() { reloadCalls += 1; } },
  addEventListener(name, listener) { windowListeners.set(name, listener); },
  setInterval() { intervalCalls += 1; return intervalCalls; },
  clearInterval() {},
};
Object.defineProperty(globalThis, "navigator", {
  configurable: true,
  value: { languages: ["en-US"], language: "en-US" },
});
globalThis.EventSource = class {
  constructor() { eventSourceCalls += 1; }
  addEventListener() {}
  close() {}
};

const measurementSelect = element("#measurement");
measurementSelect.replaceChildren(
  option("fallback-current", "Fallback current"),
  option("fallback-voltage", "Fallback voltage", true),
);
measurementSelect.value = "fallback-voltage";
const triggerSelect = element("#trigger-mode");
triggerSelect.replaceChildren(
  option("fallback-software", "Fallback software"),
  option("fallback-external", "Fallback external", true),
);
triggerSelect.value = "fallback-external";
element("#resource").value = "USB0::FALLBACK";
element("#instrument-model").value = "34461A";
element("[name='csv']").value = "C:\\meter\\fallback.csv";
element("[name='max_samples']").value = "23";
element("[name='timeout_ms']").value = "4321";
element("[name='auto_range']").checked = true;

const fallbackState = {
  measurement: selectState(measurementSelect),
  trigger: selectState(triggerSelect),
  resource: element("#resource").value,
  model: element("#instrument-model").value,
  csv: element("[name='csv']").value,
  maxSamples: element("[name='max_samples']").value,
  timeout: element("[name='timeout_ms']").value,
  autoRange: element("[name='auto_range']").checked,
};
'''


@pytest.mark.frontend_node
@pytest.mark.skipif(NODE is None, reason="Node.js is required for live Start tests")
def test_product_live_start_uses_detected_identity_and_core_support():
    from meters_tool_core.models import INSTRUMENT_PROFILES
    from meters_tool_webui._web_payloads import build_capabilities_payload

    payloads = {
        profile.model: build_capabilities_payload(
            profile, auto_unresolved=False, package_name="meters-tool", package_version="test"
        )
        for profile in INSTRUMENT_PROFILES
    }
    script = APPLICATION_TEST_SETUP + "\nconst payloads = " + json.dumps(payloads) + r''';
const idle = { active: false, state: "idle", captured: 0, errors: 0, recent_samples: [] };
const calls = [];
let resources = [];
let finishCapabilities;
let finishScan;
let finishStart;
let deferCapabilities = false;
let deferScan = false;
let deferStart = false;
globalThis.fetch = async (path, options) => {
  calls.push({ path: String(path), options });
  if (String(path).startsWith("/api/capabilities")) {
    const model = new URL(path, "http://test").searchParams.get("model") || "34461A";
    if (deferCapabilities) return new Promise((resolve) => { finishCapabilities = () => resolve(response(payloads[model])); });
    return response(payloads[model]);
  }
  if (String(path).startsWith("/api/resources")) {
    if (deferScan) return new Promise((resolve) => { finishScan = () => resolve(response({ resources })); });
    return response({ resources });
  }
  if (path === "/api/runs" && deferStart) return new Promise((resolve) => { finishStart = () => resolve(response(idle)); });
  return response(path === "/api/plan" ? { dry_run: true, scpi_commands: [] } : idle);
};
globalThis.FormData = class {
  get(name) { return {
    resource: element("#resource").value,
    visa_library: element("#visa-library").value,
    instrument_model: element("#instrument-model").value,
    measurement: measurementSelect.value, trigger_mode: triggerSelect.value,
    nplc: "1", auto_range: "on", max_samples: "1",
  }[name] ?? null; }
};
const event = (selector, name) => element(selector).listeners.get(name)();
const typeResource = (value) => { element("#resource").value = value; return event("#resource", "input"); };
const backend = async (value) => { element("#visa-library").value = value; await event("#visa-library", "change"); };
const expected = async (value) => { element("#instrument-model").value = value; await event("#instrument-model", "change"); };
const mode = async (value) => {
  for (const input of executionModeInputs) input.checked = input.value === value;
  await executionModeInputs.find((input) => input.checked).listeners.get("change")();
};
const start = () => event("#start-run", "click");
const requests = () => calls.filter((call) => call.path === "/api/runs" || call.path === "/api/plan");
const available = (value, label) => assert.equal(element("#start-run").disabled, !value, label);
element("#instrument-model").value = "";
deferCapabilities = true;
await import(appUrl);
available(false, "fallback controls cannot establish live support before capabilities arrive");
typeResource("USB0::EDIT-DURING-INITIAL-LOAD");
deferCapabilities = false;
finishCapabilities();
await new Promise((resolve) => setTimeout(resolve, 0));
const { renderStatus } = await import(new URL("./status.js", appUrl));
const { t } = await import(new URL("./i18n.js", appUrl));
const scan = () => event("#refresh-resources", "click");
const selectResource = async (resource) => { element("#resource-select").value = resource; await event("#resource-select", "change"); };

for (const [model, transport, library, allowed] of [
  ["34461A", "USB", "", true], ["34461A", "TCPIP", "", true],
  ["34461A", "TCPIP", "@py", true], ["34460A", "USB", "", true],
  ["34460A", "TCPIP", "", false], ["34460A", "TCPIP", "@py", false],
  ["34461A", "USB", "@py", false], ["34461A", "GPIB", "", false],
]) {
  await backend(library);
  const resource = `${transport}0::FAKE-${model}`;
  resources = [{ resource, instrument_model: model }];
  await scan();
  await selectResource(resource);
  available(allowed, `${model}/${transport}/${library}`);
  renderStatus(idle);
  available(allowed, "status refresh preserves support restriction");
  const before = requests().length;
  await start(); // Invoke the handler directly even if the button is disabled.
  assert.equal(requests().length, before + Number(allowed));
  if (!allowed) {
    assert.ok(element("#start-run").title);
    assert.ok(element("#latest-status").children.some((line) => line.textContent.includes(element("#start-run").title)));
  }
}

await backend("");
await expected("34460A");
for (const resource of ["USB0::MANUAL", "TCPIP0::MANUAL"]) {
  typeResource(resource);
  available(true, "Expected Model is not detected IDN");
  await start();
}
await expected("");
await start();
assert.equal("instrument_model" in JSON.parse(requests().at(-1).options.body), false);
assert.equal(requests().at(-1).path, "/api/runs");
await backend("@py");
typeResource("USB0::MANUAL");
available(false, "unknown USB/@py cannot be approved");
await mode("simulate");
await expected("34460A");
available(true, "simulation ignores live connection restrictions");
await start();
assert.equal(JSON.parse(requests().at(-1).options.body).simulate, true);
await mode("dry-run");
available(true, "dry-run ignores live connection restrictions");
await start();
assert.equal(requests().at(-1).path, "/api/plan");
await mode("real");
available(false, "returning to Real restores restriction");

await backend("");
await expected("");
resources = [
  { resource: "USB0::KNOWN", instrument_model: "34460A" },
  { resource: "TCPIP0::KNOWN", instrument_model: "34460A" },
];
await scan();
await selectResource("TCPIP0::KNOWN");
available(false, "detected model is authoritative");
await expected("34461A");
available(false, "Expected Model cannot override detected identity");
await mode("simulate");
deferCapabilities = true;
const returningToReal = mode("real");
available(false, "known unsupported identity is restored before capabilities finish");
deferCapabilities = false;
finishCapabilities();
await returningToReal;
typeResource("TCPIP0::NEW");
available(true, "new resource does not inherit old identity");
await selectResource("USB0::KNOWN");
triggerSelect.value = "external";
await event("#trigger-mode", "change");
available(false, "unapproved trigger blocks Start");
await start();
assert.equal(element("#start-run").title, t("support.reason.scope_unavailable"));
element("#locale-toggle").click();
assert.equal(documentElement.lang, "zh-TW");
assert.equal(element("#start-run").title, t("support.reason.scope_unavailable"));
triggerSelect.value = "immediate";
await event("#trigger-mode", "change");
available(true, "supported trigger restores Start");
measurementSelect.value = "unapproved-measurement";
await event("#measurement", "change");
available(false, "unapproved measurement blocks Start");
const blockedCount = requests().length;
await start();
assert.equal(requests().length, blockedCount);
measurementSelect.value = "voltage-dc";
await event("#measurement", "change");
available(true, "supported measurement restores Start");

deferCapabilities = true;
const oldSelection = selectResource("TCPIP0::KNOWN");
typeResource("USB0::NEW");
finishCapabilities();
await oldSelection;
available(true, "late capability response cannot restore old identity");
deferCapabilities = false;
deferScan = true;
const oldScan = scan();
typeResource("TCPIP0::MANUAL-AFTER-SCAN");
resources = [{ resource: "TCPIP0::MANUAL-AFTER-SCAN", instrument_model: "34460A" }];
finishScan();
await oldScan;
available(true, "late scan cannot attach identity after a resource edit");
deferScan = false;
deferStart = true;
const pending = start();
available(false, "pending submission blocks duplicate Start");
const pendingCount = requests().length;
await start();
renderStatus(idle);
available(false, "idle SSE cannot unlock pending Start");
assert.equal(requests().length, pendingCount);
finishStart();
await pending;
available(true, "completion clears pending lock");
renderStatus({ ...idle, active: true });
available(false, "active run blocks Start");
await start();
assert.equal(requests().length, pendingCount);
renderStatus(idle);
available(true, "inactive status restores valid Start");
await backend("@unsupported");
typeResource("TCPIP0::MANUAL");
available(false, "an unrecognized backend must not inherit System VISA support");
const unsupportedCount = requests().length;
await start();
assert.equal(requests().length, unsupportedCount);

await backend("");
typeResource("USB0::MANUAL");
// Features must be approved together by one candidate model, not across models.
for (const scope of payloads["34461A"].support["start-trigger-record"].live.scopes) {
  scope.features.measurement["voltage-dc"].validation_status = "feature_pending";
}
for (const scope of payloads["34460A"].support["start-trigger-record"].live.scopes) {
  scope.features.trigger_mode.immediate.validation_status = "feature_pending";
}
await expected("34461A");
await expected("34460A");
measurementSelect.value = "voltage-dc";
triggerSelect.value = "immediate";
await event("#measurement", "change");
available(false, "no candidate approves both features");
const pendingFeatureCount = requests().length;
await start();
assert.equal(requests().length, pendingFeatureCount);
resources = [{ resource: "USB0::PENDING-FEATURE", instrument_model: "34461A" }];
await scan();
await selectResource(resources[0].resource);
measurementSelect.value = "voltage-dc";
await event("#measurement", "change");
available(false, "known pending measurement blocks Start");
assert.equal(element("#start-run").title, t("support.reason.pending_live_validation"));
'''
    completed = run_node(script, STATIC_DIR / "app.js")
    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.skipif(NODE is None, reason="Node.js is required for execution-mode tests")
def test_execution_mode_pending_lock_and_real_resource_isolation():
    script = APPLICATION_TEST_SETUP + r'''
const capabilities = {
  app: { version: "2.0.0" },
  limits: {},
  support_summary: null,
  support: {
    "start-trigger-record": {
      live: {
        transport_scope: "usb",
        scopes: [
          {
            transport_scope: "usb",
            backend_scope: "system_visa",
            validation_status: "live_validated_full_suite",
            features: {
              measurement: {
                "current-dc": { validation_status: "live_validated_full_suite" },
                "voltage-dc": { validation_status: "live_validated_full_suite" },
              },
              trigger_mode: { immediate: { validation_status: "live_validated_full_suite" } },
            },
          },
          {
            transport_scope: "tcpip",
            backend_scope: "system_visa",
            validation_status: "live_validated_full_suite",
            features: {
              measurement: {
                "current-dc": { validation_status: "live_validated_full_suite" },
                "voltage-dc": { validation_status: "feature_pending" },
              },
              trigger_mode: { immediate: { validation_status: "live_validated_full_suite" } },
            },
          },
        ],
      },
    },
  },
  available_profiles: [{ model: "34460A" }, { model: "34461A" }],
  measurements: [
    { name: "current-dc", unit: "A", nplc_options: [1], range_options: [], defaults: {} },
    { name: "voltage-dc", unit: "V", nplc_options: [1], range_options: [], defaults: {} },
  ],
  trigger_modes: ["immediate"],
  trigger_mode_metadata: { immediate: { uses_trigger_timeout: false } },
};
const inactiveStatus = {
  run_id: null,
  state: "idle",
  active: false,
  captured: 0,
  errors: 0,
  csv_path: null,
  latest_status: "idle",
  recent_samples: [],
  latest_sample: null,
  sample_capacity: 100,
};
function deferred() {
  let resolve;
  const promise = new Promise((complete) => { resolve = complete; });
  return { promise, resolve };
}
let runRequest = deferred();
let planRequest = deferred();
let runRequestCount = 0;
let planRequestCount = 0;
globalThis.fetch = async (path) => {
  const target = String(path);
  if (target.includes("/api/capabilities")) return response(capabilities);
  if (target === "/api/runs") {
    runRequestCount += 1;
    return runRequest.promise;
  }
  if (target === "/api/plan") {
    planRequestCount += 1;
    return planRequest.promise;
  }
  return response(inactiveStatus);
};
globalThis.FormData = class {
  get(name) {
    const values = {
      resource: element("#resource").value,
      instrument_model: element("#instrument-model").value,
      trigger_mode: element("#trigger-mode").value,
      measurement: element("#measurement").value,
      nplc: "1",
      auto_range: "on",
      max_samples: "1",
    };
    return values[name] ?? null;
  }
};

element("#resource").value = "TCPIP0::REAL::INSTR";
element("#instrument-model").value = "34461A";
element("#measurement").value = "voltage-dc";
element("#trigger-mode").value = "immediate";

await import(appUrl);
await new Promise((resolve) => setTimeout(resolve, 0));
const status = await import(new URL("./status.js", appUrl));
const mode = (value) => executionModeInputs.find((input) => input.value === value);
const changeMode = async (value) => {
  mode(value).checked = true;
  await mode(value).listeners.get("change")();
};

assert.equal(optionByValue(element("#measurement"), "voltage-dc").disabled, true);
await changeMode("simulate");
assert.equal(element("#resource").value, "");
assert.equal(optionByValue(element("#measurement"), "voltage-dc").disabled, false);
await changeMode("real");
assert.equal(element("#resource").value, "TCPIP0::REAL::INSTR");

const start = element("#start-run").listeners.get("click");
const pendingRun = start();
await new Promise((resolve) => setTimeout(resolve, 0));
assert.equal(runRequestCount, 1);
assert.equal(element("#start-run").disabled, true);
assert.equal(executionModeInputs.every((input) => input.disabled), true);
status.renderStatus(inactiveStatus);
assert.equal(element("#start-run").disabled, true);
assert.equal(executionModeInputs.every((input) => input.disabled), true);
await start();
assert.equal(runRequestCount, 1);
await changeMode("dry-run");
assert.equal(mode("real").checked, true);
assert.equal(element("#resource").value, "TCPIP0::REAL::INSTR");

const runningStatus = { ...inactiveStatus, run_id: "run-1", state: "running", active: true };
runRequest.resolve(response(runningStatus));
await pendingRun;
assert.match(element("#raw-status").textContent, /"run_id": "run-1"/);
assert.equal(element("#dry-run-plan-result").classList.contains("is-hidden"), true);

status.renderStatus(inactiveStatus);
await changeMode("dry-run");
assert.equal(element("#resource").value, "");
const pendingPlan = start();
await new Promise((resolve) => setTimeout(resolve, 0));
assert.equal(planRequestCount, 1);
await changeMode("real");
assert.equal(mode("dry-run").checked, true);
planRequest.resolve(response({ dry_run: true, simulate: false, scpi_commands: [] }));
await pendingPlan;
assert.match(element("#dry-run-plan").textContent, /"dry_run": true/);
assert.equal(element("#dry-run-plan-result").classList.contains("is-hidden"), false);
assert.equal(element("#start-run").disabled, false);
assert.equal(executionModeInputs.every((input) => !input.disabled), true);

await changeMode("real");
assert.equal(element("#resource").value, "TCPIP0::REAL::INSTR");
process.stdout.write(JSON.stringify({ ok: true }));
'''
    completed = run_node(script, STATIC_DIR / "app.js")
    assert completed.returncode == 0, (
        "Execution-mode pending/resource regression failed\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert completed.stdout == '{"ok":true}'


@pytest.mark.skipif(NODE is None, reason="Node.js is required for locale runtime tests")
def test_locale_resolution_and_storage_contract():
    script = r'''
import assert from "node:assert/strict";

const [localeUiUrl, domI18nUrl] = process.argv.slice(1);
const guardedGlobals = [
  "document", "window", "navigator", "localStorage", "fetch", "XMLHttpRequest", "EventSource",
];
const globalAccesses = [];
for (const name of guardedGlobals) {
  Object.defineProperty(globalThis, name, {
    configurable: true,
    get() {
      globalAccesses.push(name);
      throw new Error(`unexpected global access: ${name}`);
    },
  });
}

const localeUi = await import(localeUiUrl);
const domI18n = await import(domI18nUrl);
const i18n = await import(new URL("./i18n.js", localeUiUrl));
assert.deepEqual(globalAccesses, []);
assert.deepEqual(localeUi.SUPPORTED_LOCALES, ["en", "zh-TW"]);
assert.equal(localeUi.LOCALE_STORAGE_KEY, "meters-tool.webui.locale");

for (const value of ["zh-TW", "ZH_tw", "zh-Hant", "zh_hAnT_TW", "zh-TW-x-test", "zh-Hant-TW-x-test"]) {
  assert.equal(localeUi.browserLocaleToSupportedLocale(value), "zh-TW");
}
for (const value of ["zh", "en-US", "fr-FR", "", null, undefined, 3]) {
  assert.equal(localeUi.browserLocaleToSupportedLocale(value), "en");
}

assert.equal(localeUi.detectBrowserLocale({ languages: ["zh-Hant", "en-US"], language: "en-US" }), "zh-TW");
assert.equal(localeUi.detectBrowserLocale({ languages: ["en-US", "zh-TW"], language: "zh-TW" }), "en");
assert.equal(localeUi.detectBrowserLocale({ languages: [], language: "zh-Hant" }), "zh-TW");
assert.equal(localeUi.detectBrowserLocale({ language: "zh-TW" }), "zh-TW");
assert.equal(localeUi.detectBrowserLocale({ languages: [null, ""], language: "fr" }), "en");
assert.equal(localeUi.detectBrowserLocale({}), "en");

class Storage {
  constructor(value = null, throwOnRead = false, throwOnWrite = false) {
    this.value = value;
    this.throwOnRead = throwOnRead;
    this.throwOnWrite = throwOnWrite;
    this.readKeys = [];
    this.writes = [];
  }
  getItem(key) {
    this.readKeys.push(key);
    if (this.throwOnRead) throw new Error("storage read failed");
    return this.value;
  }
  setItem(key, value) {
    if (this.throwOnWrite) throw new Error("storage write failed");
    this.writes.push([key, value]);
  }
}

const savedZh = new Storage("zh-TW");
assert.equal(
  localeUi.resolveInitialLocale({ storage: savedZh, navigatorLike: { language: "en-US" } }),
  "zh-TW",
);
assert.deepEqual(savedZh.readKeys, ["meters-tool.webui.locale"]);
assert.deepEqual(savedZh.writes, []);

const savedEn = new Storage("en");
assert.equal(
  localeUi.resolveInitialLocale({ storage: savedEn, navigatorLike: { language: "zh-TW" } }),
  "en",
);
assert.equal(
  localeUi.resolveInitialLocale({ storage: new Storage("fr"), navigatorLike: { language: "zh-TW" } }),
  "zh-TW",
);
assert.equal(
  localeUi.resolveInitialLocale({ storage: new Storage(null, true), navigatorLike: { language: "zh-TW" } }),
  "zh-TW",
);

const keyOnlyStorage = new Storage(null);
assert.equal(localeUi.persistLocale(keyOnlyStorage, "zh-TW"), true);
assert.deepEqual(keyOnlyStorage.writes, [["meters-tool.webui.locale", "zh-TW"]]);
assert.equal(localeUi.persistLocale(keyOnlyStorage, "ZH-tw"), false);
assert.deepEqual(keyOnlyStorage.writes, [["meters-tool.webui.locale", "zh-TW"]]);
assert.equal(localeUi.persistLocale(null, "zh-TW"), false);
assert.equal(localeUi.persistLocale({}, "zh-TW"), false);
assert.equal(localeUi.persistLocale(new Storage(null, false, true), "en"), false);

class FakeElement {
  constructor() {
    this.attributes = new Map();
    this.listeners = new Map();
    this.textContent = "";
    this.lang = "";
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  removeAttribute(name) { this.attributes.delete(name); }
  addEventListener(name, listener) { this.listeners.set(name, listener); }
  click() { this.listeners.get("click")?.(); }
}

const button = new FakeElement();
const label = new FakeElement();
const documentElement = { lang: "en" };
const storage = new Storage(null);
let refreshCount = 0;
assert.equal(
  localeUi.initializeLocaleUi({
    button,
    label,
    documentElement,
    storage,
    navigatorLike: { language: "en-US" },
    onLocaleChange: () => { refreshCount += 1; },
  }),
  "en",
);
assert.equal(label.getAttribute("data-i18n"), "locale.display_en");
assert.equal(label.lang, "en");
assert.equal(label.textContent, i18n.t("locale.display_en"));
assert.equal(button.getAttribute("data-i18n"), null);
assert.equal(button.getAttribute("data-i18n-aria-label"), "accessibility.switch_language_to_zh_tw");
assert.equal(button.getAttribute("data-i18n-title"), "accessibility.switch_language_to_zh_tw");
assert.equal(button.getAttribute("title"), i18n.t("accessibility.switch_language_to_zh_tw"));
assert.equal(button.getAttribute("title"), button.getAttribute("aria-label"));

const firstRenderStorage = new Storage("zh-TW");
const firstRenderButton = new FakeElement();
const firstRenderLabel = new FakeElement();
const firstRenderDocument = { lang: "en" };
localeUi.initializeLocaleUi({
  button: firstRenderButton,
  label: firstRenderLabel,
  documentElement: firstRenderDocument,
  storage: firstRenderStorage,
  navigatorLike: { language: "en-US" },
});
const firstRenderText = new FakeElement();
firstRenderText.setAttribute("data-i18n", "app.unofficial_tool");
domI18n.applyStaticTranslations({ querySelectorAll: () => [firstRenderText] });
assert.equal(firstRenderDocument.lang, "zh-TW");
assert.equal(i18n.getLocale(), "zh-TW");
assert.equal(firstRenderText.textContent, i18n.t("app.unofficial_tool"));

localeUi.initializeLocaleUi({
  button,
  label,
  documentElement,
  storage: new Storage("en"),
  navigatorLike: { language: "en-US" },
  onLocaleChange: () => { refreshCount += 1; },
});
button.click();
assert.equal(documentElement.lang, "zh-TW");
assert.equal(label.getAttribute("data-i18n"), "locale.display_zh_tw");
assert.equal(label.lang, "zh-TW");
assert.equal(label.textContent, i18n.t("locale.display_zh_tw"));
assert.equal(button.getAttribute("data-i18n-aria-label"), "accessibility.switch_language_to_en");
assert.equal(button.getAttribute("data-i18n-title"), "accessibility.switch_language_to_en");
assert.equal(button.getAttribute("title"), i18n.t("accessibility.switch_language_to_en"));
assert.equal(button.getAttribute("title"), button.getAttribute("aria-label"));
assert.deepEqual(storage.writes, [["meters-tool.webui.locale", "zh-TW"]]);
assert.equal(refreshCount, 1);

const writeFailButton = new FakeElement();
const writeFailLabel = new FakeElement();
const writeFailDocument = { lang: "en" };
let writeFailRefreshCount = 0;
localeUi.initializeLocaleUi({
  button: writeFailButton,
  label: writeFailLabel,
  documentElement: writeFailDocument,
  storage: new Storage(null, false, true),
  navigatorLike: { language: "en-US" },
  onLocaleChange: () => { writeFailRefreshCount += 1; },
});
writeFailButton.click();
assert.equal(writeFailDocument.lang, "zh-TW");
assert.equal(writeFailRefreshCount, 1);

const noStorageButton = new FakeElement();
const noStorageLabel = new FakeElement();
const noStorageDocument = { lang: "en" };
let noStorageRefreshCount = 0;
localeUi.initializeLocaleUi({
  button: noStorageButton,
  label: noStorageLabel,
  documentElement: noStorageDocument,
  storage: null,
  navigatorLike: { language: "en-US" },
  onLocaleChange: () => { noStorageRefreshCount += 1; },
});
noStorageButton.click();
assert.equal(noStorageDocument.lang, "zh-TW");
assert.equal(noStorageRefreshCount, 1);

const duplicateButton = new FakeElement();
const duplicateLabel = new FakeElement();
const duplicateDocument = { lang: "en" };
let duplicateRefreshCount = 0;
localeUi.initializeLocaleUi({
  button: duplicateButton,
  label: duplicateLabel,
  documentElement: duplicateDocument,
  navigatorLike: { language: "en-US" },
  onLocaleChange: () => { duplicateRefreshCount += 1; },
});
localeUi.initializeLocaleUi({
  button: duplicateButton,
  label: duplicateLabel,
  documentElement: duplicateDocument,
  navigatorLike: { language: "en-US" },
  onLocaleChange: () => { duplicateRefreshCount += 100; },
});
assert.equal(duplicateButton.listeners.size, 1);
duplicateButton.click();
assert.equal(duplicateRefreshCount, 1);

process.stdout.write(JSON.stringify({ ok: true }));
'''
    completed = run_node(script, STATIC_DIR / "locale_ui.js", STATIC_DIR / "dom_i18n.js")
    assert completed.returncode == 0, (
        "Node locale resolution contract failed\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert completed.stdout == '{"ok":true}'


def test_locale_toggle_static_machine_contract():
    index = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    assert index.count('id="locale-toggle"') == 1
    assert re.search(
        r'<button\b(?=[^>]*\bid="locale-toggle")'
        r'(?=[^>]*\btype="button")'
        r'(?=[^>]*\bdata-i18n-aria-label="accessibility\.switch_language_to_zh_tw")'
        r'(?=[^>]*\bdata-i18n-title="accessibility\.switch_language_to_zh_tw")'
        r'(?=[^>]*\btitle="Switch language to Traditional Chinese")'
        r"[^>]*>",
        index,
    )
    assert re.search(
        r'<span\b(?=[^>]*\bid="locale-toggle-label")'
        r'(?=[^>]*\blang="en")'
        r'(?=[^>]*\bdata-i18n="locale\.display_en")'
        r"[^>]*>",
        index,
    )
    assert re.search(
        r"<svg\b(?=[^>]*\baria-hidden=\"true\")"
        r"(?=[^>]*\bfocusable=\"false\")[^>]*>",
        index,
    )


@pytest.mark.skipif(NODE is None, reason="Node.js is required for application locale tests")
def test_application_locale_switch_uses_cached_presentation_without_runtime_requests():
    script = r'''
import assert from "node:assert/strict";

const [appUrl] = process.argv.slice(1);

class FakeClassList {
  constructor() { this.values = new Set(); }
  add(name) { this.values.add(name); }
  remove(name) { this.values.delete(name); }
  toggle(name, force) {
    const enabled = force === undefined ? !this.values.has(name) : Boolean(force);
    if (enabled) this.values.add(name);
    else this.values.delete(name);
  }
  contains(name) { return this.values.has(name); }
}

class FakeElement {
  constructor() {
    this.value = "";
    this.textContent = "";
    this.checked = false;
    this.disabled = false;
    this.required = false;
    this.children = [];
    this.attributes = new Map();
    this.listeners = new Map();
    this.classList = new FakeClassList();
    this.dataset = {};
    this.clientWidth = 640;
    this.clientHeight = 760;
  }
  get options() { return this.children; }
  get selectedOptions() { return this.children.filter((child) => child.value === this.value); }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  removeAttribute(name) { this.attributes.delete(name); }
  addEventListener(name, listener) { this.listeners.set(name, listener); }
  appendChild(child) { this.children.push(child); return child; }
  replaceChildren(...children) { this.children = children; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  contains() { return false; }
  closest() { return null; }
  setCustomValidity() {}
  click() { this.listeners.get("click")?.({ target: this }); }
}

const elements = new Map();
function element(selector) {
  if (!elements.has(selector)) elements.set(selector, new FakeElement());
  return elements.get(selector);
}
function resourceOption(value) {
  return element("#resource-select").options.find((item) => item.value === value);
}
const documentElement = new FakeElement();
const documentListeners = new Map();
const windowListeners = new Map();
let intervalCalls = 0;
let eventSourceCalls = 0;
globalThis.document = {
  documentElement,
  querySelector: element,
  querySelectorAll: () => [],
  createElement: () => new FakeElement(),
  createElementNS: () => new FakeElement(),
  addEventListener(name, listener) { documentListeners.set(name, listener); },
};
globalThis.window = {
  localStorage: undefined,
  addEventListener(name, listener) { windowListeners.set(name, listener); },
  setInterval() { intervalCalls += 1; return intervalCalls; },
  clearInterval() {},
};
Object.defineProperty(globalThis, "navigator", {
  configurable: true,
  value: { languages: ["en-US"], language: "en-US" },
});
globalThis.EventSource = class {
  constructor() { eventSourceCalls += 1; }
  addEventListener() {}
  close() {}
};

const capabilities = {
  app: { version: "2.0.0" },
  limits: {},
  support_summary: null,
  support: { "start-trigger-record": { live: null } },
  available_profiles: [],
  supported_devices: [
    { vendor: "Keysight", model: "34461A", connections: ["usb", "tcpip"], backend_connections: { system_visa: ["usb", "tcpip"], pyvisa_py: ["tcpip"] } },
    { vendor: "Keysight", model: "34460A", connections: ["usb"], backend_connections: { system_visa: ["usb"] } },
  ],
  measurements: [{ name: "current-dc", unit: "A", nplc_options: [], range_options: [], defaults: {} }],
  trigger_modes: ["software"],
};
const currentStatus = {
  run_id: "run-1",
  state: "running",
  active: false,
  captured: 2,
  errors: 0,
  csv_path: "",
  latest_status: "ready",
  recent_samples: [],
  latest_sample: null,
  sample_capacity: 100,
};
let fetchCalls = 0;
globalThis.fetch = async (path) => {
  fetchCalls += 1;
  let payload = currentStatus;
  if (String(path).includes("/api/capabilities")) {
    payload = capabilities;
  } else if (String(path).includes("/api/resources")) {
    payload = {
      resources: [
        { resource: "USB0::SIM", status: "live", detail: "raw detail", instrument_model: "34461A" },
        { resource: "USB0::RAW", status: "vendor-status", detail: "raw vendor detail", instrument_model: null },
      ],
    };
  }
  return { ok: true, statusText: "OK", async text() { return JSON.stringify(payload); } };
};

element("#resource").value = "USB0::SIM";
element("#measurement").value = "current-dc";
element("#trigger-mode").value = "software";
element("[name='csv']").value = "C:\\meter\\output.csv";
element("[name='max_samples']").value = "10";
element("#stop-run").disabled = true;

await import(appUrl);
await new Promise((resolve) => setTimeout(resolve, 0));
element("#refresh-resources").click();
await new Promise((resolve) => setTimeout(resolve, 0));
element("#resource-select").value = "USB0::SIM";
const readyFetchCalls = fetchCalls;
const readyIntervalCalls = intervalCalls;
const readyEventSourceCalls = eventSourceCalls;
const beforeSwitch = {
  resource: element("#resource").value,
  measurement: element("#measurement").value,
  triggerMode: element("#trigger-mode").value,
  csv: element("[name='csv']").value,
  active: element("#stop-run").disabled === false,
};
assert.equal(
  element("#locale-toggle-label").getAttribute("data-i18n"),
  "locale.display_en"
);
assert.equal(documentElement.lang, "en");
assert.equal(
  resourceOption("USB0::SIM").getAttribute("data-i18n"),
  "resource.option_with_detail"
);
assert.match(resourceOption("USB0::RAW").textContent, /raw vendor detail/);
const supportedRows = element("#supported-devices-body").children;
assert.equal(supportedRows.length, 2);
assert.deepEqual(
  supportedRows.map((row) => row.children.map((cell) => cell.textContent)),
  [
    ["34461A", "USB, LAN"],
    ["34460A", "USB"],
  ]
);

element("#locale-toggle").click();
assert.equal(documentElement.lang, "zh-TW");
assert.equal(
  element("#locale-toggle-label").getAttribute("data-i18n"),
  "locale.display_zh_tw"
);
assert.equal(
  element("#locale-toggle").getAttribute("data-i18n-aria-label"),
  "accessibility.switch_language_to_en"
);
assert.equal(element("#status-state").getAttribute("data-i18n"), "status.running");
assert.equal(element("#resource-select").value, "USB0::SIM");
assert.equal(
  resourceOption("USB0::SIM").getAttribute("data-i18n"),
  "resource.option_with_detail"
);
assert.match(resourceOption("USB0::RAW").textContent, /raw vendor detail/);
assert.deepEqual(
  element("#supported-devices-body").children.map(
    (row) => row.children.map((cell) => cell.textContent)
  ),
  [
    ["34461A", "USB、LAN"],
    ["34460A", "USB"],
  ]
);
assert.deepEqual(
  {
    resource: element("#resource").value,
    measurement: element("#measurement").value,
    triggerMode: element("#trigger-mode").value,
    csv: element("[name='csv']").value,
    active: element("#stop-run").disabled === false,
  },
  beforeSwitch,
);
assert.equal(fetchCalls, readyFetchCalls);
assert.equal(intervalCalls, readyIntervalCalls);
assert.equal(eventSourceCalls, readyEventSourceCalls);
process.stdout.write(JSON.stringify({ ok: true }));
'''
    completed = run_node(script, STATIC_DIR / "app.js")
    assert completed.returncode == 0, (
        "Node application locale refresh contract failed\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert completed.stdout == '{"ok":true}'


@pytest.mark.skipif(NODE is None, reason="Node.js is required for application locale tests")
def test_application_locale_switch_preserves_fallbacks_while_capabilities_are_pending():
    script = APPLICATION_TEST_SETUP + r'''
const capabilities = {
  app: { version: "2.0.0" },
  limits: {},
  support_summary: {
    model: "34461A",
    validation_status: "live_validated_full_suite",
    status_text: "Cached support status",
    open_workflows: ["software"],
    limits: [],
    pending: [],
  },
  support: {
    "start-trigger-record": {
      live: {
        scopes: [{
          transport_scope: "usb",
          backend_scope: "system_visa",
          validation_status: "live_validated_full_suite",
          features: {
            measurement: {
              "current-dc": { validation_status: "live_validated_full_suite" },
              "voltage-dc": { validation_status: "feature_pending" },
            },
            trigger_mode: {
              software: { validation_status: "live_validated_full_suite" },
              external: { validation_status: "not_supported_by_model" },
            },
          },
        }],
      },
    },
  },
  available_profiles: [{ model: "34461A" }],
  measurements: [
    { name: "current-dc", unit: "A", nplc_options: [], range_options: [], defaults: {} },
    { name: "voltage-dc", unit: "V", nplc_options: [], range_options: [], defaults: {} },
  ],
  trigger_modes: ["software", "external"],
};
const currentStatus = {
  state: "idle", active: false, captured: 0, errors: 0, csv_path: "",
  latest_status: "idle", recent_samples: [], latest_sample: null, sample_capacity: 100,
};
let fetchCalls = 0;
let resolveCapabilities;
globalThis.fetch = (path) => {
  fetchCalls += 1;
  if (String(path).includes("/api/capabilities")) {
    return new Promise((resolve) => { resolveCapabilities = resolve; });
  }
  return Promise.resolve(response(currentStatus));
};

await import(appUrl);
await new Promise((resolve) => setTimeout(resolve, 0));
assert.equal(fetchCalls, 1);
assert.deepEqual(selectState(measurementSelect), fallbackState.measurement);
assert.deepEqual(selectState(triggerSelect), fallbackState.trigger);
const beforeSwitchFetchCalls = fetchCalls;
const beforeSwitchIntervalCalls = intervalCalls;
const beforeSwitchEventSourceCalls = eventSourceCalls;

element("#locale-toggle").click();
assert.equal(documentElement.lang, "zh-TW");
assert.equal(
  element("#locale-toggle-label").getAttribute("data-i18n"),
  "locale.display_zh_tw"
);
assert.equal(
  element("#locale-toggle").getAttribute("data-i18n-aria-label"),
  "accessibility.switch_language_to_en"
);
assert.deepEqual(selectState(measurementSelect), fallbackState.measurement);
assert.deepEqual(selectState(triggerSelect), fallbackState.trigger);
assert.deepEqual(
  {
    resource: element("#resource").value,
    model: element("#instrument-model").value,
    csv: element("[name='csv']").value,
    maxSamples: element("[name='max_samples']").value,
    timeout: element("[name='timeout_ms']").value,
    autoRange: element("[name='auto_range']").checked,
  },
  {
    resource: fallbackState.resource,
    model: fallbackState.model,
    csv: fallbackState.csv,
    maxSamples: fallbackState.maxSamples,
    timeout: fallbackState.timeout,
    autoRange: fallbackState.autoRange,
  },
);
assert.equal(fetchCalls, beforeSwitchFetchCalls);
assert.equal(intervalCalls, beforeSwitchIntervalCalls);
assert.equal(eventSourceCalls, beforeSwitchEventSourceCalls);
assert.equal(reloadCalls, 0);

resolveCapabilities(response(capabilities));
await new Promise((resolve) => setTimeout(resolve, 0));
await new Promise((resolve) => setTimeout(resolve, 0));
assert.deepEqual(measurementSelect.options.map((item) => item.value), ["current-dc", "voltage-dc"]);
assert.deepEqual(triggerSelect.options.map((item) => item.value), ["software", "external"]);
assert.equal(measurementSelect.value, "current-dc");
assert.equal(triggerSelect.value, "software");
assert.equal(
  optionByValue(measurementSelect, "current-dc").getAttribute("data-i18n"),
  "measurement.option_label"
);
assert.equal(
  optionByValue(triggerSelect, "software").getAttribute("data-i18n"),
  "trigger.option_label"
);
assert.equal(optionByValue(measurementSelect, "voltage-dc").disabled, true);
assert.equal(optionByValue(triggerSelect, "external").disabled, true);
assert.equal(intervalCalls, 1);
assert.equal(eventSourceCalls, 1);

measurementSelect.value = "voltage-dc";
triggerSelect.value = "external";
const readyFormState = {
  measurement: selectState(measurementSelect),
  trigger: selectState(triggerSelect),
  resource: element("#resource").value,
  model: element("#instrument-model").value,
  csv: element("[name='csv']").value,
  maxSamples: element("[name='max_samples']").value,
  timeout: element("[name='timeout_ms']").value,
  autoRange: element("[name='auto_range']").checked,
};
const readyFetchCalls = fetchCalls;
const readyIntervalCalls = intervalCalls;
const readyEventSourceCalls = eventSourceCalls;
element("#locale-toggle").click();
assert.equal(documentElement.lang, "en");
assert.deepEqual(
  {
    measurement: selectState(measurementSelect),
    trigger: selectState(triggerSelect),
    resource: element("#resource").value,
    model: element("#instrument-model").value,
    csv: element("[name='csv']").value,
    maxSamples: element("[name='max_samples']").value,
    timeout: element("[name='timeout_ms']").value,
    autoRange: element("[name='auto_range']").checked,
  },
  readyFormState,
);
assert.equal(optionByValue(measurementSelect, "voltage-dc").disabled, true);
assert.equal(optionByValue(triggerSelect, "external").disabled, true);
assert.equal(
  optionByValue(measurementSelect, "voltage-dc").getAttribute("data-i18n-title"),
  "support.reason.pending_live_validation"
);
assert.equal(
  optionByValue(triggerSelect, "external").getAttribute("data-i18n-title"),
  "support.reason.not_supported_by_model"
);
assert.equal(element("#model-support-status").textContent.includes("Cached support status"), true);
assert.equal(fetchCalls, readyFetchCalls);
assert.equal(intervalCalls, readyIntervalCalls);
assert.equal(eventSourceCalls, readyEventSourceCalls);
assert.equal(reloadCalls, 0);
process.stdout.write(JSON.stringify({ ok: true }));
'''
    completed = run_node(script, STATIC_DIR / "app.js")
    assert completed.returncode == 0, (
        "Deferred capabilities locale-switch contract failed\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert completed.stdout == '{"ok":true}'


@pytest.mark.skipif(NODE is None, reason="Node.js is required for application locale tests")
def test_application_locale_switch_preserves_fallbacks_after_capabilities_failure():
    script = APPLICATION_TEST_SETUP + r'''
let fetchCalls = 0;
globalThis.fetch = async (path) => {
  fetchCalls += 1;
  assert.equal(String(path).includes("/api/capabilities"), true);
  return response({ detail: "capabilities unavailable" }, false, "Service Unavailable");
};

await import(appUrl);
await new Promise((resolve) => setTimeout(resolve, 0));
await new Promise((resolve) => setTimeout(resolve, 0));
assert.equal(fetchCalls, 1);
assert.deepEqual(selectState(measurementSelect), fallbackState.measurement);
assert.deepEqual(selectState(triggerSelect), fallbackState.trigger);
assert.equal(element("#latest-status").options.at(-1).textContent, "capabilities unavailable");
assert.equal(intervalCalls, 1);
assert.equal(eventSourceCalls, 1);
const beforeSwitchFetchCalls = fetchCalls;
const beforeSwitchIntervalCalls = intervalCalls;
const beforeSwitchEventSourceCalls = eventSourceCalls;

element("#locale-toggle").click();
assert.equal(documentElement.lang, "zh-TW");
assert.equal(
  element("#locale-toggle-label").getAttribute("data-i18n"),
  "locale.display_zh_tw"
);
assert.deepEqual(selectState(measurementSelect), fallbackState.measurement);
assert.deepEqual(selectState(triggerSelect), fallbackState.trigger);
assert.deepEqual(
  {
    resource: element("#resource").value,
    model: element("#instrument-model").value,
    csv: element("[name='csv']").value,
    maxSamples: element("[name='max_samples']").value,
    timeout: element("[name='timeout_ms']").value,
    autoRange: element("[name='auto_range']").checked,
  },
  {
    resource: fallbackState.resource,
    model: fallbackState.model,
    csv: fallbackState.csv,
    maxSamples: fallbackState.maxSamples,
    timeout: fallbackState.timeout,
    autoRange: fallbackState.autoRange,
  },
);
assert.equal(fetchCalls, beforeSwitchFetchCalls);
assert.equal(intervalCalls, beforeSwitchIntervalCalls);
assert.equal(eventSourceCalls, beforeSwitchEventSourceCalls);
assert.equal(reloadCalls, 0);
process.stdout.write(JSON.stringify({ ok: true }));
'''
    completed = run_node(script, STATIC_DIR / "app.js")
    assert completed.returncode == 0, (
        "Failed capabilities locale-switch contract failed\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert completed.stdout == '{"ok":true}'


@pytest.mark.skipif(NODE is None, reason="Node.js is required for import side-effect tests")
def test_locale_ui_and_i18n_imports_remain_browser_independent():
    script = r'''
import assert from "node:assert/strict";

const [localeUiUrl, i18nUrl] = process.argv.slice(1);
const names = ["document", "window", "navigator", "localStorage", "fetch", "XMLHttpRequest", "EventSource"];
const accesses = [];
for (const name of names) {
  Object.defineProperty(globalThis, name, {
    configurable: true,
    get() {
      accesses.push(name);
      throw new Error(`unexpected ${name}`);
    },
  });
}
await import(localeUiUrl);
await import(i18nUrl);
assert.deepEqual(accesses, []);
process.stdout.write(JSON.stringify({ ok: true }));
'''
    completed = run_node(script, STATIC_DIR / "locale_ui.js", STATIC_DIR / "i18n.js")
    assert completed.returncode == 0, (
        "Browser-independent import contract failed\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert completed.stdout == '{"ok":true}'


@pytest.mark.skipif(NODE is None, reason="Node.js is required for ES-module runtime tests")
def test_help_path_for_locale():
    script = r'''
import assert from "node:assert/strict";
const [localeUiUrl] = process.argv.slice(1);
const localeUi = await import(localeUiUrl);
assert.equal(localeUi.helpPathForLocale("en"), "/help/");
assert.equal(localeUi.helpPathForLocale("zh-TW"), "/help/webui.zh-TW.html");
process.stdout.write(JSON.stringify({ ok: true }));
'''
    completed = run_node(script, STATIC_DIR / "locale_ui.js")
    assert completed.returncode == 0, (
        f"Help path locale contract failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert completed.stdout == '{"ok":true}'


@pytest.mark.frontend_node
@pytest.mark.skipif(NODE is None, reason="Node.js is required for backend selection tests")
def test_backend_switch_invalidates_scan_and_keeps_support_filter_independent():
    script = APPLICATION_TEST_SETUP + r"""
const buttons = ["", "@py"].map((backend) => {
  const button = new FakeElement();
  button.dataset.supportBackend = backend;
  return button;
});
const originalQuery = document.querySelectorAll;
document.querySelectorAll = (selector) => selector === "[data-support-backend]"
  ? buttons : originalQuery(selector);
const features = {
  measurement: { "current-dc": { validation_status: "live_validated_full_suite" } },
  trigger_mode: { immediate: { validation_status: "live_validated_full_suite" } },
};
const scopes = [
  { transport_scope: "usb", backend_scope: "system_visa", validation_status: "live_validated_full_suite", features },
  { transport_scope: "tcpip", backend_scope: "pyvisa_py", validation_status: "live_validated_full_suite", features },
];
const capabilities = {
  limits: {}, available_profiles: [{ model: "34461A" }],
  supported_devices: [
    { model: "34461A", backend_connections: { system_visa: ["usb", "tcpip"], pyvisa_py: ["tcpip"] } },
    { model: "34460A", backend_connections: { system_visa: ["usb"] } },
  ],
  support: { "start-trigger-record": { live: { transport_scope: "usb", scopes } } },
  measurements: [{ name: "current-dc", unit: "A", nplc_options: [1], range_options: [], defaults: {} }],
  trigger_modes: ["immediate"], trigger_mode_metadata: {},
};
const idle = { active: false, state: "idle", captured: 0, errors: 0, recent_samples: [] };
let finishScan;
let finishCapabilities;
let finishInitialCapabilities;
let finishStart;
const calls = [];
globalThis.fetch = async (path, options) => {
  calls.push({ path: String(path), options });
  if (String(path).startsWith("/api/capabilities")) {
    if (calls.length === 1) return new Promise((resolve) => { finishInitialCapabilities = resolve; });
    return response(capabilities);
  }
  if (String(path).startsWith("/api/resources")) return new Promise((resolve) => { finishScan = resolve; });
  if (String(path) === "/api/runs") return new Promise((resolve) => { finishStart = resolve; });
  return response(idle);
};
globalThis.FormData = class {
  get(name) { return {
    resource: element("#resource").value, visa_library: element("#visa-library").value,
    instrument_model: "34461A", measurement: "current-dc", trigger_mode: "immediate",
    nplc: "1", auto_range: "on", max_samples: "1",
  }[name] ?? null; }
};
await import(appUrl);
await new Promise((resolve) => setTimeout(resolve, 0));
const backend = element("#visa-library");
const scan = element("#refresh-resources").listeners.get("click");
const switchBackend = async (value) => { backend.value = value; await backend.listeners.get("change")(); };
const pendingScan = scan();
await switchBackend("@py");
finishInitialCapabilities(response(capabilities));
finishScan(response({ resources: [{ resource: "USB::OLD", instrument_model: "34460A" }] }));
await pendingScan;
assert.equal(element("#resource").value, "");
assert.equal(element("#resource-select").options.length, 1);
const pyScan = scan();
finishScan(response({ resources: [{ resource: "TCPIP0::fake::inst0::INSTR", instrument_model: "34461A" }] }));
await pyScan;
assert.match(calls.findLast((call) => call.path.includes("/api/resources")).path, /visa_library=%40py/);
assert.equal(element("#resource").value, "TCPIP0::fake::inst0::INSTR");
assert.equal(element("#measurement").options[0].disabled, false);
element("#supported-devices-toggle").listeners.get("click")({ stopPropagation() {} });
const rows = element("#supported-devices-body");
assert.equal(rows.children.length, 1);
assert.equal(rows.children[0].children.length, 2);
assert.equal(rows.children[0].children[0].textContent, "34461A");
buttons[0].click();
assert.equal(rows.children.length, 2);
assert.equal(backend.value, "@py");
const { setLocale } = await import(new URL("./i18n.js", appUrl));
setLocale("zh-TW");
element("#locale-toggle").click();
assert.equal(backend.value, "@py");
assert.equal(buttons[0].getAttribute("aria-pressed"), "true");
const pendingStart = element("#start-run").listeners.get("click")();
const run = calls.findLast((call) => call.path === "/api/runs");
assert.equal(JSON.parse(run.options.body).visa_library, "@py");
const { renderStatus } = await import(new URL("./status.js", appUrl));
const completed = { ...idle, run_id: "fast-run", state: "stopped", captured: 1, latest_status: "recording stopped" };
renderStatus(completed); // Newer SSE event arrives before the Start POST response.
finishStart(response({ ...completed, state: "running", active: true, captured: 0, latest_status: "ready" }));
await pendingStart;
assert.equal(element("#status-captured").textContent, "1");
assert.equal(JSON.parse(element("#raw-status").textContent).state, "stopped");
renderStatus({ ...idle, active: true });
assert.equal(backend.disabled, true);
await switchBackend("");
assert.equal(backend.value, "@py");
renderStatus(idle);
// An inferred profile response from the old backend must not restore stale options.
const originalFetch = globalThis.fetch;
globalThis.fetch = async (path, options) => String(path).startsWith("/api/capabilities")
  ? new Promise((resolve) => { finishCapabilities = resolve; }) : originalFetch(path, options);
const oldSelection = element("#resource-select").listeners.get("change")();
globalThis.fetch = originalFetch;
await switchBackend("");
finishCapabilities(response({ ...capabilities, trigger_modes: ["stale-mode"] }));
await oldSelection;
assert.equal(element("#trigger-mode").options.some((option) => option.value === "stale-mode"), false);
assert.equal(element("#resource").value, "");
"""
    completed = run_node(script, STATIC_DIR / "app.js")
    assert completed.returncode == 0, completed.stdout + completed.stderr
