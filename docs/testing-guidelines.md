# Testing Guidelines

This project uses tests to protect public contracts, safety boundaries, and
documented integration behavior. Tests should avoid freezing incidental wording
or implementation details that contributors can reasonably change without
breaking users.

## What To Test

- Public Python APIs, component ownership boundaries, console entry points, JSON
  and JSONL schema fields, HTTP endpoints, request payload names, and stable DOM
  IDs or form `name` attributes used by automation.
- Instrument safety behavior, including cleanup order, stop/release behavior,
  trigger read-path selection, and validation limits that prevent risky runs.
- Documentation structure that affects users or maintainers: live links,
  component ownership, stale renamed paths, private lab information, and
  durable contract headings or schema tokens.

## What Not To Freeze

- README prose, exact sentence wording, status-style sections, release counts,
  generated summary totals, or unordered lists where order is not part of the
  contract.
- WebUI layout details such as CSS colors, grid measurements, panel order,
  button text, helper function names, local JavaScript variable names, or query
  selector implementation details.
- Documentation examples by exact line count. Prefer checking that runnable
  examples use the intended entry point and that fallback examples are clearly
  framed as fallback, alternative, or development usage.

## Documentation Tests

Documentation tests should prefer structural checks over prose checks:

- Verify that linked files exist and old public paths are not referenced.
- Check durable headings, contract revision tokens, schema field names,
  names, import names, and safety/privacy boundaries.
- Do not require full paragraphs or exact natural-language sentences unless the
  sentence itself is a public warning, legal/safety boundary, or contract text.

## Frontend Static Tests

Static WebUI tests should protect the integration contract:

- Stable element IDs, form `name` attributes, `data-mode-scope` and
  `data-measurement-scope` attributes.
- HTTP endpoint URLs, request payload field names, response field names used by
  the UI, and the presence of SSE with polling fallback.
- Numeric limits that mirror CLI/Core validation.

Avoid asserting CSS values, exact HTML ordering, visible copy, JavaScript helper
function names, or local variable names unless a detail is intentionally exposed
to users or automation.

## Review Standard

When adding a strict assertion, make the reason clear in the test name or nearby
code. Strict tests are appropriate when the checked detail is a public contract,
an instrument safety boundary, a privacy boundary, or a component ownership rule.
