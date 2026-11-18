# hsfix: pad_hspad TERM_VCM / PAD-side resistance fix + R-aware extraction (netres.py)
Designer notes (second designer; the first died after writing a stub). NOT published, NOT committed. Started 2026-11-14.
Everything is in `scratch/pads-core/hsfix/`. One job at a time, `../dock.sh 'cmd'` (pinned iic-osic-tools image, /work = scratch/pads-core).

## State (update as work proceeds)
- [ ] 1. netres.py written, validated, run on published pad_hspad and the other families
- [ ] 2. leg fix (hs_leg_layout.py option) + composer trunk
- [ ] 3. verification of the fixed cell
- [ ] 4. R-aware evidence
- [ ] 5. final summary

## PDK resistances used (Magic tech /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.tech, sha256 f0c3a445..., pinned image)
- typical, `variants ()` (line 3310): `resist (allm1..allm4) 90` mohm/sq (lines 3341-3345), `(allm5) 40` (3347); `contact m2c 4500` (Via1, 3355), `m3c 4500` (Via2, 3356), `via3 4500` (3357), `via4 4500` (3358) mohm per cut
- high, `variants (hrhc),(hrlc)` (line 3361): Metal1-4 104 (3390-3394), Metal5 49 (3396); m2c / m3c / via3 / via4 15000 (3404-3407)

## Log
- netres.py written; validation `../dock.sh 'cd /work/hsfix && python3 val/make_test.py && python3 netres.py --gds val/test.gds --top T --spec val/spec.json --out val/result.json --tech /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.tech; python3 val/check.py'` -> VALIDATION PASS (val/check.txt)
- option (a) Magic extresist attempt on the published flat cell: `extresist/run.tcl`, log `extresist/run.log` (timeout 40 min)
- Magic extresist (option a) RAN on the published flat cell without a segfault (Magic 8.3.678 of the pinned image, 48249 R, about 1 min):
  `extresist/run.tcl`, `extresist/pad_hspad_rc.spice`, `rcnet.py`. TERM_VCM leg P sources <-> leg N sources (shorted groups) = 40.36 ohm typical.
  BUT it lumps device terminals on big nets (all 12 PAD_P diodes, the 25 heads and both MIMs sit on 1-4 `.tK` nodes; "Missing terminal connection" for 4 devices;
  RX_P gets 3 terminals, RX_N 4), so it cannot answer pad -> device questions. Usable as a cross-check on small nets, not as the pad-flow answer.
- netres.py on the PUBLISHED pad_hspad (GDS 5b7c598e): `python3 spec_hspad.py > res/spec_hspad.json`;
  `../dock.sh 'cd /work/hsfix && python3 netres.py --gds /proj/analog/pads/generated/stress-safe-families/wired-receive-hs/pad_hspad.gds --top pad_hspad --spec res/spec_hspad.json --out res/published.json --only TERM_VCM,RX_P,RX_N,VBIAS,VDD'`
  and `--out res/published_pad.json --only PAD_P,PAD_N,VSS`. Results (typ / high, ohm):
  | Net, path | typ | high | note |
  |---|---|---|---|
  | TERM_VCM leg P sources <-> leg N sources (shorted) | 39.91 | 68.99 | reviewer 34-44 / 60-70; Magic extresist 40.36. 1 um Metal3/Metal4, 2 single Via3 carry 100 % |
  | TERM_VCM same, each source through 1 kohm (distribution along the rail) | 44.20 | 72.22 | |
  | TERM_VCM pin <-> P / N sources | 31.91 / 29.73 | 58.55 / 56.03 | 2.2 ohm asymmetry |
  | PAD_P bond pad <-> 25 resistor heads | 16.44 | 36.71 | NEW: of this 11.49 / 25.28 is in the SHELL (bond -> composer strap): Metal2 escape, Metal4 trunk, ONE Via4 at (288, 416) carrying 100 % |
  | PAD_N bond pad <-> 25 heads | 16.82 | 37.27 | shell part 12.80 / 26.97, ONE Via4 at (304, 432) |
  | PAD_P / PAD_N composer strap -> heads (leg part) | 4.95 / 4.02 | 11.42 / 10.29 | 2 um Metal3 rail fed from one end, 3 Via3 |
  | PAD_P / PAD_N strap -> MIM bottom plates | 11.79 / 10.86 | 32.78 / 31.65 | each MIM through one 0.4 um Metal2 riser + single Via2/Via3 stack |
  | PAD_P bond pad <-> the 12 ESD diode terminals (shorted) | 25.39 | 65.23 | NEW, SHELL/NETWORK: single Via4 (288,416), single Via4 (288,480), single Via3 (186,480), 2 um Metal3, one Via1 per diode. PAD_N 26.33 / 66.34 (Via4 (304,432), (304,500), Via3 (190,500)) |
  | RX_P / RX_N pin <-> MIM top | 38.84 / 38.82 | 84.87 / 84.84 | reviewer estimated 22; no DC current |
  | VBIAS pin <-> RB (P / N) | 37.8 / 32.6 | 83.4 / 77.3 | in series with 40 kohm: irrelevant |
  | VDD pin <-> leg devices (P / N) | 28.6 / 26.1 | 54.0 / 51.0 | clamps only, no current |
  | VSS shell return <-> leg taps (P / N) | 2.64 / 12.99 | 4.85 / 17.32 | guard/clamp only; VSS pin strap 15-19 ohm (single Via4) |
