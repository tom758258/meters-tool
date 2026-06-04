from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from keysight_logger.cli import (
    StopController,
    WindowsConsoleStopHandler,
    WindowsKeyboardStopPoller,
    build_parser,
    cmd_list_resources,
    cmd_start,
    cmd_soft_trigger,
    cmd_soft_stop,
    main,
    print_buffer_overflow_warnings,
    resolve_csv_path,
    resolve_trigger_mode,
    validate_start_args,
)
from keysight_logger.instrument import InstrumentError
from keysight_logger.models import InstrumentProfile, MeasurementOptions


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


class CliArgsTests(unittest.TestCase):
    def test_start_defaults(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
            ]
        )
        self.assertIsNone(args.csv)
        self.assertEqual(1.0, args.nplc)
        self.assertTrue(args.auto_zero)
        self.assertTrue(args.auto_range)
        self.assertEqual(0.0, args.hw_trigger_delay_s)
        self.assertEqual(0, args.sw_min_interval_ms)
        self.assertEqual(0, args.sw_queue_max)
        self.assertEqual("current-dc", args.measurement)
        self.assertIsNone(args.measurement_range)
        self.assertIsNone(args.current_range)
        self.assertEqual("default", args.dcv_input_impedance)
        self.assertIsNone(args.trigger_mode)
        self.assertIsNone(args.max_samples)
        self.assertIsNone(args.trigger_count)
        self.assertIsNone(args.sample_count)
        self.assertIsNone(args.timer_interval_s)
        self.assertIsNone(args.buffer_drain_size)
        self.assertFalse(args.allow_buffer_overflow_risk)
        self.assertIsNone(args.vm_comp_slope)

    def test_simulate_requires_max_samples_for_simple_modes(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--simulate",
                "--trigger-mode",
                "immediate",
            ]
        )

        with self.assertRaisesRegex(ValueError, "--simulate requires --max-samples"):
            validate_start_args(args, "immediate", instrument_profile=FAKE_CURRENT_ONLY_PROFILE)

    def test_start_help_lists_cli_limits(self):
        parser = build_parser()
        stdout = io.StringIO()

        with self.assertRaises(SystemExit) as exc, redirect_stdout(stdout):
            parser.parse_args(["start-trigger-record", "--help"])

        self.assertEqual(0, exc.exception.code)
        help_text = stdout.getvalue()
        self.assertIn("NPLC choices for DC/resistance: 0.02, 0.2, 1, 10, 100", help_text)
        self.assertIn("current-dc: 0.0001, 0.001, 0.01, 0.1, 1, 3, 10 A", help_text)
        self.assertIn("--timer-interval-s: 0.5-86400 s", help_text)
        self.assertIn("--trigger-timeout-ms: 500-600000 ms", help_text)
        self.assertIn("--trigger-count/--sample-count: 1-1000000", help_text)

    def test_numeric_limits_accept_boundaries(self):
        parser = build_parser()
        cases = [
            (["--timeout-ms", "100"], "software"),
            (["--timeout-ms", "600000"], "software"),
            (["--trigger-timeout-ms", "500"], "software"),
            (["--trigger-timeout-ms", "600000"], "software"),
            (["--sw-trigger-port", "0"], "software"),
            (["--sw-trigger-port", "1024"], "software"),
            (["--sw-trigger-port", "65535"], "software"),
            (["--sw-min-interval-ms", "0"], "software"),
            (["--sw-min-interval-ms", "50"], "software"),
            (["--sw-min-interval-ms", "600000"], "software"),
            (["--sw-queue-max", "0"], "software"),
            (["--sw-queue-max", "10000"], "software"),
            (["--max-samples", "1"], "software"),
            (["--max-samples", "1000000"], "software"),
            (["--timer-interval-s", "0.5"], "software"),
            (["--timer-interval-s", "86400"], "software"),
            (["--hw-trigger-delay-s", "0"], "software"),
            (["--hw-trigger-delay-s", "3600"], "software"),
            (
                [
                    "--trigger-mode",
                    "immediate-custom",
                    "--trigger-count",
                    "1",
                    "--sample-count",
                    "10000",
                    "--buffer-drain-size",
                    "1",
                ],
                "immediate-custom",
            ),
            (
                [
                    "--trigger-mode",
                    "immediate-custom",
                    "--trigger-count",
                    "1000000",
                    "--sample-count",
                    "1000000",
                    "--buffer-drain-size",
                    "10000",
                    "--allow-buffer-overflow-risk",
                ],
                "immediate-custom",
            ),
        ]
        for extra_args, expected_mode in cases:
            with self.subTest(extra_args=extra_args):
                args = parser.parse_args(["start-trigger-record", "--resource", "USB::FAKE", *extra_args])
                trigger_mode = resolve_trigger_mode(args)
                validate_start_args(args, trigger_mode)
                self.assertEqual(expected_mode, trigger_mode)

    def test_numeric_limits_reject_out_of_range_values(self):
        parser = build_parser()
        cases = [
            (["--timeout-ms", "99"], "--timeout-ms 99 is outside the supported range 100-600000"),
            (
                ["--trigger-timeout-ms", "100"],
                "--trigger-timeout-ms 100 is outside the supported range 500-600000",
            ),
            (
                ["--sw-trigger-port", "1023"],
                "--sw-trigger-port 1023 is outside the supported values",
            ),
            (
                ["--sw-min-interval-ms", "49"],
                "--sw-min-interval-ms 49 is outside the supported values",
            ),
            (["--sw-queue-max", "10001"], "--sw-queue-max 10001 is outside"),
            (["--max-samples", "1000001"], "--max-samples 1000001 is outside"),
            (
                ["--timer-interval-s", "0.01"],
                "--timer-interval-s 0.01 is below the supported minimum 0.5 s",
            ),
            (
                ["--timer-interval-s", "86400.1"],
                "--timer-interval-s 86400.1 is outside the supported range 0.5-86400 s",
            ),
            (
                ["--hw-trigger-delay-s", "3600.1"],
                "--hw-trigger-delay-s 3600.1 is outside the supported range 0-3600 s",
            ),
            (
                ["--trigger-mode", "immediate-custom", "--trigger-count", "1000001", "--sample-count", "1"],
                "--trigger-count 1000001 is outside the 34461A supported range 1-1000000",
            ),
            (
                ["--trigger-mode", "immediate-custom", "--trigger-count", "1", "--sample-count", "1000001"],
                "--sample-count 1000001 is outside the 34461A supported range 1-1000000",
            ),
            (
                [
                    "--trigger-mode",
                    "immediate-custom",
                    "--trigger-count",
                    "1",
                    "--sample-count",
                    "1",
                    "--buffer-drain-size",
                    "10001",
                ],
                "--buffer-drain-size 10001 is outside the 34461A reading-memory range 1-10000",
            ),
        ]
        for extra_args, expected in cases:
            with self.subTest(extra_args=extra_args):
                args = parser.parse_args(["start-trigger-record", "--resource", "USB::FAKE", *extra_args])
                with self.assertRaisesRegex(ValueError, expected):
                    validate_start_args(args, resolve_trigger_mode(args))

    def test_csv_path_defaults_to_timestamped_data_file(self):
        now = datetime(2026, 5, 11, 6, 30, 5, tzinfo=timezone.utc)

        self.assertEqual(
            Path("data") / "2026-05-11-14-30-05.csv",
            resolve_csv_path(None, now=now),
        )

    def test_csv_path_uses_explicit_path(self):
        self.assertEqual(Path("out.csv"), resolve_csv_path("out.csv"))

    def test_start_with_manual_options(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--auto-range",
                "off",
                "--current-range",
                "0.1",
                "--auto-zero",
                "off",
                "--nplc",
                "0.2",
                "--hw-trigger-delay-s",
                "1.5",
                "--sw-min-interval-ms",
                "50",
                "--sw-queue-max",
                "5",
                "--trigger-mode",
                "immediate",
                "--max-samples",
                "10",
                "--vm-comp-slope",
                "pos",
            ]
        )
        self.assertFalse(args.auto_range)
        self.assertIsNone(args.measurement_range)
        self.assertEqual(0.1, args.current_range)
        self.assertFalse(args.auto_zero)
        self.assertEqual(0.2, args.nplc)
        self.assertEqual(1.5, args.hw_trigger_delay_s)
        self.assertEqual(50, args.sw_min_interval_ms)
        self.assertEqual(5, args.sw_queue_max)
        self.assertEqual("immediate", args.trigger_mode)
        self.assertEqual(10, args.max_samples)
        self.assertEqual("pos", args.vm_comp_slope)

    def test_range_is_accepted_with_auto_range_off(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--measurement",
                "current-dc",
                "--auto-range",
                "off",
                "--range",
                "0.1",
            ]
        )

        validate_start_args(args, resolve_trigger_mode(args))

        self.assertEqual("current-dc", args.measurement)
        self.assertEqual(0.1, args.measurement_range)
        self.assertIsNone(args.current_range)

    def test_current_range_alias_is_accepted_with_auto_range_off(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--auto-range",
                "off",
                "--current-range",
                "0.1",
            ]
        )

        validate_start_args(args, resolve_trigger_mode(args))

        self.assertIsNone(args.measurement_range)
        self.assertEqual(0.1, args.current_range)

    def test_range_and_current_range_conflict(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--range",
                "0.1",
                "--current-range",
                "0.1",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--range and --current-range cannot be used together",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_unsupported_measurement_is_rejected(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--measurement",
                "capacitance",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            (
                "--measurement must be one of: current-dc, voltage-dc, "
                "current-ac, voltage-ac, resistance-2w, resistance-4w"
            ),
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_profile_controls_supported_measurements(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--measurement",
                "voltage-dc",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--measurement must be one of: current-dc",
        ):
            validate_start_args(
                args,
                resolve_trigger_mode(args),
                instrument_profile=FAKE_CURRENT_ONLY_PROFILE,
            )

    def test_profile_controls_measurement_range_validation(self):
        parser = build_parser()

        accepted = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--measurement",
                "current-dc",
                "--range",
                "0.5",
            ]
        )
        validate_start_args(
            accepted,
            resolve_trigger_mode(accepted),
            instrument_profile=FAKE_CURRENT_ONLY_PROFILE,
        )

        rejected = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--measurement",
                "current-dc",
                "--range",
                "0.1",
            ]
        )
        with self.assertRaisesRegex(ValueError, "Allowed ranges in A: 0.5"):
            validate_start_args(
                rejected,
                resolve_trigger_mode(rejected),
                instrument_profile=FAKE_CURRENT_ONLY_PROFILE,
            )

    def test_profile_controls_nplc_validation(self):
        parser = build_parser()

        accepted = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--measurement",
                "current-dc",
                "--nplc",
                "2.0",
            ]
        )
        validate_start_args(
            accepted,
            resolve_trigger_mode(accepted),
            instrument_profile=FAKE_CURRENT_ONLY_PROFILE,
        )

        rejected = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--measurement",
                "current-dc",
                "--nplc",
                "0.2",
            ]
        )
        with self.assertRaisesRegex(ValueError, "Allowed NPLC values: 1, 2"):
            validate_start_args(
                rejected,
                resolve_trigger_mode(rejected),
                instrument_profile=FAKE_CURRENT_ONLY_PROFILE,
            )

    def test_voltage_dc_range_is_accepted_with_auto_range_off(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--measurement",
                "voltage-dc",
                "--auto-range",
                "off",
                "--range",
                "10",
            ]
        )

        validate_start_args(args, resolve_trigger_mode(args))

        self.assertEqual("voltage-dc", args.measurement)
        self.assertEqual(10.0, args.measurement_range)

    def test_voltage_dc_allows_range_with_auto_range_on(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--measurement",
                "voltage-dc",
                "--auto-range",
                "on",
                "--range",
                "10",
            ]
        )

        validate_start_args(args, resolve_trigger_mode(args))

        self.assertEqual(10.0, args.measurement_range)

    def test_voltage_dc_rejects_current_range_alias(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--measurement",
                "voltage-dc",
                "--current-range",
                "0.1",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--current-range can only be used with --measurement current-dc",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_voltage_dc_requires_range_when_auto_range_off(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--measurement",
                "voltage-dc",
                "--auto-range",
                "off",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--range is required when --auto-range off",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_voltage_dc_accepts_dcv_input_impedance(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--measurement",
                "voltage-dc",
                "--dcv-input-impedance",
                "10M",
            ]
        )

        validate_start_args(args, resolve_trigger_mode(args))

        self.assertEqual("10m", args.dcv_input_impedance)

    def test_dcv_input_impedance_rejects_non_voltage_dc_measurement(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--measurement",
                "current-dc",
                "--dcv-input-impedance",
                "auto",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--dcv-input-impedance can only be used with --measurement voltage-dc",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_current_ac_range_is_accepted_with_auto_range_off(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--measurement",
                "current-ac",
                "--auto-range",
                "off",
                "--range",
                "0.1",
            ]
        )

        validate_start_args(args, resolve_trigger_mode(args))

        self.assertEqual("current-ac", args.measurement)
        self.assertEqual(0.1, args.measurement_range)

    def test_current_ac_rejects_current_range_alias(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--measurement",
                "current-ac",
                "--current-range",
                "0.1",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--current-range can only be used with --measurement current-dc",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_current_ac_requires_range_when_auto_range_off(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--measurement",
                "current-ac",
                "--auto-range",
                "off",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--range is required when --auto-range off",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_voltage_ac_range_is_accepted_with_auto_range_off(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--measurement",
                "voltage-ac",
                "--auto-range",
                "off",
                "--range",
                "10",
            ]
        )

        validate_start_args(args, resolve_trigger_mode(args))

        self.assertEqual("voltage-ac", args.measurement)
        self.assertEqual(10.0, args.measurement_range)

    def test_voltage_ac_rejects_current_range_alias(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--measurement",
                "voltage-ac",
                "--current-range",
                "0.1",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--current-range can only be used with --measurement current-dc",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_voltage_ac_requires_range_when_auto_range_off(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--measurement",
                "voltage-ac",
                "--auto-range",
                "off",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--range is required when --auto-range off",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_resistance_2w_range_is_accepted_with_auto_range_off(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--measurement",
                "resistance-2w",
                "--auto-range",
                "off",
                "--range",
                "1000",
            ]
        )

        validate_start_args(args, resolve_trigger_mode(args))

        self.assertEqual("resistance-2w", args.measurement)
        self.assertEqual(1000.0, args.measurement_range)

    def test_resistance_2w_allows_range_with_auto_range_on(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--measurement",
                "resistance-2w",
                "--auto-range",
                "on",
                "--range",
                "1000",
            ]
        )

        validate_start_args(args, resolve_trigger_mode(args))

        self.assertEqual(1000.0, args.measurement_range)

    def test_resistance_2w_rejects_current_range_alias(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--measurement",
                "resistance-2w",
                "--current-range",
                "0.1",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--current-range can only be used with --measurement current-dc",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_resistance_2w_requires_range_when_auto_range_off(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--measurement",
                "resistance-2w",
                "--auto-range",
                "off",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--range is required when --auto-range off",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_resistance_4w_range_is_accepted_with_auto_range_off(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--measurement",
                "resistance-4w",
                "--auto-range",
                "off",
                "--range",
                "1000",
            ]
        )

        validate_start_args(args, resolve_trigger_mode(args))

        self.assertEqual("resistance-4w", args.measurement)
        self.assertEqual(1000.0, args.measurement_range)

    def test_resistance_4w_allows_range_with_auto_range_on(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--measurement",
                "resistance-4w",
                "--auto-range",
                "on",
                "--range",
                "1000",
            ]
        )

        validate_start_args(args, resolve_trigger_mode(args))

        self.assertEqual(1000.0, args.measurement_range)

    def test_resistance_4w_rejects_current_range_alias(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--measurement",
                "resistance-4w",
                "--current-range",
                "0.1",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--current-range can only be used with --measurement current-dc",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_resistance_4w_requires_range_when_auto_range_off(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--measurement",
                "resistance-4w",
                "--auto-range",
                "off",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--range is required when --auto-range off",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_manual_range_is_required_when_auto_range_off(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--auto-range",
                "off",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--range or --current-range is required when --auto-range off",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_measurement_range_whitelist_accepts_each_measurement_options(self):
        parser = build_parser()
        cases = {
            "current-dc": ["0.0001", "0.001", "0.01", "0.1", "1", "3", "10"],
            "current-ac": ["0.0001", "0.001", "0.01", "0.1", "1", "3", "10"],
            "voltage-dc": ["0.1", "1", "10", "100", "1000"],
            "voltage-ac": ["0.1", "1", "10", "100", "750"],
            "resistance-2w": ["100", "1000", "10000", "100000", "1000000", "10000000", "100000000"],
            "resistance-4w": ["100", "1000", "10000", "100000", "1000000", "10000000", "100000000"],
        }

        for measurement, range_values in cases.items():
            for range_value in range_values:
                with self.subTest(measurement=measurement, range_value=range_value):
                    args = parser.parse_args(
                        [
                            "start-trigger-record",
                            "--resource",
                            "USB::FAKE",
                            "--measurement",
                            measurement,
                            "--range",
                            range_value,
                        ]
                    )
                    validate_start_args(args, resolve_trigger_mode(args))

    def test_measurement_range_whitelist_rejects_invalid_range(self):
        parser = build_parser()
        cases = [
            ("current-dc", "7.5", "Allowed ranges in A: 0.0001, 0.001, 0.01, 0.1, 1, 3, 10"),
            ("voltage-dc", "7.5", "Allowed ranges in V: 0.1, 1, 10, 100, 1000"),
            ("voltage-ac", "1000", "Allowed ranges in V: 0.1, 1, 10, 100, 750"),
            (
                "resistance-2w",
                "7.5",
                "Allowed ranges in Ohm: 100, 1000, 10000, 100000, 1000000, 10000000, 100000000",
            ),
        ]

        for measurement, range_value, expected in cases:
            with self.subTest(measurement=measurement, range_value=range_value):
                args = parser.parse_args(
                    [
                        "start-trigger-record",
                        "--resource",
                        "USB::FAKE",
                        "--measurement",
                        measurement,
                        "--range",
                        range_value,
                    ]
                )
                with self.assertRaisesRegex(ValueError, expected):
                    validate_start_args(args, resolve_trigger_mode(args))

    def test_dc_and_resistance_nplc_whitelist_rejects_invalid_value(self):
        parser = build_parser()
        for measurement in ["current-dc", "voltage-dc", "resistance-2w", "resistance-4w"]:
            with self.subTest(measurement=measurement):
                args = parser.parse_args(
                    [
                        "start-trigger-record",
                        "--resource",
                        "USB::FAKE",
                        "--measurement",
                        measurement,
                        "--nplc",
                        "7.5",
                    ]
                )
                with self.assertRaisesRegex(
                    ValueError,
                    "--nplc 7.5 is not valid.*Allowed NPLC values: 0.02, 0.2, 1, 10, 100",
                ):
                    validate_start_args(args, resolve_trigger_mode(args))

    def test_ac_measurements_accept_only_neutral_nplc(self):
        parser = build_parser()
        for measurement in ["current-ac", "voltage-ac"]:
            with self.subTest(measurement=measurement):
                args = parser.parse_args(
                    [
                        "start-trigger-record",
                        "--resource",
                        "USB::FAKE",
                        "--measurement",
                        measurement,
                        "--nplc",
                        "1.0",
                    ]
                )
                validate_start_args(args, resolve_trigger_mode(args))

                args = parser.parse_args(
                    [
                        "start-trigger-record",
                        "--resource",
                        "USB::FAKE",
                        "--measurement",
                        measurement,
                        "--nplc",
                        "0.2",
                    ]
                )
                with self.assertRaisesRegex(
                    ValueError,
                    "AC measurements do not support NPLC SCPI. Omit --nplc",
                ):
                    validate_start_args(args, resolve_trigger_mode(args))

    def test_immediate_custom_requires_trigger_count(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate-custom",
                "--sample-count",
                "10",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--trigger-count is required with custom trigger modes",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_immediate_custom_requires_sample_count(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate-custom",
                "--trigger-count",
                "10",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--sample-count is required with custom trigger modes",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_immediate_custom_rejects_max_samples(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate-custom",
                "--trigger-count",
                "1",
                "--sample-count",
                "10",
                "--max-samples",
                "10",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--max-samples cannot be used with custom trigger modes",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_immediate_custom_rejects_more_than_34461a_memory_without_override(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate-custom",
                "--trigger-count",
                "101",
                "--sample-count",
                "100",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "custom mode expected readings 10100 exceed 34461A reading memory 10000",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_custom_mode_memory_limit_comes_from_profile(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate-custom",
                "--trigger-count",
                "3",
                "--sample-count",
                "2",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "custom mode expected readings 6 exceed FAKE100 reading memory 5",
        ):
            validate_start_args(
                args,
                resolve_trigger_mode(args),
                instrument_profile=FAKE_CURRENT_ONLY_PROFILE,
            )

    def test_immediate_custom_accepts_overflow_override(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate-custom",
                "--trigger-count",
                "101",
                "--sample-count",
                "100",
                "--allow-buffer-overflow-risk",
            ]
        )

        trigger_mode = resolve_trigger_mode(args)
        validate_start_args(args, trigger_mode)

        self.assertEqual("immediate-custom", trigger_mode)
        self.assertTrue(args.allow_buffer_overflow_risk)

    def test_immediate_custom_accepts_instrument_counts(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate-custom",
                "--trigger-count",
                "2",
                "--sample-count",
                "100",
                "--buffer-drain-size",
                "4",
            ]
        )

        trigger_mode = resolve_trigger_mode(args)
        validate_start_args(args, trigger_mode)

        self.assertEqual("immediate-custom", trigger_mode)
        self.assertEqual(2, args.trigger_count)
        self.assertEqual(100, args.sample_count)
        self.assertEqual(4, args.buffer_drain_size)

    def test_software_custom_accepts_instrument_counts(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "software-custom",
                "--trigger-count",
                "2",
                "--sample-count",
                "100",
            ]
        )

        trigger_mode = resolve_trigger_mode(args)
        validate_start_args(args, trigger_mode)

        self.assertEqual("software-custom", trigger_mode)
        self.assertEqual(2, args.trigger_count)
        self.assertEqual(100, args.sample_count)

    def test_software_custom_rejects_timer_interval(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "software-custom",
                "--trigger-count",
                "1",
                "--sample-count",
                "10",
                "--timer-interval-s",
                "1.0",
            ]
        )

        with self.assertRaisesRegex(ValueError, "--timer-interval-s requires --trigger-mode software"):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_external_custom_accepts_instrument_counts(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "external-custom",
                "--trigger-count",
                "2",
                "--sample-count",
                "100",
            ]
        )

        trigger_mode = resolve_trigger_mode(args)
        validate_start_args(args, trigger_mode)

        self.assertEqual("external-custom", trigger_mode)
        self.assertEqual(2, args.trigger_count)
        self.assertEqual(100, args.sample_count)

    def test_external_custom_rejects_timer_interval(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "external-custom",
                "--trigger-count",
                "1",
                "--sample-count",
                "10",
                "--timer-interval-s",
                "1.0",
            ]
        )

        with self.assertRaisesRegex(ValueError, "--timer-interval-s requires --trigger-mode software"):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_buffer_drain_size_requires_custom_mode(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate",
                "--max-samples",
                "10",
                "--buffer-drain-size",
                "2",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--buffer-drain-size requires a custom trigger mode",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_buffer_drain_size_must_be_positive(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate-custom",
                "--trigger-count",
                "1",
                "--sample-count",
                "10",
                "--buffer-drain-size",
                "0",
            ]
        )

        with self.assertRaisesRegex(ValueError, "--buffer-drain-size 0 is outside"):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_buffer_drain_size_rejects_more_than_34461a_memory(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate-custom",
                "--trigger-count",
                "1",
                "--sample-count",
                "10",
                "--buffer-drain-size",
                "10001",
            ]
        )

        with self.assertRaisesRegex(ValueError, "--buffer-drain-size 10001 is outside"):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_buffer_drain_size_respects_profile_memory_limit(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate-custom",
                "--trigger-count",
                "1",
                "--sample-count",
                "5",
                "--buffer-drain-size",
                "6",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--buffer-drain-size 6 is outside the FAKE100 reading-memory range 1-5",
        ):
            validate_start_args(
                args,
                resolve_trigger_mode(args),
                instrument_profile=FAKE_CURRENT_ONLY_PROFILE,
            )

    def test_trigger_count_requires_custom_mode(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate",
                "--trigger-count",
                "1",
            ]
        )

        with self.assertRaisesRegex(ValueError, "--trigger-count requires a custom trigger mode"):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_sample_count_requires_custom_mode(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate",
                "--sample-count",
                "1",
            ]
        )

        with self.assertRaisesRegex(ValueError, "--sample-count requires a custom trigger mode"):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_allow_buffer_overflow_risk_requires_custom_mode(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate",
                "--allow-buffer-overflow-risk",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--allow-buffer-overflow-risk requires a custom trigger mode",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_allow_buffer_overflow_risk_prints_warnings(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate-custom",
                "--trigger-count",
                "101",
                "--sample-count",
                "100",
                "--allow-buffer-overflow-risk",
            ]
        )

        with patch("builtins.print") as mock_print:
            print_buffer_overflow_warnings(args, "immediate-custom")

        self.assertEqual(5, mock_print.call_count)

    def test_timer_interval_is_valid_with_default_software_mode(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--timer-interval-s",
                "1.0",
            ]
        )

        trigger_mode = resolve_trigger_mode(args)
        validate_start_args(args, trigger_mode)

        self.assertEqual("software", trigger_mode)
        self.assertEqual(1.0, args.timer_interval_s)

    def test_timer_interval_must_be_positive(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--timer-interval-s",
                "0",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--timer-interval-s 0 is below the supported minimum 0.5 s",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_timer_interval_requires_software_mode(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "external",
                "--timer-interval-s",
                "1.0",
            ]
        )

        with self.assertRaisesRegex(ValueError, "--timer-interval-s requires --trigger-mode software"):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_enable_hw_trigger_conflicts_with_timer_interval(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--enable-hw-trigger",
                "--timer-interval-s",
                "1.0",
            ]
        )

        with self.assertRaisesRegex(ValueError, "--timer-interval-s requires --trigger-mode software"):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_legacy_enable_hw_trigger_maps_to_external_mode(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--enable-hw-trigger",
            ]
        )

        self.assertEqual("external", resolve_trigger_mode(args))

    def test_enable_hw_trigger_conflicts_with_non_external_mode(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "software",
                "--enable-hw-trigger",
            ]
        )

        with self.assertRaises(ValueError):
            resolve_trigger_mode(args)

    def test_list_resources_verify_flag(self):
        parser = build_parser()
        args = parser.parse_args(["list-resources", "--verify"])

        self.assertTrue(args.verify)
        self.assertFalse(args.live_only)
        self.assertEqual("text", args.output_format)

    def test_list_resources_live_only_flag(self):
        parser = build_parser()
        args = parser.parse_args(["list-resources", "--live-only"])

        self.assertFalse(args.verify)
        self.assertTrue(args.live_only)
        self.assertEqual("text", args.output_format)

    def test_list_resources_json_format(self):
        parser = build_parser()
        args = parser.parse_args(["list-resources", "--verify", "--format", "json"])

        self.assertTrue(args.verify)
        self.assertFalse(args.live_only)
        self.assertEqual("json", args.output_format)


