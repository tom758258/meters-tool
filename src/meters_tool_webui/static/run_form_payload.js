import {
  isCustomMode,
  isHardwareMode,
  isSoftwareTriggeredMode,
  supportsAcBandwidth,
  supportsAutoZero,
  supportsCurrentTerminal,
  supportsDcvInputZ,
  supportsFreqPeriodTimeout,
  supportsGateTime,
  usesTriggerTimeout,
} from "./run_form_support.js";

const DEFAULT_TRIGGER_TIMEOUT_MS = 10000;

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

export function compactPayload(payload) {
  return Object.fromEntries(
    Object.entries(payload).filter(([_key, value]) => value !== null)
  );
}

export function buildRunPayload(values, context) {
  const csvEnabled =
    values.csv_enabled === undefined
      ? true
      : values.csv_enabled === "on" || values.csv_enabled === true;
  const triggerMode = textOrNull(values.trigger_mode) || "software";
  const customMode = isCustomMode(triggerMode);
  const hardwareMode = isHardwareMode(triggerMode);
  const softwareTriggeredMode = isSoftwareTriggeredMode(triggerMode);
  const selectedMeasurement = String(values.measurement || "current-dc");
  const measurement = context?.measurement;
  const autoZeroVisible = supportsAutoZero(measurement);
  const dcvInputZVisible = supportsDcvInputZ(measurement);
  const triggerTimeoutValue = usesTriggerTimeout(
    triggerMode,
    context?.triggerModeMetadata
  )
    ? values.trigger_timeout_ms
    : DEFAULT_TRIGGER_TIMEOUT_MS;

  const payload = {
    resource: String(values.resource || "").trim(),
    instrument_model: textOrNull(values.instrument_model),
    visa_library: textOrNull(values.visa_library),
    csv_enabled: csvEnabled,
    csv: csvEnabled ? textOrNull(values.csv) : null,
    timeout_ms: numberOrNull(values.timeout_ms),
    trigger_timeout_ms: numberOrNull(triggerTimeoutValue),
    trigger_mode: triggerMode,
    measurement: selectedMeasurement,
    nplc: numberOrNull(values.nplc),
    auto_zero: autoZeroVisible ? (values.auto_zero || "on") : "on",
    auto_range: values.auto_range === "on",
    measurement_range: numberOrNull(values.measurement_range),
    dcv_input_impedance: dcvInputZVisible
      ? String(values.dcv_input_impedance || "default")
      : null,
    vm_comp_slope: textOrNull(values.vm_comp_slope),
  };

  if (supportsAcBandwidth(measurement) && values.ac_bandwidth_hz) {
    payload.ac_bandwidth_hz = numberOrNull(values.ac_bandwidth_hz);
  }
  if (supportsGateTime(measurement) && values.gate_time_s) {
    payload.gate_time_s = numberOrNull(values.gate_time_s);
  }
  if (supportsFreqPeriodTimeout(measurement) && values.freq_period_timeout) {
    payload.freq_period_timeout = String(values.freq_period_timeout);
  }
  if (supportsCurrentTerminal(measurement) && values.current_terminal) {
    payload.current_terminal = numberOrNull(values.current_terminal);
  }
  if (!customMode) {
    payload.max_samples = numberOrNull(values.max_samples);
  }
  if (triggerMode === "software") {
    payload.timer_interval_s = numberOrNull(values.timer_interval_s);
  }
  if (customMode) {
    payload.trigger_count = numberOrNull(values.trigger_count);
    payload.sample_count = numberOrNull(values.sample_count);
    payload.buffer_drain_size = numberOrNull(values.buffer_drain_size);
    payload.allow_buffer_overflow_risk =
      values.allow_buffer_overflow_risk === "on";
  }
  if (hardwareMode) {
    payload.hw_trigger_slope = String(values.hw_trigger_slope || "neg");
    payload.hw_trigger_delay_s = numberOrNull(values.hw_trigger_delay_s);
  }
  if (softwareTriggeredMode) {
    payload.sw_min_interval_ms = numberOrNull(values.sw_min_interval_ms);
    payload.sw_queue_max = numberOrNull(values.sw_queue_max);
  }
  return compactPayload(payload);
}

export function buildExecutionRequest(payload, executionMode) {
  const mode = String(executionMode || "real");
  if (mode === "real") {
    return { path: "/api/runs", payload: { ...payload } };
  }
  if (!["simulate", "dry-run"].includes(mode)) {
    throw new Error(`Unsupported execution mode: ${mode}`);
  }
  const model = textOrNull(payload.instrument_model);
  if (!model) {
    throw new Error("model is required for no-hardware execution");
  }
  // SIM::<model> is also the deterministic no-hardware placeholder for planning;
  // dry-run remains dry_run=true and simulate=false in the backend.
  const noHardwarePayload = {
    ...payload,
    resource: `SIM::${model}`,
  };
  if (mode === "simulate") {
    noHardwarePayload.simulate = true;
  } else {
    delete noHardwarePayload.simulate;
  }
  return {
    path: mode === "dry-run" ? "/api/plan" : "/api/runs",
    payload: noHardwarePayload,
  };
}
