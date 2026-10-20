import { api } from "./api.js";
import { t } from "./i18n.js";
import {
  buildRunPayload,
  numberOrNull,
  textOrNull,
} from "./run_form_payload.js";
import {
  featureAvailability,
  findProductSupportScope,
  isCustomMode,
  isHardwareMode,
  isSoftwareTriggeredMode,
  modeScopeVisible,
  supportsAcBandwidth,
  supportsAutoZero,
  supportsCurrentTerminal,
  supportsDcvInputZ,
  supportsFreqPeriodTimeout,
  supportsGateTime,
  usesTriggerTimeout as modeUsesTriggerTimeout,
} from "./run_form_support.js";
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
  executionModeInputs,
  visaLibrarySelect,
  measurementRangeInput,
  measurementScopedControls,
  measurementSelect,
  modelSupportLimits,
  modelSupportOpen,
  modelSupportPending,
  modelSupportStatus,
  modeScopedControls,
  nplcField,
  nplcSelect,
  rangeContainer,
  rangeSuffix,
  rangeUnit,
  resourceInput,
  sampleCountInput,
  startRunButton,
  subtitle,
  swMinIntervalContainer,
  swMinIntervalInput,
  swQueueMaxContainer,
  swQueueMaxInput,
  timerIntervalContainer,
  timerIntervalInput,
  timerTriggerCheckbox,
  triggerCountInfiniteCheckbox,
  triggerCountInput,
  triggerMetadataContainer,
  triggerMetadataInput,
  triggerModeSelect,
  triggerRunButton,
  triggerTimeoutInput,
} from "./dom.js";

let measurementsByName = new Map();
let supportedTriggerModes = [];
let triggerModeMetadata = {};
let liveSupport = null;
let liveSupportByModel = new Map();
let detectedInstrumentModel = null;
let inputLimits = {};
let latestSupportSummary = null;
let capabilitiesLoaded = false;

const MEASUREMENT_MESSAGE_KEYS = Object.freeze({
  "current-dc": "measurement.option.current_dc",
  "voltage-dc": "measurement.option.voltage_dc",
  "voltage-dc-ratio": "measurement.option.voltage_dc_ratio",
  "current-ac": "measurement.option.current_ac",
  "voltage-ac": "measurement.option.voltage_ac",
  frequency: "measurement.option.frequency",
  period: "measurement.option.period",
  "resistance-2w": "measurement.option.resistance_2w",
  "resistance-4w": "measurement.option.resistance_4w",
});

const TRIGGER_MESSAGE_KEYS = Object.freeze({
  software: "trigger.option.software",
  immediate: "trigger.option.immediate",
  external: "trigger.option.external",
  "immediate-custom": "trigger.option.immediate_custom",
  "software-custom": "trigger.option.software_custom",
  "external-custom": "trigger.option.external_custom",
});

function bindTranslation(element, binding, key, params) {
  element.setAttribute(binding, key);
  if (params !== undefined) {
    element.setAttribute("data-i18n-params", JSON.stringify(params));
  }
  return t(key, params);
}

function setTranslatedText(element, key, params) {
  element.textContent = bindTranslation(element, "data-i18n", key, params);
}

function translatedOptionElement(value, key, params) {
  const option = optionElement(value, "");
  setTranslatedText(option, key, params);
  return option;
}

function measurementDisplayName(value) {
  const key = MEASUREMENT_MESSAGE_KEYS[value];
  return key ? t(key) : capitalizeFirst(value);
}

function triggerDisplayName(value) {
  const key = TRIGGER_MESSAGE_KEYS[value];
  return key ? t(key) : capitalizeFirst(value);
}

function measurementOptionElement(item) {
  const key = MEASUREMENT_MESSAGE_KEYS[item.name];
  if (!key) {
    return featureOptionElement(
      item.name,
      `${capitalizeFirst(item.name)} (${item.unit})`,
      "measurement"
    );
  }
  return featureOptionElement(
    item.name,
    t("measurement.option_label", {
      name: t(key),
      canonical: item.name,
      unit: item.unit,
    }),
    "measurement",
    "measurement.option_label",
    { name: t(key), canonical: item.name, unit: item.unit }
  );
}