class StopControllerTests(unittest.TestCase):
    def test_signal_stop_first_interrupt_is_graceful(self):
        calls = []
        messages = []
        controller = StopController(lambda: calls.append("stop"), print_fn=messages.append)

        controller.request_signal_stop()

        self.assertTrue(controller.stop)
        self.assertFalse(controller.force)
        self.assertEqual(1, controller.interrupt_count)
        self.assertEqual(["stop"], calls)
        self.assertEqual(
            ["interrupt received, stopping gracefully (press Ctrl+C again to force)..."],
            messages,
        )

    def test_signal_stop_second_interrupt_forces_shutdown(self):
        calls = []
        messages = []
        controller = StopController(lambda: calls.append("stop"), print_fn=messages.append)

        controller.request_signal_stop()
        controller.request_signal_stop()

        self.assertTrue(controller.stop)
        self.assertTrue(controller.force)
        self.assertEqual(2, controller.interrupt_count)
        self.assertEqual(["stop", "stop"], calls)
        self.assertEqual(
            "second interrupt received, forcing shutdown...",
            messages[-1],
        )

    def test_http_stop_does_not_count_as_keyboard_interrupt(self):
        calls = []
        messages = []
        controller = StopController(lambda: calls.append("stop"), print_fn=messages.append)

        controller.request_http_stop()

        self.assertTrue(controller.stop)
        self.assertFalse(controller.force)
        self.assertEqual(0, controller.interrupt_count)
        self.assertEqual(["stop"], calls)
        self.assertEqual([], messages)


