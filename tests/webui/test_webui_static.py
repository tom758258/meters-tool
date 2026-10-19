from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

from webui_test_helpers import STATIC_DIR, assert_tag_with_attrs, load_static_ui


APP_JS_CACHEBUSTER_TOKEN = "__METERS_TOOL_APP_JS_CACHEBUSTER__"


class _HtmlTreeParser(HTMLParser):
    _VOID_ELEMENTS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
    }

    def __init__(self):
        super().__init__()
        self.root = {"tag": None, "attrs": {}, "children": []}
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "children": []}
        self.stack[-1]["children"].append(node)
        if tag not in self._VOID_ELEMENTS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self._VOID_ELEMENTS:
            self.stack.pop()

    def handle_endtag(self, tag):
        if len(self.stack) > 1 and self.stack[-1]["tag"] == tag:
            self.stack.pop()

    def find_by_id(self, element_id):
        pending = [self.root]
        while pending:
            node = pending.pop()
            if node["attrs"].get("id") == element_id:
                return node
            pending.extend(reversed(node["children"]))
        return None

    @staticmethod
    def descendants(node):
        pending = list(node["children"])
        while pending:
            child = pending.pop(0)
            yield child
            pending[0:0] = child["children"]


class WebUiStaticTests(unittest.TestCase):
    def test_static_ui_exposes_non_persistent_execution_modes_and_plan_result(self):
        index, app_js = load_static_ui()
        payload_js = (STATIC_DIR / "run_form_payload.js").read_text(encoding="utf-8")

        for value in ("real", "simulate", "dry-run"):
            self.assertRegex(
                index,
                rf'<input\b(?=[^>]*\bname="execution-mode")(?=[^>]*\bvalue="{value}")[^>]*>',
            )
        self.assertRegex(
            index,
            r'<input\b(?=[^>]*\bname="execution-mode")(?=[^>]*\bvalue="real")'
            r'(?=[^>]*\bchecked\b)[^>]*>',
        )
        self.assertIn('id="execution-model-label"', index)
        self.assertIn('id="dry-run-plan"', index)
        self.assertIn('"/api/plan"', payload_js)
        self.assertNotIn("execution-mode.locale", app_js)
        self.assertNotIn("execution-mode.storage", app_js)

        styles_css = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
        self.assertIn('.execution-mode-options input[type="radio"]', styles_css)
        self.assertIn("min-height: 0;", styles_css)
        self.assertIn("padding: 0;", styles_css)
        self.assertIn("box-shadow: none;", styles_css)
        self.assertIn("white-space: nowrap;", styles_css)

    def test_static_ui_omits_cli_compat_only_controls(self):
        index, _ = load_static_ui()
        javascript_sources = {
            path.name: path.read_text(encoding="utf-8")
            for path in sorted(STATIC_DIR.glob("*.js"))
        }

        for token in ("current_range", "enable_hw_trigger"):
            self.assertNotIn(token, index)
            for filename, source in javascript_sources.items():
                self.assertNotIn(token, source, f"{token!r} found in {filename}")

    def test_static_ui_exposes_live_resource_select_and_range_unit(self):
        index, app_js = load_static_ui()
        run_form_js = (STATIC_DIR / "run_form.js").read_text(encoding="utf-8")
        payload_js = (STATIC_DIR / "run_form_payload.js").read_text(encoding="utf-8")

        self.assertIn('id="resource-select"', index)
        self.assertIn("live_only=true", app_js)
        self.assertIn('id="range-unit"', index)
        self.assertIn('id="range-suffix"', index)
        assert_tag_with_attrs(self, index, "select", {"id": "measurement-range"})
        assert_tag_with_attrs(self, index, "select", {"id": "nplc", "name": "nplc"})
        self.assertNotIn('name="measurement_range" form="run-form" type="number"', index)
        self.assertNotIn('name="nplc" form="run-form" type="number"', index)
        self.assertIn("measurement_range", payload_js)
        self.assertIn("nplc", payload_js)
        assert_tag_with_attrs(
            self,
            index,
            "select",
            {"id": "instrument-model", "name": "instrument_model", "form": "run-form"},
        )
        self.assertIn("instrument_model", payload_js)
        self.assertIn("/api/capabilities?model=", run_form_js)

    def test_static_ui_exposes_expected_model_device_options_contract(self):
        index, _app_js = load_static_ui()

        assert_tag_with_attrs(
            self,
            index,
            "button",
            {
                "id": "device-options-toggle",
                "type": "button",
                "data-i18n-title": "accessibility.device_options",
                "data-i18n-aria-label": "accessibility.device_options",
                "aria-controls": "device-options-panel",
                "aria-expanded": "false",
            },
        )
        self.assertIn('id="device-options-panel"', index)
        self.assertIn('data-i18n="device.expected_model"', index)
        self.assertIn('data-i18n="device.expected_model_help"', index)

    def test_static_ui_exposes_supported_device_list(self):
        index, app_js = load_static_ui()

        assert_tag_with_attrs(
            self,
            index,
            "button",
            {
                "id": "supported-devices-toggle",
                "type": "button",
                "aria-controls": "supported-devices-panel",
                "aria-expanded": "false",
            },
        )
        self.assertLess(
            index.index('id="supported-devices-toggle"'),
            index.index('id="device-options-toggle"'),
        )
        for expected in (
            'id="supported-devices-panel"',
            'id="supported-devices-body"',
            'id="visa-library"',
            'name="visa_library"',
            'data-support-backend="@py"',
            'data-i18n="supported_devices.model"',
            'data-i18n="supported_devices.connections"',
        ):
            self.assertIn(expected, index)
        self.assertIn("renderSupportedDevices", app_js)

    def test_static_ui_displays_validation_scoped_model_support(self):
        index, _app_js = load_static_ui()
        run_form_js = (STATIC_DIR / "run_form.js").read_text(encoding="utf-8")

        for expected in [
            'id="model-support-summary"',
            'id="model-support-status"',
            'id="model-support-open"',
            'id="model-support-limits"',
            'id="model-support-pending"',
            'data-i18n="support.heading"',
            'data-i18n="support.open"',
            'data-i18n="support.limits"',
            'data-i18n="support.pending"',
        ]:
            with self.subTest(expected=expected):
                self.assertIn(expected, index)

        self.assertNotIn("/api/capabilities?locale=", run_form_js)

    def test_static_ui_device_resource_section_has_collapse_and_summary(self):
        index, _app_js = load_static_ui()

        assert_tag_with_attrs(
            self,
            index,
            "button",
            {
                "id": "toggle-device-resource",
                "type": "button",
                "aria-controls": "device-resource-body",
                "aria-expanded": "true",
            },
        )
        self.assertIn('id="device-resource-summary"', index)
        self.assertIn('id="device-resource-body"', index)
        self.assertIn('id="resource"', index)
        self.assertIn('id="resource-select"', index)
        self.assertIn('id="refresh-resources"', index)

        assert_tag_with_attrs(
            self,
            index,
            "button",
            {
                "id": "device-options-toggle",
                "type": "button",
                "aria-controls": "device-options-panel",
            },
        )
        assert_tag_with_attrs(
            self,
            index,
            "select",
            {"id": "instrument-model", "name": "instrument_model", "form": "run-form"},
        )
    def test_static_ui_expected_model_payload_semantics_remain_instrument_model(self):
        index, _app_js = load_static_ui()
        run_form_js = (STATIC_DIR / "run_form.js").read_text(encoding="utf-8")
        payload_js = (STATIC_DIR / "run_form_payload.js").read_text(encoding="utf-8")

        for value in ["", "34460A", "34461A"]:
            with self.subTest(value=value):
                assert_tag_with_attrs(self, index, "option", {"value": value})
        self.assertIn('data-i18n="device.auto_detect"', index)
        self.assertIn('data-i18n="device.require_model"', index)
        self.assertIn(
            'instrument_model: data.get("instrument_model")',
            run_form_js,
        )
        self.assertIn(
            "instrument_model: textOrNull(values.instrument_model)",
            payload_js,
        )
        self.assertNotIn("model_mode:", run_form_js)
        self.assertNotIn("modelMode:", run_form_js)
        self.assertNotIn("model_mode:", payload_js)
        self.assertNotIn("modelMode:", payload_js)

    def test_static_ui_exposes_stable_live_data_and_csv_contracts(self):
        index, app_js = load_static_ui()
        dom_js = (STATIC_DIR / "dom.js").read_text(encoding="utf-8")
        run_form_js = (STATIC_DIR / "run_form.js").read_text(encoding="utf-8")
        payload_js = (STATIC_DIR / "run_form_payload.js").read_text(encoding="utf-8")

        self.assertIn('id="resource"', index)
        self.assertIn('id="resource-select"', index)
        self.assertIn('id="select-csv-folder"', index)
        assert_tag_with_attrs(
            self,
            index,
            "input",
            {
                "id": "csv-enabled-checkbox",
                "name": "csv_enabled",
                "type": "checkbox",
            },
        )
        self.assertRegex(
            index,
            r'<input\b(?=[^>]*\bid="csv-enabled-checkbox")(?=[^>]*\bchecked\b)[^>]*>',
        )
        assert_tag_with_attrs(self, index, "input", {"id": "csv-path-input", "name": "csv"})
        self.assertIn('id="live-trend-chart"', index)
        self.assertIn('id="live-samples-body"', index)
        self.assertIn('id="live-sample-details"', index)
        self.assertIn('id="open-csv"', index)
        self.assertIn('"/api/runs/current/open-csv"', app_js)
        self.assertIn('"/api/csv/select-folder"', app_js)
        self.assertIn("csv_path", app_js)
        self.assertIn("csvEnabledCheckbox.checked", app_js)
        self.assertIn("csvInput.disabled = !enabled", app_js)
        self.assertIn("selectCsvFolderButton.disabled = !enabled", app_js)
        self.assertIn('querySelector("#csv-enabled-checkbox")', dom_js)
        self.assertIn('csv_enabled: data.get("csv_enabled")', run_form_js)
        self.assertIn("csv_enabled: csvEnabled", payload_js)

    def test_output_panel_fields_use_existing_run_form_contract(self):
        index, _app_js = load_static_ui()
        self.assertIn('data-panel="output-settings"', index)
        self.assertIn('data-summary-for="output-settings"', index)
        assert_tag_with_attrs(
            self, index, "input",
            {"id": "csv-enabled-checkbox", "form": "run-form", "name": "csv_enabled"},
        )
        assert_tag_with_attrs(
            self, index, "input",
            {"id": "csv-path-input", "form": "run-form", "name": "csv"},
        )
        assert_tag_with_attrs(
            self, index, "select",
            {"id": "csv-format", "form": "run-form", "name": "csv_format"},
        )
        for key in ("csv-elapsed", "csv-delta"):
            assert_tag_with_attrs(self, index, "input", {"id": key, "form": "run-form"})
        self.assertNotRegex(
            index,
            r'<input\b(?=[^>]*\bid="csv-(?:elapsed|delta)")[^>]*\bchecked\b',
        )
        tree = _HtmlTreeParser()
        tree.feed(index)
        output_panel = next(
            node for node in tree.descendants(tree.root)
            if node["attrs"].get("data-panel") == "output-settings"
        )
        self.assertNotIn("is-collapsed", output_panel["attrs"].get("class", "").split())

    def test_static_ui_exposes_live_data_panel(self):
        index, _app_js = load_static_ui()
        live_data_js = (STATIC_DIR / "live_data.js").read_text(encoding="utf-8")

        for expected in [
            'id="live-data-summary"',
            'id="status-state"',
            'id="status-captured"',
            'id="status-errors"',
            'id="webui-state-indicator"',
            'id="command-state-indicator"',
            'id="live-state-indicator"',
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
                self.assertIn(expected, live_data_js)

        assert_tag_with_attrs(
            self,
            index,
            "div",
            {"class": "live-status-row", "aria-live": "polite"},
        )
        for indicator_id in (
            "webui-state-indicator",
            "command-state-indicator",
            "live-state-indicator",
        ):
            with self.subTest(indicator=indicator_id):
                assert_tag_with_attrs(
                    self,
                    index,
                    "strong",
                    {"id": indicator_id},
                )
        assert_tag_with_attrs(
            self,
            index,
            "span",
            {"class": "state-dot", "aria-hidden": "true"},
        )

    def test_static_ui_live_chart_controls_preserve_accessibility_and_form_boundary(self):
        index, _app_js = load_static_ui()

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

        self.assertRegex(
            index,
            r"<option\b(?=[^>]*\bvalue=\"range-step\")(?=[^>]*\bdisabled\b)[^>]*>",
        )
        self.assertIn('id="live-chart-scale-mode-help"', index)
        assert_tag_with_attrs(
            self,
            index,
            "span",
            {"id": "live-chart-scale-mode-help", "class": "field-help is-hidden"},
        )
        assert_tag_with_attrs(
            self,
            index,
            "button",
            {
                "id": "toggle-live-chart",
                "type": "button",
                "aria-controls": "live-chart-content",
                "aria-expanded": "true",
            },
        )
        assert_tag_with_attrs(
            self,
            index,
            "svg",
            {
                "id": "live-trend-chart",
                "role": "img",
                "data-i18n-aria-label": "accessibility.live_sample_trend",
            },
        )

    def test_static_ui_exposes_cli_limit_constraints(self):
        index, _app_js = load_static_ui()
        run_form_js = (STATIC_DIR / "run_form.js").read_text(encoding="utf-8")

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
        self.assertIn("limits", run_form_js)
        self.assertIn("sw_min_interval_ms", run_form_js)

    def test_static_ui_status_log_and_details_toggle(self):
        index, _app_js = load_static_ui()

        self.assertIn('id="latest-status"', index)
        self.assertIn('role="log"', index)
        self.assertIn('id="toggle-status-details"', index)
        self.assertIn('aria-controls="status-details"', index)
        self.assertIn('aria-expanded="false"', index)
        self.assertIn('id="status-details"', index)
        self.assertIn('id="fatal-error"', index)
        self.assertIn('id="cleanup-status"', index)
        self.assertIn('id="raw-status"', index)

    def test_static_ui_exposes_run_control_and_endpoint_contracts(self):
        index, app_js = load_static_ui()
        endpoint_sources = app_js + (STATIC_DIR / "run_form_payload.js").read_text(
            encoding="utf-8"
        )

        for element_id in (
            "refresh-resources",
            "start-run",
            "trigger-run",
            "stop-run",
            "open-csv",
        ):
            with self.subTest(element_id=element_id):
                assert_tag_with_attrs(
                    self,
                    index,
                    "button",
                    {"id": element_id, "type": "button"},
                )
        for endpoint in (
            '"/api/runs"',
            '"/api/runs/current/command"',
            '"/api/runs/current/stop"',
            '"/api/runs/current/open-csv"',
        ):
            with self.subTest(endpoint=endpoint):
                self.assertIn(endpoint, endpoint_sources)
        self.assertIn("metadata,", app_js)
        self.assertNotIn("schema_version", app_js)
        self.assertNotIn('command: "software_trigger"', app_js)
        self.assertNotIn("arguments:", app_js)

    def test_dynamic_optional_labels_group_title_and_marker_before_select(self):
        index, _app_js = load_static_ui()
        parser = _HtmlTreeParser()
        parser.feed(index)

        contracts = {
            "ac-bandwidth-container": {
                "title_key": "measurement.ac_filter",
                "select_id": "ac-bandwidth",
                "name": "ac_bandwidth_hz",
            },
            "current-terminal-container": {
                "title_key": "measurement.current_terminal",
                "select_id": "current-terminal",
                "name": "current_terminal",
            },
        }
        for container_id, contract in contracts.items():
            with self.subTest(container_id=container_id):
                label = parser.find_by_id(container_id)
                self.assertIsNotNone(label)
                self.assertEqual(label["tag"], "label")
                self.assertIn("is-hidden", label["attrs"].get("class", "").split())
                descendants = list(parser.descendants(label))
                title = next(
                    node
                    for node in descendants
                    if "label-title" in node["attrs"].get("class", "").split()
                )
                title_text = next(
                    node
                    for node in parser.descendants(title)
                    if node["attrs"].get("data-i18n") == contract["title_key"]
                )
                optional_marker = next(
                    node
                    for node in parser.descendants(title)
                    if "optional-mark" in node["attrs"].get("class", "").split()
                )
                select = next(
                    node
                    for node in descendants
                    if node["tag"] == "select"
                    and node["attrs"].get("id") == contract["select_id"]
                )
                self.assertEqual(
                    title_text["attrs"].get("data-i18n"),
                    contract["title_key"],
                )
                self.assertIn(
                    "optional-mark",
                    optional_marker["attrs"].get("class", "").split(),
                )
                self.assertEqual(
                    optional_marker["attrs"].get("data-i18n"),
                    "common.optional",
                )

                self.assertEqual(select["tag"], "select")
                self.assertEqual(select["attrs"].get("id"), contract["select_id"])
                self.assertEqual(select["attrs"].get("name"), contract["name"])
                self.assertEqual(select["attrs"].get("form"), "run-form")
                self.assertIn("disabled", select["attrs"])

    def test_static_ui_scopes_trigger_options_by_mode(self):
        index, _app_js = load_static_ui()
        payload_js = (STATIC_DIR / "run_form_payload.js").read_text(encoding="utf-8")

        self.assertIn('data-mode-scope="simple"', index)
        self.assertIn('data-mode-scope="software"', index)
        self.assertIn('data-mode-scope="custom"', index)
        self.assertIn('data-mode-scope="hardware"', index)
        self.assertIn('data-mode-scope="software-trigger"', index)
        self.assertIn('data-mode-scope="trigger-timeout"', index)
        self.assertIn("trigger_count", payload_js)
        self.assertIn("sample_count", payload_js)

    def test_static_ui_preserves_hidden_trigger_timeout_payload_contract(self):
        payload_js = (STATIC_DIR / "run_form_payload.js").read_text(encoding="utf-8")
        support_js = (STATIC_DIR / "run_form_support.js").read_text(encoding="utf-8")

        self.assertIn("external", support_js)
        self.assertIn("external-custom", support_js)
        self.assertIn("trigger_timeout_ms", payload_js)

    def test_static_ui_preserves_measurement_scope_contract(self):
        index, _app_js = load_static_ui()
        self.assertIn('data-measurement-scope="voltage-dc,voltage-dc-ratio"', index)

    def test_static_ui_exposes_software_queue_and_trigger_metadata(self):
        index, _app_js = load_static_ui()
        payload_js = (STATIC_DIR / "run_form_payload.js").read_text(encoding="utf-8")

        self.assertIn('id="sw-queue-max-container"', index)
        self.assertIn('name="sw_queue_max"', index)
        self.assertIn('id="trigger-metadata-container"', index)
        self.assertIn('id="trigger-metadata"', index)
        self.assertIn("payload.sw_queue_max", payload_js)

    def test_static_ui_auto_zero_select_and_new_dropdowns(self):
        index, _app_js = load_static_ui()
        payload_js = (STATIC_DIR / "run_form_payload.js").read_text(encoding="utf-8")

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
        self.assertIn("auto_zero", payload_js)
        self.assertIn("payload.ac_bandwidth_hz", payload_js)
        self.assertIn("payload.gate_time_s", payload_js)
        self.assertIn("payload.freq_period_timeout", payload_js)
        self.assertIn("payload.current_terminal", payload_js)
        self.assertRegex(index, r'<select[^>]*id="gate-time"[^>]*disabled[^>]*>')
        self.assertRegex(
            index,
            r'<select[^>]*id="freq-period-timeout"[^>]*disabled[^>]*>',
        )

    def test_static_js_contains_sse_init_and_handlers(self):
        status_js = (STATIC_DIR / "status.js").read_text(encoding="utf-8")

        self.assertIn('EventSource("/api/runs/current/events")', status_js)
        self.assertIn('"run-status"', status_js)
        self.assertIn('typeof EventSource === "undefined"', status_js)
        self.assertIn('api("/api/runs/current")', status_js)

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

    def test_static_ui_exposes_help_button(self):
        index, _ = load_static_ui()

        assert_tag_with_attrs(
            self,
            index,
            "button",
            {"id": "help-button", "type": "button", "data-i18n": "app.help"},
        )

if __name__ == "__main__":
    unittest.main()
