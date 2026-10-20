from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from meters_tool_cli._runtime_output import CliEventEmitter, CliStartRunEventSink
from meters_tool_cli.cli import (
    build_parser,
    cmd_start,
    main,
)
from meters_tool_core.models import KEYSIGHT_34461A_PROFILE, StartRequest
from meters_tool_core.session import StartRunEvent, StartRunResult
from meters_tool_core.support_policy import (
    SUPPORT_POLICY_MODE_PRODUCT,
    SUPPORT_POLICY_MODE_VALIDATION,
)

from cli_command_helpers import (
    CliCommandHarnessMixin,
    ConnectFailingStartInstrument,
    FakeStartKeyboardPoller,
    FakeStartServer,
    InstalledConsoleHandler,
)


class CliStartCommandTests(CliCommandHarnessMixin, unittest.TestCase):
    def _worker_status(self, *, fatal_error=None):
        return {
            "schema_version": 2,
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
                    "--validation-allow-pending-live-support",
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

    def test_start_infinite_custom_flags_reach_request_and_exit_code(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--model",
                "34461A",
                "--simulate",
                "--trigger-mode",
                "software-custom",
                "--trigger-count-infinite",
                "--monitor-overflow",
                "--stop-on-overflow",
                "--sample-count",
                "2",
                "--allow-buffer-overflow-risk",
                "--validation-allow-pending-live-support",
                "--json",
            ]
        )
        fake_result = StartRunResult(
            run_id="run-123",
            ok=False,
            reason="overflow_detected",
            captured=0,
            errors=0,
            fatal_error=None,
            csv_path=None,
            trigger_count_infinite=True,
            overflow_monitoring="active",
            overflow_detected=True,
            stop_reason="overflow_detected",
            data_integrity="incomplete",
        )

        with patch("meters_tool_cli.cli.run_start_session", return_value=fake_result) as runner:
            rc = cmd_start(args)

        self.assertEqual(3, rc)
        request_model, trigger_mode, _profile = runner.call_args.args[:3]
        self.assertEqual("software-custom", trigger_mode)
        self.assertTrue(request_model.trigger_count_infinite)
        self.assertTrue(request_model.monitor_overflow)
        self.assertTrue(request_model.stop_on_overflow)
        self.assertIsNone(request_model.trigger_count)
        self.assertEqual(2, request_model.sample_count)

    def test_summary_event_preserves_core_ok_and_structured_fields(self):
        lines: list[str] = []
        sink = CliStartRunEventSink(
            CliEventEmitter(print_fn=lines.append, output_format="jsonl")
        )

        sink.emit(
            StartRunEvent.summary_event(
                "run-123",
                0,
                1,
                None,
                ok=False,
                trigger_count_infinite=True,
                expected_readings=None,
                overflow_monitoring="failed",
                overflow_detected=None,
                stop_reason="overflow_monitor_failed",
                final_drain_complete=True,
                data_integrity="unknown",
            )
        )

        summary = json.loads(lines[-1])
        self.assertEqual("summary", summary["event"])
        self.assertIs(False, summary["ok"])
        self.assertIs(True, summary["trigger_count_infinite"])
        self.assertIsNone(summary["expected_readings"])
        self.assertEqual("failed", summary["overflow_monitoring"])
        self.assertIsNone(summary["overflow_detected"])
        self.assertEqual("overflow_monitor_failed", summary["stop_reason"])
        self.assertIs(True, summary["final_drain_complete"])
        self.assertEqual("unknown", summary["data_integrity"])

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

    def test_start_live_34461a_validated_lan_scopes_reach_runner(self):
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
            (
                [
                    "--resource",
                    "TCPIP0::host::inst0::INSTR",
                ],
                None,
            ),
            (
                [
                    "--resource",
                    "TCPIP::host::INSTR",
                    "--visa-library",
                    "@py",
                ],
                "@py",
            ),
            (
                [
                    "--resource",
                    "TCPIP::host::INSTR",
                    "--backend",
                    "@py",
                ],
                "@py",
            ),
        ]

        for resource_args, expected_visa_library in cases:
            with self.subTest(visa_library=expected_visa_library):
                args = parser.parse_args(
                    [
                        "start-trigger-record",
                        *resource_args,
                        "--model",
                        "34461A",
                        "--csv",
                        "data\\delegate_live.csv",
                        "--measurement",
                        "voltage-dc",
                        "--trigger-mode",
                        "immediate",
                        "--max-samples",
                        "1",
                    ]
                )
                with (
                    patch(
                        "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
                        return_value="Keysight Technologies,34461A,MY123,1.0",
                    ),
                    patch("meters_tool_cli.cli.run_start_session", return_value=fake_result) as runner,
                ):
                    rc = cmd_start(args)

                self.assertEqual(0, rc)
                request_model = runner.call_args.args[0]
                self.assertEqual(expected_visa_library, request_model.visa_library)
                runner.assert_called_once()

    def test_start_live_34460a_policy_closed_workflow_fails_before_runner(self):
        parser = build_parser()
        cases = [
            (
                [
                    "--visa-library",
                    "@py",
                    "--measurement",
                    "voltage-dc-ratio",
                    "--trigger-mode",
                    "immediate",
                    "--max-samples",
                    "1",
                ],
                "not registered for transport=usb, backend=pyvisa_py",
            ),
            (
                [
                    "--resource",
                    "TCPIP0::host::inst0::INSTR",
                    "--measurement",
                    "voltage-dc-ratio",
                    "--trigger-mode",
                    "immediate",
                    "--max-samples",
                    "1",
                ],
                "start-trigger-record is pending for transport=tcpip, backend=system_visa",
            ),
            (
                [
                    "--resource",
                    "TCPIP::host::INSTR",
                    "--backend",
                    "@py",
                    "--measurement",
                    "voltage-dc-ratio",
                    "--trigger-mode",
                    "immediate",
                    "--max-samples",
                    "1",
                ],
                "start-trigger-record is pending for transport=tcpip, backend=pyvisa_py",
            ),
        ]

        for extra_args, expected in cases:
            with self.subTest(expected=expected):
                args = parser.parse_args(
                    [
                        "start-trigger-record",
                        "--model",
                        "34460A",
                        "--csv",
                        "data\\delegate_live.csv",
                        "--resource",
                        "USB0::FAKE::INSTR",
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

    def test_hidden_validation_flag_allows_pending_34460a_lan_and_passes_mode_to_runner(self):
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
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--validation-allow-pending-live-support",
                "--resource",
                "TCPIP0::host::inst0::INSTR",
                "--model",
                "34460A",
                "--csv",
                "data\\delegate_live.csv",
                "--measurement",
                "voltage-dc",
                "--trigger-mode",
                "immediate",
                "--max-samples",
                "1",
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
        self.assertEqual(
            SUPPORT_POLICY_MODE_VALIDATION,
            runner.call_args.kwargs["support_policy_mode"],
        )

    def test_product_mode_allows_promoted_34460a_ratio_without_hidden_validation_flag(self):
        parser = build_parser()
        fake_result = StartRunResult(
            run_id="run-ratio",
            ok=True,
            reason="completed",
            captured=1,
            errors=0,
            fatal_error=None,
            csv_path="data\\ratio_validation.csv",
        )
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB0::FAKE::INSTR",
                "--model",
                "34460A",
                "--csv",
                "data\\ratio_validation.csv",
                "--measurement",
                "voltage-dc-ratio",
                "--trigger-mode",
                "immediate",
                "--max-samples",
                "1",
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
        request_model = runner.call_args.args[0]
        self.assertEqual("voltage-dc-ratio", request_model.measurement)
        self.assertEqual(
            SUPPORT_POLICY_MODE_PRODUCT,
            runner.call_args.kwargs["support_policy_mode"],
        )

    def test_hidden_validation_flag_does_not_bypass_34460a_profile_limits(self):
        parser = build_parser()
        cases = [
            (
                ["--trigger-mode", "external", "--max-samples", "1"],
                "--trigger-mode external is not supported by 34460A",
            ),
            (
                [
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
                ],
                "--range 10 is not valid",
            ),
        ]

        for extra_args, expected in cases:
            with self.subTest(expected=expected):
                args = parser.parse_args(
                    [
                        "start-trigger-record",
                        "--validation-allow-pending-live-support",
                        "--resource",
                        "USB0::FAKE::INSTR",
                        "--model",
                        "34460A",
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

    def test_hidden_validation_flag_does_not_bypass_missing_feature_metadata(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--validation-allow-pending-live-support",
                "--resource",
                "USB0::FAKE::INSTR",
                "--model",
                "34460A",
                "--measurement",
                "voltage-dc",
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
                return_value="Keysight Technologies,34460A,MY123,1.0",
            ),
            patch("meters_tool_core.support_policy.find_feature_support", return_value=None),
            patch("meters_tool_cli.cli.run_start_session") as runner,
            redirect_stderr(stderr),
        ):
            rc = cmd_start(args)

        self.assertEqual(2, rc)
        self.assertIn(
            "live feature support is not registered for measurement=voltage-dc",
            stderr.getvalue(),
        )
        runner.assert_not_called()

    def test_hidden_validation_flag_is_not_in_start_help(self):
        parser = build_parser()
        stdout = io.StringIO()

        with redirect_stdout(stdout), self.assertRaises(SystemExit) as exc:
            parser.parse_args(["start-trigger-record", "--help"])

        self.assertEqual(0, exc.exception.code)
        self.assertNotIn("--validation-allow-pending-live-support", stdout.getvalue())

    def test_start_runner_final_gate_surfaces_error_if_adapter_resolution_is_wrong(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "TCPIP0::host::inst0::INSTR",
                "--csv",
                "data\\delegate_live.csv",
                "--measurement",
                "voltage-dc",
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
            "start-trigger-record is pending for transport=tcpip, backend=system_visa",
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
                "--csv-format",
                "full",
                "--csv-time-columns",
                "elapsed,delta",
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
        self.assertTrue(request_model.csv_enabled)
        self.assertEqual("full", request_model.csv_format)
        self.assertEqual(("elapsed", "delta"), request_model.csv_time_columns)
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

    def test_start_normalizes_blank_optional_text_before_runner(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "SIM::34461A",
                "--visa-library",
                "   ",
                "--csv",
                "   ",
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
        self.assertIsNone(request_model.csv)
        self.assertTrue(request_model.csv_enabled)

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

    def test_main_dispatches_start_trigger_record(self):
        with patch("meters_tool_cli.cli.cmd_start", return_value=23) as mock_cmd:
            rc = main(["start-trigger-record", "--resource", "USB::FAKE"])

        self.assertEqual(23, rc)
        self.assertEqual("USB::FAKE", mock_cmd.call_args.args[0].resource)


if __name__ == "__main__":
    unittest.main()
