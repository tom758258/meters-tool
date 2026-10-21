from __future__ import annotations

from types import SimpleNamespace

import pytest

from meters_tool_core.acquisition import TriggerAcquisitionEngine
from meters_tool_core.measurement import BufferedReadError
from meters_tool_core.models import AcquisitionConfig, TriggerEvent, TriggerSource
from meters_tool_core.models import StartRequest, get_default_instrument_profile
from meters_tool_core.runner import StartRunnerDependencies, run_start_session
from meters_tool_core.session import NoOpStartRunControls, StartControlPlaneHandle
from meters_tool_core.simulator import SimulatedVisaInstrument
from meters_tool_core.streaming import RunBoundStreamState
from meters_tool_core.trigger import HardwareTriggerAdapter, TriggerRouter

from core_test_helpers import FakeBufferedMeasurement, FakeMeasurement, RecordingInstrument


class StreamingInstrument(RecordingInstrument):
    def set_timeout_ms(self, timeout_ms):
        self.timeout_ms = timeout_ms

    def read_status_byte(self):
        return 0

    def poll_system_error(self):
        raise AssertionError("stream observation failure must not query the error queue")


class WaitingMeasurement(FakeBufferedMeasurement):
    def configure_external_custom(self, *args, **kwargs):
        super().configure_external_custom(*args, **kwargs)
        self.sample_count = 0

    def waiting_for_trigger(self, instrument):
        return self.software_trigger_ready(instrument)


def test_stream_state_is_monotonic_and_snapshots_are_detached():
    state = RunBoundStreamState("test-run")
    snapshot = state.status_fields()
    assert state.ready_fields() == {"stream": {"lifecycle": "run_bound"}}
    assert state.activate()
    assert not state.activate()
    assert snapshot["stream"]["state"] == "waiting"
    assert state.end()
    assert not state.end()
    assert not state.activate()
    assert state.status_fields()["stream"]["state"] == "ended"
    stopped = RunBoundStreamState("stopped-run")
    assert stopped.end()
    assert not stopped.activate()


@pytest.mark.parametrize("mode,timer", [
    ("immediate", None), ("software", None), ("software", 0.01),
    ("external", None), ("immediate-custom", None),
    ("software-custom", None), ("external-custom", None),
])
def test_mode_active_boundaries_precede_samples(mode, timer):
    instrument = StreamingInstrument()
    router = TriggerRouter()
    events = []
    custom = mode.endswith("-custom")
    measurement = WaitingMeasurement() if custom else FakeMeasurement()
    if mode == "external":
        instrument.read_status_byte = lambda: 0x20
    config = AcquisitionConfig(
        max_samples=None if custom else 1, trigger_count=1 if custom else None,
        sample_count=1 if custom else None, timer_interval_s=timer, trigger_timeout_ms=1000,
    )

    def active():
        events.append("active")
        if mode in {"software", "software-custom"} and timer is None:
            # A consumer may wait for active before sending its first trigger.
            router.publish(TriggerEvent.new(TriggerSource.SOFTWARE))
        if mode == "external-custom":
            measurement.sample_count = 1

    engine = TriggerAcquisitionEngine(
        instrument, measurement, None, config, router,
        active_cb=active, sample_cb=lambda *_: events.append("sample"),
    )
    engine.run(mode)
    assert engine.ok
    assert events == ["active", "sample"]
    if mode in {"software-custom", "external-custom"}:
        assert instrument.commands.count("STAT:OPER:COND?") == 1
    else:
        assert "STAT:OPER:COND?" not in instrument.commands


@pytest.mark.parametrize("streaming", [False, True])
def test_stopped_before_start_never_observes_or_declares_active(streaming):
    instrument = StreamingInstrument()
    events = []
    engine = TriggerAcquisitionEngine(
        instrument, WaitingMeasurement(), None,
        AcquisitionConfig(trigger_count=1, sample_count=1), TriggerRouter(),
        active_cb=(lambda: events.append("active")) if streaming else None,
    )
    engine.stop()
    engine.run("software-custom")
    assert events == []
    assert instrument.commands == []


def test_opt_out_adds_no_startup_query():
    instrument = StreamingInstrument()
    router = TriggerRouter()
    router.publish(TriggerEvent.new(TriggerSource.SOFTWARE))
    engine = TriggerAcquisitionEngine(
        instrument, WaitingMeasurement(), None,
        AcquisitionConfig(trigger_count=1, sample_count=1), router,
    )
    engine.run("software-custom")
    assert engine.stats.captured == 1
    assert "STAT:OPER:COND?" not in instrument.commands


@pytest.mark.parametrize("failure", [TimeoutError("query timeout"), OSError("connection lost"),
                                    RuntimeError("invalid status register")])
