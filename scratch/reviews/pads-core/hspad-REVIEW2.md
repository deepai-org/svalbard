# REVIEW2: stacked `pad_hspad` (staged in `b2/`) - independent review

2026-11-14. Reviewer is not the designer. Nothing in `b2/` or the project tree was modified; nothing published.
Reruns and scripts: `scratch/pads-core/hspad/review2/` (16 MB; the swapped negative-control GDS was deleted after the run). RERAN = done by this review, READ = taken from the designer's artefacts.

## Verdict: GO with conditions

The cell is what STATUS.md says it is (identity, LVS, precheck, geometry, evidence all reproduce) and it closes conditions 1-3 of
`scratch/area-pass-4/review/REVIEW.md`. It is better than the published cell on RX pin placement and on the TERM_VCM path.
One designer claim is wrong by an order of magnitude in the quantity that matters (TERM_VCM resistance between the two legs:
~34-44 ohm, not ~4 ohm). That defect lives in the unchanged `pt_hs_leg` master and is worse (~44-54 ohm) in the published cell,
so it does not argue against replacing the published cell, but it must be written down correctly and fixed or accepted before tapeout.

### Blocking for publish
1. **TERM_VCM statement and termination numbers must be corrected in STATUS / README deltas.** "~4 ohm" counts only the 42 um
   channel crossing. The differential termination current runs through the whole 1 um Metal4 trunk between the two legs'
   single Via3: 282 squares = 25.4 ohm, + 2 single Via3 = 9 ohm, + Metal3 rails and per-unit vias. What-if simulation (RERAN,
   section 4): Rdiff tt code 5 is 142 ohm, not 100.8; 100 ohm is reached only at code 15 (tt) / code 12 (ff) and not at all at
   ss (116-123 ohm); die RL at 2.4 GHz 6.3-7.1 dB at the best code, not 7.85-8.37. The README text deltas (Rdiff, per-corner codes
   6/9/2, "die RL 7.85-8.37 dB", "Termination R identical to published") must be labelled "model without metal resistance" and
   carry these numbers as an open item. No bench sees it (Magic extraction here is C-only).
2. **Register the block.** `pad_hspad` is not in `$P/verification/kl_block_drc_blocks.json`, so `make transceiver-block-kldrc-check`
   says nothing about it (neither CLEAN nor STALE), today or after publish. Add the entry in section 2 with the publish.
3. **Publish together with the floorplan change, or tell assembly first.** `inventory.py` reads the published path. With the mirrored east
   placement the new outline is chip rect x 2993.09-3906, y 735.0-1227.055; in `scratch/chip-assembly-v6/run/floorplan-v6.json`
   `detect` ends at y 735.26 under x 2776-3466, i.e. it touches the edge that now carries every core pin (0 um channel, PAD_HALO is 15 um),
   and `PORT_LABEL['hspad']='RX_P'` still models one pin.

### Blocking before tapeout (leg master, inherited; not a reason to hold this publish)
4. Fix or formally accept the TERM_VCM path in `pt_hs_leg`: widen / parallel the Metal4 trunk (Metal5 strap), multi-cut Via3, wider
   Metal3 rail; or at least extract R on that net and rerun `rterm` / `ac`. EM: both single Via3 carry the full differential signal
   current (section 4). The PAD-side trunk/rail resistance was not assessed here and needs the same look.

### Non-blocking
5. TERM_VCM pin tap is off the midline: 13.8 ohm to the P leg, 11.6 ohm to the N leg (2.2 ohm asymmetry; published was symmetric). Mode conversion estimate <= -40 dB.
6. `lu.json`, `layout-screen.json`, the device audit and the derived `hspad-pn-*.json` / `hspad-rl-b40.json` carry no GDS sha. Derivation was shown by rerun (section 1); not stale.
7. Publish list omits `hspad-pn-ac5.json` / `hspad-pn-ac692.json`, the source of the 15.3 fF pad P/N claim. Add them.
8. Pad P/N C 15.3 fF (published 13.3), RX C 71.3 fF (58.75), leg C +18 fF: as stated by the designer, accepted.
9. AC / rterm benches stop at 3.35 V. At the 3.50 V setpoint the termination is 2.4 % (tt) to 5.5 % (ss, vs 3.15 V) lower, under one trim step (section 6).
10. CDM surrogate 9.03 V at 3 A (> 8.0 V) and 250 V CDM not verified: unchanged from published.
11. `$P/analog/pads/hs_pad_compose.py` is modified and uncommitted (sha 44f44ad2 = `b2/` copy). Commit it with the publish.
12. Unextracted RX series R ~22 ohm per leg (Metal4 74 sq + single Via4 + 0.6 um Metal5 262 sq), equal on P and N, no DC current: negligible (pole > 30 GHz on 190 fF).

