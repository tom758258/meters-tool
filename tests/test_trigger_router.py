import unittest

from keysight_logger.models import TriggerEvent, TriggerSource
from keysight_logger.trigger import TriggerRouter


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


if __name__ == "__main__":
    unittest.main()
