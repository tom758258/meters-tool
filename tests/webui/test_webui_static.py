from __future__ import annotations

import re
import unittest
from pathlib import Path

from webui_test_helpers import STATIC_DIR, assert_tag_with_attrs, load_static_ui


APP_JS_CACHEBUSTER_TOKEN = "__METERS_TOOL_APP_JS_CACHEBUSTER__"


class WebUiStaticTests(unittest.TestCase):
    def test_static_ui_omits_cli_compat_only_controls(self):
        index, app_js = load_static_ui()

        self.assertNotIn("current_range", index)
        self.assertNotIn("current_range", app_js)
        self.assertNotIn("enable_hw_trigger", index)
        self.assertNotIn("enable_hw_trigger", app_js)

    def test_static_ui_exposes_live_resource_select_and_range_unit(self):
        index, app_js = load_static_ui()

        self.assertIn('id="resource-select"', index)
        self.assertIn("live_only=true", app_js)
        self.assertIn('id="range-unit"', index)
        self.assertIn('id="range-suffix"', index)
        assert_tag_with_attrs(self, index, "select", {"id": "measurement-range"})
        assert_tag_with_attrs(self, index, "select", {"id": "nplc", "name": "nplc"})
        self.assertNotIn('name="measurement_range" form="run-form" type="number"', index)
        self.assertNotIn('name="nplc" form="run-form" type="number"', index)
        self.assertIn("measurement_range", app_js)
        self.assertIn("nplc", app_js)
        assert_tag_with_attrs(
            self,
            index,
            "select",
            {"id": "instrument-model", "name": "instrument_model", "form": "run-form"},
        )
        self.assertIn("instrument_model", app_js)
        self.assertIn("/api/capabilities?model=", app_js)

    def test_static_ui_places_expected_model_in_device_options_panel(self):
        index, app_js = load_static_ui()

        assert_tag_with_attrs(
            self,
            index,
            "button",
            {
                "id": "device-options-toggle",
                "type": "button",
                "title": "Device options",
                "aria-label": "Device options",
                "aria-expanded": "false",
            },
        )
        self.assertIn('aria-controls="device-options-panel"', index)
        self.assertNotIn("Instrument model override", index)

        run_setup = index[
            index.index('<form id="run-form"')
            : index.index('<section class="panel collapsible-panel" data-panel="measurement-options">')
        ]
        self.assertNotIn('id="instrument-model"', run_setup)
        self.assertNotIn("Expected model", run_setup)

        panel = index[
            index.index('id="device-options-panel"')
            : index.index("VISA resource")
        ]
        for expected in [
            "Device options",
            "Expected model",
            "Auto-detect",
            "Require 34460A",
            "Require 34461A",
            (
                "Auto-detect uses the connected instrument IDN. Select a model only "
                "when you want to require a specific one. In live mode, the detected "
                "IDN model remains the runtime driver."
            ),
        ]:
            with self.subTest(expected=expected):
                self.assertIn(expected, panel)

        self.assertIn("setDeviceOptionsExpanded", app_js)
        self.assertIn('event.key === "Escape"', app_js)
        self.assertIn('document.addEventListener("click"', app_js)

    def test_static_ui_displays_validation_scoped_model_support(self):
        index, app_js = load_static_ui()

        for expected in [
            'id="model-support-summary"',
            'id="model-support-status"',
            'id="model-support-open"',
            'id="model-support-limits"',
            'id="model-support-pending"',
            "Model support",
            "Open",
            "Limits",
            "Pending",
        ]:
            with self.subTest(expected=expected):
                self.assertIn(expected, index)

        for expected in [
            "latestSupportSummary = capabilities.support_summary ?? null",
            "refreshSupportSummaryPresentation()",
            "translateSemanticKeyOrFallback",
            "status_key",
            "runtime_driver_note_key",
            "open_workflow_keys",
            "limit_keys",
            "pending_keys",
            "validation_status",
            "transport_scope",
            "backend_scope",
            "open_workflows",
            "is_fallback_capability_view",
            "runtime_driver_note",
            '"support.summary.auto_detect_status"',
            '"support.summary.profile_status"',
            '"support.summary.none"',
            "modelSupportLimits",
            "modelSupportPending",
        ]:
            with self.subTest(expected=expected):
                self.assertIn(expected, app_js)

        self.assertNotIn("/api/capabilities?locale=", app_js)
        self.assertNotIn("locale=", app_js)

    def test_static_ui_device_resource_section_has_collapse_and_summary(self):
        index, app_js = load_static_ui()

        resource_section = index[
            index.index('<section class="resource-row"')
            : index.index('<section class="grid">')
        ]
        assert_tag_with_attrs(
            self,
            resource_section,
            "button",
            {
                "id": "toggle-device-resource",
                "type": "button",
                "aria-controls": "device-resource-body",
                "aria-expanded": "true",
            },
        )
        self.assertIn('id="device-resource-summary"', resource_section)
        self.assertIn('id="device-resource-body"', resource_section)
        self.assertIn('id="resource"', resource_section)
        self.assertIn('id="resource-select"', resource_section)
        self.assertIn('id="refresh-resources"', resource_section)

        resource_actions = resource_section[
            resource_section.index('<div class="resource-row-actions">')
            : resource_section.index('<div id="device-resource-body"')
        ]
        self.assertLess(
            resource_actions.index('id="device-options-toggle"'),
            resource_actions.index('id="toggle-device-resource"'),
        )

        assert_tag_with_attrs(
            self,
            resource_section,
            "button",
            {
                "id": "device-options-toggle",
                "type": "button",
                "title": "Device options",
                "aria-label": "Device options",
                "aria-controls": "device-options-panel",
            },
        )
        assert_tag_with_attrs(
            self,
            resource_section,
            "select",
            {"id": "instrument-model", "name": "instrument_model", "form": "run-form"},
        )

        self.assertIn("setDeviceResourceExpanded", app_js)
        self.assertIn('deviceResourceBody.classList.toggle("is-hidden", !expanded)', app_js)
        self.assertIn('deviceResourceToggleButton.setAttribute("aria-expanded"', app_js)
        self.assertIn("updateDeviceResourceSummary", app_js)
        self.assertIn(
            "scanMetadataByResource.get(resourceSelect.value)?.instrument_model",
            app_js,
        )
        self.assertIn('t("resource.live_model", { model })', app_js)
        self.assertIn('t("resource.live_selected")', app_js)
        self.assertIn('setTranslatedText(deviceResourceSummary, "device.resource_summary", params)', app_js)
        self.assertIn('resourceInput.addEventListener("input", () =>', app_js)
        self.assertIn("updateDeviceResourceSummary();", app_js)
        self.assertIn("updateFeatureAvailability();", app_js)

    def test_static_ui_expected_model_payload_semantics_remain_instrument_model(self):
        index, app_js = load_static_ui()

        for value in ["", "34460A", "34461A"]:
            with self.subTest(value=value):
                assert_tag_with_attrs(self, index, "option", {"value": value})
        self.assertIn("Auto-detect</option>", index)
        self.assertIn("Require 34460A</option>", index)
        self.assertIn("Require 34461A</option>", index)
        self.assertIn(
            'instrument_model: textOrNull(data.get("instrument_model"))',
            app_js,
        )
        self.assertIn(
            'translatedOptionElement("", "device.auto_detect")',
            app_js,
        )
        self.assertIn(
            'translatedOptionElement(profile.model, "device.require_model"',
            app_js,
        )
        run_form_js = (STATIC_DIR / "run_form.js").read_text(encoding="utf-8")
        self.assertNotIn("model_mode:", run_form_js)
        self.assertNotIn("modelMode:", run_form_js)

    def test_static_ui_scan_resource_metadata_reloads_capabilities_without_forcing_model(self):
        _index, app_js = load_static_ui()

        self.assertIn("scanMetadataByResource = new Map", app_js)
        self.assertIn("result.resources.map((item) => [item.resource, item])", app_js)
        self.assertIn("metadata?.instrument_model || null", app_js)
        self.assertIn("const forcedModel = instrumentModelSelect.value || \"\"", app_js)
        self.assertIn("await loadCapabilities(forcedModel || inferredModel)", app_js)
        self.assertIn("instrumentModelSelect.value = forcedModel", app_js)
        self.assertIn(
            "Live resource model could not be inferred; Start will auto-detect it.",
            app_js,
        )

    def test_static_ui_resource_selection_orders_model_reload_before_ui_updates(self):
        _index, app_js = load_static_ui()

        self.assertRegex(
            app_js,
            r"resourceInput\.value = resource;[\s\S]*?"
            r"resourceSelect\.value = resource;[\s\S]*?"
            r"await loadCapabilities\(forcedModel \|\| inferredModel\);[\s\S]*?"
            r"instrumentModelSelect\.value = forcedModel;[\s\S]*?"
            r"updateRangeAndLiveChartScale\(\);[\s\S]*?"
            r"updateTriggerModeUi\(\);[\s\S]*?"
            r"updatePanelSummaries\(\);",
        )

    def test_static_ui_manual_model_change_reloads_capabilities_without_resource_clear(self):
        _index, app_js = load_static_ui()

        self.assertIn(
            "instrumentModelSelect.addEventListener(\"change\", async () =>",
            app_js,
        )
        self.assertIn("await loadCapabilities(instrumentModelSelect.value)", app_js)
        manual_handler = re.search(
            r"instrumentModelSelect\.addEventListener\(\"change\", async \(\) => \{"
            r"([\s\S]*?)\n\}\);",
            app_js,
        )
        self.assertIsNotNone(manual_handler)
        self.assertNotIn("resourceInput.value", manual_handler.group(1))
        self.assertNotIn("resourceSelect.value", manual_handler.group(1))

    def test_static_ui_unsupported_34460a_options_remain_capabilities_driven(self):
        _index, app_js = load_static_ui()

        self.assertIn("supportedTriggerModes = [...capabilities.trigger_modes]", app_js)
        self.assertIn("supportsCurrentTerminal(measurement)", app_js)
        self.assertNotIn("instrumentModelSelect.value === \"34460A\"", app_js)
        self.assertNotIn("selectedModel === \"34460A\"", app_js)

    def test_static_ui_disables_product_unavailable_feature_options_from_metadata(self):
        _index, app_js = load_static_ui()

        for expected in [
            'capabilities.support?.["start-trigger-record"]?.live',
            'scope.features?.[featureKind]?.[featureValue]',
            'validationStatus === "feature_pending"',
            'validationStatus === "not_supported_by_model"',
            "option.disabled = !availability.available",
            '"support.reason.pending_live_validation"',
            '"support.reason.not_supported_by_model"',
            '"support.reason.scope_unavailable"',
            'scope.backend_scope === "system_visa"',
        ]:
            with self.subTest(expected=expected):
                self.assertIn(expected, app_js)

        self.assertNotIn("validation_allow_pending_live_support", app_js)
        self.assertNotIn("--validation-allow-pending-live-support", app_js)

    def test_static_ui_uses_requested_layout_sections(self):
        index, app_js = load_static_ui()

        self.assertIn('id="resource"', index)
        self.assertIn('id="resource-select"', index)
        self.assertIn('id="select-csv-folder"', index)
        assert_tag_with_attrs(self, index, "input", {"id": "csv-path-input", "name": "csv"})
        self.assertIn('id="live-trend-chart"', index)
        self.assertIn('id="live-samples-body"', index)
        self.assertIn('id="live-sample-details"', index)
        self.assertIn('id="open-csv"', index)
        self.assertIn('"/api/runs/current/open-csv"', app_js)
        self.assertIn('"/api/csv/select-folder"', app_js)
        self.assertIn("csv_path", app_js)

    def test_static_ui_exposes_live_data_panel(self):
        index, app_js = load_static_ui()

        for expected in [
            'id="live-data-summary"',
            'id="status-state"',
            'id="status-captured"',
            'id="status-errors"',
            'id="live-latest-value"',
            'id="live-latest-time"',
            'id="live-latest-trigger"',
            'id="live-stat-min"',
            'id="live-stat-average"',
            'id="live-stat-max"',
            'id="live-stat-span"',
            'id="live-stat-std-dev"',
            'id="live-stat-sample"',
            'id="toggle-live-stats"',
            'id="live-stats-grid"',
            'id="toggle-live-chart"',
            'id="live-chart-content"',
            'id="live-chart-scale-mode"',
            'id="live-chart-manual-span"',
            'id="live-chart-scale-info"',
            'id="live-chart-shell"',
            'id="live-trend-chart"',
            'id="live-chart-empty"',
            'id="toggle-live-samples"',
            'id="live-table-wrap"',
            'id="live-samples-body"',
            'id="live-sample-metadata"',
            'id="live-selected-sample"',
            'id="live-sample-details"',
            'id="close-live-sample-details"',
        ]:
            with self.subTest(expected=expected):
                self.assertIn(expected, index)

        for expected in [
            "run_id",
            "recent_samples",
            "latest_sample",
            "sample_capacity",
        ]:
            with self.subTest(expected=expected):
                self.assertIn(expected, app_js)

    def test_static_ui_live_chart_scale_controls_are_in_trend_section(self):
        index, app_js = load_static_ui()

        trend_section = re.search(
            r"<div class=\"live-collapse-section\">[\s\S]*?<span[^>]*>Trend</span>"
            r"[\s\S]*?</div>\s*</div>\s*"
            r"<div class=\"live-collapse-section\">[\s\S]*?<span[^>]*>Statistics</span>",
            index,
        )
        self.assertIsNotNone(trend_section)
        trend_html = trend_section.group(0)

        assert_tag_with_attrs(
            self,
            trend_html,
            "button",
            {"id": "toggle-live-chart", "aria-controls": "live-chart-content"},
        )
        self.assertRegex(
            trend_html,
            r"<div\b(?=[^>]*\bid=\"live-chart-content\")"
            r"(?=[^>]*\bclass=\"live-chart-content\")[^>]*>"
            r"[\s\S]*?<div class=\"live-chart-controls\">"
            r"[\s\S]*?id=\"live-chart-scale-info\""
            r"[\s\S]*?id=\"live-chart-shell\"",
        )
        self.assertLess(
            trend_html.index('id="live-chart-scale-mode"'),
            trend_html.index('id="live-chart-shell"'),
        )
        self.assertLess(
            trend_html.index('id="live-chart-manual-span"'),
            trend_html.index('id="live-chart-shell"'),
        )
        self.assertLess(
            trend_html.index('id="live-chart-scale-info"'),
            trend_html.index('id="live-chart-shell"'),
        )
        self.assertIn('id="live-trend-chart"', trend_html)
        self.assertIn("export const liveChartContent", app_js)

        chart_toggle = re.search(
            r"toggleLiveChartButton\.addEventListener\(\"click\", \(\) => \{"
            r"([\s\S]*?)\n  \}\);",
            app_js,
        )
        self.assertIsNotNone(chart_toggle)
        self.assertIn("liveChartContent", chart_toggle.group(1))
        self.assertNotIn("liveChartShell", chart_toggle.group(1))
        self.assertIn(
            "setLiveSectionVisible(toggleLiveChartButton, liveChartContent, true)",
            app_js,
        )

    def test_static_ui_live_chart_scale_defaults_and_form_boundary(self):
        index, app_js = load_static_ui()

        self.assertRegex(
            index,
            r"<option\b(?=[^>]*\bvalue=\"auto-deviation\")(?=[^>]*\bselected\b)[^>]*>",
        )
        assert_tag_with_attrs(
            self,
            index,
            "label",
            {
                "id": "live-chart-manual-span-field",
                "class": "is-hidden",
                "aria-hidden": "true",
            },
        )
        self.assertRegex(
            index,
            r"<input\b(?=[^>]*\bid=\"live-chart-manual-span\")"
            r"(?=[^>]*\btype=\"number\")(?=[^>]*\bdisabled\b)[^>]*>",
        )

        manual_span_tag = re.search(r"<input\b[^>]*id=\"live-chart-manual-span\"[^>]*>", index)
        self.assertIsNotNone(manual_span_tag)
        self.assertNotIn("name=", manual_span_tag.group(0))
        self.assertNotIn("form=", manual_span_tag.group(0))

        self.assertIn('liveChartScaleMode = "auto-deviation"', app_js)
        self.assertIn(
            'liveChartScaleMode = liveChartScaleModeSelect.value || "auto-deviation"',
            app_js,
        )
        self.assertIn('liveChartScaleMode === "manual-span"', app_js)
        self.assertIn(
            'liveChartManualSpanField.setAttribute("aria-hidden", String(!manual))',
            app_js,
        )
        self.assertIn("liveChartManualSpanInput.disabled = !manual", app_js)
        self.assertIn("window.__KEYSIGHT_LIVE_DATA_SCALE_MODES__ = true", app_js)

        scale_change = re.search(
            r"liveChartScaleModeSelect\.addEventListener\(\"change\", \(\) => \{"
            r"([\s\S]*?)\n  \}\);",
            app_js,
        )
        self.assertIsNotNone(scale_change)
        self.assertIn(
            'liveChartScaleMode = liveChartScaleModeSelect.value || "auto-deviation"',
            scale_change.group(1),
        )
        self.assertIn("updateLiveChartScaleControls();", scale_change.group(1))
        self.assertIn("renderLiveChart(lastLiveChartSamples);", scale_change.group(1))

        form_payload = re.search(r"export function formPayload\(\) \{([\s\S]*?)\n\}", app_js)
        self.assertIsNotNone(form_payload)
        self.assertNotIn("live-chart-scale-mode", form_payload.group(1))
        self.assertNotIn("live-chart-manual-span", form_payload.group(1))
        self.assertNotIn("liveChartScaleMode", form_payload.group(1))
        self.assertNotIn("liveChartManualSpan", form_payload.group(1))

    def test_static_ui_live_chart_scale_keeps_existing_layout_contracts(self):
        index, app_js = load_static_ui()
        styles = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")

        self.assertNotIn("<dialog", index)
        self.assertNotIn('role="dialog"', index)
        self.assertNotIn('class="modal', index)
        self.assertIn('id="start-run"', index)
        self.assertIn('id="trigger-run"', index)
        self.assertIn('id="stop-run"', index)
        self.assertIn('id="open-csv"', index)
        self.assertIn('"/api/runs"', app_js)
        self.assertIn('"/api/runs/current/command"', app_js)
        self.assertIn('"/api/runs/current/stop"', app_js)
        self.assertIn('"/api/runs/current/open-csv"', app_js)
        self.assertIn('id="live-stats-grid"', index)
        self.assertIn('id="live-table-wrap"', index)
        self.assertIn("Manual span requires a positive value", app_js)
        self.assertIn("Auto deviation: Center", app_js)
        self.assertIn("Auto absolute: Range", app_js)
        self.assertIn("Manual span: Center", app_js)
        self.assertIn("Range step: Center", app_js)
        self.assertIn("Range step disabled because Auto range is on.", app_js)
        self.assertIn(
            "Range step requires Auto range off and a selected manual Range.",
            app_js,
        )
        self.assertIn(".live-chart-axis-label", styles)
        self.assertIn("fill: var(--muted);", styles)

    def test_static_ui_live_chart_y_axis_labels_use_active_scale(self):
        index, app_js = load_static_ui()

        self.assertIn('id="live-trend-chart"', index)
        self.assertIn('viewBox="0 0 640 760"', index)
        self.assertIn(
            "const width = Math.max(Math.round(liveTrendChart.clientWidth || 0), 640)",
            app_js,
        )
        self.assertIn(
            "const height = Math.max(Math.round(liveTrendChart.clientHeight || 0), 760)",
            app_js,
        )
        self.assertIn(
            'liveTrendChart.setAttribute("viewBox", `0 0 ${width} ${height}`)',
            app_js,
        )
        self.assertIn("const leftPadding = 120", app_js)
        self.assertNotIn("const leftPadding = 72", app_js)
        self.assertIn("const rightPadding = 18", app_js)
        self.assertIn("const plotLeft = leftPadding", app_js)
        self.assertIn("const plotRight = width - rightPadding", app_js)
        self.assertIn("x1: plotLeft", app_js)
        self.assertIn("x2: plotRight", app_js)
        self.assertNotIn("x1: 18", app_js)
        self.assertIn('svgElement("text"', app_js)
        self.assertIn("x: plotLeft - 10", app_js)
        self.assertIn('class: "live-chart-axis-label"', app_js)
        self.assertIn("const valueAtGrid = scale.center - offset * scale.gridStepValue", app_js)
        self.assertIn("label.textContent = formatLiveAxisLabel(valueAtGrid, unit)", app_js)
        self.assertIn("function formatLiveAxisLabel(value, unit)", app_js)
        self.assertIn("const scaled = scaleLiveValue(value, unit)", app_js)
        self.assertIn("function formatLiveAxisNumber(value)", app_js)
        self.assertIn("maximumSignificantDigits: 4", app_js)
        self.assertNotIn("live-chart-axis-label", index)

    def test_static_ui_live_chart_range_step_mode_is_guarded(self):
        index, app_js = load_static_ui()
        styles = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
        controls_styles = re.search(
            r"\.live-chart-controls\s*\{([\s\S]*?)\n\}",
            styles,
        )
        self.assertIsNotNone(controls_styles)
        controls_css = controls_styles.group(1)

        self.assertRegex(
            index,
            r"<option\b(?=[^>]*\bvalue=\"range-step\")(?=[^>]*\bdisabled\b)[^>]*>"
            r"Range step</option>",
        )
        self.assertIn('option[value="range-step"]', app_js)
        self.assertIn("rangeStepOption.disabled = !rangeStepAvailable", app_js)
        self.assertIn("!autoRangeCheckbox.checked", app_js)
        self.assertIn("hasMeasurementRangeOptions()", app_js)
        self.assertIn("selectedManualRange()", app_js)
        self.assertIn('liveChartScaleMode !== "range-step"', app_js)
        self.assertIn('liveChartScaleMode = "auto-deviation"', app_js)
        self.assertIn('liveChartScaleModeSelect.value = "auto-deviation"', app_js)
        self.assertIn("chartScaleForRangeStep(baseline, rangeStepSpan)", app_js)
        self.assertIn('id="live-chart-scale-mode-help"', index)
        assert_tag_with_attrs(
            self,
            index,
            "span",
            {"id": "live-chart-scale-mode-help", "class": "field-help is-hidden"},
        )
        self.assertIn("export const liveChartScaleModeHelp", app_js)
        self.assertIn("liveChartScaleModeHelp", app_js)
        self.assertIn("setTranslatedText(liveChartScaleModeHelp, rangeStepUnavailableKey())", app_js)
        self.assertIn('return "live_data.range_step_requires_manual_range";', app_js)
        self.assertIn(
            'liveChartScaleModeHelp.classList.toggle("is-hidden", rangeStepAvailable)',
            app_js,
        )
        self.assertIn(
            "grid-template-columns: minmax(260px, 320px) minmax(120px, 160px)",
            controls_css,
        )
        self.assertIn("align-items: start", controls_css)
        self.assertNotIn("minmax(160px, 220px)", controls_css)
        self.assertNotIn("align-items: end", controls_css)
        self.assertIn(
            "gridStepValue: span / LIVE_CHART_GRID_LINE_COUNT_PER_SIDE",
            app_js,
        )
        self.assertIn(
            "refreshLiveChartScaleAvailability(\"\")",
            app_js,
        )
        self.assertIn("updateRangeAndLiveChartScale(", app_js)
        self.assertIn(
            'autoRangeCheckbox.checked\n'
            '      ? "live_data.range_step_auto_range"\n'
            '      : ""',
            app_js,
        )

        range_change = re.search(
            r"measurementRangeInput\.addEventListener\(\"change\", \(\) => \{"
            r"([\s\S]*?)\n\}\);",
            app_js,
        )
        self.assertIsNotNone(range_change)
        self.assertIn("refreshLiveChartScaleAvailability(\"\");", range_change.group(1))

        form_payload = re.search(r"export function formPayload\(\) \{([\s\S]*?)\n\}", app_js)
        self.assertIsNotNone(form_payload)
        self.assertNotIn("range-step", form_payload.group(1))
        self.assertNotIn("liveChartScaleMode", form_payload.group(1))

    def test_static_ui_exposes_cli_limit_constraints(self):
        index, app_js = load_static_ui()

        for attrs in [
            {"name": "timeout_ms", "type": "number", "min": "100", "max": "600000"},
            {"name": "trigger_timeout_ms", "type": "number", "min": "500", "max": "600000"},
            {"name": "max_samples", "type": "number", "min": "1", "max": "1000000"},
            {"name": "trigger_count", "type": "number", "min": "1", "max": "1000000"},
            {"name": "sample_count", "type": "number", "min": "1", "max": "1000000"},
            {"name": "buffer_drain_size", "type": "number", "min": "1", "max": "10000"},
            {"name": "hw_trigger_delay_s", "type": "number", "min": "0", "max": "3600"},
            {"name": "timer_interval_s", "type": "number", "min": "0.5", "max": "86400"},
        ]:
            with self.subTest(attrs=attrs):
                assert_tag_with_attrs(self, index, "input", attrs)
        self.assertIn("limits", app_js)
        self.assertIn("sw_min_interval_ms", app_js)

    def test_static_ui_status_log_and_details_toggle(self):
        index, app_js = load_static_ui()

        self.assertIn('id="latest-status"', index)
        self.assertIn('role="log"', index)
        self.assertIn('id="toggle-status-details"', index)
        self.assertIn('aria-controls="status-details"', index)
        self.assertIn('aria-expanded="false"', index)
        self.assertIn('id="status-details"', index)
        self.assertIn('id="fatal-error"', index)
        self.assertIn('id="cleanup-status"', index)
        self.assertIn('id="raw-status"', index)
        self.assertIn("status", app_js)

    def test_static_ui_guards_run_controls_while_status_active(self):
        index, app_js = load_static_ui()

        for expected in [
            'id="refresh-resources"',
            'id="start-run"',
            'id="trigger-run"',
            'id="stop-run"',
            'id="open-csv"',
        ]:
            with self.subTest(expected=expected):
                self.assertIn(expected, index)

        self.assertIn("export const refreshResourcesButton", app_js)
        self.assertIn("export const startRunButton", app_js)
        self.assertIn("export const stopRunButton", app_js)
        self.assertIn("stopRunButton.addEventListener(\"click\"", app_js)
        self.assertNotIn(
            'document.querySelector("#stop-run").addEventListener',
            app_js,
        )
        self.assertIn("let latestRenderedStatus = null", app_js)
        self.assertIn("latestRenderedStatus = status || null", app_js)
        self.assertIn("export function isRunActive()", app_js)
        self.assertIn("startRunButton.disabled = active", app_js)
        self.assertIn("refreshResourcesButton.disabled = active", app_js)
        self.assertRegex(
            app_js,
            r"if \(active\) \{\s+stopRunButton\.disabled = false;\s+\}",
        )

        scan_handler = app_js[
            app_js.index("refreshResourcesButton.addEventListener")
            : app_js.index("resourceSelect.addEventListener")
        ]
        self.assertIn("if (isRunActive())", scan_handler)
        self.assertIn('appendTranslatedStatusLog("status.active_run_scan_blocked")', scan_handler)
        self.assertLess(scan_handler.index("if (isRunActive())"), scan_handler.index("refreshResources()"))

        start_handler = app_js[
            app_js.index("startRunButton.addEventListener")
            : app_js.index("triggerRunButton.addEventListener")
        ]
        self.assertIn("if (isRunActive())", start_handler)
        self.assertIn(
            'appendTranslatedStatusLog("status.active_run_start_blocked")',
            start_handler,
        )
        self.assertLess(start_handler.index("if (isRunActive())"), start_handler.index('api("/api/runs"'))

        form_payload = re.search(r"export function formPayload\(\) \{([\s\S]*?)\n\}", app_js)
        self.assertIsNotNone(form_payload)
        self.assertNotIn("isRunActive", form_payload.group(1))
        self.assertNotIn("latestRenderedStatus", form_payload.group(1))

    def test_static_ui_warns_before_unload_only_for_active_run(self):
        _index, app_js = load_static_ui()

        self.assertIn('t("status.active_run_unload_warning")', app_js)
        self.assertIn(
            'window.addEventListener("beforeunload", warnBeforeUnloadIfActive)',
            app_js,
        )
        beforeunload_handler = re.search(
            r"function warnBeforeUnloadIfActive\(event\) \{([\s\S]*?)\n\}",
            app_js,
        )
        self.assertIsNotNone(beforeunload_handler)
        handler_body = beforeunload_handler.group(1)
        self.assertIn("if (!isRunActive())", handler_body)
        self.assertIn("return undefined", handler_body)
        self.assertIn("event.preventDefault()", handler_body)
        self.assertIn("event.returnValue = message", handler_body)

    def test_static_ui_marks_blankable_inputs_optional(self):
        index, _app_js = load_static_ui()

        optional_fields = [
            "csv",
            "timeout_ms",
            "trigger_timeout_ms",
            "max_samples",
            "buffer_drain_size",
            "ac_bandwidth_hz",
            "current_terminal",
            "hw_trigger_delay_s",
            "sw_min_interval_ms",
            "sw_queue_max",
        ]
        for name in optional_fields:
            with self.subTest(name=name):
                marker_before_name = re.search(
                    rf"optional-mark[\s\S]{{0,400}}name=\"{re.escape(name)}\"",
                    index,
                )
                marker_after_name = re.search(
                    rf"name=\"{re.escape(name)}\"[\s\S]{{0,400}}optional-mark",
                    index,
                )
                self.assertTrue(marker_before_name or marker_after_name)

    def test_static_ui_scopes_trigger_options_by_mode(self):
        index, app_js = load_static_ui()

        self.assertIn('data-mode-scope="simple"', index)
        self.assertIn('data-mode-scope="software"', index)
        self.assertIn('data-mode-scope="custom"', index)
        self.assertIn('data-mode-scope="hardware"', index)
        self.assertIn('data-mode-scope="software-trigger"', index)
        self.assertIn('data-mode-scope="trigger-timeout"', index)
        self.assertIn("trigger_count", app_js)
        self.assertIn("sample_count", app_js)

    def test_static_ui_preserves_hidden_trigger_timeout_payload_contract(self):
        _index, app_js = load_static_ui()

        self.assertIn("external", app_js)
        self.assertIn("external-custom", app_js)
        self.assertIn("trigger_timeout_ms", app_js)

    def test_static_ui_scopes_dcv_input_and_trigger_button(self):
        index, app_js = load_static_ui()

        self.assertIn('data-measurement-scope="voltage-dc,voltage-dc-ratio"', index)
        self.assertIn("software-custom", app_js)
        self.assertIn("software", app_js)
        self.assertIn("timerActive", app_js)
        self.assertIn("timer_interval_s", app_js)

    def test_static_ui_exposes_software_queue_and_trigger_metadata(self):
        index, app_js = load_static_ui()

        self.assertIn('id="sw-queue-max-container"', index)
        self.assertIn('name="sw_queue_max"', index)
        self.assertIn('id="trigger-metadata-container"', index)
        self.assertIn('id="trigger-metadata"', index)
        self.assertIn("payload.sw_queue_max", app_js)
        self.assertIn("trigger_metadata", app_js)

    def test_static_ui_auto_zero_select_and_new_dropdowns(self):
        index, app_js = load_static_ui()

        self.assertIn('name="auto_zero"', index)
        self.assertNotIn('<input name="auto_zero" form="run-form" type="checkbox"', index)

        self.assertIn('id="ac-bandwidth-container"', index)
        self.assertIn('id="ac-bandwidth"', index)
        self.assertIn('id="gate-time-container"', index)
        self.assertIn('id="gate-time"', index)
        self.assertIn('id="freq-period-timeout-container"', index)
        self.assertIn('id="freq-period-timeout"', index)
        self.assertIn('id="current-terminal-container"', index)
        self.assertIn('id="current-terminal"', index)
        self.assertIn(
            f'/static/app.js?v={APP_JS_CACHEBUSTER_TOKEN}',
            index,
        )
        self.assertRegex(
            index,
            rf'<script[\s\S]*?type="module"[\s\S]*?'
            rf'src="/static/app\.js\?v={APP_JS_CACHEBUSTER_TOKEN}"',
        )
        self.assertNotIn("1.4.0-ac-filter", index)

        self.assertIn("auto_zero", app_js)
        self.assertIn("ac_bandwidth_hz", app_js)
        self.assertIn("gate_time_s", app_js)
        self.assertIn("freq_period_timeout", app_js)
        self.assertIn("current_terminal", app_js)
        self.assertIn("payload.ac_bandwidth_hz", app_js)
        self.assertIn("payload.gate_time_s", app_js)
        self.assertIn("payload.freq_period_timeout", app_js)
        self.assertIn("payload.current_terminal", app_js)
        self.assertIn("AC Filter >", app_js)
        self.assertIn(
            'translatedOptionElement("", "measurement.keep_current_setting")',
            app_js,
        )
        self.assertNotIn("Auto (Default)", app_js)
        self.assertIn(
            "if (defaultAcBandwidth === null || defaultAcBandwidth === undefined)",
            app_js,
        )

        self.assertRegex(index, r'<select[^>]*id="gate-time"[^>]*disabled[^>]*>')
        self.assertRegex(
            index,
            r'<select[^>]*id="freq-period-timeout"[^>]*disabled[^>]*>',
        )

    def test_static_js_contains_sse_init_and_handlers(self):
        _index, app_js = load_static_ui()

        self.assertIn('EventSource("/api/runs/current/events")', app_js)
        self.assertIn('sseSource.addEventListener("run-status"', app_js)
        self.assertIn('typeof EventSource === "undefined"', app_js)
        self.assertIn('api("/api/runs/current")', app_js)
        self.assertNotIn("\nwindow.setInterval(pollStatus, 1000)", app_js)

    def test_static_js_module_imports_are_local_and_exist(self):
        import_pattern = re.compile(r'from\s+"([^"]+)"')
        named_import_pattern = re.compile(
            r'import\s+\{([\s\S]*?)\}\s+from\s+"([^"]+)"'
        )
        export_pattern = re.compile(
            r"export\s+(?:async\s+)?(?:const|function|class)\s+([A-Za-z_$][\w$]*)"
        )
        imports = []

        for path in sorted(STATIC_DIR.glob("*.js")):
            source = path.read_text(encoding="utf-8")
            for target in import_pattern.findall(source):
                imports.append((path, target))

        self.assertTrue(imports)
        for source_path, target in imports:
            with self.subTest(source=source_path.name, target=target):
                self.assertTrue(target.startswith("./"))
                self.assertTrue(target.endswith(".js"))
                imported_path = (source_path.parent / Path(target)).resolve()
                self.assertEqual(STATIC_DIR.resolve(), imported_path.parent)
                self.assertTrue(imported_path.is_file())

        for source_path in sorted(STATIC_DIR.glob("*.js")):
            source = source_path.read_text(encoding="utf-8")
            for raw_names, target in named_import_pattern.findall(source):
                imported_path = (source_path.parent / Path(target)).resolve()
                exported_names = set(
                    export_pattern.findall(imported_path.read_text(encoding="utf-8"))
                )
                for raw_name in raw_names.split(","):
                    imported_name = raw_name.strip().split(" as ", 1)[0]
                    if not imported_name:
                        continue
                    with self.subTest(
                        source=source_path.name,
                        target=target,
                        imported_name=imported_name,
                    ):
                        self.assertIn(imported_name, exported_names)

    def test_static_i18n_applies_once_before_existing_initialization(self):
        app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

        self.assertIn(
            'import { applyStaticTranslations } from "./dom_i18n.js";',
            app_js,
        )
        self.assertEqual(app_js.count("applyStaticTranslations(document);"), 1)
        apply_index = app_js.index("applyStaticTranslations(document);")
        self.assertLess(apply_index, app_js.index("initializeStatusUi();"))
        self.assertLess(apply_index, app_js.index("initializeLiveDataUi();"))
        self.assertLess(apply_index, app_js.index("loadCapabilities()"))

        for forbidden in [
            "setLocale(",
            "navigator.language",
            "navigator.languages",
            "localStorage",
            "LOCALE_STORAGE_KEY",
            "language-button",
        ]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, app_js)

        for migrated_key in [
            "resource.scanning",
            "resource.scan_result_count",
            "live_data.range_step_auto_range",
            "validation.check_run_settings",
        ]:
            with self.subTest(migrated_key=migrated_key):
                self.assertIn(f'"{migrated_key}"', app_js)

        for migrated_literal in [
            "Scanning live resources...",
            "Live resources found:",
            "Range step disabled because Auto range is on.",
            "Check highlighted run settings before Start",
        ]:
            with self.subTest(migrated_literal=migrated_literal):
                self.assertNotIn(migrated_literal, app_js)

    def test_p24_status_and_live_data_keep_raw_machine_contracts(self):
        app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        status_js = (STATIC_DIR / "status.js").read_text(encoding="utf-8")
        live_data_js = (STATIC_DIR / "live_data.js").read_text(encoding="utf-8")
        presentation_js = (STATIC_DIR / "presentation_i18n.js").read_text(
            encoding="utf-8"
        )

        for raw_status in (
            "waiting trigger",
            "waiting software custom trigger",
            "software trigger queued",
            "idle",
        ):
            self.assertIn(f'"{raw_status}"', status_js)
        self.assertIn("const normalized = normalizeStatusValue(message)", status_js)
        self.assertIn("shouldSuppressApiStatusLog(normalized, status)", status_js)
        self.assertIn("`${runId}:${normalized}`", status_js)
        self.assertIn('identity: `api:${normalized}`', status_js)
        self.assertIn('normalized === "software trigger queued"', status_js)
        self.assertIn('normalized === "idle"', status_js)
        self.assertIn('status.latest_status === "software trigger queued"', app_js)

        self.assertIn("fatalError.textContent = status.fatal_error", status_js)
        self.assertIn("cleanupStatus.textContent = status.cleanup_status", status_js)
        self.assertIn("rawStatus.textContent = JSON.stringify(status, null, 2)", status_js)
        self.assertIn("tableCell(sample.status || \"--\")", live_data_js)
        self.assertIn("return sample.trigger_source || \"--\"", live_data_js)
        self.assertIn("trigger_metadata: sample.trigger_metadata || {}", live_data_js)
        self.assertIn("measurement_metadata: sample.measurement_metadata || {}", live_data_js)
        self.assertIn("setRawText(liveSampleDetails, JSON.stringify(", live_data_js)

        self.assertIn("element.removeAttribute(\"data-i18n\")", live_data_js)
        self.assertIn("element.removeAttribute(\"data-i18n-params\")", live_data_js)
        self.assertIn("clearTranslationBinding(element)", status_js)
        self.assertIn(": rawPresentation(value)", presentation_js)
        self.assertNotIn("includes(text)", presentation_js)

        production_sources = "\n".join(
            (STATIC_DIR / name).read_text(encoding="utf-8")
            for name in (
                "app.js",
                "status.js",
                "live_data.js",
                "presentation_i18n.js",
            )
        )
        for forbidden in (
            "setLocale(",
            "navigator.language",
            "navigator.languages",
            "localStorage",
            "status_key",
            "runtime_driver_note_key",
            "open_workflow_keys",
            "limit_keys",
            "pending_keys",
        ):
            self.assertNotIn(forbidden, production_sources)



if __name__ == "__main__":
    unittest.main()
