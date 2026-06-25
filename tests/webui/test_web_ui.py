from __future__ import annotations

import contextlib
import io
import importlib.metadata
import logging.config
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - dependency-gated tests
    TestClient = None

if TestClient is not None:
    from keysight_logger_webui.web_ui import (
        CsvFolderSelectionUnavailable,
        FALLBACK_WEBUI_VERSION,
        RunAlreadyActive,
        RunStartRequest,
        WebRunManager,
        _uvicorn_log_config,
        create_app,
        get_webui_version,
        main,
    )


STATIC_DIR = Path(__file__).parents[2] / "src" / "keysight_logger_webui" / "static"


def load_static_ui():
    return (
        (STATIC_DIR / "index.html").read_text(encoding="utf-8"),
        (STATIC_DIR / "app.js").read_text(encoding="utf-8"),
    )


def assert_tag_with_attrs(testcase, html, tag, attrs):
    lookaheads = "".join(
        rf"(?=[^>]*\b{re.escape(name)}=\"{re.escape(value)}\")"
        for name, value in attrs.items()
    )
    testcase.assertRegex(html, rf"<{tag}\b{lookaheads}[^>]*>")


@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class WebUiApiTests(unittest.TestCase):
    def make_client(self):
        self.tempdir = tempfile.TemporaryDirectory()
        csv_path = Path(self.tempdir.name) / "out.csv"
        manager = WebRunManager()
        app = create_app(manager)
        return TestClient(app), csv_path

    def make_client_with_manager(self, manager):
        app = create_app(manager)
        return TestClient(app)

    def wait_until_inactive(self, client, timeout_s=1.0):
        deadline = time.monotonic() + timeout_s
        status = client.get("/api/runs/current").json()
        while status.get("active") and time.monotonic() < deadline:
            time.sleep(0.02)
            status = client.get("/api/runs/current").json()
        return status

    def tearDown(self):
        tempdir = getattr(self, "tempdir", None)
        if tempdir is not None:
            tempdir.cleanup()

    def test_capabilities_expose_cli_baseline_surface(self):
        client, _csv_path = self.make_client()

        response = client.get("/api/capabilities")

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(
            {"name": "keysight-logger-webui", "version": get_webui_version()},
            payload["app"],
        )
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

        limits = payload["limits"]
        self.assertEqual({"min": 100, "max": 600000}, limits["timeout_ms"])
        self.assertEqual({"min": 500, "max": 600000}, limits["trigger_timeout_ms"])
        self.assertEqual({"min": 1, "max": 1000000}, limits["max_samples"])
        self.assertEqual({"min": 0.5, "max": 86400.0}, limits["timer_interval_s"])
        self.assertEqual({"min": 0, "max": 600000, "nonzero_min": 50}, limits["sw_min_interval_ms"])
        self.assertEqual({"min": 0, "max": 10000}, limits["sw_queue_max"])

        defaults = payload["defaults"]
        self.assertEqual("on", defaults["auto_zero"])
        self.assertIsNone(defaults["ac_bandwidth_hz"])
        self.assertIsNone(defaults["gate_time_s"])
        self.assertIsNone(defaults["freq_period_timeout"])
        self.assertIsNone(defaults["current_terminal"])

    def test_capabilities_use_fallback_version_when_package_metadata_is_unavailable(self):
        client, _csv_path = self.make_client()

        with (
            patch(
                "keysight_logger_webui.web_ui.importlib.metadata.version",
                side_effect=importlib.metadata.PackageNotFoundError,
            ),
            patch(
                "keysight_logger_webui.web_ui._read_project_version",
                side_effect=FileNotFoundError("pyproject.toml"),
            ),
        ):
            response = client.get("/api/capabilities")

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {"name": "keysight-logger-webui", "version": FALLBACK_WEBUI_VERSION},
            response.json()["app"],
        )

    def test_run_start_rejects_second_active_run_and_stop_releases_it(self):
        client, csv_path = self.make_client()
        request = {
            "resource": "USB::FAKE",
            "csv": str(csv_path),
            "simulate": True,
            "trigger_mode": "software-custom",
            "trigger_timeout_ms": 500,
            "trigger_count": 1,
            "sample_count": 1,
        }

        first = client.post("/api/runs", json=request)
        second = client.post("/api/runs", json=request)
        stopped = client.post("/api/runs/current/stop")

        self.assertEqual(200, first.status_code)
        self.assertEqual(409, second.status_code)
        self.assertEqual(202, stopped.status_code)
        self.assertIn(stopped.json()["state"], {"running", "stopping", "stopped"})
        self.assertFalse(self.wait_until_inactive(client)["active"])

    def test_open_current_csv_rejects_idle_status(self):
        client, _csv_path = self.make_client()

        response = client.post("/api/runs/current/open-csv")

        self.assertEqual(409, response.status_code)
        self.assertEqual("no completed CSV available", response.json()["detail"])

    def test_open_current_csv_rejects_active_run(self):
        client, csv_path = self.make_client()
        started = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
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
        self.wait_until_inactive(client)

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
        client = self.make_client_with_manager(manager)

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
        client = self.make_client_with_manager(manager)

        response = client.post("/api/runs/current/open-csv")

        self.assertEqual(200, response.status_code)
        self.assertEqual({"opened": True, "csv_path": str(csv_path)}, response.json())
        self.assertEqual([csv_path], opened_paths)

    def test_select_csv_folder_returns_timestamped_csv_path(self):
        self.tempdir = tempfile.TemporaryDirectory()
        folder_path = Path(self.tempdir.name)
        manager = WebRunManager(directory_selector=lambda: folder_path)
        client = self.make_client_with_manager(manager)

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
        client = self.make_client_with_manager(manager)

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
        client = self.make_client_with_manager(manager)

        response = client.post("/api/csv/select-folder")

        self.assertEqual(503, response.status_code)
        self.assertEqual("folder selection dialog is unavailable", response.json()["detail"])

    def test_run_start_rejects_second_run_while_active(self):
        tempdir = tempfile.TemporaryDirectory()
        self.tempdir = tempdir
        csv_path = Path(tempdir.name) / "out.csv"
        manager = WebRunManager()
        request = RunStartRequest(
            resource="USB::FAKE",
            csv=str(csv_path),
            simulate=True,
            trigger_mode="software-custom",
            trigger_timeout_ms=500,
            trigger_count=1,
            sample_count=1,
        )
        started = manager.start(request)
        self.assertTrue(started["active"])

        with self.assertRaises(RunAlreadyActive):
            manager.start(request)

        manager.stop()
        deadline = time.monotonic() + 1.0
        while manager.status()["active"] and time.monotonic() < deadline:
            time.sleep(0.02)

    def test_software_trigger_updates_status_and_captures(self):
        client, csv_path = self.make_client()
        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "csv": str(csv_path),
                "simulate": True,
                "trigger_mode": "software",
                "trigger_timeout_ms": 500,
                "max_samples": 1,
            },
        )
        self.assertEqual(200, response.status_code)

        triggered = client.post(
            "/api/runs/current/command",
            json={
                "command": "software_trigger",
                "arguments": {"metadata": {"source": "web-ui", "batch": "A"}},
            },
        )
        self.assertEqual(202, triggered.status_code)
        self.assertEqual(
            {"status": "accepted", "command": "software_trigger", "job_id": None},
            triggered.json(),
        )
        self.assertEqual(
            404,
            client.post(
                "/api/runs/current/trigger",
                json={
                    "command": "software_trigger",
                    "arguments": {"metadata": {}},
                },
            ).status_code,
        )
        deadline = time.monotonic() + 1.0
        status = {}
        while time.monotonic() < deadline:
            status = client.get("/api/runs/current").json()
            if status["captured"] == 1 and not status["active"]:
                break
            time.sleep(0.02)

        self.assertEqual(1, status["captured"])
        self.assertFalse(status["active"])
        self.assertEqual("stopped", status["state"])
        self.assertEqual(5000, status["sample_capacity"])
        self.assertEqual(1, len(status["recent_samples"]))
        sample = status["latest_sample"]
        self.assertEqual(sample, status["recent_samples"][-1])
        self.assertEqual(1, sample["sequence"])
        self.assertEqual("current_dc", sample["measurement_type"])
        self.assertAlmostEqual(1.23, sample["value"])
        self.assertEqual("A", sample["unit"])
        self.assertEqual("ok", sample["status"])
        self.assertEqual("USB::FAKE", sample["resource_id"])
        self.assertEqual("software", sample["trigger_source"])
        self.assertEqual("A", sample["trigger_metadata"]["batch"])
        self.assertEqual("web-ui", sample["trigger_metadata"]["source"])
        self.assertRegex(sample["timestamp_utc_plus_8"], r"\+08:00$")
        self.assertIsInstance(sample["measurement_metadata"], dict)

    def test_command_endpoint_returns_structured_validation_and_no_active_errors(self):
        client, _ = self.make_client()

        no_active = client.post(
            "/api/runs/current/command",
            json={"command": "software_trigger", "job_id": "job-1"},
        )
        malformed = client.post(
            "/api/runs/current/command",
            content="{bad json",
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(409, no_active.status_code)
        self.assertEqual(
            {
                "status": "error",
                "command": "software_trigger",
                "job_id": "job-1",
                "error": "no_active_run",
                "message": "no active run",
            },
            no_active.json(),
        )
        self.assertEqual(400, malformed.status_code)
        self.assertEqual("error", malformed.json()["status"])
        self.assertEqual("validation_error", malformed.json()["error"])
        self.assertIsNone(malformed.json()["command"])
        self.assertIsNone(malformed.json()["job_id"])

    def test_live_data_retains_latest_5000_samples_until_next_start(self):
        self.tempdir = tempfile.TemporaryDirectory()
        csv_path = Path(self.tempdir.name) / "out.csv"
        manager = WebRunManager()
        client = self.make_client_with_manager(manager)
        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "csv": str(csv_path),
                "simulate": True,
                "trigger_mode": "immediate",
                "max_samples": 1,
            },
        )
        self.assertEqual(200, response.status_code)
        initial_status = self.wait_until_inactive(client, timeout_s=1.0)
        self.assertEqual(1, initial_status["captured"])

        for sequence in range(2, 5006):
            manager._record_event(
                SimpleNamespace(
                    run_id=initial_status["run_id"],
                    event="sample",
                    message=None,
                    captured=sequence,
                    sample=SimpleNamespace(
                        timestamp_utc=None,
                        measurement_type="current_dc",
                        value=1.23,
                        unit="A",
                        trigger_id=None,
                        trigger_source="immediate",
                        trigger_metadata={},
                        measurement_metadata={},
                        resource_id="USB::FAKE",
                        status="ok",
                    ),
                )
            )

        status = client.get("/api/runs/current").json()

        self.assertEqual(5005, status["captured"])
        self.assertFalse(status["active"])
        self.assertEqual(5000, status["sample_capacity"])
        self.assertEqual(5000, len(status["recent_samples"]))
        self.assertEqual(6, status["recent_samples"][0]["sequence"])
        self.assertEqual(5005, status["recent_samples"][-1]["sequence"])
        self.assertEqual(status["recent_samples"][-1], status["latest_sample"])

        next_csv_path = csv_path.with_name("next.csv")
        restarted = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "csv": str(next_csv_path),
                "simulate": True,
                "trigger_mode": "immediate",
                "max_samples": 1,
            },
        )
        self.assertEqual(200, restarted.status_code)
        restarted_status = self.wait_until_inactive(client, timeout_s=1.0)

        self.assertEqual(1, restarted_status["captured"])
        self.assertEqual(1, len(restarted_status["recent_samples"]))
        self.assertEqual(1, restarted_status["latest_sample"]["sequence"])

    def test_start_validation_reuses_cli_constraints(self):
        client, csv_path = self.make_client()

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "csv": str(csv_path),
                "simulate": True,
                "auto_range": False,
                "measurement": "voltage-dc",
            },
        )

        self.assertEqual(422, response.status_code)
        self.assertIn("--range is required when --auto-range off", response.json()["detail"])

    def test_start_validation_rejects_cli_limit_violations(self):
        client, csv_path = self.make_client()
        cases = [
            ({"timeout_ms": 99}, "--timeout-ms 99 is outside"),
            ({"timer_interval_s": 0.01}, "--timer-interval-s 0.01 is below"),
            ({"sw_queue_max": 10001}, "--sw-queue-max 10001 is outside"),
        ]

        for extra_payload, expected_detail in cases:
            with self.subTest(extra_payload=extra_payload):
                response = client.post(
                    "/api/runs",
                    json={
                        "resource": "USB::FAKE",
                        "csv": str(csv_path),
                        "simulate": True,
                        **extra_payload,
                    },
                )

                self.assertEqual(422, response.status_code)
                self.assertIn(expected_detail, response.json()["detail"])

    def test_manager_can_build_default_request_model(self):
        request = RunStartRequest(resource="USB::FAKE")

        self.assertEqual("current-dc", request.measurement)
        self.assertEqual("on", request.auto_zero)
        self.assertIsNone(request.ac_bandwidth_hz)
        self.assertIsNone(request.gate_time_s)
        self.assertIsNone(request.freq_period_timeout)
        self.assertIsNone(request.current_terminal)

    def test_manager_normalizes_legacy_auto_zero_booleans(self):
        manager = WebRunManager()

        on_request = manager._validate_request(
            RunStartRequest(resource="USB::FAKE", auto_zero=True)
        )
        off_request = manager._validate_request(
            RunStartRequest(resource="USB::FAKE", auto_zero=False)
        )

        self.assertEqual("on", on_request.auto_zero)
        self.assertEqual("off", off_request.auto_zero)

    def test_webui_version_flag_uses_project_version(self):
        output = io.StringIO()

        with self.assertRaises(SystemExit) as raised:
            with contextlib.redirect_stdout(output):
                main(["--version"])

        self.assertEqual(0, raised.exception.code)
        self.assertIn("keysight-logger-webui", output.getvalue())
        self.assertIn(get_webui_version(), output.getvalue())

    def test_webui_version_uses_fallback_when_metadata_and_project_are_unavailable(self):
        with (
            patch(
                "keysight_logger_webui.web_ui.importlib.metadata.version",
                side_effect=importlib.metadata.PackageNotFoundError,
            ),
            patch(
                "keysight_logger_webui.web_ui._read_project_version",
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

    def test_api_runs_validation_core_v1_1_0_contracts(self):
        client, csv_path = self.make_client()

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "csv": str(csv_path),
                "simulate": True,
                "measurement": "current-dc",
                "auto_zero": "once",
                "trigger_mode": "software-custom",
                "trigger_timeout_ms": 500,
                "trigger_count": 1,
                "sample_count": 1,
            },
        )
        self.assertEqual(200, response.status_code)
        client.post("/api/runs/current/stop")
        self.wait_until_inactive(client)

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "csv": str(csv_path),
                "simulate": True,
                "measurement": "period",
                "freq_period_timeout": "auto",
                "trigger_mode": "software-custom",
                "trigger_timeout_ms": 500,
                "trigger_count": 1,
                "sample_count": 1,
            },
        )
        self.assertEqual(422, response.status_code)
        self.assertIn(
            "--freq-period-timeout is not supported for --measurement period",
            response.json()["detail"],
        )

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "csv": str(csv_path),
                "simulate": True,
                "measurement": "frequency",
                "ac_bandwidth_hz": 20.0,
                "gate_time_s": 0.1,
                "freq_period_timeout": "auto",
                "trigger_mode": "software-custom",
                "trigger_timeout_ms": 500,
                "trigger_count": 1,
                "sample_count": 1,
            },
        )
        self.assertEqual(200, response.status_code)
        client.post("/api/runs/current/stop")
        self.wait_until_inactive(client)

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "csv": str(csv_path),
                "simulate": True,
                "measurement": "voltage-ac",
                "ac_bandwidth_hz": 200.0,
                "trigger_mode": "software-custom",
                "trigger_timeout_ms": 500,
                "trigger_count": 1,
                "sample_count": 1,
            },
        )
        self.assertEqual(200, response.status_code)
        client.post("/api/runs/current/stop")
        self.wait_until_inactive(client)

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "csv": str(csv_path),
                "simulate": True,
                "measurement": "current-dc",
                "auto_range": False,
                "measurement_range": 10.0,
                "current_terminal": 10,
                "trigger_mode": "software-custom",
                "trigger_timeout_ms": 500,
                "trigger_count": 1,
                "sample_count": 1,
            },
        )
        self.assertEqual(200, response.status_code)
        client.post("/api/runs/current/stop")
        self.wait_until_inactive(client)

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "csv": str(csv_path),
                "simulate": True,
                "measurement": "voltage-dc-ratio",
                "dcv_input_impedance": "10m",
                "trigger_mode": "software-custom",
                "trigger_timeout_ms": 500,
                "trigger_count": 1,
                "sample_count": 1,
            },
        )
        self.assertEqual(200, response.status_code)
        client.post("/api/runs/current/stop")
        self.wait_until_inactive(client)

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "csv": str(csv_path),
                "simulate": True,
                "measurement": "current-dc",
                "auto_range": False,
                "measurement_range": 10.0,
                "current_terminal": 3,
                "trigger_mode": "software-custom",
                "trigger_timeout_ms": 500,
                "trigger_count": 1,
                "sample_count": 1,
            },
        )
        self.assertEqual(422, response.status_code)
        self.assertIn("cannot be used with the 10 A current range", response.json()["detail"])

    def test_api_rejects_frequency_period_fields_for_other_measurements(self):
        client, csv_path = self.make_client()

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "csv": str(csv_path),
                "simulate": True,
                "measurement": "voltage-dc",
                "gate_time_s": 0.1,
                "trigger_mode": "immediate",
                "max_samples": 1,
            },
        )

        self.assertEqual(422, response.status_code)
        self.assertIn(
            "gate-time-s can only be used with --measurement frequency or period",
            response.json()["detail"],
        )

    def test_immediate_run_publishes_final_inactive_status_without_polling(self):
        self.tempdir = tempfile.TemporaryDirectory()
        csv_path = Path(self.tempdir.name) / "out.csv"
        manager = WebRunManager()
        client = self.make_client_with_manager(manager)
        version_before = manager._status_version

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "csv": str(csv_path),
                "simulate": True,
                "trigger_mode": "immediate",
                "max_samples": 1,
            },
        )
        self.assertEqual(200, response.status_code)

        with manager._lock:
            handle = manager._active
        self.assertIsNotNone(handle)
        self.assertIsNotNone(handle.worker)
        handle.worker.join(timeout=1.0)

        with manager._lock:
            status = dict(manager._last_status)
            version_after = manager._status_version

        self.assertFalse(handle.worker.is_alive())
        self.assertTrue(handle.worker_done)
        self.assertGreater(version_after, version_before)
        self.assertEqual("stopped", status["state"])
        self.assertFalse(status["active"])
        self.assertEqual(1, status["captured"])
        self.assertIsNone(status["fatal_error"])
        self.assertEqual(1, len(status["recent_samples"]))
        self.assertEqual(status["recent_samples"][-1], status["latest_sample"])

    def test_current_run_events_returns_initial_status_snapshot(self):
        manager = WebRunManager()
        app = create_app(manager)
        route_fn = next(route.endpoint for route in app.routes if route.path == "/api/runs/current/events")
        response = route_fn()

        self.assertEqual("text/event-stream", response.media_type)

        import asyncio

        async def get_next(async_gen):
            async for item in async_gen:
                return item

        first_event = asyncio.run(get_next(response.body_iterator))
        self.assertTrue(first_event.startswith("event: run-status"))
        self.assertIn("id: 0", first_event)
        self.assertIn('"state":"idle"', first_event)
        self.assertIn('"active":false', first_event)

        manager.close_event_streams()
        self.assertIsNone(asyncio.run(get_next(response.body_iterator)))

    def test_static_js_contains_sse_init_and_handlers(self):
        _index, app_js = load_static_ui()

        self.assertIn('EventSource("/api/runs/current/events")', app_js)
        self.assertIn('sseSource.addEventListener("run-status"', app_js)
        self.assertIn('typeof EventSource === "undefined"', app_js)
        self.assertIn('api("/api/runs/current")', app_js)
        self.assertNotIn("\nwindow.setInterval(pollStatus, 1000)", app_js)


if __name__ == "__main__":
    unittest.main()
