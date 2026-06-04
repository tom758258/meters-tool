from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from keysight_logger.instrument import InstrumentError, VisaInstrument, is_pyvisa_timeout_error
from keysight_logger.models import InstrumentConfig, Transport


class FakeVisaSession:
    def __init__(self):
        self.timeout = None
        self.writes: list[str] = []
        self.closed = False
        self.cleared = False
        self.idn_response = " Keysight Technologies,34461A,MY123,1.0 \n"
        self.query_response = " Keysight Technologies,34461A,MY123,1.0 \n"
        self.status_byte = 32
        self.control_ren_calls: list[int] = []
        self.fail_query = False
        self.fail_clear = False
        self.fail_writes: set[str] = set()
        self.fail_control_ren_modes: set[int] = set()

    def write(self, command: str) -> None:
        if command in self.fail_writes:
            raise RuntimeError(f"write failed: {command}")
        self.writes.append(command)

    def query(self, command: str) -> str:
        if self.fail_query:
            raise RuntimeError("query failed")
        self.writes.append(f"query:{command}")
        if command == "*IDN?":
            return self.idn_response
        return self.query_response

    def read_stb(self) -> int:
        return self.status_byte

    def clear(self) -> None:
        if self.fail_clear:
            raise RuntimeError("clear failed")
        self.cleared = True

    def control_ren(self, mode: int) -> None:
        self.control_ren_calls.append(mode)
        if mode in self.fail_control_ren_modes:
            raise RuntimeError(f"control_ren failed: {mode}")

    def close(self) -> None:
        self.closed = True


class FakeResourceManager:
    def __init__(self, resources=("USB::FAKE",), session: FakeVisaSession | None = None):
        self.resources = resources
        self.session = session or FakeVisaSession()
        self.opened_resources: list[str] = []
        self.closed = False

    def list_resources(self):
        return self.resources

    def open_resource(self, resource: str):
        self.opened_resources.append(resource)
        return self.session

    def close(self) -> None:
        self.closed = True


class FakeVisaIOError(Exception):
    def __init__(self, error_code: int) -> None:
        super().__init__(f"visa error {error_code}")
        self.error_code = error_code


class VisaInstrumentStaticTests(unittest.TestCase):
    def test_pyvisa_unavailable_raises_instrument_error(self):
        with patch("keysight_logger.instrument.pyvisa", None):
            with self.assertRaisesRegex(InstrumentError, "pyvisa is not installed"):
                VisaInstrument.list_resources()

    def test_list_resources_returns_list_and_closes_resource_manager(self):
        rm = FakeResourceManager(resources=("USB::A", "TCPIP::B"))
        fake_pyvisa = SimpleNamespace(ResourceManager=lambda: rm)

        with patch("keysight_logger.instrument.pyvisa", fake_pyvisa):
            resources = VisaInstrument.list_resources()

        self.assertEqual(["USB::A", "TCPIP::B"], resources)
        self.assertTrue(rm.closed)

    def test_verify_resource_queries_idn_and_cleans_up(self):
        session = FakeVisaSession()
        rm = FakeResourceManager(session=session)
        fake_pyvisa = SimpleNamespace(ResourceManager=lambda: rm)

        with patch("keysight_logger.instrument.pyvisa", fake_pyvisa):
            ok, detail = VisaInstrument.verify_resource("USB::FAKE", timeout_ms=1234)

        self.assertTrue(ok)
        self.assertEqual("Keysight Technologies,34461A,MY123,1.0", detail)
        self.assertEqual(1234, session.timeout)
        self.assertEqual(["query:*IDN?"], session.writes)
        self.assertTrue(session.closed)
        self.assertTrue(rm.closed)

    def test_verify_resource_returns_failure_detail_and_cleans_up(self):
        session = FakeVisaSession()
        session.fail_query = True
        rm = FakeResourceManager(session=session)
        fake_pyvisa = SimpleNamespace(ResourceManager=lambda: rm)

        with patch("keysight_logger.instrument.pyvisa", fake_pyvisa):
            ok, detail = VisaInstrument.verify_resource("USB::FAKE")

        self.assertFalse(ok)
        self.assertIn("RuntimeError: query failed", detail)
        self.assertTrue(session.closed)
        self.assertTrue(rm.closed)

    def test_infer_transport_detects_usb_lan_and_unknown(self):
        self.assertEqual(Transport.USB, VisaInstrument.infer_transport("USB0::FAKE"))
        self.assertEqual(Transport.LAN, VisaInstrument.infer_transport("TCPIP0::FAKE"))
        self.assertIsNone(VisaInstrument.infer_transport("GPIB0::1::INSTR"))

    def test_pyvisa_timeout_error_classifier_accepts_timeout_status_code(self):
        fake_pyvisa = SimpleNamespace(
            errors=SimpleNamespace(VisaIOError=FakeVisaIOError),
            constants=SimpleNamespace(
                StatusCode=SimpleNamespace(error_timeout=-1073807339)
            ),
        )

        with patch("keysight_logger.instrument.pyvisa", fake_pyvisa):
            self.assertTrue(is_pyvisa_timeout_error(FakeVisaIOError(-1073807339)))

    def test_pyvisa_timeout_error_classifier_rejects_non_timeout_and_unrelated_errors(self):
        fake_pyvisa = SimpleNamespace(
            errors=SimpleNamespace(VisaIOError=FakeVisaIOError),
            constants=SimpleNamespace(
                StatusCode=SimpleNamespace(error_timeout=-1073807339)
            ),
        )

        with patch("keysight_logger.instrument.pyvisa", fake_pyvisa):
            self.assertFalse(is_pyvisa_timeout_error(FakeVisaIOError(-1)))
            self.assertFalse(is_pyvisa_timeout_error(TimeoutError("overall wait")))
            self.assertFalse(is_pyvisa_timeout_error(RuntimeError("other")))


