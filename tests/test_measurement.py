from __future__ import annotations

import unittest

from keysight_logger.core.measurement import (
    CurrentAcMeasurement,
    CurrentDcMeasurement,
    CurrentMeasurement,
    Resistance2wMeasurement,
    Resistance4wMeasurement,
    ScalarDmmMeasurement,
    VoltageAcMeasurement,
    VoltageDcMeasurement,
    create_measurement_plugin,
    format_measurement_type,
    get_measurement_definition,
    normalize_measurement_type,
    registered_measurement_types,
)
from keysight_logger.core.models import AcquisitionConfig, TriggerEvent, TriggerSource


class FakeInstrument:
    def __init__(self) -> None:
        self.resource_id = "USB::FAKE"
        self.commands: list[str] = []
        self.responses: dict[str, str] = {}

    def write(self, command: str) -> None:
        self.commands.append(command)

    def query_ascii_float(self, command: str) -> float:
        self.commands.append(command)
        return 1.23

    def query(self, command: str) -> str:
        self.commands.append(command)
        return self.responses[command]


class CurrentMeasurementTests(unittest.TestCase):
    def test_current_compatibility_alias_is_preserved(self):
        self.assertIs(CurrentMeasurement, CurrentDcMeasurement)

    def test_auto_range_writes_current_scpi(self):
        inst = FakeInstrument()
        measurement = CurrentMeasurement()

        measurement.configure(inst, AcquisitionConfig())

        self.assertEqual(
            [
                "CONF:CURR:DC AUTO",
                "CURR:DC:RANG:AUTO ON",
                "CURR:DC:NPLC 1.0",
                "ZERO:AUTO ON",
            ],
            inst.commands,
        )

    def test_hardware_trigger_reads_with_fetch(self):
        inst = FakeInstrument()
        measurement = CurrentMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        sample = measurement.read_sample(inst, TriggerEvent.new(TriggerSource.HARDWARE))

        self.assertEqual(1.23, sample.value)
        self.assertEqual("FETC?", inst.commands[-1])

    def test_software_trigger_reads_with_read_query(self):
        inst = FakeInstrument()
        measurement = CurrentMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        sample = measurement.read_sample(inst, TriggerEvent.new(TriggerSource.SOFTWARE))

        self.assertEqual(1.23, sample.value)
        self.assertEqual("READ?", inst.commands[-1])

    def test_trigger_metadata_is_copied_to_sample(self):
        inst = FakeInstrument()
        measurement = CurrentMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        sample = measurement.read_sample(
            inst,
            TriggerEvent.new(TriggerSource.SOFTWARE, {"batch": "A1"}),
        )

        self.assertEqual({"batch": "A1"}, sample.trigger_metadata)

    def test_manual_measurement_range_writes_current_range_scpi(self):
        inst = FakeInstrument()
        measurement = CurrentMeasurement()

        measurement.configure(inst, AcquisitionConfig(auto_range=False, measurement_range=0.1))

        self.assertIn("CURR:DC:RANG 0.1", inst.commands)

    def test_current_range_alias_writes_same_current_range_scpi(self):
        inst = FakeInstrument()
        measurement = CurrentMeasurement()

        measurement.configure(inst, AcquisitionConfig(auto_range=False, current_range=0.1))

        self.assertIn("CURR:DC:RANG 0.1", inst.commands)

    def test_auto_zero_once_writes_current_once_scpi(self):
        inst = FakeInstrument()
        measurement = CurrentMeasurement()

        measurement.configure(inst, AcquisitionConfig(auto_zero="once"))

        self.assertIn("ZERO:AUTO ONCE", inst.commands)

    def test_current_terminal_10_writes_terminal_without_10a_range_scpi(self):
        inst = FakeInstrument()
        measurement = CurrentMeasurement()

        measurement.configure(
            inst,
            AcquisitionConfig(
                auto_range=False,
                measurement_range=10.0,
                current_terminal=10,
            ),
        )

        self.assertIn("CURR:DC:TERM 10", inst.commands)
        self.assertNotIn("CURR:DC:RANG 10.0", inst.commands)

    def test_immediate_trigger_reads_with_read_query(self):
        inst = FakeInstrument()
        measurement = CurrentMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        sample = measurement.read_sample(inst, TriggerEvent.new(TriggerSource.IMMEDIATE))

        self.assertEqual(1.23, sample.value)
        self.assertEqual("READ?", inst.commands[-1])

    def test_immediate_custom_configures_trigger_and_sample_count(self):
        inst = FakeInstrument()
        measurement = CurrentMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        measurement.configure_immediate_custom(
            inst,
            AcquisitionConfig(),
            trigger_count=2,
            sample_count=3,
        )
        measurement.start_buffered_capture(inst)

        self.assertIn("TRIG:SOUR IMM", inst.commands)
        self.assertIn("TRIG:COUNT 2", inst.commands)
        self.assertIn("SAMP:COUNT 3", inst.commands)
        self.assertEqual("INIT", inst.commands[-1])

    def test_software_custom_configures_bus_trigger_and_sample_count(self):
        inst = FakeInstrument()
        measurement = CurrentMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        measurement.configure_software_custom(
            inst,
            AcquisitionConfig(),
            trigger_count=2,
            sample_count=3,
        )
        measurement.start_buffered_capture(inst)
        measurement.send_bus_trigger(inst)

        self.assertIn("TRIG:SOUR BUS", inst.commands)
        self.assertIn("TRIG:COUNT 2", inst.commands)
        self.assertIn("SAMP:COUNT 3", inst.commands)
        self.assertEqual("*TRG", inst.commands[-1])

    def test_external_custom_configures_external_trigger_and_sample_count(self):
        inst = FakeInstrument()
        measurement = CurrentMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        measurement.configure_external_custom(
            inst,
            AcquisitionConfig(),
            trigger_count=2,
            sample_count=3,
            slope="pos",
            delay_s=0.25,
        )
        measurement.start_buffered_capture(inst)

        self.assertIn("TRIG:SOUR EXT", inst.commands)
        self.assertIn("TRIG:SLOP POS", inst.commands)
        self.assertIn("TRIG:COUNT 2", inst.commands)
        self.assertIn("SAMP:COUNT 3", inst.commands)
        self.assertIn("TRIG:DEL 0.25", inst.commands)
        self.assertEqual("INIT", inst.commands[-1])

    def test_immediate_custom_reads_and_removes_available_points(self):
        inst = FakeInstrument()
        inst.responses["DATA:POINts?"] = "2"
        inst.responses["DATA:REMove? 2"] = "1.1,2.2"
        measurement = CurrentMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        available = measurement.buffered_points_available(inst)
        samples = measurement.read_buffered_samples(
            inst,
            TriggerEvent.new(TriggerSource.IMMEDIATE_CUSTOM),
            count=2,
            first_sample_index=5,
        )

        self.assertEqual(2, available)
        self.assertEqual([1.1, 2.2], [sample.value for sample in samples])
        self.assertEqual(
            ["immediate-custom", "immediate-custom"],
            [sample.trigger_source for sample in samples],
        )
        self.assertEqual("5", samples[0].trigger_metadata["buffer_index"])
        self.assertEqual("6", samples[1].trigger_metadata["buffer_index"])
        self.assertEqual(
            "pc_data_remove_time_not_instrument_sample_time",
            samples[0].trigger_metadata["time_basis"],
        )

    def test_software_custom_buffered_samples_use_software_custom_source(self):
        inst = FakeInstrument()
        inst.responses["DATA:REMove? 1"] = "1.1"
        measurement = CurrentMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        samples = measurement.read_buffered_samples(
            inst,
            TriggerEvent.new(TriggerSource.SOFTWARE_CUSTOM),
            count=1,
            first_sample_index=0,
        )

        self.assertEqual(["software-custom"], [sample.trigger_source for sample in samples])

    def test_external_custom_buffered_samples_use_external_custom_source(self):
        inst = FakeInstrument()
        inst.responses["DATA:REMove? 1"] = "1.1"
        measurement = CurrentMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        samples = measurement.read_buffered_samples(
            inst,
            TriggerEvent.new(TriggerSource.EXTERNAL_CUSTOM),
            count=1,
            first_sample_index=0,
        )

        self.assertEqual(["external-custom"], [sample.trigger_source for sample in samples])

    def test_timer_trigger_reads_with_read_query(self):
        inst = FakeInstrument()
        measurement = CurrentMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        sample = measurement.read_sample(inst, TriggerEvent.new(TriggerSource.TIMER))

        self.assertEqual(1.23, sample.value)
        self.assertEqual("READ?", inst.commands[-1])

    def test_vm_comp_slope_is_left_unchanged_by_default(self):
        inst = FakeInstrument()
        measurement = CurrentMeasurement()

        measurement.configure(inst, AcquisitionConfig())

        self.assertNotIn("OUTP:TRIG:SLOP POS", inst.commands)
        self.assertNotIn("OUTP:TRIG:SLOP NEG", inst.commands)

    def test_vm_comp_slope_writes_output_trigger_slope(self):
        inst = FakeInstrument()
        measurement = CurrentMeasurement()

        measurement.configure(inst, AcquisitionConfig(vm_comp_slope="pos"))

        self.assertIn("OUTP:TRIG:SLOP POS", inst.commands)

    def test_invalid_vm_comp_slope_is_rejected(self):
        inst = FakeInstrument()
        measurement = CurrentMeasurement()

        with self.assertRaises(ValueError):
            measurement.configure(inst, AcquisitionConfig(vm_comp_slope="rising"))


