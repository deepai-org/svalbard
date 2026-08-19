#!/usr/bin/env python3
"""Screen active-strength VCO variants using a full-RC tile as the base model."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path

MEASURE = re.compile(
    r"^(period|period_late|diff_high|diff_low|output_cm|supply_current|startup_time)\s*=\s*([-+0-9.eE]+)",
    re.MULTILINE,
)
MOS_LINE = re.compile(r"^(X\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+nfet_03v3\s+(.*)$")
WIDTH = re.compile(r"\bw=([0-9.]+)u\b")
LENGTH = re.compile(r"\bl=([0-9.]+)u\b")
LOAD_LENGTH = re.compile(r"\br_length=([0-9.]+)u\b")

CONTROLS = (1.20, 1.25, 1.30, 1.35)
ENVIRONMENTS = (
    ("ss", "res_ff", 2.97, 125),
    ("ss", "res_ss", 2.97, 125),
)
CANDIDATES = (
    # name, load L, cap L, input, main tail, latch, latch tail width scales
    ("low_selected", 4.00, 0.38, 1.00, 1.50, 1.00, 1.50),
    ("low_slow_neighbor", 4.00, 0.40, 1.00, 1.50, 1.00, 1.50),
    ("gain_selected", 6.25, 0.37, 1.00, 1.50, 1.00, 1.25),
    ("gain_fast_neighbor", 6.25, 0.35, 1.00, 1.50, 1.00, 1.25),
)


def instantiate(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", value)
    remaining = re.findall(r"@[A-Z0-9_]+@", template)
    if remaining:
        raise ValueError(f"unfilled tokens: {remaining}")
    return template


def scaled_number(text: str, pattern: re.Pattern[str], value: float) -> str:
    return pattern.sub(lambda match: match.group(0).replace(match.group(1), f"{value:g}"), text)


def scale_geometry(parameters: str, scale: float) -> str:
    for parameter, suffix in (("ad", "p"), ("as", "p"), ("pd", "u"), ("ps", "u")):
        pattern = re.compile(rf"\b{parameter}=([0-9.]+){suffix}\b")
        match = pattern.search(parameters)
        if match:
            parameters = scaled_number(parameters, pattern, float(match.group(1)) * scale)
    return parameters


def mutate_pex(base: str, candidate: tuple[object, ...]) -> tuple[str, dict[str, float]]:
    name, load_l, cap_l, input_scale, main_tail_scale, latch_scale, latch_tail_scale = candidate
    scales = {
        "input": float(input_scale),
        "main_tail": float(main_tail_scale),
        "latch": float(latch_scale),
        "latch_tail": float(latch_tail_scale),
    }
    output = []
    counts = {key: 0 for key in scales}
    load_count = 0
    cap_count = 0
    for line in base.splitlines():
        if " ppolyf_u " in line and "r_length=" in line:
            line = scaled_number(line, LOAD_LENGTH, float(load_l))
            load_count += 1
        match = MOS_LINE.match(line)
        if match:
            gate = match.group(3)
            parameters = match.group(6)
            width_match = WIDTH.search(parameters)
            length_match = LENGTH.search(parameters)
            if width_match and length_match:
                width = float(width_match.group(1))
                length = float(length_match.group(1))
                device_class = None
                if abs(length - 0.28) < 1e-6 and abs(width - 5.0) < 1e-6:
                    device_class = "input"
                elif abs(length - 0.28) < 1e-6 and abs(width - 10.0) < 1e-6:
                    device_class = "main_tail"
                elif abs(length - 0.28) < 1e-6 and abs(width - 4.0) < 1e-6:
                    device_class = "latch_tail" if gate.startswith("VCTRL") else "latch"
                elif abs(width - 4.0) < 1e-6 and length > 0.28:
                    line = scaled_number(line, LENGTH, float(cap_l))
                    cap_count += 1
                if device_class:
                    scale = scales[device_class]
                    line = scaled_number(line, WIDTH, width * scale)
                    line = scale_geometry(line, scale)
                    counts[device_class] += 1
        output.append(line)
    if counts != {"input": 4, "main_tail": 4, "latch": 2, "latch_tail": 2}:
        raise ValueError(f"{name}: unexpected active-device classification {counts}")
    if load_count != 2 or cap_count != 2:
        raise ValueError(f"{name}: expected two loads and two caps, got {load_count}/{cap_count}")
    dimensions = {
        "load_length_um": float(load_l),
        "cap_length_um": float(cap_l),
        **{f"{key}_width_scale": value for key, value in scales.items()},
    }
    return "\n".join(output) + "\n", dimensions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "extracted_ring_tb.spice.in").read_text()
    base = args.pex.read_text()
    variants = {}
    for candidate in CANDIDATES:
        name = str(candidate[0])
        pex, dimensions = mutate_pex(base, candidate)
        pex_path = args.work / f"{name}.spice"
        pex_path.write_text(pex)
        variants[name] = {"pex": pex_path, "dimensions": dimensions}

    specs = [(environment, str(candidate[0]), control)
             for environment in ENVIRONMENTS for candidate in CANDIDATES
             if ((environment[1] == "res_ff" and str(candidate[0]).startswith("gain_"))
                 or (environment[1] == "res_ss" and str(candidate[0]).startswith("low_")))
             for control in CONTROLS]

    def simulate(spec: tuple[tuple[str, str, float, int], str, float]) -> dict[str, object]:
        environment, name, control = spec
        mos, resistor, supply, temperature = environment
        case_id = f"{mos}_{resistor}_{name}_{control:.2f}"
        deck = args.work / f"{case_id}.cir"
        log = args.work / f"{case_id}.log"
        pex_path = variants[name]["pex"]
        ring_instances = "\n".join((
            "X0 N2P N2N N0P N0N VCTRL VDD VSS cml_vco_delay_pex",
            "X1 N0P N0N N1P N1N VCTRL VDD VSS cml_vco_delay_pex",
            "X2 N1P N1N N2P N2N VCTRL VDD VSS cml_vco_delay_pex",
            "XBUF N2P N2N CLK_P CLK_N VCTRL VDD VSS cml_vco_delay_pex",
        ))
        deck.write_text(instantiate(template, {
            "MOS_CORNER": mos,
            "RES_CORNER": resistor,
            "TEMP_C": str(temperature),
            "VDD_V": f"{supply:.2f}",
            "VCTRL_V": f"{control:.2f}",
            "PEX_PATH": str(pex_path),
            "RING_INSTANCES": ring_instances,
            "SEED_HIGH": f"{0.52*supply + 0.002:.6f}",
            "SEED_LOW": f"{0.52*supply - 0.002:.6f}",
        }))
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=90, check=False)
        observed = {key: float(value) for key, value in MEASURE.findall(log.read_text())}
        complete = run.returncode == 0 and len(observed) == 7 and observed.get("period", 0) > 0
        frequency = 1.0 / observed["period"] if complete else 0.0
        late_frequency = 1.0 / observed["period_late"] if complete else 0.0
        stable = complete and abs(frequency - late_frequency) / frequency <= 0.01
        electrical = (stable and observed["diff_high"] >= 0.20 and observed["diff_low"] <= -0.20
                      and 0.003 <= observed["supply_current"] <= 0.040
                      and observed["startup_time"] <= 10e-9)
        return {
            "environment": list(environment),
            "candidate": name,
            "control_v": control,
            "frequency_hz": frequency,
            "observed": observed,
            "result": "pass" if electrical else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        cases = list(executor.map(simulate, specs))

    groups = []
    for environment in ENVIRONMENTS:
        candidates = []
        for candidate in CANDIDATES:
            name = str(candidate[0])
            if ((environment[1] == "res_ff" and not name.startswith("gain_"))
                    or (environment[1] == "res_ss" and not name.startswith("low_"))):
                continue
            valid = sorted((case for case in cases
                            if case["environment"] == list(environment)
                            and case["candidate"] == name and case["result"] == "pass"),
                           key=lambda case: float(case["control_v"]))
            brackets = []
            for lower, upper in zip(valid, valid[1:]):
                lower_hz = float(lower["frequency_hz"])
                upper_hz = float(upper["frequency_hz"])
                if (lower_hz - 2.5e9) * (upper_hz - 2.5e9) <= 0 and lower_hz != upper_hz:
                    brackets.append({
                        "controls_v": [lower["control_v"], upper["control_v"]],
                        "kvco_polarity": "positive" if upper_hz > lower_hz else "negative",
                    })
            minimum = min((float(case["frequency_hz"]) for case in valid), default=0)
            maximum = max((float(case["frequency_hz"]) for case in valid), default=0)
            candidates.append({
                "candidate": name,
                "dimensions": variants[name]["dimensions"],
                "valid_control_count": len(valid),
                "minimum_hz": minimum,
                "maximum_hz": maximum,
                "target_brackets_v": brackets,
                "two_percent_guardband": minimum <= 2.45e9 and maximum >= 2.55e9,
            })
        groups.append({
            "environment": list(environment),
            "covering_candidates": [candidate["candidate"] for candidate in candidates
                                    if candidate["target_brackets_v"]],
            "guardband_candidates": [candidate["candidate"] for candidate in candidates
                                     if candidate["two_percent_guardband"]],
            "candidates": candidates,
        })

    passed = all(group["covering_candidates"] for group in groups)
    result = {
        "schema_version": 1,
        "model": "full_rc_interconnect_with_perturbed_device_geometry",
        "limitation": "screening only; regenerated layout parasitics required",
        "base_pex_sha256": hashlib.sha256(base.encode()).hexdigest(),
        "case_count": len(cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "result": "pass" if passed else "fail",
        "groups": groups,
        "cases": cases,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("active VCO screen: " + ", ".join(
        f"{group['environment'][1]}={len(group['covering_candidates'])} covering"
        for group in groups))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
