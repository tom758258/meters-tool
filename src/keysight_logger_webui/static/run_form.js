import { api } from "./api.js";
import {
  acBandwidthContainer,
  acBandwidthSelect,
  autoRangeCheckbox,
  autoZeroContainer,
  autoZeroSelect,
  currentTerminalContainer,
  currentTerminalSelect,
  form,
  freqPeriodTimeoutContainer,
  freqPeriodTimeoutSelect,
  gateTimeContainer,
  gateTimeSelect,
  instrumentModelSelect,
  measurementRangeInput,
  measurementScopedControls,
  measurementSelect,
  modeScopedControls,
  nplcField,
  nplcSelect,
  rangeContainer,
  rangeSuffix,
  rangeUnit,
  sampleCountInput,
  subtitle,
  swMinIntervalContainer,
  swMinIntervalInput,
  swQueueMaxContainer,
  swQueueMaxInput,
  timerIntervalContainer,
  timerIntervalInput,
  timerTriggerCheckbox,
  triggerCountInput,
  triggerMetadataContainer,
  triggerMetadataInput,
  triggerModeSelect,
  triggerRunButton,
  triggerTimeoutInput,
} from "./dom.js";

const DEFAULT_TRIGGER_TIMEOUT_MS = 10000;
let measurementsByName = new Map();
let inputLimits = {};

export function numberOrNull(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  return Number(value);
}

export function textOrNull(value) {
  const text = String(value || "").trim();
  return text ? text : null;
}

export function capitalizeFirst(value) {
  const text = String(value || "");
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
}

function supportsAutoZero(measurementName) {
  return ["current-dc", "voltage-dc", "resistance-2w"].includes(measurementName);
}

function supportsAcBandwidth(measurement) {
  return Boolean(measurement?.supports_ac_bandwidth);
}

function supportsCurrentTerminal(measurement) {
  return Boolean(measurement?.supports_current_terminal);
}

function supportsGateTime(measurement) {
  return Boolean(measurement?.supports_gate_time);
}

function supportsFreqPeriodTimeout(measurement) {
  return Boolean(measurement?.supports_freq_period_timeout);
}

function supportsDcvInputZ(measurementName) {
  return ["voltage-dc", "voltage-dc-ratio"].includes(measurementName);
}

function usesTriggerTimeout(mode) {
  return mode === "external" || mode === "external-custom";
}

function triggerTimeoutMs(data, mode) {
  return numberOrNull(
    usesTriggerTimeout(mode) ? data.get("trigger_timeout_ms") : DEFAULT_TRIGGER_TIMEOUT_MS
  );
}

export function formPayload() {
  const data = new FormData(form);
  const resource = String(data.get("resource") || "").trim();
  const triggerMode = textOrNull(data.get("trigger_mode")) || "software";
  const customMode = isCustomMode(triggerMode);
  const hardwareMode = isHardwareMode(triggerMode);
  const softwareTriggeredMode = isSoftwareTriggeredMode(triggerMode);
  const selectedMeasurement = String(data.get("measurement") || "current-dc");
  const measurement = measurementsByName.get(selectedMeasurement);
  const autoZeroVisible = supportsAutoZero(selectedMeasurement);
  const dcvInputZVisible = supportsDcvInputZ(selectedMeasurement);

  const payload = {
    resource,
    instrument_model: textOrNull(data.get("instrument_model")),
    csv: textOrNull(data.get("csv")),
    timeout_ms: numberOrNull(data.get("timeout_ms")),
    trigger_timeout_ms: triggerTimeoutMs(data, triggerMode),
    trigger_mode: triggerMode,
    measurement: selectedMeasurement,
    nplc: numberOrNull(data.get("nplc")),
    auto_zero: autoZeroVisible ? (data.get("auto_zero") || "on") : "on",
    auto_range: data.get("auto_range") === "on",
    measurement_range: numberOrNull(data.get("measurement_range")),
    dcv_input_impedance: dcvInputZVisible
      ? String(data.get("dcv_input_impedance") || "default")
      : null,
    vm_comp_slope: textOrNull(data.get("vm_comp_slope")),
  };

  if (supportsAcBandwidth(measurement) && data.get("ac_bandwidth_hz")) {
    payload.ac_bandwidth_hz = numberOrNull(data.get("ac_bandwidth_hz"));
  }
  if (supportsGateTime(measurement) && data.get("gate_time_s")) {
    payload.gate_time_s = numberOrNull(data.get("gate_time_s"));
  }
  if (supportsFreqPeriodTimeout(measurement) && data.get("freq_period_timeout")) {
    payload.freq_period_timeout = String(data.get("freq_period_timeout"));
  }
  if (supportsCurrentTerminal(measurement) && data.get("current_terminal")) {
    payload.current_terminal = numberOrNull(data.get("current_terminal"));
  }
  if (!customMode) {
    payload.max_samples = numberOrNull(data.get("max_samples"));
  }
  if (triggerMode === "software") {
    payload.timer_interval_s = numberOrNull(data.get("timer_interval_s"));
  }
  if (customMode) {
    payload.trigger_count = numberOrNull(data.get("trigger_count"));
    payload.sample_count = numberOrNull(data.get("sample_count"));
    payload.buffer_drain_size = numberOrNull(data.get("buffer_drain_size"));
    payload.allow_buffer_overflow_risk = data.get("allow_buffer_overflow_risk") === "on";
  }
  if (hardwareMode) {
    payload.hw_trigger_slope = String(data.get("hw_trigger_slope") || "neg");
    payload.hw_trigger_delay_s = numberOrNull(data.get("hw_trigger_delay_s"));
  }
  if (softwareTriggeredMode) {
    payload.sw_min_interval_ms = numberOrNull(data.get("sw_min_interval_ms"));
    payload.sw_queue_max = numberOrNull(data.get("sw_queue_max"));
  }
  return compactPayload(payload);
}