def test_observation_failure_preserves_final_drain_and_failed_result(failure):
    events = []
    instrument = StreamingInstrument()

    class TailMeasurement(WaitingMeasurement):
        def waiting_for_trigger(self, instrument):
            instrument.write("STAT:OPER:COND?")
            self.sample_count = 2
            events.append("observation_failure")
            raise failure

    engine = TriggerAcquisitionEngine(
        instrument, TailMeasurement(), None,
        AcquisitionConfig(trigger_count_infinite=True, sample_count=2), TriggerRouter(),
        active_cb=lambda: events.append("active"),
        sample_cb=lambda *_: events.append("sample"),
    )
    engine.run("software-custom")
    assert events == ["observation_failure", "active", "sample", "sample"]
    assert instrument.abort_count == 1
    assert instrument.commands.count("STAT:OPER:COND?") == 1
    assert engine.stats.errors == 1
    assert engine.stats.stop_reason == "fatal_error"
    assert engine.stats.final_drain_complete is True
    assert str(failure) in engine.fatal_error
    assert not engine.ok


@pytest.mark.parametrize("tail_count", [0, 1])
def test_stop_during_observation_ignores_waiting_bit_but_keeps_tail_evidence(tail_count):
    events = []

    class StopDuringQuery(WaitingMeasurement):
        def waiting_for_trigger(self, instrument):
            self.sample_count = tail_count
            engine.stop()
            return True

    engine = TriggerAcquisitionEngine(
        StreamingInstrument(), StopDuringQuery(), None,
        AcquisitionConfig(trigger_count_infinite=True, sample_count=1), TriggerRouter(),
        active_cb=lambda: events.append("active"),
        sample_cb=lambda *_: events.append("sample"),
    )
    engine.run("external-custom")
    assert events == (["active", "sample"] if tail_count else [])
    assert engine.stats.stop_reason == "stop_requested"
    assert engine.ok


def test_partial_buffer_read_keeps_active_before_retained_sample():
    events = []

    class PartialRead(WaitingMeasurement):
        def read_buffered_samples(self, instrument, trigger, count, first_sample_index):
            samples = super().read_buffered_samples(instrument, trigger, 1, first_sample_index)
            raise BufferedReadError("partial read", samples)

    engine = TriggerAcquisitionEngine(
        StreamingInstrument(), PartialRead(), None,
        AcquisitionConfig(trigger_count=1, sample_count=2), TriggerRouter(),
        active_cb=lambda: events.append("active"),
        sample_cb=lambda *_: events.append("sample"),
    )
    engine.run("immediate-custom")
    assert events == ["active", "sample"]
    assert not engine.ok


def test_observation_interval_is_measured_from_query_completion(monkeypatch):
    clock = SimpleNamespace(now=0.0)
    starts, finishes = [], []
    monkeypatch.setattr("meters_tool_core.acquisition.time.monotonic", lambda: clock.now)

    class SlowQuery(WaitingMeasurement):
        def buffered_points_available(self, instrument):
            clock.now += 0.05
            return 0

        def waiting_for_trigger(self, instrument):
            starts.append(clock.now)
            clock.now += 0.17
            finishes.append(clock.now)
            return len(starts) == 3

    engine = TriggerAcquisitionEngine(
        StreamingInstrument(), SlowQuery(), None,
        AcquisitionConfig(trigger_count=1, sample_count=1), TriggerRouter(),
        active_cb=lambda: engine.stop(),
    )
    engine.run("external-custom")
    assert len(starts) == 3
    assert all(start - end >= 0.2 for start, end in zip(starts[1:], finishes))
    assert engine.stats.errors == 0


def test_external_observation_error_is_fatal_not_protective_rearm():
    instrument = StreamingInstrument()

    class FailingObservation(FakeMeasurement):
        def waiting_for_trigger(self, instrument):
            instrument.write("STAT:OPER:COND?")
            raise TimeoutError("observation timed out")

    engine = TriggerAcquisitionEngine(
        instrument, FailingObservation(), None,
        AcquisitionConfig(trigger_timeout_ms=1000), TriggerRouter(), active_cb=lambda: None,
    )
    engine.run("external")
    assert not engine.ok
    assert engine.stats.errors == 1
    assert instrument.commands.count("INIT") == 1
    assert instrument.commands.count("*CLS") == 1
    assert instrument.abort_count == 1
    assert "TimeoutError" in engine.fatal_error


def test_external_waiting_evidence_precedes_completion_and_stops_observations():
    events = []

    class DelayedTrigger(StreamingInstrument):
        polls = 0

        def read_status_byte(self):
            self.polls += 1
            return 0x20 if self.polls == 4 else 0

    class ArmedMeasurement(FakeMeasurement):
        def waiting_for_trigger(self, instrument):
            instrument.write("STAT:OPER:COND?")
            return True

    instrument = DelayedTrigger()
    engine = TriggerAcquisitionEngine(
        instrument, ArmedMeasurement(), None,
        AcquisitionConfig(trigger_timeout_ms=2000, max_samples=1), TriggerRouter(),
        active_cb=lambda: events.append(("active", instrument.polls)),
        sample_cb=lambda *_: events.append(("sample", instrument.polls)),
    )
    engine.run("external")
    assert events == [("active", 1), ("sample", 4)]
    assert instrument.commands.count("STAT:OPER:COND?") == 1
    assert engine.ok


