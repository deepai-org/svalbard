# txr: metal resistance in the published wired transmit pad `pad_txpad` (measurement only)

Subject: `$P/analog/pads/generated/stress-safe-families/wired-transmit/` combined.gds, physical.spice
(sha256 dd8641f7..., Magic C-only), lvs-reference.spice. Nothing under `$P` is edited. Tools read from `../hsfix/`.

## 1. Circuit (read from `circuits.py:wired_transmit` and physical.spice; device counts checked in physical.spice)
- Termination, per leg: PAD_x -> one `ppolyf_s` 1.0 x 1.8 um (net TERM_x_R) -> 8 parallel `nfet_03v3` 20/0.28 (gate
  TERM_ENABLE_LOCAL = TERM_ENABLE through two 6 V inverters on VDD, body VSS) -> TERM_VCM; TERM_VCM also has a 1 kohm
  `ppolyf_u_1k` 2x2 um to VSS. No trim. The leg resistance is mostly the NMOS switch (gate 3.3 V, source 1.65 V).
- Output stage, per leg: PAD_x -> 16 `nfet_06v0` 16/0.7 cascodes (8 units x 2, gate CASCODE) -> SUM_x_D_0..7 -> per unit
  three `nfet_03v3` 20/0.28 steering switches (gates MAIN_x, POST_x, TMDS_x) -> shared tails MAIN/POST/TMDS_TAIL_0..7 ->
  `nfet_03v3` 20/1 tail sources to VSS (4 per unit MAIN, 4 POST, 2 TMDS; gates MAIN_BIAS / POST_BIAS / TMDS_BIAS).
  Open-drain current steering; VDD only feeds the two enable buffers and the detect sources (DETECT_PBIAS pfet 4/2 ->
  DETECT_x_I -> nfet_06v0 4/0.7 isolator, gate DETECT_ENABLE_LOCAL -> PAD_x). No driver current flows in pad VDD.

## 2. Limits, declared BEFORE any run of this directory (2026-11-18)
- L1: differential termination, TERM_ENABLE on, DC (+-10 mV about TERM_VCM = 1.65 V, the level of the published
  bench `rlsweep.py`): 100 ohm +-10 % (90.0..110.0) at tt 27 C 3.3 V, ss 32 C 3.15 V, ff 22 C 3.35 V, typ and high metal.
- L2: P leg minus N leg <= 2 ohm (absolute) at each of those points.
- L3: series metal bond pad -> driver output (cascode drains, used together) <= 2 ohm per leg, typ and high.
- Bench proof: (a) C-only model reproduces the published `pd13-rl-txpad.json` rdiff_ohm_100MHz = 90.533 (typical 27 C
  3.3 V), 127.337 (ss 22 C), 60.486 (ff 32 C) with the same AC measurement, to 0.1 ohm; (b) TERM_ENABLE = 0 reads > 10 kohm.

## 3. Bench proof (RUN 2026-11-18, `tb.py`, logs `bench-pubc-*.log`, json `bench/pubc-*.json`)
- Known answer, C-only published model, AC 100 MHz, 3.3 V: typical 27 C 90.53343975869407, ss 22 C 127.33725794782352,
  ff 32 C 60.48645325865259 ohm = `pd13-rl-txpad.json` to every printed digit. PASS.
- Broken case, TERM_ENABLE = 0, DC: 674.8 k (tt), 762.6 k (ss), 572.0 k (ff) ohm differential, > 10 kohm. PASS.
- C-only DC baseline (TERM_ENABLE on): see table in section 5. (DC is about 1 % above the 100 MHz real part, as expected
  for R parallel C.)

## 4. netres (RUN 2026-11-18; `mkspec.py` -> spec.json + devmap.json; `../hsfix/netres.py --tech` check passed; res.json, res_vss.json)
46 nets of combined.gds (sha ae75af97...), typ / high metal, every device terminal its own terminal: PAD_P, PAD_N, TERM_P_R,
TERM_N_R, TERM_VCM, SUM_{P,N}_D_0..7, MAIN/POST/TMDS_TAIL_0..7, VSS (whole net, 1 um step, pin + the 80 tail sources).
VDD not run: it carries no driver or termination current (open-drain stage; only enable inverters and detect sources).
Figures from the reduced networks (`paths.py` -> paths.json), ohm typ / high:

