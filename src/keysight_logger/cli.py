from __future__ import annotations

import argparse
import ctypes
import json
import signal
import sys
import threading
import time
from pathlib import Path
from urllib import request
from urllib.error import URLError

from .acquisition import TriggerAcquisitionEngine
from .instrument import InstrumentConfig, VisaInstrument
from .measurement import CurrentMeasurement
from .models import KEYSIGHT_34461A_CAPABILITIES, AcquisitionConfig
from .storage import CsvWriter
from .trigger import SoftwareTriggerAdapter, TriggerRouter


class StopController:
    def __init__(self, stop_engine, print_fn=print):  # noqa: ANN001
        self.stop = False
        self.interrupt_count = 0
        self.force = False
        self._stop_engine = stop_engine
        self._print = print_fn
        self._lock = threading.Lock()

    def request_stop(self, force: bool = False) -> None:
        with self._lock:
            self.stop = True
            if force:
                self.force = True
                message = "second interrupt received, forcing shutdown..."
            else:
                message = "interrupt received, stopping gracefully (press Ctrl+C again to force)..."
        self._stop_engine()
        self._print(message)

    def request_http_stop(self) -> None:
        with self._lock:
            self.stop = True
        self._stop_engine()

    def request_signal_stop(self) -> None:
        with self._lock:
            self.interrupt_count += 1
            force = self.interrupt_count >= 2
        self.request_stop(force=force)


class WindowsConsoleStopHandler:
    _CTRL_C_EVENT = 0
    _CTRL_BREAK_EVENT = 1
    _STD_INPUT_HANDLE = -10
    _ENABLE_PROCESSED_INPUT = 0x0001

    def __init__(self, stop_controller: StopController):
        self._stop_controller = stop_controller
        self._kernel32 = None
        self._handler = None
        self._stdin_handle = None
        self._previous_input_mode = None
        self.installed = False
        self.input_mode_configured = False

    def install(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            from ctypes import wintypes

            self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
            self._kernel32.SetConsoleCtrlHandler.argtypes = (callback_type, wintypes.BOOL)
            self._kernel32.SetConsoleCtrlHandler.restype = wintypes.BOOL
            self._kernel32.GetStdHandle.argtypes = (wintypes.DWORD,)
            self._kernel32.GetStdHandle.restype = wintypes.HANDLE
            self._kernel32.GetConsoleMode.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
            self._kernel32.GetConsoleMode.restype = wintypes.BOOL
            self._kernel32.SetConsoleMode.argtypes = (wintypes.HANDLE, wintypes.DWORD)
            self._kernel32.SetConsoleMode.restype = wintypes.BOOL
            self._configure_input_mode(wintypes)
            self._handler = callback_type(self._handle)
            if not self._kernel32.SetConsoleCtrlHandler(self._handler, True):
                return False
        except (AttributeError, OSError):
            return False
        self.installed = True
        return True

    def uninstall(self) -> None:
        if not self.installed or self._kernel32 is None or self._handler is None:
            return
        self._restore_input_mode()
        self._kernel32.SetConsoleCtrlHandler(self._handler, False)
        self.installed = False

    def _handle(self, ctrl_type: int) -> bool:
        if ctrl_type not in (self._CTRL_C_EVENT, self._CTRL_BREAK_EVENT):
            return False
        self._stop_controller.request_signal_stop()
        return True

    def _configure_input_mode(self, wintypes) -> None:  # noqa: ANN001
        if self._kernel32 is None:
            return
        handle = self._kernel32.GetStdHandle(self._STD_INPUT_HANDLE)
        if not handle:
            return
        mode = wintypes.DWORD()
        if not self._kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return
        self._stdin_handle = handle
        self._previous_input_mode = int(mode.value)
        desired_mode = int(mode.value) | self._ENABLE_PROCESSED_INPUT
        if self._kernel32.SetConsoleMode(handle, desired_mode):
            self.input_mode_configured = True

    def _restore_input_mode(self) -> None:
        if (
            self._kernel32 is None
            or self._stdin_handle is None
            or self._previous_input_mode is None
            or not self.input_mode_configured
        ):
            return
        self._kernel32.SetConsoleMode(self._stdin_handle, self._previous_input_mode)
        self.input_mode_configured = False


class WindowsKeyboardStopPoller:
    def __init__(self):
        self._msvcrt = None
        if sys.platform == "win32":
            try:
                import msvcrt

                self._msvcrt = msvcrt
            except ImportError:
                self._msvcrt = None

    def poll_stop_requested(self) -> bool:
        if self._msvcrt is None:
            return False
        requested = False
        while self._msvcrt.kbhit():
            ch = self._msvcrt.getwch()
            if ch in ("\x00", "\xe0"):
                if self._msvcrt.kbhit():
                    self._msvcrt.getwch()
                continue
            if ch in ("\x03", "q", "Q"):
                requested = True
        return requested


def parse_on_off(value: str) -> bool:
    lower = str(value).strip().lower()
    if lower == "on":
        return True
    if lower == "off":
        return False
    raise argparse.ArgumentTypeError("value must be 'on' or 'off'")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="keysight-logger")
    sub = parser.add_subparsers(dest="command", required=True)

    list_resources = sub.add_parser("list-resources")
    list_resources.add_argument(
        "--verify",
        action="store_true",
        help="open each resource and query *IDN? to mark live vs stale",
    )

    start = sub.add_parser("start-trigger-record")
    start.add_argument("--resource", required=True, help="VISA resource string")
    start.add_argument("--csv", required=True, help="CSV output path")
    start.add_argument("--timeout-ms", type=int, default=5000)
    start.add_argument("--trigger-timeout-ms", type=int, default=10000)
    start.add_argument("--sw-trigger-port", type=int, default=8765)
    start.add_argument("--sw-min-interval-ms", type=int, default=0)
    start.add_argument("--sw-queue-max", type=int, default=0)
    start.add_argument(
        "--trigger-mode",
        choices=["software", "external", "immediate", "immediate-custom", "software-custom"],
        default=None,
        help="single acquisition trigger mode; default: software",
    )
    start.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="stop automatically after successfully recording N samples",
    )
    start.add_argument(
        "--trigger-count",
        type=int,
        default=None,
        help="instrument trigger count; required with custom trigger modes",
    )
    start.add_argument(
        "--sample-count",
        type=int,
        default=None,
        help="instrument sample count per trigger; required with custom trigger modes",
    )
    start.add_argument(
        "--timer-interval-s",
        type=float,
        default=None,
        help="software timer interval in seconds; valid only with software trigger mode",
    )
    start.add_argument(
        "--buffer-drain-size",
        type=int,
        default=None,
        help="maximum readings to remove per buffer drain; valid only with custom modes",
    )
    start.add_argument(
        "--allow-buffer-overflow-risk",
        action="store_true",
        help="allow custom modes to request more readings than 34461A reading memory",
    )
    start.add_argument("--enable-hw-trigger", action="store_true")
    start.add_argument(
        "--hw-trigger-slope",
        choices=["pos", "neg"],
        default="neg",
        help="hardware trigger edge polarity (default: neg)",
    )
    start.add_argument("--hw-trigger-delay-s", type=float, default=0.0)
    start.add_argument("--nplc", type=float, default=1.0)
    start.add_argument("--auto-zero", type=parse_on_off, default=True)
    start.add_argument("--auto-range", type=parse_on_off, default=True)
    start.add_argument("--current-range", type=float, default=None)
    start.add_argument(
        "--vm-comp-slope",
        choices=["pos", "neg"],
        default=None,
        help="VM Comp rear-panel output pulse slope; omit to leave unchanged",
    )

    trig = sub.add_parser("soft-trigger")
    trig.add_argument("--port", type=int, default=8765)
    trig.add_argument("--meta", default="{}", help='JSON metadata, e.g. {"batch":"A"}')
    stop = sub.add_parser("soft-stop")
    stop.add_argument("--port", type=int, default=8765)

    return parser


