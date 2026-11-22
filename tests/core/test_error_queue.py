from unittest.mock import Mock, call

import pytest

from meters_tool_core.diagnostics import ErrorQueueReadError, ScpiError, read_error_queue
from meters_tool_core.instrument import InstrumentError


@pytest.fixture
def visa():
    manager = Mock()
    instrument = manager.open_resource.return_value
    return manager, instrument


@pytest.mark.parametrize(
    ("model", "resource", "backend", "replies", "limit", "errors", "cleared"),
    [
        ("34460A", "USB::FAKE::INSTR", None, ["0,No error"], 20, (), True),
        ("34460A", "USB::FAKE::INSTR", None, ["+0"], 20, (), True),
        (
            "34461A", "TCPIP::meter.example::INSTR", "@py",
            ['-113, "Undefined header"', '-222,"Data out of range, channel 1"', '+0,"No error"'],
            3, (ScpiError(-113, "Undefined header"), ScpiError(-222, "Data out of range, channel 1")),
            True,
        ),
        (
            "34461A", "TCPIP::meter.example::INSTR", None,
            ['-113,"Undefined header"', '-222,"Data out of range"'],
            1, (ScpiError(-113, "Undefined header"),), False,
        ),
    ],
)
def test_error_queue_quits_at_zero_or_limit_using_only_queries(
    visa, model, resource, backend, replies, limit, errors, cleared
):
    manager, instrument = visa
    instrument.query.side_effect = [f"Keysight Technologies,{model},FAKE,1.0", *replies]
    result = read_error_queue(
        resource, visa_library=backend, max_reads=limit, resource_manager_factory=lambda: manager
    )
    assert result.errors == errors
    assert result.queue_cleared is cleared
    assert result.termination == ("no_error" if cleared else "max_reads")
    assert result.reads == len(errors) + int(cleared)
    assert result.max_reads == limit
    assert result.model == model
    assert manager.mock_calls == [
        call.open_resource(resource),
        call.open_resource().query("*IDN?"),
        *[call.open_resource().query("SYST:ERR?")] * result.reads,
        call.open_resource().close(),
        call.close(),
    ]


@pytest.mark.parametrize(
    "options",
    [
        {"max_reads": 0}, {"max_reads": -1}, {"max_reads": 1.5},
        {"max_reads": True}, {"max_reads": "2"},
        {"visa_library": "@py"}, {"visa_library": "@bt"},
        {"resource": ""}, {"resource": "ASRL1::INSTR"},
        {"resource": "TCPIP::meter.example::INSTR", "instrument_model": "34460A"},
    ],
)
def test_invalid_request_never_opens_visa(options):
    factory = Mock()
    with pytest.raises(ValueError):
        read_error_queue(**({"resource": "USB::FAKE::INSTR"} | options), resource_manager_factory=factory)
    factory.assert_not_called()


@pytest.mark.parametrize(
    ("resource", "idn", "expected"),
    [
        ("USB::FAKE::INSTR", "Other Vendor,1234,FAKE,1.0", None),
        ("USB::FAKE::INSTR", "Keysight Technologies,34460A,FAKE,1.0", "34461A"),
        ("TCPIP::meter.example::INSTR", "Keysight Technologies,34460A,FAKE,1.0", None),
    ],
)
def test_unsupported_identity_or_scope_leaves_queue_untouched(visa, resource, idn, expected):
    manager, instrument = visa
    instrument.query.return_value = idn
    with pytest.raises(ValueError):
        read_error_queue(resource, instrument_model=expected, resource_manager_factory=lambda: manager)
    assert instrument.mock_calls == [call.query("*IDN?"), call.close()]
    manager.close.assert_called_once()


@pytest.mark.parametrize(
    ("replies", "prior_error"),
    [
        ([TimeoutError("timed out")], None),
        (['invalid reply'], None),
        (['+0,"unterminated'], None),
        (['-113,"Undefined header"', TimeoutError("timed out")], ScpiError(-113, "Undefined header")),
    ],
)
def test_query_failure_closes_visa_and_preserves_retrieved_errors(visa, replies, prior_error):
    manager, instrument = visa
    instrument.query.side_effect = ["Keysight Technologies,34461A,FAKE,1.0", *replies]
    error_type = ErrorQueueReadError if prior_error is not None else InstrumentError
    with pytest.raises(error_type) as failure:
        read_error_queue("USB::FAKE::INSTR", resource_manager_factory=lambda: manager)
    if prior_error is not None:
        partial = failure.value.partial_result
        assert partial.errors == (prior_error,)
        assert partial.reads == 1
        assert partial.termination == "failed"
        assert partial.queue_cleared is False
        assert "timed out" in str(failure.value)
    instrument.close.assert_called_once()
    manager.close.assert_called_once()


def test_open_failure_closes_resource_manager(visa):
    manager, _ = visa
    manager.open_resource.side_effect = OSError("open failed")
    with pytest.raises(InstrumentError, match="open failed"):
        read_error_queue("USB::FAKE::INSTR", resource_manager_factory=lambda: manager)
    manager.close.assert_called_once()
