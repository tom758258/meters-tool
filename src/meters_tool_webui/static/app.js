import { api } from "./api.js";
import {
  acBandwidthSelect,
  autoRangeCheckbox,
  autoZeroSelect,
  csvInput,
  currentTerminalSelect,
  deviceResourceBody,
  deviceResourceSummary,
  deviceResourceToggleButton,
  deviceOptionsPanel,
  deviceOptionsToggleButton,
  form,
  freqPeriodTimeoutSelect,
  gateTimeSelect,
  instrumentModelSelect,
  measurementRangeInput,
  measurementSelect,
  nplcSelect,
  openCsvButton,
  panelToggles,
  refreshResourcesButton,
  resourceInput,
  resourceSelect,
  selectCsvFolderButton,
  startRunButton,
  stopRunButton,
  swMinIntervalInput,
  timerIntervalInput,
  timerTriggerCheckbox,
  triggerModeSelect,
  triggerRunButton,
} from "./dom.js";
import {
  initializeLiveDataUi,
  refreshLiveChartScaleAvailability,
} from "./live_data.js";
import {
  formPayload,
  loadCapabilities,
  triggerMetadataPayload,
  updateMeasurementUi,
  updatePanelSummaries,
  updateRangeVisibility,
  updateTriggerButtonUi,
  updateTriggerModeUi,
  validateSwMinInterval,
} from "./run_form.js";
import {
  appendStatusLog,
  initializeStatusUi,
  isRunActive,
  markSoftwareTriggerQueuedForLog,
  pollStatus,
  renderStatus,
  startStatusUpdates,
} from "./status.js";

function setPanelExpanded(button, expanded) {
  const panel = button.closest(".collapsible-panel");
  if (!panel) {
    return;
  }
  panel.classList.toggle("is-collapsed", !expanded);
  button.setAttribute("aria-expanded", String(expanded));
  button.textContent = expanded ? "-" : "+";
}

function setDeviceOptionsExpanded(expanded) {
  if (!deviceOptionsPanel || !deviceOptionsToggleButton) {
    return;
  }
  deviceOptionsPanel.classList.toggle("is-hidden", !expanded);
  deviceOptionsToggleButton.setAttribute("aria-expanded", String(expanded));
}

function setDeviceResourceExpanded(expanded) {
  if (!deviceResourceBody || !deviceResourceToggleButton) {
    return;
  }
  deviceResourceBody.classList.toggle("is-hidden", !expanded);
  deviceResourceToggleButton.setAttribute("aria-expanded", String(expanded));
  deviceResourceToggleButton.textContent = expanded ? "-" : "+";
  deviceResourceToggleButton.setAttribute(
    "aria-label",
    expanded ? "Collapse Device / Resource" : "Expand Device / Resource"
  );
}

function updateMeasurementAndLiveChartScale() {
  updateMeasurementUi();
  refreshLiveChartScaleAvailability("");
}

function updateRangeAndLiveChartScale(notice = "") {
  updateRangeVisibility();
  refreshLiveChartScaleAvailability(notice);
}

let scanMetadataByResource = new Map();

function liveResourceSummary() {
  if (!resourceSelect.value) {
    return "not scanned";
  }
  const model = scanMetadataByResource.get(resourceSelect.value)?.instrument_model;
  return model ? `live ${model}` : "live selected";
}

function expectedModelSummary() {
  return instrumentModelSelect.selectedOptions[0]?.textContent || "Auto-detect";
}

function updateDeviceResourceSummary() {
  if (!deviceResourceSummary) {
    return;
  }
  const resource = resourceInput.value.trim() || "No resource";
  deviceResourceSummary.textContent = [
    resource,
    liveResourceSummary(),
    expectedModelSummary(),
  ].join(" / ");
}

async function applyScannedResource(resource) {
  if (!resource) {
    return;
  }
  const metadata = scanMetadataByResource.get(resource);
  const inferredModel = metadata?.instrument_model || null;
  const forcedModel = instrumentModelSelect.value || "";
  resourceInput.value = resource;
  resourceSelect.value = resource;
  updateDeviceResourceSummary();
  if (!inferredModel) {
    appendStatusLog("Live resource model could not be inferred; Start will auto-detect it.");
    return;
  }
  await loadCapabilities(forcedModel || inferredModel);
  instrumentModelSelect.value = forcedModel;
  updateRangeAndLiveChartScale();
  updateTriggerModeUi();
  updatePanelSummaries();
  updateDeviceResourceSummary();
}

async function refreshResources() {
  appendStatusLog("Scanning live resources...");
  const result = await api("/api/resources?verify=true&live_only=true");
  scanMetadataByResource = new Map(
    result.resources.map((item) => [item.resource, item])
  );
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = result.resources.length
    ? "Select live resource"
    : "No live resources found";
  resourceSelect.replaceChildren(
    placeholder,
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
    await applyScannedResource(result.resources[0].resource);
  }
  updateDeviceResourceSummary();
  appendStatusLog(`Live resources found: ${result.resources.length}`);
}

