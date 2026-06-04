from __future__ import annotations

from typing import List, Optional

from .models import InstrumentConfig, Transport

import time

try:
    import pyvisa
except ImportError:  # pragma: no cover - resolved at runtime if pyvisa installed
    pyvisa = None


class InstrumentError(RuntimeError):
    pass


_VISA_TIMEOUT_ERROR_CODE = -1073807339


def is_pyvisa_timeout_error(exc: Exception) -> bool:
    if pyvisa is None:
        return False

    visa_io_error_type = getattr(getattr(pyvisa, "errors", None), "VisaIOError", None)
    if visa_io_error_type is None:
        visa_io_error_type = getattr(pyvisa, "VisaIOError", None)
    if visa_io_error_type is None or not isinstance(exc, visa_io_error_type):
        return False

    error_code = getattr(exc, "error_code", None)
    timeout_code = _VISA_TIMEOUT_ERROR_CODE
    status_code = getattr(getattr(pyvisa, "constants", None), "StatusCode", None)
    if status_code is not None and hasattr(status_code, "error_timeout"):
        timeout_code = status_code.error_timeout

    return error_code == timeout_code or error_code == _VISA_TIMEOUT_ERROR_CODE


def _is_supported_34461a_idn(idn: str) -> bool:
    parts = [part.strip().upper() for part in str(idn).split(",")]
    if len(parts) < 2:
        return False
    manufacturer = parts[0]
    model = parts[1]
    return ("KEYSIGHT" in manufacturer or "AGILENT" in manufacturer) and model == "34461A"


