from __future__ import annotations

import unittest
from pathlib import Path

from keysight_logger_core.models import StartRequest, get_default_instrument_profile
from keysight_logger_core.run_plan import StartPlan, build_start_plan


def make_start_request(**overrides) -> StartRequest:  # noqa: ANN003
    values = {
        "resource": "USB::FAKE",
        "csv": str(Path("data") / "plan.csv"),
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
        "hw_trigger_slope": "neg",
        "hw_trigger_delay_s": 0.0,
        "measurement": "current-dc",
        "nplc": 1.0,
        "auto_zero": True,
        "auto_range": True,
        "measurement_range": None,
        "current_range": None,
        "ac_bandwidth_hz": None,
        "current_terminal": None,
        "dcv_input_impedance": "default",
        "vm_comp_slope": None,
    }
    values.update(overrides)
    return StartRequest(**values)


class CoreRunPlanTests(unittest.TestCase):
    def build_plan(
        self,
        trigger_mode: str,
        request: StartRequest | None = None,
        buffer_warnings: list[str] | None = None,
    ) -> StartPlan:
        return build_start_plan(
            request or make_start_request(),
            trigger_mode,
            get_default_instrument_profile(),
            buffer_warnings=buffer_warnings,
        )

    def test_immediate_simple_mode_uses_read_without_buffered_path(self):
        plan = self.build_plan("immediate", make_start_request(trigger_mode="immediate", max_samples=1))

        self.assertEqual("READ?", plan.read_path)
        self.assertIn("CONF:CURR:DC AUTO", plan.scpi_commands)
        self.assertIn("CURR:DC:RANG:AUTO ON", plan.scpi_commands)
        self.assertNotIn("INIT", plan.scpi_commands)
        self.assertFalse(any(command.startswith("DATA:") for command in plan.scpi_commands))
        self.assertFalse(any(command.startswith("TRIG:SOUR") for command in plan.scpi_commands))

    def test_external_simple_mode_uses_fetch_and_external_trigger_scpi(self):
        plan = self.build_plan(
            "external",
            make_start_request(
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
            make_start_request(
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
            make_start_request(
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
            make_start_request(
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
            make_start_request(
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
            make_start_request(trigger_mode="immediate", max_samples=1, simulate=True),
        )

        self.assertIn("simulate uses deterministic fake instrument values", plan.notes)

    def test_plan_includes_adapter_readable_descriptions_without_replacing_fields(self):
        plan = self.build_plan(
            "software",
            make_start_request(
                trigger_mode="software",
                timer_interval_s=1.5,
                max_samples=2,
                measurement="voltage-dc",
                dcv_input_impedance="auto",
            ),
        )

        self.assertEqual("software timer every 1.5 s", plan.trigger_description)
        self.assertEqual("max_samples=2", plan.sample_limit_description)
        self.assertEqual(
            {
                "auto_range": True,
                "auto_zero": True,
                "nplc": 1.0,
                "dcv_input_impedance": "auto",
            },
            plan.option_summary,
        )

    def test_custom_plan_sample_description_and_option_summary(self):
        plan = self.build_plan(
            "software-custom",
            make_start_request(
                trigger_mode="software-custom",
                trigger_count=3,
                sample_count=4,
                buffer_drain_size=2,
                allow_buffer_overflow_risk=True,
            ),
        )

        self.assertEqual(
            "software-custom buffered capture trigger_count=3 sample_count=4",
            plan.trigger_description,
        )
        self.assertEqual("12 expected buffered readings", plan.sample_limit_description)
        self.assertEqual(2, plan.option_summary["buffer_drain_size"])
        self.assertTrue(plan.option_summary["allow_buffer_overflow_risk"])

    def test_plan_metadata_is_normalized(self):
        csv_path = str(Path("data") / "voltage.csv")
        plan = self.build_plan(
            "software",
            make_start_request(
                measurement="voltage-dc",
                csv=csv_path,
                resource="USB::34461A",
            ),
        )

        self.assertEqual("software", plan.trigger_mode)
        self.assertEqual("voltage_dc", plan.measurement_type)
        self.assertEqual("voltage-dc", plan.measurement_name)
        self.assertEqual("V", plan.measurement_unit)
        self.assertEqual(csv_path, plan.csv_path)
        self.assertEqual("USB::34461A", plan.resource)
        self.assertFalse(plan.simulate)
        self.assertTrue(plan.dry_run)
        self.assertFalse(hasattr(plan, "status_format"))
        self.assertFalse(hasattr(plan, "measurement_cli" + "_name"))
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

    def test_new_measurement_options_are_included_in_dry_run_scpi(self):
        current_plan = self.build_plan(
            "software",
            make_start_request(
                measurement="current-dc",
                auto_zero="once",
                auto_range=False,
                measurement_range=10.0,
                current_terminal=10,
            ),
        )
        current_ac_plan = self.build_plan(
            "software",
            make_start_request(
                measurement="current-ac",
                ac_bandwidth_hz=3.0,
                auto_range=False,
                measurement_range=10.0,
                current_terminal=10,
            ),
        )
        voltage_ac_plan = self.build_plan(
            "software",
            make_start_request(measurement="voltage-ac", ac_bandwidth_hz=200.0),
        )

        self.assertIn("ZERO:AUTO ONCE", current_plan.scpi_commands)
        self.assertIn("CURR:DC:TERM 10", current_plan.scpi_commands)
        self.assertNotIn("CURR:DC:RANG 10.0", current_plan.scpi_commands)
        self.assertIn("CURR:AC:TERM 10", current_ac_plan.scpi_commands)
        self.assertIn("CURR:AC:BAND 3", current_ac_plan.scpi_commands)
        self.assertNotIn("CURR:AC:RANG 10.0", current_ac_plan.scpi_commands)
        self.assertIn("VOLT:AC:BAND 200", voltage_ac_plan.scpi_commands)

    def test_voltage_dc_ratio_plan_includes_secondary_data_path(self):
        plan = self.build_plan(
            "software",
            make_start_request(
                measurement="voltage-dc-ratio",
                dcv_input_impedance="10m",
            ),
        )

        self.assertEqual("READ? / DATA2?", plan.read_path)
        self.assertEqual("voltage_dc_ratio", plan.measurement_type)
        self.assertEqual("voltage-dc-ratio", plan.measurement_name)
        self.assertEqual("ratio", plan.measurement_unit)
        self.assertEqual(
            [
                "CONF:VOLT:DC:RAT AUTO",
                "VOLT:DC:IMP:AUTO OFF",
                "VOLT:DC:NPLC 1.0",
                'VOLT:RAT:SEC "SENS:DATA"',
            ],
            plan.scpi_commands,
        )
        self.assertFalse(any("ZERO" in command for command in plan.scpi_commands))
        self.assertIn(
            "voltage-dc-ratio stores DATA2? signal/reference voltage in measurement_metadata",
            plan.notes,
        )

    def test_voltage_dc_ratio_custom_plan_drains_one_reading_for_metadata(self):
        plan = self.build_plan(
            "immediate-custom",
            make_start_request(
                measurement="voltage-dc-ratio",
                trigger_mode="immediate-custom",
                trigger_count=1,
                sample_count=2,
            ),
        )

        self.assertEqual("DATA:POINts? / DATA:REMove? 1 / DATA2?", plan.read_path)
        self.assertIn("TRIG:SOUR IMM", plan.scpi_commands)
        self.assertIn("INIT", plan.scpi_commands)
        self.assertIn(
            "voltage-dc-ratio buffered drain uses DATA:REMove? 1 plus DATA2? per sample",
            plan.notes,
        )


if __name__ == "__main__":
    unittest.main()
