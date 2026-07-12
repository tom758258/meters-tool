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
assert.equal(ZH_TW_MESSAGES["measurement.auto_range"], "自動量程");
assert.equal(ZH_TW_MESSAGES["measurement.auto_zero"], "自動歸零");
assert.equal(ZH_TW_MESSAGES["trigger.timer"], "定時觸發");
assert.equal(ZH_TW_MESSAGES["run.start"], "開始");
assert.equal(ZH_TW_MESSAGES["run.stop"], "停止");
assert.equal(ZH_TW_MESSAGES["run.open_csv"], "開啟 CSV");
assert.equal(ZH_TW_MESSAGES["measurement.nplc"], "NPLC");
assert.match(ZH_TW_MESSAGES["device.expected_model_help"], /IDN/);
assert.match(ZH_TW_MESSAGES["live_data.time_utc_plus_8"], /UTC\+8/);

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

    assert binding_keys == catalog_keys
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
