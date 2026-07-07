import {
  autoRangeCheckbox,
  closeLiveSampleDetailsButton,
  liveChartContent,
  liveChartEmpty,
  liveChartManualSpanField,
  liveChartManualSpanInput,
  liveChartScaleInfo,
  liveChartScaleModeHelp,
  liveChartScaleModeSelect,
  liveDataSummary,
  liveLatestTime,
  liveLatestTrigger,
  liveLatestValue,
  liveSampleDetails,
  liveSampleMetadata,
  liveSamplesBody,
  liveSelectedSample,
  liveStatAverage,
  liveStatMax,
  liveStatMin,
  liveStatSample,
  liveStatSpan,
  liveStatStdDev,
  liveStatsGrid,
  liveTableWrap,
  liveTrendChart,
  measurementRangeInput,
  toggleLiveChartButton,
  toggleLiveSamplesButton,
  toggleLiveStatsButton,
} from "./dom.js";

const SVG_NS = "http://www.w3.org/2000/svg";
const LIVE_CHART_VISIBLE_GRID_LIMIT = 4;
const LIVE_CHART_GRID_LINE_COUNT_PER_SIDE = 5;
let selectedLiveSampleSequence = null;
let liveSampleDetailsVisible = false;
let liveChartBaselineRunId = null;
let liveChartBaselineValue = null;
let liveChartScaleMode = "auto-deviation";
let liveChartManualSpan = null;
let liveChartManualSpanInputInvalid = false;
let liveChartScaleNotice = "";
let lastLiveChartSamples = [];

if (typeof window !== "undefined") {
  window.__KEYSIGHT_LIVE_DATA_SCALE_MODES__ = true;
}

export function setLiveSectionVisible(button, section, visible) {
  section.classList.toggle("is-hidden", !visible);
  button.setAttribute("aria-expanded", String(visible));
  button.textContent = visible ? "-" : "+";
}

export function initializeLiveDataUi() {
  liveChartScaleMode = liveChartScaleModeSelect.value || "auto-deviation";

  closeLiveSampleDetailsButton.addEventListener("click", () => {
    liveSampleDetailsVisible = false;
    selectedLiveSampleSequence = null;
    renderLiveSampleDetails(null);
    updateLiveSelectedRows();
  });
  liveChartScaleModeSelect.addEventListener("change", () => {
    liveChartScaleMode = liveChartScaleModeSelect.value || "auto-deviation";
    liveChartScaleNotice = "";
    liveChartManualSpanInputInvalid =
      liveChartScaleMode === "manual-span" && !validManualSpanInput();
    refreshLiveChartScaleAvailability();
    updateLiveChartScaleControls();
    renderLiveChart(lastLiveChartSamples);
  });
  liveChartManualSpanInput.addEventListener("input", () => {
    liveChartScaleNotice = "";
    const span = Number(liveChartManualSpanInput.value);
    if (Number.isFinite(span) && span > 0) {
      liveChartManualSpan = span;
      liveChartManualSpanInputInvalid = false;
    } else {
      liveChartManualSpanInputInvalid = true;
    }
    renderLiveChart(lastLiveChartSamples);
  });
  toggleLiveStatsButton.addEventListener("click", () => {
    setLiveSectionVisible(
      toggleLiveStatsButton,
      liveStatsGrid,
      toggleLiveStatsButton.getAttribute("aria-expanded") !== "true"
    );
  });
  toggleLiveChartButton.addEventListener("click", () => {
    setLiveSectionVisible(
      toggleLiveChartButton,
      liveChartContent,
      toggleLiveChartButton.getAttribute("aria-expanded") !== "true"
    );
  });
  toggleLiveSamplesButton.addEventListener("click", () => {
    setLiveSectionVisible(
      toggleLiveSamplesButton,
      liveTableWrap,
      toggleLiveSamplesButton.getAttribute("aria-expanded") !== "true"
    );
  });

  setLiveSectionVisible(toggleLiveChartButton, liveChartContent, true);
  setLiveSectionVisible(toggleLiveStatsButton, liveStatsGrid, true);
  setLiveSectionVisible(toggleLiveSamplesButton, liveTableWrap, true);
  refreshLiveChartScaleAvailability();
  updateLiveChartScaleControls();
  renderLiveChart(lastLiveChartSamples);
}

