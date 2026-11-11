# Island support cells: power switch, analog test bus, isolation clamp

These are the reusable support cells every switched island needs. Everything
here is generated from `design.py`. Every number below comes from
`evidence.json`, which `run.sh` writes.

Island allocations and membership come from `spec/analog-architecture.json`.

The evidence is cell-level plus one integration fixture: an island
back-driven from its pad, with `iso_clamp` cells at the core boundary.

| File | Role |
| --- | --- |
| `design.py` | Island table from `analog-architecture.json` and the DEBUG estimate, sizing rule and all transistor netlists |
| `sim.py` | Schematic ngspice campaign: function, safety and exploratory points |
| `layout.py` | Magic layout generator: device rows, M3 columns, M4 tracks, pass-array grid. Device and route style follows `ip/blocks/analog/wireline_serdes/clock_pulse/layout.tcl` |
| `physical.sh` | Magic DRC, KLayout DRC (gf180mcu macro deck), Netgen LVS and Magic PEX (C-coupled) |
| `extracted.py` | Reruns the schematic testbenches on the extracted netlists at every envelope point. ATB cells use a default-mode ext2spice extraction (`pexd`, see section 3) |
| `rc_check.py` | Full-RC extraction (`sak-pex -m 3 -t 1 -r 1 -y 0`) and DC switch drop including metal |
| `integration.py` | RF_TX back-drive fixture with `iso_clamp` at the core boundary (schematic and extracted) |
| `crosscheck.sh` | Independent Magic DRC and Netgen LVS from GDS in the librelane canary image |
| `summarize.py` | Builds `evidence.json` with its verdicts and the proposed readiness. A missing input gives `unverified`, never `pass` |
| `run.sh` | Reproducible entry point. Containers run offline with bounded resources and `OMP_NUM_THREADS=1`. Outputs go to `scratch/island-support-*` and take about 2 h at 10 CPUs |

## Envelope and supply assumptions

The envelope follows `spec/tapeout-plan.md`, section "Operating envelope":

- **Function:** tt/ss/ff × 22/32 °C × 3.15/3.35 V at the die, plus tt/27 °C/3.3 V.
- **Safety:** ramps from 0 to 3.63 V (1 µs and 100 µs), brownout dips to 1.0 V and 2.0 V, repeated ramps, 0–85 °C.
- **Exploratory only:** −40/125 °C, 3.0/3.6 V, fs/sf. These are recorded but gate nothing.

**PDN in the transient benches** (coordinator decision):

- The bond DC resistance is 0.1 Ω/8 for supply plus 0.1 Ω/10 for return.
- The 2 Ω `package_r` is an AC damping value, so it is modelled across the bond inductance, not in series.
- The 1 nF die decap and the board network are taken from `power.parameters.reduced_pdn_model`.
- A 130 mA background load puts the ring at 3.284 V before any island turns on.

**Drop budget:** the switch drop target is ≤ 20 mV at design current, on the
full-RC extracted layout, at the worst functional point (ss/32 °C/3.15 V). It
sits inside the ~100 mV on-die grid-plus-switch allocation.

## 1. Island power switch `isw_<island>`

Ports:

| Port | Meaning |
| --- | --- |
| `VDD` | M5 edge bar on the ring side |
| `VISL` | M5 edge bar on the island side |
| `VSS` | Ground |
| `EN` | Core register file enable, active high |
| `ISO` | Island-off clamp request, high = isolate. ISO = NAND(EN, PG) |
| `PG` | Rail good |

Each switch has these parts:

- **Pass device:** a pfet_03v3 array with W = 10 µm fingers and L = 0.28 µm. Its n-well is the auto-bulk node VMAX = max(VDD, VISL), so it blocks reverse current.
- **Auto-bulk selectors MB1/MB2:** they scale as W_pass/330. MB3 ties the well to VDD while the switch is on.
- **MB3 turn-off delay (MRD/MCD RC):** it keeps the well on VDD until the pass gate is fully up, so an unloaded island turns off instead of its well sagging into the auto-bulk dead zone.
- **Default off:**
  - `EN` has a weak L = 20 µm pulldown.
  - The off gate is pulled to VMAX by `MPU`.
  - Soft start comes from a weak saturated NMOS (W/L = 0.42/20) discharging the gate against the pass device's Miller capacitance.
