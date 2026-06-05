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
const liveDataSummary = document.querySelector("#live-data-summary");
const liveLatestValue = document.querySelector("#live-latest-value");
const liveLatestTime = document.querySelector("#live-latest-time");
const liveLatestTrigger = document.querySelector("#live-latest-trigger");
const liveStatMin = document.querySelector("#live-stat-min");
const liveStatAverage = document.querySelector("#live-stat-average");
const liveStatMax = document.querySelector("#live-stat-max");
const liveStatSpan = document.querySelector("#live-stat-span");
const liveStatStdDev = document.querySelector("#live-stat-std-dev");
const liveStatSample = document.querySelector("#live-stat-sample");
const liveStatsGrid = document.querySelector("#live-stats-grid");
const toggleLiveStatsButton = document.querySelector("#toggle-live-stats");
const liveChartShell = document.querySelector("#live-chart-shell");
const toggleLiveChartButton = document.querySelector("#toggle-live-chart");
const liveTrendChart = document.querySelector("#live-trend-chart");
const liveChartEmpty = document.querySelector("#live-chart-empty");
const liveTableWrap = document.querySelector("#live-table-wrap");
const toggleLiveSamplesButton = document.querySelector("#toggle-live-samples");
const liveSamplesBody = document.querySelector("#live-samples-body");
const liveSampleMetadata = document.querySelector("#live-sample-metadata");
const liveSelectedSample = document.querySelector("#live-selected-sample");
const liveSampleDetails = document.querySelector("#live-sample-details");
const closeLiveSampleDetailsButton = document.querySelector("#close-live-sample-details");
const resourceInput = document.querySelector("#resource");
const resourceSelect = document.querySelector("#resource-select");
const csvInput = document.querySelector("[name='csv']");
const selectCsvFolderButton = document.querySelector("#select-csv-folder");
const triggerRunButton = document.querySelector("#trigger-run");
const openCsvButton = document.querySelector("#open-csv");
const measurementSelect = document.querySelector("#measurement");
const measurementRangeInput = document.querySelector("#measurement-range");
const autoRangeCheckbox = document.querySelector("[name='auto_range']");
const autoZeroContainer = document.querySelector("#auto-zero-container");
const autoZeroSelect = document.querySelector("[name='auto_zero']");
const acBandwidthContainer = document.querySelector("#ac-bandwidth-container");
const acBandwidthSelect = document.querySelector("#ac-bandwidth");
const currentTerminalContainer = document.querySelector("#current-terminal-container");
const currentTerminalSelect = document.querySelector("#current-terminal");
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
const SVG_NS = "http://www.w3.org/2000/svg";
const DEFAULT_TRIGGER_TIMEOUT_MS = 10000;
const STATUS_LOG_LINE_COUNT = 5;
const LIVE_CHART_VISIBLE_GRID_LIMIT = 4;
const SOFTWARE_TRIGGER_QUEUED_BURST_COUNT = 5;
const SOFTWARE_TRIGGER_QUEUED_BURST_MS = 2000;
let measurementsByName = new Map();
let inputLimits = {};
let statusLogMessages = [];
let lastApiLatestStatus = "";
let selectedLiveSampleSequence = null;
let liveSampleDetailsVisible = false;
let liveChartBaselineRunId = null;
let liveChartBaselineValue = null;
let softwareTriggerQueuedTimes = [];
let showNextSoftwareTriggerQueued = false;
let loggedWaitingTriggerKeys = new Set();

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

