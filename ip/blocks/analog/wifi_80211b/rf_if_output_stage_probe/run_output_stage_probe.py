#!/usr/bin/env python3
"""Screen a CMOS IF-driver output-stage coupon at the Wi-Fi 100-MHz boundary."""

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
EFFECTIVE_NMOS_WIDTHS_UM = (4.0, 20.0, 100.0, 500.0, 1000.0, 2500.0,
                            5000.0, 10000.0, 20000.0)
TARGET_FREQUENCY_HZ = 100e6
MAX_OUTPUT_IMPEDANCE_OHM = 0.37864900487166514
MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def values(log: Path) -> dict[str, float]:
    return {name: float(value) for name, value in MEASURE.findall(log.read_text())}


def log_tail(log: Path) -> list[str]:
    return log.read_text().splitlines()[-12:]


def dc_deck(source: Path, corner: str, vdd: float, temp: int, width_um: float) -> str:
    return f"""* Wi-Fi IF driver output-stage DC trip-point probe.
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice {corner}
.include {source}
.temp {temp}
VDD VDD 0 {vdd:.12g}
VGATE GATE 0 0
XDUT GATE OUT VDD 0 wifi_if_push_pull_output M={width_um / 4.0:.12g}
.control
dc VGATE 0 {vdd:.12g} 1m
meas dc gate_mid when v(OUT)={vdd / 2.0:.12g} cross=1
quit
.endc
.end
"""


def ac_deck(source: Path, corner: str, vdd: float, temp: int, width_um: float,
            gate_mid: float, data: Path) -> str:
    return f"""* Wi-Fi IF driver output-stage 100-MHz AC impedance probe.
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice {corner}
.include {source}
.temp {temp}
VDD VDD 0 {vdd:.12g}
VGATE GATE 0 dc {gate_mid:.12g} ac 0
ITEST OUT 0 dc 0 ac 1
XDUT GATE OUT VDD 0 wifi_if_push_pull_output M={width_um / 4.0:.12g}
.control
ac lin 3 {TARGET_FREQUENCY_HZ * 0.99:.12g} {TARGET_FREQUENCY_HZ * 1.01:.12g}
set wr_singlescale
set wr_vecnames
wrdata {data} v(OUT)
quit
.endc
.end
"""


def gate_ac_deck(source: Path, corner: str, vdd: float, temp: int,
                 width_um: float, gate_mid: float, data: Path) -> str:
    return f"""* Wi-Fi IF driver output-stage gate-admittance probe.
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice {corner}
.include {source}
.temp {temp}
VDD VDD 0 {vdd:.12g}
VOUT OUT 0 dc {vdd / 2.0:.12g} ac 0
VGATE GATE 0 dc {gate_mid:.12g} ac 1
XDUT GATE OUT VDD 0 wifi_if_push_pull_output M={width_um / 4.0:.12g}
.control
ac lin 3 {TARGET_FREQUENCY_HZ * 0.99:.12g} {TARGET_FREQUENCY_HZ * 1.01:.12g}
set wr_singlescale
set wr_vecnames
wrdata {data} i(VGATE)
quit
.endc
.end
"""


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
    if len(row) >= 3:
        return math.hypot(row[-2], row[-1])
    return abs(row[-1]) if len(row) >= 2 else math.nan