function triggerOptionElement(mode) {
  const key = TRIGGER_MESSAGE_KEYS[mode];
  if (!key) {
    return featureOptionElement(mode, capitalizeFirst(mode), "trigger_mode");
  }
  return featureOptionElement(
    mode,
    t("trigger.option_label", { name: t(key), canonical: mode }),
    "trigger_mode",
    "trigger.option_label",
    { name: t(key), canonical: mode }
  );
}

function currentProductSupportScopes() {
  const noHardware = [...executionModeInputs].some(
    (input) => input.checked && input.value !== "real"
  );
  if (noHardware) return [findProductSupportScope("", liveSupport)];
  const candidates = detectedInstrumentModel
    ? [liveSupportByModel.get(detectedInstrumentModel)]
    : [...liveSupportByModel.values()];
  return candidates.map((support) => findProductSupportScope(
    resourceInput?.value, support, visaLibrarySelect?.value
  ));
}

export function productLiveAvailability() {
  if ([...executionModeInputs].some((input) => input.checked && input.value !== "real")) {
    return { available: true, reasonKey: null };
  }
  const results = currentProductSupportScopes().map((scope) => {
    const measurement = featureAvailability(scope, "measurement", measurementSelect.value);
    if (!measurement.available) return measurement;
    const trigger = featureAvailability(scope, "trigger_mode", triggerModeSelect.value);
    if (!trigger.available) return trigger;
    const customFeature = customAcquisitionFeatureValue();
    return customFeature
      ? featureAvailability(scope, "custom_acquisition", customFeature)
      : trigger;
  });
  return results.find((result) => result.available)
    || results[0] || featureAvailability(null, "measurement", measurementSelect.value);
}

function customAcquisitionFeatureValue() {
  const mode = triggerModeSelect.value;
  if (!isCustomMode(mode)) return null;
  const infinite = triggerCountInfiniteCheckbox.checked;
  const stop = document.querySelector("[name='stop_on_overflow']")?.checked;
  const monitor = document.querySelector("[name='monitor_overflow']")?.checked;
  if (!infinite && !stop && !monitor) return null;
  return `${mode}:${infinite ? "infinite" : "finite"}:${stop ? "stop_on_overflow" : "monitor"}`;
}

export function updateStartButtonUi(active = startRunButton.dataset.runActive === "true") {
  const availability = productLiveAvailability();
  startRunButton.dataset.runActive = String(active);
  startRunButton.disabled = active
    || startRunButton.dataset.executionPending === "true" || !availability.available;
  startRunButton.title = availability.available ? "" : bindTranslation(
    startRunButton, "data-i18n-title", availability.reasonKey
  );
  if (availability.available) startRunButton.removeAttribute("data-i18n-title");
}

function featureOptionElement(value, text, featureKind, textKey, textParams) {
  const results = currentProductSupportScopes().map(
    (scope) => featureAvailability(scope, featureKind, value)
  );
  const availability = results.find((result) => result.available)
    || results[0] || featureAvailability(null, featureKind, value);
  const option = optionElement(value, text);
  if (availability.available && textKey) {
    setTranslatedText(option, textKey, textParams);
  } else if (!availability.available) {
    const reason = t(availability.reasonKey);
    setTranslatedText(option, "support.unavailable_option", { label: text, reason });
    option.title = bindTranslation(
      option,
      "data-i18n-title",
      availability.reasonKey
    );
  }
  option.disabled = !availability.available;
  option.dataset.validationStatus = availability.validationStatus;
  return option;
}

function selectAvailableOption(select, previousValue) {
  const previous = [...select.options].find(
    (option) => option.value === previousValue && !option.disabled
  );
  const selected = previous || [...select.options].find((option) => !option.disabled);
  if (selected) {
    select.value = selected.value;
  }
}

function restoreSelectValue(select, previousValue) {
  if ([...select.options].some((option) => option.value === previousValue)) {
    select.value = previousValue;
  }
}

