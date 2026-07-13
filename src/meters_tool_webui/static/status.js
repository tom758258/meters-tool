import { api } from "./api.js";
import {
  cleanupStatus,
  fatalError,
  latestStatus,
  openCsvButton,
  rawStatus,
  refreshResourcesButton,
  startRunButton,
  statusCaptured,
  statusCsv,
  statusDetails,
  statusErrors,
  statusState,
  stopRunButton,
  toggleStatusDetailsButton,
  triggerModeSelect,
} from "./dom.js";
import { refreshLiveDataPresentation, renderLiveData } from "./live_data.js";
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

function clearTranslationBinding(element, binding = "data-i18n") {
  element.removeAttribute(binding);
  element.removeAttribute("data-i18n-params");
}

function setTranslatedText(element, key, params = {}) {
  element.setAttribute("data-i18n", key);
  if (Object.keys(params).length > 0) {
    element.setAttribute("data-i18n-params", JSON.stringify(params));
  } else {
    element.removeAttribute("data-i18n-params");
  }
  element.textContent = t(key, params);
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

export function renderStatus(status) {
  latestRenderedStatus = status || null;
  renderPresentation(statusState, runStatePresentation(status.state || "idle"));
  statusCaptured.textContent = String(status.captured ?? 0);
  statusErrors.textContent = String(status.errors ?? 0);
  if (statusCsv) {
    if (status.csv_path) {
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
  renderLiveData(status);
}

export function refreshStatusPresentation() {
  renderStatusLog();
  const detailsVisible = !statusDetails.classList.contains("is-hidden");
  setStatusDetailsVisible(detailsVisible);
  if (latestRenderedStatus) {
    renderPresentation(
      statusState,
      runStatePresentation(latestRenderedStatus.state || "idle")
    );
    if (statusCsv && !latestRenderedStatus.csv_path) {
      setTranslatedText(statusCsv, "common.default");
    }
  }
  refreshLiveDataPresentation();
}

function updateRunControlButtons(status) {
  const active = Boolean(status?.active);
  startRunButton.disabled = active;
  refreshResourcesButton.disabled = active;
  if (active) {
    stopRunButton.disabled = false;
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
