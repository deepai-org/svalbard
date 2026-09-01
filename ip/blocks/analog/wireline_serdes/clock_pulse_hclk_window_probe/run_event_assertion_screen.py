#!/usr/bin/env python3
"""Screen realizable assertion-duration candidates into the exact lane PEX."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path

import compile_event_capture_state_free_stretched_source as compiler
import run_event_capture_schematic as event_runner
import run_event_lane_composition as composition
import run_hclk_window_probe as base


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane-pex", required=True, type=Path)
    parser.add_argument("--lane-physical", required=True, type=Path)
    parser.add_argument("--delay-cells", nargs="+", type=int, default=[1, 2, 3, 4])
    parser.add_argument("--environment-ids", nargs="+", default=["tt", "ss_hot"])
    parser.add_argument("--control-id", default="sense1_interval0_epoch0")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    composition.require(1 <= args.jobs <= 8, "jobs must be 1--8")
    composition.require(len(args.delay_cells) == len(set(args.delay_cells)),
                        "delay-cell candidates must be unique")
    lane_physical = composition.require_physical_pex(
        args.lane_pex, args.lane_physical, False)
    environments = {item["id"]: item for item in base.CONTRACT["environments"]}
    controls = {item["id"]: item for item in event_runner.CONTROLS}
    composition.require(set(args.environment_ids) <= environments.keys(),
                        "unknown environment")
    composition.require(args.control_id in controls, "unknown control")
    args.work.mkdir(parents=True, exist_ok=True)
    sources = {}
    for delay_cells in args.delay_cells:
        source = args.work / f"assertion_delay{delay_cells}.spice"
        source.write_text(compiler.compile_source(delay_cells, True))
        sources[delay_cells] = source
    specs = []
    for delay_cells, source in sources.items():
        node_names = [("sfdrv", "SFDRV"), ("sfwide", "SFWIDE")]
        if delay_cells:
            node_names.append(("sfdelay", "SFDELAY"))
        schematic_debug_nodes = tuple(
            (f"{phase}_{name}", f"xevent.x{phase}.{node}")
            for phase in ("e", "o") for name, node in node_names)
        for environment_id in args.environment_ids:
            case_work = args.work / f"delay{delay_cells}"
            case_work.mkdir(exist_ok=True)
            specs.append((delay_cells, (source, args.lane_pex, case_work,
                                        environments[environment_id],
                                        controls[args.control_id], (), False,
                                        schematic_debug_nodes)))

    def run_tagged(spec):
        delay_cells, case_spec = spec
        case = composition.run_case(case_spec)
        case["delay_cells"] = delay_cells
        return case

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        cases = list(pool.map(run_tagged, specs))
    candidates = []
    for delay_cells in args.delay_cells:
        selected = [case for case in cases if case["delay_cells"] == delay_cells]
        candidates.append({
            "id": f"delay_cells_{delay_cells}",
            "delay_cells": delay_cells,
            "schematic_sha256": digest(sources[delay_cells]),
            "passing_case_count": sum(case["result"] == "pass" for case in selected),
            "case_count": len(selected),
            "environment_coverage": [case["environment_id"] for case in selected
                                     if case["result"] == "pass"],
        })
    result = {
        "schema_version": 1,
        "claim": "realizable_assertion_duration_screen_into_exact_lane_pex",
        "scope": "schematic event and interface candidate driving one exact physically bound lane PEX",
        "source_revision": compiler.SOURCE_REVISION,
        "lane_claim": lane_physical["claim"],
        "lane_pex_sha256": digest(args.lane_pex),
        "control_id": args.control_id,
        "environments": args.environment_ids,
        "candidates": candidates,
        "cases": cases,
        "not_a_claim": ["event or interface PEX", "routed parent", "five-environment closure", "PCIe compliance"],
        "result": "pass" if any(item["passing_case_count"] == item["case_count"]
                                  for item in candidates) else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": result["result"], "candidates": candidates}, sort_keys=True))
    raise SystemExit(0 if result["result"] == "pass" else 1)


if __name__ == "__main__":
    main()