function populateFeatureOptions(
  previousMeasurement,
  previousTriggerMode,
  preserveUnavailableSelections = false
) {
  measurementSelect.replaceChildren(
    ...[...measurementsByName.values()].map(measurementOptionElement)
  );
  if (preserveUnavailableSelections) {
    restoreSelectValue(measurementSelect, previousMeasurement);
  } else {
    selectAvailableOption(measurementSelect, previousMeasurement);
  }

  triggerModeSelect.replaceChildren(
    ...supportedTriggerModes.map(triggerOptionElement)
  );
  if (preserveUnavailableSelections) {
    restoreSelectValue(triggerModeSelect, previousTriggerMode);
  } else {
    selectAvailableOption(triggerModeSelect, previousTriggerMode);
  }
}

export function updateFeatureAvailability(detectedModel = null) {
  detectedInstrumentModel = detectedModel;
  const previousMeasurement = measurementSelect.value;
  const previousTriggerMode = triggerModeSelect.value;
  populateFeatureOptions(previousMeasurement, previousTriggerMode);
  updateMeasurementUi();
  updateTriggerModeUi();
}

export { numberOrNull, textOrNull };

export function capitalizeFirst(value) {
  const text = String(value || "");
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
}

export { supportsAutoZero, supportsDcvInputZ };

export function usesTriggerTimeout(mode) {
  return modeUsesTriggerTimeout(mode, triggerModeMetadata);
}

export function formPayload() {
  const data = new FormData(form);
  const selectedMeasurement = String(data.get("measurement") || "current-dc");
  const values = {
    resource: data.get("resource"),
    visa_library: data.get("visa_library"),
    instrument_model: data.get("instrument_model"),
    csv_enabled: data.get("csv_enabled"),
    csv: data.get("csv"),
    csv_format: data.get("csv_format"),
    csv_elapsed: data.get("csv_elapsed"),
    csv_delta: data.get("csv_delta"),
    timeout_ms: data.get("timeout_ms"),
    trigger_timeout_ms: data.get("trigger_timeout_ms"),
    trigger_mode: data.get("trigger_mode"),
    measurement: selectedMeasurement,
    nplc: data.get("nplc"),
    auto_zero: data.get("auto_zero"),
    auto_range: data.get("auto_range"),
    measurement_range: data.get("measurement_range"),
    dcv_input_impedance: data.get("dcv_input_impedance"),
    vm_comp_slope: data.get("vm_comp_slope"),
    ac_bandwidth_hz: data.get("ac_bandwidth_hz"),
    gate_time_s: data.get("gate_time_s"),
    freq_period_timeout: data.get("freq_period_timeout"),
    current_terminal: data.get("current_terminal"),
    max_samples: data.get("max_samples"),
    timer_interval_s: data.get("timer_interval_s"),
    trigger_count: data.get("trigger_count"),
    trigger_count_infinite: data.get("trigger_count_infinite"),
    monitor_overflow: document.querySelector("[name='monitor_overflow']")?.checked ? "on" : null,
    stop_on_overflow: data.get("stop_on_overflow"),
    sample_count: data.get("sample_count"),
    buffer_drain_size: data.get("buffer_drain_size"),
    allow_buffer_overflow_risk: data.get("allow_buffer_overflow_risk"),
    hw_trigger_slope: data.get("hw_trigger_slope"),
    hw_trigger_delay_s: data.get("hw_trigger_delay_s"),
    sw_min_interval_ms: data.get("sw_min_interval_ms"),
    sw_queue_max: data.get("sw_queue_max"),
  };
  return buildRunPayload(values, {
    measurement: measurementsByName.get(selectedMeasurement),
    triggerModeMetadata,
  });
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
      t("validation.interval_range", { min: nonzeroMin, max })
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
    throw new Error(t("error.trigger_metadata_invalid_json"));
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(t("error.trigger_metadata_not_object"));
  }
  return { source: "web-ui", ...parsed };
}

