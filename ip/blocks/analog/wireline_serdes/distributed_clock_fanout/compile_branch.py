#!/usr/bin/env python3
"""Lower independently placeable final clock-fanout branch macros."""

from __future__ import annotations

import argparse
from pathlib import Path


KINDS = {
    "sampler": ("distributed_sampler_pair", (6, 16, 32), "SENSE"),
    "capture": ("distributed_capture_pair", (4, 8), "CAPTURE_CLK"),
}
SOURCE_REVISION = "distributed_v1_preserve_v7_branch_ratios"


def compile_source(kind: str) -> str:
    top, stages, output = KINDS[kind]
    calls = []
    for phase, clock in (("E", "CLKP_H"), ("O", "CLKN_H")):
        source = clock
        for index, mult in enumerate(stages):
            target = f"{phase}_{output}" if index == len(stages) - 1 else f"{phase}_B{index}"
            # The explicit hierarchy token preserves the functional-root name
            # expected by the physical placer without a parameterized wrapper
            # that LVS would flatten with default device multiplicities.
            calls.append(
                f"X{phase}S__XI{index} {source} {target} VDD VSS cp_inv "
                f"MP={mult} MN={mult}")
            source = target
    return f"""* SPDX-License-Identifier: Apache-2.0
* source_revision: {SOURCE_REVISION}
* physical_intent: place one branch beside its consumer; route only A remotely
.subckt cp_inv A Y VDD VSS params: MP=1 MN=1
XP Y A VDD VDD pfet_03v3 w=8u l=0.28u m={{MP}}
XN Y A VSS VSS nfet_03v3 w=8u l=0.28u m={{MN}}
.ends cp_inv

.subckt {top} CLKP_H CLKN_H VDD VSS E_{output} O_{output}
{chr(10).join(calls)}
.ends {top}
"""


def compile_lvs_source(kind: str) -> str:
    """Emit the parameter-free aggregate-width view consumed by Netgen."""
    top, stages, output = KINDS[kind]
    devices = []
    for phase, clock in (("E", "CLKP_H"), ("O", "CLKN_H")):
        source = clock
        for index, mult in enumerate(stages):
            target = f"{phase}_{output}" if index == len(stages) - 1 else f"{phase}_B{index}"
            width = 8 * mult
            devices.extend([
                f"XP_{phase}{index} {target} {source} VDD VDD pfet_03v3 w={width}u l=0.28u",
                f"XN_{phase}{index} {target} {source} VSS VSS nfet_03v3 w={width}u l=0.28u",
            ])
            source = target
    return f"""* SPDX-License-Identifier: Apache-2.0
* mechanically lowered LVS view: {SOURCE_REVISION}
.subckt {top} CLKP_H CLKN_H VDD VSS E_{output} O_{output}
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
