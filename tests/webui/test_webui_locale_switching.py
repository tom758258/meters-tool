from __future__ import annotations

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
            "--eval",
            script,
            *(module.resolve().as_uri() for module in modules),
        ],
        cwd=REPO_ROOT,
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

const documentElement = new FakeElement();
const documentListeners = new Map();
const windowListeners = new Map();
let intervalCalls = 0;
let eventSourceCalls = 0;
let reloadCalls = 0;
globalThis.document = {
  documentElement,
  querySelector: element,
  querySelectorAll: () => [],
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
assert.equal(label.textContent, "繁體中文");
assert.equal(label.lang, "zh-TW");
assert.equal(button.getAttribute("aria-label"), "Switch language to Traditional Chinese");
assert.equal(button.getAttribute("data-i18n"), null);
assert.equal(button.getAttribute("data-i18n-aria-label"), "accessibility.switch_language_to_zh_tw");

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
assert.equal(firstRenderText.textContent, "非官方工具");

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
assert.equal(label.textContent, "English");
assert.equal(label.lang, "en");
assert.equal(button.getAttribute("aria-label"), "切換語言至英文");
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


def test_locale_static_markup_and_refresh_source_contracts():
    index = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    run_form = (STATIC_DIR / "run_form.js").read_text(encoding="utf-8")
    status = (STATIC_DIR / "status.js").read_text(encoding="utf-8")
    live_data = (STATIC_DIR / "live_data.js").read_text(encoding="utf-8")

    assert index.count('id="locale-toggle"') == 1
    assert 'class="toolbar"' in index
    assert 'id="locale-toggle"' in index[index.index('class="toolbar"'):index.index('class="toolbar"') + 1500]
    assert 'type="button"' in index[index.index('id="locale-toggle"'):index.index('id="locale-toggle"') + 500]
    assert '<svg' in index[index.index('id="locale-toggle"'):index.index('id="locale-toggle"') + 500]
    assert 'aria-hidden="true"' in index[index.index('id="locale-toggle"'):index.index('id="locale-toggle"') + 500]
    assert 'focusable="false"' in index[index.index('id="locale-toggle"'):index.index('id="locale-toggle"') + 500]
    assert 'id="locale-toggle-label"' in index
    assert 'lang="zh-TW"' in index
    styles = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    assert "locale-toggle" in styles
    locale_styles = styles[styles.index(".locale-toggle {"):styles.index(".locale-toggle-label {")]
    assert "display: none" not in locale_styles

    assert "initializeLocaleUi({" in app
    assert app.index("initializeLocaleUi({") < app.index("applyStaticTranslations(document);", app.index("initializeLocaleUi({"))
    assert "refreshRunFormPresentation();" in app
    assert "refreshResourcesPresentation();" in app
    assert "refreshStatusPresentation();" in app
    assert "resourceScanCompleted" in app
    assert "api(\"/api/resources?verify=true&live_only=true\")" in app
    assert "export function refreshRunFormPresentation()" in run_form
    assert "preserveUnavailableSelections = false" in run_form
    refresh_start = run_form.index("export function refreshRunFormPresentation()")
    refresh_end = run_form.index("export async function loadCapabilities", refresh_start)
    run_form_refresh = run_form[refresh_start:refresh_end]
    readiness_guard = run_form_refresh.index("if (capabilitiesLoaded)")
    assert readiness_guard < run_form_refresh.index("populateFeatureOptions(")
    assert readiness_guard < run_form_refresh.index("refreshMeasurementOptionPresentation();")
    load_start = run_form.index("export async function loadCapabilities")
    load_capabilities = run_form[load_start:]
    ready_assignment = load_capabilities.index("capabilitiesLoaded = true;")
    for required_assignment in (
        "applyAppMetadata(capabilities.app);",
        "applyInputLimits(capabilities.limits);",
        "latestSupportSummary = capabilities.support_summary ?? null;",
        'liveSupport = capabilities.support?.["start-trigger-record"]?.live || null;',
        "capabilities.available_profiles || []",
        "measurementsByName = new Map(",
        "supportedTriggerModes = [...capabilities.trigger_modes];",
    ):
        assert load_capabilities.index(required_assignment) < ready_assignment
    assert "export function refreshStatusPresentation()" in status
    assert "export function refreshLiveDataPresentation()" in live_data
    refresh_start = app.index("function refreshLocalizedPresentation()")
    refresh_end = app.index("function browserStorage()", refresh_start)
    refresh_body = app[refresh_start:refresh_end]
    for forbidden in ("api(", "EventSource", "loadCapabilities", "pollStatus", "applyScannedResource"):
        assert forbidden not in refresh_body
    resource_refresh = app[app.index("export function refreshResourcesPresentation") : app.index("async function refreshResources()")]
    assert "applyScannedResource" not in resource_refresh


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
assert.equal(element("#locale-toggle-label").textContent, "繁體中文");
assert.equal(documentElement.lang, "en");
assert.match(element("#resource-select").children[1].textContent, /live/);
assert.match(element("#resource-select").children[2].textContent, /raw vendor detail/);

element("#locale-toggle").click();
assert.equal(documentElement.lang, "zh-TW");
assert.equal(element("#locale-toggle-label").textContent, "English");
assert.equal(element("#locale-toggle").getAttribute("aria-label"), "切換語言至英文");
assert.equal(element("#status-state").textContent, "執行中");
assert.equal(element("#resource-select").value, "USB0::SIM");
assert.match(element("#resource-select").children[1].textContent, /實機/);
assert.match(element("#resource-select").children[2].textContent, /raw vendor detail/);
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
assert.equal(element("#locale-toggle-label").textContent, "English");
assert.notEqual(element("#locale-toggle").getAttribute("aria-label"), null);
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
assert.equal(measurementSelect.options[0].getAttribute("data-i18n"), "measurement.option_label");
assert.equal(triggerSelect.options[0].getAttribute("data-i18n"), "trigger.option_label");
assert.equal(measurementSelect.options[1].disabled, true);
assert.equal(triggerSelect.options[1].disabled, true);
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
assert.equal(measurementSelect.options[1].disabled, true);
assert.equal(triggerSelect.options[1].disabled, true);
assert.match(measurementSelect.options[1].textContent, /Pending live validation/);
assert.match(triggerSelect.options[1].textContent, /Not supported by model/);
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
assert.equal(element("#locale-toggle-label").textContent, "English");
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
