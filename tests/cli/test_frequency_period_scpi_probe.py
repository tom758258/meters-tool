from __future__ import annotations

from collections import deque
from unittest.mock import patch

import pytest

from scripts import _frequency_period_scpi_probe as probe


FREQUENCY_COMMANDS = [
    "CONF:FREQ",
    "FREQ:VOLT:RANG:AUTO ON",
    "FREQ:RANG:LOW 20",
    "FREQ:APER 0.1",
    "FREQ:TIM:AUTO ON",
]

PERIOD_COMMANDS = [
    "CONF:PER",
    "PER:VOLT:RANG:AUTO ON",
    "PER:RANG:LOW 20",
    "PER:APER 0.1",
]


class FakeVisaSession:
    def __init__(
        self,
        error_responses: dict[str, list[str]] | None = None,
        idn: str = "Keysight Technologies,34461A,MY12345678,A.03.02",
    ):
        self.timeout = None
        self.writes: list[str] = []
        self.closed = False
        self.cleared = False
        self.control_ren_calls: list[int] = []
        self.idn = idn
        self._error_responses = error_responses or {}
        self._active_errors: deque[str] = deque()

    def write(self, command: str) -> None:
        self.writes.append(command)
        self._active_errors = deque(self._error_responses.get(command, ['+0,"No error"']))

    def query(self, command: str) -> str:
        self.writes.append(f"query:{command}")
        if command == "*IDN?":
            self._active_errors = deque(
                self._error_responses.get(command, ['+0,"No error"'])
            )
            return self.idn
        if command == "READ?":
            self._active_errors = deque(
                self._error_responses.get(command, ['+0,"No error"'])
            )
            return "1000.0"
        if command == "SYST:ERR?":
            if self._active_errors:
                return self._active_errors.popleft()
            return '+0,"No error"'
        raise AssertionError(f"unexpected query: {command}")

    def clear(self) -> None:
        self.cleared = True

    def control_ren(self, mode: int) -> None:
        self.control_ren_calls.append(mode)

    def close(self) -> None:
        self.closed = True


class FakeResourceManager:
    def __init__(self, session: FakeVisaSession):
        self.session = session
        self.opened_resources: list[str] = []
        self.closed = False

    def open_resource(self, resource: str) -> FakeVisaSession:
        self.opened_resources.append(resource)
        return self.session

    def close(self) -> None:
        self.closed = True


def resource_manager_factory(
    sessions: list[FakeVisaSession],
) -> tuple[object, list[FakeResourceManager]]:
    managers = [FakeResourceManager(session) for session in sessions]
    remaining = deque(managers)

    def factory() -> FakeResourceManager:
        return remaining.popleft()

    return factory, managers


def run_frequency_probe(
    sessions: list[FakeVisaSession],
    commands: list[str] | None = None,
    model: str | None = None,
) -> tuple[dict, list[FakeResourceManager]]:
    factory, managers = resource_manager_factory(sessions)
    with patch("meters_tool_core.instrument.time.sleep", return_value=None):
        result = probe.run_probe(
            resource="USB::FAKE",
            measurement="frequency",
            commands=commands or FREQUENCY_COMMANDS,
            model=model,
            resource_manager_factory=factory,
        )
    return result, managers


def test_probe_accepts_zero_error_queue_and_cleans_up():
    session = FakeVisaSession()

    result, managers = run_frequency_probe([session])

    assert result["status"] == "passed"
    assert result["all_scpi_error_responses_zero"] is True
    assert result["idn"] == "Keysight Technologies,34461A,MY12345678,A.03.02"
    assert result["firmware_revision"] == "A.03.02"
    assert all(record["all_error_responses_zero"] for record in result["commands"])
    assert result["read"]["response"] == "1000.0"
    assert result["read"]["all_error_responses_zero"] is True
    assert result["cleanup"]["order"] == ["abort", "release_to_local", "close"]
    assert session.closed is True
    assert managers[0].closed is True


def test_probe_accepts_34460a_identity_when_model_selected():
    session = FakeVisaSession(
        idn="Keysight Technologies,34460A,MY12345678,A.03.02"
    )

    result, managers = run_frequency_probe([session], model="34460A")

    assert result["status"] == "passed"
    assert result["idn"] == "Keysight Technologies,34460A,MY12345678,A.03.02"
    assert session.closed is True
    assert managers[0].closed is True


def test_probe_without_model_keeps_default_34461a_identity_check():
    session = FakeVisaSession(
        idn="Keysight Technologies,34460A,MY12345678,A.03.02"
    )

    result, managers = run_frequency_probe([session], model=None)

    assert result["status"] == "failed"
    assert any(
        "expected Keysight/Agilent 34461A" in reason
        for reason in result["failure_reasons"]
    )
    assert session.closed is True
    assert managers[0].closed is True


def test_probe_attributes_single_error_to_exact_command():
    session = FakeVisaSession(
        {
            "FREQ:APER 0.1": [
                '-222,"Data out of range"',
                '+0,"No error"',
            ]
        }
    )

    result, _managers = run_frequency_probe([session])

    assert result["status"] == "failed"
    failed = next(
        record for record in result["commands"] if record["command"] == "FREQ:APER 0.1"
    )
    assert [item["code"] for item in failed["system_error_responses"]] == [-222, 0]
    assert failed["all_error_responses_zero"] is False


def test_probe_records_multiple_errors_before_zero():
    session = FakeVisaSession(
        {
            "CONF:FREQ": [
                '-113,"Undefined header"',
                '-221,"Settings conflict"',
                '+0,"No error"',
            ]
        }
    )

    result, _managers = run_frequency_probe([session])

    failed = result["commands"][0]
    assert [item["code"] for item in failed["system_error_responses"]] == [
        -113,
        -221,
        0,
    ]
    assert failed["error_queue_terminated"] is True
    assert failed["error_limit_reached"] is False
    assert result["status"] == "failed"


def test_probe_stops_after_ten_error_responses():
    session = FakeVisaSession(
        {
            "CONF:FREQ": [
                f'-100,"Error {index}"'
                for index in range(probe.MAX_ERROR_RESPONSES + 1)
            ]
        }
    )

    result, _managers = run_frequency_probe([session])

    failed = result["commands"][0]
    assert len(failed["system_error_responses"]) == probe.MAX_ERROR_RESPONSES
    assert failed["error_queue_terminated"] is False
    assert failed["error_limit_reached"] is True


def test_period_probe_uses_only_planned_commands():
    session = FakeVisaSession()
    factory, managers = resource_manager_factory([session])

    with patch("meters_tool_core.instrument.time.sleep", return_value=None):
        result = probe.run_probe(
            resource="USB::FAKE",
            measurement="period",
            commands=PERIOD_COMMANDS,
            resource_manager_factory=factory,
        )

    assert result["status"] == "passed"
    assert [record["command"] for record in result["commands"]] == PERIOD_COMMANDS
    assert all("TIM" not in command for command in session.writes)
    assert session.closed is True
    assert managers[0].closed is True


def test_probe_rejects_missing_explicit_resource():
    with pytest.raises(ValueError, match="resource must be explicitly provided"):
        probe.run_probe(
            resource=" ",
            measurement="frequency",
            commands=FREQUENCY_COMMANDS,
        )
