from __future__ import annotations

import unittest
from unittest.mock import patch
from urllib.error import URLError

from keysight_logger.cli import (
    StopController,
    WindowsConsoleStopHandler,
    WindowsKeyboardStopPoller,
    build_parser,
    cmd_list_resources,
    cmd_soft_stop,
    print_buffer_overflow_warnings,
    resolve_trigger_mode,
    validate_start_args,
)


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
        self.assertIsNone(args.trigger_mode)
        self.assertIsNone(args.max_samples)
        self.assertIsNone(args.trigger_count)
        self.assertIsNone(args.sample_count)
        self.assertIsNone(args.timer_interval_s)
        self.assertIsNone(args.buffer_drain_size)
        self.assertFalse(args.allow_buffer_overflow_risk)
        self.assertIsNone(args.vm_comp_slope)

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
                "--trigger-mode",
                "immediate",
                "--max-samples",
                "10",
                "--vm-comp-slope",
                "pos",
            ]
        )
        self.assertFalse(args.auto_range)
        self.assertEqual(0.1, args.current_range)
        self.assertFalse(args.auto_zero)
        self.assertEqual(0.2, args.nplc)
        self.assertEqual(1.5, args.hw_trigger_delay_s)
        self.assertEqual(50, args.sw_min_interval_ms)
        self.assertEqual(5, args.sw_queue_max)
        self.assertEqual("immediate", args.trigger_mode)
        self.assertEqual(10, args.max_samples)
        self.assertEqual("pos", args.vm_comp_slope)

    def test_immediate_custom_requires_trigger_count(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate-custom",
                "--sample-count",
                "10",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--trigger-count is required with custom trigger modes",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_immediate_custom_requires_sample_count(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate-custom",
                "--trigger-count",
                "10",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--sample-count is required with custom trigger modes",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_immediate_custom_rejects_max_samples(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate-custom",
                "--trigger-count",
                "1",
                "--sample-count",
                "10",
                "--max-samples",
                "10",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--max-samples cannot be used with custom trigger modes",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_immediate_custom_rejects_more_than_34461a_memory_without_override(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate-custom",
                "--trigger-count",
                "101",
                "--sample-count",
                "100",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "custom mode expected readings exceed 10000",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_immediate_custom_accepts_overflow_override(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate-custom",
                "--trigger-count",
                "101",
                "--sample-count",
                "100",
                "--allow-buffer-overflow-risk",
            ]
        )

        trigger_mode = resolve_trigger_mode(args)
        validate_start_args(args, trigger_mode)

        self.assertEqual("immediate-custom", trigger_mode)
        self.assertTrue(args.allow_buffer_overflow_risk)

    def test_immediate_custom_accepts_instrument_counts(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate-custom",
                "--trigger-count",
                "2",
                "--sample-count",
                "100",
                "--buffer-drain-size",
                "4",
            ]
        )

        trigger_mode = resolve_trigger_mode(args)
        validate_start_args(args, trigger_mode)

        self.assertEqual("immediate-custom", trigger_mode)
        self.assertEqual(2, args.trigger_count)
        self.assertEqual(100, args.sample_count)
        self.assertEqual(4, args.buffer_drain_size)

    def test_software_custom_accepts_instrument_counts(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "software-custom",
                "--trigger-count",
                "2",
                "--sample-count",
                "100",
            ]
        )

        trigger_mode = resolve_trigger_mode(args)
        validate_start_args(args, trigger_mode)

        self.assertEqual("software-custom", trigger_mode)
        self.assertEqual(2, args.trigger_count)
        self.assertEqual(100, args.sample_count)

    def test_software_custom_rejects_timer_interval(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "software-custom",
                "--trigger-count",
                "1",
                "--sample-count",
                "10",
                "--timer-interval-s",
                "1.0",
            ]
        )

        with self.assertRaisesRegex(ValueError, "--timer-interval-s requires --trigger-mode software"):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_external_custom_accepts_instrument_counts(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "external-custom",
                "--trigger-count",
                "2",
                "--sample-count",
                "100",
            ]
        )

        trigger_mode = resolve_trigger_mode(args)
        validate_start_args(args, trigger_mode)

        self.assertEqual("external-custom", trigger_mode)
        self.assertEqual(2, args.trigger_count)
        self.assertEqual(100, args.sample_count)

    def test_external_custom_rejects_timer_interval(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "external-custom",
                "--trigger-count",
                "1",
                "--sample-count",
                "10",
                "--timer-interval-s",
                "1.0",
            ]
        )

        with self.assertRaisesRegex(ValueError, "--timer-interval-s requires --trigger-mode software"):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_buffer_drain_size_requires_custom_mode(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate",
                "--max-samples",
                "10",
                "--buffer-drain-size",
                "2",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--buffer-drain-size requires a custom trigger mode",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_buffer_drain_size_must_be_positive(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate-custom",
                "--trigger-count",
                "1",
                "--sample-count",
                "10",
                "--buffer-drain-size",
                "0",
            ]
        )

        with self.assertRaisesRegex(ValueError, "--buffer-drain-size must be > 0"):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_buffer_drain_size_rejects_more_than_34461a_memory(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate-custom",
                "--trigger-count",
                "1",
                "--sample-count",
                "10",
                "--buffer-drain-size",
                "10001",
            ]
        )

        with self.assertRaisesRegex(ValueError, "--buffer-drain-size must be <= 10000"):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_trigger_count_requires_custom_mode(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate",
                "--trigger-count",
                "1",
            ]
        )

        with self.assertRaisesRegex(ValueError, "--trigger-count requires a custom trigger mode"):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_sample_count_requires_custom_mode(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate",
                "--sample-count",
                "1",
            ]
        )

        with self.assertRaisesRegex(ValueError, "--sample-count requires a custom trigger mode"):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_allow_buffer_overflow_risk_requires_custom_mode(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate",
                "--allow-buffer-overflow-risk",
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "--allow-buffer-overflow-risk requires a custom trigger mode",
        ):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_allow_buffer_overflow_risk_prints_warnings(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "immediate-custom",
                "--trigger-count",
                "101",
                "--sample-count",
                "100",
                "--allow-buffer-overflow-risk",
            ]
        )

        with patch("builtins.print") as mock_print:
            print_buffer_overflow_warnings(args, "immediate-custom")

        self.assertEqual(5, mock_print.call_count)

    def test_timer_interval_is_valid_with_default_software_mode(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--timer-interval-s",
                "1.0",
            ]
        )

        trigger_mode = resolve_trigger_mode(args)
        validate_start_args(args, trigger_mode)

        self.assertEqual("software", trigger_mode)
        self.assertEqual(1.0, args.timer_interval_s)

    def test_timer_interval_must_be_positive(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--timer-interval-s",
                "0",
            ]
        )

        with self.assertRaisesRegex(ValueError, "--timer-interval-s must be > 0"):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_timer_interval_requires_software_mode(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "external",
                "--timer-interval-s",
                "1.0",
            ]
        )

        with self.assertRaisesRegex(ValueError, "--timer-interval-s requires --trigger-mode software"):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_enable_hw_trigger_conflicts_with_timer_interval(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--enable-hw-trigger",
                "--timer-interval-s",
                "1.0",
            ]
        )

        with self.assertRaisesRegex(ValueError, "--timer-interval-s requires --trigger-mode software"):
            validate_start_args(args, resolve_trigger_mode(args))

    def test_legacy_enable_hw_trigger_maps_to_external_mode(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--enable-hw-trigger",
            ]
        )

        self.assertEqual("external", resolve_trigger_mode(args))

    def test_enable_hw_trigger_conflicts_with_non_external_mode(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "start-trigger-record",
                "--resource",
                "USB::FAKE",
                "--csv",
                "out.csv",
                "--trigger-mode",
                "software",
                "--enable-hw-trigger",
            ]
        )

        with self.assertRaises(ValueError):
            resolve_trigger_mode(args)

    def test_list_resources_verify_flag(self):
        parser = build_parser()
        args = parser.parse_args(["list-resources", "--verify"])

        self.assertTrue(args.verify)


