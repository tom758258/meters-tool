# WebUI Localization Contract

## Purpose And Phase Boundary

This contract governs localization of the browser WebUI. The first maintained
locales are `en` and `zh-TW`. English is the complete source locale and the
mandatory fallback locale.

Phase 2 Part 0 (P2.0) completed this contract and the current-text inventory.
Locale runtime, translation dictionaries, and language switching are not
implemented in P2.0. P2.1 provides the dependency-free runtime foundation.
P2.2 registers the static browser prose from `index.html` in English and
Traditional Chinese catalogs, adds explicit text, placeholder, title, and
ARIA-label bindings, then applies them once at startup using the singleton's
default English locale.
Nothing in this document claims that the current WebUI can switch languages.

The Windows launcher GUI is outside this browser-localization scope unless a
separate change is approved. CLI output, Core messages, CSV, JSON, and JSONL
are not localized by this phase.

### P2.1-P2.5 Foundation And Current Status

P2.1 adds three native ES modules at the static root:

- `locale_en.js` exports the frozen English source catalog `EN_MESSAGES`;
- `locale_zh_tw.js` exports the frozen Traditional Chinese catalog
  `ZH_TW_MESSAGES`;
- `i18n.js` exports the locale contract and translator API.

The production catalogs contain the matching P2.2 static HTML key set, the P2.3
dynamic run-form presentation, and the P2.4 app/resource, status/log, Live data,
dynamic ARIA, and recognized browser-error presentation. English fallback
literals remain in `index.html`, and the browser applies the static bindings
once before the existing UI initialization. Dynamic translated nodes render
through the same singleton and retain semantic binding metadata where
practical. Status comparisons, suppression, de-duplication, software-trigger
burst handling, and control decisions continue to use raw machine values.
Unknown Core/backend/status diagnostics remain raw fallbacks, and raw status
JSON, sample metadata, and schemas are not translated. Browser HTTP errors keep
FastAPI `detail` as first priority, then preserve structured command-response
`message` and raw `reason` values before the HTTP status-text fallback. Exact
known command messages may therefore use semantic browser translations, while
unknown rejection reasons remain raw diagnostics. The singleton still starts
in English, so the currently rendered UI remains English.

P2.5 adds `status_key`, `runtime_driver_note_key`,
`open_workflow_keys`, `limit_keys`, and `pending_keys` as additive
support-summary presentation metadata. The existing English prose fields
remain unchanged API fallbacks. The browser prefers recognized semantic keys,
but the prose lists remain the authoritative inventory: missing, malformed,
unknown, short, or long key lists safely fall back positionally to prose and
cannot add entries. Raw validation status, transport, backend, model, and
profile values remain machine values. The latest raw support summary is cached
so its presentation can be recomputed without another capability request.

There is no active language selector, browser detection, saved-locale lookup,
`<html lang>` update, or runtime locale-switch wiring; P2.6 owns locale
selection and switching. API endpoints, Core, support policy, SCPI, VISA,
trigger, acquisition, CSV, JSON, JSONL, SSE, and cleanup contracts are
unchanged. The current inventory remains the authoritative ownership record.

The runtime exports these constants:

```text
SOURCE_LOCALE = "en"
FALLBACK_LOCALE = "en"
SUPPORTED_LOCALES = ["en", "zh-TW"] (frozen)
LOCALE_STORAGE_KEY = "meters-tool.webui.locale"
```

`LOCALE_STORAGE_KEY` defines the future persistence contract only; P2.1 does
not access storage. `isSupportedLocale(value)` accepts only the two exact
maintained identifiers. It does not map browser language results.

`createI18n({ catalogs, initialLocale, onMissingKey })` creates an isolated
translator with `getLocale()`, `setLocale(locale)`, and `t(key, params)`.
Catalog input must be a plain object containing plain-object catalogs for both
maintained locales. Keys must follow the flat semantic key convention, and
every message value must be a string. The factory validates and freezes
shallow copies without mutating caller-owned catalogs. A valid explicit
`initialLocale` is used; otherwise the initial locale is `en`. An invalid
explicit locale raises `RangeError`.

`setLocale(locale)` accepts only an exact maintained identifier, changes only
that translator's internal locale, and returns the resulting locale. A
rejected locale raises `RangeError` without changing the previous locale.
The production singleton is exposed through module-level `getLocale()`,
`setLocale(locale)`, and `t(key, params)` functions and starts in English.

`t(key, params)` requires a non-empty string key and looks up the current
catalog first, then the English source catalog. A key missing from both
catalogs is returned unchanged. The optional missing-key callback receives an
object containing `key`, `locale`, and `fallbackLocale`; diagnostics cannot
replace or hide the returned key.

Named interpolation replaces `{name}`-style placeholders only from matching
own properties in `params`, using ordinary string conversion. Repeated
placeholders are supported, extra parameters are ignored, and missing or
undefined parameters remain visible. Interpolation neither parses nor
executes markup. The runtime reads no DOM, browser locale, storage, or network
state and triggers no application action.

P2.2 adds `applyStaticTranslations(root, translate)` in `dom_i18n.js`. The
adapter recognizes only `data-i18n`, `data-i18n-placeholder`,
`data-i18n-title`, and `data-i18n-aria-label`, with optional JSON-object
parameters from `data-i18n-params`. It validates and translates all pending
bindings before writing through `textContent` or fixed safe attributes. Module
import has no DOM, storage, browser-locale, network, or application side effect.

## Locked Product Decisions

### Supported Locales And Initial Selection

The maintained locale identifiers are exactly:

- `en`
- `zh-TW`

The future initial-locale precedence is:

1. A valid locale saved in `localStorage`.
2. Browser language detection.
3. English fallback.

The persistence key is `meters-tool.webui.locale`. A saved value outside the
maintained locale set is ignored. Browser results `zh-TW` and `zh-Hant` select
`zh-TW`; every other browser-language result selects `en`. Browser detection is
used only until the user makes a manual selection.

### Manual Language Control

