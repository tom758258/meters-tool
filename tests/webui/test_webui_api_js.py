from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "src" / "meters_tool_webui" / "static"
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="Node.js is required for api.js runtime tests")
def test_api_preserves_structured_command_errors_and_http_contract():
    script = r"""
import assert from "node:assert/strict";

const apiUrl = process.argv[1];
const presentationUrl = process.argv[2];
for (const name of ["document", "window", "navigator", "localStorage"]) {
  Object.defineProperty(globalThis, name, {
    configurable: true,
    get() { throw new Error(`unexpected global access: ${name}`); },
  });
}

const { api } = await import(apiUrl);
const { browserErrorPresentation } = await import(presentationUrl);

let nextResponse;
const requests = [];
globalThis.fetch = async (path, options) => {
  requests.push({ path, options });
  return {
    ok: nextResponse.ok,
    statusText: nextResponse.statusText,
    text: async () => JSON.stringify(nextResponse.payload),
  };
};

async function rejectedMessage(payload, expected, statusText = "Conflict") {
  nextResponse = { ok: false, payload, statusText };
  await assert.rejects(
    () => api("/api/runs/current/command", { method: "POST", body: "{}" }),
    (error) => error instanceof Error && error.message === expected
  );
}

await rejectedMessage({
  detail: "resource is required",
  message: "ignored message",
  reason: "ignored_reason",
}, "resource is required");
await rejectedMessage({
  detail: [{ loc: ["body", "resource"], msg: "field required" }],
}, "body.resource: field required");
await rejectedMessage({
  detail: { code: "custom_error" },
}, '{"code":"custom_error"}');

for (const [payload, expectedMessage, expectedPresentation, statusText] of [
  [
    { message: "no active run" },
    "no active run",
    { kind: "translated", key: "error.command_no_active_run", params: {} },
    "Conflict",
  ],
  [
    { message: "run is not ready" },
    "run is not ready",
    { kind: "translated", key: "error.command_not_ready", params: {} },
    "Conflict",
  ],
  [
    { reason: "queue_full" },
    "queue_full",
    { kind: "raw", text: "queue_full" },
    "Too Many Requests",
  ],
  [
    { reason: "rate_limited" },
    "rate_limited",
    { kind: "raw", text: "rate_limited" },
    "Too Many Requests",
  ],
]) {
  await rejectedMessage(payload, expectedMessage, statusText);
  assert.deepEqual(browserErrorPresentation(expectedMessage), expectedPresentation);
}

await rejectedMessage({
  message: "run is not ready",
  reason: "queue_full",
}, "run is not ready");
await rejectedMessage({ message: "", reason: "" }, "Conflict");
await rejectedMessage({}, "Conflict");

nextResponse = { ok: true, payload: { status: "accepted" }, statusText: "Accepted" };
const success = await api("/api/example", { method: "POST", body: '{"value":1}' });
assert.deepEqual(success, { status: "accepted" });
const request = requests.at(-1);
assert.equal(request.path, "/api/example");
assert.equal(request.options.method, "POST");
assert.equal(request.options.body, '{"value":1}');
assert.equal(request.options.headers["Content-Type"], "application/json");

process.stdout.write(JSON.stringify({ ok: true }));
"""
    completed = subprocess.run(
        [
            NODE,
            "--input-type=module",
            "--eval",
            script,
            (STATIC_DIR / "api.js").resolve().as_uri(),
            (STATIC_DIR / "presentation_i18n.js").resolve().as_uri(),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, (
        "Node api.js structured-error contract failed\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert completed.stdout == '{"ok":true}'


def test_api_module_stays_transport_only():
    source = (STATIC_DIR / "api.js").read_text(encoding="utf-8")
    for forbidden in (
        'from "./i18n.js"',
        "from './i18n.js'",
        "setLocale(",
        "navigator.language",
        "navigator.languages",
        "localStorage",
        "document.",
    ):
        assert forbidden not in source
    assert re.search(r"(?<![\w.])t\s*\(", source) is None
