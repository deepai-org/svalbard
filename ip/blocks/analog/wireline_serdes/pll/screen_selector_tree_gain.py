#!/usr/bin/env python3
"""Screen selector restoring-load geometry while retaining extracted routing RC."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path

import run_selector_tree as tree

MOS = re.compile(r"^(X\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+nfet_03v3\s+(.*)$")
WIDTH = re.compile(r"\bw=([0-9.]+)u\b")
CANDIDATES = (
    # name, input-pair scale, restoring-pair scale
    ("base", 1.00, 1.00),
    ("restore_1p5", 1.00, 1.50),
    ("restore_2p0", 1.00, 2.00),
    ("pairs_1p5", 1.50, 1.50),
    ("pairs_2p0", 2.00, 2.00),
    ("pairs_2p5", 2.50, 2.50),
)
CASES = (
    ("typical", "res_typical", 3.30, 27, 0, 1.35, 1.20),
    ("ss", "res_ff", 2.97, 125, 8, 1.50, 1.35),
    ("ss", "res_ss", 2.97, 125, 11, 1.50, 1.35),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    base = args.pex.read_text()
    template = (args.source / "selector_tree_tb.spice.in").read_text()
    variants: dict[str, Path] = {}
    dimensions: dict[str, dict[str, float]] = {}
    for name, input_scale, restore_scale in CANDIDATES:
        counts = {"input_pair": 0, "restoring_pair": 0}
        lines = []
        for line in base.splitlines():
            match = MOS.match(line)
            if match:
                gate, parameters = match.group(3), match.group(6)
                width_match = WIDTH.search(parameters)
                if width_match and abs(float(width_match.group(1)) - 5.0) < 1e-9:
                    input_gate = re.match(
                        r"(?:I\d+[PN]|VDUMMY|X\d+\.(?:CLK|[AB])_[PN])(?:\.t\d+)?$", gate)
                    control_gate = re.match(r"S\d+[AB](?:\.t\d+)?$", gate)
                    device_class = "input_pair" if input_gate else (
                        None if control_gate else "restoring_pair")
                    if device_class:
                        scale = input_scale if device_class == "input_pair" else restore_scale
                        parameters = WIDTH.sub(f"w={5.0 * scale:g}u", parameters)
                        for parameter, suffix in (("ad", "p"), ("as", "p"),
                                                  ("pd", "u"), ("ps", "u")):
                            pattern = re.compile(rf"\b{parameter}=([0-9.]+){suffix}\b")
                            parameters = pattern.sub(
                                lambda item, s=scale, p=parameter, u=suffix:
                                f"{p}={float(item.group(1)) * s:g}{u}", parameters)
                        line = " ".join((*match.groups()[:5], "nfet_03v3", parameters))
                        counts[device_class] += 1
            lines.append(line)
        if counts != {"input_pair": 120, "restoring_pair": 60}:
            raise ValueError(f"{name}: unexpected pair classification {counts}")
        path = args.work / f"{name}.pex.spice"
        path.write_text("\n".join(lines) + "\n")
        variants[name] = path
        dimensions[name] = {"input_pair_width_scale": input_scale,
                            "restoring_pair_width_scale": restore_scale}

    specs = [(candidate, case) for candidate in CANDIDATES for case in CASES]

    def simulate(spec: tuple[tuple[str, float, float], tuple[str, str, float, int, int, float, float]]) -> dict[str, object]:
        candidate, case = spec
        name = candidate[0]
        mos, resistor, supply, temperature, leaf, active, buffer = case
        case_id = f"{name}_{mos}_{resistor}_leaf{leaf}"
        deck = args.work / f"{case_id}.spice"
        log = args.work / f"{case_id}.log"
        wave = args.work / f"{case_id}.dat"
        deck.write_text(tree.instantiate(template, {
            "MOS_CORNER": mos, "RES_CORNER": resistor,
            "TEMP_C": str(temperature), "VDD_V": f"{supply:.2f}",
            "TREE_PEX_PATH": str(variants[name]),
            "INPUT_SOURCES": tree.input_sources(supply, leaf),
            "CONTROL_SOURCES": tree.static_controls(leaf, active, buffer),
            "TREE_INSTANCE": tree.tree_instance(), "WAVE_PATH": str(wave),
        }))
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=240, check=False)
        observed = {name: float(value) for name, value in tree.SCALAR.findall(log.read_text())}
        timing = tree.metrics(*tree.waveform(wave), 10e-9, 20e-9, 2.5e9)
        passed = (run.returncode == 0 and len(observed) == 2
                  and timing["crossing_count"] >= 20
                  and timing["frequency_error_fraction"] <= 0.005
                  and timing["cycle_jitter_pp_s"] <= 20e-12
                  and timing["differential_high_v"] >= 0.20
                  and timing["differential_low_v"] <= -0.20
                  and 0.005 <= observed["current_late"] <= 0.040
                  and observed["current_max"] <= 0.050)
        return {"candidate": name, "dimensions": dimensions[name],
                "environment": [mos, resistor, supply, temperature],
                "selected_leaf": leaf, "observed": observed, "timing": timing,
                "result": "pass" if passed else "fail"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        cases = list(executor.map(simulate, specs))
    candidates = []
    for name, _, _ in CANDIDATES:
        selected = [case for case in cases if case["candidate"] == name]
        candidates.append({"candidate": name, "dimensions": dimensions[name],
                           "passing_case_count": sum(case["result"] == "pass" for case in selected),
                           "result": "pass" if all(case["result"] == "pass" for case in selected) else "fail"})
    passing = [candidate["candidate"] for candidate in candidates
               if candidate["result"] == "pass"]
    result = {
        "schema_version": 1,
        "claim": "selector_tree_active_gain_candidate_screen",
        "model": "full_rc_interconnect_with_perturbed_active_geometry",
        "limitation": "screening only; regenerate layout and repeat DRC/LVS/full-RC PEX",
        "base_pex_sha256": hashlib.sha256(base.encode()).hexdigest(),
        "passing_candidates": passing,
        "selected_candidate": passing[0] if passing else None,
        "candidates": candidates, "cases": cases,
        "result": "pass" if passing else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"selector tree gain screen: passing candidates={passing}")
    if not passing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
