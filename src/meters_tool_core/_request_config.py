from __future__ import annotations

from .models import AcquisitionConfig, StartRequest
from .validation import resolve_measurement_range


def acquisition_config_from_start_request(
    request: StartRequest,
    measurement_type: str,
) -> AcquisitionConfig:
    return AcquisitionConfig(
        measurement_type=measurement_type,
        trigger_timeout_ms=request.trigger_timeout_ms,
        max_samples=request.max_samples,
        trigger_count=request.trigger_count,
        sample_count=request.sample_count,
        timer_interval_s=request.timer_interval_s,
        buffer_drain_size=request.buffer_drain_size,
        allow_buffer_overflow_risk=request.allow_buffer_overflow_risk,
        nplc=request.nplc,
        auto_zero=request.auto_zero,
        auto_range=request.auto_range,
        measurement_range=resolve_measurement_range(request),
        current_range=request.current_range,
        ac_bandwidth_hz=request.ac_bandwidth_hz,
        gate_time_s=request.gate_time_s,
        freq_period_timeout=request.freq_period_timeout,
        current_terminal=request.current_terminal,
        dcv_input_impedance=request.dcv_input_impedance,
        hw_trigger_delay_s=request.hw_trigger_delay_s,
        vm_comp_slope=request.vm_comp_slope,
    )
