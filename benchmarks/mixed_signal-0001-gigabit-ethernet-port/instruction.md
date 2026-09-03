# MS-T1-001: Complete Gigabit Ethernet port

## Task

Implement one full-duplex, fixed-link 1000BASE-X-style port from independent
8-bit packet streams to die-side TXP/TXN/RXP/RXN terminals. The design includes
the MAC, PCS, PMA, serializer, deserializer, CDR, analog front end, controls,
loopbacks, and diagnostics. Line rate is 1.25 GBd; payload rate is 1 Gb/s.

Build the system. Partial blocks receive diagnostic tier results but cannot pass
the complete-port contract. There is no golden netlist or layout to copy.

Local authorities are:

- this file for required behavior;
- `benchmark_profile.json` for all numerical limits;
- `pdk.lock.json` for process and model identity;
- `tests/coverage/coverage_manifest.json` for requirement-to-test closure;
- `tests/assets/tiered_reward.json` for gates and scoring; and
- executable files in `tests/reference/` for CRC, 8b/10b, ordered sets, and
  analog measurements.

## Submission

Copy the starter from `/app/input_files/` and write candidate files only under
`/app/output/`:

```text
/app/output/rtl/gigabit_ethernet_port_pkg.sv
/app/output/rtl/gigabit_ethernet_port.sv
/app/output/analog/gigabit_ethernet_phy.spice
/app/output/integration/port_manifest.json
/app/output/layout/gigabit_ethernet_port.gds
```

Keep the starter top name and ports unchanged. GDS is required for physical
tiers and the complete-port pass. It must contain the mapped digital design and
analog PHY through the die-side serial terminals. The verifier supplies the
pad/package/channel fixture; custom pads and ESD are outside v1.

Do not submit PDK files, tools, cloned dependencies, generated simulation output,
or precomputed answers.

## Required behavior

### Host and MAC

The host uses independent 125-MHz, 8-bit ready/valid streams. A byte transfers
on `valid && ready`; `last` marks the final byte. TX `user` requests abort and RX
`user` marks a bad frame. Backpressure must not lose, duplicate, or reorder data.

Host frames contain destination address, source address, the big-endian
EtherType/length field, and unpadded payload. They exclude preamble, SFD,
padding, and FCS. RX retains on-wire padding but removes preamble, SFD, and the
verified FCS.

The MAC must pad short frames, generate/check Ethernet CRC-32, enforce IPG,
reject bad/truncated/oversized frames without emitting a partial good frame,
support simultaneous TX/RX, implement pause control and counters, and recover
from errors within the profile bounds.

`rst_ni` is asynchronous active-low. During reset, valid/enable, lock/link/config
status, and counters are zero and `phy_reset_no` is low.

`control_i` fields are enable `[0]`, loopback `[2:1]`, TX swing `[5:3]`, RX
threshold `[8:6]`, bias `[12:9]`, and CDR loop `[15:13]`. `status_o[4:0]` are
enabled, PHY lock, link up, configuration complete, and sticky fault;
`status_o[31:5]` are zero. Codes may not be repurposed.

### PCS and PMA

Implement the benchmark's complete 8b/10b mapping, running disparity, comma
alignment, ordered sets, fixed-link establishment, idle/data transitions,
loss-of-sync, polarity correction, and bounded reacquisition. The local codec
oracle defines encoding, wire order, delimiters, preamble/SFD, and carrier
extension.

The RTL/analog boundary carries one 10-bit code group per `clk_125_i` cycle.
Code bit 0 is transmitted first. The analog PHY owns 10:1 serialization, clock
recovery, 1:10 deserialization, and `phy_rx_code_valid_i`. CDC must preserve
symbol order. Digital, PCS, and analog near-end loopbacks are required only as
diagnostics, not for normal packet transfer.

### Analog and physical

The fixture supplies a 100-ohm differential load, reference clock, and pinned
package/channel family. Build the PHY with programmable TX swing, RX threshold,
bias, and CDR-loop controls; safe reset codes; deterministic startup;
disabled-state isolation; and complete TX, RX, CDR, and clock generation.

Mandatory profile measurements cover swing, common mode, eye height/width,
crossing symmetry, jitter, RX sensitivity, CDR acquisition/tracking, frequency
offset, jitter tolerance, current, startup, calibration range, and TX-to-RX
coupling. Cases include patterns, channels, public PVT corners, supply
disturbance, bounded model perturbations, and supported mismatch.

Use GF180MCU option D exactly as pinned in `pdk.lock.json`: METAL5, MIM_2P0,
3.3-V analog MOS, and `gf180mcu_fd_sc_mcu7t5v0` logic. Implement and verify every
voltage crossing. The final layout must have zero unwaived DRC errors, unique
LVS equivalence, full-RC PEX, final fill, clean density and antenna checks,
acceptable static IR drop and current density, balanced differential parasitics,
and exact pin/manifest identity. Rerun every critical case after extraction.

## Verification and scoring

| Tier | Evidence boundary |
|---|---|
| T1 | MAC against packet oracle |
| T2 | MAC + PCS against symbol peer |
| T3 | Mapped digital path with STA and gate simulation |
| T4 | Transistor TX/RX with ideal clocks |
| T5 | Integrated CDR closes the serial loop |
| T6 | DRC/LVS-clean extracted PHY passes required cases |
| T7 | Routed packet-to-pins-to-packet composition |

T7 is the only complete solution. Pass every hard gate and mandatory case.
Nominal margin cannot offset a failed corner. Public and hidden tests enforce the
same frozen contract; hidden tests vary legal values, seeds, timing, channels,
corners, and fault locations.

A T7 pass proves packet-to-pins-to-packet operation under the exact process,
fixtures, corners, and limits locked by this benchmark. Fabrication signoff and
standards certification are separate deliverables and are not scored here.

The specification, coverage map, and local oracles are complete. Public launch
requires one end-to-end pilot to bind candidate-specific analog/PEX adapters and
freeze measured runtime and score thresholds.

Run `make selftest` to validate this package. With a candidate present, run:

```sh
make visible OUTPUT=/app/output
```