class VisaInstrument:
    def __init__(self, config: InstrumentConfig):
        self._config = config
        self._rm = None
        self._inst = None

    @staticmethod
    def list_resources() -> List[str]:
        if pyvisa is None:
            raise InstrumentError("pyvisa is not installed. Run: pip install -r requirements.txt")
        rm = pyvisa.ResourceManager()
        resources = list(rm.list_resources())
        rm.close()
        return resources

    @staticmethod
    def verify_resource(resource: str, timeout_ms: int = 1000) -> tuple[bool, str]:
        if pyvisa is None:
            raise InstrumentError("pyvisa is not installed. Run: pip install -r requirements.txt")

        rm = None
        inst = None
        try:
            rm = pyvisa.ResourceManager()
            inst = rm.open_resource(resource)
            inst.timeout = timeout_ms
            idn_detail = str(inst.query("*IDN?")).strip()
            try:
                VisaInstrument(
                    InstrumentConfig(resource_string=resource)
                )._release_session_to_local(inst)
            except Exception:
                pass
            return True, idn_detail
        except Exception as exc:
            return False, f"{type(exc).__name__}: {exc}"
        finally:
            if inst is not None:
                try:
                    inst.close()
                except Exception:
                    pass
            if rm is not None:
                try:
                    rm.close()
                except Exception:
                    pass

    @staticmethod
    def infer_transport(resource: str) -> Optional[Transport]:
        upper = resource.upper()
        if upper.startswith("TCPIP"):
            return Transport.LAN
        if upper.startswith("USB"):
            return Transport.USB
        return None

    def connect(self) -> None:
        if pyvisa is None:
            raise InstrumentError("pyvisa is not installed. Run: pip install -r requirements.txt")
        try:
            self._rm = pyvisa.ResourceManager()
            self._inst = self._rm.open_resource(self._config.resource_string)
            self._inst.timeout = self._config.timeout_ms
            idn = str(self._inst.query("*IDN?")).strip()
            if not _is_supported_34461a_idn(idn):
                raise InstrumentError(
                    "unsupported instrument identity; expected Keysight/Agilent 34461A, "
                    f"got '{idn}'"
                )
            self._inst.write("*CLS")
            self._inst.write("*RST")
        except InstrumentError:
            self.close()
            raise
        except Exception as exc:
            self.close()
            raise InstrumentError(f"failed to validate instrument identity: {exc}") from exc

    def write(self, command: str) -> None:
        if self._inst is None:
            raise InstrumentError("Instrument is not connected")
        self._inst.write(command)

    def set_timeout_ms(self, timeout_ms: int) -> None:
        if self._inst is None:
            raise InstrumentError("Instrument is not connected")
        self._inst.timeout = timeout_ms

    def query(self, command: str) -> str:
        if self._inst is None:
            raise InstrumentError("Instrument is not connected")
        return str(self._inst.query(command)).strip()

    def query_ascii_float(self, command: str) -> float:
        raw = self.query(command)
        try:
            return float(raw)
        except ValueError as exc:
            raise InstrumentError(f"Failed to parse float from '{raw}'") from exc

    def read_status_byte(self) -> int:
        if self._inst is None:
            raise InstrumentError("Instrument is not connected")
        return int(self._inst.read_stb())

    def close(self) -> None:
        if self._inst is not None:
            self._inst.close()
            self._inst = None
        if self._rm is not None:
            self._rm.close()
            self._rm = None

    def poll_system_error(self) -> str:
        # Best-effort SCPI error query for diagnostics.
        try:
            return self.query("SYST:ERR?")
        except Exception:
            return "unknown"

    def abort_measurement(self) -> bool:
        try:
            self.write("ABOR")
            return True
        except Exception:
            return False

    def release_to_local(self) -> str:
        if self._inst is None:
            return "not_connected"

        return self._release_session_to_local(self._inst)

    def cleanup_release_to_local(self, timeout_ms: int = 1000) -> str:
        if pyvisa is None:
            return "pyvisa_unavailable"

        results: list[str] = []
        rm = None
        inst = None
        try:
            rm = pyvisa.ResourceManager()
            inst = rm.open_resource(self._config.resource_string)
            inst.timeout = timeout_ms
            results.append("cleanup_open:ok")
            results.append(self._release_session_to_local(inst))
        except Exception as exc:
            results.append(f"cleanup_open_or_release:failed:{type(exc).__name__}")
        finally:
            if inst is not None:
                try:
                    inst.close()
                    results.append("cleanup_close:ok")
                except Exception as exc:
                    results.append(f"cleanup_close:failed:{type(exc).__name__}")
            if rm is not None:
                try:
                    rm.close()
                    results.append("cleanup_rm_close:ok")
                except Exception as exc:
                    results.append(f"cleanup_rm_close:failed:{type(exc).__name__}")
        return ", ".join(results)

    def _release_session_to_local(self, inst) -> str:  # noqa: ANN001

        results: list[str] = []
        # Clear pending bus state before issuing release commands.
        try:
            inst.clear()
            results.append("visa_clear:ok")
        except Exception as exc:
            results.append(f"visa_clear:failed:{type(exc).__name__}")

        try:
            inst.timeout = 500
        except Exception:
            pass

        try:
            inst.write("*CLS")
            inst.write("*WAI")
            results.append("*CLS:ok")
        except Exception as exc:
            results.append(f"*CLS:failed:{type(exc).__name__}")

        for command in ("ABOR", "SYST:LOC"):
            try:
                inst.write(command)
                results.append(f"{command}:ok")
                if command == "SYST:LOC":
                    time.sleep(0.5)
            except Exception as exc:
                results.append(f"{command}:failed:{type(exc).__name__}")

        control_ren = getattr(inst, "control_ren", None)
        if callable(control_ren):
            # USB-TMC generally supports mode 0; LAN/GPIB-like paths may need mode 6 fallback.
            transport = VisaInstrument.infer_transport(self._config.resource_string)
            modes_to_try = (0,) if transport == Transport.USB else (6, 0)
            for mode in modes_to_try:
                try:
                    control_ren(mode)
                    results.append(f"control_ren({mode}):ok")
                    break
                except Exception as exc:
                    results.append(f"control_ren({mode}):failed:{type(exc).__name__}")
        else:
            results.append("control_ren:unavailable")

        return ", ".join(results)

    @property
    def resource_id(self) -> str:
        return self._config.resource_string
