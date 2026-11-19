# Die fit per chip (state of 2026-11-19, after the two-chip split)

Each chip has its own fixed die 3.932 x 5.122 mm (core 3028 x 4218 um = 12.772 mm2) on its own wafer.space slot.
**Both chips fit, as built, with every block placed, the full 5.4 nF decap plan (D9) and the routing channels:
margin after routing `pt_rf` +0.8 mm2, `pt_wired` +2.2 mm2 (targets met: +1.9 / +2.8; lower bounds: +3.3 / +3.5).**
These are packer placements of measured outlines (no top-level wiring); the macro outlines come from synthesis of each
chip configuration, not from place and route.

Work directory `die-fit/`, one run per chip: `chip.sh <rf|wired>` = `ledger.py` (per-instance rows of
`integration/chips/<chip>/chip.conn` + booked items, measured outlines from `meas/measured.json`) -> `decap.py` (5.4 nF
plan) -> `ledger.py` (tiles booked) -> `fit.py` (packer, scenarios S / T / LB, 12 trials each) -> `overheads.py`
(routing, grid) -> `summarize.py`. Outputs: `<chip>/ledger.{md,csv,json}`, `<chip>/overheads.json`, `<chip>/summary.json`,
`run/<chip>/fit-{s,t,lb}.{json,png}`, `decap.json`, `macro.json` (macro outlines). The chip floorplans are made by
`integration/assembly/floorplan.py`, which runs `fit.py` (S) with the real pad-cell footprints (`PADS_JSON`) and the GDS
outlines (`SIZES_JSON`) instead of the modelled ones.

## 1. Ledger (mm2; S = as built, T = targets, LB = lower bounds)

| | `pt_rf` S / T / LB | `pt_wired` S / T / LB |
|---|---|---|
| digital macro (outline from synthesis, `macro.json`) | 2.155 / 2.155 / 1.823 | 2.666 / 2.666 / 2.317 |
| custom pads, occupied core intrusion | 0.931 / 0.931 / 0.637 | 1.450 / 1.347 / 1.247 |
| analog blocks in the conn | 5.753 / 4.945 / 4.237 | 2.586 / 2.254 / 1.960 |
| booked items (incl. decap bank 0.39 and tiles) | 0.886 / 0.886 / 0.886 * | 1.866 / 1.866 / 1.802 * |
| **block demand** | **9.724** / 8.917 / 7.583 | **8.568** / 8.133 / 7.326 |
| of it estimates (E rows) | 3.092 | 4.451 |
| raw margin against the core, before channels and scrap | +3.05 / +3.86 / +5.19 | +4.20 / +4.64 / +5.45 |

`*` the ledger books the S tile area in every column; the packer uses each scenario's own tile count (section 2).
`pt_rf` carries both rings (D1, D2: TX ring for the host / converter clocks, CDR ring as the second host-clock route) and
the AUX pair (D3); `pt_wired` carries the TX ring, the CDR ring and the AUX pair as well. `core_bias` is the single-die
composite on both (0.302; per-chip bank lists are D8 / D-SPLIT-BIAS). Booked on `pt_wired`: new transmit path,
second slicer / capture / blender, CTLE followers, T-coil reserve, forwarded-clock repeaters; on `pt_rf`: LNA additions,
VCM buffer; on both: D2H strip, RF / host time base, decap bank and tiles.

## 2. Decap, full 5.4 nF plan on each chip (`decap.json`)

| nF (S / T / LB) | `pt_rf` | `pt_wired` |
|---|---|---|
| macro-edge bank (0.39 mm2) | 1.5 | 1.5 |
| grid MIM over the block outlines (measured Metal4/Metal5-free area, plates on 55 %) | 1.54 / 0.99 / 0.56 | 0.65 / 0.43 / 0.22 |
| macro row fill (0.45 nF at 2.814 mm2, scaled) | 0.34 / 0.34 / 0.29 | 0.43 / 0.43 / 0.37 |
| bond-site tiles (0.45 nF for 24 custom sites, scaled) | 0.23 | 0.26 |
| **stacked MOS + MIM tiles for the rest** (4 fF/um2) | **1.79 / 2.34 / 2.83 nF = 0.45 / 0.58 / 0.71 mm2** | **2.57 / 2.78 / 3.05 nF = 0.64 / 0.70 / 0.76 mm2** |

