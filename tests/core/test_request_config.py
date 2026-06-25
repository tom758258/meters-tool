from __future__ import annotations

import unittest

from keysight_logger_core._request_config import acquisition_config_from_start_request
from keysight_logger_core.models import StartRequest


class RequestConfigTests(unittest.TestCase):
    def test_acquisition_config_maps_start_request_fields(self):
        request = StartRequest(
            resource="USB::FAKE",
            trigger_timeout_ms=1234,
            max_samples=42,
            trigger_count=5,
            sample_count=6,
            timer_interval_s=1.25,
            buffer_drain_size=7,
            allow_buffer_overflow_risk=True,
            nplc=10.0,
            auto_zero="once",
            auto_range=False,
            current_range=10.0,
            ac_bandwidth_hz=200.0,
            gate_time_s=0.5,
            freq_period_timeout="1s",
            current_terminal=10,
            dcv_input_impedance="10m",
            hw_trigger_delay_s=0.75,
            vm_comp_slope="pos",
        )

        config = acquisition_config_from_start_request(request, "frequency")

        self.assertEqual("frequency", config.measurement_type)
        self.assertEqual(1234, config.trigger_timeout_ms)
        self.assertEqual(42, config.max_samples)
        self.assertEqual(5, config.trigger_count)
        self.assertEqual(6, config.sample_count)
        self.assertEqual(1.25, config.timer_interval_s)
        self.assertEqual(7, config.buffer_drain_size)
        self.assertTrue(config.allow_buffer_overflow_risk)
        self.assertEqual(10.0, config.nplc)
        self.assertEqual("once", config.auto_zero)
        self.assertFalse(config.auto_range)
        self.assertEqual(10.0, config.measurement_range)
        self.assertEqual(10.0, config.current_range)
        self.assertEqual(200.0, config.ac_bandwidth_hz)
        self.assertEqual(0.5, config.gate_time_s)
        self.assertEqual("1s", config.freq_period_timeout)
        self.assertEqual(10, config.current_terminal)
        self.assertEqual("10m", config.dcv_input_impedance)
        self.assertEqual(0.75, config.hw_trigger_delay_s)
        self.assertEqual("pos", config.vm_comp_slope)


if __name__ == "__main__":
    unittest.main()
