const RUN_STATE_KEYS = Object.freeze({
  idle: "status.idle",
  starting: "status.starting",
  running: "status.running",
  stopping: "status.stopping",
  stopped: "status.stopped",
  error: "status.error",
});

const LATEST_STATUS_KEYS = Object.freeze({
  ready: "status.ready",
  "software trigger queued": "status.software_trigger_queued",
  "stop requested": "status.stop_requested",
  "recording stopped": "status.recording_stopped",
  "waiting trigger": "status.waiting_trigger",
  "waiting software custom trigger": "status.waiting_software_custom_trigger",
});

const RESOURCE_STATUS_KEYS = Object.freeze({
  live: "resource.status.live",
  stale: "resource.status.stale",
});

const ERROR_KEYS = Object.freeze({
  "a run is already active": "error.run_active",
  "resource is required": "error.resource_required",
  "run is still active": "error.csv_run_active",
  "no completed CSV available": "error.csv_unavailable",
  "CSV file not found": "error.csv_not_found",
  "folder selection unavailable": "error.csv_folder_selector_unavailable",
  "folder selection dialog is unavailable": "error.csv_folder_selector_unavailable",
  "no active run": "error.command_no_active_run",
  "run is not ready": "error.command_not_ready",
  "request body must be a JSON object": "error.request_json_object",
  "model_mode/modelMode is not supported; use instrument_model only":
    "error.model_mode_unsupported",
});

function rawPresentation(value) {
  return { kind: "raw", text: String(value ?? "") };
}

function keyedPresentation(key, params = {}) {
  return { kind: "translated", key, params };
}

export function normalizeStatusValue(value) {
  return String(value ?? "").trim().toLowerCase();
}

function mappedPresentation(value, keys) {
  const key = keys[normalizeStatusValue(value)];
  return key ? keyedPresentation(key) : rawPresentation(value);
}

export function runStatePresentation(value) {
  return mappedPresentation(value, RUN_STATE_KEYS);
}

export function latestStatusPresentation(value) {
  return mappedPresentation(value, LATEST_STATUS_KEYS);
}

export function resourceStatusPresentation(value) {
  const key = RESOURCE_STATUS_KEYS[String(value ?? "")];
  return key ? keyedPresentation(key) : rawPresentation(value);
}

export function browserErrorPresentation(value) {
  const text = String(value ?? "");
  const exactKey = ERROR_KEYS[text];
  if (exactKey) {
    return keyedPresentation(exactKey);
  }
  const mismatch = text.match(
    /^Selected model ([A-Za-z0-9-]+) does not match the connected instrument IDN ([A-Za-z0-9-]+)\. Select \2 or rescan the device\.$/
  );
  if (mismatch) {
    return keyedPresentation("error.model_idn_mismatch", {
      selected: mismatch[1],
      connected: mismatch[2],
    });
  }
  return rawPresentation(text);
}