The future browser UI must permanently provide one language button in the main
toolbar at the top right. It is independent from the Device options gear and
must not be hidden in Settings, a hamburger menu, or another dialog. While
there are only two maintained locales, it is a one-click toggle, not a
dropdown.

The button is a normal keyboard-operable `<button>` with a globe SVG and
visible text. The SVG is `aria-hidden`. The visible text names the destination
locale: the English UI shows `繁體中文`, and the Traditional Chinese UI shows
`English`. Its accessible name also describes the destination locale, and the
destination-language label has its own `lang` attribute.

Switching language must apply immediately without a page reload. It must not:

- stop an active run or issue a Start, Trigger, or Stop request;
- clear the VISA resource, CSV path, or any form value;
- change canonical measurement or trigger values;
- reset panel state, live samples, chart state, status, or other runtime UI state.

The switch updates `<html lang>` to `en` or `zh-TW` and saves the manual choice
under `meters-tool.webui.locale`. A third maintained locale may justify a
language menu, but that is not part of v2.0.0.

## Ownership And Architecture Boundary

WebUI owns browser presentation only. Core owns request validation, profile
resolution, support policy, SCPI, VISA, acquisition, trigger routing, storage,
stop, and cleanup. Translation must never become authorization. Disabled
controls remain UX guidance only; Core remains authoritative for normal
browser submissions and forged or stale requests.

Translated values are display-only. Raw machine values remain the inputs to
runtime, validation, policy, comparison, suppression, and control decisions.

WebUI localization must not import CLI code. Core must not depend on
localization or browser locale state. The browser locale must not be sent to
Core to alter runtime behavior, validation, capability selection, or support
policy.

## Non-Translatable Machine Contracts

The following contracts must remain byte-for-byte canonical where the existing
contract requires it. Display text may be translated around a token, but the
token itself and submitted value remain unchanged.

In particular, localization must preserve API fields, canonical values, and
runtime schemas.

| Contract | Protected examples |
| --- | --- |
| Endpoint paths | `/api/capabilities`, `/api/resources`, `/api/runs`, `/api/runs/current`, `/api/runs/current/events`, `/api/runs/current/command`, `/api/runs/current/stop`, `/api/runs/current/open-csv`, `/api/csv/select-folder` |
| HTTP contract | Methods, status behavior, media types, and validation envelopes |
| API fields | All request and response field names, including command envelope fields |
| SSE contract | Event name `run-status`, event IDs, data shape, and keepalive behavior |
| Measurement values | `voltage-dc`, `current-dc`, `frequency`, and every other canonical measurement value |
| Trigger values | `software`, `software-custom`, `external`, and every other canonical trigger mode |
| Model identity | `34460A`, `34461A`, `keysight-34460a`, `keysight-34461a` |
| Runtime values | Transport/backend values, support-policy statuses, run states, and command names such as `software_trigger` |
| DOM/form contracts | Form `name` attributes, contract element IDs, and `data-*` scope values |
| File/runtime schemas | CSV headers and metadata; JSON and JSONL keys; raw status JSON; trigger metadata keys |
| Error contracts | Core exception content and machine-readable error, reason, status, and command fields |

For example, a translated label may render `直流電壓（voltage-dc）`, but the
request must still submit:

```json
{"measurement": "voltage-dc"}
```

Units and technical tokens are not translated. Locale-aware display formatting
must never rewrite a canonical payload, raw sample value, schema, or stored
file.

## Translation-Key Contract

Future keys use dot-separated namespaces and lowercase `snake_case` segments.
Keys describe semantic concepts, not complete English prose. A key must not use
a DOM ID as its only meaning, an array index, an embedded locale name, or a
full English sentence.

Recommended namespaces are:

```text
common.*
app.*
device.*
resource.*
run.*
measurement.*
trigger.*
live_data.*
status.*
support.*
validation.*
error.*
accessibility.*
```

Representative keys include:

```text
resource.scan_button
resource.scan_in_progress
run.setup_heading
measurement.auto_range
trigger.software_custom
status.software_trigger_queued
support.reason.pending_live_validation
error.trigger_metadata_invalid_json
accessibility.collapse_device_resource
```

Parameterized concepts such as `resource.scan_result_count`,
`status.captured_count`, and `validation.interval_range` receive named values.
Interpolation values are inserted as text, never HTML. Unknown parameters must
not execute markup or script. Plural-sensitive messages must not be assembled
with fragile string concatenation.

English must define every maintained key. A missing `zh-TW` key falls back to
English. A missing English key is a contract and test failure. Unknown keys
remain diagnosable and must not silently render an empty string. P2.1
implements lookup, fallback, and interpolation; P2.2 owns the static HTML key
set and bindings, while later Parts own dynamic message keys and language
selection.

## User-Visible Text Inventory

### Classification

| Treatment | Meaning |
| --- | --- |
| `translate` | Browser-owned presentation text receives a locale entry. |
| `translate_with_canonical_token` | Explanatory text is translated while the embedded/submitted technical token stays canonical. |
| `preserve_raw` | Diagnostic, unknown backend text, metadata, path, or raw data stays visible in its original form. |
| `machine_value` | A value used by logic, transport, storage, API, DOM, or schema is never translated. |
| `not_user_visible` | Internal selector, source marker, console diagnostic, or metadata not rendered in the product UI. |
| `out_of_scope` | User-visible content outside browser localization, such as the Windows launcher. |

Identical text is consolidated where its source locations and surfaces are
listed together. `--`, punctuation-only collapse glyphs, numeric values, units,
IDs, `name`, `value`, and `data-*` attributes are not translation prose.

### `static/index.html`

