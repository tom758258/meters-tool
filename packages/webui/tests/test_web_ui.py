from __future__ import annotations

import contextlib
import io
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - dependency-gated tests
    TestClient = None

if TestClient is not None:
    from keysight_logger_webui.web_ui import (
        CsvFolderSelectionUnavailable,
        RunAlreadyActive,
        RunStartRequest,
        WebRunManager,
        create_app,
        get_webui_version,
        main,
    )


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
        self.assertIsNone(defaults["current_terminal"])

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
            "/api/runs/current/trigger",
            json={"source": "web-ui", "batch": "A"},
        )
        self.assertEqual(202, triggered.status_code)
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

    def test_static_ui_omits_cli_compat_only_controls(self):
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger_webui" / "static"
        index = (static_dir / "index.html").read_text(encoding="utf-8")
        app_js = (static_dir / "app.js").read_text(encoding="utf-8")
        styles = (static_dir / "styles.css").read_text(encoding="utf-8")

        self.assertNotIn("Current range alias", index)
        self.assertNotIn("Legacy external trigger", index)
        self.assertNotIn("current_range", index)
        self.assertNotIn("current_range", app_js)
        self.assertNotIn("enable_hw_trigger", index)
        self.assertNotIn("enable_hw_trigger", app_js)

    def test_static_ui_exposes_live_resource_select_and_range_unit(self):
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger_webui" / "static"
        index = (static_dir / "index.html").read_text(encoding="utf-8")
        app_js = (static_dir / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="resource-select"', index)
        self.assertIn("Live resource", index)
        self.assertIn("live_only=true", app_js)
        self.assertIn('id="range-unit"', index)
        self.assertIn('id="range-suffix"', index)
        self.assertRegex(index, r"<select\s+id=\"measurement-range\"")
        self.assertIn('<select id="nplc"', index)
        self.assertNotIn('name="measurement_range" form="run-form" type="number"', index)
        self.assertNotIn('name="nplc" form="run-form" type="number"', index)
        self.assertIn("resourceSelect.addEventListener", app_js)
        self.assertIn("updateMeasurementUi", app_js)
        self.assertIn("populateRangeOptions", app_js)
        self.assertIn("populateNplcOptions", app_js)
        self.assertIn("measurementRangeInput.required = !autoRangeEnabled", app_js)

    def test_static_ui_uses_requested_layout_sections(self):
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger_webui" / "static"
        index = (static_dir / "index.html").read_text(encoding="utf-8")
        app_js = (static_dir / "app.js").read_text(encoding="utf-8")
        styles = (static_dir / "styles.css").read_text(encoding="utf-8")

        self.assertIn("<h1>Keysight Meters</h1>", index)
        self.assertIn('<p class="subtitle">Local acquisition console</p>', index)
        self.assertIn('const subtitle = document.querySelector(".subtitle");', app_js)
        self.assertIn("function applyAppMetadata", app_js)
        self.assertIn("applyAppMetadata(capabilities.app)", app_js)
        self.assertIn("Local acquisition console · v${version}", app_js)
        self.assertLess(index.index('class="resource-row"'), index.index('class="grid"'))
        self.assertNotIn('class="status-strip"', index)
        self.assertIn('id="resource"', index)
        self.assertIn('id="resource-select"', index)
        self.assertIn('id="select-csv-folder"', index)
        self.assertIn('id="csv-path-input" name="csv" placeholder="Default"', index)
        self.assertNotIn("Live data view is not implemented yet.", index)
        self.assertIn('id="live-trend-chart"', index)
        self.assertIn('id="live-samples-body"', index)
        self.assertIn('id="live-sample-details"', index)
        self.assertIn('id="open-csv"', index)
        self.assertGreater(index.index('class="run-controls"'), index.index('id="live-data-heading"'))
        self.assertLess(index.index('class="live-data-metrics"'), index.index('class="run-controls"'))
        self.assertLess(index.index('id="stop-run"'), index.index('id="open-csv"'))
        self.assertIn('<button class="panel-toggle" type="button" aria-expanded="true">-</button>', index)
        self.assertIn("function setPanelExpanded", app_js)
        self.assertIn('button.textContent = expanded ? "-" : "+";', app_js)
        self.assertIn("function renderLiveData", app_js)
        self.assertIn('"/api/runs/current/open-csv"', app_js)
        self.assertIn('"/api/csv/select-folder"', app_js)
        self.assertIn("csvInput.value = result.csv_path", app_js)
        self.assertIn("updateOpenCsvButton", app_js)
        self.assertIn("grid-template-columns: minmax(192px, 0.2fr) minmax(0, 0.8fr)", styles)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", styles)
        self.assertIn("grid-auto-rows: 68px", styles)
        self.assertIn("height: 760px", styles)
        self.assertIn("background: #e6ede8", styles)
        self.assertIn("color: #18302b", styles)
        self.assertIn("background: #f4f7f2", styles)
        self.assertIn("color: #24332f", styles)

    def test_static_ui_exposes_live_data_panel(self):
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger_webui" / "static"
        index = (static_dir / "index.html").read_text(encoding="utf-8")
        app_js = (static_dir / "app.js").read_text(encoding="utf-8")
        styles = (static_dir / "styles.css").read_text(encoding="utf-8")

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
            "function renderLiveData",
            "function renderLiveChart",
            "function updateLiveChartBaseline",
            "liveChartBaselineRunId",
            "liveChartBaselineValue",
            "status.run_id || null",
            "gridLineCountPerSide = 5",
            "const LIVE_CHART_VISIBLE_GRID_LIMIT = 4;",
            "maxAbsDeviation / LIVE_CHART_VISIBLE_GRID_LIMIT",
            "function renderLiveSamplesTable",
            "function renderLiveSampleDetails",
            "function renderLiveStats",
            "function scaleLiveValue",
            "function setLiveSectionVisible",
            "function shouldSuppressApiStatusLog",
            "function markSoftwareTriggerQueuedForLog",
            "recent_samples",
            "latest_sample",
            "sample_capacity",
        ]:
            with self.subTest(expected=expected):
                self.assertIn(expected, app_js)

        self.assertIn(".live-trend-chart", styles)
        self.assertIn(".live-stats-grid", styles)
        self.assertIn(".live-collapse-toggle", styles)
        self.assertNotIn(".live-chart-axis", styles)
        self.assertNotIn(".live-chart-axis-line", styles)
        self.assertIn(".live-samples-table", styles)
        self.assertIn(".live-chart-line", styles)
        self.assertIn(".live-chart-grid-center", styles)

    def test_static_ui_exposes_cli_limit_constraints(self):
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger_webui" / "static"
        index = (static_dir / "index.html").read_text(encoding="utf-8")
        app_js = (static_dir / "app.js").read_text(encoding="utf-8")

        self.assertIn('name="timeout_ms" type="number" min="100" max="600000"', index)
        self.assertIn('name="trigger_timeout_ms" type="number" min="500" max="600000"', index)
        self.assertIn('name="max_samples" type="number" min="1" max="1000000"', index)
        self.assertIn('name="trigger_count" form="run-form" type="number" min="1" max="1000000"', index)
        self.assertIn('name="sample_count" form="run-form" type="number" min="1" max="1000000"', index)
        self.assertIn('name="buffer_drain_size" form="run-form" type="number" min="1" max="10000"', index)
        self.assertIn('name="hw_trigger_delay_s" form="run-form" type="number" min="0" max="3600"', index)
        self.assertIn('name="timer_interval_s" form="run-form" type="number" min="0.5" max="86400"', index)
        self.assertIn("function applyInputLimits", app_js)
        self.assertIn("function validateSwMinInterval", app_js)
        self.assertIn("Use 0 to disable throttling", app_js)

    def test_static_ui_status_log_and_details_toggle(self):
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger_webui" / "static"
        index = (static_dir / "index.html").read_text(encoding="utf-8")
        app_js = (static_dir / "app.js").read_text(encoding="utf-8")
        styles = (static_dir / "styles.css").read_text(encoding="utf-8")

        self.assertIn('id="latest-status"', index)
        self.assertIn('class="status-log"', index)
        self.assertIn('role="log"', index)
        self.assertIn('id="toggle-status-details"', index)
        self.assertIn('aria-controls="status-details"', index)
        self.assertIn('aria-expanded="false"', index)
        self.assertIn('id="status-details" class="status-details is-hidden"', index)
        self.assertIn('id="fatal-error"', index)
        self.assertIn('id="cleanup-status"', index)
        self.assertIn('id="raw-status"', index)
        self.assertIn("const STATUS_LOG_LINE_COUNT = 5;", app_js)
        self.assertIn("function appendStatusLog", app_js)
        self.assertIn("function appendApiStatusLog", app_js)
        self.assertIn("function setStatusDetailsVisible", app_js)
        self.assertIn("Show Details", app_js)
        self.assertIn("Hide Details", app_js)
        self.assertIn(".status-log", styles)
        self.assertIn("grid-template-rows: repeat(5, 1.45em)", styles)

    def test_static_ui_marks_blankable_inputs_optional(self):
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger_webui" / "static"
        index = (static_dir / "index.html").read_text(encoding="utf-8")

        optional_labels = [
            "CSV path",
            "Timeout ms",
            "Trigger timeout ms",
            "Max samples",
            "Buffer drain size",
            "AC bandwidth",
            "Current terminal",
            "HW delay s",
            "SW min interval ms",
            "SW queue max",
            "Trigger metadata JSON",
        ]
        for label in optional_labels:
            with self.subTest(label=label):
                self.assertRegex(
                    index,
                    rf"{re.escape(label)}\s*<span class=\"optional-mark\">\(Optional\)</span>",
                )

        required_labels = [
            "VISA resource",
            "Range",
            "Trigger count",
            "Sample count",
            "Timer interval s",
        ]
        for label in required_labels:
            with self.subTest(label=label):
                self.assertNotRegex(
                    index,
                    rf"{re.escape(label)}\s*<span class=\"optional-mark\">\(Optional\)</span>",
                )

    def test_static_ui_scopes_trigger_options_by_mode(self):
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger_webui" / "static"
        index = (static_dir / "index.html").read_text(encoding="utf-8")
        app_js = (static_dir / "app.js").read_text(encoding="utf-8")
        styles = (static_dir / "styles.css").read_text(encoding="utf-8")

        self.assertIn('data-mode-scope="simple"', index)
        self.assertIn('data-mode-scope="software"', index)
        self.assertIn('data-mode-scope="custom"', index)
        self.assertIn('data-mode-scope="hardware"', index)
        self.assertIn('data-mode-scope="software-trigger"', index)
        self.assertIn('data-mode-scope="trigger-timeout"', index)
        self.assertIn("function updateTriggerModeUi", app_js)
        self.assertIn("function modeScopeVisible", app_js)
        self.assertIn("triggerMode === \"software\"", app_js)
        self.assertIn("if (customMode)", app_js)
        self.assertIn("if (hardwareMode)", app_js)
        self.assertIn("triggerCountInput.required = customMode", app_js)
        self.assertIn("sampleCountInput.required = customMode", app_js)
        self.assertIn("is-hidden", styles)

    def test_static_ui_preserves_hidden_trigger_timeout_payload_contract(self):
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger_webui" / "static"
        app_js = (static_dir / "app.js").read_text(encoding="utf-8")

        self.assertIn("const DEFAULT_TRIGGER_TIMEOUT_MS = 10000;", app_js)
        self.assertIn("function triggerTimeoutMs", app_js)
        self.assertIn("function usesTriggerTimeout", app_js)
        self.assertIn('return mode === "external" || mode === "external-custom";', app_js)
        self.assertIn(
            'usesTriggerTimeout(mode) ? data.get("trigger_timeout_ms") : DEFAULT_TRIGGER_TIMEOUT_MS',
            app_js,
        )
        self.assertIn("trigger_timeout_ms: triggerTimeoutMs(data, triggerMode)", app_js)

    def test_static_ui_scopes_dcv_input_and_trigger_button(self):
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger_webui" / "static"
        index = (static_dir / "index.html").read_text(encoding="utf-8")
        app_js = (static_dir / "app.js").read_text(encoding="utf-8")

        self.assertIn('data-measurement-scope="voltage-dc,voltage-dc-ratio"', index)
        self.assertIn("measurementScopedControls", app_js)
        self.assertIn("updateTriggerButtonUi", app_js)
        self.assertIn("mode === \"software-custom\"", app_js)
        self.assertIn("mode === \"software\" && !timerActive", app_js)
        self.assertIn("timerIntervalInput.addEventListener", app_js)
        self.assertIn("timerIntervalInput.required = timerEnabled", app_js)
        self.assertIn("Check highlighted run settings before Start", app_js)

    def test_static_ui_exposes_software_queue_and_trigger_metadata(self):
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger_webui" / "static"
        index = (static_dir / "index.html").read_text(encoding="utf-8")
        app_js = (static_dir / "app.js").read_text(encoding="utf-8")
        styles = (static_dir / "styles.css").read_text(encoding="utf-8")

        self.assertIn('id="sw-queue-max-container"', index)
        self.assertIn('name="sw_queue_max"', index)
        self.assertIn('id="trigger-metadata-container"', index)
        self.assertIn('id="trigger-metadata"', index)
        self.assertIn("#trigger-metadata", styles)
        self.assertIn("resize: none", styles)
        self.assertIn("overflow: auto", styles)
        self.assertIn("swQueueMaxContainer", app_js)
        self.assertIn("payload.sw_queue_max", app_js)
        self.assertIn("function triggerMetadataPayload", app_js)
        self.assertIn("Trigger metadata must be valid JSON object", app_js)

    def test_static_ui_auto_zero_select_and_new_dropdowns(self):
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger_webui" / "static"
        index = (static_dir / "index.html").read_text(encoding="utf-8")
        app_js = (static_dir / "app.js").read_text(encoding="utf-8")

        self.assertIn('<select name="auto_zero" form="run-form">', index)
        self.assertNotIn('<input name="auto_zero" form="run-form" type="checkbox"', index)

        self.assertIn('id="ac-bandwidth-container"', index)
        self.assertIn('id="ac-bandwidth"', index)
        self.assertIn('id="current-terminal-container"', index)
        self.assertIn('id="current-terminal"', index)

        self.assertIn('const autoZeroSelect = document.querySelector("[name=\'auto_zero\']");', app_js)
        self.assertIn('const acBandwidthContainer = document.querySelector("#ac-bandwidth-container");', app_js)
        self.assertIn('const acBandwidthSelect = document.querySelector("#ac-bandwidth");', app_js)
        self.assertIn('const currentTerminalContainer = document.querySelector("#current-terminal-container");', app_js)
        self.assertIn('const currentTerminalSelect = document.querySelector("#current-terminal");', app_js)
        self.assertIn("function supportsAcBandwidth", app_js)
        self.assertIn("function supportsCurrentTerminal", app_js)
        self.assertIn('auto_zero: autoZeroVisible ? (data.get("auto_zero") || "on") : "on",', app_js)
        self.assertIn("const autoZeroVisible = supportsAutoZero(selectedMeasurement);", app_js)
        self.assertIn("const autoZeroVisible = supportsAutoZero(selected);", app_js)
        self.assertNotIn('selected === "voltage-dc-ratio"', app_js)
        self.assertIn("const acBandwidthVisible = supportsAcBandwidth(measurement);", app_js)
        self.assertIn("const currentTerminalVisible = supportsCurrentTerminal(measurement);", app_js)
        self.assertIn('payload.ac_bandwidth_hz = numberOrNull(data.get("ac_bandwidth_hz"));', app_js)
        self.assertIn('payload.current_terminal = numberOrNull(data.get("current_terminal"));', app_js)
        self.assertIn('acBandwidthSelect.value = "";', app_js)
        self.assertIn('currentTerminalSelect.value = "";', app_js)

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
        static_dir = Path(__file__).parent.parent / "src" / "keysight_logger_webui" / "static"
        app_js = (static_dir / "app.js").read_text(encoding="utf-8")

        self.assertIn('EventSource("/api/runs/current/events")', app_js)
        self.assertIn('sseSource.addEventListener("run-status"', app_js)
        self.assertIn('typeof EventSource === "undefined"', app_js)
        self.assertIn('api("/api/runs/current")', app_js)
        self.assertIn("renderStatus(status)", app_js)
        self.assertIn("startPolling()", app_js)
        self.assertIn("stopPolling()", app_js)
        self.assertIn("initSSE()", app_js)
        self.assertNotIn("\nwindow.setInterval(pollStatus, 1000)", app_js)


if __name__ == "__main__":
    unittest.main()