def ac_complex(data: Path) -> complex:
    rows = []
    for line in data.read_text().splitlines():
        try:
            rows.append([float(field) for field in line.split()])
        except ValueError:
            continue
    if not rows:
        return complex(math.nan, math.nan)
    row = min(rows, key=lambda values: abs(values[0] - TARGET_FREQUENCY_HZ))
    if len(row) < 3:
        return complex(math.nan, math.nan)
    return complex(row[-2], row[-1])


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
    source = args.source / "rf_if_output_stage.spice"

    def run_case(spec: tuple[tuple[str, str, float, int], float]) -> dict[str, object]:
        (name, corner, vdd, temp), width_um = spec
        root = args.work / f"{name}_{width_um:g}um"
        root.mkdir(parents=True, exist_ok=True)
        dc = root / "dc.spice"
        dc_log = root / "dc.log"
        dc.write_text(dc_deck(source, corner, vdd, temp, width_um))
        with dc_log.open("w") as output:
            dc_run = subprocess.run(["ngspice", "-b", str(dc)], stdout=output,
                                    stderr=subprocess.STDOUT, timeout=240,
                                    check=False)
        dc_values = values(dc_log)
        gate_mid = dc_values.get("gate_mid", math.nan)
        ac_values: dict[str, float] = {}
        ac_returncode = -1
        ac_tail: list[str] = []
        gate_ac_returncode = -1
        gate_ac_tail: list[str] = []
        gate_input_admittance = complex(math.nan, math.nan)
        if math.isfinite(gate_mid):
            ac = root / "ac.spice"
            ac_log = root / "ac.log"
            ac_data = root / "ac.dat"
            ac.write_text(ac_deck(source, corner, vdd, temp, width_um, gate_mid,
                                  ac_data))
            with ac_log.open("w") as output:
                ac_run = subprocess.run(["ngspice", "-b", str(ac)], stdout=output,
                                        stderr=subprocess.STDOUT, timeout=240,
                                        check=False)
            ac_returncode = ac_run.returncode
            ac_values = values(ac_log)
            ac_tail = log_tail(ac_log)
            gate_ac = root / "gate_ac.spice"
            gate_ac_log = root / "gate_ac.log"
            gate_ac_data = root / "gate_ac.dat"
            gate_ac.write_text(gate_ac_deck(source, corner, vdd, temp, width_um,
                                             gate_mid, gate_ac_data))
            with gate_ac_log.open("w") as output:
                gate_ac_run = subprocess.run(["ngspice", "-b", str(gate_ac)],
                                             stdout=output, stderr=subprocess.STDOUT,
                                             timeout=240, check=False)
            gate_ac_returncode = gate_ac_run.returncode
            gate_ac_tail = log_tail(gate_ac_log)
            if gate_ac_returncode == 0 and gate_ac_data.exists():
                gate_input_admittance = ac_complex(gate_ac_data)
        output_impedance = ac_magnitude(ac_data) if math.isfinite(gate_mid) \
            and ac_returncode == 0 and ac_data.exists() else math.nan
        gate_input_capacitance = (-gate_input_admittance.imag
                                  / (2.0 * math.pi * TARGET_FREQUENCY_HZ))
        complete = (dc_run.returncode == 0 and ac_returncode == 0
                    and gate_ac_returncode == 0 and math.isfinite(gate_mid)
                    and math.isfinite(output_impedance)
                    and math.isfinite(gate_input_capacitance)
                    and gate_input_capacitance > 0.0)
        return {
            "case_id": f"{name}_{width_um:g}um",
            "environment": [corner, vdd, temp],
            "nmos_width_um": width_um,
            "pmos_width_um": 2.0 * width_um,
            "finger_count": width_um / 4.0,
            "dc_returncode": dc_run.returncode,
            "dc_log_tail": log_tail(dc_log),
            "gate_mid_v": gate_mid,
            "output_impedance_ohm": output_impedance,
            "ac_returncode": ac_returncode,
            "ac_log_tail": ac_tail,
            "gate_ac_returncode": gate_ac_returncode,
            "gate_ac_log_tail": gate_ac_tail,
            "gate_input_conductance_s": gate_input_admittance.real,
            "gate_input_capacitance_f": gate_input_capacitance,
            "complete": complete,
            "result": "pass" if complete and output_impedance <= MAX_OUTPUT_IMPEDANCE_OHM else "fail",
        }

    specs = [(environment, width)
             for environment in ENVIRONMENTS for width in EFFECTIVE_NMOS_WIDTHS_UM]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        cases = list(pool.map(run_case, specs))
    qualifying = [case for case in cases if case["result"] == "pass"]
    output = {
        "schema_version": 1,
        "claim": "wifi_real_if_push_pull_output_stage_100mhz_feasibility",
        "result": "pass" if qualifying else "fail",
        "target_frequency_hz": TARGET_FREQUENCY_HZ,
        "maximum_output_impedance_ohm": MAX_OUTPUT_IMPEDANCE_OHM,
        "case_count": len(cases),
        "qualifying_case_count": len(qualifying),
        "effective_nmos_widths_um": list(EFFECTIVE_NMOS_WIDTHS_UM),
        "source_sha256": digest(source),
        "runner_sha256": digest(Path(__file__)),
        "scope": "open-loop, small-signal output-stage coupon at its DC trip point; not a buffered, linear, stable, sampled, or physical-layout claim",
        "not_a_claim": [
            "implemented_if_buffer", "output_swing", "output_linearity",
            "common_mode_control", "loop_stability", "sampled_input_settling",
            "adc_enob", "integrated_wifi_receiver",
        ],
        "cases": cases,
    }
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "result": output["result"], "qualifying_case_count": len(qualifying),
        "best_output_impedance_ohm": min(
            (case["output_impedance_ohm"] for case in cases
             if math.isfinite(case["output_impedance_ohm"])), default=None),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
