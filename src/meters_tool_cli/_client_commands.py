from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from typing import Any
from urllib import request
from urllib.error import URLError

from meters_tool_core.command import CommandValidationError, parse_command_envelope
from meters_tool_core.validation import validate_client_port

from ._constants import CLI_EVENT_SCHEMA_VERSION


class StatusPayloadError(ValueError):
    def __init__(self, message: str, http_status: int) -> None:
        super().__init__(message)
        self.http_status = http_status


class CommandResponsePayloadError(ValueError):
    def __init__(self, message: str, http_status: int) -> None:
        super().__init__(message)
        self.http_status = http_status


def validate_client_timeout_ms(timeout_ms: int) -> None:
    if timeout_ms < 100 or timeout_ms > 600000:
        raise ValueError(f"--timeout-ms {timeout_ms} is outside the supported range 100-600000")


def _client_timeout_s(timeout_ms: int) -> float:
    return timeout_ms / 1000.0


def _emit_client_dry_run(
    command_name: str,
    port: int,
    body,  # noqa: ANN001
    output_format: str,
    *,
    method: str = "POST",
    path: str | None = None,
) -> None:
    if path is None:
        path = f"/{command_name.split('-')[-1]}"
    payload = {
        "body": body,
        "client_command": command_name,
        "endpoint": path,
        "event": "dry_run",
        "method": method,
        "ok": True,
        "port": port,
        "request_sent": False,
        "schema_version": CLI_EVENT_SCHEMA_VERSION,
        "send_request": False,
        "status": "dry_run",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "url": f"http://127.0.0.1:{port}{path}",
    }
    if output_format == "json":
        print(json.dumps(payload, sort_keys=True))
        return
    print(f"dry-run {command_name}:")
    print(f"  method: {method}")
    print(f"  url: {payload['url']}")
    print(f"  body: {json.dumps(body, sort_keys=True)}")
    print("  send_request: false")



def _client_command_name(event: str) -> str:
    return event if event != "error" else "unknown"


