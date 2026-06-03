from __future__ import annotations

import unittest

from keysight_logger.measurement import (
    CurrentMeasurement,
    VoltageDcMeasurement,
    create_measurement_plugin,
)
from keysight_logger.models import AcquisitionConfig, TriggerEvent, TriggerSource


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


class MeasurementFactoryTests(unittest.TestCase):
    def test_create_current_measurement_plugin(self):
        self.assertIsInstance(create_measurement_plugin("current-dc"), CurrentMeasurement)

    def test_create_voltage_measurement_plugin(self):
        self.assertIsInstance(create_measurement_plugin("voltage-dc"), VoltageDcMeasurement)

    def test_unsupported_measurement_plugin_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported measurement type"):
            create_measurement_plugin("resistance-2w")


if __name__ == "__main__":
    unittest.main()
