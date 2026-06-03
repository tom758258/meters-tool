# Keysight 34461A Trigger Logger (Sprint 1)

CLI-first Python implementation for Keysight 34461A trigger-based logging.

## Implemented
- VISA resource listing (`LAN`/`USB`)
- Current DC measurement plugin
- Trigger-mode acquisition
- Software trigger endpoint (`localhost` HTTP)
- Hardware trigger adapter scaffold (SCPI-based)
- Optional VM Comp output slope configuration
- Immediate CSV write per captured sample

## Install
```bash
python -m venv .venv
source .venv/bin/activate
python -m uv pip install -r requirements.txt
python -m uv pip install -r requirements-dev.txt
python -m uv pip install -e .
```

Windows PowerShell activation:
```powershell
.venv\Scripts\Activate.ps1
```

If you do not run tests, you can skip `requirements-dev.txt` and install only:
```powershell
python -m uv pip install -r requirements.txt
python -m uv pip install -e .
```

## Commands
List VISA resources:
```bash
python -m keysight_logger.cli list-resources
```

Start trigger recording:
```bash
python -m keysight_logger.cli start-trigger-record \
  --resource "TCPIP0::192.168.x.x::inst0::INSTR" \
  --csv ./data/run1.csv \
  --enable-hw-trigger
```

Configure the rear-panel VM Comp output pulse slope only when needed:
```bash
python -m keysight_logger.cli start-trigger-record \
  --resource "USB::YOUR_RESOURCE" \
  --csv ./data/run1.csv \
  --vm-comp-slope pos
```

Send software trigger:
```bash
python -m keysight_logger.cli soft-trigger --port 8765 --meta '{"batch":"A1"}'
```

## CSV Fields
- `timestamp_utc`
- `measurement_type`
- `value`
- `unit`
- `trigger_id`
- `trigger_source`
- `resource_id`
- `status`

## Tests
```bash
python -m pytest -q
python -m unittest discover -s tests -p "test_*.py" -v
```
