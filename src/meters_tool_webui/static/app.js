import { api } from "./api.js";
import { applyStaticTranslations, setTranslatedText, setTranslatedAriaLabel } from "./dom_i18n.js";
import { getLocale, t } from "./i18n.js";
import { helpPathForLocale, initializeLocaleUi } from "./locale_ui.js";
import {
  acBandwidthSelect,
  autoRangeCheckbox,
  autoZeroSelect,
  csvEnabledCheckbox,
  csvInput,
  currentTerminalSelect,
  deviceResourceBody,
  deviceResourceSummary,
  deviceResourceToggleButton,
  deviceOptionsPanel,
  deviceOptionsToggleButton,
  executionModeInputs,
  executionModelHelp,
  executionModelLabel,
  form,
  freqPeriodTimeoutSelect,
  gateTimeSelect,
  helpButton,
  instrumentModelSelect,
  visaLibrarySelect,
  supportedBackendButtons,
  localeToggle,
  localeToggleLabel,
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
  supportedDevicesBody,
  supportedDevicesPanel,
  supportedDevicesToggleButton,
  swMinIntervalInput,
  timerIntervalInput,
  timerTriggerCheckbox,
  triggerCountInfiniteCheckbox,
  triggerModeSelect,
  triggerRunButton,
  themeToggle,
  themeToggleLabel,
} from "./dom.js";
import { buildExecutionRequest } from "./run_form_payload.js";
import {
  initializeLiveDataUi,
  refreshLiveChartScaleAvailability,
} from "./live_data.js";
import {
  formPayload,
  loadCapabilities,
  invalidateCapabilities,
  triggerMetadataPayload,
  productLiveAvailability,
  updateFeatureAvailability,
  updateMeasurementUi,
  updatePanelSummaries,
  refreshRunFormPresentation,
  updateRangeVisibility,
  updateTriggerButtonUi,
  updateTriggerModeUi,
  updateStartButtonUi,
  validateSwMinInterval,
} from "./run_form.js";
import {
  appendBrowserError,
  appendTranslatedStatusLog,
  beginPlanPreview,
  clearPlanPreview,
  initializeStatusUi,
  isRunActive,
  markSoftwareTriggerQueuedForLog,
  pollStatus,
  renderStatus,
  renderStartStatus,
  renderPlanPreview,
  refreshStatusPresentation,
  startStatusUpdates,
} from "./status.js";
import { resourceStatusPresentation } from "./presentation_i18n.js";
import { initializeThemeUi } from "./theme_ui.js";

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

