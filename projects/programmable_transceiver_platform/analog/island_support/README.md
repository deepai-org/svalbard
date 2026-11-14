# Island support cells: power switch, isolation, analog test bus

Reusable cells for the switched supply islands. Everything is generated from `design.py`. Unless a row names
another source, every number comes from `evidence.json` (written by `run.sh`).

| Cell | Function | Published view |
| --- | --- | --- |
| `isw_wired`, `isw_rf`, `isw_debug`, `isw_conv` | island power switch masters | `generated/isw/` (GDS, LVS netlist, C-coupled and full-RC extraction, precheck record, `SHA256SUMS`) |
| `iso_clamp`, `iso_clamp_x4`, `iso_pd`, `iso_pd2` | isolation cells | `generated/iso-family/` |
| `atb_leaf_s`, `atb_leaf_f`, `atb_grp`, `atb_pad` | analog test bus switches | none in the tree (see Open items) |

Ten islands use the four switch masters; the partition, currents and grid rules are in
`spec/power-delivery.md` section 2. Chip instances and bindings are in `integration/top/pt_chip.conn`.

## Conditions

| Use | Points |
| --- | --- |
| Function | tt/ss/ff × 22/32 °C × 3.15/3.35 V plus tt/27 °C/3.3 V (13 points) |
| Safety | ramps 0 → 3.63 V in 1 µs and 100 µs, brownout dips to 1.0 V and 2.0 V, repeated ramps, 0–85 °C |
| Exploratory (gates nothing) | −40/125 °C, 3.0/3.6 V, fs/sf |

Transient benches use the common-ring supply model of `sim.py` with a 130 mA background load (ring at 3.284 V
before an island turns on). Drop limit: ≤ 20 mV at the design current, full-RC extracted, worst functional point.

## 1. Island power switch `isw_<master>`

| Port | Meaning |
| --- | --- |
| `VDD` | Metal5 edge bar, ring side |
| `VISL` | Metal5 edge bar, island side |
| `VSS` | ground |
| `EN` | enable, active high, weak internal pull-down |
| `PG` | rail good (skewed inverter on `VISL`) |
| `ISO` | NAND(`EN`, `PG`), high = isolate |

Circuit: pfet_03v3 pass array (W = 10 µm fingers, L = 0.28 µm) whose n-well follows max(`VDD`, `VISL`), so it
blocks reverse current. The gate is pulled to the higher rail when off and discharged by a weak saturated NMOS
for soft start. A small NMOS discharges the island rail when off.

| Master | Design current | Pass W | Area | Full-RC drop at design current, worst / tt 27 °C | Islands (worst / design current, drop at design) |
| --- | ---: | ---: | ---: | --- | --- |
| `isw_wired` | 80 mA | 35 200 µm | 0.064 mm² | 19.9 / 18.1 mV | wired_cap 67.6 / 72.9 mA, 18.1 mV; lod 70.6 / 74.1 mA, 18.4 mV |
| `isw_rf` | 55 mA | 25 200 µm | 0.050 mm² | 16.5 / 14.9 mV | rf_rx 38.2 / 43.6 mA, 13.1 mV |
| `isw_debug` | 40 mA | 17 600 µm | 0.037 mm² | 15.5 / 13.8 mV | wired_rx 28.7 / 30.9 mA, 12.0 mV; wired_tx 37.5 mA, 14.5 mV; rf_tx 26.3 / 32.3 mA, 12.5 mV; pll 26.4 / 29.4 mA, 11.4 mV; debug 40 mA, 15.5 mV |
| `isw_conv` | 30 mA | 13 200 µm | 0.032 mm² | 14.4 / 12.7 mV | lo 27.5 / 28.1 mA, 13.5 mV; conv 18.7 mA, 9.0 mV |

Island currents and per-island drops: `spec/power-delivery.md` (`spec/budgets/power_budget.py --reconcile`).
Ten instances total 0.427 mm². A fifth verified cell, `isw_pll` (60 mA), is not instantiated or published.
The debug island is limited by rule to 40 mA of debug loads enabled at once.

