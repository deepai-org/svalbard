# Independent review: pad_rftxpad t7 (PC-81), 2026-11-24 — LIGHT scope

Scope changed partway through (user via coordinator): the ESD target is now the basic handling class only (HBM 1 kV / CDM 1 A),
and signal matters more than ESD margin. This review was cut down to checking for shorts, LVS or DRC problems and for any regression vs t2.
I did not do the full R+C re-extraction, the CDM 2 A run, the current-density runs or my own pad C.

## Verdict: GO with conditions (layout); ESD only partly reviewed

My layout checks on the published GDS are all clean. Its sha matches the evidence file.
The HBM 1 kV / CDM 1 A pass is still only the authors' claim. It comes from the lumped model (t2 model + lumped band), which this review did not replace.

## What I ran (all outputs here; GDS copied to b/t7.gds, sha256 835fc848…1316 = evidence pad.gds)
| check | result | evidence |
|---|---|---|
| Magic DRC (flattened) | 0 | chk/t7/summary.txt |
| Floating nets in the Magic extraction | 1 (t2: 1), no increase | x/t7/pad_rftxpad_flat.spice |
| Read-back LVS vs rf-tx/reference.spice | match uniquely | chk/t7/rbx/rb_pos.log |
| Negative control: VSS<->ESD_RAIL label swap | mismatch (fails as it should) | chk/t7/rbx/rb_neg.log |
| Negative control: reference with one band up-diode (DBPU5) dropped | mismatch (fails as it should) | chk/t7/rbx/d1 |
| KLayout precheck (kl_block_drc) | main 0 / antenna 0 | chk/t7/kl |
| rail_site_check (rail cells at x 0, 211) | PASS (main 0, antenna 0) | chk/t7/rail |
| Latch-up, 15 um | 0 / 0 um2 | chk/t7/lu.json |

Device census from the flat netlist matches the design: per leg 10 pd2nw PAD->ESD_RAIL (6 band + 4 core) and 10 nd2ps VSS->PAD (4 site + 2 band + 4 core); 4 rail nd2ps diodes; 634 nfet_06v0 clamp fingers.
rail_site PASS with the provider rail cell over the sites means the Metal5 VSS strap overlap (depth 343-348.39) passes DRC/antenna there.
That check does not prove net identity, though, and the railcap extraction that would have confirmed it is DVSS failed (F2).

## Findings
| # | sev | finding | evidence |
|---|---|---|---|
| F1 | medium | The published ESD numbers (HBM 1 kV 6.15 V, CDM 1 A 8.64 V high metal) come from the t2 lumped model + a lumped band (mkmodel_band.py). P and N band cathodes share one 0.59 ohm resistor, and the core-network ESD_RAIL resistances (33.5 / 37.7 ohm) are hand-entered from an old report (mkmodel.py `ER`). MANDATE 4a says hand-entered lumped R is not evidence. There is margin: 6.15 V vs 11 V, and 8.64 vs 10.5/11 V. A full extraction is unlikely to flip the pass, but the claim is unverified. | ../mkmodel.py, ../mkmodel_band.py, ../models/t7_high.spice |
| F2 | medium | I could not reproduce the pad C. My railasm step through dock.sh produced no asm.gds, so the extraction ran on an empty cell; I did not debug it under the reduced scope. The +0.37/+0.38 pF per leg (over the +0.3 pF RF limit, an accepted miss) stays the authors' number. | cap/t7/asm.tcl.log |
| F3 | low | No C cross-check per net (MANDATE 4a) exists for the published physical-r models: the band wiring C is a single lumped capacitor at the bond. | pc81 evidence `misses_and_conditions` |
| F4 | info | ESD vs t2 (authors' model, read only): every positive case improves (HBM 1 kV 13.3 -> 6.15 V). Negative cases were already fine. No regression seen in the authors' data. | ../esd/t7h.json, t2h.json |

## Not run / read only
- Full netres + Magic R+C re-extraction, bench known-answer / negative controls, HBM/CDM matrix on an independent model, CDM 2 A, cur.py density: not run (scope cut).
  Prepared but unused: tools/probe.py, ref_drop1.spice. Planned method: netres auto_contacts per diode diffusion with the reduced_network, mapping flat-netlist diodes to geometric fingers by class counts.
- Pad C with the rail cell: attempted, failed (F2).
- t8 (4 up-diodes): if it replaces t7, rerun `./chk.sh t8 <reference> <drop1 reference>` here after copying the GDS to b/t8.gds.