| Path | P leg | N leg | Narrowest metal, single-cut vias on the path |
|---|---|---|---|
| bond pad -> termination resistor head (PAD_x) | 43.2 / 101.1 | 61.0 / 121.7 | 0.4 um M2; V1, V2, V3, V4 of the pin stack + the ONE Via4 of the pad escape (P (41.22, 426), N (32.22, 434)) |
| resistor far end -> 8 switch drains (TERM_x_R) | 45.6 / 97.1 | 37.9 / 88.3 | 0.38 um M1; V1..V4 single at the resistor pin; each switch drain its own single-cut stack |
| 8 switch sources -> TERM_VCM pin | 3.85 / 9.48 | 3.87 / 9.53 | 8 um M5, no single cut common to all (each source: single-cut stack) |
| P switch sources <-> N switch sources (differential return) | 7.26 / 18.45 total | | |
| bond pad -> 16 cascode drains shorted (PAD_x) | 15.8 / 32.8 | 19.2 / 36.7 | 4 um M2 escape (364 um), ONE Via4 carries 100 % |
| same, equal current split, mean (min..max) | 15.9 (15.2..16.8) / 32.8 | 19.3 (18.6..20.2) / 36.7 | each drain: single V1-V2-V3-V4, 0.4 um M2/M3/M4 |
| bond pad -> one unit alone (2 drains) | 26.0..32.4 / 61.7..69.3 | 29.6..36.4 / 66.0..73.9 | |
| 2 cascode sources -> MAIN switch drain (SUM_x_D_u, per unit, carries I/8) | 47.0..66.4 / 114..137 | 48.6..68.1 / 116..139 | 0.4 um M2, 8 single cuts, 0.44 um M5 trunk |
| same -> POST switch drain | 64.2..81.6 / 135..156 | 65.6..83.2 / 137..158 | |
| MAIN switch source -> 4 tail drains (MAIN_TAIL_u, per unit) | 30.8..53.9 / 85.1..111 | 32.0..54.7 / 86.1..112 | 0.4 um M2, 4 single cuts |
| POST switch source -> 4 tail drains (POST_TAIL_u) | 27.8..45.8 / 81.4..102 | 28.9..45.4 / 82.5..102 | |
| 32 MAIN tail sources -> VSS pin, equal split, mean (min..max) | 3.76 (3.26..4.37) / 5.76 | same net | 8 um M5, no single cut common |
| 32 POST tail sources -> VSS pin | 2.89 / 4.69 | | |

Hand check of one figure (PAD_P bond -> resistor head, typ): 364 um x 4 um M2 8.19 + 3x3 via stack 1.0 + Via4 4.5 + 145 um of
8 um M5 0.73 + Via4 4.5 + 31.7 um of 0.4 um M4 7.14 + Via3 4.5 + 13.1 um of 0.4 um M3 2.94 + Via2 4.5 + 2.5 um M2 0.56 + Via1 4.5
= 43.1 ohm; netres 43.17.

## 5. R-aware model and termination (RUN; `make_rmodel_tx.py`, models/tx_{zero,rt,rh}.spice; `tb.py term`; bench/*-term.json)
Model = published physical.spice + exact reduced networks of PAD_P, PAD_N, TERM_P_R, TERM_N_R, TERM_VCM (927 resistors); 66 MOS
terminals, 16 diodes, 5 resistor heads moved to their own nodes. Self-check: the same model with every inserted resistor x 1e-6
gives 91.578 / 152.128 / 57.696 ohm = the C-only model (91.577 / 152.128 / 57.696). SUM / TAIL / VSS nets are NOT in the model.
DC, +-10 mV about TERM_VCM 1.65 V, TERM_ENABLE = VDD, driver off, ohm:

| Corner | | C-only | R-aware typ | R-aware high | L1 90..110 | L2 P-N <= 2 |
|---|---|---|---|---|---|---|
| tt 27 C 3.30 V | diff | 91.58 | 286.59 | 517.79 | pass / FAIL / FAIL | |
| | P / N leg | 45.79 / 45.79 | 138.39 / 148.56 | 253.15 / 264.91 | | 0.00 pass / -10.17 FAIL / -11.76 FAIL |
| ss 32 C 3.15 V | diff | 152.13 | 347.22 | 578.34 | FAIL / FAIL / FAIL | |
| | P / N leg | 76.06 / 76.06 | 168.67 / 178.85 | 283.41 / 295.17 | | 0.00 pass / -10.18 FAIL / -11.76 FAIL |
| ff 22 C 3.35 V | diff | 57.70 | 252.63 | 483.85 | FAIL / FAIL / FAIL | |
| | P / N leg | 28.85 / 28.85 | 121.44 / 131.60 | 236.19 / 247.94 | | 0.00 pass / -10.16 FAIL / -11.75 FAIL |

Added metal per leg (typ): P 92.6, N 102.8 ohm = PAD 43.2 / 61.0 + TERM_x_R 45.6 / 37.9 + half of the TERM_VCM return 3.6
(sum 92.4 / 102.5; the simulation gives 0.2 more because the switches do not share equally). Broken case on the R-aware typ
model (TERM_ENABLE = 0): 674.8 k / 762.7 k / 572.0 k ohm.
Separate from metal: the C-only termination is already outside +-10 % at ss (152) and ff (58): the leg is a 20/0.28 x 8
`nfet_03v3` switch with 1.65 V of gate drive behind a 1.8-square salicided resistor, and there is no trim.

## 6. Driver output path (netres figures + arithmetic in `vcost.py` -> vcost.json; NO driver simulation was run)
L3 (bond pad -> cascode drains <= 2 ohm per leg): 15.8 (P) / 19.2 (N) typ, 32.8 / 36.7 high. FAIL, P/N differ by 3.4 ohm.
Equivalent series metal of the leg that carries the branch current I (equal split over 8 units):
R = PAD + mean(SUM)/8 + mean(TAIL)/8 + VSS = MAIN typ 15.9 + 7.1 + 5.1 + 3.8 = 31.9 (P), 35.7 (N); high 66.4 (P), 70.8 (N).
POST: 32.3 / 36.1 typ, 66.9 / 71.3 high. TMDS: 35.8 / 39.2 typ, 73.5 / 77.4 high.

| Pad tail current | Metal voltage P / N, typ | high | of which bond pad -> cascode drains, typ | high |
|---|---|---|---|---|
| 9.05 mA (MAIN code 109, reset; wired_tx README) | 0.29 / 0.32 V | 0.60 / 0.64 V | 0.14 / 0.17 V | 0.30 / 0.33 V |
| 21 mA (MAIN code 255) | 0.67 / 0.75 V | 1.39 / 1.49 V | 0.33 / 0.40 V | 0.69 / 0.77 V |
| 22 mA | 0.70 / 0.79 V | 1.46 / 1.56 V | 0.35 / 0.42 V | 0.72 / 0.81 V |
| 28 mA | 0.89 / 1.00 V | 1.86 / 1.98 V | 0.45 / 0.54 V | 0.92 / 1.03 V |
| 44 mA, half MAIN half POST, same leg | 1.09-1.11 / 1.24-1.27 V | 2.22-2.26 / 2.41-2.44 V | 0.70 / 0.85 V | 1.44 / 1.62 V |
| 52 mA, same | 1.28-1.32 / 1.47-1.50 V | 2.63-2.67 / 2.84-2.89 V | 0.83 / 1.00 V | 1.71 / 1.91 V |

Caveats: (a) the README states 22-28 / 44-52 mA as the SUPPLY current of the pre-driver `wtx_mux8`, not as pad output current;
the pad current is the tail DAC (9.05 mA reset, 21 mA full scale). The 22..52 mA rows are the arithmetic the brief asked for.
(b) the MAIN + POST rows ignore that both branches share part of each SUM net (slightly optimistic). (c) the VSS part (3.8 ohm typ:
79 mV at 21 mA) lifts the tail sources against MAIN_BIAS, so it changes the current, not only the headroom.
Single cuts carrying current: the pad-escape Via4 of each leg carries 100 % of the leg current (21 mA in one cut); each
cascode drain, SUM, TAIL pin has one V1-V2-V3-V4 stack carrying I/16 (drain) or I/8 (switch pins): 2.6 mA per cut at 21 mA.