class StopControllerTests(unittest.TestCase):
    def test_signal_stop_first_interrupt_is_graceful(self):
        calls = []
        messages = []
        controller = StopController(lambda: calls.append("stop"), print_fn=messages.append)

        controller.request_signal_stop()

        self.assertTrue(controller.stop)
        self.assertFalse(controller.force)
        self.assertEqual(1, controller.interrupt_count)
        self.assertEqual(["stop"], calls)
        self.assertEqual(
            ["interrupt received, stopping gracefully (press Ctrl+C again to force)..."],
            messages,
        )

    def test_signal_stop_second_interrupt_forces_shutdown(self):
        calls = []
        messages = []
        controller = StopController(lambda: calls.append("stop"), print_fn=messages.append)

        controller.request_signal_stop()
        controller.request_signal_stop()

        self.assertTrue(controller.stop)
        self.assertTrue(controller.force)
        self.assertEqual(2, controller.interrupt_count)
        self.assertEqual(["stop", "stop"], calls)
        self.assertEqual(
            "second interrupt received, forcing shutdown...",
            messages[-1],
        )

    def test_http_stop_does_not_count_as_keyboard_interrupt(self):
        calls = []
        messages = []
        controller = StopController(lambda: calls.append("stop"), print_fn=messages.append)

        controller.request_http_stop()

        self.assertTrue(controller.stop)
        self.assertFalse(controller.force)
        self.assertEqual(0, controller.interrupt_count)
        self.assertEqual(["stop"], calls)
        self.assertEqual([], messages)


