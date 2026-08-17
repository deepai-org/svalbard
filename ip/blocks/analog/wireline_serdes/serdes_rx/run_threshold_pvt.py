#!/usr/bin/env python3
"""Verify receiver threshold-control range at every calibrated AC corner."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

MEASURE = re.compile(r"^(trip_input|out_at_m50|out_at_p50)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)
THRESHOLD_DRIVES = (-0.2, 0.0, 0.2)


def instantiate(template: str, values: dict[str, str]) -> str:
    result = template
    for name, value in values.items():
        result = result.replace(f"@{name}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", result)))
    if remaining:
        raise ValueError(f"unfilled tokens: {remaining}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--calibration", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pex", type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "threshold_tb.spice.in").read_text()
    calibration = json.loads(args.calibration.read_text())
    groups = []
    for entry in calibration["calibrated_groups"]:
        selected = entry.get("selected_case")
        if not selected:
            groups.append({"group": entry["group"], "result": "fail", "reason": "uncalibrated"})
            continue
        mos, resistor, vdd, temp, cm_fraction, high_bw = entry["group"]
        vcm = float(vdd) * float(cm_fraction)
        trips = {}
        complete = True
        for drive in THRESHOLD_DRIVES:
            case_id = (f"{mos}_{resistor}_{float(vdd):.2f}_{int(temp):+d}_cm{float(cm_fraction):.2f}_"
                       f"bw{int(bool(high_bw))}_b{float(selected['bias_v']):.2f}_th{drive:+.1f}")
            case_id = case_id.replace("+", "p").replace("-", "m")
            values = {"MOS_CORNER": str(mos), "RES_CORNER": str(resistor),
                      "DUT_INCLUDE": (f".include {args.pex}" if args.pex else
                                      ".include /src/serdes_rx.spice"),
                      "DUT_SUBCKT": "serdes_rx_pex" if args.pex else "serdes_rx",
                      "TEMP_C": str(int(temp)), "VDD_V": f"{float(vdd):.2f}",
                      "VCM_V": f"{vcm:.6f}", "VTHP_V": f"{vcm + drive / 2:.6f}",
                      "VTHN_V": f"{vcm - drive / 2:.6f}",
                      "VBIAS_V": f"{float(selected['bias_v']):.2f}",
                      "BW_CODE_V": "0" if high_bw else f"{float(vdd):.2f}", "CLOAD_F": "50f"}
            deck = args.work / f"{case_id}.spice"
            log = args.work / f"{case_id}.log"
            deck.write_text(instantiate(template, values))
            with log.open("w") as output:
                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                     stderr=subprocess.STDOUT, timeout=30, check=False)
            observed = {name: float(value) for name, value in MEASURE.findall(log.read_text())}
            if run.returncode != 0 or "trip_input" not in observed:
                complete = False
            else:
                trips[f"{drive:+.1f}"] = observed
        passed = (complete and trips["-0.2"]["trip_input"] >= 0.025
                  and abs(trips["+0.0"]["trip_input"]) <= 0.0015
                  and trips["+0.2"]["trip_input"] <= -0.025)
        groups.append({"group": entry["group"], "bias_v": selected["bias_v"],
                       "observed": trips, "result": "pass" if passed else "fail"})
    passing = sum(group["result"] == "pass" for group in groups)
    result = {"schema_version": 1, "extraction": "full_rc" if args.pex else "schematic",
              "result": "pass" if passing == len(groups) else "fail",
              "group_count": len(groups), "passing_group_count": passing,
              "threshold_drive_v": list(THRESHOLD_DRIVES), "groups": groups}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"serdes_rx threshold PVT: {passing}/{len(groups)} groups pass")
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
