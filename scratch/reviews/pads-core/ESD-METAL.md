# Metal resistance in the pad ESD and signal paths (pads owner, 2026-11-18)

Current state. Answers the coordinator's request after evidence-audit row EA-3. Evidence:
`scratch/pads-core/esdcheck/REPORT.md` (independent second and third method, all families),
`scratch/pads-core/hsfix/` and `hsfix2/` (`pad_hspad`), `scratch/pads-core/txr/STATUS.md` (`pad_txpad`).

## 1. The finding is confirmed for every custom pad family

Bond pad to the pad-side primary diodes, ohm, typical / high-resistance metal (Magic tech file values: Metal1-4
90 / 104 mohm/sq, Metal5 40 / 49, 4.5 / 15 ohm per via cut). Three methods that do not share code: hand sum over the
traced segments, Magic `extresist` on the traced nets, a separate 2-D solve; `netres.py` for comparison.

| Cell (published) | Hand | Magic `extresist` | 2-D solve | `netres.py` | Single cuts carrying everything | Verdict |
|---|---|---|---|---|---|---|
| `pad_refpad` | 24.8-26.6 / 46.7-48.8 | 24.7-26.5 / 46.6-48.7 | 24.8-26.6 / 46.7-48.8 | 24.9-26.7 / 46.8-48.8 | 1, then one Via1 per diode | confirmed |
| `pad_wirepad` (USB) | 22.9-26.3 / 38.4-48.4 | 22.9-26.2 / 38.3-48.3 | 22.9-26.3 / 38.4-48.4 | 23.0-26.3 / 38.5-48.5 | 1, then Via1 per diode | confirmed |
| `pad_txpad` | 25.7-27.5 / 47.7-49.8 | 25.6-27.4 / 47.6-49.7 | 25.7-27.5 / 47.7-49.8 | 25.8-27.6 / 47.8-49.9 | 1, then Via1 per diode | confirmed |
| `pad_hspad` (5b7c598e) | 27.7-31.5 / 70-80.5 | 27.7-31.4 / 70-80.4 | 27.9-31.7 / 70-81 | 25.4-26.3 / 65-66 | 4, then Via1 per diode | confirmed, higher than first reported |
| `pad_rf_pair`, `pad_rftxpad` | 28.4-30.6 / 77-79 | 28.3-30.5 / 77-79 | 28.7-30.8 / 77-80 | not run | 4, then Via1 per diode | confirmed |
| `pad_single_leg` | 28.4 / 76.9 | 28.3 / 76.9 | 28.7 / 77.2 | not run | 4, then Via1 per diode | confirmed |
| `pad_tlp_flat` | 0.43 / 0.72 | 0.46 / 0.80 | 0.44 / 0.73 | not run | 0 | not affected |

The return side is built the same way and was in no model at all (2-D solve only, cell level): rail diodes to the
clamp drains 12-20 ohm, VSS diodes to the ring landings 27-50 ohm, clamp sources to the ring 19-39 ohm. Full
discharge loop 56-85 ohm typical.

Where it comes from (all families, same generators):
- `protection_array.py`: one Via1 per diode terminal, 0.48 um Metal2 bars, one Via2, 2 um Metal3 buses. Its own
  report says "single terminal vias are not discharge-current qualified"; that limitation was never closed.
- `wired_protection_layout_ss.py` / the RF route generators: single cuts between the shell trunks.
- `layout.py`: the pad leaves the ring band on ONE Metal2 neck, 4-8 um wide and 330-365 um long (4.0-8.2 ohm),
  because the ring rails occupy Metal3-5 there. The cell VSS meets the ring through two 2 x 2 um stacks.

Consequence at the bond pad, typical metal, added to the published capacitance-only peaks: 31-42 V at 2 kV
(1.33 A), 15-21 V at 1 kV. **No custom pad family meets its HBM tier with resistance included; every
HBM / CDM pass on record is capacitance-only and is not evidence.** For the 8.0 V transient limit the pad side may have
0.8-1.9 ohm at 2 kV and about 4.9 ohm at 1 kV. The TLP site (0.44 ohm) will not show the problem on the bench.

## 2. Signal-path consequences of the same metal

| Cell | Quantity | Capacitance-only | With metal resistance, typ / high |
|---|---|---|---|
| `pad_hspad` published | differential termination, best code | 97-103 ohm | 130-154 / 201-225 ohm (code 15): cannot be trimmed |
| `pad_txpad` published | differential termination, tt / ss / ff (no trim) | 92 / 152 / 58 ohm | 287 / 347 / 253 ohm; high metal 518 / 578 / 484 |
| `pad_txpad` published | bond pad to the 16 output cascodes | 0 | 15.8-19.2 / 32.8-36.7 ohm per leg, one Via4 carries all of it |
| `pad_txpad` published | metal drop at 21 mA output current | 0 | 0.67-0.75 / 1.39-1.49 V |
| `pad_wirepad` published | in series with the 45 ohm HS termination | 0 | about 81 ohm typ (survey, not benched) |

`pad_txpad` fails its termination at ss and ff even without metal (untrimmed, switch-dominated leg).

## 3. What is fixed

| Cell | State |
|---|---|
| `pad_hspad` | Candidate `scratch/pads-core/hsfix/build/f6` (GDS sha 8c8e2533...): leg re-strapped and resized, overlays on the pad, VSS and rail paths in the top cell. Termination passes with resistance extracted (section 4). Bond pad to diodes 5.2-6.0 ohm (was 28-32), VSS return 2.1-3.1 ohm (was 27-58), rail to clamp 0.5-0.8 ohm (was 12-20); no single cut carries more than 3.5 %. HBM with pad-side resistance in the model: 11.6-12.2 V at the bond pad at 2 kV (published cell 38.3-38.9 V), 6.8-7.3 V at 1 kV, no MOS over the 6.0 V screen in either; with the return resistance added by arithmetic about +4.7 V / +2.3 V. **2 kV is not met; 1 kV is marginal.** |
| all other families | Not fixed. |

## 4. Decided layout fix (user decision 2026-11-18, row PC-27)

Overlays cannot go below the Metal2 neck through the ring band (4-8 ohm in every family), and widening the neck costs
about 5 fF per um in the cell plus about 15 fF per um against the ring rails (the existing neck already has about
0.12 pF to the rails that no pad model contains).

**Decided: primary diodes at the bond pad, inside the pad site, tied straight to the ring rails** (down-diodes to ring
VSS, up-diodes to the ring supply; the `pad_tlp_flat` pattern, 0.44 ohm). The neck then carries signal current only
and the core-side network is the secondary stage. Back-feed into an unpowered chip is accepted; the board controls
sequencing. Applies to all seven families, in the order `pad_txpad`, `pad_hspad`, USB, reference, RF pair, RF TX,
single-leg. No family is rebuilt this way yet: candidates are in work under `scratch/pads-core/esdopt/`.

## 5. Rule from now on

Pad evidence uses capacitance and resistance extraction. Tools: `scratch/pads-core/hsfix/netres.py` (validated against
known answers, and against hand / Magic / an independent solver on eight cells) and the per-family model builders
(`hsfix/make_rmodel.py`, `txr/make_rmodel_tx.py`).