class WindowsConsoleStopHandlerTests(unittest.TestCase):
    def test_ctrl_c_event_requests_stop(self):
        calls = []
        controller = StopController(lambda: calls.append("stop"), print_fn=lambda message: None)
        handler = WindowsConsoleStopHandler(controller)

        handled = handler._handle(0)

        self.assertTrue(handled)
        self.assertTrue(controller.stop)
        self.assertEqual(1, controller.interrupt_count)
        self.assertEqual(["stop"], calls)

    def test_ctrl_break_event_requests_stop(self):
        calls = []
        controller = StopController(lambda: calls.append("stop"), print_fn=lambda message: None)
        handler = WindowsConsoleStopHandler(controller)

        handled = handler._handle(1)

        self.assertTrue(handled)
        self.assertTrue(controller.stop)
        self.assertEqual(1, controller.interrupt_count)
        self.assertEqual(["stop"], calls)

    def test_non_interrupt_event_is_not_handled(self):
        calls = []
        controller = StopController(lambda: calls.append("stop"), print_fn=lambda message: None)
        handler = WindowsConsoleStopHandler(controller)

        handled = handler._handle(2)

        self.assertFalse(handled)
        self.assertFalse(controller.stop)
        self.assertEqual(0, controller.interrupt_count)
        self.assertEqual([], calls)


