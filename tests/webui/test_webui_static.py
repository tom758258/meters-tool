from __future__ import annotations

import re
import unittest
from pathlib import Path

from webui_test_helpers import STATIC_DIR, assert_tag_with_attrs, load_static_ui


APP_JS_CACHEBUSTER_TOKEN = "__KEYSIGHT_LOGGER_APP_JS_CACHEBUSTER__"


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
        self.assertIn('id="instrument-model"', index)
        self.assertIn('name="instrument_model"', index)
        self.assertIn("instrument_model", app_js)
        self.assertIn("/api/capabilities?model=", app_js)

    def test_static_ui_scan_resource_metadata_drives_model_selection(self):
        _index, app_js = load_static_ui()

        self.assertIn("scanMetadataByResource = new Map", app_js)
        self.assertIn("result.resources.map((item) => [item.resource, item])", app_js)
        self.assertIn("metadata?.instrument_model || null", app_js)
        self.assertIn("instrumentModelSelect.value = inferredModel", app_js)
        self.assertIn("await loadCapabilities(inferredModel)", app_js)
        self.assertIn(
            "Live resource model could not be inferred; select Instrument model manually.",
            app_js,
        )

    def test_static_ui_resource_selection_orders_model_reload_before_ui_updates(self):
        _index, app_js = load_static_ui()

        self.assertRegex(
            app_js,
            r"resourceInput\.value = resource;[\s\S]*?"
            r"resourceSelect\.value = resource;[\s\S]*?"
            r"instrumentModelSelect\.value = inferredModel;[\s\S]*?"
            r"await loadCapabilities\(inferredModel\);[\s\S]*?"
            r"updateRangeVisibility\(\);[\s\S]*?"
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

        self.assertIn("capabilities.trigger_modes.map", app_js)
        self.assertIn("supportsCurrentTerminal(measurement)", app_js)
        self.assertNotIn("instrumentModelSelect.value === \"34460A\"", app_js)
        self.assertNotIn("selectedModel === \"34460A\"", app_js)

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
                    rf"optional-mark[\s\S]{{0,240}}name=\"{re.escape(name)}\"",
                    index,
                )
                marker_after_name = re.search(
                    rf"name=\"{re.escape(name)}\"[\s\S]{{0,240}}optional-mark",
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
        self.assertIn('optionElement("", "Keep current setting")', app_js)
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



if __name__ == "__main__":
    unittest.main()