class VisaInstrumentInstanceTests(unittest.TestCase):
    def make_instrument(self, session: FakeVisaSession | None = None, resource: str = "USB::FAKE"):
        rm = FakeResourceManager(session=session)
        fake_pyvisa = SimpleNamespace(ResourceManager=lambda: rm)
        instrument = VisaInstrument(InstrumentConfig(resource_string=resource, timeout_ms=4321))
        return instrument, rm, fake_pyvisa

    def test_connect_opens_resource_sets_timeout_and_resets(self):
        session = FakeVisaSession()
        instrument, rm, fake_pyvisa = self.make_instrument(session=session)

        with patch("keysight_logger.instrument.pyvisa", fake_pyvisa):
            instrument.connect()

        self.assertEqual(["USB::FAKE"], rm.opened_resources)
        self.assertEqual(4321, session.timeout)
        self.assertEqual(["query:*IDN?", "*CLS", "*RST"], session.writes)

    def test_connect_rejects_unsupported_idn_and_closes_without_reset(self):
        session = FakeVisaSession()
        session.idn_response = "Other Vendor,1234,MY123,1.0"
        instrument, rm, fake_pyvisa = self.make_instrument(session=session)

        with patch("keysight_logger.instrument.pyvisa", fake_pyvisa):
            with self.assertRaisesRegex(InstrumentError, "unsupported instrument identity"):
                instrument.connect()

        self.assertEqual(["query:*IDN?"], session.writes)
        self.assertTrue(session.closed)
        self.assertTrue(rm.closed)
        self.assertEqual("not_connected", instrument.release_to_local())

    def test_connect_closes_without_reset_when_idn_query_fails(self):
        session = FakeVisaSession()
        session.fail_query = True
        instrument, rm, fake_pyvisa = self.make_instrument(session=session)

        with patch("keysight_logger.instrument.pyvisa", fake_pyvisa):
            with self.assertRaisesRegex(InstrumentError, "failed to validate instrument identity"):
                instrument.connect()

        self.assertEqual([], session.writes)
        self.assertTrue(session.closed)
        self.assertTrue(rm.closed)
        self.assertEqual("not_connected", instrument.release_to_local())

    def test_unconnected_operations_raise_instrument_error(self):
        instrument = VisaInstrument(InstrumentConfig(resource_string="USB::FAKE"))

        for action in (
            lambda: instrument.write("*IDN?"),
            lambda: instrument.query("*IDN?"),
            lambda: instrument.query_ascii_float("READ?"),
            lambda: instrument.read_status_byte(),
            lambda: instrument.set_timeout_ms(1000),
        ):
            with self.subTest(action=action):
                with self.assertRaisesRegex(InstrumentError, "Instrument is not connected"):
                    action()

    def test_write_query_float_timeout_status_and_close_delegate_to_session(self):
        session = FakeVisaSession()
        session.query_response = " 12.5\n"
        instrument, rm, fake_pyvisa = self.make_instrument(session=session)

        with patch("keysight_logger.instrument.pyvisa", fake_pyvisa):
            instrument.connect()
            instrument.write("CONF:VOLT:DC AUTO")
            instrument.set_timeout_ms(2500)
            query_result = instrument.query("READ?")
            float_result = instrument.query_ascii_float("READ?")
            status_byte = instrument.read_status_byte()
            instrument.close()

        self.assertEqual("12.5", query_result)
        self.assertEqual(12.5, float_result)
        self.assertEqual(32, status_byte)
        self.assertEqual(2500, session.timeout)
        self.assertIn("CONF:VOLT:DC AUTO", session.writes)
        self.assertTrue(session.closed)
        self.assertTrue(rm.closed)

    def test_query_ascii_float_wraps_parse_failure(self):
        session = FakeVisaSession()
        session.query_response = "not-a-float"
        instrument, _rm, fake_pyvisa = self.make_instrument(session=session)

        with patch("keysight_logger.instrument.pyvisa", fake_pyvisa):
            instrument.connect()
            with self.assertRaisesRegex(InstrumentError, "Failed to parse float"):
                instrument.query_ascii_float("READ?")

    def test_poll_system_error_and_abort_measurement_are_best_effort(self):
        session = FakeVisaSession()
        session.query_response = "+0,No error"
        instrument, _rm, fake_pyvisa = self.make_instrument(session=session)

        with patch("keysight_logger.instrument.pyvisa", fake_pyvisa):
            instrument.connect()
            self.assertEqual("+0,No error", instrument.poll_system_error())
            self.assertTrue(instrument.abort_measurement())
            session.fail_writes.add("ABOR")
            self.assertFalse(instrument.abort_measurement())

    def test_release_to_local_returns_not_connected_without_session(self):
        instrument = VisaInstrument(InstrumentConfig(resource_string="USB::FAKE"))

        self.assertEqual("not_connected", instrument.release_to_local())

    def test_release_to_local_uses_usb_control_ren_mode_zero(self):
        session = FakeVisaSession()
        instrument, _rm, fake_pyvisa = self.make_instrument(session=session, resource="USB::FAKE")

        with (
            patch("keysight_logger.instrument.pyvisa", fake_pyvisa),
            patch("keysight_logger.instrument.time.sleep", return_value=None),
        ):
            instrument.connect()
            result = instrument.release_to_local()

        self.assertIn("visa_clear:ok", result)
        self.assertIn("*CLS:ok", result)
        self.assertIn("ABOR:ok", result)
        self.assertIn("SYST:LOC:ok", result)
        self.assertIn("control_ren(0):ok", result)
        self.assertEqual([0], session.control_ren_calls)

    def test_release_to_local_uses_lan_control_ren_fallback(self):
        session = FakeVisaSession()
        session.fail_control_ren_modes.add(6)
        instrument, _rm, fake_pyvisa = self.make_instrument(
            session=session,
            resource="TCPIP0::192.0.2.1::INSTR",
        )

        with (
            patch("keysight_logger.instrument.pyvisa", fake_pyvisa),
            patch("keysight_logger.instrument.time.sleep", return_value=None),
        ):
            instrument.connect()
            result = instrument.release_to_local()

        self.assertIn("control_ren(6):failed:RuntimeError", result)
        self.assertIn("control_ren(0):ok", result)
        self.assertEqual([6, 0], session.control_ren_calls)

    def test_cleanup_release_to_local_opens_releases_closes_and_reports(self):
        session = FakeVisaSession()
        instrument, rm, fake_pyvisa = self.make_instrument(session=session)

        with (
            patch("keysight_logger.instrument.pyvisa", fake_pyvisa),
            patch("keysight_logger.instrument.time.sleep", return_value=None),
        ):
            result = instrument.cleanup_release_to_local(timeout_ms=777)

        self.assertEqual(["USB::FAKE"], rm.opened_resources)
        self.assertEqual(500, session.timeout)
        self.assertIn("cleanup_open:ok", result)
        self.assertIn("SYST:LOC:ok", result)
        self.assertIn("cleanup_close:ok", result)
        self.assertIn("cleanup_rm_close:ok", result)
        self.assertTrue(session.closed)
        self.assertTrue(rm.closed)

    def test_cleanup_release_to_local_handles_unavailable_pyvisa(self):
        instrument = VisaInstrument(InstrumentConfig(resource_string="USB::FAKE"))

        with patch("keysight_logger.instrument.pyvisa", None):
            self.assertEqual("pyvisa_unavailable", instrument.cleanup_release_to_local())


if __name__ == "__main__":
    unittest.main()
