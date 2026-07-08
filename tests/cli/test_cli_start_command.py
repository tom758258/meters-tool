from __future__ import annotations

import io
import csv
import json
import socket
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from urllib import request
from urllib.error import HTTPError, URLError

from meters_tool_cli.cli import (
    build_parser,
    cmd_list_resources,
    cmd_send_command,
    cmd_start,
    cmd_status,
    cmd_stop,
    cmd_wait_ready,
    main,
)
from meters_tool_core.models import KEYSIGHT_34461A_PROFILE, StartRequest
from meters_tool_core.session import StartRunResult

from cli_command_helpers import CliCommandHarnessMixin
from cli_command_helpers import *  # noqa: F403

class CliStartCommandTests(CliCommandHarnessMixin, unittest.TestCase):
    def _worker_status(self, *, fatal_error=None):
        return {
            "schema_version": 1,
            "service": "keysight-meter",
            "run_id": "run-123",
            "status": "running",
            "command_url": "http://127.0.0.1:8765/command",
            "stop_url": "http://127.0.0.1:8765/stop",
            "status_url": "http://127.0.0.1:8765/status",
            "queue_size": 0,
            "queue_max": 10000,
            "min_interval_ms": 0,
            "captured": 10,
            "errors": 0,
            "fatal_error": fatal_error,
            "timestamp_utc": "2026-05-31T00:00:00+00:00",
        }

    def _fake_json_response(self, payload):
        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(payload).encode("utf-8")

        return FakeResponse()

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

    def test_start_connect_instrument_error_returns_3_without_release_cleanup(self):
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
        fake_backend = ConnectFailingStartInstrument(None)

        with (
            patch("meters_tool_core.runner.create_instrument_backend", return_value=fake_backend),
            patch("meters_tool_core.runner.SoftwareTriggerAdapter", FakeStartServer),
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

    def test_start_dry_run_omitted_model_real_resource_fails_without_preflight(self):
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
                "--dry-run",
            ]
        )
        stderr = io.StringIO()

        with (
            patch("meters_tool_core.start_resolution.VisaInstrument.preflight_idn") as preflight,
            redirect_stderr(stderr),
        ):
            rc = cmd_start(args)

        self.assertEqual(2, rc)
        self.assertIn(
            "dry-run cannot auto-detect the instrument model without VISA I/O",
            stderr.getvalue(),
        )
        preflight.assert_not_called()

    def test_start_unsupported_model_fails_core_validation_without_argparse_choices(self):
        stderr = io.StringIO()

        with (
            patch("meters_tool_core.start_resolution.VisaInstrument.preflight_idn") as preflight,
            redirect_stderr(stderr),
        ):
            rc = main(
                [
                    "start-trigger-record",
                    "--resource",
                    "USB::FAKE",
                    "--model",
                    "BADMODEL",
                    "--dry-run",
                ]
            )

        self.assertEqual(2, rc)
        self.assertIn("Unsupported instrument model: BADMODEL", stderr.getvalue())
        self.assertIn("Supported models:", stderr.getvalue())
        self.assertNotIn("invalid choice", stderr.getvalue())
        preflight.assert_not_called()

    def test_start_parser_accepts_bad_model_as_free_text(self):
        parser = build_parser()

        args = parser.parse_args(
            ["start-trigger-record", "--resource", "USB::FAKE", "--model", "BADMODEL"]
        )

        self.assertEqual("BADMODEL", args.instrument_model)

    def test_start_live_omitted_model_uses_preflight_profile_for_runner(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "data\\delegate_live.csv",
                "--trigger-mode",
                "immediate",
                "--max-samples",
                "1",
            ]
        )
        fake_result = StartRunResult(
            run_id="run-123",
            ok=True,
            reason="completed",
            captured=1,
            errors=0,
            fatal_error=None,
            csv_path="data\\delegate_live.csv",
        )

        with (
            patch(
                "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
                return_value="Keysight Technologies,34460A,MY123,1.0",
            ) as preflight,
            patch("meters_tool_cli.cli.run_start_session", return_value=fake_result) as runner,
        ):
            rc = cmd_start(args)

        self.assertEqual(0, rc)
        request_model, _trigger_mode, profile = runner.call_args.args[:3]
        self.assertEqual("34460A", request_model.instrument_model)
        self.assertEqual("34460A", profile.model)
        preflight.assert_called_once()

    def test_start_live_selected_model_mismatch_does_not_override_detected_profile(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--model",
                "34460A",
                "--csv",
                "data\\delegate_live.csv",
                "--trigger-mode",
                "immediate",
                "--max-samples",
                "1",
            ]
        )
        stderr = io.StringIO()

        with (
            patch(
                "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
                return_value="Keysight Technologies,34461A,MY123,1.0",
            ) as preflight,
            patch("meters_tool_cli.cli.run_start_session") as runner,
            redirect_stderr(stderr),
        ):
            rc = cmd_start(args)

        self.assertEqual(2, rc)
        self.assertIn(
            "Selected model 34460A does not match the connected instrument IDN 34461A",
            stderr.getvalue(),
        )
        runner.assert_not_called()
        preflight.assert_called_once()

    def test_start_live_34460a_full_suite_workflow_reaches_runner(self):
        parser = build_parser()
        fake_result = StartRunResult(
            run_id="run-123",
            ok=True,
            reason="completed",
            captured=1,
            errors=0,
            fatal_error=None,
            csv_path="data\\delegate_live.csv",
        )
        cases = [
            ("current-dc", "immediate", ["--max-samples", "1"]),
            ("current-ac", "immediate", ["--max-samples", "1"]),
            ("resistance-2w", "immediate", ["--max-samples", "1"]),
            ("voltage-dc", "software", ["--timer-interval-s", "1.0", "--max-samples", "1"]),
            ("voltage-dc", "immediate-custom", ["--trigger-count", "1", "--sample-count", "1"]),
            ("frequency", "immediate", ["--max-samples", "1"]),
            ("period", "immediate", ["--max-samples", "1"]),
        ]

        for measurement, trigger_mode, extra_args in cases:
            with self.subTest(measurement=measurement, trigger_mode=trigger_mode):
                args = parser.parse_args(
                    [
                        "start-trigger-record",
                        "--resource",
                        "USB0::FAKE::INSTR",
                        "--model",
                        "34460A",
                        "--csv",
                        "data\\delegate_live.csv",
                        "--measurement",
                        measurement,
                        "--trigger-mode",
                        trigger_mode,
                        *extra_args,
                    ]
                )
                with (
                    patch(
                        "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
                        return_value="Keysight Technologies,34460A,MY123,1.0",
                    ),
                    patch("meters_tool_cli.cli.run_start_session", return_value=fake_result) as runner,
                ):
                    rc = cmd_start(args)

                self.assertEqual(0, rc)
                runner.assert_called_once()

    def test_start_live_34460a_policy_closed_workflow_fails_before_runner(self):
        parser = build_parser()
        cases = [
            (
                [
                    "--measurement",
                    "voltage-dc-ratio",
                    "--trigger-mode",
                    "immediate",
                    "--max-samples",
                    "1",
                ],
                "34460A live support for --measurement voltage-dc-ratio is not validated",
            ),
            (
                [
                    "--visa-library",
                    "@py",
                    "--measurement",
                    "voltage-dc",
                    "--trigger-mode",
                    "immediate",
                    "--max-samples",
                    "1",
                ],
                "transport=usb, backend=pyvisa_py is pending",
            ),
        ]

        for extra_args, expected in cases:
            with self.subTest(expected=expected):
                args = parser.parse_args(
                    [
                        "start-trigger-record",
                        "--resource",
                        "USB0::FAKE::INSTR",
                        "--model",
                        "34460A",
                        "--csv",
                        "data\\delegate_live.csv",
                        *extra_args,
                    ]
                )
                stderr = io.StringIO()
                with (
                    patch(
                        "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
                        return_value="Keysight Technologies,34460A,MY123,1.0",
                    ),
                    patch("meters_tool_cli.cli.run_start_session") as runner,
                    redirect_stderr(stderr),
                ):
                    rc = cmd_start(args)

                self.assertEqual(2, rc)
                self.assertIn(expected, stderr.getvalue())
                runner.assert_not_called()

    def test_start_runner_final_gate_surfaces_error_if_adapter_resolution_is_wrong(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB0::FAKE::INSTR",
                "--csv",
                "data\\delegate_live.csv",
                "--measurement",
                "voltage-dc-ratio",
                "--trigger-mode",
                "immediate",
                "--max-samples",
                "1",
            ]
        )
        stderr = io.StringIO()

        def wrong_adapter_resolution(request_model):  # noqa: ANN001
            return request_model, KEYSIGHT_34461A_PROFILE

        with (
            patch("meters_tool_cli.cli.resolve_start_profile", side_effect=wrong_adapter_resolution),
            patch("meters_tool_cli.cli.validate_start_request"),
            patch("meters_tool_cli.cli.validate_start_workflow_support"),
            patch(
                "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
                return_value="Keysight Technologies,34460A,MY123,1.0",
            ),
            redirect_stderr(stderr),
        ):
            rc = cmd_start(args)

        self.assertEqual(2, rc)
        self.assertIn(
            "34460A live support for --measurement voltage-dc-ratio is not validated",
            stderr.getvalue(),
        )

    def test_start_simulate_selected_model_does_not_run_visa_preflight(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "SIM::34460A",
                "--model",
                "34460A",
                "--csv",
                "data\\simulate_no_preflight.csv",
                "--simulate",
                "--trigger-mode",
                "immediate",
                "--max-samples",
                "1",
            ]
        )
        fake_result = StartRunResult(
            run_id="run-123",
            ok=True,
            reason="completed",
            captured=1,
            errors=0,
            fatal_error=None,
            csv_path="data\\simulate_no_preflight.csv",
        )

        with (
            patch("meters_tool_core.start_resolution.VisaInstrument.preflight_idn") as preflight,
            patch("meters_tool_cli.cli.run_start_session", return_value=fake_result) as runner,
        ):
            rc = cmd_start(args)

        self.assertEqual(0, rc)
        preflight.assert_not_called()
        self.assertEqual("34460A", runner.call_args.args[2].model)

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
        self.assertFalse(payload["dry_run_performs_visa_io"])
        self.assertFalse(payload["dry_run_writes_csv"])
        self.assertFalse(payload["dry_run_starts_http_server"])
        self.assertEqual("current-dc", payload["measurement_cli_name"])
        self.assertNotIn("measurement_name", payload)
        self.assertEqual("FETC?", payload["read_path"])
        self.assertIn("TRIG:SOUR EXT", payload["scpi_commands"])
        self.assertNotIn("run_id", payload)

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

    def test_period_dry_run_rejects_explicit_frequency_timeout_before_visa(self):
        stderr = io.StringIO()

        with (
            patch(
                "meters_tool_core.instrument.VisaInstrument.connect"
            ) as mock_connect,
            redirect_stderr(stderr),
        ):
            rc = main(
                [
                    "start-trigger-record",
                    "--resource",
                    "USB::FAKE",
                    "--model",
                    "34461A",
                    "--measurement",
                    "period",
                    "--freq-period-timeout",
                    "auto",
                    "--dry-run",
                ]
            )

        self.assertEqual(2, rc)
        self.assertIn(
            "--freq-period-timeout is not supported for --measurement period",
            stderr.getvalue(),
        )
        mock_connect.assert_not_called()

    def test_start_model_34460a_dry_run_uses_profile_limits(self):
        cases = [
            (
                "current-dc-range-3",
                [
                    "--model",
                    "34460A",
                    "--measurement",
                    "current-dc",
                    "--auto-range",
                    "off",
                    "--range",
                    "3",
                    "--trigger-mode",
                    "immediate",
                    "--max-samples",
                    "1",
                    "--dry-run",
                ],
                0,
                "",
            ),
            (
                "current-dc-range-10",
                [
                    "--model",
                    "34460A",
                    "--measurement",
                    "current-dc",
                    "--auto-range",
                    "off",
                    "--range",
                    "10",
                    "--trigger-mode",
                    "immediate",
                    "--max-samples",
                    "1",
                    "--dry-run",
                ],
                2,
                "--range 10 is not valid for --measurement current-dc",
            ),
            (
                "overflow-without-allow",
                [
                    "--model",
                    "34460A",
                    "--measurement",
                    "voltage-dc",
                    "--trigger-mode",
                    "immediate-custom",
                    "--trigger-count",
                    "1",
                    "--sample-count",
                    "1001",
                    "--dry-run",
                ],
                2,
                "custom mode expected readings 1001 exceed 34460A reading memory 1000",
            ),
            (
                "overflow-with-allow",
                [
                    "--model",
                    "34460A",
                    "--measurement",
                    "voltage-dc",
                    "--trigger-mode",
                    "immediate-custom",
                    "--trigger-count",
                    "1",
                    "--sample-count",
                    "1001",
                    "--allow-buffer-overflow-risk",
                    "--dry-run",
                ],
                0,
                "",
            ),
        ]
        for name, extra_args, expected_rc, expected_error in cases:
            with self.subTest(name=name):
                stdout = io.StringIO()
                stderr = io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    rc = main(["start-trigger-record", "--resource", "USB::FAKE", *extra_args])

                self.assertEqual(expected_rc, rc)
                if expected_error:
                    self.assertIn(expected_error, stderr.getvalue())

    def test_start_json_alias_sets_jsonl_status_format(self):
        parser = build_parser()
        args = parser.parse_args(["start-trigger-record", "--resource", "USB::FAKE", "--json"])

        self.assertEqual("jsonl", args.status_format)

    def test_start_parser_accepts_instrument_model_aliases(self):
        parser = build_parser()

        model_args = parser.parse_args(
            ["start-trigger-record", "--resource", "USB::FAKE", "--model", "34460A"]
        )
        instrument_model_args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--instrument-model",
                "34461A",
            ]
        )

        self.assertEqual("34460A", model_args.instrument_model)
        self.assertEqual("34461A", instrument_model_args.instrument_model)

    def test_start_parser_preserves_lowercase_model_for_core_validation(self):
        parser = build_parser()

        args = parser.parse_args(
            ["start-trigger-record", "--resource", "USB::FAKE", "--model", "34461a"]
        )

        self.assertEqual("34461a", args.instrument_model)

    def test_start_parser_accepts_visa_library_aliases(self):
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

    def test_start_json_alias_conflicts_with_text_status_format(self):
        parser = build_parser()

        with self.assertRaises(SystemExit) as exc:
            parser.parse_args(
                [
                    "start-trigger-record",
                    "--resource",
                    "USB::FAKE",
                    "--json",
                    "--status-format",
                    "text",
                ]
            )

        self.assertEqual(2, exc.exception.code)

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

    def test_start_removed_enable_hw_trigger_flag_is_rejected_by_parser(self):
        parser = build_parser()
        stderr = io.StringIO()

        with redirect_stderr(stderr), self.assertRaises(SystemExit) as exc:
            parser.parse_args(
                [
                    "start-trigger-record",
                    "--resource",
                    "USB::FAKE",
                    "--csv",
                    "data\\dry_run.csv",
                    "--measurement",
                    "current-dc",
                    "--dry-run",
                    "--enable-hw-trigger",
                    "--status-format",
                    "jsonl",
                ]
            )

        self.assertEqual(2, exc.exception.code)
        self.assertIn("unrecognized arguments: --enable-hw-trigger", stderr.getvalue())

    def test_start_non_dry_run_delegates_to_core_runner_with_start_request(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "SIM::34461A",
                "--model",
                "34461A",
                "--visa-library",
                "@py",
                "--csv",
                "data\\delegate.csv",
                "--trigger-mode",
                "immediate",
                "--measurement",
                "current-ac",
                "--auto-range",
                "off",
                "--range",
                "10",
                "--ac-bandwidth-hz",
                "20",
                "--current-terminal",
                "10",
                "--simulate",
                "--max-samples",
                "1",
                "--status-format",
                "jsonl",
            ]
        )
        stdout = io.StringIO()

        fake_result = StartRunResult(
            run_id="run-123",
            ok=True,
            reason="completed",
            captured=1,
            errors=0,
            fatal_error=None,
            csv_path="data\\delegate.csv",
        )
        with (
            redirect_stdout(stdout),
            patch("meters_tool_cli.cli.run_start_session", return_value=fake_result) as mock_runner,
        ):
            rc = cmd_start(args)

        self.assertEqual(0, rc)
        mock_runner.assert_called_once()
        request_model, trigger_mode, _profile, event_sink, controls = mock_runner.call_args.args
        self.assertIsInstance(request_model, StartRequest)
        self.assertEqual("SIM::34461A", request_model.resource)
        self.assertEqual("34461A", request_model.instrument_model)
        self.assertEqual("@py", request_model.visa_library)
        self.assertEqual("data\\delegate.csv", request_model.csv)
        self.assertTrue(request_model.simulate)
        self.assertEqual("current-ac", request_model.measurement)
        self.assertFalse(request_model.auto_range)
        self.assertEqual(10.0, request_model.measurement_range)
        self.assertEqual(20.0, request_model.ac_bandwidth_hz)
        self.assertEqual(10, request_model.current_terminal)
        self.assertFalse(hasattr(request_model, "status_format"))
        self.assertFalse(hasattr(request_model, "enable_hw_trigger"))
        self.assertEqual("immediate", trigger_mode)
        self.assertEqual("CliStartRunEventSink", type(event_sink).__name__)
        self.assertEqual("CliStartRunControls", type(controls).__name__)
        self.assertIn("run_id", mock_runner.call_args.kwargs)

    def test_start_normalizes_blank_visa_library_before_runner(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "SIM::34461A",
                "--visa-library",
                "   ",
                "--csv",
                "data\\delegate.csv",
                "--trigger-mode",
                "immediate",
                "--measurement",
                "voltage-dc",
                "--simulate",
                "--max-samples",
                "1",
            ]
        )

        fake_result = StartRunResult(
            run_id="run-123",
            ok=True,
            reason="completed",
            captured=1,
            errors=0,
            fatal_error=None,
            csv_path="data\\delegate.csv",
        )
        with patch("meters_tool_cli.cli.run_start_session", return_value=fake_result) as mock_runner:
            rc = cmd_start(args)

        self.assertEqual(0, rc)
        request_model = mock_runner.call_args.args[0]
        self.assertIsNone(request_model.visa_library)

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
            patch("meters_tool_core.runner.SoftwareTriggerAdapter", FakeStartServer),
            patch("meters_tool_core.runner.CsvWriter", FakeCapturingCsvWriter),
            patch("meters_tool_cli.cli.WindowsConsoleStopHandler", FakeStartConsoleHandler),
            patch("meters_tool_cli.cli.WindowsKeyboardStopPoller", FakeStartKeyboardPoller),
            patch("meters_tool_cli.cli.signal.signal", side_effect=lambda _sig, _handler: None),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            rc = cmd_start(args)

        self.assertEqual(0, rc)
        self.assertEqual(1, len(FakeCapturingCsvWriter.samples))
        self.assertIn("captured=1 errors=0", stdout.getvalue())
        self.assertIn("command endpoint: http://127.0.0.1:8765/command", stdout.getvalue())
        self.assertNotIn("ready", stdout.getvalue())

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

    def test_start_simulate_status_endpoint_reports_worker_status(self):
        parser = build_parser()
        port = self._unused_local_port()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "SIM::34461A",
                "--csv",
                "data\\simulate_status.csv",
                "--trigger-mode",
                "software",
                "--measurement",
                "current-dc",
                "--simulate",
                "--max-samples",
                "1",
                "--sw-trigger-port",
                str(port),
                "--sw-min-interval-ms",
                "50",
                "--sw-queue-max",
                "7",
            ]
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        result = {}

        def run_command() -> None:
            try:
                with (
                    patch("meters_tool_core.runner.CsvWriter", FakeCapturingCsvWriter),
                    patch("meters_tool_cli.cli.WindowsConsoleStopHandler", FakeStartConsoleHandler),
                    patch("meters_tool_cli.cli.WindowsKeyboardStopPoller", FakeStartKeyboardPoller),
                    patch("meters_tool_cli.cli.signal.signal", side_effect=lambda _sig, _handler: None),
                    redirect_stdout(stdout),
                    redirect_stderr(stderr),
                ):
                    result["rc"] = cmd_start(args)
            except BaseException as exc:  # pragma: no cover - re-raised in the test thread
                result["exception"] = exc

        worker = threading.Thread(target=run_command)
        worker.start()
        payload = None
        try:
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                try:
                    with request.urlopen(f"http://127.0.0.1:{port}/status", timeout=0.5) as resp:
                        payload = json.loads(resp.read().decode("utf-8"))
                        self.assertEqual(200, resp.status)
                        break
                except (OSError, TimeoutError, URLError):
                    if not worker.is_alive():
                        break
                    time.sleep(0.05)

            self.assertIsNotNone(payload)
            assert payload is not None
            self.assertEqual(1, payload["schema_version"])
            self.assertEqual("keysight-meter", payload["service"])
            self.assertEqual("running", payload["status"])
            self.assertEqual(f"http://127.0.0.1:{port}/command", payload["command_url"])
            self.assertEqual(f"http://127.0.0.1:{port}/stop", payload["stop_url"])
            self.assertEqual(f"http://127.0.0.1:{port}/status", payload["status_url"])
            self.assertEqual(0, payload["queue_size"])
            self.assertEqual(7, payload["queue_max"])
            self.assertEqual(50, payload["min_interval_ms"])
            self.assertEqual(0, payload["captured"])
            self.assertEqual(0, payload["errors"])
            self.assertIsNone(payload["fatal_error"])
            self.assertIsInstance(payload["run_id"], str)

            trigger_req = request.Request(
                f"http://127.0.0.1:{port}/command",
                method="POST",
                data=b'{"command":"software_trigger"}',
                headers={"Content-Type": "application/json"},
            )
            with request.urlopen(trigger_req, timeout=1.0) as resp:
                self.assertEqual(202, resp.status)
        finally:
            if worker.is_alive():
                try:
                    stop_req = request.Request(
                        f"http://127.0.0.1:{port}/stop",
                        method="POST",
                        data=b"{}",
                        headers={"Content-Type": "application/json"},
                    )
                    request.urlopen(stop_req, timeout=1.0).close()
                except (OSError, TimeoutError, URLError):
                    pass
            worker.join(timeout=5.0)

        self.assertFalse(worker.is_alive())
        if "exception" in result:
            raise result["exception"]
        self.assertEqual(0, result.get("rc"))
        self.assertIn(f"software status endpoint: http://127.0.0.1:{port}/status", stdout.getvalue())

    def test_start_simulate_jsonl_trigger_mode_matrix(self):
        parser = build_parser()
        cases = [
            (
                "immediate",
                [
                    "--trigger-mode",
                    "immediate",
                    "--max-samples",
                    "1",
                ],
                1,
                0,
            ),
            (
                "software",
                [
                    "--trigger-mode",
                    "software",
                    "--max-samples",
                    "2",
                ],
                2,
                2,
            ),
            (
                "software-timer",
                [
                    "--trigger-mode",
                    "software",
                    "--timer-interval-s",
                    "0.5",
                    "--max-samples",
                    "1",
                ],
                1,
                0,
            ),
            (
                "immediate-custom",
                [
                    "--trigger-mode",
                    "immediate-custom",
                    "--trigger-count",
                    "2",
                    "--sample-count",
                    "2",
                ],
                4,
                0,
            ),
            (
                "software-custom",
                [
                    "--trigger-mode",
                    "software-custom",
                    "--trigger-count",
                    "2",
                    "--sample-count",
                    "2",
                ],
                4,
                2,
            ),
            (
                "external-custom",
                [
                    "--trigger-mode",
                    "external-custom",
                    "--trigger-count",
                    "2",
                    "--sample-count",
                    "2",
                ],
                4,
                0,
            ),
        ]

        for name, mode_args, expected_samples, trigger_count in cases:
            with self.subTest(name=name):
                args = parser.parse_args(
                    [
                        "start-trigger-record",
                        "--resource",
                        "SIM::34461A",
                        "--csv",
                        f"data\\simulate_{name}.csv",
                        "--measurement",
                        "current-dc",
                        "--simulate",
                        "--status-format",
                        "jsonl",
                        *mode_args,
                    ]
                )

                rc, output, _stderr = self._run_cmd_start_with_simulate_harness(
                    args,
                    software_trigger_count=trigger_count,
                    trigger_metadata={"agent": name},
                )

                self.assertEqual(0, rc)
                events = self._parse_jsonl_events(output)
                self._assert_success_jsonl_events(events, expected_samples)

    def test_start_simulate_external_jsonl_uses_hardware_trigger_event(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "SIM::34461A",
                "--csv",
                "data\\simulate_external.csv",
                "--trigger-mode",
                "external",
                "--measurement",
                "current-dc",
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
        self.assertEqual("hardware", sample["trigger_source"])
        summary = [event for event in events if event["event"] == "summary"][-1]
        self.assertEqual(1, summary["captured"])
        self.assertEqual(0, summary["errors"])
        self.assertIs(True, summary["ok"])

    def test_start_simulate_immediate_custom_jsonl_drains_buffer_in_batches(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "SIM::34461A",
                "--csv",
                "data\\simulate_immediate_custom_batches.csv",
                "--trigger-mode",
                "immediate-custom",
                "--measurement",
                "current-dc",
                "--simulate",
                "--trigger-count",
                "1",
                "--sample-count",
                "5",
                "--buffer-drain-size",
                "2",
                "--status-format",
                "jsonl",
            ]
        )

        rc, output, _stderr = self._run_cmd_start_with_simulate_harness(args)

        self.assertEqual(0, rc)
        events = self._parse_jsonl_events(output)
        self._assert_success_jsonl_events(events, expected_samples=5)
        samples = [event for event in events if event["event"] == "sample"]
        self.assertEqual(
            ["2", "2", "2", "2", "1"],
            [sample["trigger_metadata"]["buffer_batch_size"] for sample in samples],
        )
        self.assertEqual(
            ["0", "1", "2", "3", "4"],
            [sample["trigger_metadata"]["buffer_index"] for sample in samples],
        )

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
        self.assertIn("simulated read failure", summary["fatal_error"])

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
        self.assertIn("buffered capture failure", summary["fatal_error"])

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
        self.assertIn("cannot open CSV output file", summary["fatal_error"])

    def test_start_simulate_queue_pressure_stop_control_is_accepted(self):
        parser = build_parser()
        QueuePressureStopStartServer.trigger_accepted = False
        QueuePressureStopStartServer.stop_accepted = False
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "SIM::34461A",
                "--csv",
                "data\\simulate_stop_pressure.csv",
                "--trigger-mode",
                "software-custom",
                "--measurement",
                "current-dc",
                "--simulate",
                "--trigger-count",
                "1",
                "--sample-count",
                "1",
                "--sw-queue-max",
                "1",
                "--status-format",
                "jsonl",
            ]
        )

        rc, output, _stderr = self._run_cmd_start_with_simulate_harness(
            args,
            server_cls=QueuePressureStopStartServer,
        )

        self.assertEqual(0, rc)
        self.assertTrue(QueuePressureStopStartServer.trigger_accepted)
        self.assertTrue(QueuePressureStopStartServer.stop_accepted)
        events = self._parse_jsonl_events(output)
        summary = [event for event in events if event["event"] == "summary"][-1]
        self.assertEqual(0, summary["captured"])
        self.assertEqual(0, summary["errors"])
        self.assertIs(True, summary["ok"])

    def test_start_simulate_writes_real_csv_smoke(self):
        parser = build_parser()
        with tempfile.TemporaryDirectory() as tempdir:
            csv_path = Path(tempdir) / "simulate.csv"
            args = parser.parse_args(
                [
                    "start-trigger-record",
                    "--resource",
                    "SIM::34461A",
                    "--csv",
                    str(csv_path),
                    "--trigger-mode",
                    "software",
                    "--measurement",
                    "current-dc",
                    "--simulate",
                    "--max-samples",
                    "1",
                ]
            )

            rc, _output, _stderr = self._run_cmd_start_with_simulate_harness(
                args,
                software_trigger_count=1,
                trigger_metadata={"operator": "agent", "purpose": "csv-smoke"},
                csv_writer=None,
            )

            self.assertEqual(0, rc)
            with csv_path.open(newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                fieldnames = reader.fieldnames
                rows = list(reader)

        self.assertEqual(
            [
                "timestamp_utc_plus_8",
                "measurement_type",
                "value",
                "unit",
                "trigger_id",
                "trigger_source",
                "trigger_metadata",
                "measurement_metadata",
                "resource_id",
                "status",
            ],
            fieldnames,
        )
        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertEqual("current_dc", row["measurement_type"])
        self.assertEqual("A", row["unit"])
        self.assertEqual("software", row["trigger_source"])
        self.assertEqual("SIM::34461A", row["resource_id"])
        self.assertEqual("ok", row["status"])
        metadata = json.loads(row["trigger_metadata"])
        self.assertEqual({"operator": "agent", "purpose": "csv-smoke"}, metadata)
        self.assertEqual({}, json.loads(row["measurement_metadata"]))

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

    def test_start_dry_run_conflicts_with_simulate(self):
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
                "current-dc",
                "--dry-run",
                "--simulate",
                "--max-samples",
                "1",
            ]
        )
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            rc = cmd_start(args)

        self.assertEqual(2, rc)
        self.assertIn("--dry-run and --simulate cannot be used together", stderr.getvalue())

    def test_start_simulate_immediate_custom_no_max_samples_ok(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "SIM::34461A",
                "--csv",
                "data\\sim_custom.csv",
                "--trigger-mode",
                "immediate-custom",
                "--measurement",
                "current-dc",
                "--simulate",
                "--trigger-count",
                "2",
                "--sample-count",
                "3",
            ]
        )
        stdout = io.StringIO()

        with (
            patch("meters_tool_core.runner.SoftwareTriggerAdapter", FakeStartServer),
            patch("meters_tool_core.runner.CsvWriter", FakeCapturingCsvWriter),
            patch("meters_tool_cli.cli.WindowsConsoleStopHandler", FakeStartConsoleHandler),
            patch("meters_tool_cli.cli.WindowsKeyboardStopPoller", FakeStartKeyboardPoller),
            patch("meters_tool_cli.cli.signal.signal", side_effect=lambda _sig, _handler: None),
            redirect_stdout(stdout),
        ):
            rc = cmd_start(args)

        self.assertEqual(0, rc)
        self.assertIn("captured=6 errors=0", stdout.getvalue())

    def test_main_dispatches_start_trigger_record(self):
        with patch("meters_tool_cli.cli.cmd_start", return_value=23) as mock_cmd:
            rc = main(["start-trigger-record", "--resource", "USB::FAKE"])

        self.assertEqual(23, rc)
        self.assertEqual("USB::FAKE", mock_cmd.call_args.args[0].resource)



if __name__ == "__main__":
    unittest.main()
