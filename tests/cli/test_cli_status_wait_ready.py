from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch
from urllib.error import URLError

from meters_tool_cli.cli import (
    build_parser,
    cmd_status,
    cmd_wait_ready,
    main,
)

from cli_command_helpers import CliCommandHarnessMixin


class CliStatusWaitReadyTests(CliCommandHarnessMixin, unittest.TestCase):
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
        self.assertEqual(3, event["worker_schema_version"])
        self.assertEqual("2026-05-31T00:00:00+00:00", event["worker_timestamp_utc"])

    @patch("meters_tool_cli._client_commands.request.urlopen")
    def test_soft_status_preserves_structured_acquisition_fields(self, mock_urlopen):
        fields = {
            "trigger_count_infinite": True,
            "expected_readings": None,
            "overflow_monitoring": "active",
            "overflow_detected": True,
            "stop_reason": "overflow_detected",
            "final_drain_complete": False,
            "data_integrity": "incomplete",
        }
        mock_urlopen.return_value = self._fake_json_response({**self._worker_status(), **fields})
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_status(8765, output_format="json")

        self.assertEqual(0, rc)
        event = json.loads(stdout.getvalue())
        for name, value in fields.items():
            self.assertEqual(value, event[name])

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


if __name__ == "__main__":
    unittest.main()