class FakeMsvcrt:
    def __init__(self, keys):
        self.keys = list(keys)

    def kbhit(self):
        return bool(self.keys)

    def getwch(self):
        return self.keys.pop(0)


class FakeStartInstrument:
    resource_id = "USB::FAKE"

    def __init__(self, _config):
        self.closed = False

    def connect(self):
        return None

    def release_to_local(self):
        return "release:ok"

    def cleanup_release_to_local(self):
        return "cleanup:ok"

    def close(self):
        self.closed = True


class ConnectFailingStartInstrument(FakeStartInstrument):
    release_calls = 0
    cleanup_calls = 0
    close_calls = 0

    def connect(self):
        raise InstrumentError("unsupported instrument identity; expected Keysight/Agilent 34461A")

    def release_to_local(self):
        type(self).release_calls += 1
        return "release:should-not-run"

    def cleanup_release_to_local(self):
        type(self).cleanup_calls += 1
        return "cleanup:should-not-run"

    def close(self):
        type(self).close_calls += 1
        self.closed = True


class FakeStartServer:
    def __init__(self, *_args, **_kwargs):
        self.stopped = False

    def start(self):
        return "127.0.0.1", 8765

    def stop(self):
        self.stopped = True


class FakeStartConsoleHandler:
    input_mode_configured = False

    def __init__(self, _controller):
        return

    def install(self):
        return False

    def uninstall(self):
        return