- **Active discharge `MDIS`:** W = W_pass/9000, L = 1 µm. It is sized so a 1 µs ring ramp with `EN` undefined keeps VISL ≤ 0.32 V.
- **`PG`:** a high-threshold skewed inverter on VISL plus a restoring inverter.
- **Pass-array metal:**
  - per-row M4 VDD and VISL bars;
  - interleaved vertical M5 stripes;
  - a VDD M5 edge bar on top (ring side) and a VISL M5 edge bar on the bottom (island side);
  - arrays about twice as wide as they are tall;
  - the control strip stacked under the array.
- **Integration requirement:** the ring, and the island grid, must strap to their edge bars at at least 4 evenly spaced points, or continuously. The RC check models exactly 4 feed points; a single centre feed gives 21.5–25 mV on the wired switch. (risk: ISL-01)
- **Bias trunk:** each island's bias distributor (core_support) should enter the island behind its `ISO`. Bias branches open when ISO = 1, so an off island neither loads the master bias nor is biased into a back-powered state. These cells have no bias input.

**Sizing.** Design current = peak allocation × 1.25, rounded up to 5 mA. The device is sized for 12 mV at the worst functional point, using Ron·W = 5.27 kΩ·µm at ss/32 °C/3.15 V (4.47 kΩ·µm at tt/27 °C). That leaves about 8 mV for metal.

| Island | Blocks | Peak allocation → design current | Pass W (array) | Cell area |
| --- | --- | --- | --- | --- |
| wired (includes USB) | 12 wire-domain blocks | 62.86 → 80 mA | 35 200 µm (11×320) | 0.064 mm² |
| rf | 15 rf-domain blocks | 42.49 → 55 mA | 25 200 µm (9×280) | 0.050 mm² |
| pll | 8 pll-domain blocks (master bias excluded) | 47.78 → 60 mA | 27 000 µm (9×300) | 0.053 mm² |
| conv | adc_i/q, dac_i/q, refbuf | 23.0 → 30 mA | 13 200 µm (6×220) | 0.032 mm² |
| debug | bb_tap ×2, wmon, clk_obs ×2, aux/wclk/wtx_ext receivers, ring_osc, vco_replica | 28.02 → 40 mA | 17 600 µm (8×220) | 0.037 mm² |

The switches total **0.236 mm²** (bounding boxes), within the 0.35 mm² granted from the power reserve.

**The DEBUG current is an estimate** (`design.py:DEBUG_ESTIMATE_MA`). Only
bb_tap is characterized (1.01 mA, `analog/rf_rx`). The rest are planning
estimates; the debug blocks have no allocation entry in
`analog-architecture.json`. (risk: MOD-15)

**Results.** All criteria pass on all five islands.

| Check | Result |
| --- | --- |
| Drop at design current, full-RC extracted, 13 functional points | wired 19.9, rf 16.5, pll 17.3, conv 14.4, debug 15.5 mV (tt/27 °C: 18.1, 14.9, 15.5, 12.7, 13.8 mV). Device alone: ≤ 11.8 mV (risk: PDN-05) |
| Soft start (DC-corrected common-ring PDN) | Ring dip below its settled value: **0 mV** (schematic and extracted). Abrupt gate drive: 121–286 mV. Peak switch current equals the island load (23–62 mA), vs 147–334 mA abrupt. Rail 10–90 % in 1.0–4.6 µs. EN→PG ≤ 7.8 µs (risk: PDN-07) |
| Off leakage, pass device | ≤ 13.5 nA at 3.35 V, 22–32 °C. ≤ 0.43 µA at 3.63 V, 0–85 °C. ≤ 3.7 µA at 125 °C (exploratory) |
| Reverse blocking: peer at 3.63 V behind 10 Ω; ring at 0/1.5/3.15/3.3 V; 0–85 °C; tt/ss/ff | Current into ring ≤ 0.43 µA |
| Same, other topologies (wired size) | Edwards-style body-on-ring: 0.30 A. Back-to-back: 0.27 µA |
| Active discharge: unloaded rail to < 0.3 V after EN falls | 1.2–3.3 µs |
| Default off: EN floating, 0→3.63 V in 1 µs or 100 µs, 0/85 °C | VISL ≤ 0.32 V, ISO high |
| Brownout and repeated ramps | VISL ≤ 0.18 V with EN floating. PG/ISO recover with EN on |
| ISO assertion after EN falls | ≤ 6 ns |

