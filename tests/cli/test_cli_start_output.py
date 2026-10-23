from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from meters_tool_cli.cli import (
    build_parser,
    cmd_start,
)

from cli_command_helpers import (
    CliCommandHarnessMixin,
    ConnectFailingStartInstrument,
    FailingReadSimulatedVisaInstrument,
    FakeStartInstrument,
    FakeStartKeyboardPoller,
    FakeStartMeasurement,
    FakeStartServer,
    InstalledConsoleHandler,
    PermissionDeniedCsvWriter,
    ShortBufferedReadSimulatedVisaInstrument,
)


class CliStartOutputTests(CliCommandHarnessMixin, unittest.TestCase):
    def test_start_csv_permission_error_prints_friendly_message(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--model",
                "34461A",
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
        fake_backend = FakeStartInstrument(None)

        with (
            patch("meters_tool_core.runner.create_instrument_backend", return_value=fake_backend),
            patch("meters_tool_core.runner.SoftwareTriggerAdapter", FakeStartServer),
            patch("meters_tool_core.runner.CsvWriter", PermissionDeniedCsvWriter),
            patch(
                "meters_tool_core.runner.create_measurement_plugin",
                return_value=FakeStartMeasurement(),
            ),
            patch(
                "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
                return_value="Keysight Technologies,34461A,MY123,1.0",
            ),
            patch("meters_tool_cli.cli.WindowsConsoleStopHandler", InstalledConsoleHandler),
            patch("meters_tool_cli.cli.WindowsKeyboardStopPoller", FakeStartKeyboardPoller),
            patch("meters_tool_cli.cli.signal.signal", side_effect=lambda _sig, _handler: None),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            rc = cmd_start(args)

        self.assertEqual(3, rc)
        self.assertIn("cannot open CSV output file: data\\locked.csv", stderr.getvalue())
        self.assertIn("file may be open in Excel", stderr.getvalue())
        self.assertIn("captured=0 errors=1", stdout.getvalue())
        self.assertNotIn("measurement worker exited before stop was requested", stdout.getvalue())

    def test_start_dry_run_prints_plan_without_opening_instrument(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--model",
                "34461A",
                "--visa-library",
                "@py",
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
            patch("meters_tool_core.runner.create_instrument_backend") as mock_factory,
            patch("meters_tool_core.runner.SoftwareTriggerAdapter") as mock_server,
            redirect_stdout(stdout),
        ):
            rc = cmd_start(args)

        self.assertEqual(0, rc)
        self.assertIn("dry-run plan:", stdout.getvalue())
        self.assertIn("performs VISA I/O: false", stdout.getvalue())
        self.assertIn("writes CSV: false", stdout.getvalue())
        self.assertIn("starts HTTP server: false", stdout.getvalue())
        self.assertIn("CONF:VOLT:DC AUTO", stdout.getvalue())
        self.assertNotIn("software status endpoint:", stdout.getvalue())
        mock_factory.assert_not_called()
        mock_server.assert_not_called()
        self.assertEqual("@py", args.visa_library)

    def test_start_no_csv_text_dry_run_reports_disabled_without_none_path(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "SIM::34461A",
                "--no-csv",
                "--trigger-mode",
                "immediate",
                "--max-samples",
                "1",
                "--dry-run",
            ]
        )
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_start(args)

        self.assertEqual(0, rc)
        self.assertIn("CSV output for real run: disabled", stdout.getvalue())
        self.assertNotIn("csv_path: None", stdout.getvalue())

    def test_start_dry_run_jsonl_outputs_one_plan_object(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--model",
                "34461A",
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
        self.assertNotEqual("ready", payload["event"])
        for key in [
            "cleanup_steps",
            "csv_path",
            "dry_run",
            "dry_run_performs_visa_io",
            "dry_run_starts_http_server",
            "dry_run_writes_csv",
            "measurement_cli_name",
            "measurement_type",
            "measurement_unit",
            "notes",
            "read_path",
            "resource",
            "schema_version",
            "scpi_commands",
            "simulate",
            "timestamp_utc",
            "trigger_mode",
        ]:
            self.assertIn(key, payload)
        self.assertEqual("current_dc", payload["measurement_type"])
        self.assertTrue(payload["csv_enabled"])
        self.assertEqual("data\\dry_run.csv", payload["csv_path"])
        self.assertFalse(payload["dry_run_performs_visa_io"])
        self.assertFalse(payload["dry_run_writes_csv"])
        self.assertFalse(payload["dry_run_starts_http_server"])
        self.assertEqual("current-dc", payload["measurement_cli_name"])
        self.assertNotIn("measurement_name", payload)
        self.assertEqual("FETC?", payload["read_path"])
        self.assertIn("TRIG:SOUR EXT", payload["scpi_commands"])
        self.assertNotIn("run_id", payload)

    def test_start_no_csv_dry_run_jsonl_reports_disabled_plan(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "SIM::34461A",
                "--no-csv",
                "--trigger-mode",
                "immediate",
                "--max-samples",
                "1",
                "--dry-run",
                "--status-format",
                "jsonl",
            ]
        )
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_start(args)

        self.assertEqual(0, rc)
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["csv_enabled"])
        self.assertIsNone(payload["csv_path"])
        self.assertFalse(payload["dry_run_writes_csv"])

    def test_frequency_dry_run_json_uses_effective_defaults(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--model",
                "34461A",
                "--measurement",
                "frequency",
                "--dry-run",
                "--json",
            ]
        )
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_start(args)

        self.assertEqual(0, rc)
        payload = json.loads(stdout.getvalue())
        self.assertEqual("frequency", payload["measurement_type"])
        self.assertEqual("Hz", payload["measurement_unit"])
        self.assertEqual("READ?", payload["read_path"])
        self.assertEqual(
            [
                "CONF:FREQ",
                "FREQ:VOLT:RANG:AUTO ON",
                "FREQ:RANG:LOW 20",
                "FREQ:APER 0.1",
                "FREQ:TIM:AUTO ON",
            ],
            payload["scpi_commands"],
        )

    def test_start_dry_run_json_alias_outputs_one_plan_object(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--model",
                "34461A",
                "--csv",
                "data\\dry_run.json.csv",
                "--trigger-mode",
                "external",
                "--measurement",
                "current-dc",
                "--dry-run",
                "--json",
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
        self.assertEqual("jsonl", args.status_format)

    def test_start_dry_run_jsonl_overflow_warnings_are_plan_notes_only(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--model",
                "34461A",
                "--csv",
                "data\\dry_run.csv",
                "--trigger-mode",
                "software-custom",
                "--measurement",
                "current-dc",
                "--dry-run",
                "--status-format",
                "jsonl",
                "--allow-buffer-overflow-risk",
                "--trigger-count",
                "100",
                "--sample-count",
                "1000",
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
        self.assertTrue(any("requested readings exceed" in note for note in payload["notes"]))
        self.assertFalse(lines[0].startswith("WARNING:"))

    def test_start_jsonl_overflow_warnings_are_status_events(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::WRONG",
                "--model",
                "34461A",
                "--csv",
                "data\\unused.csv",
                "--trigger-mode",
                "software-custom",
                "--measurement",
                "current-dc",
                "--status-format",
                "jsonl",
                "--allow-buffer-overflow-risk",
                "--trigger-count",
                "101",
                "--sample-count",
                "100",
            ]
        )
        ConnectFailingStartInstrument.release_calls = 0
        ConnectFailingStartInstrument.cleanup_calls = 0
        ConnectFailingStartInstrument.close_calls = 0
        stdout = io.StringIO()
        fake_backend = ConnectFailingStartInstrument(None)

        with (
            patch("meters_tool_core.runner.create_instrument_backend", return_value=fake_backend),
            patch(
                "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
                return_value="Keysight Technologies,34461A,MY123,1.0",
            ),
            redirect_stdout(stdout),
        ):
            rc = cmd_start(args)

        self.assertEqual(3, rc)
        events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertGreaterEqual(len(events), 6)
        self.assertTrue(all(event["event"] == "status" for event in events[:5]))
        self.assertTrue(all("WARNING:" in event["message"] for event in events[:5]))
        warning_run_ids = {event["run_id"] for event in events[:5]}
        self.assertEqual(1, len(warning_run_ids))
        self.assertTrue(any(event["event"] == "error" for event in events))

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

        rc, output, _stderr = self._run_cmd_start_with_simulate_harness(args)

        self.assertEqual(0, rc)
        events = self._parse_jsonl_events(output)
        self._assert_success_jsonl_events(events, expected_samples=1)
        ready = [event for event in events if event["event"] == "ready"]
        self.assertEqual(1, len(ready))
        self.assertEqual("keysight-meter", ready[0]["service"])
        self.assertEqual("127.0.0.1", ready[0]["host"])
        self.assertEqual(8765, ready[0]["port"])
        self.assertEqual("http://127.0.0.1:8765/command", ready[0]["command_url"])
        self.assertEqual("http://127.0.0.1:8765/stop", ready[0]["stop_url"])
        self.assertEqual("http://127.0.0.1:8765/status", ready[0]["status_url"])
        self.assertIn("run_id", ready[0])
        sample = [event for event in events if event["event"] == "sample"][-1]
        self.assertEqual({}, sample["measurement_metadata"])

    def test_start_simulate_jsonl_voltage_dc_ratio_includes_measurement_metadata(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "SIM::34461A",
                "--csv",
                "data\\simulate_ratio_jsonl.csv",
                "--trigger-mode",
                "immediate",
                "--measurement",
                "voltage-dc-ratio",
                "--simulate",
                "--max-samples",
                "1",
                "--status-format",
                "jsonl",
            ]
        )

        rc, output, _stderr = self._run_cmd_start_with_simulate_harness(args)

        self.assertEqual(0, rc)
        events = self._parse_jsonl_events(output)
        self._assert_success_jsonl_events(events, expected_samples=1)
        sample = [event for event in events if event["event"] == "sample"][-1]
        self.assertEqual("voltage_dc_ratio", sample["measurement_type"])
        self.assertEqual("ratio", sample["unit"])
        self.assertIn("signal_voltage_v", sample["measurement_metadata"])
        self.assertIn("reference_voltage_v", sample["measurement_metadata"])

    def test_start_simulate_jsonl_emits_error_and_fatal_summary_on_read_failure(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "SIM::34461A",
                "--csv",
                "data\\simulate_failure.csv",
                "--trigger-mode",
                "immediate",
                "--measurement",
                "current-dc",
                "--simulate",
                "--max-samples",
                "1",
                "--status-format",
                "jsonl",
            ]
        )

        rc, output, _stderr = self._run_cmd_start_with_simulate_harness(
            args,
            instrument_cls=FailingReadSimulatedVisaInstrument,
        )

        self.assertEqual(3, rc)
        events = self._parse_jsonl_events(output)
        errors = [event for event in events if event["event"] == "error"]
        self.assertTrue(errors)
        self.assertIn("simulated read failure", errors[-1]["message"])
        summary = [event for event in events if event["event"] == "summary"][-1]
        self.assertEqual(0, summary["captured"])
        self.assertEqual(1, summary["errors"])
        self.assertIs(False, summary["ok"])
        self.assertIn("simulated read failure", summary["fatal_error"]["details"]["domain_error"])

    def test_start_simulate_jsonl_emits_error_on_malformed_buffered_read(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "SIM::34461A",
                "--csv",
                "data\\simulate_buffered_failure.csv",
                "--trigger-mode",
                "immediate-custom",
                "--measurement",
                "current-dc",
                "--simulate",
                "--trigger-count",
                "1",
                "--sample-count",
                "2",
                "--buffer-drain-size",
                "2",
                "--status-format",
                "jsonl",
            ]
        )

        rc, output, _stderr = self._run_cmd_start_with_simulate_harness(
            args,
            instrument_cls=ShortBufferedReadSimulatedVisaInstrument,
        )

        self.assertEqual(3, rc)
        events = self._parse_jsonl_events(output)
        errors = [event for event in events if event["event"] == "error"]
        self.assertTrue(errors)
        self.assertIn("buffered capture failure", errors[-1]["message"])
        self.assertIn("Expected 2 buffered readings, got 1", errors[-1]["message"])
        summary = [event for event in events if event["event"] == "summary"][-1]
        self.assertEqual(0, summary["captured"])
        self.assertEqual(1, summary["errors"])
        self.assertIs(False, summary["ok"])
        self.assertIn("buffered capture failure", summary["fatal_error"]["details"]["domain_error"])

    def test_start_simulate_jsonl_csv_permission_error_is_structured(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "SIM::34461A",
                "--csv",
                "data\\locked_simulate.csv",
                "--trigger-mode",
                "immediate",
                "--measurement",
                "current-dc",
                "--simulate",
                "--max-samples",
                "1",
                "--status-format",
                "jsonl",
            ]
        )

        rc, output, stderr = self._run_cmd_start_with_simulate_harness(
            args,
            csv_writer=PermissionDeniedCsvWriter,
        )

        self.assertEqual(3, rc)
        self.assertEqual("", stderr)
        events = self._parse_jsonl_events(output)
        errors = [event for event in events if event["event"] == "error"]
        self.assertTrue(errors)
        self.assertIn("cannot open CSV output file: data\\locked_simulate.csv", errors[-1]["message"])
        summary = [event for event in events if event["event"] == "summary"][-1]
        self.assertEqual(0, summary["captured"])
        self.assertEqual(1, summary["errors"])
        self.assertIs(False, summary["ok"])
        self.assertIn("cannot open CSV output file", summary["fatal_error"]["details"]["domain_error"])

    def test_start_dry_run_immediate_no_buffered_scpi(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--model",
                "34461A",
                "--csv",
                "data\\dry_run.csv",
                "--trigger-mode",
                "immediate",
                "--measurement",
                "current-dc",
                "--dry-run",
            ]
        )
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_start(args)

        self.assertEqual(0, rc)
        output = stdout.getvalue()
        self.assertIn("READ?", output)
        self.assertNotIn("DATA:POINts?", output)
        self.assertNotIn("DATA:REMove?", output)
        self.assertNotIn("TRIG:COUNT", output)

    def test_start_dry_run_custom_read_path(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--model",
                "34461A",
                "--csv",
                "data\\dry_run_custom.csv",
                "--trigger-mode",
                "software-custom",
                "--measurement",
                "current-dc",
                "--dry-run",
                "--trigger-count",
                "3",
                "--sample-count",
                "5",
            ]
        )
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_start(args)

        self.assertEqual(0, rc)
        output = stdout.getvalue()
        self.assertIn("DATA:POINts? / DATA:REMove?", output)
        self.assertIn("TRIG:COUNT 3", output)
        self.assertIn("SAMP:COUNT 5", output)
        self.assertIn("TRIG:SOUR BUS", output)


if __name__ == "__main__":
    unittest.main()
