from __future__ import annotations

import json
import threading
import time
from uuid import uuid4
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Empty, Full, Queue
from typing import Callable, Optional, Tuple, cast

from .command import (
    COMMAND_SCHEMA_VERSION,
    CommandValidationError,
    command_response,
    common_error,
    parse_stop_request_json,
    parse_command_envelope_json,
)
from .instrument import is_pyvisa_timeout_error
from .instrument_backend import InstrumentBackend
from .models import TriggerEvent, TriggerSource
from .trigger_plan import external_trigger_setup_commands


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
        control = self.poll_control()
        if control is not None:
            return control
        try:
            return self._queue.get(timeout=timeout_s)
        except Empty:
            return None

    def poll_control(self) -> Optional[TriggerEvent]:
        try:
            return self._control_queue.get_nowait()
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
        for command in external_trigger_setup_commands(slope=slope, delay_s=delay_s):
            self._instrument.write(command)

    def wait_and_read_triggered(
        self,
        timeout_ms: int,
        stop_event: Optional[threading.Event] = None,
        poll_interval_ms: int = 200,
        status_poll_timeout_cb: Optional[Callable[[int, Exception], None]] = None,
        readiness_cb: Optional[Callable[[], None]] = None,
    ) -> Optional[TriggerEvent]:
        # Arm once, then poll the status byte so shutdown can interrupt the wait.
        timeout_s = max(0, timeout_ms) / 1000.0
        poll_s = max(0.05, poll_interval_ms / 1000.0)
        deadline = time.monotonic() + timeout_s
        io_timeout_ms = max(100, min(timeout_ms, poll_interval_ms))
        self._instrument.set_timeout_ms(io_timeout_ms)
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
            if readiness_cb is not None and deadline - time.monotonic() >= io_timeout_ms / 1000.0:
                readiness_cb()
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


class _SoftwareTriggerHttpServer(ThreadingHTTPServer):
    adapter: SoftwareTriggerAdapter


