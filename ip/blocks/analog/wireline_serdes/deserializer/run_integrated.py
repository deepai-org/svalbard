#!/usr/bin/env python3
"""Compose full-RC CML regeneration with transistor-level CMOS capture."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path

BITS = (1, 0, 1, 1, 0, 0, 1, 0, 1, 0, 0, 1, 1, 0)
SAMPLE_INDICES = tuple(range(3, 12))
ENVIRONMENTS = (
    ("typical", 3.30, 27, 0.70),
    ("ff", 2.97, -40, 0.60), ("ff", 2.97, -40, 0.80),
    ("ff", 3.63, 125, 0.60), ("ff", 3.63, 125, 0.80),
    ("ss", 2.97, 125, 0.60), ("ss", 2.97, 125, 0.80),
    ("ss", 3.63, -40, 0.60), ("ss", 3.63, -40, 0.80),
)
CAPTURE_CLOSE_PS = (820, 850, 880, 900)
OUTPUT_SETTLE_PS = 300
SCALAR = re.compile(r"^(q_\d+|qb_\d+|supply_current)\s*=\s*([-+0-9.eE]+)",
                    re.MULTILINE)


def instantiate(template: str, values: dict[str, str]) -> str:
    result = template
    for name, value in values.items():
        result = result.replace(f"@{name}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", result)))
    if remaining:
        raise ValueError(f"unfilled tokens: {remaining}")
    return result


def input_pwl(positive: bool, common_mode: float, peak: float) -> str:
    interval, edge = 800e-12, 20e-12
    points = [(0.0, common_mode + (peak if BITS[0] == positive else -peak))]
    previous = BITS[0]
    for index, bit in enumerate(BITS[1:], start=1):
        if bit == previous:
            continue
        center = index * interval
        old = common_mode + (peak if previous == positive else -peak)
        new = common_mode + (peak if bit == positive else -peak)
        points.extend(((center - edge / 2, old), (center + edge / 2, new)))
        previous = bit
    points.append(((len(BITS) + 1) * interval,
                   common_mode + (peak if previous == positive else -peak)))
    return " ".join(f"{time:.12g} {voltage:.6f}" for time, voltage in points)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--frontend-pex", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--timeout-s", type=int, default=300)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    args.work.mkdir(parents=True, exist_ok=True)
    deserializer = args.source / "deserializer.spice"
    template = (args.source / "integrated_tb.spice.in").read_text()
    frontend_sha256 = hashlib.sha256(args.frontend_pex.read_bytes()).hexdigest()
    deserializer_sha256 = hashlib.sha256(deserializer.read_bytes()).hexdigest()
    expected_scalars = 2 * len(SAMPLE_INDICES) + 1
    specifications = []
    for mos, vdd, temp, common_mode_fraction in ENVIRONMENTS:
        common_mode = vdd * common_mode_fraction
        for close_ps in CAPTURE_CLOSE_PS:
            case_id = (f"{mos}_{vdd:.2f}_{temp:+d}_cm{common_mode_fraction:.2f}_"
                       f"close{close_ps}")
            case_id = case_id.replace("+", "p").replace("-", "m").replace(".", "p")
            measures = []
            for index in SAMPLE_INDICES:
                time = index * 800e-12 + (close_ps + OUTPUT_SETTLE_PS) * 1e-12
                measures.append(f"meas tran q_{index} find v(Q) at={time:.12g}")
                measures.append(f"meas tran qb_{index} find v(QB) at={time:.12g}")
            values = {
                "FRONTEND_SHA256": frontend_sha256,
                "DESERIALIZER_SHA256": deserializer_sha256,
                "FRONTEND_PATH": str(args.frontend_pex),
                "DESERIALIZER_PATH": str(deserializer),
                "MOS_CORNER": mos, "TEMP_C": str(temp), "VDD_V": f"{vdd:.2f}",
                "INP_PWL": input_pwl(True, common_mode, 0.10),
                "INN_PWL": input_pwl(False, common_mode, 0.10),
                "BOOST_CLOCK": (f"PULSE(0 {vdd:.2f} 50p 20p 20p 575p 800p)"
                                if common_mode_fraction <= 0.70 else "0"),
                "CAPTURE_WIDTH": f"{close_ps - 620}p",
                "TSTOP": f"{len(BITS) * 800e-12:.12g}",
                "MEASURES": "\n".join(measures),
            }
            specifications.append((case_id, mos, vdd, temp, common_mode_fraction,
                                   close_ps, values))

    def simulate(specification: tuple[object, ...]) -> dict[str, object]:
        case_id, mos, vdd, temp, common_mode_fraction, close_ps, values = specification
        deck = args.work / f"{case_id}.spice"
        log = args.work / f"{case_id}.log"
        deck_text = instantiate(template, values)
        reusable = (deck.exists() and log.exists() and deck.read_text() == deck_text
                    and len({name for name, _ in SCALAR.findall(log.read_text())})
                    == expected_scalars)
        return_code = 0
        if not reusable:
            deck.write_text(deck_text)
            with log.open("w") as output:
                try:
                    run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                         stderr=subprocess.STDOUT, timeout=args.timeout_s,
                                         check=False)
                    return_code = run.returncode
                except subprocess.TimeoutExpired:
                    return_code = 124
        observed = {name: float(value) for name, value in SCALAR.findall(log.read_text())}
        margins = []
        for index in SAMPLE_INDICES:
            q = observed.get(f"q_{index}", 0.0)
            qb = observed.get(f"qb_{index}", 0.0)
            high, low = (q, qb) if BITS[index] else (qb, q)
            margins.extend((high - 0.8 * vdd, 0.2 * vdd - low))
        complete = return_code == 0 and len(observed) == expected_scalars
        margin = min(margins)
        current = observed.get("supply_current", 0.0)
        passed = complete and margin >= 0 and 1e-5 <= current <= 0.025
        return {
            "id": case_id, "environment": [mos, vdd, temp, common_mode_fraction],
            "capture_close_s": close_ps * 1e-12,
            "output_sample_s": (close_ps + OUTPUT_SETTLE_PS) * 1e-12,
            "complete": complete, "logic_margin_v": margin,
            "supply_current_a": current, "result": "pass" if passed else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(simulate, specifications))
    groups = []
    for environment in sorted({tuple(case["environment"]) for case in cases}):
        members = [case for case in cases if tuple(case["environment"]) == environment]
        passing = [case for case in members if case["result"] == "pass"]
        groups.append({
            "environment": list(environment), "case_count": len(members),
            "passing_case_count": len(passing),
            "passing_capture_close_s": [case["capture_close_s"] for case in passing],
            "result": "pass" if passing else "fail",
        })
    complete_count = sum(case["complete"] for case in cases)
    passing_groups = sum(group["result"] == "pass" for group in groups)
    result = {
        "schema_version": 1, "frontend_pex_sha256": frontend_sha256,
        "deserializer_sha256": deserializer_sha256,
        "result": "pass" if complete_count == len(cases)
                  and passing_groups == len(groups) else "fail",
        "case_count": len(cases), "complete_case_count": complete_count,
        "group_count": len(groups), "passing_group_count": passing_groups,
        "cases": cases, "groups": groups,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"integrated capture: {complete_count}/{len(cases)} complete; "
          f"{passing_groups}/{len(groups)} environments pass")
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
