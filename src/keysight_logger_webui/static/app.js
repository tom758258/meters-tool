import { api } from "./api.js";
import {
  acBandwidthSelect,
  autoRangeCheckbox,
  autoZeroSelect,
  csvInput,
  currentTerminalSelect,
  form,
  freqPeriodTimeoutSelect,
  gateTimeSelect,
  measurementSelect,
  nplcSelect,
  openCsvButton,
  panelToggles,
  resourceInput,
  resourceSelect,
  selectCsvFolderButton,
  swMinIntervalInput,
  timerIntervalInput,
  timerTriggerCheckbox,
  triggerModeSelect,
  triggerRunButton,
} from "./dom.js";
import { initializeLiveDataUi } from "./live_data.js";
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

async function refreshResources() {
  appendStatusLog("Scanning live resources...");
  const result = await api("/api/resources?verify=true&live_only=true");
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
    resourceInput.value = result.resources[0].resource;
    resourceSelect.value = result.resources[0].resource;
  }
  appendStatusLog(`Live resources found: ${result.resources.length}`);
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

initializeStatusUi();
initializeLiveDataUi();
for (const button of panelToggles) {
  setPanelExpanded(button, true);
}

loadCapabilities()
  .then(() => {
    updateRangeVisibility();
    return pollStatus();
  })
  .then(startStatusUpdates)
  .catch((error) => {
    appendStatusLog(error.message);
    startStatusUpdates();
  });