function appendApiStatusLog(statusOrMessage) {
  const status =
    typeof statusOrMessage === "object" && statusOrMessage !== null ? statusOrMessage : null;
  const message = status ? status.latest_status : statusOrMessage;
  const formatted = formatStatusLogMessage(message);
  if (!formatted) {
    return;
  }
  if (shouldSuppressApiStatusLog(formatted, status)) {
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

function shouldSuppressApiStatusLog(formatted, status) {
  const normalized = formatted.toLowerCase();
  const mode = String(status?.trigger_mode || triggerModeSelect.value || "");
  const runId = String(status?.run_id || "no-run");
  if (
    ["software", "software-custom"].includes(mode) &&
    ["waiting trigger", "waiting software custom trigger"].includes(normalized)
  ) {
    const key = `${runId}:${normalized}`;
    if (loggedWaitingTriggerKeys.has(key)) {
      return true;
    }
    loggedWaitingTriggerKeys.add(key);
    return false;
  }
  if (normalized === "software trigger queued") {
    if (!showNextSoftwareTriggerQueued) {
      return true;
    }
    showNextSoftwareTriggerQueued = false;
  }
  return false;
}

function markSoftwareTriggerQueuedForLog() {
  const now = Date.now();
  softwareTriggerQueuedTimes = [...softwareTriggerQueuedTimes, now].filter(
    (time) => now - time <= SOFTWARE_TRIGGER_QUEUED_BURST_MS
  );
  if (softwareTriggerQueuedTimes.length >= SOFTWARE_TRIGGER_QUEUED_BURST_COUNT) {
    showNextSoftwareTriggerQueued = true;
    softwareTriggerQueuedTimes = [];
  }
}

function setStatusDetailsVisible(visible) {
  statusDetails.classList.toggle("is-hidden", !visible);
  toggleStatusDetailsButton.setAttribute("aria-expanded", String(visible));
  toggleStatusDetailsButton.textContent = visible ? "Hide Details" : "Show Details";
}

function setLiveSectionVisible(button, section, visible) {
  section.classList.toggle("is-hidden", !visible);
  button.setAttribute("aria-expanded", String(visible));
  button.textContent = visible ? "-" : "+";
}

function setPanelExpanded(button, expanded) {
  const panel = button.closest(".collapsible-panel");
  if (!panel) {
    return;
  }
  panel.classList.toggle("is-collapsed", !expanded);
  button.setAttribute("aria-expanded", String(expanded));
  button.textContent = expanded ? "-" : "+";
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

function formPayload() {
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

  const acBandwidthVisible = supportsAcBandwidth(measurement);
  if (acBandwidthVisible && data.get("ac_bandwidth_hz")) {
    payload.ac_bandwidth_hz = numberOrNull(data.get("ac_bandwidth_hz"));
  }

  const currentTerminalVisible = supportsCurrentTerminal(measurement);
  if (currentTerminalVisible && data.get("current_terminal")) {
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
    if (["on", "off", "once"].includes(existingAutoZero)) {
      autoZeroSelect.value = existingAutoZero;
    } else {
      autoZeroSelect.value = "on";
    }
  } else {
    autoZeroSelect.value = "on";
  }

  const acBandwidthVisible = supportsAcBandwidth(measurement);
  acBandwidthContainer.classList.toggle("is-hidden", !acBandwidthVisible);
  acBandwidthSelect.disabled = !acBandwidthVisible;

  if (acBandwidthVisible) {
    const existingAcBandwidth = acBandwidthSelect.value;
    const bandwidthOptions = measurement?.ac_bandwidth_hz_options || [];
    acBandwidthSelect.replaceChildren(
      optionElement("", "Auto (Default)"),
      ...bandwidthOptions.map((value) =>
        optionElement(value, `${formatNumberLabel(value)} Hz`)
      )
    );
    if (bandwidthOptions.map(String).includes(String(existingAcBandwidth))) {
      acBandwidthSelect.value = existingAcBandwidth;
    } else {
      acBandwidthSelect.value = "";
    }
  } else {
    acBandwidthSelect.value = "";
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
    if (terminalOptions.map(String).includes(String(existingCurrentTerminal))) {
      currentTerminalSelect.value = existingCurrentTerminal;
    } else {
      currentTerminalSelect.value = "";
    }
  } else {
    currentTerminalSelect.value = "";
  }

  const unit = measurement?.unit || "";
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
  appendApiStatusLog(status);
  fatalError.textContent = status.fatal_error || "";
  cleanupStatus.textContent = status.cleanup_status || "";
  rawStatus.textContent = JSON.stringify(status, null, 2);
  renderLiveData(status);
}

function renderLiveData(status) {
  const samples = Array.isArray(status.recent_samples) ? status.recent_samples : [];
  const latest = status.latest_sample || samples[samples.length - 1] || null;
  const capacity = Number(status.sample_capacity || 100);
  updateLiveChartBaseline(status, samples);

  if (samples.length === 0) {
    selectedLiveSampleSequence = null;
  } else if (
    selectedLiveSampleSequence === null ||
    !samples.some((sample) => sameSequence(sample.sequence, selectedLiveSampleSequence))
  ) {
    selectedLiveSampleSequence = latest.sequence;
  }

  liveDataSummary.textContent = samples.length
    ? `${samples.length}/${capacity} recent samples`
    : "No samples captured";
  liveLatestValue.textContent = latest
    ? formatLiveValueWithUnit(latest.value, latest.unit)
    : "--";
  liveLatestTime.textContent = latest ? formatLiveTime(latest.timestamp_utc_plus_8) : "--";
  liveLatestTrigger.textContent = latest ? formatLiveTrigger(latest) : "--";
  renderLiveStats(samples, latest);

  renderLiveChart(samples);
  renderLiveSamplesTable(samples);
  renderLiveSampleDetails(
    samples.find((sample) => sameSequence(sample.sequence, selectedLiveSampleSequence)) || null
  );
}

function updateLiveChartBaseline(status, samples) {
  const runId = status.run_id || null;
  if (runId !== liveChartBaselineRunId) {
    liveChartBaselineRunId = runId;
    liveChartBaselineValue = null;
  }
  if (runId === null || liveChartBaselineValue !== null) {
    return;
  }
  const firstNumericSample = samples.find((sample) => Number.isFinite(Number(sample.value)));
  if (firstNumericSample) {
    liveChartBaselineValue = Number(firstNumericSample.value);
  }
}

function renderLiveStats(samples, latest) {
  const unit = latest?.unit || samples.find((sample) => sample.unit)?.unit || "";
  const values = samples
    .map((sample) => Number(sample.value))
    .filter((value) => Number.isFinite(value));
  if (values.length === 0) {
    liveStatMin.textContent = "--";
    liveStatAverage.textContent = "--";
    liveStatMax.textContent = "--";
    liveStatSpan.textContent = "--";
    liveStatStdDev.textContent = "--";
    liveStatSample.textContent = latest ? `#${latest.sequence}` : "--";
    return;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const average = values.reduce((total, value) => total + value, 0) / values.length;
  const variance =
    values.reduce((total, value) => total + ((value - average) ** 2), 0) / values.length;

  liveStatMin.textContent = formatLiveValueWithUnit(min, unit);
  liveStatAverage.textContent = formatLiveValueWithUnit(average, unit);
  liveStatMax.textContent = formatLiveValueWithUnit(max, unit);
  liveStatSpan.textContent = formatLiveValueWithUnit(max - min, unit);
  liveStatStdDev.textContent = formatLiveValueWithUnit(Math.sqrt(variance), unit);
  liveStatSample.textContent = latest ? `#${latest.sequence}` : "--";
}

function renderLiveChart(samples) {
  const numericSamples = samples.filter((sample) => Number.isFinite(Number(sample.value)));
  liveTrendChart.replaceChildren();
  const width = 640;
  const height = 180;
  const padding = 18;
  const centerY = height / 2;
  const gridLineCountPerSide = 5;
  const gridStepPx = (centerY - padding) / gridLineCountPerSide;

  for (let offset = -gridLineCountPerSide; offset <= gridLineCountPerSide; offset += 1) {
    const y = centerY + offset * gridStepPx;
    liveTrendChart.appendChild(svgElement("line", {
      x1: 18,
      y1: y,
      x2: 624,
      y2: y,
      class: offset === 0 ? "live-chart-grid live-chart-grid-center" : "live-chart-grid",
    }));
  }

  if (numericSamples.length === 0) {
    liveChartEmpty.textContent = "Waiting for samples";
    liveChartEmpty.classList.remove("is-hidden");
    return;
  }

  const values = numericSamples.map((sample) => Number(sample.value));
  const baseline = Number.isFinite(liveChartBaselineValue)
    ? liveChartBaselineValue
    : values[0];
  const deviations = values.map((value) => value - baseline);
  const absDeviations = deviations.map((value) => Math.abs(value));
  const maxAbsDeviation = Math.max(...absDeviations);
  const baselineMagnitude = Math.max(Math.abs(baseline), 1);
  const minimumGridValue = baselineMagnitude * 1e-9;
  const gridStepValue = Math.max(
    maxAbsDeviation / LIVE_CHART_VISIBLE_GRID_LIMIT,
    minimumGridValue
  );
  const plotWidth = width - padding * 2;
  const points = numericSamples.map((sample, index) => {
    const x = numericSamples.length === 1
      ? width / 2
      : padding + (index * plotWidth) / (numericSamples.length - 1);
    const deviation = Number(sample.value) - baseline;
    const y = centerY - (deviation / gridStepValue) * gridStepPx;
    return { x, y };
  });

  if (points.length > 1) {
    liveTrendChart.appendChild(svgElement("polyline", {
      points: points.map((point) => `${point.x},${point.y}`).join(" "),
      class: "live-chart-line",
    }));
  }

  const lastPoint = points[points.length - 1];
  liveTrendChart.appendChild(svgElement("circle", {
    cx: lastPoint.x,
    cy: lastPoint.y,
    r: 2.75,
    class: "live-chart-point",
  }));
  liveChartEmpty.classList.add("is-hidden");
}

function renderLiveSamplesTable(samples) {
  if (samples.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 7;
    cell.textContent = "No samples captured";
    row.appendChild(cell);
    liveSamplesBody.replaceChildren(row);
    return;
  }

  liveSamplesBody.replaceChildren(
    ...[...samples].reverse().map((sample) => {
      const row = document.createElement("tr");
      row.dataset.sequence = String(sample.sequence);
      row.classList.toggle(
        "is-selected",
        sameSequence(sample.sequence, selectedLiveSampleSequence)
      );
      row.appendChild(tableCell(sample.sequence));
      row.appendChild(tableCell(formatLiveTime(sample.timestamp_utc_plus_8)));
      row.appendChild(tableCell(formatLiveValue(sample.value)));
      row.appendChild(tableCell(sample.unit || "--"));
      row.appendChild(tableCell(formatLiveTrigger(sample)));
      row.appendChild(tableCell(sample.status || "--"));

      const detailsCell = document.createElement("td");
      const detailsButton = document.createElement("button");
      detailsButton.type = "button";
      detailsButton.className = "live-detail-button";
      detailsButton.textContent = "Details";
      detailsButton.setAttribute("aria-expanded", String(
        liveSampleDetailsVisible && sameSequence(sample.sequence, selectedLiveSampleSequence)
      ));
      detailsButton.setAttribute("aria-label", `Toggle details for sample ${sample.sequence}`);
      detailsButton.addEventListener("click", () => {
        const closing =
          liveSampleDetailsVisible && sameSequence(sample.sequence, selectedLiveSampleSequence);
        liveSampleDetailsVisible = !closing;
        selectedLiveSampleSequence = closing ? null : sample.sequence;
        renderLiveSampleDetails(sample);
        updateLiveSelectedRows();
      });
      detailsCell.appendChild(detailsButton);
      row.appendChild(detailsCell);
      return row;
    })
  );
}

function renderLiveSampleDetails(sample) {
  liveSampleMetadata.classList.toggle("is-hidden", !liveSampleDetailsVisible || !sample);
  if (!liveSampleDetailsVisible || !sample) {
    liveSelectedSample.textContent = "No sample selected";
    liveSampleDetails.textContent = "";
    return;
  }
  liveSelectedSample.textContent = `Sample #${sample.sequence}`;
  liveSampleDetails.textContent = JSON.stringify(
    {
      sequence: sample.sequence,
      trigger_metadata: sample.trigger_metadata || {},
      measurement_metadata: sample.measurement_metadata || {},
    },
    null,
    2
  );
}

function updateLiveSelectedRows() {
  for (const row of liveSamplesBody.querySelectorAll("tr[data-sequence]")) {
    row.classList.toggle(
      "is-selected",
      liveSampleDetailsVisible && sameSequence(row.dataset.sequence, selectedLiveSampleSequence)
    );
    const detailsButton = row.querySelector(".live-detail-button");
    detailsButton?.setAttribute(
      "aria-expanded",
      String(liveSampleDetailsVisible && sameSequence(row.dataset.sequence, selectedLiveSampleSequence))
    );
  }
}

function sameSequence(left, right) {
  return String(left) === String(right);
}

function tableCell(value) {
  const cell = document.createElement("td");
  cell.textContent = value === null || value === undefined || value === "" ? "--" : String(value);
  return cell;
}

function formatLiveValueWithUnit(value, unit) {
  const scaled = scaleLiveValue(value, unit);
  return [formatLiveValue(scaled.value), scaled.unit || ""].filter(Boolean).join(" ");
}

function scaleLiveValue(value, unit) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return { value, unit };
  }

  const absValue = Math.abs(numeric);
  if (unit === "A") {
    if (absValue > 0 && absValue < 1e-3) {
      return { value: numeric * 1000000, unit: "uA" };
    }
    if (absValue > 0 && absValue < 1) {
      return { value: numeric * 1000, unit: "mA" };
    }
  }
  if (unit === "V") {
    if (absValue > 0 && absValue < 1e-3) {
      return { value: numeric * 1000000, unit: "uV" };
    }
    if (absValue > 0 && absValue < 1) {
      return { value: numeric * 1000, unit: "mV" };
    }
  }
  if (unit === "Ohm") {
    if (absValue >= 1000000) {
      return { value: numeric / 1000000, unit: "MOhm" };
    }
    if (absValue >= 1000) {
      return { value: numeric / 1000, unit: "kOhm" };
    }
  }
  return { value: numeric, unit };
}

function formatLiveValue(value) {
  const numeric = Number(value);
  if (Number.isFinite(numeric)) {
    return numeric.toLocaleString("en-US", { maximumSignificantDigits: 6 });
  }
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  return String(value);
}

function formatLiveTime(value) {
  const text = String(value || "");
  const [datePart, timePart] = text.split("T");
  if (datePart && timePart) {
    return `${datePart} ${timePart.slice(0, 8)}`;
  }
  return text || "--";
}

function formatLiveTrigger(sample) {
  return sample.trigger_source || "--";
}

function svgElement(tagName, attributes) {
  const element = document.createElementNS(SVG_NS, tagName);
  for (const [name, value] of Object.entries(attributes)) {
    element.setAttribute(name, String(value));
  }
  return element;
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
    const selectedMeasurement = measurementSelect.value || "current-dc";
    const measurement = measurementsByName.get(selectedMeasurement);
    const autoZeroVisible = supportsAutoZero(selectedMeasurement);
    const acBandwidthVisible = supportsAcBandwidth(measurement);
    const currentTerminalVisible = supportsCurrentTerminal(measurement);

    const autoZeroText = autoZeroVisible && autoZeroSelect.value
      ? `Auto zero ${autoZeroSelect.value}`
      : "";

    measurementSummary.textContent = [
      autoRangeCheckbox.checked ? "Auto range" : "Manual range",
      autoZeroText,
      (!nplcSelect.disabled && nplcSelect.value) ? `NPLC ${nplcSelect.value}` : "",
      (acBandwidthVisible && acBandwidthSelect.value)
        ? `AC Band ${acBandwidthSelect.value} Hz`
        : "",
      (currentTerminalVisible && currentTerminalSelect.value)
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

selectCsvFolderButton.addEventListener("click", async () => {
  try {
    appendStatusLog("Opening CSV folder selector...");
    const result = await api("/api/csv/select-folder", { method: "POST" });
    if (result.selected && result.csv_path) {
      csvInput.value = result.csv_path;
      appendStatusLog(`CSV path selected: ${result.csv_path}`);
    } else {
      appendStatusLog("CSV folder selection cancelled");
    }
  } catch (error) {
    appendStatusLog(error.message);
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
autoZeroSelect.addEventListener("change", updatePanelSummaries);
acBandwidthSelect.addEventListener("change", updatePanelSummaries);
currentTerminalSelect.addEventListener("change", updatePanelSummaries);
nplcSelect.addEventListener("change", updatePanelSummaries);
document.querySelector("[name='max_samples']").addEventListener("input", updatePanelSummaries);
swMinIntervalInput.addEventListener("input", validateSwMinInterval);
toggleStatusDetailsButton.addEventListener("click", () => {
  setStatusDetailsVisible(statusDetails.classList.contains("is-hidden"));
});
closeLiveSampleDetailsButton.addEventListener("click", () => {
  liveSampleDetailsVisible = false;
  selectedLiveSampleSequence = null;
  renderLiveSampleDetails(null);
  updateLiveSelectedRows();
});
toggleLiveStatsButton.addEventListener("click", () => {
  setLiveSectionVisible(
    toggleLiveStatsButton,
    liveStatsGrid,
    toggleLiveStatsButton.getAttribute("aria-expanded") !== "true"
  );
});
toggleLiveChartButton.addEventListener("click", () => {
  setLiveSectionVisible(
    toggleLiveChartButton,
    liveChartShell,
    toggleLiveChartButton.getAttribute("aria-expanded") !== "true"
  );
});
toggleLiveSamplesButton.addEventListener("click", () => {
  setLiveSectionVisible(
    toggleLiveSamplesButton,
    liveTableWrap,
    toggleLiveSamplesButton.getAttribute("aria-expanded") !== "true"
  );
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
    const status = await api("/api/runs/current/trigger", {
      method: "POST",
      body: JSON.stringify(metadata),
    });
    if (status.latest_status === "software trigger queued") {
      markSoftwareTriggerQueuedForLog();
    }
    renderStatus(status);
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
setLiveSectionVisible(toggleLiveChartButton, liveChartShell, true);
setLiveSectionVisible(toggleLiveStatsButton, liveStatsGrid, true);
setLiveSectionVisible(toggleLiveSamplesButton, liveTableWrap, true);
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
