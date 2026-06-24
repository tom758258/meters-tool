from __future__ import annotations

import ast
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from keysight_logger_core.models import InstrumentProfile, MeasurementOptions, StartRequest
from keysight_logger_core.validation import (
    CoreWarning,
    generate_buffer_overflow_warning_details,
    generate_buffer_overflow_warnings,
    resolve_csv_path,
    resolve_trigger_mode,
    start_help_epilog,
    validate_client_port,
    validate_start_request,
)


FAKE_CURRENT_ONLY_PROFILE = InstrumentProfile(
    vendor="Fake",
    model="FAKE100",
    aliases=("FAKE100",),
    reading_memory_limit=5,
    supports_buffered_reading_memory=True,
    supports_bus_trigger=True,
    supports_external_trigger=True,
    supports_sample_timer=False,
    measurement_options=(
        MeasurementOptions(
            measurement_type="current_dc",
            range_options=(("500 mA", 0.5),),
            nplc_options=(1.0, 2.0),
        ),
    ),
)


def assert_contains_tokens(testcase: unittest.TestCase, text: str, tokens: tuple[str, ...]) -> None:
    for token in tokens:
        testcase.assertIn(token, text)


def make_start_request(**overrides) -> StartRequest:  # noqa: ANN003
    values = {
        "resource": "USB::FAKE",
        "csv": "out.csv",
        "dry_run": False,
        "simulate": False,
        "timeout_ms": 5000,
        "trigger_timeout_ms": 10000,
        "sw_trigger_port": 8765,
        "sw_min_interval_ms": 0,
        "sw_queue_max": 0,
        "trigger_mode": None,
        "max_samples": None,
        "trigger_count": None,
        "sample_count": None,
        "timer_interval_s": None,
        "buffer_drain_size": None,
        "allow_buffer_overflow_risk": False,
        "hw_trigger_slope": "neg",
        "hw_trigger_delay_s": 0.0,
        "measurement": "current-dc",
        "nplc": 1.0,
        "auto_zero": True,
        "auto_range": True,
        "measurement_range": None,
        "current_range": None,
        "ac_bandwidth_hz": None,
        "gate_time_s": None,
        "freq_period_timeout": None,
        "current_terminal": None,
        "dcv_input_impedance": "default",
        "vm_comp_slope": None,
    }
    values.update(overrides)
    return StartRequest(**values)


