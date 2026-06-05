from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import Any, Callable, Literal, Protocol
from uuid import uuid4


StartRunEventType = Literal["message", "status", "sample", "ready", "error", "summary"]


def new_run_id() -> str:
    return str(uuid4())


@dataclass(frozen=True)
class StartRunEvent:
    event: StartRunEventType
    run_id: str | None = None
    message: str | None = None
    sample: Any | None = None
    captured: int | None = None
    errors: int | None = None
    fatal_error: str | None = None
    host: str | None = None
    port: int | None = None
    trigger_url: str | None = None
    stop_url: str | None = None
    status_url: str | None = None
    fields: dict[str, object] = field(default_factory=dict)

    @staticmethod
    def message_event(run_id: str, message: str) -> "StartRunEvent":
        return StartRunEvent(event="message", run_id=run_id, message=message)

    @staticmethod
    def status_event(run_id: str, message: str, **fields: object) -> "StartRunEvent":
        return StartRunEvent(event="status", run_id=run_id, message=message, fields=fields)

    @staticmethod
    def sample_event(run_id: str, sample: Any, captured: int) -> "StartRunEvent":
        return StartRunEvent(event="sample", run_id=run_id, sample=sample, captured=captured)

    @staticmethod
    def ready_event(run_id: str, handle: "StartControlPlaneHandle") -> "StartRunEvent":
        return StartRunEvent(
            event="ready",
            run_id=run_id,
            host=handle.host,
            port=handle.port,
            trigger_url=handle.trigger_url,
            stop_url=handle.stop_url,
            status_url=handle.status_url,
        )

    @staticmethod
    def error_event(run_id: str, message: str) -> "StartRunEvent":
        return StartRunEvent(event="error", run_id=run_id, message=message)

    @staticmethod
    def summary_event(
        run_id: str,
        captured: int,
        errors: int,
        fatal_error: str | None = None,
    ) -> "StartRunEvent":
        return StartRunEvent(
            event="summary",
            run_id=run_id,
            captured=captured,
            errors=errors,
            fatal_error=fatal_error,
        )


class StartRunEventSink(Protocol):
    def emit(self, event: StartRunEvent) -> None: ...


class NullStartRunEventSink:
    def emit(self, event: StartRunEvent) -> None:  # noqa: ARG002
        return None


@dataclass(frozen=True)
class StartControlPlaneHandle:
    host: str | None = None
    port: int | None = None
    trigger_url: str | None = None
    stop_url: str | None = None
    status_url: str | None = None
    _stop_fn: Callable[[], None] = field(default=lambda: None, repr=False, compare=False)

    @property
    def active(self) -> bool:
        return self.host is not None and self.port is not None

    def stop(self) -> None:
        self._stop_fn()


class StartControlPlane(Protocol):
    def start(
        self,
        *,
        router: Any,
        port: int,
        min_interval_ms: int,
        queue_max: int,
        stop_cb: Callable[[], None],
        status_provider: Callable[[], dict[str, object]],
    ) -> StartControlPlaneHandle: ...


class NoOpControlPlane:
    def start(
        self,
        *,
        router: Any,  # noqa: ARG002
        port: int,  # noqa: ARG002
        min_interval_ms: int,  # noqa: ARG002
        queue_max: int,  # noqa: ARG002
        stop_cb: Callable[[], None],  # noqa: ARG002
        status_provider: Callable[[], dict[str, object]],  # noqa: ARG002
    ) -> StartControlPlaneHandle:
        return StartControlPlaneHandle()


class SoftwareTriggerControlPlane:
    def __init__(self, server_factory: Callable[..., Any]) -> None:
        self._server_factory = server_factory

    def start(
        self,
        *,
        router: Any,
        port: int,
        min_interval_ms: int,
        queue_max: int,
        stop_cb: Callable[[], None],
        status_provider: Callable[[], dict[str, object]],
    ) -> StartControlPlaneHandle:
        server = self._server_factory(
            router,
            port=port,
            min_interval_ms=min_interval_ms,
            queue_max=queue_max,
            stop_cb=stop_cb,
            status_provider=status_provider,
        )
        host, actual_port = server.start()
        base_url = f"http://{host}:{actual_port}"
        return StartControlPlaneHandle(
            host=host,
            port=actual_port,
            trigger_url=f"{base_url}/trigger",
            stop_url=f"{base_url}/stop",
            status_url=f"{base_url}/status",
            _stop_fn=server.stop,
        )


class StartRunControls(Protocol):
    def install(self, stop_controller: "StopController") -> None: ...

    def after_connect(self, event_sink: StartRunEventSink, run_id: str) -> None: ...

    def poll_stop_requested(self) -> bool: ...

    def uninstall(self) -> None: ...


class NoOpStartRunControls:
    def install(self, stop_controller: "StopController") -> None:  # noqa: ARG002
        return None

    def after_connect(self, event_sink: StartRunEventSink, run_id: str) -> None:  # noqa: ARG002
        return None

    def poll_stop_requested(self) -> bool:
        return False

    def uninstall(self) -> None:
        return None


class StopController:
    def __init__(self, stop_engine: Callable[[], None]):
        self.stop = False
        self.interrupt_count = 0
        self.force = False
        self._stop_engine = stop_engine
        self._lock = threading.Lock()
        self._messages: list[str] = []

    def request_stop(self, force: bool = False) -> None:
        with self._lock:
            self.stop = True
            if force:
                self.force = True
                message = "second interrupt received, forcing shutdown..."
            else:
                message = "interrupt received, stopping gracefully (press Ctrl+C again to force)..."
            self._messages.append(message)
        self._stop_engine()

    def request_http_stop(self) -> None:
        with self._lock:
            self.stop = True
        self._stop_engine()

    def request_signal_stop(self) -> None:
        with self._lock:
            self.interrupt_count += 1
            force = self.interrupt_count >= 2
        self.request_stop(force=force)

    def pop_messages(self) -> list[str]:
        with self._lock:
            messages = list(self._messages)
            self._messages.clear()
            return messages


@dataclass(frozen=True)
class StartRunResult:
    run_id: str
    ok: bool
    reason: str
    captured: int
    errors: int
    fatal_error: str | None
    csv_path: Any
    control: StartControlPlaneHandle | None = None