A powered peer driving an off island sees up to 1.2 mA, sunk by the discharge
NMOS from the back-driven rail; none of it reaches the ring.

**RF_TX back-drive.** The pad at 3.3 or
3.63 V feeds the RF rail through the driver output junctions, modelled as a
diode plus 28 Ω. The model is calibrated to 89–93 mA into a 0 V rail. With the
RF island off: (risk: LU-03)

- **Into the ring:** ≤ 0.27 µA, with the ring at 0 or 3.3 V, 0–85 °C.
- **Island rail with decap only:** it is not clamped. It floats to 2.6–3.5 V, and the pad supplies ≤ 0.85 mA.
- **Island rail with the RF allocation as load:** 1.8–2.2 V, and the pad supplies ≤ 29 mA, dissipated in the island.
- **Status with the ring powered:** ISO stays high, and PG reads 1 while EN = 0. That PG/EN combination is the SPI diagnostic for back-drive.

## 2. Core-boundary isolation clamp `iso_clamp`

Y = A AND NOT ISO, in the core VDD domain. Ports: A, ISO, Y, VDD, VSS. Six
devices, 906 µm².

It is used in both directions:
- island→core, so a back-powered island's outputs read 0 in the core;
- core→island, so the core cannot drive an off island's inputs and power it through their ESD diodes.

A only reaches gates, so an island at up to 3.63 V cannot inject into the core.

**Integration fixture** (`integration.py`): the RF switch and both clamps, with
the island output stage driving its worst-case high level, an island input with
an ESD diode to VISL, and the core attempting to drive that input high. Cases:
72 DC points (tt/ss/ff × 0/27/85 °C × ring 0/3.3 V × pad 3.3/3.63 V × with and
without load), a pad hot-plug transient (0→3.63 V in 100 ns), and a check that
the clamp is transparent with the island on.

| Result | Schematic | Extracted (C-coupled RF switch and clamp) |
| --- | --- | --- |
| Core-side input from the island (CORE_IN), max | 0.07 µV | 0.07 µV |
| Island input driven by the core (ISL_IN), max | 0.146 V (ring unpowered, clamp unpowered) | 0.146 V |
| DC current into ring, max | 0.27 µA | 0.27 µA |
| Hot-plug glitch at CORE_IN / ISL_IN | 5.2 mV / 0.3 mV | 10.5 mV / 0.4 mV |
| ISO high with the ring powered | yes | yes |
| Island on, no back-drive: CORE_IN | 3.3 V (transparent) | 3.3 V |
| Verdict | **pass** | **pass** |

The hot-plug ring current peak (0.77–0.83 mA) is capacitive displacement through
the off pass device during the 100 ns pad edge, not DC conduction. (risk: PDN-08)

### 2a. Isolation-clamp family for LU-02 (pads owner, 2026-11-10) (risk: LU-02)

Risk register LU-02 / RA-2: v3 had no clamp instances. The family adds a
clock-strength logic clamp and an analog/RF clamp with no series element
(`design.py:ISO_CELLS`, built by `iso_family.sh <outdir>`; the NMOS-only cells
use the bank-A-only path of `layout.logic_block`).

| Cell | Function / ports | Area (µm²) | Use |
| --- | --- | --- | --- |
| `iso_clamp` | Y = A·!ISO; `A ISO Y VDD VSS` | 906 | slow status nets (analog_status[0], WTX_EXT_DATA) |
| `iso_clamp_x4` | same function, 4× output stage | 1,025 | clocks routed to the macro (fc_src[0..3], ct_wclk, ct_word_clk) |
| `iso_pd` | nfet_03v3 0.5/0.28 pull-down Y→VSS while ISO=1; `Y ISO VSS` | 95 | LO_IP/IN/QP/QN, WMON_IN (gate-only analog/RF nets) |
| `iso_pd2` | two `iso_pd` in one cell | 176 | **not recommended**: extracted leg C is asymmetric (P 1.09 fF, N 3.02 fF); use two `iso_pd` for matched LO legs |

