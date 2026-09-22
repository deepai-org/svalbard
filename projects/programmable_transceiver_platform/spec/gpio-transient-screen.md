# Native GPIO pair transient screen, pass 5

## Scope and reproducibility

`make transceiver-gpio-transient` runs the installed transistor-level `gf180mcu_fd_io__bi_24t` data/clock pair through the existing bounded analog container harness. Four cases cover TT/3.30 V/25 C and SS/2.97 V/125 C, alternating and PRBS7 stimuli, and **5 pF explicit external lumped capacitance per output**. No pad model geometry or bin limits are edited. Passive diode/MOSCAP corners remain typical; resistor corners track the selected MOS corner. This is not complete passive/PVT closure.

The [retained report](../evidence/gpio-transient-screen.json) records the exact simulator, pinned image, input-model hashes, simulator initialization, deck hashes, waveform hashes and analysis source hash. The first successful waveforms were reanalyzed after correcting the crossing extractor; the report explicitly identifies reanalysis, with exact deck and initialization checks. The initial simulator launch failure and analysis errors are not claimed as successful runs.

Raw decks, initialization, logs and waveforms are retained outside Git in `scratch/transceiver-gpio-pass5-waveforms.tar.gz`, SHA-256 `d76bd823ee2e502b6c5f0625a3c8b44d283480092d35a5d75ad0561fd00f3613`. They must become an immutable release artifact before any externally reproduced claim depends on them. The fresh-run Make target regenerates the experiment; it does not require that local archive. Replay is available through `run_gpio_transient.py --replay` with saved case directories mounted at `/work`, matching their generated deck paths.

## Simulator setup correction

The native pad includes 120 µm-wide, two-finger PMOS devices. Default ngspice bin selection rejected the 120 µm total width against a 100.01 µm model-bin upper limit. The [ngspice manual](https://ngspice.sourceforge.io/docs/ngspice-42-manual.pdf), sections 16.14.9–10, documents width-per-finger binning in Spectre/HSPICE compatibility mode. Each case therefore explicitly supplies `.spiceinit` containing `set ngbehavior=hs`: bin selection sees 60 µm per finger. The device and model remain unchanged. This is simulator compatibility, not a waiver to widen model validity.

The `ff`/`ss` wrapper sections use 6 V nominal model definitions with corner-dependent parameters; selecting a definition named `_t` internally is not evidence that those wrappers ignore corners. Inspect both definitions and wrapper parameter assignments when auditing the PDK.

## Measured assumptions and results

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

## Architectural consequence: host-bank power

For identical alternating activity, scaling the two-pad I/O current by 11/2 estimates **73.00 mA at TT and 64.63 mA at SS** for ten data outputs plus forwarded clock, even with only 5 pF external load. This is a linear ideal-supply estimate, not an eleven-pad simultaneous-switching simulation. It excludes input-bank activity and any additional bank circuitry.

The [I/O library datasheet](https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/datasheet.html) lists 60 mA DC capability for a supply pad. The original one-host-supply/one-host-ground allocation is therefore rejected as an established solution for this load/activity case. The total 50-terminal/full-companion constraint remains. Next consider at least two physical host supply/return paths, reallocating the existing domain budget only after checking the other domains, or qualify a lower-current output implementation/loading. Do not silently trade away required payload bandwidth or RF capability.

## Remaining work

The 5 pF external-load transient result is not yet reconciled with Liberty load coordinates; process characterization and parasitic differences may also contribute. Add actual package/bond/PCB impedance, receiver loading/thresholds, core-driver loading, mismatch, jitter and all-output switching. Close H2D independently. Choose real FPGA-bank candidates and derive timing/voltage/SSO limits. Re-run the power allocation with concrete rail-current and return-path evidence. RF, SerDes, protocol latency, resource sharing and whole-chip layout remain separate unresolved gates.
