import { api } from "./api.js";
import { applyStaticTranslations } from "./dom_i18n.js";
import { t } from "./i18n.js";
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
  updateFeatureAvailability,
  updateMeasurementUi,
  updatePanelSummaries,
  updateRangeVisibility,
  updateTriggerButtonUi,
  updateTriggerModeUi,
  validateSwMinInterval,
} from "./run_form.js";
import {
  appendBrowserError,
  appendTranslatedStatusLog,
  initializeStatusUi,
  isRunActive,
  markSoftwareTriggerQueuedForLog,
  pollStatus,
  renderStatus,
  startStatusUpdates,
} from "./status.js";
import { resourceStatusPresentation } from "./presentation_i18n.js";

function setTranslatedText(element, key, params = {}) {
  element.setAttribute("data-i18n", key);
  if (Object.keys(params).length > 0) {
    element.setAttribute("data-i18n-params", JSON.stringify(params));
  } else {
    element.removeAttribute("data-i18n-params");
  }
  element.textContent = t(key, params);
}

function setTranslatedAriaLabel(element, key, params = {}) {
  element.setAttribute("data-i18n-aria-label", key);
  if (Object.keys(params).length > 0) {
    element.setAttribute("data-i18n-params", JSON.stringify(params));
  } else {
    element.removeAttribute("data-i18n-params");
  }
  element.setAttribute("aria-label", t(key, params));
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
  setTranslatedAriaLabel(
    deviceResourceToggleButton,
    expanded
      ? "accessibility.collapse_device_resource"
      : "accessibility.expand_device_resource"
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
    return t("resource.not_scanned");
  }
  const model = scanMetadataByResource.get(resourceSelect.value)?.instrument_model;
  return model
    ? t("resource.live_model", { model })
    : t("resource.live_selected");
}

function expectedModelSummary() {
  return instrumentModelSelect.selectedOptions[0]?.textContent || t("device.auto_detect");
}

function updateDeviceResourceSummary() {
  if (!deviceResourceSummary) {
    return;
  }
  const params = {
    resource: resourceInput.value.trim() || t("resource.no_resource"),
    availability: liveResourceSummary(),
    model: expectedModelSummary(),
  };
  setTranslatedText(deviceResourceSummary, "device.resource_summary", params);
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
  updateFeatureAvailability();
  updateDeviceResourceSummary();
  if (!inferredModel) {
    appendTranslatedStatusLog("resource.model_inference_failed");
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
  appendTranslatedStatusLog("resource.scanning");
  const result = await api("/api/resources?verify=true&live_only=true");
  scanMetadataByResource = new Map(
    result.resources.map((item) => [item.resource, item])
  );
  const placeholder = document.createElement("option");
  placeholder.value = "";
  setTranslatedText(
    placeholder,
    result.resources.length ? "resource.select_live" : "resource.no_live_resources"
  );
  resourceSelect.replaceChildren(
    placeholder,
    ...result.resources.map((item) => {
      const option = document.createElement("option");
      option.value = item.resource;
      if (!item.detail) {
        option.textContent = item.resource;
        return option;
      }
      const statusPresentation = resourceStatusPresentation(item.status);
      if (statusPresentation.kind === "translated") {
        setTranslatedText(option, "resource.option_with_detail", {
          resource: item.resource,
          status: t(statusPresentation.key),
          detail: item.detail,
        });
      } else {
        option.textContent = `${item.resource} (${item.status}: ${item.detail})`;
      }
      return option;
    })
  );
  if (!resourceInput.value && result.resources.length > 0) {
    await applyScannedResource(result.resources[0].resource);
  }
  updateDeviceResourceSummary();
  appendTranslatedStatusLog("resource.scan_result_count", {
    count: result.resources.length,
  });
}

refreshResourcesButton.addEventListener("click", async () => {
  if (isRunActive()) {
    appendTranslatedStatusLog("status.active_run_scan_blocked");
    return;
  }
  try {
    await refreshResources();
  } catch (error) {
    appendBrowserError(error);
  }
});

resourceSelect.addEventListener("change", async () => {
  if (resourceSelect.value) {
    try {
      await applyScannedResource(resourceSelect.value);
    } catch (error) {
      appendBrowserError(error);
    }
  } else {
    updateDeviceResourceSummary();
  }
});

resourceInput.addEventListener("input", () => {
  updateDeviceResourceSummary();
  updateFeatureAvailability();
});

selectCsvFolderButton.addEventListener("click", async () => {
  try {
    appendTranslatedStatusLog("run.opening_csv_folder_selector");
    const result = await api("/api/csv/select-folder", { method: "POST" });
    if (result.selected && result.csv_path) {
      csvInput.value = result.csv_path;
      appendTranslatedStatusLog("run.csv_path_selected", { path: result.csv_path });
    } else {
      appendTranslatedStatusLog("run.csv_folder_selection_cancelled");
    }
  } catch (error) {
    appendBrowserError(error);
  }
});

measurementSelect.addEventListener("change", updateMeasurementAndLiveChartScale);
instrumentModelSelect.addEventListener("change", async () => {
  try {
    await loadCapabilities(instrumentModelSelect.value);
    updateRangeAndLiveChartScale();
    updateDeviceResourceSummary();
  } catch (error) {
    appendBrowserError(error);
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
      ? "live_data.range_step_auto_range"
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
    appendTranslatedStatusLog("status.active_run_start_blocked");
    return;
  }
  try {
    const payload = formPayload();
    if (!payload.resource) {
      appendTranslatedStatusLog("validation.visa_resource_required");
      resourceInput.focus();
      return;
    }
    validateSwMinInterval();
    if (!form.checkValidity()) {
      appendTranslatedStatusLog("validation.check_run_settings");
      form.reportValidity();
      return;
    }
    renderStatus(await api("/api/runs", {
      method: "POST",
      body: JSON.stringify(payload),
    }));
  } catch (error) {
    appendBrowserError(error);
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
    appendBrowserError(error);
  }
});

stopRunButton.addEventListener("click", async () => {
  try {
    renderStatus(await api("/api/runs/current/stop", { method: "POST" }));
  } catch (error) {
    appendBrowserError(error);
  }
});

openCsvButton.addEventListener("click", async () => {
  try {
    const result = await api("/api/runs/current/open-csv", { method: "POST" });
    appendTranslatedStatusLog("run.opened_csv", { path: result.csv_path });
  } catch (error) {
    appendBrowserError(error);
  }
});

applyStaticTranslations(document);
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
    appendBrowserError(error);
    startStatusUpdates();
  });
