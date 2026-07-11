# Migrating to Meters Tool v2

## Status

`v2.0.0` is the next planned public release, but it has not been released. The
unreleased work was previously prepared against a `1.6.0` development baseline;
there is no longer a formal `v1.6.0` release target.

The repository may still report package version `1.6.0`. This is the validated
pre-v2 development baseline, not a released v2 package. The package version will
be changed to `2.0.0` during final release preparation.

## Why this is a major release

Meters Tool v2 changes the distribution name, Python import packages, and
console commands. These are breaking public-interface changes, and no
compatibility shims or aliases are provided for the old names. The release
therefore requires a SemVer major version change.

## Name migration table

| Surface | Before v2 | v2 |
| --- | --- | --- |
| Distribution | `keysight-logger` | `meters-tool` |
| Core import | `keysight_logger_core` | `meters_tool_core` |
| CLI import | `keysight_logger_cli` | `meters_tool_cli` |
| WebUI import | `keysight_logger_webui` | `meters_tool_webui` |
| CLI command | `keysight-logger` | `meters-tool` |
| WebUI command | `keysight-logger-webui` | `meters-tool-webui` |
| WebUI launcher | `keysight-logger-webui-launcher` | `meters-tool-webui-launcher` |

## Upgrade examples

After v2 is released, replace the old distribution in the target environment:

```powershell
python -m pip uninstall keysight-logger
python -m pip install meters-tool
```

Update Python imports to use the new package names:

```python
# Before
import keysight_logger_core

# v2
import meters_tool_core
```

Apply the same rename to CLI and WebUI imports and console commands wherever
they are referenced.

## Preserved contracts

The current rename baseline explicitly preserves the following existing
contracts; this list does not expand their documented support scope:

- Keysight hardware profile identities and stable model IDs, including
  `keysight-34460a` and `keysight-34461a`.
- Existing SCPI and VISA runtime behavior.
- The CSV runtime schema and CLI JSON/JSONL fields.
- Existing WebUI endpoint paths and HTTP contracts.
- The worker `service` value.
- The authority of the profile detected from live `*IDN?` and the semantics of
  an explicitly selected model as an expected-model guard.
- The exact support-policy behavior and existing Product-open or pending
  states. The rename does not promote or broaden any model, connection scope,
  measurement feature, or trigger-mode feature.

## Compatibility limitations

No `keysight_logger_*` import shim is provided, and no old
`keysight-logger*` console command alias is provided. Integrations, scripts,
virtual environments, PyInstaller specifications, service launchers, and other
automation that hard-code old names must be updated.

Recreate or reinstall affected environments for v2 instead of assuming that
old entry points remain available.

## Planned v2 completion work

The following work is planned and is not implemented by this P0 documentation
change:

- A secure validation artifact privacy and private-shareable evidence contract
  will be completed.
- A Traditional Chinese WebUI will be implemented.
- Package metadata will receive the final `2.0.0` version bump.
- Final release validation will be completed against the final release state.

## Non-goals of this P0 documentation change

This P0 documentation change does not modify:

- Core, CLI, or WebUI runtime behavior.
- SCPI, VISA, trigger, acquisition, or cleanup behavior.
- CSV, JSON, JSONL, or HTTP runtime schemas.
- Model support or promotion status.
- Artifact layout.
- WebUI language behavior.
- Package metadata.