function compactPayload(payload) {
  return Object.fromEntries(
    Object.entries(payload).filter(([_key, value]) => value !== null)
  );
}

function applyInputLimits(limits) {
  inputLimits = limits || {};
  setNumberLimit("timeout_ms", document.querySelector("[name='timeout_ms']"));
  setNumberLimit("trigger_timeout_ms", triggerTimeoutInput);
  setNumberLimit("max_samples", document.querySelector("[name='max_samples']"));
  setNumberLimit("trigger_count", triggerCountInput);
  setNumberLimit("sample_count", sampleCountInput);
  setNumberLimit("timer_interval_s", timerIntervalInput);
  setNumberLimit("buffer_drain_size", document.querySelector("[name='buffer_drain_size']"));
  setNumberLimit("hw_trigger_delay_s", document.querySelector("[name='hw_trigger_delay_s']"));
  setNumberLimit("sw_min_interval_ms", swMinIntervalInput);
  setNumberLimit("sw_queue_max", swQueueMaxInput);
  validateSwMinInterval();
}

function setNumberLimit(name, control) {
  const limit = inputLimits[name];
  if (!control || !limit) {
    return;
  }
  if (limit.min !== undefined) {
    control.min = String(limit.min);
  }
  if (limit.max !== undefined) {
    control.max = String(limit.max);
  }
}

export function validateSwMinInterval() {
  if (!swMinIntervalInput || swMinIntervalInput.disabled) {
    swMinIntervalInput?.setCustomValidity("");
    return true;
  }
  const value = numberOrNull(swMinIntervalInput.value);
  const limit = inputLimits.sw_min_interval_ms || {};
  const max = Number(limit.max ?? 600000);
  const nonzeroMin = Number(limit.nonzero_min ?? 50);
  if (value === null || value === 0) {
    swMinIntervalInput.setCustomValidity("");
    return true;
  }
  if (!Number.isFinite(value) || value < nonzeroMin || value > max) {
    swMinIntervalInput.setCustomValidity(
      `Use 0 to disable throttling, or use ${nonzeroMin}-${max} ms.`
    );
    return false;
  }
  swMinIntervalInput.setCustomValidity("");
  return true;
}

export function triggerMetadataPayload() {
  const base = { source: "web-ui" };
  const text = String(triggerMetadataInput?.value || "").trim();
  if (!text) {
    return base;
  }
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch (_error) {
    throw new Error("Trigger metadata must be valid JSON object");
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Trigger metadata must be a JSON object");
  }
  return { source: "web-ui", ...parsed };
}