## 1. Identity
| Item | Result | |
|---|---|---|
| `b2/pad_hspad.gds` | 5b7c598e6c32a6aa487129d4a43db3173905ad6f6b7b20343d5e603750d3f679 | RERAN |
| `b2/physical.spice` | 320c43d90e70588592c72caa11f8cacf05ccc8f32429d5d6bc90c7345eabc74c | RERAN |
| `b2/reference.spice` | d5608531...; `diff` vs published `wired-receive-hs/reference.spice` empty | RERAN |
| Inputs | `b2/shell.gds` 1f153fd5, `b2/leg.gds` c381962a = published `shell/pad.gds`, `leg/pt_hs_leg.gds`; composer 44f44ad2 = project file | RERAN |
| `b2/pad_hspad-kldrc.json` | gds_sha256 5b7c598e, main 0 / antenna 0; `gds` field is the scratch path (do not copy it, section 2) | READ |
| `b2/independent-device-audit.json` | 508/508; binds physical.spice 320c43d9 and `pad_hspad_flat.spice` 25e8a702; no GDS sha | READ |
| Model <- GDS | re-extraction of GDS 5b7c598e (`review2/lvs/`): device lines identical, 479 C pairs, max difference 0.0 fF vs `b2/pad_hspad_flat.spice`; `physical.spice` = that + wrapper + well diode | RERAN |
| `b2/lu.json` | no sha; rerun `review2/lu.json` is identical (0 um2 uncovered at 15 um, NMOS and PMOS) | RERAN |
| `hspad-safe-hbm.json`, `hspad-hbm-1kv.json`, `cdm-stacked.json`, `bench/*.json` | all carry model sha 320c43d9 | READ |
| `hspad-pn-*.json`, `hspad-rl-b40.json` | no sha (derived from the AC waveforms / a formula) | READ |
No stale record found.

## 2. LVS and KLayout precheck (on the GDS read back from disk)
- `rb_lvs.py` (Magic `gds read` -> extract -> netgen, canary image): **Circuits match uniquely, no property errors, device census 508/508** (`review2/rb/pos/`). RERAN
- Negative control, RX_P/RX_N labels swapped: **Netlists do not match** (`review2/rb/neg/`). RERAN
- Previous reviewer's partial rerun `review2/lvs/` (04:33, flatten flow, same GDS sha): Magic DRC 0, match uniquely. Valid, reused.
- `kl_block_drc.py --gds ... --out review2/kldrc --threads 1`: **main 0 / antenna 0**, gds_sha256 5b7c598e, KLayout 0.30.9, variant D, deep (`review2/kldrc/pad_hspad/kldrc.json`). RERAN

What the checker needs (`check_block_kldrc.py` READ): for every key `name` in `kl_block_drc_blocks.json["blocks"]` it reads
`<directory of that entry's gds>/<name>-kldrc.json` and reports CLEAN only if `gds_sha256` equals the sha of the GDS on disk and `clean` is true.
- Record to write: `$P/analog/pads/generated/stress-safe-families/wired-receive-hs/pad_hspad-kldrc.json`, block name `pad_hspad`.
  The designer's `kl_block_drc.py --gds $G/pad_hspad.gds --top pad_hspad --name pad_hspad --publish` writes exactly that file. Correct.
- Registry entry is missing (no hs pad entry under any name), so the designer's last line `make transceiver-block-kldrc-check` does not test this block. Add:
  `"pad_hspad": {"gds": "projects/programmable_transceiver_platform/analog/pads/generated/stress-safe-families/wired-receive-hs/pad_hspad.gds", "top": "pad_hspad", "owner": "pads"}`

## 3. Geometry (KLayout in the pinned image, `review2/geo/`; RERAN)
- Outline (-0.055, 0)-(492, 912.91); every layer's bbox is inside it. Published: (-0.055, 0)-(478, 1111.25).
- Pad openings (37/0): (7.5,2)-(67.5,62) and (218.5,2)-(278.5,62), XOR vs published 0.
- Ring band y < 426: Metal2 / Metal3 / Metal4 and Via2/3/4 XOR vs published = 0. Metal5 differs only by the PAD_P strap (294,414)-(339,426), 212 um2. Shell region x < 310, y > 426: Metal2-4 identical, Metal5 differs only at the PAD_N strap.
- RX_P label (491.5, 612.75), RX_N (491.5, 618.75), Metal5 81/10, on the x = 492 edge, 6 um pitch, 5.4 um gap, nothing between them.
- In-cell RX routes, P vs N: Metal4 trunk 1.0 um x 74.08 um each (18.5 um of it new); one Via4 each; Metal5 strap 0.6 um x 157.1 um each (area 94.90 um2 both). Mirror-identical about y 615.75.
- Extracted C (recomputed from the re-extraction): RX_P 71.30 / RX_N 71.16 fF (0.14 fF), mutual 3.37 fF; PAD_P - PAD_N wiring 14.55 fF.

