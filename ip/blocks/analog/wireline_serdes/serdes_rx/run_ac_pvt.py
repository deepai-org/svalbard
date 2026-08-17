#!/usr/bin/env python3
"""Search receiver bias and bandwidth modes across schematic PVT."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

MEASURE = re.compile(
    r"^(output_cm|stage1_cm|supply_current|gain_100m|gain_1p25g|gain_2p5g|gain_5g|bandwidth)\s*=\s*([-+0-9.eE]+)",
    re.MULTILINE,
)
MOS_CORNERS = ("typical", "ff", "ss")
RES_CORNERS = ("res_typical", "res_ff", "res_ss")
BIAS_VALUES = (0.85, 0.95, 1.05, 1.15, 1.25, 1.35, 1.45)


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
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pex", type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "ac_tb.spice.in").read_text()
    cases = []
    for mos in MOS_CORNERS:
        for resistor in RES_CORNERS:
            for vdd in (2.97, 3.30, 3.63):
                for temp in (-40, 27, 125):
                    for cm_fraction in (0.45, 0.50, 0.55):
                        for high_bw in (False, True):
                            for bias in BIAS_VALUES:
                                case_id = (f"{mos}_{resistor}_{vdd:.2f}_{temp:+d}_cm{cm_fraction:.2f}_"
                                           f"bw{int(high_bw)}_b{bias:.2f}").replace("+", "p").replace("-", "m")
                                values = {"MOS_CORNER": mos, "RES_CORNER": resistor,
                                          "DUT_INCLUDE": (f".include {args.pex}" if args.pex else
                                                          ".include /src/serdes_rx.spice"),
                                          "DUT_SUBCKT": "serdes_rx_pex" if args.pex else "serdes_rx",
                                          "STAGE1P": ("v(XDUT.a_n6572_3500.t6)" if args.pex else
                                                      "v(XDUT.N1P)"),
                                          "STAGE1N": ("v(XDUT.a_n3600_5641.t6)" if args.pex else
                                                      "v(XDUT.N1N)"),
                                          "TEMP_C": str(temp), "VDD_V": f"{vdd:.2f}",
                                          "VCM_V": f"{vdd * cm_fraction:.6f}",
                                          "VBIAS_V": f"{bias:.2f}",
                                          "BW_CODE_V": "0" if high_bw else f"{vdd:.2f}",
                                          "CLOAD_F": "50f"}
                                deck = args.work / f"{case_id}.spice"
                                log = args.work / f"{case_id}.log"
                                deck.write_text(instantiate(template, values))
                                with log.open("w") as output:
                                    run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                                         stderr=subprocess.STDOUT, timeout=30, check=False)
                                observed = {name: float(value) for name, value in MEASURE.findall(log.read_text())}
                                required = {"output_cm", "stage1_cm", "supply_current", "gain_100m",
                                            "gain_1p25g", "gain_2p5g", "gain_5g", "bandwidth"}
                                complete = run.returncode == 0 and required <= observed.keys()
                                cases.append({"id": case_id, "mos_corner": mos, "res_corner": resistor,
                                              "supply_v": vdd, "temperature_c": temp,
                                              "common_mode_fraction": cm_fraction, "high_bandwidth": high_bw,
                                              "bias_v": bias, "observed": observed,
                                              "result": "pass" if complete else "fail"})
    groups: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for case in cases:
        key = (case["mos_corner"], case["res_corner"], case["supply_v"],
               case["temperature_c"], case["common_mode_fraction"], case["high_bandwidth"])
        groups.setdefault(key, []).append(case)
    calibrated = []
    for key, candidates in groups.items():
        high_bw = bool(key[-1])
        valid = []
        for case in candidates:
            obs = case["observed"]
            if case["result"] != "pass":
                continue
            # These floors qualify a 200 mVpp receiver-core input.  Extreme
            # independent public-model corners can be attenuating, so the
            # transient matrix—not an assumed gain above unity—is decisive.
            gain_limit = 0.55 if high_bw else 0.90
            bandwidth_limit = 2.0e9 if high_bw else 1.5e9
            if (0.95 <= float(case["bias_v"]) <= 1.35
                    and float(obs["gain_1p25g"]) >= gain_limit
                    and float(obs["bandwidth"]) >= bandwidth_limit
                    and 1.20 <= float(obs["output_cm"]) <= float(case["supply_v"]) - 0.10
                    and 1.20 <= float(obs["stage1_cm"]) <= float(case["supply_v"]) - 0.10
                    and 0.001 <= float(obs["supply_current"]) <= 0.010):
                valid.append(case)
        selected = min(valid, key=lambda case: abs(float(case["bias_v"]) - 1.15), default=None)
        calibrated.append({"group": list(key), "selected_case": selected,
                           "result": "pass" if selected else "fail"})
    complete_count = sum(case["result"] == "pass" for case in cases)
    calibrated_count = sum(group["result"] == "pass" for group in calibrated)
    passed = complete_count == len(cases) and calibrated_count == len(calibrated)
    result = {"schema_version": 1, "extraction": "full_rc" if args.pex else "schematic",
              "result": "pass" if passed else "fail",
              "case_count": len(cases), "complete_case_count": complete_count,
              "calibrated_group_count": len(calibrated),
              "passing_calibrated_group_count": calibrated_count,
              "calibrated_groups": calibrated, "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"serdes_rx AC PVT: {complete_count}/{len(cases)} complete; "
          f"{calibrated_count}/{len(calibrated)} calibrated")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
