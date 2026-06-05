from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


ALLOWED_COMMAND_ENVELOPE_KEYS = {"command", "arguments", "job_id"}
METERS_SOFTWARE_TRIGGER_COMMAND = "software_trigger"


class CommandValidationError(ValueError):
    pass


@dataclass(frozen=True)
class SoftwareTriggerCommand:
    metadata: dict[str, str]
    job_id: str | None = None


def normalize_command_metadata(metadata: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in metadata.items():
        if not isinstance(key, str):
            raise CommandValidationError("metadata keys must be strings")
        if isinstance(value, str):
            normalized[key] = value
        else:
            normalized[key] = json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
    return normalized


def parse_command_envelope_json(raw_payload: str) -> SoftwareTriggerCommand:
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise CommandValidationError(f"malformed JSON: {exc.msg}") from exc
    return parse_command_envelope(payload)


def parse_command_envelope(payload: Any) -> SoftwareTriggerCommand:
    if not isinstance(payload, dict):
        raise CommandValidationError("request body must be a JSON object")
    unknown = sorted(set(payload) - ALLOWED_COMMAND_ENVELOPE_KEYS)
    if unknown:
        raise CommandValidationError(f"unknown top-level field: {unknown[0]}")

    command = payload.get("command")
    if not isinstance(command, str) or not command:
        raise CommandValidationError("command must be a non-empty string")
    if command != METERS_SOFTWARE_TRIGGER_COMMAND:
        raise CommandValidationError(f"unknown command: {command}")

    job_id = payload.get("job_id")
    if job_id is not None and not isinstance(job_id, str):
        raise CommandValidationError("job_id must be a string")

    arguments = payload.get("arguments", {})
    if not isinstance(arguments, dict):
        raise CommandValidationError("arguments must be a JSON object")
    metadata = arguments.get("metadata", {})
    if not isinstance(metadata, dict):
        raise CommandValidationError("metadata must be a JSON object")

    return SoftwareTriggerCommand(
        metadata=normalize_command_metadata(metadata),
        job_id=job_id,
    )


def software_trigger_envelope(
    *,
    metadata: dict[str, Any] | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        "command": METERS_SOFTWARE_TRIGGER_COMMAND,
        "arguments": {"metadata": metadata or {}},
    }
    if job_id is not None:
        envelope["job_id"] = job_id
    return envelope
