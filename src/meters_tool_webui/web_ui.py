from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Literal

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import ValidationError
except ImportError as exc:  # pragma: no cover - exercised only without web deps
    raise RuntimeError(
        'Web UI dependencies are not installed. Run: uv pip install -e ".[webui]" --link-mode=copy'
    ) from exc

from meters_tool_webui._run_manager import (
    CsvFolderSelectionUnavailable as CsvFolderSelectionUnavailable,
    FALLBACK_WEBUI_VERSION as FALLBACK_WEBUI_VERSION,
    NoActiveRun as NoActiveRun,
    PACKAGE_NAME as PACKAGE_NAME,
    RunAlreadyActive as RunAlreadyActive,
    RunConnectionError as RunConnectionError,
    RunStartRequest,
    RunValidationError,
    WebRunError,
    WebRunManager,
    get_webui_version,
)
from meters_tool_webui._web_payloads import parse_software_trigger_payload


APP_JS_CACHEBUSTER_TOKEN = "__METERS_TOOL_APP_JS_CACHEBUSTER__"


class _NoStoreStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: dict[str, Any]):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"
        return response


def create_app(
    manager: WebRunManager | None = None,
    *,
    help_dir: Path | None = None,
) -> FastAPI:
    static_dir = Path(__file__).with_name("static")
    if help_dir is None:
        help_dir = static_dir / "help"
    else:
        help_dir = Path(help_dir)
    index_html = _render_index_html(static_dir)
    app = FastAPI(title="Meters Tool WebUI")
    app.state.manager = manager or WebRunManager()

    @app.get("/help/", include_in_schema=False)
    def help_index() -> FileResponse:
        target = help_dir / "webui.html"
        if not target.is_file():
            raise HTTPException(status_code=404, detail="Help not found")
        return FileResponse(str(target), headers={"Cache-Control": "no-store"})

    app.mount("/static", _NoStoreStaticFiles(directory=static_dir), name="static")
    if help_dir.is_dir():
        app.mount("/help", _NoStoreStaticFiles(directory=help_dir, html=False), name="help")

    @app.get("/")
    def index() -> HTMLResponse:
        return HTMLResponse(
            index_html,
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/capabilities")
    def api_capabilities(model: str | None = None) -> dict[str, Any]:
        try:
            return app.state.manager.capabilities(instrument_model=model)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/resources")
    def api_resources(
        verify: bool = False,
        live_only: bool = False,
        visa_library: Literal["", "@py"] | None = None,
    ) -> dict[str, Any]:
        try:
            return app.state.manager.list_resources(
                verify=verify, live_only=live_only, visa_library=visa_library
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/runs")
    async def api_start_run(request: Request) -> dict[str, Any]:
        try:
            raw_payload = json.loads((await request.body()).decode("utf-8"))
            if not isinstance(raw_payload, dict):
                raise RunValidationError("request body must be a JSON object")
            if "model_mode" in raw_payload or "modelMode" in raw_payload:
                raise RunValidationError(
                    "model_mode/modelMode is not supported; use instrument_model only"
                )
            payload = RunStartRequest(**raw_payload)
            return app.state.manager.start(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=f"malformed JSON: {exc}") from exc
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=json.loads(exc.json())) from exc
        except WebRunError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/plan")
    async def api_plan(request: Request) -> dict[str, Any]:
        try:
            raw_payload = json.loads((await request.body()).decode("utf-8"))
            if not isinstance(raw_payload, dict):
                raise RunValidationError("request body must be a JSON object")
            payload = RunStartRequest(**raw_payload)
            return app.state.manager.plan(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=f"malformed JSON: {exc}") from exc
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=json.loads(exc.json())) from exc
        except WebRunError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/runs/current")
    def api_current_run() -> dict[str, Any]:
        return app.state.manager.status()

    @app.get("/api/runs/current/events")
    def api_current_run_events() -> StreamingResponse:
        return StreamingResponse(
            app.state.manager.iter_status_events(),
            media_type="text/event-stream",
        )

    @app.post("/api/runs/current/command")
    async def api_command(request: Request) -> JSONResponse:
        try:
            payload = json.loads((await request.body()).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "error": "validation_error",
                    "message": f"malformed JSON: {exc}",
                },
            )
        try:
            command = parse_software_trigger_payload(payload)
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "error": "validation_error",
                    "message": str(exc),
                },
            )
        status_code, response = app.state.manager.send_software_trigger(command)
        return JSONResponse(status_code=status_code, content=response)

    @app.post("/api/runs/current/stop", status_code=202)
    def api_stop() -> dict[str, Any]:
        return app.state.manager.stop()

    @app.post("/api/runs/current/open-csv")
    def api_open_csv() -> dict[str, Any]:
        try:
            return app.state.manager.open_current_csv()
        except WebRunError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/csv/select-folder")
    def api_select_csv_folder() -> dict[str, Any]:
        try:
            return app.state.manager.select_csv_folder()
        except WebRunError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return app


def _render_index_html(static_dir: Path) -> str:
    template = (static_dir / "index.html").read_text(encoding="utf-8")
    if APP_JS_CACHEBUSTER_TOKEN not in template:
        raise RuntimeError("WebUI index template is missing the app.js cachebuster token")
    app_js_digest = _static_js_digest(static_dir)
    cachebuster = f"{get_webui_version()}-{app_js_digest}"
    return template.replace(APP_JS_CACHEBUSTER_TOKEN, cachebuster)


def _static_js_digest(static_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(static_dir.glob("*.js"), key=lambda item: item.name):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:12]


def _uvicorn_log_config() -> dict[str, Any]:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(levelname)s: %(message)s",
            },
            "access": {
                "format": "%(levelname)s: %(message)s",
            },
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stderr",
            },
            "access": {
                "class": "logging.StreamHandler",
                "formatter": "access",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["default"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["default"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["access"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="meters-tool-webui")
    parser.add_argument("--version", action="version", version=f"%(prog)s {get_webui_version()}")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args(argv)

    manager = WebRunManager()
    server = create_uvicorn_server(manager, host=args.host, port=args.port)
    _run_uvicorn_server(server)
    return 0


def create_uvicorn_server(
    manager: WebRunManager,
    *,
    host: str,
    port: int,
    access_log: bool = True,
) -> Any:
    import uvicorn

    class WebUiServer(uvicorn.Server):
        def handle_exit(self, sig: int, frame: Any) -> None:
            try:
                if not manager.shutdown():
                    logging.getLogger(__name__).error(
                        "Timed out waiting for the active WebUI run to finish cleanup."
                    )
            except Exception:
                logging.getLogger(__name__).exception(
                    "Failed to gracefully shut down the active WebUI run."
                )
            finally:
                super().handle_exit(sig, frame)

    config = uvicorn.Config(
        create_app(manager),
        host=host,
        port=port,
        lifespan="off",
        log_config=_uvicorn_log_config(),
        access_log=access_log,
    )
    return WebUiServer(config=config)


def _run_uvicorn_server(server: Any) -> None:
    try:
        server.run()
    except KeyboardInterrupt:
        pass


app = create_app()


if __name__ == "__main__":
    raise SystemExit(main())
