import { EN_MESSAGES } from "./locale_en.js";
import { ZH_TW_MESSAGES } from "./locale_zh_tw.js";

export const SOURCE_LOCALE = "en";
export const FALLBACK_LOCALE = "en";
export const SUPPORTED_LOCALES = Object.freeze(["en", "zh-TW"]);
export const LOCALE_STORAGE_KEY = "meters-tool.webui.locale";

const TRANSLATION_KEY_PATTERN = /^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$/;
const PLACEHOLDER_PATTERN = /\{([A-Za-z_][A-Za-z0-9_]*)\}/g;
const hasOwn = (value, key) => Object.prototype.hasOwnProperty.call(value, key);

export function isSupportedLocale(value) {
  return SUPPORTED_LOCALES.includes(value);
}

function isPlainObject(value) {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function normalizeCatalogs(catalogs) {
  if (!isPlainObject(catalogs)) {
    throw new TypeError("catalogs must be a plain object");
  }

  const normalized = {};
  for (const locale of SUPPORTED_LOCALES) {
    if (!hasOwn(catalogs, locale)) {
      throw new TypeError(`catalogs must include the ${locale} catalog`);
    }
    const catalog = catalogs[locale];
    if (!isPlainObject(catalog)) {
      throw new TypeError(`catalog for ${locale} must be a plain object`);
    }
    for (const [key, message] of Object.entries(catalog)) {
      if (!TRANSLATION_KEY_PATTERN.test(key)) {
        throw new TypeError(`invalid translation key in ${locale}: ${key}`);
      }
      if (typeof message !== "string") {
        throw new TypeError(`message for ${locale}.${key} must be a string`);
      }
    }
    normalized[locale] = Object.freeze({ ...catalog });
  }

  const sourceCatalog = normalized[SOURCE_LOCALE];
  for (const locale of SUPPORTED_LOCALES) {
    if (locale === SOURCE_LOCALE) {
      continue;
    }
    for (const key of Object.keys(normalized[locale])) {
      if (!hasOwn(sourceCatalog, key)) {
        throw new TypeError(
          `message key ${key} in ${locale} is missing from the English source catalog`
        );
      }
    }
  }

  return Object.freeze(normalized);
}

function interpolate(message, params) {
  if (
    params === null ||
    params === undefined ||
    (typeof params !== "object" && typeof params !== "function")
  ) {
    return message;
  }
  return message.replace(PLACEHOLDER_PATTERN, (placeholder, name) => {
    if (!hasOwn(params, name) || params[name] === undefined) {
      return placeholder;
    }
    return String(params[name]);
  });
}

export function createI18n({ catalogs, initialLocale = SOURCE_LOCALE, onMissingKey } = {}) {
  const messages = normalizeCatalogs(catalogs);
  if (!isSupportedLocale(initialLocale)) {
    throw new RangeError(`unsupported locale: ${String(initialLocale)}`);
  }
  if (onMissingKey !== undefined && typeof onMissingKey !== "function") {
    throw new TypeError("onMissingKey must be a function");
  }

  let currentLocale = initialLocale;

  return Object.freeze({
    getLocale() {
      return currentLocale;
    },

    setLocale(locale) {
      if (!isSupportedLocale(locale)) {
        throw new RangeError(`unsupported locale: ${String(locale)}`);
      }
      currentLocale = locale;
      return currentLocale;
    },

    t(key, params) {
      if (typeof key !== "string" || key.length === 0) {
        throw new TypeError("translation key must be a non-empty string");
      }
      let message;
      if (hasOwn(messages[currentLocale], key)) {
        message = messages[currentLocale][key];
      } else if (hasOwn(messages[FALLBACK_LOCALE], key)) {
        message = messages[FALLBACK_LOCALE][key];
      } else {
        if (onMissingKey) {
          try {
            onMissingKey({
              key,
              locale: currentLocale,
              fallbackLocale: FALLBACK_LOCALE,
            });
          } catch (_error) {
            // Diagnostics must not hide the missing translation key.
          }
        }
        return key;
      }
      return interpolate(message, params);
    },
  });
}

const defaultI18n = createI18n({
  catalogs: {
    en: EN_MESSAGES,
    "zh-TW": ZH_TW_MESSAGES,
  },
});

export function getLocale() {
  return defaultI18n.getLocale();
}

export function setLocale(locale) {
  return defaultI18n.setLocale(locale);
}

export function t(key, params) {
  return defaultI18n.t(key, params);
}
