from __future__ import annotations

import re
import tempfile
import threading
import time
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - dependency-gated tests
    TestClient = None

if TestClient is not None:
    from keysight_logger.models import MeasurementSample
    from keysight_logger.web_ui import RunAlreadyActive, RunStartRequest, WebRunManager, create_app


class FakeInstrument:
    resource_id = "USB::FAKE"

    def __init__(self, config):
        self.config = config
        self.connected = False
        self.closed = False
        self.abort_count = 0

    def connect(self):
        self.connected = True

    def write(self, _command):
        return

    def query_ascii_float(self, _command):
        return 1.23

    def set_timeout_ms(self, _timeout_ms):
        return

    def abort_measurement(self):
        self.abort_count += 1
        return True

    def release_to_local(self):
        return "release:ok"

    def cleanup_release_to_local(self):
        return "cleanup:ok"

    def close(self):
        self.closed = True


class FakeMeasurement:
    def __init__(self, measurement_type="current_dc"):
        self._measurement_type = measurement_type

    def configure(self, _instrument, _config):
        return

    def read_sample(self, instrument, trigger):
        from datetime import datetime, timezone

        return MeasurementSample(
            timestamp_utc=datetime.now(timezone.utc),
            measurement_type=self._measurement_type,
            value=1.23,
            unit="A",
            status="ok",
            resource_id=instrument.resource_id,
            trigger_id=trigger.id,
            trigger_source=trigger.source.value,
        )


