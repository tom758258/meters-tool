from __future__ import annotations

import argparse
import asyncio
import errno
from importlib import import_module
from importlib.resources import files
import json
from pathlib import Path
from queue import Empty, Queue
import socket
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser
from typing import Any, Callable

try:
    from .web_ui import PACKAGE_NAME, WebRunManager, create_uvicorn_server
except ImportError:  # pragma: no cover - PyInstaller script entry point
    from meters_tool_webui.web_ui import (
        PACKAGE_NAME,
        WebRunManager,
        create_uvicorn_server,
    )


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8767
AUTO_PORT_ATTEMPTS = 100


def _launcher_icon_path() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if isinstance(bundle_root, str) and bundle_root:
        return Path(bundle_root) / "meters_tool_webui" / "assets" / "meters-icon.ico"
    return Path(__file__).resolve().parents[2] / "desktop" / "assets" / "meters-icon.ico"


def _apply_window_icon(root: tk.Tk) -> None:
    icon_path = _launcher_icon_path()
    try:
        if icon_path.is_file():
            root.iconbitmap(default=str(icon_path))
    except (OSError, tk.TclError):
        pass


def build_local_url(port: int) -> str:
    return f"http://{DEFAULT_HOST}:{port}"


def parse_port(value: str) -> int:
    try:
        port = int(value.strip())
    except ValueError as exc:
        raise ValueError("Port must be a number.") from exc
    if port < 1 or port > 65535:
        raise ValueError("Port must be between 1 and 65535.")
    return port


