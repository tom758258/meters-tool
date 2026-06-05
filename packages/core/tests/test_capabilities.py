from __future__ import annotations

import unittest

from keysight_logger_core.models import (
    DEFAULT_INSTRUMENT_PROFILE,
    INSTRUMENT_PROFILES,
    KEYSIGHT_34461A_CAPABILITIES,
    KEYSIGHT_34461A_CURRENT_RANGES,
    KEYSIGHT_34461A_DCV_RANGES,
    KEYSIGHT_34461A_NPLC_OPTIONS,
    KEYSIGHT_34461A_RESISTANCE_RANGES,
    KEYSIGHT_34461A_PROFILE,
    find_instrument_profile_by_idn,
    find_instrument_profile_by_model,
    get_default_instrument_profile,
)


class CapabilitiesTests(unittest.TestCase):
    def test_34461a_capabilities_capture_current_supported_behavior(self):
        capabilities = KEYSIGHT_34461A_CAPABILITIES

        self.assertIs(capabilities, KEYSIGHT_34461A_PROFILE)
        self.assertIs(DEFAULT_INSTRUMENT_PROFILE, KEYSIGHT_34461A_PROFILE)
        self.assertIn(KEYSIGHT_34461A_PROFILE, INSTRUMENT_PROFILES)
        self.assertEqual("Keysight", capabilities.vendor)
        self.assertEqual("34461A", capabilities.model)
        self.assertIn("34461A", capabilities.aliases)
        self.assertEqual(10000, capabilities.reading_memory_limit)
        self.assertEqual(
            (
                "current_dc",
                "voltage_dc",
                "voltage_dc_ratio",
                "current_ac",
                "voltage_ac",
                "resistance_2w",
                "resistance_4w",
            ),
            capabilities.supported_measurement_types,
        )
        self.assertTrue(capabilities.supports_buffered_reading_memory)
        self.assertTrue(capabilities.supports_bus_trigger)
        self.assertTrue(capabilities.supports_external_trigger)
        self.assertFalse(capabilities.supports_sample_timer)

    def test_34461a_profile_exposes_measurement_options(self):
        profile = KEYSIGHT_34461A_PROFILE

        self.assertEqual(
            profile.supported_measurement_types,
            tuple(options.measurement_type for options in profile.measurement_options),
        )
        self.assertEqual(
            KEYSIGHT_34461A_CURRENT_RANGES,
            profile.get_measurement_options("current-dc").range_options,
        )
        self.assertEqual(
            KEYSIGHT_34461A_DCV_RANGES,
            profile.get_measurement_options("voltage-dc").range_options,
        )
        self.assertEqual(
            KEYSIGHT_34461A_DCV_RANGES,
            profile.get_measurement_options("voltage-dc-ratio").range_options,
        )
        self.assertEqual(
            KEYSIGHT_34461A_RESISTANCE_RANGES,
            profile.get_measurement_options("resistance-2w").range_options,
        )
        self.assertEqual(
            KEYSIGHT_34461A_RESISTANCE_RANGES,
            profile.get_measurement_options("resistance-4w").range_options,
        )
        self.assertEqual(
            KEYSIGHT_34461A_NPLC_OPTIONS,
            profile.get_measurement_options("current-dc").nplc_options,
        )
        self.assertEqual(
            KEYSIGHT_34461A_NPLC_OPTIONS,
            profile.get_measurement_options("voltage-dc").nplc_options,
        )
        self.assertEqual(
            KEYSIGHT_34461A_NPLC_OPTIONS,
            profile.get_measurement_options("voltage-dc-ratio").nplc_options,
        )
        self.assertEqual((), profile.get_measurement_options("current-ac").nplc_options)
        self.assertEqual((), profile.get_measurement_options("voltage-ac").nplc_options)

    def test_profile_lookup_defaults_to_34461a(self):
        self.assertIs(get_default_instrument_profile(), KEYSIGHT_34461A_PROFILE)
        self.assertIs(find_instrument_profile_by_model("34461A"), KEYSIGHT_34461A_PROFILE)
        self.assertIs(
            find_instrument_profile_by_idn("Keysight Technologies,34461A,MY123,1.0"),
            KEYSIGHT_34461A_PROFILE,
        )

    def test_unknown_profile_lookup_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported instrument model"):
            find_instrument_profile_by_model("FAKE")

        with self.assertRaisesRegex(ValueError, "Unsupported instrument IDN"):
            find_instrument_profile_by_idn("Vendor,FAKE,123")

        with self.assertRaisesRegex(ValueError, "Unsupported instrument IDN"):
            find_instrument_profile_by_idn("Keysight Technologies,34461AX,MY123,1.0")


if __name__ == "__main__":
    unittest.main()
