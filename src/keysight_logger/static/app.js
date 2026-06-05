const form = document.querySelector("#run-form");
const statusState = document.querySelector("#status-state");
const statusCaptured = document.querySelector("#status-captured");
const statusErrors = document.querySelector("#status-errors");
const statusCsv = document.querySelector("#status-csv");
const latestStatus = document.querySelector("#latest-status");
const fatalError = document.querySelector("#fatal-error");
const cleanupStatus = document.querySelector("#cleanup-status");
const rawStatus = document.querySelector("#raw-status");
const statusDetails = document.querySelector("#status-details");
const toggleStatusDetailsButton = document.querySelector("#toggle-status-details");
const resourceInput = document.querySelector("#resource");
const resourceSelect = document.querySelector("#resource-select");
const triggerRunButton = document.querySelector("#trigger-run");
const openCsvButton = document.querySelector("#open-csv");
const measurementSelect = document.querySelector("#measurement");
const measurementRangeInput = document.querySelector("#measurement-range");
const autoRangeCheckbox = document.querySelector("[name='auto_range']");
const autoZeroContainer = document.querySelector("#auto-zero-container");
const autoZeroCheckbox = document.querySelector("[name='auto_zero']");
const rangeContainer = document.querySelector("#range-container");
const rangeUnit = document.querySelector("#range-unit");
const rangeSuffix = document.querySelector("#range-suffix");
const nplcField = document.querySelector("#nplc-field");
const nplcSelect = document.querySelector("#nplc");
const triggerModeSelect = document.querySelector("#trigger-mode");
const timerIntervalInput = document.querySelector("[name='timer_interval_s']");
const timerTriggerCheckbox = document.querySelector("#timer-trigger-checkbox");
const timerIntervalContainer = document.querySelector("#timer-interval-container");
const triggerTimeoutInput = document.querySelector("[name='trigger_timeout_ms']");
const swMinIntervalContainer = document.querySelector("#sw-min-interval-container");
const swMinIntervalInput = document.querySelector("[name='sw_min_interval_ms']");
const swQueueMaxContainer = document.querySelector("#sw-queue-max-container");
const swQueueMaxInput = document.querySelector("[name='sw_queue_max']");
const triggerCountInput = document.querySelector("[name='trigger_count']");
const sampleCountInput = document.querySelector("[name='sample_count']");
const triggerMetadataContainer = document.querySelector("#trigger-metadata-container");
const triggerMetadataInput = document.querySelector("#trigger-metadata");
const triggerOptionsPanel = document.querySelector("#trigger-options-panel");
const panelToggles = [...document.querySelectorAll(".panel-toggle")];
const modeScopedControls = [...document.querySelectorAll("[data-mode-scope]")];
const measurementScopedControls = [
  ...document.querySelectorAll("[data-measurement-scope]"),
];
const DEFAULT_TRIGGER_TIMEOUT_MS = 10000;
const STATUS_LOG_LINE_COUNT = 5;
let measurementsByName = new Map();
let inputLimits = {};
let statusLogMessages = [];
let lastApiLatestStatus = "";

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

function capitalizeFirst(value) {
  const text = String(value || "");
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
}

function renderStatusLog() {
  const blankLineCount = Math.max(0, STATUS_LOG_LINE_COUNT - statusLogMessages.length);
  const visibleLines = [
    ...Array.from({ length: blankLineCount }, () => ""),
    ...statusLogMessages,
  ];
  latestStatus.replaceChildren(
    ...visibleLines.map((message) => {
      const line = document.createElement("div");
      line.className = "status-log-line";
      line.textContent = message;
      return line;
    })
  );
}

function formatStatusLogMessage(message) {
  return capitalizeFirst(String(message || "").trim());
}

function appendStatusLog(message) {
  const formatted = formatStatusLogMessage(message);
  if (!formatted) {
    return;
  }
  if (statusLogMessages[statusLogMessages.length - 1] === formatted) {
    return;
  }
  statusLogMessages = [...statusLogMessages, formatted].slice(-STATUS_LOG_LINE_COUNT);
  renderStatusLog();
}

