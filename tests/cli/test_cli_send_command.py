from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from meters_tool_cli.cli import (
    build_parser,
    cmd_send_command,
    main,
)

from cli_command_helpers import CliCommandHarnessMixin


class CliSendCommandTests(CliCommandHarnessMixin, unittest.TestCase):
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
                return b'{"schema_version":3,"run_id":"run-123","status":"accepted","command":"software_trigger","job_id":null,"kind":"control","worker_job_id":null,"error":null}'

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
            b'{"schema_version":3,"command":"software_trigger","arguments":{"metadata":{"operator":"tom"}}}',
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
                "schema_version": 3,
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
                return b'{"schema_version":3,"run_id":"run-123","status":"accepted","command":"software_trigger","job_id":null,"kind":"control","worker_job_id":null,"error":null}'

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
                return b'{"schema_version":3,"run_id":"run-123","status":"accepted","command":"software_trigger","job_id":"job-1","kind":"control","worker_job_id":null,"error":null}'

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
    def test_soft_trigger_rejects_non_v3_worker_response(self, mock_urlopen):
        class FakeResponse:
            status = 202

            def read(self):
                return b'{"schema_version":1,"status":"accepted","command":"software_trigger","job_id":null}'

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
        self.assertIn("requires schema_version 3", event["message"])

    @patch("meters_tool_cli._client_commands.request.urlopen")
    def test_soft_trigger_http_400_merges_worker_response_and_returns_2(self, mock_urlopen):
        body = io.BytesIO(
            b'{"schema_version":3,"run_id":"run-123","status":"error","command":"software_trigger","job_id":"job-1",'
            b'"kind":"control","worker_job_id":null,"error":{"category":"validation","code":"validation_error",'
            b'"message":"metadata must be a JSON object","details":{}}}'
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
                return b'{"schema_version":3,"run_id":"run-123","status":"accepted","command":"software_trigger","job_id":"other","kind":"control","worker_job_id":null,"error":null}'

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


if __name__ == "__main__":
    unittest.main()
