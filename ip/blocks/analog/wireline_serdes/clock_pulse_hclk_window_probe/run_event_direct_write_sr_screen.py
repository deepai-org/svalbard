#!/usr/bin/env python3
"""Screen local direct-write SENSE latches into the exact lane PEX."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path

import compile_event_capture_direct_write_sr_source as compiler
import run_event_capture_schematic as event_runner
import run_event_lane_composition as composition
import run_hclk_window_probe as base


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane-pex", required=True, type=Path)
    parser.add_argument("--lane-physical", required=True, type=Path)
    parser.add_argument("--latch-mults", nargs="+", type=int, default=[1])
    parser.add_argument("--write-mults", nargs="+", type=int, default=[4])
    parser.add_argument("--latch-p-widths", nargs="+", type=int, default=[4])
    parser.add_argument("--control-id", default="sense1_interval1_epoch0")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    lane_physical = composition.require_physical_pex(
        args.lane_pex, args.lane_physical, False)
    environments = {item["id"]: item for item in base.CONTRACT["environments"]}
    controls = {item["id"]: item for item in event_runner.CONTROLS}
    composition.require(args.control_id in controls,
                        f"unknown control id: {args.control_id}")
    control = controls[args.control_id]
    args.work.mkdir(parents=True, exist_ok=True)
    sources: dict[tuple[int, int, int], Path] = {}
    specs = []
    debug_nodes = tuple(
        (f"{phase}_{name}", f"xevent.x{phase}.xsensedw.{node}")
        for phase in ("e", "o")
        for name, node in (("startb", "STARTB"), ("endb", "ENDB"),
                           ("q", "Q"), ("qb", "QB"), ("o0", "O0")))
    for latch_mult in args.latch_mults:
        for write_mult in args.write_mults:
            for latch_p_width in args.latch_p_widths:
                key = (latch_mult, write_mult, latch_p_width)
                source = args.work / f"direct_write_sr_l{latch_mult}_w{write_mult}_p{latch_p_width}.spice"
                source.write_text(compiler.compile_source(
                    latch_mult, write_mult, screening_top=True,
                    latch_p_width_um=latch_p_width))
                sources[key] = source
                case_work = args.work / f"l{latch_mult}_w{write_mult}_p{latch_p_width}"
                case_work.mkdir(exist_ok=True)
                for environment_id in ("tt", "ss_hot"):
                    specs.append((key, (source, args.lane_pex, case_work,
                                 environments[environment_id], control, (), False,
                                 debug_nodes)))

    def run_tagged(spec):
        key, case_spec = spec
        case = composition.run_case(case_spec)
        case["latch_mult"], case["write_mult"], case["latch_p_width_um"] = key
        return case

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        cases = list(pool.map(run_tagged, specs))
    candidates = []
    for key, source in sources.items():
        latch_mult, write_mult, latch_p_width = key
        selected = [case for case in cases
                    if (case["latch_mult"], case["write_mult"],
                        case["latch_p_width_um"]) == key]
        candidates.append({
            "id": f"direct_write_sr_l{latch_mult}_w{write_mult}_p{latch_p_width}_{args.control_id}",
            "latch_mult": latch_mult,
            "write_mult": write_mult,
            "latch_p_width_um": latch_p_width,
            "schematic_sha256": digest(source),
            "case_count": len(selected),
            "passing_case_count": sum(case["result"] == "pass" for case in selected),
            "environment_coverage": [case["environment_id"] for case in selected
                                     if case["result"] == "pass"],
        })
    result = {
        "schema_version": 1,
        "claim": "direct_write_start_end_sense_screen_into_exact_lane_pex",
        "scope": "schematic event/interface candidate driving one exact physically bound lane PEX",
        "source_revision": compiler.SOURCE_REVISION,
        "control_id": args.control_id,
        "lane_claim": lane_physical["claim"],
        "lane_pex_sha256": digest(args.lane_pex),
        "candidates": candidates,
        "cases": cases,
        "not_a_claim": ["event or interface PEX", "routed parent",
                        "five-environment closure", "PCIe compliance"],
        "result": "pass" if any(item["passing_case_count"] == item["case_count"]
                                  for item in candidates) else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": result["result"], "candidates": candidates},
                     sort_keys=True))
    raise SystemExit(0 if result["result"] == "pass" else 1)


if __name__ == "__main__":
    main()