| Source | Surface/function | Current literal or pattern | Content type | Future treatment | Proposed key or namespace | Planned Part |
| --- | --- | --- | --- | --- | --- | --- |
| `index.html` | Document and toolbar | `Meters Tool` (title and heading) | product name | `translate_with_canonical_token` (name preserved) | `app.title` | P2.2 |
| `index.html` | Toolbar subtitle | `Unofficial Tool` | visible text | `translate` | `app.unofficial_tool` | P2.2 |
| `index.html` | Device section | `Device / Resource`; `No resource / not scanned / Auto-detect` | heading/empty summary | `translate` | `device.resource_heading`, `device.summary_empty` | P2.2 |
| `index.html` | Device options | `Device options` in heading, `title`, and `aria-label` | visible/accessibility | `translate` | `device.options`, `accessibility.device_options` | P2.2 |
| `index.html` | Model selector | `Expected model`; `Auto-detect`; `Require 34460A`; `Require 34461A` | label/options | `translate_with_canonical_token` | `device.expected_model`, `device.auto_detect`, `device.require_model` | P2.2/P2.3 |
| `index.html` | Model help | `Auto-detect uses ... runtime driver.` | help text | `translate_with_canonical_token` | `device.expected_model_help` | P2.2 |
| `index.html` | Support summary | `Model support`; `Loading support status`; `Open`; `Limits`; `Pending` | headings/initial state | `translate` | `support.heading`, `support.loading`, `support.open`, `support.limits`, `support.pending` | P2.2 |
| `index.html` | Device collapse | `Collapse Device / Resource` | `aria-label` | `translate` | `accessibility.collapse_device_resource` | P2.2 |
| `index.html` | Resource controls | `VISA resource`; `Waiting Scan`; `Live resource`; `Scan to load live resources`; `Scan Device` | labels/placeholder/option/button | `translate_with_canonical_token` for VISA; otherwise `translate` | `resource.*` | P2.2 |
| `index.html` | Run panel | `Run Setup`; `Software current-dc` | heading/initial summary | `translate_with_canonical_token` | `run.setup_heading`, `run.summary_initial` | P2.2 |
| `index.html` | CSV control | `CSV path`; `(Optional)`; `Select`; `Default` | label/marker/button/placeholder | `translate_with_canonical_token` for CSV; otherwise `translate` | `run.csv_path`, `common.optional`, `common.select`, `common.default` | P2.2 |
| `index.html` | Run selectors | `Measurement`; `Trigger mode` | labels | `translate` | `measurement.heading`, `trigger.mode` | P2.2 |
| `index.html` | Run limits | `Timeout ms`; `Trigger timeout ms`; `Max samples`; `Default: 5000`; `Default: 10000`; `Default: Unlimited` | labels/placeholders | `translate_with_canonical_token` | `run.timeout_ms`, `trigger.timeout_ms`, `run.max_samples`, `common.default_value` | P2.2 |
| `index.html` | Measurement panel | `Measurement options`; `Auto range, auto zero` | heading/initial summary | `translate` | `measurement.options_heading`, `measurement.summary_initial` | P2.2 |
| `index.html` | Range controls | `Auto range`; `Range`; initial `A` unit | label/unit | label `translate`; unit `machine_value` | `measurement.auto_range`, `measurement.range` | P2.2 |
| `index.html` | Measurement controls | `Auto zero`; `NPLC`; `AC filter`; `Gate time`; `Timeout`; `Current terminal` | labels | `translate_with_canonical_token` where technical | `measurement.*` | P2.2 |
| `index.html` | DCV/VM controls | `DCV input Z`; `Default`; `10M`; `Auto`; `VM Comp slope`; `Leave unchanged`; `Pos`; `Neg` | labels/options | `translate_with_canonical_token` | `measurement.dcv_input_z`, `measurement.vm_comp_slope`, `common.*` | P2.2 |
| `index.html` | Trigger panel | `Trigger options`; `Software trigger ready`; `Timer trigger` | heading/summary/label | `translate` | `trigger.options_heading`, `trigger.summary_initial`, `trigger.timer` | P2.2 |
| `index.html` | Custom trigger | `Trigger count`; `Sample count`; `Buffer drain size`; `Default: No limit`; `Allow buffer risk` | labels/placeholder | `translate` | `trigger.trigger_count`, `trigger.sample_count`, `trigger.buffer_drain_size`, `trigger.allow_buffer_risk` | P2.2 |
| `index.html` | Hardware trigger | `HW delay s`; `HW slope`; `Neg`; `Pos`; `Default: 0` | labels/options/placeholder | `translate_with_canonical_token` | `trigger.hardware_delay_s`, `trigger.hardware_slope`, `common.negative`, `common.positive` | P2.2 |
| `index.html` | Software trigger | `SW min interval ms`; `SW queue max`; `Default: 0 (Disabled)` | labels/placeholders | `translate_with_canonical_token` | `trigger.software_min_interval_ms`, `trigger.software_queue_max`, `common.disabled_default` | P2.2 |
| `index.html` | Timer/metadata | `Timer interval s`; `Trigger metadata JSON`; `{"batch":"A1"}` | labels/example placeholder | labels `translate_with_canonical_token`; example `preserve_raw` | `trigger.timer_interval_s`, `trigger.metadata_json` | P2.2 |
| `index.html` | Live data header | `Live data`; `No samples captured` | heading/empty state | `translate` | `live_data.heading`, `live_data.no_samples` | P2.2 |
| `index.html` | Run metrics | `State`; `Sample`; `Errors`; hidden `CSV`; `Idle`; hidden `Default` | labels/defaults | labels/defaults `translate`; CSV token preserved | `status.state`, `status.sample`, `status.errors`, `status.idle`, `common.default` | P2.2 |
| `index.html` | Run controls | `Start`; `Trigger`; `Stop`; `Open CSV` | buttons | `translate_with_canonical_token` for CSV; otherwise `translate` | `run.start`, `trigger.send`, `run.stop`, `run.open_csv` | P2.2 |
| `index.html` | Latest sample | `Latest`; `Time UTC+8`; `Trigger` | labels | `translate_with_canonical_token` for UTC+8 | `live_data.latest`, `live_data.time_utc_plus_8`, `trigger.heading` | P2.2 |
| `index.html` | Trend section | `Trend`; `Scale mode`; `Auto deviation`; `Auto absolute`; `Manual span`; `Range step` | heading/labels/options | `translate` | `live_data.trend`, `live_data.scale_mode`, `live_data.scale.*` | P2.2 |
| `index.html` | Trend help | `Range step disabled because Auto range is on.`; `0.01`; `Live sample value trend`; `Waiting for samples` | help/placeholder/ARIA/empty state | text `translate`; numeric placeholder `machine_value` | `live_data.range_step_auto_range`, `accessibility.live_sample_trend`, `live_data.waiting_samples` | P2.2 |
| `index.html` | Statistics | `Statistics`; `Live sample statistics`; `Min`; `Average`; `Max`; `Span`; `Std dev`; `Sample` | heading/ARIA/labels | `translate` | `live_data.statistics`, `accessibility.live_statistics`, `live_data.stat.*` | P2.2 |
| `index.html` | Recent table | `Recent samples`; `Recent live samples`; `Seq`; `Time UTC+8`; `Value`; `Unit`; `Trigger`; `Status`; `Details`; `No samples captured` | heading/ARIA/columns/empty state | `translate_with_canonical_token` where technical | `live_data.recent_samples`, `accessibility.recent_samples`, `live_data.column.*` | P2.2 |
| `index.html` | Sample details | `Sample details`; `No sample selected`; `Close sample details`; visible `X` | label/state/ARIA | `translate` (`X` remains glyph) | `live_data.sample_details`, `live_data.no_sample_selected`, `accessibility.close_sample_details` | P2.2 |
| `index.html` | Status panel | `Status`; `Show Details`; `Status log` | heading/button/ARIA | `translate` | `status.heading`, `status.show_details`, `accessibility.status_log` | P2.2 |
| `index.html` | Contract attributes | IDs, form names/values, `data-*` scopes, units, `lang="en"` baseline | machine/DOM contract | `machine_value` | none | P2.1/P2.2 (preserve) |

