from __future__ import annotations

import csv
import unittest
from pathlib import Path
from uuid import uuid4

from keysight_logger_core import (
    NoOpControlPlane,
    StartRequest,
    StartControlPlaneHandle,
    StartRunEvent,
    get_default_instrument_profile,
    resolve_trigger_mode,
    run_start_session,
    validate_start_request,
)
from keysight_logger_core.models import InstrumentConfig, TriggerEvent, TriggerSource
from keysight_logger_core.simulator import SimulatedVisaInstrument


class RecordingEventSink:
    def __init__(self) -> None:
        self.events: list[StartRunEvent] = []

    def emit(self, event: StartRunEvent) -> None:
        self.events.append(event)

    def samples(self):  # noqa: ANN201
        return [event.sample for event in self.events if event.event == "sample"]


class PreloadedSoftwareTriggerControlPlane:
    def __init__(self, count: int) -> None:
        self._count = count

    def start(
        self,
        *,
        router,
        port: int,  # noqa: ARG002
        min_interval_ms: int,  # noqa: ARG002
        queue_max: int,  # noqa: ARG002
        stop_cb,  # noqa: ANN001, ARG002
        status_provider,  # noqa: ANN001, ARG002
    ) -> StartControlPlaneHandle:
        for index in range(self._count):
            router.publish(TriggerEvent.new(TriggerSource.SOFTWARE, {"preloaded": str(index)}))
        return StartControlPlaneHandle()


class SimulatedVisaInstrumentTests(unittest.TestCase):
    def test_read_path_returns_deterministic_values(self):
        instrument = SimulatedVisaInstrument(
            InstrumentConfig(resource_string="SIM::34461A"),
            measurement_type="voltage_dc",
        )

        self.assertEqual("SIM::34461A", instrument.resource_id)
        self.assertEqual(1.23, instrument.query_ascii_float("READ?"))
        self.assertEqual(2.23, instrument.query_ascii_float("READ?"))

    def test_ratio_read_path_returns_secondary_data2_values(self):
        instrument = SimulatedVisaInstrument(
            InstrumentConfig(resource_string="SIM::34461A"),
            measurement_type="voltage_dc_ratio",
        )

        self.assertEqual(1.23, instrument.query_ascii_float("READ?"))
        self.assertEqual("2.46,2", instrument.query("DATA2?"))

    def test_buffered_flow_tracks_triggered_points(self):
        instrument = SimulatedVisaInstrument(
            InstrumentConfig(resource_string="SIM::34461A"),
            measurement_type="current_dc",
        )

        instrument.write("TRIG:SOUR BUS")
        instrument.write("TRIG:COUNT 2")
        instrument.write("SAMP:COUNT 3")
        instrument.write("INIT")
        self.assertEqual("0", instrument.query("DATA:POINts?"))
        instrument.write("*TRG")
        self.assertEqual("3", instrument.query("DATA:POINts?"))
        self.assertEqual("1.23,2.23", instrument.query("DATA:REMove? 2"))
        self.assertEqual("1", instrument.query("DATA:POINts?"))

    def test_bus_triggers_do_not_exceed_configured_buffered_points(self):
        instrument = SimulatedVisaInstrument(
            InstrumentConfig(resource_string="SIM::34461A"),
            measurement_type="current_dc",
        )

        instrument.write("TRIG:SOUR BUS")
        instrument.write("TRIG:COUNT 2")
        instrument.write("SAMP:COUNT 3")
        instrument.write("INIT")
        for _index in range(4):
            instrument.write("*TRG")

        self.assertEqual("6", instrument.query("DATA:POINts?"))

    def test_ratio_buffered_flow_updates_data2_for_removed_reading(self):
        instrument = SimulatedVisaInstrument(
            InstrumentConfig(resource_string="SIM::34461A"),
            measurement_type="voltage_dc_ratio",
        )

        instrument.write("TRIG:SOUR IMM")
        instrument.write("TRIG:COUNT 1")
        instrument.write("SAMP:COUNT 2")
        instrument.write("INIT")
        self.assertEqual("2", instrument.query("DATA:POINts?"))
        self.assertEqual("1.23", instrument.query("DATA:REMove? 1"))
        self.assertEqual("2.46,2", instrument.query("DATA2?"))
        self.assertEqual("2.23", instrument.query("DATA:REMove? 1"))
        self.assertEqual("4.46,2", instrument.query("DATA2?"))

    def test_status_byte_tracks_armed_external_completion_and_abort(self):
        instrument = SimulatedVisaInstrument(
            InstrumentConfig(resource_string="SIM::34461A"),
            measurement_type="current_dc",
        )

        instrument.write("TRIG:SOUR EXT")
        instrument.write("INIT")
        self.assertEqual(0x20, instrument.read_status_byte())

        instrument.write("ABOR")
        self.assertEqual(0, instrument.read_status_byte())


