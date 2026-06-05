from __future__ import annotations

import json
import time
import unittest
from urllib import request
from urllib.error import HTTPError

from keysight_logger.core.trigger import SoftwareTriggerAdapter, TriggerRouter


class SoftwareTriggerAdapterTests(unittest.TestCase):
    def _post_trigger(self, port: int, payload: bytes = b"{}") -> int:
        req = request.Request(
            f"http://127.0.0.1:{port}/trigger",
            method="POST",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=1.0) as resp:
                return resp.status
        except HTTPError as err:
            return err.code

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
            return err.code

    def test_status_endpoint_returns_base_json(self):
        router = TriggerRouter()
        server = SoftwareTriggerAdapter(router, port=0, min_interval_ms=0, queue_max=0)
        _, port = server.start()
        try:
            status, payload = self._get_json(port)

            self.assertEqual(200, status)
            self.assertEqual(1, payload["schema_version"])
            self.assertEqual("keysight-meter", payload["service"])
            self.assertEqual("running", payload["status"])
            self.assertEqual(f"http://127.0.0.1:{port}/trigger", payload["trigger_url"])
            self.assertEqual(f"http://127.0.0.1:{port}/stop", payload["stop_url"])
            self.assertEqual(f"http://127.0.0.1:{port}/status", payload["status_url"])
            self.assertEqual(0, payload["queue_size"])
            self.assertEqual(TriggerRouter.DEFAULT_MAX_PENDING_EVENTS, payload["queue_max"])
            self.assertEqual(0, payload["min_interval_ms"])
            self.assertIsNone(payload["captured"])
            self.assertIsNone(payload["errors"])
            self.assertIsNone(payload["fatal_error"])
            self.assertIsNone(payload["run_id"])
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
            status_provider=lambda: {
                "status": "stopping",
                "run_id": "run-123",
                "captured": 2,
                "errors": 1,
                "fatal_error": "capture failed",
            },
        )
        _, port = server.start()
        try:
            self.assertEqual(202, self._post_trigger(port))
            status, payload = self._get_json(port)

            self.assertEqual(200, status)
            self.assertEqual("stopping", payload["status"])
            self.assertEqual(1, payload["queue_size"])
            self.assertEqual(3, payload["queue_max"])
            self.assertEqual(50, payload["min_interval_ms"])
            self.assertEqual(2, payload["captured"])
            self.assertEqual(1, payload["errors"])
            self.assertEqual("capture failed", payload["fatal_error"])
            self.assertEqual("run-123", payload["run_id"])
        finally:
            server.stop()

    def test_status_provider_exception_returns_nullable_dynamic_fields(self):
        def failing_provider() -> dict[str, object]:
            raise RuntimeError("status unavailable")

        router = TriggerRouter()
        server = SoftwareTriggerAdapter(router, port=0, status_provider=failing_provider)
        _, port = server.start()
        try:
            status, payload = self._get_json(port)

            self.assertEqual(200, status)
            self.assertEqual("running", payload["status"])
            self.assertIsNone(payload["captured"])
            self.assertIsNone(payload["errors"])
            self.assertIsNone(payload["fatal_error"])
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
            first = self._post_trigger(port)
            second = self._post_trigger(port)
            self.assertEqual(202, first)
            self.assertEqual(429, second)
            time.sleep(0.12)
            third = self._post_trigger(port)
            self.assertEqual(202, third)
        finally:
            server.stop()

    def test_queue_full_returns_429(self):
        router = TriggerRouter()
        server = SoftwareTriggerAdapter(router, port=0, min_interval_ms=0, queue_max=1)
        _, port = server.start()
        try:
            first = self._post_trigger(port)
            second = self._post_trigger(port)
            self.assertEqual(202, first)
            self.assertEqual(429, second)
            event = router.wait(timeout_s=0.1)
            self.assertIsNotNone(event)
            third = self._post_trigger(port)
            self.assertEqual(202, third)
        finally:
            server.stop()

    def test_trigger_endpoint_preserves_metadata(self):
        router = TriggerRouter()
        server = SoftwareTriggerAdapter(router, port=0, min_interval_ms=0, queue_max=0)
        _, port = server.start()
        try:
            status = self._post_trigger(port, b'{"batch":"A1","count":3}')
            self.assertEqual(202, status)
            event = router.wait(timeout_s=0.1)
            self.assertIsNotNone(event)
            assert event is not None
            self.assertEqual({"batch": "A1", "count": "3"}, event.metadata)
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

    def test_stop_endpoint_is_accepted_when_trigger_queue_is_full(self):
        router = TriggerRouter(max_pending_events=1)
        server = SoftwareTriggerAdapter(router, port=0, min_interval_ms=0, queue_max=0)
        _, port = server.start()
        try:
            first = self._post_trigger(port)
            second = self._post_trigger(port)
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


if __name__ == "__main__":
    unittest.main()