## 7. What a fix would take (READ only, nothing implemented)
The layout comes from `$P/analog/pads/layout.py:generate` (called by `stress_safe_compact_layout.py`), widths from
`spec/schematic-implementation.json` io_pad_first_pass.layout_parameters.wired_transmit.trunk_width_overrides_um.
1. Per-pin routing loop, `layout.py:generate` lines 375-391 with helpers `via()` (339-345, always ONE 0.26 um cut per level)
   and `wire()` (346-349, default 0.4 um, 0.44 um on M5): every device pin gets V1 - 0.4 um M2 - V2 - 0.4 um M3 - V3 - 0.4 um M4
   (103 um for the N resistor head) - V4 onto the trunk. 18 ohm typ (60 high) of cuts plus up to 23 ohm typ of M4 per pin. Needs a
   per-net class (cut arrays, wide M2/M3/M4) for PAD_x, TERM_x_R, TERM_VCM, SUM_*, *_TAIL_*, VSS pins. The M4 rows are on a
   0.8 um pitch (`route_y = route_base + terminal*.8`, 7 columns per 26 um row), so wide rows mean a new row plan.
2. Pad escape, `layout.py:generate` lines 440-456: `escape_width = 4.` (line 144) M2 for 364 um = 8.2 ohm typ alone, then the single
   `via(tracks['PAD_'+leg], bond_y, 4, 5)`. A cut array fixes 4.5 (15) ohm; reaching 2 ohm needs about 16 um of M2 equivalent
   (RF families already use 12) or a shorter escape (active_origin 440).
3. Trunks, `layout.py:trunk_geometry` (0.44 um for every net without an override): SUM_* and *_TAIL_* have none; the bank is
   limited to 146 um (`if edge>146`).
4. Placement, `layout.py:generate` lines 239-286 (21 x 26 um grid, one device per slot, P/N front devices sorted to the bond
   side): the termination resistor sits at y 584 / 558, its switches at y 1129-1207, the cascodes at 453-557 and the MAIN
   switches at 583-739. Grouping each unit (cascode, switch, tail) and the resistor with its switches removes most of the length.
5. Circuit, `circuits.py:wired_transmit` lines 176-182: `ppolyf_s` 1.0 x 1.8 um with a single 2-contact head + 8 x 20/0.28 switch,
   no trim: outside +-10 % over corners without any metal (section 5).
The proposed 0.6x MAIN switch (WT24 r3/r5/r6, WT34 (1)) would touch: `circuits.py:wired_transmit` `steering_width_um=20.`, which is
one value for MAIN, POST and TMDS (line 155), so a per-branch width is needed (WT34 (2) asks POST = 1/3 of MAIN; WT27 asks to
drop TMDS in the same pass); `layout.py:generate` only passes `serial_tail_units` to `wired_transmit` (line 133) and
`generation_parameters.wired_transmit` in the spec holds only that; a new primitive cell per (model, W, L) (`kkey`, line 174)
with new pin positions, hence new M2 jogs and antenna terms; then re-extraction, lvs-reference.spice (`lvs_reference.py`), model
and device audits, HBM screens, README section 3 row, and the consumers `screen.py`, `tx_compliance.py`, `wired_tx_loading.py`.
It does not change any of the metal in sections 4-6: the resize benches so far used a netlist scale of the C-only model, so
they do not contain the 0.3-0.7 V (typ) of metal drop found here.

## 8. Not done
- No R-aware driver simulation (SUM / TAIL / VSS networks are extracted in res.json / res_vss.json but not inserted in a model);
  section 6 is netres resistance times current.
- No AC / return-loss or eye rerun with the R-aware model; no HBM rerun (bond -> diodes 25.8-27.6 typ / 47.8-49.9 high per leg).
- VDD net, gate lines (MAIN/POST/TMDS/CASCODE/bias, TERM_ENABLE_LOCAL), detect path: not surveyed.
- netres itself was not re-validated here beyond the hand check in section 4; contact and diffusion resistance are not in it;
  "high" is Magic's hrhc/hrlc variant (15 ohm per cut).
- No corner beyond the three declared; no 3.5 V point; no electromigration check against a limit.
- No fix, no resize, nothing under `$P` edited, nothing committed.