### `static/app.js`

| Source | Surface/function | Current literal or pattern | Content type | Future treatment | Proposed key or namespace | Planned Part |
| --- | --- | --- | --- | --- | --- | --- |
| `app.js` | Collapse controls | `Collapse Device / Resource`; `Expand Device / Resource`; `-`; `+` | ARIA/glyph | labels `translate`; glyphs `not_user_visible` prose | `accessibility.collapse_device_resource`, `accessibility.expand_device_resource` | P2.4 |
| `app.js` | Resource summary | `not scanned`; `live {model}`; `live selected`; `Auto-detect`; `No resource`; `{resource} / ...` | dynamic summary | `translate_with_canonical_token` | `resource.summary.*`, `device.auto_detect` | P2.4 |
| `app.js` | Inference notice | `Live resource model could not be inferred; Start will auto-detect it.` | browser log | `translate_with_canonical_token` | `resource.model_inference_failed` | P2.4 |
| `app.js` | Scan progress/results | `Scanning live resources...`; `Select live resource`; `No live resources found`; `Live resources found: {count}` | log/options/count template | `translate` | `resource.scan_in_progress`, `resource.select_live`, `resource.none_found`, `resource.scan_result_count` | P2.4 |
| `app.js` | Scan option | `{resource} ({status}: {detail})` | dynamic result | wrapper `translate`; resource/status/detail `preserve_raw` | `resource.scan_result_detail` | P2.4 |
| `app.js` | Scan warning | `Stop the active run before scanning resources.` | browser log | `translate` | `run.stop_before_scan` | P2.4 |
| `app.js` | CSV selection | `Opening CSV folder selector...`; `CSV path selected: {path}`; `CSV folder selection cancelled` | log/path template | wrapper `translate`; path `preserve_raw` | `run.csv_selector_opening`, `run.csv_path_selected`, `run.csv_selection_cancelled` | P2.4 |
| `app.js` | Range-step notice | `Range step disabled because Auto range is on.` | dynamic help | `translate` | `live_data.range_step_auto_range` | P2.4 |
| `app.js`, `status.js` | Active-run warnings | `A run is already active. Stop it before starting another run.`; `Stop the active run before scanning resources.` | browser log | `translate` | `run.already_active`, `run.stop_before_scan` | P2.4 |
| `app.js` | Start validation | `Select or enter a VISA resource before Start`; `Check highlighted run settings before Start` | browser validation/log | `translate_with_canonical_token` | `validation.resource_required`, `validation.run_settings` | P2.4 |
| `app.js` | Open CSV result | `Opened CSV: {path}` | log/path template | wrapper `translate`; path `preserve_raw` | `run.csv_opened` | P2.4 |
| `app.js` | Raw caught error | `error.message` from scan, capability, CSV, Start, Trigger, Stop, Open CSV, initial load | unknown diagnostic | `preserve_raw` | none; optional translated wrapper only | P2.4 |
| `app.js` | API and command values | endpoint strings, `software_trigger`, request field names, raw `latest_status === "software trigger queued"` | logic/API contract | `machine_value` | none | P2.1/P2.4 (preserve) |

### `static/run_form.js`

