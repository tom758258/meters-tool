from __future__ import annotations

import unittest

from meters_tool_core.models import StartRequest, find_instrument_profile_by_model
from meters_tool_core.validation import supported_trigger_modes, validate_start_request


class ModelProfileValidationTests(unittest.TestCase):
    def profile(self, model: str):
        return find_instrument_profile_by_model(model)

    def assert_validation_error(self, request: StartRequest, message: str) -> None:
        with self.assertRaisesRegex(ValueError, message):
            validate_start_request(
                request,
                request.trigger_mode or "software",
                instrument_profile=self.profile(request.instrument_model or "34461A"),
            )

    def test_34460a_capabilities_exclude_external_trigger_modes(self):
        modes = supported_trigger_modes(self.profile("34460A"))

        self.assertNotIn("external", modes)
        self.assertNotIn("external-custom", modes)
        self.assertIn("software-custom", modes)

    def test_34460a_rejects_external_trigger_modes_at_core_gate(self):
        for trigger_mode in ("external", "external-custom"):
            with self.subTest(trigger_mode=trigger_mode):
                request = StartRequest(
                    resource="SIM::34460A",
                    instrument_model="34460A",
                    simulate=True,
                    trigger_mode=trigger_mode,
                    measurement="current-dc",
                    max_samples=1 if trigger_mode == "external" else None,
                    trigger_count=1 if trigger_mode == "external-custom" else None,
                    sample_count=1 if trigger_mode == "external-custom" else None,
                )

                self.assert_validation_error(
                    request,
                    f"--trigger-mode {trigger_mode} is not supported by 34460A",
                )

    def test_34460a_rejects_current_terminal_and_10a_current_range(self):
        cases = [
            (
                "current-terminal",
                StartRequest(
                    resource="SIM::34460A",
                    instrument_model="34460A",
                    simulate=True,
                    trigger_mode="immediate",
                    measurement="current-dc",
                    max_samples=1,
                    current_terminal=3,
                ),
                "--current-terminal can only be used with --measurement current-dc or current-ac",
            ),
            (
                "10a-range",
                StartRequest(
                    resource="SIM::34460A",
                    instrument_model="34460A",
                    simulate=True,
                    trigger_mode="immediate",
                    measurement="current-dc",
                    max_samples=1,
                    auto_range=False,
                    measurement_range=10.0,
                ),
                "--range 10 is not valid for --measurement current-dc",
            ),
        ]

        for name, request, message in cases:
            with self.subTest(name=name):
                self.assert_validation_error(request, message)

    def test_34460a_rejects_custom_readings_above_memory_without_risk_ack(self):
        request = StartRequest(
            resource="SIM::34460A",
            instrument_model="34460A",
            simulate=True,
            trigger_mode="software-custom",
            measurement="voltage-dc",
            trigger_count=1,
            sample_count=1001,
        )

        self.assert_validation_error(
            request,
            "custom mode expected readings 1001 exceed 34460A reading memory 1000",
        )

    def test_34460a_allows_custom_readings_above_memory_with_risk_ack(self):
        request = StartRequest(
            resource="SIM::34460A",
            instrument_model="34460A",
            simulate=True,
            trigger_mode="software-custom",
            measurement="voltage-dc",
            trigger_count=1,
            sample_count=1001,
            allow_buffer_overflow_risk=True,
        )

        validate_start_request(
            request,
            "software-custom",
            instrument_profile=self.profile("34460A"),
        )

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
