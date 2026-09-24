# Ordinary-GPIO host feasibility

The FPGA-bank frequency screen is a necessary-condition rejection screen, not a compatible-board declaration. ECP5 is the first examined candidate, not the required host family. Preserve the full companion and ordinary-GPIO objective.

## Exclusive-mode reassessment — 2026-09-23

The simultaneous PCIe-plus-RF bandwidth rejection below is historical: the
accepted operating policy requires only one payload engine at a time.
`screen_ecp5_host.py` now reports both the historical sum and the exclusive-mode
budget. With 59 payload slots per 64 ten-bit words and the existing +/-100 ppm
source/host allowances, a hypothetical 150 MHz DDR interface needs 54 slots
for the full 2.5 Gb/s wired lane, leaving five spare payload slots. Each other
required stream also fits independently. The arithmetic minimum DDR clock for
that wired lane is approximately 135.621 MHz.

This reopens a lower-host-clock architecture candidate without reducing the
wired line rate or RF sample formats. It requires actual exclusive slot
reallocation, clock generation, queue/latency analysis and endpoint agreement;
the current executable chip profiles remain 125/156.25 MHz. The existing
documented FPGA frequency screen alone does not qualify board timing, output
loading, jitter or receiver sampling. Do not transfer existing profile results
to the proposed 150 MHz interface or claim a compatible FPGA board from this
bandwidth calculation.

The optional `screen_ecp5_host.py --queues` check also passes each exclusive
stream through 512 frames at four source phases with the conservative host/source
offsets. It uses the current five-header-slot placement and ideal streaming
release after header acceptance. The 2.5 Gb/s case peaks at 540 ingress bits,
1,090 egress bits and 1,070 staging bits, within the planning allocations; these
are not implemented RTL FIFO depths. A 53-slot negative control overflows ingress,
while the proposed 54-slot service passes. Header decoding, CDC, host pauses,
mode changes, actual clock generation and latency acceptance remain open.

For this ideal fixed-rate queue model, the checker also derives conservative
duration-independent bounds. In host-word time, let `F=64`, sample width `s`,
source bit rate `r`, allocated service `R=10*q/F`, and arrival burst allowance
`b=s+9`. A frame-boundary snapshot server supplies rate R with at most one frame
of latency. The following-frame staging/emission adds at most two frames;
finishing a partial ten-bit word can wait one sample period because s is at
least ten bits. Thus delivery delay is bounded by `3*F + b/R + s/r` when R>=r.
Ingress is bounded by `b+r*F`, and the two staging banks by `20*q` bits.

With producer and consumer at the same constant cadence and consumer start
delayed S=256 host words, the delivery bound below S prevents starvation after
startup. Delivery cannot precede one frame of staging, giving the conservative
egress bound `r*(S-F)+2*s+10`, including packet/word rounding allowances.
Across the four streams, delivery bounds are below 230 host words. The largest
ingress/egress/staging bounds are 553/1,631/1,080 bits, within the planning
allocations. The finite tests also check their observed peaks against these
bounds. These arguments address indefinite operation only under the stated
constant, matched-rate and uninterrupted-service assumptions. They do not bound
independent sink drift, host stalls, extra CDC latency, acquisition or transitions.

## Primary evidence

