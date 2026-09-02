#!/usr/bin/env python3
"""Compose independently extracted branch pairs behind the legacy fanout API."""

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("--sampler", type=Path, required=True)
parser.add_argument("--capture", type=Path, required=True)
parser.add_argument("--leaf-physical", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--physical-output", type=Path, required=True)
args = parser.parse_args()
leaf = json.loads(args.leaf_physical.read_text())
if leaf.get("result") != "pass":
    raise ValueError("leaf physical record is not passing")
if leaf["branches"]["sampler"]["identity"]["pex_sha256"] != digest(args.sampler):
    raise ValueError("sampler PEX identity mismatch")
if leaf["branches"]["capture"]["identity"]["pex_sha256"] != digest(args.capture):
    raise ValueError("capture PEX identity mismatch")
wrapper = """
.subckt local_clock_fanout_pex CLKP_H CLKP_HB CLKN_H CLKN_HB VDD VSS
+ E_SENSE E_CAPTURE_CLK E_CAPTURE_CLKB O_SENSE O_CAPTURE_CLK O_CAPTURE_CLKB
XS CLKP_HB CLKN_HB VDD VSS E_SENSE O_SENSE distributed_sampler_pair_pex
XC CLKP_H CLKN_H VDD VSS E_CAPTURE_CLK O_CAPTURE_CLK distributed_capture_pair_pex
XCB CLKP_HB CLKN_HB VDD VSS E_CAPTURE_CLKB O_CAPTURE_CLKB distributed_capture_pair_pex
.ends local_clock_fanout_pex
"""
args.output.write_text(args.sampler.read_text() + "\n" + args.capture.read_text() + wrapper)
physical = {
    "schema_version": 1,
    "claim": "isolated_distributed_leaf_pex_composition_identity",
    "top": "local_clock_fanout",
    "selected_candidate": {
        "sampler_stage_mults": [6, 16, 32],
        "sampler_final_p_mult": 32,
        "sampler_final_n_mult": 32,
        "capture_pre_mult": 4,
        "capture_output_mult": 8
    },
    "identity": {
        "pex_sha256": digest(args.output),
        "leaf_physical_sha256": digest(args.leaf_physical)
    },
    "result": "pass",
    "not_a_claim": ["routed parent", "placed interconnect", "PCIe compliance"]
}
args.physical_output.write_text(json.dumps(physical, indent=2, sort_keys=True) + "\n")
