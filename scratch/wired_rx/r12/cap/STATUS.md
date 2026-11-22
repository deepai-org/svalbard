# pt_wrx_cap r7f (wired RX r12 capture sub-agent) - STATUS

Staged under `scratch/wired_rx/r12/cap/` (no publish; `analog/wired_rx/generated/` untouched). Source: `analog/wired_rx/capture.py`.
Task: revise staged r7e (review `scratch/wired_rx/r11/review/capture/REVIEW.md`, interface row WR11-4) so that it has no timing races,
with resistance-aware evidence.

## Gates (declared 2026-11-20 ~10:05 UTC, BEFORE any r7f result; not to be relaxed)

Characterisation input used by the gates (done before any r7f build, `char/`, extracted one-flop cell `wc_char`, TSPC flop of
this block with its 2-inverter local clock buffer): TSPC setup / hold requirement t_su / t_h (D-edge to flop-clock offset at which
Q is wrong or clk->q grows > 10 %): ff 100 / 78 ps, tt ~120 / ~92 ps, ss/3.15 182 / 132 ps, pessimistic ss/3.15 228 / 184 ps
(sf, fs, ss/3.50: tt, tt, ss values are used).

G1 Functional, extracted netlist (C-only from the build flow), every case 0 data errors AND 0 edge errors, PD votes correct, word
   strobe correct, and judged bits >= MIN_BITS (quarter 150, half 120, full 100 = 5 words, i.e. more than r7e's 3 judged words):
   corners tt/27/3.30, ss/32/3.15, ss/32/3.50, ff/22/3.35, sf/27/3.30, fs/27/3.30, slow-pessimistic bound (ss/32/3.15 + r7slicer
   pess.py: wiring C x1.15, Rg, device C +25 %);
   ring 480, 625, 675, 810 MHz; at every (corner, rate): quarter RCS=0, quarter RCS=1, half RCS=0, full RCS=1 phase select 0
   (every mode is used at every ring rate: full 0.48-0.81, half 0.96-1.62, quarter 1.92-3.24 Gb/s; RCS only selects the front
   path, the back end is shared, so each front path and each back-end mode runs at every corner and rate) = 112 runs.
   Plus at tt 480: full phase select 3, 5, 7; LDE phase cases at tt 625 (run_capture q625_lde50/60 + sweep for the contract);
   safe state safes_q625 (EN = 0, S static: < 10 uA, outputs < 0.3 V).
   The run_capture.CASES gating list is contained in this matrix (834 MHz cases: reported only, ring maximum is now 810 MHz).
G2 Hop slack: for EVERY internal flop and latch (D not driven directly by a block input pin), in every G1 run, at its own clock
   pin: setup slack = (clock edge - last D crossing) - t_su >= 0.10 T and hold slack = (next D crossing - clock edge) - t_h
   >= 0.10 T, 50 % VDD crossings, corner t_su/t_h above. Worst hop per corner reported. Input hops (S, LDE, PSEL, SLIP) reported,
   not gated (their windows are the slicer / macro contract).
G3 Negative controls that must fail: (a) clock phase: quarter RCS=1 at tt 625 with CKP2 displaced by +3T/8 at the capture input
   (S2 then changes before its capture edge) must report data errors; (b) the hop instrument run on r7e extracted at nominal
   ss/32/3.15, 625 MHz must report the slot-enable violation the reviewer measured (ELQ19 hop slack < 0); (c) run_capture's
   neg_s2stuck must fail.
G4 LDE contract re-derived on r7f (cell sweep + full top) and stated with numbers per corner.
G5 Layout: Magic DRC 0, KLayout precheck (gds_uniquify.publish_checked, main + antenna) 0, LVS unique on the GDS read back from
   disk with device properties compared and a failing negative control (rb.py pattern of r11/cap/readback).
G6 R+C: Magic extresist, `simplify off`, `tolerance 0` (method of scratch/wired_tx/s14/rcov/RCOV.md), net coverage stated;
   declared threshold: a net is "R-relevant" if wire R >= 5 % of its driver Ron or R*C >= 2 ps; G1+G2 repeated on the R+C
   netlist for at least the worst corner per rate: pessimistic bound at 480/625/675/810 (quarter RCS=1 and full) and ff at 480
   (quarter RCS=0 and full; hold side).

Pins: as r7e unless unavoidable (then listed for an interface row).

## Log
- 10:55 G3b PASS (control failed as required): hop instrument on r7e extracted, ss/32/3.15, 625 MHz quarter: 21 internal hops
  below the gate; worst setup XCTL.ELQ19 (D = E19C) -37.6 ps (the reviewer's slot-enable violation), worst hold XFRONT1.H0 35.8 ps.
  Functional: 0 errors in 120 bits (as the reviewer: r7e passes functionally while the hop is violated). res/g3b_r7e_ss625.json.
- r7f first build (capture.py r7f source): DRC 0, LVS unique, top 1229.1 x 290.43 um = 356,968 um2 (r7e 300,638: +18.7 %).
- 11:00 owner note ASM-8 added to G5: report Metal5 area (um2, % outline) and whether Metal4 crosses the 70 um grid strap positions (integration/assembly/strap_widths.json); Metal5 free preferred.
- owner note: R+C netlist via scratch/wired_tx/s16/net/fixcap16.py (or r11 mkrc.py with per-net AND per-coupling-pair C ratio ~1.0 vs C-only); s14 fixcap.py not used.
- commit rule: git add -f <paths>; git commit -m ... -- <paths>

## Wrap-up 2026-11-22 (owner asked for a finished-if-imperfect baseline): r7f is NOT usable; nothing staged under stage/

State: r7f build 1 (b1) = the r7f architecture below, built from capture.py as it was on 11-20 ~10:40 (intended netlists in
r7f/fast/*.spice; extraction r7f/gen/wrx_cap.ext.spice). capture.py in the tree now holds b2 (lane in local groups with own
crossing flops, XPAD 1 / LPAD 2, front chains laid out per sample with one leaf per flop, INJS pad); b2 was NEVER BUILT OR SIMULATED.
r7e source = git a13d1485 (regenerate r7e from there).

r7f architecture (b1): back end entirely on CK rise; latch-based clock gates (ICG) for the pair R flops (GCK), word load GW
(from ELQ20 = ELQ19 one cycle later) and the phase-select/slip shadow GP (from ELQ15); lanes registered in the CK domain with
the full-rate 8:1 selection pipelined (DFa/DFb -> DFR, PS re-registered as PT every cycle); front retiming only by 6/8 or 7/8
ring-phase hops or padded 8/8 shifts (r7e had 4/8 hops), octet O at 48/8 (r7e 32/8, +2 cycles latency); new cell wc_word
(PSEL decode, PS, slip, SLP/SLM); ctl reduced to EN/CK/CKN/mode. Pins: top port list unchanged (r7e); pin positions follow the
new floorplan (not checked against r7e positions). Interface items if pursued: PSEL/SLIP shadowed 5 cycles before the word
boundary in full rate (was half a cycle), octet/PD latency +2 ring cycles, LDE contract below.

| Gate | Result |
|---|---|
| G1 functional matrix (112 runs) | NOT RUN. Probes only (tuning, short windows): ff/480 quarter RCS0: 0 errors / 120 bits; tt/625 half: 2 data + 6 edge errors / 100 bits FAIL; pessimistic 810 quarter RCS1 and full: dead (0 words) FAIL |
| G2 hop slack >= 10 % T | FAIL everywhere probed. ff/480: 53 hops below 208 ps (worst: pair R hold vs DL 0.4 ps; OC crossing hold OP 107 ps; W hold 43 ps). tt/625: 49 below (lane DFaR -104/-92 ps, DLr/ELr hold -42 ps, R hold 0.9 ps). pess/810: 105-113 below, nearly every front / slot / lane / PD hop negative: in-situ hop delays are ~1.6x the wc_char characterisation (long in-row wires, shared leaves), so 6/8-period hops do not fit at the pessimistic bound |
| G3a clock-phase control | NOT RUN |
| G3b instrument control (r7e, ss/3.15, 625) | PASS: instrument reports XCTL.ELQ19 setup slack -37.6 ps (reviewer's violation), 21 hops below the gate, while the functional bench passes (0/120) |
| G3c neg_s2stuck | NOT RUN on r7f |
| G4 LDE contract (wc_cnt cell, r7f b1 extraction, 10 ps steps) | no double / missed INJ at tt 625, ff 625, ss 810, pess 810, pess 480 (width 1 T), ff 480 (0.85 T), ff 810 (0.75 T), tt 625 (2 T); the capture cycle changes for an LDE edge 7-27 ps after CK at the cell (all corners); sub-10 ps band not resolved (reviewer saw a <1 ps drop band on r7e). Full-top LDE phase vs CKP0 not run |
| G5 layout | Magic DRC 0, KLayout precheck flow DRC 0 (top build), LVS unique (build flow). Read-back LVS NOT run. Area 1229.1 x 290.43 = 356,968 um2 (r7e 300,638, +18.7 %). Metal5 42,523 um2 = 11.9 % of outline (r7e 35,571): NOT Metal5-free; Metal4 vs grid straps not checked |
| G6 R+C | NOT RUN |

Why no Metal5-free cell: pt_wrx_cap's top routing (layout_engine.generate, timing owner's file) puts every vertical signal
trunk and the supply straps on Metal5 (layout_engine.py lines 643-652); there is no option to keep Metal5 free. A Metal5-free
r7e or r7f needs a router change in analog/timing/layout_engine.py (outside this sub-agent's allowed files) -> owner/timing.

Next steps if r7f continues: build + probe b2; if pess/810 still fails, the hop budget needs flops with lower clk->q or
physically shorter hops (per-chain placement was the b2 attempt); the pess/810 front may need a quantitative limit study.
Files kept: char/ (wc_char characterisation JSON), hop/ (instrument, registries), run7f.py, q.sh, matrix.py, stage.py,
lde/ (ldecell.py, q.sh, lde.log), res/*.json (all runs), r7f/fast + r7f/gen (b1 extraction, no GDS committed).
