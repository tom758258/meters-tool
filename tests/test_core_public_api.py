from __future__ import annotations

import unittest
from pathlib import Path

import keysight_logger.core as core
from keysight_logger.core import (
    InstrumentProfile,
    NoOpControlPlane,
    StartControlPlane,
    StartControlPlaneHandle,
    StartPlan,
    StartRequest,
    StartRunEvent,
    StartRunEventSink,
    StartRunResult,
    StopController,
    build_start_plan,
    generate_buffer_overflow_warnings,
    get_default_instrument_profile,
    resolve_trigger_mode,
    run_start_session,
    validate_start_request,
)


EXPECTED_PUBLIC_API = [
    "InstrumentProfile",
    "StartRequest",
    "get_default_instrument_profile",
    "StartPlan",
    "build_start_plan",
    "generate_buffer_overflow_warnings",
    "resolve_trigger_mode",
    "validate_start_request",
    "StartRunEvent",
    "StartRunEventSink",
    "StartRunResult",
    "StartControlPlane",
    "StartControlPlaneHandle",
    "NoOpControlPlane",
    "StopController",
    "run_start_session",
]


class CorePublicApiTests(unittest.TestCase):
    def test_public_imports_are_available(self):
        imported = {
            "InstrumentProfile": InstrumentProfile,
            "StartRequest": StartRequest,
            "get_default_instrument_profile": get_default_instrument_profile,
            "StartPlan": StartPlan,
            "build_start_plan": build_start_plan,
            "generate_buffer_overflow_warnings": generate_buffer_overflow_warnings,
            "resolve_trigger_mode": resolve_trigger_mode,
            "validate_start_request": validate_start_request,
            "StartRunEvent": StartRunEvent,
            "StartRunEventSink": StartRunEventSink,
            "StartRunResult": StartRunResult,
            "StartControlPlane": StartControlPlane,
            "StartControlPlaneHandle": StartControlPlaneHandle,
            "NoOpControlPlane": NoOpControlPlane,
            "StopController": StopController,
            "run_start_session": run_start_session,
        }

        for name in EXPECTED_PUBLIC_API:
            self.assertIs(imported[name], getattr(core, name))

    def test_all_exactly_matches_minimal_public_api(self):
        self.assertEqual(EXPECTED_PUBLIC_API, core.__all__)

    def test_public_api_builds_valid_dry_run_plan(self):
        request = StartRequest(
            resource="USB::FAKE",
            csv=str(Path("data") / "public_api.csv"),
            dry_run=True,
            trigger_mode="immediate",
            max_samples=1,
        )
        profile = get_default_instrument_profile()
        trigger_mode = resolve_trigger_mode(request)

        validate_start_request(request, trigger_mode, instrument_profile=profile)
        warnings = generate_buffer_overflow_warnings(request, trigger_mode)
        plan = build_start_plan(request, trigger_mode, profile, buffer_warnings=warnings)

        self.assertIsInstance(profile, InstrumentProfile)
        self.assertIsInstance(plan, StartPlan)
        self.assertEqual("immediate", plan.trigger_mode)
        self.assertEqual("current-dc", plan.measurement_name)
        self.assertFalse(hasattr(plan, "measurement_cli" + "_name"))

    def test_old_internal_names_are_not_public_root_exports(self):
        self.assertFalse(hasattr(core, "StartCommandPlan"))
        self.assertFalse(hasattr(core, "print_buffer_overflow_warnings"))


if __name__ == "__main__":
    unittest.main()
