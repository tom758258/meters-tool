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

class CliListResourcesCommandTests(CliCommandHarnessMixin, unittest.TestCase):
    @patch("meters_tool_cli.cli.VisaInstrument")
    def test_list_resources_without_verify_prints_resources(self, mock_visa):
        mock_visa.list_resources.return_value = ["USB::LIVE"]
        lines = []

        rc = cmd_list_resources(verify=False, print_fn=lines.append)

        self.assertEqual(0, rc)
        self.assertEqual(["USB::LIVE"], lines)
        mock_visa.list_resources.assert_called_once_with(
            resource_manager_factory=None,
            visa_library=None,
        )
        mock_visa.verify_resource.assert_not_called()

    @patch("meters_tool_cli.cli.VisaInstrument")
    def test_list_resources_dry_run_text_outputs_contract_without_discovery(self, mock_visa):
        lines = []

        rc = cmd_list_resources(dry_run=True, print_fn=lines.append)

        self.assertEqual(0, rc)
        self.assertIn("dry-run list-resources:", lines)
        self.assertIn("  output_format: text", lines)
        self.assertIn("  verify: false", lines)
        self.assertIn("  live_only: false", lines)
        self.assertIn("  visa_library: default", lines)
        self.assertIn("  effective_verify: false", lines)
        self.assertIn("  dry_run_performs_visa_io: false", lines)
        self.assertIn("  VISA I/O: no", lines)
        self.assertIn("    list VISA resources: yes", lines)
        mock_visa.list_resources.assert_not_called()
        mock_visa.verify_resource.assert_not_called()

    @patch("meters_tool_cli.cli.VisaInstrument")
    def test_list_resources_dry_run_json_outputs_one_contract_without_discovery(self, mock_visa):
        lines = []

        rc = cmd_list_resources(dry_run=True, output_format="json", print_fn=lines.append)

        self.assertEqual(0, rc)
        self.assertEqual(1, len(lines))
        payload = json.loads(lines[0])
        self.assertEqual("dry_run", payload["event"])
        self.assertEqual("list-resources", payload["command"])
        self.assertEqual("json", payload["output_format"])
        self.assertIsNone(payload["visa_library"])
        self.assertFalse(payload["dry_run_performs_visa_io"])
        self.assertFalse(payload["effective_verify"])
        for key in [
            "close_each_resource",
            "filter_live_only",
            "list_visa_resources",
            "open_each_resource",
            "query_idn",
            "release_to_local_after_successful_non_asrl_verify",
            "release_to_local_after_successful_verify",
            "serial_termination_applies_to_asrl_only",
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

    @patch("meters_tool_cli.cli.VisaInstrument")
    def test_list_resources_passes_visa_library_to_list(self, mock_visa):
        mock_visa.list_resources.return_value = ["TCPIP::LIVE"]
        lines = []

        rc = cmd_list_resources(visa_library="@py", print_fn=lines.append)

        self.assertEqual(0, rc)
        self.assertEqual(["TCPIP::LIVE"], lines)
        mock_visa.list_resources.assert_called_once_with(
            resource_manager_factory=None,
            visa_library="@py",
        )
        mock_visa.verify_resource.assert_not_called()

    @patch("meters_tool_cli.cli.VisaInstrument")
    def test_list_resources_normalizes_blank_visa_library(self, mock_visa):
        mock_visa.list_resources.return_value = ["USB::LIVE"]
        lines = []

        rc = cmd_list_resources(visa_library="   ", print_fn=lines.append)

        self.assertEqual(0, rc)
        mock_visa.list_resources.assert_called_once_with(
            resource_manager_factory=None,
            visa_library=None,
        )

    @patch("meters_tool_cli.cli.VisaInstrument")
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
        mock_visa.list_resources.assert_called_once_with(
            resource_manager_factory=None,
            visa_library=None,
        )
        self.assertEqual(2, mock_visa.verify_resource.call_count)

    @patch("meters_tool_cli.cli.VisaInstrument")
    def test_list_resources_verify_passes_visa_library_to_list_and_verify(self, mock_visa):
        mock_visa.list_resources.return_value = ["USB::LIVE", "USB::STALE"]
        mock_visa.verify_resource.side_effect = [
            (True, "Keysight Technologies,34461A,MY123,1.0"),
            (False, "VisaIOError: timeout"),
        ]
        lines = []

        rc = cmd_list_resources(verify=True, visa_library="@py", print_fn=lines.append)

        self.assertEqual(0, rc)
        mock_visa.list_resources.assert_called_once_with(
            resource_manager_factory=None,
            visa_library="@py",
        )
        self.assertEqual(
            [call.kwargs["visa_library"] for call in mock_visa.verify_resource.call_args_list],
            ["@py", "@py"],
        )

    @patch("meters_tool_cli.cli.VisaInstrument")
    def test_list_resources_verify_passes_serial_terminations_to_verify(self, mock_visa):
        mock_visa.list_resources.return_value = ["ASRL6::INSTR"]
        mock_visa.verify_resource.return_value = (True, "Keysight Technologies,34461A,MY123,1.0")
        lines = []

        rc = cmd_list_resources(
            verify=True,
            serial_read_termination="CRLF",
            serial_write_termination="LF",
            print_fn=lines.append,
        )

        self.assertEqual(0, rc)
        mock_visa.verify_resource.assert_called_once_with(
            "ASRL6::INSTR",
            resource_manager_factory=None,
            visa_library=None,
            serial_read_termination="\r\n",
            serial_write_termination="\n",
        )

    @patch("meters_tool_cli.cli.VisaInstrument")
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
        payload = json.loads(lines[0])
        self.assertEqual("list-resources", payload["event"])
        self.assertEqual(1, payload["schema_version"])
        self.assertEqual(2, payload["count"])
        self.assertEqual(1, payload["live_count"])
        self.assertEqual(1, payload["stale_count"])
        self.assertIsNone(payload["visa_library"])
        self.assertNotIn("live_only", payload)
        self.assertEqual([], payload["diagnostic_hints"])
        self.assertEqual(
            [
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
            payload["resources"],
        )
        self.assertTrue(payload["verify"])

    @patch("meters_tool_cli.cli.VisaInstrument")
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

    @patch("meters_tool_cli.cli.VisaInstrument")
    def test_list_resources_live_only_prints_message_when_none_live(self, mock_visa):
        mock_visa.list_resources.return_value = ["USB::STALE"]
        mock_visa.verify_resource.return_value = (False, "VisaIOError: timeout")
        lines = []

        rc = cmd_list_resources(live_only=True, print_fn=lines.append)

        self.assertEqual(0, rc)
        self.assertEqual(["no live VISA resources found"], lines)

    @patch("meters_tool_cli.cli.VisaInstrument")
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
        payload = json.loads(lines[0])
        self.assertEqual("list-resources", payload["event"])
        self.assertEqual(1, payload["count"])
        self.assertEqual(1, payload["live_count"])
        self.assertEqual(0, payload["stale_count"])
        self.assertTrue(payload["live_only"])
        self.assertEqual(
            [
                {
                    "detail": "Keysight Technologies,34461A,MY123,1.0",
                    "live": True,
                    "resource": "USB::LIVE",
                    "status": "live",
                },
            ],
            payload["resources"],
        )
        self.assertTrue(payload["verify"])

    @patch("meters_tool_cli.cli.VisaInstrument")
    def test_list_resources_live_only_continues_after_first_asrl_stale(self, mock_visa):
        mock_visa.list_resources.return_value = ["ASRL6::INSTR", "USB::LIVE"]
        mock_visa.verify_resource.side_effect = [
            (False, "ASRL verification timed out after 1000 ms"),
            (True, "Keysight Technologies,34461A,MY123,1.0"),
        ]
        lines = []

        rc = cmd_list_resources(live_only=True, print_fn=lines.append)

        self.assertEqual(0, rc)
        self.assertEqual(["live\tUSB::LIVE\tKeysight Technologies,34461A,MY123,1.0"], lines)
        self.assertEqual(2, mock_visa.verify_resource.call_count)

    @patch("meters_tool_cli.cli.VisaInstrument")
    def test_list_resources_verify_records_helper_failure_and_continues(self, mock_visa):
        mock_visa.list_resources.return_value = ["ASRL6::INSTR", "USB::LIVE"]
        mock_visa.verify_resource.side_effect = [
            RuntimeError("helper failed"),
            (True, "Keysight Technologies,34461A,MY123,1.0"),
        ]
        lines = []

        rc = cmd_list_resources(verify=True, print_fn=lines.append)

        self.assertEqual(0, rc)
        self.assertEqual(
            [
                "stale\tASRL6::INSTR\tRuntimeError: helper failed",
                "live\tUSB::LIVE\tKeysight Technologies,34461A,MY123,1.0",
            ],
            lines,
        )

    @patch("meters_tool_cli.cli.VisaInstrument")
    def test_list_resources_verify_json_includes_stale_asrl_detail(self, mock_visa):
        mock_visa.list_resources.return_value = ["ASRL6::INSTR", "USB::LIVE"]
        mock_visa.verify_resource.side_effect = [
            (False, "ASRL verification timed out after 1000 ms"),
            (True, "Keysight Technologies,34461A,MY123,1.0"),
        ]
        lines = []

        rc = cmd_list_resources(verify=True, output_format="json", print_fn=lines.append)

        self.assertEqual(0, rc)
        payload = json.loads(lines[0])
        self.assertEqual(2, payload["count"])
        self.assertEqual(1, payload["live_count"])
        self.assertEqual(1, payload["stale_count"])
        self.assertEqual(
            {
                "detail": "ASRL verification timed out after 1000 ms",
                "live": False,
                "resource": "ASRL6::INSTR",
                "status": "stale",
            },
            payload["resources"][0],
        )

    @patch("meters_tool_cli.cli.VisaInstrument")
    def test_list_resources_live_only_json_filters_stale_asrl(self, mock_visa):
        mock_visa.list_resources.return_value = ["ASRL6::INSTR", "USB::LIVE"]
        mock_visa.verify_resource.side_effect = [
            (False, "ASRL verification timed out after 1000 ms"),
            (True, "Keysight Technologies,34461A,MY123,1.0"),
        ]
        lines = []

        rc = cmd_list_resources(live_only=True, output_format="json", print_fn=lines.append)

        self.assertEqual(0, rc)
        payload = json.loads(lines[0])
        self.assertEqual(1, payload["count"])
        self.assertEqual(
            [
                {
                    "detail": "Keysight Technologies,34461A,MY123,1.0",
                    "live": True,
                    "resource": "USB::LIVE",
                    "status": "live",
                },
            ],
            payload["resources"],
        )

    def test_main_dispatches_list_resources(self):
        with patch("meters_tool_cli.cli.cmd_list_resources", return_value=17) as mock_cmd:
            rc = main(["list-resources", "--live-only", "--format", "json"])

        self.assertEqual(17, rc)
        mock_cmd.assert_called_once_with(
            verify=False,
            live_only=True,
            output_format="json",
            dry_run=False,
            visa_library=None,
            serial_read_termination=None,
            serial_write_termination=None,
        )

    def test_main_dispatches_list_resources_dry_run_json(self):
        with patch("meters_tool_cli.cli.cmd_list_resources", return_value=17) as mock_cmd:
            rc = main(["list-resources", "--dry-run", "--json"])

        self.assertEqual(17, rc)
        mock_cmd.assert_called_once_with(
            verify=False,
            live_only=False,
            output_format="json",
            dry_run=True,
            visa_library=None,
            serial_read_termination=None,
            serial_write_termination=None,
        )

    def test_main_dispatches_list_resources_with_visa_library_aliases(self):
        with patch("meters_tool_cli.cli.cmd_list_resources", return_value=17) as mock_cmd:
            rc = main(["list-resources", "--visa-library", "@py"])

        self.assertEqual(17, rc)
        self.assertEqual("@py", mock_cmd.call_args.kwargs["visa_library"])

        with patch("meters_tool_cli.cli.cmd_list_resources", return_value=18) as mock_cmd:
            rc = main(["list-resources", "--backend", "@py"])

        self.assertEqual(18, rc)
        self.assertEqual("@py", mock_cmd.call_args.kwargs["visa_library"])

    def test_main_dispatches_list_resources_with_serial_terminations(self):
        with patch("meters_tool_cli.cli.cmd_list_resources", return_value=17) as mock_cmd:
            rc = main(
                [
                    "list-resources",
                    "--verify",
                    "--serial-read-termination",
                    "CRLF",
                    "--serial-write-termination",
                    "LF",
                ]
            )

        self.assertEqual(17, rc)
        self.assertEqual("CRLF", mock_cmd.call_args.kwargs["serial_read_termination"])
        self.assertEqual("LF", mock_cmd.call_args.kwargs["serial_write_termination"])



if __name__ == "__main__":
    unittest.main()