function setSupportedDevicesExpanded(expanded) {
  if (!supportedDevicesPanel || !supportedDevicesToggleButton) {
    return;
  }
  if (expanded) {
    supportBackend = visaLibrarySelect.value;
    renderSupportedDevices();
  }
  supportedDevicesPanel.classList.toggle("is-hidden", !expanded);
  supportedDevicesToggleButton.setAttribute("aria-expanded", String(expanded));
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
let resourceScanCompleted = false;
let currentExecutionMode = "real";
let executionRequestPending = false;
let realResourceValue = resourceInput.value;
let realModelValue = instrumentModelSelect.value;
let noHardwareModelValue = "";
let supportedDevices = [];
let supportBackend = "";
let selectedBackend = visaLibrarySelect.value;
let scanRevision = 0;

function connectionLabel(connection) {
  return connection === "tcpip"
    ? t("supported_devices.connection.tcpip")
    : t("supported_devices.connection.usb");
}

function renderSupportedDevices() {
  if (!supportedDevicesBody) {
    return;
  }
  const backend = supportBackend === "@py" ? "pyvisa_py" : "system_visa";
  for (const button of supportedBackendButtons) {
    button.setAttribute("aria-pressed", String(button.dataset.supportBackend === supportBackend));
  }
  supportedDevicesBody.replaceChildren(
    ...supportedDevices.filter((device) => device.backend_connections?.[backend]?.length).map((device) => {
      const row = document.createElement("tr");
      for (const value of [
        device.model,
        (device.backend_connections[backend] || [])
          .map(connectionLabel)
          .join(t("supported_devices.connection_separator")),
      ]) {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.appendChild(cell);
      }
      return row;
    })
  );
}

function setExecutionModeSelection(mode) {
  for (const input of executionModeInputs) {
    input.checked = input.value === mode;
  }
}

function updateModelSelectorPresentation() {
  const noHardware = currentExecutionMode !== "real";
  const labelKey = currentExecutionMode === "simulate"
    ? "device.simulation_model"
    : currentExecutionMode === "dry-run"
      ? "device.planning_model"
      : "device.expected_model";
  const helpKey = currentExecutionMode === "simulate"
    ? "device.simulation_model_help"
    : currentExecutionMode === "dry-run"
      ? "device.planning_model_help"
      : "device.expected_model_help";
  setTranslatedText(executionModelLabel, labelKey);
  setTranslatedText(executionModelHelp, helpKey);
  for (const option of instrumentModelSelect.options) {
    if (!option.value) {
      option.disabled = noHardware;
      setTranslatedText(
        option,
        noHardware ? "device.select_model" : "device.auto_detect"
      );
    } else {
      setTranslatedText(
        option,
        noHardware ? "device.model_value" : "device.require_model",
        { model: option.value }
      );
    }
  }
}

function updateExecutionModePresentation() {
  const noHardware = currentExecutionMode !== "real";
  visaLibrarySelect.disabled = executionRequestPending || isRunActive();
  startRunButton.dataset.executionPending = String(executionRequestPending);
  updateStartButtonUi(isRunActive());
  for (const input of executionModeInputs) {
    input.disabled = executionRequestPending || isRunActive();
  }
  resourceInput.disabled = noHardware;
  resourceInput.required = !noHardware;
  resourceSelect.disabled = noHardware;
  refreshResourcesButton.dataset.executionDisabled = String(noHardware);
  refreshResourcesButton.disabled = noHardware || isRunActive();
  deviceResourceToggleButton.disabled = noHardware;
  if (noHardware) {
    deviceResourceBody.classList.add("is-hidden");
  } else {
    deviceResourceBody.classList.toggle(
      "is-hidden",
      deviceResourceToggleButton.getAttribute("aria-expanded") !== "true"
    );
  }
  instrumentModelSelect.required = noHardware;
  document.querySelector("#model-support-summary")?.classList.toggle(
    "is-hidden",
    noHardware
  );
  const dryRun = currentExecutionMode === "dry-run";
  triggerRunButton.dataset.executionDisabled = String(dryRun);
  stopRunButton.dataset.executionDisabled = String(dryRun);
  if (dryRun) {
    triggerRunButton.disabled = true;
    stopRunButton.disabled = true;
  } else {
    stopRunButton.disabled = false;
    updateTriggerButtonUi();
  }
  setTranslatedText(startRunButton, dryRun ? "execution.preview_plan" : "run.start");
  updateModelSelectorPresentation();
  updateDeviceResourceSummary();
}

async function switchExecutionMode(nextMode) {
  if (executionRequestPending || isRunActive()) {
    setExecutionModeSelection(currentExecutionMode);
    return;
  }
  if (nextMode === currentExecutionMode) {
    return;
  }
  if (currentExecutionMode === "real") {
    realResourceValue = resourceInput.value;
    realModelValue = instrumentModelSelect.value;
    if (!noHardwareModelValue && realModelValue) {
      noHardwareModelValue = realModelValue;
    }
  } else {
    noHardwareModelValue = instrumentModelSelect.value;
  }
  scanRevision += 1;
  currentExecutionMode = nextMode;
  if (currentExecutionMode === "real") {
    resourceInput.value = realResourceValue;
    instrumentModelSelect.value = realModelValue;
  } else {
    resourceInput.value = "";
    instrumentModelSelect.value = noHardwareModelValue;
  }
  clearPlanPreview();
  updateExecutionModePresentation();
  updateFeatureAvailability(
    currentExecutionMode === "real"
      ? scanMetadataByResource.get(resourceInput.value.trim())?.instrument_model : null
  );
  await loadCapabilities(instrumentModelSelect.value);
  updateModelSelectorPresentation();
  updateRangeAndLiveChartScale();
  updateDeviceResourceSummary();
}

function liveResourceSummary() {
  if (!resourceSelect.value) {
    return resourceScanCompleted
      ? t("resource.no_live_resources")
      : t("resource.not_scanned");
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
  if (currentExecutionMode !== "real") {
    const model = instrumentModelSelect.value || t("device.select_model");
    setTranslatedText(
      deviceResourceSummary,
      currentExecutionMode === "simulate"
        ? "device.simulation_summary"
        : "device.planning_summary",
      { model }
    );
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
  const revision = scanRevision;
  const metadata = scanMetadataByResource.get(resource);
  const inferredModel = metadata?.instrument_model || null;
  const forcedModel = instrumentModelSelect.value || "";
  resourceInput.value = resource;
  resourceSelect.value = resource;
  updateFeatureAvailability(inferredModel);
  updateDeviceResourceSummary();
  if (!inferredModel) {
    appendTranslatedStatusLog("resource.model_inference_failed");
    return;
  }
  const capabilities = await loadCapabilities(forcedModel || inferredModel, resource);
  if (!capabilities || revision !== scanRevision) return;
  instrumentModelSelect.value = forcedModel;
  updateRangeAndLiveChartScale();
  updateTriggerModeUi();
  updatePanelSummaries();
  updateDeviceResourceSummary();
}

function renderScannedResourceOptions() {
  const previousResource = resourceSelect.value;
  const resources = [...scanMetadataByResource.values()];
  const placeholder = document.createElement("option");
  placeholder.value = "";
  setTranslatedText(
    placeholder,
    !resourceScanCompleted
      ? "resource.not_scanned"
      : resources.length ? "resource.select_live" : "resource.no_live_resources"
  );
  resourceSelect.replaceChildren(
    placeholder,
    ...resources.map((item) => {
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
  if (resources.some((item) => item.resource === previousResource)) {
    resourceSelect.value = previousResource;
  }
}

export function refreshResourcesPresentation() {
  renderScannedResourceOptions();
  updateDeviceResourceSummary();
}

async function refreshResources() {
  appendTranslatedStatusLog("resource.scanning");
  const revision = ++scanRevision;
  const query = selectedBackend ? `&visa_library=${encodeURIComponent(selectedBackend)}` : "";
  let result;
  try {
    result = await api(`/api/resources?verify=true&live_only=true${query}`);
  } catch (error) {
    if (revision !== scanRevision) return;
    throw error;
  }
  if (revision !== scanRevision || currentExecutionMode !== "real") return;
  scanMetadataByResource = new Map(
    result.resources.map((item) => [item.resource, item])
  );
  resourceScanCompleted = true;
  renderScannedResourceOptions();
  if (!resourceInput.value && result.resources.length > 0) {
    await applyScannedResource(result.resources[0].resource);
  }
  if (revision !== scanRevision) return;
  updateFeatureAvailability(scanMetadataByResource.get(resourceInput.value.trim())?.instrument_model);
  updateDeviceResourceSummary();
  appendTranslatedStatusLog("resource.scan_result_count", {
    count: result.resources.length,
  });
}

visaLibrarySelect.addEventListener("change", async () => {
  if (executionRequestPending || isRunActive()) {
    visaLibrarySelect.value = selectedBackend;
    return;
  }
  selectedBackend = visaLibrarySelect.value;
  scanRevision += 1;
  invalidateCapabilities();
  scanMetadataByResource.clear();
  resourceScanCompleted = false;
  resourceInput.value = "";
  realResourceValue = "";
  renderScannedResourceOptions();
  clearPlanPreview();
  updateFeatureAvailability();
  updateDeviceResourceSummary();
  try {
    const capabilities = await loadCapabilities(instrumentModelSelect.value);
    if (capabilities) {
      supportedDevices = capabilities.supported_devices || [];
      renderSupportedDevices();
      updateModelSelectorPresentation();
    }
  } catch (error) {
    appendBrowserError(error);
  }
});

for (const button of supportedBackendButtons) {
  button.addEventListener("click", () => {
    supportBackend = button.dataset.supportBackend;
    renderSupportedDevices();
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
  scanRevision += 1;
  resourceSelect.value = scanMetadataByResource.has(resourceInput.value.trim())
    ? resourceInput.value.trim() : "";
  updateDeviceResourceSummary();
  updateFeatureAvailability(scanMetadataByResource.get(resourceInput.value.trim())?.instrument_model);
});

let csvFolderPickerPending = false;

function updateCsvOutputUi() {
  const enabled = csvEnabledCheckbox.checked;
  for (const selector of ["#csv-format", "#csv-elapsed", "#csv-delta"]) {
    const control = document.querySelector(selector);
    if (control) control.disabled = !enabled;
  }
  csvInput.disabled = !enabled;
  selectCsvFolderButton.disabled = !enabled;
  if (csvFolderPickerPending) selectCsvFolderButton.disabled = true;
  updatePanelSummaries();
}

csvEnabledCheckbox.addEventListener("change", updateCsvOutputUi);
for (const selector of ["#csv-format", "#csv-elapsed", "#csv-delta"]) {
  document.querySelector(selector)?.addEventListener("change", updatePanelSummaries);
}

selectCsvFolderButton.addEventListener("click", async () => {
  if (csvFolderPickerPending) return;
  csvFolderPickerPending = true;
  updateCsvOutputUi();
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
  } finally {
    csvFolderPickerPending = false;
    updateCsvOutputUi();
  }
});

measurementSelect.addEventListener("change", updateMeasurementAndLiveChartScale);
instrumentModelSelect.addEventListener("change", async () => {
  try {
    if (currentExecutionMode === "real") {
      realModelValue = instrumentModelSelect.value;
    } else {
      noHardwareModelValue = instrumentModelSelect.value;
    }
    const capabilities = await loadCapabilities(instrumentModelSelect.value);
    if (capabilities) {
      supportedDevices = capabilities.supported_devices || [];
      renderSupportedDevices();
      updateModelSelectorPresentation();
    }
    updateRangeAndLiveChartScale();
    updateDeviceResourceSummary();
  } catch (error) {
    appendBrowserError(error);
  }
});
for (const input of executionModeInputs) {
  input.addEventListener("change", async () => {
    if (!input.checked) {
      return;
    }
    try {
      await switchExecutionMode(input.value);
    } catch (error) {
      setExecutionModeSelection(currentExecutionMode);
      appendBrowserError(error);
    }
  });
}
triggerModeSelect.addEventListener("change", updateTriggerModeUi);
timerIntervalInput.addEventListener("input", () => {
  updateTriggerButtonUi();
  updatePanelSummaries();
});
timerTriggerCheckbox.addEventListener("change", updateTriggerModeUi);
triggerCountInfiniteCheckbox.addEventListener("change", updateTriggerModeUi);
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
    setSupportedDevicesExpanded(false);
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
    setSupportedDevicesExpanded(false);
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
if (supportedDevicesToggleButton && supportedDevicesPanel) {
  supportedDevicesToggleButton.addEventListener("click", (event) => {
    event.stopPropagation();
    setDeviceOptionsExpanded(false);
    setSupportedDevicesExpanded(
      supportedDevicesToggleButton.getAttribute("aria-expanded") !== "true"
    );
  });
  supportedDevicesPanel.addEventListener("click", (event) => {
    event.stopPropagation();
  });
  document.addEventListener("keydown", (event) => {
    if (
      event.key === "Escape" &&
      supportedDevicesToggleButton.getAttribute("aria-expanded") === "true"
    ) {
      setSupportedDevicesExpanded(false);
      supportedDevicesToggleButton.focus();
    }
  });
}

startRunButton.addEventListener("click", async () => {
  if (executionRequestPending || isRunActive()) {
    appendTranslatedStatusLog("status.active_run_start_blocked");
    return;
  }
  const availability = productLiveAvailability();
  if (!availability.available) {
    updateStartButtonUi(isRunActive());
    appendTranslatedStatusLog(availability.reasonKey);
    return;
  }
  const submittedMode = currentExecutionMode;
  try {
    const payload = formPayload();
    if (submittedMode !== "real" && !payload.instrument_model) {
      appendTranslatedStatusLog("validation.execution_model_required");
      instrumentModelSelect.focus();
      return;
    }
    if (submittedMode === "real" && !payload.resource) {
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
    const request = buildExecutionRequest(payload, submittedMode);
    executionRequestPending = true;
    updateExecutionModePresentation();
    if (submittedMode === "dry-run") {
      beginPlanPreview();
    } else {
      clearPlanPreview();
    }
    const result = await api(request.path, {
      method: "POST",
      body: JSON.stringify(request.payload),
    });
    if (submittedMode === "dry-run") {
      renderPlanPreview(result);
    } else {
      renderStartStatus(result);
    }
  } catch (error) {
    appendBrowserError(error);
  } finally {
    executionRequestPending = false;
    updateExecutionModePresentation();
  }
});

triggerRunButton.addEventListener("click", async () => {
  if (currentExecutionMode === "dry-run") {
    return;
  }
  try {
    const metadata = triggerMetadataPayload();
    await api("/api/runs/current/command", {
      method: "POST",
      body: JSON.stringify({
        metadata,
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
  if (currentExecutionMode === "dry-run") {
    return;
  }
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

if (helpButton) {
  helpButton.addEventListener("click", () => {
    window.open(helpPathForLocale(getLocale()), "_blank", "noopener");
  });
}

function refreshLocalizedPresentation() {
  applyStaticTranslations(document);
  themeUi.refresh();
  refreshRunFormPresentation();
  refreshResourcesPresentation();
  refreshStatusPresentation();
  updateExecutionModePresentation();
  renderSupportedDevices();
}

function browserStorage() {
  try {
    return window.localStorage;
  } catch (_error) {
    return null;
  }
}

function browserNavigator() {
  try {
    return navigator;
  } catch (_error) {
    return null;
  }
}

initializeLocaleUi({
  button: localeToggle,
  label: localeToggleLabel,
  documentElement: document.documentElement,
  storage: browserStorage(),
  navigatorLike: browserNavigator(),
  onLocaleChange: refreshLocalizedPresentation,
});

const themeUi = initializeThemeUi({
  button: themeToggle,
  label: themeToggleLabel,
  documentElement: document.documentElement,
  cookieDocument: document,
  mediaQuery: (() => {
    try {
      return window.matchMedia?.("(prefers-color-scheme: dark)") || null;
    } catch (_error) {
      return null;
    }
  })(),
});

applyStaticTranslations(document);

initializeStatusUi();
initializeLiveDataUi();
updateCsvOutputUi();
setDeviceResourceExpanded(true);
setExecutionModeSelection("real");
updateExecutionModePresentation();
updateDeviceResourceSummary();
for (const button of panelToggles) {
  setPanelExpanded(button, true);
}

loadCapabilities()
  .then((capabilities) => {
    if (capabilities) supportedDevices = capabilities.supported_devices || [];
    renderSupportedDevices();
    updateModelSelectorPresentation();
    updateRangeAndLiveChartScale();
    updateDeviceResourceSummary();
    return pollStatus();
  })
  .then(startStatusUpdates)
  .catch((error) => {
    appendBrowserError(error);
    startStatusUpdates();
  });
