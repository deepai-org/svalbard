#!/usr/bin/env python3
"""Fail closed on the Wi-Fi real-IF sampled-input thermal/settling budget."""

from __future__ import annotations

import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
K_BOLTZMANN_J_PER_K = 1.380649e-23
MAX_TEMPERATURE_K = 398.15
BITS = 12
DIFFERENTIAL_FULL_SCALE_SPAN_V = 0.5
TRACK_TIME_S = 1.45e-9
PER_LEG_FULL_SCALE_PEAK_V = 0.125
SIGMA_MARGIN = 6.0
EXISTING_HOLD_CAPACITANCE_F = 5e-12
EXISTING_SOURCE_RESISTANCE_OHM = 10.0


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def close(actual: object, expected: float, name: str) -> None:
    require(isinstance(actual, (int, float))
            and math.isclose(float(actual), expected, rel_tol=1e-12, abs_tol=1e-18),
            f"{name} changed: expected {expected:.16g}, got {actual!r}")


def main() -> None:
    data = json.loads((HERE / "sampler_thermal_settling_budget.json").read_text())
    lsb_v = DIFFERENTIAL_FULL_SCALE_SPAN_V / (2 ** BITS)
    allocation_v = lsb_v / 4.0
    per_leg_allocation_v = allocation_v / 2.0
    minimum_hold_capacitance_f = (
        2.0 * K_BOLTZMANN_J_PER_K * MAX_TEMPERATURE_K
        * (SIGMA_MARGIN / allocation_v) ** 2)
    existing_differential_sigma_v = math.sqrt(
        2.0 * K_BOLTZMANN_J_PER_K * MAX_TEMPERATURE_K
        / EXISTING_HOLD_CAPACITANCE_F)
    max_total_acquisition_resistance_ohm = TRACK_TIME_S / (
        minimum_hold_capacitance_f
        * math.log(PER_LEG_FULL_SCALE_PEAK_V / per_leg_allocation_v))
    required_input_sine_current_peak_a = (
        2.0 * math.pi * 100e6 * minimum_hold_capacitance_f
        * PER_LEG_FULL_SCALE_PEAK_V)

    require(data.get("result") == "5pf_boundary_rejected_before_sampler_layout",
            "thermal/settling decision changed")
    calculation = data.get("calculation", {})
    close(calculation.get("lsb_v"), lsb_v, "LSB")
    close(calculation.get("quarter_lsb_allocation_v"), allocation_v,
          "quarter-LSB allocation")
    close(calculation.get("minimum_hold_capacitance_per_leg_f"),
          minimum_hold_capacitance_f, "minimum hold capacitance")
    close(calculation.get("existing_5pf_differential_thermal_sigma_v"),
          existing_differential_sigma_v, "existing thermal sigma")
    close(calculation.get("maximum_total_acquisition_resistance_ohm"),
          max_total_acquisition_resistance_ohm, "maximum acquisition resistance")
    close(calculation.get("required_100mhz_input_sine_current_peak_a"),
          required_input_sine_current_peak_a, "required input current")
    require(data.get("thermal_model") == (
        "independent kT/C noise on two equal hold capacitors; no switch, "
        "buffer, mismatch, jitter, reference, or ADC noise credited"),
        "thermal-model scope changed")
    print("Wi-Fi real-IF sampled-input thermal/settling budget: PASS")


if __name__ == "__main__":
    main()
