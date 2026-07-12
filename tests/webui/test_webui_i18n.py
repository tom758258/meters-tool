from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "src" / "meters_tool_webui" / "static"
NODE = shutil.which("node")


def test_i18n_modules_use_the_existing_static_root_package_layout():
    expected = {
        STATIC_DIR / "i18n.js",
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