| Check (per master unless noted) | Result |
| --- | --- |
| Device-only drop at design current | ≤ 11.8 mV |
| Soft start at the master's design load: ring dip below its settled value | 0 mV, schematic and extracted (abrupt gate: 121–286 mV) |
| Soft start: peak switch current / rail 10–90 % / `EN` to `PG` | equals the load / 1.0–4.6 µs / ≤ 7.8 µs |
| Soft start at the ten islands' worst loads and capacitances, extracted, 3.3 V, tt/ss/ff (`pd2-softstart.json`) | dip 0 mV; peak ≤ 1.007 × load; rail 10–90 % 1.1–4.8 µs; `EN` to `PG` ≤ 8.4 µs. Abrupt-gate negative control fails (92 mV, 126 mA) |
| Enable groups on one edge, schematic masters (`pd2-softstart.json`) | rf_rx + rf_tx + lod + lo: 156 mA, ring step 19 mV; wired_rx + wired_cap + wired_tx: 132 mA, 16 mV; no overshoot |
| Off leakage of the pass device | ≤ 13.5 nA at 3.35 V, 22–32 °C; ≤ 0.43 µA at 3.63 V, 0–85 °C |
| Reverse blocking, peer at 3.63 V behind 10 Ω, ring at 0–3.3 V, 0–85 °C | ≤ 0.43 µA into the ring; the peer supplies up to 1.2 mA into the discharge NMOS |
| Active discharge, unloaded rail to < 0.3 V | 1.2–3.3 µs |
| Default off, `EN` floating, 0 → 3.63 V in 1 µs or 100 µs | `VISL` ≤ 0.32 V, `ISO` high |
| Default off, slow ramp, unloaded, ff/85 °C (`scratch/reviews/always-on-audit.md` F8) | `VISL` 0.34–0.35 V |
| Brownout and repeated ramps, `EN` floating | `VISL` ≤ 0.18 V; `PG`/`ISO` recover with `EN` on |
| `ISO` after `EN` falls | ≤ 6 ns |

RF_TX pad back-drive with the island off (pad at 3.3 or 3.63 V into the rail through a diode plus 28 Ω):
≤ 0.27 µA into the ring; the island rail floats to 2.6–3.5 V with decap only (pad supplies ≤ 0.85 mA) and
1.8–2.2 V with the island load (≤ 29 mA). With the ring powered `ISO` stays high and `PG` reads 1 with
`EN` = 0: that combination is the back-drive signature in the status register.

Integration requirements:

- Ring and island grid strap to each edge bar at ≥ 4 evenly spaced points or continuously. A single centre
  feed gives 21.5–25 mV on `isw_wired`. (risk: ISL-01)
- A bank of the bias distribution must not be biased from a trunk while its island rail is off
  (`analog/core_support/README.md`, Open items).

## 2. Isolation cells

Island-to-macro inputs (about 130) are clamped inside the digital macro with AND cells gated by `island_on`.
The cells here serve the nets that stay outside the macro: 16 clamps and 2 pull-downs in `pt_chip.conn`.
Their `ISO` input is the macro's `island_off[k]` of the driving island.

### 2a. Cell family

| Cell | Function / ports | Area (µm²) | Use |
| --- | --- | ---: | --- |
| `iso_clamp` | Y = A AND NOT ISO; `A ISO Y VDD VSS`; A reaches gates only | 906 | slow logic nets |
| `iso_clamp_x4` | same, 4× output stage | 1 025 | clocks |
| `iso_pd` | nfet_03v3 0.5/0.28 pull-down Y → VSS while ISO = 1; `Y ISO VSS`; no series element | 95 | gate-only analog nets |
| `iso_pd2` | two `iso_pd` in one cell | 176 | not used: extracted leg capacitance is asymmetric (1.09 / 3.02 fF) |

Physical, all four: Magic DRC 0, KLayout DRC 0, LVS unique match, precheck decks main 0 / antenna 0
(`generated/iso-family/*-kldrc.json`).

