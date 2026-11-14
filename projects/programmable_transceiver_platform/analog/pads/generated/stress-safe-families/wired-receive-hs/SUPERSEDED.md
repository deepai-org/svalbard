# Evidence status (PC, 2026-11-14)

Published cell = the STACKED `pad_hspad` (area pass 4 candidate, RX pins made adjacent; build `scratch/pads-core/hspad/b2`,
composer `hs_pad_compose.py --stacked`). GDS sha256 5b7c598e6c32a6aa487129d4a43db3173905ad6f6b7b20343d5e603750d3f679,
model `physical.spice` 320c43d90e70588592c72caa11f8cacf05ccc8f32429d5d6bc90c7345eabc74c. Outline 492 x 912.91 um.
Independent reviews: `scratch/area-pass-4/review/REVIEW.md` (previous candidate), `scratch/pads-core/hspad/REVIEW2.md` (this build: GO with conditions).

Current (on this netlist): pad_hspad.gds, physical.spice, reference.spice, lvs-reference.spice, pad-lvs.txt, layout-screen,
independent-device-audit, config/geometry/marker-merge, lu.json, pad_hspad-kldrc.json, and every `ap4-hspad-*.json`
(safe/HBM 2 kV, HBM 1 kV, CDM-speed surrogate, AC, P/N, RX path, termination, B40 ladder). `shell/` and `leg/` are unchanged inputs.

Historical (PD21 side-by-side netlist, sha 1f1c589d...): every `pd21-hspad-*.json`, `pd21-rl-cob-and-board-compensation.json`,
and the hspad rows of `../pd48-esd-tiering.json` `pd48c`. `pd21-hspad-power.json` (power-up) was not rerun on the stacked cell
(same devices and nets). Backup of the previous published folder: `scratch/pads-core/hspad-backup-published-pd21`.

OPEN DEFECT (inherited from `pt_hs_leg`, also in the PD21 cell; REVIEW2 finding 1/4): the extraction is capacitance-only, so no
bench sees the TERM_VCM metal between the two legs' termination common points: about 34-44 ohm here (1 um Metal4 trunk 25.4 ohm,
two single Via3 9 ohm, Metal3 rails 7-10 ohm; 44-54 ohm in the PD21 cell). What-if with that resistance added: differential
termination tt code 5 is 142 ohm (model 100.8), about 100 ohm only at code 15 (tt) / 12 (ff), 116-123 ohm at ss code 15;
die return loss at 2.4 GHz 6.0-7.1 dB at the best code (model 7.85-8.37). Typical metal values; at the PDK high-resistance
corner (104 mohm/sq, 15 ohm per via) it is 60-70 ohm and tt cannot reach 100 ohm either (117.9 ohm at code 15; second review
`scratch/pads-core/hspad/REVIEW2-addendum.md`). Every termination / return-loss number in the
`ap4-hspad-*` and `pd21-*` files is therefore "model without metal resistance". Fix (leg master: Metal5-strapped trunk,
multi-cut Via3) and R-aware rerun are open.