class FakeStartKeyboardPoller:
    def poll_stop_requested(self):
        return False


class FakeStartMeasurement:
    def configure(self, _instrument, _config):
        return


class PermissionDeniedCsvWriter:
    def __init__(self, path):
        self.path = path

    def open(self):
        raise PermissionError(13, "Permission denied", str(self.path))

    def close(self):
        return

    def write(self, _sample):
        return


class FakeCapturingCsvWriter:
    samples = []

    def __init__(self, path):
        self.path = path

    def open(self):
        type(self).samples = []

    def close(self):
        return

    def write(self, sample):
        type(self).samples.append(sample)


class WindowsKeyboardStopPollerTests(unittest.TestCase):
    def test_ctrl_c_character_requests_stop(self):
        poller = WindowsKeyboardStopPoller()
        poller._msvcrt = FakeMsvcrt(["\x03"])

        self.assertTrue(poller.poll_stop_requested())

    def test_q_requests_stop(self):
        poller = WindowsKeyboardStopPoller()
        poller._msvcrt = FakeMsvcrt(["q"])

        self.assertTrue(poller.poll_stop_requested())

    def test_other_key_does_not_request_stop(self):
        poller = WindowsKeyboardStopPoller()
        poller._msvcrt = FakeMsvcrt(["x"])

        self.assertFalse(poller.poll_stop_requested())


