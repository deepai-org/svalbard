#!/usr/bin/env python3
"""Screen remaining VCO guardband endpoints while preserving extracted routing RC."""
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
CONTROLS = (0.88, 0.98, 1.08, 1.15, 1.18, 1.20, 1.25, 1.30, 1.35, 1.40, 1.50)
CANDIDATES = (
    # name, base, cap length, cap width scale
    ("typ_slow085", "center", 0.85, 1.0),
    ("typ_slow090", "center", 0.90, 1.0),
    ("typ_slow100", "center", 1.00, 1.0),
    ("ssff_slow040", "ss_ff", 0.40, 1.0),
    ("ssff_slow045", "ss_ff", 0.45, 1.0),
    ("ssff_slow050", "ss_ff", 0.50, 1.0),
    ("ssff_fastw090", "ss_ff", 0.37, 0.9),
    ("ssff_fastw080", "ss_ff", 0.37, 0.8),
)
BASES = {
    "center": ("typical", "res_typical", 3.30, 27, "cml_vco_delay_pex"),
    "ss_ff": ("ss", "res_ff", 2.97, 125, "cml_vco_delay_ss_ff_pex"),
}


def instantiate(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", value)
    remaining = re.findall(r"@[A-Z0-9_]+@", template)
    if remaining:
        raise ValueError(f"unfilled tokens: {remaining}")
    return template


def replace_number(text: str, pattern: re.Pattern[str], value: float) -> str:
    return pattern.sub(lambda match: match.group(0).replace(match.group(1), f"{value:g}"), text)


def scale_junctions(parameters: str, scale: float) -> str:
    for parameter, suffix in (("ad", "p"), ("as", "p"), ("pd", "u"), ("ps", "u")):
        pattern = re.compile(rf"\b{parameter}=([0-9.]+){suffix}\b")
        match = pattern.search(parameters)
        if match:
            parameters = replace_number(parameters, pattern, float(match.group(1)) * scale)
    return parameters


def mutate_caps(base: str, cap_length: float, width_scale: float) -> str:
    output = []
    cap_count = 0
    for line in base.splitlines():
        match = MOS_LINE.match(line)
        if match:
            parameters = match.group(6)
            width_match = WIDTH.search(parameters)
            length_match = LENGTH.search(parameters)
            if width_match and length_match and float(length_match.group(1)) > 0.28:
                width = float(width_match.group(1))
                line = replace_number(line, LENGTH, cap_length)
                line = replace_number(line, WIDTH, width * width_scale)
                line = scale_junctions(line, width_scale)
                cap_count += 1
        output.append(line)
    if cap_count != 2:
        raise ValueError(f"expected two MOS caps, found {cap_count}")
    return "\n".join(output) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--center-pex", type=Path, required=True)
    parser.add_argument("--ss-ff-pex", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "extracted_ring_tb.spice.in").read_text()
    base_paths = {"center": args.center_pex, "ss_ff": args.ss_ff_pex}
    variants: dict[str, dict[str, object]] = {}
    for name, base_name, cap_length, width_scale in CANDIDATES:
        base = base_paths[base_name].read_text()
        pex_path = args.work / f"{name}.spice"
        pex_path.write_text(mutate_caps(base, cap_length, width_scale))
        variants[name] = {
            "base": base_name,
            "pex": pex_path,
            "cap_length_um": cap_length,
            "cap_width_scale": width_scale,
            "base_pex_sha256": hashlib.sha256(base.encode()).hexdigest(),
        }

    specs = [(candidate, control) for candidate in CANDIDATES for control in CONTROLS]

    def simulate(spec: tuple[tuple[object, ...], float]) -> dict[str, object]:
        candidate, control = spec
        name, base_name, _, _ = candidate
        mos, resistor, supply, temperature, subckt = BASES[str(base_name)]
        case_id = f"{name}_{control:.2f}"
        deck = args.work / f"{case_id}.cir"
        log = args.work / f"{case_id}.log"
        ring_instances = "\n".join((
            f"X0 N2P N2N N0P N0N VCTRL VDD VSS {subckt}",
            f"X1 N0P N0N N1P N1N VCTRL VDD VSS {subckt}",
            f"X2 N1P N1N N2P N2N VCTRL VDD VSS {subckt}",
            f"XBUF N2P N2N CLK_P CLK_N VCTRL VDD VSS {subckt}",
        ))
        deck.write_text(instantiate(template, {
            "MOS_CORNER": mos,
            "RES_CORNER": resistor,
            "TEMP_C": str(temperature),
            "VDD_V": f"{supply:.2f}",
            "VCTRL_V": f"{control:.2f}",
            "PEX_PATH": str(variants[str(name)]["pex"]),
            "PEX_SUBCKT": subckt,
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
            "candidate": name,
            "base": base_name,
            "environment": [mos, resistor, supply, temperature],
            "control_v": control,
            "frequency_hz": frequency,
            "observed": observed,
            "result": "pass" if electrical else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        cases = list(executor.map(simulate, specs))

    groups = []
    for base_name in BASES:
        candidates = []
        for candidate in CANDIDATES:
            name = str(candidate[0])
            if candidate[1] != base_name:
                continue
            valid = [case for case in cases if case["candidate"] == name and case["result"] == "pass"]
            candidates.append({
                "candidate": name,
                "cap_length_um": variants[name]["cap_length_um"],
                "cap_width_scale": variants[name]["cap_width_scale"],
                "valid_control_count": len(valid),
                "minimum_hz": min((float(case["frequency_hz"]) for case in valid), default=0),
                "maximum_hz": max((float(case["frequency_hz"]) for case in valid), default=0),
            })
        valid_candidates = [candidate for candidate in candidates if candidate["valid_control_count"]]
        minimum = min((float(candidate["minimum_hz"]) for candidate in valid_candidates), default=0)
        maximum = max((float(candidate["maximum_hz"]) for candidate in valid_candidates), default=0)
        low_covered = minimum > 0 and minimum <= 2.45e9
        high_covered = maximum >= 2.55e9
        required = low_covered if base_name == "center" else low_covered and high_covered
        groups.append({
            "base": base_name,
            "environment": list(BASES[base_name][:4]),
            "minimum_hz": minimum,
            "maximum_hz": maximum,
            "low_endpoint_covered": low_covered,
            "high_endpoint_covered": high_covered,
            "result": "pass" if required else "fail",
            "candidates": candidates,
        })

    passed = all(group["result"] == "pass" for group in groups)
    result = {
        "schema_version": 1,
        "model": "full_rc_interconnect_with_perturbed_mos_cap_geometry",
        "limitation": "screening only; regenerated layout parasitics required",
        "case_count": len(cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "result": "pass" if passed else "fail",
        "groups": groups,
        "cases": cases,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("VCO guardband screen: " + ", ".join(
        f"{group['base']}={group['result']}" for group in groups))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
