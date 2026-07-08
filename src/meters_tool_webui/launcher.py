from __future__ import annotations

import json
from queue import Empty, Queue
import threading
import time
import tkinter as tk
from tkinter import messagebox
from urllib.error import HTTPError, URLError
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


class LauncherApp:
    def __init__(
        self,
        root: tk.Tk,
        *,
        server_factory: Callable[[WebRunManager, int], Any] | None = None,
        browser_open: Callable[[str], object] | None = None,
        readiness_checker: Callable[[str], bool] | None = None,
        http_checker: Callable[[str], bool] | None = None,
    ) -> None:
        self._root = root
        self._server_factory = server_factory or self._create_server
        self._browser_open = browser_open or webbrowser.open
        self._readiness_checker = readiness_checker or _server_is_ready
        self._http_checker = http_checker or _http_server_is_ready
        self._manager: WebRunManager | None = None
        self._server: Any | None = None
        self._server_thread: threading.Thread | None = None
        self._startup_thread: threading.Thread | None = None
        self._ui_queue: Queue[Callable[[], None]] = Queue()
        self._startup_success = threading.Event()
        self._server_error: BaseException | None = None

        self._use_default_port = tk.BooleanVar(value=True)
        self._port_value = tk.StringVar(value=str(DEFAULT_PORT))
        self._url_value = tk.StringVar(value=build_local_url(DEFAULT_PORT))
        self._status_value = tk.StringVar(value="Ready")

        self._root.title("Meters Tool WebUI Launcher")
        self._root.protocol("WM_DELETE_WINDOW", self.quit)

        frame = tk.Frame(self._root, padx=16, pady=14)
        frame.grid(row=0, column=0, sticky="nsew")
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        default_checkbox = tk.Checkbutton(
            frame,
            text=f"Use default port {DEFAULT_PORT}",
            variable=self._use_default_port,
            command=self._sync_port_controls,
        )
        default_checkbox.grid(row=0, column=0, columnspan=2, sticky="w")

        tk.Label(frame, text="Port").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self._port_entry = tk.Entry(frame, textvariable=self._port_value, width=10)
        self._port_entry.grid(row=1, column=1, sticky="w", pady=(10, 0))

        tk.Label(frame, text="URL").grid(row=2, column=0, sticky="w", pady=(10, 0))
        tk.Label(frame, textvariable=self._url_value, anchor="w").grid(
            row=2, column=1, sticky="ew", pady=(10, 0)
        )

        tk.Label(frame, textvariable=self._status_value, anchor="w").grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0)
        )

        button_row = tk.Frame(frame)
        button_row.grid(row=4, column=0, columnspan=2, sticky="e", pady=(14, 0))
        self._start_button = tk.Button(
            button_row,
            text="Start",
            width=10,
            command=self.start,
        )
        self._start_button.grid(row=0, column=0, padx=(0, 8))
        tk.Button(button_row, text="Quit", width=10, command=self.quit).grid(
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

    def start(self) -> None:
        try:
            port = self._selected_port()
        except ValueError as exc:
            messagebox.showerror("Invalid port", str(exc))
            return

        self._lock_started_controls()
        self._status_value.set("Starting...")
        self._port_value.set(str(port))
        url = build_local_url(port)
        health_url = f"{url}/api/capabilities"
        self._startup_success.clear()
        self._server_error = None
        if self._readiness_checker(health_url):
            self._mark_server_ready(url, already_running=True)
            return
        if self._http_checker(url):
            self._show_startup_error(
                RuntimeError(
                    f"Port {port} is already in use by a service that is not {PACKAGE_NAME}."
                )
            )
            return
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
            self._show_startup_error(exc)

    def _wait_for_startup(self, port: int) -> None:
        url = build_local_url(port)
        health_url = f"{url}/api/capabilities"
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            if self._readiness_checker(health_url) or self._http_checker(url):
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
        try:
            self._server.run()
        except BaseException as exc:  # pragma: no cover - runtime safety net
            self._server_error = exc

    def _mark_server_ready(self, url: str, *, already_running: bool = False) -> None:
        self._startup_success.set()
        if already_running:
            self._status_value.set(f"Server already running at {url}")
        else:
            self._status_value.set(f"Running at {url}")
        self._browser_open(url)

    def _show_startup_error(self, exc: BaseException) -> None:
        if self._startup_success.is_set():
            return
        message = f"{type(exc).__name__}: {exc}"
        self._status_value.set(f"Failed: {message}")
        self._start_button.configure(state="normal")
        if self._server is not None:
            self._server.should_exit = True
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
        if self._manager is not None:
            self._manager.close_event_streams()
        if self._server is not None:
            self._server.should_exit = True
        if self._server_thread is not None and self._server_thread.is_alive():
            self._server_thread.join(timeout=3.0)
        self._root.destroy()

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
            return app.get("name") == "meters-tool-webui"
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return False


def _http_server_is_ready(url: str) -> bool:
    try:
        with urlopen(url, timeout=0.5) as response:
            return 100 <= int(response.status) < 600
    except HTTPError as exc:
        return 100 <= int(exc.code) < 600
    except (OSError, URLError, ValueError):
        return False


def main() -> int:
    root = tk.Tk()
    LauncherApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