- `hs_leg_layout.py --legacy` regenerates the published leg: `./leg.sh leg_legacy --legacy`; `xor.py tmp/leg_pub.gds pt_hs_leg build/leg_legacy/pt_hs_leg.gds pt_hs_leg` -> TOTAL XOR 0 on every layer (file sha differs: timestamps). Leg-level KLayout note PP.2 x 20 is the same as in the published layout-info.json.
- NEXT: `./leg.sh leg1` (R-fixed leg, units 2.0 / 1.0 um), then `./build.sh f1` (composer), netres on the fixed cell, then checks and sims.
- Sizing study (schematic units + lumped metal): `presize/presize.py Lb Lt` (in the image). With the shell's 7-8 ohm per leg still in series the published unit sizes cannot meet "100 ohm with 2 codes margin" (tt 9.4, ss 13.4, ss/high metal > 15), so the unit poly lengths were shortened: base 3.05 -> 2.0 um, trim 2.0 -> 1.0 um (PDK minimum). DEVICE CHANGE, see final section.
- Builds so far (all in `build/`): leg1/f1 (overlays, units 2.0/1.0), leg2 (extra via1/via2 on the TU units: Magic DRC 100 x M1.2a, notch between two via pads on the resistor heads, fixed), leg3/f3 (clean, units 2.0/1.0).
  f3 R-aware termination (`./term.sh ...`, `python3 termtab.py pubc pubrt pubrh f3c f3rt f3rh`): 100 ohm at codes 2.0 (ff 22/3.63, typ metal) ... 10.2 (ss 32/3.15, high metal): lower margin only just 2 codes,
  so base poly length goes 2.0 -> 2.6 um to centre the range. NEXT: `./both.sh leg4 f4`, netres (`spec_hspad.py build/f4/config.json`, `spec_tu.py`), `make_rmodel.py`, `term.sh`, then checks + evidence on f4.
- FINAL CANDIDATE = `build/f4` (leg `build/leg4`, units base 2.6 um / trim 1.0 um): `./both.sh leg4 f4` -> Magic DRC 0, composer LVS match, device audit match, bbox (-0.055,0)-(492,912.91).
  `./rflow.sh f4 leg4` (netres main + TU nets, models `models/f4_r_{typ,high}.spice`), `./term.sh f4rt=models/f4_r_typ.spice f4rh=models/f4_r_high.spice f4c=build/f4/physical.spice`, `python3 termtab.py f4c f4rt f4rh`:
  100 ohm differential at codes 3.4 (ff 22/3.63, typ metal) ... 11.6 (ss 32/3.15, high metal). Published cell R-aware: 128.8-153.8 ohm at code 15 (typ metal), 200-225 ohm (high): no code reaches 100 ohm.
- RUNNING: `./checks.sh f4` (rb_lvs pos / neg, KLayout precheck, LU, XOR vs published) -> `checks/progress`, logs in `checks/`. NEXT: other-family surveys (`survey.sh`), then AC / RX / HBM / CDM benches on f4 and the comparison table.
- f4 KLayout precheck FAILED: V4.2b x 1376 (via4 arrays larger than 3 x 3 need 0.36 um spacing; the composer's arrays used a 0.6 um pitch; Magic DRC does not check it). Record kept in `checks_f4/`. Fixed in `hs_pad_compose.py` (0.7 um pitch).
- FINAL = `build/f5` (same leg `build/leg4`): `./final.sh leg4 f5` (compose, rflow, term bench, checks). ALL LAYOUT CHECKS PASS:
  Magic DRC 0 (`build/f5/extract.tcl.log`), composer LVS match + device audit match (`build/f5/layout-screen.json`), rb_lvs pos "match", netgen unique, census 508/508 (`checks/rb/pos/result.json`),
  rb_lvs neg (RX_P/RX_N labels swapped) "Netlists do not match" (`checks/rb/neg/result.json`), KLayout precheck CLEAN main 0 / antenna 0 (`checks/kldrc/pad_hspad/kldrc.json`, sha 57035834),
  LU 0 / 0 um2 uncovered at 15 um (`checks/lu.json`), XOR vs published in the ring band y < 426: only Via4 (the 288-cut array at the PAD_P shell exit), Metal2/3/4 = 0 (`checks/geo.txt`).
  sha256: `build/f5/pad_hspad.gds` 5703583468d5c3b626d99b0cbba71877af847721dde522768a1d734b838809c6, `build/f5/physical.spice` cbe53833ae840bfa8e476a69dd80e1839cd569dab5fb76dd36cb0eea151b30ba,
  `models/f5_r_typ.spice` 77c900613d830aca1cf07cb16c9782b06eb74114e43706428d08d8fee6c5e259, `models/f5_r_high.spice` 04712e2f25eb29c9e22ef4c2ff0afa29655a97e8beed3d8de31a7afbef9f2f63, `build/leg4/pt_hs_leg.gds` 9229a29419baa34167b938d38bf0db7d16dc92ed0ffbd5fb33e4c5c76878cd84.
- NEXT: other-family surveys (`./survey.sh ...`), then `./sims.sh f5` (AC, RX path, safe/HBM 2 kV, HBM 1 kV, CDM surrogate on C-only and R-aware models; progress in `sims.progress`), then the table.
- Other families surveyed (`./survey.sh <family> combined.gds <tag> NET...` -> `res/{ref,usb,usb2,tx}.json|.log`; `rterm_list.py`, `rgroup.py` for per-terminal / group figures). Findings are in the final section.
- RUNNING: `./sims.sh f5` (started after the surveys; `sims.progress`). Order: ac + rxpath for pubc / pubrt / pubrh / f5rt / f5rh / f5c, then safe+HBM 2 kV, HBM 1 kV, CDM surrogate for f5 C-only, f5 R-aware (typ), published R-aware (typ).
  If it dies: rerun `./sims.sh f5` (stress_safe_clamp.run resumes only identical decks; .dat files are deleted after each part, so finished parts rerun).
