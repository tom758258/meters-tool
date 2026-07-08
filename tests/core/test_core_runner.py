from __future__ import annotations

from types import SimpleNamespace
import unittest

from meters_tool_core.instrument import InstrumentError
from meters_tool_core.models import StartRequest, get_default_instrument_profile
from meters_tool_core.runner import (
    StartRunnerDependencies,
    StopController,
    run_start_session,
)
from meters_tool_core.session import NoOpControlPlane, StartRunEvent


def make_start_request(**overrides) -> StartRequest:  # noqa: ANN003
    values = {
        "resource": "SIM::34461A",
        "csv": "data\\runner.csv",
        "simulate": True,
        "trigger_mode": "immediate",
        "max_samples": 1,
    }
    values.update(overrides)
    return StartRequest(**values)


class RecordingEventSink:
    def __init__(self) -> None:
        self.events: list[StartRunEvent] = []

    def emit(self, event: StartRunEvent) -> None:
        self.events.append(event)

    def by_type(self, event_type: str) -> list[StartRunEvent]:
        return [event for event in self.events if event.event == event_type]


class RecordingControls:
    def __init__(self, operations: list[str]) -> None:
        self._operations = operations

    def install(self, stop_controller: StopController) -> None:
        self._operations.append("controls_install")
        self._stop_controller = stop_controller

    def after_connect(self, _event_sink: RecordingEventSink, _run_id: str) -> None:
        self._operations.append("controls_after_connect")

    def poll_stop_requested(self) -> bool:
        return False

    def uninstall(self) -> None:
        self._operations.append("controls_uninstall")


class RecordingInstrument:
    resource_id = "SIM::34461A"

    def __init__(self, operations: list[str], *, connect_error: bool = False) -> None:
        self._operations = operations
        self._connect_error = connect_error

    def connect(self) -> None:
        self._operations.append("connect")
        if self._connect_error:
            raise InstrumentError("unsupported instrument identity")

    def release_to_local(self) -> str:
        self._operations.append("release_to_local")
        return "release:ok"

    def close(self) -> None:
        self._operations.append("close")

    def cleanup_release_to_local(self) -> str:
        self._operations.append("cleanup_release_to_local")
        return "cleanup:ok"


class RecordingStorage:
    def __init__(self, _path) -> None:  # noqa: ANN001
        return


class RecordingEngine:
    def __init__(
        self,
        *,
        operations: list[str],
        captured: int = 1,
        errors: int = 0,
        fatal_error: str | None = None,
    ) -> None:
        self._operations = operations
        self.stats = SimpleNamespace(captured=0, errors=0)
        self.fatal_error = None
        self._captured = captured
        self._errors = errors
        self._run_fatal_error = fatal_error

    def run(self, *, trigger_mode: str, hardware_trigger_slope: str) -> None:
        self._operations.append(f"engine_run:{trigger_mode}:{hardware_trigger_slope}")
        self.stats.captured = self._captured
        self.stats.errors = self._errors
        self.fatal_error = self._run_fatal_error

    def stop(self) -> None:
        self._operations.append("engine_stop")


class CompletedThread:
    def __init__(self, *, target, kwargs, daemon):  # noqa: ANN001, ARG002
        self._target = target
        self._kwargs = kwargs
        self._alive = False

    def start(self) -> None:
        self._alive = True
        self._target(**self._kwargs)
        self._alive = False

    def is_alive(self) -> bool:
        return self._alive

    def join(self, timeout=None) -> None:  # noqa: ANN001, ARG002
        self._alive = False


class RecordingServer:
    def __init__(self, operations: list[str], *_args, status_provider=None, **_kwargs) -> None:  # noqa: ANN001
        self._operations = operations
        self._status_provider = status_provider

    def start(self) -> tuple[str, int]:
        self._operations.append("server_start")
        assert self._status_provider is not None
        status = self._status_provider()
        self._operations.append(f"status:{status['status']}")
        return "127.0.0.1", 8765

    def stop(self) -> None:
        self._operations.append("server_stop")


