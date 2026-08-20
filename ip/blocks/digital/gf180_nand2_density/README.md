# GF180 NAND2 density and FO1 speed study

This experiment compares a compact custom 3.3 V NAND2 against
`gf180mcu_fd_sc_mcu7t5v0__nand2_1`, the default 7-track library cell.  The
load requirement is exactly one gate input.  The timing fixture is a chain of
three identical, full-RC-extracted NAND2 cells; the middle stage is measured,
so it sees both an extracted predecessor and one extracted input load.

## Result

| cell | footprint | relative area | nominal worst FO1 delay | PVT worst delay |
|---|---:|---:|---:|---:|
| compact 3.3 V | 1.96 x 2.75 um = 5.390 um2 | 49.1% | 131.02 ps | 209.90 ps |
| fast 3.3 V, constrained below default area | 1.96 x 5.06 um = 9.918 um2 | 90.4% | 87.93 ps | 143.43 ps |
| default 7-track | 2.80 x 3.92 um = 10.976 um2 | 100% | 223.50 ps | 428.65 ps |

The compact point is 50.9% smaller and 41.4% faster at nominal conditions
than the default in this fixture.  The speed-biased point is 9.6% smaller and
60.7% faster.  The custom cells use minimum-length 3.3 V devices; the default
cell uses longer 5 V devices, so the result is a comparison of available cell
implementations at 3.3 V, not merely a layout-efficiency comparison.

All three final layouts report zero Magic DRC errors, a unique Netgen LVS
match, and full-RC extraction.  Timing covers both controlling-input arcs at:

- typical devices/resistors, 3.30 V, 25 C;
- fast devices/resistors, 3.63 V, -40 C;
- slow devices/resistors, 2.97 V, 125 C.

The 23-point extracted physical sweep includes NMOS widths from 0.42 to 4.20
um and PMOS:NMOS ratios from 1.5 through 2.5.  Delay continues toward an
asymptote when every stage is enlarged.  Therefore an unconstrained
"absolute fastest FO1 gate" is not a useful finite objective: it consumes
ever more area for diminishing improvement.  The reported fast point is the
fastest swept point whose footprint remains below the default cell area.

## Scope of the minimum claim

The 5.390 um2 point is the smallest zero-DRC candidate found in the searched
domain: four-transistor static CMOS, minimum-length 3.3 V PDK PCells, shared
source/drain diffusion, and physically accessible A1, A2, ZN, VDD, and VSS
connections.  The PDK permits 0.22 um channel width, but reducing both widths
below 0.42 um in this contacted topology does not reduce the wiring/contact
floor and produced DRC violations in the boundary sweep (18 errors at 0.30
um, falling to zero at 0.42 um).  This is strong evidence for this topology,
not a mathematical global proof over every possible hand-drawn diffusion
shape.

The compact cells are research macros, not drop-in standard cells yet.  They
need a row-compatible site/rail contract, abutment DRC, tap and fill strategy,
antenna review, LEF obstruction/access validation, and Liberty
characterization before use in automated place and route.  The default cell
already supplies that integration work.

## Reproduce

Run `./run.sh`.  It uses the repository's pinned, network-disabled analog
container with four CPUs and 6 GiB RAM.  The flow regenerates the layouts,
runs DRC/LVS/PEX, performs the extracted physical sweep and PVT FO1 timing,
renders the comparison image, and emits hash-bound JSON evidence.

Key files:

- `layout.tcl`: parameterized custom layout generator;
- `screen_physical.py`: DRC/LVS/PEX size sweep and nominal FO1 timing;
- `characterize.py`: final exact-PEX PVT comparison;
- `result-last.json`: verification summary;
- `layout-comparison.png`: rendered layout comparison.