| Source | Surface/function | Current literal or pattern | Content type | Future treatment | Proposed key or namespace | Planned Part |
| --- | --- | --- | --- | --- | --- | --- |
| `run_form.js` | Availability reasons | `Not available for current transport/backend scope`; `Not supported by model`; `Pending live validation` | option title/reason | `translate` | `support.reason.*` | P2.3 |
| `run_form.js` | Feature options | `{label} — {reason}`; option `title={reason}` | label/title template | `translate_with_canonical_token` | `support.unavailable_option` | P2.3 |
| `run_form.js` | Measurement options | `{Capitalize(canonical measurement)} ({unit})` | dynamic label | `translate_with_canonical_token` | `measurement.<canonical concept>` | P2.3 |
| `run_form.js` | Trigger options | capitalized canonical trigger mode | dynamic label | `translate_with_canonical_token` | `trigger.<canonical concept>` | P2.3 |
| `run_form.js` | Interval validity | `Use 0 to disable throttling, or use {min}-{max} ms.` | custom validity/template | `translate_with_canonical_token` | `validation.interval_range` | P2.3 |
| `run_form.js` | Metadata errors | `Trigger metadata must be valid JSON object`; `Trigger metadata must be a JSON object` | browser error | `translate_with_canonical_token` | `error.trigger_metadata_invalid_json`, `error.trigger_metadata_not_object` | P2.3 |
| `run_form.js` | Auto Zero options | `On`; `Off`; `Once` | dynamic options | `translate` | `common.on`, `common.off`, `measurement.auto_zero_once` | P2.3 |
| `run_form.js` | AC filter options | `{value} Hz`; `Keep current setting` | dynamic options | label `translate`; value/unit `machine_value` | `measurement.ac_filter_value`, `measurement.keep_current_setting` | P2.3 |
| `run_form.js` | Gate/timeout/terminal | `{value} s`; `Auto`; `1 s`; `Default`; `{value} A` | dynamic options | labels `translate`; values/units `machine_value` | `measurement.value_seconds`, `common.auto`, `common.default`, `measurement.terminal_value` | P2.3 |
| `run_form.js` | Range/NPLC | `Select range`; Core `range_options[].label`; numeric NPLC labels | options | prompt `translate`; Core label `translate_with_canonical_token`; numbers `machine_value` | `measurement.select_range`, `measurement.range_value` | P2.3 |
| `run_form.js` | Run summary | `{Mode} / {measurement} / max {count}` | panel summary | `translate_with_canonical_token` | `run.summary` | P2.3 |
| `run_form.js` | Measurement summary | `Auto range`; `Manual range`; `Auto zero {value}`; `NPLC {value}`; `AC Filter >{value} Hz`; `AC Band {value} Hz`; `Gate {value} s`; `Timeout {value}`; `Terminal {value} A` | dynamic summary fragments | `translate_with_canonical_token` | `measurement.summary.*` | P2.3 |
| `run_form.js` | Trigger summary | `Timer {value|unset} s`; `{Mode} trigger`; `unset` | dynamic summary | `translate_with_canonical_token` | `trigger.summary_timer`, `trigger.summary_mode`, `common.unset` | P2.3 |
| `run_form.js` | App subtitle | `Unofficial Tool v{version}` / `Unofficial Tool` | dynamic title | `translate_with_canonical_token` | `app.unofficial_tool_version`, `app.unofficial_tool` | P2.3 |
| `run_form.js` | Support fallback | `selected model`; `Support status unavailable.`; `unknown`; `unspecified transport`; `unspecified backend` | fallback prose/tokens | prose `translate`; unknown machine tokens `preserve_raw` | `support.summary.*` | P2.5 |
| `run_form.js` | Auto-detect support | `Auto-detect: showing {profile} fallback capability view until Start or Scan detects IDN. {note} ({validation}, {transport}/{backend})` | dynamic support template | `translate_with_canonical_token`; raw fields preserved | `support.summary.auto_detect_status` | P2.5 |
| `run_form.js` | Explicit support | `{model}: {status_text} ({validation}, {transport}/{backend})` | dynamic support template | wrapper `translate`; existing prose fallback/raw tokens preserved | `support.summary.profile_status` | P2.5 |
| `run_form.js` | Support lists | comma-joined `open_workflows`, `limits`, `pending`; empty `None` | server prose/fallback | semantic keys preferred; positionally matched prose remains authoritative fallback; `None` `translate` | `support.summary.none`, `support.*` | P2.5 |
| `run_form.js` | Model selector | `Auto-detect`; `Require {model}` | dynamic options | `translate_with_canonical_token` | `device.auto_detect`, `device.require_model` | P2.3 |
| `run_form.js` | Canonical logic | measurement/trigger/model/status/backend values, payload keys, scope comparisons, `en-US` numeric formatting | machine/runtime logic | `machine_value` | none | P2.1/P2.3 (preserve) |

### `static/status.js`

| Source | Surface/function | Current literal or pattern | Content type | Future treatment | Proposed key or namespace | Planned Part |
| --- | --- | --- | --- | --- | --- | --- |
| `status.js` | Before unload | `A measurement run is active. Refreshing or closing the page will not stop it.` | browser warning | `translate` | `run.active_before_unload` | P2.4 |
| `status.js` | Detail toggle | `Show Details`; `Hide Details` | button text | `translate` | `status.show_details`, `status.hide_details` | P2.4 |
| `status.js` | State display | capitalized raw `status.state`, default `idle` | known/unknown status | known values `translate`; unknown `preserve_raw` | `status.state.*` | P2.4 |
| `status.js` | Default CSV | `Default` | fallback display | `translate` | `common.default` | P2.4 |
| `status.js` | Control warnings | active-run and stop-before-scan warnings | browser log | `translate` | `run.already_active`, `run.stop_before_scan` | P2.4 |
| `status.js` | SSE fallback | `SSE unavailable, falling back to polling`; `SSE connection lost, falling back to polling` | browser log | `translate_with_canonical_token` | `status.sse_unavailable`, `status.sse_lost` | P2.4 |
| `status.js` | Known statuses | `idle`; `waiting trigger`; `waiting software custom trigger`; `software trigger queued` | raw logic/status | comparisons `machine_value`; rendered known label `translate` | `status.idle`, `status.waiting_trigger`, `status.waiting_software_custom_trigger`, `status.software_trigger_queued` | P2.4 |
| `status.js` | Backend status log | `latest_status` after capitalization | backend text | known status display `translate`; unknown text `preserve_raw` | `status.*` where known | P2.4 |
| `status.js` | Fatal/cleanup | raw `fatal_error`; raw `cleanup_status` | diagnostic | `preserve_raw` | optional translated labels only | P2.4 |
| `status.js` | Raw details | `JSON.stringify(status, null, 2)` | raw status JSON | `preserve_raw` | none | P2.4 |
| `status.js` | SSE parse console error | `Failed to parse SSE data:` | developer console | `not_user_visible` | none | P2.4 |
| `status.js` | Protocol values | `run-status`, endpoint, trigger modes, run IDs, de-duplication keys | control logic | `machine_value` | none | P2.4 (preserve) |