class _SoftwareTriggerRequestHandler(BaseHTTPRequestHandler):
    def _adapter(self) -> SoftwareTriggerAdapter:
        return cast(_SoftwareTriggerHttpServer, self.server).adapter

    def _send_json(
        self,
        status_code: int,
        payload: dict[str, object],
        *,
        sort_keys: bool = False,
    ) -> None:
        body = json.dumps(
            payload,
            separators=None if sort_keys else (",", ":"),
            sort_keys=sort_keys,
        ).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # type: ignore[override]
        if self.path != "/status":
            self.send_response(404)
            self.end_headers()
            return
        adapter = self._adapter()
        try:
            payload = adapter._status_payload()
        except Exception as exc:
            self._send_json(500, adapter._status_error_payload(exc))
            return
        self._send_json(200, payload, sort_keys=True)

    def do_POST(self):  # type: ignore[override]
        adapter = self._adapter()
        if self.path not in {"/command", "/stop"}:
            self.send_response(404)
            self.end_headers()
            return
        try:
            content_len = int(self.headers.get("Content-Length", "0"))
            if content_len < 0:
                raise ValueError("invalid request body length")
            request_body = self.rfile.read(content_len) if content_len else b""
            payload = request_body.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            error = common_error("validation", "invalid_request", str(exc))
            if self.path == "/stop":
                self._send_json(400, adapter._stop_response("error", error=error))
            else:
                self._send_json(400, command_response(
                    "error", run_id=adapter._run_id, command=None, job_id=None, error=error,
                ))
            return
        if self.path == "/stop":
            try:
                parse_stop_request_json(payload)
            except CommandValidationError as exc:
                self._send_json(400, adapter._stop_response(
                    "error", error=common_error("validation", "invalid_stop_request", str(exc)),
                ))
                return
            first_stop = adapter._publish_stop()
            try:
                self._send_json(202, adapter._stop_response("accepted"))
            finally:
                if first_stop:
                    adapter._start_stop_callback()
            return
        status_code, response = adapter._handle_command(payload)
        self._send_json(status_code, response)

    def log_message(self, format, *args):  # noqa: A003
        return


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
        run_id: str | None = None,
    ) -> None:
        self._router = router
        self._host = host
        self._port = port
        self._min_interval_ms = max(0, int(min_interval_ms))
        self._queue_max = max(0, int(queue_max))
        self._stop_cb = stop_cb
        self._status_provider = status_provider
        self._run_id = run_id or str(uuid4())
        self._stop_requested = False
        self._stop_guard = threading.Lock()
        self._last_accepted_monotonic = 0.0
        self._guard = threading.Lock()
        self._server: Optional[_SoftwareTriggerHttpServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> Tuple[str, int]:
        self._server = _SoftwareTriggerHttpServer(
            (self._host, self._port),
            _SoftwareTriggerRequestHandler,
        )
        self._server.adapter = self
        self._port = int(self._server.server_address[1])
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self._host, self._port

    def _handle_command(self, payload: str) -> tuple[int, dict[str, object]]:
        try:
            command = parse_command_envelope_json(payload)
        except CommandValidationError as exc:
            return 400, command_response(
                "error", run_id=self._run_id, command=exc.command, job_id=exc.job_id,
                error=common_error("validation", "invalid_command_request", str(exc)),
            )
        accepted, reason = self._try_accept_trigger()
        if not accepted:
            return 429, command_response(
                "rejected", run_id=self._run_id, command="software_trigger",
                job_id=command.job_id, reason=reason,
                error=common_error("admission", reason, reason),
            )
        if not self._router.publish(
            TriggerEvent.new(TriggerSource.SOFTWARE, metadata=command.metadata)
        ):
            return 429, command_response(
                "rejected", run_id=self._run_id, command="software_trigger",
                job_id=command.job_id, reason="queue_full",
                error=common_error("admission", "queue_full", "queue_full"),
            )
        return 202, command_response(
            "accepted", run_id=self._run_id, command="software_trigger",
            job_id=command.job_id,
        )

    def _stop_response(
        self, status: str, *, error: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return {"schema_version": COMMAND_SCHEMA_VERSION,
                "run_id": self._run_id, "status": status, "error": error}

    def _publish_stop(self) -> bool:
        with self._stop_guard:
            if self._stop_requested:
                return False
            self._stop_requested = True
            self._router.publish(
                TriggerEvent.new(TriggerSource.SOFTWARE, metadata={"control": "stop"})
            )
            return True

    def _start_stop_callback(self) -> None:
        if self._stop_cb is not None:
            threading.Thread(target=self._stop_cb, daemon=True).start()

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

    def _status_error_payload(self, exc: Exception) -> dict[str, object]:
        return {
            "schema_version": COMMAND_SCHEMA_VERSION, "run_id": self._run_id,
            "status": "error",
            "error": common_error("worker", "status_failed", str(exc)),
        }

    def _status_payload(self) -> dict[str, object]:
        dynamic: dict[str, object] = {}
        if self._status_provider is not None:
            provided = self._status_provider()
            if not isinstance(provided, dict):
                raise ValueError("status provider returned a non-object")
            dynamic = provided
        if dynamic.get("run_id", self._run_id) != self._run_id:
            raise ValueError("status provider run_id mismatch")
        status = str(dynamic.get("status") or "running")
        if status not in {"running", "stopping"}:
            raise ValueError("invalid worker status")
        if self._stop_requested:
            status = "stopping"
        fatal = dynamic.get("fatal_error")
        if fatal is not None and not isinstance(fatal, str):
            raise ValueError("invalid fatal error")
        worker_state = "failed" if fatal else status
        base_url = f"http://{self._host}:{self._port}"
        streaming = dynamic.get("stream")
        return {
            "schema_version": COMMAND_SCHEMA_VERSION,
            "service": "keysight-meter",
            "run_id": self._run_id,
            **({"stream": streaming} if streaming is not None else {}),
            "features": (
                {"common.streaming": {"contract_version": 1, "lifecycles": ["run_bound"]}}
                if streaming is not None else {}
            ),
            "status": status,
            "worker_state": worker_state,
            "command_url": f"{base_url}/command",
            "stop_url": f"{base_url}/stop",
            "status_url": f"{base_url}/status",
            "queue_size": self._router.size(),
            "queue_max": self._queue_max if self._queue_max > 0 else self._router.max_size(),
            "min_interval_ms": self._min_interval_ms,
            "captured": dynamic.get("captured"),
            "errors": dynamic.get("errors"),
            "fatal_error": (
                common_error("execution", "acquisition_failed", fatal) if fatal else None
            ),
            "trigger_count_infinite": dynamic.get("trigger_count_infinite", False),
            "expected_readings": dynamic.get("expected_readings"),
            "overflow_monitoring": dynamic.get("overflow_monitoring", "off"),
            "overflow_detected": dynamic.get("overflow_detected"),
            "stop_reason": dynamic.get("stop_reason", "unknown"),
            "final_drain_complete": dynamic.get("final_drain_complete"),
            "data_integrity": dynamic.get("data_integrity", "unknown"),
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
