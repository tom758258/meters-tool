from __future__ import annotations

import unittest

from keysight_logger.core.models import InstrumentConfig
from keysight_logger.core.simulator import SimulatedVisaInstrument


class SimulatedVisaInstrumentTests(unittest.TestCase):
    def test_read_path_returns_deterministic_values(self):
        instrument = SimulatedVisaInstrument(
            InstrumentConfig(resource_string="SIM::34461A"),
            measurement_type="voltage_dc",
        )

        self.assertEqual("SIM::34461A", instrument.resource_id)
        self.assertEqual(1.23, instrument.query_ascii_float("READ?"))
        self.assertEqual(2.23, instrument.query_ascii_float("READ?"))

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


if __name__ == "__main__":
    unittest.main()
