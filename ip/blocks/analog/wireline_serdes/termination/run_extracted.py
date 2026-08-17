#!/usr/bin/env python3
"""Characterize the full-RC extracted programmable termination."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

MEASURE = re.compile(r"^(rdiff_dc|zmag_\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)


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
    parser.add_argument("--pex", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--full-pvt", action="store_true")
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "extracted_tb.spice.in").read_text()
    mos_corners = ("typical", "ff", "ss") if args.full_pvt else ("typical",)
    res_corners = ("res_typical", "res_ff", "res_ss") if args.full_pvt else ("res_typical",)
    supplies = (2.97, 3.30, 3.63) if args.full_pvt else (3.30,)
    temperatures = (-40, 27, 125) if args.full_pvt else (27,)
    common_modes = (0.35, 0.50, 0.65) if args.full_pvt else (0.50,)
    cases = []
    for mos in mos_corners:
        for resistor in res_corners:
            for vdd in supplies:
                for temp in temperatures:
                    for cm_fraction in common_modes:
                        for enabled in range(8):
                            case_id = (f"{mos}_{resistor}_{vdd:.2f}_{temp:+d}_"
                                       f"cm{cm_fraction:.2f}_c{enabled}").replace("+", "p").replace("-", "m")
                            values = {"MOS_CORNER": mos, "RES_CORNER": resistor,
                                      "PEX_FILE": str(args.pex.resolve()),
                                      "VDD_V": f"{vdd:.2f}", "TEMP_C": str(temp),
                                      "VCM_V": f"{vdd * cm_fraction:.6f}", "VTEST_V": "0.1",
                                      **{f"B{index}_V": "0" if index < enabled else f"{vdd:.2f}"
                                         for index in range(7)}}
                            deck = args.work / f"{case_id}.spice"
                            log = args.work / f"{case_id}.log"
                            deck.write_text(instantiate(template, values))
                            with log.open("w") as output:
                                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                                     stderr=subprocess.STDOUT, timeout=60, check=False)
                            observed = {name: float(value) for name, value in MEASURE.findall(log.read_text())}
                            required = {"rdiff_dc", "zmag_100m", "zmag_1p25g", "zmag_2p5g", "zmag_5g"}
                            complete = run.returncode == 0 and required <= observed.keys()
                            cases.append({"id": case_id, "mos_corner": mos, "res_corner": resistor,
                                          "supply_v": vdd, "temperature_c": temp,
                                          "common_mode_fraction": cm_fraction,
                                          "enabled_branches": enabled, "observed": observed,
                                          "result": "pass" if complete else "fail"})
    complete_count = sum(case["result"] == "pass" for case in cases)
    groups: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for case in cases:
        key = (case["mos_corner"], case["res_corner"], case["supply_v"],
               case["temperature_c"], case["common_mode_fraction"])
        groups.setdefault(key, []).append(case)
    calibrated = []
    for key, candidates in groups.items():
        in_range = [case for case in candidates
                    if 1 <= int(case["enabled_branches"]) <= 6
                    and 95.0 <= float(case["observed"].get("zmag_2p5g", 0.0)) <= 105.0]
        selected = min(in_range,
                       key=lambda case: abs(float(case["observed"]["zmag_2p5g"]) - 100.0),
                       default=None)
        calibrated.append({"group": list(key), "selected_case": selected,
                           "result": "pass" if selected else "fail"})
    calibrated_count = sum(group["result"] == "pass" for group in calibrated)
    passed = complete_count == len(cases) and calibrated_count == len(calibrated)
    result = {"schema_version": 1, "extraction": "full_rc",
              "result": "pass" if passed else "fail", "case_count": len(cases),
              "complete_case_count": complete_count, "calibrated_group_count": len(calibrated),
              "passing_calibrated_group_count": calibrated_count,
              "calibrated_groups": calibrated, "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"termination extracted: {complete_count}/{len(cases)} complete; "
          f"{calibrated_count}/{len(calibrated)} calibrated")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
