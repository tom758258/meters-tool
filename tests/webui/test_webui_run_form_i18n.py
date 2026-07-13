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
    "voltage-dc-ratio": { validation_status: "live_validated_full_suite" },
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
const supportSummary = {
  model: "34461A",
  capability_profile: "34461A",
  is_fallback_capability_view: true,
  validation_status: "live_validated_full_suite",
  transport_scope: "usb",
  backend_scope: "system_visa",
  status_text: (
    "Full-suite validated for profile-supported workflows on USB/system-VISA, " +
    "LAN/system-VISA, and optional CLI-only LAN/pyvisa-py @py."
  ),
  status_key: "support.status.profile_workflows_validated",
  runtime_driver_note: "Live runtime model is selected from detected *IDN?.",
  runtime_driver_note_key: "support.runtime_driver.detected_idn",
  open_workflows: [
    "immediate", "software", "software timer", "custom buffered", "Frequency", "Period",
  ],
  open_workflow_keys: [
    "support.workflow.immediate",
    "support.workflow.software",
    "support.workflow.software_timer",
    "support.workflow.custom_buffered",
    "support.workflow.frequency",
    "support.workflow.period",
  ],
  limits: [
    "no 10 A current path",
    "no current-terminal selection",
    "1000-reading memory limit",
    "no base-profile external trigger support",
  ],
  limit_keys: [
    "support.limit.no_10a_current_path",
    "support.limit.no_current_terminal_selection",
    "support.limit.reading_memory_1000",
    "support.limit.no_base_profile_external_trigger",
  ],
  pending: [
    "LAN/TCPIP system-VISA validation",
    "LAN/TCPIP pyvisa-py @py validation",
  ],
  pending_keys: [
    "support.pending.lan_tcpip_system_visa_validation",
    "support.pending.lan_tcpip_pyvisa_py_validation",
  ],
};
const capabilities = {
  app: appMetadata,
  limits: { sw_min_interval_ms: { nonzero_min: 50, max: 600000 } },
  support_summary: supportSummary,
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
    { name: "voltage-dc-ratio", unit: "ratio", nplc_options: [1], range_options: [], defaults: {} },
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

let fetchCount = 0;
globalThis.fetch = async () => {
  fetchCount += 1;
  return ({
  ok: true,
  statusText: "OK",
  async text() {
    capabilities.app = appMetadata;
    return JSON.stringify(capabilities);
  },
  });
};

element("#resource").value = "USB0::SIM";
element("#instrument-model").value = "34461A";
element("#measurement").value = "current-dc";
element("#trigger-mode").value = "software";
element("[name='auto_range']").checked = true;
element("[name='auto_zero']").value = "on";
element("[name='max_samples']").value = "100";
element("[name='timer_interval_s']").value = "1";

const runForm = await import(runFormUrl);
const i18n = await import(new URL("./i18n.js", runFormUrl));
await runForm.loadCapabilities();
assert.equal(fetchCount, 1);

const supportStatus = element("#model-support-status");
const supportOpen = element("#model-support-open");
const supportLimits = element("#model-support-limits");
const supportPending = element("#model-support-pending");
assert.equal(
  supportStatus.textContent,
  (
    "Auto-detect: showing 34461A fallback capability view until Start or Scan " +
    "detects IDN. Live runtime model is selected from detected *IDN?. " +
    "(live_validated_full_suite, usb/system_visa)"
  )
);
assert.equal(
  supportOpen.textContent,
  "immediate, software, software timer, custom buffered, Frequency, Period"
);
assert.equal(
  supportLimits.textContent,
  (
    "no 10 A current path, no current-terminal selection, " +
    "1000-reading memory limit, no base-profile external trigger support"
  )
);
assert.equal(
  supportPending.textContent,
  "LAN/TCPIP system-VISA validation, LAN/TCPIP pyvisa-py @py validation"
);

supportSummary.is_fallback_capability_view = false;
supportSummary.model = "34460A";
supportSummary.status_text = "USB/system-VISA full-suite validated.";
supportSummary.status_key = "support.status.usb_system_visa_validated";
await runForm.loadCapabilities();
assert.equal(
  supportStatus.textContent,
  "34460A: USB/system-VISA full-suite validated. (live_validated_full_suite, usb/system_visa)"
);
assert.equal(fetchCount, 2);

const preservedValues = {
  measurement: element("#measurement").value,
  triggerMode: element("#trigger-mode").value,
  expectedModel: element("#instrument-model").value,
  resource: element("#resource").value,
};
supportSummary.is_fallback_capability_view = true;
supportSummary.model = "34461A";
supportSummary.capability_profile = "34461A";
supportSummary.status_text = (
  "Full-suite validated for profile-supported workflows on USB/system-VISA, " +
  "LAN/system-VISA, and optional CLI-only LAN/pyvisa-py @py."
);
supportSummary.status_key = "support.status.profile_workflows_validated";
await runForm.loadCapabilities();
const refreshFetchCount = fetchCount;
i18n.setLocale("zh-TW");
runForm.refreshSupportSummaryPresentation();
assert.equal(
  supportStatus.textContent,
  (
    "自動偵測：目前顯示 34461A 的備援功能檢視，直到開始或掃描時偵測到 IDN。" +
    "實機執行型號由偵測到的 *IDN? 決定。" +
    "（live_validated_full_suite，usb/system_visa）"
  )
);
assert.equal(
  supportOpen.textContent,
  "立即觸發, 軟體觸發, 軟體定時觸發, 自訂緩衝, 頻率, 週期"
);
assert.match(supportLimits.textContent, /無 10 A 電流路徑/);
assert.match(supportLimits.textContent, /1000 筆讀值記憶體限制/);
assert.match(supportPending.textContent, /LAN\/TCPIP system-VISA 驗證/);
assert.equal(fetchCount, refreshFetchCount);
assert.deepEqual(
  {
    measurement: element("#measurement").value,
    triggerMode: element("#trigger-mode").value,
    expectedModel: element("#instrument-model").value,
    resource: element("#resource").value,
  },
  preservedValues
);
assert.equal(supportSummary.validation_status, "live_validated_full_suite");
assert.equal(supportSummary.transport_scope, "usb");
assert.equal(supportSummary.backend_scope, "system_visa");

supportSummary.is_fallback_capability_view = false;
supportSummary.model = "34460A";
supportSummary.status_text = "USB/system-VISA full-suite validated.";
delete supportSummary.status_key;
await runForm.loadCapabilities();
assert.match(supportStatus.textContent, /USB\/system-VISA full-suite validated\./);

supportSummary.status_key = "support.future.unknown_key";
await runForm.loadCapabilities();
assert.match(supportStatus.textContent, /USB\/system-VISA full-suite validated\./);
assert.doesNotMatch(supportStatus.textContent, /support\.future\.unknown_key/);

delete supportSummary.open_workflow_keys;
await runForm.loadCapabilities();
assert.equal(
  supportOpen.textContent,
  "immediate, software, software timer, custom buffered, Frequency, Period"
);

supportSummary.open_workflow_keys = ["support.workflow.immediate"];
await runForm.loadCapabilities();
assert.equal(
  supportOpen.textContent,
  "立即觸發, software, software timer, custom buffered, Frequency, Period"
);

supportSummary.open_workflow_keys = [
  "support.workflow.immediate",
  "support.future.unknown_key",
  "support.workflow.software_timer",
  "support.workflow.custom_buffered",
  "support.workflow.frequency",
  "support.workflow.period",
  "support.future.extra_key",
];
await runForm.loadCapabilities();
assert.equal(
  supportOpen.textContent,
  "立即觸發, software, 軟體定時觸發, 自訂緩衝, 頻率, 週期"
);
assert.doesNotMatch(supportOpen.textContent, /support\.future/);

supportSummary.open_workflow_keys = { malformed: true };
await runForm.loadCapabilities();
assert.equal(
  supportOpen.textContent,
  "immediate, software, software timer, custom buffered, Frequency, Period"
);

supportSummary.open_workflows = [];
supportSummary.open_workflow_keys = ["support.workflow.immediate"];
supportSummary.limits = [];
supportSummary.limit_keys = ["support.limit.no_10a_current_path"];
supportSummary.pending = [];
supportSummary.pending_keys = null;
await runForm.loadCapabilities();
assert.equal(supportOpen.textContent, "無");
assert.equal(supportLimits.textContent, "無");
assert.equal(supportPending.textContent, "無");

i18n.setLocale("en");
const finalRefreshFetchCount = fetchCount;
runForm.refreshSupportSummaryPresentation();
assert.equal(supportOpen.textContent, "None");
assert.equal(supportLimits.textContent, "None");
assert.equal(supportPending.textContent, "None");
assert.equal(fetchCount, finalRefreshFetchCount);
await runForm.loadCapabilities();

const measurementSelect = element("#measurement");
const triggerSelect = element("#trigger-mode");
const modelSelect = element("#instrument-model");
const optionByValue = (select, value) => select.options.find((option) => option.value === value);

measurementSelect.value = "voltage-dc";
triggerSelect.value = "external";
const preservedPresentationValues = {
  measurement: measurementSelect.value,
  triggerMode: triggerSelect.value,
  resource: element("#resource").value,
  autoRange: element("[name='auto_range']").checked,
  maxSamples: element("[name='max_samples']").value,
};
const beforePresentationRefreshFetchCount = fetchCount;
i18n.setLocale("zh-TW");
runForm.refreshRunFormPresentation();
assert.deepEqual(
  {
    measurement: measurementSelect.value,
    triggerMode: triggerSelect.value,
    resource: element("#resource").value,
    autoRange: element("[name='auto_range']").checked,
    maxSamples: element("[name='max_samples']").value,
  },
  preservedPresentationValues,
);
assert.equal(optionByValue(measurementSelect, "voltage-dc").disabled, true);
assert.match(optionByValue(measurementSelect, "voltage-dc").textContent, /等待實機驗證/);
assert.equal(optionByValue(triggerSelect, "external").disabled, true);
assert.match(optionByValue(triggerSelect, "external").textContent, /型號不支援/);
assert.equal(fetchCount, beforePresentationRefreshFetchCount);
i18n.setLocale("en");
runForm.refreshRunFormPresentation();
measurementSelect.value = "current-dc";
triggerSelect.value = "software";
runForm.updatePanelSummaries();

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

const promotedRatioMeasurement = optionByValue(measurementSelect, "voltage-dc-ratio");
assert.equal(promotedRatioMeasurement.disabled, false);
assert.equal(promotedRatioMeasurement.dataset.validationStatus, "live_validated_full_suite");

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


def test_p23_and_p25_source_boundaries_and_semantic_keys():
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
        "support.runtime_driver.detected_idn",
        "support.summary.auto_detect_status",
        "support.summary.profile_status",
        "support.summary.status_unavailable",
        "support.summary.selected_model",
        "support.summary.unspecified_transport",
        "support.summary.unspecified_backend",
        "support.summary.none",
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

    for migrated_support_text in (
        "Support status unavailable.",
        "selected model",
        "unspecified transport",
        "unspecified backend",
        "Live runtime driver remains detected IDN.",
        "fallback capability view",
        'return values.length ? values.join(", ") : "None";',
    ):
        assert migrated_support_text not in source

    for support_metadata_field in (
        "status_key",
        "runtime_driver_note_key",
        "open_workflow_keys",
        "limit_keys",
        "pending_keys",
    ):
        assert support_metadata_field in source

    assert "export function refreshSupportSummaryPresentation()" in source
    assert "translated === key ? safeFallback : translated" in source
    assert "latestSupportSummary = capabilities.support_summary ?? null" in source
    assert 'const validationStatus = summary?.validation_status || "unknown"' in source
    assert "/api/capabilities?locale=" not in source

    assert 'scope.validation_status !== "live_validated_full_suite"' in source
    assert 'option.dataset.validationStatus = availability.validationStatus' in source
    assert 'instrument_model: textOrNull(data.get("instrument_model"))' in source
    assert 'trigger_mode: triggerMode' in source
    assert 'measurement: selectedMeasurement' in source
