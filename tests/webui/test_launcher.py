from __future__ import annotations

import contextlib
import errno
import io
import json
from pathlib import Path
from queue import Empty, Queue
import threading
import time
import unittest
from unittest.mock import patch

from meters_tool_webui import launcher


class FakeResponse:
    def __init__(self, payload: object, events: list[str] | None = None) -> None:
        self.status = 200
        self._payload = payload
        self._events = events

    def __enter__(self):
        if self._events is not None:
            self._events.append("capabilities-ready")
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class FakeValue:
    def __init__(self, value="") -> None:
        self.value = value

    def set(self, value) -> None:
        self.value = value

    def get(self):
        return self.value


class FakeBoolean(FakeValue):
    pass


class FakeControl:
    def __init__(self) -> None:
        self.state = "normal"
        self.visible = True

    def configure(self, **kwargs) -> None:
        if "state" in kwargs:
            self.state = kwargs["state"]

    def grid(self, **_kwargs) -> None:
        self.visible = True

    def grid_remove(self) -> None:
        self.visible = False

    def cget(self, name: str):
        if name == "state":
            return self.state
        raise KeyError(name)


class FakeRoot:
    def __init__(self, events: list[str] | None = None) -> None:
        self.events = events if events is not None else []
        self.destroyed = False
        self.withdrawn = False
        self.restored = False
        self.lifted = False
        self.icon_path = None

    def iconbitmap(self, *, default) -> None:
        self.icon_path = default

    def after(self, _delay, callback) -> None:
        callback()

    def mainloop(self) -> None:
        return None

    def withdraw(self) -> None:
        self.withdrawn = True

    def deiconify(self) -> None:
        self.withdrawn = False
        self.restored = True

    def lift(self) -> None:
        self.lifted = True

    def update_idletasks(self) -> None:
        return None

    def destroy(self) -> None:
        self.events.append("window.destroy")
        self.destroyed = True


class FakeServerConfig:
    def __init__(self) -> None:
        self.setup_event_loop_accessed = False

    @property
    def setup_event_loop(self):
        self.setup_event_loop_accessed = True
        raise AttributeError("setup_event_loop was removed")


class FakeServer:
    def __init__(self, *, error: BaseException | None = None) -> None:
        self.should_exit = False
        self.config = FakeServerConfig()
        self.served_sockets: list[object] = []
        self.error = error

    async def serve(self, *, sockets: list[object]) -> None:
        self.served_sockets = sockets
        if self.error is not None:
            raise self.error


class FakeSocket:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class ImmediateThread:
    def __init__(self, *, target, name: str, daemon: bool, args=()) -> None:
        self._target = target
        self._args = args
        self._alive = False

    def start(self) -> None:
        self._alive = True
        self._target(*self._args)
        self._alive = False

    def is_alive(self) -> bool:
        return self._alive

    def join(self, timeout=None) -> None:
        self._alive = False