refreshResourcesButton.addEventListener("click", async () => {
  if (isRunActive()) {
    appendStatusLog("Stop the active run before scanning resources.");
    return;
  }
  try {
    await refreshResources();
  } catch (error) {
    appendStatusLog(error.message);
  }
});

resourceSelect.addEventListener("change", async () => {
  if (resourceSelect.value) {
    try {
      await applyScannedResource(resourceSelect.value);
    } catch (error) {
      appendStatusLog(error.message);
    }
  } else {
    updateDeviceResourceSummary();
  }
});

resourceInput.addEventListener("input", updateDeviceResourceSummary);

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

measurementSelect.addEventListener("change", updateMeasurementAndLiveChartScale);
instrumentModelSelect.addEventListener("change", async () => {
  try {
    await loadCapabilities(instrumentModelSelect.value);
    updateRangeAndLiveChartScale();
    updateDeviceResourceSummary();
  } catch (error) {
    appendStatusLog(error.message);
  }
});
triggerModeSelect.addEventListener("change", updateTriggerModeUi);
timerIntervalInput.addEventListener("input", () => {
  updateTriggerButtonUi();
  updatePanelSummaries();
});
timerTriggerCheckbox.addEventListener("change", updateTriggerModeUi);
autoRangeCheckbox.addEventListener("change", () => {
  updateRangeAndLiveChartScale(
    autoRangeCheckbox.checked
      ? "Range step disabled because Auto range is on."
      : ""
  );
});
measurementRangeInput.addEventListener("change", () => {
  refreshLiveChartScaleAvailability("");
});
autoZeroSelect.addEventListener("change", updatePanelSummaries);
acBandwidthSelect.addEventListener("change", updatePanelSummaries);
gateTimeSelect.addEventListener("change", updatePanelSummaries);
freqPeriodTimeoutSelect.addEventListener("change", updatePanelSummaries);
currentTerminalSelect.addEventListener("change", updatePanelSummaries);
nplcSelect.addEventListener("change", updatePanelSummaries);
document.querySelector("[name='max_samples']").addEventListener(
  "input",
  updatePanelSummaries
);
swMinIntervalInput.addEventListener("input", validateSwMinInterval);
for (const button of panelToggles) {
  button.addEventListener("click", () => {
    setPanelExpanded(button, button.getAttribute("aria-expanded") !== "true");
  });
}
if (deviceResourceToggleButton && deviceResourceBody) {
  deviceResourceToggleButton.addEventListener("click", () => {
    setDeviceResourceExpanded(
      deviceResourceToggleButton.getAttribute("aria-expanded") !== "true"
    );
  });
}
if (deviceOptionsToggleButton && deviceOptionsPanel) {
  deviceOptionsToggleButton.addEventListener("click", (event) => {
    event.stopPropagation();
    setDeviceOptionsExpanded(
      deviceOptionsToggleButton.getAttribute("aria-expanded") !== "true"
    );
  });
  deviceOptionsPanel.addEventListener("click", (event) => {
    event.stopPropagation();
  });
  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Node)) {
      return;
    }
    if (
      deviceOptionsToggleButton.contains(target) ||
      deviceOptionsPanel.contains(target)
    ) {
      return;
    }
    setDeviceOptionsExpanded(false);
  });
  document.addEventListener("keydown", (event) => {
    if (
      event.key === "Escape" &&
      deviceOptionsToggleButton.getAttribute("aria-expanded") === "true"
    ) {
      setDeviceOptionsExpanded(false);
      deviceOptionsToggleButton.focus();
    }
  });
}

startRunButton.addEventListener("click", async () => {
  if (isRunActive()) {
    appendStatusLog("A run is already active. Stop it before starting another run.");
    return;
  }
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

triggerRunButton.addEventListener("click", async () => {
  try {
    const metadata = triggerMetadataPayload();
    await api("/api/runs/current/command", {
      method: "POST",
      body: JSON.stringify({
        command: "software_trigger",
        arguments: { metadata },
      }),
    });
    const status = await api("/api/runs/current");
    if (status.latest_status === "software trigger queued") {
      markSoftwareTriggerQueuedForLog();
    }
    renderStatus(status);
  } catch (error) {
    appendStatusLog(error.message);
  }
});

stopRunButton.addEventListener("click", async () => {
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

initializeStatusUi();
initializeLiveDataUi();
setDeviceResourceExpanded(true);
updateDeviceResourceSummary();
for (const button of panelToggles) {
  setPanelExpanded(button, true);
}

loadCapabilities()
  .then(() => {
    updateRangeAndLiveChartScale();
    updateDeviceResourceSummary();
    return pollStatus();
  })
  .then(startStatusUpdates)
  .catch((error) => {
    appendStatusLog(error.message);
    startStatusUpdates();
  });
