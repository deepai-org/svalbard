# esdopt/usb: pad_wirepad (USB) under ESD option A. NOT committed, NOT published.
Started 2026-11-20. Brief: rebuild `pad_wirepad` with pad-site primaries tied to the ring rails (PC-27), no core array, local
secondaries where devices miss, HS termination 45 ohm per leg incl. metal, to a reviewable candidate.
Rules: ONE simulation at a time, OMP_NUM_THREADS=1; generator edits only behind options whose default rebuilds the published cell
(XOR 0 vs `$P/analog/pads/generated/stress-safe-families/wired-receive-usb/combined.gds`, sha 4e4b9d92...); intermediates deleted.

## Pass limits (declared 2026-11-20 before any run; not to be moved)
Layout
- L1 Magic DRC 0 (flat cell). L2 read-back LVS on the GDS from disk "match uniquely" vs the generator schematic AND a failing control
  (PAD_P/PAD_N or RX_P/RX_N swap -> mismatch). L3 KLayout precheck main 0 / antenna 0 (cell). L4 latch-up 0 um2 uncovered at 15 um.
- L5 `rail_site_check.py` PASS for the candidate on the provider rail cell (and `--selftest` OK).
- L6 floating nodes (`**FLOATING` / node without device) not above the published cell's count (counted the same way on both).
- L7 default path: the generator command of the published cell (`stress_safe_compact_layout.py wired_receive_usb <w> network-gc-d2
  usbfix6v2lsm 14`) with no new option: KLayout XOR 0 against the published combined.gds.
- L8 outline inside the published one (2.78..524 x 0..1434.72 bbox as measured on the published GDS the same way) and ports as published
  plus any new ring port (DVDD), stated.
ESD (R+C model of the exact GDS incl. return side; ring at the extracted bound of ../ring/esd3.py, SITECAP 1 nF at the east-edge site
behind 0.7 ohm per rail; typical and high-resistance metal)
- E1 every MOS max(|Vg-x|, |Vds|) <= 8.0 V (6 V oxide) / 5.0 V (3.3 V oxide) transient; DC screens 6.0 / 3.63 V reported as counts.
- E2 non-primary junctions reverse < model bv (nd2ps_06v0 11 V, pd2nw_06v0 10.5 V; others: model bv as found).
- E3 primary site diodes: peak current per finger width <= 10 mA/um forward, <= 1 mA/um avalanche.
- E4 MIM <= 6.0 V.
- Requirement points: HBM 2 kV (1.33 A; USB tier) all cases (P/N +/- vs VSS, +/- vs VDD, P vs N both signs); CDM surrogate 2 A 1 ns with
  the 1 nF SITECAP; 1 A and 3 A reported (not pass/fail). HBM 1 kV reported.
- Bench proofs before real runs: known-answer (resistor in place of the pad) and a failing negative control (site diodes stripped).
Functional (R+C models, typical and high metal)
- F1 HS termination: per leg 45 ohm +/- 10 % (40.5..49.5, the published window) INCLUDING metal at some trim code, at all 23 corners
  (tt/ss/ff/sf/fs x 22/32 C x 3.15/3.35 V + ss 3.50 V), typical and high metal. P-N at the chosen code reported.
- F2 FS / LS drivers and pull-ups not worse than published (pd47-usb-ls-miller.json): FS edges 4-20 ns into 50 pF, VOH >= 2.8 V,
  VOL <= 0.3 V; LS_SLOW edges 75-300 ns (published 94.7-201 ns); pull-up as published; benches on the R+C model.
- F3 pad capacitance per leg (same bench and corners, like for like): candidate R+C model WITH the rail cell <= published R+C model WITH
  the rail cell + 0.3 pF (published number stated incl. its under-rail term).
- F4 USB HS eye / return loss: only if a bench exists; else reported "not run".

## Log
- Default path baseline: `stress_safe_compact_layout.py wired_receive_usb build/def0 network-gc-d2 usbfix6v2lsm 14` (image b6027809) rebuilds the
  published cell: KLayout XOR 0.0 um2 vs `combined.gds` (top `pad_wirepad`, = `tx_with_primary` of the build). Published model: 1 `**FLOATING` line.
