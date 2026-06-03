import unittest
import threading

from keysight_logger.models import TriggerEvent, TriggerSource
from keysight_logger.trigger import HardwareTriggerAdapter, TriggerRouter


class FakeHardwareInstrument:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.timeout_ms = 0

    def set_timeout_ms(self, timeout_ms: int) -> None:
        self.timeout_ms = timeout_ms

    def write(self, command: str) -> None:
        self.commands.append(command)

    def read_status_byte(self) -> int:
        return 0


class TriggerRouterTests(unittest.TestCase):
    def test_trigger_router_roundtrip(self):
        router = TriggerRouter()
        event = TriggerEvent.new(TriggerSource.SOFTWARE, {"k": "v"})
        router.publish(event)
        got = router.wait(timeout_s=0.1)
        self.assertIsNotNone(got)
        assert got is not None
        self.assertEqual(event.id, got.id)
        self.assertEqual(TriggerSource.SOFTWARE, got.source)


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


if __name__ == "__main__":
    unittest.main()