def _parse_cli_port(value: str) -> int:
    try:
        return parse_port(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _candidate_ports(start_port: int, *, auto_port: bool) -> tuple[int, ...]:
    attempt_count = AUTO_PORT_ATTEMPTS if auto_port else 1
    stop_port = min(start_port + attempt_count, 65536)
    return tuple(range(start_port, stop_port))


def bind_local_socket(port: int) -> socket.socket:
    return socket.create_server((DEFAULT_HOST, port))


def _is_port_in_use_error(exc: OSError) -> bool:
    return exc.errno == errno.EADDRINUSE or getattr(exc, "winerror", None) == 10048


def _is_retryable_bind_error(exc: OSError) -> bool:
    if _is_port_in_use_error(exc):
        return True
    return exc.errno == errno.EACCES or getattr(exc, "winerror", None) == 10013


def run_self_test() -> int:
    try:
        for module_name in ("meters_tool_webui", "meters_tool_webui.web_ui"):
            import_module(module_name)
        static_root = files("meters_tool_webui").joinpath("static")
        missing = [
            name
            for name in ("index.html", "styles.css", "app.js")
            if not static_root.joinpath(name).is_file()
        ]
        if missing:
            raise FileNotFoundError(f"Missing packaged WebUI static files: {missing}")
    except Exception as exc:
        if sys.stderr is not None:
            print(
                f"WebUI launcher self-test failed: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
        return 1
    if sys.stdout is not None:
        print("WebUI launcher self-test passed")
    return 0


class LauncherApp:
    def __init__(
        self,
        root: tk.Tk,
        *,
        server_factory: Callable[[WebRunManager, int], Any] | None = None,
        socket_binder: Callable[[int], Any] | None = None,
        browser_open: Callable[[str], object] | None = None,
        readiness_checker: Callable[[str], bool] | None = None,
        initial_port: int = DEFAULT_PORT,
    ) -> None:
        self._root = root
        self._server_factory = server_factory or self._create_server
        self._socket_binder = socket_binder or bind_local_socket
        self._browser_open = browser_open or webbrowser.open
        self._readiness_checker = readiness_checker or _server_is_ready
        self._manager: WebRunManager | None = None
        self._server: Any | None = None
        self._server_socket: Any | None = None
        self._server_thread: threading.Thread | None = None
        self._server_loop: asyncio.AbstractEventLoop | None = None
        self._startup_thread: threading.Thread | None = None
        self._ui_queue: Queue[Callable[[], None]] = Queue()
        self._startup_success = threading.Event()
        self._server_error: BaseException | None = None
        self._fallback_active = False
        self._quitting = False

        self._use_default_port = tk.BooleanVar(value=initial_port == DEFAULT_PORT)
        self._port_value = tk.StringVar(value=str(initial_port))
        self._url_value = tk.StringVar(value=build_local_url(initial_port))
        self._status_value = tk.StringVar(value="Ready")

        self._root.title("Meters Tool WebUI Launcher")
        self._root.protocol("WM_DELETE_WINDOW", self.quit)

        frame = tk.Frame(self._root, padx=16, pady=14)
        frame.grid(row=0, column=0, sticky="nsew")
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        self._config_frame = tk.Frame(frame)
        self._config_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        self._config_frame.columnconfigure(1, weight=1)
        self._default_checkbox = tk.Checkbutton(
            self._config_frame,
            text=f"Use default port {DEFAULT_PORT}",
            variable=self._use_default_port,
            command=self._sync_port_controls,
        )
        self._default_checkbox.grid(row=0, column=0, columnspan=2, sticky="w")

        tk.Label(self._config_frame, text="Port").grid(
            row=1, column=0, sticky="w", pady=(10, 0)
        )
        self._port_entry = tk.Entry(
            self._config_frame,
            textvariable=self._port_value,
            width=10,
        )
        self._port_entry.grid(row=1, column=1, sticky="w", pady=(10, 0))

        tk.Label(frame, text="URL").grid(row=1, column=0, sticky="w", pady=(10, 0))
        tk.Label(frame, textvariable=self._url_value, anchor="w").grid(
            row=1, column=1, sticky="ew", pady=(10, 0)
        )

        tk.Label(frame, textvariable=self._status_value, anchor="w").grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0)
        )

        button_row = tk.Frame(frame)
        button_row.grid(row=3, column=0, columnspan=2, sticky="e", pady=(14, 0))
        self._start_button = tk.Button(
            button_row,
            text="Start",
            width=10,
            command=self.start,
        )
        self._start_button.grid(row=0, column=0, padx=(0, 8))
        self._quit_button = tk.Button(
            button_row,
            text="Quit",
            width=10,
            command=self.quit,
        )
        self._quit_button.grid(
            row=0,
            column=1,
        )

        self._port_value.trace_add("write", lambda *_args: self._update_url())
        self._sync_port_controls()
        self._root.after(100, self._process_ui_queue)

    @property
    def server(self) -> Any | None:
        return self._server

    @property
    def server_thread(self) -> threading.Thread | None:
        return self._server_thread

    def start(self, *, auto_port: bool = False) -> None:
        try:
            start_port = self._selected_port()
        except ValueError as exc:
            messagebox.showerror("Invalid port", str(exc))
            return

        candidates = _candidate_ports(start_port, auto_port=auto_port)
        self._lock_started_controls()
        if auto_port:
            self._status_value.set(
                f"Starting on an available port in {candidates[0]}..{candidates[-1]}..."
            )
        else:
            self._status_value.set(f"Starting on port {start_port}...")
        self._startup_success.clear()
        self._server_error = None
        self._manager = None
        self._server = None
        self._server_socket = None
        self._server_thread = None
        self._server_loop = None

        for port in candidates:
            self._port_value.set(str(port))
            try:
                server_socket = self._socket_binder(port)
            except OSError as exc:
                if self._fallback_active:
                    self._show_manual_port_error(port, exc)
                    return
                if auto_port and _is_retryable_bind_error(exc):
                    continue
                if _is_port_in_use_error(exc):
                    self._show_startup_error(
                        RuntimeError(f"Port {port} is already in use.")
                    )
                else:
                    self._show_startup_error(exc)
                return

            if port != DEFAULT_PORT:
                self._use_default_port.set(False)
                self._port_value.set(str(port))
            self._server_socket = server_socket
            try:
                self._manager = WebRunManager()
                self._server = self._server_factory(self._manager, port)
                self._server_thread = threading.Thread(
                    target=self._run_server,
                    name="meters-tool-webui-launcher-server",
                    daemon=True,
                )
                self._server_thread.start()
                self._startup_thread = threading.Thread(
                    target=self._wait_for_startup,
                    args=(port,),
                    name="meters-tool-webui-launcher-startup",
                    daemon=True,
                )
                self._startup_thread.start()
            except Exception as exc:
                if (
                    self._server_thread is None
                    or not self._server_thread.is_alive()
                ):
                    server_socket.close()
                    if self._server_socket is server_socket:
                        self._server_socket = None
                self._show_startup_error(exc)
            return

        self._fallback_active = True
        self._use_default_port.set(False)
        self._sync_port_controls()
        message = (
            f"No available port was found in {candidates[0]}..{candidates[-1]}. "
            "Enter another port and select Start."
        )
        self._status_value.set(message)
        self._show_fallback_window()
        messagebox.showerror("No available port", message)

    def _wait_for_startup(self, port: int) -> None:
        url = build_local_url(port)
        health_url = f"{url}/api/capabilities"
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            if self._readiness_checker(health_url):
                self._post_ui(lambda: self._mark_server_ready(url))
                return
            if self._server_thread is not None and not self._server_thread.is_alive():
                error = self._server_error or RuntimeError(
                    "WebUI server stopped during startup."
                )
                self._post_ui(
                    lambda error=error: self._show_startup_error(error),
                )
                return
            time.sleep(0.2)
        self._post_ui(
            lambda: self._show_startup_error(
                TimeoutError(f"WebUI server did not become ready at {url}.")
            ),
        )

    def _run_server(self) -> None:
        server_socket = self._server_socket
        try:
            asyncio.run(self._serve_server(server_socket))
        except BaseException as exc:  # pragma: no cover - runtime safety net
            self._server_error = exc
        finally:
            if server_socket is not None:
                server_socket.close()
            if self._server_socket is server_socket:
                self._server_socket = None
            self._server_loop = None

    async def _serve_server(self, server_socket: Any) -> None:
        self._server_loop = asyncio.get_running_loop()
        await self._server.serve(sockets=[server_socket])

    def _mark_server_ready(self, url: str) -> None:
        self._startup_success.set()
        self._fallback_active = False
        self._status_value.set(f"Running at {url}")
        self._show_running_window()
        self._browser_open(url)

    def _show_startup_error(self, exc: BaseException) -> None:
        if self._startup_success.is_set():
            return
        self._server_error = exc
        message = f"{type(exc).__name__}: {exc}"
        self._status_value.set(f"Failed: {message}")
        messagebox.showerror("Start failed", message)
        self.quit()

    def _show_manual_port_error(self, port: int, exc: OSError) -> None:
        if _is_port_in_use_error(exc):
            message = f"Port {port} is already in use."
        else:
            message = f"{type(exc).__name__}: {exc}"
        self._status_value.set(f"Failed: {message}")
        self._start_button.configure(state="normal")
        self._default_checkbox.configure(state="normal")
        self._sync_port_controls()
        messagebox.showerror("Start failed", message)

    def _post_ui(self, callback: Callable[[], None]) -> None:
        self._ui_queue.put(callback)

    def _process_ui_queue(self) -> None:
        while True:
            try:
                callback = self._ui_queue.get_nowait()
            except Empty:
                break
            callback()
        try:
            self._root.after(100, self._process_ui_queue)
        except tk.TclError:
            pass

    def quit(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        self._start_button.configure(state="disabled")
        self._default_checkbox.configure(state="disabled")
        self._port_entry.configure(state="disabled")
        self._quit_button.configure(state="disabled")
        self._status_value.set("Stopping...")
        self._root.update_idletasks()

        shutdown_error: Exception | None = None
        shutdown_complete = True
        if self._manager is not None:
            try:
                shutdown_complete = self._manager.shutdown()
            except Exception as exc:
                shutdown_complete = False
                shutdown_error = exc

        if not shutdown_complete:
            if shutdown_error is None:
                message = "Timed out waiting for the active run to finish cleanup."
            else:
                message = f"{type(shutdown_error).__name__}: {shutdown_error}"
            self._status_value.set(f"Shutdown incomplete: {message}")
            messagebox.showerror("Shutdown incomplete", message)
            self._quitting = False
            self._quit_button.configure(state="normal")
            self._show_running_window()
            return

        if self._server is not None:
            self._server.should_exit = True
        if self._server_thread is not None and self._server_thread.is_alive():
            self._server_thread.join(timeout=3.0)
        self._root.destroy()

    def _show_running_window(self) -> None:
        self._config_frame.grid_remove()
        self._start_button.grid_remove()
        self._quit_button.configure(state="normal")
        self._root.deiconify()

    def _show_fallback_window(self) -> None:
        self._config_frame.grid()
        self._start_button.grid()
        self._start_button.configure(state="normal")
        self._default_checkbox.configure(state="normal")
        self._quit_button.configure(state="normal")
        self._sync_port_controls()
        self._root.deiconify()
        self._root.lift()

    def _sync_port_controls(self) -> None:
        if self._use_default_port.get():
            self._port_value.set(str(DEFAULT_PORT))
            self._port_entry.configure(state="disabled")
        else:
            self._port_entry.configure(state="normal")
        self._update_url()

    def _update_url(self) -> None:
        try:
            port = self._selected_port()
        except ValueError:
            self._url_value.set(f"http://{DEFAULT_HOST}:")
            return
        self._url_value.set(build_local_url(port))

    def _selected_port(self) -> int:
        if self._use_default_port.get():
            return DEFAULT_PORT
        return parse_port(self._port_value.get())

    def _lock_started_controls(self) -> None:
        self._start_button.configure(state="disabled")
        self._default_checkbox.configure(state="disabled")
        self._port_entry.configure(state="disabled")

    @staticmethod
    def _create_server(manager: WebRunManager, port: int) -> Any:
        return create_uvicorn_server(manager, host=DEFAULT_HOST, port=port)


def _server_is_ready(url: str) -> bool:
    try:
        with urlopen(url, timeout=0.5) as response:
            if int(response.status) != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
            app = payload.get("app", {}) if isinstance(payload, dict) else {}
            return app.get("name") == PACKAGE_NAME
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="meters-tool-webui-launcher",
        description="Meters Tool WebUI Launcher",
    )
    parser.add_argument(
        "--port",
        type=_parse_cli_port,
        help="Fixed port to bind; use --auto-port to search from this port",
    )
    parser.add_argument(
        "--auto-port",
        action="store_true",
        help=(
            f"Try up to {AUTO_PORT_ATTEMPTS} ports starting from --port or "
            f"{DEFAULT_PORT}; default when --port is omitted"
        ),
    )
    parser.add_argument("--self-test", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()
    initial_port = args.port if args.port is not None else DEFAULT_PORT
    auto_port = args.auto_port or args.port is None
    root = tk.Tk()
    _apply_window_icon(root)
    root.withdraw()
    app = LauncherApp(root, initial_port=initial_port)
    root.after(0, lambda: app.start(auto_port=auto_port))
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
