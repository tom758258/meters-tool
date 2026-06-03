from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
import time
from pathlib import Path
from urllib import request

from .acquisition import TriggerAcquisitionEngine
from .instrument import InstrumentConfig, VisaInstrument
from .measurement import CurrentMeasurement
from .models import AcquisitionConfig, TriggerSource
from .storage import CsvWriter
from .trigger import SoftwareTriggerAdapter, TriggerRouter


def parse_on_off(value: str) -> bool:
    lower = str(value).strip().lower()
    if lower == "on":
        return True
    if lower == "off":
        return False
    raise argparse.ArgumentTypeError("value must be 'on' or 'off'")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="keysight-logger")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-resources")

    start = sub.add_parser("start-trigger-record")
    start.add_argument("--resource", required=True, help="VISA resource string")
    start.add_argument("--csv", required=True, help="CSV output path")
    start.add_argument("--timeout-ms", type=int, default=5000)
    start.add_argument("--trigger-timeout-ms", type=int, default=10000)
    start.add_argument("--sw-trigger-port", type=int, default=8765)
    start.add_argument("--sw-min-interval-ms", type=int, default=0)
    start.add_argument("--sw-queue-max", type=int, default=0)
    start.add_argument("--enable-hw-trigger", action="store_true")
    start.add_argument(
        "--hw-trigger-slope",
        choices=["pos", "neg"],
        default="neg",
        help="hardware trigger edge polarity (default: neg)",
    )
    start.add_argument("--hw-trigger-delay-s", type=float, default=0.0)
    start.add_argument("--nplc", type=float, default=1.0)
    start.add_argument("--auto-zero", type=parse_on_off, default=True)
    start.add_argument("--auto-range", type=parse_on_off, default=True)
    start.add_argument("--current-range", type=float, default=None)

    trig = sub.add_parser("soft-trigger")
    trig.add_argument("--port", type=int, default=8765)
    trig.add_argument("--meta", default="{}", help='JSON metadata, e.g. {"batch":"A"}')

    return parser


def cmd_list_resources() -> int:
    for resource in VisaInstrument.list_resources():
        print(resource)
    return 0


def cmd_soft_trigger(port: int, meta: str) -> int:
    try:
        payload = json.dumps(json.loads(meta)).encode("utf-8")
    except json.JSONDecodeError:
        print("meta must be valid JSON", file=sys.stderr)
        return 2
    req = request.Request(
        f"http://127.0.0.1:{port}/trigger",
        method="POST",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=3) as response:
        print(f"trigger accepted: {response.status}")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    if args.current_range is not None and args.current_range <= 0:
        print("--current-range must be > 0", file=sys.stderr)
        return 2
    if args.nplc <= 0:
        print("--nplc must be > 0", file=sys.stderr)
        return 2
    if args.hw_trigger_delay_s < 0:
        print("--hw-trigger-delay-s must be >= 0", file=sys.stderr)
        return 2
    if not args.auto_range and args.current_range is None:
        print("--current-range is required when --auto-range off", file=sys.stderr)
        return 2
    if args.sw_min_interval_ms < 0:
        print("--sw-min-interval-ms must be >= 0", file=sys.stderr)
        return 2
    if args.sw_queue_max < 0:
        print("--sw-queue-max must be >= 0", file=sys.stderr)
        return 2

    iconfig = InstrumentConfig(resource_string=args.resource, timeout_ms=args.timeout_ms)
    aconfig = AcquisitionConfig(
        trigger_timeout_ms=args.trigger_timeout_ms,
        nplc=args.nplc,
        auto_zero=args.auto_zero,
        auto_range=args.auto_range,
        current_range=args.current_range,
        hw_trigger_delay_s=args.hw_trigger_delay_s,
    )
    instrument = VisaInstrument(iconfig)
    router = TriggerRouter()
    server = SoftwareTriggerAdapter(
        router,
        port=args.sw_trigger_port,
        min_interval_ms=args.sw_min_interval_ms,
        queue_max=args.sw_queue_max,
    )
    storage = CsvWriter(Path(args.csv))
    measurement = CurrentMeasurement()
    engine = TriggerAcquisitionEngine(
        instrument=instrument,
        measurement=measurement,
        storage=storage,
        config=aconfig,
        router=router,
        status_cb=lambda m: print(f"[status] {m}"),
    )

    stop_state = {"stop": False, "interrupt_count": 0, "force": False}

    def handle_signal(signum, frame):  # noqa: ARG001
        stop_state["interrupt_count"] += 1
        if stop_state["interrupt_count"] == 1:
            stop_state["stop"] = True
            print("interrupt received, stopping gracefully (press Ctrl+C again to force)...")
            engine.stop()
            return
        stop_state["force"] = True
        stop_state["stop"] = True
        print("second interrupt received, forcing shutdown...")
        instrument.close()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    worker: threading.Thread | None = None
    try:
        instrument.connect()
        host, port = server.start()
        print(f"software trigger endpoint: http://{host}:{port}/trigger")
        worker = threading.Thread(
            target=engine.run,
            kwargs={
                "enable_hardware_trigger": args.enable_hw_trigger,
                "hardware_trigger_slope": args.hw_trigger_slope,
            },
            daemon=True,
        )
        worker.start()
        try:
            while worker.is_alive() and not stop_state["stop"]:
                time.sleep(0.2)
        except KeyboardInterrupt:
            handle_signal(None, None)
        finally:
            engine.stop()
            if worker.is_alive():
                worker.join(timeout=2)
            if worker.is_alive() or stop_state["force"]:
                # Force-close VISA session to break blocked queries in worker.
                instrument.close()
                worker.join(timeout=2)
        print(f"captured={engine.stats.captured} errors={engine.stats.errors}")
        return 0
    finally:
        instrument.release_to_local()
        server.stop()
        instrument.close()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "list-resources":
        return cmd_list_resources()
    if args.command == "soft-trigger":
        return cmd_soft_trigger(args.port, args.meta)
    if args.command == "start-trigger-record":
        return cmd_start(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
