from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Empty, Full, Queue
from typing import Callable, Optional, Tuple

from .instrument import is_pyvisa_timeout_error
from .instrument_backend import InstrumentBackend
from .models import TriggerEvent, TriggerSource


class TriggerRouter:
    DEFAULT_MAX_PENDING_EVENTS = 10000

    def __init__(self, max_pending_events: int = DEFAULT_MAX_PENDING_EVENTS) -> None:
        maxsize = (
            self.DEFAULT_MAX_PENDING_EVENTS
            if int(max_pending_events) <= 0
            else int(max_pending_events)
        )
        self._queue: Queue[TriggerEvent] = Queue(maxsize=maxsize)
        self._control_queue: Queue[TriggerEvent] = Queue()

    def publish(self, event: TriggerEvent) -> bool:
        if self._is_control_event(event):
            self._control_queue.put(event)
            return True
        try:
            self._queue.put_nowait(event)
            return True
        except Full:
            return False

    def wait(self, timeout_s: float) -> Optional[TriggerEvent]:
        try:
            return self._control_queue.get_nowait()
        except Empty:
            pass
        try:
            return self._queue.get(timeout=timeout_s)
        except Empty:
            return None

    def size(self) -> int:
        return self._queue.qsize()

    def max_size(self) -> int:
        return self._queue.maxsize

    def _is_control_event(self, event: TriggerEvent) -> bool:
        return bool(event.metadata.get("control"))


class HardwareTriggerAdapter:
    def __init__(self, instrument: InstrumentBackend) -> None:
        self._instrument = instrument

    def configure_external_trigger(self, slope: str = "NEG", delay_s: float = 0.0) -> None:
        slope_cmd = "POS" if str(slope).upper() == "POS" else "NEG"
        self._instrument.write("TRIG:SOUR EXT")
        self._instrument.write(f"TRIG:SLOP {slope_cmd}")
        self._instrument.write("TRIG:COUNT 1")
        self._instrument.write("SAMP:COUNT 1")
        self._instrument.write(f"TRIG:DEL {max(0.0, float(delay_s))}")

    def wait_and_read_triggered(
        self,
        timeout_ms: int,
        stop_event: Optional[threading.Event] = None,
        poll_interval_ms: int = 200,
        status_poll_timeout_cb: Optional[Callable[[int, Exception], None]] = None,
    ) -> Optional[TriggerEvent]:
        # Arm once, then poll the status byte so shutdown can interrupt the wait.
        timeout_s = max(0, timeout_ms) / 1000.0
        poll_s = max(0.05, poll_interval_ms / 1000.0)
        deadline = time.monotonic() + timeout_s
        self._instrument.set_timeout_ms(max(100, min(timeout_ms, poll_interval_ms)))
        self._instrument.write("*CLS")
        self._instrument.write("*ESE 1")
        self._instrument.write("INIT")
        self._instrument.write("*OPC")
        consecutive_status_timeouts = 0

        while True:
            if stop_event is not None and stop_event.is_set():
                return None
            remaining_s = deadline - time.monotonic()
            if remaining_s <= 0:
                raise TimeoutError("hardware trigger wait timed out")
            wait_s = min(poll_s, remaining_s)
            if stop_event is not None and stop_event.wait(wait_s):
                return None
            try:
                status_byte = self._instrument.read_status_byte()
            except Exception as exc:
                if not is_pyvisa_timeout_error(exc):
                    raise
                consecutive_status_timeouts += 1
                if status_poll_timeout_cb is not None:
                    status_poll_timeout_cb(consecutive_status_timeouts, exc)
                continue
            consecutive_status_timeouts = 0
            if status_byte & 0x20:
                return TriggerEvent.new(TriggerSource.HARDWARE)
        # Unreachable, loop exits via timeout/stop/trigger.

    def recover_from_timeout(self) -> None:
        # Best effort reset after external-trigger wait timeout to avoid
        # accumulating instrument-side trigger/remote command errors.
        try:
            self._instrument.abort_measurement()
        except Exception:
            try:
                self._instrument.write("ABOR")
            except Exception:
                pass
        try:
            self._instrument.write("*CLS")
        except Exception:
            pass