class VoltageDcMeasurementTests(unittest.TestCase):
    def test_voltage_uses_scalar_base_without_inheriting_current(self):
        measurement = VoltageDcMeasurement()

        self.assertIsInstance(measurement, ScalarDmmMeasurement)
        self.assertNotIsInstance(measurement, CurrentMeasurement)

    def test_auto_range_writes_voltage_scpi(self):
        inst = FakeInstrument()
        measurement = VoltageDcMeasurement()

        measurement.configure(inst, AcquisitionConfig())

        self.assertEqual(
            [
                "CONF:VOLT:DC AUTO",
                "VOLT:DC:RANG:AUTO ON",
                "VOLT:DC:NPLC 1.0",
                "VOLT:DC:ZERO:AUTO ON",
            ],
            inst.commands,
        )

    def test_manual_range_writes_voltage_range_scpi(self):
        inst = FakeInstrument()
        measurement = VoltageDcMeasurement()

        measurement.configure(
            inst,
            AcquisitionConfig(auto_range=False, measurement_range=10.0, auto_zero=False),
        )

        self.assertEqual(
            [
                "CONF:VOLT:DC AUTO",
                "VOLT:DC:RANG 10.0",
                "VOLT:DC:NPLC 1.0",
                "VOLT:DC:ZERO:AUTO OFF",
            ],
            inst.commands,
        )

    def test_auto_zero_once_writes_voltage_once_scpi(self):
        inst = FakeInstrument()
        measurement = VoltageDcMeasurement()

        measurement.configure(inst, AcquisitionConfig(auto_zero="once"))

        self.assertIn("VOLT:DC:ZERO:AUTO ONCE", inst.commands)

    def test_voltage_dc_input_impedance_10m_writes_auto_off(self):
        inst = FakeInstrument()
        measurement = VoltageDcMeasurement()

        measurement.configure(inst, AcquisitionConfig(dcv_input_impedance="10m"))

        self.assertEqual(
            [
                "CONF:VOLT:DC AUTO",
                "VOLT:DC:RANG:AUTO ON",
                "VOLT:DC:IMP:AUTO OFF",
                "VOLT:DC:NPLC 1.0",
                "VOLT:DC:ZERO:AUTO ON",
            ],
            inst.commands,
        )

    def test_voltage_dc_input_impedance_auto_writes_auto_on(self):
        inst = FakeInstrument()
        measurement = VoltageDcMeasurement()

        measurement.configure(inst, AcquisitionConfig(dcv_input_impedance="auto"))

        self.assertEqual(
            [
                "CONF:VOLT:DC AUTO",
                "VOLT:DC:RANG:AUTO ON",
                "VOLT:DC:IMP:AUTO ON",
                "VOLT:DC:NPLC 1.0",
                "VOLT:DC:ZERO:AUTO ON",
            ],
            inst.commands,
        )

    def test_read_sample_uses_voltage_metadata_and_fetch_for_hardware(self):
        inst = FakeInstrument()
        measurement = VoltageDcMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        sample = measurement.read_sample(inst, TriggerEvent.new(TriggerSource.HARDWARE))

        self.assertEqual("voltage_dc", sample.measurement_type)
        self.assertEqual("V", sample.unit)
        self.assertEqual(1.23, sample.value)
        self.assertEqual("FETC?", inst.commands[-1])

    def test_buffered_samples_use_voltage_metadata(self):
        inst = FakeInstrument()
        inst.responses["DATA:REMove? 1"] = "5.5"
        measurement = VoltageDcMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        samples = measurement.read_buffered_samples(
            inst,
            TriggerEvent.new(TriggerSource.IMMEDIATE_CUSTOM),
            count=1,
            first_sample_index=0,
        )

        self.assertEqual("voltage_dc", samples[0].measurement_type)
        self.assertEqual("V", samples[0].unit)
        self.assertEqual(5.5, samples[0].value)

    def test_vm_comp_slope_writes_output_trigger_slope(self):
        inst = FakeInstrument()
        measurement = VoltageDcMeasurement()

        measurement.configure(inst, AcquisitionConfig(vm_comp_slope="neg"))

        self.assertIn("OUTP:TRIG:SLOP NEG", inst.commands)


