#!/usr/bin/env python3
"""Screen 3.3 V NAND2 sizing for self-loaded FO1 delay."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path

WN_VALUES = (0.42, 0.56, 0.70, 0.84, 1.12, 1.40, 1.68, 2.24)
WP_VALUES = (0.42, 0.56, 0.70, 0.84, 1.12, 1.40, 1.68, 2.24)
MEASURE = re.compile(r"^(tplh|tphl|trise|tfall|iavg)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def deck(wn: float, wp: float, driven_pin: str) -> str:
    other_pin = "A2" if driven_pin == "A1" else "A1"
    instance = lambda name, signal, output, supply: (
        f"X{name} {signal if driven_pin == 'A1' else supply} "
        f"{supply if other_pin == 'A2' else signal} {output} "
        f"{supply} {supply} 0 0 DUT"
    )
    return f"""* Generated FO1 NAND2 sizing screen.
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_typical
.temp 25
.subckt DUT A1 A2 ZN VDD VNW VPW VSS
XN_TOP ZN A2 NINT VPW nfet_03v3 w={wn:.3f}u l=0.28u
XN_BOT NINT A1 VSS VPW nfet_03v3 w={wn:.3f}u l=0.28u
XP1 ZN A1 VDD VNW pfet_03v3 w={wp:.3f}u l=0.28u
XP2 ZN A2 VDD VNW pfet_03v3 w={wp:.3f}u l=0.28u
.ends DUT
V0 VDD0 0 3.3
V1 VDD1 0 3.3
V2 VDD2 0 3.3
VIN IN 0 PULSE(0 3.3 1n 20p 20p 1n 2n)
{instance('0', 'IN', 'N0', 'VDD0')}
{instance('1', 'N0', 'N1', 'VDD1')}
{instance('2', 'N1', 'N2', 'VDD2')}
.control
tran 1p 8n
meas tran tplh trig v(N0) val=1.65 fall=2 targ v(N1) val=1.65 rise=2
meas tran tphl trig v(N0) val=1.65 rise=2 targ v(N1) val=1.65 fall=2
meas tran trise trig v(N1) val=0.66 rise=2 targ v(N1) val=2.64 rise=2
meas tran tfall trig v(N1) val=2.64 fall=2 targ v(N1) val=0.66 fall=2
let imid = -i(V1)
meas tran iavg avg imid from=2n to=8n
print tplh tphl trise tfall iavg
.endc
.end
"""


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--wn-values")
    parser.add_argument("--wp-values")
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    wn_values = (tuple(float(value) for value in args.wn_values.split(","))
                 if args.wn_values else WN_VALUES)
    wp_values = (tuple(float(value) for value in args.wp_values.split(","))
                 if args.wp_values else WP_VALUES)
    if not wn_values or not wp_values or min(wn_values) < 0.42 or min(wp_values) < 0.42:
        parser.error("width lists must be non-empty and no smaller than 0.42 um")
    args.work.mkdir(parents=True, exist_ok=True)

    specs = [(wn, wp, pin) for wn in wn_values for wp in wp_values for pin in ("A1", "A2")]

    def run(spec: tuple[float, float, str]) -> dict[str, object]:
        wn, wp, pin = spec
        ident = f"wn{wn:.2f}_wp{wp:.2f}_{pin}".replace(".", "p")
        spice = args.work / f"{ident}.spice"
        log = args.work / f"{ident}.log"
        spice.write_text(deck(wn, wp, pin))
        with log.open("w") as stream:
            result = subprocess.run(["ngspice", "-b", str(spice)], stdout=stream,
                                    stderr=subprocess.STDOUT, check=False, timeout=30)
        values = {name: float(value) for name, value in MEASURE.findall(log.read_text())}
        complete = result.returncode == 0 and len(values) == 5 and all(value > 0 for value in values.values())
        return {"wn_um": wn, "wp_um": wp, "driven_pin": pin,
                **{f"{name}_s" if name != "iavg" else "average_current_a": value
                   for name, value in values.items()},
                "result": "pass" if complete else "fail"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(run, specs))
    grouped = []
    for wn in wn_values:
        for wp in wp_values:
            members = [case for case in cases if case["wn_um"] == wn and case["wp_um"] == wp]
            passed = len(members) == 2 and all(case["result"] == "pass" for case in members)
            grouped.append({
                "wn_um": wn, "wp_um": wp,
                "worst_delay_s": max(max(case.get("tplh_s", 1.0), case.get("tphl_s", 1.0))
                                     for case in members),
                "worst_transition_s": max(max(case.get("trise_s", 1.0), case.get("tfall_s", 1.0))
                                          for case in members),
                "result": "pass" if passed else "fail",
            })
    passing = [item for item in grouped if item["result"] == "pass"]
    selected = min(passing, key=lambda item: (item["worst_delay_s"], item["worst_transition_s"]))
    output = {
        "schema_version": 1,
        "claim": "schematic_3v3_nand2_fo1_size_screen",
        "benchmark": {"supply_v": 3.3, "temperature_c": 25, "input_edge_s": 20e-12,
                      "load": "one identical NAND2 input", "measured_stage": 1},
        "candidate_count": len(grouped), "case_count": len(cases),
        "selected": selected, "candidates": grouped, "cases": cases,
        "source_sha256": sha256(Path(__file__)),
        "result": "pass" if len(passing) == len(grouped) else "fail",
    }
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(f"NAND2 FO1 sizing: {len(passing)}/{len(grouped)} candidates; "
          f"selected Wn={selected['wn_um']:.2f}um Wp={selected['wp_um']:.2f}um "
          f"worst={selected['worst_delay_s']*1e12:.2f}ps")
    if output["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
