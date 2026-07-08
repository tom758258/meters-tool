from __future__ import annotations

from datetime import datetime, timezone

from meters_tool_core.acquisition import TriggerAcquisitionEngine
from meters_tool_core.models import AcquisitionConfig, MeasurementSample
from meters_tool_core.trigger import TriggerRouter


class CommandRecordingInstrument:
    def __init__(self) -> None:
        self.resource_id = "USB::FAKE"
        self.commands: list[str] = []
        self.responses: dict[str, object] = {}

    def write(self, command: str) -> None:
        self.commands.append(command)

    def query_ascii_float(self, command: str) -> float:
        self.commands.append(command)
        return 1.23

    def query(self, command: str) -> str:
        self.commands.append(command)
        response = self.responses[command]
        if isinstance(response, list):
            return response.pop(0)
        return str(response)


class FakeInstrument:
    resource_id = "FAKE::INSTR"

    def __init__(self) -> None:
        self.abort_count = 0

    def write(self, command: str) -> None:  # noqa: ARG002
        return

    def abort_measurement(self) -> bool:
        self.abort_count += 1
        return True


class RecordingInstrument(FakeInstrument):
    def __init__(self) -> None:
        super().__init__()
        self.commands: list[str] = []

    def write(self, command: str) -> None:
        self.commands.append(command)


class FakeMeasurement:
    def __init__(
        self,
        value: float = 1.23,
        unit: str = "A",
        measurement_type: str = "current_dc",
    ) -> None:
        self.value = value
        self.unit = unit
        self.measurement_type = measurement_type

    def configure(self, instrument, config):  # noqa: ANN001, ARG002
        return

    def read_sample(self, instrument, trigger):  # noqa: ANN001
        return MeasurementSample(
            timestamp_utc=datetime.now(timezone.utc),
            measurement_type=self.measurement_type,
            value=self.value,
            unit=self.unit,
            status="ok",
            resource_id=instrument.resource_id,
            trigger_id=trigger.id,
            trigger_source=trigger.source.value,
        )


class FailingMeasurement(FakeMeasurement):
    def read_sample(self, instrument, trigger):  # noqa: ANN001
        raise AssertionError("software trigger should not be captured")


class CaptureFailingMeasurement(FakeMeasurement):
    def read_sample(self, instrument, trigger):  # noqa: ANN001, ARG002
        raise RuntimeError("read failed")


class FakeBufferedMeasurement(FakeMeasurement):
    def __init__(self) -> None:
        self.sample_count = 0
        self.sample_count_per_trigger = 0
        self.started = False
        self.read_counts: list[int] = []
        self.bus_triggers_sent = 0

    def configure_immediate_custom(self, instrument, config, trigger_count, sample_count):  # noqa: ANN001, ARG002
        self.sample_count = trigger_count * sample_count
        instrument.write("TRIG:SOUR IMM")
        instrument.write(f"TRIG:COUNT {trigger_count}")
        instrument.write(f"SAMP:COUNT {sample_count}")

    def configure_software_custom(self, instrument, config, trigger_count, sample_count):  # noqa: ANN001, ARG002
        self.sample_count = 0
        self.sample_count_per_trigger = sample_count
        instrument.write("TRIG:SOUR BUS")
        instrument.write(f"TRIG:COUNT {trigger_count}")
        instrument.write(f"SAMP:COUNT {sample_count}")

    def configure_external_custom(self, instrument, config, trigger_count, sample_count, slope, delay_s):  # noqa: ANN001, ARG002
        self.sample_count = trigger_count * sample_count
        slope_cmd = "POS" if str(slope).upper() == "POS" else "NEG"
        instrument.write("TRIG:SOUR EXT")
        instrument.write(f"TRIG:SLOP {slope_cmd}")
        instrument.write(f"TRIG:COUNT {trigger_count}")
        instrument.write(f"SAMP:COUNT {sample_count}")
        instrument.write(f"TRIG:DEL {max(0.0, float(delay_s))}")

    def send_bus_trigger(self, instrument):  # noqa: ANN001
        self.bus_triggers_sent += 1
        self.sample_count += self.sample_count_per_trigger
        instrument.write("*TRG")

    def start_buffered_capture(self, instrument):  # noqa: ANN001
        self.started = True
        instrument.write("INIT")

    def buffered_points_available(self, instrument):  # noqa: ANN001, ARG002
        return max(0, self.sample_count)

    def read_buffered_samples(self, instrument, trigger, count, first_sample_index):  # noqa: ANN001, ARG002
        self.read_counts.append(count)
        self.sample_count -= count
        return [
            MeasurementSample(
                timestamp_utc=datetime.now(timezone.utc),
                measurement_type="current_dc",
                value=float(first_sample_index + offset),
                unit="A",
                status="ok",
                resource_id=instrument.resource_id,
                trigger_id=trigger.id,
                trigger_source=trigger.source.value,
                trigger_metadata={
                    "buffer_index": str(first_sample_index + offset),
                    "time_basis": "pc_data_remove_time_not_instrument_sample_time",
                },
            )
            for offset in range(count)
        ]


class BufferedReadFailingMeasurement(FakeBufferedMeasurement):
    def read_buffered_samples(self, instrument, trigger, count, first_sample_index):  # noqa: ANN001, ARG002
        raise RuntimeError("buffer read failed")


class BufferedAvailableFailingMeasurement(FakeBufferedMeasurement):
    def buffered_points_available(self, instrument):  # noqa: ANN001, ARG002
        raise RuntimeError("points query failed")


class FakeStorage:
    def open(self) -> None:
        return

    def close(self) -> None:
        return

    def write(self, sample) -> None:  # noqa: ANN001, ARG002
        return


class CapturingStorage(FakeStorage):
    def __init__(self) -> None:
        self.samples = []

    def write(self, sample) -> None:  # noqa: ANN001
        self.samples.append(sample)


class PermissionDeniedStorage(FakeStorage):
    def open(self) -> None:
        raise PermissionError(13, "Permission denied", "data\\locked.csv")


def make_acquisition_engine(
    *,
    instrument=None,
    measurement=None,
    storage=None,
    config=None,
    router=None,
    instrument_profile=None,
    status_cb=None,
) -> TriggerAcquisitionEngine:
    kwargs = {
        "instrument": instrument if instrument is not None else FakeInstrument(),
        "measurement": measurement if measurement is not None else FakeMeasurement(),
        "storage": storage if storage is not None else FakeStorage(),
        "config": config if config is not None else AcquisitionConfig(trigger_timeout_ms=50),
        "router": router if router is not None else TriggerRouter(),
    }
    if instrument_profile is not None:
        kwargs["instrument_profile"] = instrument_profile
    if status_cb is not None:
        kwargs["status_cb"] = status_cb
    return TriggerAcquisitionEngine(**kwargs)  # type: ignore[arg-type]
