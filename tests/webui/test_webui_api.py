from __future__ import annotations

import contextlib
import hashlib
import io
import importlib.metadata
import logging.config
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - dependency-gated tests
    TestClient = None

if TestClient is not None:
    from meters_tool_webui._web_payloads import support_summary
    from meters_tool_webui.web_ui import (
        APP_JS_CACHEBUSTER_TOKEN,
        CsvFolderSelectionUnavailable,
        FALLBACK_WEBUI_VERSION,
        WebRunManager,
        _uvicorn_log_config,
        get_webui_version,
        main,
    )


from webui_test_helpers import (
    cleanup_tempdir,
    make_api_client,
    make_api_client_with_manager,
    wait_until_inactive,
)

@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class WebUiApiTests(unittest.TestCase):
    def tearDown(self):
        cleanup_tempdir(self)

    def test_capabilities_expose_cli_baseline_surface(self):
        client, _csv_path = make_api_client(self)

        response = client.get("/api/capabilities")

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(
            {"name": "meters-tool-webui", "version": get_webui_version()},
            payload["app"],
        )
        self.assertEqual("34461A", payload["instrument_profile"]["model"])
        self.assertEqual(
            "keysight-34461a",
            payload["instrument_profile"]["model_id"],
        )
        self.assertEqual(
            [
                {
                    "model": "34461A",
                    "model_id": "keysight-34461a",
                    "vendor": "Keysight",
                },
                {
                    "model": "34460A",
                    "model_id": "keysight-34460a",
                    "vendor": "Keysight",
                },
            ],
            payload["available_profiles"],
        )
        self.assertEqual(
            [
                {
                    "vendor": "Keysight",
                    "model": "34461A",
                    "connections": ["usb", "tcpip"],
                },
                {
                    "vendor": "Keysight",
                    "model": "34460A",
                    "connections": ["usb"],
                },
            ],
            payload["supported_devices"],
        )
        self.assertNotIn("backend", str(payload["supported_devices"]).lower())
        self.assertNotIn("@py", str(payload["supported_devices"]).lower())
        self.assertEqual(
            [
                "current-dc",
                "voltage-dc",
                "voltage-dc-ratio",
                "current-ac",
                "voltage-ac",
                "frequency",
                "period",
                "resistance-2w",
                "resistance-4w",
            ],
            [item["name"] for item in payload["measurements"]],
        )
        self.assertIn("software-custom", payload["trigger_modes"])
        measurements = {item["name"]: item for item in payload["measurements"]}
        self.assertEqual(
            ["on", "off", "once"],
            measurements["voltage-dc"]["auto_zero_options"],
        )
        self.assertTrue(measurements["voltage-dc"]["supports_auto_zero"])
        self.assertEqual([], measurements["voltage-ac"]["auto_zero_options"])
        self.assertFalse(measurements["voltage-ac"]["supports_auto_zero"])
        self.assertEqual(
            ["default", "10m", "auto"],
            measurements["voltage-dc"]["dcv_input_impedance_options"],
        )
        self.assertTrue(
            measurements["voltage-dc"]["supports_dcv_input_impedance"]
        )
        self.assertEqual(
            [],
            measurements["current-dc"]["dcv_input_impedance_options"],
        )
        self.assertFalse(
            measurements["current-dc"]["supports_dcv_input_impedance"]
        )
        self.assertTrue(
            payload["trigger_mode_metadata"]["external"]["uses_trigger_timeout"]
        )
        self.assertTrue(
            payload["trigger_mode_metadata"]["external-custom"][
                "uses_trigger_timeout"
            ]
        )
        self.assertFalse(
            payload["trigger_mode_metadata"]["software"]["uses_trigger_timeout"]
        )
        self.assertEqual(
            [
                {"label": "100 mV", "value": 0.1},
                {"label": "1 V", "value": 1.0},
                {"label": "10 V", "value": 10.0},
                {"label": "100 V", "value": 100.0},
                {"label": "1000 V", "value": 1000.0},
            ],
            measurements["voltage-dc"]["range_options"],
        )
        self.assertEqual([0.02, 0.2, 1.0, 10.0, 100.0], measurements["voltage-dc"]["nplc_options"])
        self.assertFalse(measurements["voltage-ac"]["supports_nplc"])
        self.assertEqual([3.0, 20.0, 200.0], measurements["voltage-ac"]["ac_bandwidth_hz_options"])
        self.assertEqual([3.0, 20.0, 200.0], measurements["current-ac"]["ac_bandwidth_hz_options"])
        self.assertEqual([3, 10], measurements["current-dc"]["current_terminal_options"])
        self.assertEqual([3, 10], measurements["current-ac"]["current_terminal_options"])
        self.assertTrue(measurements["voltage-ac"]["supports_ac_bandwidth"])
        self.assertTrue(measurements["current-dc"]["supports_current_terminal"])
        self.assertFalse(measurements["voltage-dc"]["supports_ac_bandwidth"])
        self.assertFalse(measurements["voltage-dc"]["supports_current_terminal"])
        for name, unit in [("frequency", "Hz"), ("period", "s")]:
            with self.subTest(measurement=name):
                measurement = measurements[name]
                self.assertEqual(unit, measurement["unit"])
                self.assertEqual(
                    [
                        {"label": "100 mV", "value": 0.1},
                        {"label": "1 V", "value": 1.0},
                        {"label": "10 V", "value": 10.0},
                        {"label": "100 V", "value": 100.0},
                        {"label": "750 V", "value": 750.0},
                    ],
                    measurement["range_options"],
                )
                self.assertEqual([3.0, 20.0, 200.0], measurement["ac_bandwidth_hz_options"])
                self.assertEqual([0.01, 0.1, 1.0], measurement["gate_time_s_options"])
                self.assertTrue(measurement["supports_gate_time"])
                self.assertEqual(
                    {
                        "auto_range": True,
                        "ac_bandwidth_hz": 20.0,
                        "gate_time_s": 0.1,
                        "freq_period_timeout": "auto" if name == "frequency" else None,
                    },
                    measurement["defaults"],
                )
        self.assertEqual(
            ["auto", "1s"],
            measurements["frequency"]["freq_period_timeout_options"],
        )
        self.assertTrue(measurements["frequency"]["supports_freq_period_timeout"])
        self.assertEqual([], measurements["period"]["freq_period_timeout_options"])
        self.assertFalse(measurements["period"]["supports_freq_period_timeout"])
        support = payload["support"]["start-trigger-record"]["live"]
        self.assertEqual("live_validated_full_suite", support["validation_status"])
        self.assertEqual("usb", support["transport_scope"])
        self.assertEqual("system_visa", support["backend_scope"])
        support_scopes = {
            (scope["transport_scope"], scope["backend_scope"]): scope
            for scope in support["scopes"]
        }
        self.assertEqual(
            "live_validated_full_suite",
            support_scopes[("tcpip", "system_visa")]["validation_status"],
        )
        self.assertEqual(
            "reviewed_artifact_correction",
            support_scopes[("tcpip", "system_visa")]["evidence"],
        )
        self.assertEqual(
            "live_validated_full_suite",
            support_scopes[("tcpip", "pyvisa_py")]["validation_status"],
        )
        usb_features = support_scopes[("usb", "system_visa")]["features"]
        self.assertEqual(
            "live_validated_full_suite",
            usb_features["measurement"]["voltage-dc-ratio"]["validation_status"],
        )
        self.assertEqual(
            "live_validated_full_suite",
            usb_features["trigger_mode"]["external-custom"]["validation_status"],
        )
        summary = payload["support_summary"]
        self.assertEqual("34461A", summary["model"])
        self.assertEqual("keysight-34461a", summary["model_id"])
        self.assertEqual("Auto-detect", summary["display_model"])
        self.assertEqual("34461A", summary["capability_profile"])
        self.assertEqual(
            "keysight-34461a",
            summary["capability_profile_id"],
        )
        self.assertTrue(summary["is_fallback_capability_view"])
        self.assertIsInstance(summary["runtime_driver_note"], str)
        self.assertTrue(summary["runtime_driver_note"])
        self.assertEqual(
            "support.runtime_driver.detected_idn",
            summary["runtime_driver_note_key"],
        )
        self.assertIsInstance(summary["status_text"], str)
        self.assertTrue(summary["status_text"])
        self.assertEqual(
            "support.status.profile_workflows_validated",
            summary["status_key"],
        )
        self.assertEqual("live_validated_full_suite", summary["validation_status"])
        self.assertEqual("usb", summary["transport_scope"])
        self.assertEqual("system_visa", summary["backend_scope"])
        self.assertEqual(
            [
                "support.workflow.immediate",
                "support.workflow.software",
                "support.workflow.software_timer",
                "support.workflow.custom_buffered",
                "support.workflow.frequency",
                "support.workflow.period",
                "support.workflow.external_trigger",
            ],
            summary["open_workflow_keys"],
        )
        self.assertEqual(
            len(summary["open_workflows"]),
            len(summary["open_workflow_keys"]),
        )
        self.assertEqual([], summary["limits"])
        self.assertEqual([], summary["limit_keys"])
        self.assertEqual([], summary["pending"])
        self.assertEqual([], summary["pending_keys"])
        summary_scopes = {
            (scope["transport_scope"], scope["backend_scope"]): scope
            for scope in summary["scopes"]
        }
        self.assertEqual(
            "live_validated_full_suite",
            summary_scopes[("tcpip", "system_visa")]["validation_status"],
        )
        self.assertEqual(
            "live_validated_full_suite",
            summary_scopes[("tcpip", "pyvisa_py")]["validation_status"],
        )

        limits = payload["limits"]
        self.assertEqual({"min": 100, "max": 600000}, limits["timeout_ms"])
        self.assertEqual({"min": 500, "max": 600000}, limits["trigger_timeout_ms"])
        self.assertEqual({"min": 1, "max": 1000000}, limits["max_samples"])
        self.assertEqual({"min": 0.5, "max": 86400.0}, limits["timer_interval_s"])
        self.assertEqual({"min": 0, "max": 600000, "nonzero_min": 50}, limits["sw_min_interval_ms"])
        self.assertEqual({"min": 0, "max": 10000}, limits["sw_queue_max"])

        defaults = payload["defaults"]
        self.assertIsNone(defaults["instrument_model"])
        self.assertEqual(
            {
                "mode": "auto",
                "resolved": False,
                "fallback_profile": "34461A",
                "fallback_profile_id": "keysight-34461a",
            },
            payload["model_resolution"],
        )
        self.assertEqual("on", defaults["auto_zero"])
        self.assertIsNone(defaults["ac_bandwidth_hz"])
        self.assertIsNone(defaults["gate_time_s"])
        self.assertIsNone(defaults["freq_period_timeout"])
        self.assertIsNone(defaults["current_terminal"])

    def test_capabilities_model_query_returns_34460a_limits(self):
        client, _csv_path = make_api_client(self)

        response = client.get("/api/capabilities?model=34460A")

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("34460A", payload["instrument_profile"]["model"])
        self.assertEqual(
            "keysight-34460a",
            payload["instrument_profile"]["model_id"],
        )
        self.assertEqual(1000, payload["instrument_profile"]["reading_memory_limit"])
        self.assertEqual(1000, payload["limits"]["buffer_drain_size"]["max"])
        self.assertNotIn("external", payload["trigger_modes"])
        self.assertNotIn("external-custom", payload["trigger_modes"])
        self.assertIn("software-custom", payload["trigger_modes"])
        summary = payload["support_summary"]
        self.assertEqual("34460A", summary["model"])
        self.assertEqual("keysight-34460a", summary["model_id"])
        self.assertEqual("34460A", summary["display_model"])
        self.assertEqual("34460A", summary["capability_profile"])
        self.assertEqual(
            "keysight-34460a",
            summary["capability_profile_id"],
        )
        self.assertFalse(summary["is_fallback_capability_view"])
        self.assertEqual("34460A", payload["defaults"]["instrument_model"])
        self.assertEqual(
            {
                "mode": "explicit",
                "resolved": True,
                "fallback_profile": None,
                "fallback_profile_id": None,
            },
            payload["model_resolution"],
        )
        self.assertEqual("live_validated_full_suite", summary["validation_status"])
        self.assertEqual("usb", summary["transport_scope"])
        self.assertEqual("system_visa", summary["backend_scope"])
        self.assertIsInstance(summary["runtime_driver_note"], str)
        self.assertTrue(summary["runtime_driver_note"])
        self.assertEqual(
            "support.runtime_driver.detected_idn",
            summary["runtime_driver_note_key"],
        )
        self.assertIsInstance(summary["status_text"], str)
        self.assertTrue(summary["status_text"])
        self.assertEqual(
            "support.status.usb_system_visa_validated",
            summary["status_key"],
        )
        self.assertEqual(
            [
                "support.workflow.immediate",
                "support.workflow.software",
                "support.workflow.software_timer",
                "support.workflow.custom_buffered",
                "support.workflow.frequency",
                "support.workflow.period",
            ],
            summary["open_workflow_keys"],
        )
        self.assertEqual(
            [
                "support.limit.no_10a_current_path",
                "support.limit.no_current_terminal_selection",
                "support.limit.reading_memory_1000",
                "support.limit.no_base_profile_external_trigger",
            ],
            summary["limit_keys"],
        )
        self.assertEqual(
            [
                "support.pending.lan_tcpip_system_visa_validation",
                "support.pending.lan_tcpip_pyvisa_py_validation",
            ],
            summary["pending_keys"],
        )
        for prose_field, key_field in (
            ("open_workflows", "open_workflow_keys"),
            ("limits", "limit_keys"),
            ("pending", "pending_keys"),
        ):
            self.assertEqual(len(summary[prose_field]), len(summary[key_field]))
        summary_scopes = {
            (scope["transport_scope"], scope["backend_scope"]): scope
            for scope in summary["scopes"]
        }
        self.assertEqual(
            "transport_pending",
            summary_scopes[("tcpip", "system_visa")]["validation_status"],
        )
        self.assertEqual(
            "transport_pending",
            summary_scopes[("tcpip", "pyvisa_py")]["validation_status"],
        )
        usb_features = summary_scopes[("usb", "system_visa")]["features"]
        self.assertEqual(
            "live_validated_full_suite",
            usb_features["measurement"]["voltage-dc-ratio"]["validation_status"],
        )
        self.assertEqual(
            "live_validated_full_suite",
            usb_features["measurement"]["voltage-dc"]["validation_status"],
        )
        self.assertEqual(
            "live_validated_full_suite",
            usb_features["trigger_mode"]["software-custom"]["validation_status"],
        )
        lan_features = summary_scopes[("tcpip", "system_visa")]["features"]
        self.assertEqual(
            "feature_pending",
            lan_features["measurement"]["voltage-dc"]["validation_status"],
        )
        self.assertEqual(
            "feature_pending",
            lan_features["trigger_mode"]["immediate"]["validation_status"],
        )
        measurements = {item["name"]: item for item in payload["measurements"]}
        for name in ("current-dc", "current-ac"):
            with self.subTest(name=name):
                range_values = [item["value"] for item in measurements[name]["range_options"]]
                self.assertNotIn(10.0, range_values)
                self.assertEqual([], measurements[name]["current_terminal_options"])
                self.assertFalse(measurements[name]["supports_current_terminal"])

    def test_capabilities_model_query_preserves_34461a_limits(self):
        client, _csv_path = make_api_client(self)

        response = client.get("/api/capabilities?model=34461A")

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("34461A", payload["instrument_profile"]["model"])
        self.assertEqual(
            "keysight-34461a",
            payload["instrument_profile"]["model_id"],
        )
        self.assertEqual(10000, payload["instrument_profile"]["reading_memory_limit"])
        self.assertIn("external", payload["trigger_modes"])
        self.assertIn("external-custom", payload["trigger_modes"])
        summary = payload["support_summary"]
        self.assertEqual("34461A", summary["model"])
        self.assertEqual("keysight-34461a", summary["model_id"])
        self.assertEqual("34461A", summary["display_model"])
        self.assertEqual("34461A", summary["capability_profile"])
        self.assertEqual(
            "keysight-34461a",
            summary["capability_profile_id"],
        )
        self.assertFalse(summary["is_fallback_capability_view"])
        self.assertEqual("34461A", payload["defaults"]["instrument_model"])
        self.assertEqual(
            {
                "mode": "explicit",
                "resolved": True,
                "fallback_profile": None,
                "fallback_profile_id": None,
            },
            payload["model_resolution"],
        )
        self.assertIsInstance(summary["status_text"], str)
        self.assertTrue(summary["status_text"])
        self.assertEqual(
            "support.status.profile_workflows_validated",
            summary["status_key"],
        )
        self.assertEqual(
            "support.runtime_driver.detected_idn",
            summary["runtime_driver_note_key"],
        )
        self.assertEqual(
            [
                "support.workflow.immediate",
                "support.workflow.software",
                "support.workflow.software_timer",
                "support.workflow.custom_buffered",
                "support.workflow.frequency",
                "support.workflow.period",
                "support.workflow.external_trigger",
            ],
            summary["open_workflow_keys"],
        )
        self.assertEqual(len(summary["open_workflows"]), len(summary["open_workflow_keys"]))
        self.assertEqual([], summary["limits"])
        self.assertEqual([], summary["limit_keys"])
        self.assertEqual([], summary["pending"])
        self.assertEqual([], summary["pending_keys"])
        summary_scopes = {
            (scope["transport_scope"], scope["backend_scope"]): scope
            for scope in summary["scopes"]
        }
        self.assertEqual(
            "live_validated_full_suite",
            summary_scopes[("tcpip", "system_visa")]["validation_status"],
        )
        self.assertEqual(
            "live_validated_full_suite",
            summary_scopes[("tcpip", "pyvisa_py")]["validation_status"],
        )
        measurements = {item["name"]: item for item in payload["measurements"]}
        self.assertIn(10.0, [item["value"] for item in measurements["current-dc"]["range_options"]])
        self.assertEqual([3, 10], measurements["current-dc"]["current_terminal_options"])

    def test_support_summary_unknown_profile_keeps_prose_and_adds_empty_key_lists(self):
        fake_profile = SimpleNamespace(model="FutureModel", model_id="future-model")
        fake_live_support = SimpleNamespace(
            validation_status="not_supported_by_model",
            transport_scope="unknown",
            backend_scope="unknown",
            scopes=(),
        )

        with patch(
            "meters_tool_webui._web_payloads.start_workflow_support",
            return_value={"start-trigger-record": {"live": fake_live_support}},
        ):
            summary = support_summary(fake_profile)

        self.assertIsInstance(summary["status_text"], str)
        self.assertTrue(summary["status_text"])
        self.assertEqual("support.status.not_open", summary["status_key"])
        self.assertIsInstance(summary["runtime_driver_note"], str)
        self.assertTrue(summary["runtime_driver_note"])
        self.assertEqual(
            "support.runtime_driver.detected_idn",
            summary["runtime_driver_note_key"],
        )
        self.assertEqual([], summary["open_workflows"])
        self.assertEqual([], summary["open_workflow_keys"])
        self.assertEqual([], summary["limits"])
        self.assertEqual([], summary["limit_keys"])
        self.assertEqual([], summary["pending"])
        self.assertEqual([], summary["pending_keys"])

    def test_capabilities_model_id_query_returns_canonical_profile_metadata(self):
        client, _csv_path = make_api_client(self)

        response = client.get("/api/capabilities?model=keysight-34461a")

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("34461A", payload["instrument_profile"]["model"])
        self.assertEqual(
            "keysight-34461a",
            payload["instrument_profile"]["model_id"],
        )
        self.assertEqual("34461A", payload["defaults"]["instrument_model"])

    def test_capabilities_use_fallback_version_when_package_metadata_is_unavailable(self):
        with (
            patch(
                "meters_tool_core._version.importlib.metadata.version",
                side_effect=importlib.metadata.PackageNotFoundError,
            ),
            patch(
                "meters_tool_core._version.read_project_version",
                side_effect=FileNotFoundError("pyproject.toml"),
            ),
        ):
            client, _csv_path = make_api_client(self)
            response = client.get("/api/capabilities")

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {"name": "meters-tool-webui", "version": FALLBACK_WEBUI_VERSION},
            response.json()["app"],
        )

    def test_verified_resource_scan_infers_34460a_model_metadata(self):
        client, _csv_path = make_api_client(self)

        with (
            patch(
                "meters_tool_webui._run_manager.VisaInstrument.list_resources",
                return_value=["USB::METER"],
            ),
            patch(
                "meters_tool_webui._run_manager.VisaInstrument.verify_resource",
                return_value=(True, "Keysight Technologies,34460A,MY123,1.0"),
            ),
        ):
            response = client.get("/api/resources?verify=true&live_only=true")

        self.assertEqual(200, response.status_code)
        resource = response.json()["resources"][0]
        self.assertEqual("34460A", resource["instrument_model"])
        self.assertEqual("keysight-34460a", resource["instrument_model_id"])
        self.assertEqual(
            {
                "vendor": "Keysight",
                "model": "34460A",
                "model_id": "keysight-34460a",
            },
            resource["matched_profile"],
        )

    def test_verified_resource_scan_infers_34461a_model_metadata(self):
        client, _csv_path = make_api_client(self)

        with (
            patch(
                "meters_tool_webui._run_manager.VisaInstrument.list_resources",
                return_value=["USB::METER"],
            ),
            patch(
                "meters_tool_webui._run_manager.VisaInstrument.verify_resource",
                return_value=(True, "Keysight Technologies,34461A,MY123,1.0"),
            ),
        ):
            response = client.get("/api/resources?verify=true&live_only=true")

        self.assertEqual(200, response.status_code)
        resource = response.json()["resources"][0]
        self.assertEqual("34461A", resource["instrument_model"])
        self.assertEqual("keysight-34461a", resource["instrument_model_id"])
        self.assertEqual(
            {
                "vendor": "Keysight",
                "model": "34461A",
                "model_id": "keysight-34461a",
            },
            resource["matched_profile"],
        )

    def test_verified_resource_scan_keeps_unknown_or_empty_idn_without_model_metadata(self):
        client, _csv_path = make_api_client(self)

        for detail in ("Other Vendor,1234,ABC,1.0", ""):
            with self.subTest(detail=detail):
                with (
                    patch(
                        "meters_tool_webui._run_manager.VisaInstrument.list_resources",
                        return_value=["USB::UNKNOWN"],
                    ),
                    patch(
                        "meters_tool_webui._run_manager.VisaInstrument.verify_resource",
                        return_value=(True, detail),
                    ),
                ):
                    response = client.get(
                        "/api/resources?verify=true&live_only=true"
                    )

                self.assertEqual(200, response.status_code)
                resource = response.json()["resources"][0]
                self.assertIsNone(resource["instrument_model"])
                self.assertIsNone(resource["instrument_model_id"])
                self.assertIsNone(resource["matched_profile"])

    def test_plain_resource_scan_does_not_verify_or_add_model_metadata(self):
        client, _csv_path = make_api_client(self)

        with (
            patch(
                "meters_tool_webui._run_manager.VisaInstrument.list_resources",
                return_value=["USB::METER"],
            ),
            patch("meters_tool_webui._run_manager.VisaInstrument.verify_resource") as verify,
        ):
            response = client.get("/api/resources")

        self.assertEqual(200, response.status_code)
        self.assertEqual([{"resource": "USB::METER"}], response.json()["resources"])
        verify.assert_not_called()

    def test_index_uses_versioned_static_js_content_cachebuster(self):
        client, _csv_path = make_api_client(self)
        static_dir = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "meters_tool_webui"
            / "static"
        )
        hasher = hashlib.sha256()
        for path in sorted(static_dir.glob("*.js"), key=lambda item: item.name):
            hasher.update(path.name.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(path.read_bytes())
            hasher.update(b"\0")
        digest = hasher.hexdigest()[:12]

        response = client.get("/")

        self.assertEqual(200, response.status_code)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertNotIn(APP_JS_CACHEBUSTER_TOKEN, response.text)
        self.assertIn(
            f'/static/app.js?v={get_webui_version()}-{digest}',
            response.text,
        )

    def test_static_javascript_assets_are_not_cached(self):
        client, _csv_path = make_api_client(self)

        response = client.get("/static/live_data.js")

        self.assertEqual(200, response.status_code)
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_static_css_assets_are_not_cached(self):
        client, _csv_path = make_api_client(self)

        response = client.get("/static/styles.css")

        self.assertEqual(200, response.status_code)
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_open_current_csv_rejects_idle_status(self):
        client, _csv_path = make_api_client(self)

        status = client.get("/api/runs/current").json()

        response = client.post("/api/runs/current/open-csv")

        self.assertIsNone(status["csv_enabled"])
        self.assertIsNone(status["csv_path"])
        self.assertEqual(409, response.status_code)
        self.assertEqual("no completed CSV available", response.json()["detail"])

    def test_open_current_csv_rejects_active_run(self):
        client, csv_path = make_api_client(self)
        started = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "instrument_model": "34461A",
                "csv": str(csv_path),
                "simulate": True,
                "trigger_mode": "software-custom",
                "trigger_timeout_ms": 500,
                "trigger_count": 1,
                "sample_count": 1,
            },
        )
        self.assertEqual(200, started.status_code)

        response = client.post("/api/runs/current/open-csv")
        client.post("/api/runs/current/stop")
        wait_until_inactive(client)

        self.assertEqual(409, response.status_code)
        self.assertEqual("run is still active", response.json()["detail"])

    def test_open_current_csv_rejects_missing_completed_file(self):
        self.tempdir = tempfile.TemporaryDirectory()
        missing_csv = Path(self.tempdir.name) / "missing.csv"
        manager = WebRunManager()
        manager._last_status = {
            **manager.status(),
            "state": "stopped",
            "active": False,
            "csv_path": str(missing_csv),
        }
        client = make_api_client_with_manager(manager)

        response = client.post("/api/runs/current/open-csv")

        self.assertEqual(404, response.status_code)
        self.assertEqual("CSV file not found", response.json()["detail"])

    def test_open_current_csv_uses_default_app_for_completed_file(self):
        self.tempdir = tempfile.TemporaryDirectory()
        csv_path = Path(self.tempdir.name) / "out.csv"
        csv_path.write_text("timestamp,value\n", encoding="utf-8")
        opened_paths: list[Path] = []
        manager = WebRunManager(csv_opener=opened_paths.append)
        manager._last_status = {
            **manager.status(),
            "state": "stopped",
            "active": False,
            "csv_path": str(csv_path),
        }
        client = make_api_client_with_manager(manager)

        response = client.post("/api/runs/current/open-csv")

        self.assertEqual(200, response.status_code)
        self.assertEqual({"opened": True, "csv_path": str(csv_path)}, response.json())
        self.assertEqual([csv_path], opened_paths)

    def test_select_csv_folder_returns_timestamped_csv_path(self):
        self.tempdir = tempfile.TemporaryDirectory()
        folder_path = Path(self.tempdir.name)
        manager = WebRunManager(directory_selector=lambda: folder_path)
        client = make_api_client_with_manager(manager)

        response = client.post("/api/csv/select-folder")

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["selected"])
        self.assertEqual(str(folder_path), payload["folder_path"])
        csv_path = Path(payload["csv_path"])
        self.assertEqual(folder_path, csv_path.parent)
        self.assertRegex(csv_path.name, r"^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}\.csv$")

    def test_select_csv_folder_cancel_returns_empty_selection(self):
        manager = WebRunManager(directory_selector=lambda: None)
        client = make_api_client_with_manager(manager)

        response = client.post("/api/csv/select-folder")

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {"selected": False, "folder_path": None, "csv_path": None},
            response.json(),
        )

    def test_select_csv_folder_unavailable_returns_503(self):
        def unavailable():
            raise CsvFolderSelectionUnavailable("folder selection dialog is unavailable")

        manager = WebRunManager(directory_selector=unavailable)
        client = make_api_client_with_manager(manager)

        response = client.post("/api/csv/select-folder")

        self.assertEqual(503, response.status_code)
        self.assertEqual("folder selection dialog is unavailable", response.json()["detail"])

    def test_webui_version_flag_uses_project_version(self):
        output = io.StringIO()

        with self.assertRaises(SystemExit) as raised:
            with contextlib.redirect_stdout(output):
                main(["--version"])

        self.assertEqual(0, raised.exception.code)
        self.assertIn("meters-tool-webui", output.getvalue())
        self.assertIn(get_webui_version(), output.getvalue())

    def test_webui_version_uses_fallback_when_metadata_and_project_are_unavailable(self):
        with (
            patch(
                "meters_tool_core._version.importlib.metadata.version",
                side_effect=importlib.metadata.PackageNotFoundError,
            ),
            patch(
                "meters_tool_core._version.read_project_version",
                side_effect=FileNotFoundError("pyproject.toml"),
            ),
        ):
            self.assertEqual(FALLBACK_WEBUI_VERSION, get_webui_version())

    def test_uvicorn_log_config_uses_standard_logging_formatters(self):
        log_config = _uvicorn_log_config()

        logging.config.dictConfig(log_config)

        self.assertEqual(1, log_config["version"])
        self.assertFalse(log_config["disable_existing_loggers"])
        self.assertIn("default", log_config["formatters"])
        self.assertIn("access", log_config["formatters"])
        self.assertNotIn("()", log_config["formatters"]["default"])
        self.assertEqual("default", log_config["handlers"]["default"]["formatter"])
        self.assertEqual("access", log_config["handlers"]["access"]["formatter"])

    def test_webui_server_uses_shutdown_friendly_uvicorn_options(self):
        configs = []

        class FakeConfig:
            def __init__(self, app, **kwargs):
                self.app = app
                self.kwargs = kwargs

        class FakeServer:
            def __init__(self, config):
                self.config = config

            def handle_exit(self, sig, frame):
                self.should_exit = True

            def run(self):
                configs.append(self.config)

        original_uvicorn = sys.modules.get("uvicorn")
        sys.modules["uvicorn"] = SimpleNamespace(Config=FakeConfig, Server=FakeServer)
        try:
            exit_code = main(["--host", "127.0.0.1", "--port", "8769"])
        finally:
            if original_uvicorn is None:
                sys.modules.pop("uvicorn", None)
            else:
                sys.modules["uvicorn"] = original_uvicorn

        self.assertEqual(0, exit_code)
        self.assertEqual("127.0.0.1", configs[0].kwargs["host"])
        self.assertEqual(8769, configs[0].kwargs["port"])
        self.assertEqual("off", configs[0].kwargs["lifespan"])
        self.assertEqual(_uvicorn_log_config(), configs[0].kwargs["log_config"])
        self.assertTrue(configs[0].kwargs["access_log"])


if __name__ == "__main__":
    unittest.main()
