import { t } from "./i18n.js";

const BINDINGS = Object.freeze([
  Object.freeze({ binding: "data-i18n", property: "textContent" }),
  Object.freeze({ binding: "data-i18n-placeholder", attribute: "placeholder" }),
  Object.freeze({ binding: "data-i18n-title", attribute: "title" }),
  Object.freeze({ binding: "data-i18n-aria-label", attribute: "aria-label" }),
]);
const BINDING_SELECTOR = BINDINGS.map(({ binding }) => `[${binding}]`).join(",");

function staticParams(element) {
  const raw = element.getAttribute("data-i18n-params");
  if (raw === null) {
    return undefined;
  }

  let params;
  try {
    params = JSON.parse(raw);
  } catch (error) {
    throw new TypeError(`invalid data-i18n-params JSON: ${error.message}`);
  }
  if (params === null || typeof params !== "object" || Array.isArray(params)) {
    throw new TypeError("data-i18n-params must be a JSON object");
  }
  return params;
}

export function applyStaticTranslations(root, translate = t) {
  if (root === null || root === undefined || typeof root.querySelectorAll !== "function") {
    throw new TypeError("root must provide querySelectorAll");
  }
  if (typeof translate !== "function") {
    throw new TypeError("translate must be a function");
  }

  const pending = [];
  for (const element of root.querySelectorAll(BINDING_SELECTOR)) {
    const params = staticParams(element);
    for (const binding of BINDINGS) {
      const key = element.getAttribute(binding.binding);
      if (key === null) {
        continue;
      }
      pending.push({
        element,
        binding,
        value: translate(key, params),
      });
    }
  }

  for (const { element, binding, value } of pending) {
    if (binding.property) {
      element[binding.property] = value;
    } else {
      element.setAttribute(binding.attribute, value);
    }
  }
  return pending.length;
}
