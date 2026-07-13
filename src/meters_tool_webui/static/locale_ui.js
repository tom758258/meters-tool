import {
  LOCALE_STORAGE_KEY,
  SUPPORTED_LOCALES,
  getLocale,
  isSupportedLocale,
  setLocale,
  t,
} from "./i18n.js";

function normalizedBrowserLanguage(value) {
  if (typeof value !== "string") {
    return "";
  }
  return value.trim().replaceAll("_", "-").toLowerCase();
}

export function browserLocaleToSupportedLocale(value) {
  const normalized = normalizedBrowserLanguage(value);
  if (
    normalized === "zh-tw" ||
    normalized.startsWith("zh-tw-") ||
    normalized === "zh-hant" ||
    normalized.startsWith("zh-hant-")
  ) {
    return "zh-TW";
  }
  return "en";
}

export function detectBrowserLocale(navigatorLike) {
  let languages;
  try {
    languages = navigatorLike?.languages;
  } catch (_error) {
    languages = null;
  }
  if (Array.isArray(languages) && languages.length > 0) {
    for (const language of languages) {
      if (typeof language === "string" && language.trim()) {
        return browserLocaleToSupportedLocale(language);
      }
    }
  }
  let language;
  try {
    language = navigatorLike?.language;
  } catch (_error) {
    language = null;
  }
  if (typeof language === "string" && language.trim()) {
    return browserLocaleToSupportedLocale(language);
  }
  return "en";
}

export function readSavedLocale(storage) {
  try {
    const saved = storage?.getItem?.(LOCALE_STORAGE_KEY);
    return isSupportedLocale(saved) ? saved : null;
  } catch (_error) {
    return null;
  }
}

export function resolveInitialLocale({ storage, navigatorLike } = {}) {
  return readSavedLocale(storage) || detectBrowserLocale(navigatorLike);
}

export function persistLocale(storage, locale) {
  if (!isSupportedLocale(locale)) {
    return false;
  }
  try {
    storage?.setItem?.(LOCALE_STORAGE_KEY, locale);
    return true;
  } catch (_error) {
    return false;
  }
}

function destinationLocale(locale) {
  return locale === "zh-TW" ? "en" : "zh-TW";
}

export function renderLanguageButton(button, label) {
  const destination = destinationLocale(getLocale());
  const labelKey = destination === "zh-TW"
    ? "locale.switch_to_zh_tw"
    : "locale.switch_to_en";
  const accessibleNameKey = destination === "zh-TW"
    ? "accessibility.switch_language_to_zh_tw"
    : "accessibility.switch_language_to_en";
  label.setAttribute("data-i18n", labelKey);
  label.removeAttribute("data-i18n-params");
  label.lang = destination;
  label.textContent = t(labelKey);
  button.setAttribute("data-i18n-aria-label", accessibleNameKey);
  button.removeAttribute("data-i18n-params");
  button.setAttribute("aria-label", t(accessibleNameKey));
}

const initializedButtons = new WeakSet();

export function initializeLocaleUi({
  button,
  label,
  documentElement,
  storage,
  navigatorLike,
  onLocaleChange,
} = {}) {
  if (!button || !label || !documentElement) {
    throw new TypeError("button, label, and documentElement are required");
  }
  if (onLocaleChange !== undefined && typeof onLocaleChange !== "function") {
    throw new TypeError("onLocaleChange must be a function");
  }

  const initialLocale = resolveInitialLocale({ storage, navigatorLike });
  setLocale(initialLocale);
  documentElement.lang = initialLocale;
  renderLanguageButton(button, label);

  if (!initializedButtons.has(button)) {
    initializedButtons.add(button);
    button.addEventListener("click", () => {
      const nextLocale = destinationLocale(getLocale());
      setLocale(nextLocale);
      documentElement.lang = nextLocale;
      renderLanguageButton(button, label);
      persistLocale(storage, nextLocale);
      onLocaleChange?.(nextLocale);
    });
  }

  return initialLocale;
}

export { LOCALE_STORAGE_KEY, SUPPORTED_LOCALES };