export function updateMeasurementUi() {
  const selected = measurementSelect.value || "current-dc";
  const measurement = measurementsByName.get(selected);
  const autoZeroVisible = supportsAutoZero(measurement);
  autoZeroContainer.classList.toggle("is-hidden", !autoZeroVisible);
  autoZeroSelect.disabled = !autoZeroVisible;

  if (autoZeroVisible) {
    const existingAutoZero = autoZeroSelect.value || "on";
    const autoZeroOptions = measurement.auto_zero_options;
    autoZeroSelect.replaceChildren(
      ...autoZeroOptions.map((value) =>
        translatedOptionElement(
          value,
          value === "once" ? "measurement.auto_zero_once" : `common.${value}`
        )
      )
    );
    autoZeroSelect.value = autoZeroOptions.includes(existingAutoZero)
      ? existingAutoZero
      : String(autoZeroOptions[0] || "on");
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
      translatedOptionElement(value, "measurement.value_hz", {
        value: formatNumberLabel(value),
      })
    );
    if (defaultAcBandwidth === null || defaultAcBandwidth === undefined) {
      bandwidthOptionElements.unshift(
        translatedOptionElement("", "measurement.keep_current_setting")
      );
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
        translatedOptionElement(value, "measurement.value_seconds", {
          value: formatNumberLabel(value),
        })
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
        value === "auto"
          ? translatedOptionElement(value, "common.auto")
          : translatedOptionElement(value, "measurement.value_seconds", { value: 1 })
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
      translatedOptionElement("", "common.default"),
      ...terminalOptions.map((value) =>
        translatedOptionElement(value, "measurement.terminal_value", {
          value: formatNumberLabel(value),
        })
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
    const isDcvInputImpedanceControl =
      element.querySelectorAll("[name='dcv_input_impedance']").length > 0;
    const visible = isDcvInputImpedanceControl
      ? supportsDcvInputZ(measurement)
      : scopes.includes(selected);
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
    translatedOptionElement("", "measurement.select_range"),
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

function replaceOptionsPreservingValue(select, options) {
  const previousValue = select.value;
  select.replaceChildren(...options);
  restoreSelectValue(select, previousValue);
}

function refreshMeasurementOptionPresentation() {
  const measurement = measurementsByName.get(measurementSelect.value);
  if (autoZeroSelect.options.length > 0) {
    const metadataValues = measurement?.auto_zero_options || [];
    const values = metadataValues.length > 0
      ? metadataValues
      : [...autoZeroSelect.options].map((option) => option.value);
    replaceOptionsPreservingValue(
      autoZeroSelect,
      values.map((value) =>
        translatedOptionElement(
          value,
          value === "once" ? "measurement.auto_zero_once" : `common.${value}`
        )
      )
    );
  }
  if (acBandwidthSelect.options.length > 0) {
    const includeKeepCurrent = [...acBandwidthSelect.options].some(
      (option) => option.value === ""
    );
    const values = measurement?.ac_bandwidth_hz_options || [...acBandwidthSelect.options]
      .map((option) => option.value)
      .filter(Boolean);
    const options = values.map((value) =>
      translatedOptionElement(value, "measurement.value_hz", {
        value: formatNumberLabel(value),
      })
    );
    if (includeKeepCurrent) {
      options.unshift(translatedOptionElement("", "measurement.keep_current_setting"));
    }
    replaceOptionsPreservingValue(acBandwidthSelect, options);
  }
  if (gateTimeSelect.options.length > 0) {
    const values = measurement?.gate_time_s_options || [...gateTimeSelect.options]
      .map((option) => option.value);
    replaceOptionsPreservingValue(
      gateTimeSelect,
      values.map((value) =>
        translatedOptionElement(value, "measurement.value_seconds", {
          value: formatNumberLabel(value),
        })
      )
    );
  }
  if (freqPeriodTimeoutSelect.options.length > 0) {
    const values = measurement?.freq_period_timeout_options || [...freqPeriodTimeoutSelect.options]
      .map((option) => option.value);
    replaceOptionsPreservingValue(
      freqPeriodTimeoutSelect,
      values.map((value) =>
        value === "auto"
          ? translatedOptionElement(value, "common.auto")
          : translatedOptionElement(value, "measurement.value_seconds", {
            value: String(value).replace(/s$/, ""),
          })
      )
    );
  }
  if (currentTerminalSelect.options.length > 0) {
    const includeDefault = [...currentTerminalSelect.options].some(
      (option) => option.value === ""
    );
    const values = measurement?.current_terminal_options || [...currentTerminalSelect.options]
      .map((option) => option.value)
      .filter(Boolean);
    const options = values.map((value) =>
      translatedOptionElement(value, "measurement.terminal_value", {
        value: formatNumberLabel(value),
      })
    );
    if (includeDefault) {
      options.unshift(translatedOptionElement("", "common.default"));
    }
    replaceOptionsPreservingValue(currentTerminalSelect, options);
  }
  if (measurementRangeInput.options.length > 0) {
    const options = [...measurementRangeInput.options].map((option) =>
      option.value === ""
        ? translatedOptionElement("", "measurement.select_range")
        : optionElement(option.value, option.textContent)
    );
    replaceOptionsPreservingValue(measurementRangeInput, options);
  }
  if (nplcSelect.options.length > 0) {
    replaceOptionsPreservingValue(
      nplcSelect,
      [...nplcSelect.options].map((option) =>
        optionElement(option.value, formatNumberLabel(option.value))
      )
    );
  }
}

function formatNumberLabel(value) {
  return Number(value).toLocaleString("en-US", { maximumSignificantDigits: 10 });
}

export function updateTriggerModeUi() {
  const mode = triggerModeSelect.value || "software";
  const customMode = isCustomMode(mode);
  for (const element of modeScopedControls) {
    const visible = modeScopeVisible(
      element.dataset.modeScope,
      mode,
      triggerModeMetadata
    );
    element.classList.toggle("is-hidden", !visible);
    for (const control of element.querySelectorAll("input, select, textarea")) {
      control.disabled = !visible;
    }
  }
  const infiniteTriggerCount =
    customMode && triggerCountInfiniteCheckbox.checked;
  const monitorCheckbox = document.querySelector("[name='monitor_overflow']");
  const stopCheckbox = document.querySelector("[name='stop_on_overflow']");
  if (monitorCheckbox) {
    const forced = infiniteTriggerCount || (customMode && stopCheckbox?.checked);
    if (monitorCheckbox.dataset.manualChecked === undefined) {
      monitorCheckbox.dataset.manualChecked = String(monitorCheckbox.checked);
    }
    monitorCheckbox.checked = forced || monitorCheckbox.dataset.manualChecked === "true";
    monitorCheckbox.disabled = !customMode || forced;
  }
  triggerCountInput.required = customMode && !infiniteTriggerCount;
  triggerCountInput.disabled = !customMode || infiniteTriggerCount;
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
  triggerRunButton.disabled =
    !visible || triggerRunButton.dataset.executionDisabled === "true";
}

export function updatePanelSummaries() {
  updateStartButtonUi();
  const outputSummary = document.querySelector("[data-summary-for='output-settings']");
  if (outputSummary) {
    const csvOn = document.querySelector("#csv-enabled-checkbox")?.checked;
    const format = document.querySelector("#csv-format")?.value || "data";
    const selected = [
      document.querySelector("#csv-elapsed")?.checked ? t("output.summary_elapsed") : "",
      document.querySelector("#csv-delta")?.checked ? "Δt" : "",
    ].filter(Boolean).join(" + ");
    setTranslatedText(outputSummary, csvOn ? "output.summary" : "output.summary_disabled", {
      format: format === "full" ? "Full" : "Data",
      columns: selected ? " · " + selected : "",
    });
  }
  const runSummary = document.querySelector("[data-summary-for='run-setup']");
  const measurementSummary = document.querySelector(
    "[data-summary-for='measurement-options']"
  );
  const triggerSummary = document.querySelector("[data-summary-for='trigger-options']");
  if (runSummary) {
    const measurement = measurementSelect.value || "current-dc";
    const mode = triggerModeSelect.value || "software";
    const maxSamples = document.querySelector("[name='max_samples']")?.value;
    const params = {
      trigger: t("trigger.option_label", {
        name: triggerDisplayName(mode),
        canonical: mode,
      }),
      measurement: t("measurement.summary_label", {
        name: measurementDisplayName(measurement),
        canonical: measurement,
      }),
    };
    if (maxSamples) {
      params.max = maxSamples;
      setTranslatedText(runSummary, "run.summary_with_max", params);
    } else {
      setTranslatedText(runSummary, "run.summary", params);
    }
  }
  if (measurementSummary) {
    const selectedMeasurement = measurementSelect.value || "current-dc";
    const measurement = measurementsByName.get(selectedMeasurement);
    const frequencyOrPeriod = ["frequency", "period"].includes(selectedMeasurement);
    const autoZeroText = supportsAutoZero(measurement) && autoZeroSelect.value
      ? t("measurement.summary.auto_zero", {
        value: autoZeroSelect.value === "once"
          ? t("measurement.auto_zero_once")
          : t(`common.${autoZeroSelect.value}`),
      })
      : "";
    const fragments = [
      t(autoRangeCheckbox.checked
        ? "measurement.summary.auto_range"
        : "measurement.summary.manual_range"),
      autoZeroText,
      (!nplcSelect.disabled && nplcSelect.value)
        ? t("measurement.summary.nplc", { value: nplcSelect.value })
        : "",
      (supportsAcBandwidth(measurement) && acBandwidthSelect.value)
        ? (frequencyOrPeriod
          ? t("measurement.summary.ac_filter", { value: acBandwidthSelect.value })
          : t("measurement.summary.ac_band", { value: acBandwidthSelect.value }))
        : "",
      (supportsGateTime(measurement) && gateTimeSelect.value)
        ? t("measurement.summary.gate", { value: gateTimeSelect.value })
        : "",
      (supportsFreqPeriodTimeout(measurement) && freqPeriodTimeoutSelect.value)
        ? t("measurement.summary.timeout", { value: freqPeriodTimeoutSelect.value })
        : "",
      (supportsCurrentTerminal(measurement) && currentTerminalSelect.value)
        ? t("measurement.summary.terminal", { value: currentTerminalSelect.value })
        : "",
    ].filter(Boolean);
    setTranslatedText(measurementSummary, "measurement.summary", {
      fragments: fragments.join(t("measurement.summary.separator")),
    });
  }
  if (triggerSummary) {
    const mode = triggerModeSelect.value || "software";
    const timerEnabled = mode === "software" && timerTriggerCheckbox.checked;
    if (timerEnabled) {
      setTranslatedText(triggerSummary, "trigger.summary.timer", {
        value: timerIntervalInput.value || t("common.unset"),
      });
    } else {
      setTranslatedText(triggerSummary, "trigger.summary.mode", {
        mode: t("trigger.option_label", {
          name: triggerDisplayName(mode),
          canonical: mode,
        }),
      });
    }
  }
}

function applyAppMetadata(app) {
  if (!subtitle) {
    return;
  }
  const version = app?.version;
  if (version) {
    setTranslatedText(subtitle, "app.unofficial_tool_version", { version });
  } else {
    setTranslatedText(subtitle, "app.unofficial_tool");
  }
}

function translateSemanticKeyOrFallback(key, fallback) {
  const safeFallback = String(fallback || "");
  if (typeof key !== "string" || !key.trim()) {
    return safeFallback;
  }
  const translated = t(key);
  return translated === key ? safeFallback : translated;
}

function renderSupportSummary(summary) {
  if (!modelSupportStatus) {
    return;
  }
  const model = summary?.model || t("support.summary.selected_model");
  const statusFallback =
    summary?.status_text || t("support.summary.status_unavailable");
  const statusText = translateSemanticKeyOrFallback(
    summary?.status_key,
    statusFallback
  );
  const validationStatus = summary?.validation_status || "unknown";
  const transport =
    summary?.transport_scope || t("support.summary.unspecified_transport");
  const backend =
    summary?.backend_scope || t("support.summary.unspecified_backend");
  if (summary?.is_fallback_capability_view) {
    const capabilityProfile = summary?.capability_profile || model;
    const runtimeNoteFallback =
      summary?.runtime_driver_note || t("support.runtime_driver.detected_idn");
    const runtimeNote = translateSemanticKeyOrFallback(
      summary?.runtime_driver_note_key,
      runtimeNoteFallback
    );
    setTranslatedText(modelSupportStatus, "support.summary.auto_detect_status", {
      profile: capabilityProfile,
      runtime_note: runtimeNote,
      validation_status: validationStatus,
      transport,
      backend,
    });
  } else {
    setTranslatedText(modelSupportStatus, "support.summary.profile_status", {
      model,
      status: statusText,
      validation_status: validationStatus,
      transport,
      backend,
    });
  }
  modelSupportOpen.textContent = listSummary(
    summary?.open_workflows,
    summary?.open_workflow_keys
  );
  modelSupportLimits.textContent = listSummary(
    summary?.limits,
    summary?.limit_keys
  );
  modelSupportPending.textContent = listSummary(
    summary?.pending,
    summary?.pending_keys
  );
}

function listSummary(items, keys) {
  const proseValues = Array.isArray(items) ? items : [];
  const semanticKeys = Array.isArray(keys) ? keys : [];
  const values = proseValues.flatMap((item, index) => {
    const fallback = String(item || "");
    return fallback
      ? [translateSemanticKeyOrFallback(semanticKeys[index], fallback)]
      : [];
  });
  return values.length ? values.join(", ") : t("support.summary.none");
}

export function refreshSupportSummaryPresentation() {
  renderSupportSummary(latestSupportSummary);
}

export function refreshRunFormPresentation() {
  if (capabilitiesLoaded) {
    const previousMeasurement = measurementSelect.value;
    const previousTriggerMode = triggerModeSelect.value;
    populateFeatureOptions(previousMeasurement, previousTriggerMode, true);
    refreshMeasurementOptionPresentation();
  }
  validateSwMinInterval();
  updatePanelSummaries();
  refreshSupportSummaryPresentation();
}

let capabilitiesRevision = 0;

export function invalidateCapabilities() {
  capabilitiesRevision += 1;
}

export async function loadCapabilities(model = null, resource = null) {
  const revision = ++capabilitiesRevision;
  const selectedModel = textOrNull(model || instrumentModelSelect?.value);
  const url = selectedModel
    ? `/api/capabilities?model=${encodeURIComponent(selectedModel)}`
    : "/api/capabilities";
  const previousMeasurement = measurementSelect.value;
  const previousTriggerMode = triggerModeSelect.value;
  const capabilities = await api(url);
  if (revision !== capabilitiesRevision || (resource !== null && resource !== resourceInput.value.trim())) return null;
  // Cache policy by model, independently of the expected model or scanned identity.
  const supports = new Map(liveSupportByModel);
  const profileModel = capabilities.instrument_profile?.model
    || selectedModel || capabilities.support_summary?.model;
  if (profileModel) {
    supports.set(profileModel, capabilities.support?.["start-trigger-record"]?.live);
  }
  const missingProfiles = (capabilities.available_profiles || []).filter(
    (profile) => !supports.has(profile.model)
  );
  const otherCapabilities = await Promise.all(missingProfiles.map(async (profile) => [
    profile.model, await api(`/api/capabilities?model=${encodeURIComponent(profile.model)}`),
  ]));
  if (revision !== capabilitiesRevision || (resource !== null && resource !== resourceInput.value.trim())) return null;
  for (const [modelName, payload] of otherCapabilities) {
    supports.set(modelName, payload.support?.["start-trigger-record"]?.live);
  }
  liveSupportByModel = supports;
  applyAppMetadata(capabilities.app);
  applyInputLimits(capabilities.limits);
  latestSupportSummary = capabilities.support_summary ?? null;
  refreshSupportSummaryPresentation();
  liveSupport = capabilities.support?.["start-trigger-record"]?.live || null;
  if (instrumentModelSelect) {
    const forcedModel = textOrNull(instrumentModelSelect.value);
    const profileOptions = [...(capabilities.available_profiles || [])].sort((a, b) =>
      String(a.model || "").localeCompare(String(b.model || ""))
    );
    instrumentModelSelect.replaceChildren(
      translatedOptionElement("", "device.auto_detect"),
      ...profileOptions.map((profile) =>
        translatedOptionElement(profile.model, "device.require_model", {
          model: profile.model,
        })
      )
    );
    instrumentModelSelect.value = forcedModel || "";
  }
  measurementsByName = new Map(
    capabilities.measurements.map((item) => [item.name, item])
  );
  supportedTriggerModes = [...capabilities.trigger_modes];
  triggerModeMetadata = capabilities.trigger_mode_metadata || {};
  capabilitiesLoaded = true;
  populateFeatureOptions(previousMeasurement, previousTriggerMode);
  updateMeasurementUi();
  updateTriggerModeUi();
  return capabilities;
}
