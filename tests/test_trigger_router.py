import unittest
import threading

from keysight_logger.models import TriggerEvent, TriggerSource
from keysight_logger.trigger import HardwareTriggerAdapter, TriggerRouter


class FakeHardwareInstrument:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.timeout_ms = 0
        self.abort_count = 0

    def set_timeout_ms(self, timeout_ms: int) -> None:
        self.timeout_ms = timeout_ms

    def write(self, command: str) -> None:
        self.commands.append(command)

    def read_status_byte(self) -> int:
        return 0

    def abort_measurement(self) -> bool:
        self.abort_count += 1
        return True


class TriggerRouterTests(unittest.TestCase):
    def test_trigger_router_roundtrip(self):
        router = TriggerRouter()
        event = TriggerEvent.new(TriggerSource.SOFTWARE, {"k": "v"})
        self.assertTrue(router.publish(event))
        got = router.wait(timeout_s=0.1)
        self.assertIsNotNone(got)
        assert got is not None
        self.assertEqual(event.id, got.id)
        self.assertEqual(TriggerSource.SOFTWARE, got.source)

    def test_trigger_router_rejects_normal_event_when_bounded_queue_is_full(self):
        router = TriggerRouter(max_pending_events=1)
        first = TriggerEvent.new(TriggerSource.SOFTWARE, {"seq": "1"})
        second = TriggerEvent.new(TriggerSource.SOFTWARE, {"seq": "2"})

        self.assertTrue(router.publish(first))
        self.assertFalse(router.publish(second))
        self.assertEqual(1, router.size())

        got = router.wait(timeout_s=0.1)
        self.assertIsNotNone(got)
        assert got is not None
        self.assertEqual(first.id, got.id)

    def test_trigger_router_accepts_stop_control_event_when_normal_queue_is_full(self):
        router = TriggerRouter(max_pending_events=1)
        trigger_event = TriggerEvent.new(TriggerSource.SOFTWARE)
        stop_event = TriggerEvent.new(TriggerSource.SOFTWARE, {"control": "stop"})

        self.assertTrue(router.publish(trigger_event))
        self.assertTrue(router.publish(stop_event))

        got_stop = router.wait(timeout_s=0.1)
        self.assertIsNotNone(got_stop)
        assert got_stop is not None
        self.assertEqual(stop_event.id, got_stop.id)
        self.assertEqual("stop", got_stop.metadata.get("control"))

        got_trigger = router.wait(timeout_s=0.1)
        self.assertIsNotNone(got_trigger)
        assert got_trigger is not None
        self.assertEqual(trigger_event.id, got_trigger.id)


class HardwareTriggerAdapterTests(unittest.TestCase):
    def test_wait_can_be_interrupted_by_stop_event(self):
        instrument = FakeHardwareInstrument()
        adapter = HardwareTriggerAdapter(instrument)  # type: ignore[arg-type]
        stop_event = threading.Event()
        stop_event.set()

        event = adapter.wait_and_read_triggered(
            timeout_ms=5000,
            stop_event=stop_event,
            poll_interval_ms=50,
        )

        self.assertIsNone(event)
        self.assertEqual(["*CLS", "*ESE 1", "INIT", "*OPC"], instrument.commands)

    def test_recover_from_timeout_aborts_and_clears(self):
        instrument = FakeHardwareInstrument()
        adapter = HardwareTriggerAdapter(instrument)  # type: ignore[arg-type]

        adapter.recover_from_timeout()

        self.assertEqual(1, instrument.abort_count)
        self.assertEqual(["*CLS"], instrument.commands)


if __name__ == "__main__":
    unittest.main()