@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class WebUiApiTests(unittest.TestCase):
    def make_client(self):
        self.tempdir = tempfile.TemporaryDirectory()
        csv_path = Path(self.tempdir.name) / "out.csv"
        manager = WebRunManager(
            instrument_factory=FakeInstrument,
            measurement_factory=lambda measurement_type: FakeMeasurement(measurement_type),
        )
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
            [
                "current-dc",
                "voltage-dc",
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
        limits = payload["limits"]
        self.assertEqual({"min": 100, "max": 600000}, limits["timeout_ms"])
        self.assertEqual({"min": 500, "max": 600000}, limits["trigger_timeout_ms"])
        self.assertEqual({"min": 1, "max": 1000000}, limits["max_samples"])
        self.assertEqual({"min": 0.5, "max": 86400.0}, limits["timer_interval_s"])
        self.assertEqual({"min": 0, "max": 600000, "nonzero_min": 50}, limits["sw_min_interval_ms"])
        self.assertEqual({"min": 0, "max": 10000}, limits["sw_queue_max"])

    def test_run_start_rejects_second_active_run_and_stop_releases_it(self):
        client, csv_path = self.make_client()
        request = {
            "resource": "USB::FAKE",
            "csv": str(csv_path),
            "trigger_mode": "software",
            "trigger_timeout_ms": 500,
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
                "trigger_mode": "software",
                "trigger_timeout_ms": 500,
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
        manager = WebRunManager(
            instrument_factory=FakeInstrument,
            measurement_factory=lambda measurement_type: FakeMeasurement(measurement_type),
        )
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
        manager = WebRunManager(
            instrument_factory=FakeInstrument,
            measurement_factory=lambda measurement_type: FakeMeasurement(measurement_type),
            csv_opener=opened_paths.append,
        )
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

    def test_run_start_rejects_second_run_while_first_is_connecting(self):
        tempdir = tempfile.TemporaryDirectory()
        self.tempdir = tempdir
        csv_path = Path(tempdir.name) / "out.csv"
        connect_entered = threading.Event()
        release_connect = threading.Event()
        created_instruments: list[FakeInstrument] = []

        class SlowConnectInstrument(FakeInstrument):
            def connect(self):
                connect_entered.set()
                self.connected = True
                release_connect.wait(timeout=1)

        def instrument_factory(config):
            instrument = SlowConnectInstrument(config)
            created_instruments.append(instrument)
            return instrument

        manager = WebRunManager(
            instrument_factory=instrument_factory,
            measurement_factory=lambda measurement_type: FakeMeasurement(measurement_type),
        )
        request = RunStartRequest(
            resource="USB::FAKE",
            csv=str(csv_path),
            trigger_mode="software",
            trigger_timeout_ms=500,
        )
        first_error: list[BaseException] = []

        def start_first():
            try:
                manager.start(request)
            except BaseException as exc:  # pragma: no cover - failure path for the worker thread
                first_error.append(exc)

        worker = threading.Thread(target=start_first)
        worker.start()
        self.assertTrue(connect_entered.wait(timeout=1))

        with self.assertRaises(RunAlreadyActive):
            manager.start(request)

        release_connect.set()
        worker.join(timeout=1)
        self.assertFalse(worker.is_alive())
        self.assertEqual([], first_error)
        self.assertEqual(1, len(created_instruments))
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
                "trigger_mode": "software",
                "trigger_timeout_ms": 500,
                "max_samples": 1,
            },
        )
        self.assertEqual(200, response.status_code)

        triggered = client.post("/api/runs/current/trigger", json={"batch": "A"})
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

    def test_start_validation_reuses_cli_constraints(self):
        client, csv_path = self.make_client()

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "csv": str(csv_path),
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
                        **extra_payload,
                    },
                )

                self.assertEqual(422, response.status_code)
                self.assertIn(expected_detail, response.json()["detail"])

    def test_manager_can_build_default_request_model(self):
        request = RunStartRequest(resource="USB::FAKE")

        self.assertEqual("current-dc", request.measurement)
        self.assertTrue(request.auto_zero)

    def test_static_ui_omits_cli_compat_only_controls(self):
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger" / "static"
        index = (static_dir / "index.html").read_text(encoding="utf-8")
        app_js = (static_dir / "app.js").read_text(encoding="utf-8")

        self.assertNotIn("Current range alias", index)
        self.assertNotIn("Legacy external trigger", index)
        self.assertNotIn("current_range", index)
        self.assertNotIn("current_range", app_js)
        self.assertNotIn("enable_hw_trigger", index)
        self.assertNotIn("enable_hw_trigger", app_js)

    def test_static_ui_exposes_live_resource_select_and_range_unit(self):
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger" / "static"
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
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger" / "static"
        index = (static_dir / "index.html").read_text(encoding="utf-8")
        app_js = (static_dir / "app.js").read_text(encoding="utf-8")
        styles = (static_dir / "styles.css").read_text(encoding="utf-8")

        self.assertIn("<h1>Keysight Meters</h1>", index)
        self.assertIn('<p class="subtitle">Local acquisition console</p>', index)
        self.assertLess(index.index('class="resource-row"'), index.index('class="status-strip"'))
        self.assertIn('id="resource"', index)
        self.assertIn('id="resource-select"', index)
        self.assertIn("Live data view is not implemented yet.", index)
        self.assertIn('id="open-csv"', index)
        self.assertLess(index.index('id="stop-run"'), index.index('id="open-csv"'))
        self.assertIn('class="panel-toggle"', index)
        self.assertIn("function setPanelExpanded", app_js)
        self.assertIn('"/api/runs/current/open-csv"', app_js)
        self.assertIn("updateOpenCsvButton", app_js)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", styles)
        self.assertIn("background: #e6ede8", styles)
        self.assertIn("color: #18302b", styles)
        self.assertIn("background: #f4f7f2", styles)
        self.assertIn("color: #24332f", styles)

    def test_static_ui_exposes_cli_limit_constraints(self):
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger" / "static"
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
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger" / "static"
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
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger" / "static"
        index = (static_dir / "index.html").read_text(encoding="utf-8")

        optional_labels = [
            "CSV path",
            "Timeout ms",
            "Trigger timeout ms",
            "Max samples",
            "Buffer drain size",
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
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger" / "static"
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
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger" / "static"
        app_js = (static_dir / "app.js").read_text(encoding="utf-8")

        self.assertIn("const DEFAULT_TRIGGER_TIMEOUT_MS = 10000;", app_js)
        self.assertIn("function triggerTimeoutMs", app_js)
        self.assertIn("function usesTriggerTimeout", app_js)
        self.assertIn(
            'usesTriggerTimeout(mode) ? data.get("trigger_timeout_ms") : DEFAULT_TRIGGER_TIMEOUT_MS',
            app_js,
        )
        self.assertIn("trigger_timeout_ms: triggerTimeoutMs(data, triggerMode)", app_js)

    def test_static_ui_scopes_dcv_input_and_trigger_button(self):
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger" / "static"
        index = (static_dir / "index.html").read_text(encoding="utf-8")
        app_js = (static_dir / "app.js").read_text(encoding="utf-8")

        self.assertIn('data-measurement-scope="voltage-dc"', index)
        self.assertIn("measurementScopedControls", app_js)
        self.assertIn("updateTriggerButtonUi", app_js)
        self.assertIn("mode === \"software-custom\"", app_js)
        self.assertIn("mode === \"software\" && !timerActive", app_js)
        self.assertIn("timerIntervalInput.addEventListener", app_js)
        self.assertIn("timerIntervalInput.required = timerEnabled", app_js)
        self.assertIn("Check highlighted run settings before Start", app_js)

    def test_static_ui_exposes_software_queue_and_trigger_metadata(self):
        static_dir = Path(__file__).parents[1] / "src" / "keysight_logger" / "static"
        index = (static_dir / "index.html").read_text(encoding="utf-8")
        app_js = (static_dir / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="sw-queue-max-container"', index)
        self.assertIn('name="sw_queue_max"', index)
        self.assertIn('id="trigger-metadata-container"', index)
        self.assertIn('id="trigger-metadata"', index)
        self.assertIn("swQueueMaxContainer", app_js)
        self.assertIn("payload.sw_queue_max", app_js)
        self.assertIn("function triggerMetadataPayload", app_js)
        self.assertIn("Trigger metadata must be valid JSON object", app_js)


if __name__ == "__main__":
    unittest.main()