Physical (`scratch/iso-family/`): Magic DRC 0, KLayout DRC 0 (sak), netgen
unique match, PEX, and the tapeout KLayout precheck (main 0 / antenna 0) for
all four after `gds_uniquify`.

Extracted checks (`scratch/iso-family/sims/iso_sims.py`, `iso-sims.json`):

| Check | Result |
| --- | --- |
| `iso_pd` on a 2.45 GHz LO leg (100 Ω source, 30 fF mixer gate), ISO=0, tt/ss/ff × 22/32 °C | amplitude −0.0016 dB worst, phase ≤ 0.22°; load 1.75 fF + junction |
| `iso_pd` release with the driver unpowered (node left at 1.0 V, 1 GΩ) | < 50 mV in ≤ 369 ps after ISO rises |
| `iso_clamp` / `iso_clamp_x4` A→Y into 200 fF (~1 mm), 12 functional points | worst 2.08 ns / 0.93 ns; high level ≥ 3.11 / 3.15 V |
| ISO=1, A at 0 / 1.65 / 3.63 V (floating or back-powered island), tt/27, ss/0/3.63, ff/85/3.63, ss/85/3.15 | Y ≤ 0.0001 mV |

ISO source: `ISLAND_OFF_<driving island>` = NOT `island_on[k]` (honours
`pgood_override`, mismatch I3); the switch's own ISO stays the backstop.
Placement list for assembly: `generated/iso-family/iso-placement.json` (cells, PEX, sims and KLayout records in the same directory)
(13 cells, 8.4k µm²). Two v3 binding defects block two of the nets:
`ct_word_clk` and `island_on[0]` each have two drivers (see interface-changes
"Pads owner: LU-01 / ESD-04 / LU-02 / PDN-04"). (risk: LU-02)

## 3. Analog test bus

### Architecture

The register file already decodes `debug.atb.atb0`/`atb1` into one-hot lines
`atb0_sw[56:0]` and `atb1_sw[56:0]` (`rtl/pt_regfile.sv`). It ANDs island
nodes with `island_on` and enforces break-before-make by committing a zero code
between two non-zero codes. So:

- **Leaves are bare switch pairs.** Each is one inverter plus a T-switch (NODE–T1–MID–T2–BUS, with MID shunted to VSS while open). One leaf is driven directly by one `atbX_sw` line. Leaves contain no pulldown, delay or non-overlap logic:
  - default-open comes from the register reset;
  - break-before-make between leaves comes from the register-file gap.
- **The default-open and break-before-make control lives once per group,** in `atb_grp` (local bus to global bus) and in `atb_pad` (global bus to pad). Each has a weak pulldown on its select, plus a delayed-close / early-open non-overlap control. That gives a hardware break-before-make backstop at group and pad level.

| Cell | Count in the register-map tree | T1 (node side) / T2 (bus side) / shunt | Area |
| --- | --- | --- | --- |
| `atb_leaf_s` (bare) | 54 (every hardware node, ATB1) | 0.42/0.84 µm, L 0.28 / 1/2 µm / 1 µm | 827 µm² |
| `atb_leaf_f` (bare) | 20 (the ATB0-legal codes: 7 override + 13 replica/matching/vbg) | 4/8 µm, L 0.5 / 4/8 µm / 1 µm | 1 086 µm² |
| `atb_grp` (with control) | 5 on ATB1 + 2 on ATB0 (≤ 12 leaves each) | 8/16 µm | 6 145 µm² |
| `atb_pad` (with control) | 2: `analog[0]` = ATB0 force, `analog[1]` = ATB1 sense | TG 8/16 µm; PMOS well auto-bulk max(VDD, PAD); off gate to VMAX; bus shunted while open | 6 626 µm² |

**Tree area** (bounding boxes, no routing):
- Register-map tree (57 sense leaves, 20 force leaves, 7 groups, 2 pads): **0.125 mm²**.
- A full 96-slot tree (96 sense, 32 force, 16 groups, 2 pads): 0.226 mm².
- Target: ≤ 0.3 mm².

