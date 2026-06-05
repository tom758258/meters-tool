from __future__ import annotations

from dataclasses import dataclass

from .measurement import get_measurement_definition
from .models import InstrumentProfile, get_default_instrument_profile
from .validation import (
    AUTO_ZERO_MEASUREMENTS,
    CURRENT_MEASUREMENTS,
    DCV_INPUT_IMPEDANCE_MEASUREMENTS,
    DCV_INPUT_IMPEDANCE_OPTIONS,
    supported_measurement_types,
)


@dataclass(frozen=True)
class MeasurementCapability:
    measurement_name: str
    measurement_type: str
    unit: str
    range_values: tuple[float, ...]
    nplc_values: tuple[float, ...]
    ac_bandwidth_hz_values: tuple[float, ...]
    current_terminal_values: tuple[int, ...]
    dcv_input_impedance_values: tuple[str, ...]
    auto_zero_values: tuple[str, ...]


@dataclass(frozen=True)
class CoreCapabilities:
    vendor: str
    model: str
    aliases: tuple[str, ...]
    reading_memory_limit: int
    trigger_modes: tuple[str, ...]
    measurements: tuple[MeasurementCapability, ...]


def _auto_zero_values(measurement_type: str) -> tuple[str, ...]:
    if measurement_type in AUTO_ZERO_MEASUREMENTS:
        return ("on", "off", "once")
    if measurement_type == "voltage_dc_ratio":
        return ("on",)
    return ()


def _dcv_input_impedance_values(measurement_type: str) -> tuple[str, ...]:
    if measurement_type in DCV_INPUT_IMPEDANCE_MEASUREMENTS:
        return DCV_INPUT_IMPEDANCE_OPTIONS
    return ()


def _trigger_modes(profile: InstrumentProfile) -> tuple[str, ...]:
    modes = ["software", "immediate"]
    if profile.supports_external_trigger:
        modes.append("external")
    if profile.supports_buffered_reading_memory:
        modes.append("immediate-custom")
        if profile.supports_bus_trigger:
            modes.append("software-custom")
        if profile.supports_external_trigger:
            modes.append("external-custom")
    return tuple(modes)


def get_core_capabilities(profile: InstrumentProfile | None = None) -> CoreCapabilities:
    effective_profile = profile or get_default_instrument_profile()
    measurement_capabilities: list[MeasurementCapability] = []
    for measurement_type in supported_measurement_types(effective_profile):
        options = effective_profile.get_measurement_options(measurement_type)
        definition = get_measurement_definition(measurement_type)
        current_terminal_values = (
            options.current_terminal_options if measurement_type in CURRENT_MEASUREMENTS else ()
        )
        measurement_capabilities.append(
            MeasurementCapability(
                measurement_name=definition.canonical_name,
                measurement_type=definition.internal_type,
                unit=definition.unit,
                range_values=tuple(value for _label, value in options.range_options),
                nplc_values=options.nplc_options,
                ac_bandwidth_hz_values=options.ac_bandwidth_hz_options,
                current_terminal_values=current_terminal_values,
                dcv_input_impedance_values=_dcv_input_impedance_values(measurement_type),
                auto_zero_values=_auto_zero_values(measurement_type),
            )
        )
    return CoreCapabilities(
        vendor=effective_profile.vendor,
        model=effective_profile.model,
        aliases=effective_profile.aliases,
        reading_memory_limit=effective_profile.reading_memory_limit,
        trigger_modes=_trigger_modes(effective_profile),
        measurements=tuple(measurement_capabilities),
    )
