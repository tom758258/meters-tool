from __future__ import annotations

from typing import List, Optional

from .models import InstrumentConfig, Transport

try:
    import pyvisa
except ImportError:  # pragma: no cover - resolved at runtime if pyvisa installed
    pyvisa = None


class InstrumentError(RuntimeError):
    pass


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
        self._rm = pyvisa.ResourceManager()
        self._inst = self._rm.open_resource(self._config.resource_string)
        self._inst.timeout = self._config.timeout_ms
        self._inst.write("*CLS")
        self._inst.write("*RST")

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

        results: list[str] = []
        try:
            self._inst.timeout = min(int(getattr(self._inst, "timeout", 1000)), 1000)
        except Exception:
            pass

        for command in ("ABOR", "SYST:LOC"):
            try:
                self.write(command)
                results.append(f"{command}:ok")
            except Exception as exc:
                results.append(f"{command}:failed:{type(exc).__name__}")

        control_ren = getattr(self._inst, "control_ren", None)
        if callable(control_ren):
            for mode in (6, 0):
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