def _client_error_payload(
    event: str,
    port: int,
    message: str,
    exit_code: int = 3,
    *,
    client_command: str | None = None,
    error_phase: str = "request",
    request_sent: bool = True,
    reachable: bool = False,
    http_status: int | None = None,
    method: str | None = None,
    url: str | None = None,
    endpoint: str | None = None,
    timeout_ms: int | None = None,
    elapsed_ms: int | None = None,
) -> dict[str, object]:
    payload = {
        "client_command": client_command or _client_command_name(event),
        "error_phase": error_phase,
        "event": event,
        "exit_code": exit_code,
        "message": message,
        "ok": False,
        "port": port,
        "request_sent": request_sent,
        "reachable": False,
        "running": False,
        "schema_version": CLI_EVENT_SCHEMA_VERSION,
        "stopping": False,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    payload["reachable"] = reachable
    if http_status is not None:
        payload["http_status"] = http_status
    if method is not None:
        payload["method"] = method
    if url is not None:
        payload["url"] = url
    if endpoint is not None:
        payload["endpoint"] = endpoint
    if timeout_ms is not None:
        payload["timeout_ms"] = timeout_ms
    if elapsed_ms is not None:
        payload["elapsed_ms"] = elapsed_ms
    return payload


def _client_url(port: int, endpoint: str) -> str:
    return f"http://127.0.0.1:{port}{endpoint}"


def _client_http_status(exc: BaseException) -> int | None:
    http_status = getattr(exc, "http_status", None)
    if isinstance(http_status, int):
        return http_status
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    status = getattr(exc, "status", None)
    return status if isinstance(status, int) else None


def _print_client_error(
    event: str,
    port: int,
    message: str,
    output_format: str,
    *,
    error_phase: str = "request",
    request_sent: bool = True,
    reachable: bool = False,
    http_status: int | None = None,
    method: str | None = None,
    endpoint: str | None = None,
    timeout_ms: int | None = None,
    elapsed_ms: int | None = None,
) -> int:
    url = _client_url(port, endpoint) if endpoint is not None else None
    if output_format == "json":
        print(
            json.dumps(
                _client_error_payload(
                    event,
                    port,
                    message,
                    client_command=event,
                    error_phase=error_phase,
                    request_sent=request_sent,
                    reachable=reachable,
                    http_status=http_status,
                    method=method,
                    url=url,
                    endpoint=endpoint,
                    timeout_ms=timeout_ms,
                    elapsed_ms=elapsed_ms,
                ),
                sort_keys=True,
            )
        )
    else:
        print(message, file=sys.stderr)
    return 3


def _fetch_worker_status(port: int, timeout_ms: int) -> tuple[int, dict[str, object]]:
    req = request.Request(_client_url(port, "/status"), method="GET")
    with request.urlopen(req, timeout=_client_timeout_s(timeout_ms)) as response:
        http_status = int(response.status)
        raw_payload = response.read()
        try:
            worker_status = json.loads(raw_payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StatusPayloadError(
                f"status endpoint returned invalid JSON: {exc}",
                http_status,
            ) from exc
        if not isinstance(worker_status, dict):
            raise StatusPayloadError("status endpoint returned invalid JSON object", http_status)
        return http_status, worker_status


def _read_command_response(response: Any, http_status: int) -> dict[str, object]:
    raw_payload = response.read()
    if not raw_payload:
        raise CommandResponsePayloadError("command endpoint returned an empty response", http_status)
    try:
        payload = json.loads(raw_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CommandResponsePayloadError(
            f"command endpoint returned invalid JSON: {exc}",
            http_status,
        ) from exc
    if not isinstance(payload, dict):
        raise CommandResponsePayloadError(
            "command endpoint returned an invalid JSON object",
            http_status,
        )
    if payload.get("status") not in {"accepted", "rejected", "error"}:
        raise CommandResponsePayloadError(
            "command endpoint returned an invalid status",
            http_status,
        )
    if "command" not in payload or (
        payload["command"] is not None and not isinstance(payload["command"], str)
    ):
        raise CommandResponsePayloadError(
            "command endpoint returned an invalid command identity",
            http_status,
        )
    if "job_id" not in payload or (
        payload["job_id"] is not None and not isinstance(payload["job_id"], str)
    ):
        raise CommandResponsePayloadError(
            "command endpoint returned an invalid job_id identity",
            http_status,
        )
    return payload


def _normalized_status_payload(
    event: str,
    port: int,
    http_status: int,
    worker_status: dict[str, object],
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    status_value = worker_status.get("status")
    fatal_error = worker_status.get("fatal_error")
    payload = {
        "event": event,
        "client_command": event,
        "endpoint": "/status",
        "method": "GET",
        "schema_version": CLI_EVENT_SCHEMA_VERSION,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "ok": fatal_error is None,
        "reachable": True,
        "request_sent": True,
        "running": status_value == "running",
        "stopping": status_value == "stopping",
        "port": port,
        "http_status": http_status,
        "timeout_ms": extra.get("timeout_ms") if extra is not None else None,
        "url": _client_url(port, "/status"),
        "worker_schema_version": worker_status.get("schema_version"),
        "worker_timestamp_utc": worker_status.get("timestamp_utc"),
        "service": worker_status.get("service"),
        "run_id": worker_status.get("run_id"),
        "status": status_value,
        "command_url": worker_status.get("command_url"),
        "stop_url": worker_status.get("stop_url"),
        "status_url": worker_status.get("status_url"),
        "queue_size": worker_status.get("queue_size"),
        "queue_max": worker_status.get("queue_max"),
        "min_interval_ms": worker_status.get("min_interval_ms"),
        "captured": worker_status.get("captured"),
        "errors": worker_status.get("errors"),
        "fatal_error": fatal_error,
    }
    if extra is not None:
        payload.update(extra)
    if payload.get("timeout_ms") is None:
        del payload["timeout_ms"]
    return payload


def _format_status_text(prefix: str, payload: dict[str, object]) -> str:
    fatal_error = payload.get("fatal_error")
    fatal_text = "null" if fatal_error is None else str(fatal_error)
    return (
        f"{prefix}: {payload.get('status')} "
        f"captured={payload.get('captured')} "
        f"errors={payload.get('errors')} "
        f"fatal_error={fatal_text} "
        f"run_id={payload.get('run_id')}"
    )


def cmd_send_command(
    port: int,
    arguments_json: str,
    output_format: str = "text",
    dry_run: bool = False,
    timeout_ms: int = 3000,
    command: str = "software_trigger",
    job_id: str | None = None,
) -> int:
    endpoint = "/command"
    url = _client_url(port, endpoint)

    def emit_error(
        message: str,
        *,
        exit_code: int,
        error_phase: str,
        request_sent: bool,
        reachable: bool = False,
        http_status: int | None = None,
        elapsed_ms: int | None = None,
        worker_response: dict[str, object] | None = None,
    ) -> int:
        if output_format == "json":
            payload = _client_error_payload(
                "error",
                port,
                message,
                exit_code=exit_code,
                client_command="send-command",
                error_phase=error_phase,
                request_sent=request_sent,
                reachable=reachable,
                http_status=http_status,
                method="POST",
                url=url,
                endpoint=endpoint,
                timeout_ms=timeout_ms,
                elapsed_ms=elapsed_ms,
            )
            if worker_response is not None:
                for key in ("command", "job_id", "reason", "error", "message"):
                    if key in worker_response:
                        payload[key] = worker_response[key]
            print(json.dumps(payload, sort_keys=True))
        else:
            print(message, file=sys.stderr)
        return exit_code

    try:
        arguments = json.loads(arguments_json)
    except json.JSONDecodeError:
        return emit_error(
            "arguments-json must be valid JSON",
            exit_code=2,
            error_phase="validation",
            request_sent=False,
        )
    if not isinstance(arguments, dict):
        return emit_error(
            "arguments-json must be a JSON object",
            exit_code=2,
            error_phase="validation",
            request_sent=False,
        )
    envelope: dict[str, object] = {"command": command, "arguments": arguments}
    if job_id is not None:
        envelope["job_id"] = job_id
    try:
        parse_command_envelope(envelope)
    except CommandValidationError as exc:
        return emit_error(
            str(exc),
            exit_code=2,
            error_phase="validation",
            request_sent=False,
            worker_response={
                "command": exc.command,
                "job_id": exc.job_id,
                "error": "validation_error",
                "message": str(exc),
            },
        )
    if dry_run:
        _emit_client_dry_run("send-command", port, envelope, output_format, path="/command")
        return 0
    req = request.Request(
        url,
        method="POST",
        data=json.dumps(envelope, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    started_at = time.monotonic()
    try:
        with request.urlopen(req, timeout=_client_timeout_s(timeout_ms)) as response:
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            worker_response = _read_command_response(response, response.status)
            if response.status != 202 or worker_response.get("status") != "accepted":
                raise CommandResponsePayloadError(
                    "command endpoint returned a non-accepted success response",
                    response.status,
                )
            if (
                worker_response.get("command") != command
                or worker_response.get("job_id") != job_id
            ):
                raise CommandResponsePayloadError(
                    "command endpoint returned mismatched command identity",
                    response.status,
                )
            if output_format == "json":
                payload = {
                    "client_command": "send-command",
                    "elapsed_ms": elapsed_ms,
                    "endpoint": endpoint,
                    "event": "send-command",
                    "http_status": response.status,
                    "message": "command accepted",
                    "method": "POST",
                    "ok": True,
                    "port": port,
                    "reachable": True,
                    "request_sent": True,
                    "schema_version": CLI_EVENT_SCHEMA_VERSION,
                    "status": "accepted",
                    "timeout_ms": timeout_ms,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "url": url,
                }
                for key in ("command", "job_id", "reason", "error", "message"):
                    if key in worker_response:
                        payload[key] = worker_response[key]
                print(json.dumps(payload, sort_keys=True))
            else:
                print(f"command accepted: {response.status}")
    except CommandResponsePayloadError as exc:
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        return emit_error(
            str(exc),
            exit_code=3,
            error_phase="request",
            request_sent=True,
            reachable=True,
            http_status=exc.http_status,
            elapsed_ms=elapsed_ms,
        )
    except URLError as exc:
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        http_status = _client_http_status(exc)
        worker_response = None
        if http_status is not None:
            try:
                worker_response = _read_command_response(exc, http_status)
            except CommandResponsePayloadError:
                worker_response = None
        exit_code = 2 if http_status == 400 else 3
        message = (
            str(worker_response.get("message"))
            if worker_response is not None and worker_response.get("message")
            else f"command request failed: {exc}"
        )
        return emit_error(
            message,
            exit_code=exit_code,
            error_phase="validation" if http_status == 400 else "request",
            request_sent=True,
            reachable=http_status is not None,
            http_status=http_status,
            elapsed_ms=elapsed_ms,
            worker_response=worker_response,
        )
    return 0


def cmd_stop(
    port: int,
    output_format: str = "text",
    dry_run: bool = False,
    timeout_ms: int = 3000,
) -> int:
    if dry_run:
        _emit_client_dry_run("stop", port, {}, output_format, path="/stop")
        return 0
    endpoint = "/stop"
    req = request.Request(
        _client_url(port, endpoint),
        method="POST",
        data=b"{}",
        headers={"Content-Type": "application/json"},
    )
    started_at = time.monotonic()
    try:
        with request.urlopen(req, timeout=_client_timeout_s(timeout_ms)) as response:
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            if output_format == "json":
                print(
                    json.dumps(
                        {
                            "client_command": "stop",
                            "elapsed_ms": elapsed_ms,
                            "endpoint": endpoint,
                            "event": "stop",
                            "http_status": response.status,
                            "message": "stop accepted",
                            "method": "POST",
                            "ok": True,
                            "port": port,
                            "reachable": True,
                            "request_sent": True,
                            "schema_version": CLI_EVENT_SCHEMA_VERSION,
                            "status": "accepted",
                            "timeout_ms": timeout_ms,
                            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                            "url": _client_url(port, endpoint),
                        },
                        sort_keys=True,
                    )
                )
            else:
                print(f"stop accepted: {response.status}")
    except URLError as exc:
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        reason = getattr(exc, "reason", None)
        winerror = getattr(reason, "winerror", None)
        errno = getattr(reason, "errno", None)
        if winerror == 10061 or errno == 10061:
            if output_format == "json":
                print(
                    json.dumps(
                        {
                            "client_command": "stop",
                            "elapsed_ms": elapsed_ms,
                            "endpoint": endpoint,
                            "event": "stop",
                            "method": "POST",
                            "message": "already stopped (endpoint not listening)",
                            "ok": True,
                            "port": port,
                            "reachable": False,
                            "request_sent": True,
                            "schema_version": CLI_EVENT_SCHEMA_VERSION,
                            "status": "already_stopped",
                            "timeout_ms": timeout_ms,
                            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                            "url": _client_url(port, endpoint),
                        },
                        sort_keys=True,
                    )
                )
            else:
                print("already stopped (endpoint not listening)")
            return 0
        http_status = _client_http_status(exc)
        if output_format == "json":
            print(
                json.dumps(
                    _client_error_payload(
                        "error",
                        port,
                        f"stop request failed: {exc}",
                        client_command="stop",
                        error_phase="request",
                        request_sent=True,
                        reachable=http_status is not None,
                        http_status=http_status,
                        method="POST",
                        url=_client_url(port, endpoint),
                        endpoint=endpoint,
                        timeout_ms=timeout_ms,
                        elapsed_ms=elapsed_ms,
                    ),
                    sort_keys=True,
                )
            )
        else:
            print(f"stop request failed: {exc}", file=sys.stderr)
        return 3
    return 0


def cmd_status(
    port: int,
    output_format: str = "text",
    dry_run: bool = False,
    timeout_ms: int = 3000,
) -> int:
    if dry_run:
        _emit_client_dry_run(
            "status",
            port,
            None,
            output_format,
            method="GET",
            path="/status",
        )
        return 0
    try:
        started_at = time.monotonic()
        http_status, worker_status = _fetch_worker_status(port, timeout_ms)
    except (URLError, ValueError) as exc:
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        http_status = _client_http_status(exc)
        return _print_client_error(
            "status",
            port,
            f"status request failed: {exc}",
            output_format,
            error_phase="request",
            request_sent=True,
            reachable=http_status is not None,
            http_status=http_status,
            method="GET",
            endpoint="/status",
            timeout_ms=timeout_ms,
            elapsed_ms=elapsed_ms,
        )

    elapsed_ms = int((time.monotonic() - started_at) * 1000)
    payload = _normalized_status_payload(
        "status",
        port,
        http_status,
        worker_status,
        extra={"elapsed_ms": elapsed_ms, "timeout_ms": timeout_ms},
    )
    if output_format == "json":
        print(json.dumps(payload, sort_keys=True))
    else:
        print(_format_status_text("status", payload))
    return 0


def cmd_wait_ready(port: int, output_format: str = "text", timeout_ms: int = 10000) -> int:
    deadline = time.monotonic() + _client_timeout_s(timeout_ms)
    attempts = 0
    last_error: Exception | None = None
    start = time.monotonic()

    while True:
        remaining_s = deadline - time.monotonic()
        if remaining_s <= 0:
            break
        attempts += 1
        try:
            request_timeout_ms = max(1, min(1000, int(remaining_s * 1000)))
            http_status, worker_status = _fetch_worker_status(port, request_timeout_ms)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            payload = _normalized_status_payload(
                "wait-ready",
                port,
                http_status,
                worker_status,
                extra={
                    "attempts": attempts,
                    "elapsed_ms": elapsed_ms,
                    "timeout_ms": timeout_ms,
                },
            )
            if output_format == "json":
                print(json.dumps(payload, sort_keys=True))
            else:
                print(
                    "ready: "
                    f"http://127.0.0.1:{port}/status "
                    f"status={payload.get('status')} "
                    f"run_id={payload.get('run_id')}"
                )
            return 0
        except (URLError, ValueError) as exc:
            last_error = exc

        remaining_s = deadline - time.monotonic()
        if remaining_s <= 0:
            break
        time.sleep(min(0.2, remaining_s))

    message = f"timed out waiting for status endpoint after {timeout_ms} ms"
    if last_error is not None:
        message = f"{message}: {last_error}"
    if output_format == "json":
        elapsed_ms = int((time.monotonic() - start) * 1000)
        http_status = _client_http_status(last_error) if last_error is not None else None
        payload = _client_error_payload(
            "wait-ready",
            port,
            message,
            error_phase="request",
            request_sent=attempts > 0,
            reachable=http_status is not None,
            http_status=http_status,
            method="GET",
            url=_client_url(port, "/status"),
            endpoint="/status",
            timeout_ms=timeout_ms,
            elapsed_ms=elapsed_ms,
        )
        payload.update({"attempts": attempts, "elapsed_ms": elapsed_ms, "timeout_ms": timeout_ms})
        print(json.dumps(payload, sort_keys=True))
    else:
        print(message, file=sys.stderr)
    return 3


def _validate_client_port_and_timeout(args: argparse.Namespace) -> int | None:
    try:
        validate_client_port(args.port)
        validate_client_timeout_ms(args.timeout_ms)
    except ValueError as exc:
        diagnostics = {
            "send-command": ("POST", "/command"),
            "stop": ("POST", "/stop"),
            "status": ("GET", "/status"),
            "wait-ready": ("GET", "/status"),
        }
        method, endpoint = diagnostics.get(args.command, (None, None))
        if args.output_format == "json":
            print(
                json.dumps(
                    {
                        **_client_error_payload(
                            "error",
                            args.port,
                            str(exc),
                            exit_code=2,
                            client_command=args.command,
                            error_phase="validation",
                            request_sent=False,
                            method=method,
                            url=_client_url(args.port, endpoint) if endpoint is not None else None,
                            endpoint=endpoint,
                            timeout_ms=args.timeout_ms,
                        )
                    },
                    sort_keys=True,
                )
            )
        else:
            print(str(exc), file=sys.stderr)
        return 2
    return None
