from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from meters_tool_core.instrument import InstrumentError
from meters_tool_core.models import (
    KEYSIGHT_34460A_PROFILE,
    KEYSIGHT_34461A_PROFILE,
    StartRequest,
    get_default_instrument_profile,
)
from meters_tool_core.runner import (
    StartRunnerDependencies,
    StopController,
    run_start_session,
)
from meters_tool_core.session import NoOpControlPlane, StartRunEvent
from meters_tool_core.support_policy import SUPPORT_POLICY_MODE_VALIDATION


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

    def _live_dependencies(
        self,
        operations: list[str],
        *,
        expected_model: str,
        expected_resource: str = "USB0::FAKE::INSTR",
        expected_visa_library: str | None = None,
        expected_measurement_type: str = "voltage_dc",
    ) -> StartRunnerDependencies:
        def instrument_factory(config, *, simulate, measurement_type):  # noqa: ANN001
            self.assertEqual(expected_resource, config.resource_string)
            self.assertEqual(expected_model, config.expected_model)
            self.assertEqual(expected_visa_library, config.visa_library)
            self.assertFalse(simulate)
            self.assertEqual(expected_measurement_type, measurement_type)
            operations.append(f"factory:{config.expected_model}")
            return RecordingInstrument(operations)

        def engine_factory(**_kwargs):  # noqa: ANN003
            return RecordingEngine(operations=operations)

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

    def test_run_start_session_recomputes_immediate_trigger_mode_from_request(self):
        operations: list[str] = []
        sink = RecordingEventSink()

        result = run_start_session(
            make_start_request(trigger_mode="immediate"),
            "external",
            get_default_instrument_profile(),
            sink,
            RecordingControls(operations),
            control_plane=NoOpControlPlane(),
            run_id="run-123",
            dependencies=self._dependencies(operations),
        )

        self.assertTrue(result.ok)
        self.assertIn("engine_run:immediate:neg", operations)
        self.assertNotIn("engine_run:external:neg", operations)

    def test_run_start_session_recomputes_external_trigger_mode_from_request(self):
        operations: list[str] = []
        sink = RecordingEventSink()

        result = run_start_session(
            make_start_request(trigger_mode="external"),
            "immediate",
            get_default_instrument_profile(),
            sink,
            RecordingControls(operations),
            control_plane=NoOpControlPlane(),
            run_id="run-123",
            dependencies=self._dependencies(operations),
        )

        self.assertTrue(result.ok)
        self.assertIn("engine_run:external:neg", operations)
        self.assertNotIn("engine_run:immediate:neg", operations)

    def test_live_runner_recomputed_trigger_mode_prevents_34460a_external_bypass(self):
        operations: list[str] = []
        sink = RecordingEventSink()
        request = StartRequest(
            resource="USB0::FAKE::INSTR",
            trigger_mode="external",
            measurement="voltage-dc",
            max_samples=1,
        )

        def fail_factory(*_args, **_kwargs):  # noqa: ANN002, ANN003
            operations.append("factory")
            raise AssertionError("backend factory must not be called")

        deps = StartRunnerDependencies(instrument_backend_factory=fail_factory)
        with (
            patch(
                "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
                return_value="Keysight Technologies,34460A,MY123,1.0",
            ),
            self.assertRaisesRegex(
                ValueError,
                "--trigger-mode external is not supported by 34460A",
            ),
        ):
            run_start_session(
                request,
                "immediate",
                KEYSIGHT_34461A_PROFILE,
                sink,
                RecordingControls(operations),
                dependencies=deps,
            )

        self.assertEqual([], operations)

    def test_live_runner_uses_idn_detected_profile_not_external_profile_argument(self):
        operations: list[str] = []
        sink = RecordingEventSink()
        request = StartRequest(
            resource="USB0::FAKE::INSTR",
            trigger_mode="immediate",
            measurement="voltage-dc",
            max_samples=1,
        )

        with patch(
            "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
            return_value="Keysight Technologies,34460A,MY123,1.0",
        ) as preflight:
            result = run_start_session(
                request,
                "immediate",
                KEYSIGHT_34461A_PROFILE,
                sink,
                RecordingControls(operations),
                control_plane=NoOpControlPlane(),
                run_id="run-live",
                dependencies=self._live_dependencies(
                    operations,
                    expected_model="34460A",
                ),
            )

        self.assertTrue(result.ok)
        self.assertIn("factory:34460A", operations)
        preflight.assert_called_once()

    def test_live_runner_omitted_model_uses_detected_34461a_profile(self):
        operations: list[str] = []
        sink = RecordingEventSink()
        request = StartRequest(
            resource="USB0::FAKE::INSTR",
            trigger_mode="immediate",
            measurement="voltage-dc",
            max_samples=1,
        )

        with patch(
            "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
            return_value="Keysight Technologies,34461A,MY123,1.0",
        ):
            result = run_start_session(
                request,
                "immediate",
                KEYSIGHT_34460A_PROFILE,
                sink,
                RecordingControls(operations),
                control_plane=NoOpControlPlane(),
                run_id="run-live",
                dependencies=self._live_dependencies(
                    operations,
                    expected_model="34461A",
                ),
            )

        self.assertTrue(result.ok)
        self.assertIn("factory:34461A", operations)

    def test_live_runner_allows_validated_34461a_lan_scopes_before_backend_factory(self):
        cases = [
            (
                StartRequest(
                    resource="TCPIP0::host::inst0::INSTR",
                    trigger_mode="immediate",
                    measurement="voltage-dc",
                    max_samples=1,
                ),
                None,
            ),
            (
                StartRequest(
                    resource="TCPIP::host::INSTR",
                    visa_library="@py",
                    trigger_mode="immediate",
                    measurement="voltage-dc",
                    max_samples=1,
                ),
                "@py",
            ),
        ]

        for request, expected_visa_library in cases:
            with self.subTest(visa_library=expected_visa_library):
                operations: list[str] = []
                sink = RecordingEventSink()

                with patch(
                    "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
                    return_value="Keysight Technologies,34461A,MY123,1.0",
                ):
                    result = run_start_session(
                        request,
                        "immediate",
                        KEYSIGHT_34461A_PROFILE,
                        sink,
                        RecordingControls(operations),
                        control_plane=NoOpControlPlane(),
                        run_id="run-live",
                        dependencies=self._live_dependencies(
                            operations,
                            expected_model="34461A",
                            expected_resource=request.resource,
                            expected_visa_library=expected_visa_library,
                        ),
                    )

                self.assertTrue(result.ok)
                self.assertIn("factory:34461A", operations)

    def test_live_runner_expected_model_mismatch_fails_before_backend_factory(self):
        operations: list[str] = []
        sink = RecordingEventSink()
        request = StartRequest(
            resource="USB0::FAKE::INSTR",
            instrument_model="34461A",
            trigger_mode="immediate",
            measurement="voltage-dc",
            max_samples=1,
        )

        def fail_factory(*_args, **_kwargs):  # noqa: ANN002, ANN003
            operations.append("factory")
            raise AssertionError("backend factory must not be called")

        deps = StartRunnerDependencies(instrument_backend_factory=fail_factory)
        with (
            patch(
                "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
                return_value="Keysight Technologies,34460A,MY123,1.0",
            ),
            self.assertRaisesRegex(
                ValueError,
                "Selected model 34461A does not match the connected instrument IDN 34460A",
            ),
        ):
            run_start_session(
                request,
                "immediate",
                KEYSIGHT_34461A_PROFILE,
                sink,
                RecordingControls(operations),
                dependencies=deps,
            )

        self.assertEqual([], operations)

    def test_live_runner_rejects_detected_34460a_unsupported_workflows_before_backend_factory(self):
        cases = [
            (
                StartRequest(
                    resource="USB0::FAKE::INSTR",
                    trigger_mode="external",
                    measurement="voltage-dc",
                    max_samples=1,
                ),
                "--trigger-mode external is not supported by 34460A",
            ),
            (
                StartRequest(
                    resource="USB0::FAKE::INSTR",
                    trigger_mode="external-custom",
                    measurement="voltage-dc",
                    trigger_count=1,
                    sample_count=1,
                ),
                "--trigger-mode external-custom is not supported by 34460A",
            ),
            (
                StartRequest(
                    resource="USB0::FAKE::INSTR",
                    trigger_mode="immediate",
                    measurement="current-dc",
                    max_samples=1,
                    auto_range=False,
                    measurement_range=10.0,
                ),
                "--range 10 is not valid",
            ),
            (
                StartRequest(
                    resource="USB0::FAKE::INSTR",
                    trigger_mode="immediate",
                    measurement="current-dc",
                    max_samples=1,
                    current_terminal=10,
                ),
                "--current-terminal can only be used",
            ),
            (
                StartRequest(
                    resource="USB0::FAKE::INSTR",
                    trigger_mode="immediate-custom",
                    measurement="voltage-dc",
                    trigger_count=1,
                    sample_count=1,
                    buffer_drain_size=1001,
                ),
                "--buffer-drain-size 1001 is outside the 34460A reading-memory range 1-1000",
            ),
            (
                StartRequest(
                    resource="TCPIP0::host::inst0::INSTR",
                    trigger_mode="immediate",
                    measurement="voltage-dc",
                    max_samples=1,
                ),
                "start-trigger-record is pending for transport=tcpip, backend=system_visa",
            ),
            (
                StartRequest(
                    resource="USB0::FAKE::INSTR",
                    visa_library="@py",
                    trigger_mode="immediate",
                    measurement="voltage-dc",
                    max_samples=1,
                ),
                "not registered for transport=usb, backend=pyvisa_py",
            ),
            (
                StartRequest(
                    resource="TCPIP::host::INSTR",
                    visa_library="@py",
                    trigger_mode="immediate",
                    measurement="voltage-dc",
                    max_samples=1,
                ),
                "start-trigger-record is pending for transport=tcpip, backend=pyvisa_py",
            ),
        ]

        for request, expected in cases:
            with self.subTest(expected=expected):
                operations: list[str] = []
                sink = RecordingEventSink()

                def fail_factory(*_args, **_kwargs):  # noqa: ANN002, ANN003
                    operations.append("factory")
                    raise AssertionError("backend factory must not be called")

                deps = StartRunnerDependencies(instrument_backend_factory=fail_factory)
                with (
                    patch(
                        "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
                        return_value="Keysight Technologies,34460A,MY123,1.0",
                    ),
                    self.assertRaises(ValueError) as exc,
                ):
                    run_start_session(
                        request,
                        request.trigger_mode or "software",
                        KEYSIGHT_34461A_PROFILE,
                        sink,
                        RecordingControls(operations),
                        dependencies=deps,
                    )

                self.assertIn(expected, str(exc.exception))
                self.assertEqual([], operations)

    def test_live_runner_validation_mode_allows_pending_34460a_lan_before_backend_factory(self):
        operations: list[str] = []
        sink = RecordingEventSink()
        request = StartRequest(
            resource="TCPIP0::host::inst0::INSTR",
            trigger_mode="immediate",
            measurement="voltage-dc",
            max_samples=1,
        )

        with patch(
            "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
            return_value="Keysight Technologies,34460A,MY123,1.0",
        ):
            result = run_start_session(
                request,
                "immediate",
                KEYSIGHT_34461A_PROFILE,
                sink,
                RecordingControls(operations),
                control_plane=NoOpControlPlane(),
                run_id="run-live",
                dependencies=self._live_dependencies(
                    operations,
                    expected_model="34460A",
                    expected_resource="TCPIP0::host::inst0::INSTR",
                ),
                support_policy_mode=SUPPORT_POLICY_MODE_VALIDATION,
            )

        self.assertTrue(result.ok)
        self.assertIn("factory:34460A", operations)

    def test_live_runner_product_mode_allows_promoted_34460a_ratio(self):
        operations: list[str] = []
        sink = RecordingEventSink()
        request = StartRequest(
            resource="USB0::FAKE::INSTR",
            trigger_mode="immediate",
            measurement="voltage-dc-ratio",
            max_samples=1,
        )

        with patch(
            "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
            return_value="Keysight Technologies,34460A,MY123,1.0",
        ):
            result = run_start_session(
                request,
                "external",
                KEYSIGHT_34461A_PROFILE,
                sink,
                RecordingControls(operations),
                run_id="run-live-ratio",
                dependencies=self._live_dependencies(
                    operations,
                    expected_model="34460A",
                    expected_measurement_type="voltage_dc_ratio",
                ),
            )

        self.assertTrue(result.ok)
        self.assertIn("factory:34460A", operations)
        self.assertIn("engine_run:immediate:neg", operations)
        self.assertNotIn("engine_run:external:neg", operations)
        cleanup_order = [
            "release_to_local",
            "close",
            "cleanup_release_to_local",
            "server_stop",
        ]
        positions = [operations.index(step) for step in cleanup_order]
        self.assertEqual(sorted(positions), positions)

    def test_live_runner_missing_feature_metadata_rejects_before_backend_factory(self):
        operations: list[str] = []
        request = StartRequest(
            resource="USB0::FAKE::INSTR",
            trigger_mode="immediate",
            measurement="voltage-dc",
            max_samples=1,
        )

        def fail_factory(*_args, **_kwargs):  # noqa: ANN002, ANN003
            operations.append("factory")
            raise AssertionError("backend factory must not be called")

        with (
            patch(
                "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
                return_value="Keysight Technologies,34460A,MY123,1.0",
            ),
            patch("meters_tool_core.support_policy.find_feature_support", return_value=None),
            self.assertRaisesRegex(
                ValueError,
                "live feature support is not registered for measurement=voltage-dc",
            ),
        ):
            run_start_session(
                request,
                "immediate",
                KEYSIGHT_34461A_PROFILE,
                RecordingEventSink(),
                RecordingControls(operations),
                dependencies=StartRunnerDependencies(
                    instrument_backend_factory=fail_factory
                ),
            )

        self.assertEqual([], operations)

    def test_dry_run_and_simulate_runner_resolution_do_not_query_live_idn(self):
        dry_run_request = StartRequest(
            resource="USB0::FAKE::INSTR",
            dry_run=True,
            trigger_mode="immediate",
            measurement="voltage-dc",
            max_samples=1,
        )
        with patch("meters_tool_core.start_resolution.VisaInstrument.preflight_idn") as preflight:
            with self.assertRaisesRegex(
                ValueError,
                "dry-run cannot auto-detect the instrument model without VISA I/O",
            ):
                run_start_session(
                    dry_run_request,
                    "immediate",
                    KEYSIGHT_34461A_PROFILE,
                    RecordingEventSink(),
                    RecordingControls([]),
                )
        preflight.assert_not_called()

        simulate_request = make_start_request(resource="SIM::34461A", simulate=True)
        operations: list[str] = []
        with patch("meters_tool_core.start_resolution.VisaInstrument.preflight_idn") as preflight:
            result = run_start_session(
                simulate_request,
                "immediate",
                KEYSIGHT_34461A_PROFILE,
                RecordingEventSink(),
                RecordingControls(operations),
                control_plane=NoOpControlPlane(),
                dependencies=self._dependencies(operations),
            )

        self.assertTrue(result.ok)
        preflight.assert_not_called()


if __name__ == "__main__":
    unittest.main()