class LauncherHelperTests(unittest.TestCase):
    def test_default_url_uses_loopback_and_default_port(self):
        self.assertEqual(
            "http://127.0.0.1:8767",
            launcher.build_local_url(launcher.DEFAULT_PORT),
        )

    def test_parse_port_rejects_invalid_values(self):
        for value in ("", "abc", "0", "65536"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    launcher.parse_port(value)

    def test_parse_port_accepts_valid_values(self):
        self.assertEqual(8767, launcher.parse_port("8767"))
        self.assertEqual(8080, launcher.parse_port(" 8080 "))

    def test_candidate_ports_apply_mode_limit_and_legal_upper_bound(self):
        automatic = launcher._candidate_ports(8767, auto_port=True)
        self.assertEqual(100, len(automatic))
        self.assertEqual((8767, 8866), (automatic[0], automatic[-1]))
        self.assertEqual((9000,), launcher._candidate_ports(9000, auto_port=False))
        self.assertEqual(
            (65534, 65535),
            launcher._candidate_ports(65534, auto_port=True),
        )

    def test_window_icon_uses_packaged_asset(self):
        root = FakeRoot()
        bundle_root = Path("C:/meters-tool/_internal")
        icon_path = bundle_root / "meters_tool_webui" / "assets" / "meters-icon.ico"
        with (
            patch.object(launcher.sys, "_MEIPASS", str(bundle_root), create=True),
            patch.object(Path, "is_file", return_value=True),
        ):
            launcher._apply_window_icon(root)

        self.assertEqual(str(icon_path), root.icon_path)

    def test_window_icon_failures_do_not_block_startup(self):
        class FailingRoot:
            def iconbitmap(self, *, default) -> None:
                raise launcher.tk.TclError(f"cannot load {default}")

        with patch.object(Path, "is_file", return_value=False):
            launcher._apply_window_icon(FailingRoot())
        with patch.object(Path, "is_file", return_value=True):
            launcher._apply_window_icon(FailingRoot())

    def test_self_test_succeeds_with_required_static_resources(self):
        with (
            patch("meters_tool_webui.launcher.import_module"),
            patch("meters_tool_webui.launcher.files") as resource_files,
        ):
            static_root = resource_files.return_value.joinpath.return_value
            static_root.joinpath.return_value.is_file.return_value = True

            self.assertEqual(0, launcher.run_self_test())

    def test_self_test_fails_when_static_resource_is_missing(self):
        with (
            patch("meters_tool_webui.launcher.import_module"),
            patch("meters_tool_webui.launcher.files") as resource_files,
        ):
            static_root = resource_files.return_value.joinpath.return_value
            static_root.joinpath.return_value.is_file.side_effect = [True, False, True]

            self.assertEqual(1, launcher.run_self_test())

    @patch("meters_tool_webui.launcher.tk.Tk")
    def test_self_test_does_not_create_tk_root(self, tk_root):
        self.assertEqual(0, launcher.main(["--self-test"]))
        tk_root.assert_not_called()

    @patch("meters_tool_webui.launcher.tk.Tk")
    def test_help_documents_port_modes_without_creating_tk_root(self, tk_root):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            launcher.main(["--help"])

        help_text = output.getvalue()
        self.assertIn("--port PORT", help_text)
        self.assertIn("--auto-port", help_text)
        self.assertIn("Fixed port to bind", help_text)
        self.assertIn("up to 100 ports", help_text)
        tk_root.assert_not_called()

    @patch("meters_tool_webui.launcher.tk.Tk")
    def test_cli_rejects_invalid_port_without_creating_tk_root(self, tk_root):
        output = io.StringIO()
        with contextlib.redirect_stderr(output), self.assertRaises(SystemExit):
            launcher.main(["--port", "65536"])

        self.assertIn("Port must be between 1 and 65535.", output.getvalue())
        tk_root.assert_not_called()

    def test_main_maps_cli_arguments_to_initial_port_and_auto_mode(self):
        cases = (
            ([], launcher.DEFAULT_PORT, True),
            (["--port", "9000"], 9000, False),
            (["--port", "9000", "--auto-port"], 9000, True),
            (["--auto-port"], launcher.DEFAULT_PORT, True),
        )

        for argv, expected_port, expected_auto in cases:
            with self.subTest(argv=argv):
                root = FakeRoot()
                calls = []

                class FakeApp:
                    def __init__(self, _root, *, initial_port):
                        calls.append(("init", initial_port))

                    def start(self, *, auto_port):
                        calls.append(("start", auto_port))

                with (
                    patch("meters_tool_webui.launcher.tk.Tk", return_value=root),
                    patch("meters_tool_webui.launcher.LauncherApp", FakeApp),
                ):
                    self.assertEqual(0, launcher.main(list(argv)))

                self.assertTrue(root.withdrawn)
                self.assertEqual(str(launcher._launcher_icon_path()), root.icon_path)
                self.assertEqual(
                    [("init", expected_port), ("start", expected_auto)],
                    calls,
                )

    def test_server_is_ready_rejects_wrong_identity(self):
        response = FakeResponse({"app": {"name": "other-service"}})
        with patch("meters_tool_webui.launcher.urlopen", return_value=response):
            self.assertFalse(
                launcher._server_is_ready(
                    "http://127.0.0.1:8767/api/capabilities"
                )
            )


class LauncherStartupTests(unittest.TestCase):
    def test_auto_port_hands_same_socket_to_uvicorn_then_opens_actual_ready_url(self):
        for retryable_error in _retryable_bind_errors():
            with self.subTest(retryable_error=type(retryable_error).__name__):
                self._assert_auto_port_skips_to_next_candidate(retryable_error)

    def _assert_auto_port_skips_to_next_candidate(self, retryable_error):
        attempted_ports = []
        created_ports = []
        browser_urls = []
        events = []
        bound_socket = FakeSocket()
        server = FakeServer()

        def socket_binder(port):
            attempted_ports.append(port)
            if port == launcher.DEFAULT_PORT:
                raise OSError(errno.EADDRINUSE, "in use")
            if port == launcher.DEFAULT_PORT + 1:
                raise retryable_error
            return bound_socket

        def server_factory(_manager, port):
            created_ports.append(port)
            return server

        app = _make_startup_launcher(
            initial_port=launcher.DEFAULT_PORT,
            socket_binder=socket_binder,
            server_factory=server_factory,
            browser_open=lambda url: (events.append("browser"), browser_urls.append(url)),
        )
        response = FakeResponse(
            {"app": {"name": "meters-tool-webui", "version": "test"}},
            events,
        )

        with (
            patch("meters_tool_webui.launcher.threading.Thread", ImmediateThread),
            patch("meters_tool_webui.launcher.urlopen", return_value=response) as urlopen,
            patch("meters_tool_webui.launcher.messagebox.showerror") as showerror,
        ):
            app.start(auto_port=True)
            _drain_ui_queue(app)

        expected_url = f"http://127.0.0.1:{launcher.DEFAULT_PORT + 2}"
        self.assertEqual([8767, 8768, 8769], attempted_ports)
        self.assertEqual([8769], created_ports)
        self.assertFalse(server.config.setup_event_loop_accessed)
        self.assertEqual([bound_socket], server.served_sockets)
        self.assertEqual(["capabilities-ready", "browser"], events)
        self.assertEqual([expected_url], browser_urls)
        self.assertEqual(f"Running at {expected_url}", app._status_value.get())
        self.assertFalse(app._config_frame.visible)
        self.assertFalse(app._start_button.visible)
        self.assertTrue(app._root.restored)
        self.assertTrue(bound_socket.closed)
        urlopen.assert_called_once_with(
            f"{expected_url}/api/capabilities",
            timeout=0.5,
        )
        showerror.assert_not_called()

    def test_fixed_port_bind_error_attempts_once_and_exits(self):
        cases = (
            (
                OSError(errno.EADDRINUSE, "in use"),
                "RuntimeError: Port 9000 is already in use.",
            ),
            (
                PermissionError(errno.EACCES, "bind denied"),
                "PermissionError: [Errno 13] bind denied",
            ),
        )

        for bind_error, expected_message in cases:
            with self.subTest(bind_error=type(bind_error).__name__):
                attempted_ports = []
                app = _make_startup_launcher(
                    initial_port=9000,
                    socket_binder=lambda port: _raise_bind_error(
                        attempted_ports, port, bind_error
                    ),
                    server_factory=lambda _manager, _port: self.fail(
                        "server must not be created"
                    ),
                )

                with patch("meters_tool_webui.launcher.messagebox.showerror") as showerror:
                    app.start()

                self.assertEqual([9000], attempted_ports)
                self.assertTrue(app._root.destroyed)
                self.assertFalse(app._root.restored)
                showerror.assert_called_once_with("Start failed", expected_message)

    def test_auto_port_exhaustion_shows_fallback_and_manual_retry_stays_fixed(self):
        attempted_ports = []
        retryable_errors = iter(
            [
                OSError(errno.EADDRINUSE, "in use"),
                PermissionError(errno.EACCES, "bind denied"),
                _windows_access_denied(),
            ]
        )

        def socket_binder(port):
            attempted_ports.append(port)
            raise next(retryable_errors)

        app = _make_startup_launcher(
            initial_port=launcher.DEFAULT_PORT,
            socket_binder=socket_binder,
            server_factory=lambda _manager, _port: self.fail("server must not be created"),
        )

        with (
            patch("meters_tool_webui.launcher.AUTO_PORT_ATTEMPTS", 3),
            patch("meters_tool_webui.launcher.messagebox.showerror") as showerror,
        ):
            app.start(auto_port=True)
            self.assertEqual([8767, 8768, 8769], attempted_ports)
            self.assertTrue(app._fallback_active)
            self.assertTrue(app._root.restored)
            self.assertTrue(app._config_frame.visible)
            self.assertEqual("normal", app._port_entry.state)
            self.assertIn("8767..8769", app._status_value.get())

            app._port_value.set("9100")
            app._socket_binder = lambda port: _raise_bind_error(
                attempted_ports, port, PermissionError(errno.EACCES, "bind denied")
            )

            app.start()
            self.assertFalse(app._root.destroyed)
            self.assertEqual("normal", app._start_button.state)
            self.assertEqual("normal", app._default_checkbox.state)
            self.assertIn("PermissionError", app._status_value.get())

            app.start()

        self.assertEqual([8767, 8768, 8769, 9100, 9100], attempted_ports)
        self.assertEqual(3, showerror.call_count)

    def test_unexpected_bind_error_stops_auto_search_and_exits(self):
        attempted_ports = []
        expected_error = PermissionError("bind denied")

        def socket_binder(port):
            attempted_ports.append(port)
            raise expected_error

        app = _make_startup_launcher(
            initial_port=launcher.DEFAULT_PORT,
            socket_binder=socket_binder,
            server_factory=lambda _manager, _port: self.fail("server must not be created"),
        )

        with patch("meters_tool_webui.launcher.messagebox.showerror") as showerror:
            app.start(auto_port=True)

        self.assertEqual([launcher.DEFAULT_PORT], attempted_ports)
        self.assertIs(expected_error, app._server_error)
        self.assertTrue(app._root.destroyed)
        showerror.assert_called_once_with(
            "Start failed",
            "PermissionError: bind denied",
        )

    def test_server_factory_error_closes_socket_and_preserves_exception(self):
        bound_socket = FakeSocket()
        expected_error = RuntimeError("application initialization failed")
        app = _make_startup_launcher(
            initial_port=launcher.DEFAULT_PORT,
            socket_binder=lambda _port: bound_socket,
            server_factory=lambda _manager, _port: _raise(expected_error),
        )

        with patch("meters_tool_webui.launcher.messagebox.showerror"):
            app.start(auto_port=True)

        self.assertTrue(bound_socket.closed)
        self.assertIs(expected_error, app._server_error)
        self.assertTrue(app._root.destroyed)

    def test_server_thread_exit_before_readiness_reports_original_error(self):
        bound_socket = FakeSocket()
        server_error = SystemExit(1)
        server = FakeServer(error=server_error)
        app = _make_startup_launcher(
            initial_port=launcher.DEFAULT_PORT,
            socket_binder=lambda _port: bound_socket,
            server_factory=lambda _manager, _port: server,
            readiness_checker=lambda _url: False,
        )

        with (
            patch("meters_tool_webui.launcher.threading.Thread", ImmediateThread),
            patch("meters_tool_webui.launcher.messagebox.showerror") as showerror,
        ):
            app.start(auto_port=True)
            _drain_ui_queue(app)

        self.assertTrue(bound_socket.closed)
        self.assertTrue(app._root.destroyed)
        showerror.assert_called_once_with("Start failed", "SystemExit: 1")


class LauncherLifecycleTests(unittest.TestCase):
    def test_idle_quit_shuts_down_manager_server_and_window(self):
        events = []

        class FakeManager:
            def shutdown(self):
                events.append("manager.shutdown")
                return True

        class FakeShutdownServer:
            should_exit = False

        app = _make_shutdown_launcher(
            manager=FakeManager(),
            server=FakeShutdownServer(),
            events=events,
        )
        app.quit()

        self.assertEqual(["manager.shutdown", "window.destroy"], events)
        self.assertTrue(app.server.should_exit)

    def test_active_quit_waits_for_manager_before_stopping_server(self):
        events = []

        class FakeManager:
            def shutdown(self):
                events.extend(["manager.stop", "worker.join"])
                return True

        class FakeShutdownServer:
            def __init__(self):
                self._should_exit = False

            @property
            def should_exit(self):
                return self._should_exit

            @should_exit.setter
            def should_exit(self, value):
                self._should_exit = value
                events.append("server.should_exit")

        class FakeServerThread:
            def is_alive(self):
                return True

            def join(self, timeout=None):
                events.append("server.join")

        app = _make_shutdown_launcher(
            manager=FakeManager(),
            server=FakeShutdownServer(),
            server_thread=FakeServerThread(),
            events=events,
        )
        app.quit()

        self.assertEqual(
            [
                "manager.stop",
                "worker.join",
                "server.should_exit",
                "server.join",
                "window.destroy",
            ],
            events,
        )

    def test_repeated_quit_only_starts_shutdown_once(self):
        shutdown_calls = []

        class FakeManager:
            def shutdown(self):
                shutdown_calls.append("shutdown")
                return True

        app = _make_shutdown_launcher(manager=FakeManager())
        app.quit()
        app.quit()

        self.assertEqual(["shutdown"], shutdown_calls)

    def test_shutdown_timeout_keeps_launcher_open_and_retry_completes_exit(self):
        class FakeManager:
            def __init__(self):
                self.shutdown_results = iter((False, True))

            def shutdown(self):
                return next(self.shutdown_results)

        class FakeShutdownServer:
            should_exit = False

        class FakeServerThread:
            def __init__(self):
                self.join_calls = 0

            def is_alive(self):
                return True

            def join(self, timeout=None):
                self.join_calls += 1

        events = []
        server_thread = FakeServerThread()
        app = _make_shutdown_launcher(
            manager=FakeManager(),
            server=FakeShutdownServer(),
            server_thread=server_thread,
            events=events,
        )

        started = time.monotonic()
        with patch("meters_tool_webui.launcher.messagebox.showerror") as showerror:
            app.quit()
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 1.0)
        self.assertFalse(app.server.should_exit)
        self.assertEqual(0, server_thread.join_calls)
        self.assertEqual([], events)
        self.assertFalse(app._quitting)
        self.assertEqual("normal", app._quit_button.state)
        self.assertFalse(app._config_frame.visible)
        self.assertTrue(app._root.restored)
        showerror.assert_called_once_with(
            "Shutdown incomplete",
            "Timed out waiting for the active run to finish cleanup.",
        )

        app.quit()

        self.assertTrue(app.server.should_exit)
        self.assertEqual(1, server_thread.join_calls)
        self.assertEqual(["window.destroy"], events)