class CurrentAcMeasurementTests(unittest.TestCase):
    def test_current_ac_uses_scalar_base_without_inheriting_dc_current(self):
        measurement = CurrentAcMeasurement()

        self.assertIsInstance(measurement, ScalarDmmMeasurement)
        self.assertNotIsInstance(measurement, CurrentMeasurement)

    def test_auto_range_writes_current_ac_scpi_without_dc_only_settings(self):
        inst = FakeInstrument()
        measurement = CurrentAcMeasurement()

        measurement.configure(inst, AcquisitionConfig(nplc=10.0, auto_zero=False))

        self.assertEqual(
            [
                "CONF:CURR:AC AUTO",
                "CURR:AC:RANG:AUTO ON",
            ],
            inst.commands,
        )

    def test_manual_range_writes_current_ac_range_scpi(self):
        inst = FakeInstrument()
        measurement = CurrentAcMeasurement()

        measurement.configure(
            inst,
            AcquisitionConfig(auto_range=False, measurement_range=0.1),
        )

        self.assertEqual(
            [
                "CONF:CURR:AC AUTO",
                "CURR:AC:RANG 0.1",
            ],
            inst.commands,
        )

    def test_ac_bandwidth_writes_current_ac_bandwidth_scpi(self):
        inst = FakeInstrument()
        measurement = CurrentAcMeasurement()

        measurement.configure(inst, AcquisitionConfig(ac_bandwidth_hz=3.0))

        self.assertIn("CURR:AC:BAND 3", inst.commands)

    def test_current_ac_terminal_10_writes_terminal_without_10a_range_scpi(self):
        inst = FakeInstrument()
        measurement = CurrentAcMeasurement()

        measurement.configure(
            inst,
            AcquisitionConfig(
                auto_range=False,
                measurement_range=10.0,
                current_terminal=10,
            ),
        )

        self.assertIn("CURR:AC:TERM 10", inst.commands)
        self.assertNotIn("CURR:AC:RANG 10.0", inst.commands)

    def test_read_sample_uses_current_ac_metadata_and_fetch_for_hardware(self):
        inst = FakeInstrument()
        measurement = CurrentAcMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        sample = measurement.read_sample(inst, TriggerEvent.new(TriggerSource.HARDWARE))

        self.assertEqual("current_ac", sample.measurement_type)
        self.assertEqual("A", sample.unit)
        self.assertEqual(1.23, sample.value)
        self.assertEqual("FETC?", inst.commands[-1])

    def test_buffered_samples_use_current_ac_metadata(self):
        inst = FakeInstrument()
        inst.responses["DATA:REMove? 1"] = "0.12"
        measurement = CurrentAcMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        samples = measurement.read_buffered_samples(
            inst,
            TriggerEvent.new(TriggerSource.IMMEDIATE_CUSTOM),
            count=1,
            first_sample_index=0,
        )

        self.assertEqual("current_ac", samples[0].measurement_type)
        self.assertEqual("A", samples[0].unit)
        self.assertEqual(0.12, samples[0].value)

    def test_vm_comp_slope_writes_output_trigger_slope(self):
        inst = FakeInstrument()
        measurement = CurrentAcMeasurement()

        measurement.configure(inst, AcquisitionConfig(vm_comp_slope="pos"))

        self.assertIn("OUTP:TRIG:SLOP POS", inst.commands)