- Published R+C (new, `rflow.sh` = mkspec_usb.py + netres.py on the published GDS -> `rpub/`, `mkmodel_usb.py` -> `models/pub_r_{typ,high}.spice`,
  self-check x0.01 `models/pub_zero.spice`): HS termination per leg at tt 27 C 3.3 V, codes 0..7: C-only 55.7 .. 38.7 ohm (bench known answer =
  pd43 cal-raw.json exactly), x0.01 57.6 .. 40.2, **typical metal 248 .. 188 ohm (P), 255 .. 165 ohm (N)**: the published termination is
  4-5x off with metal (the trim nets alone are 80-190 ohm: 8 single cuts in series per unit). The "81 ohm" survey figure was TERM_VCM only.
- Design (option A, all behind `--esd-a`, default unchanged): no protection-network macro; pad-site primaries (`pad_site_primary.py`, 5 + 5
  fingers, neck (33.5, 41.5) = Metal2 neck widened 4 -> 8 um, VSS bridge to the shell's VSS strip x 9-11); the HS termination (TERM_x poly, 10
  switches, 3 trim units per leg; same devices) leaves the device grid and is drawn as a low-R block per leg in y 352-395 just above the ring band,
  fed from the neck by a Metal2/3/4 PAD rail; sources on 0.8 um Metal2 bars to a Metal3/4/5 TERM_VCM rail, a 40 um Metal4/5 strap (x 253-293) and a
  Metal3/4 bar at the top edge into the TERM_VCM trunk 0.5-7 um below its pin; gates / TERM_x_R / trim on Metal2 risers + Metal3 rows into the
  grid trunks. Grid height kept (ports at the published y). Generators: layout.py `usb_term_block`, wired_protection_layout_ss.py `esd_a`,
  stress_safe_compact_layout.py `--esd-a[=JSON]` (keys tb / site / term_poly / trim_poly).
- Bench proofs: ESD `esd_usb.py` (= ../ring/esd3.py + site currents, bound ring 0.155/0.189/0.46/0.57, far 5+7, SITECAP 1 nF / 0.7 ohm per rail):
  2 ohm toy 2.899 V at 2 kV (hand 1.3243 A x 2.189 ohm = 2.899), 4.378 V at CDM 2 A (hand 4.378). Termination `tbench.py` known answer above.
- Later builds: CDM 2 A screen on the 5+5 site (b1, high metal) MISSED: pad 10.7 V, 32 MOS over 8.0 V (HS isolates / bypass with source or drain
  on the pad, trim switches behind their poly). Model what-if (+3 pd2nw per pad): worst 7.3-7.5 V. Added `pad_site_primary.py` option
  `n_up_left` (default 0 = unchanged): 3 pd2nw fingers left of the neck, tap bar joined to the VSS strip, DVDD band-134 landing over the neck.
  Poly re-centred for the block metal (base 16 x 1.16 um, trim bit-0 4 x 1.2 um; from a fitted model of the C-only table). No secondaries
  were needed. Fixes on the way: neck Metal1 kept inside the rail cell's p-tap frame lines (b3 shorted PAD to VSS under the rail), via-array
  pitch 0.7 (V2.2b / V3.2b), strap Metal5 in two stripes (MSLOT5.1), read-back LVS on a flattened copy (site primitives are subcells).
  Superseded builds b1-b4 and their models / benches deleted.

## CANDIDATE b5 (2026-11-20). NOT published, NOT committed.
GDS `build/b5/pad/combined.gds` (top `tx_with_primary`) sha256 44c7f42471ed...; physical.spice 8337dec4f210; models `models/b5_r_{typ,high}.spice`
630598e4 / 51a03274, `_rail` ac54c6f6 / 8640ed0e. Generators (all uncommitted edits, defaults unchanged): layout.py b4ee7fa4, wired_protection_layout_ss.py
dbfaac63, stress_safe_compact_layout.py a28c740e, pad_site_primary.py 4a3b087f.
Command: `build.sh b5 '--esd-a={"term_poly": [16, 1.16], "trim_poly": [4, 1.2], "site": {"n_up_left": 3}}'` (= stress_safe_compact_layout.py
wired_receive_usb <w> network-gc-d2 usbfix6v2lsm 14 --esd-a=...), then `q.sh b5` (rmodels.sh, railmodels.sh, tbench.py, esd_usb.py, padc_usb.py,
fbench.py, checks_usb.sh); published references `q_pub.sh`. Tables: `ttab.py b5rt b5rh`, `esdtab.py b5rh b5rt`.