## 4. TERM_VCM path
Sheet values: PDK Magic tech `gf180mcuD.tech` (image `hpretl/iic-osic-tools@sha256:8964...`), typical extract style: `resist (allm1..allm4) 90`,
`(allm5) 40` mohm/sq, `contact via3 4500`, `via4 4500` mohm per cut; high corner 104 / 49 mohm/sq. EM limits as the project uses them
(READ, DRM 14.2 via `spec/path-to-tapeout.md`, `timing/lo_rows.py`): Metal1-4 2.09 mA/um, Via 0.58 mA/cut average, 0.87 mA peak for reversing current, 85 C.

Traced net (b2): 25 switch sources per leg -> Metal2 finger -> single Via2 -> Metal3 rail 1 um x 137.5 um (P: y 474.14-475.14, N: y 756.36-757.36)
-> **one Via3** at (332.5, 474.64) / (332.5, 756.86) -> **one Metal4 polygon 1 um wide, x 332-333, y 474.34-757.16** -> pin tap: one Via4 at (332.5, 627.75) -> Metal5 1 um strap to x 492.
There is no other metal on the net.

| Segment | Squares / cuts | Typical ohm | Where it sits |
|---|---|---|---|
| Channel crossing only (y 594.75-636.75), the designer's figure | 42 sq | 3.8 | between the legs |
| Metal4 trunk Via3(P) -> Via3(N) | 282.2 sq | **25.4** (29.4 high) | between the legs: in series with the differential termination |
| Via3, one per leg | 2 cuts | 9.0 | same |
| Metal3 rail + per-unit Via1/Via2, both legs | distributed | ~7-10 (from simulation) | same |
| Pin: Via4 + Metal5 strap | 1 cut + 159.5 sq | 10.9 | common to both legs: common mode only |
| Tap asymmetry: trunk P side 153.1 sq / N side 129.1 sq | | 13.8 / 11.6 | 2.2 ohm leg imbalance |

Published cell, same method (RERAN trace): per leg Metal4 1 um x 120.1 um + 0.5 um x 9 um + one Via4, then 26 um of Metal5: 34.9 ohm, + 2 Via3 = **43.9 ohm**
(candidate 34.4 ohm for the same segments). The designer's "published ~6 / new ~4 ohm" compares only the part outside the legs. The candidate is ~9.5 ohm better and removes two single Via4 from the differential path.