**Placement:** sense leaves for per-block bias nodes sit at the
core_support bias-bank outputs, which gives the same observability as the
mirror gate with shorter routing. There is one leaf per register-map code.
Supply-monitor leaves (codes 5–13) tap each switched rail and are not
island-gated.

### Results

Extracted at the 13 functional points unless noted. All ATB verdicts pass.

| Cell | Ron, functional max | Off load at tapped node (extracted max) | Off leakage, 22–32 °C (85 °C) | Gap between two cells on one bus |
| --- | --- | --- | --- | --- |
| atb_leaf_s | 16.4 kΩ | **3.17 fF** (limit 5 fF) | 17 pA (0.32 nA) | 20 ns (the register-file gap) |
| atb_leaf_f | 4.4 kΩ | 17.1 fF | **1.5 pA** (54 pA); limit 100 pA | 20 ns (the register-file gap) |
| atb_grp | 1.17 kΩ | 34.4 fF | 0.23 nA (4.5 nA) | ≥ 5.5 ns, internal |
| atb_pad | 0.59 kΩ | n/a | n/a | ≥ 5.7 ns, internal |

- **Leaf internal overlap:** because the leaves are bare, the TG and shunt overlap for 0.07–0.38 ns while a leaf switches.
- **Select disturbance** on a 1.2 V bias node fed through 100 kΩ with 1 pF (sense bus held at 1.2 V):
  - `atb_leaf_s`: ≤ 14 mV closing, ≤ 0.7 mV opening.
  - `atb_leaf_f`: ≤ 54 mV closing, ≤ 7 mV opening.
  - It is dominated by gate charge injection and recovers with the node's RC. Force leaves only sit on overridable bias/reference nodes and replicas.
- **Isolation** (extracted, tt/27 °C, 10 kΩ node, 1 V on the bus): sense leaf −174/−134/−94 dB at 1/10/100 MHz.
- **Force/sense** (100 µA through leaf_f → grp → pad, read through leaf_s → grp → pad with a 10 MΩ meter):
  - The force pad reads 192–322 mV above the node.
  - The sense pad is within 0.6–1.2 mV of the node.
- **Sense settling:** 1.01 µs to 1 %, extracted.
- **Pad overvoltage:** ring current ≤ 1.1 nA, global bus ≤ 45 mV.
  - One extracted dead-zone case (ring 3.3 V, PAD 3.63 V, 27 °C) draws 56 µA from PAD into the bus shunt. It does not reach the ring.
- **Extraction note:** sak-pex runs ext2spice in `lvs` mode. That mode moves the substrate capacitance of gate-only nets (in `atb_leaf_s`: SEL 6.27 fF + SWB 4.52 fF) in equal halves onto NODE and MID (+5.40 fF each).
  - Default-mode ext2spice keeps NODE at its `.ext` value: 0.47 fF to substrate.
  - The ATB results use the default-mode extraction.
  - The `lvs`-mode figure is kept in `evidence.json:atb.lvsmode_off_c_tt22_mid_f` (leaf_s 8.3 fF) for comparison.

## Register interface (what the register file must drive)

### ATB

| Signal (core domain, 3.3 V) | Width | Drives | Requirement |
| --- | --- | --- | --- |
| `atb0_sw[i]`, `atb1_sw[i]`, i = code − 1 | 57 each, one-hot or all-zero | One leaf `SEL` | Already present. 1 = closed. Reset 0. Island-node lines ANDed with `island_on[island]`; supply-monitor lines not gated. At most one line high per bus. |
| `atb0_grp[g]`, `atb1_grp[g]` | 2 and 5 (one per group) | `atb_grp` `SEL` | **New.** OR of that group's `atbX_sw` lines, after island gating. |
| `atb0_en`, `atb1_en` | 1 each | `atb_pad` `SEL` | **New.** OR of all `atbX_sw` lines on that bus. |
| All-off gap between two non-zero codes on one bus | — | — | **≥ 20 ns** from the deselect edge to the next select edge on the same bus. That covers the leaf turn-off (≤ 0.4 ns) and the group/pad non-overlap delay (≤ 5.7 ns) with margin. The existing zero-commit rule separates the two commits by at least one SPI transaction (32 SCLK), which meets this at any SCLK below 1.6 GHz. |

