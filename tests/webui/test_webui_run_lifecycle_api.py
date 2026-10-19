from __future__ import annotations

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
    from meters_tool_core.runner import StartRunnerDependencies
    from meters_tool_webui.web_ui import (
        RunAlreadyActive,
        RunStartRequest,
        WebRunManager,
    )


from webui_test_helpers import (
    cleanup_tempdir,
    make_api_client,
    make_api_client_with_manager,
    wait_until_inactive,
)


@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class WebUiRunLifecycleApiTests(unittest.TestCase):
    def tearDown(self):
        cleanup_tempdir(self)
    def test_run_start_rejects_second_active_run_and_stop_releases_it(self):
        client, csv_path = make_api_client(self)
        request = {
            "resource": "USB::FAKE",
            "instrument_model": "34461A",
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
        self.assertFalse(wait_until_inactive(client)["active"])

    def test_run_start_rejects_second_run_while_active(self):
        tempdir = tempfile.TemporaryDirectory()
        self.tempdir = tempdir
        csv_path = Path(tempdir.name) / "out.csv"
        manager = WebRunManager()
        request = RunStartRequest(
            resource="USB::FAKE",
            instrument_model="34461A",
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

    def test_live_data_retains_latest_5000_samples_until_next_start(self):
        self.tempdir = tempfile.TemporaryDirectory()
        csv_path = Path(self.tempdir.name) / "out.csv"
        manager = WebRunManager()
        client = make_api_client_with_manager(manager)
        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "instrument_model": "34461A",
                "csv": str(csv_path),
                "simulate": True,
                "trigger_mode": "immediate",
                "max_samples": 1,
            },
        )
        self.assertEqual(200, response.status_code)
        initial_status = wait_until_inactive(client, timeout_s=1.0)
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
                "instrument_model": "34461A",
                "csv": str(next_csv_path),
                "simulate": True,
                "trigger_mode": "immediate",
                "max_samples": 1,
            },
        )
        self.assertEqual(200, restarted.status_code)
        restarted_status = wait_until_inactive(client, timeout_s=1.0)

        self.assertEqual(1, restarted_status["captured"])
        self.assertEqual(1, len(restarted_status["recent_samples"]))
        self.assertEqual(1, restarted_status["latest_sample"]["sequence"])

    def test_manager_can_build_default_request_model(self):
        request = RunStartRequest(resource="USB::FAKE")
        request_fields = getattr(RunStartRequest, "model_fields", None)
        if request_fields is None:
            request_fields = RunStartRequest.__fields__

        self.assertEqual("current-dc", request.measurement)
        self.assertTrue(request.csv_enabled)
        self.assertEqual("data", request.csv_format)
        self.assertEqual((), request.csv_time_columns)
        self.assertEqual("on", request.auto_zero)
        self.assertIsNone(request.ac_bandwidth_hz)
        self.assertIsNone(request.gate_time_s)
        self.assertIsNone(request.freq_period_timeout)
        self.assertIsNone(request.current_terminal)
        self.assertNotIn("validation_allow_pending_live_support", request_fields)
        self.assertNotIn("support_policy_mode", request_fields)

        normalized = WebRunManager()._normalize_request_payload(request)
        self.assertTrue(normalized.csv_enabled)
        selected = WebRunManager()._normalize_request_payload(RunStartRequest(
            resource="USB::FAKE", csv_format="full", csv_time_columns=("elapsed", "delta")
        ))
        self.assertEqual("full", selected.csv_format)
        self.assertEqual(("elapsed", "delta"), selected.csv_time_columns)

    def test_manager_normalizes_legacy_auto_zero_booleans(self):
        manager = WebRunManager()

        on_request = manager._normalize_request_payload(
            RunStartRequest(resource="USB::FAKE", auto_zero=True)
        )
        off_request = manager._normalize_request_payload(
            RunStartRequest(resource="USB::FAKE", auto_zero=False)
        )

        self.assertEqual("on", on_request.auto_zero)
        self.assertEqual("off", off_request.auto_zero)

    def test_immediate_run_publishes_final_inactive_status_without_polling(self):
        self.tempdir = tempfile.TemporaryDirectory()
        csv_path = Path(self.tempdir.name) / "csv-only-parent" / "out.csv"

        def fail_storage_factory(*args, **kwargs):  # noqa: ARG001
            self.fail("no-CSV WebUI run must not create CSV storage")

        manager = WebRunManager(
            runner_dependencies=StartRunnerDependencies(
                storage_factory=fail_storage_factory,
            )
        )
        client = make_api_client_with_manager(manager)
        version_before = manager._status_version

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "instrument_model": "34461A",
                "csv": str(csv_path),
                "csv_enabled": False,
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
        self.assertFalse(handle.csv_enabled)
        self.assertIsNone(handle.csv_path)
        self.assertGreater(version_after, version_before)
        self.assertEqual("stopped", status["state"])
        self.assertFalse(status["active"])
        self.assertEqual(1, status["captured"])
        self.assertEqual(0, status["errors"])
        self.assertFalse(status["csv_enabled"])
        self.assertIsNone(status["csv_path"])
        self.assertIsNone(status["fatal_error"])
        self.assertEqual(1, len(status["recent_samples"]))
        self.assertEqual(status["recent_samples"][-1], status["latest_sample"])
        self.assertFalse(csv_path.exists())
        self.assertFalse(csv_path.parent.exists())

        open_response = client.post("/api/runs/current/open-csv")
        self.assertEqual(409, open_response.status_code)
        self.assertEqual("no completed CSV available", open_response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
