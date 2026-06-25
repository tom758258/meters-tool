from __future__ import annotations

import io
import json
import socket
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from unittest.mock import patch

from keysight_logger_cli.cli import cmd_start
from keysight_logger_core.instrument import InstrumentError
from keysight_logger_core.models import TriggerEvent, TriggerSource
from keysight_logger_core.simulator import SimulatedVisaInstrument

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




class CliCommandHarnessMixin:
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
            patch("keysight_logger_core.runner.SoftwareTriggerAdapter", server_cls),
            patch("keysight_logger_cli.cli.WindowsConsoleStopHandler", InstalledConsoleHandler),
            patch("keysight_logger_cli.cli.WindowsKeyboardStopPoller", FakeStartKeyboardPoller),
            patch("keysight_logger_cli.cli.signal.signal", side_effect=lambda _sig, _handler: None),
        ]
        if csv_writer is not None:
            patches.append(patch("keysight_logger_core.runner.CsvWriter", csv_writer))
        if instrument_cls is not None:
            patches.append(
                patch(
                    "keysight_logger_core.runner.create_instrument_backend",
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
        for key in ["run_id", "service", "host", "port", "command_url", "stop_url", "status_url"]:
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

    def _worker_status(self, *, fatal_error=None, status="running"):
        return {
            "schema_version": 1,
            "service": "keysight-meter",
            "run_id": "run-123",
            "status": status,
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
