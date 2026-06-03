from __future__ import annotations

import unittest

from keysight_logger.cli import build_parser


class CliArgsTests(unittest.TestCase):
    def test_start_defaults(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
            ]
        )
        self.assertEqual(1.0, args.nplc)
        self.assertTrue(args.auto_zero)
        self.assertTrue(args.auto_range)
        self.assertEqual(0.0, args.hw_trigger_delay_s)
        self.assertEqual(0, args.sw_min_interval_ms)
        self.assertEqual(0, args.sw_queue_max)

    def test_start_with_manual_options(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--auto-range",
                "off",
                "--current-range",
                "0.1",
                "--auto-zero",
                "off",
                "--nplc",
                "0.2",
                "--hw-trigger-delay-s",
                "1.5",
                "--sw-min-interval-ms",
                "50",
                "--sw-queue-max",
                "5",
            ]
        )
        self.assertFalse(args.auto_range)
        self.assertEqual(0.1, args.current_range)
        self.assertFalse(args.auto_zero)
        self.assertEqual(0.2, args.nplc)
        self.assertEqual(1.5, args.hw_trigger_delay_s)
        self.assertEqual(50, args.sw_min_interval_ms)
        self.assertEqual(5, args.sw_queue_max)


if __name__ == "__main__":
    unittest.main()