| Check (extracted, `generated/iso-family/iso-sims.json`) | Result |
| --- | --- |
| `iso_pd` on a 2.45 GHz leg (100 Ω source, 30 fF load), ISO = 0, tt/ss/ff × 22/32 °C | −0.0016 dB, ≤ 0.22°; adds 1.75 fF plus junction |
| `iso_pd` release, node left at 1.0 V | below 50 mV within 369 ps |
| `iso_clamp` / `iso_clamp_x4` A → Y into 200 fF, 12 functional points | ≤ 2.08 ns / ≤ 0.93 ns; high level ≥ 3.11 / 3.15 V |
| ISO = 1 with A at 0 / 1.65 / 3.63 V | Y ≤ 0.0001 mV |

Back-drive fixture (`integration.py`: `isw_rf`, `iso_clamp` in both directions, pad back-driving the island;
72 DC points plus a 100 ns pad hot-plug), schematic and extracted:

| Result | Value |
| --- | --- |
| Core-side input from the island, max | 0.07 µV |
| Island input driven by the core, max | 0.146 V |
| DC current into the ring, max | 0.27 µA |
| Hot-plug glitch at the core input / island input | 5.2 / 0.3 mV schematic, 9.3 / 0.4 mV extracted |
| Hot-plug ring current peak (capacitive, through the off pass device) | 0.77–0.83 mA |
| Island on: clamp transparent | yes |

## 3. Analog test bus

ATB0 is the force bus and ATB1 the sense bus. The register file decodes one-hot leaf selects and puts an
all-open commit between two non-zero codes; leaves are bare switches. Break-before-make and default-open
hardware lives once per group (`atb_grp`, local bus to global bus) and once per pad (`atb_pad`).

| Cell | Instances in `pt_chip.conn` | Switch | Area (µm²) |
| --- | ---: | --- | ---: |
| `atb_leaf_s` (sense) | 58 | inverter + T-switch, middle node shunted to VSS while open | 827 |
| `atb_leaf_f` (force) | 21 | same, wider devices | 1 086 |
| `atb_grp` | 7 (2 on ATB0, 5 on ATB1) | with select pull-down and non-overlap control | 6 145 |
| `atb_pad` | 2 | with auto-bulk PMOS well, bus shunted while open | 6 626 |

Cell area of that tree: 0.127 mm², without routing.

| Cell | Ron, functional max | Off load on the tapped node, extracted max | Off leakage 22–32 °C (85 °C) | Gap on one bus |
| --- | --- | --- | --- | --- |
| `atb_leaf_s` | 16.4 kΩ | 3.17 fF (limit 5 fF) | 17 pA (0.32 nA) | 20 ns, from the register file |
| `atb_leaf_f` | 4.4 kΩ | 17.1 fF | 1.5 pA (54 pA) | 20 ns, from the register file |
| `atb_grp` | 1.17 kΩ | 34.4 fF | 0.23 nA (4.5 nA) | ≥ 5.5 ns, internal |
| `atb_pad` | 0.59 kΩ | | | ≥ 5.7 ns, internal |

- Select disturbance on a 1.2 V node behind 100 kΩ with 1 pF: `atb_leaf_s` ≤ 14 mV closing, ≤ 0.7 mV opening;
  `atb_leaf_f` ≤ 54 mV closing, ≤ 7 mV opening. (risk: ISL-03)
- Sense-leaf isolation, extracted, tt/27 °C: −174 / −134 / −94 dB at 1 / 10 / 100 MHz.
- Pad overvoltage: ring current ≤ 1.1 nA, global bus ≤ 45 mV. One extracted case (ring 3.3 V, pad 3.63 V,
  27 °C) draws 56 µA from the pad into the bus shunt; it does not reach the ring. (risk: ISL-02)
- ATB results use a default-mode ext2spice extraction: the `lvs` mode moves the substrate capacitance of
  gate-only nets onto the switch nodes (leaf_s 8.3 fF, kept in `evidence.json:atb.lvsmode_off_c_tt22_mid_f`).

## Register and macro interface

