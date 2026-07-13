from __future__ import annotations

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "src" / "meters_tool_webui" / "static"
NODE = shutil.which("node")


def test_i18n_modules_use_the_existing_static_root_package_layout():
    expected = {
        STATIC_DIR / "i18n.js",
        STATIC_DIR / "dom_i18n.js",
        STATIC_DIR / "locale_en.js",
        STATIC_DIR / "locale_zh_tw.js",
    }

    assert all(path.is_file() for path in expected)
    assert not (STATIC_DIR / "locales").exists()
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"static/*.js"' in pyproject


@pytest.mark.skipif(NODE is None, reason="Node.js is required for ES-module runtime tests")
def test_i18n_es_module_runtime_contract():
    script = r"""
import assert from "node:assert/strict";

const [i18nUrl, enUrl, zhTwUrl] = process.argv.slice(1);
const guardedGlobals = [
  "document",
  "window",
  "navigator",
  "localStorage",
  "fetch",
  "XMLHttpRequest",
  "EventSource",
];
const globalAccesses = [];
for (const name of guardedGlobals) {
  Object.defineProperty(globalThis, name, {
    configurable: true,
    get() {
      globalAccesses.push(name);
      throw new Error(`unexpected global access: ${name}`);
    },
  });
}

const i18n = await import(i18nUrl);
const enModule = await import(enUrl);
const zhTwModule = await import(zhTwUrl);
const { EN_MESSAGES } = enModule;
const { ZH_TW_MESSAGES } = zhTwModule;

assert.equal(i18n.SOURCE_LOCALE, "en");
assert.equal(i18n.FALLBACK_LOCALE, "en");
assert.deepEqual(i18n.SUPPORTED_LOCALES, ["en", "zh-TW"]);
assert.equal(i18n.LOCALE_STORAGE_KEY, "meters-tool.webui.locale");
assert.equal(Object.isFrozen(i18n.SUPPORTED_LOCALES), true);
assert.equal(Object.isFrozen(EN_MESSAGES), true);
assert.equal(Object.isFrozen(ZH_TW_MESSAGES), true);
assert.equal(enModule.default, EN_MESSAGES);
assert.equal(zhTwModule.default, ZH_TW_MESSAGES);
assert.deepEqual(Object.keys(EN_MESSAGES), Object.keys(ZH_TW_MESSAGES));
assert.equal(Object.keys(EN_MESSAGES).length > 0, true);
for (const catalog of [EN_MESSAGES, ZH_TW_MESSAGES]) {
  for (const message of Object.values(catalog)) {
    assert.equal(typeof message, "string");
    assert.equal(message.length > 0, true);
  }
}
assert.equal(EN_MESSAGES["app.title"], "Meters Tool");
assert.equal(ZH_TW_MESSAGES["app.title"], "Meters Tool");
assert.equal(ZH_TW_MESSAGES["app.unofficial_tool"], "非官方工具");
assert.equal(ZH_TW_MESSAGES["resource.visa_resource"], "VISA 資源");
assert.equal(ZH_TW_MESSAGES["measurement.heading"], "量測");
assert.equal(EN_MESSAGES["measurement.auto_range"], "Auto range");
assert.equal(ZH_TW_MESSAGES["measurement.auto_range"], "自動量程（Auto range）");
assert.equal(EN_MESSAGES["measurement.summary.auto_range"], "Auto range");
assert.equal(ZH_TW_MESSAGES["measurement.summary.auto_range"], "自動量程");
assert.equal(EN_MESSAGES["measurement.summary_initial"], "Auto range, auto zero");
assert.equal(ZH_TW_MESSAGES["measurement.summary_initial"], "自動量程、自動歸零");
assert.equal(ZH_TW_MESSAGES["measurement.auto_zero"], "自動歸零");
assert.equal(ZH_TW_MESSAGES["trigger.timer"], "定時觸發");
assert.equal(ZH_TW_MESSAGES["run.start"], "開始");
assert.equal(ZH_TW_MESSAGES["run.stop"], "停止");
assert.equal(ZH_TW_MESSAGES["run.open_csv"], "開啟 CSV");
assert.equal(ZH_TW_MESSAGES["measurement.nplc"], "NPLC");
assert.match(ZH_TW_MESSAGES["device.expected_model_help"], /IDN/);
assert.match(ZH_TW_MESSAGES["live_data.time_utc_plus_8"], /UTC\+8/);

const p23Keys = [
  "app.unofficial_tool_version",
  "common.off", "common.on", "common.unset",
  "error.trigger_metadata_invalid_json", "error.trigger_metadata_not_object",
  "measurement.auto_zero_once", "measurement.keep_current_setting",
  "measurement.option.current_ac", "measurement.option.current_dc",
  "measurement.option.frequency", "measurement.option.period",
  "measurement.option.resistance_2w", "measurement.option.resistance_4w",
  "measurement.option.voltage_ac", "measurement.option.voltage_dc",
  "measurement.option.voltage_dc_ratio", "measurement.option_label",
  "measurement.select_range", "measurement.summary", "measurement.summary.ac_band",
  "measurement.summary.ac_filter", "measurement.summary.auto_range",
  "measurement.summary.auto_zero", "measurement.summary.gate",
  "measurement.summary.manual_range", "measurement.summary.nplc",
  "measurement.summary.separator", "measurement.summary.terminal",
  "measurement.summary.timeout", "measurement.summary_label",
  "measurement.terminal_value", "measurement.value_hz",
  "measurement.value_seconds", "run.summary", "run.summary_with_max",
  "support.reason.not_supported_by_model",
  "support.reason.pending_live_validation", "support.reason.scope_unavailable",
  "support.unavailable_option", "trigger.option.external",
  "trigger.option.external_custom", "trigger.option.immediate",
  "trigger.option.immediate_custom", "trigger.option.software",
  "trigger.option.software_custom", "trigger.option_label",
  "trigger.summary.mode", "trigger.summary.timer", "validation.interval_range",
];
for (const key of p23Keys) {
  assert.equal(typeof EN_MESSAGES[key], "string", `missing en key ${key}`);
  assert.equal(typeof ZH_TW_MESSAGES[key], "string", `missing zh-TW key ${key}`);
  assert.notEqual(EN_MESSAGES[key], "");
  assert.notEqual(ZH_TW_MESSAGES[key], "");
}
assert.equal(ZH_TW_MESSAGES["support.reason.scope_unavailable"], "目前的傳輸／後端範圍不可用");
assert.equal(ZH_TW_MESSAGES["support.reason.not_supported_by_model"], "型號不支援");
assert.equal(ZH_TW_MESSAGES["support.reason.pending_live_validation"], "等待實機驗證");
assert.equal(ZH_TW_MESSAGES["measurement.option.voltage_dc"], "直流電壓");
assert.equal(ZH_TW_MESSAGES["measurement.option.resistance_2w"], "二線式電阻");
assert.equal(ZH_TW_MESSAGES["trigger.option.software_custom"], "軟體自訂");

const p24Keys = [
  "accessibility.collapse_device_resource", "accessibility.expand_device_resource",
  "accessibility.toggle_sample_details", "common.default", "device.auto_detect",
  "device.resource_summary", "error.command_no_active_run",
  "error.command_not_ready", "error.csv_folder_selector_unavailable",
  "error.csv_not_found", "error.csv_run_active", "error.csv_unavailable",
  "error.model_idn_mismatch", "error.model_mode_unsupported",
  "error.request_json_object", "error.resource_required", "error.run_active",
  "live_data.column_details", "live_data.no_sample_selected", "live_data.no_samples",
  "live_data.range_step_auto_range", "live_data.range_step_requires_manual_range",
  "live_data.recent_sample_summary", "live_data.scale_info.auto_absolute",
  "live_data.scale_info.auto_deviation", "live_data.scale_info.manual_span",
  "live_data.scale_info.manual_span_invalid", "live_data.scale_info.range_step",
  "live_data.scale.auto_absolute", "live_data.scale.auto_deviation",
  "live_data.scale.manual_span", "live_data.scale.range_step",
  "live_data.selected_sample", "live_data.waiting_samples",
  "resource.live_model", "resource.live_selected",
  "resource.model_inference_failed", "resource.no_live_resources",
  "resource.no_resource", "resource.not_scanned", "resource.option_with_detail",
  "resource.scan_result_count", "resource.scanning", "resource.select_live",
  "resource.status.live", "resource.status.stale",
  "run.csv_folder_selection_cancelled", "run.csv_path_selected",
  "run.opened_csv", "run.opening_csv_folder_selector",
  "status.active_run_scan_blocked", "status.active_run_start_blocked",
  "status.active_run_unload_warning", "status.error", "status.hide_details",
  "status.idle",
  "status.ready", "status.recording_stopped", "status.running",
  "status.software_trigger_queued", "status.sse_connection_lost_polling",
  "status.sse_unavailable_polling", "status.starting", "status.stop_requested",
  "status.stopped", "status.stopping", "status.waiting_software_custom_trigger",
  "status.show_details", "status.waiting_trigger", "validation.check_run_settings",
  "validation.visa_resource_required",
];
for (const key of p24Keys) {
  assert.equal(typeof EN_MESSAGES[key], "string", `missing en key ${key}`);
  assert.equal(typeof ZH_TW_MESSAGES[key], "string", `missing zh-TW key ${key}`);
  assert.notEqual(EN_MESSAGES[key], "");
  assert.notEqual(ZH_TW_MESSAGES[key], "");
}
assert.equal(ZH_TW_MESSAGES["status.running"], "執行中");
assert.equal(ZH_TW_MESSAGES["status.waiting_trigger"], "等待觸發");
assert.equal(ZH_TW_MESSAGES["status.software_trigger_queued"], "軟體觸發已排入佇列");
assert.equal(ZH_TW_MESSAGES["live_data.no_samples"], "尚無取樣");
assert.equal(
  ZH_TW_MESSAGES["live_data.range_step_requires_manual_range"],
  "量程步進需要關閉自動量程並選擇手動量程。"
);

const p25Keys = [
  "support.limit.no_10a_current_path",
  "support.limit.no_base_profile_external_trigger",
  "support.limit.no_current_terminal_selection",
  "support.limit.reading_memory_1000",
  "support.pending.keysight_34460a_dcv_ratio_live_validation",
  "support.pending.lan_tcpip_pyvisa_py_validation",
  "support.pending.lan_tcpip_system_visa_validation",
  "support.runtime_driver.detected_idn",
  "support.status.not_open",
  "support.status.profile_workflows_validated",
  "support.status.usb_system_visa_validated",
  "support.summary.auto_detect_status",
  "support.summary.none",
  "support.summary.profile_status",
  "support.summary.selected_model",
  "support.summary.status_unavailable",
  "support.summary.unspecified_backend",
  "support.summary.unspecified_transport",
  "support.workflow.custom_buffered",
  "support.workflow.external_trigger",
  "support.workflow.frequency",
  "support.workflow.immediate",
  "support.workflow.period",
  "support.workflow.software",
  "support.workflow.software_timer",
];
for (const key of p25Keys) {
  assert.equal(typeof EN_MESSAGES[key], "string", `missing en key ${key}`);
  assert.equal(typeof ZH_TW_MESSAGES[key], "string", `missing zh-TW key ${key}`);
  assert.notEqual(EN_MESSAGES[key], "");
  assert.notEqual(ZH_TW_MESSAGES[key], "");
}
assert.equal(ZH_TW_MESSAGES["support.summary.none"], "無");
assert.equal(
  ZH_TW_MESSAGES["support.runtime_driver.detected_idn"],
  "實機執行型號由偵測到的 *IDN? 決定。"
);
assert.equal(
  ZH_TW_MESSAGES["support.workflow.external_trigger"],
  "外部觸發工作流程"
);
assert.equal(
  ZH_TW_MESSAGES["support.limit.no_current_terminal_selection"],
  "無法選擇電流端子"
);

const productionZh = i18n.createI18n({
  catalogs: { en: EN_MESSAGES, "zh-TW": ZH_TW_MESSAGES },
  initialLocale: "zh-TW",
});
assert.equal(
  productionZh.t("measurement.option_label", {
    name: productionZh.t("measurement.option.voltage_dc"),
    canonical: "voltage-dc",
    unit: "V",
  }),
  "直流電壓（voltage-dc，V）"
);
assert.equal(
  productionZh.t("trigger.option_label", {
    name: productionZh.t("trigger.option.software_custom"),
    canonical: "software-custom",
  }),
  "軟體自訂（software-custom）"
);
assert.equal(
  productionZh.t("validation.interval_range", { min: 50, max: 600000 }),
  "使用 0 停用節流，或使用 50–600000 ms。"
);
assert.equal(
  productionZh.t("resource.scan_result_count", { count: 3 }),
  "找到的實機資源：3"
);
assert.equal(
  productionZh.t("run.csv_path_selected", { path: "C:\\meter\\out.csv" }),
  "已選取 CSV 路徑：C:\\meter\\out.csv"
);
assert.equal(
  productionZh.t("error.model_idn_mismatch", {
    selected: "34460A", connected: "34461A",
  }),
  "選取的型號 34460A 與已連接儀器的 IDN 34461A 不符。請選取 34461A 或重新掃描裝置。"
);
assert.equal(
  productionZh.t("live_data.selected_sample", { sequence: 17 }),
  "取樣 #17"
);
assert.equal(
  productionZh.t("live_data.scale_info.range_step", {
    center: "1.2 V", span: "3 V", grid: "0.6 V",
  }),
  "量程步進：中心 1.2 V / 跨度 3 V / 格線 0.6 V"
);
assert.equal(
  productionZh.t("support.summary.auto_detect_status", {
    profile: "34461A",
    runtime_note: productionZh.t("support.runtime_driver.detected_idn"),
    validation_status: "live_validated_full_suite",
    transport: "tcpip",
    backend: "system_visa",
  }),
  (
    "自動偵測：目前顯示 34461A 的備援功能檢視，直到開始或掃描時偵測到 IDN。" +
    "實機執行型號由偵測到的 *IDN? 決定。" +
    "（live_validated_full_suite，tcpip/system_visa）"
  )
);
assert.equal(
  productionZh.t("support.summary.profile_status", {
    model: "34460A",
    status: productionZh.t("support.status.usb_system_visa_validated"),
    validation_status: "live_validated_full_suite",
    transport: "usb",
    backend: "system_visa",
  }),
  "34460A：USB/system-VISA 已完成完整測試套件驗證。（live_validated_full_suite，usb/system_visa）"
);
assert.equal(productionZh.t("p23.unknown_key"), "p23.unknown_key");

assert.equal(i18n.getLocale(), "en");
assert.equal(i18n.setLocale("zh-TW"), "zh-TW");
assert.equal(i18n.getLocale(), "zh-TW");
assert.throws(() => i18n.setLocale("ZH-tw"), RangeError);
assert.equal(i18n.getLocale(), "zh-TW");
assert.equal(i18n.setLocale("en"), "en");

for (const value of ["en", "zh-TW"]) {
  assert.equal(i18n.isSupportedLocale(value), true);
}
for (const value of ["", "EN", "zh-tw", "zh-Hant", null, undefined, 1, {}]) {
  assert.equal(i18n.isSupportedLocale(value), false);
}

const enCatalog = {
  "test.greeting": "Hello {name}",
  "test.count": "Captured {count} samples; {count} total",
  "test.fallback": "English fallback",
  "test.undefined": "Value {value}",
  "test.literal": "Content {value}",
};
const zhTwCatalog = {
  "test.greeting": "你好 {name}",
  "test.count": "已擷取 {count} 筆；共 {count} 筆",
  "test.undefined": "值 {value}",
  "test.literal": "內容 {value}",
};
const catalogs = { en: enCatalog, "zh-TW": zhTwCatalog };
const before = JSON.stringify(catalogs);
const missing = [];
const translator = i18n.createI18n({
  catalogs,
  initialLocale: "zh-TW",
  onMissingKey(info) {
    missing.push(info);
  },
});

assert.equal(translator.getLocale(), "zh-TW");
assert.equal(translator.t("test.greeting", { name: "世界" }), "你好 世界");
assert.equal(translator.t("test.fallback"), "English fallback");
assert.equal(translator.t("test.missing"), "test.missing");
assert.deepEqual(missing, [{
  key: "test.missing",
  locale: "zh-TW",
  fallbackLocale: "en",
}]);
assert.throws(() => translator.t(null), TypeError);
assert.throws(() => translator.t(""), TypeError);

assert.equal(translator.t("test.count", { count: 3, extra: "ignored" }), "已擷取 3 筆；共 3 筆");
assert.equal(translator.t("test.greeting", {}), "你好 {name}");
assert.equal(translator.t("test.undefined", { value: undefined }), "值 {value}");
const inheritedParams = Object.create({ name: "prototype value" });
assert.equal(translator.t("test.greeting", inheritedParams), "你好 {name}");
const malicious = "<img src=x onerror=alert(1)>";
assert.equal(translator.t("test.literal", { value: malicious }), `內容 ${malicious}`);

assert.equal(translator.setLocale("en"), "en");
assert.equal(translator.getLocale(), "en");
assert.equal(translator.t("test.greeting", { name: "Ada" }), "Hello Ada");
assert.throws(() => translator.setLocale("fr"), RangeError);
assert.equal(translator.getLocale(), "en");
assert.equal(JSON.stringify(catalogs), before);

const second = i18n.createI18n({ catalogs });
assert.equal(second.getLocale(), "en");
assert.equal(second.setLocale("zh-TW"), "zh-TW");
assert.equal(translator.getLocale(), "en");

Object.prototype["test.prototype"] = "inherited message";
try {
  assert.equal(translator.t("test.prototype"), "test.prototype");
} finally {
  delete Object.prototype["test.prototype"];
}

assert.throws(() => i18n.createI18n(), TypeError);
assert.throws(() => i18n.createI18n({ catalogs: [] }), TypeError);
assert.throws(() => i18n.createI18n({ catalogs: { en: {} } }), TypeError);
assert.throws(() => i18n.createI18n({ catalogs: { "zh-TW": {} } }), TypeError);
assert.throws(
  () => i18n.createI18n({ catalogs: { en: [], "zh-TW": {} } }),
  TypeError
);
assert.throws(
  () => i18n.createI18n({ catalogs: { en: { "test.bad": 1 }, "zh-TW": {} } }),
  TypeError
);
assert.throws(
  () => i18n.createI18n({ catalogs: { en: { bad: "value" }, "zh-TW": {} } }),
  TypeError
);
assert.throws(
  () => i18n.createI18n({
    catalogs: {
      en: {},
      "zh-TW": { "test.zh_only": "只有繁中" },
    },
  }),
  /test\.zh_only.*zh-TW.*English source catalog/i
);
const englishOnly = i18n.createI18n({
  catalogs: {
    en: { "test.english_only": "English fallback" },
    "zh-TW": {},
  },
  initialLocale: "zh-TW",
});
assert.equal(englishOnly.t("test.english_only"), "English fallback");
assert.throws(() => i18n.createI18n({ catalogs, initialLocale: "fr" }), RangeError);
assert.throws(() => i18n.createI18n({ catalogs, onMissingKey: true }), TypeError);

assert.deepEqual(globalAccesses, []);
process.stdout.write(JSON.stringify({ ok: true }));
"""
    completed = subprocess.run(
        [
            NODE,
            "--input-type=module",
            "--eval",
            script,
            (STATIC_DIR / "i18n.js").resolve().as_uri(),
            (STATIC_DIR / "locale_en.js").resolve().as_uri(),
            (STATIC_DIR / "locale_zh_tw.js").resolve().as_uri(),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, (
        f"Node i18n contract failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert completed.stdout == '{"ok":true}'


@pytest.mark.skipif(NODE is None, reason="Node.js is required for ES-module runtime tests")
def test_dom_i18n_es_module_runtime_contract():
    script = r"""
import assert from "node:assert/strict";

const [domI18nUrl] = process.argv.slice(1);
const guardedGlobals = [
  "document",
  "window",
  "navigator",
  "localStorage",
  "fetch",
  "XMLHttpRequest",
  "EventSource",
];
const globalAccesses = [];
for (const name of guardedGlobals) {
  Object.defineProperty(globalThis, name, {
    configurable: true,
    get() {
      globalAccesses.push(name);
      throw new Error(`unexpected global access: ${name}`);
    },
  });
}

const { applyStaticTranslations } = await import(domI18nUrl);
assert.deepEqual(globalAccesses, []);

class FakeElement {
  constructor(attributes = {}) {
    this.attributes = { ...attributes };
    this.textContent = "English fallback";
    this.innerHTML = "unchanged markup";
    this.id = "protected-id";
    this.name = "protected-name";
    this.value = "protected-value";
    this.className = "protected-class";
  }

  getAttribute(name) {
    return Object.hasOwn(this.attributes, name) ? this.attributes[name] : null;
  }

  setAttribute(name, value) {
    this.attributes[name] = value;
  }
}

const textElement = new FakeElement({ "data-i18n": "test.text" });
const placeholderElement = new FakeElement({
  "data-i18n-placeholder": "test.placeholder",
  placeholder: "English placeholder",
});
const multiElement = new FakeElement({
  "data-i18n-title": "test.model",
  "data-i18n-aria-label": "test.model",
  "data-i18n-params": '{"model":"34461A"}',
  title: "English title",
  "aria-label": "English label",
  "data-mode-scope": "software",
  "aria-controls": "protected-controls",
  "aria-expanded": "true",
});
const maliciousElement = new FakeElement({ "data-i18n": "test.malicious" });
const elements = [textElement, placeholderElement, multiElement, maliciousElement];
const messages = {
  "test.text": "Translated text",
  "test.placeholder": "Translated placeholder",
  "test.model": "Require {model}",
  "test.malicious": "<img src=x onerror=alert(1)>",
};
const translate = (key, params) => messages[key].replace(
  /\{([A-Za-z_][A-Za-z0-9_]*)\}/g,
  (placeholder, name) => params && Object.hasOwn(params, name) ? String(params[name]) : placeholder
);
const root = {
  querySelectorAll(selector) {
    assert.equal(
      selector,
      "[data-i18n],[data-i18n-placeholder],[data-i18n-title],[data-i18n-aria-label]"
    );
    return elements;
  },
};

assert.equal(applyStaticTranslations(root, translate), 5);
assert.equal(textElement.textContent, "Translated text");
assert.equal(placeholderElement.attributes.placeholder, "Translated placeholder");
assert.equal(multiElement.attributes.title, "Require 34461A");
assert.equal(multiElement.attributes["aria-label"], "Require 34461A");
assert.equal(maliciousElement.textContent, "<img src=x onerror=alert(1)>");
assert.equal(maliciousElement.innerHTML, "unchanged markup");
assert.equal(multiElement.id, "protected-id");
assert.equal(multiElement.name, "protected-name");
assert.equal(multiElement.value, "protected-value");
assert.equal(multiElement.className, "protected-class");
assert.equal(multiElement.attributes["data-mode-scope"], "software");
assert.equal(multiElement.attributes["aria-controls"], "protected-controls");
assert.equal(multiElement.attributes["aria-expanded"], "true");

assert.throws(() => applyStaticTranslations(null, translate), TypeError);
assert.throws(() => applyStaticTranslations({}, translate), TypeError);
assert.throws(() => applyStaticTranslations(root, null), TypeError);
for (const raw of ["not json", "[]", "null"]) {
  const untouched = new FakeElement({ "data-i18n": "test.text" });
  const invalid = new FakeElement({
    "data-i18n": "test.text",
    "data-i18n-params": raw,
  });
  const invalidRoot = { querySelectorAll() { return [untouched, invalid]; } };
  assert.throws(() => applyStaticTranslations(invalidRoot, translate), TypeError);
  assert.equal(untouched.textContent, "English fallback");
}

assert.deepEqual(globalAccesses, []);
process.stdout.write(JSON.stringify({ ok: true }));
"""
    completed = subprocess.run(
        [
            NODE,
            "--input-type=module",
            "--eval",
            script,
            (STATIC_DIR / "dom_i18n.js").resolve().as_uri(),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, (
        f"Node DOM i18n contract failed\nstdout:\n{completed.stdout}"
        f"\nstderr:\n{completed.stderr}"
    )
    assert completed.stdout == '{"ok":true}'


class _StaticTextBindingParser(HTMLParser):
    void_elements = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta"}

    def __init__(self):
        super().__init__()
        self.stack = []
        self.unbound_text = []
        self.bound_fallbacks = []

    @staticmethod
    def _params(attributes):
        raw = attributes.get("data-i18n-params")
        return json.loads(raw) if raw is not None else {}

    def _record_attribute_bindings(self, attributes):
        params = self._params(attributes)
        for binding, attribute in [
            ("data-i18n-placeholder", "placeholder"),
            ("data-i18n-title", "title"),
            ("data-i18n-aria-label", "aria-label"),
        ]:
            if binding in attributes:
                self.bound_fallbacks.append(
                    (attributes[binding], params, attributes[attribute])
                )

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self._record_attribute_bindings(attributes)
        self.stack.append({"tag": tag, "attributes": attributes, "text": []})
        if tag in self.void_elements:
            self.stack.pop()

    def handle_startendtag(self, _tag, attrs):
        self._record_attribute_bindings(dict(attrs))

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1]["tag"] == tag:
            frame = self.stack.pop()
            attributes = frame["attributes"]
            if "data-i18n" in attributes:
                self.bound_fallbacks.append(
                    (
                        attributes["data-i18n"],
                        self._params(attributes),
                        "".join(frame["text"]).strip(),
                    )
                )

    def handle_data(self, data):
        text = data.strip()
        if self.stack:
            self.stack[-1]["text"].append(data)
        if text and self.stack and "data-i18n" not in self.stack[-1]["attributes"]:
            self.unbound_text.append(text)


def test_static_html_bindings_cover_p2_2_prose_and_preserve_fallbacks():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    en_source = (STATIC_DIR / "locale_en.js").read_text(encoding="utf-8")
    catalog_entries = re.findall(
        r'^  ("[a-z][a-z0-9_.]+"):\s+(".*"),$', en_source, re.MULTILINE
    )
    messages = {
        json.loads(raw_key): json.loads(raw_message)
        for raw_key, raw_message in catalog_entries
    }
    catalog_keys = set(messages)
    binding_keys = set(
        re.findall(
            r'data-i18n(?:-placeholder|-title|-aria-label)?="([a-z][a-z0-9_.]+)"',
            html,
        )
    )

    dynamic_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in STATIC_DIR.glob("*.js")
    )
    dynamic_keys = set(re.findall(r'"([a-z][a-z0-9_.]+)"', dynamic_source))
    assert binding_keys <= catalog_keys
    assert catalog_keys - binding_keys <= dynamic_keys
    assert '<html lang="en">' in html
    for fallback in [
        "Meters Tool",
        "Unofficial Tool",
        "Device / Resource",
        "Run Setup",
        "Measurement options",
        "Trigger options",
        "Live data",
        "No samples captured",
        "Show Details",
    ]:
        assert fallback in html

    parser = _StaticTextBindingParser()
    parser.feed(html)
    allowed_raw = {"-", "X", "A", "CSV", "10M", "0", "--", "⚙"}
    assert set(parser.unbound_text) <= allowed_raw
    for key, params, fallback in parser.bound_fallbacks:
        expected = re.sub(
            r"\{([A-Za-z_][A-Za-z0-9_]*)\}",
            lambda match: str(params.get(match.group(1), match.group(0))),
            messages[key],
        )
        assert fallback == expected

    for tag in re.findall(r"<[^>]+>", html):
        if "placeholder=" in tag and not any(raw in tag for raw in ['placeholder="0.01"', 'placeholder="{&quot;batch&quot;']):
            assert "data-i18n-placeholder=" in tag
        if " title=" in tag:
            assert "data-i18n-title=" in tag
        if "aria-label=" in tag:
            assert "data-i18n-aria-label=" in tag

    assert 'placeholder="0.01"' in html
    assert 'placeholder="{&quot;batch&quot;:&quot;A1&quot;}"' in html
    assert "data-i18n-placeholder" not in re.search(
        r'<textarea\b[^>]*id="trigger-metadata"[^>]*>', html
    ).group(0)
