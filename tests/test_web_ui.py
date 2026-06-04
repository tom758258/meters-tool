from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - dependency-gated tests
    TestClient = None

if TestClient is not None:
    from keysight_logger.models import MeasurementSample
    from keysight_logger.web_ui import RunStartRequest, WebRunManager, create_app


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

    def test_run_start_rejects_second_active_run_and_stop_releases_it(self):
        client, csv_path = self.make_client()
        request = {
            "resource": "USB::FAKE",
            "csv": str(csv_path),
            "trigger_mode": "software",
            "trigger_timeout_ms": 50,
        }

        first = client.post("/api/runs", json=request)
        second = client.post("/api/runs", json=request)
        stopped = client.post("/api/runs/current/stop")

        self.assertEqual(200, first.status_code)
        self.assertEqual(409, second.status_code)
        self.assertEqual(202, stopped.status_code)
        self.assertIn(stopped.json()["state"], {"running", "stopping", "stopped"})

    def test_software_trigger_updates_status_and_captures(self):
        client, csv_path = self.make_client()
        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "csv": str(csv_path),
                "trigger_mode": "software",
                "trigger_timeout_ms": 50,
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

    def test_manager_can_build_default_request_model(self):
        request = RunStartRequest(resource="USB::FAKE")

        self.assertEqual("current-dc", request.measurement)
        self.assertTrue(request.auto_zero)


if __name__ == "__main__":
    unittest.main()
