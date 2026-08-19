#!/usr/bin/env python3
"""Measure exact-parent VDD/reference pushing at selected PVT codes."""
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
CROSSING_COUNT = 12
SCALARS = (
    "startup_time", "diff_high", "diff_low", "output_cm",
    "supply_current", "reference_power_avg",
)
DISTURBANCES = (
    ("baseline", 0.0, 10e6, 0.0, 0.0, 10e6, 0.0),
    ("vdd50m_10m_p0", 0.050, 10e6, 0.0, 0.0, 10e6, 0.0),
    ("vdd50m_10m_p90", 0.050, 10e6, 90.0, 0.0, 10e6, 0.0),
    ("vdd50m_100m_p0", 0.050, 100e6, 0.0, 0.0, 10e6, 0.0),
    ("vdd50m_100m_p90", 0.050, 100e6, 90.0, 0.0, 10e6, 0.0),
    ("vdd25m_625m_p0", 0.025, 625e6, 0.0, 0.0, 10e6, 0.0),
    ("vdd25m_625m_p90", 0.025, 625e6, 90.0, 0.0, 10e6, 0.0),
    ("ref20m_10m_p0", 0.0, 10e6, 0.0, 0.020, 10e6, 0.0),
    ("ref20m_10m_p90", 0.0, 10e6, 0.0, 0.020, 10e6, 90.0),
    ("ref20m_100m_p0", 0.0, 10e6, 0.0, 0.020, 100e6, 0.0),
    ("ref20m_100m_p90", 0.0, 10e6, 0.0, 0.020, 100e6, 90.0),
)


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
    parser.add_argument("--pvt", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    args.work.mkdir(parents=True, exist_ok=True)
    pvt = json.loads(args.pvt.read_text())
    if pvt.get("result") != "pass" or pvt.get("pex_sha256") != sha256_file(args.pex):
        raise SystemExit("PVT evidence is not passing or does not match this PEX")
    calibration = pvt.get("calibration", [])
    environment_index(calibration)
    template_path = args.source / "vco_bank_top_supply_tb.spice.in"
    template = template_path.read_text()
    crossing_names = tuple(f"cross_{index:02d}" for index in range(CROSSING_COUNT))
    crossing_measures = "\n".join(
        f"meas tran {name} when vdiff=0 rise={index + 1} td=12n"
        for index, name in enumerate(crossing_names)
    )
    pattern = re.compile(
        rf"^({'|'.join(SCALARS + crossing_names)})\s*=\s*([-+0-9.eE]+)",
        re.MULTILINE,
    )
    specifications = [
        (selection, disturbance)
        for selection in calibration
        for disturbance in DISTURBANCES
    ]

    def simulate(specification: tuple[object, ...]) -> dict[str, object]:
        selection, disturbance = specification
        mos, resistor, supply, temperature = selection["environment"]
        member = str(selection["selected_member"])
        codes = selection["selected_codes"]
        main, regen = int(codes["main"]), int(codes["regen"])
        (disturbance_id, vdd_ripple, vdd_frequency, vdd_phase,
         ref_ripple, ref_frequency, ref_phase) = disturbance
        environment_id = f"{mos}_{resistor}_{float(supply):.2f}_{int(temperature):+d}"
        case_id = f"{environment_id}_{member}_{disturbance_id}".replace(
            "+", "p"
        ).replace("-", "m").replace(".", "p")
        deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
        fast_codes = (main, regen) if member == "fast" else (0, 0)
        gain_codes = (main, regen) if member == "gain" else (0, 0)
        sources = (
            bit_sources("F", *fast_codes, float(supply))
            + bit_sources("G", *gain_codes, float(supply))
        )
        pulse = f"PULSE(0 {float(supply):.2f} 1n 20p 20p 250p 100n)"
        selected = "PWL(0 0 3n 0 3.1n 1.50)"
        deck_text = instantiate(template, {
            "MOS_CORNER": str(mos), "RES_CORNER": str(resistor),
            "TEMP_C": str(temperature), "VDD_V": f"{float(supply):.6f}",
            "VDD_RIPPLE_V": f"{float(vdd_ripple):.6f}",
            "VDD_RIPPLE_HZ": f"{float(vdd_frequency):.12g}",
            "VDD_PHASE_DEG": f"{float(vdd_phase):.1f}",
            "REF_RIPPLE_V": f"{float(ref_ripple):.6f}",
            "REF_RIPPLE_HZ": f"{float(ref_frequency):.12g}",
            "REF_PHASE_DEG": f"{float(ref_phase):.1f}",
            "PEX_PATH": str(args.pex), "DUT_CODE_PORTS": " ".join(CODE_PORTS),
            "BIT_SOURCES": "\n".join(sources),
            "FAST_KICKP_SOURCE": pulse if member == "fast" else "0",
            "FAST_KICKN_SOURCE": "0",
            "GAIN_KICKP_SOURCE": pulse if member == "gain" else "0",
            "GAIN_KICKN_SOURCE": "0",
            "SEL_A_SOURCE": selected if member == "fast" else "0",
            "SEL_B_SOURCE": selected if member == "gain" else "0",
            "CROSSING_MEASURES": crossing_measures,
            "CROSSING_NAMES": " ".join(crossing_names),
        })
        reusable = deck.exists() and log.exists() and deck.read_text() == deck_text
        if not reusable:
            deck.write_text(deck_text)
            with log.open("w") as output:
                run = subprocess.run(
                    ["ngspice", "-b", str(deck)], stdout=output,
                    stderr=subprocess.STDOUT, timeout=300, check=False,
                )
            return_code = run.returncode
        else:
            return_code = 0
        observed = {name: float(value) for name, value in pattern.findall(log.read_text())}
        crossings = [observed[name] for name in crossing_names if name in observed]
        periods = [upper - lower for lower, upper in zip(crossings, crossings[1:])]
        complete = return_code == 0 and len(observed) == len(SCALARS) + CROSSING_COUNT
        median_period = sorted(periods)[len(periods) // 2] if periods else 0.0
        return {
            "id": case_id,
            "environment": [mos, resistor, supply, temperature],
            "selected_member": member,
            "selected_codes": {"main": main, "regen": regen},
            "disturbance": {
                "id": disturbance_id,
                "vdd_ripple_peak_v": vdd_ripple,
                "vdd_ripple_hz": vdd_frequency,
                "vdd_phase_deg": vdd_phase,
                "reference_ripple_peak_v": ref_ripple,
                "reference_ripple_hz": ref_frequency,
                "reference_phase_deg": ref_phase,
            },
            "complete": complete,
            "observed": {name: observed.get(name) for name in SCALARS},
            "crossings_s": crossings,
            "periods_s": periods,
            "median_frequency_hz": 1.0 / median_period if median_period > 0 else 0.0,
            "period_peak_to_peak_s": max(periods) - min(periods) if periods else 1.0,
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(simulate, specifications))
    baselines = {
        tuple(case["environment"]): case
        for case in cases if case["disturbance"]["id"] == "baseline"
    }
    for case in cases:
        baseline = baselines.get(tuple(case["environment"]))
        baseline_periods = baseline["periods_s"] if baseline else []
        baseline_period = (
            sorted(baseline_periods)[len(baseline_periods) // 2]
            if baseline_periods else 0.0
        )
        periods = case["periods_s"]
        maximum_displacement = max(
            (abs(period - baseline_period) for period in periods), default=1.0
        )
        frequency = float(case["median_frequency_hz"])
        baseline_frequency = float(baseline["median_frequency_hz"]) if baseline else 0.0
        pushing = (
            abs(frequency - baseline_frequency) / baseline_frequency
            if baseline_frequency > 0 else 1.0
        )
        observed = case["observed"]
        case["maximum_cycle_displacement_s"] = maximum_displacement
        case["frequency_pushing_fraction"] = pushing
        passed = (
            case["complete"]
            and 1.20e9 <= frequency <= 1.30e9
            and float(case["period_peak_to_peak_s"]) <= 40e-12
            and maximum_displacement <= 40e-12
            and pushing <= 0.02
            and float(observed["startup_time"]) <= 8e-9
            and float(observed["diff_high"]) >= 0.15
            and float(observed["diff_low"]) <= -0.15
            and 0.4 <= float(observed["output_cm"]) <= float(case["environment"][2])
            and float(observed["supply_current"]) <= 0.035
            and float(observed["reference_power_avg"]) <= 0.003
        )
        case["result"] = "pass" if passed else "fail"
    groups = []
    for selection in calibration:
        environment = selection["environment"]
        members = [case for case in cases if case["environment"] == environment]
        groups.append({
            "environment": environment,
            "case_count": len(members),
            "passing_case_count": sum(case["result"] == "pass" for case in members),
            "maximum_cycle_displacement_s": max(
                case["maximum_cycle_displacement_s"] for case in members
            ),
            "maximum_frequency_pushing_fraction": max(
                case["frequency_pushing_fraction"] for case in members
            ),
            "result": "pass" if len(members) == len(DISTURBANCES)
            and all(case["result"] == "pass" for case in members) else "fail",
        })
    environment_index(groups)
    passed = len(groups) == 5 and all(group["result"] == "pass" for group in groups)
    result = {
        "schema_version": 1,
        "claim": "selected_vco_bank_parent_bounded_supply_reference_pushing",
        "case_count": len(cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "passing_environment_count": sum(group["result"] == "pass" for group in groups),
        "cycle_displacement_limit_s": 40e-12,
        "frequency_pushing_limit_fraction": 0.02,
        "groups": groups,
        "cases": cases,
        "pex_sha256": sha256_file(args.pex),
        "pvt_evidence_sha256": sha256_file(args.pvt),
        "simulation_source_sha256": sha256_file(Path(__file__)),
        "testbench_source_sha256": sha256_file(template_path),
        "shared_evidence_source_sha256": sha256_file(SERDES_ROOT / "analog_evidence.py"),
        "result": "pass" if passed else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        f"selected bank supply/reference stress: {result['passing_case_count']}/"
        f"{result['case_count']} cases; {result['passing_environment_count']}/5 env"
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