| Limit | b5 | Result |
|---|---|---|
| L1 Magic DRC (base / combined) | 0 / 0 | PASS |
| L2 read-back LVS pos / composer schematic; controls RX swap / site diode missing | match / match; mismatch / mismatch | PASS |
| L3 KLayout precheck main / antenna; sliver control | 0 / 0; M1.1 + NP.5a + DF.14_LV reported | PASS |
| L4 latch-up uncovered at 15 um; isolated-nmos control | 0.0 um2; 6.4 um2 | PASS |
| L5 rail_site_check / --selftest / pad-on-rail precheck / railconn | PASS / OK / 0 / clean (DVDD only on DVDD bands) | PASS |
| L6 floating lines (published 1) | 0 | PASS |
| L7 default path XOR vs published (final generator shas) | 0.0 um2 | PASS |
| L8 outline / ports | bbox (2.78, 0)-(315.64, 1434.72) inside published (.. 524); ports as published, ATB_ESD_RAIL removed (no network), DVDD added; area 272,803 um2 (ceiling 340,000) | PASS (port change stated) |
| E1 HBM 2 kV, 10 cases, high / typ | worst 5.65 / 5.13 V (nfet_06v0, P+N), 0 over | PASS |
| E1 CDM 2 A + SITECAP 1 nF / 0.7 ohm, high / typ (requirement) | worst 7.66 / 6.90 V (nfet_06v0, P+N), 0 over | PASS (0.34 V margin high) |
| CDM 1 A / 3 A (report) | 1 A 4.99 V PASS; 3 A 10.27 V high (43 over), 9.18 V typ (37 over) | report |
| HBM 1 kV (report) | 4.13 V | report |
| E2 non-primary junction reverse < bv | 0.0 V (antenna diodes never reverse-biased in these cases) | PASS |
| E3 site fingers fwd <= 10 / avalanche <= 1 mA/um | HBM 2 kV 4.25 / 0.009; CDM 2 A 6.43 / 0.048 (3 A: 9.66 / 0.06) | PASS |
| E4 MIM <= 6 V | HBM 2 kV 5.02 V (Miller caps) | PASS (0.98 V margin) |
| ESD bench proofs: 2 ohm toy; site diodes stripped | 2.899 V (hand 2.899), CDM 4.378 (hand 4.378); stripped: 84.7 V gate, 107 over | PASS |
| RX_P/N (info; consumers pt_rxselect / wmon_sel / detect, oxide not checked) | RX-VSS 0.82 V, RX-VDD 4.07 V CDM 2 A high | info |
| F1 HS termination 40.5-49.5 ohm per leg incl. metal, 23 corners, typ / high | every corner has codes in window (ss 6-7, ff 0-2, tt 2-5); P-N 0.8 ohm | PASS |
| F1 known answer / self-check / TERM_ENABLE 0 | published C-only 55.69..38.72 = pd43; x0.01 model 48.7..34.0; off: pad held at 4.15 V by the up-diodes at 8.9 mA | PASS / info |
| F2 FS edges 4-20 ns, 50 pF | fall 6.2-9.1 ns, RISE 19.5-24.9 ns (published with metal 21-29 ns; C-only 5.9-11.3) | **MISS** (FS high-side metal, grid, not reworked) |
| F2 VOH / VOL; LS_SLOW 75-300 ns; pull-up | 3.11 V / 0 V; 103-282 ns (published with metal 105-331); pull-up 2.78-3.06 V = published | PASS |
| F3 pad C per leg, R+C with rail, vs published R+C with rail + 0.3 pF | typ: max 3.116 vs 2.804, worst delta +0.385 pF; high +0.598 | **MISS** |
| F3 context | published under-rail term 91 fF/leg, b5 206 fF; cell alone at x0.01 metal: b5 3.18 vs published 3.37 pF (-0.09..-0.24); published C reads low with metal because its 20-250 ohm series metal hides it at 1 GHz; ctest +100 fF reads 100 fF; P/N 78 fF | info |
| F4 USB HS eye / return loss | no USB bench exists | not run |

