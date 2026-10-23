from __future__ import annotations

import json
import threading
import time
import unittest
from urllib import request
from urllib.error import HTTPError

import pytest

from meters_tool_core.command import CommandValidationError, parse_command_envelope
from meters_tool_core.trigger import SoftwareTriggerAdapter, TriggerRouter


class SoftwareTriggerAdapterTests(unittest.TestCase):
    def _post_command(
        self,
        port: int,
        payload: bytes = b'{"schema_version":3,"command":"software_trigger"}',
    ) -> int:
        req = request.Request(
            f"http://127.0.0.1:{port}/command",
            method="POST",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=1.0) as resp:
                return resp.status
        except HTTPError as err:
            with err:
                err.read()
                return err.code

    def _post_command_json(self, port: int, payload: bytes) -> tuple[int, dict, str]:
        req = request.Request(
            f"http://127.0.0.1:{port}/command",
            method="POST",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            response = request.urlopen(req, timeout=1.0)
        except HTTPError as err:
            response = err
        with response:
            return (
                response.status,
                json.loads(response.read().decode("utf-8")),
                response.headers.get_content_type(),
            )

    def _post_stop(self, port: int) -> int:
        req = request.Request(
            f"http://127.0.0.1:{port}/stop",
            method="POST",
            data=b"{}",
            headers={"Content-Type": "application/json"},
        )
        with request.urlopen(req, timeout=1.0) as resp:
            return resp.status

    def _get_json(self, port: int, path: str = "/status") -> tuple[int, dict]:
        req = request.Request(f"http://127.0.0.1:{port}{path}", method="GET")
        with request.urlopen(req, timeout=1.0) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return resp.status, payload

    def _get_status_code(self, port: int, path: str) -> int:
        req = request.Request(f"http://127.0.0.1:{port}{path}", method="GET")
        try:
            with request.urlopen(req, timeout=1.0) as resp:
                return resp.status
        except HTTPError as err:
            with err:
                err.read()
                return err.code

    def test_status_endpoint_returns_base_json(self):
        router = TriggerRouter()
        server = SoftwareTriggerAdapter(router, port=0, min_interval_ms=0, queue_max=0)
        _, port = server.start()
        try:
            status, payload = self._get_json(port)

            self.assertEqual(200, status)
            self.assertEqual(3, payload["schema_version"])
            self.assertEqual("keysight-meter", payload["service"])
            self.assertEqual("running", payload["status"])
            self.assertEqual(f"http://127.0.0.1:{port}/command", payload["command_url"])
            self.assertEqual(f"http://127.0.0.1:{port}/stop", payload["stop_url"])
            self.assertEqual(f"http://127.0.0.1:{port}/status", payload["status_url"])
            self.assertEqual(0, payload["queue_size"])
            self.assertEqual(TriggerRouter.DEFAULT_MAX_PENDING_EVENTS, payload["queue_max"])
            self.assertEqual(0, payload["min_interval_ms"])
            self.assertIsNone(payload["captured"])
            self.assertIsNone(payload["errors"])
            self.assertIsNone(payload["fatal_error"])
            self.assertTrue(payload["run_id"])
            self.assertFalse(payload["trigger_count_infinite"])
            self.assertEqual("off", payload["overflow_monitoring"])
            self.assertEqual("unknown", payload["data_integrity"])
            self.assertIn("timestamp_utc", payload)
        finally:
            server.stop()

    def test_status_endpoint_includes_limits_queue_size_and_provider_values(self):
        router = TriggerRouter()
        server = SoftwareTriggerAdapter(
            router,
            port=0,
            min_interval_ms=50,
            queue_max=3,
            run_id="run-123",
            status_provider=lambda: {
                "status": "stopping",
                "run_id": "run-123",
                "captured": 2,
                "errors": 1,
                "fatal_error": "capture failed",
                "trigger_count_infinite": True,
                "expected_readings": None,
                "overflow_monitoring": "active",
                "overflow_detected": True,
                "stop_reason": "overflow_detected",
                "final_drain_complete": False,
                "data_integrity": "incomplete",
            },
        )
        _, port = server.start()
        try:
            self.assertEqual(202, self._post_command(port))
            status, payload = self._get_json(port)

            self.assertEqual(200, status)
            self.assertEqual("stopping", payload["status"])
            self.assertEqual(1, payload["queue_size"])
            self.assertEqual(3, payload["queue_max"])
            self.assertEqual(50, payload["min_interval_ms"])
            self.assertEqual(2, payload["captured"])
            self.assertEqual(1, payload["errors"])
            self.assertEqual("capture failed", payload["fatal_error"]["details"]["domain_error"])
            self.assertEqual("failed", payload["worker_state"])
            self.assertEqual("run-123", payload["run_id"])
            self.assertTrue(payload["trigger_count_infinite"])
            self.assertIsNone(payload["expected_readings"])
            self.assertEqual("active", payload["overflow_monitoring"])
            self.assertTrue(payload["overflow_detected"])
            self.assertEqual("overflow_detected", payload["stop_reason"])
            self.assertFalse(payload["final_drain_complete"])
            self.assertEqual("incomplete", payload["data_integrity"])
        finally:
            server.stop()

    def test_status_provider_exception_returns_structured_http_500(self):
        def failing_provider() -> dict[str, object]:
            raise RuntimeError("status unavailable")

        router = TriggerRouter()
        server = SoftwareTriggerAdapter(router, port=0, status_provider=failing_provider)
        _, port = server.start()
        try:
            with self.assertRaises(HTTPError) as raised:
                self._get_json(port)
            with raised.exception as response:
                self.assertEqual(500, response.code)
                payload = json.loads(response.read())
            self.assertEqual(3, payload["schema_version"])
            self.assertEqual("error", payload["status"])
            self.assertEqual("worker", payload["error"]["category"])
            self.assertEqual("status_failed", payload["error"]["code"])
            self.assertTrue(payload["run_id"])
        finally:
            server.stop()

    def test_status_provider_unserializable_data_is_structured_http_500(self):
        router = TriggerRouter()
        server = SoftwareTriggerAdapter(
            router, port=0, status_provider=lambda: {"captured": {1, 2}}
        )
        _, port = server.start()
        try:
            with self.assertRaises(HTTPError) as raised:
                self._get_json(port)
            with raised.exception as response:
                self.assertEqual(500, response.code)
                payload = json.loads(response.read())
            self.assertEqual(3, payload["schema_version"])
            self.assertEqual(server._run_id, payload["run_id"])
            self.assertEqual("error", payload["status"])
            self.assertEqual("worker", payload["error"]["category"])
            self.assertEqual("status_failed", payload["error"]["code"])
        finally:
            server.stop()

    def test_unknown_get_path_returns_404(self):
        router = TriggerRouter()
        server = SoftwareTriggerAdapter(router, port=0)
        _, port = server.start()
        try:
            self.assertEqual(404, self._get_status_code(port, "/unknown"))
        finally:
            server.stop()

    def test_rate_limit_returns_429(self):
        router = TriggerRouter()
        server = SoftwareTriggerAdapter(router, port=0, min_interval_ms=100, queue_max=0)
        _, port = server.start()
        try:
            first = self._post_command(port)
            second = self._post_command(port)
            self.assertEqual(202, first)
            self.assertEqual(429, second)
            time.sleep(0.12)
            third = self._post_command(port)
            self.assertEqual(202, third)
        finally:
            server.stop()

    def test_queue_full_returns_429(self):
        router = TriggerRouter()
        server = SoftwareTriggerAdapter(router, port=0, min_interval_ms=0, queue_max=1)
        _, port = server.start()
        try:
            first = self._post_command(port)
            second = self._post_command(port)
            self.assertEqual(202, first)
            self.assertEqual(429, second)
            event = router.wait(timeout_s=0.1)
            self.assertIsNotNone(event)
            third = self._post_command(port)
            self.assertEqual(202, third)
        finally:
            server.stop()

    def test_command_endpoint_preserves_normalized_metadata(self):
        router = TriggerRouter()
        server = SoftwareTriggerAdapter(router, port=0, min_interval_ms=0, queue_max=0)
        _, port = server.start()
        try:
            status = self._post_command(
                port,
                b'{"schema_version":3,"command":"software_trigger","arguments":{"metadata":{"batch":"A1","count":3,"tags":["x"]}}}',
            )
            self.assertEqual(202, status)
            event = router.wait(timeout_s=0.1)
            self.assertIsNotNone(event)
            assert event is not None
            self.assertEqual({"batch": "A1", "count": "3", "tags": '["x"]'}, event.metadata)
        finally:
            server.stop()

    def test_command_validation_returns_400_and_does_not_publish(self):
        router = TriggerRouter()
        server = SoftwareTriggerAdapter(router, port=0, min_interval_ms=0, queue_max=0)
        _, port = server.start()
        try:
            self.assertEqual(
                400,
                self._post_command(
                    port,
                    b'{"schema_version":1,"command":"software_trigger"}',
                ),
            )
            self.assertIsNone(router.wait(timeout_s=0.01))
        finally:
            server.stop()

    def test_command_responses_use_common_envelope_and_echo_safe_identity(self):
        router = TriggerRouter()
        server = SoftwareTriggerAdapter(router, port=0, min_interval_ms=1000)
        _, port = server.start()
        try:
            accepted = self._post_command_json(
                port, b'{"schema_version":3,"command":"software_trigger","job_id":"job-1"}',
            )
            rejected = self._post_command_json(
                port, b'{"schema_version":3,"command":"software_trigger","job_id":"job-2"}',
            )
            invalid = self._post_command_json(
                port,
                b'{"schema_version":3,"command":"software_trigger","job_id":"job-3","arguments":{"metadata":[]}}',
            )
            invalid_job = self._post_command_json(
                port, b'{"schema_version":3,"command":"software_trigger","job_id":3}',
            )
            self.assertEqual([202, 429, 400, 400], [x[0] for x in
                             (accepted, rejected, invalid, invalid_job)])
            for _, payload, content_type in (accepted, rejected, invalid, invalid_job):
                self.assertEqual("application/json", content_type)
                self.assertEqual(3, payload["schema_version"])
                self.assertEqual(server._run_id, payload["run_id"])
                self.assertIsNone(payload["worker_job_id"])
                self.assertEqual("control", payload["kind"])
            self.assertEqual("accepted", accepted[1]["status"])
            self.assertIsNone(accepted[1]["error"])
            self.assertEqual("job-1", accepted[1]["job_id"])
            self.assertEqual("rejected", rejected[1]["status"])
            self.assertEqual("rate_limited", rejected[1]["reason"])
            self.assertEqual("admission", rejected[1]["error"]["category"])
            self.assertEqual("validation", invalid[1]["error"]["category"])
            self.assertEqual("job-3", invalid[1]["job_id"])
            self.assertIsNone(invalid_job[1]["job_id"])
            self.assertIsNotNone(router.wait(timeout_s=0.01))
            self.assertIsNone(router.wait(timeout_s=0.01))
        finally:
            server.stop()

    def test_stop_ack_is_idempotent_and_invalid_body_is_rejected(self):
        router = TriggerRouter()
        callback_called = threading.Event()
        callbacks = []

        def stop_cb():
            callbacks.append("called")
            callback_called.set()

        server = SoftwareTriggerAdapter(router, port=0, stop_cb=stop_cb)
        _, port = server.start()
        try:
            for body, expected in [
                (b'{"schema_version":2}', 400),
                (b'{"schema_version":3.0}', 400),
                (b'{"schema_version":3e0}', 400),
                (b'{"context":{}}', 400),
                (b'{"reason":5}', 400),
            ]:
                req = request.Request(f"http://127.0.0.1:{port}/stop",
                                      method="POST", data=body)
                with self.assertRaises(HTTPError) as failed:
                    request.urlopen(req, timeout=1)
                self.assertEqual(expected, failed.exception.code)
            self.assertIsNone(router.wait(timeout_s=0.01))
            for _ in range(2):
                req = request.Request(f"http://127.0.0.1:{port}/stop",
                                      method="POST", data=b'{"schema_version":3}')
                with request.urlopen(req, timeout=1) as response:
                    self.assertEqual(202, response.status)
                    ack = json.loads(response.read())
                    self.assertEqual("accepted", ack["status"])
                    self.assertEqual(3, ack["schema_version"])
                    self.assertIsNone(ack["error"])
            self.assertTrue(callback_called.wait(timeout=1))
            self.assertEqual(["called"], callbacks)
            self.assertEqual("stop", router.wait(timeout_s=0.1).metadata["control"])
            self.assertIsNone(router.wait(timeout_s=0.01))
        finally:
            server.stop()

    def test_startup_bound_context_rejected_without_trigger_side_effect(self):
        router = TriggerRouter()
        server = SoftwareTriggerAdapter(router, port=0)
        _, port = server.start()
        try:
            code, data, _ = self._post_command_json(
                port, b'{"schema_version":3,"command":"software_trigger","context":{}}',
            )
            self.assertEqual(400, code)
            self.assertEqual("validation", data["error"]["category"])
            self.assertIsNone(router.wait(timeout_s=0.01))
        finally:
            server.stop()

    def test_trigger_endpoint_returns_404(self):
        router = TriggerRouter()
        server = SoftwareTriggerAdapter(router, port=0, min_interval_ms=0, queue_max=0)
        _, port = server.start()
        try:
            req = request.Request(
                f"http://127.0.0.1:{port}/trigger",
                method="POST",
                data=b"{}",
                headers={"Content-Type": "application/json"},
            )
            with self.assertRaises(HTTPError) as ctx:
                request.urlopen(req, timeout=1.0)
            self.assertEqual(404, ctx.exception.code)
        finally:
            server.stop()

    def test_stop_endpoint_publishes_control_event(self):
        router = TriggerRouter()
        server = SoftwareTriggerAdapter(router, port=0, min_interval_ms=0, queue_max=0)
        _, port = server.start()
        try:
            status = self._post_stop(port)
            self.assertEqual(202, status)
            event = router.wait(timeout_s=0.1)
            self.assertIsNotNone(event)
            assert event is not None
            self.assertEqual("stop", event.metadata.get("control"))
        finally:
            server.stop()

    def test_stop_endpoint_runs_callback_on_background_thread(self):
        router = TriggerRouter()
        callback_called = threading.Event()
        callback_thread_ids = []

        def stop_callback() -> None:
            callback_thread_ids.append(threading.get_ident())
            callback_called.set()

        server = SoftwareTriggerAdapter(
            router,
            port=0,
            min_interval_ms=0,
            queue_max=0,
            stop_cb=stop_callback,
        )
        _, port = server.start()
        request_thread_id = threading.get_ident()
        try:
            self.assertEqual(202, self._post_stop(port))
            self.assertTrue(callback_called.wait(timeout=1.0))
            self.assertNotEqual(request_thread_id, callback_thread_ids[0])

            event = router.wait(timeout_s=0.1)
            self.assertIsNotNone(event)
            assert event is not None
            self.assertEqual("stop", event.metadata.get("control"))
        finally:
            server.stop()

    def test_stop_endpoint_is_accepted_when_trigger_queue_is_full(self):
        router = TriggerRouter(max_pending_events=1)
        server = SoftwareTriggerAdapter(router, port=0, min_interval_ms=0, queue_max=0)
        _, port = server.start()
        try:
            first = self._post_command(port)
            second = self._post_command(port)
            stop = self._post_stop(port)
            self.assertEqual(202, first)
            self.assertEqual(429, second)
            self.assertEqual(202, stop)

            event = router.wait(timeout_s=0.1)
            self.assertIsNotNone(event)
            assert event is not None
            self.assertEqual("stop", event.metadata.get("control"))
        finally:
            server.stop()


_MISSING_SCHEMA_VERSION = object()


@pytest.mark.parametrize(
    "schema_version",
    [_MISSING_SCHEMA_VERSION, 2, "3", 3.0, True],
    ids=["missing", "v1", "string", "float", "boolean"],
)
def test_command_parser_rejects_non_v3_schema_versions(schema_version):
    payload = {"command": "software_trigger"}
    if schema_version is not _MISSING_SCHEMA_VERSION:
        payload["schema_version"] = schema_version

    with pytest.raises(CommandValidationError, match="schema_version must be exact integer 3"):
        parse_command_envelope(payload)


if __name__ == "__main__":
    unittest.main()