export function refreshLiveChartScaleAvailability(notice = null) {
  if (notice !== null) {
    liveChartScaleNotice = notice;
  }
  const rangeStepOption = liveChartScaleModeSelect.querySelector(
    'option[value="range-step"]'
  );
  if (!rangeStepOption) {
    return;
  }
  const rangeStepAvailable = liveChartRangeStepAvailable();
  rangeStepOption.disabled = !rangeStepAvailable;
  if (liveChartScaleModeHelp) {
    liveChartScaleModeHelp.textContent = rangeStepAvailable
      ? ""
      : rangeStepUnavailableMessage();
    liveChartScaleModeHelp.classList.toggle("is-hidden", rangeStepAvailable);
  }
  if (liveChartScaleMode !== "range-step") {
    renderLiveChart(lastLiveChartSamples);
    return;
  }
  if (rangeStepAvailable) {
    renderLiveChart(lastLiveChartSamples);
    return;
  }
  liveChartScaleMode = "auto-deviation";
  liveChartScaleModeSelect.value = "auto-deviation";
  liveChartScaleNotice = notice || rangeStepUnavailableMessage();
  updateLiveChartScaleControls();
  renderLiveChart(lastLiveChartSamples);
}

export function renderLiveData(status) {
  const samples = Array.isArray(status.recent_samples) ? status.recent_samples : [];
  const latest = status.latest_sample || samples[samples.length - 1] || null;
  const capacity = Number(status.sample_capacity || 100);
  updateLiveChartBaseline(status, samples);

  if (samples.length === 0) {
    selectedLiveSampleSequence = null;
  } else if (
    selectedLiveSampleSequence === null ||
    !samples.some((sample) => sameSequence(sample.sequence, selectedLiveSampleSequence))
  ) {
    selectedLiveSampleSequence = latest.sequence;
  }

  liveDataSummary.textContent = samples.length
    ? `${samples.length}/${capacity} recent samples`
    : "No samples captured";
  liveLatestValue.textContent = latest
    ? formatLiveValueWithUnit(latest.value, latest.unit)
    : "--";
  liveLatestTime.textContent = latest
    ? formatLiveTime(latest.timestamp_utc_plus_8)
    : "--";
  liveLatestTrigger.textContent = latest ? formatLiveTrigger(latest) : "--";
  renderLiveStats(samples, latest);
  renderLiveChart(samples);
  renderLiveSamplesTable(samples);
  renderLiveSampleDetails(
    samples.find((sample) =>
      sameSequence(sample.sequence, selectedLiveSampleSequence)
    ) || null
  );
}

function updateLiveChartBaseline(status, samples) {
  const runId = status.run_id || null;
  if (runId !== liveChartBaselineRunId) {
    liveChartBaselineRunId = runId;
    liveChartBaselineValue = null;
  }
  if (runId === null || liveChartBaselineValue !== null) {
    return;
  }
  const firstNumericSample = samples.find((sample) =>
    Number.isFinite(Number(sample.value))
  );
  if (firstNumericSample) {
    liveChartBaselineValue = Number(firstNumericSample.value);
  }
}