export function updateMeasurementUi() {
  const selected = measurementSelect.value || "current-dc";
  const measurement = measurementsByName.get(selected);
  const autoZeroVisible = supportsAutoZero(selected);
  autoZeroContainer.classList.toggle("is-hidden", !autoZeroVisible);
  autoZeroSelect.disabled = !autoZeroVisible;

  if (autoZeroVisible) {
    const existingAutoZero = autoZeroSelect.value || "on";
    autoZeroSelect.replaceChildren(
      optionElement("on", "On"),
      optionElement("off", "Off"),
      optionElement("once", "Once")
    );
    autoZeroSelect.value = ["on", "off", "once"].includes(existingAutoZero)
      ? existingAutoZero
      : "on";
  } else {
    autoZeroSelect.value = "on";
  }

  const acBandwidthVisible = supportsAcBandwidth(measurement);
  acBandwidthContainer.classList.toggle("is-hidden", !acBandwidthVisible);
  acBandwidthSelect.disabled = !acBandwidthVisible;
  if (acBandwidthVisible) {
    const existingAcBandwidth = acBandwidthSelect.value;
    const bandwidthOptions = measurement?.ac_bandwidth_hz_options || [];
    const defaultAcBandwidth = measurement?.defaults?.ac_bandwidth_hz;
    const bandwidthOptionElements = bandwidthOptions.map((value) =>
      optionElement(value, `${formatNumberLabel(value)} Hz`)
    );
    if (defaultAcBandwidth === null || defaultAcBandwidth === undefined) {
      bandwidthOptionElements.unshift(optionElement("", "Keep current setting"));
    }
    acBandwidthSelect.replaceChildren(...bandwidthOptionElements);
    if (defaultAcBandwidth !== null && defaultAcBandwidth !== undefined) {
      acBandwidthSelect.value = String(defaultAcBandwidth);
    } else if (bandwidthOptions.map(String).includes(String(existingAcBandwidth))) {
      acBandwidthSelect.value = existingAcBandwidth;
    } else {
      acBandwidthSelect.value = "";
    }
  } else {
    acBandwidthSelect.value = "";
  }

  const gateTimeVisible = supportsGateTime(measurement);
  gateTimeContainer.classList.toggle("is-hidden", !gateTimeVisible);
  gateTimeSelect.disabled = !gateTimeVisible;
  if (gateTimeVisible) {
    const gateTimeOptions = measurement?.gate_time_s_options || [];
    const defaultGateTime = measurement?.defaults?.gate_time_s;
    gateTimeSelect.replaceChildren(
      ...gateTimeOptions.map((value) =>
        optionElement(value, `${formatNumberLabel(value)} s`)
      )
    );
    gateTimeSelect.value = String(defaultGateTime ?? gateTimeOptions[0] ?? "");
  } else {
    gateTimeSelect.value = "";
  }

  const freqPeriodTimeoutVisible = supportsFreqPeriodTimeout(measurement);
  freqPeriodTimeoutContainer.classList.toggle("is-hidden", !freqPeriodTimeoutVisible);
  freqPeriodTimeoutSelect.disabled = !freqPeriodTimeoutVisible;
  if (freqPeriodTimeoutVisible) {
    const timeoutOptions = measurement?.freq_period_timeout_options || [];
    const defaultTimeout = measurement?.defaults?.freq_period_timeout;
    freqPeriodTimeoutSelect.replaceChildren(
      ...timeoutOptions.map((value) =>
        optionElement(value, value === "auto" ? "Auto" : "1 s")
      )
    );
    freqPeriodTimeoutSelect.value = String(defaultTimeout ?? timeoutOptions[0] ?? "");
  } else {
    freqPeriodTimeoutSelect.value = "";
  }

  const currentTerminalVisible = supportsCurrentTerminal(measurement);
  currentTerminalContainer.classList.toggle("is-hidden", !currentTerminalVisible);
  currentTerminalSelect.disabled = !currentTerminalVisible;
  if (currentTerminalVisible) {
    const existingCurrentTerminal = currentTerminalSelect.value;
    const terminalOptions = measurement?.current_terminal_options || [];
    currentTerminalSelect.replaceChildren(
      optionElement("", "Default"),
      ...terminalOptions.map((value) =>
        optionElement(value, `${formatNumberLabel(value)} A`)
      )
    );
    currentTerminalSelect.value = terminalOptions
      .map(String)
      .includes(String(existingCurrentTerminal))
      ? existingCurrentTerminal
      : "";
  } else {
    currentTerminalSelect.value = "";
  }

  rangeUnit.textContent = "";
  rangeSuffix.textContent = "";
  populateRangeOptions(measurement);
  populateNplcOptions(measurement);
  for (const element of measurementScopedControls) {
    const scopes = (element.dataset.measurementScope || "").split(",");
    const visible = scopes.includes(selected);
    element.classList.toggle("is-hidden", !visible);
    for (const control of element.querySelectorAll("input, select, textarea")) {
      control.disabled = !visible;
    }
  }
  updatePanelSummaries();
}

