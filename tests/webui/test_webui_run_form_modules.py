from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "src" / "meters_tool_webui" / "static"
NODE = shutil.which("node")


def run_node(script: str, *module_paths: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            NODE,
            "--input-type=module",
            "--eval",
            script,
            *(path.resolve().as_uri() for path in module_paths),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


@pytest.mark.frontend_node
@pytest.mark.skipif(NODE is None, reason="Node.js is required for run-form module tests")
def test_run_form_support_module_contracts():
    script = r"""
import assert from "node:assert/strict";

const [supportUrl] = process.argv.slice(1);
for (const name of ["document", "window", "fetch", "FormData"]) {
  Object.defineProperty(globalThis, name, {
    configurable: true,
    get() { throw new Error(`unexpected global access: ${name}`); },
  });
}

const support = await import(supportUrl);

assert.equal(support.supportsAutoZero({
  supports_auto_zero: true,
  auto_zero_options: ["on", "off", "once"],
}), true);
for (const measurement of [
  {},
  { supports_auto_zero: true },
  { supports_auto_zero: true, auto_zero_options: [] },
  { supports_auto_zero: true, auto_zero_options: ["on"] },
  { supports_auto_zero: true, auto_zero_options: "on" },
  { supports_auto_zero: false, auto_zero_options: ["on", "off"] },
]) {
  assert.equal(support.supportsAutoZero(measurement), false);
}

assert.equal(support.supportsDcvInputZ({
  supports_dcv_input_impedance: true,
  dcv_input_impedance_options: ["default", "10m", "auto"],
}), true);
for (const measurement of [
  {},
  { supports_dcv_input_impedance: true },
  { supports_dcv_input_impedance: true, dcv_input_impedance_options: [] },
  { supports_dcv_input_impedance: true, dcv_input_impedance_options: "default" },
  { supports_dcv_input_impedance: false, dcv_input_impedance_options: ["default"] },
]) {
  assert.equal(support.supportsDcvInputZ(measurement), false);
}

assert.equal(support.inferTransportScope(" usb0::sim "), "usb");
assert.equal(support.inferTransportScope("TCPIP0::sim"), "tcpip");
assert.equal(support.inferTransportScope("GPIB0::1"), null);

const openScope = {
  validation_status: "live_validated_full_suite",
  features: {
    measurement: {
      open: { validation_status: "live_validated_full_suite" },
      pending: { validation_status: "feature_pending" },
      unsupported: { validation_status: "not_supported_by_model" },
    },
  },
};
assert.deepEqual(support.featureAvailability(openScope, "measurement", "open"), {
  available: true,
  reasonKey: null,
  validationStatus: "live_validated_full_suite",
});
assert.deepEqual(support.featureAvailability(openScope, "measurement", "pending"), {
  available: false,
  reasonKey: "support.reason.pending_live_validation",
  validationStatus: "feature_pending",
});
assert.deepEqual(support.featureAvailability(openScope, "measurement", "unsupported"), {
  available: false,
  reasonKey: "support.reason.not_supported_by_model",
  validationStatus: "not_supported_by_model",
});
assert.deepEqual(support.featureAvailability(openScope, "measurement", "missing"), {
  available: false,
  reasonKey: "support.reason.scope_unavailable",
  validationStatus: "missing",
});
assert.equal(support.featureAvailability({
  validation_status: "feature_pending",
}, "measurement", "open").reasonKey, "support.reason.pending_live_validation");
assert.equal(support.featureAvailability({
  validation_status: "not_supported_by_model",
}, "measurement", "open").reasonKey, "support.reason.not_supported_by_model");
assert.equal(
  support.featureAvailability(null, "measurement", "open").validationStatus,
  "missing"
);

const triggerMetadata = {
  external: { uses_trigger_timeout: true },
  software: { uses_trigger_timeout: false },
};
assert.equal(support.usesTriggerTimeout("external", triggerMetadata), true);
assert.equal(support.usesTriggerTimeout("software", triggerMetadata), false);
assert.equal(support.usesTriggerTimeout("future-trigger", triggerMetadata), false);

process.stdout.write(JSON.stringify({ ok: true }));
"""
    completed = run_node(script, STATIC_DIR / "run_form_support.js")

    assert completed.returncode == 0, (
        "Node run_form_support.js contract failed\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert completed.stdout == '{"ok":true}'


@pytest.mark.frontend_node
@pytest.mark.skipif(NODE is None, reason="Node.js is required for run-form module tests")
def test_run_form_payload_builder_contracts():
    script = r"""
import assert from "node:assert/strict";

const [payloadUrl] = process.argv.slice(1);
for (const name of ["document", "window", "fetch", "FormData"]) {
  Object.defineProperty(globalThis, name, {
    configurable: true,
    get() { throw new Error(`unexpected global access: ${name}`); },
  });
}

const { buildExecutionRequest, buildRunPayload } = await import(payloadUrl);

const simpleValues = {
  resource: " USB0::SIM ",
  instrument_model: "",
  csv: "  ",
  timeout_ms: "",
  trigger_timeout_ms: "2500",
  trigger_mode: "immediate",
  measurement: "current-dc",
  nplc: "1",
  auto_zero: "off",
  auto_range: "on",
  measurement_range: "",
  dcv_input_impedance: "10m",
  vm_comp_slope: "",
  max_samples: "3",
};
const simpleBefore = structuredClone(simpleValues);
const simple = buildRunPayload(simpleValues, {
  measurement: {},
  triggerModeMetadata: {
    immediate: { uses_trigger_timeout: false },
  },
});
assert.deepEqual(simpleValues, simpleBefore);
assert.deepEqual(simple, {
  resource: "USB0::SIM",
  csv_enabled: true,
  csv_format: "data",
  csv_time_columns: [],
  trigger_timeout_ms: 10000,
  trigger_mode: "immediate",
  measurement: "current-dc",
  nplc: 1,
  auto_zero: "on",
  auto_range: true,
  max_samples: 3,
});

const customValues = {
  resource: "USB0::SIM",
  instrument_model: " 34461A ",
  timeout_ms: "5000",
  trigger_timeout_ms: "2500",
  trigger_mode: "software-custom",
  measurement: "voltage-dc",
  nplc: "10",
  auto_zero: "off",
  auto_range: null,
  measurement_range: "1",
  dcv_input_impedance: "10m",
  max_samples: "99",
  trigger_count: "2",
  sample_count: "3",
  buffer_drain_size: "4",
  allow_buffer_overflow_risk: "on",
  sw_min_interval_ms: "50",
  sw_queue_max: "6",
};
const custom = buildRunPayload(customValues, {
  measurement: {
    supports_auto_zero: true,
    auto_zero_options: ["on", "off", "once"],
    supports_dcv_input_impedance: true,
    dcv_input_impedance_options: ["default", "10m", "auto"],
  },
  triggerModeMetadata: {
    "software-custom": { uses_trigger_timeout: false },
  },
});
assert.equal(custom.instrument_model, "34461A");
assert.equal(custom.timeout_ms, 5000);
assert.equal(custom.trigger_timeout_ms, 10000);
assert.equal(custom.auto_zero, "off");
assert.equal(custom.auto_range, false);
assert.equal(custom.measurement_range, 1);
assert.equal(custom.dcv_input_impedance, "10m");
assert.equal(custom.trigger_count, 2);
assert.equal(custom.sample_count, 3);
assert.equal(custom.buffer_drain_size, 4);
assert.equal(custom.allow_buffer_overflow_risk, true);
assert.equal(custom.sw_min_interval_ms, 50);
assert.equal(custom.sw_queue_max, 6);
assert.equal("max_samples" in custom, false);
assert.equal("csv" in custom, false);
assert.equal(custom.csv_enabled, true);

for (const csvEnabled of ["on", true]) {
  const enabled = buildRunPayload({
    resource: "USB0::SIM",
    csv_enabled: csvEnabled,
    csv: " data/example.csv ",
  }, { measurement: {} });
  assert.equal(enabled.csv_enabled, true);
  assert.equal(enabled.csv, "data/example.csv");
  assert.equal(enabled.csv_format, "data");
}
const withTimes = buildRunPayload({
  resource: "USB0::SIM",
  csv_format: "full",
  csv_elapsed: "on",
  csv_delta: "on",
}, { measurement: {} });
assert.equal(withTimes.csv_format, "full");
assert.deepEqual(withTimes.csv_time_columns, ["elapsed", "delta"]);
for (const csvEnabled of [null, false]) {
  const disabled = buildRunPayload({
    resource: "USB0::SIM",
    csv_enabled: csvEnabled,
    csv: "data/residual.csv",
  }, { measurement: {} });
  assert.equal(disabled.csv_enabled, false);
  assert.equal("csv" in disabled, false);
}

const external = buildRunPayload({
  resource: "TCPIP0::SIM",
  trigger_timeout_ms: "2500",
  trigger_mode: "external",
  measurement: "voltage-dc",
  nplc: "1",
  auto_range: "on",
  max_samples: "5",
  hw_trigger_slope: "",
  hw_trigger_delay_s: "0.5",
  sw_min_interval_ms: "50",
  sw_queue_max: "6",
}, {
  measurement: {},
  triggerModeMetadata: {
    external: { uses_trigger_timeout: true },
  },
});
assert.equal(external.trigger_timeout_ms, 2500);
assert.equal(external.max_samples, 5);
assert.equal(external.hw_trigger_slope, "neg");
assert.equal(external.hw_trigger_delay_s, 0.5);
assert.equal(external.auto_zero, "on");
assert.equal(external.csv_enabled, true);
assert.equal("dcv_input_impedance" in external, false);
assert.equal("sw_min_interval_ms" in external, false);
assert.equal("sw_queue_max" in external, false);

const realRequest = buildExecutionRequest(simple, "real");
assert.equal(realRequest.path, "/api/runs");
assert.deepEqual(realRequest.payload, simple);

const simulateRequest = buildExecutionRequest({
  ...simple,
  resource: "TCPIP0::REAL",
  instrument_model: "34460A",
}, "simulate");
assert.equal(simulateRequest.path, "/api/runs");
assert.equal(simulateRequest.payload.resource, "SIM::34460A");
assert.equal(simulateRequest.payload.simulate, true);

const planRequest = buildExecutionRequest({
  ...simple,
  resource: "USB0::REAL",
  instrument_model: "34461A",
  simulate: true,
}, "dry-run");
assert.equal(planRequest.path, "/api/plan");
assert.equal(planRequest.payload.resource, "SIM::34461A");
assert.equal("simulate" in planRequest.payload, false);
assert.throws(
  () => buildExecutionRequest({ ...simple, instrument_model: null }, "simulate"),
  /model is required/
);

process.stdout.write(JSON.stringify({ ok: true }));
"""
    completed = run_node(script, STATIC_DIR / "run_form_payload.js")

    assert completed.returncode == 0, (
        "Node run_form_payload.js contract failed\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert completed.stdout == '{"ok":true}'