def cmd_list_resources(verify: bool = False, print_fn=print) -> int:  # noqa: ANN001
    for resource in VisaInstrument.list_resources():
        if not verify:
            print_fn(resource)
            continue
        ok, detail = VisaInstrument.verify_resource(resource)
        status = "live" if ok else "stale"
        print_fn(f"{status}\t{resource}\t{detail}")
    return 0


def cmd_soft_trigger(port: int, meta: str) -> int:
    try:
        payload = json.dumps(json.loads(meta)).encode("utf-8")
    except json.JSONDecodeError:
        print("meta must be valid JSON", file=sys.stderr)
        return 2
    req = request.Request(
        f"http://127.0.0.1:{port}/trigger",
        method="POST",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=3) as response:
            print(f"trigger accepted: {response.status}")
    except URLError as exc:
        print(f"trigger request failed: {exc}", file=sys.stderr)
        return 3
    return 0


def cmd_soft_stop(port: int) -> int:
    req = request.Request(
        f"http://127.0.0.1:{port}/stop",
        method="POST",
        data=b"{}",
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=3) as response:
            print(f"stop accepted: {response.status}")
    except URLError as exc:
        reason = getattr(exc, "reason", None)
        winerror = getattr(reason, "winerror", None)
        errno = getattr(reason, "errno", None)
        if winerror == 10061 or errno == 10061:
            print("already stopped (endpoint not listening)")
            return 0
        print(f"stop request failed: {exc}", file=sys.stderr)
        return 3
    return 0


