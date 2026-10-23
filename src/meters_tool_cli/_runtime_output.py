from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from meters_tool_core import StartPlan, StartRunEvent
from meters_tool_core.command import common_error

from ._constants import CLI_EVENT_SCHEMA_VERSION, WORKER_SCHEMA_VERSION


class CliEventEmitter:
    def __init__(self, print_fn=print, output_format: str = "text") -> None:  # noqa: ANN001
        self._print = print_fn
        self._output_format = output_format

    @property
    def output_format(self) -> str:
        return self._output_format

    def _emit_json(self, payload: dict) -> None:
        self._print(json.dumps(payload, sort_keys=True))
        if self._print is print:
            sys.stdout.flush()

    def status(self, message: str, **fields) -> None:  # noqa: ANN003
        if self._output_format == "jsonl":
            payload = {
                "event": "status",
                "message": message,
                "schema_version": WORKER_SCHEMA_VERSION,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
            payload.update(fields)
            payload.setdefault("worker_state", "running")
            fatal = payload.get("fatal_error")
            payload["fatal_error"] = (
                common_error("execution", "acquisition_failed", fatal)
                if isinstance(fatal, str) and fatal else None
            )
            self._emit_json(payload)
            return
        self._print(f"[status] {message}")

    def sample(self, sample, captured: int, **fields) -> None:  # noqa: ANN001, ANN003
        if self._output_format == "jsonl":
            payload = {
                "captured": captured,
                "event": "sample",
                "measurement_type": sample.measurement_type,
                "measurement_metadata": sample.measurement_metadata,
                "message": f"value={sample.value:g} {sample.unit}",
                "resource_id": sample.resource_id,
                "schema_version": WORKER_SCHEMA_VERSION,
                "status": sample.status,
                "timestamp_utc": sample.timestamp_utc.isoformat(),
                "trigger_id": sample.trigger_id,
                "trigger_metadata": sample.trigger_metadata,
                "trigger_source": sample.trigger_source,
                "unit": sample.unit,
                "value": sample.value,
            }
            payload.update(fields)
            self._emit_json(payload)

    def summary(
        self,
        captured: int,
        errors: int,
        fatal_error: str | None = None,
        ok: bool | None = None,
        **fields,  # noqa: ANN003
    ) -> None:
        if self._output_format == "jsonl":
            payload = {
                "captured": captured,
                "errors": errors,
                "event": "summary",
                "ok": fatal_error is None if ok is None else ok,
                "schema_version": WORKER_SCHEMA_VERSION,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
            payload["fatal_error"] = (
                common_error("execution", "acquisition_failed", fatal_error)
                if fatal_error else None
            )
            payload.update(fields)
            payload["exit_code"] = 0 if payload["ok"] else 3
            self._emit_json(payload)
            return
        self._print(f"captured={captured} errors={errors}")

    def ready(self, host: str, port: int, **fields) -> None:  # noqa: ANN003
        if self._output_format != "jsonl":
            return
        base_url = f"http://{host}:{port}"
        payload = {
            "event": "ready",
            "host": host,
            "port": port,
            "schema_version": WORKER_SCHEMA_VERSION,
            "service": "keysight-meter",
            "status_url": f"{base_url}/status",
            "stop_url": f"{base_url}/stop",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "command_url": f"{base_url}/command",
        }
        payload.update(fields)
        payload["features"] = (
            {"common.streaming": {"contract_version": 1, "lifecycles": ["run_bound"]}}
            if "stream" in payload else {}
        )
        self._emit_json(payload)

    def line(self, message: str, **fields) -> None:  # noqa: ANN003
        if self._output_format == "jsonl":
            payload = {
                "event": "message",
                "message": message,
                "schema_version": WORKER_SCHEMA_VERSION,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
            payload.update(fields)
            self._emit_json(payload)
            return
        self._print(message)

    def error(self, message: str, rc: int = 3, **fields) -> None:  # noqa: ANN003
        if self._output_format == "jsonl":
            scope = fields.pop("scope", "worker" if "run_id" in fields else "request")
            fatal = fields.pop("fatal", rc == 3 and scope == "worker")
            category = fields.pop("category", "validation" if rc == 2 else "worker")
            code = fields.pop("code", "invalid_request" if rc == 2 else "worker_failed")
            payload = {
                "event": "error",
                "message": message,
                "schema_version": WORKER_SCHEMA_VERSION,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "exit_code": rc,
                "scope": scope,
                "fatal": fatal,
                "error": common_error(category, code, message),
            }
            payload.update(fields)
            self._emit_json(payload)
            return
        self._print(message, file=sys.stderr)


class CliStartRunEventSink:
    def __init__(self, emitter: CliEventEmitter) -> None:
        self._emitter = emitter

    def _runtime_fields(self, event: StartRunEvent) -> dict[str, object]:
        return {"run_id": event.run_id} if event.run_id is not None else {}

    def emit(self, event: StartRunEvent) -> None:
        fields = self._runtime_fields(event)
        if event.event == "status":
            fields.update(event.fields)
            self._emitter.status(event.message or "", **fields)
            return
        if event.event == "sample":
            self._emitter.sample(event.sample, int(event.captured or 0), **fields)
            return
        if event.event == "summary":
            fields.update(event.fields)
            self._emitter.summary(
                int(event.captured or 0),
                int(event.errors or 0),
                event.fatal_error,
                **fields,
            )
            return
        if event.event == "ready":
            if event.host is not None and event.port is not None:
                ready_fields = dict(fields)
                ready_fields.update(event.fields)
                if event.command_url is not None:
                    ready_fields["command_url"] = event.command_url
                if event.stop_url is not None:
                    ready_fields["stop_url"] = event.stop_url
                if event.status_url is not None:
                    ready_fields["status_url"] = event.status_url
                self._emitter.ready(event.host, event.port, **ready_fields)
            return
        if event.event == "error":
            fields.update(event.fields)
            fields.setdefault("scope", "worker")
            fields.setdefault("fatal", False)
            self._emitter.error(event.message or "", rc=3, **fields)
            return
        self._emitter.line(event.message or "", **fields)


def _emit_start_plan(plan: StartPlan, emitter: CliEventEmitter) -> None:
    if emitter.output_format == "jsonl":
        emitter._emit_json(
            {
                "dry_run_performs_visa_io": False,
                "dry_run_starts_http_server": False,
                "dry_run_writes_csv": False,
                "event": "dry_run",
                "schema_version": CLI_EVENT_SCHEMA_VERSION,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "trigger_mode": plan.trigger_mode,
                "measurement_type": plan.measurement_type,
                "measurement_cli_name": plan.measurement_name,
                "measurement_unit": plan.measurement_unit,
                "csv_enabled": plan.csv_enabled,
                "csv_path": plan.csv_path,
                "resource": plan.resource,
                "simulate": plan.simulate,
                "dry_run": plan.dry_run,
                "scpi_commands": plan.scpi_commands,
                "read_path": plan.read_path,
                "cleanup_steps": plan.cleanup_steps,
                "notes": plan.notes,
            }
        )
        return
    emitter.line("dry-run plan:")
    emitter.line("  performs VISA I/O: false")
    emitter.line("  writes CSV: false")
    emitter.line("  starts HTTP server: false")
    emitter.line(f"  resource: {plan.resource}")
    emitter.line(f"  measurement: {plan.measurement_name} ({plan.measurement_unit})")
    emitter.line(f"  trigger_mode: {plan.trigger_mode}")
    if plan.csv_enabled:
        emitter.line(f"  csv_path: {plan.csv_path}")
    else:
        emitter.line("  CSV output for real run: disabled")
    emitter.line(f"  simulate: {plan.simulate}")
    emitter.line("  scpi:")
    for command in plan.scpi_commands:
        emitter.line(f"    {command}")
    emitter.line(f"  read_path: {plan.read_path}")
    emitter.line(f"  cleanup: {', '.join(plan.cleanup_steps)}")
    for note in plan.notes:
        emitter.line(f"  note: {note}")
