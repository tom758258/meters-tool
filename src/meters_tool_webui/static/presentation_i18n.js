const RUN_STATE_KEYS = Object.freeze({
  idle: "status.idle",
  starting: "status.starting",
  running: "status.running",
  stopping: "status.stopping",
  stopped: "status.stopped",
  error: "status.error",
});

const LATEST_STATUS_KEYS = Object.freeze({
  idle: "status.idle",
  starting: "status.starting",
  ready: "status.ready",
  "recording started": "status.recording_started",
  "software trigger queued": "status.software_trigger_queued",
  "stop requested": "status.stop_requested",
  "recording stopped": "status.recording_stopped",
  "waiting trigger": "status.waiting_trigger",
  "waiting software custom trigger": "status.waiting_software_custom_trigger",
  "hardware trigger wait timed out; re-armed and waiting for next edge":
    "status.hardware_trigger_rearmed",
  "software trigger ignored while hardware trigger is enabled":
    "status.software_trigger_ignored_hardware",
  "software trigger ignored while immediate mode is enabled":
    "status.software_trigger_ignored_immediate",
  "software trigger ignored while external custom is enabled":
    "status.software_trigger_ignored_external_custom",
  "software trigger ignored while software timer is enabled":
    "status.software_trigger_ignored_timer",
  "overflow monitoring active": "status.overflow_monitoring_active",
  "overflow detected: questionable status bit 0x4000": "status.overflow_status_bit",
  "immediate custom capture started": "status.immediate_custom_started",
  "software custom capture armed": "status.software_custom_armed",
  "external custom capture armed": "status.external_custom_armed",
  "final drain budget exhausted": "status.final_drain_budget_exhausted",
  "stop request received": "status.stop_request_received",
  "measurement worker exited before stop was requested": "status.worker_exited",
  "main cleanup starting": "status.main_cleanup_starting",
  "final cleanup starting": "status.final_cleanup_starting",
  "waiting for measurement worker to stop": "status.waiting_worker_stop",
  "waiting worker to fully stop...": "status.waiting_worker_fully_stop",
  "stopping software trigger server": "status.trigger_server_stopping",
  "software trigger server stopped": "status.trigger_server_stopped",
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
  const fixed = mappedPresentation(value, LATEST_STATUS_KEYS);
  if (fixed.kind === "translated") {
    return fixed;
  }
  const text = String(value ?? "");
  const timer = text.match(
    /^software timer enabled interval_s=(?<interval_s>\d+(?:\.\d+)?(?:e[+-]?\d+)?)$/
  );
  if (timer) {
    return keyedPresentation("status.software_timer_enabled", timer.groups);
  }
  const maxSamples = text.match(/^max samples reached: (?<count>\d+)$/);
  if (maxSamples) {
    return keyedPresentation("status.max_samples_reached", maxSamples.groups);
  }
  const hardware = text.match(
    /^hardware trigger configured slope=(?<slope>POS|NEG) delay_s=(?<delay_s>\d+(?:\.\d+)?(?:e[+-]?\d+)?)$/
  );
  if (hardware) {
    return keyedPresentation("status.hardware_trigger_configured", hardware.groups);
  }
  const immediateCustom = text.match(
    /^immediate custom capture configured trigger_count=(?<trigger_count>\d+|infinity) sample_count=(?<sample_count>\d+) expected_readings=(?<expected_readings>\d+|unbounded)$/
  );
  if (immediateCustom) {
    return keyedPresentation("status.immediate_custom_configured", immediateCustom.groups);
  }
  const softwareCustom = text.match(
    /^software custom capture configured trigger_count=(?<trigger_count>\d+|infinity) sample_count=(?<sample_count>\d+) expected_readings=(?<expected_readings>\d+|unbounded)$/
  );
  if (softwareCustom) {
    return keyedPresentation("status.software_custom_configured", softwareCustom.groups);
  }
  const externalCustom = text.match(
    /^external custom capture configured trigger_count=(?<trigger_count>\d+|infinity) sample_count=(?<sample_count>\d+) expected_readings=(?<expected_readings>\d+|unbounded) slope=(?<slope>POS|NEG) delay_s=(?<delay_s>\d+(?:\.\d+)?(?:e[+-]?\d+)?)$/
  );
  if (externalCustom) {
    return keyedPresentation("status.external_custom_configured", externalCustom.groups);
  }
  const softwareTrigger = text.match(
    /^software custom trigger sent=(?<sent>\d+)\/(?<trigger_count>\d+|infinity)$/
  );
  if (softwareTrigger) {
    return keyedPresentation("status.software_custom_trigger_sent", softwareTrigger.groups);
  }
  const expectedReadings = text.match(/^expected readings reached: (?<count>\d+)$/);
  if (expectedReadings) {
    return keyedPresentation("status.expected_readings_reached", expectedReadings.groups);
  }
  const csvPath = text.match(/^csv output path: (?<path>.+)$/);
  if (csvPath) {
    return keyedPresentation("status.csv_output_path", csvPath.groups);
  }
  return rawPresentation(value);
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
