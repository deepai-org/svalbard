#!/usr/bin/env python3
"""Compose extracted predriver/final segments behind the six-clock API."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


KINDS = ("sampler_pre", "sampler_final", "capture_pre", "capture_final")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wrapper() -> str:
    lines = [
        ".subckt local_clock_fanout_pex CLKP_H CLKP_HB CLKN_H CLKN_HB VDD VSS",
        "+ E_SENSE E_CAPTURE_CLK E_CAPTURE_CLKB O_SENSE O_CAPTURE_CLK O_CAPTURE_CLKB",
    ]
    branches = (
        ("SE", "CLKP_HB", "E_SENSE", "sampler"),
        ("SO", "CLKN_HB", "O_SENSE", "sampler"),
        ("CE", "CLKP_H", "E_CAPTURE_CLK", "capture"),
        ("CO", "CLKN_H", "O_CAPTURE_CLK", "capture"),
        ("CBE", "CLKP_HB", "E_CAPTURE_CLKB", "capture"),
        ("CBO", "CLKN_HB", "O_CAPTURE_CLKB", "capture"),
    )
    for name, source, output, family in branches:
        mid = f"{name}_MID"
        lines.extend([
            f"X{name}P {source} 0 VDD VSS {mid} {name}_PDUMMY distributed_{family}_pre_pex",
            f"X{name}F {mid} 0 VDD VSS {output} {name}_FDUMMY distributed_{family}_final_pex",
        ])
    lines.append(".ends local_clock_fanout_pex")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    for kind in KINDS:
        parser.add_argument(f"--{kind.replace('_', '-')}", type=Path, required=True)
    parser.add_argument("--segment-physical", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--physical-output", type=Path, required=True)
    args = parser.parse_args()
    physical = json.loads(args.segment_physical.read_text())
    if physical.get("result") != "pass":
        raise ValueError("segment physical record is not passing")
    paths = {kind: getattr(args, kind) for kind in KINDS}
    for kind, path in paths.items():
        recorded = physical["segments"][kind]["identity"]["pex_sha256"]
        if recorded != digest(path):
            raise ValueError(f"{kind} PEX identity mismatch")
    args.output.write_text("\n".join(path.read_text() for path in paths.values())
                           + "\n" + wrapper())
    record = {
        "schema_version": 1,
        "claim": "isolated_segmented_leaf_pex_composition_identity",
        "top": "local_clock_fanout",
        "selected_candidate": {
            "sampler_stage_mults": [6, 16, 32],
            "sampler_final_p_mult": 32,
            "sampler_final_n_mult": 32,
            "capture_pre_mult": 4,
            "capture_output_mult": 8,
        },
        "segment_pex_sha256": {kind: digest(path) for kind, path in paths.items()},
        "identity": {
            "pex_sha256": digest(args.output),
            "segment_physical_sha256": digest(args.segment_physical),
        },
        "result": "pass",
        "not_a_claim": ["inter-segment routed RC", "routed parent", "PCIe compliance"],
    }
    args.physical_output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
