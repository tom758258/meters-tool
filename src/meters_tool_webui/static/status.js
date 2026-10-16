import { api } from "./api.js";
import {
  cleanupStatus,
  commandStateIndicator,
  dryRunPlan,
  dryRunPlanResult,
  executionModeInputs,
  fatalError,
  latestStatus,
  liveStateIndicator,
  openCsvButton,
  rawStatus,
  refreshResourcesButton,
  visaLibrarySelect,
  startRunButton,
  statusCaptured,
  statusCsv,
  statusDetails,
  statusErrors,
  statusState,
  stopRunButton,
  toggleStatusDetailsButton,
  triggerModeSelect,
  webuiStateIndicator,
} from "./dom.js";
import { refreshLiveDataPresentation, renderLiveData } from "./live_data.js";
import { setTranslatedText } from "./dom_i18n.js";
import { t } from "./i18n.js";
import {
  browserErrorPresentation,
  latestStatusPresentation,
  normalizeStatusValue,
  runStatePresentation,
} from "./presentation_i18n.js";

const STATUS_LOG_LINE_COUNT = 5;
const SOFTWARE_TRIGGER_QUEUED_BURST_COUNT = 5;
const SOFTWARE_TRIGGER_QUEUED_BURST_MS = 2000;
const INDICATOR_STATE_CLASSES = [
  "state-ok",
  "state-warning",
  "state-error",
  "state-idle",
];
let statusLogEntries = [];
let lastApiLatestStatus = "";
let softwareTriggerQueuedTimes = [];
let showNextSoftwareTriggerQueued = false;
let loggedWaitingTriggerKeys = new Set();
let sseSource = null;
let pollingIntervalId = null;
let loggedSseFallback = false;
let latestRenderedStatus = null;
let lastRunControlsActive = false;
let planPreviewActive = false;
let webuiIndicatorRender = {
  cls: "state-warning",
  key: "live_data.indicator_checking",
};
let commandIndicatorRender = { cls: "state-ok", key: "status.ready" };
let liveIndicatorRender = {
  cls: "state-idle",
  key: "live_data.indicator_not_monitoring",
};

const EMPTY_PLAN_LIVE_DATA = Object.freeze({
  run_id: null,
  latest_sample: null,
  recent_samples: [],
  sample_capacity: 5000,
});

function clearTranslationBinding(element, binding = "data-i18n") {
  element.removeAttribute(binding);
  element.removeAttribute("data-i18n-params");
}

function setRawText(element, text) {
  clearTranslationBinding(element);
  element.textContent = String(text ?? "");
}

function renderPresentation(element, presentation) {
  if (presentation.kind === "translated") {
    setTranslatedText(element, presentation.key, presentation.params);
  } else {
    setRawText(element, presentation.text);
  }
}

function renderStatusLog() {
  const blankLineCount = Math.max(0, STATUS_LOG_LINE_COUNT - statusLogEntries.length);
  const visibleLines = [
    ...Array.from({ length: blankLineCount }, () => ({
      kind: "raw",
      text: "",
      identity: "blank",
    })),
    ...statusLogEntries,
  ];
  latestStatus.replaceChildren(
    ...visibleLines.map((entry) => {
      const line = document.createElement("div");
      line.className = "status-log-line";
      renderPresentation(line, entry);
      return line;
    })
  );
}

function appendStatusLogEntry(entry) {
  if (entry.kind === "raw" && !entry.text) {
    return;
  }
  if (statusLogEntries[statusLogEntries.length - 1]?.identity === entry.identity) {
    return;
  }
  statusLogEntries = [...statusLogEntries, entry].slice(-STATUS_LOG_LINE_COUNT);
  renderStatusLog();
}

export function appendRawStatusLog(message) {
  const text = String(message ?? "");
  appendStatusLogEntry({ kind: "raw", text, identity: `raw:${text}` });
}

export function appendTranslatedStatusLog(key, params = {}) {
  appendStatusLogEntry({
    kind: "translated",
    key,
    params,
    identity: `translated:${key}:${JSON.stringify(params)}`,
  });
}

export function appendBrowserError(error) {
  const presentation = browserErrorPresentation(error?.message ?? error);
  if (presentation.kind === "translated") {
    appendTranslatedStatusLog(presentation.key, presentation.params);
  } else {
    appendRawStatusLog(presentation.text);
  }
}

export function appendStatusLog(message) {
  appendRawStatusLog(message);
}

function appendApiStatusLog(statusOrMessage) {
  const status =
    typeof statusOrMessage === "object" && statusOrMessage !== null
      ? statusOrMessage
      : null;
  const message = status ? status.latest_status : statusOrMessage;
  const normalized = normalizeStatusValue(message);
  if (!normalized || shouldSuppressApiStatusLog(normalized, status)) {
    return;
  }
  if (normalized === "idle") {
    lastApiLatestStatus = normalized;
    return;
  }
  if (normalized === lastApiLatestStatus) {
    return;
  }
  lastApiLatestStatus = normalized;
  const presentation = latestStatusPresentation(message);
  appendStatusLogEntry({
    ...presentation,
    identity: `api:${normalized}`,
  });
}