There is no separate group or leaf address field. The 6-bit code is the select,
and the code-to-group mapping is a placement table owned by the integration
step. Leaves never need decoding in the analog domain.

### Islands

| Cell port | Register-file signal | Requirement |
| --- | --- | --- |
| `isw_<island>.EN` | `island_en[b]` (`debug.island_power.<island>`) | Reset 0. Core-domain level. The cell's internal pulldown handles an undriven line. |
| `isw_<island>.PG` | `island_pgood[b]` | Asynchronous. The register file synchronizes it into SCLK with two flops; status 0x0A b13:8 shows it. |
| `iso_clamp.ISO` (boundary clamps, both directions) | **`~island_on[b]`** | **New output.** See mismatch I3. |
| `isw_<island>.ISO` | — | Local backstop only. Its NAND(EN, PG) ignores `pgood_override`. |

### Mismatches against the current register map

Sources: `spec/register-map.md`, `spec/debug-controls.json` (`islands`, `atb_nodes`, `debug.atb`, `break_before_make_rule`), `rtl/pt_regfile.sv`, `rtl/pt_digital.sv`.

| # | Item | Register map today | These cells | Proposed fix |
| --- | --- | --- | --- | --- |
| A1 | Group and pad enables | Only per-node one-hot `atb0_sw`/`atb1_sw` | `atb_grp` and `atb_pad` need `atbX_grp[g]` and `atbX_en` | Add them as ORs of the island-gated `atbX_sw` lines; or the integration step adds an analog OR. The first is cheaper. (risk: INT-22) |
| A2 | Dead time | `control_semantics.switch_dead_time_s` = 4 ns | Needs ≥ 20 ns. The group/pad non-overlap delay alone is up to 5.7 ns | Raise the ATB entry to ≥ 20 ns. The zero-commit rule already gives far more, so no RTL change is needed. |
| A3 | USB nodes | Code 10 `usb_vdd_sw_sense`; codes 40 `usbhs_ibias` and 41 `usbfs_vref` gated by island `usb` | There is no USB island switch | Code 10: mark `hardware=false` (no USB rail). Codes 40 and 41: gate by `wired` (usbhs) and leave ungated (usbfs, host domain). (risk: INT-22) |
| A4 | Code range | `debug.atb` max 57 (code 57 `idac1_source_ibias` added); `PT_ATB_W` 57 | One sense leaf per hardware code: 54 | Consistent. No change. |
| A5 | Force legality | ATB0 legal on 20 codes, enforced at commit | One force leaf per legal code | Consistent. |
| I1 | Island bits | `islands` has 6 bits: wired 0, rf 1, pll 2, usb 3, conv 4, debug 5 | 5 switches: wired, rf, pll, conv, debug | Drop `usb` (bit 3), or leave it reserved with `island_en[3]` unconnected and `island_pgood[3]` tied 0. Then `island_on[3]` = 0 and every control that lists `usb` stays clamped. Re-point the `usbhs`/`usbdrive` island lists to `wired` only. `usbfs` is on the host domain and should have no island. |
| I2 | Island membership text | `islands.wired.description` omits usbhs/usbdrive. `islands.pll` includes the AUX_CLK/WCLK_IN receivers | The wired switch carries all 12 wire-domain blocks including USB HS/drive. The DEBUG switch carries the AUX_CLK/WCLK_IN/WTX_EXT receivers | Update the descriptions, and decide whether the debug-pad receivers sit on `pll` or `debug`. |
| I3 | Boundary isolation | `island_on` = `island_en` AND (`pgood` OR `pgood_override`) exists inside `pt_regfile`/`pt_digital` but is not an output port | `iso_clamp` needs an ISO per island. The cell's own ISO = NAND(EN, PG) would keep clamping when PG fails and `pgood_override` is set | Export `island_on[5:0]` (or `island_iso[5:0]` = ~`island_on`) from `pt_digital` and drive every `iso_clamp` ISO from it. That keeps boundary clamping, control-output gating (`gating_rule`) and status 0x0A identical. The cell ISO stays as an unused backstop. (risk: INT-22) |
| I4 | Power-good semantics | Status 0x0A b13:8 = power-good, b5:0 = effective-on | PG is a ratiometric threshold (the island rail crossed a skewed-inverter threshold; the threshold voltage is not characterized here). It is 1 whenever the rail is up, including back-drive with EN = 0 | Document PG = 1 with `island_power` = 0 as the back-drive signature. No register change. (risk: INT-22) |

