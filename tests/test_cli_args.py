from __future__ import annotations

import unittest

from keysight_logger.cli import (
    StopController,
    WindowsConsoleStopHandler,
    WindowsKeyboardStopPoller,
    build_parser,
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


if __name__ == "__main__":
    unittest.main()