function shouldSuppressApiStatusLog(normalized, status) {
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

export function markSoftwareTriggerQueuedForLog() {
  const now = Date.now();
  softwareTriggerQueuedTimes = [...softwareTriggerQueuedTimes, now].filter(
    (time) => now - time <= SOFTWARE_TRIGGER_QUEUED_BURST_MS
  );
  if (softwareTriggerQueuedTimes.length >= SOFTWARE_TRIGGER_QUEUED_BURST_COUNT) {
    showNextSoftwareTriggerQueued = true;
    softwareTriggerQueuedTimes = [];
  }
}

export function isRunActive() {
  return Boolean(latestRenderedStatus?.active);
}

function warnBeforeUnloadIfActive(event) {
  if (!isRunActive()) {
    return undefined;
  }
  const message = t("status.active_run_unload_warning");
  event.preventDefault();
  event.returnValue = message;
  return message;
}

function setStatusDetailsVisible(visible) {
  statusDetails.classList.toggle("is-hidden", !visible);
  toggleStatusDetailsButton.setAttribute("aria-expanded", String(visible));
  setTranslatedText(
    toggleStatusDetailsButton,
    visible ? "status.hide_details" : "status.show_details"
  );
}

function setStateIndicator(indicator, render) {
  if (!indicator) {
    return;
  }
  for (const candidate of INDICATOR_STATE_CLASSES) {
    indicator.classList.toggle(candidate, candidate === render.cls);
  }
  const text = indicator.querySelector(".state-text");
  if (text) {
    setTranslatedText(text, render.key);
  }
}

function updateCommandStateIndicator(status) {
  if (status.fatal_error) {
    commandIndicatorRender = { cls: "state-error", key: "status.error" };
  } else if (status.active) {
    commandIndicatorRender = {
      cls: "state-warning",
      key: "live_data.indicator_busy",
    };
  } else {
    commandIndicatorRender = { cls: "state-ok", key: "status.ready" };
  }
  setStateIndicator(commandStateIndicator, commandIndicatorRender);
}

function updateLiveStateIndicator(status) {
  const samples = Array.isArray(status.recent_samples)
    ? status.recent_samples
    : [];
  if (status.fatal_error) {
    liveIndicatorRender = { cls: "state-error", key: "status.error" };
  } else if (status.active) {
    if (samples.length > 0 || status.latest_sample) {
      liveIndicatorRender = { cls: "state-ok", key: "live_data.indicator_live" };
    } else {
      liveIndicatorRender = {
        cls: "state-warning",
        key: "live_data.waiting_samples",
      };
    }
  } else {
    liveIndicatorRender = {
      cls: "state-idle",
      key: "live_data.indicator_not_monitoring",
    };
  }
  setStateIndicator(liveStateIndicator, liveIndicatorRender);
}

function markWebUiStateReady() {
  webuiIndicatorRender = { cls: "state-ok", key: "status.ready" };
  setStateIndicator(webuiStateIndicator, webuiIndicatorRender);
}

function markWebUiStateError() {
  webuiIndicatorRender = { cls: "state-error", key: "status.error" };
  setStateIndicator(webuiStateIndicator, webuiIndicatorRender);
}

export function renderStatus(status) {
  latestRenderedStatus = status || null;
  markWebUiStateReady();
  updateCommandStateIndicator(latestRenderedStatus || {});
  updateLiveStateIndicator(latestRenderedStatus || {});
  renderPresentation(statusState, runStatePresentation(status.state || "idle"));
  statusCaptured.textContent = String(status.captured ?? 0);
  statusErrors.textContent = String(status.errors ?? 0);
  if (statusCsv) {
    if (status.csv_enabled === false) {
      setTranslatedText(statusCsv, "common.off");
    } else if (status.csv_path) {
      setRawText(statusCsv, status.csv_path);
    } else {
      setTranslatedText(statusCsv, "common.default");
    }
  }
  updateRunControlButtons(status);
  updateOpenCsvButton(status);
  appendApiStatusLog(status);
  fatalError.textContent = status.fatal_error || "";
  cleanupStatus.textContent = status.cleanup_status || "";
  rawStatus.textContent = JSON.stringify(status, null, 2);
  renderLiveData(planPreviewActive ? EMPTY_PLAN_LIVE_DATA : status);
}

// The Start HTTP response can arrive after a newer SSE status for the same run.
export function renderStartStatus(status) {
  const current = latestRenderedStatus;
  if (
    status?.run_id &&
    current?.run_id === status.run_id &&
    ((current.captured ?? 0) > (status.captured ?? 0) ||
      (current.active === false && status.active === true))
  ) {
    return;
  }
  renderStatus(status);
}

export function beginPlanPreview() {
  planPreviewActive = true;
  dryRunPlanResult.classList.add("is-hidden");
  dryRunPlan.textContent = "";
  renderLiveData(EMPTY_PLAN_LIVE_DATA);
}

export function renderPlanPreview(plan) {
  planPreviewActive = true;
  dryRunPlan.textContent = JSON.stringify(plan, null, 2);
  dryRunPlanResult.classList.remove("is-hidden");
  setStatusDetailsVisible(true);
  renderLiveData(EMPTY_PLAN_LIVE_DATA);
  appendTranslatedStatusLog("execution.plan_completed");
}

export function clearPlanPreview() {
  planPreviewActive = false;
  dryRunPlanResult.classList.add("is-hidden");
  dryRunPlan.textContent = "";
  if (latestRenderedStatus) {
    renderLiveData(latestRenderedStatus);
  }
}

export function refreshStatusPresentation() {
  renderStatusLog();
  const detailsVisible = !statusDetails.classList.contains("is-hidden");
  setStatusDetailsVisible(detailsVisible);
  setStateIndicator(webuiStateIndicator, webuiIndicatorRender);
  setStateIndicator(commandStateIndicator, commandIndicatorRender);
  setStateIndicator(liveStateIndicator, liveIndicatorRender);
  if (latestRenderedStatus) {
    renderPresentation(
      statusState,
      runStatePresentation(latestRenderedStatus.state || "idle")
    );
    if (statusCsv) {
      if (latestRenderedStatus.csv_enabled === false) {
        setTranslatedText(statusCsv, "common.off");
      } else if (!latestRenderedStatus.csv_path) {
        setTranslatedText(statusCsv, "common.default");
      }
    }
  }
  refreshLiveDataPresentation();
}

function updateRunControlButtons(status) {
  const active = Boolean(status?.active);
  const executionPending = startRunButton.dataset.executionPending === "true";
  startRunButton.disabled = active || executionPending;
  if (visaLibrarySelect) visaLibrarySelect.disabled = active || executionPending;
  refreshResourcesButton.disabled =
    active || refreshResourcesButton.dataset.executionDisabled === "true";
  for (const input of executionModeInputs) {
    input.disabled = active || executionPending;
  }
  if (active) {
    stopRunButton.disabled = false;
  } else if (stopRunButton.dataset.executionDisabled === "true") {
    stopRunButton.disabled = true;
  }
  if (active && !lastRunControlsActive) {
    appendTranslatedStatusLog("status.active_run_start_blocked");
    appendTranslatedStatusLog("status.active_run_scan_blocked");
  }
  lastRunControlsActive = active;
}

function updateOpenCsvButton(status) {
  const ready = !status.active && Boolean(status.csv_path);
  openCsvButton.disabled = !ready;
  openCsvButton.classList.toggle("is-ready", ready);
}

export async function pollStatus() {
  try {
    renderStatus(await api("/api/runs/current"));
  } catch (error) {
    appendBrowserError(error);
    markWebUiStateError();
  }
}

function startPolling() {
  if (pollingIntervalId === null) {
    pollingIntervalId = window.setInterval(pollStatus, 1000);
  }
}

function stopPolling() {
  if (pollingIntervalId !== null) {
    window.clearInterval(pollingIntervalId);
    pollingIntervalId = null;
  }
}

function initSSE() {
  if (typeof EventSource === "undefined") {
    if (!loggedSseFallback) {
      appendTranslatedStatusLog("status.sse_unavailable_polling");
      loggedSseFallback = true;
    }
    startPolling();
    return;
  }
  if (sseSource) {
    sseSource.close();
  }
  sseSource = new EventSource("/api/runs/current/events");
  sseSource.addEventListener("run-status", (event) => {
    try {
      renderStatus(JSON.parse(event.data));
    } catch (error) {
      console.error("Failed to parse SSE data:", error);
    }
  });
  sseSource.onopen = () => {
    stopPolling();
    loggedSseFallback = false;
  };
  sseSource.onerror = () => {
    if (!loggedSseFallback) {
      appendTranslatedStatusLog("status.sse_connection_lost_polling");
      loggedSseFallback = true;
    }
    startPolling();
  };
}

export function initializeStatusUi() {
  toggleStatusDetailsButton.addEventListener("click", () => {
    setStatusDetailsVisible(statusDetails.classList.contains("is-hidden"));
  });
  window.addEventListener("beforeunload", warnBeforeUnloadIfActive);
  renderStatusLog();
  setStatusDetailsVisible(false);
}

export function startStatusUpdates() {
  startPolling();
  initSSE();
}
