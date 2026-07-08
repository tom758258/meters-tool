from __future__ import annotations

import unittest
from pathlib import Path

import meters_tool_core as core
from meters_tool_core import (
    CoreCapabilities,
    CoreWarning,
    InstrumentProfile,
    MeasurementCapability,
    NoOpControlPlane,
    StartControlPlane,
    StartControlPlaneHandle,
    StartPlan,
    StartRequest,
    StartRunEvent,
    StartRunEventSink,
    StartRunResult,
    StartWorkflowSupport,
    StopController,
    build_start_plan,
    generate_buffer_overflow_warning_details,
    generate_buffer_overflow_warnings,
    get_core_capabilities,
    get_default_instrument_profile,
    resolve_instrument_profile,
    resolve_trigger_mode,
    run_start_session,
    start_workflow_support,
    validate_start_request,
    validate_start_workflow_support,
)
from meters_tool_core.models import KEYSIGHT_34460A_PROFILE


EXPECTED_PUBLIC_API = {
    "MeasurementCapability",
    "CoreCapabilities",
    "get_core_capabilities",
    "CoreWarning",
    "InstrumentProfile",
    "StartRequest",
    "StartWorkflowSupport",
    "get_default_instrument_profile",
    "resolve_instrument_profile",
    "StartPlan",
    "build_start_plan",
    "generate_buffer_overflow_warning_details",
    "generate_buffer_overflow_warnings",
    "resolve_trigger_mode",
    "validate_start_request",
    "start_workflow_support",
    "validate_start_workflow_support",
    "StartRunEvent",
    "StartRunEventSink",
    "StartRunResult",
    "StartControlPlane",
    "StartControlPlaneHandle",
    "NoOpControlPlane",
    "StopController",
    "run_start_session",
}


class CorePublicApiTests(unittest.TestCase):
    def test_public_imports_are_available(self):
        imported = {
            "MeasurementCapability": MeasurementCapability,
            "CoreCapabilities": CoreCapabilities,
            "get_core_capabilities": get_core_capabilities,
            "CoreWarning": CoreWarning,
            "InstrumentProfile": InstrumentProfile,
            "StartRequest": StartRequest,
            "StartWorkflowSupport": StartWorkflowSupport,
            "get_default_instrument_profile": get_default_instrument_profile,
            "resolve_instrument_profile": resolve_instrument_profile,
            "StartPlan": StartPlan,
            "build_start_plan": build_start_plan,
            "generate_buffer_overflow_warning_details": generate_buffer_overflow_warning_details,
            "generate_buffer_overflow_warnings": generate_buffer_overflow_warnings,
            "resolve_trigger_mode": resolve_trigger_mode,
            "validate_start_request": validate_start_request,
            "start_workflow_support": start_workflow_support,
            "validate_start_workflow_support": validate_start_workflow_support,
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
        self.assertEqual(EXPECTED_PUBLIC_API, set(core.__all__))

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

    def test_public_api_exposes_capabilities_for_adapters(self):
        capabilities = get_core_capabilities()

        self.assertIsInstance(capabilities, CoreCapabilities)
        self.assertEqual("Keysight", capabilities.vendor)
        self.assertEqual("34461A", capabilities.model)
        self.assertEqual(10000, capabilities.reading_memory_limit)
        self.assertEqual(
            (
                "software",
                "immediate",
                "external",
                "immediate-custom",
                "software-custom",
                "external-custom",
            ),
            capabilities.trigger_modes,
        )
        measurements = {
            measurement.measurement_name: measurement
            for measurement in capabilities.measurements
        }
        current_dc = measurements["current-dc"]
        self.assertIsInstance(current_dc, MeasurementCapability)
        self.assertEqual("current-dc", current_dc.measurement_name)
        self.assertEqual("current_dc", current_dc.measurement_type)
        self.assertEqual("A", current_dc.unit)
        self.assertEqual((0.0001, 0.001, 0.01, 0.1, 1.0, 3.0, 10.0), current_dc.range_values)
        self.assertEqual((0.02, 0.2, 1.0, 10.0, 100.0), current_dc.nplc_values)
        self.assertEqual((3, 10), current_dc.current_terminal_values)
        self.assertEqual(("on", "off", "once"), current_dc.auto_zero_values)

        ratio = measurements["voltage-dc-ratio"]
        self.assertEqual(("default", "10m", "auto"), ratio.dcv_input_impedance_values)
        self.assertEqual(("on",), ratio.auto_zero_values)

        frequency = measurements["frequency"]
        self.assertEqual("Hz", frequency.unit)
        self.assertEqual((0.1, 1.0, 10.0, 100.0, 750.0), frequency.range_values)
        self.assertEqual((3.0, 20.0, 200.0), frequency.ac_bandwidth_hz_values)
        self.assertEqual((0.01, 0.1, 1.0), frequency.gate_time_s_values)
        self.assertEqual(("auto", "1s"), frequency.freq_period_timeout_values)
        self.assertTrue(frequency.default_auto_range)
        self.assertEqual(20.0, frequency.default_ac_bandwidth_hz)
        self.assertEqual(0.1, frequency.default_gate_time_s)
        self.assertEqual("auto", frequency.default_freq_period_timeout)

        period = measurements["period"]
        self.assertEqual((), period.freq_period_timeout_values)
        self.assertIsNone(period.default_freq_period_timeout)

    def test_public_api_exposes_34460a_capabilities_for_adapters(self):
        capabilities = get_core_capabilities(KEYSIGHT_34460A_PROFILE)

        self.assertEqual("34460A", capabilities.model)
        self.assertEqual(1000, capabilities.reading_memory_limit)
        self.assertEqual(
            ("software", "immediate", "immediate-custom", "software-custom"),
            capabilities.trigger_modes,
        )
        self.assertIn(
            {"model": "34460A", "vendor": "Keysight"},
            capabilities.available_profiles,
        )
        measurements = {
            measurement.measurement_name: measurement
            for measurement in capabilities.measurements
        }
        self.assertEqual(
            (0.0001, 0.001, 0.01, 0.1, 1.0, 3.0),
            measurements["current-dc"].range_values,
        )
        self.assertEqual((), measurements["current-dc"].current_terminal_values)
        self.assertEqual(
            (0.0001, 0.001, 0.01, 0.1, 1.0, 3.0),
            measurements["current-ac"].range_values,
        )
        self.assertEqual((), measurements["current-ac"].current_terminal_values)

    def test_public_api_exposes_structured_warnings(self):
        request = StartRequest(
            resource="USB::FAKE",
            trigger_mode="immediate-custom",
            trigger_count=101,
            sample_count=100,
            allow_buffer_overflow_risk=True,
        )

        details = generate_buffer_overflow_warning_details(request, "immediate-custom")
        messages = generate_buffer_overflow_warnings(request, "immediate-custom")

        self.assertEqual(messages, [warning.message for warning in details])
        warnings_by_code = {warning.code: warning for warning in details}
        self.assertEqual(
            {
                "buffer_overflow_risk",
                "buffer_overflow_counts",
                "buffer_overflow_drain_rate",
                "buffer_overflow_data_loss",
                "buffer_overflow_validation",
            },
            set(warnings_by_code),
        )
        self.assertTrue(all(warning.severity == "warning" for warning in details))
        self.assertEqual(
            10100,
            warnings_by_code["buffer_overflow_risk"].fields["expected_readings"],
        )

    def test_old_internal_names_are_not_public_root_exports(self):
        self.assertFalse(hasattr(core, "StartCommandPlan"))
        self.assertFalse(hasattr(core, "print_buffer_overflow_warnings"))


if __name__ == "__main__":
    unittest.main()
