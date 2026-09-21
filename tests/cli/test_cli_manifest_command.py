from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from meters_tool_cli.cli import main


class CliManifestCommandTests(unittest.TestCase):
    def run_json(self) -> tuple[int, dict[str, object], str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            rc = main(["manifest", "--json"])
        lines = stdout.getvalue().splitlines()
        self.assertEqual(1, len(lines))
        return rc, json.loads(lines[0]), stderr.getvalue()

    @patch("meters_tool_cli.cli.run_start_session")
    @patch("meters_tool_cli.cli.VisaInstrument")
    def test_manifest_json_contract_without_runtime_io(
        self,
        mock_visa,
        mock_run_start_session,
    ):
        rc, payload, stderr = self.run_json()

        self.assertEqual(0, rc)
        self.assertEqual("", stderr)
        self.assertEqual("tool_manifest", payload["event"])
        self.assertEqual(2, payload["schema_version"])
        self.assertEqual("meters", payload["tool_id"])
        self.assertEqual("3.1.2", payload["tool_version"])
        self.assertEqual(
            {
                "compatibility_policy": "v2-only",
                "schema_versions": [2],
            },
            payload["worker_protocol"],
        )
        mock_visa.assert_not_called()
        mock_run_start_session.assert_not_called()

    @patch("meters_tool_cli.cli.run_start_session")
    @patch("meters_tool_cli.cli.VisaInstrument")
    def test_manifest_creates_no_files_or_directories(
        self,
        mock_visa,
        mock_run_start_session,
    ):
        previous_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tempdir:
            try:
                os.chdir(tempdir)
                rc, _payload, _stderr = self.run_json()

                self.assertEqual(0, rc)
                self.assertEqual([], os.listdir(tempdir))
            finally:
                os.chdir(previous_cwd)

        mock_visa.assert_not_called()
        mock_run_start_session.assert_not_called()

    def test_manifest_json_alias_conflicts_with_text_format(self):
        from meters_tool_cli.cli import build_parser

        parser = build_parser()

        with self.assertRaises(SystemExit) as exc:
            parser.parse_args(["manifest", "--json", "--format", "text"])

        self.assertEqual(2, exc.exception.code)


if __name__ == "__main__":
    unittest.main()
