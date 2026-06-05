from __future__ import annotations

import argparse
import unittest
from pathlib import Path

from keysight_logger.core.models import get_default_instrument_profile
from keysight_logger.core.run_plan import StartCommandPlan, build_start_plan


def make_start_args(**overrides) -> argparse.Namespace:  # noqa: ANN003
    values = {
        "resource": "USB::FAKE",
        "csv": str(Path("data") / "plan.csv"),
        "status_format": "text",
        "dry_run": True,
        "simulate": False,
        "timeout_ms": 5000,
        "trigger_timeout_ms": 10000,
        "sw_trigger_port": 8765,
        "sw_min_interval_ms": 0,
        "sw_queue_max": 0,
        "trigger_mode": None,
        "max_samples": None,
        "trigger_count": None,
        "sample_count": None,
        "timer_interval_s": None,
        "buffer_drain_size": None,
        "allow_buffer_overflow_risk": False,
        "enable_hw_trigger": False,
        "hw_trigger_slope": "neg",
        "hw_trigger_delay_s": 0.0,
        "measurement": "current-dc",
        "nplc": 1.0,
        "auto_zero": True,
        "auto_range": True,
        "measurement_range": None,
        "current_range": None,
        "dcv_input_impedance": "default",
        "vm_comp_slope": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class CoreRunPlanTests(unittest.TestCase):
    def build_plan(
        self,
        trigger_mode: str,
        args: argparse.Namespace | None = None,
        buffer_warnings: list[str] | None = None,
    ) -> StartCommandPlan:
        return build_start_plan(
            args or make_start_args(),
            trigger_mode,
            get_default_instrument_profile(),
            buffer_warnings=buffer_warnings,
        )

    def test_immediate_simple_mode_uses_read_without_buffered_path(self):
        plan = self.build_plan("immediate", make_start_args(trigger_mode="immediate", max_samples=1))

        self.assertEqual("READ?", plan.read_path)
        self.assertIn("CONF:CURR:DC AUTO", plan.scpi_commands)
        self.assertIn("CURR:DC:RANG:AUTO ON", plan.scpi_commands)
        self.assertNotIn("INIT", plan.scpi_commands)
        self.assertFalse(any(command.startswith("DATA:") for command in plan.scpi_commands))
        self.assertFalse(any(command.startswith("TRIG:SOUR") for command in plan.scpi_commands))

    def test_external_simple_mode_uses_fetch_and_external_trigger_scpi(self):
        plan = self.build_plan(
            "external",
            make_start_args(
                trigger_mode="external",
                max_samples=1,
                hw_trigger_slope="pos",
                hw_trigger_delay_s=1.5,
            ),
        )

        self.assertEqual("FETC?", plan.read_path)
        self.assertIn("TRIG:SOUR EXT", plan.scpi_commands)
        self.assertIn("TRIG:SLOP POS", plan.scpi_commands)
        self.assertIn("TRIG:COUNT 1", plan.scpi_commands)
        self.assertIn("SAMP:COUNT 1", plan.scpi_commands)
        self.assertIn("TRIG:DEL 1.5", plan.scpi_commands)
        self.assertIn("hardware trigger uses INIT + status-byte polling before FETC?", plan.notes)

    def test_immediate_custom_plan_uses_buffered_read_path(self):
        plan = self.build_plan(
            "immediate-custom",
            make_start_args(
                trigger_mode="immediate-custom",
                trigger_count=2,
                sample_count=3,
                buffer_drain_size=2,
            ),
        )

        self.assertEqual("DATA:POINts? / DATA:REMove?", plan.read_path)
        self.assertIn("TRIG:SOUR IMM", plan.scpi_commands)
        self.assertIn("TRIG:COUNT 2", plan.scpi_commands)
        self.assertIn("SAMP:COUNT 3", plan.scpi_commands)
        self.assertIn("INIT", plan.scpi_commands)
        self.assertIn("buffered drain uses DATA:POINts? and DATA:REMove?", plan.notes)
        self.assertIn("immediate-custom uses IMM trigger source", plan.notes)

    def test_software_custom_plan_uses_bus_trigger_and_buffered_read_path(self):
        plan = self.build_plan(
            "software-custom",
            make_start_args(
                trigger_mode="software-custom",
                trigger_count=4,
                sample_count=5,
                buffer_drain_size=2,
            ),
        )

        self.assertEqual("DATA:POINts? / DATA:REMove?", plan.read_path)
        self.assertIn("TRIG:SOUR BUS", plan.scpi_commands)
        self.assertIn("TRIG:COUNT 4", plan.scpi_commands)
        self.assertIn("SAMP:COUNT 5", plan.scpi_commands)
        self.assertIn("INIT", plan.scpi_commands)
        self.assertIn("software-custom uses BUS trigger plus *TRG", plan.notes)

    def test_external_custom_plan_includes_external_trigger_details(self):
        plan = self.build_plan(
            "external-custom",
            make_start_args(
                trigger_mode="external-custom",
                trigger_count=6,
                sample_count=7,
                buffer_drain_size=3,
                hw_trigger_slope="pos",
                hw_trigger_delay_s=2.25,
            ),
        )

        self.assertEqual("DATA:POINts? / DATA:REMove?", plan.read_path)
        self.assertIn("TRIG:SOUR EXT", plan.scpi_commands)
        self.assertIn("TRIG:SLOP POS", plan.scpi_commands)
        self.assertIn("TRIG:COUNT 6", plan.scpi_commands)
        self.assertIn("SAMP:COUNT 7", plan.scpi_commands)
        self.assertIn("TRIG:DEL 2.25", plan.scpi_commands)
        self.assertIn("INIT", plan.scpi_commands)

    def test_buffer_warnings_are_preserved_in_notes(self):
        warnings = ["WARNING: requested readings exceed 34461A reading memory."]
        plan = self.build_plan(
            "software-custom",
            make_start_args(
                trigger_mode="software-custom",
                trigger_count=101,
                sample_count=100,
                allow_buffer_overflow_risk=True,
            ),
            buffer_warnings=warnings,
        )

        self.assertEqual(warnings, plan.notes[: len(warnings)])
        self.assertIn("buffered drain uses DATA:POINts? and DATA:REMove?", plan.notes)

    def test_simulate_adds_simulator_note(self):
        plan = self.build_plan(
            "immediate",
            make_start_args(trigger_mode="immediate", max_samples=1, simulate=True),
        )

        self.assertIn("simulate uses deterministic fake instrument values", plan.notes)

    def test_plan_metadata_is_normalized(self):
        csv_path = str(Path("data") / "voltage.csv")
        plan = self.build_plan(
            "software",
            make_start_args(
                measurement="voltage-dc",
                csv=csv_path,
                resource="USB::34461A",
                status_format="jsonl",
            ),
        )

        self.assertEqual("software", plan.trigger_mode)
        self.assertEqual("voltage_dc", plan.measurement_type)
        self.assertEqual("voltage-dc", plan.measurement_cli_name)
        self.assertEqual("V", plan.measurement_unit)
        self.assertEqual(csv_path, plan.csv_path)
        self.assertEqual("USB::34461A", plan.resource)
        self.assertFalse(plan.simulate)
        self.assertTrue(plan.dry_run)
        self.assertEqual("jsonl", plan.status_format)
        self.assertEqual(
            [
                "wait for worker",
                "release_to_local",
                "close",
                "cleanup_release_to_local",
                "stop_http_server",
            ],
            plan.cleanup_steps,
        )


if __name__ == "__main__":
    unittest.main()