class VoltageAcMeasurementTests(unittest.TestCase):
    def test_voltage_ac_uses_scalar_base_without_inheriting_current(self):
        measurement = VoltageAcMeasurement()

        self.assertIsInstance(measurement, ScalarDmmMeasurement)
        self.assertNotIsInstance(measurement, CurrentMeasurement)

    def test_auto_range_writes_voltage_ac_scpi_without_dc_only_settings(self):
        inst = FakeInstrument()
        measurement = VoltageAcMeasurement()

        measurement.configure(inst, AcquisitionConfig(nplc=10.0, auto_zero=False))

        self.assertEqual(
            [
                "CONF:VOLT:AC AUTO",
                "VOLT:AC:RANG:AUTO ON",
            ],
            inst.commands,
        )

    def test_manual_range_writes_voltage_ac_range_scpi(self):
        inst = FakeInstrument()
        measurement = VoltageAcMeasurement()

        measurement.configure(
            inst,
            AcquisitionConfig(auto_range=False, measurement_range=10.0),
        )

        self.assertEqual(
            [
                "CONF:VOLT:AC AUTO",
                "VOLT:AC:RANG 10.0",
            ],
            inst.commands,
        )

    def test_ac_bandwidth_writes_voltage_ac_bandwidth_scpi(self):
        inst = FakeInstrument()
        measurement = VoltageAcMeasurement()

        measurement.configure(inst, AcquisitionConfig(ac_bandwidth_hz=200.0))

        self.assertIn("VOLT:AC:BAND 200", inst.commands)

    def test_read_sample_uses_voltage_ac_metadata_and_fetch_for_hardware(self):
        inst = FakeInstrument()
        measurement = VoltageAcMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        sample = measurement.read_sample(inst, TriggerEvent.new(TriggerSource.HARDWARE))

        self.assertEqual("voltage_ac", sample.measurement_type)
        self.assertEqual("V", sample.unit)
        self.assertEqual(1.23, sample.value)
        self.assertEqual("FETC?", inst.commands[-1])

    def test_buffered_samples_use_voltage_ac_metadata(self):
        inst = FakeInstrument()
        inst.responses["DATA:REMove? 1"] = "12.5"
        measurement = VoltageAcMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        samples = measurement.read_buffered_samples(
            inst,
            TriggerEvent.new(TriggerSource.IMMEDIATE_CUSTOM),
            count=1,
            first_sample_index=0,
        )

        self.assertEqual("voltage_ac", samples[0].measurement_type)
        self.assertEqual("V", samples[0].unit)
        self.assertEqual(12.5, samples[0].value)

    def test_vm_comp_slope_writes_output_trigger_slope(self):
        inst = FakeInstrument()
        measurement = VoltageAcMeasurement()

        measurement.configure(inst, AcquisitionConfig(vm_comp_slope="neg"))

        self.assertIn("OUTP:TRIG:SLOP NEG", inst.commands)


