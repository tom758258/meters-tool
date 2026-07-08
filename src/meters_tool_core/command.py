from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


ALLOWED_COMMAND_ENVELOPE_KEYS = {"command", "arguments", "job_id"}
METERS_SOFTWARE_TRIGGER_COMMAND = "software_trigger"


class CommandValidationError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        command: str | None = None,
        job_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.command = command
        self.job_id = job_id


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


def command_identity(payload: Any) -> tuple[str | None, str | None]:
    if not isinstance(payload, dict):
        return None, None
    command = payload.get("command")
    job_id = payload.get("job_id")
    return (
        command if isinstance(command, str) and command else None,
        job_id if isinstance(job_id, str) else None,
    )


def command_response(
    status: str,
    *,
    command: str | None,
    job_id: str | None,
    reason: str | None = None,
    error: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "status": status,
        "command": command,
        "job_id": job_id,
    }
    if reason is not None:
        response["reason"] = reason
    if error is not None:
        response["error"] = error
    if message is not None:
        response["message"] = message
    return response


def parse_command_envelope(payload: Any) -> SoftwareTriggerCommand:
    command_identity_value, job_id_identity = command_identity(payload)

    def fail(message: str) -> None:
        raise CommandValidationError(
            message,
            command=command_identity_value,
            job_id=job_id_identity,
        )

    if not isinstance(payload, dict):
        fail("request body must be a JSON object")
    unknown = sorted(set(payload) - ALLOWED_COMMAND_ENVELOPE_KEYS)
    if unknown:
        fail(f"unknown top-level field: {unknown[0]}")

    command = payload.get("command")
    if not isinstance(command, str) or not command:
        fail("command must be a non-empty string")
    if command != METERS_SOFTWARE_TRIGGER_COMMAND:
        fail(f"unknown command: {command}")

    job_id = payload.get("job_id")
    if job_id is not None and not isinstance(job_id, str):
        fail("job_id must be a string")

    arguments = payload.get("arguments", {})
    if not isinstance(arguments, dict):
        fail("arguments must be a JSON object")
    metadata = arguments.get("metadata", {})
    if not isinstance(metadata, dict):
        fail("metadata must be a JSON object")

    try:
        normalized_metadata = normalize_command_metadata(metadata)
    except CommandValidationError as exc:
        fail(str(exc))
    return SoftwareTriggerCommand(metadata=normalized_metadata, job_id=job_id)


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
