from __future__ import annotations

import io
import csv
import json
import socket
import tempfile
import threading
import time
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from urllib import request
from urllib.error import URLError

from keysight_logger.cli import (
    WindowsConsoleStopHandler,
    WindowsKeyboardStopPoller,
    build_parser,
    cmd_list_resources,
    cmd_start,
    cmd_soft_status,
    cmd_soft_trigger,
    cmd_soft_stop,
    cmd_wait_ready,
    get_cli_version,
    main,
)
from keysight_logger.core.instrument import InstrumentError
from keysight_logger.core.models import (
    StartRequest,
    TriggerEvent,
    TriggerSource,
)
from keysight_logger.core.runner import StopController
from keysight_logger.core.session import StartRunResult
from keysight_logger.core.simulator import SimulatedVisaInstrument


class CliArgsTests(unittest.TestCase):
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
            "soft-trigger",
            "soft-stop",
            "soft-status",
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
            "list-resources": ["--dry-run", "--json", "--format"],
            "start-trigger-record": ["--dry-run", "--simulate", "--json", "--status-format"],
            "soft-trigger": ["--dry-run", "--json", "--format", "--timeout-ms"],
            "soft-stop": ["--dry-run", "--json", "--format", "--timeout-ms"],
            "soft-status": ["--dry-run", "--json", "--format", "--timeout-ms"],
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
        self.assertIn("AC bandwidth choices for AC current/voltage: 3, 20, 200 Hz", help_text)
        self.assertIn("current terminal choices for current measurements: 3, 10", help_text)

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


class StopControllerTests(unittest.TestCase):
    def test_signal_stop_first_interrupt_is_graceful(self):
        calls = []
        controller = StopController(lambda: calls.append("stop"))

        controller.request_signal_stop()

        self.assertTrue(controller.stop)
        self.assertFalse(controller.force)
        self.assertEqual(1, controller.interrupt_count)
        self.assertEqual(["stop"], calls)
        self.assertEqual(
            ["interrupt received, stopping gracefully (press Ctrl+C again to force)..."],
            controller.pop_messages(),
        )

    def test_signal_stop_second_interrupt_forces_shutdown(self):
        calls = []
        controller = StopController(lambda: calls.append("stop"))

        controller.request_signal_stop()
        controller.request_signal_stop()

        self.assertTrue(controller.stop)
        self.assertTrue(controller.force)
        self.assertEqual(2, controller.interrupt_count)
        self.assertEqual(["stop", "stop"], calls)
        self.assertEqual(
            "second interrupt received, forcing shutdown...",
            controller.pop_messages()[-1],
        )

    def test_http_stop_does_not_count_as_keyboard_interrupt(self):
        calls = []
        controller = StopController(lambda: calls.append("stop"))

        controller.request_http_stop()

        self.assertTrue(controller.stop)
        self.assertFalse(controller.force)
        self.assertEqual(0, controller.interrupt_count)
        self.assertEqual(["stop"], calls)
        self.assertEqual([], controller.pop_messages())


class WindowsConsoleStopHandlerTests(unittest.TestCase):
    def test_ctrl_c_event_requests_stop(self):
        calls = []
        controller = StopController(lambda: calls.append("stop"))
        handler = WindowsConsoleStopHandler(controller)

        handled = handler._handle(0)

        self.assertTrue(handled)
        self.assertTrue(controller.stop)
        self.assertEqual(1, controller.interrupt_count)
        self.assertEqual(["stop"], calls)

    def test_ctrl_break_event_requests_stop(self):
        calls = []
        controller = StopController(lambda: calls.append("stop"))
        handler = WindowsConsoleStopHandler(controller)

        handled = handler._handle(1)

        self.assertTrue(handled)
        self.assertTrue(controller.stop)
        self.assertEqual(1, controller.interrupt_count)
        self.assertEqual(["stop"], calls)

    def test_non_interrupt_event_is_not_handled(self):
        calls = []
        controller = StopController(lambda: calls.append("stop"))
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


def make_publishing_start_server(trigger_count=0, metadata=None):
    class PublishingStartServer:
        def __init__(self, router, *_args, **_kwargs):
            self._router = router
            self.stopped = False

        def start(self):
            for _index in range(trigger_count):
                self._router.publish(
                    TriggerEvent.new(
                        TriggerSource.SOFTWARE,
                        metadata=dict(metadata or {}),
                    )
                )
            return "127.0.0.1", 8765

        def stop(self):
            self.stopped = True

    return PublishingStartServer


class FakeStartConsoleHandler:
    input_mode_configured = False

    def __init__(self, _controller):
        return

    def install(self):
        return False

    def uninstall(self):
        return


class InstalledConsoleHandler:
    input_mode_configured = False

    def __init__(self, _controller):
        return

    def install(self):
        return True

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


class FailingReadSimulatedVisaInstrument(SimulatedVisaInstrument):
    def query_ascii_float(self, command: str) -> float:
        if command.strip().upper() in {"READ?", "FETC?"}:
            raise RuntimeError("simulated read failure")
        return super().query_ascii_float(command)


class ShortBufferedReadSimulatedVisaInstrument(SimulatedVisaInstrument):
    def query(self, command: str) -> str:
        if command.strip().upper().startswith("DATA:REMOVE?"):
            return "1.23"
        return super().query(command)


