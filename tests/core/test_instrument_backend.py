from __future__ import annotations

import unittest

from keysight_logger_core.instrument import VisaInstrument
from keysight_logger_core.instrument_backend import (
    InstrumentBackend,
    create_instrument_backend,
)
from keysight_logger_core.models import InstrumentConfig
from keysight_logger_core.simulator import SimulatedVisaInstrument


class FakeVisaSession:
    def __init__(self) -> None:
        self.timeout = None
        self.writes: list[str] = []
        self.closed = False

    def query(self, command: str) -> str:
        self.writes.append(f"query:{command}")
        if command == "*IDN?":
            return "Keysight Technologies,34461A,MY123,1.0"
        return "1.23"

    def write(self, command: str) -> None:
        self.writes.append(command)

    def read_stb(self) -> int:
        return 32

    def close(self) -> None:
        self.closed = True


class FakeResourceManager:
    def __init__(self, session: FakeVisaSession) -> None:
        self.session = session
        self.opened_resources: list[str] = []
        self.closed = False

    def open_resource(self, resource: str) -> FakeVisaSession:
        self.opened_resources.append(resource)
        return self.session

    def close(self) -> None:
        self.closed = True


class InstrumentBackendTests(unittest.TestCase):
    def test_visa_instrument_satisfies_backend_protocol(self) -> None:
        instrument = VisaInstrument(InstrumentConfig(resource_string="USB::FAKE"))

        self.assertIsInstance(instrument, InstrumentBackend)

    def test_simulated_instrument_satisfies_backend_protocol(self) -> None:
        instrument = SimulatedVisaInstrument(InstrumentConfig(resource_string="SIM::34461A"))

        self.assertIsInstance(instrument, InstrumentBackend)

    def test_factory_returns_simulator_with_measurement_type(self) -> None:
        instrument = create_instrument_backend(
            InstrumentConfig(resource_string="SIM::34461A"),
            simulate=True,
            measurement_type="voltage_dc",
        )

        self.assertIsInstance(instrument, SimulatedVisaInstrument)
        self.assertEqual("voltage_dc", instrument._state.measurement_type)

    def test_factory_returns_visa_with_resource_manager_factory(self) -> None:
        session = FakeVisaSession()
        resource_manager = FakeResourceManager(session)
        instrument = create_instrument_backend(
            InstrumentConfig(resource_string="USB::FAKE", timeout_ms=4321),
            simulate=False,
            measurement_type="current_dc",
            resource_manager_factory=lambda: resource_manager,
        )

        self.assertIsInstance(instrument, VisaInstrument)
        instrument.connect()

        self.assertEqual(["USB::FAKE"], resource_manager.opened_resources)
        self.assertEqual(4321, session.timeout)
        self.assertEqual(["query:*IDN?", "*CLS", "*RST"], session.writes)


if __name__ == "__main__":
    unittest.main()