class CliCommandTests(unittest.TestCase):
    def test_soft_trigger_port_is_validated_before_request(self):
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            rc = main(["soft-trigger", "--port", "0"])

        self.assertEqual(2, rc)
        self.assertIn("--port 0 is outside the supported range 1-65535", stderr.getvalue())

    def test_soft_trigger_rejects_invalid_json_meta(self):
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            rc = cmd_soft_trigger(8765, "{bad json")

        self.assertEqual(2, rc)
        self.assertIn("meta must be valid JSON", stderr.getvalue())

    @patch("keysight_logger.cli.request.urlopen")
    def test_soft_trigger_posts_json_payload(self, mock_urlopen):
        class FakeResponse:
            status = 202

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        mock_urlopen.return_value = FakeResponse()
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_soft_trigger(8765, '{"operator": "tom"}')

        self.assertEqual(0, rc)
        self.assertIn("trigger accepted: 202", stdout.getvalue())
        req = mock_urlopen.call_args.args[0]
        self.assertEqual("http://127.0.0.1:8765/trigger", req.full_url)
        self.assertEqual("POST", req.get_method())
        self.assertEqual(b'{"operator": "tom"}', req.data)

    @patch("keysight_logger.cli.request.urlopen", side_effect=URLError("offline"))
    def test_soft_trigger_url_error_returns_3(self, _mock_urlopen):
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            rc = cmd_soft_trigger(8765, "{}")

        self.assertEqual(3, rc)
        self.assertIn("trigger request failed", stderr.getvalue())

    def test_soft_stop_port_is_validated_before_request(self):
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            rc = main(["soft-stop", "--port", "65536"])

        self.assertEqual(2, rc)
        self.assertIn("--port 65536 is outside the supported range 1-65535", stderr.getvalue())

    @patch("keysight_logger.cli.request.urlopen")
    def test_soft_stop_posts_stop_request(self, mock_urlopen):
        class FakeResponse:
            status = 204

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        mock_urlopen.return_value = FakeResponse()
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_soft_stop(8765)

        self.assertEqual(0, rc)
        self.assertIn("stop accepted: 204", stdout.getvalue())
        req = mock_urlopen.call_args.args[0]
        self.assertEqual("http://127.0.0.1:8765/stop", req.full_url)
        self.assertEqual("POST", req.get_method())
        self.assertEqual(b"{}", req.data)

    @patch("keysight_logger.cli.request.urlopen", side_effect=URLError("offline"))
    def test_soft_stop_non_connection_refused_url_error_returns_3(self, _mock_urlopen):
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            rc = cmd_soft_stop(8765)

        self.assertEqual(3, rc)
        self.assertIn("stop request failed", stderr.getvalue())

    def test_start_csv_permission_error_prints_friendly_message(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "data\\locked.csv",
                "--trigger-mode",
                "immediate",
                "--max-samples",
                "1",
            ]
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch("keysight_logger.cli.VisaInstrument", FakeStartInstrument),
            patch("keysight_logger.cli.SoftwareTriggerAdapter", FakeStartServer),
            patch("keysight_logger.cli.CsvWriter", PermissionDeniedCsvWriter),
            patch(
                "keysight_logger.cli.create_measurement_plugin",
                return_value=FakeStartMeasurement(),
            ),
            patch("keysight_logger.cli.WindowsConsoleStopHandler", FakeStartConsoleHandler),
            patch("keysight_logger.cli.WindowsKeyboardStopPoller", FakeStartKeyboardPoller),
            patch("keysight_logger.cli.signal.signal", side_effect=lambda _sig, _handler: None),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            rc = cmd_start(args)

        self.assertEqual(3, rc)
        self.assertIn("cannot open CSV output file: data\\locked.csv", stderr.getvalue())
        self.assertIn("file may be open in Excel", stderr.getvalue())
        self.assertIn("captured=0 errors=1", stdout.getvalue())
        self.assertNotIn("measurement worker exited before stop was requested", stdout.getvalue())

    def test_start_connect_instrument_error_returns_3_without_release_cleanup(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::WRONG",
                "--csv",
                "data\\unused.csv",
                "--trigger-mode",
                "immediate",
                "--max-samples",
                "1",
            ]
        )
        ConnectFailingStartInstrument.release_calls = 0
        ConnectFailingStartInstrument.cleanup_calls = 0
        ConnectFailingStartInstrument.close_calls = 0
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch("keysight_logger.cli.VisaInstrument", ConnectFailingStartInstrument),
            patch("keysight_logger.cli.SoftwareTriggerAdapter", FakeStartServer),
            patch("keysight_logger.cli.WindowsConsoleStopHandler", FakeStartConsoleHandler),
            patch("keysight_logger.cli.WindowsKeyboardStopPoller", FakeStartKeyboardPoller),
            patch("keysight_logger.cli.signal.signal", side_effect=lambda _sig, _handler: None),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            rc = cmd_start(args)

        self.assertEqual(3, rc)
        self.assertIn("error: unsupported instrument identity", stderr.getvalue())
        self.assertEqual(0, ConnectFailingStartInstrument.release_calls)
        self.assertEqual(0, ConnectFailingStartInstrument.cleanup_calls)
        self.assertEqual(0, ConnectFailingStartInstrument.close_calls)
        self.assertNotIn("release_to_local:", stdout.getvalue())
        self.assertNotIn("cleanup_release_to_local:", stdout.getvalue())

    def test_start_dry_run_prints_plan_without_opening_instrument(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "data\\dry_run.csv",
                "--trigger-mode",
                "immediate",
                "--measurement",
                "voltage-dc",
                "--dry-run",
            ]
        )
        stdout = io.StringIO()

        with (
            patch("keysight_logger.cli.VisaInstrument") as mock_visa,
            patch("keysight_logger.cli.SoftwareTriggerAdapter") as mock_server,
            redirect_stdout(stdout),
        ):
            rc = cmd_start(args)

        self.assertEqual(0, rc)
        self.assertIn("dry-run plan:", stdout.getvalue())
        self.assertIn("CONF:VOLT:DC AUTO", stdout.getvalue())
        mock_visa.assert_not_called()
        mock_server.assert_not_called()

    def test_start_dry_run_jsonl_outputs_one_plan_object(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "data\\dry_run.csv",
                "--trigger-mode",
                "external",
                "--measurement",
                "current-dc",
                "--dry-run",
                "--status-format",
                "jsonl",
            ]
        )
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_start(args)

        self.assertEqual(0, rc)
        lines = [line for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(1, len(lines))
        payload = json.loads(lines[0])
        self.assertEqual("dry_run", payload["event"])
        self.assertEqual("current_dc", payload["measurement_type"])
        self.assertEqual("FETC?", payload["read_path"])
        self.assertIn("TRIG:SOUR EXT", payload["scpi_commands"])

    def test_start_simulate_immediate_captures_sample(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "SIM::34461A",
                "--csv",
                "data\\simulate.csv",
                "--trigger-mode",
                "immediate",
                "--measurement",
                "current-dc",
                "--simulate",
                "--max-samples",
                "1",
            ]
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch("keysight_logger.cli.SoftwareTriggerAdapter", FakeStartServer),
            patch("keysight_logger.cli.CsvWriter", FakeCapturingCsvWriter),
            patch("keysight_logger.cli.WindowsConsoleStopHandler", FakeStartConsoleHandler),
            patch("keysight_logger.cli.WindowsKeyboardStopPoller", FakeStartKeyboardPoller),
            patch("keysight_logger.cli.signal.signal", side_effect=lambda _sig, _handler: None),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            rc = cmd_start(args)

        self.assertEqual(0, rc)
        self.assertEqual(1, len(FakeCapturingCsvWriter.samples))
        self.assertIn("captured=1 errors=0", stdout.getvalue())

    def test_start_simulate_jsonl_emits_parseable_sample_and_summary(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "SIM::34461A",
                "--csv",
                "data\\simulate_jsonl.csv",
                "--trigger-mode",
                "immediate",
                "--measurement",
                "voltage-dc",
                "--simulate",
                "--max-samples",
                "1",
                "--status-format",
                "jsonl",
            ]
        )
        stdout = io.StringIO()

        with (
            patch("keysight_logger.cli.SoftwareTriggerAdapter", FakeStartServer),
            patch("keysight_logger.cli.CsvWriter", FakeCapturingCsvWriter),
            patch("keysight_logger.cli.WindowsConsoleStopHandler", FakeStartConsoleHandler),
            patch("keysight_logger.cli.WindowsKeyboardStopPoller", FakeStartKeyboardPoller),
            patch("keysight_logger.cli.signal.signal", side_effect=lambda _sig, _handler: None),
            redirect_stdout(stdout),
        ):
            rc = cmd_start(args)

        self.assertEqual(0, rc)
        events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertTrue(all(event["schema_version"] == 1 for event in events))
        self.assertTrue(any(event["event"] == "sample" for event in events))
        summary = [event for event in events if event["event"] == "summary"][-1]
        self.assertEqual(1, summary["captured"])
        self.assertEqual(0, summary["errors"])

    @patch("keysight_logger.cli.VisaInstrument")
    def test_list_resources_without_verify_prints_resources(self, mock_visa):
        mock_visa.list_resources.return_value = ["USB::LIVE"]
        lines = []

        rc = cmd_list_resources(verify=False, print_fn=lines.append)

        self.assertEqual(0, rc)
        self.assertEqual(["USB::LIVE"], lines)
        mock_visa.verify_resource.assert_not_called()

    @patch("keysight_logger.cli.VisaInstrument")
    def test_list_resources_verify_marks_live_and_stale(self, mock_visa):
        mock_visa.list_resources.return_value = ["USB::LIVE", "USB::STALE"]
        mock_visa.verify_resource.side_effect = [
            (True, "Keysight Technologies,34461A,MY123,1.0"),
            (False, "VisaIOError: timeout"),
        ]
        lines = []

        rc = cmd_list_resources(verify=True, print_fn=lines.append)

        self.assertEqual(0, rc)
        self.assertEqual(
            [
                "live\tUSB::LIVE\tKeysight Technologies,34461A,MY123,1.0",
                "stale\tUSB::STALE\tVisaIOError: timeout",
            ],
            lines,
        )

    @patch("keysight_logger.cli.VisaInstrument")
    def test_list_resources_verify_json_marks_live_and_stale(self, mock_visa):
        mock_visa.list_resources.return_value = ["USB::LIVE", "USB::STALE"]
        mock_visa.verify_resource.side_effect = [
            (True, "Keysight Technologies,34461A,MY123,1.0"),
            (False, "VisaIOError: timeout"),
        ]
        lines = []

        rc = cmd_list_resources(verify=True, output_format="json", print_fn=lines.append)

        self.assertEqual(0, rc)
        self.assertEqual(1, len(lines))
        self.assertEqual(
            {
                "resources": [
                    {
                        "detail": "Keysight Technologies,34461A,MY123,1.0",
                        "live": True,
                        "resource": "USB::LIVE",
                        "status": "live",
                    },
                    {
                        "detail": "VisaIOError: timeout",
                        "live": False,
                        "resource": "USB::STALE",
                        "status": "stale",
                    },
                ],
                "verify": True,
            },
            json.loads(lines[0]),
        )

    @patch("keysight_logger.cli.VisaInstrument")
    def test_list_resources_live_only_prints_only_live_resources(self, mock_visa):
        mock_visa.list_resources.return_value = ["USB::LIVE", "USB::STALE"]
        mock_visa.verify_resource.side_effect = [
            (True, "Keysight Technologies,34461A,MY123,1.0"),
            (False, "VisaIOError: timeout"),
        ]
        lines = []

        rc = cmd_list_resources(live_only=True, print_fn=lines.append)

        self.assertEqual(0, rc)
        self.assertEqual(
            ["live\tUSB::LIVE\tKeysight Technologies,34461A,MY123,1.0"],
            lines,
        )

    @patch("keysight_logger.cli.VisaInstrument")
    def test_list_resources_live_only_prints_message_when_none_live(self, mock_visa):
        mock_visa.list_resources.return_value = ["USB::STALE"]
        mock_visa.verify_resource.return_value = (False, "VisaIOError: timeout")
        lines = []

        rc = cmd_list_resources(live_only=True, print_fn=lines.append)

        self.assertEqual(0, rc)
        self.assertEqual(["no live VISA resources found"], lines)

    @patch("keysight_logger.cli.VisaInstrument")
    def test_list_resources_live_only_json_filters_stale_resources(self, mock_visa):
        mock_visa.list_resources.return_value = ["USB::LIVE", "USB::STALE"]
        mock_visa.verify_resource.side_effect = [
            (True, "Keysight Technologies,34461A,MY123,1.0"),
            (False, "VisaIOError: timeout"),
        ]
        lines = []

        rc = cmd_list_resources(live_only=True, output_format="json", print_fn=lines.append)

        self.assertEqual(0, rc)
        self.assertEqual(1, len(lines))
        self.assertEqual(
            {
                "live_only": True,
                "resources": [
                    {
                        "detail": "Keysight Technologies,34461A,MY123,1.0",
                        "live": True,
                        "resource": "USB::LIVE",
                        "status": "live",
                    },
                ],
                "verify": True,
            },
            json.loads(lines[0]),
        )

    def test_main_dispatches_list_resources(self):
        with patch("keysight_logger.cli.cmd_list_resources", return_value=17) as mock_cmd:
            rc = main(["list-resources", "--live-only", "--format", "json"])

        self.assertEqual(17, rc)
        mock_cmd.assert_called_once_with(verify=False, live_only=True, output_format="json")

    def test_main_dispatches_start_trigger_record(self):
        with patch("keysight_logger.cli.cmd_start", return_value=23) as mock_cmd:
            rc = main(["start-trigger-record", "--resource", "USB::FAKE"])

        self.assertEqual(23, rc)
        self.assertEqual("USB::FAKE", mock_cmd.call_args.args[0].resource)

    @patch(
        "keysight_logger.cli.request.urlopen",
        side_effect=URLError(ConnectionRefusedError(10061, "refused")),
    )
    def test_soft_stop_connection_refused_returns_0(self, _mock_urlopen):
        rc = cmd_soft_stop(8765)
        self.assertEqual(0, rc)


if __name__ == "__main__":
    unittest.main()
