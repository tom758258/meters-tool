from __future__ import annotations

import io
import csv
import json
import os
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib import request
from urllib.error import URLError

from meters_tool_cli.cli import (
    build_parser,
    cmd_start,
)

from cli_command_helpers import (
    CliCommandHarnessMixin,
    FakeCapturingCsvWriter,
    FakeStartConsoleHandler,
    FakeStartKeyboardPoller,
    FakeStartServer,
    QueuePressureStopStartServer,
)


class CliStartRuntimeTests(CliCommandHarnessMixin, unittest.TestCase):
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
            self.assertEqual(3, payload["schema_version"])
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
                data=b'{"schema_version":3,"command":"software_trigger"}',
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

    def test_start_simulate_no_csv_jsonl_runtime_conformance(self):
        parser = build_parser()
        with tempfile.TemporaryDirectory() as tempdir:
            previous_cwd = os.getcwd()
            try:
                os.chdir(tempdir)
                args = parser.parse_args(
                    [
                        "start-trigger-record",
                        "--resource",
                        "SIM::34461A",
                        "--no-csv",
                        "--measurement",
                        "current-dc",
                        "--simulate",
                        "--trigger-mode",
                        "immediate",
                        "--max-samples",
                        "2",
                        "--json",
                    ]
                )

                rc, output, stderr = self._run_cmd_start_with_simulate_harness(
                    args,
                    csv_writer=None,
                )
                remaining_entries = os.listdir(tempdir)
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(0, rc)
        self.assertEqual("", stderr)
        events = self._parse_jsonl_events(output)
        self._assert_success_jsonl_events(events, expected_samples=2)
        summary = [event for event in events if event["event"] == "summary"][-1]
        self.assertIs(True, summary["ok"])
        self.assertEqual([], remaining_entries)

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
        self.assertEqual("incomplete", summary["data_integrity"])

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
                    "--csv-format",
                    "full",
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


if __name__ == "__main__":
    unittest.main()