Not run: ss/ff device corners and hot in ESD; low-metal corner (netres has typ/high only); ring R beyond the bound; HS current delivered
(hs_term) on the R model; differential (DIFF_ENABLE) termination with metal (TERM_x_R links to the grid are ~100 ohm, DIFF mode not
judged); EM of the HS current path (published single Via4 into the PAD trunk, unchanged).
Interface / reports: new port DVDD (ring supply, lands on the ring at both sites); ATB_ESD_RAIL removed. PC-31 item 4 (VBUS short back-feed):
8 up-diodes per pad to the ring supply, so a VBUS short drives the die supply through 8 pd2nw per leg - reported, not solved.
TERM_ENABLE=0 with a pad driven above VDD + 0.7 V now conducts into the ring supply (option A, accepted by PC-27).

## CANDIDATE b6 (2026-11-20). NOT published, NOT committed. b5's build, models and extraction deleted (its table above stays).
GDS `build/b6/pad/combined.gds` (top `tx_with_primary`) sha256 69413a421d43...; physical.spice 33c9f85bf26e; models `models/b6_r_{typ,high}.spice`
652057c3 / f3a1d369, `_rail` d432ad1e / f66565ea (CRAIL 151 fF per leg; published 91). Generators (uncommitted, defaults unchanged, L7 XOR 0):
layout.py f485d8fe, wired_protection_layout_ss.py dbfaac63 (unchanged since b5), stress_safe_compact_layout.py a849f82d, pad_site_primary.py 4a3b087f
(unchanged). Benches: dbench.py 844a70c3 (new), fbench.py 4988181f (+ hs_term), q6.sh a91a5243, xor_def.sh 854a1e3c, padcmp.py.
Command: `build.sh b6 '--esd-a={"term_poly": [16, 0.96], "trim_poly": [4, 1.0], "fs_pad_6v": true, "site": {"n_up_left": 3}, "tb": {"fs": {"bus_w2": 4},
"neck_m1": null, "neck_hi": [150, 4], "top_pins": true}}'`, then `q6.sh b6` (= q.sh + FS high metal, hs_term typ/high, dbench x4, published 1 % rail
model + padc, xor_def.sh). Tables: `ttab.py b6rt b6rh`, `esdtab.py b6rh b6rt b6rh_nosite`, `padcmp.py bench/b6rt_rail-padc.json bench/pubrt_rail-padc.json`.

What changed from b5 (all behind options):
- FS high side out of the grid (`tb.fs`, layout.py `_usb_fs_block`): per leg east of the termination block, FS_x_R (ring on the block VSS riser,
  head on the PAD rail), 24 pad-side PMOS as one 24-finger PCell (drains -> Metal3 OUT plate), 24 supply PMOS as one 24-finger PCell (drains ->
  Metal3/4 plates -> Metal5 VDD bus joining both legs; the P plate crosses the TERM_VCM rail on Metal2 into a Metal5 bar on the grid VDD trunk),
  sources + n-tap guard -> Metal3 WELL row; GATE / WELL / OUT link to their grid trunks on Metal3 rows y 400.6-406.6. PAD -> FS_OUT metal 3.9 ohm
  (b5 35-41 + 53-83 ohm).
- **Schematic device change (`fs_pad_6v`): the 48 pad-side FS PMOS FS_x_PAD_i pfet_03v3 L 0.28 -> pfet_06v0 L 0.55 (same W).** Reason: with
  the low-R block the 3.3 V pad-side PMOS takes VDD - pad in CDM (b6t, 3.3 V: 5.78 V, 24 over 5.0 V; the b5 metal R had hidden it). Model what-ifs on
  b6t: +40 ohm series 5.24 V, +100 ohm 4.84 V (would put FS rise back near 20 ns); 6 V device: CDM 7.63 V (6 V gates), FS rise 9.0-16.7 ns.
  Needs a ruling (PC-50). Applied to the circuit before layout, so schematic = layout (LVS on the changed device).
