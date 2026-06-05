from __future__ import annotations


def test_legacy_core_module_import_paths_are_compatible():
    from keysight_logger import acquisition as legacy_acquisition
    from keysight_logger import instrument as legacy_instrument
    from keysight_logger import instrument_backend as legacy_instrument_backend
    from keysight_logger import measurement as legacy_measurement
    from keysight_logger import models as legacy_models
    from keysight_logger import simulator as legacy_simulator
    from keysight_logger import storage as legacy_storage
    from keysight_logger import trigger as legacy_trigger
    from keysight_logger.core import acquisition as core_acquisition
    from keysight_logger.core import instrument as core_instrument
    from keysight_logger.core import instrument_backend as core_instrument_backend
    from keysight_logger.core import measurement as core_measurement
    from keysight_logger.core import models as core_models
    from keysight_logger.core import simulator as core_simulator
    from keysight_logger.core import storage as core_storage
    from keysight_logger.core import trigger as core_trigger

    assert legacy_acquisition.TriggerAcquisitionEngine is core_acquisition.TriggerAcquisitionEngine
    assert legacy_instrument.VisaInstrument is core_instrument.VisaInstrument
    assert legacy_instrument_backend.create_instrument_backend is core_instrument_backend.create_instrument_backend
    assert legacy_measurement.create_measurement_plugin is core_measurement.create_measurement_plugin
    assert legacy_models.InstrumentConfig is core_models.InstrumentConfig
    assert legacy_simulator.SimulatedVisaInstrument is core_simulator.SimulatedVisaInstrument
    assert legacy_storage.CsvWriter is core_storage.CsvWriter
    assert legacy_trigger.TriggerRouter is core_trigger.TriggerRouter