function renderLiveStats(samples, latest) {
  const unit = latest?.unit || samples.find((sample) => sample.unit)?.unit || "";
  const values = samples
    .map((sample) => Number(sample.value))
    .filter((value) => Number.isFinite(value));
  if (values.length === 0) {
    liveStatMin.textContent = "--";
    liveStatAverage.textContent = "--";
    liveStatMax.textContent = "--";
    liveStatSpan.textContent = "--";
    liveStatStdDev.textContent = "--";
    liveStatSample.textContent = latest ? `#${latest.sequence}` : "--";
    return;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const average = values.reduce((total, value) => total + value, 0) / values.length;
  const variance =
    values.reduce((total, value) => total + ((value - average) ** 2), 0) / values.length;

  liveStatMin.textContent = formatLiveValueWithUnit(min, unit);
  liveStatAverage.textContent = formatLiveValueWithUnit(average, unit);
  liveStatMax.textContent = formatLiveValueWithUnit(max, unit);
  liveStatSpan.textContent = formatLiveValueWithUnit(max - min, unit);
  liveStatStdDev.textContent = formatLiveValueWithUnit(Math.sqrt(variance), unit);
  liveStatSample.textContent = latest ? `#${latest.sequence}` : "--";
}

function renderLiveChart(samples) {
  lastLiveChartSamples = samples;
  const numericSamples = samples.filter((sample) =>
    Number.isFinite(Number(sample.value))
  );
  liveTrendChart.replaceChildren();
  const width = Math.max(Math.round(liveTrendChart.clientWidth || 0), 640);
  const height = Math.max(Math.round(liveTrendChart.clientHeight || 0), 760);
  liveTrendChart.setAttribute("viewBox", `0 0 ${width} ${height}`);
  const leftPadding = 120;
  const rightPadding = 18;
  const topBottomPadding = 18;
  const plotLeft = leftPadding;
  const plotRight = width - rightPadding;
  const plotWidth = plotRight - plotLeft;
  const centerY = height / 2;
  const gridStepPx = (
    centerY - topBottomPadding
  ) / LIVE_CHART_GRID_LINE_COUNT_PER_SIDE;

  for (
    let offset = -LIVE_CHART_GRID_LINE_COUNT_PER_SIDE;
    offset <= LIVE_CHART_GRID_LINE_COUNT_PER_SIDE;
    offset += 1
  ) {
    const y = centerY + offset * gridStepPx;
    liveTrendChart.appendChild(svgElement("line", {
      x1: plotLeft,
      y1: y,
      x2: plotRight,
      y2: y,
      class: offset === 0
        ? "live-chart-grid live-chart-grid-center"
        : "live-chart-grid",
    }));
  }

  if (numericSamples.length === 0) {
    liveChartEmpty.textContent = "Waiting for samples";
    liveChartEmpty.classList.remove("is-hidden");
    liveChartScaleInfo.textContent = liveChartScaleNotice
      ? liveChartScaleNotice
      : scaleModeLabel(liveChartScaleMode);
    return;
  }

  const values = numericSamples.map((sample) => Number(sample.value));
  const unit = numericSamples[numericSamples.length - 1]?.unit || "";
  const baseline = Number.isFinite(liveChartBaselineValue)
    ? liveChartBaselineValue
    : values[0];
  const scale = liveChartScaleFor(
    values,
    baseline,
    liveChartScaleMode,
    liveChartManualSpan,
    liveChartManualSpanInputInvalid,
    selectedManualRange()
  );
  for (
    let offset = -LIVE_CHART_GRID_LINE_COUNT_PER_SIDE;
    offset <= LIVE_CHART_GRID_LINE_COUNT_PER_SIDE;
    offset += 1
  ) {
    const y = centerY + offset * gridStepPx;
    const valueAtGrid = scale.center - offset * scale.gridStepValue;
    const label = svgElement("text", {
      x: plotLeft - 10,
      y,
      "text-anchor": "end",
      "dominant-baseline": "middle",
      class: "live-chart-axis-label",
    });
    label.textContent = formatLiveAxisLabel(valueAtGrid, unit);
    liveTrendChart.appendChild(label);
  }
  const points = numericSamples.map((sample, index) => {
    const x = numericSamples.length === 1
      ? plotLeft + plotWidth / 2
      : plotLeft + (index * plotWidth) / (numericSamples.length - 1);
    const gridOffset = clamp(
      (Number(sample.value) - scale.center) / scale.gridStepValue,
      -LIVE_CHART_GRID_LINE_COUNT_PER_SIDE,
      LIVE_CHART_GRID_LINE_COUNT_PER_SIDE
    );
    const y = centerY - gridOffset * gridStepPx;
    return { x, y };
  });

  if (points.length > 1) {
    liveTrendChart.appendChild(svgElement("polyline", {
      points: points.map((point) => `${point.x},${point.y}`).join(" "),
      class: "live-chart-line",
    }));
  }
  const lastPoint = points[points.length - 1];
  liveTrendChart.appendChild(svgElement("circle", {
    cx: lastPoint.x,
    cy: lastPoint.y,
    r: 2.75,
    class: "live-chart-point",
  }));
  liveChartEmpty.classList.add("is-hidden");
  liveChartScaleInfo.textContent = liveChartScaleNotice
    ? liveChartScaleNotice
    : formatLiveChartScaleInfo(scale, unit);
}

function updateLiveChartScaleControls() {
  const manual = liveChartScaleMode === "manual-span";
  liveChartManualSpanField.classList.toggle("is-hidden", !manual);
  liveChartManualSpanField.setAttribute("aria-hidden", String(!manual));
  liveChartManualSpanInput.disabled = !manual;
}

function liveChartScaleFor(
  values,
  baseline,
  mode,
  manualSpan,
  manualSpanInputInvalid,
  rangeStepSpan
) {
  if (mode === "auto-absolute") {
    return chartScaleForAutoAbsolute(values);
  }
  if (mode === "range-step") {
    return chartScaleForRangeStep(baseline, rangeStepSpan)
      || chartScaleForAutoDeviation(values, baseline);
  }
  if (mode === "manual-span") {
    const manualScale = chartScaleForManualSpan(baseline, manualSpan);
    if (manualSpanInputInvalid) {
      return {
        ...(manualScale || chartScaleForAutoDeviation(values, baseline)),
        mode: "manual-span-invalid",
      };
    }
    if (manualScale) {
      return manualScale;
    }
    return {
      ...chartScaleForAutoDeviation(values, baseline),
      mode: "manual-span-invalid",
    };
  }
  return chartScaleForAutoDeviation(values, baseline);
}

function chartScaleForAutoDeviation(values, baseline) {
  const deviations = values.map((value) => value - baseline);
  const maxAbsDeviation = Math.max(...deviations.map((value) => Math.abs(value)));
  const gridStepValue = Math.max(
    maxAbsDeviation / LIVE_CHART_VISIBLE_GRID_LIMIT,
    minimumGridValueFor(baseline)
  );
  return {
    mode: "auto-deviation",
    center: baseline,
    gridStepValue,
  };
}

function chartScaleForAutoAbsolute(values) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const center = (min + max) / 2;
  const halfRange = (max - min) / 2;
  const paddedHalfRange = Math.max(
    halfRange * 1.1,
    minimumGridValueFor(center) * LIVE_CHART_GRID_LINE_COUNT_PER_SIDE
  );
  return {
    mode: "auto-absolute",
    center,
    gridStepValue: paddedHalfRange / LIVE_CHART_GRID_LINE_COUNT_PER_SIDE,
    min,
    max,
  };
}

