#!/usr/bin/env python3
"""Compile the manifest-selected dual-phase pulse macro for layout/LVS."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import run_sense_write_composition as compose


SELECTED_WRITE = "hier_epoch_extra_2x_start_0p85x"
SELECTED_SENSE = "sense_edge_pm12_base4_extra64_folded"
TOP = "selected_dual_control_pulse"


def select(candidates: list[dict], identifier: str) -> dict:
    matches = [candidate for candidate in candidates
               if candidate["id"] == identifier]
    compose.base.require(len(matches) == 1,
                         f"selected candidate {identifier} must resolve once")
    return matches[0]


def compile_source() -> str:
    write = select(compose.WRITE_CANDIDATES, SELECTED_WRITE)
    sense = select(compose.SENSE_CANDIDATES, SELECTED_SENSE)
    prefix = compose.source_prefix()
    start = prefix.find(".subckt cp_inv")
    compose.base.require(start >= 0, "primitive source boundary not found")
    suffix = compose.APPEND_PATH.read_text().split("\nVDD VDD 0 PWL", 1)[0]
    text = prefix[start:] + suffix
    for key, value in {**write["replacements"],
                       **sense["replacements"]}.items():
        text = text.replace(f"@{key}@", value)
    unresolved = sorted(set(compose.base.PLACEHOLDER.findall(text)))
    compose.base.require(not unresolved,
                         f"physical source has unresolved placeholders: {unresolved}")
    top = f"""

.subckt {TOP} CLKP_H CLKN_H SEL0 SEL1 VDD VSS
+ E_SENSE E_BOOST E_WRITE O_SENSE O_BOOST O_WRITE
XE CLKP_H SEL0 SEL1 VDD VSS E_SENSE E_BOOST E_WRITE E_WPN sense_write_phase
XO CLKN_H SEL0 SEL1 VDD VSS O_SENSE O_BOOST O_WRITE O_WPN sense_write_phase
.ends {TOP}
"""
    return "* SPDX-License-Identifier: Apache-2.0\n" + text.strip() + top


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = compile_source()
    args.output.write_text(source)
    print(f"top={TOP} source_sha256={hashlib.sha256(source.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