| Cell port | Macro signal | Notes |
| --- | --- | --- |
| `isw_*.EN` | `island_en[b]` (`debug.island_power.<group>`) | reset 0. Enable groups: wired = wired_rx + wired_cap + wired_tx (bit 0); rf = rf_rx + rf_tx + lod + lo (bit 1); pll (2); conv (4); debug (5). Bit 3 (`usb`) is reserved: there is no USB switch (register-map source tag I1) |
| `isw_*.PG` | `s_pg_<island>` | one per switch; the macro ANDs each group; status 0x0A |
| isolation cell `ISO` | `island_off[b]` = NOT `island_on[b]` | `island_on` = `island_en` AND (power-good OR `pgood_override`) |
| `isw_*.ISO` | unused, except `isw_wired_tx.ISO` (wired TX fallback control) | NAND(`EN`, `PG`) ignores `pgood_override` |
| leaf `SEL` | `atb0_sw[code − 1]`, `atb1_sw[code − 1]` | one-hot or all zero; island nodes gated with `island_on` |
| `atb_grp.SEL` | `atb0_grp[1:0]`, `atb1_grp[4:0]` | OR of the group's leaf selects |
| `atb_pad.SEL` | `atb0_en`, `atb1_en` | OR of all leaf selects on the bus |

All-off gap between two non-zero codes on one bus: ≥ 20 ns (`spec/debug-controls.json`
`atb_switch_dead_time_s`); the zero commit gives at least one SPI transaction.

## Flow

```
analog/island_support/run.sh          # all cells, about 2 h at 10 CPUs, outputs in scratch/island-support-*
analog/island_support/iso_family.sh <outdir>
analog/island_support/pd2_softstart.sh
```

| File | Role |
| --- | --- |
| `design.py` | island table from `spec/analog-architecture.json`, sizing rule, all transistor netlists |
| `sim.py` | schematic ngspice campaign |
| `layout.py` | Magic layout generator |
| `physical.sh` | Magic DRC, KLayout DRC, Netgen LVS, Magic extraction |
| `extracted.py` | reruns the benches on the extracted netlists at every function point |
| `rc_check.py` | full-RC extraction and DC drop including metal |
| `integration.py` | back-drive fixture with `iso_clamp` |
| `crosscheck.sh` | independent Magic DRC and Netgen LVS from GDS in the librelane canary image |
| `summarize.py` | builds `evidence.json`; a missing input gives `unverified`, never `pass` |
| `pd2_softstart.py` | soft start of the masters at the ten islands' loads |

Physical status of the ten original cells (`isw_{wired,rf,pll,conv,debug}`, four ATB cells, `iso_clamp`):
Magic DRC 0, KLayout DRC 0, LVS match, and the same from GDS in the cross-check image. GDS and extraction
hashes are in `evidence.json:physical`; the four published masters match them (`generated/isw/SHA256SUMS`).

## Open items

Risks: ISL-01, ISL-02, ISL-03, LU-02, LU-03, PDN-05, PDN-07, PDN-08, INT-04, INT-22, MOD-15
(`spec/risk-register.md`).

- `evidence.json` is stale against `design.py`, `layout.py` and `run.sh` (the isolation family was added after
  the run). All GDS and extraction hashes of the ten original cells still match.
- The ATB cells have no published GDS or extraction in the tree; `verification/kl_block_drc_blocks.json` points
  at `scratch/island-support-20261108-075605/` for them, for `iso_clamp` and for the switches.
- `generated/iso-family/iso-placement.json` describes an earlier clamp placement; `pt_chip.conn` is the
  binding in force.
- ATB leaves on the five bias trunk nodes and on `VREF0` of the converter reference are not gated by the
  rail that owns the node (interface row PC-10).
- Soft start at the ten islands' loads was run at 3.3 V with resistive loads only; 3.15 / 3.35 V, the 3.50 V
  supply-trim point and real loads are not run. No cell has a 3.5 V function point.
- Safety cases (default off, 3.63 V leakage, brownout) are schematic only in `evidence.json`.
- Electromigration of the switch straps is a hand calculation (`spec/power-delivery.md` section 2).
- The debug island current is mostly an estimate (`design.py:DEBUG_ESTIMATE_MA`).
- Not done: mismatch and Monte Carlo, ESD/TLP of the switch arrays, `PG` threshold characterisation, ATB bus
  routing and its area.
