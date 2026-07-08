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
from meters_tool_core.models import StartRequest
from meters_tool_core.session import StartRunResult

from cli_command_helpers import CliCommandHarnessMixin
from cli_command_helpers import *  # noqa: F403

class CliClientCommandTests(CliCommandHarnessMixin, unittest.TestCase):
    def test_soft_trigger_port_is_validated_before_request(self):
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            rc = main(["send-command", "--port", "0"])

        self.assertEqual(2, rc)
        self.assertIn("--port 0 is outside the supported range 1-65535", stderr.getvalue())

    def test_soft_trigger_rejects_invalid_json_meta(self):
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            rc = cmd_send_command(8765, "{bad json")

        self.assertEqual(2, rc)
        self.assertIn("arguments-json must be valid JSON", stderr.getvalue())

    @patch("meters_tool_cli._client_commands.request.urlopen")
    def test_soft_trigger_posts_json_payload(self, mock_urlopen):
        class FakeResponse:
            status = 202

            def read(self):
                return b'{"status":"accepted","command":"software_trigger","job_id":null}'

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        mock_urlopen.return_value = FakeResponse()
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_send_command(8765, '{"metadata":{"operator": "tom"}}')

        self.assertEqual(0, rc)
        self.assertIn("command accepted: 202", stdout.getvalue())
        req = mock_urlopen.call_args.args[0]
        self.assertEqual("http://127.0.0.1:8765/command", req.full_url)
        self.assertEqual("POST", req.get_method())
        self.assertEqual(
            b'{"command":"software_trigger","arguments":{"metadata":{"operator":"tom"}}}',
            req.data,
        )

    def test_soft_trigger_json_alias_uses_json_format(self):
        parser = build_parser()
        args = parser.parse_args(["send-command", "--json"])

        self.assertEqual("json", args.output_format)

    def test_soft_trigger_json_alias_conflicts_with_text_format(self):
        parser = build_parser()

        with self.assertRaises(SystemExit) as exc:
            parser.parse_args(["send-command", "--json", "--format", "text"])

        self.assertEqual(2, exc.exception.code)

    def test_soft_trigger_dry_run_prints_preview_without_request(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout), patch("meters_tool_cli._client_commands.request.urlopen") as mock_urlopen:
            rc = cmd_send_command(8765, '{"metadata":{"operator": "tom"}}', dry_run=True)

        self.assertEqual(0, rc)
        self.assertIn("dry-run send-command:", stdout.getvalue())
        self.assertIn("http://127.0.0.1:8765/command", stdout.getvalue())
        mock_urlopen.assert_not_called()

    def test_soft_trigger_dry_run_json_emits_preview_object(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout), patch("meters_tool_cli._client_commands.request.urlopen") as mock_urlopen:
            rc = cmd_send_command(
                8765,
                '{"metadata":{"operator": "tom"}}',
                output_format="json",
                dry_run=True,
            )

        self.assertEqual(0, rc)
        events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(1, len(events))
        self.assertEqual("dry_run", events[0]["event"])
        self.assertEqual("dry_run", events[0]["status"])
        self.assertEqual("POST", events[0]["method"])
        self.assertFalse(events[0]["send_request"])
        self.assertEqual(
            {
                "command": "software_trigger",
                "arguments": {"metadata": {"operator": "tom"}},
            },
            events[0]["body"],
        )
        mock_urlopen.assert_not_called()

    def test_soft_trigger_dry_run_invalid_json_returns_error(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = cmd_send_command(8765, "{bad json", output_format="json", dry_run=True)

        self.assertEqual(2, rc)
        events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(1, len(events))
        self.assertEqual("error", events[0]["event"])

    def test_soft_trigger_main_dispatches_dry_run(self):
        with patch("meters_tool_cli.cli.cmd_send_command", return_value=19) as mock_cmd:
            rc = main(["send-command", "--dry-run", "--json"])

        self.assertEqual(19, rc)
        mock_cmd.assert_called_once_with(
            8765,
            "{}",
            "json",
            True,
            3000,
            command="software_trigger",
            job_id=None,
        )

    def test_soft_trigger_timeout_ms_is_validated_before_request(self):
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            rc = main(["send-command", "--timeout-ms", "99"])

        self.assertEqual(2, rc)
        self.assertIn("--timeout-ms 99 is outside the supported range 100-600000", stderr.getvalue())

    @patch("meters_tool_cli._client_commands.request.urlopen")
    def test_soft_trigger_uses_configured_timeout(self, mock_urlopen):
        class FakeResponse:
            status = 202

            def read(self):
                return b'{"status":"accepted","command":"software_trigger","job_id":null}'

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        mock_urlopen.return_value = FakeResponse()

        rc = cmd_send_command(8765, "{}", timeout_ms=2000)

        self.assertEqual(0, rc)
        self.assertEqual(2.0, mock_urlopen.call_args.kwargs["timeout"])

    @patch("meters_tool_cli._client_commands.request.urlopen", side_effect=URLError("offline"))
    def test_soft_command_url_error_returns_3(self, _mock_urlopen):
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            rc = cmd_send_command(8765, "{}")

        self.assertEqual(3, rc)
        self.assertIn("command request failed", stderr.getvalue())

    def test_soft_stop_port_is_validated_before_request(self):
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            rc = main(["stop", "--port", "65536"])

        self.assertEqual(2, rc)
        self.assertIn("--port 65536 is outside the supported range 1-65535", stderr.getvalue())

    @patch("meters_tool_cli._client_commands.request.urlopen")
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
            rc = cmd_stop(8765)

        self.assertEqual(0, rc)
        self.assertIn("stop accepted: 204", stdout.getvalue())
        req = mock_urlopen.call_args.args[0]
        self.assertEqual("http://127.0.0.1:8765/stop", req.full_url)
        self.assertEqual("POST", req.get_method())
        self.assertEqual(b"{}", req.data)

    def test_soft_stop_json_alias_uses_json_format(self):
        parser = build_parser()
        args = parser.parse_args(["stop", "--json"])

        self.assertEqual("json", args.output_format)

    def test_soft_stop_json_alias_conflicts_with_text_format(self):
        parser = build_parser()

        with self.assertRaises(SystemExit) as exc:
            parser.parse_args(["stop", "--json", "--format", "text"])

        self.assertEqual(2, exc.exception.code)

    def test_soft_stop_dry_run_prints_preview_without_request(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout), patch("meters_tool_cli._client_commands.request.urlopen") as mock_urlopen:
            rc = cmd_stop(8765, dry_run=True)

        self.assertEqual(0, rc)
        self.assertIn("dry-run stop:", stdout.getvalue())
        self.assertIn("http://127.0.0.1:8765/stop", stdout.getvalue())
        mock_urlopen.assert_not_called()

    def test_soft_stop_dry_run_json_emits_preview_object(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout), patch("meters_tool_cli._client_commands.request.urlopen") as mock_urlopen:
            rc = cmd_stop(8765, output_format="json", dry_run=True)

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
        with patch("meters_tool_cli.cli.cmd_stop", return_value=21) as mock_cmd:
            rc = main(["stop", "--dry-run", "--json"])

        self.assertEqual(21, rc)
        mock_cmd.assert_called_once_with(8765, "json", True, 3000)

    @patch("meters_tool_cli._client_commands.request.urlopen")
    def test_soft_stop_uses_configured_timeout(self, mock_urlopen):
        class FakeResponse:
            status = 204

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        mock_urlopen.return_value = FakeResponse()

        rc = cmd_stop(8765, timeout_ms=2000)

        self.assertEqual(0, rc)
        self.assertEqual(2.0, mock_urlopen.call_args.kwargs["timeout"])

    @patch("meters_tool_cli._client_commands.request.urlopen", side_effect=URLError("offline"))
    def test_soft_stop_non_connection_refused_url_error_returns_3(self, _mock_urlopen):
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            rc = cmd_stop(8765)

        self.assertEqual(3, rc)
        self.assertIn("stop request failed", stderr.getvalue())

    def test_soft_status_json_alias_uses_json_format(self):
        parser = build_parser()
        args = parser.parse_args(["status", "--json"])

        self.assertEqual("json", args.output_format)

    def test_soft_status_json_alias_conflicts_with_text_format(self):
        parser = build_parser()

        with self.assertRaises(SystemExit) as exc:
            parser.parse_args(["status", "--json", "--format", "text"])

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
            rc = main(["status", "--port", "0"])

        self.assertEqual(2, rc)
        self.assertIn("--port 0 is outside the supported range 1-65535", stderr.getvalue())

    def test_wait_ready_timeout_ms_is_validated_before_request(self):
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            rc = main(["wait-ready", "--timeout-ms", "99"])

        self.assertEqual(2, rc)
        self.assertIn("--timeout-ms 99 is outside the supported range 100-600000", stderr.getvalue())

    @patch("meters_tool_cli._client_commands.request.urlopen")
    def test_soft_status_gets_status_and_emits_normalized_json(self, mock_urlopen):
        mock_urlopen.return_value = self._fake_json_response(self._worker_status())
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_status(8765, output_format="json")

        self.assertEqual(0, rc)
        req = mock_urlopen.call_args.args[0]
        self.assertEqual("http://127.0.0.1:8765/status", req.full_url)
        self.assertEqual("GET", req.get_method())
        self.assertEqual(3.0, mock_urlopen.call_args.kwargs["timeout"])
        event = json.loads(stdout.getvalue())
        self.assertEqual("status", event["event"])
        self.assertTrue(event["ok"])
        self.assertTrue(event["reachable"])
        self.assertTrue(event["running"])
        self.assertEqual("run-123", event["run_id"])
        self.assertEqual(1, event["worker_schema_version"])
        self.assertEqual("2026-05-31T00:00:00+00:00", event["worker_timestamp_utc"])

    @patch("meters_tool_cli._client_commands.request.urlopen")
    def test_soft_status_text_mode_prints_summary(self, mock_urlopen):
        mock_urlopen.return_value = self._fake_json_response(self._worker_status())
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_status(8765)

        self.assertEqual(0, rc)
        output = stdout.getvalue()
        self.assertIn("status: running captured=10 errors=0 fatal_error=null run_id=run-123", output)

    def test_soft_status_dry_run_json_emits_get_preview(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout), patch("meters_tool_cli._client_commands.request.urlopen") as mock_urlopen:
            rc = cmd_status(8765, output_format="json", dry_run=True)

        self.assertEqual(0, rc)
        event = json.loads(stdout.getvalue())
        self.assertEqual("dry_run", event["event"])
        self.assertEqual("GET", event["method"])
        self.assertIsNone(event["body"])
        self.assertEqual("http://127.0.0.1:8765/status", event["url"])
        self.assertFalse(event["send_request"])
        mock_urlopen.assert_not_called()

    @patch("meters_tool_cli._client_commands.request.urlopen", side_effect=URLError("offline"))
    def test_soft_status_unreachable_json_emits_status_error(self, _mock_urlopen):
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_status(8765, output_format="json")

        self.assertEqual(3, rc)
        event = json.loads(stdout.getvalue())
        self.assertEqual("status", event["event"])
        self.assertFalse(event["ok"])
        self.assertFalse(event["reachable"])
        self.assertEqual(3, event["exit_code"])

    @patch("meters_tool_cli._client_commands.request.urlopen")
    def test_soft_status_fatal_error_exits_0_with_ok_false(self, mock_urlopen):
        mock_urlopen.return_value = self._fake_json_response(self._worker_status(fatal_error="boom"))
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_status(8765, output_format="json")

        self.assertEqual(0, rc)
        event = json.loads(stdout.getvalue())
        self.assertFalse(event["ok"])
        self.assertTrue(event["reachable"])
        self.assertEqual("boom", event["fatal_error"])

    @patch("meters_tool_cli._client_commands.request.urlopen")
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

    @patch("meters_tool_cli._client_commands.time.sleep")
    @patch("meters_tool_cli._client_commands.request.urlopen")
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

    @patch("meters_tool_cli._client_commands.time.sleep")
    @patch("meters_tool_cli._client_commands.request.urlopen", side_effect=URLError("offline"))
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

    @patch(
        "meters_tool_cli._client_commands.request.urlopen",
        side_effect=URLError(ConnectionRefusedError(10061, "refused")),
    )
    def test_soft_stop_connection_refused_returns_0(self, _mock_urlopen):
        rc = cmd_stop(8765)
        self.assertEqual(0, rc)

    @patch(
        "meters_tool_cli._client_commands.request.urlopen",
        side_effect=URLError(ConnectionRefusedError(10061, "refused")),
    )
    def test_soft_stop_connection_refused_json_returns_formatted_json(self, _mock_urlopen):
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_stop(8765, output_format="json")

        self.assertEqual(0, rc)
        events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(1, len(events))
        self.assertEqual("stop", events[0]["event"])
        self.assertEqual("already_stopped", events[0]["status"])



class CliClientCommandJsonTests(CliCommandHarnessMixin, unittest.TestCase):
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
        for key in ("method", "url", "endpoint"):
            self.assertIn(key, payload)
        if request_sent:
            self.assertIn("timeout_ms", payload)
            self.assertIn("elapsed_ms", payload)

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
            rc = cmd_send_command(8765, "{bad json", output_format="json")

        self.assertEqual(2, rc)
        events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(1, len(events))
        self.assertEqual("error", events[0]["event"])
        self.assertEqual(2, events[0]["exit_code"])
        self.assertIn("arguments-json must be valid JSON", events[0]["message"])
        self._assert_error_contract(
            events[0],
            client_command="send-command",
            error_phase="validation",
            exit_code=2,
        )

    @patch("meters_tool_cli._client_commands.request.urlopen")
    def test_soft_trigger_success_json_returns_accepted_event(self, mock_urlopen):
        class FakeResponse:
            status = 202

            def read(self):
                return b'{"status":"accepted","command":"software_trigger","job_id":"job-1"}'

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        mock_urlopen.return_value = FakeResponse()
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = cmd_send_command(
                8765,
                '{"metadata":{"operator": "tom"}}',
                output_format="json",
                job_id="job-1",
            )
        self.assertEqual(0, rc)
        events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(1, len(events))
        self.assertEqual("send-command", events[0]["event"])
        self.assertEqual("accepted", events[0]["status"])
        self.assertEqual(202, events[0]["http_status"])
        self._assert_client_contract(
            events[0],
            event="send-command",
            client_command="send-command",
            ok=True,
            request_sent=True,
        )
        self.assertTrue(events[0]["reachable"])
        self.assertEqual("software_trigger", events[0]["command"])
        self.assertEqual("job-1", events[0]["job_id"])

    def test_soft_trigger_rejects_non_object_metadata_before_request(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout), patch("meters_tool_cli._client_commands.request.urlopen") as mock_urlopen:
            rc = cmd_send_command(8765, '{"metadata":[]}', output_format="json")

        self.assertEqual(2, rc)
        event = json.loads(stdout.getvalue())
        self.assertEqual("validation", event["error_phase"])
        self.assertEqual("validation_error", event["error"])
        self.assertEqual("software_trigger", event["command"])
        mock_urlopen.assert_not_called()

    @patch("meters_tool_cli._client_commands.request.urlopen")
    def test_soft_trigger_http_400_merges_worker_response_and_returns_2(self, mock_urlopen):
        body = io.BytesIO(
            b'{"status":"error","command":"software_trigger","job_id":"job-1",'
            b'"error":"validation_error","message":"metadata must be a JSON object"}'
        )
        mock_urlopen.side_effect = HTTPError(
            "http://127.0.0.1:8765/command",
            400,
            "Bad Request",
            {},
            body,
        )
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = cmd_send_command(8765, "{}", output_format="json", job_id="job-1")

        self.assertEqual(2, rc)
        event = json.loads(stdout.getvalue())
        self.assertEqual(400, event["http_status"])
        self.assertEqual("validation", event["error_phase"])
        self.assertEqual("job-1", event["job_id"])
        self.assertEqual("validation_error", event["error"])

    @patch("meters_tool_cli._client_commands.request.urlopen")
    def test_soft_trigger_empty_success_response_returns_3(self, mock_urlopen):
        class FakeResponse:
            status = 202

            def read(self):
                return b""

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        mock_urlopen.return_value = FakeResponse()
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = cmd_send_command(8765, "{}", output_format="json")

        self.assertEqual(3, rc)
        event = json.loads(stdout.getvalue())
        self.assertEqual(202, event["http_status"])
        self.assertIn("empty response", event["message"])

    @patch("meters_tool_cli._client_commands.request.urlopen")
    def test_soft_trigger_mismatched_success_identity_returns_3(self, mock_urlopen):
        class FakeResponse:
            status = 202

            def read(self):
                return b'{"status":"accepted","command":"software_trigger","job_id":"other"}'

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        mock_urlopen.return_value = FakeResponse()
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = cmd_send_command(8765, "{}", output_format="json", job_id="job-1")

        self.assertEqual(3, rc)
        event = json.loads(stdout.getvalue())
        self.assertIn("mismatched command identity", event["message"])

    @patch("meters_tool_cli._client_commands.request.urlopen", side_effect=URLError("offline"))
    def test_soft_command_url_error_json_returns_error_event(self, _mock_urlopen):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = cmd_send_command(8765, "{}", output_format="json")
        self.assertEqual(3, rc)
        events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(1, len(events))
        self.assertEqual("error", events[0]["event"])
        self.assertEqual(3, events[0]["exit_code"])
        self._assert_error_contract(
            events[0],
            client_command="send-command",
            error_phase="request",
            exit_code=3,
        )

    @patch("meters_tool_cli._client_commands.request.urlopen")
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
            rc = cmd_stop(8765, output_format="json")
        self.assertEqual(0, rc)
        events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(1, len(events))
        self.assertEqual("stop", events[0]["event"])
        self.assertEqual("accepted", events[0]["status"])
        self.assertEqual(204, events[0]["http_status"])
        self._assert_client_contract(
            events[0],
            event="stop",
            client_command="stop",
            ok=True,
            request_sent=True,
        )
        self.assertTrue(events[0]["reachable"])

    @patch("meters_tool_cli._client_commands.request.urlopen", side_effect=URLError("offline"))
    def test_soft_stop_url_error_json_returns_error_event(self, _mock_urlopen):
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_stop(8765, output_format="json")

        self.assertEqual(3, rc)
        events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(1, len(events))
        self.assertEqual("error", events[0]["event"])
        self.assertEqual(3, events[0]["exit_code"])
        self.assertIn("stop request failed", events[0]["message"])
        self._assert_error_contract(
            events[0],
            client_command="stop",
            error_phase="request",
            exit_code=3,
        )

    @patch(
        "meters_tool_cli._client_commands.request.urlopen",
        side_effect=URLError(ConnectionRefusedError(10061, "refused")),
    )
    def test_soft_stop_already_stopped_json_contract(self, _mock_urlopen):
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_stop(8765, output_format="json")

        self.assertEqual(0, rc)
        event = json.loads(stdout.getvalue())
        self._assert_client_contract(
            event,
            event="stop",
            client_command="stop",
            ok=True,
            request_sent=True,
        )
        self.assertEqual("already_stopped", event["status"])
        self.assertFalse(event["reachable"])

    def test_soft_trigger_dry_run_json_contract(self):
        stdout = io.StringIO()

        with redirect_stdout(stdout), patch("meters_tool_cli._client_commands.request.urlopen") as mock_urlopen:
            rc = cmd_send_command(
                8765,
                '{"metadata":{"source":"contract"}}',
                output_format="json",
                dry_run=True,
            )

        self.assertEqual(0, rc)
        event = json.loads(stdout.getvalue())
        self._assert_client_contract(
            event,
            event="dry_run",
            client_command="send-command",
            ok=True,
            request_sent=False,
        )
        self.assertEqual("dry_run", event["status"])
        self.assertFalse(event["send_request"])
        mock_urlopen.assert_not_called()

    def test_soft_stop_dry_run_json_contract(self):
        stdout = io.StringIO()

        with redirect_stdout(stdout), patch("meters_tool_cli._client_commands.request.urlopen") as mock_urlopen:
            rc = cmd_stop(8765, output_format="json", dry_run=True)

        self.assertEqual(0, rc)
        event = json.loads(stdout.getvalue())
        self._assert_client_contract(
            event,
            event="dry_run",
            client_command="stop",
            ok=True,
            request_sent=False,
        )
        self.assertEqual("dry_run", event["status"])
        self.assertFalse(event["send_request"])
        mock_urlopen.assert_not_called()

    @patch("meters_tool_cli._client_commands.request.urlopen")
    def test_soft_status_success_json_contract(self, mock_urlopen):
        mock_urlopen.return_value = self._fake_json_response(self._worker_status())
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_status(8765, output_format="json")

        self.assertEqual(0, rc)
        event = json.loads(stdout.getvalue())
        self._assert_client_contract(
            event,
            event="status",
            client_command="status",
            ok=True,
            request_sent=True,
        )
        self.assertEqual("run-123", event["run_id"])
        self.assertTrue(event["reachable"])
        self.assertEqual(200, event["http_status"])

    @patch("meters_tool_cli._client_commands.request.urlopen")
    def test_soft_status_fatal_json_contract(self, mock_urlopen):
        mock_urlopen.return_value = self._fake_json_response(self._worker_status(fatal_error="boom"))
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_status(8765, output_format="json")

        self.assertEqual(0, rc)
        event = json.loads(stdout.getvalue())
        self._assert_client_contract(
            event,
            event="status",
            client_command="status",
            ok=False,
            request_sent=True,
        )
        self.assertTrue(event["reachable"])
        self.assertEqual("boom", event["fatal_error"])

    @patch("meters_tool_cli._client_commands.request.urlopen", side_effect=URLError("offline"))
    def test_soft_status_unreachable_json_contract(self, _mock_urlopen):
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_status(8765, output_format="json")

        self.assertEqual(3, rc)
        event = json.loads(stdout.getvalue())
        self._assert_client_contract(
            event,
            event="status",
            client_command="status",
            ok=False,
            request_sent=True,
        )
        self.assertEqual("request", event["error_phase"])
        self.assertEqual(3, event["exit_code"])
        self.assertFalse(event["reachable"])

    @patch("meters_tool_cli._client_commands.request.urlopen")
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
            rc = cmd_status(8765, output_format="json")

        self.assertEqual(3, rc)
        event = json.loads(stdout.getvalue())
        self._assert_client_contract(
            event,
            event="status",
            client_command="status",
            ok=False,
            request_sent=True,
        )
        self.assertTrue(event["reachable"])
        self.assertEqual(200, event["http_status"])

    def test_soft_status_dry_run_json_contract(self):
        stdout = io.StringIO()

        with redirect_stdout(stdout), patch("meters_tool_cli._client_commands.request.urlopen") as mock_urlopen:
            rc = cmd_status(8765, output_format="json", dry_run=True)

        self.assertEqual(0, rc)
        event = json.loads(stdout.getvalue())
        self._assert_client_contract(
            event,
            event="dry_run",
            client_command="status",
            ok=True,
            request_sent=False,
        )
        self.assertEqual("GET", event["method"])
        self.assertFalse(event["send_request"])
        mock_urlopen.assert_not_called()

    @patch("meters_tool_cli._client_commands.request.urlopen")
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

    @patch("meters_tool_cli._client_commands.time.sleep")
    @patch("meters_tool_cli._client_commands.request.urlopen")
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

    @patch("meters_tool_cli._client_commands.time.sleep")
    @patch("meters_tool_cli._client_commands.request.urlopen", side_effect=URLError("offline"))
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
            rc = main(["status", "--port", "0", "--json"])

        self.assertEqual(2, rc)
        event = json.loads(stdout.getvalue())
        self._assert_error_contract(
            event,
            client_command="status",
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