- Pad-C levers, CDM 2 A high re-run after each (esd/b6l*rh_cdm.json; pad C typ worst delta vs published like for like):
  b6u (FS block + 6 V) +0.572 / 7.657 V; (a) neck Metal1 dropped (`neck_m1: null`) +0.486 / 7.621 V; (b) neck 4 um above y 150 (`neck_hi`, new)
  +0.358 / 7.589 V; (c) one left up-diode less (n_up_left 2) +0.326 / **7.985 V (margin 0.015 < 0.3: rejected)**; (d, own) VDD bus a 4 um stripe
  between the two supply PMOS (`fs.bus_w2`) +0.344 / 7.589 V. b6 = a + b + d.
- Termination re-centred for the narrower neck (base poly 16 x 0.96, trim bit-0 4 x 1.0). Found on the way: the top-edge TERM_VCM pin first hung on
  ONE via4 (4.5 / 15 ohm in series with the termination); now a Metal4 strip joins the pin to the TERM_VCM Metal3/4 bar.
- ASM-2 (coordinator, added mid-task; `tb.top_pins`): every core port except PAD_P / PAD_N (and the DVDD ring landings) is a Metal4 pin on the
  top edge, y 1433.0-1434.72 (flush with the bbox), via4 to its Metal5 trunk; RX_P / RX_N trunks run up to the top, side pins dropped (the
  receiver-discharge macro keeps its access at y 438). Pins (x1-x2, all y 1433.0-1434.72): BYPASS_ENABLE 2.78-3.22, DIFF_ENABLE 3.78-4.22,
  DIV_ENABLE 4.78-5.22, FS_HIGH_N 9.78-10.22, FS_HIGH_P 10.78-11.22, FS_LOW_N 11.78-12.22, FS_LOW_P 12.78-13.22, HS_N 35.78-36.22, HS_P 50.78-51.22,
  HS_PBIAS 51.78-52.22, PULLDOWN_N 68.78-69.22, PULLDOWN_P 70.78-71.22, PULLUP_N 72.78-73.22, PULLUP_P 84.78-85.22, RX_N 96.78-97.22,
  RX_P 97.78-98.22, TERM_ENABLE 98.78-99.22, LS_SLOW 99.78-100.22, TERM_TRIM0 115.78-116.22, TERM_TRIM1 116.78-117.22, TERM_TRIM2 117.78-118.22,
  TERM_VCM 118.55-120.9 (strip down to the bar at 1431.6), VDD 121.22-129.22, VSS 130.22-138.22. Labels Metal4 (46/10). Unchanged: PAD_P / PAD_N
  (Metal5 at 68 / 67, y 437.75), DVDD (Metal3 at 57.75 / 268.75, y 141.4).
- Extraction (coordinator note): no extresist anywhere in this flow (plain Magic extract / ext2spice C + netres R); nothing to switch.

