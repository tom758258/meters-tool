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

## Continuous Integration Responsibilities

The `Tests` GitHub Actions workflow runs for pull requests and pushes to
`main`. It separates tests by the system boundary they protect:

- **Code quality & WebUI** runs Ruff, tracked-text encoding hygiene, committed
  change-range whitespace checks, JavaScript syntax checks, and every
  `frontend_node` test. Node.js is required; Node-dependent tests must not
  silently skip in this job.
- **Linux Python 3.13** runs the main no-hardware suite. Python 3.10, 3.11,
  and 3.12 run an explicit set of compatibility tests for model profiles,
  exact-scope support, stop/cleanup, CLI/Worker, WebUI, and simulation contracts.
- **Windows Python 3.10, 3.12, and 3.13** run cross-platform Windows-specific
  behavioral contracts and source-level package/layout contracts. Python
  3.10/3.12 additionally run a small PowerShell-to-Python boundary smoke suite.
  All Python matrix jobs build the Python distribution and smoke CLI entry points.
- **Windows PowerShell validation** runs conditionally for Core/CLI Python,
  validation scripts and their tests, and shared dependency/workflow inputs. It owns `windows_powershell`
  tests, wrapper runtime behavior, preflight/live PlanOnly boundaries, and
  contract tests for `release-acceptance.ps1`. These tests **do not execute**
  a full formal release acceptance or contact real instruments.
- **Windows packaging smoke** runs conditionally on package, Core/CLI/WebUI,
  Desktop, or build-input changes. It performs a real PyInstaller/Electron
  Desktop build and packaged CLI/Launcher smoke. When release-layout inputs
  change, it builds the release layout once instead and checks the ZIP, wheel,
  sdist, and packaged entry points. This smoke is **not** formal release
  acceptance and produces no releasable artifacts.

The path filter uses separate `validation`, `packaging`, and `release_layout`
outputs. It controls only the two expensive Windows jobs. Invalid or
inaccessible change-detection data must fail the workflow rather than report
an accepted result without validation. No-hardware tests never open physical
VISA resources; real-instrument validation is opt-in and operator-controlled.

`release-acceptance.ps1` remains a separate, explicitly invoked formal release
candidate gate. It must run on a clean, unchanged committed `HEAD`, test the
entire no-hardware workspace, build its release artifacts from one source
snapshot, validate installs and packaging, and verify SHA-256 digests. Passing
CI packaging smoke does not authorize a GitHub Release or promote any live
support scope. The existing manual `Build Windows` workflow provides build
artifacts and optional draft release handling; its `release` mode invokes
`build_release.ps1`, not formal `release-acceptance.ps1`.
