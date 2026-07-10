from __future__ import annotations

from dataclasses import replace
import unittest
from unittest.mock import patch

from meters_tool_core.models import (
    KEYSIGHT_34460A_PROFILE,
    KEYSIGHT_34461A_PROFILE,
    StartRequest,
)
from meters_tool_core.support_policy import (
    BACKEND_PYVISA_PY,
    BACKEND_SYSTEM_VISA,
    FEATURE_KIND_MEASUREMENT,
    FEATURE_KIND_TRIGGER_MODE,
    SUPPORT_POLICY_MODE_PRODUCT,
    SUPPORT_POLICY_MODE_VALIDATION,
    StartFeatureSupportScope,
    StartWorkflowSupport,
    StartWorkflowSupportScope,
    TRANSPORT_TCPIP,
    TRANSPORT_USB,
    VALIDATION_STATUS_FEATURE_PENDING,
    VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE,
    VALIDATION_STATUS_NOT_SUPPORTED_BY_MODEL,
    VALIDATION_STATUS_TRANSPORT_PENDING,
    find_feature_support,
    start_request_feature_requirements,
    start_workflow_support,
    validate_start_workflow_support,
    validate_start_workflow_support_metadata,
)
from meters_tool_core.validation import (
    resolve_trigger_mode,
    supported_measurement_types,
    supported_trigger_modes,
    validate_start_request,
)


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


def make_feature(
    feature_kind: str,
    feature_value: str,
    validation_status: str,
    *,
    evidence: str | None = None,
) -> StartFeatureSupportScope:
    return StartFeatureSupportScope(
        feature_kind,
        feature_value,
        validation_status,
        evidence=evidence,
    )


def make_scope(
    *,
    transport: str = TRANSPORT_USB,
    backend: str = BACKEND_SYSTEM_VISA,
    connection_status: str = VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE,
    measurement_status: str | None = VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE,
    trigger_status: str | None = VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE,
    measurement_evidence: str | None = None,
) -> StartWorkflowSupportScope:
    features = []
    if measurement_status is not None:
        features.append(
            make_feature(
                FEATURE_KIND_MEASUREMENT,
                "voltage_dc",
                measurement_status,
                evidence=measurement_evidence,
            )
        )
    if trigger_status is not None:
        features.append(
            make_feature(FEATURE_KIND_TRIGGER_MODE, "immediate", trigger_status)
        )
    return StartWorkflowSupportScope(
        connection_status,
        transport,
        backend,
        feature_scopes=tuple(features),
    )


def make_live_support(*scopes: StartWorkflowSupportScope) -> StartWorkflowSupport:
    return StartWorkflowSupport(
        VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE,
        transport_scope=TRANSPORT_USB,
        backend_scope=BACKEND_SYSTEM_VISA,
        scopes=tuple(scopes),
    )