class SoftwareTriggerAdapter:
    def __init__(
        self,
        router: TriggerRouter,
        host: str = "127.0.0.1",
        port: int = 8765,
        min_interval_ms: int = 0,
        queue_max: int = 0,
        stop_cb: Optional[Callable[[], None]] = None,
        status_provider: Optional[Callable[[], dict[str, object]]] = None,
    ) -> None:
        self._router = router
        self._host = host
        self._port = port
        self._min_interval_ms = max(0, int(min_interval_ms))
        self._queue_max = max(0, int(queue_max))
        self._stop_cb = stop_cb
        self._status_provider = status_provider
        self._last_accepted_monotonic = 0.0
        self._guard = threading.Lock()
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> Tuple[str, int]:
        router = self._router

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # type: ignore[override]
                if self.path != "/status":
                    self.send_response(404)
                    self.end_headers()
                    return
                payload = self.server.adapter._status_payload()  # type: ignore[attr-defined]
                body = json.dumps(payload, sort_keys=True).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):  # type: ignore[override]
                if self.path == "/stop":
                    router.publish(
                        TriggerEvent.new(
                            TriggerSource.SOFTWARE,
                            metadata={"control": "stop"},
                        )
                    )
                    self.send_response(202)
                    self.end_headers()
                    stop_cb = self.server.adapter._stop_cb  # type: ignore[attr-defined]
                    if stop_cb is not None:
                        threading.Thread(target=stop_cb, daemon=True).start()
                    return
                if self.path != "/trigger":
                    self.send_response(404)
                    self.end_headers()
                    return
                content_len = int(self.headers.get("Content-Length", "0"))
                payload = self.rfile.read(content_len).decode("utf-8") if content_len else "{}"
                metadata = {}
                try:
                    body = json.loads(payload)
                    if isinstance(body, dict):
                        metadata = {str(k): str(v) for k, v in body.items()}
                except json.JSONDecodeError:
                    metadata = {}
                accepted, reason = self.server.adapter._try_accept_trigger()  # type: ignore[attr-defined]
                if not accepted:
                    self.send_response(429)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "rejected", "reason": reason}).encode("utf-8"))
                    return
                if not router.publish(TriggerEvent.new(TriggerSource.SOFTWARE, metadata=metadata)):
                    self.send_response(429)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "rejected", "reason": "queue_full"}).encode("utf-8"))
                    return
                self.send_response(202)
                self.end_headers()

            def log_message(self, format, *args):  # noqa: A003
                return

        self._server = ThreadingHTTPServer((self._host, self._port), Handler)
        self._server.adapter = self  # type: ignore[attr-defined]
        self._port = int(self._server.server_address[1])
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self._host, self._port

    def _try_accept_trigger(self) -> tuple[bool, str]:
        with self._guard:
            if self._queue_max > 0 and self._router.size() >= self._queue_max:
                return False, "queue_full"
            if self._min_interval_ms > 0:
                now = time.monotonic()
                elapsed_ms = (now - self._last_accepted_monotonic) * 1000.0
                if self._last_accepted_monotonic > 0 and elapsed_ms < self._min_interval_ms:
                    return False, "rate_limited"
                self._last_accepted_monotonic = now
            return True, ""

    def _status_payload(self) -> dict[str, object]:
        dynamic: dict[str, object] = {}
        if self._status_provider is not None:
            try:
                provided = self._status_provider()
                if isinstance(provided, dict):
                    dynamic = provided
            except Exception:
                dynamic = {}
        status = str(dynamic.get("status") or "running")
        if status not in {"running", "stopping"}:
            status = "running"
        base_url = f"http://{self._host}:{self._port}"
        return {
            "schema_version": 1,
            "service": "keysight-meter",
            "status": status,
            "trigger_url": f"{base_url}/trigger",
            "stop_url": f"{base_url}/stop",
            "status_url": f"{base_url}/status",
            "queue_size": self._router.size(),
            "queue_max": self._queue_max if self._queue_max > 0 else self._router.max_size(),
            "min_interval_ms": self._min_interval_ms,
            "captured": dynamic.get("captured"),
            "errors": dynamic.get("errors"),
            "fatal_error": dynamic.get("fatal_error"),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
