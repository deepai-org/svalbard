# Independent review: USB pad_wirepad candidate b7 (truncated on coordinator request, no sims run by reviewer)

GDS: build/b7/pad/combined.gds sha e3298c47... (top tx_with_primary). Verdict: **GO with conditions**.

## Evidence chain
- GDS mtime 23:05:16; physical.spice / models (b7_r_typ 73d0ef6d, b7_r_high 9a97caa7) built 23:05 by rmodels.sh from that GDS on disk;
  ESD jsons carry the same model sha. Default-path XOR log: 0.0 um2 (logs/b7-xor.log). Not independently re-extracted.
- Note: q-b7.progress shows esd stages at 0 s duration; esd/b7*.json are dated 00:14-00:55, i.e. ESD was re-run outside the queue
  (same model sha, so acceptable, but the queue log is not the record).

## Limits (recomputed from esd/*.json, bench/*.json)
| Limit | Value b7 (worst typ/high) | Status |
|---|---|---|
| E1 HBM 2 kV MOS <= 8.0 / 5.0 V | 5.65 V nfet_06v0 | pass |
| E1 CDM 2 A | 7.66 V nfet_06v0 (high metal, P+N) | pass, 4 % margin |
| E1 CDM 3 A (report) | 10.26 V, 43 devices over | reported only |
| E2 non-primary junctions | 0.0 V in all runs incl. control | **unverified** (see F2) |
| E3 site fwd / aval | 6.07 / 0.053 mA/um (2 A) | pass |
| E4 MIM <= 6 V | 5.03 V (HBM 2 kV high) | pass, 16 % margin |
| ESD negative control (sites stripped) | 75 V gate, 104-132 over | fails as it must |
| HS eye template 1 @TP (tt nom / tt cal / ss cal / ff cal / tt 50 mm) | inner 45/80/78/81/87 mV, outer 33.9/13.5/55.9/**0.6**/24.7 mV | pass, ff outer ~0 |
| HS level 360-440 mV | uncal tt 361.7 / -362.9 mV | pass by 1.7 mV; calibrated cases 391-399 |
| HS line edge >= 500 ps | tt nom 496 ps, ff 498 ps | **fail by 2-4 ps** (bench edges_ok) |
| RL (no USB numeric limit) | min 19.3 dB to 480 MHz, 9.2 dB to 1 GHz; TDR 82.8-117.3 ohm | reported |
| Eye bench known answers | ideal: +-400 mV, inner 100.1, outer 74.9 mV, RL ideal30 13.98 dB | correct |
| Eye bench failing control (5 pF, 2.5 ns) | inner -65 mV, ok=false | fails as it must (outer did not fail; only inner discriminates) |
Termination F1, FS edges F2, pad C F3: not re-verified (truncated).

## Findings
1. **Gate stand-in ramp is optimistic for overshoot.** Bench drives HS_P/HS_N from an ideal 1.2 ns linear ramp; the published
   pt_usb_txdrv line edge is 857-873 ps at tt. Bench line edges are already 496-705 ps; a faster real gate (HS_STR) gives faster
   line edges and more overshoot: ff outer margin is 0.6 mV and edges are 2-4 ps under 500 ps. A slower gate ramp is pessimistic for
   the inner mask only. Condition: rerun tt/ff eye with the real driver (or a ramp tuned to match its edge) and an HS_STR code; confirm
   outer margin > 0 and THSR/THSF >= 500 ps.
2. **E2 is vacuous as monitored.** worst_nonprimary_diode_rev_v = 0.0 in every run, including the stripped-site control with a 90 V pad.
   The model has 32 diodes (nd2ps_03v3 x6, nd2ps_06v0 x10, pd2nw_06v0 x16); either all are classified primary or the monitor misses
   them (esd_usb.py l.169-190). Condition: show one non-primary junction is monitored (control must report > 0 V).
3. Eye bench idealities (all optimistic): 143 bits PRBS7, no jitter/noise, uncoupled legs, lossless 5 ns cable, receptacle 0.5 nH/0.3 pF
   estimate with no spec value, measurement through matched cable + host instead of the spec fixture. Template 1 points
   (7.5/37.5/62.5/92.5 % UI, 0/300 mV, outer 525/475 mV) match my recollection of USB 2.0 Fig 7-13; not verified against the PDF.
   Channel element values taken from package-channel-wired.json by code; F.Cu 86.6 ohm / eeff 3.14 hard-coded, not cross-checked.
4. --cal scales the bias DAC by 1.09-1.12 to hit 400 mV, i.e. uncalibrated amplitude is ~9-11 % low (tt 362 mV, limit 360). HS current
   17.78 mA +-10 % is therefore near its low edge without B11 calibration; calibration is a board/firmware dependency.
5. EM of the HS path (17.78 mA DC per leg through switches, termination and trunk): **not screened** by anyone. Condition before tapeout.
6. CDM 2 A margin 4 % (7.66 / 8.0 V) on high metal; MIM 5.03/6.0 V. Pass, thin.
7. No limit movement found in the declared Pass limits section (dated 2026-11-20, before runs); F4 eye/RL limits come from the
   coordinator ruling PC-50, not moved.

## Conditions for GO
C1 eye rerun with real driver edge (finding 1), outer margin and >= 500 ps edges at ff; C2 working E2 monitor; C3 HS path EM check;
C4 F1/F2/F3 numbers independently re-read (not done here).