Status suppression, de-duplication, and control logic must continue to use raw
machine status values. Translation occurs only after those decisions are
complete. Unknown backend status or error text remains visible in its original
form.

### `static/live_data.js`

| Source | Surface/function | Current literal or pattern | Content type | Future treatment | Proposed key or namespace | Planned Part |
| --- | --- | --- | --- | --- | --- | --- |
| `live_data.js` | Recent count | `{count}/{capacity} recent samples`; `No samples captured` | count/empty state | `translate` | `live_data.recent_count`, `live_data.no_samples` | P2.4 |
| `live_data.js` | Latest/stat values | formatted value plus unit; `#{sequence}`; `--` | numeric/template | number presentation locale-aware later; unit/sequence `machine_value` | `live_data.sample_number` | P2.4 |
| `live_data.js` | Chart empty/labels | `Waiting for samples`; `Auto deviation`; `Auto absolute`; `Manual span`; `Range step` | state/mode label | `translate` | `live_data.waiting_samples`, `live_data.scale.*` | P2.4 |
| `live_data.js` | Range availability | `Range step disabled because Auto range is on.`; `Range step requires Auto range off and a selected manual Range.` | help/status | `translate` | `live_data.range_step_auto_range`, `live_data.range_step_requirements` | P2.4 |
| `live_data.js` | Auto absolute info | `Auto absolute: Range {min} to {max}` | chart template | `translate_with_canonical_token` | `live_data.scale_info.auto_absolute` | P2.4 |
| `live_data.js` | Range-step info | `Range step: Center {center} / Span {span} / Grid {grid}` | chart template | `translate_with_canonical_token` | `live_data.scale_info.range_step` | P2.4 |
| `live_data.js` | Manual-span info | `Manual span: Center {center} / Span {span}`; `Manual span requires a positive value` | chart template/validation | `translate_with_canonical_token` | `live_data.scale_info.manual_span`, `validation.manual_span_positive` | P2.4 |
| `live_data.js` | Auto-deviation info | `Auto deviation: Center {center} / Grid {grid}` | chart template | `translate_with_canonical_token` | `live_data.scale_info.auto_deviation` | P2.4 |
| `live_data.js` | Table empty/details | `No samples captured`; `Details`; `Toggle details for sample {sequence}` | state/button/ARIA | `translate` | `live_data.no_samples`, `live_data.details`, `accessibility.toggle_sample_details` | P2.4 |
| `live_data.js` | Selected sample | `No sample selected`; `Sample #{sequence}` | state/template | `translate_with_canonical_token` | `live_data.no_sample_selected`, `live_data.selected_sample` | P2.4 |
| `live_data.js` | Selected metadata | JSON with `sequence`, `trigger_metadata`, `measurement_metadata` | raw schema/data | `preserve_raw` | none | P2.4 |
| `live_data.js` | Sample-provided fields | `unit`, `status`, `trigger_source`, timestamp, value | runtime data | `preserve_raw`; known status may receive display mapping only | none/`status.*` | P2.4 |
| `live_data.js` | Units/scale tokens | `A`, `V`, `Ohm`, `uA`, `mA`, `uV`, `mV`, `MOhm`, `kOhm`; scale-mode values; sequence/data attributes | technical/machine | `machine_value` | none | P2.4 |
| `live_data.js` | Number/time format | current `en-US` number formatting and `YYYY-MM-DD HH:MM:SS` slicing | display formatting | `translate_with_canonical_token`; must not alter raw data | `live_data.number_format`, `live_data.time_format` | P2.4/P2.7 |
| `live_data.js` | Internal marker | `window.__KEYSIGHT_LIVE_DATA_SCALE_MODES__` | test/internal marker | `not_user_visible` | none | none |

### `static/api.js`

| Source | Surface/function | Current literal or pattern | Content type | Future treatment | Proposed key or namespace | Planned Part |
| --- | --- | --- | --- | --- | --- | --- |
| `api.js` | HTTP detail string | server `detail` string | raw server diagnostic | `preserve_raw` | none | P2.4 |
| `api.js` | Validation array | `{loc}: {msg}` joined by `; ` | raw validation diagnostic/wrapper | location/message `preserve_raw`; punctuation wrapper may be localized only without loss | `error.validation_item` | P2.4 |
| `api.js` | Structured detail | `JSON.stringify(detail)` | raw diagnostic | `preserve_raw` | none | P2.4 |
| `api.js` | Browser fallback | HTTP `statusText` when no usable `detail`, `message`, or `reason` exists | browser/platform diagnostic | `preserve_raw` | optional `error.http_failure` wrapper | P2.4 |
| `api.js` | Invalid response body | JSON parse exception exposed through caught `error.message` | browser/platform diagnostic | `preserve_raw` | optional `error.response_invalid_json` wrapper | P2.4 |
| `api.js` | Command-envelope diagnostics | non-empty `message`, then non-empty `reason`, are selected after `detail`; `error` remains machine data | machine fields/raw diagnostic | exact known messages may use browser presentation keys; unknown reasons `preserve_raw` | `error.command_*` where exact known | P2.4 |
| `api.js` | Protocol | `Content-Type`, JSON parsing, response status behavior | HTTP contract | `machine_value` | none | P2.1 (preserve) |

### Browser-Facing Python