class Resistance2wMeasurementTests(unittest.TestCase):
    def test_resistance_2w_uses_scalar_base_without_inheriting_current(self):
        measurement = Resistance2wMeasurement()

        self.assertIsInstance(measurement, ScalarDmmMeasurement)
        self.assertNotIsInstance(measurement, CurrentMeasurement)

    def test_auto_range_writes_resistance_scpi(self):
        inst = FakeInstrument()
        measurement = Resistance2wMeasurement()

        measurement.configure(inst, AcquisitionConfig())

        self.assertEqual(
            [
                "CONF:RES AUTO",
                "RES:RANG:AUTO ON",
                "RES:NPLC 1.0",
                "RES:ZERO:AUTO ON",
            ],
            inst.commands,
        )

    def test_manual_range_writes_resistance_range_scpi(self):
        inst = FakeInstrument()
        measurement = Resistance2wMeasurement()

        measurement.configure(
            inst,
            AcquisitionConfig(auto_range=False, measurement_range=1000.0, auto_zero=False),
        )

        self.assertEqual(
            [
                "CONF:RES AUTO",
                "RES:RANG 1000.0",
                "RES:NPLC 1.0",
                "RES:ZERO:AUTO OFF",
            ],
            inst.commands,
        )

    def test_auto_zero_once_writes_resistance_once_scpi(self):
        inst = FakeInstrument()
        measurement = Resistance2wMeasurement()

        measurement.configure(inst, AcquisitionConfig(auto_zero="once"))

        self.assertIn("RES:ZERO:AUTO ONCE", inst.commands)

    def test_read_sample_uses_resistance_metadata_and_fetch_for_hardware(self):
        inst = FakeInstrument()
        measurement = Resistance2wMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        sample = measurement.read_sample(inst, TriggerEvent.new(TriggerSource.HARDWARE))

        self.assertEqual("resistance_2w", sample.measurement_type)
        self.assertEqual("Ohm", sample.unit)
        self.assertEqual(1.23, sample.value)
        self.assertEqual("FETC?", inst.commands[-1])

    def test_buffered_samples_use_resistance_metadata(self):
        inst = FakeInstrument()
        inst.responses["DATA:REMove? 1"] = "123.4"
        measurement = Resistance2wMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        samples = measurement.read_buffered_samples(
            inst,
            TriggerEvent.new(TriggerSource.IMMEDIATE_CUSTOM),
            count=1,
            first_sample_index=0,
        )

        self.assertEqual("resistance_2w", samples[0].measurement_type)
        self.assertEqual("Ohm", samples[0].unit)
        self.assertEqual(123.4, samples[0].value)

    def test_vm_comp_slope_writes_output_trigger_slope(self):
        inst = FakeInstrument()
        measurement = Resistance2wMeasurement()

        measurement.configure(inst, AcquisitionConfig(vm_comp_slope="pos"))

        self.assertIn("OUTP:TRIG:SLOP POS", inst.commands)


