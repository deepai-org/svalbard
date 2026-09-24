# Host output loading and driver selection

The 8 mA native driver is a candidate under nominal lumped-load assumptions;
no driver or FPGA board is physically qualified. This document owns the load
and drive-strength comparisons. [FPGA host screening](fpga-host-screen.md)
owns device frequency and bandwidth constraints; [power partitioning](power-partition.md)
owns the bank allocation. RF and wired payloads are exclusive, so preserve the
full rate of each selected mode without requiring concurrent RF/wired payload.

## Artix load baseline

## Primary evidence

[AMD DS181](https://docs.amd.com/v/u/en-US/ds181_Artix_7_Data_Sheet), v1.27.1, July 3 2024: Table 3 specifies up to 8 pF die input capacitance, excluding package. Table 8 gives LVCMOS33 low/high input boundaries of 0.8/2.0 V. Table 19 uses a 1.65 V input timing reference. Table 21's -1 input-logic setup/hold values are internal-pin values, not a board interface timing guarantee. Published LVDS throughput does not establish LVCMOS throughput. Source PDF SHA-256 is retained in the report.

### Fresh native-pad evidence

Run `verification/run_artix_load.sh` from this project or its absolute path. It uses the repository's bounded, pinned analog container and the unchanged native pad deck generator. Two fresh nominal 3.3 V, 25 C cases use 8 pF external lumped loading per data/clock output, alternating and PRBS7 patterns. Four existing measurement regressions passed first.

The [raw result summary](../evidence/artix-load-screen.json) records deck, waveform and log hashes. The minimum host-threshold margin across 20 bits per case is 0.799 V in the assumed ±0.2 ns aperture. This analysis includes all saved interior samples plus interpolated aperture boundaries. Clock edges are paired in order; no phase search selects a passing result. The 1.65 V reference is a measurement convention, not proof of the actual receiver's switching point. No claim of Artix timing closure follows.

The alternating pair draws 16.409 mA average from DVDD. Applying the existing per-output extrapolation and allowances produces 53.28 mA for HOST_A and **63.54 mA for HOST_B**, exceeding HOST_B's 55 mA planning ceiling. See the [power screen](../evidence/artix-load-power-screen.json). The measured extrapolation before allowances is 49.23 mA for HOST_B; the result rejects the present planning margin, not a direct measurement of a six-pad bank exceeding its supply-cell rating.

The original 5 pF result remains valid only for its load. Its passing power check does not close this 8 pF case. Package and board loading are still absent, and 8 pF is not a complete host load model. Narrow temperature/voltage operation does not remove that load or the associated power demand.

### Execution provenance and next decision

Both simulations completed and waveforms were archived. The initial harness invocation then reported failure because it expected a signoff-style `result` field absent from this characterization JSON. Requested outputs were preserved; the reproducible wrapper now treats simulation completion separately from design acceptance. No rerun is claimed. The raw archive is `scratch/transceiver-artix-load-waveforms.tar.gz`; its SHA-256 is retained in the power report.

Artix-7 remains an unqualified candidate, with no chosen package or completed DDR implementation. Next investigate host-bank power/driver options at realistic loading without changing the 50-terminal or full-rate targets. A third supply pair, lower-capacitance host, driver redesign or another electrical interface must earn its own area/power/timing evidence; merely reducing an allowance to turn the check green is not closure. Host timing, H2D behavior and protocol latency remain open in parallel with this physical issue.

## 12 and 16 mA alternatives

## Supply-path audit

The [GF180 I/O cell list](https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/datasheet.html) assigns 60 mA DC capacity to each native supply/ground cell. This is not a package-terminal rating. The [supply-pad description](https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/power.html) describes ESD circuits; it does not qualify a higher-current custom feed. The installed supply SPICE exposes rail nodes without a separate external bond node, so that schematic alone cannot prove feed-metal or bond capacity.

Do not assume that paralleling clamps, using a stronger bond wire, or narrowing temperature automatically increases native-cell current capacity. A custom supply path remains possible but needs physical metal/via, ESD and package evidence. Keep the present terminal allocation while investigating current at its source.

### Native driver comparison

The [programmable driver controls](https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/digital.html) select 12 mA with PDRV1/PDRV0=1/0 and 16 mA with 1/1. The native `bi_t` netlist includes these pins, unlike `bi_24t`. The runner now accepts a drive selection; its default 24 mA instance text remains unchanged. Six measurement/pin-mapping tests passed inside the pinned analog image.

Four fresh transistor simulations compare 12/16 mA settings using alternating and PRBS7 patterns. Conditions remain 312.5 Mb/s/pin, 8 pF per output, 3.3 V, 25 C, typical process, ideal supplies. All four cases check 20 bits at the same assumed three-point ±0.2 ns aperture and 0.3/0.7 VDD thresholds. These are generic screens, not the host-specific threshold analysis from pass 8.

| Native drive setting | Alternating pair DVDD average | Worst sampled margin across two patterns | HOST_B current with unchanged allowances |
|---|---:|---:|---:|
| 24 mA, pass 8 baseline | 16.409 mA | 0.983 V | 63.54 mA |
| 16 mA | 15.551 mA | 0.968 V | 60.32 mA |
| 12 mA | 14.334 mA | 0.916 V | 55.75 mA |

The smaller drivers reduce modeled current while retaining positive sampled margin. **Neither tested replacement meets the 55 mA HOST_B planning ceiling with existing allowances.** The 12 mA result is close but still fails; no allowance or ceiling was relaxed. No driver is selected for implementation yet.

The drive labels are library modes, not constant-current sources or guaranteed currents at this operating voltage. Absolute clock delay also changes; common delay cancellation in this matched pair does not establish skew or FPGA timing.

### Reproduction and next step

Run `verification/run_drive_strength.sh` from this project. The [report](../evidence/drive-strength-screen.json) records source/deck/waveform/log hashes and current calculations tied to the unchanged contract. Raw waveforms are retained in `scratch/transceiver-drive-strength-waveforms.tar.gz`. The wrapper's PASS means bounded characterization completed, not that the candidate meets the chip requirements.

The 8 mA screen below extends this comparison to weaker drive and host thresholds. Package/rail impedance and concurrent-bank switching still need qualification before selection. Keep 50 terminals, both 10-bit buses and the full rate of each selected RF or wired mode. No reduction in data rate, payload or functionality was used to improve the current result. Actual host timing, process variation and the numerical narrow operating envelope remain unclosed.

Waveform archive SHA-256: `6668274a18c3a37f987e8e79b91e3499c341f63062b74c4d28086284257453f5`.

## 8 mA candidate

Four fresh native-pad cases hold the top data rate at 312.5 Mb/s/pin and use the programmable `bi_t` 8 mA mode (PDRV1/PDRV0=0/1). Conditions are typical process, 3.3 V, 25 C, fast slew and ideal rails. Alternating and PRBS7 patterns are run at both 8 pF and 10 pF external load per output. The latter is an explicit stress assumption, not a package/PCB characterization.

| Load per output | Alternating pair DVDD average | HOST_A estimate with allowances | HOST_B estimate with allowances | Worst host-threshold margin, two patterns |
|---|---:|---:|---:|---:|
| 8 pF | 12.601 mA | 41.38 mA | 49.25 mA | 0.720 V |
| 10 pF | 13.813 mA | 45.17 mA | 53.80 mA | 0.661 V |

Both bank estimates remain below the unchanged 55 mA planning ceiling. The 10 pF HOST_B estimate leaves only 1.20 mA after the existing provisional allowances. These are still extrapolations from two pads, not measurements of bank current or proven bounds. The native drive label is a library setting, not its measured current at 3.3 V.

The host-threshold analysis uses the [previously sourced Artix boundaries](#artix-load-baseline), 0.8/2.0 V, and a 1.65 V clock measurement reference. It checks every saved sample within an assumed ±0.2 ns aperture plus interpolated endpoints. Twenty bits per case are checked; none fail. Two synthetic tests verify rejection of an interior voltage glitch and missing clock edges. Six existing measurement/pin-mapping tests passed in the simulation container; the two new host-analysis tests passed on the host after simulation and are included in subsequent container runs.

This result promotes 8 mA drive to a **candidate for the next physical screen**. It does not freeze the implemented driver, establish FPGA setup/hold, or replace the documented older evidence. The 10 pF load includes no series inductance, transmission-line behavior, ground bounce, inter-output skew or crosstalk. Process spread, voltage/temperature windows, H2D, and real FPGA implementation remain unclosed. A narrow operating envelope still needs measured or simulated numerical bounds; a nominal run is not that envelope.

Reproduce with `verification/run_weak_drive.sh` from this project. The [retained report](../evidence/weak-drive-screen.json) contains exact source, deck, waveform, log and contract hashes. Raw archive: `scratch/transceiver-weak-drive-waveforms.tar.gz`. Wrapper success means characterization completed, not tapeout acceptance.

Next add explicit supply/return and signal-path impedance sensitivity, then a complete switching bank. Choose those model values as documented stress assumptions until actual package geometry is available. Preserve both buses, the full PCIe/RF payload target, 50 terminals and the current planning allowances. The older 5 pF `check_power.py` remains a scoped historical screen; it does not automatically select or qualify this candidate.

Archive SHA-256: `25286e3d54ccaac072239455fe7b7c269ea32eda62c86a61c035fc7ada253400`.
