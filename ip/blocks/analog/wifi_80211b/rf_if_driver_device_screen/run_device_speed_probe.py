#!/usr/bin/env python3
"""Screen GF180 compact-model device speed for the Wi-Fi IF-driver boundary."""

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
DEVICE_WIDTHS_UM = {"nmos": 4.0, "pmos": 8.0}
DEVICE_LENGTH_UM = 0.28
REQUIRED_SETTLING_BANDWIDTH_HZ = 989056138.6153347
MINIMUM_TRANSIT_HEADROOM = 5.0
MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measurements(log: Path) -> dict[str, float]:
    return {name: float(value) for name, value in MEASURE.findall(log.read_text())}


def tail(log: Path) -> list[str]:
    return log.read_text().splitlines()[-12:]


def midpoint_deck(corner: str, vdd: float, temp: int) -> str:
    return f"""* DC trip point of the exact bare balanced output-stage topology.
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice {corner}
.temp {temp}
VDD VDD 0 {vdd:.12g}
VGATE GATE 0 0
MP OUT GATE VDD VDD pfet_03v3 w=8u l=0.28u
MN OUT GATE 0 0 nfet_03v3 w=4u l=0.28u
.control
dc VGATE 0 {vdd:.12g} 1m
meas dc gate_mid when v(OUT)={vdd / 2.0:.12g} cross=1
quit
.endc
.end
"""


def ac_deck(kind: str, corner: str, vdd: float, temp: int, gate_mid: float,
            data: Path) -> str:
    if kind == "nmos":
        device = "MN DRAIN GATE 0 0 nfet_03v3 w=4u l=0.28u"
        supplies = f"VDRAIN DRAIN 0 dc {vdd / 2.0:.12g} ac 0"
    else:
        device = "MP DRAIN GATE SOURCE SOURCE pfet_03v3 w=8u l=0.28u"
        supplies = (f"VSOURCE SOURCE 0 dc {vdd:.12g} ac 0\n"
                    f"VDRAIN DRAIN 0 dc {vdd / 2.0:.12g} ac 0")
    return f"""* Small-signal compact-model current-gain crossing probe.
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice {corner}
.temp {temp}
{supplies}
VGATE GATE 0 dc {gate_mid:.12g} ac 1
{device}
.control
ac dec 100 1e6 100e9
set wr_singlescale
set wr_vecnames
wrdata {data} i(VGATE) i(VDRAIN)
quit
.endc
.end
"""


def current_gain_crossing(data: Path) -> float:
    points: list[tuple[float, float]] = []
    for line in data.read_text().splitlines():
        try:
            row = [float(field) for field in line.split()]
        except ValueError:
            continue
        if len(row) < 5:
            continue
        frequency = row[0]
        input_current = complex(row[1], row[2])
        output_current = complex(row[3], row[4])
        if frequency > 0.0 and abs(input_current) > 0.0:
            points.append((frequency, abs(output_current / input_current)))
    if len(points) < 2:
        return math.nan
    for (f0, gain0), (f1, gain1) in zip(points, points[1:]):
        if gain0 >= 1.0 >= gain1 and f1 > f0 and gain0 > 0.0 and gain1 > 0.0:
            fraction = math.log(gain0) / (math.log(gain0) - math.log(gain1))
            return math.exp(math.log(f0) + fraction * (math.log(f1) - math.log(f0)))
    return math.nan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        parser.error("--jobs must be between 1 and 8")
    args.work.mkdir(parents=True, exist_ok=True)

    def run_case(spec: tuple[tuple[str, str, float, int], str]) -> dict[str, object]:
        (name, corner, vdd, temp), kind = spec
        root = args.work / f"{name}_{kind}"
        root.mkdir(parents=True, exist_ok=True)
        midpoint = root / "midpoint.spice"
        midpoint_log = root / "midpoint.log"
        midpoint.write_text(midpoint_deck(corner, vdd, temp))
        with midpoint_log.open("w") as output:
            dc_run = subprocess.run(["ngspice", "-b", str(midpoint)], stdout=output,
                                    stderr=subprocess.STDOUT, timeout=240, check=False)
        gate_mid = measurements(midpoint_log).get("gate_mid", math.nan)
        ac_returncode = -1
        ac_log_tail: list[str] = []
        transit_hz = math.nan
        if math.isfinite(gate_mid):
            ac = root / "current_gain.spice"
            ac_log = root / "current_gain.log"
            data = root / "current_gain.dat"
            ac.write_text(ac_deck(kind, corner, vdd, temp, gate_mid, data))
            with ac_log.open("w") as output:
                ac_run = subprocess.run(["ngspice", "-b", str(ac)], stdout=output,
                                        stderr=subprocess.STDOUT, timeout=240, check=False)
            ac_returncode = ac_run.returncode
            ac_log_tail = tail(ac_log)
            if ac_returncode == 0 and data.exists():
                transit_hz = current_gain_crossing(data)
        headroom = transit_hz / REQUIRED_SETTLING_BANDWIDTH_HZ
        complete = (dc_run.returncode == 0 and ac_returncode == 0
                    and math.isfinite(gate_mid) and math.isfinite(transit_hz))
        return {
            "case_id": f"{name}_{kind}",
            "environment": [corner, vdd, temp],
            "device": kind,
            "width_um": DEVICE_WIDTHS_UM[kind],
            "length_um": DEVICE_LENGTH_UM,
            "gate_mid_v": gate_mid,
            "dc_returncode": dc_run.returncode,
            "dc_log_tail": tail(midpoint_log),
            "ac_returncode": ac_returncode,
            "ac_log_tail": ac_log_tail,
            "current_gain_unity_crossing_hz": transit_hz,
            "headroom_to_required_single_pole_settling_bandwidth": headroom,
            "complete": complete,
            "result": ("pass" if complete and headroom >= MINIMUM_TRANSIT_HEADROOM
                       else "fail"),
        }

    specs = [(environment, kind) for environment in ENVIRONMENTS
             for kind in ("nmos", "pmos")]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        cases = list(pool.map(run_case, specs))
    complete = all(case["complete"] for case in cases)
    passed = complete and all(case["result"] == "pass" for case in cases)
    output = {
        "schema_version": 1,
        "claim": "wifi_if_driver_raw_device_speed_necessary_screen",
        "result": "pass" if passed else "fail",
        "case_count": len(cases),
        "complete_case_count": sum(case["complete"] for case in cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "required_single_pole_settling_bandwidth_hz": REQUIRED_SETTLING_BANDWIDTH_HZ,
        "minimum_transit_headroom": MINIMUM_TRANSIT_HEADROOM,
        "screen_definition": (
            "the drain-current/gate-current unity crossing of one 4-um NMOS or "
            "8-um PMOS at the bare output stage's own DC trip point must be at least "
            "five times the 989.056-MHz sampled-input one-pole settling requirement"),
        "scope": (
            "necessary compact-model device-speed screen only; no output-bank gate "
            "resistance/distribution, feedback-loop, load, noise, linearity, layout, "
            "or model-validity claim"),
        "not_a_claim": [
            "implemented_if_driver", "closed_loop_stability", "output_settling",
            "physical_layout", "adc_enob", "integrated_wifi_receiver",
        ],
        "runner_sha256": digest(Path(__file__)),
        "cases": cases,
    }
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "result": output["result"],
        "complete_case_count": output["complete_case_count"],
        "passing_case_count": output["passing_case_count"],
        "minimum_transit_hz": min(
            (case["current_gain_unity_crossing_hz"] for case in cases
             if math.isfinite(case["current_gain_unity_crossing_hz"])), default=None),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
