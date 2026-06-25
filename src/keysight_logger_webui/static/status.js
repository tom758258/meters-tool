import { api } from "./api.js";
import {
  cleanupStatus,
  fatalError,
  latestStatus,
  openCsvButton,
  rawStatus,
  statusCaptured,
  statusCsv,
  statusDetails,
  statusErrors,
  statusState,
  toggleStatusDetailsButton,
  triggerModeSelect,
} from "./dom.js";
import { renderLiveData } from "./live_data.js";
import { capitalizeFirst } from "./run_form.js";

const STATUS_LOG_LINE_COUNT = 5;
const SOFTWARE_TRIGGER_QUEUED_BURST_COUNT = 5;
const SOFTWARE_TRIGGER_QUEUED_BURST_MS = 2000;
let statusLogMessages = [];
let lastApiLatestStatus = "";
let softwareTriggerQueuedTimes = [];
let showNextSoftwareTriggerQueued = false;
let loggedWaitingTriggerKeys = new Set();
let sseSource = null;
let pollingIntervalId = null;
let loggedSseFallback = false;

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

export function appendStatusLog(message) {
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
    typeof statusOrMessage === "object" && statusOrMessage !== null
      ? statusOrMessage
      : null;
  const message = status ? status.latest_status : statusOrMessage;
  const formatted = formatStatusLogMessage(message);
  if (!formatted || shouldSuppressApiStatusLog(formatted, status)) {
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

function setStatusDetailsVisible(visible) {
  statusDetails.classList.toggle("is-hidden", !visible);
  toggleStatusDetailsButton.setAttribute("aria-expanded", String(visible));
  toggleStatusDetailsButton.textContent = visible ? "Hide Details" : "Show Details";
}

export function renderStatus(status) {
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

function updateOpenCsvButton(status) {
  const ready = !status.active && Boolean(status.csv_path);
  openCsvButton.disabled = !ready;
  openCsvButton.classList.toggle("is-ready", ready);
}

export async function pollStatus() {
  try {
    renderStatus(await api("/api/runs/current"));
  } catch (error) {
    appendStatusLog(error.message);
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
      appendStatusLog("SSE unavailable, falling back to polling");
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
      appendStatusLog("SSE connection lost, falling back to polling");
      loggedSseFallback = true;
    }
    startPolling();
  };
}

export function initializeStatusUi() {
  toggleStatusDetailsButton.addEventListener("click", () => {
    setStatusDetailsVisible(statusDetails.classList.contains("is-hidden"));
  });
  renderStatusLog();
  setStatusDetailsVisible(false);
}

export function startStatusUpdates() {
  startPolling();
  initSSE();
}