[Lattice ECP5 family datasheet](https://www.latticesemi.com/view_document?document_id=50461), FPGA-DS-02012-3.4 (September 2025), Table 3.21, printed pages 65–66: LVCMOS33 input/output clock ceilings are 200/150 MHz. DDR transfers twice per clock. These speeds are characterized, not tested on every device; fast slew is used. Table 3.44 uses a 0 pF fixture load for LVCMOS timing, so the stated frequency is not proof at our board load. Source PDF SHA-256 is retained in the report.

## Design consequences and independent arithmetic

The 156.25 MHz top profile exceeds the documented H2D output-clock ceiling. D2H is below the input ceiling, but neither direction has board timing closure. The 125 MHz profile passes this frequency-only screen. A faster FPGA internal clock specification does not override its pad limit. The accepted narrow operating envelope does not establish undocumented host speed.

Even a hypothetical 150 MHz DDR profile cannot preserve PCIe plus the declared RF stream: useful nominal bandwidth is 2.765625 Gb/s per direction versus 2.82 Gb/s demand. With the contract's provisional clock offsets and whole-slot reservations, wire needs 54 slots and I/Q needs 7, exceeding the 59 available. Neither tighter voltage/temperature nor removing clock-offset allowance fixes that nominal bandwidth deficit. No lower-rate substitute has been inserted into the contract.

Reproduce the [retained report](../evidence/ecp5-host-screen.json):

```sh
python3 projects/programmable_transceiver_platform/verification/screen_ecp5_host.py
```

The script reads the current contract and records its hash. It does not download or parse the PDF; the documented limits are manually transcribed evidence. Every profile remains explicitly unqualified.

## Native GF180 GPIO evidence

The pass-4 and pass-5 results below retain their original load and operating
assumptions. Their single-host-supply allocation and drive choice are historical:
[power partition](power-partition.md) owns the revised supply allocation, and
[host-driver selection](host-driver-selection.md) owns subsequent driver/load
comparisons. Neither screen qualifies a complete board link. The closure work
for both native pads and the external FPGA is collected at the end of this guide.

### Liberty timing and charging-current screen, pass 4

#### Finding and decision

The 312.5 Mbit/s-per-pin GPIO link is a high-risk physical block, not a free consequence of using parallel pins. Installed GF180 I/O Liberty tables provide candidate output timing, but do not establish a DDR eye, FPGA timing compatibility, simultaneous-switching behavior, or a safe power-pad allocation. Retain the full companion/rate objective and move next to actual output/input path and package characterization.

The original one supply/one ground connection for the host bank is **not closed**. A simple capacitive charging calculation already exceeds a documented supply-cell DC rating for one plausible loading case, without accounting for internal current. This is a pin/power architecture issue that must be resolved before padframe freeze, not hidden by a protocol simulation.

#### Reproducible source and scope

Run `make transceiver-gpio-screen`. The wrapper reads the installed `gf180mcuD` I/O libraries from the digest-pinned local digital canary image, without network, host EDA installation, or write access to the repository. The retained [report](../evidence/gpio-liberty-screen.json) records the image ID, extractor SHA-256 and input-library SHA-256 values. Its four candidate corners are TT/25 C/3.30 V, SS/125 C/2.97 V, FF/-40 C/3.63 V, and FF/125 C/3.63 V. The fabrication `process.lock` remains unresolved: this is exploratory source provenance, not foundry/provider acceptance.

The limited parser selects combinational A-to-PAD arcs in `bi_24t` and `bi_t`, retaining every drive/slew condition. It validates ns/pF units and bilinearly interpolates at 0.5 ns input slew and table-load coordinates 5, 10 and 15 pF without extrapolation. Tests independently check nesting, interpolation/endpoints, malformed tables and out-of-range rejection. The report has 120 rows, not a selected nominal-only result.

The load axis begins near the listed pad capacitance (about 3.7 pF for this `bi_24t` model); **table-load coordinate is not yet equated to external load alone**. Establish the characterization convention before using these numbers to approve a board capacitance. The source model, package, PCB and remote FPGA capacitance must be composed without omission or double counting.

#### Output timing observations

Candidate `gf180mcu_fd_io__bi_24t`, condition `!IE&OE&!SL`, 0.5 ns core-side input slew:

| Candidate corner | Rise/fall transition at 5 pF table coordinate (ns) | Rise/fall transition at 10 pF coordinate (ns) |
|---|---|---|
| TT/25 C/3.30 V | 0.691 / 0.518 | 0.938 / 0.762 |
| SS/125 C/2.97 V | 1.282 / 0.960 | 1.721 / 1.397 |
| FF/-40 C/3.63 V | 0.426 / 0.318 | 0.579 / 0.478 |
| FF/125 C/3.63 V | 0.688 / 0.495 | 0.927 / 0.743 |

Liberty transition thresholds here are 10–90%. The host bit interval is 3.2 ns. Slow-corner rise time at the 10 pF coordinate consumes roughly 54% of that interval; some weaker or slow-slew settings exceed an entire interval. This screens drive choices but does not predict an eye or set a maximum data rate. At that same slow-corner point, A-to-PAD rise/fall propagation is about 5.784/5.819 ns. Absolute propagation greater than a UI is **not** itself disqualifying for source-synchronous signaling: matching, duty-cycle distortion, phase selection and pattern response matter. Conversely, subtracting transition time from UI is not a setup/hold proof.

Provisional D2H candidate: 24 mA fast-slew pads for data and forwarded clock, with matched loading and placement. Keep the setting a candidate until extracted transient/SSO evidence passes. H2D requires a separately checked FPGA driver and GF180 input-buffer path. Neither a slow bidirectional GPIO assumption nor the strongest drive setting is automatically safe.

#### Supply-current sanity check

The [GF180 I/O datasheet](https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/datasheet.html) lists the `bi_24t` 24 mA drive and a 60 mA DC current-carrying capability for each `dvdd`/`dvss` supply cell. Drive strength is not a prediction of average current. Confirm the rating's applicability to the selected pad, metal, bond and supply topology at G0/G4.

For ten data outputs toggling every UI and a 156.25 MHz forwarded clock, each output has 156.25 million rising edges per second. The load-charging component is:

`I = 11 × C_effective × V × 156.25 MHz`.

| Assumed effective switched capacitance per output | At 3.30 V | At 3.63 V |
|---|---:|---:|
| 5 pF | 28.36 mA | 31.20 mA |
| 10 pF | 56.72 mA | 62.39 mA |

These capacitances are explicit **power-analysis assumptions**, separate from the unresolved Liberty load-axis convention. Values exclude internal switching/short-circuit current, input activity, leakage and margin. They are not a complete power estimate. At 3.63 V, the 10 pF case already exceeds 60 mA using load charging alone. Statistical random data may draw less; arbitrary legal/training patterns still need qualification. Peak return current, bond inductance and ground bounce require transient analysis even when average current fits.

### Native GPIO pair transient screen, pass 5

#### Scope and reproducibility

`make transceiver-gpio-transient` runs the installed transistor-level `gf180mcu_fd_io__bi_24t` data/clock pair through the existing bounded analog container harness. Four cases cover TT/3.30 V/25 C and SS/2.97 V/125 C, alternating and PRBS7 stimuli, and **5 pF explicit external lumped capacitance per output**. No pad model geometry or bin limits are edited. Passive diode/MOSCAP corners remain typical; resistor corners track the selected MOS corner. This is not complete passive/PVT closure.

The [retained report](../evidence/gpio-transient-screen.json) records the exact simulator, pinned image, input-model hashes, simulator initialization, deck hashes, waveform hashes and analysis source hash. The first successful waveforms were reanalyzed after correcting the crossing extractor; the report explicitly identifies reanalysis, with exact deck and initialization checks. The initial simulator launch failure and analysis errors are not claimed as successful runs.

Raw decks, initialization, logs and waveforms are retained outside Git in `scratch/transceiver-gpio-pass5-waveforms.tar.gz`, SHA-256 `d76bd823ee2e502b6c5f0625a3c8b44d283480092d35a5d75ad0561fd00f3613`. They must become an immutable release artifact before any externally reproduced claim depends on them. The fresh-run Make target regenerates the experiment; it does not require that local archive. Replay is available through `run_gpio_transient.py --replay` with saved case directories mounted at `/work`, matching their generated deck paths.

#### Simulator setup correction

The native pad includes 120 µm-wide, two-finger PMOS devices. Default ngspice bin selection rejected the 120 µm total width against a 100.01 µm model-bin upper limit. The [ngspice manual](https://ngspice.sourceforge.io/docs/ngspice-42-manual.pdf), sections 16.14.9–10, documents width-per-finger binning in Spectre/HSPICE compatibility mode. Each case therefore explicitly supplies `.spiceinit` containing `set ngbehavior=hs`: bin selection sees 60 µm per finger. The device and model remain unchanged. This is simulator compatibility, not a waiver to widen model validity.

The `ff`/`ss` wrapper sections use 6 V nominal model definitions with corner-dependent parameters; selecting a definition named `_t` internally is not evidence that those wrappers ignore corners. Inspect both definitions and wrapper parameter assignments when auditing the PDK.

#### Measured assumptions and results

Core-side drive is ideal with 0.5 ns edges. Host data UI is 3.2 ns; the forwarded clock is shifted by 1.6 ns at its source. Supplies are ideal. Both outputs use the same pad, load and slew control (`IE=0`, `OE=1`, `SL=0`). The analyzer pairs ordered input/output clock edges and samples the expected data at the received-clock crossing and ±0.2 ns. Assumed receiver thresholds are 0.3/0.7 of supply. These are explicit test assumptions, not a selected FPGA's guaranteed specifications.

The bounded first matrix drives 32 data bits per case and checks 20 bits after startup/before drain. This is a functionality screen, not BER evidence. It neither selects a best latency nor searches for a passing sample phase.

| Case | Worst sampled voltage margin | Threshold failures | Two-pad I/O supply average | Two-pad core supply average |
|---|---:|---:|---:|---:|
| TT alternating | 0.988 V | 0/20 | 13.272 mA | 0.0288 mA |
| TT PRBS7 | 0.988 V | 0/20 | 9.299 mA | 0.0201 mA |
| SS alternating | 0.858 V | 0/20 | 11.751 mA | 0.0262 mA |
| SS PRBS7 | 0.836 V | 0/20 | 8.419 mA | 0.0183 mA |

Clock propagation spans about 2.506–2.545 ns at TT and 4.525–4.725 ns at SS. Matched source-synchronous timing can therefore work in this narrow ideal model despite absolute pad delay exceeding a UI. This is not a full eye-width measurement, and the full bus is not qualified by the two-pad result.

Measurement regression tests cover crossings exactly on thresholds, interpolated crossings, no crossings and nonconstant stimuli. The first extractor missed exact-threshold crossings; that bug is fixed and the stored report uses the corrected extractor. The finite sample count is checked explicitly so an empty measurement cannot pass.

#### Architectural consequence: host-bank power

For identical alternating activity, scaling the two-pad I/O current by 11/2 estimates **73.00 mA at TT and 64.63 mA at SS** for ten data outputs plus forwarded clock, even with only 5 pF external load. This is a linear ideal-supply estimate, not an eleven-pad simultaneous-switching simulation. It excludes input-bank activity and any additional bank circuitry.

The [I/O library datasheet](https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/datasheet.html) lists 60 mA DC capability for a supply pad. The original one-host-supply/one-host-ground allocation is therefore rejected as an established solution for this load/activity case. The total 50-terminal/full-companion constraint remains. Next consider at least two physical host supply/return paths, reallocating the existing domain budget only after checking the other domains, or qualify a lower-current output implementation/loading. Do not silently trade away required payload bandwidth or RF capability.

## Current closure work

1. Reconcile Liberty load coordinates with native transistor-pad and characterization
   conventions; compose pad, package, board and FPGA capacitance without omission
   or double counting. Select actual input/output pads, core-side loads and domain
   crossings; retain selected PVT/passive-corner and simulator-compatibility limits.
2. Select a documented FPGA device/package/speed grade, bank supply, forwarded-clock
   pins and DDR resources. Close both directions using receiver thresholds, driver
   behavior, skew, jitter, input slew, phase-training range and placed host timing.
   Compare alternating and PRBS clock/data pairs, then all ten data pins plus clock,
   with package/bond/PCB impedance, mismatch and simultaneous-switching effects.
3. Resolve supply/return allocation from actual current and return-path evidence,
   including pre-driver, input-bank and internal switching consumption. Confirm
   the selected supply-cell rating applies to its metal, bond and operating envelope.
   The [power owner](power-partition.md) keeps the revised allocation and its open
   limits; pair-current scaling and ideal supply models are insufficient for freeze.
4. Reassess the hypothetical 150 MHz exclusive profile against the same electrical,
   clock-generation, slot/queue and latency checks. Preserve the 50-terminal/full-
   companion requirement and every required wired/RF rate in its selected mode;
   simultaneous RF/wired payload is not required. Do not assume an extra paddle,
   remove the radio, reduce the required PCIe rate, or substitute FPGA serial
   transceivers for the ordinary-GPIO objective.

These screens do not close RF, SerDes, protocol latency, resource sharing or
whole-chip layout. Provider acceptance, unresolved process provenance and model
validity remain separate from the limited numerical evidence above.
