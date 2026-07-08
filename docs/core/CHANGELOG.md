# Changelog

## v1.6.0

- Renamed the Core import package from `keysight_logger_core` to
  `meters_tool_core` as part of the breaking Meters Tool rename.
- Bumped the shared `meters-tool` package version and Core fallback version
  to `1.6.0`.
- Refreshed English Core-facing documentation for expected-model auto-detect
  and deterministic simulator resources.
- Preserved Core request models, validation paths, SCPI planning, VISA access,
  trigger behavior, and cleanup behavior.

## v1.5.0

- Added `frequency` and `period` measurement definitions, profile capabilities,
  validation, run-plan fields, simulator support, units, and acquisition
  configuration.
- Added Frequency/Period voltage range, AC filter, gate-time, default-value,
  and Frequency timeout capability metadata.
- Preserved Frequency timeout SCPI while rejecting explicit Period timeout
  requests before VISA I/O and omitting unsupported Period timeout SCPI.
- Shared StartRequest-to-AcquisitionConfig mapping and split start validation
  into focused internal helpers without changing the public request model or
  validation behavior.
- Simplified measurement SCPI helpers and extracted software-trigger HTTP
  transport handling while preserving command ordering, endpoints, response
  envelopes, queue semantics, and cleanup behavior.
- Centralized the distribution fallback version used by Core, CLI, and WebUI.

## v1.4.0

- Core now ships inside the single root `keysight-logger` distribution while
  preserving the `keysight_logger_core` import package.

## v1.2.1

- Unified `/command` accepted, rejected, and validation responses under the
  common JSON envelope with safe `command` and `job_id` echoing.
- Bumped `keysight-logger-core` package metadata from `1.2.0` to `1.2.1`
  for the patch release baseline without changing public APIs or runtime
  behavior.

## v1.2.0

- Released the Core package from the unified monorepo layout after merging the
  Core, CLI, and WebUI product branches into `main` while preserving Core's
  public API and package boundary.
- Bumped `keysight-logger-core` package metadata from `1.1.1` to `1.2.0`.

## v1.1.1

- Added public Core capability introspection through `get_core_capabilities()`,
  `CoreCapabilities`, and `MeasurementCapability`.
- Added structured buffer-overflow warning details through `CoreWarning` and
  `generate_buffer_overflow_warning_details()` while preserving the existing
  string warning helper.
- Added adapter-readable dry-run plan descriptions and option summaries without
  changing existing `StartPlan` fields or SCPI planning.
- Strengthened no-hardware validation, simulator, runner, CSV metadata, public
  API, docs ownership, and package metadata coverage.
- Bumped `keysight-logger-core` package metadata from `1.1.0` to `1.1.1`.

## v1.0.0

- Completed the Core/Cli separation on the Core branch by removing adapter
  runtime code, wrapper scripts, adapter-specific tests, and legacy top-level
  re-export shims.
- Renamed package metadata to `keysight-logger-core` and removed console
  script metadata while preserving the `keysight_logger_core` public import
  boundary.
- Removed the adapter measurement-name alias from Core measurement metadata.