| Source | Surface/function | Current literal or pattern | Content type | Future treatment | Proposed key or namespace | Planned Part |
| --- | --- | --- | --- | --- | --- | --- |
| `_web_payloads.py` | Common support note | `Live runtime model is selected from detected *IDN?.` | API presentation prose | existing text `preserve_raw`; additive semantic key | `support.runtime_driver.detected_idn` | P2.5 |
| `_web_payloads.py` | 34460A status | `USB/system-VISA full-suite validated.` | API presentation prose | existing text fallback plus semantic key | `support.status.usb_system_visa_validated` | P2.5 |
| `_web_payloads.py` | 34460A open workflows | `immediate`; `software`; `software timer`; `custom buffered`; `Frequency`; `Period` | API presentation list | existing prose fallback plus positional semantic keys | `support.workflow.*` | P2.5 |
| `_web_payloads.py` | 34460A limits | `no 10 A current path`; `no current-terminal selection`; `1000-reading memory limit`; `no base-profile external trigger support` | API presentation list | existing prose fallback plus positional semantic keys | `support.limit.*` | P2.5 |
| `_web_payloads.py` | 34460A pending | `34460A DCV Ratio live validation`; `LAN/TCPIP system-VISA validation`; `LAN/TCPIP pyvisa-py @py validation` | API presentation list | existing prose fallback plus positional semantic keys | `support.pending.*` | P2.5 |
| `_web_payloads.py` | 34461A status | `Full-suite validated ... optional CLI-only LAN/pyvisa-py @py.` | API presentation prose | existing text fallback plus semantic key | `support.status.profile_workflows_validated` | P2.5 |
| `_web_payloads.py` | 34461A open workflow | preceding common items plus `external trigger workflows` | API presentation list | existing prose fallback plus positional semantic keys | `support.workflow.external_trigger` | P2.5 |
| `_web_payloads.py` | Unknown profile | `Live support is not open for this profile.` | API presentation prose | existing text fallback plus semantic key | `support.status.not_open` | P2.5 |
| `_web_payloads.py` | Display identity | `Auto-detect`, model tokens, `display_model`; range labels from Core | display/canonical mix | wrapper `translate`; tokens `machine_value` | `device.auto_detect`, `measurement.range_value` | P2.3/P2.5 |
| `_web_payloads.py` | Support metadata | `status_text`, `runtime_driver_note`, `open_workflows`, `limits`, `pending`; validation/transport/backend/feature fields | API fields | field names and policy values `machine_value`; prose remains fallback | none | P2.5 |
| `_web_payloads.py` | Sample payload | sample status, unit, resource, metadata and all JSON keys | runtime schema/data | keys `machine_value`; data `preserve_raw` | none | P2.4 (preserve) |
| `web_ui.py` | Resource scan | `live` / `stale` status and Core `verify_resource()` detail | API machine status/raw diagnostic | status `machine_value`; detail `preserve_raw` | display wrapper under `resource.*` | P2.4 |
| `web_ui.py` | Run admission | `a run is already active`; `resource is required`; request/model-mode JSON-object errors | API errors | preserve existing raw diagnostic; browser may translate known wrapper | `error.run_active`, `validation.resource_required`, `error.request_json_object`, `error.model_mode_unsupported` | P2.4 |
| `web_ui.py` | Field validation | `hw_trigger_slope ...`; `vm_comp_slope ...`; `auto_zero ...`; `dcv_input_impedance ...` | API/Core-bound validation | `preserve_raw` including field/canonical values | optional `validation.*` browser wrappers | P2.4 |
| `web_ui.py` | Command admission | `no active run`; `run is not ready`; command validation messages; `queue_full`; `rate_limited` | command envelope text/reasons | fields/reasons `machine_value`; message `preserve_raw` | optional `error.command.*` | P2.4 |
| `web_ui.py` | Run statuses | `starting`; `ready`; `software trigger queued`; `stop requested`; `recording stopped`; `idle`; state values | raw status/state | `machine_value` for logic; known display translation later | `status.*` | P2.4 |
| `web_ui.py` | CSV open | `run is still active`; `no completed CSV available`; `CSV file not found` | API errors | `preserve_raw`; browser wrapper may translate | `error.csv_run_active`, `error.csv_unavailable`, `error.csv_not_found` | P2.4 |
| `web_ui.py` | CSV selection | `folder selection unavailable`; `folder selection dialog is unavailable`; raw PowerShell stderr; dialog title `Select CSV output folder` | API/backend dialog | API/raw stderr `preserve_raw`; native dialog text outside browser presentation | `error.csv_folder_selector_unavailable` / `out_of_scope` dialog | P2.4 |
| `web_ui.py` | JSON/HTTP errors | `malformed JSON: {error}`; Pydantic detail arrays; arbitrary `str(exc)` | API diagnostic | `preserve_raw` | optional `error.malformed_json` wrapper | P2.4 |
| `web_ui.py` | IDN mismatch | `Selected model {selected} does not match ... Select {connected} or rescan the device.` | browser-visible API error | `translate_with_canonical_token` when recognized; raw fallback otherwise | `error.model_idn_mismatch` | P2.4 |
| `web_ui.py` | Core events/errors | event messages, `fatal_error`, result reason, exception type/detail | backend/Core diagnostic | `preserve_raw` | none | P2.4 |
| `web_ui.py` | Cleanup aggregation | Core prefixes and semicolon-joined cleanup messages | raw diagnostic/control matching | matching `machine_value`; rendered text `preserve_raw` | optional labels only | P2.4 |
| `web_ui.py` | Framework/internal text | FastAPI title, missing cachebuster error, dependency-install error, CLI parser/log formats | not product browser surface | `not_user_visible` | none | none |
| `launcher.py` | Windows launcher | window title, Port/URL/Start/Quit, status and error messages | separate GUI | `out_of_scope` | none | separately approved work |
| `__init__.py`, `__main__.py` | Package/entry point | module description and execution plumbing | internal | `not_user_visible` | none | none |

### Checked Sources With No Visible Text

| Source | Finding | Treatment |
| --- | --- | --- |
| `static/styles.css` | No CSS-generated `content` or other user-visible literal; comments and style tokens only. | `not_user_visible` |
| `static/dom.js` | DOM selectors and exported references only; no rendered prose. | `not_user_visible` |
| Other files under `src/meters_tool_webui/` | All Python files were checked; launcher text is out of browser scope and package entry files contain no browser presentation. | as listed above |

## Dynamic Status And Error Policy

Raw and display values are separate:

