# Keysight Logger Web UI Project Plan

Updated: 2026-05-29

## Purpose

This branch owns the Web UI adapter for the Keysight 34461A acquisition
runtime. Current WebUI status and handoff notes live in
`docs/session-handoff.md`; `docs/session-handoff.md` is only a thin
branch-neutral handoff index. Core public API rules live in
`docs/integration.md`; WebUI-specific UI rules live in
`docs/web-ui-ai-change-rules.md`; hardware validation workflow lives in
`docs/hardware-test-plan.md`.

The Web UI provides a local browser console and FastAPI adapter around the Core
runtime. It must preserve the existing UI surface while using Core request
validation, runtime orchestration, trigger routing, and cleanup behavior.

## Current Baseline

Release tag target: `webui-v1.2.1`.

The maintained runtime boundary is:

- Core API and acquisition runtime: `keysight_logger_core`
- Web UI adapter and HTTP endpoints: `packages/webui/src/keysight_logger_webui/web_ui.py`
- Static browser UI: `packages/webui/src/keysight_logger_webui/static/`

The distribution metadata is `keysight-logger-webui` version `1.2.1`. It
publishes the WebUI console script `keysight-logger-webui` and the
double-click GUI launcher script `keysight-logger-webui-launcher`; install them
through uv.

```powershell
uv pip install -e ".[dev]" --link-mode=copy
.\.venv\Scripts\keysight-logger-webui.exe --version
.\.venv\Scripts\keysight-logger-webui.exe --port 8767
.\.venv\Scripts\keysight-logger-webui-launcher.exe
```

The Web UI supports the Core measurement and trigger modes surfaced by
`/api/capabilities`:

- `current-dc`
- `voltage-dc`
- `voltage-dc-ratio`
- `current-ac`
- `voltage-ac`
- `resistance-2w`
- `resistance-4w`
- `software`, including optional software timer
- `external`
- `immediate`
- `immediate-custom`
- `software-custom`
- `external-custom`

The Live data panel displays the latest Core sample event, a browser-side trend
chart, the latest 100 serialized samples, and selected-sample metadata from the
existing WebUI status polling path.

## Architecture

`packages/webui/src/keysight_logger_webui/web_ui.py` converts WebUI request payloads into Core
`StartRequest` objects, validates with Core, builds the Core start plan for
adapter-visible status, then starts `run_start_session()` on a background
thread.

The Web UI owns only adapter concerns:

- FastAPI route shape.
- Browser-facing status payloads.
- Browser-facing Live data sample window.
- Resource scan endpoint serialization.
- Open CSV endpoint behavior.
- WebUI trigger and stop buttons.
- Static HTML, CSS, and JavaScript.

Core owns the instrument-affecting path:

- Instrument/backend creation.
- Measurement setup.
- Trigger router and acquisition worker.
- CSV writer.
- Stop controller.
- Release-to-local, close, cleanup release, and control-plane shutdown order.

The Web UI control plane publishes software trigger and stop events into the
Core router. It must not call acquisition engine internals, close VISA handles,
or reorder cleanup.

## Documentation Index

- Core contract: `docs/integration.md`
- User guide: `docs/USER_GUIDE.md`
- Detailed WebUI README: `docs/Webui-README.md`
- Web UI rules: `docs/web-ui-ai-change-rules.md`
- Web UI handoff: `docs/session-handoff.md`
- Branch handoff index: `docs/session-handoff.md`
- Hardware validation: `docs/hardware-test-plan.md`
- Historical validation: `docs/validation-history.md`
- Supported models: `docs/supported-models.md`

## Validation Workflow

Focused no-hardware validation:

```powershell
uv run pytest tests/test_web_ui.py tests/test_core_public_api.py tests/test_core_validation.py tests/test_core_run_plan.py tests/test_core_runner.py packages/webui/tests/test_webui_package_metadata.py packages/webui/tests/test_webui_docs_ownership.py -q -p no:cacheprovider
```

Then run the broader suite when practical:

```powershell
uv run pytest tests -q -p no:cacheprovider
```

Live validation requires an operator-provided VISA resource and should follow
`docs/hardware-test-plan.md`.

## Safety Rules

- Do not change SCPI behavior without explicit user approval.
- Do not change VISA timeout strategy without explicit user approval.
- Do not change trigger wait strategy, `TRIG:DEL`, NPLC, Auto Zero, Auto Range,
  VM Comp, stop behavior, release/local behavior, or cleanup order without
  explicit user approval.
- Keep WebUI stop routed through the Core control path. VISA I/O belongs on the
  Core worker or cleanup path.
- Hardware trigger timeout remains a protective re-arm condition, not a capture
  error by itself.
- Hardware-triggered simple reads use Core's `FETC?` path after the trigger
  adapter arms and completes measurement.
- Software-triggered and immediate simple reads use Core's `READ?` path.

## Roadmap

1. Keep WebUI tests and Core contract tests green after merge points.
2. Keep the UI behavior aligned with `docs/web-ui-ai-change-rules.md`.
3. Record WebUI-specific validation in `docs/session-handoff.md` and
   `docs/validation-history.md`.
4. Run manual browser smoke validation before real instrument use.
5. Keep new instrument/model support in Core first, then expose it through
   `/api/capabilities`.
