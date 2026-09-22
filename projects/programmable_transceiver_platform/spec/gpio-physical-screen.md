# GPIO physical feasibility screen, pass 4

## Finding and decision

The 312.5 Mbit/s-per-pin GPIO link is a high-risk physical block, not a free consequence of using parallel pins. Installed GF180 I/O Liberty tables provide candidate output timing, but do not establish a DDR eye, FPGA timing compatibility, simultaneous-switching behavior, or a safe power-pad allocation. Retain the full companion/rate objective and move next to actual output/input path and package characterization.

The current one supply/one ground connection for the host bank is **not closed**. A simple capacitive charging calculation already exceeds a documented supply-cell DC rating for one plausible loading case, without accounting for internal current. This is a pin/power architecture issue that must be resolved before padframe freeze, not hidden by a protocol simulation.

## Reproducible source and scope

Run `make transceiver-gpio-screen`. The wrapper reads the installed `gf180mcuD` I/O libraries from the digest-pinned local digital canary image, without network, host EDA installation, or write access to the repository. The retained [report](../evidence/gpio-liberty-screen.json) records the image ID, extractor SHA-256 and input-library SHA-256 values. Its four candidate corners are TT/25 C/3.30 V, SS/125 C/2.97 V, FF/-40 C/3.63 V, and FF/125 C/3.63 V. The fabrication `process.lock` remains unresolved: this is exploratory source provenance, not foundry/provider acceptance.

The limited parser selects combinational A-to-PAD arcs in `bi_24t` and `bi_t`, retaining every drive/slew condition. It validates ns/pF units and bilinearly interpolates at 0.5 ns input slew and table-load coordinates 5, 10 and 15 pF without extrapolation. Tests independently check nesting, interpolation/endpoints, malformed tables and out-of-range rejection. The report has 120 rows, not a selected nominal-only result.

The load axis begins near the listed pad capacitance (about 3.7 pF for this `bi_24t` model); **table-load coordinate is not yet equated to external load alone**. Establish the characterization convention before using these numbers to approve a board capacitance. The source model, package, PCB and remote FPGA capacitance must be composed without omission or double counting.

## Output timing observations

Candidate `gf180mcu_fd_io__bi_24t`, condition `!IE&OE&!SL`, 0.5 ns core-side input slew:

| Candidate corner | Rise/fall transition at 5 pF table coordinate (ns) | Rise/fall transition at 10 pF coordinate (ns) |
|---|---|---|
| TT/25 C/3.30 V | 0.691 / 0.518 | 0.938 / 0.762 |
| SS/125 C/2.97 V | 1.282 / 0.960 | 1.721 / 1.397 |
| FF/-40 C/3.63 V | 0.426 / 0.318 | 0.579 / 0.478 |
| FF/125 C/3.63 V | 0.688 / 0.495 | 0.927 / 0.743 |

Liberty transition thresholds here are 10–90%. The host bit interval is 3.2 ns. Slow-corner rise time at the 10 pF coordinate consumes roughly 54% of that interval; some weaker or slow-slew settings exceed an entire interval. This screens drive choices but does not predict an eye or set a maximum data rate. At that same slow-corner point, A-to-PAD rise/fall propagation is about 5.784/5.819 ns. Absolute propagation greater than a UI is **not** itself disqualifying for source-synchronous signaling: matching, duty-cycle distortion, phase selection and pattern response matter. Conversely, subtracting transition time from UI is not a setup/hold proof.

Provisional D2H candidate: 24 mA fast-slew pads for data and forwarded clock, with matched loading and placement. Keep the setting a candidate until extracted transient/SSO evidence passes. H2D requires a separately checked FPGA driver and GF180 input-buffer path. Neither a slow bidirectional GPIO assumption nor the strongest drive setting is automatically safe.

## Supply-current sanity check

The [GF180 I/O datasheet](https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/datasheet.html) lists the `bi_24t` 24 mA drive and a 60 mA DC current-carrying capability for each `dvdd`/`dvss` supply cell. Drive strength is not a prediction of average current. Confirm the rating's applicability to the selected pad, metal, bond and supply topology at G0/G4.

For ten data outputs toggling every UI and a 156.25 MHz forwarded clock, each output has 156.25 million rising edges per second. The load-charging component is:

`I = 11 × C_effective × V × 156.25 MHz`.

| Assumed effective switched capacitance per output | At 3.30 V | At 3.63 V |
|---|---:|---:|
| 5 pF | 28.36 mA | 31.20 mA |
| 10 pF | 56.72 mA | 62.39 mA |

These capacitances are explicit **power-analysis assumptions**, separate from the unresolved Liberty load-axis convention. Values exclude internal switching/short-circuit current, input activity, leakage and margin. They are not a complete power estimate. At 3.63 V, the 10 pF case already exceeds 60 mA using load charging alone. Statistical random data may draw less; arbitrary legal/training patterns still need qualification. Peak return current, bond inductance and ground bounce require transient analysis even when average current fits.

## Next concrete closure work

1. Resolve Liberty load conventions against the installed transistor-level pad netlist and characterization documentation. Select actual clock/data output pads and input pads, including core-side loads and 3.3 V domain crossings.
2. Simulate one forwarded-clock/data pair with alternating and PRBS patterns, bounded remote capacitance and package/board parasitics; sweep selected PVT and input slew. Follow with all ten data pins plus clock switching to measure supply and ground disturbances.
3. Select real FPGA GPIO-bank candidates and published setup/hold, input capacitance, output timing and voltage limits. Close both directions and phase-training range. Do not infer LVCMOS feasibility from a vendor's differential/memory-interface maximum rate.
4. Resolve host supply/ground count using actual current/return evidence. Within the same 50-terminal/full-companion requirement, options include lower qualified load, revised pad/rail implementation, or a reviewed signal/power allocation change with transport recalculation. No unstated extra paddle, removed radio function, or permanently reduced PCIe rate.

Provider acceptance, RF/high-speed model validity and package selection remain open independently of this screen. It changes which physical assumption to test next; it does not mark any tapeout gate complete.
