# Host output loading and driver selection

The 8 mA native driver is a candidate under nominal lumped-load assumptions;
no driver or FPGA board is physically qualified. This document owns load and
drive comparisons. [FPGA screening](fpga-host-screen.md) owns frequency constraints;
[power partition](power-partition.md) owns the common-ring supply architecture.
RF and wired payloads are exclusive; preserve each selected engine's full rate.

## Artix load baseline

[AMD DS181](https://docs.amd.com/v/u/en-US/ds181_Artix_7_Data_Sheet), v1.27.1, July 3 2024: Table 3 specifies up to 8 pF die input capacitance, excluding package. Table 8 gives LVCMOS33 low/high input boundaries of 0.8/2.0 V. Table 19 uses a 1.65 V input timing reference. Table 21's -1 input-logic setup/hold values are internal-pin values, not a board interface timing guarantee. Published LVDS throughput does not establish LVCMOS throughput. Source PDF SHA-256 is retained in the report.

The die capacitance excludes package and PCB loading. Compose these at explicit
reference planes; do not equate an 8 pF ideal capacitor with a complete host link.
No specific FPGA package or placed DDR implementation is qualified.

## Native driver evidence

The scoped transistor checks use 312.5 Mb/s per pin, typical process, 3.3 V,
25 °C, alternating/PRBS7 patterns and ideal driver/core supplies. They check only
20 bits per case. The ±0.2 ns observation aperture is assumed, not demonstrated
FPGA setup/hold. Positive voltage margins do not establish clock skew, SSO or PVT.

| Drive / load | Alternating data-and-clock pair average current | Minimum Artix-threshold margin | Evidence |
| --- | --- | --- | --- |
| 24 mA / 8 pF | 16.409 mA | 0.799 V | [Artix load](../evidence/artix-load-screen.json) |
| 8 mA / 8 pF | 12.601 mA | 0.720 V | [Weak drive](../evidence/weak-drive-screen.json) |
| 8 mA / 10 pF | 13.813 mA | 0.661 V | [Weak drive](../evidence/weak-drive-screen.json) |

[Drive-strength characterization](../evidence/drive-strength-screen.json) also
compares 12/16 mA settings using generic 0.3/0.7 VDD thresholds. Those margins
are not interchangeable with the Artix thresholds. Pair-current extrapolation
cannot qualify current distribution through the common supply/return ring.

With 8 mA drive, 10 pF load and 1 Ω signal resistance, assumed data/clock
inductances of 1/1 and 2/1 nH give 0.665/0.674 V margins in the
[signal-path screen](../evidence/signal-path-screen.json). The clock-edge intervals
span 3.002–3.331 ns. These are short ideal-rail sensitivity cases, not package
bounds; better margin at one inductance does not imply monotonic improvement.
Overshoot observations do not establish reliability acceptance.

## Supply-path boundary

[GF180 I/O cell list](https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/datasheet.html) assigns 60 mA DC capacity to each native supply/ground cell. This is not a package-terminal rating. The [supply-pad description](https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/power.html) describes ESD circuits; it does not qualify a higher-current custom feed. The installed supply SPICE exposes rail nodes without a separate external bond node, so that schematic alone cannot prove feed-metal or bond capacity.

Do not assume that paralleling clamps, using a stronger bond wire, or narrowing temperature automatically increases native-cell current capacity. A custom supply path remains possible but needs physical metal/via, ESD and package evidence. Keep the present terminal allocation while investigating current at its source.

The [supply-path failure report](../evidence/supply-path-incomplete.json) records
six incomplete transistor runs with shared output supply/return impedance.
Assumptions were 0.1 Ω/1 nH or 0.25 Ω/2 nH per rail; core rails and remote load
ground remained ideal. Four default-integration runs timed out before stimulus,
and two Gear-2 runs also produced no final waveform. No electrical pass or fail
can be inferred from those numerical failures.

The next useful simulation must resolve DC/startup and numerical convergence on
a tractable supply/return circuit, then compose the complete selected ring, bank
activity and remote receiver. Extending runtime alone does not close this gap.

## Reproduction and acceptance

The bounded wrappers `verification/run_artix_load.sh`, `run_drive_strength.sh`,
`run_weak_drive.sh`, `run_signal_path.sh` and `run_supply_path.sh` retain their
scoped conditions. Reports record exact decks, libraries and waveform hashes.
Successful characterization execution is distinct from design acceptance.

Before selecting the physical driver, establish both H2D and D2H margins with
actual host thresholds/IBIS or transistor models, package/PCB impedance, matching,
simultaneous switching, current distribution, rail bounce and the agreed narrow
voltage/temperature window. Use the current pad map and power owner for budgets.
