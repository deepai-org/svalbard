#!/usr/bin/env python3
"""Sweep the schematic ring VCO tuning curve over a bounded PVT matrix."""
from __future__ import annotations

import concurrent.futures
import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path("/src")
WORK = Path("/work/vco-schematic")
MEASURE = re.compile(r"^(period|period_late|diff_high|diff_low|output_cm|supply_current|startup_time)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)
MOS = ("typical", "ff", "ss")
RES = ("res_typical", "res_ff", "res_ss")
SUPPLY = (2.97, 3.30, 3.63)
TEMPERATURE = (-40, 27, 125)
CONTROLS = (0.88, 0.98, 1.08, 1.18, 1.30, 1.40, 1.50)
BANDS = (
    ("minimum_delay", "4.25u", "4u", "2u"),
    ("minimum_transition", "4.50u", "4u", "2u"),
    ("minimum_gain", "4.75u", "4u", "2u"),
    ("low_delay", "5.25u", "4u", "2u"),
    ("low_transition", "5.25u", "4u", "2.25u"),
    ("low_transition_fine", "5.25u", "4u", "2.33u"),
    ("low_mid", "5.25u", "4u", "2.5u"),
    ("center", "5.25u", "4u", "3u"),
    ("mid_gain", "5.75u", "4u", "3u"),
    ("high_gain_fast", "6.50u", "4u", "2u"),
    ("high_gain_transition", "6.50u", "4u", "2.15u"),
    ("high_gain_transition_fine", "6.50u", "4u", "2.10u"),
    ("high_gain", "6.50u", "4u", "3u"),
    ("high_gain_mid", "6.50u", "4u", "3.5u"),
    ("high_gain_delay", "6.50u", "4u", "4u"),
)
QUALIFIED_ENVIRONMENTS = (
    ("typical", "res_typical", 3.30, 27),
    ("ff", "res_ff", 3.63, -40),
    ("ff", "res_typical", 3.30, 27),
    ("ff", "res_ss", 2.97, 125),
    ("typical", "res_ff", 2.97, 125),
    ("typical", "res_ss", 3.63, -40),
    ("ss", "res_ff", 3.63, -40),
    ("ss", "res_typical", 2.97, 125),
    ("ss", "res_ss", 3.30, 27),
    # Targeted headroom/gain and slow-frequency adversaries found by the
    # preceding 486-case single-band characterization.
    ("ss", "res_ff", 2.97, 125),
    ("ss", "res_ss", 2.97, 125),
    ("ff", "res_ff", 2.97, 125),
)


def instantiate(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", value)
    remaining = re.findall(r"@[A-Z0-9_]+@", template)
    if remaining:
        raise ValueError(f"unfilled tokens: {remaining}")
    return template


def simulate(spec: tuple[str, str, float, int, str, str, str, str, float]) -> dict[str, object]:
    mos, resistor, supply, temperature, band, load_l, cap_w, cap_l, control = spec
    case_id = f"{mos}_{resistor}_{supply:.2f}_{temperature:+d}_{band}_{control:.2f}".replace("+", "p").replace("-", "m")
    deck = WORK / f"{case_id}.spice"
    log = WORK / f"{case_id}.log"
    text = instantiate((ROOT / "transient_tb.spice.in").read_text(), {
        "MOS_CORNER": mos, "RES_CORNER": resistor, "TEMP_C": str(temperature),
        "VDD_V": f"{supply:.2f}", "VCTRL_V": f"{control:.2f}",
        "CLOAD_F": "25f", "SEED_HIGH": f"{0.52*supply + 0.002:.6f}",
        "SEED_LOW": f"{0.52*supply - 0.002:.6f}",
        "LOAD_L": load_l, "CAP_W": cap_w, "CAP_L": cap_l,
    })
    deck.write_text(text)
    with log.open("w") as output:
        run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                             stderr=subprocess.STDOUT, timeout=45, check=False)
    observed = {name: float(value) for name, value in MEASURE.findall(log.read_text())}
    complete = run.returncode == 0 and len(observed) == 7 and observed.get("period", 0) > 0
    frequency = 1.0 / observed["period"] if complete else 0.0
    late_frequency = 1.0 / observed["period_late"] if complete else 0.0
    stable = complete and abs(frequency-late_frequency)/frequency <= 0.01
    electrical = (stable and observed["diff_high"] >= 0.20 and observed["diff_low"] <= -0.20
                  and 0.003 <= observed["supply_current"] <= 0.040
                  and observed["startup_time"] <= 10e-9)
    return {"id": case_id, "mos_corner": mos, "res_corner": resistor,
            "supply_v": supply, "temperature_c": temperature, "control_v": control,
            "band": band, "load_length": load_l, "cap_width": cap_w, "cap_length": cap_l,
            "frequency_hz": frequency, "observed": observed,
            "result": "pass" if electrical else "fail"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--tune", action="store_true")
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    if args.quick:
        environments = (("typical", "res_typical", 3.30, 27),)
        qualification = "nominal_iteration"
    elif args.tune:
        environments = (
            ("typical", "res_typical", 3.30, 27),
            ("ff", "res_ff", 3.63, -40),
            ("ff", "res_typical", 3.30, 27),
            ("ff", "res_ss", 2.97, 125),
            ("ss", "res_ff", 2.97, 125),
            ("ss", "res_ss", 2.97, 125),
        )
        qualification = "band_tuning_bounds"
    elif args.repair:
        environments = (
            ("ff", "res_ss", 2.97, 125),
            ("ss", "res_ff", 2.97, 125),
            ("ss", "res_ss", 2.97, 125),
        )
        qualification = "band_gap_repair"
    elif args.full:
        environments = tuple((m, r, v, t) for m in MOS for r in RES
                             for v in SUPPLY for t in TEMPERATURE)
        qualification = "full_cartesian"
    else:
        environments = QUALIFIED_ENVIRONMENTS
        qualification = "adversarial_band_screen"
    specs = [(m, r, v, t, band, load_l, cap_w, cap_l, c)
             for m, r, v, t in environments
             for band, load_l, cap_w, cap_l in BANDS for c in CONTROLS]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        cases = list(executor.map(simulate, specs))
    environments: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for case in cases:
        key = (case["mos_corner"], case["res_corner"], case["supply_v"], case["temperature_c"])
        environments.setdefault(key, []).append(case)
    groups = []
    for key, members in environments.items():
        members.sort(key=lambda item: float(item["control_v"]))
        bands = []
        for band_name, *_ in BANDS:
            candidates = sorted((item for item in members if item["band"] == band_name
                                 and item["result"] == "pass"), key=lambda item: float(item["control_v"]))
            brackets = []
            for lower, upper in zip(candidates, candidates[1:]):
                lower_hz = float(lower["frequency_hz"])
                upper_hz = float(upper["frequency_hz"])
                if (lower_hz - 2.5e9) * (upper_hz - 2.5e9) <= 0 and lower_hz != upper_hz:
                    brackets.append({"controls_v": [lower["control_v"], upper["control_v"]],
                                     "kvco_polarity": "positive" if upper_hz > lower_hz else "negative"})
            bands.append({"band": band_name, "valid_control_count": len(candidates),
                          "minimum_hz": min((float(item["frequency_hz"]) for item in candidates), default=0),
                          "maximum_hz": max((float(item["frequency_hz"]) for item in candidates), default=0),
                          "target_brackets_v": brackets})
        viable = [band for band in bands if band["target_brackets_v"]]
        groups.append({"environment": list(key), "selected_band": viable[0]["band"] if viable else None,
                       "bands": bands, "result": "pass" if viable else "fail"})
    result = {"schema_version": 1, "extraction": "schematic", "qualification": qualification,
              "case_count": len(cases), "complete_case_count": sum(bool(c["observed"]) for c in cases),
              "passing_case_count": sum(c["result"] == "pass" for c in cases),
              "environment_count": len(groups),
              "passing_environment_count": sum(g["result"] == "pass" for g in groups),
              "result": "pass" if all(g["result"] == "pass" for g in groups) else "fail",
              "groups": groups, "cases": cases}
    Path("/work/vco-schematic-result.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(f"ring VCO: {result['passing_case_count']}/{len(cases)} electrical cases; "
          f"{result['passing_environment_count']}/{len(groups)} environments cover 2.5 GHz")
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
