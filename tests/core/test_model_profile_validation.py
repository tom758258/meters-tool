from __future__ import annotations

import unittest
from dataclasses import replace

from meters_tool_core.models import (
    KEYSIGHT_34460A_PROFILE,
    KEYSIGHT_34461A_PROFILE,
    StartRequest,
    _validate_instrument_profiles,
    find_instrument_profile_by_model,
)
from meters_tool_core.validation import supported_trigger_modes, validate_start_request


class ModelProfileValidationTests(unittest.TestCase):
    def profile(self, model: str):
        return find_instrument_profile_by_model(model)

    def test_34460a_capabilities_exclude_external_trigger_modes(self):
        modes = supported_trigger_modes(self.profile("34460A"))

        self.assertNotIn("external", modes)
        self.assertNotIn("external-custom", modes)
        self.assertIn("software-custom", modes)

    def test_profile_declarations_have_distinct_model_and_model_id(self):
        self.assertEqual("34461A", KEYSIGHT_34461A_PROFILE.model)
        self.assertEqual("keysight-34461a", KEYSIGHT_34461A_PROFILE.model_id)
        self.assertEqual("34460A", KEYSIGHT_34460A_PROFILE.model)
        self.assertEqual("keysight-34460a", KEYSIGHT_34460A_PROFILE.model_id)

    def test_profile_registry_rejects_duplicate_model_id(self):
        duplicate = replace(
            KEYSIGHT_34460A_PROFILE,
            model_id=KEYSIGHT_34461A_PROFILE.model_id,
        )

        with self.assertRaisesRegex(ValueError, "Duplicate instrument model_id"):
            _validate_instrument_profiles((KEYSIGHT_34461A_PROFILE, duplicate))

    def test_profile_registry_rejects_empty_model_id(self):
        profile = replace(KEYSIGHT_34460A_PROFILE, model_id="")

        with self.assertRaisesRegex(ValueError, "34460A has an empty model_id"):
            _validate_instrument_profiles((profile,))

    def test_profile_registry_rejects_uppercase_model_id(self):
        profile = replace(KEYSIGHT_34460A_PROFILE, model_id="Keysight-34460a")

        with self.assertRaisesRegex(ValueError, "model_id must be lowercase"):
            _validate_instrument_profiles((profile,))

    def test_profile_registry_rejects_malformed_model_id(self):
        profile = replace(KEYSIGHT_34460A_PROFILE, model_id="keysight_34460a")

        with self.assertRaisesRegex(ValueError, "malformed model_id"):
            _validate_instrument_profiles((profile,))

    def test_profile_registry_rejects_duplicate_canonical_model(self):
        duplicate = replace(
            KEYSIGHT_34460A_PROFILE,
            model="34461a",
            model_id="keysight-duplicate-model",
        )

        with self.assertRaisesRegex(ValueError, "Duplicate instrument model"):
            _validate_instrument_profiles((KEYSIGHT_34461A_PROFILE, duplicate))

    def test_profile_registry_rejects_model_id_collision_with_other_model(self):
        profile = replace(KEYSIGHT_34460A_PROFILE, model_id="34461a")

        with self.assertRaisesRegex(
            ValueError,
            "34460A model_id '34461a' conflicts with profile 34461A model '34461A'",
        ):
            _validate_instrument_profiles((KEYSIGHT_34461A_PROFILE, profile))

    def test_profile_registry_rejects_cross_profile_alias_collision(self):
        profile = replace(
            KEYSIGHT_34460A_PROFILE,
            aliases=(*KEYSIGHT_34460A_PROFILE.aliases, "keysight-34461a"),
        )

        with self.assertRaisesRegex(
            ValueError,
            "34460A alias 'keysight-34461a' conflicts with profile 34461A model_id",
        ):
            _validate_instrument_profiles((KEYSIGHT_34461A_PROFILE, profile))

    def test_34461a_validated_profile_behavior_remains_allowed(self):
        cases = [
            StartRequest(
                resource="SIM::34461A",
                instrument_model="34461A",
                simulate=True,
                trigger_mode="external",
                measurement="current-dc",
                max_samples=1,
            ),
            StartRequest(
                resource="SIM::34461A",
                instrument_model="34461A",
                simulate=True,
                trigger_mode="external-custom",
                measurement="current-dc",
                trigger_count=1,
                sample_count=1,
            ),
            StartRequest(
                resource="SIM::34461A",
                instrument_model="34461A",
                simulate=True,
                trigger_mode="immediate",
                measurement="current-dc",
                max_samples=1,
                auto_range=False,
                measurement_range=10.0,
                current_terminal=10,
            ),
        ]

        for request in cases:
            with self.subTest(trigger_mode=request.trigger_mode):
                validate_start_request(
                    request,
                    request.trigger_mode or "software",
                    instrument_profile=self.profile("34461A"),
                )


if __name__ == "__main__":
    unittest.main()