class Resistance4wMeasurementTests(unittest.TestCase):
    def test_resistance_4w_uses_scalar_base_without_inheriting_current(self):
        measurement = Resistance4wMeasurement()

        self.assertIsInstance(measurement, ScalarDmmMeasurement)
        self.assertNotIsInstance(measurement, CurrentMeasurement)

    def test_auto_range_writes_resistance_4w_scpi(self):
        inst = FakeInstrument()
        measurement = Resistance4wMeasurement()

        measurement.configure(inst, AcquisitionConfig())

        self.assertEqual(
            [
                "CONF:FRES AUTO",
                "FRES:RANG:AUTO ON",
                "FRES:NPLC 1.0",
            ],
            inst.commands,
        )

    def test_manual_range_writes_resistance_4w_range_scpi(self):
        inst = FakeInstrument()
        measurement = Resistance4wMeasurement()

        measurement.configure(
            inst,
            AcquisitionConfig(auto_range=False, measurement_range=1000.0, auto_zero=False),
        )

        self.assertEqual(
            [
                "CONF:FRES AUTO",
                "FRES:RANG 1000.0",
                "FRES:NPLC 1.0",
            ],
            inst.commands,
        )

    def test_read_sample_uses_resistance_4w_metadata_and_fetch_for_hardware(self):
        inst = FakeInstrument()
        measurement = Resistance4wMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        sample = measurement.read_sample(inst, TriggerEvent.new(TriggerSource.HARDWARE))

        self.assertEqual("resistance_4w", sample.measurement_type)
        self.assertEqual("Ohm", sample.unit)
        self.assertEqual(1.23, sample.value)
        self.assertEqual("FETC?", inst.commands[-1])

    def test_buffered_samples_use_resistance_4w_metadata(self):
        inst = FakeInstrument()
        inst.responses["DATA:REMove? 1"] = "123.4"
        measurement = Resistance4wMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        samples = measurement.read_buffered_samples(
            inst,
            TriggerEvent.new(TriggerSource.IMMEDIATE_CUSTOM),
            count=1,
            first_sample_index=0,
        )

        self.assertEqual("resistance_4w", samples[0].measurement_type)
        self.assertEqual("Ohm", samples[0].unit)
        self.assertEqual(123.4, samples[0].value)

    def test_vm_comp_slope_writes_output_trigger_slope(self):
        inst = FakeInstrument()
        measurement = Resistance4wMeasurement()

        measurement.configure(inst, AcquisitionConfig(vm_comp_slope="pos"))

        self.assertIn("OUTP:TRIG:SLOP POS", inst.commands)