export function updateRangeVisibility() {
  const autoRangeEnabled = autoRangeCheckbox.checked;
  rangeContainer.classList.toggle("is-hidden", autoRangeEnabled);
  measurementRangeInput.disabled = autoRangeEnabled;
  measurementRangeInput.required = !autoRangeEnabled;
  updatePanelSummaries();
}

function populateRangeOptions(measurement) {
  const existing = measurementRangeInput.value;
  const options = measurement?.range_options || [];
  measurementRangeInput.replaceChildren(
    optionElement("", "Select range"),
    ...options.map((item) => optionElement(item.value, item.label))
  );
  if (options.some((item) => String(item.value) === existing)) {
    measurementRangeInput.value = existing;
  }
}

function populateNplcOptions(measurement) {
  const existing = nplcSelect.value || "1";
  const options = measurement?.nplc_options || [];
  nplcSelect.replaceChildren(
    ...options.map((value) => optionElement(value, formatNumberLabel(value)))
  );
  const visible = options.length > 0;
  nplcField.classList.toggle("is-hidden", !visible);
  nplcSelect.disabled = !visible;
  if (!visible) {
    return;
  }
  if (options.some((value) => String(value) === existing)) {
    nplcSelect.value = existing;
  } else if (options.some((value) => Number(value) === 1)) {
    nplcSelect.value = "1";
  }
}

function optionElement(value, text) {
  const option = document.createElement("option");
  option.value = String(value);
  option.textContent = text;
  return option;
}

function formatNumberLabel(value) {
  return Number(value).toLocaleString("en-US", { maximumSignificantDigits: 10 });
}

function isCustomMode(mode) {
  return String(mode || "").endsWith("-custom");
}

function isHardwareMode(mode) {
  return mode === "external" || mode === "external-custom";
}

function isSoftwareTriggeredMode(mode) {
  return mode === "software" || mode === "software-custom";
}

function modeScopeVisible(scope, mode) {
  if (scope === "simple") {
    return !isCustomMode(mode);
  }
  if (scope === "custom") {
    return isCustomMode(mode);
  }
  if (scope === "hardware") {
    return isHardwareMode(mode);
  }
  if (scope === "software") {
    return mode === "software";
  }
  if (scope === "software-trigger") {
    return isSoftwareTriggeredMode(mode);
  }
  if (scope === "trigger-timeout") {
    return usesTriggerTimeout(mode);
  }
  return true;
}

export function updateTriggerModeUi() {
  const mode = triggerModeSelect.value || "software";
  const customMode = isCustomMode(mode);
  for (const element of modeScopedControls) {
    const visible = modeScopeVisible(element.dataset.modeScope, mode);
    element.classList.toggle("is-hidden", !visible);
    for (const control of element.querySelectorAll("input, select, textarea")) {
      control.disabled = !visible;
    }
  }
  triggerCountInput.required = customMode;
  sampleCountInput.required = customMode;

  const isSoftware = mode === "software";
  const timerEnabled = isSoftware && timerTriggerCheckbox.checked;
  timerIntervalContainer.classList.toggle("is-hidden", !timerEnabled);
  timerIntervalInput.disabled = !timerEnabled;
  timerIntervalInput.required = timerEnabled;

  if (isSoftware) {
    for (const container of [
      swMinIntervalContainer,
      swQueueMaxContainer,
      triggerMetadataContainer,
    ]) {
      container.classList.toggle("is-hidden", timerEnabled);
      for (const control of container.querySelectorAll("input, select, textarea")) {
        control.disabled = timerEnabled;
      }
    }
  }
  validateSwMinInterval();
  updateTriggerButtonUi();
  updatePanelSummaries();
}

export function updateTriggerButtonUi() {
  const mode = triggerModeSelect.value || "software";
  const timerActive = mode === "software" && timerTriggerCheckbox.checked;
  const visible = mode === "software-custom" || (mode === "software" && !timerActive);
  triggerRunButton.classList.toggle("is-hidden", !visible);
  triggerRunButton.disabled = !visible;
}

