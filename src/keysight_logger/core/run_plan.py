from __future__ import annotations

from dataclasses import dataclass

from .measurement import (
    create_measurement_plugin,
    get_measurement_definition,
    normalize_measurement_type,
)
from .models import AcquisitionConfig, InstrumentProfile, StartRequest
from .trigger import HardwareTriggerAdapter
from .validation import resolve_csv_path, resolve_measurement_range


class _PlanRecorder:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def write(self, command: str) -> None:
        self.commands.append(command)

    def query(self, command: str) -> str:
        self.commands.append(f"query:{command}")
        return "1.23"

    def query_ascii_float(self, command: str) -> float:
        self.commands.append(command)
        return 1.23

    def set_timeout_ms(self, timeout_ms: int) -> None:  # noqa: ARG002
        return None

    def connect(self) -> None:
        return None

    def close(self) -> None:
        return None

    def read_status_byte(self) -> int:
        return 0

    def poll_system_error(self) -> str:
        return "0,No error"

    def abort_measurement(self) -> bool:
        return True

    def release_to_local(self) -> str:
        return "dry_run_release_to_local"

    def cleanup_release_to_local(self, timeout_ms: int = 1000) -> str:  # noqa: ARG002
        return "dry_run_cleanup_release_to_local"

    @property
    def resource_id(self) -> str:
        return "<dry-run>"


@dataclass
class StartPlan:
    trigger_mode: str
    measurement_type: str
    measurement_name: str
    measurement_unit: str
    csv_path: str
    resource: str
    simulate: bool
    dry_run: bool
    scpi_commands: list[str]
    read_path: str
    cleanup_steps: list[str]
    notes: list[str]


def build_start_plan(
    request: StartRequest,
    trigger_mode: str,
    profile: InstrumentProfile,
    buffer_warnings: list[str] | None = None,
) -> StartPlan:
    args = request
    measurement_type = normalize_measurement_type(args.measurement)
    measurement_def = get_measurement_definition(measurement_type)
    csv_path = str(resolve_csv_path(args.csv))
    config = AcquisitionConfig(
        measurement_type=measurement_type,
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
        measurement_range=resolve_measurement_range(args),
        current_range=args.current_range,
        ac_bandwidth_hz=args.ac_bandwidth_hz,
        current_terminal=args.current_terminal,
        dcv_input_impedance=args.dcv_input_impedance,
        hw_trigger_delay_s=args.hw_trigger_delay_s,
        vm_comp_slope=args.vm_comp_slope,
    )
    measurement = create_measurement_plugin(measurement_type)
    recorder = _PlanRecorder()
    measurement.configure(recorder, config)
    if trigger_mode == "external":
        HardwareTriggerAdapter(recorder).configure_external_trigger(
            slope=args.hw_trigger_slope,
            delay_s=args.hw_trigger_delay_s,
        )
    elif trigger_mode == "immediate-custom":
        measurement.configure_immediate_custom(
            recorder,
            config,
            trigger_count=args.trigger_count,
            sample_count=args.sample_count,
        )
        measurement.start_buffered_capture(recorder)
    elif trigger_mode == "software-custom":
        measurement.configure_software_custom(
            recorder,
            config,
            trigger_count=args.trigger_count,
            sample_count=args.sample_count,
        )
        measurement.start_buffered_capture(recorder)
    elif trigger_mode == "external-custom":
        measurement.configure_external_custom(
            recorder,
            config,
            trigger_count=args.trigger_count,
            sample_count=args.sample_count,
            slope=args.hw_trigger_slope,
            delay_s=args.hw_trigger_delay_s,
        )
        measurement.start_buffered_capture(recorder)
    scpi_commands = recorder.commands
    ratio_metadata = measurement_type == "voltage_dc_ratio"
    if trigger_mode.endswith("-custom"):
        read_path = (
            "DATA:POINts? / DATA:REMove? 1 / DATA2?"
            if ratio_metadata
            else "DATA:POINts? / DATA:REMove?"
        )
    elif trigger_mode == "external":
        read_path = "FETC? / DATA2?" if ratio_metadata else "FETC?"
    else:
        read_path = "READ? / DATA2?" if ratio_metadata else "READ?"
    cleanup_steps = [
        "wait for worker",
        "release_to_local",
        "close",
        "cleanup_release_to_local",
        "stop_http_server",
    ]
    notes: list[str] = []
    if buffer_warnings:
        notes.extend(buffer_warnings)
    if trigger_mode.endswith("-custom"):
        notes.append("buffered drain uses DATA:POINts? and DATA:REMove?")
    if ratio_metadata:
        notes.append(
            "voltage-dc-ratio stores DATA2? signal/reference voltage in measurement_metadata"
        )
        if trigger_mode.endswith("-custom"):
            notes.append(
                "voltage-dc-ratio buffered drain uses DATA:REMove? 1 plus DATA2? per sample"
            )
    if trigger_mode == "external":
        notes.append("hardware trigger uses INIT + status-byte polling before FETC?")
    if trigger_mode == "software-custom":
        notes.append("software-custom uses BUS trigger plus *TRG")
    if trigger_mode == "immediate-custom":
        notes.append("immediate-custom uses IMM trigger source")
    if args.simulate:
        notes.append("simulate uses deterministic fake instrument values")
    return StartPlan(
        trigger_mode=trigger_mode,
        measurement_type=measurement_type,
        measurement_name=measurement_def.canonical_name,
        measurement_unit=measurement_def.unit,
        csv_path=csv_path,
        resource=args.resource,
        simulate=args.simulate,
        dry_run=args.dry_run,
        scpi_commands=scpi_commands,
        read_path=read_path,
        cleanup_steps=cleanup_steps,
        notes=notes,
    )
