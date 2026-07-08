from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from keysight_logger_cli.cli import build_parser, get_cli_version, main

class CliArgsTests(unittest.TestCase):
    def assert_contains_tokens(self, text: str, tokens: tuple[str, ...]) -> None:
        for token in tokens:
            self.assertIn(token, text)

    def test_top_level_help_lists_version_and_subcommands(self):
        parser = build_parser()
        stdout = io.StringIO()

        with self.assertRaises(SystemExit) as exc, redirect_stdout(stdout):
            parser.parse_args(["--help"])

        self.assertEqual(0, exc.exception.code)
        help_text = stdout.getvalue()
        self.assertIn("--version", help_text)
        for command in [
            "list-resources",
            "start-trigger-record",
            "send-command",
            "stop",
            "status",
            "wait-ready",
        ]:
            self.assertIn(command, help_text)

    def test_version_outputs_package_version_without_subcommand(self):
        stdout = io.StringIO()

        with self.assertRaises(SystemExit) as exc, redirect_stdout(stdout):
            main(["--version"])

        self.assertEqual(0, exc.exception.code)
        self.assertEqual(f"keysight-logger {get_cli_version()}\n", stdout.getvalue())

    def test_subcommand_help_lists_agent_flags(self):
        cases = {
            "list-resources": [
                "--dry-run",
                "--json",
                "--format",
                "--serial-read-termination",
                "--serial-write-termination",
            ],
            "start-trigger-record": ["--dry-run", "--simulate", "--json", "--status-format"],
            "send-command": ["--dry-run", "--json", "--format", "--timeout-ms"],
            "stop": ["--dry-run", "--json", "--format", "--timeout-ms"],
            "status": ["--dry-run", "--json", "--format", "--timeout-ms"],
            "wait-ready": ["--json", "--format", "--timeout-ms"],
        }
        for command, flags in cases.items():
            with self.subTest(command=command):
                parser = build_parser()
                stdout = io.StringIO()

                with self.assertRaises(SystemExit) as exc, redirect_stdout(stdout):
                    parser.parse_args([command, "--help"])

                self.assertEqual(0, exc.exception.code)
                help_text = stdout.getvalue()
                for flag in flags:
                    self.assertIn(flag, help_text)

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
        self.assertIsNone(args.ac_bandwidth_hz)
        self.assertIsNone(args.gate_time_s)
        self.assertIsNone(args.freq_period_timeout)
        self.assertIsNone(args.current_terminal)
        self.assertEqual("default", args.dcv_input_impedance)
        self.assertIsNone(args.trigger_mode)
        self.assertIsNone(args.max_samples)
        self.assertIsNone(args.trigger_count)
        self.assertIsNone(args.sample_count)
        self.assertIsNone(args.timer_interval_s)
        self.assertIsNone(args.buffer_drain_size)
        self.assertFalse(args.allow_buffer_overflow_risk)
        self.assertIsNone(args.vm_comp_slope)
        self.assertIsNone(args.visa_library)

    def test_start_parser_accepts_visa_library_and_backend_aliases(self):
        parser = build_parser()

        visa_library_args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--visa-library",
                "@py",
            ]
        )
        backend_args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--backend",
                "@py",
            ]
        )

        self.assertEqual("@py", visa_library_args.visa_library)
        self.assertEqual("@py", backend_args.visa_library)

    def test_start_help_lists_cli_limits(self):
        parser = build_parser()
        stdout = io.StringIO()

        with self.assertRaises(SystemExit) as exc, redirect_stdout(stdout):
            parser.parse_args(["start-trigger-record", "--help"])

        self.assertEqual(0, exc.exception.code)
        help_text = stdout.getvalue()
        self.assertNotIn("default: 34461A", help_text)
        self.assertIn("Omit for live", help_text)
        self.assertIn("auto-detect", help_text)
        self.assertIn("--model MODEL", help_text)
        self.assertIn("--instrument-model MODEL", help_text)
        self.assertNotIn("{34460A,34461A}", help_text)
        self.assertNotIn("{34461A,34460A}", help_text)
        for tokens in (
            ("NPLC", "DC", "resistance", "0.02", "0.2", "1", "10", "100"),
            ("current-dc", "0.0001", "0.001", "0.01", "0.1", "1", "3", "10", "A"),
            ("--timer-interval-s", "0.5", "86400", "s"),
            ("--trigger-timeout-ms", "500", "600000", "ms"),
            ("--trigger-count", "--sample-count", "1", "1000000"),
            ("AC bandwidth", "current", "voltage", "3", "20", "200", "Hz"),
            ("Frequency/Period", "gate time", "0.01", "0.1", "1"),
            ("Frequency/Period", "timeout", "auto", "1s"),
            ("current terminal", "current", "3", "10"),
        ):
            with self.subTest(tokens=tokens):
                self.assert_contains_tokens(help_text, tokens)

    def test_start_parser_accepts_model_text_without_argparse_choices(self):
        parser = build_parser()

        lowercase_args = parser.parse_args(
            ["start-trigger-record", "--resource", "USB::FAKE", "--model", "34461a"]
        )
        unknown_args = parser.parse_args(
            ["start-trigger-record", "--resource", "USB::FAKE", "--model", "BADMODEL"]
        )

        self.assertEqual("34461a", lowercase_args.instrument_model)
        self.assertEqual("BADMODEL", unknown_args.instrument_model)

    def test_start_parser_source_has_no_hard_coded_model_choices(self):
        parser_source = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "keysight_logger_cli"
            / "_parser.py"
        ).read_text(encoding="utf-8")

        self.assertNotRegex(
            parser_source,
            r"choices\s*=\s*(?:\[|\()[^\]\)]*34460A[^\]\)]*34461A[^\]\)]*(?:\]|\))",
        )
        self.assertNotRegex(
            parser_source,
            r"choices\s*=\s*(?:\[|\()[^\]\)]*34461A[^\]\)]*34460A[^\]\)]*(?:\]|\))",
        )

    def test_start_parses_core_v1_1_measurement_options(self):
        parser = build_parser()
        auto_zero_args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--measurement",
                "current-dc",
                "--auto-zero",
                "once",
            ]
        )
        ac_args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--measurement",
                "current-ac",
                "--ac-bandwidth-hz",
                "20",
                "--current-terminal",
                "10",
            ]
        )

        self.assertEqual("once", auto_zero_args.auto_zero)
        self.assertEqual(20.0, ac_args.ac_bandwidth_hz)
        self.assertEqual(10, ac_args.current_terminal)

    def test_start_parses_frequency_period_options(self):
        parser = build_parser()

        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--measurement",
                "frequency",
                "--ac-bandwidth-hz",
                "20",
                "--gate-time-s",
                "0.1",
                "--freq-period-timeout",
                "1s",
            ]
        )

        self.assertEqual("frequency", args.measurement)
        self.assertEqual(20.0, args.ac_bandwidth_hz)
        self.assertEqual(0.1, args.gate_time_s)
        self.assertEqual("1s", args.freq_period_timeout)

    def test_start_rejects_invalid_frequency_period_choices(self):
        parser = build_parser()
        for option, value in [
            ("--gate-time-s", "0.5"),
            ("--freq-period-timeout", "2s"),
        ]:
            with self.subTest(option=option, value=value):
                with self.assertRaises(SystemExit) as exc:
                    parser.parse_args(
                        [
                            "start-trigger-record",
                            "--resource",
                            "USB::FAKE",
                            "--measurement",
                            "frequency",
                            option,
                            value,
                        ]
                    )
                self.assertEqual(2, exc.exception.code)

    def test_list_resources_verify_flag(self):
        parser = build_parser()
        args = parser.parse_args(["list-resources", "--verify"])

        self.assertTrue(args.verify)
        self.assertFalse(args.live_only)
        self.assertEqual("text", args.output_format)
        self.assertIsNone(args.visa_library)
        self.assertIsNone(args.serial_read_termination)
        self.assertIsNone(args.serial_write_termination)

    def test_list_resources_parser_accepts_visa_library_and_backend_aliases(self):
        parser = build_parser()

        visa_library_args = parser.parse_args(["list-resources", "--visa-library", "@py"])
        backend_args = parser.parse_args(["list-resources", "--backend", "@py"])

        self.assertEqual("@py", visa_library_args.visa_library)
        self.assertEqual("@py", backend_args.visa_library)

    def test_list_resources_parser_accepts_serial_termination_choices(self):
        parser = build_parser()

        args = parser.parse_args(
            [
                "list-resources",
                "--verify",
                "--serial-read-termination",
                "CRLF",
                "--serial-write-termination",
                "LF",
            ]
        )

        self.assertEqual("CRLF", args.serial_read_termination)
        self.assertEqual("LF", args.serial_write_termination)

    def test_list_resources_parser_rejects_invalid_serial_termination(self):
        parser = build_parser()

        with self.assertRaises(SystemExit) as exc:
            parser.parse_args(["list-resources", "--serial-read-termination", "NUL"])

        self.assertEqual(2, exc.exception.code)

    def test_send_command_rejects_visa_library(self):
        parser = build_parser()

        with self.assertRaises(SystemExit) as exc:
            parser.parse_args(["send-command", "--visa-library", "@py"])

        self.assertEqual(2, exc.exception.code)

    def test_list_resources_live_only_flag(self):
        parser = build_parser()
        args = parser.parse_args(["list-resources", "--live-only"])

        self.assertFalse(args.verify)
        self.assertTrue(args.live_only)
        self.assertEqual("text", args.output_format)

    def test_list_resources_dry_run_flag(self):
        parser = build_parser()
        args = parser.parse_args(["list-resources", "--dry-run"])

        self.assertTrue(args.dry_run)

    def test_list_resources_json_format(self):
        parser = build_parser()
        args = parser.parse_args(["list-resources", "--verify", "--format", "json"])

        self.assertTrue(args.verify)
        self.assertFalse(args.live_only)
        self.assertEqual("json", args.output_format)

    def test_list_resources_json_alias(self):
        parser = build_parser()
        args = parser.parse_args(["list-resources", "--json"])

        self.assertEqual("json", args.output_format)

    def test_list_resources_json_alias_conflicts_with_text_format(self):
        parser = build_parser()

        with self.assertRaises(SystemExit) as exc:
            parser.parse_args(["list-resources", "--json", "--format", "text"])

        self.assertEqual(2, exc.exception.code)




if __name__ == "__main__":
    unittest.main()
