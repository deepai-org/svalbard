# Pass 9: preserve bandwidth while reducing host driver current

## Supply-path audit

The [GF180 I/O cell list](https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/datasheet.html) assigns 60 mA DC capacity to each native supply/ground cell. This is not a package-terminal rating. The [supply-pad description](https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/power.html) describes ESD circuits; it does not qualify a higher-current custom feed. The installed supply SPICE exposes rail nodes without a separate external bond node, so that schematic alone cannot prove feed-metal or bond capacity.

Do not assume that paralleling clamps, using a stronger bond wire, or narrowing temperature automatically increases native-cell current capacity. A custom supply path remains possible but needs physical metal/via, ESD and package evidence. Keep the present terminal allocation while investigating current at its source.

## Native driver comparison

The [programmable driver controls](https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/digital.html) select 12 mA with PDRV1/PDRV0=1/0 and 16 mA with 1/1. The native `bi_t` netlist includes these pins, unlike `bi_24t`. The runner now accepts a drive selection; its default 24 mA instance text remains unchanged. Six measurement/pin-mapping tests passed inside the pinned analog image.

Four fresh transistor simulations compare 12/16 mA settings using alternating and PRBS7 patterns. Conditions remain 312.5 Mb/s/pin, 8 pF per output, 3.3 V, 25 C, typical process, ideal supplies. All four cases check 20 bits at the same assumed three-point ±0.2 ns aperture and 0.3/0.7 VDD thresholds. These are generic screens, not the host-specific threshold analysis from pass 8.

| Native drive setting | Alternating pair DVDD average | Worst sampled margin across two patterns | HOST_B current with unchanged allowances |
|---|---:|---:|---:|
| 24 mA, pass 8 baseline | 16.409 mA | 0.983 V | 63.54 mA |
| 16 mA | 15.551 mA | 0.968 V | 60.32 mA |
| 12 mA | 14.334 mA | 0.916 V | 55.75 mA |

The smaller drivers reduce modeled current while retaining positive sampled margin. **Neither tested replacement meets the 55 mA HOST_B planning ceiling with existing allowances.** The 12 mA result is close but still fails; no allowance or ceiling was relaxed. No driver is selected for implementation yet.

The drive labels are library modes, not constant-current sources or guaranteed currents at this operating voltage. Absolute clock delay also changes; common delay cancellation in this matched pair does not establish skew or FPGA timing.

## Reproduction and next step

Run `verification/run_drive_strength.sh` from this project. The [report](../evidence/drive-strength-screen.json) records source/deck/waveform/log hashes and current calculations tied to the unchanged contract. Raw waveforms are retained in `scratch/transceiver-drive-strength-waveforms.tar.gz`. The wrapper's PASS means bounded characterization completed, not that the candidate meets the chip requirements.

Next test weaker drive against realistic load and host thresholds, then include package/rail impedance and concurrent-bank switching before selection. Keep 50 terminals, both 10-bit buses and full-rate concurrent mode. No reduction in data rate, payload or functionality was used to improve the current result. Actual host timing, process variation and the numerical narrow operating envelope remain unclosed.

Waveform archive SHA-256: `6668274a18c3a37f987e8e79b91e3499c341f63062b74c4d28086284257453f5`.
