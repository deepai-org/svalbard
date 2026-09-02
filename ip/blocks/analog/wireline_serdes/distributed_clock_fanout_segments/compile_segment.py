#!/usr/bin/env python3
"""Lower placeable predriver/final segments from the selected V7 fanout."""

from __future__ import annotations

import argparse
from pathlib import Path


KINDS = {
    "sampler_pre": ("distributed_sampler_pre", (6, 16)),
    "sampler_final": ("distributed_sampler_final", (32,)),
    "capture_pre": ("distributed_capture_pre", (4,)),
    "capture_final": ("distributed_capture_final", (8,)),
}
SOURCE_REVISION = "distributed_v3_consumer_local_final_segments"


def devices(kind: str, flat: bool) -> list[str]:
    _, stages = KINDS[kind]
    result, source = [], "A"
    for index, mult in enumerate(stages):
        target = "Y" if index == len(stages) - 1 else f"B{index}"
        if flat:
            width = 8 * mult
            result.extend([
                f"XP_E{index} {target} {source} VDD VDD pfet_03v3 w={width}u l=0.28u",
                f"XN_E{index} {target} {source} VSS VSS nfet_03v3 w={width}u l=0.28u",
            ])
        else:
            result.append(
                f"XES__XI{index} {source} {target} VDD VSS cp_inv MP={mult} MN={mult}")
        source = target
    # Explicit tied-off placer dummy; never connected to functional Y.
    source = "DUMMY_A"
    for index in range(len(stages)):
        target = "DUMMY_Y" if index == len(stages) - 1 else f"DB{index}"
        if flat:
            result.extend([
                f"XP_O{index} {target} {source} VDD VDD pfet_03v3 w=8u l=0.28u",
                f"XN_O{index} {target} {source} VSS VSS nfet_03v3 w=8u l=0.28u",
            ])
        else:
            result.append(
                f"XOS__XI{index} {source} {target} VDD VSS cp_inv MP=1 MN=1")
        source = target
    return result


def compile_source(kind: str, flat_for_lvs: bool = False) -> str:
    top, _ = KINDS[kind]
    primitive = "" if flat_for_lvs else """
.subckt cp_inv A Y VDD VSS params: MP=1 MN=1
XP Y A VDD VDD pfet_03v3 w=8u l=0.28u m={MP}
XN Y A VSS VSS nfet_03v3 w=8u l=0.28u m={MN}
.ends cp_inv
"""
    return f"""* SPDX-License-Identifier: Apache-2.0
* source_revision: {SOURCE_REVISION}
* segment: {kind}
{primitive}
.subckt {top} A DUMMY_A VDD VSS Y DUMMY_Y
{chr(10).join(devices(kind, flat_for_lvs))}
.ends {top}
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=KINDS, required=True)
    parser.add_argument("--flatten-for-lvs", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(compile_source(args.kind, args.flatten_for_lvs))


if __name__ == "__main__":
    main()