class CoreSimulatorRatioSessionTests(unittest.TestCase):
    def _csv_path(self, name: str) -> Path:
        out_dir = Path.cwd() / ".test-output"
        out_dir.mkdir(exist_ok=True)
        return out_dir / f"{name}-{uuid4().hex}.csv"

    def _run(self, request: StartRequest, sink: RecordingEventSink, control_plane=None):  # noqa: ANN001
        profile = get_default_instrument_profile()
        trigger_mode = resolve_trigger_mode(request)
        validate_start_request(request, trigger_mode, instrument_profile=profile)
        return run_start_session(
            request,
            trigger_mode,
            profile,
            sink,
            None,
            control_plane=control_plane or NoOpControlPlane(),
        )

    def test_no_hardware_sessions_cover_supported_trigger_paths(self):
        cases = [
            (
                "bounded-immediate",
                StartRequest(
                    resource="SIM::34461A",
                    csv=str(self._csv_path("bounded-immediate")),
                    simulate=True,
                    trigger_mode="immediate",
                    max_samples=2,
                ),
                None,
                2,
                "immediate",
            ),
            (
                "software-timer",
                StartRequest(
                    resource="SIM::34461A",
                    csv=str(self._csv_path("software-timer")),
                    simulate=True,
                    trigger_mode="software",
                    timer_interval_s=0.5,
                    max_samples=2,
                ),
                None,
                2,
                "timer",
            ),
            (
                "immediate-custom",
                StartRequest(
                    resource="SIM::34461A",
                    csv=str(self._csv_path("immediate-custom")),
                    simulate=True,
                    trigger_mode="immediate-custom",
                    trigger_count=1,
                    sample_count=2,
                ),
                None,
                2,
                "immediate-custom",
            ),
            (
                "software-custom",
                StartRequest(
                    resource="SIM::34461A",
                    csv=str(self._csv_path("software-custom")),
                    simulate=True,
                    trigger_mode="software-custom",
                    trigger_count=2,
                    sample_count=1,
                ),
                PreloadedSoftwareTriggerControlPlane(2),
                2,
                "software-custom",
            ),
            (
                "external-custom",
                StartRequest(
                    resource="SIM::34461A",
                    csv=str(self._csv_path("external-custom")),
                    simulate=True,
                    trigger_mode="external-custom",
                    trigger_count=1,
                    sample_count=2,
                ),
                None,
                2,
                "external-custom",
            ),
        ]
        for name, request, control_plane, expected_count, expected_source in cases:
            sink = RecordingEventSink()
            out = Path(request.csv or "")
            try:
                with self.subTest(name=name):
                    result = self._run(request, sink, control_plane=control_plane)

                    self.assertTrue(result.ok)
                    self.assertEqual(expected_count, result.captured)
                    samples = sink.samples()
                    self.assertEqual(expected_count, len(samples))
                    self.assertEqual(
                        [1.23, 2.23],
                        [sample.value for sample in samples],
                    )
                    self.assertTrue(
                        all(sample.trigger_source == expected_source for sample in samples)
                    )
            finally:
                if out.exists():
                    out.unlink()

    def test_immediate_ratio_session_emits_measurement_metadata(self):
        out = self._csv_path("ratio-immediate")
        sink = RecordingEventSink()
        try:
            result = self._run(
                StartRequest(
                    resource="SIM::34461A",
                    csv=str(out),
                    simulate=True,
                    trigger_mode="immediate",
                    measurement="voltage-dc-ratio",
                    max_samples=1,
                ),
                sink,
            )

            self.assertTrue(result.ok)
            self.assertEqual(1, result.captured)
            samples = sink.samples()
            self.assertEqual(1, len(samples))
            self.assertEqual("voltage_dc_ratio", samples[0].measurement_type)
            self.assertEqual("ratio", samples[0].unit)
            self.assertEqual(2.46, samples[0].measurement_metadata["signal_voltage_v"])
            with out.open("r", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual("voltage_dc_ratio", rows[0]["measurement_type"])
            self.assertIn("signal_voltage_v", rows[0]["measurement_metadata"])
        finally:
            if out.exists():
                out.unlink()

    def test_custom_buffered_ratio_session_preserves_metadata_per_sample(self):
        out = self._csv_path("ratio-buffered")
        sink = RecordingEventSink()
        try:
            result = self._run(
                StartRequest(
                    resource="SIM::34461A",
                    csv=str(out),
                    simulate=True,
                    trigger_mode="immediate-custom",
                    measurement="voltage-dc-ratio",
                    trigger_count=1,
                    sample_count=2,
                ),
                sink,
            )

            self.assertTrue(result.ok)
            self.assertEqual(2, result.captured)
            samples = sink.samples()
            self.assertEqual(2, len(samples))
            self.assertEqual([1.23, 2.23], [sample.value for sample in samples])
            self.assertEqual(2.46, samples[0].measurement_metadata["signal_voltage_v"])
            self.assertEqual(4.46, samples[1].measurement_metadata["signal_voltage_v"])
            self.assertEqual("0", samples[0].trigger_metadata["buffer_index"])
            self.assertEqual("1", samples[1].trigger_metadata["buffer_index"])
        finally:
            if out.exists():
                out.unlink()


if __name__ == "__main__":
    unittest.main()