1. Normalize, compare, suppress, and de-duplicate using raw machine values.
2. Translate a known status only when rendering it.
3. Preserve unknown status text.
4. Preserve unknown Core/backend exception details.
5. Translate known browser-authored wrapper messages when a key exists.
6. Keep raw status JSON raw.
7. Never hide an error because lookup, interpolation, or translation failed.
8. Never let translation change run-state or button-enable logic.

Examples of raw values include `idle`, `running`, `completed`,
`waiting trigger`, `waiting software custom trigger`, and
`software trigger queued`. Their localized labels are presentation only. This
contract does not define a localized Core status schema.

## Capabilities And Support-Summary Strategy

Existing English API fields remain for backward compatibility. P2.5 adds
semantic translation-key metadata without accepting a locale parameter just to
translate prose. The server does not return different support-policy behavior
by locale. The frontend uses recognized semantic keys when available and keeps
existing English prose as fallback.

The smallest additive shape is to add siblings inside `support_summary`:

```text
status_key
runtime_driver_note_key
open_workflow_keys
limit_keys
pending_keys
```

These names map cleanly to the existing scalar `status_text` and
`runtime_driver_note` and the existing prose lists `open_workflows`, `limits`,
and `pending`. `support_summary.limit_keys` must not be confused with the
top-level numeric `limits` object. Key-list entries are semantic keys, never
array-index-derived key names; existing prose at the corresponding position is
the fallback. Existing prose controls list length and ordering; missing,
malformed, shorter, longer, or unknown key entries cannot hide prose or add
display entries.

Semantic keys are presentation metadata only. They cannot affect Product-open
support, pending status, exact-scope enforcement, model/profile selection,
measurement availability, trigger availability, or hard limits.

## Accessibility Requirements

Future localization must:

- update `<html lang>`;
- keep visible text beside the globe icon and mark the SVG `aria-hidden`;
- give the language button an accessible destination-language label;
- place a `lang` attribute on the destination language name;
- use normal `<button>` keyboard behavior and preserve visible focus;
- localize placeholders, `title`, `aria-label`, empty states, and validation text;
- never use a flag icon to represent a language;
- never remove diagnostic detail needed by an operator.

## Terminology And Glossary

This glossary is the terminology contract, not the completed `zh-TW`
dictionary. Brand/product names and technical tokens stay intact inside an
otherwise translated explanation.

| English concept | Preferred zh-TW direction |
| --- | --- |
| Meters Tool | Keep untranslated |
| Keysight | Keep untranslated |
| Unofficial Tool | 非官方工具 |
| Device | 裝置 |
| VISA resource | VISA 資源 |
| Measurement | 量測 |
| Reading | 讀值 |
| Sample / captured sample | 取樣 |
| Sample count | 取樣數 |
| Trigger | 觸發 |
| Trigger mode | 觸發模式 |
| Software trigger | 軟體觸發 |
| External trigger | 外部觸發 |
| Timer trigger | 定時觸發 |
| Auto range | 自動量程 |
| Auto zero | 自動歸零 |
| Range | 量程 |
| Pending live validation | 等待實機驗證 |
| Not supported by model | 型號不支援 |
| Open | 已開放 |
| Limits | 限制 |
| Pending | 待驗證 |
| Start | 開始 |
| Stop | 停止 |
| Open CSV | 開啟 CSV |
| Cleanup status | 清理狀態 |
| Fatal error | 嚴重錯誤 |

Keep these tokens untranslated unless they occur in an explanatory phrase:

```text
VISA
SCPI
NPLC
IDN
CSV
JSON
JSONL
SSE
USB
LAN
TCPIP
pyvisa-py
system VISA
34460A
34461A
```

Context matters. `Open` in support policy means product-open (`已開放`), not
opening a file. `Reading` is a measured result, while `Sample count` is the
configured or captured quantity. `Range` means an instrument measurement range,
not a generic interval; validation intervals should use wording appropriate to
minimum/maximum bounds. `Status`, `state`, and support-policy status must not be
collapsed into one term when their meanings differ.

## Part Ownership Map

| Part | Ownership |
| --- | --- |
| P2.1 — i18n runtime and locale contract | Lookup/fallback/interpolation foundation; no prose migration ownership. |
| P2.2 — static HTML text migration | `index.html` visible text, placeholders, titles, ARIA, and initial states. Depends on P2.1. |
| P2.3 — form, measurement and trigger dynamic text | Capability-driven labels, options, custom validity, and panel summaries. Depends on P2.1/P2.2. |
| P2.4 — status, log and error presentation | Browser logs, known status mapping, raw fallback, Live data, API error wrappers, and dynamic ARIA. Depends on P2.1. |
| P2.5 — additive support-summary semantic keys | Completed additive backend presentation metadata, prose-authoritative fallback, and cached frontend re-render boundary. Depends on P2.1 and preserves existing prose. |
| P2.6 — language toggle, detection and persistence | Toolbar button, detection, saved-locale precedence, `<html lang>`, runtime switch wiring, and state-preserving switch. Depends on P2.1-P2.5. |
| P2.7 — complete zh-TW translation, integration tests and final docs | Key completion, terminology QA, cross-Part integration, and operator documentation after the feature exists. |

Rows with two Parts identify a dependency rather than duplicate ownership. In
particular, P2.2 owns initial static text while P2.3/P2.4 own later dynamic
replacement; P2.5 supplies support keys and P2.4 retains raw error fallback.

## Future Test Obligations

Later Parts must test:

- exact English and `zh-TW` key-set parity and a complete English source locale;
- English fallback, missing-key diagnostics, and safe parameter interpolation;
- initial browser detection, saved-locale precedence, and invalid saved-locale fallback;
- manual toggle persistence, `<html lang>`, and language-button accessibility;
- active-run switching without runtime requests or state loss;
- unchanged form values and canonical payload values;
- unchanged raw status suppression, de-duplication, and control logic;
- unknown backend/status/error fallback with diagnostic content retained;
- additive-only semantic support keys and unchanged support-policy decisions;
- no translation of API, CSV, JSON, or JSONL schemas;
- no external network or CDN localization dependency.
