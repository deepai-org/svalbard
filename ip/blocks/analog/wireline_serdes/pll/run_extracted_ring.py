#!/usr/bin/env python3
"""Verify a ring composed from four independently extracted CML delay tiles."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path

MEASURE = re.compile(r"^(period|period_late|diff_high|diff_low|output_cm|supply_current|startup_time)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)
CONTROLS = (0.88, 0.98, 1.08, 1.18, 1.30, 1.40, 1.50)
ENVIRONMENTS = (
    ("typical", "res_typical", 3.30, 27),
    ("ff", "res_ff", 3.63, -40),
    ("ff", "res_ss", 2.97, 125),
    ("ss", "res_ff", 2.97, 125),
    ("ss", "res_ss", 2.97, 125),
)


def instantiate(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", value)
    remaining = re.findall(r"@[A-Z0-9_]+@", template)
    if remaining:
        raise ValueError(f"unfilled tokens: {remaining}")
    return template


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pvt", action="store_true")
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "extracted_ring_tb.spice.in").read_text()
    environments = ENVIRONMENTS if args.pvt else ENVIRONMENTS[:1]
    specs = [(m, r, v, t, c) for m, r, v, t in environments for c in CONTROLS]

    def simulate(spec: tuple[str, str, float, int, float]) -> dict[str, object]:
        mos, resistor, supply, temperature, control = spec
        case_id = f"{mos}_{resistor}_{supply:.2f}_{temperature:+d}_{control:.2f}".replace("+", "p").replace("-", "m")
        deck = args.work / f"{case_id}.spice"
        log = args.work / f"{case_id}.log"
        deck.write_text(instantiate(template, {
            "MOS_CORNER": mos, "RES_CORNER": resistor, "TEMP_C": str(temperature),
            "VDD_V": f"{supply:.2f}", "VCTRL_V": f"{control:.2f}",
            "PEX_PATH": str(args.pex),
            "SEED_HIGH": f"{0.52*supply + 0.002:.6f}",
            "SEED_LOW": f"{0.52*supply - 0.002:.6f}",
        }))
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=90, check=False)
        observed = {name: float(value) for name, value in MEASURE.findall(log.read_text())}
        complete = run.returncode == 0 and len(observed) == 7 and observed.get("period", 0) > 0
        frequency = 1.0 / observed["period"] if complete else 0.0
        late_frequency = 1.0 / observed["period_late"] if complete else 0.0
        stable = complete and abs(frequency-late_frequency)/frequency <= 0.01
        electrical = (stable and observed["diff_high"] >= 0.20 and observed["diff_low"] <= -0.20
                      and 0.003 <= observed["supply_current"] <= 0.040
                      and observed["startup_time"] <= 10e-9)
        return {"id": case_id, "mos_corner": mos, "res_corner": resistor,
                "supply_v": supply, "temperature_c": temperature,
                "control_v": control, "frequency_hz": frequency,
                "observed": observed, "result": "pass" if electrical else "fail"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        cases = list(executor.map(simulate, specs))
    groups = []
    for environment in environments:
        candidates = sorted((case for case in cases
                             if (case["mos_corner"], case["res_corner"], case["supply_v"], case["temperature_c"]) == environment
                             and case["result"] == "pass"), key=lambda case: float(case["control_v"]))
        brackets = []
        for lower, upper in zip(candidates, candidates[1:]):
            lower_hz = float(lower["frequency_hz"])
            upper_hz = float(upper["frequency_hz"])
            if (lower_hz-2.5e9)*(upper_hz-2.5e9) <= 0 and lower_hz != upper_hz:
                brackets.append({"controls_v": [lower["control_v"], upper["control_v"]],
                                 "kvco_polarity": "positive" if upper_hz > lower_hz else "negative"})
        groups.append({"environment": list(environment), "valid_control_count": len(candidates),
                       "minimum_hz": min((float(case["frequency_hz"]) for case in candidates), default=0),
                       "maximum_hz": max((float(case["frequency_hz"]) for case in candidates), default=0),
                       "target_brackets_v": brackets, "result": "pass" if brackets else "fail"})
    passed = all(group["result"] == "pass" for group in groups)
    result = {"schema_version": 1, "extraction": "four_instance_full_rc",
              "pex_sha256": hashlib.sha256(args.pex.read_bytes()).hexdigest(),
              "qualification": "pvt" if args.pvt else "nominal",
              "case_count": len(cases), "passing_case_count": sum(c["result"] == "pass" for c in cases),
              "environment_count": len(groups), "passing_environment_count": sum(g["result"] == "pass" for g in groups),
              "result": "pass" if passed else "fail", "groups": groups, "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(f"extracted ring: {result['passing_case_count']}/{len(cases)} electrical; "
          f"{result['passing_environment_count']}/{len(groups)} target brackets")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