class MeasurementFactoryTests(unittest.TestCase):
    def test_create_current_measurement_plugin(self):
        self.assertIsInstance(create_measurement_plugin("current-dc"), CurrentMeasurement)

    def test_create_current_measurement_plugin_from_internal_name(self):
        self.assertIsInstance(create_measurement_plugin("current_dc"), CurrentMeasurement)

    def test_create_voltage_measurement_plugin(self):
        self.assertIsInstance(create_measurement_plugin("voltage-dc"), VoltageDcMeasurement)

    def test_create_current_ac_measurement_plugin(self):
        self.assertIsInstance(create_measurement_plugin("current-ac"), CurrentAcMeasurement)

    def test_create_voltage_ac_measurement_plugin(self):
        self.assertIsInstance(create_measurement_plugin("voltage-ac"), VoltageAcMeasurement)

    def test_create_resistance_2w_measurement_plugin(self):
        self.assertIsInstance(create_measurement_plugin("resistance-2w"), Resistance2wMeasurement)

    def test_create_resistance_2w_measurement_plugin_from_internal_name(self):
        self.assertIsInstance(create_measurement_plugin("resistance_2w"), Resistance2wMeasurement)

    def test_create_resistance_4w_measurement_plugin(self):
        self.assertIsInstance(create_measurement_plugin("resistance-4w"), Resistance4wMeasurement)

    def test_create_resistance_4w_measurement_plugin_from_internal_name(self):
        self.assertIsInstance(create_measurement_plugin("resistance_4w"), Resistance4wMeasurement)

    def test_registry_exposes_current_voltage_and_resistance_definitions(self):
        self.assertEqual(
            (
                "current_dc",
                "voltage_dc",
                "current_ac",
                "voltage_ac",
                "resistance_2w",
                "resistance_4w",
            ),
            registered_measurement_types(),
        )
        self.assertEqual("current_dc", normalize_measurement_type("current-dc"))
        self.assertEqual("voltage-dc", format_measurement_type("voltage_dc"))
        self.assertEqual("current-ac", format_measurement_type("current_ac"))
        self.assertEqual("voltage-ac", format_measurement_type("voltage_ac"))
        self.assertEqual("resistance-2w", format_measurement_type("resistance_2w"))
        self.assertEqual("resistance-4w", format_measurement_type("resistance_4w"))
        self.assertEqual("current-dc", get_measurement_definition("current-dc").canonical_name)
        self.assertEqual("A", get_measurement_definition("current-dc").unit)
        self.assertEqual("A", get_measurement_definition("current-ac").unit)
        self.assertEqual("V", get_measurement_definition("voltage-ac").unit)
        self.assertEqual("Ohm", get_measurement_definition("resistance-2w").unit)
        self.assertEqual("Ohm", get_measurement_definition("resistance-4w").unit)
        self.assertTrue(get_measurement_definition("current-dc").accepts_current_range_alias)
        self.assertFalse(get_measurement_definition("current-ac").accepts_current_range_alias)
        self.assertFalse(get_measurement_definition("voltage-dc").accepts_current_range_alias)
        self.assertFalse(get_measurement_definition("voltage-ac").accepts_current_range_alias)
        self.assertFalse(get_measurement_definition("resistance-2w").accepts_current_range_alias)
        self.assertFalse(get_measurement_definition("resistance-4w").accepts_current_range_alias)

    def test_registry_keeps_only_logical_measurement_metadata(self):
        current_dc = get_measurement_definition("current-dc")

        self.assertFalse(hasattr(current_dc, "cli" + "_name"))
        self.assertFalse(hasattr(current_dc, "range_options"))
        self.assertFalse(hasattr(current_dc, "nplc_options"))

    def test_unsupported_measurement_plugin_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported measurement type"):
            create_measurement_plugin("capacitance")


if __name__ == "__main__":
    unittest.main()
