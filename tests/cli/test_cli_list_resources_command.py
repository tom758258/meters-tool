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

from keysight_logger_cli.cli import (
    build_parser,
    cmd_list_resources,
    cmd_send_command,
    cmd_start,
    cmd_status,
    cmd_stop,
    cmd_wait_ready,
    main,
)
from keysight_logger_core.models import StartRequest
from keysight_logger_core.session import StartRunResult

from cli_command_helpers import CliCommandHarnessMixin
from cli_command_helpers import *  # noqa: F403

class CliListResourcesCommandTests(CliCommandHarnessMixin, unittest.TestCase):
    @patch("keysight_logger_cli.cli.VisaInstrument")
    def test_list_resources_without_verify_prints_resources(self, mock_visa):
        mock_visa.list_resources.return_value = ["USB::LIVE"]
        lines = []

        rc = cmd_list_resources(verify=False, print_fn=lines.append)

        self.assertEqual(0, rc)
        self.assertEqual(["USB::LIVE"], lines)
        mock_visa.verify_resource.assert_not_called()

    @patch("keysight_logger_cli.cli.VisaInstrument")
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

    @patch("keysight_logger_cli.cli.VisaInstrument")
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

    @patch("keysight_logger_cli.cli.VisaInstrument")
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

    @patch("keysight_logger_cli.cli.VisaInstrument")
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

    @patch("keysight_logger_cli.cli.VisaInstrument")
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

    @patch("keysight_logger_cli.cli.VisaInstrument")
    def test_list_resources_live_only_prints_message_when_none_live(self, mock_visa):
        mock_visa.list_resources.return_value = ["USB::STALE"]
        mock_visa.verify_resource.return_value = (False, "VisaIOError: timeout")
        lines = []

        rc = cmd_list_resources(live_only=True, print_fn=lines.append)

        self.assertEqual(0, rc)
        self.assertEqual(["no live VISA resources found"], lines)

    @patch("keysight_logger_cli.cli.VisaInstrument")
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

    def test_main_dispatches_list_resources(self):
        with patch("keysight_logger_cli.cli.cmd_list_resources", return_value=17) as mock_cmd:
            rc = main(["list-resources", "--live-only", "--format", "json"])

        self.assertEqual(17, rc)
        mock_cmd.assert_called_once_with(
            verify=False,
            live_only=True,
            output_format="json",
            dry_run=False,
        )

    def test_main_dispatches_list_resources_dry_run_json(self):
        with patch("keysight_logger_cli.cli.cmd_list_resources", return_value=17) as mock_cmd:
            rc = main(["list-resources", "--dry-run", "--json"])

        self.assertEqual(17, rc)
        mock_cmd.assert_called_once_with(
            verify=False,
            live_only=False,
            output_format="json",
            dry_run=True,
        )



if __name__ == "__main__":
    unittest.main()
