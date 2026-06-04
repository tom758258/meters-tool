const form = document.querySelector("#run-form");
const statusState = document.querySelector("#status-state");
const statusCaptured = document.querySelector("#status-captured");
const statusErrors = document.querySelector("#status-errors");
const statusCsv = document.querySelector("#status-csv");
const latestStatus = document.querySelector("#latest-status");
const fatalError = document.querySelector("#fatal-error");
const cleanupStatus = document.querySelector("#cleanup-status");
const rawStatus = document.querySelector("#raw-status");
const resourceInput = document.querySelector("#resource");
const resourceSelect = document.querySelector("#resource-select");
const triggerRunButton = document.querySelector("#trigger-run");
const measurementSelect = document.querySelector("#measurement");
const measurementRangeInput = document.querySelector("#measurement-range");
const autoRangeCheckbox = document.querySelector("[name='auto_range']");
const rangeContainer = document.querySelector("#range-container");
const rangeUnit = document.querySelector("#range-unit");
const rangeSuffix = document.querySelector("#range-suffix");
const nplcField = document.querySelector("#nplc-field");
const nplcSelect = document.querySelector("#nplc");
const triggerModeSelect = document.querySelector("#trigger-mode");
const timerIntervalInput = document.querySelector("[name='timer_interval_s']");
const triggerOptionsPanel = document.querySelector("#trigger-options-panel");
const modeScopedControls = [...document.querySelectorAll("[data-mode-scope]")];
const measurementScopedControls = [
  ...document.querySelectorAll("[data-measurement-scope]"),
];
const DEFAULT_TRIGGER_TIMEOUT_MS = 10000;
let measurementsByName = new Map();

function numberOrNull(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  return Number(value);
}

function textOrNull(value) {
  const text = String(value || "").trim();
  return text ? text : null;
}

function triggerTimeoutMs(data, hardwareMode) {
  return numberOrNull(
    hardwareMode ? data.get("trigger_timeout_ms") : DEFAULT_TRIGGER_TIMEOUT_MS
  );
}

function formPayload() {
  const data = new FormData(form);
  const resource = String(data.get("resource") || "").trim();
  const triggerMode = textOrNull(data.get("trigger_mode")) || "software";
  const customMode = isCustomMode(triggerMode);
  const hardwareMode = isHardwareMode(triggerMode);
  const softwareTriggeredMode = isSoftwareTriggeredMode(triggerMode);
  const payload = {
    resource,
    csv: textOrNull(data.get("csv")),
    timeout_ms: numberOrNull(data.get("timeout_ms")),
    trigger_timeout_ms: triggerTimeoutMs(data, hardwareMode),
    sw_queue_max: 0,
    trigger_mode: triggerMode,
    measurement: String(data.get("measurement") || "current-dc"),
    nplc: numberOrNull(data.get("nplc")),
    auto_zero: data.get("auto_zero") === "on",
    auto_range: data.get("auto_range") === "on",
    measurement_range: numberOrNull(data.get("measurement_range")),
    dcv_input_impedance: String(data.get("dcv_input_impedance") || "default"),
    vm_comp_slope: textOrNull(data.get("vm_comp_slope")),
  };
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
  }
  return compactPayload(payload);
}

function compactPayload(payload) {
  return Object.fromEntries(
    Object.entries(payload).filter(([_key, value]) => value !== null)
  );
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(formatApiError(payload, response.statusText));
  }
  return payload;
}

function formatApiError(payload, fallback) {
  const detail = payload.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const location = Array.isArray(item.loc) ? item.loc.join(".") : "";
        return location ? `${location}: ${item.msg}` : item.msg;
      })
      .join("; ");
  }
  if (detail) {
    return JSON.stringify(detail);
  }
  return fallback;
}

function updateMeasurementUi() {
  const selected = measurementSelect.value || "current-dc";
  const measurement = measurementsByName.get(selected);
  const unit = measurement?.unit || "";
  rangeUnit.textContent = "";
  rangeSuffix.textContent = "";
  populateRangeOptions(measurement);
  populateNplcOptions(measurement);
  for (const element of measurementScopedControls) {
    const visible = element.dataset.measurementScope === selected;
    element.classList.toggle("is-hidden", !visible);
    for (const control of element.querySelectorAll("input, select, textarea")) {
      control.disabled = !visible;
    }
  }
}

function updateRangeVisibility() {
  const autoRangeEnabled = autoRangeCheckbox.checked;
  rangeContainer.classList.toggle("is-hidden", autoRangeEnabled);
  measurementRangeInput.disabled = autoRangeEnabled;
}