class StartSupportPolicyTests(unittest.TestCase):
    def validate_with_support(
        self,
        support: StartWorkflowSupport,
        *,
        request: StartRequest | None = None,
        support_policy_mode: str = SUPPORT_POLICY_MODE_PRODUCT,
    ) -> None:
        effective_request = request or make_request()
        mapping = {"start-trigger-record": {"live": support}}
        with patch(
            "meters_tool_core.support_policy.start_workflow_support",
            return_value=mapping,
        ):
            validate_start_workflow_support(
                effective_request,
                resolve_trigger_mode(effective_request),
                KEYSIGHT_34460A_PROFILE,
                support_policy_mode=support_policy_mode,
            )

    def assert_policy_allows(
        self,
        request: StartRequest,
        profile=KEYSIGHT_34460A_PROFILE,  # noqa: ANN001
        *,
        support_policy_mode: str | None = None,
    ) -> None:
        trigger_mode = resolve_trigger_mode(request)
        validate_start_request(request, trigger_mode, instrument_profile=profile)
        kwargs = {}
        if support_policy_mode is not None:
            kwargs["support_policy_mode"] = support_policy_mode
        validate_start_workflow_support(request, trigger_mode, profile, **kwargs)

    def assert_policy_rejects(
        self,
        request: StartRequest,
        expected: str,
        profile=KEYSIGHT_34460A_PROFILE,  # noqa: ANN001
        *,
        support_policy_mode: str | None = None,
    ) -> None:
        trigger_mode = resolve_trigger_mode(request)
        kwargs = {}
        if support_policy_mode is not None:
            kwargs["support_policy_mode"] = support_policy_mode
        with self.assertRaises(ValueError) as exc:
            validate_start_workflow_support(request, trigger_mode, profile, **kwargs)
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
        usb_features = {
            (feature.feature_kind, feature.feature_value): feature
            for feature in scopes[(TRANSPORT_USB, BACKEND_SYSTEM_VISA)].feature_scopes
        }
        self.assertEqual(
            VALIDATION_STATUS_FEATURE_PENDING,
            usb_features[(FEATURE_KIND_MEASUREMENT, "voltage_dc_ratio")].validation_status,
        )
        self.assertEqual(
            VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE,
            usb_features[(FEATURE_KIND_TRIGGER_MODE, "software-custom")].validation_status,
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
        for scope in scopes.values():
            feature_statuses = {
                feature.validation_status for feature in scope.feature_scopes
            }
            self.assertEqual(
                {VALIDATION_STATUS_LIVE_VALIDATED_FULL_SUITE},
                feature_statuses,
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
        self.assert_policy_rejects(
            make_request(measurement="voltage-dc-ratio"),
            "measurement=voltage-dc-ratio is pending validation",
        )
        self.assert_policy_rejects(
            make_request(resource="TCPIP0::host::inst0::INSTR"),
            "start-trigger-record is pending",
        )
        self.assert_policy_rejects(
            make_request(visa_library="@py"),
            "not registered for transport=usb, backend=pyvisa_py",
        )
        self.assert_policy_rejects(
            make_request(resource="TCPIP::host::INSTR", visa_library="@py"),
            "start-trigger-record is pending",
        )

    def test_validation_mode_allows_known_34460a_pending_lan_scopes(self):
        cases = [
            make_request(resource="TCPIP0::host::inst0::INSTR"),
            make_request(
                resource="TCPIP::host::INSTR",
                visa_library="@py",
                measurement="current-dc",
            ),
        ]

        for request in cases:
            with self.subTest(resource=request.resource, visa_library=request.visa_library):
                self.assert_policy_allows(
                    request,
                    support_policy_mode=SUPPORT_POLICY_MODE_VALIDATION,
                )

    def test_validation_mode_allows_34460a_dcv_ratio_feature_pending(self):
        self.assert_policy_allows(
            make_request(measurement="voltage-dc-ratio"),
            support_policy_mode=SUPPORT_POLICY_MODE_VALIDATION,
        )

    def test_34460a_external_modes_remain_profile_rejected_in_both_policy_modes(self):
        for support_policy_mode in (
            SUPPORT_POLICY_MODE_PRODUCT,
            SUPPORT_POLICY_MODE_VALIDATION,
        ):
            for trigger_mode in ("external", "external-custom"):
                with self.subTest(
                    support_policy_mode=support_policy_mode,
                    trigger_mode=trigger_mode,
                ):
                    request = make_request(
                        trigger_mode=trigger_mode,
                        max_samples=1 if trigger_mode == "external" else None,
                        trigger_count=1 if trigger_mode == "external-custom" else None,
                        sample_count=1 if trigger_mode == "external-custom" else None,
                    )
                    with self.assertRaisesRegex(
                        ValueError,
                        f"--trigger-mode {trigger_mode} is not supported by 34460A",
                    ):
                        validate_start_request(
                            request,
                            resolve_trigger_mode(request),
                            instrument_profile=KEYSIGHT_34460A_PROFILE,
                        )

    def test_validation_mode_does_not_allow_unknown_or_custom_backend_scope(self):
        self.assert_policy_rejects(
            make_request(resource="TCPIP0::host::inst0::INSTR", visa_library="custom"),
            "not registered for transport=tcpip, backend=custom_visa",
            support_policy_mode=SUPPORT_POLICY_MODE_VALIDATION,
        )

    def test_missing_connection_scope_rejects_both_modes(self):
        request = make_request(visa_library="@py")
        for support_policy_mode in (
            SUPPORT_POLICY_MODE_PRODUCT,
            SUPPORT_POLICY_MODE_VALIDATION,
        ):
            with self.subTest(support_policy_mode=support_policy_mode):
                self.assert_policy_rejects(
                    request,
                    "not registered for transport=usb, backend=pyvisa_py",
                    support_policy_mode=support_policy_mode,
                )

    def test_start_request_feature_requirements_use_core_normalized_values(self):
        request = make_request(
            measurement="Voltage-DC",
            trigger_mode="software_custom",
            max_samples=None,
            trigger_count=1,
            sample_count=1,
        )

        self.assertEqual(
            (
                (FEATURE_KIND_MEASUREMENT, "voltage_dc"),
                (FEATURE_KIND_TRIGGER_MODE, "software-custom"),
            ),
            start_request_feature_requirements(request),
        )

    def test_feature_pending_trigger_mode_obeys_product_and_validation_modes(self):
        support = make_live_support(
            make_scope(trigger_status=VALIDATION_STATUS_FEATURE_PENDING)
        )

        with self.assertRaisesRegex(ValueError, "trigger-mode=immediate is pending validation"):
            self.validate_with_support(support)
        self.validate_with_support(
            support,
            support_policy_mode=SUPPORT_POLICY_MODE_VALIDATION,
        )

    def test_transport_pending_requires_validation_mode_and_explicit_pending_features(self):
        support = make_live_support(
            make_scope(
                transport=TRANSPORT_TCPIP,
                connection_status=VALIDATION_STATUS_TRANSPORT_PENDING,
                measurement_status=VALIDATION_STATUS_FEATURE_PENDING,
                trigger_status=VALIDATION_STATUS_FEATURE_PENDING,
            )
        )
        request = make_request(resource="TCPIP0::host::inst0::INSTR")

        with self.assertRaisesRegex(ValueError, "start-trigger-record is pending"):
            self.validate_with_support(support, request=request)
        self.validate_with_support(
            support,
            request=request,
            support_policy_mode=SUPPORT_POLICY_MODE_VALIDATION,
        )

    def test_missing_measurement_and_trigger_feature_entries_reject_both_modes(self):
        cases = [
            (
                make_live_support(make_scope(measurement_status=None)),
                "measurement=voltage-dc",
            ),
            (
                make_live_support(make_scope(trigger_status=None)),
                "trigger-mode=immediate",
            ),
        ]

        for support, expected in cases:
            for support_policy_mode in (
                SUPPORT_POLICY_MODE_PRODUCT,
                SUPPORT_POLICY_MODE_VALIDATION,
            ):
                with self.subTest(
                    expected=expected,
                    support_policy_mode=support_policy_mode,
                ):
                    with self.assertRaisesRegex(
                        ValueError,
                        f"live feature support is not registered for {expected}",
                    ):
                        self.validate_with_support(
                            support,
                            support_policy_mode=support_policy_mode,
                        )

    def test_not_supported_by_model_feature_rejects_both_modes(self):
        supports = (
            make_live_support(
                make_scope(measurement_status=VALIDATION_STATUS_NOT_SUPPORTED_BY_MODEL)
            ),
            make_live_support(
                make_scope(connection_status=VALIDATION_STATUS_NOT_SUPPORTED_BY_MODEL)
            ),
        )

        for support in supports:
            for support_policy_mode in (
                SUPPORT_POLICY_MODE_PRODUCT,
                SUPPORT_POLICY_MODE_VALIDATION,
            ):
                with self.subTest(
                    support=support,
                    support_policy_mode=support_policy_mode,
                ):
                    with self.assertRaisesRegex(ValueError, "not supported by the detected"):
                        self.validate_with_support(
                            support,
                            support_policy_mode=support_policy_mode,
                        )

    def test_unknown_connection_and_feature_statuses_reject_both_modes(self):
        cases = [
            (
                make_live_support(make_scope(connection_status="unknown_connection")),
                "unknown validation status 'unknown_connection'",
            ),
            (
                make_live_support(make_scope(measurement_status="unknown_feature")),
                "unknown validation status 'unknown_feature'",
            ),
        ]

        for support, expected in cases:
            for support_policy_mode in (
                SUPPORT_POLICY_MODE_PRODUCT,
                SUPPORT_POLICY_MODE_VALIDATION,
            ):
                with self.subTest(
                    expected=expected,
                    support_policy_mode=support_policy_mode,
                ):
                    with self.assertRaisesRegex(ValueError, expected):
                        self.validate_with_support(
                            support,
                            support_policy_mode=support_policy_mode,
                        )

    def test_feature_support_is_isolated_by_exact_transport_and_backend_scope(self):
        usb_scope = make_scope(measurement_evidence="usb-system-evidence")
        tcpip_scope = make_scope(
            transport=TRANSPORT_TCPIP,
            measurement_status=VALIDATION_STATUS_FEATURE_PENDING,
        )
        pyvisa_scope = make_scope(
            transport=TRANSPORT_TCPIP,
            backend=BACKEND_PYVISA_PY,
            measurement_status=VALIDATION_STATUS_FEATURE_PENDING,
        )
        support = make_live_support(usb_scope, tcpip_scope, pyvisa_scope)

        usb_feature = find_feature_support(
            usb_scope,
            FEATURE_KIND_MEASUREMENT,
            "voltage-dc",
        )
        tcpip_feature = find_feature_support(
            tcpip_scope,
            FEATURE_KIND_MEASUREMENT,
            "voltage-dc",
        )
        self.assertIsNotNone(usb_feature)
        self.assertEqual("usb-system-evidence", usb_feature.evidence)
        self.assertIsNotNone(tcpip_feature)
        self.assertIsNone(tcpip_feature.evidence)

        for request in (
            make_request(resource="TCPIP0::host::inst0::INSTR"),
            make_request(resource="TCPIP0::host::inst0::INSTR", visa_library="@py"),
        ):
            with self.subTest(visa_library=request.visa_library):
                with self.assertRaisesRegex(
                    ValueError,
                    "measurement=voltage-dc is pending validation",
                ):
                    self.validate_with_support(support, request=request)

        with self.assertRaisesRegex(
            ValueError,
            "not registered for transport=usb, backend=pyvisa_py",
        ):
            self.validate_with_support(
                support,
                request=make_request(visa_library="@py"),
            )

    def test_registered_policy_metadata_is_complete_for_profile_inventories(self):
        for profile in (KEYSIGHT_34460A_PROFILE, KEYSIGHT_34461A_PROFILE):
            with self.subTest(profile=profile.model):
                validate_start_workflow_support_metadata(profile)
                live_support = start_workflow_support(profile)["start-trigger-record"]["live"]
                expected_measurements = set(supported_measurement_types(profile))
                expected_triggers = set(supported_trigger_modes(profile))
                for scope in live_support.scopes:
                    actual_measurements = {
                        feature.feature_value
                        for feature in scope.feature_scopes
                        if feature.feature_kind == FEATURE_KIND_MEASUREMENT
                    }
                    actual_triggers = {
                        feature.feature_value
                        for feature in scope.feature_scopes
                        if feature.feature_kind == FEATURE_KIND_TRIGGER_MODE
                    }
                    self.assertEqual(expected_measurements, actual_measurements)
                    self.assertEqual(expected_triggers, actual_triggers)

    def test_policy_metadata_validation_detects_duplicate_and_unknown_feature_status(self):
        live_support = start_workflow_support(KEYSIGHT_34460A_PROFILE)[
            "start-trigger-record"
        ]["live"]
        usb_scope = live_support.scopes[0]
        duplicate_scope = replace(
            usb_scope,
            feature_scopes=usb_scope.feature_scopes + (usb_scope.feature_scopes[0],),
        )
        duplicate_support = replace(
            live_support,
            scopes=(duplicate_scope, *live_support.scopes[1:]),
        )
        with self.assertRaisesRegex(ValueError, "duplicate live feature support registration"):
            validate_start_workflow_support_metadata(
                KEYSIGHT_34460A_PROFILE,
                duplicate_support,
            )

        unknown_feature = replace(
            usb_scope.feature_scopes[0],
            validation_status="unknown_feature_status",
        )
        unknown_scope = replace(
            usb_scope,
            feature_scopes=(unknown_feature, *usb_scope.feature_scopes[1:]),
        )
        unknown_support = replace(
            live_support,
            scopes=(unknown_scope, *live_support.scopes[1:]),
        )
        with self.assertRaisesRegex(ValueError, "unsupported feature validation status"):
            validate_start_workflow_support_metadata(
                KEYSIGHT_34460A_PROFILE,
                unknown_support,
            )

    def test_policy_metadata_validation_detects_missing_and_unexpected_inventory(self):
        live_support = start_workflow_support(KEYSIGHT_34460A_PROFILE)[
            "start-trigger-record"
        ]["live"]
        usb_scope = live_support.scopes[0]
        missing_scope = replace(
            usb_scope,
            feature_scopes=tuple(
                feature
                for feature in usb_scope.feature_scopes
                if not (
                    feature.feature_kind == FEATURE_KIND_MEASUREMENT
                    and feature.feature_value == "frequency"
                )
            ),
        )
        missing_support = replace(
            live_support,
            scopes=(missing_scope, *live_support.scopes[1:]),
        )
        with self.assertRaisesRegex(ValueError, "missing=frequency"):
            validate_start_workflow_support_metadata(
                KEYSIGHT_34460A_PROFILE,
                missing_support,
            )

        unexpected_scope = replace(
            usb_scope,
            feature_scopes=usb_scope.feature_scopes
            + (
                make_feature(
                    FEATURE_KIND_MEASUREMENT,
                    "capacitance",
                    VALIDATION_STATUS_FEATURE_PENDING,
                ),
            ),
        )
        unexpected_support = replace(
            live_support,
            scopes=(unexpected_scope, *live_support.scopes[1:]),
        )
        with self.assertRaisesRegex(ValueError, "unexpected=capacitance"):
            validate_start_workflow_support_metadata(
                KEYSIGHT_34460A_PROFILE,
                unexpected_support,
            )

    def test_invalid_support_policy_mode_rejects(self):
        request = make_request()
        with self.assertRaisesRegex(ValueError, "unsupported support policy mode"):
            validate_start_workflow_support(
                request,
                resolve_trigger_mode(request),
                KEYSIGHT_34460A_PROFILE,
                support_policy_mode="bad",
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
            (
                make_request(measurement="voltage-dc", nplc=0.1),
                "--nplc 0.1 is not valid",
            ),
            (
                make_request(measurement="voltage-dc", ac_bandwidth_hz=20.0),
                "--ac-bandwidth-hz can only be used",
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
