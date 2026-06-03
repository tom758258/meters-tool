from __future__ import annotations

import unittest

from keysight_logger.models import KEYSIGHT_34461A_CAPABILITIES


class CapabilitiesTests(unittest.TestCase):
    def test_34461a_capabilities_capture_current_supported_behavior(self):
        capabilities = KEYSIGHT_34461A_CAPABILITIES

        self.assertEqual("34461A", capabilities.model)
        self.assertEqual(10000, capabilities.reading_memory_limit)
        self.assertEqual(("current_dc",), capabilities.supported_measurement_types)
        self.assertTrue(capabilities.supports_buffered_reading_memory)
        self.assertTrue(capabilities.supports_bus_trigger)
        self.assertTrue(capabilities.supports_external_trigger)
        self.assertFalse(capabilities.supports_sample_timer)


if __name__ == "__main__":
    unittest.main()