What-if simulation (RERAN, designer's bench, model = `physical.spice` + these resistors, `review2/rvcm/make_model.py`; an estimate, not an extraction):
| Corner, code | Rdiff 100 MHz, model as published (ohm) | with TERM_VCM R (ohm) | die RL 2.4 GHz model / with R (dB) |
|---|---|---|---|
| tt 27 C 3.3 V, code 5 | 100.84 | 142.14 (134.9 with trunk + Via3 only) | 8.07 / 6.01 |
| tt, code 12 / 15 | - / 59.05 | 111.5 / 103.1 | - / 7.01 at code 15 |
| ss 32 C 3.15 V, code 15 | 72.29 | 116.2 (123.0 with high-corner metal) | 9.08 / 6.66 (6.34) |
| ff 22 C 3.35 V, code 8 / 12 / 15 | - | 112.0 / 99.6 / 92.7 | - / 7.09 at code 12 |
- Termination value: +41 to +44 ohm differential. Trim range: tt needs the last code to reach 103 ohm, ss cannot reach 100 ohm (116-123 ohm, outside 85-115).
- Die RL: 0.8-2.0 dB worse at 2.4 GHz than claimed, even at the best code; at the claimed codes 6/9/2 the low band falls to ~13 dB at 625 MHz (claimed 19).
- Mode conversion: 2.2 ohm leg imbalance on ~70 ohm legs gives about -42 dB if the pin is a stiff AC ground, the same order as the 15 fF pad imbalance.
- EM: links are AC-coupled and DC-balanced, so DC current is ~0. Signal current at 0.6-1.2 Vppd into ~110 ohm is +-2.7 to 5.5 mA through each single Via3
  (3-6 x the 0.87 mA reversing-peak figure) and through 1 um Metal4 (1.3-2.6 x the 2.09 mA/um DC figure taken as rms). A DC-coupled common-mode offset of more than
  ~35 mV between the host and TERM_VCM exceeds 0.58 mA in the single pin Via4. The `rterm` bench's 8.9 mA is a test stimulus, not an operating point.

## 5. Evidence plausibility
- AC tt 27 C code 5 rerun with the designer's bench (`review2/bench/rac5-ac.json`): identical to `bench/ac5-ac.json` in every field (Rdiff 100.84 ohm, C leg 1.148 pF, die RL 2.4 GHz 8.07 dB, COB 6.08 dB). RERAN
- HBM 2 kV pad peak 5.035 / 5.346 / 5.413 V, 0/404; published json 5.035 / 5.346 / 5.413. One value differs in the last digit (pulse_P_neg ss 1.223 vs 1.222), so it is a fresh run, not a copy. READ
- HBM 1 kV 4.484 / 4.358 / 4.665 V, 0/404; CDM surrogate 4.800 / 6.983 / 9.033 V, 25 MOS over 6.0 V at 2 and 3 A. Same as published; expected, since shell and leg are unchanged and only ~15 fF of wiring moved. READ
- HBM set not rerun (nothing looked wrong).

## 6. Other
- Polarity: LVS binds RX_P to the PAD_P leg; the swap control fails. Pad openings and PAD_P/PAD_N labels are unchanged, so the bond map is unchanged.
- Chip coordinates (mirrored east, `floorplan.py`: chip = (3906 - y, 1227 - x)): cell rect x 2993.09-3906, y 735.0-1227.055. RX_P (3293.25, 735.5), RX_N (3287.25, 735.5);
  other pins x 3275.75-3307.25 on the same south edge. CTLE (x 2154-2748) is ~540 um west; `detect` is directly south (finding 3).
- Antenna: KLayout antenna deck 0 (RERAN).
- Supply trim: the safe set is at 3.63 V (`ramp_fast` / `ramp_slow` VDD max 3.56 / 3.63 V, peer 3.63 V, 0/404); HBM is unpowered. Termination per leg, code 5, VCM 0.4 (RERAN, `review2/bench/rrt-rterm.json`):
  tt 52.00 ohm at 3.3 V, 50.77 at 3.5 V, 50.11 at 3.63 V; ss 32 C 64.62 at 3.15 V, 61.08 at 3.5 V; ff 22 C 3.63 V 41.38. Rdiff tt code 5: 100.84 / 98.93 / 97.87 ohm at 3.3 / 3.5 / 3.63 V. Die RL moves by +0.1 dB.

## Publish command list (after conditions 1-3)
```
cd /home/ubuntu/svalbard ; P=projects/programmable_transceiver_platform
G=$P/analog/pads/generated/stress-safe-families/wired-receive-hs ; S=scratch/pads-core/hspad
sha256sum $S/b2/pad_hspad.gds $S/b2/physical.spice      # 5b7c598e... / 320c43d9...
cp -a $G scratch/pads-core/hspad-backup-published-pd21
cp $S/b2/{pad_hspad.gds,physical.spice,reference.spice,pad-lvs.txt,layout-screen.json,independent-device-audit.json,config.json,geometry.json,marker-merge.json,lu.json} $G/
# add to $P/verification/kl_block_drc_blocks.json "blocks":
#   "pad_hspad": {"gds": "projects/programmable_transceiver_platform/analog/pads/generated/stress-safe-families/wired-receive-hs/pad_hspad.gds", "top": "pad_hspad", "owner": "pads"}
python3 $P/verification/kl_block_drc.py --gds $G/pad_hspad.gds --top pad_hspad --name pad_hspad --publish --threads 1
grep gds_sha256 $G/pad_hspad-kldrc.json                 # must be 5b7c598e...
cp $S/hspad-safe-hbm.json   $G/ap4-hspad-safe-hbm.json
cp $S/hspad-hbm-1kv.json    $G/ap4-hspad-hbm-1kv.json
cp $S/cdm-stacked.json      $G/ap4-hspad-cdm-surrogate.json
cp $S/bench/ac692-ac.json   $G/ap4-hspad-ac.json ; cp $S/bench/ac5-ac.json $G/ap4-hspad-ac-code5.json
cp $S/hspad-pn-ac692.json   $G/ap4-hspad-pn-ac.json ; cp $S/hspad-pn-ac5.json $G/ap4-hspad-pn-ac-code5.json
cp $S/bench/rx-rxpath.json  $G/ap4-hspad-rxpath.json ; cp $S/bench/rt-rterm.json $G/ap4-hspad-rterm.json
cp $S/hspad-rl-b40.json     $G/ap4-hspad-rl-b40.json
make transceiver-block-kldrc-check                      # must print: CLEAN pad_hspad main=0 antenna=0
```
Then the designer's text steps (SUPERSEDED.md, family table, interface row), with the README deltas corrected per condition 1.
