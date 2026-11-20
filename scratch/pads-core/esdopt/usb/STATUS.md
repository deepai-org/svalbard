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
