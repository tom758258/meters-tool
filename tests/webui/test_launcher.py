from __future__ import annotations

import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from keysight_logger_webui.launcher import (
    DEFAULT_PORT,
    LauncherApp,
    build_local_url,
    parse_port,
)


class LauncherHelperTests(unittest.TestCase):
    def test_default_url_uses_loopback_and_default_port(self):
        self.assertEqual("http://127.0.0.1:8767", build_local_url(DEFAULT_PORT))

    def test_parse_port_rejects_invalid_values(self):
        for value in ("", "abc", "0", "65536"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_port(value)

    def test_parse_port_accepts_valid_values(self):
        self.assertEqual(8767, parse_port("8767"))
        self.assertEqual(8080, parse_port(" 8080 "))

    def test_script_entry_point_is_after_readiness_helper(self):
        source = (
            Path(__file__).parents[2]
            / "src"
            / "keysight_logger_webui"
            / "launcher.py"
        ).read_text(encoding="utf-8")

        self.assertLess(
            source.index("def _server_is_ready"),
            source.index('if __name__ == "__main__"'),
        )


class LauncherLifecycleTests(unittest.TestCase):
    def test_start_locks_controls_opens_browser_and_quit_stops_server(self):
        tk, root = _make_tk_root()
        root.withdraw()
        opened_urls = []
        servers = []

        class FakeServer:
            def __init__(self):
                self.should_exit = False
                self.run_called = False

            def run(self):
                self.run_called = True
                while not self.should_exit:
                    time.sleep(0.01)

        def server_factory(_manager, port):
            self.assertEqual(DEFAULT_PORT, port)
            server = FakeServer()
            servers.append(server)
            return server

        try:
            readiness_calls = []

            def readiness(_url):
                readiness_calls.append(_url)
                return len(readiness_calls) > 1

            launcher = LauncherApp(
                root,
                server_factory=server_factory,
                browser_open=opened_urls.append,
                readiness_checker=readiness,
                http_checker=lambda _url: False,
            )

            with patch("keysight_logger_webui.launcher.messagebox.showerror") as showerror:
                launcher.start()
                _drain_tk_events(root, condition=lambda: bool(opened_urls))

            self.assertEqual(["http://127.0.0.1:8767"], opened_urls)
            showerror.assert_not_called()
            self.assertEqual("disabled", launcher._start_button.cget("state"))
            self.assertEqual("disabled", launcher._port_entry.cget("state"))
            self.assertIs(servers[0], launcher.server)
            self.assertIsNotNone(launcher.server_thread)
            launcher.server_thread.join(timeout=1.0)
            self.assertTrue(servers[0].run_called)

            launcher.quit()

            self.assertTrue(servers[0].should_exit)
        finally:
            try:
                root.destroy()
            except tk.TclError:
                pass

    def test_existing_webui_readiness_opens_browser_without_starting_server(self):
        tk, root = _make_tk_root()
        root.withdraw()
        opened_urls = []
        server_factory_called = False

        def server_factory(_manager, _port):
            nonlocal server_factory_called
            server_factory_called = True
            raise AssertionError("already-running WebUI should not start a second server")

        try:
            launcher = LauncherApp(
                root,
                server_factory=server_factory,
                browser_open=opened_urls.append,
                readiness_checker=lambda _url: True,
                http_checker=lambda _url: False,
            )

            with patch("keysight_logger_webui.launcher.messagebox.showerror") as showerror:
                launcher.start()
                _drain_tk_events(root)

            self.assertFalse(server_factory_called)
            self.assertEqual(["http://127.0.0.1:8767"], opened_urls)
            self.assertIsNone(launcher.server_thread)
            self.assertIn("Server already running", launcher._status_value.get())
            showerror.assert_not_called()
        finally:
            try:
                root.destroy()
            except tk.TclError:
                pass

    def test_server_exits_before_readiness_reports_start_failed(self):
        tk, root = _make_tk_root()
        root.withdraw()

        class FailingServer:
            should_exit = False

            def run(self):
                raise SystemExit(1)

        try:
            launcher = LauncherApp(
                root,
                server_factory=lambda _manager, _port: FailingServer(),
                browser_open=lambda _url: None,
                readiness_checker=lambda _url: False,
                http_checker=lambda _url: False,
            )

            with patch("keysight_logger_webui.launcher.messagebox.showerror") as showerror:
                launcher.start()
                _drain_tk_events(root, condition=lambda: showerror.called)

            showerror.assert_called_once()
            title, message = showerror.call_args.args
            self.assertEqual("Start failed", title)
            self.assertIn("SystemExit: 1", message)
        finally:
            try:
                root.destroy()
            except tk.TclError:
                pass

    def test_system_exit_after_readiness_success_does_not_show_start_failed(self):
        tk, root = _make_tk_root()
        root.withdraw()
        opened_urls = []
        ready_seen = threading.Event()

        class ExitingAfterReadyServer:
            should_exit = False

            def run(self):
                while not ready_seen.is_set():
                    time.sleep(0.01)
                raise SystemExit(1)

        readiness_calls = []

        def readiness(_url):
            readiness_calls.append(_url)
            if len(readiness_calls) == 1:
                return False
            ready_seen.set()
            return True

        try:
            launcher = LauncherApp(
                root,
                server_factory=lambda _manager, _port: ExitingAfterReadyServer(),
                browser_open=opened_urls.append,
                readiness_checker=readiness,
                http_checker=lambda _url: False,
            )

            with patch("keysight_logger_webui.launcher.messagebox.showerror") as showerror:
                launcher.start()
                _drain_tk_events(root, condition=lambda: bool(opened_urls))
                if launcher.server_thread is not None:
                    launcher.server_thread.join(timeout=1.0)
                _drain_tk_events(root)

            self.assertEqual(["http://127.0.0.1:8767"], opened_urls)
            showerror.assert_not_called()
        finally:
            try:
                root.destroy()
            except tk.TclError:
                pass

    def test_new_server_root_ready_opens_browser_when_capabilities_not_ready(self):
        tk, root = _make_tk_root()
        root.withdraw()
        opened_urls = []
        server_started = threading.Event()
        servers = []

        class FakeServer:
            def __init__(self):
                self.should_exit = False

            def run(self):
                server_started.set()
                while not self.should_exit:
                    time.sleep(0.01)

        def server_factory(_manager, _port):
            server = FakeServer()
            servers.append(server)
            return server

        try:
            launcher = LauncherApp(
                root,
                server_factory=server_factory,
                browser_open=opened_urls.append,
                readiness_checker=lambda _url: False,
                http_checker=lambda _url: server_started.is_set(),
            )

            with patch("keysight_logger_webui.launcher.messagebox.showerror") as showerror:
                launcher.start()
                _drain_tk_events(root, condition=lambda: bool(opened_urls))

            self.assertEqual(["http://127.0.0.1:8767"], opened_urls)
            self.assertIn("Running at", launcher._status_value.get())
            showerror.assert_not_called()

            launcher.quit()
            self.assertTrue(servers[0].should_exit)
        finally:
            try:
                root.destroy()
            except tk.TclError:
                pass

    def test_existing_non_webui_http_service_reports_conflict(self):
        tk, root = _make_tk_root()
        root.withdraw()
        opened_urls = []
        server_factory_called = False

        def server_factory(_manager, _port):
            nonlocal server_factory_called
            server_factory_called = True
            raise AssertionError("non-WebUI port conflict should not start a server")

        try:
            launcher = LauncherApp(
                root,
                server_factory=server_factory,
                browser_open=opened_urls.append,
                readiness_checker=lambda _url: False,
                http_checker=lambda _url: True,
            )

            with patch("keysight_logger_webui.launcher.messagebox.showerror") as showerror:
                launcher.start()
                _drain_tk_events(root)

            self.assertFalse(server_factory_called)
            self.assertEqual([], opened_urls)
            showerror.assert_called_once()
            title, message = showerror.call_args.args
            self.assertEqual("Start failed", title)
            self.assertIn("Port 8767 is already in use", message)
            self.assertEqual("normal", launcher._start_button.cget("state"))
        finally:
            try:
                root.destroy()
            except tk.TclError:
                pass


def _import_tkinter():
    try:
        import tkinter as tk
    except Exception as exc:  # pragma: no cover - environment dependent
        raise unittest.SkipTest(f"tkinter is unavailable: {exc}") from exc
    return tk


def _make_tk_root():
    tk = _import_tkinter()
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise unittest.SkipTest(f"tkinter display is unavailable: {exc}") from exc
    return tk, root


def _drain_tk_events(root, timeout_s: float = 1.0, condition=None):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        root.update()
        if condition is not None and condition():
            return
        time.sleep(0.01)


if __name__ == "__main__":
    unittest.main()