def test_external_short_budget_skips_observation_and_preserves_timeout():
    instrument = StreamingInstrument()
    observations = []
    with pytest.raises(TimeoutError, match="hardware trigger wait timed out"):
        HardwareTriggerAdapter(instrument).wait_and_read_triggered(
            50, readiness_cb=lambda: observations.append(True),
        )
    assert observations == []
    assert instrument.timeout_ms == 100


def test_external_completed_status_does_not_issue_observation():
    instrument = StreamingInstrument()
    instrument.read_status_byte = lambda: 0x20
    observations = []
    result = HardwareTriggerAdapter(instrument).wait_and_read_triggered(
        1000, readiness_cb=lambda: observations.append(True),
    )
    assert result.source == TriggerSource.HARDWARE
    assert observations == []


@pytest.mark.parametrize("outcome", ["success", "stopped", "configure_failure"])
def test_runner_shares_state_and_ends_before_summary_and_cleanup(outcome):
    state = RunBoundStreamState("runner-stream")
    events = []
    snapshots = []

    class Plane:
        def start(self, **kwargs):
            self.status = kwargs["status_provider"]
            snapshots.append(self.status())
            if outcome == "stopped":
                kwargs["stop_cb"]()
            return StartControlPlaneHandle(host="127.0.0.1", port=8765)

    plane = Plane()

    def emit(event):
        events.append(event)
        if event.event == "status":
            snapshot = plane.status()
            assert snapshot["stream"] == event.fields["stream"]
            assert snapshot["run_id"] == event.run_id == state.run_id

    class ConfigureFailure(FakeMeasurement):
        def configure(self, instrument, config):
            raise RuntimeError("configure failed")

    dependencies = (
        StartRunnerDependencies(measurement_factory=lambda _: ConfigureFailure())
        if outcome == "configure_failure" else None
    )
    result = run_start_session(
        StartRequest(resource="SIM::34461A", simulate=True, csv_enabled=False,
                     trigger_mode="immediate", max_samples=1),
        "immediate", get_default_instrument_profile(), SimpleNamespace(emit=emit),
        NoOpStartRunControls(), control_plane=plane, stream_state=state,
        dependencies=dependencies,
    )
    assert snapshots[0]["stream"]["state"] == "waiting"
    ready = next(e for e in events if e.event == "ready")
    assert ready.fields == state.ready_fields()
    statuses = [e.fields["stream"]["state"] for e in events if e.event == "status"]
    assert statuses[-1] == "ended"
    assert statuses.count("ended") == 1
    assert ("active" in statuses) == (outcome == "success")
    summary = next(e for e in events if e.event == "summary")
    ended = next(e for e in events if e.event == "status" and e.fields["stream"]["state"] == "ended")
    assert events.index(ready) < events.index(ended) < events.index(summary)
    for sample in (e for e in events if e.event == "sample"):
        active = next(e for e in events if e.event == "status" and e.fields["stream"]["state"] == "active")
        assert events.index(ready) < events.index(active) < events.index(sample) < events.index(ended)
        assert "stream" not in sample.fields
    assert "stream" not in summary.fields
    assert summary.fields["ok"] == result.ok == (outcome != "configure_failure")
    assert any(e.event == "message" for e in events[events.index(summary) + 1:])


def test_runner_tail_active_does_not_erase_observation_failure():
    events = []

    class QueryFailureWithTail(SimulatedVisaInstrument):
        def query(self, command):
            if command == "STAT:OPER:COND?":
                # Simulate a trigger arriving during the failed observation.
                self.write("*TRG")
                raise TimeoutError("observation timeout with retained data")
            return super().query(command)

        def poll_system_error(self):
            raise AssertionError("no extra diagnostic query after observation failure")

    result = run_start_session(
        StartRequest(resource="SIM::34461A", simulate=True, csv_enabled=False,
                     trigger_mode="software-custom", trigger_count_infinite=True, sample_count=2,
                     allow_buffer_overflow_risk=True, sw_trigger_port=0),
        "software-custom", get_default_instrument_profile(), SimpleNamespace(emit=events.append),
        NoOpStartRunControls(), stream_state=RunBoundStreamState("failed-tail"),
        dependencies=StartRunnerDependencies(
            instrument_backend_factory=lambda config, **kw: QueryFailureWithTail(config),
        ),
    )
    assert not result.ok
    assert result.captured == 2
    assert result.final_drain_complete is True
    active = next(i for i, e in enumerate(events) if e.fields.get("stream", {}).get("state") == "active")
    samples = [i for i, e in enumerate(events) if e.event == "sample"]
    ended = next(i for i, e in enumerate(events) if e.fields.get("stream", {}).get("state") == "ended")
    summary = next(i for i, e in enumerate(events) if e.event == "summary")
    assert active < min(samples) <= max(samples) < ended < summary
    assert events[summary].fields["ok"] is False
    assert "observation timeout" in events[summary].fatal_error