export function updatePanelSummaries() {
  const runSummary = document.querySelector("[data-summary-for='run-setup']");
  const measurementSummary = document.querySelector(
    "[data-summary-for='measurement-options']"
  );
  const triggerSummary = document.querySelector("[data-summary-for='trigger-options']");
  if (runSummary) {
    const measurement = measurementSelect.value || "current-dc";
    const mode = triggerModeSelect.value || "software";
    const maxSamples = document.querySelector("[name='max_samples']")?.value;
    runSummary.textContent = `${capitalizeFirst(mode)} / ${measurement}${
      maxSamples ? ` / max ${maxSamples}` : ""
    }`;
  }
  if (measurementSummary) {
    const selectedMeasurement = measurementSelect.value || "current-dc";
    const measurement = measurementsByName.get(selectedMeasurement);
    const frequencyOrPeriod = ["frequency", "period"].includes(selectedMeasurement);
    const autoZeroText = supportsAutoZero(selectedMeasurement) && autoZeroSelect.value
      ? `Auto zero ${autoZeroSelect.value}`
      : "";
    measurementSummary.textContent = [
      autoRangeCheckbox.checked ? "Auto range" : "Manual range",
      autoZeroText,
      (!nplcSelect.disabled && nplcSelect.value) ? `NPLC ${nplcSelect.value}` : "",
      (supportsAcBandwidth(measurement) && acBandwidthSelect.value)
        ? (frequencyOrPeriod
          ? `AC Filter >${acBandwidthSelect.value} Hz`
          : `AC Band ${acBandwidthSelect.value} Hz`)
        : "",
      (supportsGateTime(measurement) && gateTimeSelect.value)
        ? `Gate ${gateTimeSelect.value} s`
        : "",
      (supportsFreqPeriodTimeout(measurement) && freqPeriodTimeoutSelect.value)
        ? `Timeout ${freqPeriodTimeoutSelect.value}`
        : "",
      (supportsCurrentTerminal(measurement) && currentTerminalSelect.value)
        ? `Terminal ${currentTerminalSelect.value} A`
        : "",
    ].filter(Boolean).join(", ");
  }
  if (triggerSummary) {
    const mode = triggerModeSelect.value || "software";
    const timerEnabled = mode === "software" && timerTriggerCheckbox.checked;
    triggerSummary.textContent = timerEnabled
      ? `Timer ${timerIntervalInput.value || "unset"} s`
      : `${capitalizeFirst(mode)} trigger`;
  }
}

function applyAppMetadata(app) {
  if (!subtitle) {
    return;
  }
  const version = app?.version;
  subtitle.textContent = version ? `Unofficial Tool v${version}` : "Unofficial Tool";
}

export async function loadCapabilities(model = null) {
  const selectedModel = textOrNull(model || instrumentModelSelect?.value);
  const url = selectedModel
    ? `/api/capabilities?model=${encodeURIComponent(selectedModel)}`
    : "/api/capabilities";
  const previousMeasurement = measurementSelect.value;
  const previousTriggerMode = triggerModeSelect.value;
  const capabilities = await api(url);
  applyAppMetadata(capabilities.app);
  applyInputLimits(capabilities.limits);
  if (instrumentModelSelect) {
    const forcedModel = textOrNull(instrumentModelSelect.value);
    const profileOptions = capabilities.available_profiles || [];
    instrumentModelSelect.replaceChildren(
      optionElement("", "Auto-detect on start"),
      ...profileOptions.map((profile) =>
        optionElement(profile.model, profile.model)
      )
    );
    instrumentModelSelect.value = forcedModel || "";
  }
  measurementsByName = new Map(
    capabilities.measurements.map((item) => [item.name, item])
  );
  measurementSelect.replaceChildren(
    ...capabilities.measurements.map((item) =>
      optionElement(item.name, `${capitalizeFirst(item.name)} (${item.unit})`)
    )
  );
  if (measurementsByName.has(previousMeasurement)) {
    measurementSelect.value = previousMeasurement;
  }
  updateMeasurementUi();
  triggerModeSelect.replaceChildren(
    ...capabilities.trigger_modes.map((mode) =>
      optionElement(mode, capitalizeFirst(mode))
    )
  );
  if (capabilities.trigger_modes.includes(previousTriggerMode)) {
    triggerModeSelect.value = previousTriggerMode;
  }
  updateTriggerModeUi();
}
