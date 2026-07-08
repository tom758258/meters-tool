from __future__ import annotations

import unittest
from unittest.mock import patch

from meters_tool_core.models import (
    StartRequest,
    find_instrument_profile_by_idn,
    normalize_requested_model,
    supported_instrument_models,
)
from meters_tool_core.start_resolution import (
    DRY_RUN_AUTO_MODEL_ERROR,
    SIMULATE_AUTO_MODEL_ERROR,
    infer_simulator_profile,
    resolve_start_profile,
)


class StartResolutionTests(unittest.TestCase):
    def test_normalize_requested_model_treats_none_and_blank_as_auto(self):
        self.assertIsNone(normalize_requested_model(None))
        self.assertIsNone(normalize_requested_model(""))
        self.assertIsNone(normalize_requested_model("  "))

    def test_normalize_requested_model_accepts_supported_models(self):
        self.assertEqual("34460A", normalize_requested_model("34460A"))
        self.assertEqual("34461A", normalize_requested_model("34461A"))
        self.assertEqual("34460A", normalize_requested_model(" 34460a "))
        self.assertEqual("34461A", normalize_requested_model("34461a"))

    def test_unsupported_model_error_lists_supported_models(self):
        with self.assertRaises(ValueError) as exc:
            normalize_requested_model("BADMODEL")

        message = str(exc.exception)
        self.assertIn("Unsupported instrument model: BADMODEL", message)
        for model in supported_instrument_models():
            self.assertIn(model, message)

    def test_idn_matching_accepts_keysight_and_agilent_supported_aliases(self):
        cases = [
            ("Keysight Technologies,34461A,MY123,1.0", "34461A"),
            ("Keysight Technologies,34460A,MY123,1.0", "34460A"),
            ("Agilent Technologies,34460A,MY123,1.0", "34460A"),
        ]
        for idn, expected_model in cases:
            with self.subTest(idn=idn):
                self.assertEqual(expected_model, find_instrument_profile_by_idn(idn).model)

    def test_unsupported_idn_returns_supported_model_error(self):
        with self.assertRaisesRegex(ValueError, "Unsupported instrument IDN"):
            find_instrument_profile_by_idn("Other Vendor,1234,ABC,1.0")

    def test_infers_only_deterministic_simulator_resource(self):
        self.assertEqual("34460A", infer_simulator_profile("SIM::34460A").model)
        self.assertEqual("34461A", infer_simulator_profile("SIM::34461A").model)
        self.assertIsNone(infer_simulator_profile("SIM::INSTR"))
        self.assertIsNone(infer_simulator_profile("SIM::default"))
        self.assertIsNone(infer_simulator_profile("SIM::34460A::34461A"))
        self.assertIsNone(infer_simulator_profile("USB::34461A"))

    def test_dry_run_omitted_model_rejects_non_deterministic_resource_without_visa(self):
        with (
            patch("meters_tool_core.start_resolution.VisaInstrument.preflight_idn") as preflight,
            self.assertRaisesRegex(ValueError, DRY_RUN_AUTO_MODEL_ERROR),
        ):
            resolve_start_profile(StartRequest(resource="USB::FAKE", dry_run=True))

        preflight.assert_not_called()

    def test_simulate_omitted_model_rejects_non_deterministic_resource(self):
        with self.assertRaisesRegex(ValueError, SIMULATE_AUTO_MODEL_ERROR):
            resolve_start_profile(StartRequest(resource="SIM::INSTR", simulate=True))

    def test_live_omitted_model_resolves_from_idn_preflight(self):
        with patch(
            "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
            return_value="Keysight Technologies,34460A,MY123,1.0",
        ) as preflight:
            request, profile = resolve_start_profile(StartRequest(resource="USB::FAKE"))

        self.assertEqual("34460A", request.instrument_model)
        self.assertEqual("34460A", profile.model)
        preflight.assert_called_once()

    def test_live_explicit_model_mismatch_fails_before_runtime(self):
        with patch(
            "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
            return_value="Keysight Technologies,34460A,MY123,1.0",
        ):
            with self.assertRaisesRegex(
                ValueError,
                "Selected model 34461A does not match the connected instrument IDN 34460A",
            ):
                resolve_start_profile(
                    StartRequest(resource="USB::FAKE", instrument_model="34461A")
                )


if __name__ == "__main__":
    unittest.main()