def _make_startup_launcher(
    *,
    initial_port,
    socket_binder,
    server_factory,
    readiness_checker=launcher._server_is_ready,
    browser_open=lambda _url: None,
):
    app = launcher.LauncherApp.__new__(launcher.LauncherApp)
    app._root = FakeRoot()
    app._server_factory = server_factory
    app._socket_binder = socket_binder
    app._browser_open = browser_open
    app._readiness_checker = readiness_checker
    app._manager = None
    app._server = None
    app._server_socket = None
    app._server_thread = None
    app._server_loop = None
    app._startup_thread = None
    app._ui_queue = Queue()
    app._startup_success = threading.Event()
    app._server_error = None
    app._fallback_active = False
    app._quitting = False
    app._use_default_port = FakeBoolean(initial_port == launcher.DEFAULT_PORT)
    app._port_value = FakeValue(str(initial_port))
    app._url_value = FakeValue(launcher.build_local_url(initial_port))
    app._status_value = FakeValue("Ready")
    app._config_frame = FakeControl()
    app._start_button = FakeControl()
    app._default_checkbox = FakeControl()
    app._port_entry = FakeControl()
    app._quit_button = FakeControl()
    return app


def _make_shutdown_launcher(
    *,
    manager=None,
    server=None,
    server_thread=None,
    events=None,
):
    app = launcher.LauncherApp.__new__(launcher.LauncherApp)
    app._root = FakeRoot(events)
    app._manager = manager
    app._server = server
    app._server_thread = server_thread
    app._quitting = False
    app._start_button = FakeControl()
    app._default_checkbox = FakeControl()
    app._port_entry = FakeControl()
    app._quit_button = FakeControl()
    app._config_frame = FakeControl()
    app._status_value = FakeValue()
    return app


def _drain_ui_queue(app):
    while True:
        try:
            callback = app._ui_queue.get_nowait()
        except Empty:
            return
        callback()


def _retryable_bind_errors():
    return (
        PermissionError(errno.EACCES, "bind denied"),
        _windows_access_denied(),
    )


def _windows_access_denied():
    error = OSError(None, "address already in use")
    error.errno = errno.EACCES
    error.winerror = 10013
    return error


def _raise_bind_error(attempted_ports, port, error):
    attempted_ports.append(port)
    raise error


def _raise(exc):
    raise exc


if __name__ == "__main__":
    unittest.main()