| Limit | b6 | Result |
|---|---|---|
| L1 Magic DRC (base / combined) | 0 / 0 | PASS |
| L2 read-back LVS pos / composer schematic; controls RX swap / site diode missing | match / match (371 devices); mismatch / mismatch | PASS |
| L3 KLayout precheck main / antenna; sliver control | 0 / 0; M1.1 + DF.14_LV reported | PASS |
| L4 latch-up uncovered at 15 um; isolated-nmos control | 0.0 um2; 6.4 um2 | PASS |
| L5 rail_site_check / --selftest / pad-on-rail precheck / railconn | PASS / OK / 0 / clean | PASS |
| L6 floating lines (published 1) | 0 | PASS |
| L7 default path XOR vs published (final generator shas) | 0.0 um2 | PASS |
| L8 outline / ports | bbox (2.78, 0)-(384.18, 1434.72) inside published (.. 524); ports as b5 (DVDD added, ATB_ESD_RAIL removed), core pins moved to the top edge (ASM-2) | PASS (stated) |
| E1 HBM 2 kV, 10 cases, high / typ | worst 5.63 / 5.11 V (nfet_06v0), 0 over | PASS |
| E1 CDM 2 A + SITECAP 1 nF / 0.7 ohm, high / typ (requirement) | worst 7.586 / 6.844 V (nfet_06v0, P+N), 0 over | PASS (0.41 V margin high) |
| CDM 1 A / 3 A (report) | 1 A 4.96 V; 3 A 10.06 V high (42 over), 9.03 V typ (38 over) | report |
| HBM 1 kV (report) | 4.12 V high | report |
| E2 non-primary junction reverse < bv | 0.0 V | PASS |
| E3 site fingers fwd <= 10 / avalanche <= 1 mA/um | HBM 2 kV 4.41 / 0.009; CDM 2 A 6.66 / 0.047 (3 A: 10.0 / 0.059) | PASS |
| E4 MIM <= 6 V | HBM 2 kV 5.01 V | PASS (0.99 V margin) |
| ESD bench proofs: site diodes stripped | HBM 70.6 V gate / CDM 61.4 V, 104 / 128 over | PASS (control fails) |
| RX_P/N (info) | RX-VSS 0.82 V, RX-VDD 4.06 V CDM 2 A high | info |
| F1 HS termination 40.5-49.5 ohm per leg incl. metal, 23 corners, typ / high | every corner has codes in window (typ: ss 6-7, ff 0-2, tt 2-5; high: ss 7 at 48.8 worst, ff 0-3); P-N 0.8 / 0.95 ohm | PASS (high ss: 0.7 ohm to the edge) |
| F1 self-check / TERM_ENABLE 0 | x0.01 model 44.4..31.5 ohm; off: pad held at 4.15 V by the up-diodes at 8.9 mA | info |
| F2 FS edges 4-20 ns, 50 pF, typ / high metal | rise 9.26-16.98 / 10.28-17.94 ns, fall 6.0-8.7 / 6.3-8.9 ns | **PASS** (b5 MISS 19.5-24.9) |
| F2 VOH / VOL; LS_SLOW 75-300 ns; pull-up | 3.12 V / 0 V; 103-238 ns; pull-up 2.78-3.06 V = published | PASS |
| F3 pad C per leg, R+C with rail, vs published R+C with rail + 0.3 pF (declared basis) | typ: max 3.143 vs 2.804, worst delta +0.405 pF; high +0.614 | **MISS** |
| F3 other basis (task 3): vs published with its metal R scaled to 1 % (`models/pub_zero_rail.spice`, published CRAIL 91 fF) | typ: b6 3.143 vs 3.458 max, every case 0.16-0.66 pF BELOW; high 0.21-1.00 below | info (for the ruling) |
| F3 context | read-out control CTEST +100 fF reads +100.0 fF; under-rail 151 fF/leg (published 91, b5 206); P-N up to 157 fF (published 66) | info |
| New: delivered HS current (hs_term, stress_safe_usb path via fbench, mirror bias, trim code per process from the term table), vs 17.78 mA +-10 % | typ metal 15.24-15.72 mA, high 13.70-14.91, x0.01 metal 15.75-16.25 | report (below the target even at 1 % metal: not a metal-only effect; not diagnosed) |
| New: differential termination (DIFF_ENABLE, dbench.py, 2 mA into PAD_P around PAD_N 0.2 V; 8.9 mA drove the pad to 4 V and was dropped) | b6 typ 330-370 ohm, high 456-500; published with metal 462-515, published x0.01 99-142 | report (DIFF switches still in the grid behind ~100 ohm links) |
| F4 USB HS eye / return loss | no USB bench exists | not run |

Not run: ss/ff device corners and hot in ESD; low-metal corner; ring R beyond the bound; DIFF mode / delivered-current limits (none declared);
EM of the HS and FS current paths; VDD / WELL / gate metal in the R model (the FS block's are local wide metal now). HS current shortfall not traced.
Open for review: the 6 V pad-side PMOS (device change), F3 basis ruling (MISS like for like, below published with its metal fixed), CDM 2 A 6 V
margin 0.41 V, termination high-metal ss 0.7 ohm from the edge, PC-31 item 4 back-feed unchanged.
