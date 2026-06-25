from __future__ import annotations

import re
import unittest

from webui_test_helpers import assert_tag_with_attrs, load_static_ui


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
        self.assertIn('/static/app.js?v=1.4.0-ac-filter', index)
        self.assertNotIn('/static/app.js?v=1.4.0"', index)

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



if __name__ == "__main__":
    unittest.main()
