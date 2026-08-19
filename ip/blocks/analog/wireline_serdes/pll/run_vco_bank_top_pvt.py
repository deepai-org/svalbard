#!/usr/bin/env python3
"""Calibrate the exact selected-bank parent PEX across declared VCO PVT."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
import sys
from pathlib import Path

SERDES_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERDES_ROOT))

from analog_evidence import environment_index, sha256_file  # noqa: E402

CODE_PORTS = tuple(
    f"{prefix}_{channel}{bit}{suffix}"
    for prefix in ("F", "G")
    for channel in ("A", "B")
    for bit in range(4, -1, -1)
    for suffix in ("", "B")
)
ENVIRONMENTS = (
    ("typical", "res_typical", 3.30, 27, "fast", ((13, 20), (14, 20), (14, 21), (15, 20), (15, 21))),
    ("ff", "res_ff", 3.63, -40, "gain", ((16, 20), (16, 21), (17, 20), (17, 21), (17, 22), (18, 21), (18, 22))),
    ("ff", "res_ss", 2.97, 125, "fast", (
        (15, 21), (16, 19), (16, 20), (16, 21), (16, 22), (16, 23),
        (17, 22), (17, 23), (17, 24),
    )),
    ("ss", "res_ff", 2.97, 125, "gain", ((24, 22), (24, 23), (25, 22), (25, 23), (26, 23), (26, 24), (27, 24))),
    ("ss", "res_ss", 2.97, 125, "fast", (
        (26, 24), (26, 25), (27, 24), (27, 25),
        (28, 25), (28, 26), (29, 26),
    )),
)
MEASUREMENTS = (
    "startup_time", "period_early", "period_late", "diff_high", "diff_low",
    "output_cm", "supply_current", "reference_power_avg",
)
PREFERRED_BAND_HZ = (1.227e9, 1.273e9)


def instantiate(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", template)))
    if remaining:
        raise ValueError(f"unfilled template tokens: {remaining}")
    return template


def bit_sources(prefix: str, code_a: int, code_b: int, vdd: float) -> list[str]:
    lines = []
    for channel, code in (("A", code_a), ("B", code_b)):
        for bit in range(4, -1, -1):
            value = (code >> bit) & 1
            for suffix, inverted in (("", False), ("B", True)):
                high = value ^ inverted
                node = f"{prefix}_{channel}{bit}{suffix}"
                lines.append(
                    f"V{node} {node} 0 PWL(0 0 500p {vdd if high else 0:.3f})"
                )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template_path = args.source / "vco_bank_top_pvt_tb.spice.in"
    template = template_path.read_text()
    pattern = re.compile(
        rf"^({'|'.join(MEASUREMENTS)})\s*=\s*([-+0-9.eE]+)", re.MULTILINE
    )
    specs = [
        (mos, resistor, supply, temperature, member, main, regen)
        for mos, resistor, supply, temperature, member, codes in ENVIRONMENTS
        for main, regen in codes
    ]

    def run_case(spec: tuple[object, ...]) -> dict[str, object]:
        mos, resistor, supply, temperature, member, main, regen = spec
        case_id = (
            f"{mos}_{resistor}_{float(supply):.2f}_{int(temperature):+d}_"
            f"{member}_m{int(main):02d}_r{int(regen):02d}"
        ).replace("+", "p").replace("-", "m").replace(".", "p")
        deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
        fast_codes = (int(main), int(regen)) if member == "fast" else (0, 0)
        gain_codes = (int(main), int(regen)) if member == "gain" else (0, 0)
        sources = (
            bit_sources("F", *fast_codes, float(supply))
            + bit_sources("G", *gain_codes, float(supply))
        )
        pulse = f"PULSE(0 {float(supply):.2f} 1n 20p 20p 250p 100n)"
        selected = "PWL(0 0 3n 0 3.1n 1.50)"
        deck.write_text(instantiate(template, {
            "MOS_CORNER": str(mos), "RES_CORNER": str(resistor),
            "VDD_V": f"{float(supply):.2f}", "TEMP_C": str(temperature),
            "PEX_PATH": str(args.pex), "DUT_CODE_PORTS": " ".join(CODE_PORTS),
            "BIT_SOURCES": "\n".join(sources),
            "FAST_KICKP_SOURCE": pulse if member == "fast" else "0",
            "FAST_KICKN_SOURCE": "0",
            "GAIN_KICKP_SOURCE": pulse if member == "gain" else "0",
            "GAIN_KICKN_SOURCE": "0",
            "SEL_A_SOURCE": selected if member == "fast" else "0",
            "SEL_B_SOURCE": selected if member == "gain" else "0",
        }))
        with log.open("w") as output:
            run = subprocess.run(
                ["ngspice", "-b", str(deck)], stdout=output,
                stderr=subprocess.STDOUT, timeout=300, check=False,
            )
        observed = {
            name: float(value) for name, value in pattern.findall(log.read_text())
        }
        complete = run.returncode == 0 and len(observed) == len(MEASUREMENTS)
        early, late = observed.get("period_early", 0.0), observed.get("period_late", 0.0)
        frequency = 1.0 / late if late > 0 else 0.0
        drift = abs(late - early) / late if late > 0 and early > 0 else 1.0
        passed = (
            complete and 1.225e9 <= frequency <= 1.275e9 and drift <= 0.01
            and observed["startup_time"] <= 8e-9
            and observed["diff_high"] >= 0.15 and observed["diff_low"] <= -0.15
            and 0.4 <= observed["output_cm"] <= float(supply)
            and observed["supply_current"] <= 0.035
            and observed["reference_power_avg"] <= 0.003
        )
        return {
            "id": case_id,
            "environment": [mos, resistor, supply, temperature],
            "selected_member": member,
            "selected_codes": {"main": main, "regen": regen},
            "complete": complete, "observed": observed,
            "frequency_hz": frequency, "period_drift_fraction": drift,
            "result": "pass" if passed else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        cases = list(executor.map(run_case, specs))
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for case in cases:
        grouped.setdefault(tuple(case["environment"]), []).append(case)
    calibration = []
    for environment, members in grouped.items():
        passing = [case for case in members if case["result"] == "pass"]
        # Once a point satisfies the complete performance band, preserve
        # calibration range before minimizing frequency error.  This avoids
        # needlessly choosing a code adjacent to a rail when a more robust
        # passing setting exists.
        selected = min(
            passing,
            key=lambda case: (
                not (
                    PREFERRED_BAND_HZ[0]
                    <= float(case["frequency_hz"])
                    <= PREFERRED_BAND_HZ[1]
                ),
                -min(
                    int(case["selected_codes"]["main"]),
                    31 - int(case["selected_codes"]["main"]),
                    int(case["selected_codes"]["regen"]),
                    31 - int(case["selected_codes"]["regen"]),
                ),
                abs(float(case["frequency_hz"]) - 1.25e9),
            ),
        ) if passing else None
        calibration.append({
            "environment": list(environment),
            "candidate_count": len(members),
            "passing_candidate_count": len(passing),
            "selected_case_id": selected["id"] if selected else None,
            "selected_member": selected["selected_member"] if selected else None,
            "selected_codes": selected["selected_codes"] if selected else None,
            "selected_frequency_hz": selected["frequency_hz"] if selected else None,
            "result": "pass" if selected else "fail",
        })
    environment_index(calibration)
    passed = len(calibration) == 5 and all(x["result"] == "pass" for x in calibration)
    result = {
        "schema_version": 1,
        "claim": "realizable_code_selected_vco_bank_parent_pex_pvt_calibration",
        "bias_reference_v": 2.0,
        "qualification_band_hz": [1.225e9, 1.275e9],
        "selection_preferred_band_hz": list(PREFERRED_BAND_HZ),
        "initial_condition": "none", "transient_uic": False,
        "case_count": len(cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "passing_environment_count": sum(x["result"] == "pass" for x in calibration),
        "calibration": calibration, "cases": cases,
        "pex_sha256": sha256_file(args.pex),
        "simulation_source_sha256": sha256_file(Path(__file__)),
        "testbench_source_sha256": sha256_file(template_path),
        "shared_evidence_source_sha256": sha256_file(
            SERDES_ROOT / "analog_evidence.py"
        ),
        "result": "pass" if passed else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        f"selected bank PVT calibration: {result['passing_case_count']}/"
        f"{result['case_count']} cases; {result['passing_environment_count']}/5 env"
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
