# Pass 10: 8 mA driver with host thresholds and added load

Four fresh native-pad cases hold the top data rate at 312.5 Mb/s/pin and use the programmable `bi_t` 8 mA mode (PDRV1/PDRV0=0/1). Conditions are typical process, 3.3 V, 25 C, fast slew and ideal rails. Alternating and PRBS7 patterns are run at both 8 pF and 10 pF external load per output. The latter is an explicit stress assumption, not a package/PCB characterization.

| Load per output | Alternating pair DVDD average | HOST_A estimate with allowances | HOST_B estimate with allowances | Worst host-threshold margin, two patterns |
|---|---:|---:|---:|---:|
| 8 pF | 12.601 mA | 41.38 mA | 49.25 mA | 0.720 V |
| 10 pF | 13.813 mA | 45.17 mA | 53.80 mA | 0.661 V |

Both bank estimates remain below the unchanged 55 mA planning ceiling. The 10 pF HOST_B estimate leaves only 1.20 mA after the existing provisional allowances. These are still extrapolations from two pads, not measurements of bank current or proven bounds. The native drive label is a library setting, not its measured current at 3.3 V.

The host-threshold analysis uses the [previously sourced Artix boundaries](artix-host-load-screen.md), 0.8/2.0 V, and a 1.65 V clock measurement reference. It checks every saved sample within an assumed ±0.2 ns aperture plus interpolated endpoints. Twenty bits per case are checked; none fail. Two synthetic tests verify rejection of an interior voltage glitch and missing clock edges. Six existing measurement/pin-mapping tests passed in the simulation container; the two new host-analysis tests passed on the host after simulation and are included in subsequent container runs.

This result promotes 8 mA drive to a **candidate for the next physical screen**. It does not freeze the implemented driver, establish FPGA setup/hold, or replace the documented older evidence. The 10 pF load includes no series inductance, transmission-line behavior, ground bounce, inter-output skew or crosstalk. Process spread, voltage/temperature windows, H2D, and real FPGA implementation remain unclosed. A narrow operating envelope still needs measured or simulated numerical bounds; a nominal run is not that envelope.

Reproduce with `verification/run_weak_drive.sh` from this project. The [retained report](../evidence/weak-drive-screen.json) contains exact source, deck, waveform, log and contract hashes. Raw archive: `scratch/transceiver-weak-drive-waveforms.tar.gz`. Wrapper success means characterization completed, not tapeout acceptance.

Next add explicit supply/return and signal-path impedance sensitivity, then a complete switching bank. Choose those model values as documented stress assumptions until actual package geometry is available. Preserve both buses, the full PCIe/RF payload target, 50 terminals and the current planning allowances. The older 5 pF `check_power.py` remains a scoped historical screen; it does not automatically select or qualify this candidate.

Archive SHA-256: `25286e3d54ccaac072239455fe7b7c269ea32eda62c86a61c035fc7ada253400`.
