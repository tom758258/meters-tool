from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Sequence
from typing import Any

from meters_tool_core.instrument import VisaInstrument
from meters_tool_core.models import InstrumentConfig


MAX_ERROR_RESPONSES = 10
_ERROR_RESPONSE_PATTERN = re.compile(r"^\s*([+-]?\d+)\s*(?:,\s*(.*))?$")


def _parse_system_error(response: str) -> dict[str, Any]:
    raw = str(response).strip()
    match = _ERROR_RESPONSE_PATTERN.match(raw)
    if match is None:
        return {
            "raw": raw,
            "code": None,
            "message": None,
            "is_error": True,
            "parse_error": True,
        }
    code = int(match.group(1))
    message = (match.group(2) or "").strip().strip('"')
    return {
        "raw": raw,
        "code": code,
        "message": message,
        "is_error": code != 0,
        "parse_error": False,
    }


def _drain_system_errors(instrument: VisaInstrument) -> dict[str, Any]:
    responses: list[dict[str, Any]] = []
    query_error = None
    for _ in range(MAX_ERROR_RESPONSES):
        try:
            parsed = _parse_system_error(instrument.query("SYST:ERR?"))
        except Exception as exc:
            query_error = f"{type(exc).__name__}: {exc}"
            break
        responses.append(parsed)
        if parsed["code"] == 0:
            break
        if parsed["code"] is None:
            break

    terminated = bool(responses and responses[-1]["code"] == 0)
    return {
        "responses": responses,
        "all_zero": (
            query_error is None
            and terminated
            and all(item["code"] == 0 for item in responses)
        ),
        "terminated": terminated,
        "limit_reached": len(responses) == MAX_ERROR_RESPONSES and not terminated,
        "query_error": query_error,
    }


def _command_record(
    instrument: VisaInstrument,
    command: str,
    *,
    query: bool = False,
) -> dict[str, Any]:
    response = None
    transport_error = None
    try:
        response = instrument.query(command) if query else None
        if not query:
            instrument.write(command)
    except Exception as exc:
        transport_error = f"{type(exc).__name__}: {exc}"

    errors = (
        _drain_system_errors(instrument)
        if transport_error is None
        else {
            "responses": [],
            "all_zero": False,
            "terminated": False,
            "limit_reached": False,
            "query_error": None,
        }
    )
    return {
        "command": command,
        "operation": "query" if query else "write",
        "response": response,
        "transport_error": transport_error,
        "system_error_responses": errors["responses"],
        "all_error_responses_zero": errors["all_zero"],
        "error_queue_terminated": errors["terminated"],
        "error_limit_reached": errors["limit_reached"],
        "system_error_query_error": errors["query_error"],
    }


def _firmware_revision(idn: str | None) -> str | None:
    if idn is None:
        return None
    parts = [part.strip() for part in idn.split(",")]
    return parts[3] if len(parts) >= 4 else None


def _cleanup(instrument: VisaInstrument) -> dict[str, Any]:
    abort_ok = instrument.abort_measurement()
    try:
        release_result = instrument.release_to_local()
    except Exception as exc:
        release_result = f"failed:{type(exc).__name__}: {exc}"
    try:
        instrument.close()
        close_result = "ok"
    except Exception as exc:
        close_result = f"failed:{type(exc).__name__}: {exc}"
    return {
        "order": ["abort", "release_to_local", "close"],
        "abort": abort_ok,
        "release_to_local": release_result,
        "close": close_result,
    }


def _run_session(
    *,
    resource: str,
    commands: Sequence[str],
    timeout_ms: int,
    model: str | None,
    resource_manager_factory: Callable[[], object] | None,
    include_read: bool,
) -> dict[str, Any]:
    instrument = VisaInstrument(
        InstrumentConfig(
            resource_string=resource,
            timeout_ms=timeout_ms,
            expected_model=model,
        ),
        resource_manager_factory=resource_manager_factory,
    )
    result: dict[str, Any] = {
        "status": "failed",
        "idn": None,
        "firmware_revision": None,
        "identity_system_errors": None,
        "commands": [],
        "read": None,
        "failure_reasons": [],
        "cleanup": None,
    }
    try:
        instrument.connect()
        idn = instrument.query("*IDN?")
        identity_errors = _drain_system_errors(instrument)
        result["idn"] = idn
        result["firmware_revision"] = _firmware_revision(idn)
        result["identity_system_errors"] = identity_errors
        if not identity_errors["all_zero"]:
            result["failure_reasons"].append(
                "non-zero or invalid SYST:ERR? response after *IDN?"
            )

        for command in commands:
            record = _command_record(instrument, command)
            result["commands"].append(record)
            if not record["all_error_responses_zero"]:
                result["failure_reasons"].append(
                    f"SCPI error response after command: {command}"
                )

        if include_read:
            read_record = _command_record(instrument, "READ?", query=True)
            result["read"] = read_record
            if not read_record["all_error_responses_zero"]:
                result["failure_reasons"].append(
                    "SCPI error response after command: READ?"
                )
    except Exception as exc:
        result["failure_reasons"].append(f"{type(exc).__name__}: {exc}")
    finally:
        result["cleanup"] = _cleanup(instrument)

    if not result["failure_reasons"]:
        result["status"] = "passed"
    return result


def run_probe(
    *,
    resource: str,
    measurement: str,
    commands: Sequence[str],
    timeout_ms: int = 5000,
    model: str | None = None,
    resource_manager_factory: Callable[[], object] | None = None,
) -> dict[str, Any]:
    if not resource.strip():
        raise ValueError("resource must be explicitly provided")
    if measurement not in {"frequency", "period"}:
        raise ValueError("measurement must be frequency or period")
    if not commands:
        raise ValueError("at least one SCPI command must be provided")

    result = _run_session(
        resource=resource,
        commands=commands,
        timeout_ms=timeout_ms,
        model=model,
        resource_manager_factory=resource_manager_factory,
        include_read=True,
    )
    result.update(
        {
            "schema_version": 1,
            "resource": resource,
            "measurement": measurement,
        }
    )

    result["all_scpi_error_responses_zero"] = result["status"] == "passed"
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Private Frequency/Period SCPI diagnostic probe."
    )
    parser.add_argument("--resource", required=True)
    parser.add_argument("--measurement", choices=("frequency", "period"), required=True)
    parser.add_argument("--command", action="append", dest="commands", required=True)
    parser.add_argument("--timeout-ms", type=int, default=5000)
    parser.add_argument("--model", choices=("34460A", "34461A"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = run_probe(
            resource=args.resource,
            measurement=args.measurement,
            commands=args.commands,
            timeout_ms=args.timeout_ms,
            model=args.model,
        )
    except Exception as exc:
        result = {
            "schema_version": 1,
            "resource": args.resource,
            "measurement": args.measurement,
            "status": "failed",
            "all_scpi_error_responses_zero": False,
            "idn": None,
            "firmware_revision": None,
            "identity_system_errors": None,
            "failure_reasons": [f"{type(exc).__name__}: {exc}"],
            "commands": [],
            "read": None,
            "cleanup": None,
        }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
