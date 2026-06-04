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
const resourceList = document.querySelector("#resource-list");
const measurementSelect = document.querySelector("#measurement");
const triggerModeSelect = document.querySelector("#trigger-mode");

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

function formPayload() {
  const data = new FormData(form);
  return compactPayload({
    resource: String(data.get("resource") || "").trim(),
    csv: textOrNull(data.get("csv")),
    timeout_ms: numberOrNull(data.get("timeout_ms")),
    trigger_timeout_ms: numberOrNull(data.get("trigger_timeout_ms")),
    sw_min_interval_ms: numberOrNull(data.get("sw_min_interval_ms")),
    sw_queue_max: 0,
    trigger_mode: textOrNull(data.get("trigger_mode")),
    max_samples: numberOrNull(data.get("max_samples")),
    trigger_count: numberOrNull(data.get("trigger_count")),
    sample_count: numberOrNull(data.get("sample_count")),
    timer_interval_s: numberOrNull(data.get("timer_interval_s")),
    buffer_drain_size: numberOrNull(data.get("buffer_drain_size")),
    allow_buffer_overflow_risk: data.get("allow_buffer_overflow_risk") === "on",
    enable_hw_trigger: data.get("enable_hw_trigger") === "on",
    hw_trigger_slope: String(data.get("hw_trigger_slope") || "neg"),
    hw_trigger_delay_s: numberOrNull(data.get("hw_trigger_delay_s")),
    measurement: String(data.get("measurement") || "current-dc"),
    nplc: numberOrNull(data.get("nplc")),
    auto_zero: data.get("auto_zero") === "on",
    auto_range: data.get("auto_range") === "on",
    measurement_range: numberOrNull(data.get("measurement_range")),
    current_range: numberOrNull(data.get("current_range")),
    dcv_input_impedance: String(data.get("dcv_input_impedance") || "default"),
    vm_comp_slope: textOrNull(data.get("vm_comp_slope")),
  });
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
    throw new Error(payload.detail || response.statusText);
  }
  return payload;
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
  measurementSelect.replaceChildren(
    ...capabilities.measurements.map((item) => {
      const option = document.createElement("option");
      option.value = item.name;
      option.textContent = `${item.name} (${item.unit})`;
      return option;
    })
  );
  triggerModeSelect.replaceChildren(
    ...capabilities.trigger_modes.map((mode) => {
      const option = document.createElement("option");
      option.value = mode;
      option.textContent = mode;
      return option;
    })
  );
}

async function refreshResources() {
  latestStatus.textContent = "scanning resources...";
  const result = await api("/api/resources?verify=true&live_only=false");
  resourceList.replaceChildren(
    ...result.resources.map((item) => {
      const option = document.createElement("option");
      option.value = item.resource;
      option.label = item.detail ? `${item.status}: ${item.detail}` : item.resource;
      return option;
    })
  );
  if (!resourceInput.value && result.resources.length > 0) {
    resourceInput.value = result.resources[0].resource;
  }
  latestStatus.textContent = `resources found: ${result.resources.length}`;
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

document.querySelector("#start-run").addEventListener("click", async () => {
  try {
    renderStatus(await api("/api/runs", {
      method: "POST",
      body: JSON.stringify(formPayload()),
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
  .then(pollStatus)
  .catch((error) => {
    latestStatus.textContent = error.message;
  });

window.setInterval(pollStatus, 1000);