function populateRangeOptions(measurement) {
  const existing = measurementRangeInput.value;
  const options = measurement?.range_options || [];
  measurementRangeInput.replaceChildren(
    emptyOption("Select range"),
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

function emptyOption(text) {
  return optionElement("", text);
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
  return true;
}

function updateTriggerModeUi() {
  const mode = triggerModeSelect.value || "software";
  for (const element of modeScopedControls) {
    const visible = modeScopeVisible(element.dataset.modeScope, mode);
    element.classList.toggle("is-hidden", !visible);
    for (const control of element.querySelectorAll("input, select, textarea")) {
      control.disabled = !visible;
    }
  }
  const visibleTriggerControls = triggerOptionsPanel.querySelectorAll(
    "[data-mode-scope]:not(.is-hidden)"
  );
  triggerOptionsPanel.classList.toggle("is-hidden", visibleTriggerControls.length === 0);
  updateTriggerButtonUi();
}

function updateTriggerButtonUi() {
  const mode = triggerModeSelect.value || "software";
  const timerActive = String(timerIntervalInput.value || "").trim() !== "";
  const visible =
    mode === "software-custom" || (mode === "software" && !timerActive);
  triggerRunButton.classList.toggle("is-hidden", !visible);
  triggerRunButton.disabled = !visible;
}

function renderStatus(status) {
  statusState.textContent = status.state || "idle";
  statusCaptured.textContent = String(status.captured ?? 0);
  statusErrors.textContent = String(status.errors ?? 0);
  statusCsv.textContent = status.csv_path || "auto";
  latestStatus.textContent = status.latest_status || "idle";
  fatalError.textContent = status.fatal_error || "";
  cleanupStatus.textContent = status.cleanup_status || "";
  rawStatus.textContent = JSON.stringify(status, null, 2);
}

async function loadCapabilities() {
  const capabilities = await api("/api/capabilities");
  measurementsByName = new Map(
    capabilities.measurements.map((item) => [item.name, item])
  );
  measurementSelect.replaceChildren(
    ...capabilities.measurements.map((item) => {
      const option = document.createElement("option");
      option.value = item.name;
      option.textContent = `${item.name} (${item.unit})`;
      return option;
    })
  );
  updateMeasurementUi();
  triggerModeSelect.replaceChildren(
    ...capabilities.trigger_modes.map((mode) => {
      const option = document.createElement("option");
      option.value = mode;
      option.textContent = mode;
      return option;
    })
  );
  updateTriggerModeUi();
}

async function refreshResources() {
  latestStatus.textContent = "scanning live resources...";
  const result = await api("/api/resources?verify=true&live_only=true");
  resourceSelect.replaceChildren(
    ...[
      (() => {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = result.resources.length
          ? "Select live resource"
          : "No live resources found";
        return option;
      })(),
    ],
    ...result.resources.map((item) => {
      const option = document.createElement("option");
      option.value = item.resource;
      option.textContent = item.detail
        ? `${item.resource} (${item.status}: ${item.detail})`
        : item.resource;
      return option;
    })
  );
  if (!resourceInput.value && result.resources.length > 0) {
    resourceInput.value = result.resources[0].resource;
    resourceSelect.value = result.resources[0].resource;
  }
  latestStatus.textContent = `live resources found: ${result.resources.length}`;
}

async function pollStatus() {
  try {
    renderStatus(await api("/api/runs/current"));
  } catch (error) {
    latestStatus.textContent = error.message;
  }
}

document.querySelector("#refresh-resources").addEventListener("click", async () => {
  try {
    await refreshResources();
  } catch (error) {
    latestStatus.textContent = error.message;
  }
});

resourceSelect.addEventListener("change", () => {
  if (resourceSelect.value) {
    resourceInput.value = resourceSelect.value;
  }
});

measurementSelect.addEventListener("change", updateMeasurementUi);
triggerModeSelect.addEventListener("change", updateTriggerModeUi);
timerIntervalInput.addEventListener("input", updateTriggerButtonUi);
autoRangeCheckbox.addEventListener("change", updateRangeVisibility);

document.querySelector("#start-run").addEventListener("click", async () => {
  try {
    const payload = formPayload();
    if (!payload.resource) {
      latestStatus.textContent = "select or enter a VISA resource before Start";
      resourceInput.focus();
      return;
    }
    renderStatus(await api("/api/runs", {
      method: "POST",
      body: JSON.stringify(payload),
    }));
  } catch (error) {
    latestStatus.textContent = error.message;
  }
});

document.querySelector("#trigger-run").addEventListener("click", async () => {
  try {
    renderStatus(await api("/api/runs/current/trigger", {
      method: "POST",
      body: JSON.stringify({ source: "web-ui" }),
    }));
  } catch (error) {
    latestStatus.textContent = error.message;
  }
});

document.querySelector("#stop-run").addEventListener("click", async () => {
  try {
    renderStatus(await api("/api/runs/current/stop", { method: "POST" }));
  } catch (error) {
    latestStatus.textContent = error.message;
  }
});

loadCapabilities()
  .then(() => {
    updateRangeVisibility();
    return pollStatus();
  })
  .catch((error) => {
    latestStatus.textContent = error.message;
  });

window.setInterval(pollStatus, 1000);
