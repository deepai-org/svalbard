#!/usr/bin/env python3
"""Screen edge-selective release holds into the exact regenerative lane PEX."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path

import compile_event_capture_state_free_edge_hold_source as compiler
import run_event_capture_schematic as event_runner
import run_event_lane_composition as composition
import run_hclk_window_probe as base


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane-pex", required=True, type=Path)
    parser.add_argument("--lane-physical", required=True, type=Path)
    parser.add_argument("--hold-mults", nargs="+", type=int, default=[1, 2, 4, 8])
    parser.add_argument("--hold-widths", nargs="+", type=float, default=[8])
    parser.add_argument("--delay-mult", type=int, default=16)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    lane_physical = composition.require_physical_pex(
        args.lane_pex, args.lane_physical, False)
    environments = {item["id"]: item for item in base.CONTRACT["environments"]}
    control = next(item for item in event_runner.CONTROLS
                   if item["id"] == "sense1_interval0_epoch0")
    args.work.mkdir(parents=True, exist_ok=True)
    sources = {}
    specs = []
    debug_nodes = tuple(
        (f"{phase}_{name}", f"xevent.x{phase}.{node}")
        for phase in ("e", "o")
        for name, node in (("sfdrv", "SFDRV"), ("sfrel", "SFREL")))
    for hold_mult in args.hold_mults:
        for hold_width in args.hold_widths:
            key = (hold_mult, hold_width)
            source = args.work / f"edge_hold_m{hold_mult}_w{hold_width}.spice"
            source.write_text(compiler.compile_source(
                hold_mult, args.delay_mult, screening_top=True,
                hold_width_um=hold_width))
            sources[key] = source
            case_work = args.work / f"m{hold_mult}_w{hold_width}"
            case_work.mkdir(exist_ok=True)
            for environment_id in ("tt", "ss_hot"):
                specs.append((key, (source, args.lane_pex, case_work,
                             environments[environment_id], control, (), False,
                             debug_nodes)))

    def run_tagged(spec):
        (hold_mult, hold_width), case_spec = spec
        case = composition.run_case(case_spec)
        case["hold_mult"] = hold_mult
        case["hold_width_um"] = hold_width
        return case

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        cases = list(pool.map(run_tagged, specs))
    candidates = []
    for hold_mult, hold_width in sources:
        selected = [case for case in cases if case["hold_mult"] == hold_mult
                    and case["hold_width_um"] == hold_width]
        candidates.append({
            "id": f"hold_m{hold_mult}_w{hold_width}_delay_m{args.delay_mult}",
            "hold_mult": hold_mult,
            "hold_width_um": hold_width,
            "delay_mult": args.delay_mult,
            "schematic_sha256": digest(sources[(hold_mult, hold_width)]),
            "case_count": len(selected),
            "passing_case_count": sum(case["result"] == "pass" for case in selected),
            "environment_coverage": [case["environment_id"] for case in selected
                                     if case["result"] == "pass"],
        })
    result = {
        "schema_version": 1,
        "claim": "edge_selective_sense_release_screen_into_exact_lane_pex",
        "scope": "schematic event/interface candidate driving one exact physically bound lane PEX",
        "source_revision": compiler.SOURCE_REVISION,
        "lane_claim": lane_physical["claim"],
        "lane_pex_sha256": digest(args.lane_pex),
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
