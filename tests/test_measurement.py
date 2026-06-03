from __future__ import annotations

import unittest

from keysight_logger.measurement import CurrentMeasurement
from keysight_logger.models import AcquisitionConfig, TriggerEvent, TriggerSource


class FakeInstrument:
    def __init__(self) -> None:
        self.resource_id = "USB::FAKE"
        self.commands: list[str] = []

    def write(self, command: str) -> None:
        self.commands.append(command)

    def query_ascii_float(self, command: str) -> float:
        self.commands.append(command)
        return 1.23


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