def resolve_trigger_mode(args: argparse.Namespace) -> str:
    trigger_mode = args.trigger_mode or "software"
    if args.enable_hw_trigger:
        if args.trigger_mode is not None and args.trigger_mode != "external":
            raise ValueError("--enable-hw-trigger conflicts with --trigger-mode; use external")
        trigger_mode = "external"
    return trigger_mode


def validate_start_args(args: argparse.Namespace, trigger_mode: str) -> None:
    custom_mode = trigger_mode.endswith("-custom")
    if args.current_range is not None and args.current_range <= 0:
        raise ValueError("--current-range must be > 0")
    if args.nplc <= 0:
        raise ValueError("--nplc must be > 0")
    if args.hw_trigger_delay_s < 0:
        raise ValueError("--hw-trigger-delay-s must be >= 0")
    if not args.auto_range and args.current_range is None:
        raise ValueError("--current-range is required when --auto-range off")
    if args.sw_min_interval_ms < 0:
        raise ValueError("--sw-min-interval-ms must be >= 0")
    if args.sw_queue_max < 0:
        raise ValueError("--sw-queue-max must be >= 0")
    if args.max_samples is not None and args.max_samples <= 0:
        raise ValueError("--max-samples must be > 0")
    if args.trigger_count is not None and args.trigger_count <= 0:
        raise ValueError("--trigger-count must be > 0")
    if args.sample_count is not None and args.sample_count <= 0:
        raise ValueError("--sample-count must be > 0")
    if args.timer_interval_s is not None:
        if args.timer_interval_s <= 0:
            raise ValueError("--timer-interval-s must be > 0")
        if trigger_mode != "software":
            raise ValueError("--timer-interval-s requires --trigger-mode software")
    if args.buffer_drain_size is not None:
        if args.buffer_drain_size <= 0:
            raise ValueError("--buffer-drain-size must be > 0")
        memory_limit = KEYSIGHT_34461A_CAPABILITIES.reading_memory_limit
        if args.buffer_drain_size > memory_limit:
            raise ValueError(f"--buffer-drain-size must be <= {memory_limit}")
        if not custom_mode:
            raise ValueError("--buffer-drain-size requires a custom trigger mode")
    if args.allow_buffer_overflow_risk and not custom_mode:
        raise ValueError("--allow-buffer-overflow-risk requires a custom trigger mode")
    if custom_mode:
        if args.max_samples is not None:
            raise ValueError("--max-samples cannot be used with custom trigger modes")
        if args.trigger_count is None:
            raise ValueError("--trigger-count is required with custom trigger modes")
        if args.sample_count is None:
            raise ValueError("--sample-count is required with custom trigger modes")
        memory_limit = KEYSIGHT_34461A_CAPABILITIES.reading_memory_limit
        expected_readings = args.trigger_count * args.sample_count
        if expected_readings > memory_limit and not args.allow_buffer_overflow_risk:
            raise ValueError(
                "custom mode expected readings exceed "
                f"{memory_limit}; use --allow-buffer-overflow-risk to proceed"
            )
    else:
        if args.trigger_count is not None:
            raise ValueError("--trigger-count requires a custom trigger mode")
        if args.sample_count is not None:
            raise ValueError("--sample-count requires a custom trigger mode")


def print_buffer_overflow_warnings(args: argparse.Namespace, trigger_mode: str) -> None:
    if not trigger_mode.endswith("-custom") or not args.allow_buffer_overflow_risk:
        return
    if args.trigger_count is None or args.sample_count is None:
        return
    memory_limit = KEYSIGHT_34461A_CAPABILITIES.reading_memory_limit
    expected_readings = args.trigger_count * args.sample_count
    if expected_readings <= memory_limit:
        return
    print("WARNING: requested readings exceed 34461A reading memory.")
    print(f"WARNING: requested={expected_readings}, memory_limit={memory_limit}.")
    print("WARNING: this depends on DATA:REMove? draining faster than acquisition fills memory.")
    print("WARNING: data loss, incomplete rows, or SCPI errors are possible.")
    print("WARNING: validate with low counts first and inspect row count/errors.")


