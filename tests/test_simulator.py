from __future__ import annotations

import unittest

from keysight_logger.models import InstrumentConfig
from keysight_logger.simulator import SimulatedVisaInstrument


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


if __name__ == "__main__":
    unittest.main()
