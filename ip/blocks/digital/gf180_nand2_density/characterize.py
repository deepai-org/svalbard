#!/usr/bin/env python3
"""Compare exact-PEX NAND2 variants in a symmetric FO1 chain."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path

ENVIRONMENTS = (
    ("typical", "res_typical", 3.30, 25),
    ("ff", "res_ff", 3.63, -40),
    ("ss", "res_ss", 2.97, 125),
)
MEASURE = re.compile(r"^(tplh|tphl|trise|tfall|iavg)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_deck(pex: Path, cell: str, driven_pin: str,
              environment: tuple[object, ...]) -> str:
    mos, resistor, supply, temperature = environment
    def instance(name: str, signal: str, output: str, rail: str) -> str:
        a1, a2 = (signal, rail) if driven_pin == "A1" else (rail, signal)
        return f"X{name} {a1} {a2} {output} {rail} {rail} 0 0 {cell}"
    return f"""* Exact-PEX self-loaded FO1 NAND2 comparison.
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice {mos}
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice {resistor}
.include {pex}
.temp {temperature}
V0 VDD0 0 {supply}
V1 VDD1 0 {supply}
V2 VDD2 0 {supply}
VIN IN 0 PULSE(0 {supply} 1n 20p 20p 1n 2n)
{instance('0', 'IN', 'N0', 'VDD0')}
{instance('1', 'N0', 'N1', 'VDD1')}
{instance('2', 'N1', 'N2', 'VDD2')}
.control
tran 1p 8n
meas tran tplh trig v(N0) val={supply/2:.6g} fall=2 targ v(N1) val={supply/2:.6g} rise=2
meas tran tphl trig v(N0) val={supply/2:.6g} rise=2 targ v(N1) val={supply/2:.6g} fall=2
meas tran trise trig v(N1) val={supply*0.2:.6g} rise=2 targ v(N1) val={supply*0.8:.6g} rise=2
meas tran tfall trig v(N1) val={supply*0.8:.6g} fall=2 targ v(N1) val={supply*0.2:.6g} fall=2
let imid = -i(V1)
meas tran iavg avg imid from=2n to=8n
print tplh tphl trise tfall iavg
.endc
.end
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-pex", type=Path, required=True)
    parser.add_argument("--fast-pex", type=Path, required=True)
    parser.add_argument("--std-pex", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    args.work.mkdir(parents=True, exist_ok=True)
    variants = {
        "minimum_3v3": (args.min_pex, "nand2_min_3v3_pex", 1.96, 2.75),
        "fastest_under_default_area_3v3": (args.fast_pex, "nand2_fast_3v3_pex", 1.96, 5.06),
        "default_7t5v0": (args.std_pex, "nand2_std_5v_pex", 2.80, 3.92),
    }
    specs = [(name, pin, environment) for name in variants
             for environment in ENVIRONMENTS for pin in ("A1", "A2")]

    def simulate(spec: tuple[str, str, tuple[object, ...]]) -> dict[str, object]:
        name, pin, environment = spec
        pex, cell, _, _ = variants[name]
        mos, resistor, supply, temperature = environment
        ident = f"{name}_{mos}_{resistor}_{supply:.2f}_{temperature:+d}_{pin}"
        ident = ident.replace(".", "p").replace("+", "p").replace("-", "m")
        deck = args.work / f"{ident}.spice"
        log = args.work / f"{ident}.log"
        deck.write_text(make_deck(pex, cell, pin, environment))
        with log.open("w") as stream:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=stream,
                                 stderr=subprocess.STDOUT, check=False, timeout=30)
        values = {key: float(value) for key, value in MEASURE.findall(log.read_text())}
        passed = run.returncode == 0 and len(values) == 5 and all(value > 0 for value in values.values())
        return {
            "variant": name, "driven_pin": pin, "environment": list(environment),
            **{f"{key}_s" if key != "iavg" else "average_current_a": value
               for key, value in values.items()},
            "result": "pass" if passed else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(simulate, specs))
    summaries = {}
    for name, (pex, _, width, height) in variants.items():
        members = [case for case in cases if case["variant"] == name]
        nominal = [case for case in members if case["environment"][0] == "typical"]
        summaries[name] = {
            "width_um": width, "height_um": height, "area_um2": width * height,
            "area_relative_to_default": width * height / (2.80 * 3.92),
            "nominal_worst_delay_s": max(max(case.get("tplh_s", 1.0), case.get("tphl_s", 1.0))
                                         for case in nominal),
            "pvt_worst_delay_s": max(max(case.get("tplh_s", 1.0), case.get("tphl_s", 1.0))
                                     for case in members),
            "pvt_worst_transition_s": max(max(case.get("trise_s", 1.0), case.get("tfall_s", 1.0))
                                          for case in members),
            "pex_resistor_count": len(re.findall(r"^R\d+\s", pex.read_text(), re.MULTILINE)),
            "pex_capacitor_count": len(re.findall(r"^C\d+\s", pex.read_text(), re.MULTILINE)),
            "pex_sha256": sha256(pex),
            "result": "pass" if len(members) == 6 and all(case["result"] == "pass" for case in members)
                      else "fail",
        }
    result = {
        "schema_version": 1, "claim": "extracted_nand2_fo1_density_speed_comparison",
        "benchmark": {"supply_and_temperature": [list(item) for item in ENVIRONMENTS],
                      "ideal_seed_edge_s": 20e-12,
                      "topology": "three identical extracted NAND2 stages; middle stage measured",
                      "load": "one identical extracted NAND2 input"},
        "summaries": summaries, "cases": cases,
        "simulation_source_sha256": sha256(Path(__file__)),
        "result": "pass" if all(item["result"] == "pass" for item in summaries.values()) else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    for name, summary in summaries.items():
        print(f"{name}: area={summary['area_um2']:.3f}um2 "
              f"nominal={summary['nominal_worst_delay_s']*1e12:.2f}ps "
              f"PVT={summary['pvt_worst_delay_s']*1e12:.2f}ps")
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