class WindowsConsoleStopHandlerTests(unittest.TestCase):
    def test_ctrl_c_event_requests_stop(self):
        calls = []
        controller = StopController(lambda: calls.append("stop"), print_fn=lambda message: None)
        handler = WindowsConsoleStopHandler(controller)

        handled = handler._handle(0)

        self.assertTrue(handled)
        self.assertTrue(controller.stop)
        self.assertEqual(1, controller.interrupt_count)
        self.assertEqual(["stop"], calls)

    def test_ctrl_break_event_requests_stop(self):
        calls = []
        controller = StopController(lambda: calls.append("stop"), print_fn=lambda message: None)
        handler = WindowsConsoleStopHandler(controller)

        handled = handler._handle(1)

        self.assertTrue(handled)
        self.assertTrue(controller.stop)
        self.assertEqual(1, controller.interrupt_count)
        self.assertEqual(["stop"], calls)

    def test_non_interrupt_event_is_not_handled(self):
        calls = []
        controller = StopController(lambda: calls.append("stop"), print_fn=lambda message: None)
        handler = WindowsConsoleStopHandler(controller)

        handled = handler._handle(2)

        self.assertFalse(handled)
        self.assertFalse(controller.stop)
        self.assertEqual(0, controller.interrupt_count)
        self.assertEqual([], calls)


class FakeMsvcrt:
    def __init__(self, keys):
        self.keys = list(keys)

    def kbhit(self):
        return bool(self.keys)

    def getwch(self):
        return self.keys.pop(0)


class WindowsKeyboardStopPollerTests(unittest.TestCase):
    def test_ctrl_c_character_requests_stop(self):
        poller = WindowsKeyboardStopPoller()
        poller._msvcrt = FakeMsvcrt(["\x03"])

        self.assertTrue(poller.poll_stop_requested())

    def test_q_requests_stop(self):
        poller = WindowsKeyboardStopPoller()
        poller._msvcrt = FakeMsvcrt(["q"])

        self.assertTrue(poller.poll_stop_requested())

    def test_other_key_does_not_request_stop(self):
        poller = WindowsKeyboardStopPoller()
        poller._msvcrt = FakeMsvcrt(["x"])

        self.assertFalse(poller.poll_stop_requested())


class CliCommandTests(unittest.TestCase):
    @patch("keysight_logger.cli.VisaInstrument")
    def test_list_resources_without_verify_prints_resources(self, mock_visa):
        mock_visa.list_resources.return_value = ["USB::LIVE"]
        lines = []

        rc = cmd_list_resources(verify=False, print_fn=lines.append)

        self.assertEqual(0, rc)
        self.assertEqual(["USB::LIVE"], lines)
        mock_visa.verify_resource.assert_not_called()

    @patch("keysight_logger.cli.VisaInstrument")
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

    @patch(
        "keysight_logger.cli.request.urlopen",
        side_effect=URLError(ConnectionRefusedError(10061, "refused")),
    )
    def test_soft_stop_connection_refused_returns_0(self, _mock_urlopen):
        rc = cmd_soft_stop(8765)
        self.assertEqual(0, rc)


if __name__ == "__main__":
    unittest.main()
