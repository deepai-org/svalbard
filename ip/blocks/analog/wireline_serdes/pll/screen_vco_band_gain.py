#!/usr/bin/env python3
"""Screen active strength against a complete routed-band full-RC extraction."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path

CONTROLS = (0.88, 0.98, 1.08, 1.18, 1.30, 1.40, 1.50)
ENVIRONMENTS = (
    ("ff", "res_ss", 2.97, 125),
    ("ss", "res_ff", 2.97, 125),
    ("ss", "res_ss", 2.97, 125),
)
# name, driven pair, main tail, regenerative pair, regenerative tail,
# keep deliberate MOS caps, and load-resistance scale
CANDIDATES = (
    ("baseline", 1.0, 1.0, 1.0, 1.0, True, 1.0),
    ("no_cap", 1.0, 1.0, 1.0, 1.0, False, 1.0),
    ("input_0p75_no_cap", 0.75, 1.0, 1.0, 1.0, False, 1.0),
    ("latch_0p75_no_cap", 1.0, 1.0, 0.75, 1.0, False, 1.0),
    ("active_0p75_no_cap", 0.75, 1.0, 0.75, 1.0, False, 1.0),
    ("active_0p5_no_cap", 0.5, 1.0, 0.5, 1.0, False, 1.0),
    ("load_0p75_no_cap", 1.0, 1.0, 1.0, 1.0, False, 0.75),
)
MOS_LINE = re.compile(r"^(X\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+nfet_03v3\s+(.*)$")
LOAD_LINE = re.compile(r"^(X\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+ppolyf_u\s+(.*)$")
WIDTH = re.compile(r"\bw=([0-9.]+)u\b")
LENGTH = re.compile(r"\bl=([0-9.]+)u\b")
LOAD_LENGTH = re.compile(r"\br_length=([0-9.]+)u\b")
MEASURE_NAMES = (
    "startup_time", "period", "period_late", "diff_high", "diff_low",
    "output_cm", "supply_current",
)
MEASURE = re.compile(
    rf"^({'|'.join(MEASURE_NAMES)})\s*=\s*([-+0-9.eE]+)", re.MULTILINE
)


def scaled(text: str, pattern: re.Pattern[str], scale: float) -> str:
    match = pattern.search(text)
    if not match:
        return text
    value = float(match.group(1)) * scale
    return pattern.sub(lambda item: item.group(0).replace(item.group(1), f"{value:g}"), text)


def scale_geometry(parameters: str, scale: float) -> str:
    for parameter, suffix in (("ad", "p"), ("as", "p"), ("pd", "u"), ("ps", "u")):
        pattern = re.compile(rf"\b{parameter}=([0-9.]+){suffix}\b")
        parameters = scaled(parameters, pattern, scale)
    return parameters


def mutate(base: str, candidate: tuple[object, ...]) -> tuple[str, dict[str, int]]:
    (name, input_scale, main_scale, latch_scale, latch_tail_scale,
     keep_caps, load_scale) = candidate
    counts = {"input": 0, "main_tail": 0, "latch": 0,
              "latch_tail": 0, "cap": 0, "load": 0}
    output = []
    for line in base.splitlines():
        load_match = LOAD_LINE.match(line)
        if load_match and LOAD_LENGTH.search(load_match.group(5)):
            parameters = scaled(load_match.group(5), LOAD_LENGTH, float(load_scale))
            line = " ".join((*load_match.groups()[:4], "ppolyf_u", parameters))
            counts["load"] += 1
        match = MOS_LINE.match(line)
        if match:
            gate, parameters = match.group(3), match.group(6)
            width_match, length_match = WIDTH.search(parameters), LENGTH.search(parameters)
            if width_match and length_match and abs(float(length_match.group(1)) - 0.28) < 1e-9:
                width = float(width_match.group(1))
                device_class = None
                scale = 1.0
                if "VCTRL" in gate and abs(width - 15.0) < 1e-9:
                    device_class, scale = "main_tail", float(main_scale)
                elif "VCTRL" in gate and abs(width - 6.0) < 1e-9:
                    device_class, scale = "latch_tail", float(latch_tail_scale)
                elif "VCTRL" not in gate and abs(width - 5.0) < 1e-9:
                    device_class, scale = "input", float(input_scale)
                elif "VCTRL" not in gate and abs(width - 4.0) < 1e-9:
                    device_class, scale = "latch", float(latch_scale)
                if device_class:
                    parameters = scaled(parameters, WIDTH, scale)
                    parameters = scale_geometry(parameters, scale)
                    line = " ".join((*match.groups()[:5], "nfet_03v3", parameters))
                    counts[device_class] += 1
            elif (width_match and length_match
                  and abs(float(width_match.group(1)) - 3.2) < 1e-9
                  and abs(float(length_match.group(1)) - 0.37) < 1e-9):
                counts["cap"] += 1
                if not keep_caps:
                    continue
        output.append(line)
    expected = {"input": 16, "main_tail": 16, "latch": 8,
                "latch_tail": 8, "cap": 8, "load": 8}
    if counts != expected:
        raise ValueError(f"{name}: active classification {counts}, expected {expected}")
    return "\n".join(output) + "\n", counts


def instantiate(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", value)
    remaining = re.findall(r"@[A-Z0-9_]+@", template)
    if remaining:
        raise ValueError(f"unfilled template tokens: {remaining}")
    return template


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    base = args.pex.read_text()
    template = (args.source / "vco_band_bank_tb.spice.in").read_text()
    pex_paths = {}
    for candidate in CANDIDATES:
        name = str(candidate[0])
        modified, _ = mutate(base, candidate)
        path = args.work / f"{name}.pex.spice"
        path.write_text(modified)
        pex_paths[name] = path
    specs = [
        (candidate, environment, control)
        for candidate in CANDIDATES for environment in ENVIRONMENTS for control in CONTROLS
    ]

    def simulate(spec: tuple[tuple[object, ...], tuple[str, str, float, int], float]) -> dict[str, object]:
        candidate, (mos, resistor, supply, temperature), control = spec
        name = str(candidate[0])
        case_id = f"{name}_{mos}_{resistor}_{control:.2f}"
        deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
        deck.write_text(instantiate(template, {
            "MOS_CORNER": mos, "RES_CORNER": resistor,
            "TEMP_C": str(temperature), "VDD_V": f"{supply:.2f}",
            "VCTRL_V": f"{control:.2f}", "BAND_PEX_PATH": str(pex_paths[name]),
            "BAND_PEX_SUBCKT": "cml_vco_band_pex",
        }))
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=90, check=False)
        observed = {key: float(value) for key, value in MEASURE.findall(log.read_text())}
        complete = run.returncode == 0 and len(observed) == len(MEASURE_NAMES)
        frequency = 1 / observed["period"] if complete and observed["period"] > 0 else 0.0
        late = 1 / observed["period_late"] if complete and observed["period_late"] > 0 else 0.0
        drift = abs(frequency - late) / frequency if frequency else 1.0
        passed = (complete and drift <= 0.01 and observed["diff_high"] >= 0.20
                  and observed["diff_low"] <= -0.20
                  and 0.003 <= observed["supply_current"] <= 0.040
                  and 0 <= observed["startup_time"] - 1.30e-9 <= 10e-9)
        return {
            "candidate": name, "environment": [mos, resistor, supply, temperature],
            "control_v": control, "frequency_hz": frequency,
            "period_drift_fraction": drift,
            "differential_high_v": observed.get("diff_high", 0.0),
            "differential_low_v": observed.get("diff_low", 0.0),
            "supply_current_a": observed.get("supply_current", 0.0),
            "result": "pass" if passed else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        cases = list(executor.map(simulate, specs))
    groups = []
    for environment in ENVIRONMENTS:
        candidates = []
        for candidate in CANDIDATES:
            name = str(candidate[0])
            valid = [case for case in cases if case["candidate"] == name
                     and tuple(case["environment"]) == environment and case["result"] == "pass"]
            candidates.append({
                "candidate": name,
                "scales": {
                    "input": candidate[1], "main_tail": candidate[2],
                    "latch": candidate[3], "latch_tail": candidate[4],
                    "deliberate_cap_present": candidate[5],
                    "load_resistance": candidate[6],
                },
                "valid_control_count": len(valid),
                "minimum_hz": min((float(case["frequency_hz"]) for case in valid), default=0.0),
                "maximum_hz": max((float(case["frequency_hz"]) for case in valid), default=0.0),
                "maximum_current_a": max((float(case["supply_current_a"]) for case in valid), default=0.0),
            })
        groups.append({"environment": list(environment), "candidates": candidates})
    result = {
        "schema_version": 1,
        "claim": "parasitic_preserving_complete_band_active_strength_screen",
        "limitation": "candidate screen only; regenerate DRC/LVS/PEX for any selected geometry",
        "base_pex_sha256": hashlib.sha256(args.pex.read_bytes()).hexdigest(),
        "case_count": len(cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "groups": groups,
        "cases": cases,
        "result": "screen_complete",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"VCO-band gain screen: {result['passing_case_count']}/{result['case_count']} valid")


if __name__ == "__main__":
    main()