class CoreValidationTests(unittest.TestCase):
    def assert_valid(self, request: StartRequest, profile: InstrumentProfile | None = None) -> None:
        validate_start_request(request, resolve_trigger_mode(request), instrument_profile=profile)

    def assert_invalid(
        self,
        request: StartRequest,
        expected: str,
        profile: InstrumentProfile | None = None,
    ) -> None:
        with self.assertRaises(ValueError) as exc:
            validate_start_request(request, resolve_trigger_mode(request), instrument_profile=profile)
        self.assertIn(expected, str(exc.exception))

    def test_csv_path_defaults_to_timestamped_utc_plus_8_data_file(self):
        now = datetime(2026, 5, 11, 6, 30, 5, tzinfo=timezone.utc)

        self.assertEqual(
            Path("data") / "2026-05-11-14-30-05.csv",
            resolve_csv_path(None, now=now),
        )

    def test_csv_path_uses_explicit_path(self):
        self.assertEqual(Path("out.csv"), resolve_csv_path("out.csv"))

    def test_validation_does_not_import_storage(self):
        source = Path("src/keysight_logger_core/validation.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        forbidden_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                forbidden_imports.extend(alias.name for alias in node.names if alias.name.endswith("storage"))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imported_names = {alias.name for alias in node.names}
                if (
                    module in {"storage", ".storage"}
                    or module.endswith(".storage")
                    or (node.level > 0 and "storage" in imported_names)
                    or (module == "keysight_logger_core" and "storage" in imported_names)
                ):
                    forbidden_imports.append(module)

        self.assertEqual([], forbidden_imports)

    def test_trigger_mode_defaults_to_software_without_legacy_cli_alias(self):
        self.assertEqual("software", resolve_trigger_mode(make_start_request()))
        self.assertEqual("external", resolve_trigger_mode(make_start_request(trigger_mode="external")))
        self.assertFalse(hasattr(make_start_request(), "enable_hw_trigger"))

    def test_numeric_limits_accept_boundaries(self):
        cases = [
            ({"timeout_ms": 100}, "software"),
            ({"timeout_ms": 600000}, "software"),
            ({"trigger_timeout_ms": 500}, "software"),
            ({"trigger_timeout_ms": 600000}, "software"),
            ({"sw_trigger_port": 0}, "software"),
            ({"sw_trigger_port": 1024}, "software"),
            ({"sw_trigger_port": 65535}, "software"),
            ({"sw_min_interval_ms": 0}, "software"),
            ({"sw_min_interval_ms": 50}, "software"),
            ({"sw_min_interval_ms": 600000}, "software"),
            ({"sw_queue_max": 0}, "software"),
            ({"sw_queue_max": 10000}, "software"),
            ({"max_samples": 1}, "software"),
            ({"max_samples": 1000000}, "software"),
            ({"timer_interval_s": 0.5}, "software"),
            ({"timer_interval_s": 86400}, "software"),
            ({"hw_trigger_delay_s": 0}, "software"),
            ({"hw_trigger_delay_s": 3600}, "software"),
            (
                {
                    "trigger_mode": "immediate-custom",
                    "trigger_count": 1,
                    "sample_count": 10000,
                    "buffer_drain_size": 1,
                },
                "immediate-custom",
            ),
            (
                {
                    "trigger_mode": "immediate-custom",
                    "trigger_count": 1000000,
                    "sample_count": 1000000,
                    "buffer_drain_size": 10000,
                    "allow_buffer_overflow_risk": True,
                },
                "immediate-custom",
            ),
        ]
        for overrides, expected_mode in cases:
            with self.subTest(overrides=overrides):
                args = make_start_request(**overrides)
                trigger_mode = resolve_trigger_mode(args)
                validate_start_request(args, trigger_mode)
                self.assertEqual(expected_mode, trigger_mode)

    def test_numeric_limits_reject_out_of_range_values(self):
        cases = [
            ({"timeout_ms": 99}, "--timeout-ms 99 is outside the supported range 100-600000"),
            (
                {"trigger_timeout_ms": 100},
                "--trigger-timeout-ms 100 is outside the supported range 500-600000",
            ),
            ({"sw_trigger_port": 1023}, "--sw-trigger-port 1023 is outside the supported values"),
            ({"sw_min_interval_ms": 49}, "--sw-min-interval-ms 49 is outside"),
            ({"sw_queue_max": 10001}, "--sw-queue-max 10001 is outside"),
            ({"max_samples": 1000001}, "--max-samples 1000001 is outside"),
            (
                {"timer_interval_s": 0.01},
                "--timer-interval-s 0.01 is below the supported minimum 0.5 s",
            ),
            (
                {"timer_interval_s": 86400.1},
                "--timer-interval-s 86400.1 is outside the supported range 0.5-86400 s",
            ),
            (
                {"hw_trigger_delay_s": 3600.1},
                "--hw-trigger-delay-s 3600.1 is outside the supported range 0-3600 s",
            ),
            (
                {
                    "trigger_mode": "immediate-custom",
                    "trigger_count": 1000001,
                    "sample_count": 1,
                },
                "--trigger-count 1000001 is outside the 34461A supported range 1-1000000",
            ),
            (
                {
                    "trigger_mode": "immediate-custom",
                    "trigger_count": 1,
                    "sample_count": 1000001,
                },
                "--sample-count 1000001 is outside the 34461A supported range 1-1000000",
            ),
            (
                {
                    "trigger_mode": "immediate-custom",
                    "trigger_count": 1,
                    "sample_count": 1,
                    "buffer_drain_size": 10001,
                },
                "--buffer-drain-size 10001 is outside the 34461A reading-memory range 1-10000",
            ),
        ]
        for overrides, expected in cases:
            with self.subTest(overrides=overrides):
                self.assert_invalid(make_start_request(**overrides), expected)

    def test_client_port_accepts_supported_boundaries(self):
        validate_client_port(1)
        validate_client_port(65535)

    def test_client_port_rejects_out_of_range_values_with_neutral_message(self):
        for port in (0, 65536):
            with self.subTest(port=port):
                with self.assertRaises(ValueError) as exc:
                    validate_client_port(port)

                message = str(exc.exception)
                self.assertIn(
                    f"--port {port} is outside the supported range 1-65535. "
                    "Use a TCP port from 1 to 65535.",
                    message,
                )
                self.assertNotIn("soft-trigger", message)
                self.assertNotIn("soft-stop", message)

    def test_supported_measurement_types_and_profile_constraints(self):
        self.assert_invalid(
            make_start_request(measurement="capacitance"),
            "--measurement must be one of: current-dc, voltage-dc, voltage-dc-ratio, "
            "current-ac, voltage-ac, frequency, period, resistance-2w, resistance-4w",
        )
        self.assert_invalid(
            make_start_request(measurement="voltage-dc"),
            "--measurement must be one of: current-dc",
            profile=FAKE_CURRENT_ONLY_PROFILE,
        )

    def test_range_whitelist_accepts_supported_measurement_options(self):
        cases = [
            ("current-dc", 0.1),
            ("voltage-dc", 10.0),
            ("voltage-dc-ratio", 10.0),
            ("current-ac", 0.1),
            ("voltage-ac", 10.0),
            ("frequency", 10.0),
            ("period", 10.0),
            ("resistance-2w", 1000.0),
            ("resistance-4w", 1000.0),
        ]
        for measurement, measurement_range in cases:
            with self.subTest(measurement=measurement):
                self.assert_valid(
                    make_start_request(
                        measurement=measurement,
                        auto_range=False,
                        measurement_range=measurement_range,
                    )
                )

    def test_range_whitelist_rejects_invalid_range(self):
        self.assert_invalid(
            make_start_request(measurement="voltage-dc", measurement_range=0.2),
            "--range 0.2 is not valid for --measurement voltage-dc",
        )
        self.assert_invalid(
            make_start_request(measurement="current-dc", current_range=0.2),
            "--current-range 0.2 is not valid for --measurement current-dc",
        )

    def test_profile_controls_range_and_nplc_options(self):
        self.assert_valid(
            make_start_request(measurement="current-dc", measurement_range=0.5, nplc=2.0),
            profile=FAKE_CURRENT_ONLY_PROFILE,
        )
        self.assert_invalid(
            make_start_request(measurement="current-dc", measurement_range=0.1),
            "Allowed ranges in A: 0.5",
            profile=FAKE_CURRENT_ONLY_PROFILE,
        )
        self.assert_invalid(
            make_start_request(measurement="current-dc", nplc=0.2),
            "Allowed NPLC values: 1, 2",
            profile=FAKE_CURRENT_ONLY_PROFILE,
        )

    def test_current_range_alias_and_dcv_input_impedance_restrictions(self):
        self.assert_valid(
            make_start_request(auto_range=False, current_range=0.1),
        )
        self.assert_invalid(
            make_start_request(measurement_range=0.1, current_range=0.1),
            "--range and --current-range cannot be used together",
        )
        self.assert_invalid(
            make_start_request(measurement="voltage-dc", current_range=0.1),
            "--current-range can only be used with --measurement current-dc",
        )
        self.assert_valid(
            make_start_request(measurement="voltage-dc", dcv_input_impedance="10m"),
        )
        self.assert_valid(
            make_start_request(measurement="voltage-dc-ratio", dcv_input_impedance="auto"),
        )
        self.assert_invalid(
            make_start_request(measurement="voltage-dc", dcv_input_impedance="highz"),
            "--dcv-input-impedance must be one of: default, 10m, auto",
        )
        self.assert_invalid(
            make_start_request(measurement="current-dc", dcv_input_impedance="auto"),
            "--dcv-input-impedance can only be used with --measurement "
            "voltage-dc or voltage-dc-ratio",
        )

    def test_nplc_whitelist_and_ac_neutral_nplc(self):
        for measurement in [
            "current-dc",
            "voltage-dc",
            "voltage-dc-ratio",
            "resistance-2w",
            "resistance-4w",
        ]:
            with self.subTest(measurement=measurement):
                self.assert_valid(make_start_request(measurement=measurement, nplc=10.0))
                self.assert_invalid(
                    make_start_request(measurement=measurement, nplc=7.5),
                    "Allowed NPLC values: 0.02, 0.2, 1, 10, 100",
                )
        for measurement in ["current-ac", "voltage-ac"]:
            with self.subTest(measurement=measurement):
                self.assert_valid(make_start_request(measurement=measurement, nplc=1.0))
                self.assert_invalid(
                    make_start_request(measurement=measurement, nplc=0.2),
                    "AC measurements do not support NPLC SCPI. Omit --nplc",
                )

    def test_auto_zero_once_scope_and_invalid_strings(self):
        for measurement in ["current-dc", "voltage-dc", "resistance-2w"]:
            with self.subTest(measurement=measurement):
                self.assert_valid(make_start_request(measurement=measurement, auto_zero="once"))
                self.assert_valid(make_start_request(measurement=measurement, auto_zero="ONCE"))
        for measurement in ["current-ac", "voltage-ac", "resistance-4w"]:
            with self.subTest(measurement=measurement):
                self.assert_invalid(
                    make_start_request(measurement=measurement, auto_zero="once"),
                    "--auto-zero once can only be used",
                )
        for auto_zero in [False, "off", "once"]:
            with self.subTest(auto_zero=auto_zero):
                self.assert_invalid(
                    make_start_request(measurement="voltage-dc-ratio", auto_zero=auto_zero),
                    "--auto-zero for --measurement voltage-dc-ratio must be on/default",
                )
        self.assert_valid(make_start_request(measurement="voltage-dc-ratio", auto_zero=True))
        self.assert_valid(make_start_request(measurement="voltage-dc-ratio", auto_zero="ON"))
        self.assert_invalid(
            make_start_request(auto_zero="enabled"),
            "--auto-zero must be one of: on, off, once",
        )

    def test_ac_bandwidth_hz_is_profile_owned(self):
        for measurement, bandwidth in [
            ("current-ac", 3.0),
            ("voltage-ac", 200.0),
            ("frequency", 20.0),
            ("period", 3.0),
        ]:
            with self.subTest(measurement=measurement):
                self.assert_valid(make_start_request(measurement=measurement, ac_bandwidth_hz=bandwidth))
        self.assert_invalid(
            make_start_request(measurement="current-ac", ac_bandwidth_hz=10.0),
            "Allowed AC bandwidth values in Hz: 3, 20, 200",
        )
        self.assert_invalid(
            make_start_request(measurement="current-dc", ac_bandwidth_hz=3.0),
            "--ac-bandwidth-hz can only be used with --measurement current-ac, voltage-ac, "
            "frequency, or period",
        )
        self.assert_invalid(
            make_start_request(measurement="current-dc", ac_bandwidth_hz=3.0),
            "--ac-bandwidth-hz can only be used",
            profile=FAKE_CURRENT_ONLY_PROFILE,
        )

    def test_frequency_period_options_and_scope(self):
        for measurement in ("frequency", "period"):
            with self.subTest(measurement=measurement):
                self.assert_valid(
                    make_start_request(
                        measurement=measurement,
                        gate_time_s=0.1,
                        freq_period_timeout="auto",
                    )
                )
                self.assert_valid(
                    make_start_request(
                        measurement=measurement,
                        gate_time_s=1.0,
                        freq_period_timeout="1s",
                    )
                )
        self.assert_invalid(
            make_start_request(measurement="frequency", gate_time_s=0.5),
            "Allowed gate time values in s: 0.01, 0.1, 1",
        )
        self.assert_invalid(
            make_start_request(measurement="period", freq_period_timeout="2s"),
            "Allowed values: auto, 1s",
        )
        self.assert_invalid(
            make_start_request(measurement="voltage-dc", gate_time_s=0.1),
            "--gate-time-s can only be used with --measurement frequency or period",
        )
        self.assert_invalid(
            make_start_request(measurement="voltage-ac", freq_period_timeout="auto"),
            "--freq-period-timeout can only be used with --measurement frequency or period",
        )

    def test_frequency_period_use_neutral_nplc(self):
        for measurement in ("frequency", "period"):
            with self.subTest(measurement=measurement):
                self.assert_valid(make_start_request(measurement=measurement, nplc=1.0))
                self.assert_invalid(
                    make_start_request(measurement=measurement, nplc=0.2),
                    "Frequency and Period do not support NPLC SCPI",
                )

    def test_current_terminal_scope_and_10a_range_rules(self):
        self.assert_valid(make_start_request(measurement="current-dc", current_terminal=3))
        self.assert_valid(make_start_request(measurement="current-ac", current_terminal=10))
        self.assert_invalid(
            make_start_request(measurement="current-dc", current_terminal=5),
            "Allowed current terminals: 3, 10",
        )
        self.assert_invalid(
            make_start_request(measurement="voltage-dc", current_terminal=3),
            "--current-terminal can only be used with --measurement current-dc or current-ac",
        )
        self.assert_invalid(
            make_start_request(
                measurement="current-dc",
                auto_range=False,
                measurement_range=10.0,
            ),
            "10 A current range requires --current-terminal 10",
        )
        self.assert_invalid(
            make_start_request(
                measurement="current-dc",
                auto_range=False,
                measurement_range=10.0,
                current_terminal=3,
            ),
            "--current-terminal 3 cannot be used with the 10 A current range",
        )
        self.assert_invalid(
            make_start_request(
                measurement="current-dc",
                auto_range=False,
                measurement_range=0.1,
                current_terminal=10,
            ),
            "--current-terminal 10 requires the 10 A current range",
        )
        self.assert_valid(
            make_start_request(
                measurement="current-dc",
                auto_range=False,
                measurement_range=10.0,
                current_terminal=10,
            )
        )

    def test_manual_range_is_required_when_auto_range_is_off(self):
        self.assert_invalid(
            make_start_request(auto_range=False),
            "--range or --current-range is required when --auto-range off",
        )
        self.assert_invalid(
            make_start_request(measurement="voltage-dc", auto_range=False),
            "--range is required when --auto-range off",
        )

    def test_simple_and_custom_mode_exclusivity(self):
        self.assert_invalid(
            make_start_request(trigger_mode="immediate-custom", sample_count=10),
            "--trigger-count is required with custom trigger modes",
        )
        self.assert_invalid(
            make_start_request(trigger_mode="immediate-custom", trigger_count=10),
            "--sample-count is required with custom trigger modes",
        )
        self.assert_invalid(
            make_start_request(
                trigger_mode="immediate-custom",
                trigger_count=1,
                sample_count=10,
                max_samples=10,
            ),
            "--max-samples cannot be used with custom trigger modes",
        )
        self.assert_invalid(
            make_start_request(trigger_mode="immediate", trigger_count=1),
            "--trigger-count requires a custom trigger mode",
        )
        self.assert_invalid(
            make_start_request(trigger_mode="immediate", sample_count=1),
            "--sample-count requires a custom trigger mode",
        )
        self.assert_invalid(
            make_start_request(trigger_mode="immediate", allow_buffer_overflow_risk=True),
            "--allow-buffer-overflow-risk requires a custom trigger mode",
        )

    def test_timer_interval_and_simulate_are_limited_to_supported_simple_modes(self):
        args = make_start_request(timer_interval_s=1.0)
        self.assertEqual("software", resolve_trigger_mode(args))
        self.assert_valid(args)
        self.assert_invalid(
            make_start_request(trigger_mode="external", timer_interval_s=1.0),
            "--timer-interval-s requires --trigger-mode software",
        )
        self.assert_invalid(
            make_start_request(trigger_mode="immediate", simulate=True),
            "--simulate requires --max-samples with simple trigger modes",
            profile=FAKE_CURRENT_ONLY_PROFILE,
        )

    def test_buffer_drain_size_and_overflow_risk(self):
        self.assert_valid(
            make_start_request(
                trigger_mode="immediate-custom",
                trigger_count=2,
                sample_count=100,
                buffer_drain_size=4,
            )
        )
        self.assert_invalid(
            make_start_request(trigger_mode="immediate", max_samples=10, buffer_drain_size=2),
            "--buffer-drain-size requires a custom trigger mode",
        )
        self.assert_invalid(
            make_start_request(
                trigger_mode="immediate-custom",
                trigger_count=1,
                sample_count=10,
                buffer_drain_size=0,
            ),
            "--buffer-drain-size 0 is outside",
        )
        self.assert_invalid(
            make_start_request(
                trigger_mode="immediate-custom",
                trigger_count=1,
                sample_count=5,
                buffer_drain_size=6,
            ),
            "--buffer-drain-size 6 is outside the FAKE100 reading-memory range 1-5",
            profile=FAKE_CURRENT_ONLY_PROFILE,
        )
        self.assert_invalid(
            make_start_request(trigger_mode="immediate-custom", trigger_count=101, sample_count=100),
            "custom mode expected readings 10100 exceed 34461A reading memory 10000",
        )
        self.assert_valid(
            make_start_request(
                trigger_mode="immediate-custom",
                trigger_count=101,
                sample_count=100,
                allow_buffer_overflow_risk=True,
            )
        )
        self.assert_invalid(
            make_start_request(trigger_mode="immediate-custom", trigger_count=3, sample_count=2),
            "custom mode expected readings 6 exceed FAKE100 reading memory 5",
            profile=FAKE_CURRENT_ONLY_PROFILE,
        )

    def test_generate_buffer_overflow_warnings_returns_messages(self):
        args = make_start_request(
            trigger_mode="immediate-custom",
            trigger_count=101,
            sample_count=100,
            allow_buffer_overflow_risk=True,
        )

        stdout = StringIO()
        with redirect_stdout(stdout):
            warnings = generate_buffer_overflow_warnings(args, "immediate-custom")

        self.assertEqual("", stdout.getvalue())
        self.assertEqual(5, len(warnings))
        self.assertIn("requested readings exceed 34461A reading memory", warnings[0])
        self.assertIn("requested=10100, memory_limit=10000", warnings[1])
        self.assertEqual([], generate_buffer_overflow_warnings(make_start_request(), "software"))

    def test_generate_buffer_overflow_warning_details_match_string_helper(self):
        args = make_start_request(
            trigger_mode="software-custom",
            trigger_count=2,
            sample_count=3,
            allow_buffer_overflow_risk=True,
        )

        details = generate_buffer_overflow_warning_details(
            args,
            "software-custom",
            FAKE_CURRENT_ONLY_PROFILE,
        )

        self.assertEqual(
            generate_buffer_overflow_warnings(args, "software-custom", FAKE_CURRENT_ONLY_PROFILE),
            [warning.message for warning in details],
        )
        self.assertEqual(5, len(details))
        self.assertTrue(all(isinstance(warning, CoreWarning) for warning in details))
        self.assertEqual("buffer_overflow_risk", details[0].code)
        self.assertEqual("warning", details[0].severity)
        self.assertEqual(
            {
                "trigger_mode": "software-custom",
                "trigger_count": 2,
                "sample_count": 3,
                "expected_readings": 6,
                "memory_limit": 5,
                "model": "FAKE100",
            },
            details[0].fields,
        )

    def test_start_help_epilog_lists_validation_limits(self):
        help_text = start_help_epilog()

        for tokens in (
            ("NPLC", "DC", "resistance", "0.02", "0.2", "1", "10", "100"),
            ("AC bandwidth", "current", "voltage", "3", "20", "200", "Hz"),
            ("Frequency/Period gate time", "0.01", "0.1", "1", "default"),
            ("Frequency/Period timeout", "auto", "1s", "default"),
            ("current terminal", "current", "3", "10"),
            ("current-dc", "0.0001", "0.001", "0.01", "0.1", "1", "3", "10", "A"),
            ("voltage-dc-ratio", "0.1", "1", "10", "100", "1000", "V"),
            ("--timer-interval-s", "0.5", "86400", "s"),
            ("--trigger-timeout-ms", "500", "600000", "ms"),
            ("--trigger-count", "--sample-count", "1", "1000000"),
        ):
            with self.subTest(tokens=tokens):
                assert_contains_tokens(self, help_text, tokens)

        fake_help = start_help_epilog(FAKE_CURRENT_ONLY_PROFILE)
        assert_contains_tokens(self, fake_help, ("measurement", "current-dc"))
        assert_contains_tokens(self, fake_help, ("current-dc", "0.5", "A"))


if __name__ == "__main__":
    unittest.main()
