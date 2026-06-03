from __future__ import annotations

import unittest

from keysight_logger.measurement import CurrentMeasurement
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

    def test_immediate_trigger_reads_with_read_query(self):
        inst = FakeInstrument()
        measurement = CurrentMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        sample = measurement.read_sample(inst, TriggerEvent.new(TriggerSource.IMMEDIATE))

        self.assertEqual(1.23, sample.value)
        self.assertEqual("READ?", inst.commands[-1])

    def test_immediate_buffered_configures_sample_count_and_immediate_trigger(self):
        inst = FakeInstrument()
        measurement = CurrentMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        measurement.configure_immediate_buffered(inst, AcquisitionConfig(), sample_count=3)
        measurement.start_buffered_capture(inst)

        self.assertIn("TRIG:SOUR IMM", inst.commands)
        self.assertIn("TRIG:COUNT 1", inst.commands)
        self.assertIn("SAMP:COUNT 3", inst.commands)
        self.assertEqual("INIT", inst.commands[-1])

    def test_immediate_buffered_reads_and_removes_available_points(self):
        inst = FakeInstrument()
        inst.responses["DATA:POINts?"] = "2"
        inst.responses["DATA:REMove? 2"] = "1.1,2.2"
        measurement = CurrentMeasurement()
        measurement.configure(inst, AcquisitionConfig())

        available = measurement.buffered_points_available(inst)
        samples = measurement.read_buffered_samples(
            inst,
            TriggerEvent.new(TriggerSource.IMMEDIATE_BUFFERED),
            count=2,
            first_sample_index=5,
        )

        self.assertEqual(2, available)
        self.assertEqual([1.1, 2.2], [sample.value for sample in samples])
        self.assertEqual(
            ["immediate-buffered", "immediate-buffered"],
            [sample.trigger_source for sample in samples],
        )
        self.assertEqual("5", samples[0].trigger_metadata["buffer_index"])
        self.assertEqual("6", samples[1].trigger_metadata["buffer_index"])
        self.assertEqual(
            "pc_data_remove_time_not_instrument_sample_time",
            samples[0].trigger_metadata["time_basis"],
        )

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


if __name__ == "__main__":
    unittest.main()
