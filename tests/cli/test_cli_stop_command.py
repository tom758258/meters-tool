from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch
from urllib.error import URLError

from meters_tool_cli.cli import (
    build_parser,
    cmd_stop,
    main,
)

from cli_command_helpers import CliCommandHarnessMixin


class CliStopCommandTests(CliCommandHarnessMixin, unittest.TestCase):
    def test_soft_stop_port_is_validated_before_request(self):
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            rc = main(["stop", "--port", "65536"])

        self.assertEqual(2, rc)
        self.assertIn("--port 65536 is outside the supported range 1-65535", stderr.getvalue())

    @patch("meters_tool_cli._client_commands.request.urlopen")
    def test_soft_stop_posts_stop_request(self, mock_urlopen):
        class FakeResponse:
            status = 202

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"schema_version":3,"run_id":"run-123","status":"accepted","error":null}'

        mock_urlopen.return_value = FakeResponse()
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = cmd_stop(8765)

        self.assertEqual(0, rc)
        self.assertIn("stop accepted: 202", stdout.getvalue())
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
            status = 202

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"schema_version":3,"run_id":"run-123","status":"accepted","error":null}'

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

    @patch("meters_tool_cli._client_commands.request.urlopen")
    def test_soft_stop_success_json_returns_accepted_event(self, mock_urlopen):
        class FakeResponse:
            status = 202

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"schema_version":3,"run_id":"run-123","status":"accepted","error":null}'

        mock_urlopen.return_value = FakeResponse()
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = cmd_stop(8765, output_format="json")
        self.assertEqual(0, rc)
        events = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(1, len(events))
        self.assertEqual("stop", events[0]["event"])
        self.assertEqual("accepted", events[0]["status"])
        self.assertEqual(202, events[0]["http_status"])
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


if __name__ == "__main__":
    unittest.main()