function chartScaleForManualSpan(baseline, span) {
  if (!Number.isFinite(span) || span <= 0) {
    return null;
  }
  return {
    mode: "manual-span",
    center: baseline,
    gridStepValue: span / LIVE_CHART_GRID_LINE_COUNT_PER_SIDE,
    span,
  };
}

function chartScaleForRangeStep(baseline, span) {
  if (!Number.isFinite(span) || span <= 0) {
    return null;
  }
  return {
    mode: "range-step",
    center: baseline,
    gridStepValue: span / LIVE_CHART_GRID_LINE_COUNT_PER_SIDE,
    span,
  };
}

function minimumGridValueFor(value) {
  return Math.max(Math.abs(value), 1) * 1e-9;
}

function validManualSpanInput() {
  const span = Number(liveChartManualSpanInput.value);
  return Number.isFinite(span) && span > 0;
}

function liveChartRangeStepAvailable() {
  return !autoRangeCheckbox.checked
    && hasMeasurementRangeOptions()
    && Number.isFinite(selectedManualRange())
    && selectedManualRange() > 0;
}

function hasMeasurementRangeOptions() {
  return [...measurementRangeInput.options].some((option) => option.value !== "");
}

function selectedManualRange() {
  const range = Number(measurementRangeInput.value);
  return Number.isFinite(range) ? range : null;
}