def cmd_start(args: argparse.Namespace) -> int:
    try:
        trigger_mode = resolve_trigger_mode(args)
        validate_start_args(args, trigger_mode)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print_buffer_overflow_warnings(args, trigger_mode)

    iconfig = InstrumentConfig(resource_string=args.resource, timeout_ms=args.timeout_ms)
    aconfig = AcquisitionConfig(
        trigger_timeout_ms=args.trigger_timeout_ms,
        max_samples=args.max_samples,
        trigger_count=args.trigger_count,
        sample_count=args.sample_count,
        timer_interval_s=args.timer_interval_s,
        buffer_drain_size=args.buffer_drain_size,
        allow_buffer_overflow_risk=args.allow_buffer_overflow_risk,
        nplc=args.nplc,
        auto_zero=args.auto_zero,
        auto_range=args.auto_range,
        current_range=args.current_range,
        hw_trigger_delay_s=args.hw_trigger_delay_s,
        vm_comp_slope=args.vm_comp_slope,
    )
    instrument = VisaInstrument(iconfig)
    router = TriggerRouter()
    storage = CsvWriter(Path(args.csv))
    measurement = CurrentMeasurement()
    engine = TriggerAcquisitionEngine(
        instrument=instrument,
        measurement=measurement,
        storage=storage,
        config=aconfig,
        router=router,
        status_cb=lambda m: print(f"[status] {m}"),
    )

    stop_controller = StopController(engine.stop)

    server = SoftwareTriggerAdapter(
        router,
        port=args.sw_trigger_port,
        min_interval_ms=args.sw_min_interval_ms,
        queue_max=args.sw_queue_max,
        stop_cb=stop_controller.request_http_stop,
    )

    def handle_stop_signal(signum, frame):  # noqa: ARG001
        stop_controller.request_signal_stop()

    previous_signal_handlers = []
    previous_signal_handlers.append((signal.SIGINT, signal.signal(signal.SIGINT, handle_stop_signal)))
    if hasattr(signal, "SIGTERM"):
        previous_signal_handlers.append(
            (signal.SIGTERM, signal.signal(signal.SIGTERM, handle_stop_signal))
        )
    if hasattr(signal, "SIGBREAK"):
        previous_signal_handlers.append(
            (signal.SIGBREAK, signal.signal(signal.SIGBREAK, handle_stop_signal))
        )
    windows_console_stop_handler = WindowsConsoleStopHandler(stop_controller)
    keyboard_stop_poller = WindowsKeyboardStopPoller()

    worker: threading.Thread | None = None
    try:
        instrument.connect()
        if windows_console_stop_handler.install():
            print(
                "windows console stop handler: installed "
                f"processed_input={windows_console_stop_handler.input_mode_configured}"
            )
        elif sys.platform == "win32":
            print("windows console stop handler: unavailable", file=sys.stderr)
        host, port = server.start()
        print(f"software trigger endpoint: http://{host}:{port}/trigger")
        print(f"software stop endpoint: http://{host}:{port}/stop")
        print("local stop keys: Ctrl+C, Ctrl+Break, q")
        worker = threading.Thread(
            target=engine.run,
            kwargs={
                "trigger_mode": trigger_mode,
                "hardware_trigger_slope": args.hw_trigger_slope,
            },
            daemon=True,
        )
        worker.start()
        try:
            while worker.is_alive() and not stop_controller.stop:
                if keyboard_stop_poller.poll_stop_requested():
                    stop_controller.request_signal_stop()
                    break
                time.sleep(0.2)
            if not worker.is_alive() and not stop_controller.stop:
                print("measurement worker exited before stop was requested")
        except KeyboardInterrupt:
            stop_controller.request_signal_stop()
            while worker.is_alive():
                try:
                    worker.join(timeout=0.2)
                    if not worker.is_alive():
                        break
                except KeyboardInterrupt:
                    stop_controller.request_signal_stop()
                    break
        finally:
            print("main cleanup starting")
            engine.stop()
            if worker.is_alive():
                join_timeout_s = max(args.trigger_timeout_ms / 1000.0 + 1.0, 2.0)
                print(f"waiting for measurement worker to stop, timeout_s={join_timeout_s:.1f}")
                worker.join(timeout=join_timeout_s)
            if worker.is_alive() or stop_controller.force:
                print(f"release_to_local before close: {instrument.release_to_local()}")
                instrument.close()
                worker.join(timeout=2)
        print(f"captured={engine.stats.captured} errors={engine.stats.errors}")
        return 0
    finally:
        print("final cleanup starting")
        # Ensure worker exits before final release/close.
        if worker is not None and worker.is_alive():
            print("waiting worker to fully stop...")
            worker.join(timeout=5)

        # Release instrument control before closing the session.
        rel = instrument.release_to_local()
        print(f"release_to_local: {rel}")
        # Retry once on transient session instability.
        if "SYST:LOC:failed" in rel:
            time.sleep(1.0)
            rel2 = instrument.release_to_local()
            print(f"release_to_local retry: {rel2}")
        instrument.close()
        print(f"cleanup_release_to_local: {instrument.cleanup_release_to_local()}")
        print("stopping software trigger server")
        server.stop()
        print("software trigger server stopped")
        windows_console_stop_handler.uninstall()
        for sig, previous_handler in previous_signal_handlers:
            signal.signal(sig, previous_handler)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "list-resources":
        return cmd_list_resources(verify=args.verify)
    if args.command == "soft-trigger":
        return cmd_soft_trigger(args.port, args.meta)
    if args.command == "soft-stop":
        return cmd_soft_stop(args.port)
    if args.command == "start-trigger-record":
        return cmd_start(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
