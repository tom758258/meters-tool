from __future__ import annotations

import time
import unittest
from urllib import request
from urllib.error import HTTPError

from keysight_logger.trigger import SoftwareTriggerAdapter, TriggerRouter


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
