from __future__ import annotations


def external_trigger_setup_commands(slope: str = "NEG", delay_s: float = 0.0) -> tuple[str, ...]:
    slope_cmd = "POS" if str(slope).upper() == "POS" else "NEG"
    return (
        "TRIG:SOUR EXT",
        f"TRIG:SLOP {slope_cmd}",
        "TRIG:COUNT 1",
        "SAMP:COUNT 1",
        f"TRIG:DEL {max(0.0, float(delay_s))}",
    )