## 4. Physical status

All 10 cells (`isw_{wired,rf,pll,conv,debug}`, `atb_leaf_s`, `atb_leaf_f`, `atb_grp`, `atb_pad`, `iso_clamp`):

| Check | Result |
| --- | --- |
| Magic DRC (iic-osic-tools) | 0 errors |
| KLayout DRC (gf180mcu macro deck) | 0 violations |
| Netgen LVS | match |
| Cross-check from GDS, Magic DRC + Netgen LVS (librelane canary) | 0 errors, match |

- Primary image: `hpretl/iic-osic-tools@sha256:8964…` (ID `sha256:bd7a70…`).
- Cross-check image: `svalbard/librelane-gf180-canary:2026.08` (ID `sha256:b6027809…`).
- GDS and PEX hashes are in `evidence.json:physical`.
- **Extracted function (C-coupled):** all 13 envelope points for every cell.
- **Full-RC drop:** all five switches.

## Readiness (block `power`, four tests)

`evidence.json:summary.proposed_tapeout_readiness_power` computes these states
from the verdicts; they match `spec/tapeout-readiness.json`.

| Test | State | Evidence |
| --- | --- | --- |
| safe | **pass** | `island_switch.*.{default_off,reverse_blocking,discharge,off_leakage}`, `rf_tx_backdrive`, `integration_rf_tx_backdrive_iso`, `atb.verdicts.pad_overvoltage` |
| clean | **pass**, cell scope | `physical`, `physical_crosscheck_librelane_image`, `island_switch.*.drop` (full RC), `atb.verdicts`. Ring decap and top-level assembly belong to freeze stage 4 |
| observable | **open** | PG/ISO and the VISL ATB taps are designed. The `EN`/`PG`/`ISO` register fields and the ATB select decode are not in `rtl/` (risk: INT-04) |
| fallback | waived_core | — |

## Open risks

1. **Register interface gaps** (A1, A3, I1–I3 above). The ISO export (I3) is needed before the boundary clamps can be wired. (risk: INT-22)
2. **Ring strapping requirement:** the 20 mV drop needs the ring and island grid strapped to the edge bars at ≥ 4 points. The wired switch has 0.13 mV of margin. A single feed point gives 21.5–25 mV. (risk: ISL-01)
3. **Back-drive powers the island:** pad back-drive powers an off island (1.8–3.5 V). The ring is protected and the boundary is clamped. The pad-side protection and the board DC block remain the owners of the island stress. (risk: LU-03)
4. **Auto-bulk dead zone** (|VISL−VDD| or |PAD−VDD| below a PMOS threshold voltage): the wells float there. It is handled at switch turn-off by the MB3 delay. The `atb_pad` 56 µA bench-load case is accepted. (risk: ISL-02)
5. **Bare-leaf select disturbance:** up to 54 mV on a 1 pF bias node when a force leaf closes. It recovers with the node's RC; avoid force leaves on nodes with very small capacitance. (risk: ISL-03)
6. **Extraction tool caveats:**
   - The C-coupled extraction has no resistance; DC drop comes from the full-RC run only.
   - ext2spice `lvs` mode misattributes the capacitance of gate-only nets, so the ATB results use the default-mode extraction.
7. **DEBUG island current** is mostly estimated, not simulated. (risk: MOD-15)
8. **Area figures** are bounding boxes without routing. The ATB bus routing (two buses to 7 groups, then 74 leaf lines from the register file) is not counted. (risk: MOD-15)
9. **Not done:** (risk: MOD-15)
   - placement and wiring of the taps and buses;
   - interaction with the provider pad's ESD;
   - mismatch and Monte Carlo;
   - ESD/TLP of the switch arrays;
   - electromigration checks on the straps.

**Evidence currency.** `evidence.json:source_sha256_at_summary` matches every
current source file. In `source_sha256` (recorded at simulation time) only
`summarize.py` differs, i.e. the report builder changed between simulation and
summary; all simulation sources match.