function rangeStepUnavailableMessage() {
  if (autoRangeCheckbox.checked) {
    return "Range step disabled because Auto range is on.";
  }
  return "Range step requires Auto range off and a selected manual Range.";
}

function formatLiveChartScaleInfo(scale, unit) {
  if (scale.mode === "auto-absolute") {
    return `Auto absolute: Range ${formatLiveValueWithUnit(scale.min, unit)} to ${formatLiveValueWithUnit(scale.max, unit)}`;
  }
  if (scale.mode === "range-step") {
    return `Range step: Center ${formatLiveValueWithUnit(scale.center, unit)} / Span ${formatLiveValueWithUnit(scale.span, unit)} / Grid ${formatLiveValueWithUnit(scale.gridStepValue, unit)}`;
  }
  if (scale.mode === "manual-span") {
    return `Manual span: Center ${formatLiveValueWithUnit(scale.center, unit)} / Span ${formatLiveValueWithUnit(scale.span, unit)}`;
  }
  if (scale.mode === "manual-span-invalid") {
    return "Manual span requires a positive value";
  }
  return `Auto deviation: Center ${formatLiveValueWithUnit(scale.center, unit)} / Grid ${formatLiveValueWithUnit(scale.gridStepValue, unit)}`;
}

function scaleModeLabel(mode) {
  if (mode === "auto-absolute") {
    return "Auto absolute";
  }
  if (mode === "manual-span") {
    return "Manual span";
  }
  if (mode === "range-step") {
    return "Range step";
  }
  return "Auto deviation";
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function renderLiveSamplesTable(samples) {
  if (samples.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 7;
    cell.textContent = "No samples captured";
    row.appendChild(cell);
    liveSamplesBody.replaceChildren(row);
    return;
  }

  liveSamplesBody.replaceChildren(
    ...[...samples].reverse().map((sample) => {
      const row = document.createElement("tr");
      row.dataset.sequence = String(sample.sequence);
      row.classList.toggle(
        "is-selected",
        sameSequence(sample.sequence, selectedLiveSampleSequence)
      );
      row.appendChild(tableCell(sample.sequence));
      row.appendChild(tableCell(formatLiveTime(sample.timestamp_utc_plus_8)));
      row.appendChild(tableCell(formatLiveValue(sample.value)));
      row.appendChild(tableCell(sample.unit || "--"));
      row.appendChild(tableCell(formatLiveTrigger(sample)));
      row.appendChild(tableCell(sample.status || "--"));

      const detailsCell = document.createElement("td");
      const detailsButton = document.createElement("button");
      detailsButton.type = "button";
      detailsButton.className = "live-detail-button";
      detailsButton.textContent = "Details";
      detailsButton.setAttribute(
        "aria-expanded",
        String(
          liveSampleDetailsVisible &&
          sameSequence(sample.sequence, selectedLiveSampleSequence)
        )
      );
      detailsButton.setAttribute(
        "aria-label",
        `Toggle details for sample ${sample.sequence}`
      );
      detailsButton.addEventListener("click", () => {
        const closing =
          liveSampleDetailsVisible &&
          sameSequence(sample.sequence, selectedLiveSampleSequence);
        liveSampleDetailsVisible = !closing;
        selectedLiveSampleSequence = closing ? null : sample.sequence;
        renderLiveSampleDetails(sample);
        updateLiveSelectedRows();
      });
      detailsCell.appendChild(detailsButton);
      row.appendChild(detailsCell);
      return row;
    })
  );
}

function renderLiveSampleDetails(sample) {
  liveSampleMetadata.classList.toggle(
    "is-hidden",
    !liveSampleDetailsVisible || !sample
  );
  if (!liveSampleDetailsVisible || !sample) {
    liveSelectedSample.textContent = "No sample selected";
    liveSampleDetails.textContent = "";
    return;
  }
  liveSelectedSample.textContent = `Sample #${sample.sequence}`;
  liveSampleDetails.textContent = JSON.stringify(
    {
      sequence: sample.sequence,
      trigger_metadata: sample.trigger_metadata || {},
      measurement_metadata: sample.measurement_metadata || {},
    },
    null,
    2
  );
}

function updateLiveSelectedRows() {
  for (const row of liveSamplesBody.querySelectorAll("tr[data-sequence]")) {
    const selected =
      liveSampleDetailsVisible &&
      sameSequence(row.dataset.sequence, selectedLiveSampleSequence);
    row.classList.toggle("is-selected", selected);
    row.querySelector(".live-detail-button")?.setAttribute(
      "aria-expanded",
      String(selected)
    );
  }
}

function sameSequence(left, right) {
  return String(left) === String(right);
}

function tableCell(value) {
  const cell = document.createElement("td");
  cell.textContent =
    value === null || value === undefined || value === "" ? "--" : String(value);
  return cell;
}

function formatLiveValueWithUnit(value, unit) {
  const scaled = scaleLiveValue(value, unit);
  return [formatLiveValue(scaled.value), scaled.unit || ""].filter(Boolean).join(" ");
}

function formatLiveAxisLabel(value, unit) {
  const scaled = scaleLiveValue(value, unit);
  const formatted = formatLiveAxisNumber(scaled.value);
  return [formatted, scaled.unit || ""].filter(Boolean).join(" ");
}

function scaleLiveValue(value, unit) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return { value, unit };
  }
  const absValue = Math.abs(numeric);
  if (unit === "A") {
    if (absValue > 0 && absValue < 1e-3) {
      return { value: numeric * 1000000, unit: "uA" };
    }
    if (absValue > 0 && absValue < 1) {
      return { value: numeric * 1000, unit: "mA" };
    }
  }
  if (unit === "V") {
    if (absValue > 0 && absValue < 1e-3) {
      return { value: numeric * 1000000, unit: "uV" };
    }
    if (absValue > 0 && absValue < 1) {
      return { value: numeric * 1000, unit: "mV" };
    }
  }
  if (unit === "Ohm") {
    if (absValue >= 1000000) {
      return { value: numeric / 1000000, unit: "MOhm" };
    }
    if (absValue >= 1000) {
      return { value: numeric / 1000, unit: "kOhm" };
    }
  }
  return { value: numeric, unit };
}

function formatLiveValue(value) {
  const numeric = Number(value);
  if (Number.isFinite(numeric)) {
    return numeric.toLocaleString("en-US", { maximumSignificantDigits: 6 });
  }
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  return String(value);
}

function formatLiveAxisNumber(value) {
  const numeric = Number(value);
  if (Number.isFinite(numeric)) {
    return numeric.toLocaleString("en-US", { maximumSignificantDigits: 4 });
  }
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  return String(value);
}

function formatLiveTime(value) {
  const text = String(value || "");
  const [datePart, timePart] = text.split("T");
  if (datePart && timePart) {
    return `${datePart} ${timePart.slice(0, 8)}`;
  }
  return text || "--";
}

function formatLiveTrigger(sample) {
  return sample.trigger_source || "--";
}

function svgElement(tagName, attributes) {
  const element = document.createElementNS(SVG_NS, tagName);
  for (const [name, value] of Object.entries(attributes)) {
    element.setAttribute(name, String(value));
  }
  return element;
}