function appendApiStatusLog(message) {
  const formatted = formatStatusLogMessage(message);
  if (!formatted) {
    return;
  }
  if (formatted.toLowerCase() === "idle") {
    lastApiLatestStatus = formatted;
    return;
  }
  if (formatted === lastApiLatestStatus) {
    return;
  }
  lastApiLatestStatus = formatted;
  appendStatusLog(formatted);
}

function setStatusDetailsVisible(visible) {
  statusDetails.classList.toggle("is-hidden", !visible);
  toggleStatusDetailsButton.setAttribute("aria-expanded", String(visible));
  toggleStatusDetailsButton.textContent = visible ? "Hide Details" : "Show Details";
}

function setPanelExpanded(button, expanded) {
  const panel = button.closest(".collapsible-panel");
  if (!panel) {
    return;
  }
  panel.classList.toggle("is-collapsed", !expanded);
  button.setAttribute("aria-expanded", String(expanded));
  button.textContent = expanded ? "Hide" : "Show";
}

function supportsAutoZero(measurementName) {
  return ["current-dc", "voltage-dc", "resistance-2w"].includes(measurementName);
}

function usesTriggerTimeout(mode) {
  return mode === "external" || mode === "external-custom";
}

function triggerTimeoutMs(data, mode) {
  return numberOrNull(
    usesTriggerTimeout(mode) ? data.get("trigger_timeout_ms") : DEFAULT_TRIGGER_TIMEOUT_MS
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
    trigger_timeout_ms: triggerTimeoutMs(data, triggerMode),
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

function validateSwMinInterval() {
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

function triggerMetadataPayload() {
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

function updateMeasurementUi() {
  const selected = measurementSelect.value || "current-dc";
  const autoZeroVisible = supportsAutoZero(selected);
  autoZeroContainer.classList.toggle("is-hidden", !autoZeroVisible);
  autoZeroCheckbox.disabled = !autoZeroVisible;
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
  updatePanelSummaries();
}

function updateRangeVisibility() {
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
  if (scope === "trigger-timeout") {
    return usesTriggerTimeout(mode);
  }
  return true;
}

function updateTriggerModeUi() {
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
    for (const container of [swMinIntervalContainer, swQueueMaxContainer, triggerMetadataContainer]) {
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

function updateTriggerButtonUi() {
  const mode = triggerModeSelect.value || "software";
  const timerActive = mode === "software" && timerTriggerCheckbox.checked;
  const visible =
    mode === "software-custom" || (mode === "software" && !timerActive);
  triggerRunButton.classList.toggle("is-hidden", !visible);
  triggerRunButton.disabled = !visible;
}

function renderStatus(status) {
  statusState.textContent = capitalizeFirst(status.state || "idle");
  statusCaptured.textContent = String(status.captured ?? 0);
  statusErrors.textContent = String(status.errors ?? 0);
  if (statusCsv) {
    statusCsv.textContent = status.csv_path || "Default";
  }
  updateOpenCsvButton(status);
  appendApiStatusLog(status.latest_status || "idle");
  fatalError.textContent = status.fatal_error || "";
  cleanupStatus.textContent = status.cleanup_status || "";
  rawStatus.textContent = JSON.stringify(status, null, 2);
}

function updateOpenCsvButton(status) {
  const ready = !status.active && Boolean(status.csv_path);
  openCsvButton.disabled = !ready;
  openCsvButton.classList.toggle("is-ready", ready);
}

function updatePanelSummaries() {
  const runSummary = document.querySelector("[data-summary-for='run-setup']");
  const measurementSummary = document.querySelector("[data-summary-for='measurement-options']");
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
    measurementSummary.textContent = [
      autoRangeCheckbox.checked ? "Auto range" : "Manual range",
      autoZeroCheckbox.checked ? "Auto zero" : "No auto zero",
      nplcSelect.value ? `NPLC ${nplcSelect.value}` : "",
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

async function loadCapabilities() {
  const capabilities = await api("/api/capabilities");
  applyInputLimits(capabilities.limits);
  measurementsByName = new Map(
    capabilities.measurements.map((item) => [item.name, item])
  );
  measurementSelect.replaceChildren(
    ...capabilities.measurements.map((item) => {
      const option = document.createElement("option");
      option.value = item.name;
      option.textContent = `${capitalizeFirst(item.name)} (${item.unit})`;
      return option;
    })
  );
  updateMeasurementUi();
  triggerModeSelect.replaceChildren(
    ...capabilities.trigger_modes.map((mode) => {
      const option = document.createElement("option");
      option.value = mode;
      option.textContent = capitalizeFirst(mode);
      return option;
    })
  );
  updateTriggerModeUi();
}

async function refreshResources() {
  appendStatusLog("Scanning live resources...");
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
  appendStatusLog(`Live resources found: ${result.resources.length}`);
}

async function pollStatus() {
  try {
    renderStatus(await api("/api/runs/current"));
  } catch (error) {
    appendStatusLog(error.message);
  }
}

document.querySelector("#refresh-resources").addEventListener("click", async () => {
  try {
    await refreshResources();
  } catch (error) {
    appendStatusLog(error.message);
  }
});

resourceSelect.addEventListener("change", () => {
  if (resourceSelect.value) {
    resourceInput.value = resourceSelect.value;
  }
});

measurementSelect.addEventListener("change", updateMeasurementUi);
triggerModeSelect.addEventListener("change", updateTriggerModeUi);
timerIntervalInput.addEventListener("input", () => {
  updateTriggerButtonUi();
  updatePanelSummaries();
});
timerTriggerCheckbox.addEventListener("change", updateTriggerModeUi);
autoRangeCheckbox.addEventListener("change", updateRangeVisibility);
autoZeroCheckbox.addEventListener("change", updatePanelSummaries);
nplcSelect.addEventListener("change", updatePanelSummaries);
document.querySelector("[name='max_samples']").addEventListener("input", updatePanelSummaries);
swMinIntervalInput.addEventListener("input", validateSwMinInterval);
toggleStatusDetailsButton.addEventListener("click", () => {
  setStatusDetailsVisible(statusDetails.classList.contains("is-hidden"));
});
for (const button of panelToggles) {
  button.addEventListener("click", () => {
    setPanelExpanded(button, button.getAttribute("aria-expanded") !== "true");
  });
}

document.querySelector("#start-run").addEventListener("click", async () => {
  try {
    const payload = formPayload();
    if (!payload.resource) {
      appendStatusLog("Select or enter a VISA resource before Start");
      resourceInput.focus();
      return;
    }
    validateSwMinInterval();
    if (!form.checkValidity()) {
      appendStatusLog("Check highlighted run settings before Start");
      form.reportValidity();
      return;
    }
    renderStatus(await api("/api/runs", {
      method: "POST",
      body: JSON.stringify(payload),
    }));
  } catch (error) {
    appendStatusLog(error.message);
  }
});

document.querySelector("#trigger-run").addEventListener("click", async () => {
  try {
    const metadata = triggerMetadataPayload();
    renderStatus(await api("/api/runs/current/trigger", {
      method: "POST",
      body: JSON.stringify(metadata),
    }));
  } catch (error) {
    appendStatusLog(error.message);
  }
});

document.querySelector("#stop-run").addEventListener("click", async () => {
  try {
    renderStatus(await api("/api/runs/current/stop", { method: "POST" }));
  } catch (error) {
    appendStatusLog(error.message);
  }
});

openCsvButton.addEventListener("click", async () => {
  try {
    const result = await api("/api/runs/current/open-csv", { method: "POST" });
    appendStatusLog(`Opened CSV: ${result.csv_path}`);
  } catch (error) {
    appendStatusLog(error.message);
  }
});

renderStatusLog();
setStatusDetailsVisible(false);
for (const button of panelToggles) {
  setPanelExpanded(button, true);
}

loadCapabilities()
  .then(() => {
    updateRangeVisibility();
    return pollStatus();
  })
  .catch((error) => {
    appendStatusLog(error.message);
  });

window.setInterval(pollStatus, 1000);
