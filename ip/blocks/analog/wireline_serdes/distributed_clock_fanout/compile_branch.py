#!/usr/bin/env python3
"""Lower independently placeable final clock-fanout branch macros."""

from __future__ import annotations

import argparse
from pathlib import Path


KINDS = {
    "sampler": ("distributed_sampler_branch", (6, 16, 32), "SENSE"),
    "capture": ("distributed_capture_branch", (4, 8), "CAPTURE_CLK"),
}
SOURCE_REVISION = "distributed_v2_individually_placeable_v7_branches"


def compile_source(kind: str) -> str:
    top, stages, output = KINDS[kind]
    calls = []
    source = "CLKP_H"
    for index, mult in enumerate(stages):
        target = f"E_{output}" if index == len(stages) - 1 else f"E_B{index}"
        calls.append(
            f"XES__XI{index} {source} {target} VDD VSS cp_inv "
            f"MP={mult} MN={mult}")
        source = target
    # The current placer requires both phase roots. This tied-off 1x physical
    # dummy is not connected to the functional output and is explicit in PEX.
    source = "CLKN_H"
    for index in range(len(stages)):
        target = "O_DUMMY" if index == len(stages) - 1 else f"O_DB{index}"
        calls.append(f"XOS__XI{index} {source} {target} VDD VSS cp_inv MP=1 MN=1")
        source = target
    return f"""* SPDX-License-Identifier: Apache-2.0
* source_revision: {SOURCE_REVISION}
* physical_intent: place one branch beside its consumer; route only A remotely
.subckt cp_inv A Y VDD VSS params: MP=1 MN=1
XP Y A VDD VDD pfet_03v3 w=8u l=0.28u m={{MP}}
XN Y A VSS VSS nfet_03v3 w=8u l=0.28u m={{MN}}
.ends cp_inv

.subckt {top} CLKP_H CLKN_H VDD VSS E_{output} O_DUMMY
{chr(10).join(calls)}
.ends {top}
"""


def compile_lvs_source(kind: str) -> str:
    """Emit the parameter-free aggregate-width view consumed by Netgen."""
    top, stages, output = KINDS[kind]
    devices = []
    source = "CLKP_H"
    for index, mult in enumerate(stages):
        target = f"E_{output}" if index == len(stages) - 1 else f"E_B{index}"
        width = 8 * mult
        devices.extend([
            f"XP_E{index} {target} {source} VDD VDD pfet_03v3 w={width}u l=0.28u",
            f"XN_E{index} {target} {source} VSS VSS nfet_03v3 w={width}u l=0.28u",
        ])
        source = target
    source = "CLKN_H"
    for index in range(len(stages)):
        target = "O_DUMMY" if index == len(stages) - 1 else f"O_DB{index}"
        devices.extend([
            f"XP_OD{index} {target} {source} VDD VDD pfet_03v3 w=8u l=0.28u",
            f"XN_OD{index} {target} {source} VSS VSS nfet_03v3 w=8u l=0.28u",
        ])
        source = target
    return f"""* SPDX-License-Identifier: Apache-2.0
* mechanically lowered LVS view: {SOURCE_REVISION}
.subckt {top} CLKP_H CLKN_H VDD VSS E_{output} O_DUMMY
{chr(10).join(devices)}
.ends {top}
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=KINDS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--flatten-for-lvs", action="store_true")
    args = parser.parse_args()
    args.output.write_text(
        compile_lvs_source(args.kind) if args.flatten_for_lvs
        else compile_source(args.kind))


if __name__ == "__main__":
    main()
