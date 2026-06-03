from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Empty, Queue
from typing import Callable, Optional, Tuple

from .instrument import VisaInstrument
from .models import TriggerEvent, TriggerSource


class TriggerRouter:
    def __init__(self) -> None:
        self._queue: Queue[TriggerEvent] = Queue()

    def publish(self, event: TriggerEvent) -> None:
        self._queue.put(event)

    def wait(self, timeout_s: float) -> Optional[TriggerEvent]:
        try:
            return self._queue.get(timeout=timeout_s)
        except Empty:
            return None

    def size(self) -> int:
        return self._queue.qsize()


class HardwareTriggerAdapter:
    def __init__(self, instrument: VisaInstrument) -> None:
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

        while True:
            if stop_event is not None and stop_event.is_set():
                return None
            remaining_s = deadline - time.monotonic()
            if remaining_s <= 0:
                raise TimeoutError("hardware trigger wait timed out")
            wait_s = min(poll_s, remaining_s)
            if stop_event is not None and stop_event.wait(wait_s):
                return None
            if self._instrument.read_status_byte() & 0x20:
                return TriggerEvent.new(TriggerSource.HARDWARE)

class SoftwareTriggerAdapter:
    def __init__(
        self,
        router: TriggerRouter,
        host: str = "127.0.0.1",
        port: int = 8765,
        min_interval_ms: int = 0,
        queue_max: int = 0,
        stop_cb: Optional[Callable[[], None]] = None,
    ) -> None:
        self._router = router
        self._host = host
        self._port = port
        self._min_interval_ms = max(0, int(min_interval_ms))
        self._queue_max = max(0, int(queue_max))
        self._stop_cb = stop_cb
        self._last_accepted_monotonic = 0.0
        self._guard = threading.Lock()
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> Tuple[str, int]:
        router = self._router

        class Handler(BaseHTTPRequestHandler):
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
                router.publish(TriggerEvent.new(TriggerSource.SOFTWARE, metadata=metadata))
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

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
