#!/usr/bin/env python3
"""Check integrated half-rate sampler/detector direction versus phase offset."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

OFFSETS_S = (-120e-12, -80e-12, -40e-12, 40e-12, 80e-12, 120e-12)
EDGE_PHASES_DEG = (-90.0, -112.5, -135.0, -157.5)
SAMPLE_CYCLES = (6, 7, 8)
SCALAR_NAMES = ("early0_avg", "late0_avg", "early1_avg", "late1_avg",
                "data_even_avg", "data_odd_avg", "edge_even_avg", "edge_odd_avg",
                "supply_current")
SCALAR = re.compile(
    rf"^({'|'.join(SCALAR_NAMES)}|(?:early|late)[01]_\d+)\s*=\s*([-+0-9.eE]+)",
    re.MULTILINE,
)


def sample_measures(ui: float) -> str:
    measures = []
    for cycle in SAMPLE_CYCLES:
        boundary0_time = (2 * cycle + 1) * ui + 150e-12
        boundary1_time = (2 * cycle + 2) * ui + 150e-12
        measures.extend((
            f"meas tran early0_{cycle} find early0 at={boundary0_time:.12g}",
            f"meas tran late0_{cycle} find late0 at={boundary0_time:.12g}",
            f"meas tran early1_{cycle} find early1 at={boundary1_time:.12g}",
            f"meas tran late1_{cycle} find late1 at={boundary1_time:.12g}",
        ))
    return "\n".join(measures)


def instantiate(template: str, values: dict[str, str]) -> str:
    result = template
    for name, value in values.items():
        result = result.replace(f"@{name}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", result)))
    if remaining:
        raise ValueError(f"unfilled tokens: {remaining}")
    return result


def alternating_pwl(positive: bool, common_mode: float, peak: float, ui: float,
                    edge: float, offset: float, count: int) -> str:
    points = [(0.0, common_mode + (peak if positive else -peak))]
    previous = 1
    for index in range(1, count):
        bit = 1 - previous
        center = (index + 0.5) * ui + offset
        old = common_mode + (peak if previous == positive else -peak)
        new = common_mode + (peak if bit == positive else -peak)
        points.extend(((center - edge / 2, old), (center + edge / 2, new)))
        previous = bit
    points.append(((count + 1) * ui,
                   common_mode + (peak if previous == positive else -peak)))
    return " ".join(f"{time:.12g} {voltage:.6f}" for time, voltage in points)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path,
                        help="CDR directory mounted at /src")
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "integrated_detector/phase_offset_tb.spice.in").read_text()
    ui, edge, count = 1 / 2.5e9, 20e-12, 24
    cases = []
    for edge_phase in EDGE_PHASES_DEG:
      for offset in OFFSETS_S:
        case_id = (f"phase_{edge_phase:+.1f}_offset_{offset / 1e-12:+.0f}ps"
                   .replace("+", "p").replace("-", "m").replace(".", "p"))
        values = {
            "MOS_CORNER": "typical", "RES_CORNER": "res_typical", "TEMP_C": "27",
            "VDD_V": "3.30", "CLOCK_CM_V": "2.20", "CLOCK_PEAK_V": "0.45",
            "EDGE_PHASE_DEG": f"{edge_phase:.1f}",
            "EDGE_N_PHASE_DEG": f"{edge_phase + 180:.1f}",
            "DATA_P_PWL": alternating_pwl(True, 2.20, 0.14, ui, edge, offset, count),
            "DATA_N_PWL": alternating_pwl(False, 2.20, 0.14, ui, edge, offset, count),
            "VBIAS_SAMPLER_V": "1.10", "VBIAS_PD_V": "0.80",
            "TSTEP_S": f"{ui / 100:.12g}", "TSTOP_S": f"{count * ui:.12g}",
            "MEAS_START_S": f"{8 * ui:.12g}", "SAMPLE_MEASURES": sample_measures(ui),
        }
        deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
        deck_text = instantiate(template, values)
        reusable = (deck.exists() and log.exists() and deck.read_text() == deck_text
                    and len({name for name, _ in SCALAR.findall(log.read_text())})
                    == len(SCALAR_NAMES) + 4 * len(SAMPLE_CYCLES))
        if reusable:
            return_code = 0
        else:
            deck.write_text(deck_text)
            with log.open("w") as output:
                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                     stderr=subprocess.STDOUT, timeout=120, check=False)
            return_code = run.returncode
        observed = {name: float(value) for name, value in SCALAR.findall(log.read_text())}
        complete = (return_code == 0
                    and len(observed) == len(SCALAR_NAMES) + 4 * len(SAMPLE_CYCLES))
        # A transition before the edge sample makes EARLY true/LATE false;
        # a transition after it makes EARLY false/LATE true.
        expected_early_sign = 1 if offset < 0 else -1
        signed = []
        for cycle in SAMPLE_CYCLES:
            signed.extend((expected_early_sign * observed.get(f"early0_{cycle}", 0.0),
                           -expected_early_sign * observed.get(f"late0_{cycle}", 0.0),
                           expected_early_sign * observed.get(f"early1_{cycle}", 0.0),
                           -expected_early_sign * observed.get(f"late1_{cycle}", 0.0)))
        passed = (complete and min(signed) >= 0.10
                  and 0.003 <= observed["supply_current"] <= 0.030)
        cases.append({"id": case_id, "edge_phase_deg": edge_phase,
                      "transition_offset_s": offset,
                      "minimum_directional_margin_v": min(signed),
                      "observed": observed, "result": "pass" if passed else "fail"})
    groups = []
    for phase in EDGE_PHASES_DEG:
        members = [case for case in cases if case["edge_phase_deg"] == phase]
        gating = [case for case in members if abs(case["transition_offset_s"]) <= 40e-12]
        groups.append({"edge_phase_deg": phase,
                       "minimum_gating_margin_v": min(case["minimum_directional_margin_v"]
                                                       for case in gating),
                       "passing_gating_case_count": sum(case["result"] == "pass"
                                                        for case in gating),
                       "gating_case_count": len(gating)})
    selected = max(groups, key=lambda group: group["minimum_gating_margin_v"])
    passing = sum(case["result"] == "pass" for case in cases)
    passed = selected["passing_gating_case_count"] == selected["gating_case_count"]
    result = {"schema_version": 1, "result": "pass" if passed else "fail",
              "case_count": len(cases), "passing_case_count": passing,
              "selected_edge_phase": selected, "phase_groups": groups, "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"cdr_alexander_frontend phase direction: {passing}/{len(cases)}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
