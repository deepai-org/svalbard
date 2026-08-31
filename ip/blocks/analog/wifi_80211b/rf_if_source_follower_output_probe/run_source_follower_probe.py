#!/usr/bin/env python3
"""Screen a class-AB source-follower output primitive at the Wi-Fi IF boundary."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path


ENVIRONMENTS = (
    ("tt", "typical", 3.30, 27),
    ("ff_cold", "ff", 3.63, -40),
    ("ff_hot", "ff", 2.97, 125),
    ("ss_hot", "ss", 2.97, 125),
    ("ss_cold", "ss", 3.63, -40),
)
EFFECTIVE_NMOS_WIDTHS_UM = (10000.0, 20000.0, 50000.0, 100000.0)
GATE_SEPARATIONS_V = (1.8, 2.0, 2.2, 2.4, 2.6, 2.8)
TARGET_FREQUENCY_HZ = 100e6
MAX_OUTPUT_IMPEDANCE_OHM = 0.37864900487166514
VALUE = re.compile(r"(?:v\(out\)|i\(vdd\))\s*=\s*([-+0-9.eE]+)", re.IGNORECASE)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tail(path: Path) -> list[str]:
    return path.read_text().splitlines()[-14:]


def op_values(log: Path) -> tuple[float, float]:
    values = [float(value) for value in VALUE.findall(log.read_text())]
    return (values[0], values[1]) if len(values) >= 2 else (math.nan, math.nan)


def ac_magnitude(data: Path) -> float:
    rows = []
    for line in data.read_text().splitlines():
        try:
            rows.append([float(field) for field in line.split()])
        except ValueError:
            continue
    if not rows:
        return math.nan
    row = min(rows, key=lambda values: abs(values[0] - TARGET_FREQUENCY_HZ))
    return math.hypot(row[-2], row[-1]) if len(row) >= 3 else math.nan


def deck(source: Path, corner: str, vdd: float, temp: int, width_um: float,
         separation_v: float, ac_data: Path) -> str:
    gate_common_v = vdd / 2.0
    nmos_gate_v = gate_common_v + separation_v / 2.0
    pmos_gate_v = gate_common_v - separation_v / 2.0
    return f"""* Wi-Fi source-follower output primitive DC/AC screen.
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice {corner}
.include {source}
.temp {temp}
VDD VDD 0 {vdd:.12g}
VGN GN 0 {nmos_gate_v:.12g}
VGP GP 0 {pmos_gate_v:.12g}
ITEST OUT 0 dc 0 ac 1
XDUT GN GP OUT VDD 0 wifi_if_complementary_source_follower M={width_um / 4.0:.12g}
.control
op
print v(OUT) i(VDD)
ac lin 3 {TARGET_FREQUENCY_HZ * 0.99:.12g} {TARGET_FREQUENCY_HZ * 1.01:.12g}
set wr_singlescale
set wr_vecnames
wrdata {ac_data} v(OUT)
quit
.endc
.end
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        parser.error("--jobs must be between 1 and 8")
    args.work.mkdir(parents=True, exist_ok=True)
    source = args.source / "wifi_if_source_follower_output.spice"

    def run_case(spec: tuple[tuple[str, str, float, int], float, float]) -> dict[str, object]:
        (name, corner, vdd, temp), width_um, separation_v = spec
        root = args.work / f"{name}_{width_um:g}um_{separation_v:g}v"
        root.mkdir(parents=True, exist_ok=True)
        spice = root / "source_follower.spice"
        log = root / "source_follower.log"
        data = root / "output_ac.dat"
        spice.write_text(deck(source, corner, vdd, temp, width_um, separation_v, data))
        try:
            with log.open("w") as output:
                run = subprocess.run(["ngspice", "-b", str(spice)], stdout=output,
                                     stderr=subprocess.STDOUT, timeout=240, check=False)
            returncode = run.returncode
        except subprocess.TimeoutExpired:
            returncode = -1
        output_v, supply_signed_a = op_values(log)
        output_impedance = ac_magnitude(data) if returncode == 0 and data.exists() else math.nan
        complete = (returncode == 0 and math.isfinite(output_v)
                    and math.isfinite(supply_signed_a) and math.isfinite(output_impedance))
        return {
            "case_id": f"{name}_{width_um:g}um_{separation_v:g}v",
            "environment": [corner, vdd, temp],
            "effective_nmos_width_um": width_um,
            "effective_pmos_width_um": 2.0 * width_um,
            "gate_separation_v": separation_v,
            "nmos_gate_v": vdd / 2.0 + separation_v / 2.0,
            "pmos_gate_v": vdd / 2.0 - separation_v / 2.0,
            "output_dc_v": output_v,
            "output_common_mode_error_from_vdd_half_v": abs(output_v - vdd / 2.0),
            "average_supply_draw_a": -supply_signed_a,
            "output_impedance_ohm": output_impedance,
            "returncode": returncode,
            "log_tail": tail(log),
            "complete": complete,
            "result": ("pass" if complete and output_impedance <= MAX_OUTPUT_IMPEDANCE_OHM
                       else "fail"),
        }

    specs = [(environment, width, separation)
             for environment in ENVIRONMENTS
             for width in EFFECTIVE_NMOS_WIDTHS_UM
             for separation in GATE_SEPARATIONS_V]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        cases = list(pool.map(run_case, specs))
    complete = all(case["complete"] for case in cases)
    qualifying = [case for case in cases if case["result"] == "pass"]
    output = {
        "schema_version": 1,
        "claim": "wifi_if_class_ab_source_follower_output_primitive_screen",
        "result": "pass" if qualifying else "fail",
        "case_count": len(cases),
        "complete_case_count": sum(case["complete"] for case in cases),
        "qualifying_case_count": len(qualifying),
        "target_frequency_hz": TARGET_FREQUENCY_HZ,
        "maximum_output_impedance_ohm": MAX_OUTPUT_IMPEDANCE_OHM,
        "scope": (
            "independently DC-biased, small-signal complementary source-follower "
            "output primitive; its gate biases are testbench sources, not an "
            "implemented class-AB bias or common-mode loop"),
        "not_a_claim": [
            "implemented_if_driver", "class_ab_bias_generation", "common_mode_feedback",
            "gate_drive", "large_signal_current", "output_settling", "physical_layout",
            "adc_enob", "integrated_wifi_receiver",
        ],
        "source_sha256": digest(source), "runner_sha256": digest(Path(__file__)),
        "cases": cases,
    }
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "result": output["result"], "complete_case_count": output["complete_case_count"],
        "qualifying_case_count": len(qualifying),
        "best_output_impedance_ohm": min((case["output_impedance_ohm"] for case in cases
                                          if math.isfinite(case["output_impedance_ohm"])), default=None),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