class QueuePressureStopStartServer:
    trigger_accepted = False
    stop_accepted = False

    def __init__(self, router, *_args, **_kwargs):
        self._router = router
        self.stopped = False

    def start(self):
        type(self).trigger_accepted = self._router.publish(
            TriggerEvent.new(TriggerSource.SOFTWARE, {"queued": "first"})
        )
        type(self).stop_accepted = self._router.publish(
            TriggerEvent.new(TriggerSource.SOFTWARE, {"control": "stop"})
        )
        return "127.0.0.1", 8765

    def stop(self):
        self.stopped = True


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
    def _unused_local_port(self) -> int:
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                port = int(sock.getsockname()[1])
            if port >= 1024:
                return port

    def _run_cmd_start_with_simulate_harness(
        self,
        args,
        *,
        software_trigger_count=0,
        trigger_metadata=None,
        csv_writer=FakeCapturingCsvWriter,
        instrument_cls=None,
        server_cls=None,
    ):
        stdout = io.StringIO()
        stderr = io.StringIO()
        if server_cls is None:
            server_cls = make_publishing_start_server(
                trigger_count=software_trigger_count,
                metadata=trigger_metadata,
            )
        patches = [
            patch("keysight_logger.core.runner.SoftwareTriggerAdapter", server_cls),
            patch("keysight_logger.cli.WindowsConsoleStopHandler", InstalledConsoleHandler),
            patch("keysight_logger.cli.WindowsKeyboardStopPoller", FakeStartKeyboardPoller),
            patch("keysight_logger.cli.signal.signal", side_effect=lambda _sig, _handler: None),
        ]
        if csv_writer is not None:
            patches.append(patch("keysight_logger.core.runner.CsvWriter", csv_writer))
        if instrument_cls is not None:
            patches.append(
                patch(
                    "keysight_logger.core.runner.create_instrument_backend",
                    side_effect=lambda config, *, simulate, measurement_type: instrument_cls(
                        config,
                        measurement_type=measurement_type,
                    ),
                )
            )

        with ExitStack() as stack:
            for active_patch in patches:
                stack.enter_context(active_patch)
            stack.enter_context(redirect_stdout(stdout))
            stack.enter_context(redirect_stderr(stderr))
            rc = cmd_start(args)
        return rc, stdout.getvalue(), stderr.getvalue()

    def _parse_jsonl_events(self, output):
        events = [json.loads(line) for line in output.splitlines() if line.strip()]
        self.assertTrue(events)
        self.assertTrue(all(event["schema_version"] == 1 for event in events))
        self.assertTrue(all("event" in event for event in events))
        self.assertTrue(all("timestamp_utc" in event for event in events))
        return events

    def _assert_success_jsonl_events(self, events, expected_samples):
        event_names = {event["event"] for event in events}
        self.assertIn("message", event_names)
        self.assertIn("ready", event_names)
        self.assertIn("status", event_names)
        self.assertIn("sample", event_names)
        self.assertIn("summary", event_names)
        self.assertNotIn("error", event_names)
        correlated_events = [
            event for event in events if event["event"] in {"ready", "status", "sample", "summary"}
        ]
        run_ids = {event.get("run_id") for event in correlated_events}
        self.assertEqual(1, len(run_ids))
        self.assertIsInstance(next(iter(run_ids)), str)
        ready = [event for event in events if event["event"] == "ready"]
        self.assertEqual(1, len(ready))
        for key in ["run_id", "service", "host", "port", "trigger_url", "stop_url", "status_url"]:
            self.assertIn(key, ready[0])
        samples = [event for event in events if event["event"] == "sample"]
        self.assertEqual(expected_samples, len(samples))
        for sample in samples:
            self.assertIn("measurement_metadata", sample)
            self.assertIsInstance(sample["measurement_metadata"], dict)
        summary = [event for event in events if event["event"] == "summary"][-1]
        self.assertIn("captured", summary)
        self.assertIn("errors", summary)
        self.assertEqual(expected_samples, summary["captured"])
        self.assertEqual(0, summary["errors"])
        self.assertIs(True, summary["ok"])
        self.assertNotIn("fatal_error", summary)

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

    def test_soft_trigger_json_alias_uses_json_format(self):
        parser = build_parser()
        args = parser.parse_args(["soft-trigger", "--json"])

        self.assertEqual("json", args.output_format)

    def test_soft_trigger_json_alias_conflicts_with_text_format(self):
        parser = build_parser()

        with self.assertRaises(SystemExit) as exc:
            parser.parse_args(["soft-trigger", "--json", "--format", "text"])

        self.assertEqual(2, exc.exception.code)

    def test_soft_trigger_dry_run_prints_preview_without_request(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout), patch("keysight_logger.cli.request.urlopen") as mock_urlopen:
            rc = cmd_soft_trigger(8765, '{"operator": "tom"}', dry_run=True)

        self.assertEqual(0, rc)
        self.assertIn("dry-run soft-trigger:", stdout.getvalue())
        self.assertIn("http://127.0.0.1:8765/trigger", stdout.getvalue())
        mock_urlopen.assert_not_called()

    def test_soft_trigger_dry_run_json_emits_preview_object(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout), patch("keysight_logger.cli.request.urlopen") as mock_urlopen:
            rc = cmd_soft_trigger(8765, '{"operator": "tom"}', output_format="json", dry_run=True)

        self.assertEqual(0, rc)
        events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(1, len(events))
        self.assertEqual("dry_run", events[0]["event"])
        self.assertEqual("dry_run", events[0]["status"])
        self.assertEqual("POST", events[0]["method"])
        self.assertFalse(events[0]["send_request"])
        self.assertEqual({"operator": "tom"}, events[0]["body"])
        mock_urlopen.assert_not_called()

    def test_soft_trigger_dry_run_invalid_json_returns_error(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = cmd_soft_trigger(8765, "{bad json", output_format="json", dry_run=True)

        self.assertEqual(2, rc)
        events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(1, len(events))
        self.assertEqual("error", events[0]["event"])

    def test_soft_trigger_main_dispatches_dry_run(self):
        with patch("keysight_logger.cli.cmd_soft_trigger", return_value=19) as mock_cmd:
            rc = main(["soft-trigger", "--dry-run", "--json"])

        self.assertEqual(19, rc)
        mock_cmd.assert_called_once_with(8765, "{}", "json", True, 3000)

    def test_soft_trigger_timeout_ms_is_validated_before_request(self):
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            rc = main(["soft-trigger", "--timeout-ms", "99"])

        self.assertEqual(2, rc)
        self.assertIn("--timeout-ms 99 is outside the supported range 100-600000", stderr.getvalue())

    @patch("keysight_logger.cli.request.urlopen")
    def test_soft_trigger_uses_configured_timeout(self, mock_urlopen):
        class FakeResponse:
            status = 202

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        mock_urlopen.return_value = FakeResponse()

        rc = cmd_soft_trigger(8765, "{}", timeout_ms=2000)

        self.assertEqual(0, rc)
        self.assertEqual(2.0, mock_urlopen.call_args.kwargs["timeout"])

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

    def test_soft_stop_json_alias_uses_json_format(self):
        parser = build_parser()
        args = parser.parse_args(["soft-stop", "--json"])

        self.assertEqual("json", args.output_format)

    def test_soft_stop_json_alias_conflicts_with_text_format(self):
        parser = build_parser()

        with self.assertRaises(SystemExit) as exc:
            parser.parse_args(["soft-stop", "--json", "--format", "text"])

        self.assertEqual(2, exc.exception.code)

    def test_soft_stop_dry_run_prints_preview_without_request(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout), patch("keysight_logger.cli.request.urlopen") as mock_urlopen:
            rc = cmd_soft_stop(8765, dry_run=True)

        self.assertEqual(0, rc)
        self.assertIn("dry-run soft-stop:", stdout.getvalue())
        self.assertIn("http://127.0.0.1:8765/stop", stdout.getvalue())
        mock_urlopen.assert_not_called()

    def test_soft_stop_dry_run_json_emits_preview_object(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout), patch("keysight_logger.cli.request.urlopen") as mock_urlopen:
            rc = cmd_soft_stop(8765, output_format="json", dry_run=True)

        self.assertEqual(0, rc)
        events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(1, len(events))
        self.assertEqual("dry_run", events[0]["event"])
        self.assertEqual("dry_run", events[0]["status"])
        self.assertEqual("POST", events[0]["method"])
        self.assertFalse(events[0]["send_request"])
        self.assertEqual({}, events[0]["body"])
        mock_urlopen.assert_not_called()

    def test_soft_stop_main_dispatches_dry_run(self):
        with patch("keysight_logger.cli.cmd_soft_stop", return_value=21) as mock_cmd:
            rc = main(["soft-stop", "--dry-run", "--json"])

        self.assertEqual(21, rc)
        mock_cmd.assert_called_once_with(8765, "json", True, 3000)

    @patch("keysight_logger.cli.request.urlopen")
    def test_soft_stop_uses_configured_timeout(self, mock_urlopen):
        class FakeResponse:
            status = 204

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        mock_urlopen.return_value = FakeResponse()

        rc = cmd_soft_stop(8765, timeout_ms=2000)

        self.assertEqual(0, rc)
        self.assertEqual(2.0, mock_urlopen.call_args.kwargs["timeout"])

    @patch("keysight_logger.cli.request.urlopen", side_effect=URLError("offline"))
    def test_soft_stop_non_connection_refused_url_error_returns_3(self, _mock_urlopen):
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            rc = cmd_soft_stop(8765)

        self.assertEqual(3, rc)
        self.assertIn("stop request failed", stderr.getvalue())

    def test_soft_status_json_alias_uses_json_format(self):
        parser = build_parser()
        args = parser.parse_args(["soft-status", "--json"])

        self.assertEqual("json", args.output_format)

    def test_soft_status_json_alias_conflicts_with_text_format(self):
        parser = build_parser()

        with self.assertRaises(SystemExit) as exc:
            parser.parse_args(["soft-status", "--json", "--format", "text"])

        self.assertEqual(2, exc.exception.code)

    def test_wait_ready_json_alias_uses_json_format(self):
        parser = build_parser()
        args = parser.parse_args(["wait-ready", "--json"])

        self.assertEqual("json", args.output_format)

    def test_wait_ready_json_alias_conflicts_with_text_format(self):
        parser = build_parser()

        with self.assertRaises(SystemExit) as exc:
            parser.parse_args(["wait-ready", "--json", "--format", "text"])

        self.assertEqual(2, exc.exception.code)

    def test_soft_status_port_is_validated_before_request(self):
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            rc = main(["soft-status", "--port", "0"])

        self.assertEqual(2, rc)
        self.assertIn("--port 0 is outside the supported range 1-65535", stderr.getvalue())

    def test_wait_ready_timeout_ms_is_validated_before_request(self):
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            rc = main(["wait-ready", "--timeout-ms", "99"])

        self.assertEqual(2, rc)
        self.assertIn("--timeout-ms 99 is outside the supported range 100-600000", stderr.getvalue())

    def _worker_status(self, *, fatal_error=None):
        return {
            "schema_version": 1,
            "service": "keysight-meter",
            "run_id": "run-123",
            "status": "running",
            "trigger_url": "http://127.0.0.1:8765/trigger",
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

    @patch("keysight_logger.cli.request.urlopen")
    def test_soft_status_gets_status_and_emits_normalized_json(self, mock_urlopen):
        mock_urlopen.return_value = self._fake_json_response(self._worker_status())
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_soft_status(8765, output_format="json")

        self.assertEqual(0, rc)
        req = mock_urlopen.call_args.args[0]
        self.assertEqual("http://127.0.0.1:8765/status", req.full_url)
        self.assertEqual("GET", req.get_method())
        self.assertEqual(3.0, mock_urlopen.call_args.kwargs["timeout"])
        event = json.loads(stdout.getvalue())
        self.assertEqual("soft-status", event["event"])
        self.assertTrue(event["ok"])
        self.assertTrue(event["reachable"])
        self.assertTrue(event["running"])
        self.assertEqual("run-123", event["run_id"])
        self.assertEqual(1, event["worker_schema_version"])
        self.assertEqual("2026-05-31T00:00:00+00:00", event["worker_timestamp_utc"])

    @patch("keysight_logger.cli.request.urlopen")
    def test_soft_status_text_mode_prints_summary(self, mock_urlopen):
        mock_urlopen.return_value = self._fake_json_response(self._worker_status())
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_soft_status(8765)

        self.assertEqual(0, rc)
        output = stdout.getvalue()
        self.assertIn("status: running captured=10 errors=0 fatal_error=null run_id=run-123", output)

    def test_soft_status_dry_run_json_emits_get_preview(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout), patch("keysight_logger.cli.request.urlopen") as mock_urlopen:
            rc = cmd_soft_status(8765, output_format="json", dry_run=True)

        self.assertEqual(0, rc)
        event = json.loads(stdout.getvalue())
        self.assertEqual("dry_run", event["event"])
        self.assertEqual("GET", event["method"])
        self.assertIsNone(event["body"])
        self.assertEqual("http://127.0.0.1:8765/status", event["url"])
        self.assertFalse(event["send_request"])
        mock_urlopen.assert_not_called()

    @patch("keysight_logger.cli.request.urlopen", side_effect=URLError("offline"))
    def test_soft_status_unreachable_json_emits_status_error(self, _mock_urlopen):
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_soft_status(8765, output_format="json")

        self.assertEqual(3, rc)
        event = json.loads(stdout.getvalue())
        self.assertEqual("soft-status", event["event"])
        self.assertFalse(event["ok"])
        self.assertFalse(event["reachable"])
        self.assertEqual(3, event["exit_code"])

    @patch("keysight_logger.cli.request.urlopen")
    def test_soft_status_fatal_error_exits_0_with_ok_false(self, mock_urlopen):
        mock_urlopen.return_value = self._fake_json_response(self._worker_status(fatal_error="boom"))
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_soft_status(8765, output_format="json")

        self.assertEqual(0, rc)
        event = json.loads(stdout.getvalue())
        self.assertFalse(event["ok"])
        self.assertTrue(event["reachable"])
        self.assertEqual("boom", event["fatal_error"])

    @patch("keysight_logger.cli.request.urlopen")
    def test_wait_ready_succeeds_on_first_successful_status(self, mock_urlopen):
        mock_urlopen.return_value = self._fake_json_response(self._worker_status())
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_wait_ready(8765, output_format="json", timeout_ms=10000)

        self.assertEqual(0, rc)
        event = json.loads(stdout.getvalue())
        self.assertEqual("wait-ready", event["event"])
        self.assertEqual(1, event["attempts"])
        self.assertEqual(10000, event["timeout_ms"])
        self.assertTrue(event["reachable"])

    @patch("keysight_logger.cli.time.sleep")
    @patch("keysight_logger.cli.request.urlopen")
    def test_wait_ready_retries_after_transient_url_error(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = [
            URLError("offline"),
            self._fake_json_response(self._worker_status()),
        ]
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_wait_ready(8765, output_format="json", timeout_ms=10000)

        self.assertEqual(0, rc)
        event = json.loads(stdout.getvalue())
        self.assertEqual(2, event["attempts"])
        mock_sleep.assert_called()

    @patch("keysight_logger.cli.time.sleep")
    @patch("keysight_logger.cli.request.urlopen", side_effect=URLError("offline"))
    def test_wait_ready_timeout_emits_json_error(self, _mock_urlopen, _mock_sleep):
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_wait_ready(8765, output_format="json", timeout_ms=100)

        self.assertEqual(3, rc)
        event = json.loads(stdout.getvalue())
        self.assertEqual("wait-ready", event["event"])
        self.assertFalse(event["ok"])
        self.assertFalse(event["reachable"])
        self.assertEqual(3, event["exit_code"])
        self.assertIn("timed out waiting for status endpoint after 100 ms", event["message"])

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
        fake_backend = FakeStartInstrument(None)

        with (
            patch("keysight_logger.core.runner.create_instrument_backend", return_value=fake_backend),
            patch("keysight_logger.core.runner.SoftwareTriggerAdapter", FakeStartServer),
            patch("keysight_logger.core.runner.CsvWriter", PermissionDeniedCsvWriter),
            patch(
                "keysight_logger.core.runner.create_measurement_plugin",
                return_value=FakeStartMeasurement(),
            ),
            patch("keysight_logger.cli.WindowsConsoleStopHandler", InstalledConsoleHandler),
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
        fake_backend = ConnectFailingStartInstrument(None)

        with (
            patch("keysight_logger.core.runner.create_instrument_backend", return_value=fake_backend),
            patch("keysight_logger.core.runner.SoftwareTriggerAdapter", FakeStartServer),
            patch("keysight_logger.cli.WindowsConsoleStopHandler", InstalledConsoleHandler),
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
            patch("keysight_logger.core.runner.create_instrument_backend") as mock_factory,
            patch("keysight_logger.core.runner.SoftwareTriggerAdapter") as mock_server,
            redirect_stdout(stdout),
        ):
            rc = cmd_start(args)

        self.assertEqual(0, rc)
        self.assertIn("dry-run plan:", stdout.getvalue())
        self.assertIn("CONF:VOLT:DC AUTO", stdout.getvalue())
        self.assertNotIn("software status endpoint:", stdout.getvalue())
        mock_factory.assert_not_called()
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
        self.assertNotEqual("ready", payload["event"])
        for key in [
            "cleanup_steps",
            "csv_path",
            "dry_run",
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
        self.assertEqual("current-dc", payload["measurement_cli_name"])
        self.assertNotIn("measurement_name", payload)
        self.assertEqual("FETC?", payload["read_path"])
        self.assertIn("TRIG:SOUR EXT", payload["scpi_commands"])
        self.assertNotIn("run_id", payload)

    def test_start_json_alias_sets_jsonl_status_format(self):
        parser = build_parser()
        args = parser.parse_args(["start-trigger-record", "--resource", "USB::FAKE", "--json"])

        self.assertEqual("jsonl", args.status_format)

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
            patch("keysight_logger.cli.run_start_session", return_value=fake_result) as mock_runner,
        ):
            rc = cmd_start(args)

        self.assertEqual(0, rc)
        mock_runner.assert_called_once()
        request_model, trigger_mode, _profile, event_sink, controls = mock_runner.call_args.args
        self.assertIsInstance(request_model, StartRequest)
        self.assertEqual("SIM::34461A", request_model.resource)
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

    def test_start_dry_run_jsonl_overflow_warnings_are_plan_notes_only(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
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
            patch("keysight_logger.core.runner.create_instrument_backend", return_value=fake_backend),
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
            patch("keysight_logger.core.runner.SoftwareTriggerAdapter", FakeStartServer),
            patch("keysight_logger.core.runner.CsvWriter", FakeCapturingCsvWriter),
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
        self.assertIn("software trigger endpoint: http://127.0.0.1:8765/trigger", stdout.getvalue())
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
        self.assertEqual("http://127.0.0.1:8765/trigger", ready[0]["trigger_url"])
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
                    patch("keysight_logger.core.runner.CsvWriter", FakeCapturingCsvWriter),
                    patch("keysight_logger.cli.WindowsConsoleStopHandler", FakeStartConsoleHandler),
                    patch("keysight_logger.cli.WindowsKeyboardStopPoller", FakeStartKeyboardPoller),
                    patch("keysight_logger.cli.signal.signal", side_effect=lambda _sig, _handler: None),
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
            self.assertEqual(f"http://127.0.0.1:{port}/trigger", payload["trigger_url"])
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
                f"http://127.0.0.1:{port}/trigger",
                method="POST",
                data=b"{}",
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
            patch("keysight_logger.core.runner.SoftwareTriggerAdapter", FakeStartServer),
            patch("keysight_logger.core.runner.CsvWriter", FakeCapturingCsvWriter),
            patch("keysight_logger.cli.WindowsConsoleStopHandler", FakeStartConsoleHandler),
            patch("keysight_logger.cli.WindowsKeyboardStopPoller", FakeStartKeyboardPoller),
            patch("keysight_logger.cli.signal.signal", side_effect=lambda _sig, _handler: None),
            redirect_stdout(stdout),
        ):
            rc = cmd_start(args)

        self.assertEqual(0, rc)
        self.assertIn("captured=6 errors=0", stdout.getvalue())


    @patch("keysight_logger.cli.VisaInstrument")
    def test_list_resources_without_verify_prints_resources(self, mock_visa):
        mock_visa.list_resources.return_value = ["USB::LIVE"]
        lines = []

        rc = cmd_list_resources(verify=False, print_fn=lines.append)

        self.assertEqual(0, rc)
        self.assertEqual(["USB::LIVE"], lines)
        mock_visa.verify_resource.assert_not_called()

    @patch("keysight_logger.cli.VisaInstrument")
    def test_list_resources_dry_run_text_outputs_contract_without_discovery(self, mock_visa):
        lines = []

        rc = cmd_list_resources(dry_run=True, print_fn=lines.append)

        self.assertEqual(0, rc)
        self.assertIn("dry-run list-resources:", lines)
        self.assertIn("  output_format: text", lines)
        self.assertIn("  verify: false", lines)
        self.assertIn("  live_only: false", lines)
        self.assertIn("  effective_verify: false", lines)
        self.assertIn("  dry_run_performs_visa_io: false", lines)
        self.assertIn("  VISA I/O: no", lines)
        self.assertIn("    list VISA resources: yes", lines)
        mock_visa.list_resources.assert_not_called()
        mock_visa.verify_resource.assert_not_called()

    @patch("keysight_logger.cli.VisaInstrument")
    def test_list_resources_dry_run_json_outputs_one_contract_without_discovery(self, mock_visa):
        lines = []

        rc = cmd_list_resources(dry_run=True, output_format="json", print_fn=lines.append)

        self.assertEqual(0, rc)
        self.assertEqual(1, len(lines))
        payload = json.loads(lines[0])
        self.assertEqual("dry_run", payload["event"])
        self.assertEqual("list-resources", payload["command"])
        self.assertEqual("json", payload["output_format"])
        self.assertFalse(payload["dry_run_performs_visa_io"])
        self.assertFalse(payload["effective_verify"])
        for key in [
            "close_each_resource",
            "filter_live_only",
            "list_visa_resources",
            "open_each_resource",
            "query_idn",
            "release_to_local_after_successful_verify",
        ]:
            self.assertIn(key, payload["planned_real_run"])
        self.assertFalse(payload["planned_real_run"]["query_idn"])
        mock_visa.list_resources.assert_not_called()
        mock_visa.verify_resource.assert_not_called()

    def test_list_resources_dry_run_verify_json_sets_effective_verify(self):
        lines = []

        rc = cmd_list_resources(
            verify=True,
            dry_run=True,
            output_format="json",
            print_fn=lines.append,
        )

        self.assertEqual(0, rc)
        payload = json.loads(lines[0])
        self.assertTrue(payload["verify"])
        self.assertTrue(payload["effective_verify"])
        self.assertTrue(payload["planned_real_run"]["open_each_resource"])
        self.assertTrue(payload["planned_real_run"]["query_idn"])

    def test_list_resources_dry_run_live_only_json_sets_effective_verify_and_filter(self):
        lines = []

        rc = cmd_list_resources(
            live_only=True,
            dry_run=True,
            output_format="json",
            print_fn=lines.append,
        )

        self.assertEqual(0, rc)
        payload = json.loads(lines[0])
        self.assertTrue(payload["live_only"])
        self.assertTrue(payload["effective_verify"])
        self.assertTrue(payload["planned_real_run"]["filter_live_only"])
        self.assertTrue(payload["planned_real_run"]["query_idn"])

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
        mock_cmd.assert_called_once_with(
            verify=False,
            live_only=True,
            output_format="json",
            dry_run=False,
        )

    def test_main_dispatches_list_resources_dry_run_json(self):
        with patch("keysight_logger.cli.cmd_list_resources", return_value=17) as mock_cmd:
            rc = main(["list-resources", "--dry-run", "--json"])

        self.assertEqual(17, rc)
        mock_cmd.assert_called_once_with(
            verify=False,
            live_only=False,
            output_format="json",
            dry_run=True,
        )

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


    @patch(
        "keysight_logger.cli.request.urlopen",
        side_effect=URLError(ConnectionRefusedError(10061, "refused")),
    )
    def test_soft_stop_connection_refused_json_returns_formatted_json(self, _mock_urlopen):
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_soft_stop(8765, output_format="json")

        self.assertEqual(0, rc)
        events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(1, len(events))
        self.assertEqual("soft-stop", events[0]["event"])
        self.assertEqual("already_stopped", events[0]["status"])

class CliCommandJsonTests(unittest.TestCase):
    def _worker_status(self, *, fatal_error=None, status="running"):
        return {
            "schema_version": 1,
            "service": "keysight-meter",
            "run_id": "run-123",
            "status": status,
            "trigger_url": "http://127.0.0.1:8765/trigger",
            "stop_url": "http://127.0.0.1:8765/stop",
            "status_url": "http://127.0.0.1:8765/status",
            "queue_size": 0,
            "queue_max": 10000,
            "min_interval_ms": 0,
            "captured": 1,
            "errors": 0,
            "fatal_error": fatal_error,
            "timestamp_utc": "2026-05-31T00:00:00+00:00",
        }

    def _fake_json_response(self, payload, *, status=200):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(payload).encode("utf-8")

        FakeResponse.status = status
        return FakeResponse()

    def _assert_parseable_timestamp(self, payload):
        datetime.fromisoformat(payload["timestamp_utc"])

    def _assert_client_contract(
        self,
        payload,
        *,
        event,
        client_command,
        ok,
        port=8765,
        request_sent,
    ):
        self._assert_parseable_timestamp(payload)
        self.assertEqual(event, payload["event"])
        self.assertEqual(client_command, payload["client_command"])
        self.assertEqual(ok, payload["ok"])
        self.assertEqual(port, payload["port"])
        self.assertEqual(request_sent, payload["request_sent"])
        self.assertEqual(1, payload["schema_version"])

    def _assert_error_contract(self, payload, *, client_command, error_phase, exit_code, port=8765):
        self._assert_client_contract(
            payload,
            event="error",
            client_command=client_command,
            ok=False,
            port=port,
            request_sent=error_phase == "request",
        )
        self.assertEqual(error_phase, payload["error_phase"])
        self.assertEqual(exit_code, payload["exit_code"])
        self.assertIn("reachable", payload)

    def test_soft_trigger_invalid_meta_json_returns_error_event(self):
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_soft_trigger(8765, "{bad json", output_format="json")

        self.assertEqual(2, rc)
        events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(1, len(events))
        self.assertEqual("error", events[0]["event"])
        self.assertEqual(2, events[0]["exit_code"])
        self.assertIn("meta must be valid JSON", events[0]["message"])
        self._assert_error_contract(
            events[0],
            client_command="soft-trigger",
            error_phase="validation",
            exit_code=2,
        )

    @patch("keysight_logger.cli.request.urlopen")
    def test_soft_trigger_success_json_returns_accepted_event(self, mock_urlopen):
        class FakeResponse:
            status = 202

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        mock_urlopen.return_value = FakeResponse()
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = cmd_soft_trigger(8765, '{"operator": "tom"}', output_format="json")
        self.assertEqual(0, rc)
        events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(1, len(events))
        self.assertEqual("soft-trigger", events[0]["event"])
        self.assertEqual("accepted", events[0]["status"])
        self.assertEqual(202, events[0]["http_status"])
        self._assert_client_contract(
            events[0],
            event="soft-trigger",
            client_command="soft-trigger",
            ok=True,
            request_sent=True,
        )
        self.assertTrue(events[0]["reachable"])

    @patch("keysight_logger.cli.request.urlopen", side_effect=URLError("offline"))
    def test_soft_trigger_url_error_json_returns_error_event(self, _mock_urlopen):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = cmd_soft_trigger(8765, "{}", output_format="json")
        self.assertEqual(3, rc)
        events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(1, len(events))
        self.assertEqual("error", events[0]["event"])
        self.assertEqual(3, events[0]["exit_code"])
        self._assert_error_contract(
            events[0],
            client_command="soft-trigger",
            error_phase="request",
            exit_code=3,
        )

    @patch("keysight_logger.cli.request.urlopen")
    def test_soft_stop_success_json_returns_accepted_event(self, mock_urlopen):
        class FakeResponse:
            status = 204

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        mock_urlopen.return_value = FakeResponse()
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = cmd_soft_stop(8765, output_format="json")
        self.assertEqual(0, rc)
        events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(1, len(events))
        self.assertEqual("soft-stop", events[0]["event"])
        self.assertEqual("accepted", events[0]["status"])
        self.assertEqual(204, events[0]["http_status"])
        self._assert_client_contract(
            events[0],
            event="soft-stop",
            client_command="soft-stop",
            ok=True,
            request_sent=True,
        )
        self.assertTrue(events[0]["reachable"])

    @patch("keysight_logger.cli.request.urlopen", side_effect=URLError("offline"))
    def test_soft_stop_url_error_json_returns_error_event(self, _mock_urlopen):
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_soft_stop(8765, output_format="json")

        self.assertEqual(3, rc)
        events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(1, len(events))
        self.assertEqual("error", events[0]["event"])
        self.assertEqual(3, events[0]["exit_code"])
        self.assertIn("stop request failed", events[0]["message"])
        self._assert_error_contract(
            events[0],
            client_command="soft-stop",
            error_phase="request",
            exit_code=3,
        )

    @patch(
        "keysight_logger.cli.request.urlopen",
        side_effect=URLError(ConnectionRefusedError(10061, "refused")),
    )
    def test_soft_stop_already_stopped_json_contract(self, _mock_urlopen):
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_soft_stop(8765, output_format="json")

        self.assertEqual(0, rc)
        event = json.loads(stdout.getvalue())
        self._assert_client_contract(
            event,
            event="soft-stop",
            client_command="soft-stop",
            ok=True,
            request_sent=True,
        )
        self.assertEqual("already_stopped", event["status"])
        self.assertFalse(event["reachable"])

    def test_soft_trigger_dry_run_json_contract(self):
        stdout = io.StringIO()

        with redirect_stdout(stdout), patch("keysight_logger.cli.request.urlopen") as mock_urlopen:
            rc = cmd_soft_trigger(8765, '{"source":"contract"}', output_format="json", dry_run=True)

        self.assertEqual(0, rc)
        event = json.loads(stdout.getvalue())
        self._assert_client_contract(
            event,
            event="dry_run",
            client_command="soft-trigger",
            ok=True,
            request_sent=False,
        )
        self.assertEqual("dry_run", event["status"])
        self.assertFalse(event["send_request"])
        mock_urlopen.assert_not_called()

    def test_soft_stop_dry_run_json_contract(self):
        stdout = io.StringIO()

        with redirect_stdout(stdout), patch("keysight_logger.cli.request.urlopen") as mock_urlopen:
            rc = cmd_soft_stop(8765, output_format="json", dry_run=True)

        self.assertEqual(0, rc)
        event = json.loads(stdout.getvalue())
        self._assert_client_contract(
            event,
            event="dry_run",
            client_command="soft-stop",
            ok=True,
            request_sent=False,
        )
        self.assertEqual("dry_run", event["status"])
        self.assertFalse(event["send_request"])
        mock_urlopen.assert_not_called()

    @patch("keysight_logger.cli.request.urlopen")
    def test_soft_status_success_json_contract(self, mock_urlopen):
        mock_urlopen.return_value = self._fake_json_response(self._worker_status())
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_soft_status(8765, output_format="json")

        self.assertEqual(0, rc)
        event = json.loads(stdout.getvalue())
        self._assert_client_contract(
            event,
            event="soft-status",
            client_command="soft-status",
            ok=True,
            request_sent=True,
        )
        self.assertEqual("run-123", event["run_id"])
        self.assertTrue(event["reachable"])
        self.assertEqual(200, event["http_status"])

    @patch("keysight_logger.cli.request.urlopen")
    def test_soft_status_fatal_json_contract(self, mock_urlopen):
        mock_urlopen.return_value = self._fake_json_response(self._worker_status(fatal_error="boom"))
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_soft_status(8765, output_format="json")

        self.assertEqual(0, rc)
        event = json.loads(stdout.getvalue())
        self._assert_client_contract(
            event,
            event="soft-status",
            client_command="soft-status",
            ok=False,
            request_sent=True,
        )
        self.assertTrue(event["reachable"])
        self.assertEqual("boom", event["fatal_error"])

    @patch("keysight_logger.cli.request.urlopen", side_effect=URLError("offline"))
    def test_soft_status_unreachable_json_contract(self, _mock_urlopen):
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_soft_status(8765, output_format="json")

        self.assertEqual(3, rc)
        event = json.loads(stdout.getvalue())
        self._assert_client_contract(
            event,
            event="soft-status",
            client_command="soft-status",
            ok=False,
            request_sent=True,
        )
        self.assertEqual("request", event["error_phase"])
        self.assertEqual(3, event["exit_code"])
        self.assertFalse(event["reachable"])

    @patch("keysight_logger.cli.request.urlopen")
    def test_soft_status_invalid_json_includes_http_status(self, mock_urlopen):
        class BadJsonResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b"{bad json"

        mock_urlopen.return_value = BadJsonResponse()
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_soft_status(8765, output_format="json")

        self.assertEqual(3, rc)
        event = json.loads(stdout.getvalue())
        self._assert_client_contract(
            event,
            event="soft-status",
            client_command="soft-status",
            ok=False,
            request_sent=True,
        )
        self.assertTrue(event["reachable"])
        self.assertEqual(200, event["http_status"])

    def test_soft_status_dry_run_json_contract(self):
        stdout = io.StringIO()

        with redirect_stdout(stdout), patch("keysight_logger.cli.request.urlopen") as mock_urlopen:
            rc = cmd_soft_status(8765, output_format="json", dry_run=True)

        self.assertEqual(0, rc)
        event = json.loads(stdout.getvalue())
        self._assert_client_contract(
            event,
            event="dry_run",
            client_command="soft-status",
            ok=True,
            request_sent=False,
        )
        self.assertEqual("GET", event["method"])
        self.assertFalse(event["send_request"])
        mock_urlopen.assert_not_called()

    @patch("keysight_logger.cli.request.urlopen")
    def test_wait_ready_success_json_contract(self, mock_urlopen):
        mock_urlopen.return_value = self._fake_json_response(self._worker_status())
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_wait_ready(8765, output_format="json", timeout_ms=10000)

        self.assertEqual(0, rc)
        event = json.loads(stdout.getvalue())
        self._assert_client_contract(
            event,
            event="wait-ready",
            client_command="wait-ready",
            ok=True,
            request_sent=True,
        )
        self.assertEqual(1, event["attempts"])
        self.assertEqual(10000, event["timeout_ms"])

    @patch("keysight_logger.cli.time.sleep")
    @patch("keysight_logger.cli.request.urlopen")
    def test_wait_ready_retry_json_contract(self, mock_urlopen, _mock_sleep):
        mock_urlopen.side_effect = [
            URLError("offline"),
            self._fake_json_response(self._worker_status()),
        ]
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_wait_ready(8765, output_format="json", timeout_ms=10000)

        self.assertEqual(0, rc)
        event = json.loads(stdout.getvalue())
        self._assert_client_contract(
            event,
            event="wait-ready",
            client_command="wait-ready",
            ok=True,
            request_sent=True,
        )
        self.assertEqual(2, event["attempts"])

    @patch("keysight_logger.cli.time.sleep")
    @patch("keysight_logger.cli.request.urlopen", side_effect=URLError("offline"))
    def test_wait_ready_timeout_json_contract(self, _mock_urlopen, _mock_sleep):
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_wait_ready(8765, output_format="json", timeout_ms=100)

        self.assertEqual(3, rc)
        event = json.loads(stdout.getvalue())
        self._assert_client_contract(
            event,
            event="wait-ready",
            client_command="wait-ready",
            ok=False,
            request_sent=True,
        )
        self.assertEqual("request", event["error_phase"])
        self.assertEqual(3, event["exit_code"])
        self.assertFalse(event["reachable"])

    def test_invalid_port_json_validation_contract(self):
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = main(["soft-status", "--port", "0", "--json"])

        self.assertEqual(2, rc)
        event = json.loads(stdout.getvalue())
        self._assert_error_contract(
            event,
            client_command="soft-status",
            error_phase="validation",
            exit_code=2,
            port=0,
        )

    def test_invalid_timeout_json_validation_contract(self):
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = main(["wait-ready", "--timeout-ms", "99", "--json"])

        self.assertEqual(2, rc)
        event = json.loads(stdout.getvalue())
        self._assert_error_contract(
            event,
            client_command="wait-ready",
            error_phase="validation",
            exit_code=2,
        )

if __name__ == "__main__":
    unittest.main()