class CoreRunnerTests(unittest.TestCase):
    def _dependencies(
        self,
        operations: list[str],
        *,
        connect_error: bool = False,
        fatal_error: str | None = None,
        errors: int = 0,
        expected_visa_library: str | None = None,
    ) -> StartRunnerDependencies:
        def instrument_factory(config, *, simulate, measurement_type):  # noqa: ANN001
            self.assertEqual("SIM::34461A", config.resource_string)
            self.assertEqual(expected_visa_library, config.visa_library)
            self.assertTrue(simulate)
            self.assertEqual("current_dc", measurement_type)
            return RecordingInstrument(operations, connect_error=connect_error)

        def engine_factory(**_kwargs):  # noqa: ANN003
            return RecordingEngine(
                operations=operations,
                errors=errors,
                fatal_error=fatal_error,
            )

        def server_factory(*args, **kwargs):  # noqa: ANN002, ANN003
            return RecordingServer(operations, *args, **kwargs)

        return StartRunnerDependencies(
            instrument_backend_factory=instrument_factory,
            storage_factory=RecordingStorage,
            measurement_factory=lambda _measurement_type: object(),
            engine_factory=engine_factory,
            server_factory=server_factory,
            thread_factory=CompletedThread,
            sleep=lambda _seconds: None,
        )

    def test_run_start_session_delegates_runtime_components_and_cleans_up_success(self):
        operations: list[str] = []
        sink = RecordingEventSink()

        result = run_start_session(
            make_start_request(),
            "immediate",
            get_default_instrument_profile(),
            sink,
            RecordingControls(operations),
            run_id="run-123",
            dependencies=self._dependencies(operations),
        )

        self.assertTrue(result.ok)
        self.assertEqual("completed", result.reason)
        self.assertEqual("run-123", result.run_id)
        summaries = sink.by_type("summary")
        self.assertEqual(1, len(summaries))
        self.assertEqual(
            (1, 0, None),
            (summaries[0].captured, summaries[0].errors, summaries[0].fatal_error),
        )
        ready_events = sink.by_type("ready")
        self.assertEqual(1, len(ready_events))
        self.assertEqual(("127.0.0.1", 8765), (ready_events[0].host, ready_events[0].port))
        self.assertIn("engine_run:immediate:neg", operations)
        cleanup_order = [
            "release_to_local",
            "close",
            "cleanup_release_to_local",
            "server_stop",
            "controls_uninstall",
        ]
        positions = [operations.index(step) for step in cleanup_order]
        self.assertEqual(sorted(positions), positions)

    def test_run_start_session_threads_visa_library_to_instrument_config(self):
        operations: list[str] = []
        sink = RecordingEventSink()

        result = run_start_session(
            make_start_request(visa_library="@py"),
            "immediate",
            get_default_instrument_profile(),
            sink,
            RecordingControls(operations),
            run_id="run-123",
            dependencies=self._dependencies(operations, expected_visa_library="@py"),
        )

        self.assertTrue(result.ok)

    def test_run_start_session_connect_error_skips_instrument_cleanup(self):
        operations: list[str] = []
        sink = RecordingEventSink()

        result = run_start_session(
            make_start_request(),
            "immediate",
            get_default_instrument_profile(),
            sink,
            RecordingControls(operations),
            run_id="run-123",
            dependencies=self._dependencies(operations, connect_error=True),
        )

        self.assertFalse(result.ok)
        self.assertEqual("connect_error", result.reason)
        self.assertEqual(
            ["error: unsupported instrument identity"],
            [event.message for event in sink.by_type("error")],
        )
        self.assertNotIn("release_to_local", operations)
        self.assertNotIn("close", operations)
        self.assertNotIn("cleanup_release_to_local", operations)
        self.assertNotIn("server_stop", operations)

    def test_run_start_session_fatal_error_returns_error_summary(self):
        operations: list[str] = []
        sink = RecordingEventSink()

        result = run_start_session(
            make_start_request(),
            "immediate",
            get_default_instrument_profile(),
            sink,
            RecordingControls(operations),
            run_id="run-123",
            dependencies=self._dependencies(operations, fatal_error="simulated read failure", errors=1),
        )

        self.assertFalse(result.ok)
        self.assertEqual("fatal_error", result.reason)
        self.assertEqual(
            ["error: simulated read failure"],
            [event.message for event in sink.by_type("error")],
        )
        summaries = sink.by_type("summary")
        self.assertEqual(1, len(summaries))
        self.assertEqual(
            (1, 1, "simulated read failure"),
            (summaries[0].captured, summaries[0].errors, summaries[0].fatal_error),
        )

    def test_run_start_session_can_disable_control_plane(self):
        operations: list[str] = []
        sink = RecordingEventSink()

        result = run_start_session(
            make_start_request(),
            "immediate",
            get_default_instrument_profile(),
            sink,
            RecordingControls(operations),
            control_plane=NoOpControlPlane(),
            run_id="run-123",
            dependencies=self._dependencies(operations),
        )

        self.assertTrue(result.ok)
        self.assertEqual([], sink.by_type("ready"))
        self.assertNotIn("server_start", operations)
        self.assertNotIn("server_stop", operations)


if __name__ == "__main__":
    unittest.main()
