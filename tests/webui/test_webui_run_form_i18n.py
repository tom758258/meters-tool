from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "src" / "meters_tool_webui" / "static"
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="Node.js is required for run-form runtime tests")
def test_dynamic_run_form_localization_preserves_machine_contracts():
    script = r"""
import assert from "node:assert/strict";

const runFormUrl = process.argv[1];

class FakeClassList {
  constructor() {
    this.values = new Set();
  }
  toggle(name, force) {
    if (force) this.values.add(name);
    else this.values.delete(name);
  }
}

class FakeElement {
  constructor(tagName = "div") {
    this.tagName = tagName;
    this._value = "";
    this.textContent = "";
    this.title = "";
    this.checked = false;
    this.disabled = false;
    this.required = false;
    this.dataset = {};
    this.children = [];
    this.attributes = new Map();
    this.classList = new FakeClassList();
    this.validationMessage = "";
  }
  get value() {
    return this._value;
  }
  set value(value) {
    this._value = String(value ?? "");
  }
  get options() {
    return this.children;
  }
  get selectedOptions() {
    return this.children.filter((child) => child.value === this.value);
  }
  replaceChildren(...children) {
    this.children = children;
  }
  querySelectorAll() {
    return [];
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }
  removeAttribute(name) {
    this.attributes.delete(name);
  }
  setCustomValidity(message) {
    this.validationMessage = message;
  }
}

const elements = new Map();
function element(selector) {
  if (!elements.has(selector)) elements.set(selector, new FakeElement());
  return elements.get(selector);
}

globalThis.document = {
  querySelector: element,
  querySelectorAll() {
    return [];
  },
  createElement(tagName) {
    return new FakeElement(tagName);
  },
};

globalThis.FormData = class {
  get(name) {
    const selectors = {
      resource: "#resource",
      instrument_model: "#instrument-model",
      measurement: "#measurement",
      trigger_mode: "#trigger-mode",
      auto_zero: "[name='auto_zero']",
      measurement_range: "#measurement-range",
      nplc: "#nplc",
      ac_bandwidth_hz: "#ac-bandwidth",
      gate_time_s: "#gate-time",
      freq_period_timeout: "#freq-period-timeout",
      current_terminal: "#current-terminal",
      max_samples: "[name='max_samples']",
      timer_interval_s: "[name='timer_interval_s']",
    };
    if (name === "auto_range") {
      return element("[name='auto_range']").checked ? "on" : null;
    }
    return selectors[name] ? element(selectors[name]).value : null;
  }
};

const featureStatus = {
  measurement: {
    "current-dc": { validation_status: "live_validated_full_suite" },
    "voltage-dc": { validation_status: "feature_pending" },
    frequency: { validation_status: "live_validated_full_suite" },
    "voltage-ac": { validation_status: "live_validated_full_suite" },
    "future-measure": { validation_status: "live_validated_full_suite" },
  },
  trigger_mode: {
    software: { validation_status: "live_validated_full_suite" },
    external: { validation_status: "not_supported_by_model" },
    "future-trigger": { validation_status: "live_validated_full_suite" },
  },
};

let appMetadata = { version: "1.6.0" };
const capabilities = {
  app: appMetadata,
  limits: { sw_min_interval_ms: { nonzero_min: 50, max: 600000 } },
  support_summary: {},
  support: {
    "start-trigger-record": {
      live: {
        transport_scope: "usb",
        scopes: [{
          transport_scope: "usb",
          backend_scope: "system_visa",
          validation_status: "live_validated_full_suite",
          features: featureStatus,
        }],
      },
    },
  },
  available_profiles: [{ model: "34461A" }, { model: "34460A" }],
  measurements: [
    {
      name: "current-dc", unit: "A", nplc_options: [1],
      range_options: [{ value: 3, label: "3 A" }],
      supports_current_terminal: true, current_terminal_options: [3], defaults: {},
    },
    { name: "voltage-dc", unit: "V", nplc_options: [1], range_options: [], defaults: {} },
    {
      name: "frequency", unit: "Hz", nplc_options: [], range_options: [],
      supports_ac_bandwidth: true, ac_bandwidth_hz_options: [20],
      supports_gate_time: true, gate_time_s_options: [0.1],
      supports_freq_period_timeout: true, freq_period_timeout_options: ["auto", "1s"],
      defaults: { ac_bandwidth_hz: 20, gate_time_s: 0.1, freq_period_timeout: "auto" },
    },
    {
      name: "voltage-ac", unit: "V", nplc_options: [], range_options: [],
      supports_ac_bandwidth: true, ac_bandwidth_hz_options: [3],
      defaults: { ac_bandwidth_hz: 3 },
    },
    { name: "future-measure", unit: "X", nplc_options: [], range_options: [], defaults: {} },
  ],
  trigger_modes: ["software", "external", "future-trigger"],
};

globalThis.fetch = async () => ({
  ok: true,
  statusText: "OK",
  async text() {
    capabilities.app = appMetadata;
    return JSON.stringify(capabilities);
  },
});

element("#resource").value = "USB0::SIM";
element("#instrument-model").value = "34461A";
element("#measurement").value = "current-dc";
element("#trigger-mode").value = "software";
element("[name='auto_range']").checked = true;
element("[name='auto_zero']").value = "on";
element("[name='max_samples']").value = "100";
element("[name='timer_interval_s']").value = "1";

const runForm = await import(runFormUrl);
await runForm.loadCapabilities();

const measurementSelect = element("#measurement");
const triggerSelect = element("#trigger-mode");
const modelSelect = element("#instrument-model");
const optionByValue = (select, value) => select.options.find((option) => option.value === value);

assert.equal(measurementSelect.value, "current-dc");
assert.equal(triggerSelect.value, "software");
assert.equal(modelSelect.value, "34461A");
assert.equal(optionByValue(measurementSelect, "current-dc").textContent, "DC current (current-dc, A)");
assert.equal(optionByValue(measurementSelect, "future-measure").textContent, "Future-measure (X)");
assert.equal(optionByValue(triggerSelect, "software").textContent, "Software (software)");
assert.equal(optionByValue(triggerSelect, "future-trigger").textContent, "Future-trigger");

const pendingMeasurement = optionByValue(measurementSelect, "voltage-dc");
assert.equal(pendingMeasurement.value, "voltage-dc");
assert.equal(pendingMeasurement.disabled, true);
assert.equal(pendingMeasurement.dataset.validationStatus, "feature_pending");
assert.match(pendingMeasurement.textContent, /Pending live validation/);
assert.equal(pendingMeasurement.title, "Pending live validation");
assert.equal(pendingMeasurement.getAttribute("data-i18n"), "support.unavailable_option");
assert.equal(pendingMeasurement.getAttribute("data-i18n-title"), "support.reason.pending_live_validation");

const unsupportedTrigger = optionByValue(triggerSelect, "external");
assert.equal(unsupportedTrigger.disabled, true);
assert.equal(unsupportedTrigger.dataset.validationStatus, "not_supported_by_model");
assert.match(unsupportedTrigger.textContent, /Not supported by model/);

assert.deepEqual(modelSelect.options.map((option) => option.value), ["", "34460A", "34461A"]);
assert.deepEqual(modelSelect.options.map((option) => option.textContent), [
  "Auto-detect", "Require 34460A", "Require 34461A",
]);
assert.equal(modelSelect.options[0].getAttribute("data-i18n"), "device.auto_detect");
assert.equal(modelSelect.options[1].getAttribute("data-i18n"), "device.require_model");

const autoZero = element("[name='auto_zero']");
assert.deepEqual(autoZero.options.map((option) => option.value), ["on", "off", "once"]);
assert.deepEqual(autoZero.options.map((option) => option.textContent), ["On", "Off", "Once"]);
assert.equal(autoZero.value, "on");
assert.equal(element(".subtitle").textContent, "Unofficial Tool v1.6.0");
assert.equal(element(".subtitle").getAttribute("data-i18n"), "app.unofficial_tool_version");

const runSummary = element("[data-summary-for='run-setup']");
assert.equal(runSummary.textContent, "Software (software) / DC current (current-dc) / max 100");
assert.equal(runSummary.getAttribute("data-i18n"), "run.summary_with_max");
element("[name='max_samples']").value = "";
runForm.updatePanelSummaries();
assert.equal(runSummary.textContent, "Software (software) / DC current (current-dc)");
assert.equal(runSummary.getAttribute("data-i18n"), "run.summary");

element("#current-terminal").value = "3";
runForm.updatePanelSummaries();
const measurementSummary = element("[data-summary-for='measurement-options']");
assert.match(measurementSummary.textContent, /Auto range/);
assert.match(measurementSummary.textContent, /Auto zero: On/);
assert.match(measurementSummary.textContent, /NPLC 1/);
assert.match(measurementSummary.textContent, /Terminal 3 A/);

measurementSelect.value = "frequency";
runForm.updateMeasurementUi();
assert.match(measurementSummary.textContent, /AC Filter >20 Hz/);
assert.match(measurementSummary.textContent, /Gate 0.1 s/);
assert.match(measurementSummary.textContent, /Timeout auto/);

measurementSelect.value = "voltage-ac";
runForm.updateMeasurementUi();
assert.match(measurementSummary.textContent, /AC Band 3 Hz/);

triggerSelect.value = "software";
element("#timer-trigger-checkbox").checked = true;
runForm.updatePanelSummaries();
const triggerSummary = element("[data-summary-for='trigger-options']");
assert.equal(triggerSummary.textContent, "Timer 1 s");
assert.equal(triggerSummary.getAttribute("data-i18n"), "trigger.summary.timer");
element("#timer-trigger-checkbox").checked = false;
runForm.updatePanelSummaries();
assert.equal(triggerSummary.textContent, "Software (software) trigger");
assert.equal(triggerSummary.getAttribute("data-i18n"), "trigger.summary.mode");

const interval = element("[name='sw_min_interval_ms']");
interval.disabled = false;
interval.value = "49";
assert.equal(runForm.validateSwMinInterval(), false);
assert.equal(interval.validationMessage, "Use 0 to disable throttling, or use 50-600000 ms.");
interval.value = "0";
assert.equal(runForm.validateSwMinInterval(), true);
assert.equal(interval.validationMessage, "");

const metadata = element("#trigger-metadata");
metadata.value = "{";
assert.throws(() => runForm.triggerMetadataPayload(), /valid JSON object/);
metadata.value = "[]";
assert.throws(() => runForm.triggerMetadataPayload(), /must be a JSON object/);
metadata.value = '{"batch":"A1"}';
assert.deepEqual(runForm.triggerMetadataPayload(), { source: "web-ui", batch: "A1" });

measurementSelect.value = "current-dc";
triggerSelect.value = "software";
modelSelect.value = "34461A";
const payload = runForm.formPayload();
assert.equal(payload.measurement, "current-dc");
assert.equal(payload.trigger_mode, "software");
assert.equal(payload.instrument_model, "34461A");

optionByValue(measurementSelect, "current-dc").textContent = "translated measurement";
optionByValue(triggerSelect, "software").textContent = "translated trigger";
modelSelect.selectedOptions[0].textContent = "translated model";
assert.equal(measurementSelect.value, "current-dc");
assert.equal(triggerSelect.value, "software");
assert.equal(modelSelect.value, "34461A");
assert.equal(runForm.formPayload().measurement, "current-dc");
assert.equal(runForm.formPayload().trigger_mode, "software");
assert.equal(runForm.formPayload().instrument_model, "34461A");

element("#resource").value = "TCPIP0::SIM";
runForm.updateFeatureAvailability();
assert.equal(optionByValue(measurementSelect, "current-dc").disabled, true);
assert.equal(optionByValue(measurementSelect, "current-dc").dataset.validationStatus, "missing");
assert.match(optionByValue(measurementSelect, "current-dc").textContent, /current transport\/backend scope/);

appMetadata = {};
element("#resource").value = "USB0::SIM";
await runForm.loadCapabilities();
assert.equal(element(".subtitle").textContent, "Unofficial Tool");
assert.equal(element(".subtitle").getAttribute("data-i18n"), "app.unofficial_tool");

process.stdout.write(JSON.stringify({ ok: true }));
"""
    completed = subprocess.run(
        [
            NODE,
            "--input-type=module",
            "--eval",
            script,
            (STATIC_DIR / "run_form.js").resolve().as_uri(),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, (
        "Node run-form i18n contract failed\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert completed.stdout == '{"ok":true}'


def test_p23_source_boundaries_and_semantic_keys():
    source = (STATIC_DIR / "run_form.js").read_text(encoding="utf-8")

    for key in (
        "support.reason.scope_unavailable",
        "support.unavailable_option",
        "measurement.option.voltage_dc",
        "measurement.option_label",
        "trigger.option.software_custom",
        "trigger.option_label",
        "validation.interval_range",
        "error.trigger_metadata_invalid_json",
        "error.trigger_metadata_not_object",
        "run.summary",
        "run.summary_with_max",
        "measurement.summary.auto_range",
        "measurement.summary.manual_range",
        "measurement.summary.auto_zero",
        "measurement.summary.nplc",
        "measurement.summary.ac_filter",
        "measurement.summary.ac_band",
        "measurement.summary.gate",
        "measurement.summary.timeout",
        "measurement.summary.terminal",
        "trigger.summary.timer",
        "trigger.summary.mode",
        "app.unofficial_tool_version",
        "device.auto_detect",
        "device.require_model",
    ):
        assert f'"{key}"' in source

    for migrated_literal in (
        "Use 0 to disable throttling, or use",
        "Trigger metadata must be valid JSON object",
        "Trigger metadata must be a JSON object",
        'optionElement("on", "On")',
        'optionElement("off", "Off")',
        'optionElement("once", "Once")',
        'optionElement("", "Select range")',
        'optionElement("", "Auto-detect")',
    ):
        assert migrated_literal not in source

    for forbidden in (
        "setLocale(",
        "navigator.language",
        "navigator.languages",
        "localStorage",
        "LOCALE_STORAGE_KEY",
        "validation_allow_pending_live_support",
        "--validation-allow-pending-live-support",
    ):
        assert forbidden not in source

    for deferred_support_text in (
        "Support status unavailable.",
        "selected model",
        "unknown",
        "unspecified transport",
        "unspecified backend",
        "Live runtime driver remains detected IDN.",
        "fallback capability view",
        'return values.length ? values.join(", ") : "None";',
    ):
        assert deferred_support_text in source

    assert 'scope.validation_status !== "live_validated_full_suite"' in source
    assert 'option.dataset.validationStatus = availability.validationStatus' in source
    assert 'instrument_model: textOrNull(data.get("instrument_model"))' in source
    assert 'trigger_mode: triggerMode' in source
    assert 'measurement: selectedMeasurement' in source
