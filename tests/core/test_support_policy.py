from __future__ import annotations

import unittest

from meters_tool_core.models import (
    KEYSIGHT_34460A_PROFILE,
    KEYSIGHT_34461A_PROFILE,
    StartRequest,
)
from meters_tool_core.support_policy import (
    BACKEND_PYVISA_PY,
    BACKEND_SYSTEM_VISA,
    TRANSPORT_TCPIP,
    TRANSPORT_USB,
    VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE,
    VALIDATION_STATUS_TRANSPORT_PENDING,
    start_workflow_support,
    validate_start_workflow_support,
)
from meters_tool_core.validation import resolve_trigger_mode, validate_start_request


def make_request(**overrides) -> StartRequest:  # noqa: ANN003
    values = {
        "resource": "USB0::FAKE::INSTR",
        "instrument_model": "34460A",
        "trigger_mode": "immediate",
        "measurement": "voltage-dc",
        "max_samples": 1,
    }
    values.update(overrides)
    return StartRequest(**values)


class StartSupportPolicyTests(unittest.TestCase):
    def assert_policy_allows(self, request: StartRequest, profile=KEYSIGHT_34460A_PROFILE) -> None:  # noqa: ANN001
        trigger_mode = resolve_trigger_mode(request)
        validate_start_request(request, trigger_mode, instrument_profile=profile)
        validate_start_workflow_support(request, trigger_mode, profile)

    def assert_policy_rejects(self, request: StartRequest, expected: str, profile=KEYSIGHT_34460A_PROFILE) -> None:  # noqa: ANN001
        trigger_mode = resolve_trigger_mode(request)
        with self.assertRaises(ValueError) as exc:
            validate_start_workflow_support(request, trigger_mode, profile)
        self.assertIn(expected, str(exc.exception))

    def test_34460a_support_metadata_uses_normalized_status_and_scope(self):
        support = start_workflow_support(KEYSIGHT_34460A_PROFILE)["start-trigger-record"]["live"]

        self.assertEqual(VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE, support.validation_status)
        self.assertEqual(TRANSPORT_USB, support.transport_scope)
        self.assertEqual(BACKEND_SYSTEM_VISA, support.backend_scope)
        self.assertNotEqual("live_validated_full_suite_usb", support.validation_status)
        scopes = {
            (scope.transport_scope, scope.backend_scope): scope
            for scope in support.scopes
        }
        self.assertEqual(
            VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE,
            scopes[(TRANSPORT_USB, BACKEND_SYSTEM_VISA)].validation_status,
        )
        self.assertEqual(
            VALIDATION_STATUS_TRANSPORT_PENDING,
            scopes[(TRANSPORT_TCPIP, BACKEND_SYSTEM_VISA)].validation_status,
        )
        self.assertEqual(
            VALIDATION_STATUS_TRANSPORT_PENDING,
            scopes[(TRANSPORT_TCPIP, BACKEND_PYVISA_PY)].validation_status,
        )

    def test_34461a_support_metadata_promotes_validated_lan_scopes(self):
        support = start_workflow_support(KEYSIGHT_34461A_PROFILE)["start-trigger-record"]["live"]

        self.assertEqual(VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE, support.validation_status)
        self.assertEqual(TRANSPORT_USB, support.transport_scope)
        self.assertEqual(BACKEND_SYSTEM_VISA, support.backend_scope)
        scopes = {
            (scope.transport_scope, scope.backend_scope): scope
            for scope in support.scopes
        }
        self.assertEqual(
            VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE,
            scopes[(TRANSPORT_USB, BACKEND_SYSTEM_VISA)].validation_status,
        )
        lan_system = scopes[(TRANSPORT_TCPIP, BACKEND_SYSTEM_VISA)]
        self.assertEqual(VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE, lan_system.validation_status)
        self.assertEqual("reviewed_artifact_correction", lan_system.evidence)
        self.assertEqual(
            ".tmp_tests/cli_live/keysight-34461a/usb/Full/20260708-211944/summary.md",
            lan_system.artifact,
        )
        lan_pyvisa = scopes[(TRANSPORT_TCPIP, BACKEND_PYVISA_PY)]
        self.assertEqual(VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE, lan_pyvisa.validation_status)
        self.assertEqual("operator_full_suite", lan_pyvisa.evidence)
        self.assertEqual(
            ".tmp_tests/cli_live/keysight-34461a/lan/full/20260709-112406/summary.md",
            lan_pyvisa.artifact,
        )

    def test_34461a_live_representative_full_suite_workflows_are_supported(self):
        cases = [
            make_request(instrument_model="34461A", measurement="current-dc", trigger_mode="immediate", max_samples=1),
            make_request(
                instrument_model="34461A",
                resource="TCPIP0::host::inst0::INSTR",
                measurement="voltage-dc",
                trigger_mode="immediate",
                max_samples=1,
            ),
            make_request(
                instrument_model="34461A",
                resource="TCPIP::host::INSTR",
                visa_library="@py",
                measurement="voltage-dc",
                trigger_mode="immediate",
                max_samples=1,
            ),
            make_request(instrument_model="34461A", measurement="voltage-dc-ratio", trigger_mode="immediate", max_samples=1),
            make_request(instrument_model="34461A", measurement="frequency", trigger_mode="software", max_samples=1),
            make_request(instrument_model="34461A", measurement="period", trigger_mode="immediate", max_samples=1),
            make_request(instrument_model="34461A", measurement="current-dc", trigger_mode="external", max_samples=1),
            make_request(
                instrument_model="34461A",
                measurement="voltage-dc",
                trigger_mode="external-custom",
                max_samples=None,
                trigger_count=1,
                sample_count=1,
            ),
            make_request(
                instrument_model="34461A",
                measurement="current-dc",
                trigger_mode="immediate",
                max_samples=1,
                auto_range=False,
                measurement_range=10.0,
                current_terminal=10,
            ),
        ]

        for request in cases:
            with self.subTest(measurement=request.measurement, trigger_mode=request.trigger_mode):
                self.assert_policy_allows(request, KEYSIGHT_34461A_PROFILE)

    def test_34460a_live_usb_system_visa_full_suite_workflows_are_supported(self):
        cases = [
            make_request(measurement="current-dc", trigger_mode="immediate", max_samples=1),
            make_request(measurement="voltage-dc", trigger_mode="immediate", max_samples=1),
            make_request(measurement="current-ac", trigger_mode="immediate", max_samples=1),
            make_request(measurement="voltage-ac", trigger_mode="immediate", max_samples=1),
            make_request(measurement="resistance-2w", trigger_mode="immediate", max_samples=1),
            make_request(measurement="resistance-4w", trigger_mode="immediate", max_samples=1),
            make_request(measurement="voltage-dc", trigger_mode="software", max_samples=1),
            make_request(
                measurement="voltage-dc",
                trigger_mode="software",
                timer_interval_s=1.0,
                max_samples=1,
            ),
            make_request(
                measurement="voltage-dc",
                trigger_mode="immediate-custom",
                max_samples=None,
                trigger_count=1,
                sample_count=1,
            ),
            make_request(
                measurement="voltage-dc",
                trigger_mode="software-custom",
                max_samples=None,
                trigger_count=1,
                sample_count=1,
            ),
            make_request(measurement="frequency", trigger_mode="immediate", max_samples=1),
            make_request(measurement="period", trigger_mode="immediate", max_samples=1),
        ]

        for request in cases:
            with self.subTest(measurement=request.measurement, trigger_mode=request.trigger_mode):
                self.assert_policy_allows(request)

    def test_34460a_live_rejects_policy_closed_workflows(self):
        for trigger_mode in ("external", "external-custom"):
            with self.subTest(trigger_mode=trigger_mode):
                request = make_request(
                    trigger_mode=trigger_mode,
                    max_samples=1 if trigger_mode == "external" else None,
                    trigger_count=1 if trigger_mode == "external-custom" else None,
                    sample_count=1 if trigger_mode == "external-custom" else None,
                )
                self.assert_policy_rejects(request, f"--trigger-mode {trigger_mode}")

        self.assert_policy_rejects(
            make_request(measurement="voltage-dc-ratio"),
            "--measurement voltage-dc-ratio is not validated",
        )
        self.assert_policy_rejects(
            make_request(resource="TCPIP0::host::inst0::INSTR"),
            "transport=tcpip, backend=system_visa is pending",
        )
        self.assert_policy_rejects(
            make_request(visa_library="@py"),
            "transport=usb, backend=pyvisa_py is pending",
        )
        self.assert_policy_rejects(
            make_request(resource="TCPIP::host::INSTR", visa_library="@py"),
            "transport=tcpip, backend=pyvisa_py is pending",
        )

    def test_34460a_live_still_rejects_hard_profile_limits(self):
        cases = [
            (
                make_request(
                    measurement="current-dc",
                    auto_range=False,
                    measurement_range=10.0,
                ),
                "--range 10 is not valid",
            ),
            (
                make_request(measurement="current-dc", current_terminal=10),
                "--current-terminal can only be used",
            ),
            (
                make_request(
                    trigger_mode="immediate-custom",
                    max_samples=None,
                    trigger_count=1,
                    sample_count=1,
                    buffer_drain_size=1001,
                ),
                "--buffer-drain-size 1001 is outside the 34460A reading-memory range 1-1000",
            ),
        ]

        for request, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaises(ValueError) as exc:
                    validate_start_request(
                        request,
                        resolve_trigger_mode(request),
                        instrument_profile=KEYSIGHT_34460A_PROFILE,
                    )
                self.assertIn(expected, str(exc.exception))

    def test_34460a_dry_run_and_simulate_keep_profile_supported_workflows_open(self):
        for mode_field in ("dry_run", "simulate"):
            with self.subTest(mode=mode_field):
                request = make_request(
                    resource="SIM::34460A",
                    measurement="voltage-dc-ratio",
                    trigger_mode="immediate",
                    max_samples=1,
                    **{mode_field: True},
                )
                trigger_mode = resolve_trigger_mode(request)
                validate_start_request(request, trigger_mode, instrument_profile=KEYSIGHT_34460A_PROFILE)
                validate_start_workflow_support(request, trigger_mode, KEYSIGHT_34460A_PROFILE)

    def test_34460a_dry_run_and_simulate_still_reject_hard_profile_limits(self):
        cases = [
            (
                make_request(
                    dry_run=True,
                    measurement="current-dc",
                    auto_range=False,
                    measurement_range=10.0,
                ),
                "--range 10 is not valid",
            ),
            (
                make_request(dry_run=True, current_terminal=10),
                "--current-terminal can only be used",
            ),
            (
                make_request(
                    simulate=True,
                    trigger_mode="immediate-custom",
                    max_samples=None,
                    trigger_count=1,
                    sample_count=1,
                    buffer_drain_size=1001,
                ),
                "--buffer-drain-size 1001 is outside the 34460A reading-memory range 1-1000",
            ),
        ]

        for request, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaises(ValueError) as exc:
                    validate_start_request(
                        request,
                        resolve_trigger_mode(request),
                        instrument_profile=KEYSIGHT_34460A_PROFILE,
                    )
                self.assertIn(expected, str(exc.exception))


if __name__ == "__main__":
    unittest.main()