The tiles are placed by the packer as 125 x 120 um blocks after every other block (they take the holes). The power-
delivery model (PD2) has not been rerun per chip with each chip's macro current (D9 asks for it).

## 3. Packing (`run/<chip>/`, `summary.json`)

| chip / scenario | macro um | blocks to place | placed / unplaced | channels (halo) | free | usable >= 60 um | scrap | routing beyond channels | **margin** | relaxed |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| `pt_rf` S | 1716 x 1256 | 6.611 | 209 / 0 | 0.871 | 1.750 | 1.277 | 0.473 | 0.44 | **+0.84** | - |
| `pt_rf` T | 1716 x 1256 | 5.803 | 209 / 0 | 0.838 | 2.606 | 2.278 | 0.328 | 0.35 | **+1.93** | - |
| `pt_rf` LB | 1716 x 1062 | 5.095 | 204 / 0 | 0.769 | 3.993 | 3.708 | 0.285 | 0.42 | **+3.29** | - |
| `pt_wired` S | 1716 x 1554 | 4.362 | 216 / 0 | 0.614 | 3.249 | 2.885 | 0.364 | 0.70 | **+2.18** | wrx_cap |
| `pt_wired` T | 1716 x 1554 | 4.031 | 214 / 0 | 0.585 | 3.725 | 3.492 | 0.233 | 0.71 | **+2.78** | wrx_cap |
| `pt_wired` LB | 1716 x 1350 | 3.673 | 210 / 0 | 0.537 | 4.568 | 4.256 | 0.312 | 0.74 | **+3.52** | wrx_cap |

- Margin = free core that still takes a >= 60 um block, minus the routing that the halo channels cannot carry at
  realistic pitch (control at minimum pitch, data / clock / analog at double pitch, `overheads.py`). Pads at their
  `bond_map.txt` sites (provider bond centres); macro on the north edge under the H2D pins; D2H strip and N-S corridor
  as before.
- **Keep-away rules: 0 failures on both chips**, including the INT23 QVCO rule (spirals >= 1.7 mm from the west edge and
  >= 1.0 mm from the RF_TX pads), macro to LNA >= 1000 um (1112 um in S), rings to QVCO >= 500 um, aosc to ADC. On `pt_rf`
  the external-LO pads are on the east edge, 2.1-2.6 mm from RF_RX.
- Pad cells sit at their measured offset from the site midpoint (`OFS` in `fit.py`); the `pt_rf` runs predate that
  correction (12-60 um along the edge, no overlap in the `pt_rf` skeleton; rerun with `chip.sh rf` when next touched).
- Relaxed: `wrx_cap` cannot get within 500 um of the `wired_cap` switch with its partners (G6 rule); the
  island strap needs to be wider there or the switch moves (owner, phase 4).
- `pt_wired` forwarded wire clock (AUX_CLK pair on the west edge to the CDR): 2 x 1.9 mm in S. Moving the AUX pair to the
  east edge would shorten it but needs an east site pair (all twelve are used): phase 4 item.
- Macro outlines are synthesis estimates scaled at the r8d density (79.5 %); a +10 % macro costs about 0.2 mm2 (rf) and
  0.27 mm2 (wired) of margin.

## 4. What this does not show

- No top-level wiring: routing is an estimate on channels, and blocks may have to give Metal3 crossing (DF-12).
- `pt_rf` is the tighter chip (QVCO 0.53, ADC pair 0.90, bbfilter pair 0.68, `lo_vreg` 0.44, both rings, probe frames):
  a 10 % growth of its analog blocks (0.58 mm2) or of its estimates (3.1 mm2 of E rows) eats most of the as-built margin.
- Grid MIM uses the measured Metal4/Metal5-free area of each block outline; the bank and tiles are not drawn.
- The per-chip supply plan (which supply bond feeds which island switch, `G4` in `fit.py`) is a placement assumption,
  not a power-delivery result.
