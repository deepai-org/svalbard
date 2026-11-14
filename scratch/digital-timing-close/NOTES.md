# Digital macro timing closure (AC-1), 2026-11-11

Inputs: AC1_R4 (scratch/digital-hardening-ac1-r4), committed RTL 830ecdd.

## Diagnosis (AC1_R4 netlist + max SPEF, characterized ss_032C_3v15; diag.tcl / diag2.tcl / parse2.py; diag0/)
- Electrical: 71,199 max-slew/cap violators at ss (limit 1.0 ns); slews of 2-5 ns on x1 cells. The resizer
  ran repair_design at tt x 1.0 and repair_timing at tt x 1.75 (RSZ_CORNERS = nom_tt only): it never saw the
  ss slews. Typical stage 1.0-1.5 ns instead of ~0.6.
- Clock tree: hcore insertion delay 13.5 ns (period 12.8). Root cause: the divider flop (synthesized dffrnq_1)
  drives the kept root buffer over 0.14 pF (5.2 ns slew); neither CTS nor the resizer touches that net.
  hddr<->hcore skew 8-10 ns; rftx skew 4.9 ns; fc skew 3.5 ns; fca/fcb blk latency 13-14 ns (same structure).
- Missing / wrong constraints (timed as synchronous with arbitrary common-period alignment):
  rftx->egress_wtx -23.5, rfrx->sclk ports -22.0 (gain override of analog_cfg), hcore->egress_mem_sclk -19.2,
  wtx->egress_rftx -15.8, hcore->rfrx -15.7 (gain_arg handshake), ingress_wrx->rfrx -8.2, wrx->ingress_rfrx -6.8,
  rfrx->hcore -1.3 (mark_ptr handshake); ref -26.5 = fcb.snap_h -> cdr_freq_locked: the 5-cycle evaluation MCP
  missed the flop because synthesis named it after the port; ref good[] self-paths also evaluation-strobed;
  capture_done bound pattern (*core.capture_done*) never matched (flop is digital.capture_done_*);
  ct_det_clk (a divided clock) timed as data; hddr -7.7 = D2H outputs referenced to the ideal hddr edge
  (absolute insertion delay) instead of the forwarded clock (source-synchronous).
- Real design problems found:
  * D2H forwarded clock left through a synthesized oai21_1: ~3.6 ns later than the data lanes at ss (> 1 UI).
  * egress playback empty = play_done || !rd_ready: reset-synchronizer output as data -> take -> 40-bit select (-15.6).
  * pops computed combinationally from consumer state (frame_tx take>rcnt; lc_tx take->advB->advA->pop) feed
    FIFO flags/select (hcore -14.4, wtx -8.1); frame_rx beat decode -> collector (14-18 levels).
  * ingress write enable: lane_in_valid -> put -> 28 x 40 array enables (1,120 flops, -7.7).
  * lc_rx enable = ENABLE synchronizer output as data into ~300 flops (-12.0); hit->adopt->deliver->dec enable.
  * clocktree ctw 6.4 ns: ref_ev -> rephase -> cnt_next -> compares (9 levels); stable counter 7 levels.
  * PRBS on wire_tx_data straight from rising-edge flops: ff hold -0.34 on the falling-launch low half.

## Fixes
See final report (agent output) for the list; files: rtl/pt_fifo.sv pt_core.sv pt_quad_link.sv pt_linecode.sv
pt_host_link.sv pt_cells.sv pt_digital.sv pt_interp2x.sv pt_freq_count.sv pt_clocktree_slow.sv;
integration/pt_digital_macro.sdc; verification/digital_hardening/config.json, run_digital_hardening.sh;
sim/tb_digital_prbs.sv, tb_pt_freq_count.sv, pt_transport_harness.sv, tb_memory_mode.sv.

## Flow experiments (repair_design after GPL on the AC-1 netlist, ss_032C max RC)
| slew/cap/fanout | area after repair | utilization |
| 1.0/0.1/10 (20 % margin) | +151 % | 120 % (illegal) |
| 1.8/0.15/10 | +57 % | 75 % |
| 2.0/0.15/10 | +48 % | 71 % |
| 2.5/0.2/12 (chosen) | +36 % | 65 % |
Timing-driven global placement: +97 % virtual area inflation -> illegal; disabled.
SYNTH_STRATEGY DELAY 1: ABC ran > 40 min on the new RTL (3 min on the old); DELAY 2 used (3 min, +3.4 % area vs AREA 0).
Runs: run0 = committed RTL + new flow/SDC (baseline; stopped at post-GRT congestion, mid-PnR STA used),
run1 = new RTL + new flow/SDC.

## Run TC2A (scratch/digital-timing-close/run2a): RTL + flow + SDC fixes, post-route, char ss_032C_3v15 max RC
Flow: DRT 0 violations; Magic/KLayout DRC 0; LVS clean; antenna 0; utilization 71.5 %; 7,459 sequential cells.
Intra-domain worst setup (q2d/, current SDC, SCLK 10 MHz): sclk +14.1, ingress_rfrx +5.2, ctref +29.0, fc +0.9,
rfrx +0.76, egress_rftx +0.63, d2h_fwd -0.71, ctdet -1.57, hword -1.81, hddr -1.91 (recovery), ingress_wrx -2.46,
ctw -3.33, h2d -3.57, rftx -4.75 (output budget), hcore -5.63 (core_rst_n recovery tree), ref -5.74, wtx -7.04,
egress_wtx -7.07, wrx -7.73. Hold ff22/ff32: all >= +0.22 except D2H source-synchronous window -0.06/-0.08.
Dominant remaining cause: high-fanout control/reset nets buffered by repair_design as serial chains of
buf_1/buf_2 (5-18 stages, ~1 ns each at ss with the 3.0 ns slew limit); repair_timing gives up.
Post-run2 RTL (sim/formal verified, NOT hardened): lc_tx take from lc_qv, divider drs_c; PD37 and MOD-00 register fields.
Next: explicit replication (pt_rep_dff) of core_rst_n/dr_n/hr_n release flops, fcb/fca run, h2d nsel (per 4-bit
group like D2H), prbs at_max/step; egress take fanout split; prbs pend as carry-select; rftx outputs registered at
the macro edge; OpenROAD gain-based fanout buffering (or MAX_FANOUT 6 for these nets); D2H forwarded-clock model
(OpenSTA generated-clock latency takes the c_f falling path for the rise edge).

## Iteration after commit (coordinator: continue to closure)
RTL: pt_rst_rep replicated hcore reset release (frame_tx/rx, collect, gm); H2D nsel x5 (per 2-pin group);
freq-counter run_e replica; registered H2D aligned quad (+locked_d); kept drs_c copy (pt_rep_dff); H2D full as
next-state register; ctdet en_q; PRBS pend candidate adders kept. All rtl-checks/pattern/formal PASS.
TC3 post-route ss32: hcore -8.5 (hpre after rotation select -> fixed by aligned_r), wrx -7.6, egress_wtx -6.1,
wtx -5.2, rftx -4.4, h2d -3.5, ctw -3.2, hddr -2.6, hword -2.5, ctdet -2.1, ref -2.0 (was -5.7), ingress_wrx -0.7.
TC4 post-route ss32: wrx -9.8 (PRBS pend adder restructured by ABC -> keep fix in TC5), egress_wtx -6.5,
wtx -6.3 (empty_r -> wire_idle output), rftx -4.9, hcore -4.8 (ingress empty -> read mux), ref -3.7,
ctw -3.3, h2d -3.0, hword -1.9, ctdet -1.7, ingress_wrx -1.4, d2h_fwd -0.65, fc -0.2; hddr closed; ff hold
clean except d2h_fwd +0.04. TC5 launched (scratch/digital-timing-close/go5.status).
Stuck-path candidates needing architecture/interface changes rather than replication:
 - rftx: rf_tx_sample/valid outputs vs an ideal-edge 0.2T output budget; the macro's rf clock insertion
   (~5-8 ns) alone breaks it. Needs the DAC to sample on a forwarded/opposite edge or a budget defined
   against the macro clock pin (interface question to RF/assembly), not more logic work.
 - wtx: wire_tx_valid/wire_idle are combinational from the egress empty flag to output ports.
 - 6.4 ns domains (hword, h2d, ctw, ctdet): ~1 ns/stage cells leave ~3 levels; need register-per-decision rewrites.

## Takeover 2026-11-11 15:05 (new agent): TC6 / TC7
Tooling: syn.sh / synall.sh (synthesis + OpenROAD pre-placement gain-buffered STA, ideal clocks; endpoint
groups in syn/<name>/groups.txt), part.sh (flow up to a step), midsum.py (per-group WNS of a max.rpt).
Calibration: post-synth (ideal clocks) is 0-3 ns optimistic vs mid-PnR for 12 ns domains (worse for wide
fanout / read-mux paths), ~0-0.7 ns for the 6.4 ns domains.
Flow findings:
 - DESIGN_REPAIR_BUFFER_GAIN (OpenROAD -buffer_gain, env passed by run_digital_hardening.sh) replaces the
   serial buf chains: TC5 (TC4 RTL + gain 4) mid-PnR ref -4.7 -> -0.3, ctdet -4.2 -> -0.2, ctw -5.1 -> -2.6,
   hcore -5.1 -> -2.5, h2d -3.3 -> -1.45. Costs ~6 % utilization (repair 53 -> 71.6 %).
 - Verilog keep/dont_touch is NOT honoured by OpenROAD: DESIGN_REPAIR_REMOVE_BUFFERS=true deleted the kept
   pt_stagger buf_1 pair (D2H stagger absent in hardened netlists), pt_clock_mux drv buffers; the kept x4
   pt_clock_dff divider flops were resized to dffrnq_1/_2 (TC6: host.divider.cdiv 5.2 ns, slew 5.5 ns).
   RSZ_DONT_TOUCH_RX on instances aborts repair (RSZ-3006: cannot buffer nets into dont_touch pins).
   Now: DESIGN_REPAIR_REMOVE_BUFFERS=false, pt_clock_buf = clkbuf_8 right after each divider flop.
 - xor3/xnor3 (2.6 ns at ss) and or4 (2.0 ns) excluded from synthesis.
 - Parameterised keep_hierarchy modules survive as $paramod cells -> flow "unmapped cells" abort: kept
   selects are 1-bit leaf modules (pt_sel1 / pt_lc_sel1 / pt_pat_sel1) with flattened W-bit wrappers.
 - UTILIZATION is now binding: TC5/TC6 (77 % after CTS) stalled in global-routing congestion iterations.
   TC7 RTL: GPL 56.7 %, after repair 74.5 % (gain) / 68.7 % (no gain); TC4 routed at 71.3 % final.
   TC7 is a DIE-AREA EXPERIMENT (1716 x 1640, +12.7 %) to measure closure with routable density.
RTL changes (all checks pass at each launch; see interface-changes.md DT-1..DT-3): RF TX output register
(pt_rf_out_reg), wired TX output stage (lane_q + valid/idle, valid/ready), unpacker 84-bit reservoir with
registered in_ready/out_valid, gain_rx registered change, lc_tx enable replicas + kept selects, lc_rx dk
parallel + kx/c4k precompute, PRBS GF(2) mask form (gen + check), PRBS error counter (kept selects,
nonzero flags, ninth overflow bit, extra adder stage), CDC FIFO (registered rn, parallel distance, kept
late selects, empty/full on registered pointer copies, two-stage read with 3 registered candidates),
pre_quads registered, frame_tx linear-split header (A: 3-stage encoder, B: pending combinational),
beat-11 compares registered, frame_rx/tx engine reset from own register, kept clock mux mux2_2+clkbuf_8.
Forks: clocktree/freq_count (fork A), host link (fork B) - see their notes in the final report.
TC7 (run7, die 1716 x 1640 experiment) post-CTS mid-PnR (ss32 characterized, 34-openroad-stamidpnr-2):
utilization 66.6 %; setup WNS egress_wtx -3.15 (egress empty_r -> payload_iq-muxed pop -> take ->
rd_count / roh, one 1.9 ns buf_1 clone), wtx -2.42 (lc_tx ures -> dA through an 18-stage serial
"rebuffer" buf_2 chain inserted by the resizer - flow artefact to investigate), rftx -1.61 (output vs
T/2 - 3.0 ns budget), wrx -1.32 (lc_rx sym -> pa), d2h_fwd -0.84, h2d -0.78, ctw -0.78, hcore -0.74
(was -4.74 in TC6), ctdet -0.15, ref -0.01, hddr +0.09 (was -2.05), hword +0.11, async +0.18;
hold min: h2d -1.33, d2h_fwd -1.00 (input/output source-synchronous windows), everything else >= +0.3.
GRT was still running at 19:55 (single-threaded, log buffered). Results land in run7/; quick STA:
runq.sh-style with run7/design/runs/TC7/<rcx>/max spef.
Independent review (read-only agent) findings handled: rf_mute now loaded with the sample (DT-5);
open: egress pops without request in fault/starved states (harmless), ENABLE async-clear recovery arc
classification in the SDC, unpack formal data assertion removed (python model covers data).
Next: (1) coordinator decision on die area (DT-4) - without it the RTL does not route; (2) egress pop:
owner-specific registered pop decode (payload_iq/linecode static) so take is 2 levels; (3) lc_tx flip/
running-disparity stage split; (4) lc_rx 6b/4b decode one more stage; (5) rftx: halfband infeasible,
bypass needs insertion <= ~3 ns (dedicated shallow rf_tx_clk branch for the 26 output flops);
(6) investigate the resizer's serial rebuffer chains (repair_timing -sequence / max_buffer_pct).
TC8 (run8, launched 20:06; approved die 1716x1640 in config.json; DT-6 rf_tx_clk_out source-synchronous;
mute fix). Post-CTS mid-PnR: util 70.1 %; setup wtx -3.99, egress_wtx -3.73, wrx -1.39, hcore -1.07,
hddr -1.05, d2h_fwd -0.54, ctw -0.21, h2d +0.01, hword +0.13, ctdet +0.21, ref +0.35, rftx +1.66,
rftx_fwd +6.90 (RF outputs closed); hold d2h_fwd -1.10, h2d +0.07, rest >= +0.27. RTL checks on TC8 RTL:
all formal/pattern/regfile pass (rtl-checks run in tc6/allchecks8.log). Still to do: items (2)-(6) above,
d2h hold window, 10 % margin everywhere, then export/DRC/LVS/STA/GLS/evidence/review.
## Takeover 2026-11-11 20:30 (agent 3): TC9
run8 (TC8) was in GRT at 20:28 (left running for the routed baseline).
TC9 RTL edits (uncommitted): (1) egress pop: pt_cdc_fifo POPQ=1 + `nonempty` register (ne_r), owner gates
eg_r/eg_l/eg_w registered in pt_core (eg_w = next of wired owner & !pat_sel & wire_running), take =
AO of registers + late request; (2) pt_lc_tx new stage P (sP/fP/dP) between ures and A (A only XORs
registered flips); pt_lc_rx new pb stage before pa (raw tables registered; dk select + kx in 2a1).
(3) lc_tx input register hq/hv (egress head -> one-entry stage; 72-bit insert sees pop_i from lc_tx regs only;
TC8 wtx -3.99 was empty_r -> pe mux -> lc_pop -> 10-stage gain/rebuffer tree -> ures).
D2H hold (TC8 mid-PnR): clock path c_f/xor/clk_out.cell placed at (957,940) ~940 um from d2h_clk_pin
(1391,2): mux2_2 drives 0.099 pF (1.68 ns); lane flops scattered y=300-660; lane spread 1.7 ns vs +-0.64.
Fix: MANUAL_GLOBAL_PLACEMENTS of the whole D2H output stage next to the pins (d2hplace.py from the synth
netlist names; Odb.ManualGlobalPlacement runs after RepairDesignPostGPL, before DPL/CTS).
Item 4 (TC8 post-CTS netlist, area.py / chains.py): no long single-load serial chains (max 5 data,
the TC7 "18-stage" is resizer rebuffer stacked on the gain tree of lc_pop: ~10 buffer levels on one
high-fanout net). Buffer area: gain 8369 cells 0.25 mm2 (13.5 % of 1.86 mm2 cell area), max_cap 0.074,
synth buf 0.11, rebuffer 0.007, hold 0.005. PL/GRT_RESIZER_SETUP_MAX_BUFFER_PCT = 80 (questionable).
CORRECTION: DEF units are 2000/um; TC8 D2H coords above are 2x (clk_out at (479,470) um, pin (696,1), ~520 um). d2hplace.py fixed; TC9 relaunched.
TC9 relaunched 20:55 with D2H + clock-source cluster placements (cdiv/core_root, egress mux/drv, fca fjc/blk buf, interp hdiv)
TC9 relaunched 21:05 (tie cells excluded; + frame_rx hpre split)
PD40/PD41 done (DT-7): regmap term_enable + gate_and + rule, generator multi-bit gate_and, pt_tx_pad_sequence dwell/timeout; regfile+formal+shared_pad tests pass.
TC9 mid-PnR (34-stamidpnr-2, TC9 RTL + D2H/clock placement): wtx -0.48 (was -3.99), egress_wtx -0.44 (-3.73),
wrx -0.73 (-1.39), hddr +0.28 (-1.05), ctw -0.28, ref +0.01, h2d +0.03, ctdet +0.11, hword +0.27, rftx +0.64;
REGRESSED: d2h_fwd setup -2.19 (lane mux -> synthesized d2h_pin buf_1 placed 340 um away at (384,23); clock path
now short), hcore -2.08 (egress.rbd/wb -> ready ripple ~12 levels), sclk -0.43 (50 ns half-period regfile commit:
commit_code -> 573-bit apply fanout through a serial gain/max_cap ladder), hold h2d -1.37 (input h2d_pin -> f,
insertion 5.5 ns vs 1.2 ns external min delay), d2h_fwd -0.59.
TC10 RTL: egress ready = window compare (rlim/rwrap regs, formal assert == occupancy compare; exhaustive py check);
regfile generator: commit_code registered (commit_code_r + cc_fresh, FE if a commit follows a write by 1 clk,
formal assert commit_code_r==commit_code when fresh; regfile sim + formal PASS); d2h_pin synth buffers placed.
TC10 launched 21:37
TC11 RTL so far: pattern errors_n register; lc_rx one-hot cand/off low-hit tests. allchecks started 21:38
TC10 mid-PnR: d2h_fwd -1.77 (DPL moved q_f[7] 150 um: 6.72 um lane pitch too dense -> d2hplace now one 15 um
column per lane), wrx -1.02 (prbs errors->gray, fixed TC11), ctw -0.50 (launching -> dm), egress_wtx -0.43
(rnr -> rd_count ripple), wtx -0.21 (sA -> encoder), hcore -0.06, h2d +0.03, hddr +0.13, ctdet +0.16,
hword +0.17, ref +0.40, rftx +1.04, sclk +7.02 (was -0.43); hold(ss) d2h_fwd -0.83, rest >= +0.04.
TC11 RTL: egress CNTPIPE=1 (split-distance rd_count, exhaustive py check), clocktree lc_c/dz_c kept replicas
(formal asserts), lc_tx r1A/a7A registered in stage A, prbs errors_n register, lc_rx one-hot cand/off.
TC11 config: PL/GRT_RESIZER_SETUP_SLACK_MARGIN 0.1/0.05 -> 0.7/0.65 (resizer repairs to the 10 % target of the 6.4 ns domains; optimization target only, SDC unchanged)
lc_rx one-hot and clocktree replica REVERTED (post-synth worse: lc_rx off -1.65, lc_rep->dm -1.25). TC11 launched 22:05
TC11 mid-PnR (TC11 RTL + resizer margins 0.7/0.65): d2h_fwd -2.81, wrx -0.82, hcore -0.65, wtx -0.60, ctw -0.43,
async -0.37, egress_wtx -0.32, rftx -0.14, h2d -0.09, hddr -0.03, ref +0.10, ctdet +0.13, sclk +0.35, hword +0.46
=> not better than TC10 (run-to-run noise ~0.5 ns; higher resizer margin did not help). Mid-PnR ss hold: h2d -1.33.
D2H STRUCTURAL FINDING (TC9-TC11): manual PLACED locations are not kept (DPL moves cells 100-150 um when the
pin-edge region is crowded; TC11: lane-2 xor -> d0 stagger buffer wire 0.108 pF). Even co-located, the data lane
is longer than the clock path: data = q_f dffnrnq_1 (2.3 ns) -> xor (fanout 2: mux + stagger d0) -> mux2_2 ->
synthesized d2h_pin buf_1 (yosys port buffer, data lanes only) -> port buffer; clock = c_r pt_clock_dff (sized
_2, 1.85 ns) -> xor -> mux2_2 -> port buffer: ~1 ns systematic skew vs +-0.64 ns budget. Needs (a) FIXED
placement (Odb.ManualGlobalPlacement only sets PLACED) or a small hand-built D2H output macro, (b) identical
cells on both paths (same flop type/size for c_r/c_f and q_r/q_f; a dummy d0 load + the same port buffer on the
clock path), or a coordinator decision. Not solvable by placement hints alone.
TC10 post-CTS worklist (midq.sh/mqsum.py on 33-*.odb, real layer RC; groups below 10 %): hcore 36 (ingress
empty -> roh, in_rd_step -> pre_quads, h2d.rb -> frame_rx.cat, ingress roh -> p0b, avail_words -> d2h_quad),
hddr 12 (dr_n reset fanout -> gearbox x/phase/f3/q_r: replicate dr_n), hword 5 (host_rate hold_n/gap), ctw 24
(launching/dz -> dm/d1/rephase/dly; my kept-replica attempt made post-synth worse, reverted), h2d 18 (input
pins -> r/fh/f, phase -> entries enable, hr_n fanout), ctdet 6, ref 4 (fca/fcb run_e -> cur), wtx 23 (lc_tx sA/
rdA -> lc_q, TC11 r1A/a7A targets this), wrx 49 (prbs errors->gray fixed in TC11 RTL; lc_rx pb->pa, hit->cand/
cand_v/v2a, off->sym), rftx 2 (status -> unpacker bits, needs 2.0).
TC12 RTL (untested in PnR): host gearbox rst_n/nrst_n from kept release copies drs_g/drs_ng (SDC *host.drs* pattern covers them); pair-word-formal + wire40 PASS.
Independent review (RTL TC9-TC11) handled: (1) HIGH stale eg_r/eg_l/eg_w when a TX clock stops -> static
payload_iq/linecode/pat_sel ANDed back into egress_pop; (2) pt_tx_pad_sequence defaults restored (PD40 via
parameters, DT-7a; pads tb PASS, pd40 tb PASS); (3) CNTPIPE count may over-report by <=2 -> RF start uses
RF_START+2. Open from review: tb_shared_egress_lifecycle uses constant wired data (cannot see lost words) -
make its data vary; term_enable has no pt_chip consumer yet (assembly).
TC11 killed in GRT (superseded). Resizer margins reverted to 0.1/0.05. TC12 launched 23:02 (all current RTL). TC10 still routing (routed calibration only: has the stale-gate bug).
TC12 first attempt (static ANDs in egress_pop): mid-PnR egress_wtx -1.82 (and4 in take path), hddr -4.17 (en_d
nand2_1 driving 0.19 pF to the pin-placed c_r_ff: 7.2 ns slew). Fix: eg_r/eg_l/eg_w async-cleared by
rst_n && enable instead of static ANDs (owner changes only while disabled); host.en_d/mode_d placed with the
D2H clock column. shared-egress-lifecycle PASS. TC12 relaunched.
Review follow-up: reviewer re-ran its stale-pop probe on current RTL: 0 stale pops (was 49); pad tb PASS; RF_START+2 OK.
Open from review: add an assertion that payload_iq/linecode/pat_sel change only while disabled; make
tb_shared_egress_lifecycle use a sequence check (varying data) instead of the constant compare.
TC12 mid-PnR (current RTL, routing continues in run12/): d2h_fwd -1.14, wrx -0.85, egress_wtx -0.67, ctw -0.33,
wtx -0.20, hcore -0.00, h2d +0.07, hword +0.13, hddr +0.15, ctdet +0.17, async +0.31, ref +0.46, rftx +1.29;
ss hold: h2d -1.37 (input window, ff not yet checked), d2h_fwd -0.85. 10 % margin NOT reached anywhere critical.
STATE AT HANDOFF (23:50): RTL checks all PASS on current RTL (allchecks + digital-rtl-checks + pd40 tb + pads tb).
TC10 (pre-review RTL) still in GRT for routed calibration. Evidence NOT updated (no passing routed run).
NEXT: (1) D2H structural fix (see D2H STRUCTURAL FINDING) - likely needs coordinator decision / hard sub-macro;
(2) worklist above (hcore 36 / ctw 24 / wtx 23 / wrx 49 / h2d 18 / hddr 12 groups below 10 %);
(3) egress_wtx: take fanout tree (ne_r -> lc_tx hv -> take -> roh/cnt_sel) - consider registering lc pop
decision fully (pop = eg_l && ne && !hf is registers + 2 gates; the remaining depth is the fanout tree);
(4) then routed run -> export/DRC/LVS/STA/GLS/evidence/review.

## Takeover 2026-11-12 ~00:00 (agent 4): TC13 = hand-placed FIXED host-link I/O block
TC12 (run12) still in GRT congestion iterations (15/50 at 00:00); TC10 killed (stale RTL). No 1716x1640 run
since TC7 has finished global routing (TC8/TC10/TC12 all stuck in GRT extra iterations): congestion is real.
Disk was full (ENOSPC): deleted run0,1,2b,3-7,9,11 (superseded; run2a/8/10/12 kept).
CTS experiments (hio/ctstest, mini design): OpenROAD CTS does NOT skip dont_touch nets (ODB-0370/0372 when a
clock net or sink is dont_touch); it splits a clock net into macro/register subnets and BALANCES latency per
clock with delay buffers (capture subtree delayed 1.45 -> 2.87 ns to match the rest); -delay_buffer_derate 0
does not stop it; separate generated clocks do (balancing is per clock).
TC13 RTL (pt_cells.sv pt_hio_*, pt_host_link.sv):
 - D2H: 11 identical lanes (clock + 10 data): lr dffrnq_1 / lf dffnrnq_1 launch flops -> hio_x xor2_1 ->
   hio_d0/hio_d1 buf_1 (stagger chain, also on the clock lane as load) -> hio_m mux2_2 -> hio_ob buf_8
   whose Z is the port bit itself (a module port in between = 1-bit wire aliased to a bus bit -> the flow's
   insbuf adds buf_1 on the data lanes only: that was the TC9-TC12 "synthesis port buffer").
   Forwarded clock: c_l logic toggle reg; launch lr takes c_l's next value, lf copies c_l (= old c_r/c_f).
 - H2D: h2d_clk -> cap_root (clkbuf_8, generated clock h2d_cap) -> 30 capture flops (r, f, fh[19:10]),
   each behind a kept mux2_2 (en=1 for r/f, pair enable for fh) fed by a per-pin hio_ib clkbuf_8;
   cap_root -> core_root (generated clock h2d) = CTS root of the rest of the domain. Port clock h2d_pin is
   the input-delay reference. SDC/sta_signoff updated (h2d_cap, d2h_fwd windows via pt_xslack).
 - Placement: hio/hioplace.py -> verification/digital_hardening/hio_placement.cfg (MACRO_PLACEMENT_CFG,
   FIRM, site grid, tap sites of the TC12 floorplan avoided; south rows 0-5 x 630-870, north rows 403-409
   x 80-320); RSZ_DONT_TOUCH_LIST = 120 hio_* instances + 152 nets (Q->pin, pin->D). Flops not dont_touch
   (CTS must connect them). Old D2H MANUAL_GLOBAL_PLACEMENTS removed (clock-source clusters kept, hio/mkcfg.py).
 - Post-synthesis (syn14): no d2h_pin port buffers; 0 insbuf on hio nets.
Review items: pt_core simulation assertion (owner/linecode/pat_sel stable across consecutive TX-clock edges
while eg_rst_n=1; negative test fires); tb_shared_egress_lifecycle rewritten with varying data and an
exact sequence check (wired counter quads, RF bitstream samples, 4 phases; the RF source is now rate-limited
to 40 MS/s: an unlimited peer overruns the RF ingress -> rx_fault, which the old 4-sample bench hid);
mutation checks fail (ungated wired pop; corrupted reference word).
RC-16g (+RC-16e, never applied): lna.match ctrim 3->4 bits reset 7, new lna.att[4:0] reset 0
(spec/analog-architecture.json; regenerated: analog_cfg 573 -> 579 bits, map_hash 0x7003).
Buffer allowance: PL/GRT_RESIZER_SETUP_MAX_BUFFER_PCT 80 -> 30. Partial flows pA (gain 4) / pB (gain 8).

## r4 status (agent 4, after login interruption)
- hio fixes: hio_m muxes no longer dont_touch instances (RSZ-3006 on stagger select); capture flops behind a
  keep buf_2 (qb) so the resizer never upsizes a FIRM flop (DPL-0033 tap overlap). syn15 clean.
- pA/pB (to ResizerTimingPostCTS): all 149 hio cells FIXED at cfg location, types unchanged. Repair start WNS
  -44 ns (sclk commit_count, pre-repair only), final WNS -4.88 flow view. Signoff SDC: worst setup -2.50
  (lc_rx en_r fanout, wrx), d2h_fwd setup -0.72 / hold -0.69 (TC12 -1.14 / -0.85). Remaining d2h term is
  cross-edge: lf (fall) data vs clock edge from lc.lr (rise) one UI later -> rise/fall asymmetry of
  rate_clock_mux (1.27 vs 1.11) and lf/lr clk->Q (2.34 vs 1.68) both count. Needs an interface decision
  (same-edge reference, or matched-edge launch), not more placement.
- -buffer_gain is deprecated/ignored by this OpenROAD: pA == pB, gain sweep is a no-op. Buffer pct 80->30 had
  no area effect (gain buffers 0.258 mm2 come from repair_design itself).
- Congestion: TC12 post-CTS odb at GRT_ADJUSTMENT 0.3 overflow 65.7k; at 0.15 + 30 iters -> 0 overflow.
  pA at 0.3: 75k. Config GRT_ADJUSTMENT 0.3 -> 0.15. run12 killed (superseded). run13 (TC13) full flow started.
- AGC remap: LNA -6 dB index -> lna.match.att=2, gain_db=1 (gain_lo off); map hash 0x2102; DT-8 logged in
  scratch/reviews/interface-changes.md. pattern assertion made X/reset-safe. rtl-checks, pattern, fast_gain pass.

## r4b (agent 4, coordinator D2H decision: ODDR / same-edge)
- D2H launch is now an ODDR per lane: pin = hio_s ? q_f : q_r through the lane's hio_x mux2_2 (was xor2):
  every pin edge is a select edge through identical cells (clock lane: q_r = 0, q_f = clk_en). Same pin
  values as the XOR form (derivation in pt_host_link.sv lq comment). q_r D = q_r_d ^ (lp&run ? x.P1 : f3)
  (rising sources only); q_f D = hr, a per-lane rising register computed from the next state of x/f3.
  Launch flops, hr and the 11 mux selects all on ONE net hio_s (fixed clkbuf host.gearbox.hio_sel):
  pC (separate select) had CTS put 10 delay buffers + a 2-level subtree on the select only -> glitch
  hold -4.39; pC also had a half-cycle nsel -> q_r path (-3.5) from the first ODDR form. Both fixed in
  RTL (syn18); pC2 checks it.
- SDC: q_r/q_f -> pin arcs disabled; data_check of each flop against the select edge that hands it to
  the pin; same-edge output windows (clock-as-data via the select) referenced to d2h_fwd rise<->rise,
  fall<->fall; clock-lane mux case-analysed to a buffer. In LibreLane steps (STEP_DIR) the windows and
  data checks are off (OpenSTA asserted in RequiredVisitor during multi-corner repair_timing, pC run 1);
  sta_signoff / probes apply them. x/f3 -> q_f multicycle removed; hr gets the hcore->hddr MC 2.
  syn16 unplaced: window -0.05/+0.34 (TC12 -1.14/-0.85); pC placed: -0.14/+0.31.
- lc_rx: en_r -> two kept replicas (pt_lc_en_rep), data-only regs (cur, sym, pb, pa, dec, bad) ungated.
- AGC override: sim/tb_agc_override.sv (16384 checks, mutation fails), added to transceiver-digital-rtl-checks.
- register-map.md lna.gain row text moved into the spec (range_text) so the generator keeps it; hash 0x2C7C.
- H2D (coordinator: same approach if relevant): not an edge-asymmetry problem. pA: setup +1.53, hold -0.99:
  CTS adds 3 clkbuf_16 levels after cap_root (capture clock ~2.5 ns vs data ~1 ns). LibreLane CTS has no
  per-clock exclusion and dont_touch clock nets are an error. Options for the coordinator: (a) custom CTS
  step with -clk_nets excluding h2d_cap + fixed cap_root fan-out buffers, (b) fixed data delay per lane.
- run13 (TC13 RTL, GRT_ADJUSTMENT 0.15) still in GRT extra iterations (2nd pass, NDRs being dropped).
- run14 killed twice (crashing SDC; then stale pre-hr RTL). Relaunch after pC2.

## r4c
- ODDR split into two generated clocks: d2h_oddr (hio_sel: launch flops + hr) and d2h_osel (hio_msel: 11
  selects; d2h_fwd derives from it). With one clock CTS treated selects as macro sinks and balanced them
  against the flops with 13 delay buffers (pC3 glitch hold -5.2). pC4: 0 delay buffers, glitch +0.60 / +1.46,
  D2H window -0.14 / +0.31 (TC12 -1.14 / -0.85). Residual setup -0.14 = data-fall vs clock-rise through
  identical cells (inherent to any lane that can switch either way): next lever is D2H_SKEW/ the output
  stage sizing, not structure. sta_signoff: clocks d2h_oddr, d2h_osel; window from d2h_osel.
- pC4 flow view: setup WNS -3.87 (lc_tx skid/advance chain sAv -> advB -> advP2A -> pop -> hq, wtx; needs a
  registered-ready redesign), hold -5.08 remaining after post-CTS hold repair at egress.mem (check at
  post-GRT before acting). Wired RX en_r no longer in the top list.
- SLI7-R: wire_rx_ptrim_en output (DT-9). Next full run TC15 = run14 RTL + this port.
- Queued (awaiting upstream decisions): W7-GEAR (incl. SLI7-M second EW flop), R8-ARCH.
- run14 (TC14, final ODDR RTL, syn19) running. run13 (TC13) in GRT at 0.15.

## Takeover 2026-11-13 (agent 5, r5): resume after the r4c agent died
State found: uncommitted r4c edits newer than the notes above (2026-11-12 04:00-04:35), no P&R evidence for them:
 - pt_cells.sv / pt_host_link.sv: D2H lane inverted between hio_x and the pin (new clkinv_2 hio_i after the ODDR
   mux, pin driver buf_8 -> clkinv_8) so the stagger mux switches with the opposite polarity to hio_x (rise/fall
   balance); hio_placement.cfg + config.json dont_touch lists updated.
 - pt_host_link.sv / pt_cts_h2d.tcl / SDC / run script: H2D capture clock hand-built (cap_root -> hio_cbr/cbf/cbh
   clkbuf_8 per row -> 30 flops); CTS wrapper restores it after clock_tree_synthesis (coordinator option a).
 - pt_linecode.sv: lc_tx stage P is a 2-entry queue; advA = uge36 && !sPv2 (registered ready).
 - SDC: egress_mem_hcore generated clock removed (hcore propagates through the mux), ODDR clocks only in CTS/sign-off.
 - run14 (TC14) died in GRT (congestion, rc=2) after CTS; run13 abandoned. No routed macro exists for any RTL after AC1_R4.
Regression on that tree: transceiver-pair-word-formal FAILED (pt_d2h_gearbox prove): the harness still compared the
gearbox lane outputs, which are now inverted. Fixed in verification/formal/pt_d2h_gearbox_fv.sv (pin = ~lane). The
04:30 rtl-checks failure was only "Sources changed during run" (pt_linecode.sv edited at 04:35 during the run).

### G3: POR override strap (DT-10)
 - rtl/pt_digital_macro.sv: new input por_bypass; rst_n = reset_n_pad & (por_n | por_bypass). Static level, one OR
   gate, no flop/clock/SPI/analog. por_flag keeps following raw por_n (stuck POR is visible: reads 1, cannot clear).
 - Alternatives: RESET_N double-pulse / keyed sequence needs state that nothing initialises when the POR is dead
   (random power-up, a counter or shift register in the reset path) -> rejected; "remove the POR from the reset
   path" loses the POR for boards that tie RESET_N high -> not chosen (the strap gives the same thing on demand).
 - No free pad: all 56 signal sites of the ring are assigned (contract.json bond_map_current). Row DT-10 asks
   pads/assembly for a strap source: (a) share DBG_OBS1 (bi_t, IE=1, PD=1 hard ties, strap = pad Y), (b) a
   dedicated in_c PD=1 site if one is freed, (c) bond option. Until then integration/pt_chip.sv ties it 0.
 - Regfile formal: `assume(por_n || !rst_n)` removed (POR no longer implies reset), P6 now `!por_n -> por_flag`;
   proof passes with por_n free (60 s).
 - Test: verification/check_por_bypass.py (sim/tb_por_bypass.sv, 21 checks, 4 mutants must fail), make
   transceiver-por-bypass, added to transceiver-digital-rtl-checks.
 - Independent review (2026-11-13): macro change GO-with-conditions; G3 NOT fixed at chip level. Sharing DBG_OBS1
   as a bidirectional strap is NO-GO (self-reset through a runt pulse with a dead POR, POR silently removed when
   the mux drives 1, loop through code 36) -> DT-10 now asks for an INPUT-ONLY strap pad (in_c PD=1), user picks
   the site. Acted on: RESET_STATUS b2 = live strap (regfile generator), bench runs the host clock and checks the
   host/core reset domains, mutants split_host / no_readback, `make transceiver-por-bypass-chip` = closure
   tripwire (fails today by design), stale "RESET_N AND POR" text in the generator/contract fixed,
   sim/tb_chip_io.sv ABI_VERSION expectation 0x0002 -> 0x0003 (+ RESET_STATUS read): check_chip_io passes again.
   Not done: post-route GLS of tb_por_bypass (needs a re-hardened macro), chip-level strap test and the
   transistor-level POR-held-low co-sim (need the pad), board-requirements entry.

### r4c D2H lane inversion: reverted (patch kept in r4c_d2h_inversion/inversion.patch)
pC5 (RTL with hio_i + clkinv_8 pin drivers): TritonCTS segfaults (separateMacroRegSinks, null instance) right
after `Net "host.clk_out.I1" has 1 sinks`: the clock-lane pin driver is now a clock INVERTER whose output net has
only the d2h_clk_pin port. Neither set_disable_timing on the driver nor deleting the hsdr clock in the CTS step
avoids it (the walk is on the netlist; hddr reaches the same net). With buf_8 (pC4) CTS prints "0 sinks,
skipping". If the rise/fall idea is retried: keep buf_8 as the pin driver and put the second inversion before it.

### G6 + pre-mortem item 5: SPI-only sign-off with top-level routes, OCV and the foundry libraries
Tools: verification/digital_hardening/spi_signoff.py + spi_signoff.tcl (pad Liberty tables: spi/pad.tcl ->
spi/pad_delays.json). Corners: slow = sc ss_125C_3v00 + io ss_125C_2v97 (bounds ss/3.15 V/85 C), fast = sc
ff_n40C_3v60 + io ff_n40C_3v63 (bounds ff/3.63 V/0 C), typ tt, plus in-window characterized ss32 / ff22.
Route model (two-sided): 2.6-3.5 mm, R 50-1400 ohm, C 0.19-1.0 pF, pad input edge 0.3-5 ns, MISO board load
5-30 pF, host tco -2..+5 ns, host budget 8 ns (5 setup + 3 round trip). Database: run14 step 33 (post-CTS
resizer, placement-estimated RC x0.8/1.0/1.25); NO routed macro exists, so every number below is provisional.
 - Pad cells are weak into the top-level wire: bi_24t PAD->Y 3.0-6.6 ns and up to 4.7 ns edge at the macro pin
   (slow bound, 1.05 pF); bi_t A->PAD 5.9-10.1 ns (5-30 pF board load, PDRV=10).
 - Setup (no OCV): limiting path wr_data -> register file (half cycle, 65.3 ns at the slow bound).
   Minimum period: slow 130.6 ns (7.65 MHz), ss32 108 ns (9.2 MHz: the 10 MHz constraint is NOT met in-window
   with the route model), typ 62.6 ns, fast 35 ns. MISO to host: 80.8 ns chip only / 96.8 ns with the host
   budget at the slow bound, because the flow left a buf_2 on spi_miso (13.4 ns, 22.7 ns slew into 1.04 pF).
   -> SDC now has set_load 1.05 pF on spi_miso/_oe and set_input_transition 0.25-4.7 ns on the SPI inputs.
 - Hold, SPI domain (pg1 -> pg2 worst), no derate: fast +0.121, ff22 +0.222, typ +0.437, ss32 +0.861, slow +1.18.
   With +-5 % early/late on all delays: fast 0.000, ff22 +0.069. With +-8 %: fast -0.072, ff22 -0.023 (FAIL),
   typ +0.096, ss32 +0.26, slow +0.49. The run14 hold margin does not survive OCV.
 - Fix in the flow (this round): SDC clock-network derate PT_OCV = 0.08 in every step (RSS of ~5 % local
   mismatch and ~5-6 % from up to 117 mV supply difference, rounded up); foundry ff_n40C_3v60 added as an
   STA + resizer corner; hold slack margin 0.1/0.05 -> 0.25/0.2 ns (PL/GRT).
   Target: SPI domain >= +0.15 ns at +-8 % on all delays at BOTH fast libraries; every other domain >= 0.
 - Max safe SCLK (provisional): 5 MHz (35 % margin at the slow bound); bring-up <= 1 MHz as planned.

### AP4-8 area: first measurements
 - MAX_FANOUT_CONSTRAINT is not the lever: post-GPL repair cell area 1.619 (12) / 1.597 (24) / 1.596 (40) mm2.
 - The 0.26 mm2 of "gain" buffers appears in ResizerTimingPostCTS (1.62 -> 1.91 mm2), i.e. it is setup repair.
   pC7 tests whether the 10 MHz SCLK constraint is what drives it (SCLK at 200 ns).
 - 2.45 mm2 at 75 % needs <= 1.84 mm2 of cells AND a routable design; routing does not converge today at 66 %
   (run13/run14 GRT). Not reachable without the registered-pop RTL work; no die-size change made.

### Queue received from the coordinator during this round (NOT started unless noted)
 1. Mode walk (scratch/reviews/mode-walk.md, MW- rows; regression scratch/reviews/mode-walk/cfg_map.py; TOP- rows
    to come): decode glue goes into the macro, register map follows the cells. MW-1 lo_ext EXT/INT/CMLSEL fields
    + validator; MW-2/19 clockmux/prescale/wordclk one-hot decoders, ref_clk driver, h2d_clk for host_follow;
    MW-3 rf_rx_clk/rf_tx_clk/rf_rx_valid/rf_tx_request producers; MW-4 bbfilter en/dir_tx + per-channel fields at
    cell widths; MW-15 SER_EN / pt_clocktree_slow serializer model; MW-27 re-harden (macro pins 568/255/57 vs
    RTL 579/256/58) and fix the evidence freshness flag; bind en_eff / island_off / wire_rx_ptrim_en /
    rf_tx_clk_out. (tb_chip_io fix done; MW-26 = DT-10.)
 2. Always-on audit (scratch/reviews/always-on-audit.md section 7): F2 core.aosc.enable reset default (1 today,
    analog evidence assumes 0; proposal: reset 0, nothing needs the oscillator before SPI, register can still
    pulse EN low for the stuck state F3) and assembly must bind aosc.EN to debug_cfg[246]; F5 bandgap enable
    interlock (reject bgap_ena 0->1 while ref_sel_vbg = 1 or any dist_en = 1, or a 10 us ordering rule); F11 drop
    or rebind ATB code 4 monitor_por_threshold (never to vcap); F1 = DT-10 pad + POR-held-low co-sim.
 3. Older requests found in interface-changes.md: RC-16k lna.bias.lo + validator, FS-2 validator rule
    (cap code <= 1 => q_trim >= 6) and per-PGA-code calibration table, WT24 r6 EN_POST/TRIM, LO17/LO18.
 4. r4c timing: D2H residual -0.14, lc_tx ready chain (2-slot P stage is in, regression passes, timing unmeasured
    until pC6), egress hold, then R8-ARCH + W7-GEAR.
 - Independent review of the SPI/hold sign-off (2026-11-13): method GO-with-conditions, numbers reproduce,
   flow fix NO-GO until a run with it exists. Acted on: foundry ff library is now a 133-cell copy with the same
   cell set as the characterized libraries (foundry_subset.py; the full library broke STA with STA-1112 and
   would have offered 96 unmodelled cells to the resizer); hold margins 0.3/0.3; spi_signoff.py reports no safe
   SCLK when hold fails and refuses vacuous passes; SDC comment no longer claims sta_signoff.py derates.
   Open (queued): pads driven outside their Liberty range in the route model (needs the pad repeaters, then
   rerun pad.tcl in range with the real pin cap 0.16-0.24 pF); CS_N-rise vs write-edge is untimed (host rule
   added to DT-11; structural fix = register the write qualifier in pt_spi); all sub-0.2 ns hold paths are
   synchronizer stage pairs on different top-level clock branches (fix = kept delay cell between the stages or
   one clock leaf per pair); sta_signoff.py has no OCV / foundry-ff rows for the other domains; state the
   target as >= 0 at +-14 % (sensitivity -0.024 ns per 1 %); SCLK high >= 71 ns / low >= 49 ns rather than
   "5 MHz"; --nl/--spef path never exercised; MISO pad slews in pad_*.log are from the wrong arc (unused).

### pC6 (2026-11-13): current RTL + clock OCV 8 % + foundry ff corner + hold margins 0.25/0.2, to post-CTS resizer
(run: pC6, part2.sh + resume.sh; logs wns_pC6.log, wns_pC6_noocv.log, h2d_pC6.log, spi/pC6_ocv0.08/)
 - CTS runs again with the D2H inversion reverted. pt_cts_h2d.tcl: name match fixed (ODB escapes brackets: the
   30 capture flops were not found); restore reports 30 flops, 34 pins reconnected, 9 CTS buffers removed, but
   5 chained CTS buffers were left (removal was single-pass; now iterative, NOT re-run yet).
 - SPI-domain hold with +-8 % on all delays: foundry ff +0.168, ff22 +0.228, slow +1.382 (run14: -0.072 /
   -0.023 / +0.49): target >= +0.15 met at post-CTS. All-domain hold at ff22 with the clock derate: WNS +0.32.
   Cost: 1068 hold buffers, 0.014 mm2. Cell area 1.764 mm2 (67.4 %), run14 1.91.
 - Setup, ss_032C_3v15, per capture clock, WITH / without the 8 % clock derate (cost of OCV 0.1-0.5 ns):
   wrx -5.37 / -5.10 (lc_rx off -> sym), wtx -4.45 / -4.19 (lc_tx rdA -> lc_q: the 2-slot P stage did not close
   it), egress_wtx -4.46 / -4.01, hcore -4.26 / -4.01 (frame_tx avail_words -> d2h_quad), rftx -4.27 / -4.13,
   ref -3.66 / -3.53 (fcb tick -> ev_cnt), hddr -3.63 / -3.13, h2d -3.29 / -3.13, ctw -2.97 / -2.85,
   ingress -1.93 / -1.69, ctdet -1.56 / -1.47, h2d_cap -1.54 / -1.20, hword -0.92 / -0.83. NOT closed; the
   >= 10 % margin target is far away and needs RTL (registered pops / pipelining), not flow settings.
 - H2D pin capture (ss32, hand-built clock, 5 CTS buffers still in the path): setup +0.58, hold -0.36
   (pA: +1.53 / -0.99). Window is 0.22 ns wide but off-centre by ~0.47 ns; ff22 hold +0.37.
 - pC7 (SCLK constrained at 200 ns, area experiment) was killed on the coordinator's throttle: no result.

## Takeover 2026-11-13 22:30 (agent 6, r6): mode-walk register / decode rework FIRST, timing after
Coordinator order: MW/TOP rework first, pipelining afterwards on the reworked RTL. Baseline: integration/top/run.sh
cfg=143 macro=276; scratch/reviews/mode-walk/cfg_map.py 39 pin groups without a field / 12 width / 80 orphans.
Work files: scratch/digital-timing-close/mw/ (spec_edit.py = the re-runnable spec migration from commit 8e5e71c;
spec_edit2.py = second pass with the sub-agents' fields). Regenerate: python3 mw/spec_edit.py && python3 $P/rtl/gen/gen_regfile.py.
Design decisions (r6):
 - Boundary: analog_cfg / debug_cfg / en_eff stay INSIDE the macro; rtl/pt_ctl_decode.sv makes the c_* ports of
   integration/top/ctl_ports.txt from generated field wires (rtl/pt_regmap_fields.svh, new generator output).
 - Dead fields are deleted from the specs (addresses compact; map hash changes), not trimmed: pga_*, rxfilter_*,
   txfilter_*, quadrature, wirepll, tmds, bias.trim, lna.gain, clockmux.state, clocktree.state, refinput.select,
   consolidation.pll / quadrature, debug.wclk_obs / wdbg_obs (pads retired, PD22: wire_status now DBG_OBS codes 37+n),
   debug.clk_select.rf_lo (replaced by rfpll.config.lo_mode), every *.enable duplicate of a state field.
 - New fields: lna.match.gain_lo, lna.bias.lo (+rule), lna.agc.code0..3 (programmable opcode-4 LNA table, RC-16p),
   bbfilter_i/q.trim (cut 7, gain dB index 5 -> LUT, qt 4, dcf 9; FS-2 rule), adc.config (interleave, acquisition),
   rfpll.config (lo_mode, vco_coarse, lo_n, lo_icp, lo_preset, atb_enable), clockmux.config (ring_ref, three prescalers),
   ring_l.config, ring_c.config (line_pll: D-HF fix, modulus, band, kp), ctle peak/lf_zero, termination hs_*,
   slicer.offset trim_d0..3/e0..3 (10 b), slicer.threshold (vthdac, vsel), slicer.capture (rcsel, rate_mode),
   wiredtx post_polarity, txpad term_request.
 - D-EN: enable = (state == active) & island_on everywhere (no published cell has a bias-only pin for "warm").
 - Always-on: core.aosc.enable reset 0; pt_bgap_interlock (128 SCLK cycles after bgap_ena before ref_sel_vbg / dist_en_*);
   ATB code 4 reserved (hardware false).
 - IX-11: transport opcodes 5 / 6 load VTH_A / VTH_B (pt_core, wired ownership), override the fields until ENABLE = 0.
 - rf_rx_valid / A-B merge: rtl/pt_boundary.sv pt_adc_merge; IX-12 lane select pt_wrx_lane (dual full lane NOT possible
   on the 40-bit ingress: open).
Sub-agents (new modules, own benches): pt_monitor (done: 146 FF, 54 checks, 9 mutants), pt_wrx_ctl, pt_usb, pt_wtx_ctl,
pt_spi fix + pt_por_path + pad demand (running at the time of writing).

## r6 state 2026-11-14 (after the rate-limit restart): rework compiles, quick regression green, committed
What is in the tree (all under $P = projects/programmable_transceiver_platform):
 - spec/analog-architecture.json control_fields + spec/debug-controls.json rewritten by mw/spec_edit.py + spec_edit2.py
   (always from commit 8e5e71c; rerun both then rtl/gen/gen_regfile.py, then integration/gen_pt_chip.py).
 - Generator: new output rtl/pt_regmap_fields.svh (one wire per bus field, f_<group>__<field>); WCLK_OBS / WDBG_OBS gone
   (wire_status on DBG_OBS codes 37+n); RESET_STATUS b4:b2 = por_path {por_masked, override effective, strap}; new
   status registers 0xF7-0xFD (monitor, wired, usb).
 - rtl/pt_digital_macro.sv rewritten: pt_por_path, pt_reset_seen, CP4-1 clamps (pt_iso_and, 130 bits), pt_digital,
   pt_monitor (fault), pt_vreg_seq, pt_bgap_interlock, pt_ctl_decode, pt_wtx_ctl, pt_wrx_ctl + pt_wrx_lane, pt_usb,
   pt_adc_merge, pt_det_clk. pt_clocktree_slow is no longer instantiated (file and its own checks kept).
 - integration/pt_chip.sv GENERATED from integration/top/pt_chip.conn by integration/gen_pt_chip.py.
 - Benches / checkers: verification/check_top_modes.py (integration/top/sim/tb_top_modes.sv: 133 checks in 10 mode
   sections, 9 decode mutants, CP4-1 clamp coverage, island-off zero masks), check_monitor.py, check_usb.py,
   check_wtx_ctl.py, check_wrx_ctl.py, check_por_path.py, check_spi_csn_race.py; sim/tb_agc_override.sv rewritten for
   the decode; tb_por_bypass / tb_chip_io / tb_regfile* / tb_digital_* updated. make transceiver-top-modes (in
   transceiver-digital-rtl-checks) and make transceiver-ctl-blocks. Full serial regression: allchecks6.sh ->
   allchecks.r6.log.
Numbers: integration/top/run.sh cfg 143 -> 0, macro 276 -> 0 (still FAIL on demand 12, staged 4, iso audit: analog /
chip-top items); scratch/reviews/mode-walk/cfg_map.py 39 / 12 / 80 -> 0 / 0 / 0 (its MAP table was updated to the new
fields; INTERNAL lists macro-internal consumers by name).
Known gaps (also rows DG6-1..13 in scratch/reviews/interface-changes.md):
 - pt_por_path: independent review found the one-flop key blocking (scratch/reviews/por-path-review/REPORT.md); the
   16-bit key fix is in the tree, its bench runs were still finishing at commit time; needs a re-review.
 - No independent review of the rework as a whole yet (launched after the first commit).
 - SDC (integration/pt_digital_macro.sdc), pin_order.cfg, hardening config (VERILOG_FILES, dont_touch for iso_and /
   key flops / por path), GLS bench tb_digital_gl.sv, sta_signoff.py, macro-contract.md are NOT updated: the macro
   cannot be hardened as is. This is the first step of the timing work (work item 3).
 - Monitor cannot run in RF payload modes (aosc forced off while running): decision needed.
 - IX-12 dual full lane, USB 10-bit direct-stream codec, HS x4 repetition: not built.
 - 13 ATB trunk / master leaves not gated by island (procedure conflict): ruling needed.
 - FF count rises by about 146 + 247 + 255 + ~60 (wtx) + ~30: area check pending (decap trade open).
Next: (1) full regression log, fix fallout; (2) independent review of the rework, fix; (3) SDC / pin order / config for
the new boundary, then pipelining on this RTL (wrx lc_rx, wtx lc_tx, hcore, rftx, ref, hddr, h2d), balanced / staggered
clock launch (PD2: 78.125 MHz component to ~10 %), setup at ss 3.15 V and 3.5 V (per-chip supply trim), routed sign-off
with OCV hold in all domains, GLS, per-mode power.

### r6 follow-up: hardening inputs for the new boundary + first timing numbers on the reworked RTL (syn_r6)
 - integration/pt_digital_macro.sdc updated at port level (ctref / ctdet clocks gone, detector divider on ctw, c_* ports
   as quasi-static SCLK-launched outputs with false paths from the other domains, wrx picker pins on wrx, FUP/FDN on
   ref). verification/digital_hardening/config.json: new RTL files, clock ports. pin_order.cfg: every one of the 300
   ports matched, sides are PROVISIONAL (consumer-facing order needs the v7 floorplan). NOT done: dont_touch entries for
   the 130 iso_and cells / key flops / por_path, hio lists unchanged, sta_signoff.py, gls.sh + sim/tb_digital_gl.sv
   (still instantiate the old ports), macro-contract.md.
 - syn_r6 = ./syn.sh syn_r6 (LibreLane synthesis + OpenROAD pre-placement STA, ideal clocks, ss_032C_3v15; 2 min).
   Cell area after synthesis 1.375 mm2 (r5 syn20: 1.241; +0.134 mm2 = +10.8 %; sequential 0.608 -> 0.687 mm2): the new
   fields (shadow + active flops) and ~700 FF of control blocks. The 66 % utilisation that did not route is now ~73 %
   before repair: AREA IS THE FIRST PROBLEM of the next round (die fixed, decap trade open).
 - Worst setup per capture clock, post-synthesis (optimistic by 0-3 ns vs mid-PnR per the r3 calibration):
   ref -15.3 (fcb result -> pt_wrx_ctl pulse counter: the counter's 5-cycle evaluation exception does not cover the new
   diff_ref consumers; register fc_diff in pt_wrx_ctl on fc_upd and extend the exception), fc4 -10.4 (pt_monitor counters
   are constrained at the 6.4 ns frequency-counter period on the aosc pin; real aosc period >= 16.7 ns: give fc4 its own
   period, then about 0), wrx -9.6 (pt_wrx_ctl picker el_sum -> step / slip count: needs a pipeline stage), wtx -6.0
   (pt_usb tx phase -> tx_ready -> core lc_q / egress pop: register the direct-stream request), hcore -0.28, h2d +0.25,
   ctw +0.47, hddr +0.66, hword +0.77, egress_wtx +1.45, ingress_wrx +2.5, rftx +6.9, rfrx +9.7, sclk +16.4.
   Cross-domain paths that need exceptions or structure: monitor fault_m (aosc) -> pad requests / async clears of the
   wtx, usb flops (fault is an asynchronous level: false path + recovery waiver), vreg_seq -> wire_tx_request_q clear,
   wrx st_freq_ok <-> word-domain synchronizers (first stages not named *.meta*: add to the synchronizer list),
   lane.ew_f (falling-edge edge-word register) -> ingress din -1.0 (half-cycle path: move the lane mux behind a register).
 - So the "pipelining" list of the brief now starts with the NEW blocks (ref, fc4, wrx, wtx), then the old list.

## r6 end of round (2026-11-14 ~06:45): reviews handled, new blocks pipelined, numbers
Commits: 3cff484 (rework), ff74593 (hardening inputs), f2af5bc (review fixes), + the last one of this round (timing of
the new blocks, observation ledger, SDC exceptions).
Reviews (all independent agents, artefacts only): rework GO-with-conditions (scratch/reviews/dg6-review/; its decode
table is now verification/check_decode_table.py: 3656 vectors, 0 mismatches); pt_por_path first review NO-GO items
P1/P2 -> 16-bit key -> re-review GO-with-conditions (scratch/reviews/por-path-review/REPORT.md, r2/). Rows DG6-14..16.
Timing sub-agent on pt_wrx_ctl / pt_monitor / pt_usb (ports unchanged; latencies: FLL pulse 9 ref cycles after the
counter update, picker reacts 5 words later with hold + 3, usb tx_ready is a flop with a one-quad holding register,
usb rx 2 clocks later): pt_wrx_ctl 247 -> 446 FF, pt_usb 255 -> 312, pt_monitor 146 -> 149; module checkers pass.
POST-SYNTHESIS timing of the final RTL (syn_r6t netlist, STA syn_r6s; ss_032C_3v15, ideal clocks, updated SDC; the r3
calibration says mid-PnR is 0-3 ns worse; run-to-run noise 1-2 ns), worst setup per capture clock:
  ref -2.39 (pt_wtx_ctl lt_cnt / pt_tx_pad_sequence request -> left: next to pipeline), wrx -0.60 (prbs_check; lc_rx
  hit -> cand -0.77 in the other run), hcore -0.13, wtx -0.08 (lc_tx sA -> lc_q), h2d +0.25, ctw +0.39, hddr +0.66,
  d2h_oddr +0.72, hword +0.77, h2d_pin +1.10, egress_wtx +1.35, fc0-3/5 +2.0, ingress_wrx +2.48, fc4 (aosc, 16 ns)
  +2.62, h2d_cap +2.75, rftx +6.3, rfrx +8.8, sclk +15.3.
  Cross-domain still negative: monitor cause flop (ref) -> wire_tx_request_q clear -7.3 (asynchronous fault path:
  needs a name-safe false path; the flop is named after the regfile port), usb.rdy_q -> core egress roh2 -1.34 (the
  old egress take chain behind the direct-stream select), D2H window -2.1 / h2d capture -1.0 / hddr -> oddr -0.8 (the
  known host-link items; unplaced numbers).
Cell area after synthesis 1.404 mm2 (r5 1.241: +13 %); sequential 0.708 mm2.
NOT done in this round (work item 3 of the brief): no P&R, no routed sign-off, no OCV hold on a routed macro, no GLS,
no per-mode power, no H2D centring / D2H inversion work, no balanced / staggered clock launch (PD2 requirement), no
3.5 V setup point (no characterized library at 3.5 V exists: libchar.py run needed), sta_signoff.py not extended,
gls.sh / tb_digital_gl.sv still on the old ports, CP4-1 clamp pins not excluded from input-port buffering in the flow.
Order for the next agent: (1) area (1.40 mm2 before repair on a die where 1.24 did not route: decide with the
coordinator what goes or whether the macro grows; candidates: direct (no-shadow) fields for the 80 slicer trim bits and
other static trims save one flop per bit, pt_wrx_ctl 446 FF); (2) flow config for the clamps + dont_touch lists + GLS
bench on the new ports; (3) pipelining list above, then the old list; (4) hardening with the pC6 hold flow.

## Takeover 2026-11-14 07:07 (agent 7, r7): flow readiness, first P&R of the r6 RTL, monitor time base
WARNING FOR THE SUCCESSOR: the account hit its usage limit at ~07:30 UTC (resets Nov 17 21:00 UTC) while two
sub-agents were running. Everything below marked UNVERIFIED was edited but not regression-tested. NOTHING of r7 is
committed (last commit 9211b44). Before committing: run the serial regression (allchecks6.sh) and fix fallout.

Coordinator rulings received (r7 brief): monitor gets a second, host/reference-derived time base (no aosc in RF
payload); 13 ATB trunk leaves stay ungated in RTL (row to pads/core-support, audit waives only with evidence);
host-follow on the TX ring = die-1 baseline pending timing / wired RX confirmation; board rules go into
spec/board-requirements.md (done: B49 RESET_N host-drivable + low through power-up with the strap, B50 SPI idle
levels / FPGA pulls (1 k resistors), B51 rescue procedure); area: no function deleted, cheap reductions only.

Done (in the working tree, uncommitted):
 - rtl/pt_cells.sv pt_async_gate (kept AND2, instance *.ag): monitor.fault_gate (the monitor's fault level) and
   wtx.w_rst_gate (word-domain reset of pt_wtx_ctl). SDC: set_false_path -through those two Z pins, justification in
   the SDC comment (every consumer synchronizes or uses an async clear with a re-timed release). Replaces the
   name-based "*monitor.fault_m*" false path and removes the ref -> wtx -7.3 ns recovery path. Post-synthesis check
   (syn_r7a): no ref -> wtx path left; wtx -> egress_wtx +0.13.
 - rtl/pt_tx_pad_sequence.sv: the two magnitude compares are registered flags (`last` == left <= 1, `tmo_ge`);
   random old-vs-new co-simulation, 4 parameter sets x 2M cycles, 0 mismatches, invariants hold
   (r7/padseq_eq/tb_eq.sv + old.sv). NOT yet through check_wtx_ctl.py / synthesis (ref was -2.48 on left[]).
 - Flow: verification/digital_hardening/config.json: RSZ_DONT_TOUCH_LIST += the 130 clamp pin nets of
   integration/top/generated/macro_clamps.txt (same mechanism that keeps buffers off h2d_pin[*]: buffer_ports and
   hold repair skip dont_touch nets; LibreLane unsets dont_touch outside resizer steps, CTS skips 1-sink nets);
   RSZ_DONT_TOUCH_RX = iso_and cells, rseen key flops, por_path key flops, *.ag gates; DIE_AREA 1716 x 1865 (see
   macro-area.md). New checker verification/digital_hardening/clamp_check.py <netlist> (--selftest): every clamp pin
   reaches exactly one .iso_and A1 and nothing else (antenna diodes allowed); passes on the synthesis netlist; MUST be
   run on the final routed netlist (pnl/nl) of every hardening run.
 - SDC: por_path key flops are found in hierarchical OpenSTA too (LibreLane STA steps died on "expected 16 por_path
   key flops": the r6 SDC had only ever been read by flattening OpenROAD).
 - sta_signoff.py: foundry ff_n40C_3v60 corner, ss_032C_3v50 corner (skipped until the library exists), clock list
   updated (ctref/ctdet gone; h2d_pin, hsdr, mon_host, rfhalf, egress_mem_sclk), missing clocks no longer fall back
   to the global worst path, new `slack_ocv_all` view (+-8 % on ALL delays, PT_STA_OCV_ALL), PT_STA_CORNERS filter.
   Not run yet (needs a routed macro).
 - libchar.py: corner ss_032C_3v50 (ss, 32 C, 3.50 V) added. Run started 07:09 in scratch/digital-libchar
   (`libchar.py run --cells used --corners ss_032C_3v50 --jobs 1 --cache cache`, log run-3v50.log), ~200 s per cell,
   115 cells; PAUSED with SIGSTOP at 07:20 after 1 cell to keep the 3-job limit (pids 4092541 4092623: `kill -CONT`
   them, or just restart the command: finished cells are cached). Then `libchar.py build --cache cache --out <dir>
   --corners ss_032C_3v50` and copy the .lib into verification/digital_hardening/liberty/.
 - macro-area.md v1 (first estimate for the die-fit study: book 3.2 mm2, range 3.0 - 3.45).
 - Disk: deleted part_g0/4/8, pC4, pC5, pC7, run13 (20 GB). pC6 and run14 kept (reference for hold flow / SPI sign-off).
UNVERIFIED (sub-agent "monitor second time base" died mid-work; its edits are in the tree):
 - New field monitor.config.timebase (0 = aosc, 1 = transport core clock / 2) in spec/analog-architecture.json,
   regenerated regfile / regmap / register-map.*; pt_digital_macro.sv: mon_div (pt_clock_dff toggle on core_clk) and
   mon_mux (pt_clock_mux, static select) feed the monitor's mon_clk; SDC: generated clock mon_host (hcore / 2),
   logically exclusive with fc4; pt_monitor.sv header text; check_monitor.py / check_top_modes.py /
   integration/top/sim/tb_top_modes.sv partly extended (it stopped at "now the bench section": the timebase = 1 bench
   section and the two mutants are probably missing or incomplete). No regression target was run by it. Rationale
   for core clock / 2 (not H2D_CLK, not REF): in RF payload with an external LO the REF pads carry the LO, so the
   only clocks that surely run are host-derived; the ring-derived core clock keeps running when H2D_CLK disappears
   (ring free-runs), so requirement 1 (H2D_CLK present) is detected; loss of the time base itself is only seen
   while ref_clk runs (ref-domain watchdog) -> analog present detector requested from pads/core-support (row not
   written yet).
 - Independent reviewer of commit 9211b44's pipelining (scratch/reviews/dg6-pipe-review/: tb_fll.sv, tb_pick.sv,
   no REPORT.md yet) was still running; if there is no REPORT.md, the review is NOT done: restart it.
Running at the time of writing:
 - P&R r7a (go_r7.sh r7a pnr -> scratch/digital-timing-close/r7a, tag R7A, 4 CPUs, started 07:26): full LibreLane
   flow of the tree as it was at 07:26 (includes the unverified monitor time base, the pad_seq change and the async
   gates), 1716 x 1865, pC6 hold flow (8 % clock OCV, foundry ff corner, margins 0.3 / 0.3). Purpose: first real
   area / congestion / post-CTS / post-route numbers of the r6 RTL, clamp check on a routed netlist, sign-off
   tooling shake-down. Status file r7a.status; when it ends: `./go_r7.sh r7a export sta gls` (gls.sh and
   sim/tb_digital_gl.sv are STILL on the old ports: rewrite first), clamp_check.py on final/nl, update macro-area.md.
Facts measured this round:
 - Cell delays at ss_032C_3v15 (post-synthesis path report): clk->Q 1.6 - 2.1 ns, simple gates 0.6 - 1.6 ns, flop
   setup ~1 ns: a 10 ns cycle holds about 7 gate levels, 12.8 ns about 9. Post-synthesis slacks near 0 therefore
   become -2 .. -4 ns routed (pC6). Closing every domain at ss / 3.15 V needs roughly a third less logic depth
   everywhere, or the 3.5 V trim point (not characterized yet), or the reduced rates (wired 2.5 Gb/s = 16 ns against
   the 12.3 ns constraint; host rate / 2, / 4).
 - Area by block (syn_r6t, hier_area.py): regfile 0.227 mm2 (1648 FF: 830 stored bits, 663 of them shadowed, 167
   already direct), ingress 0.199, egress 0.185, top-level glue 0.096, lc_tx 0.071, lc_rx 0.061, wrx 0.054, h2d
   0.046, fca + fcb 0.082, spi 0.038, usb 0.035. Shadow-less static trims can save at most ~0.03 - 0.05 mm2 of
   cells (2 - 3 %): candidates usb.config, wrx.loop, wrx.picker, monitor.config (timing fields), lna.agc,
   cdr.config, rfpll.config, ring_l.config, freq_count_a/b (needs "direct but locked while ENABLE" in the
   generator: today direct implies live); core.biasgen stays shadowed (rules 27 / 29). NOT implemented.
 - REF frequency: timers assume 50 MHz (REF_PS), the board XO is 25 MHz, the SDC constrains 100 MHz, the HDMI
   forwarded reference (74.25 / 148.5 MHz) is unqualified: the ref-domain control logic will not run at 148.5 MHz.
Not started: clock launch staggering (PD2-6), decap fill cells, per-mode power, 3.5 V STA, ring-monitor readout
codes, IX-12 80-bit capture proposal, USB HS repetition / 10-bit codec, DG6-7 questions, USB EN_MAIN rule, H2D
centring, D2H inversion, the rows for pads/core-support (window comparator `pt_supply_window`, H2D/core clock
present detector, ATB leaf switches safe with the island off), shadow-less trims.

### r7 progress 08:00 UTC (the session continued after the sub-agent's limit error)
 - Review of 9211b44 is DONE: scratch/reviews/dg6-pipe-review/REPORT.md (GO-with-conditions). F1 (stale FLL
   evaluation after a restart) fixed: pt_wrx_ctl ev_ok includes frun. F2 fixed: SDC false-paths only bit 0 of
   wrx.al_sy / lk_sy / fk_sy (count-checked). Open from it: directed macro test of pt_core tx_data / tx_valid alignment
   (USB direct stream, first valid cycle), host doc note for F3 (engine-off drops the held quad).
 - Monitor time base: the sub-agent's bench section (9b) and 4 mutants were in fact written; control-block checks,
   regfile and regfile formal PASS on the tree (r7/ctl-blocks.log, r7/chk_a.log); top-modes running. A second
   independent reviewer (r7 diff: async gates, time base, pad_seq, F1, SDC) was launched at 07:52: report expected as
   its final reply -> save to scratch/reviews/dg7-review/REPORT.md.
 - GLS rewritten for the r6 boundary: verification/digital_hardening/gls_ports.py (port glue from the macro header:
   55 inputs, 245 outputs), sim/tb_digital_gl.sv (logs every output as name=hex), gls.sh (RTL list from config.json),
   gls_check.py (lockstep on all outputs; model on SPI reads + island / ATB / obs outputs; reset safety = no X and
   a zero list of 60 enables / drivers / buses; ISLAND_STATUS b11 masked: reserved island has no switch). Tried on
   the SYNTHESIS netlist of r7a (r7/glstest): regfile stream 3952 records RTL == GL, model 0 mismatches, reset safety
   0 violations, observability ok; loopback RTL locks in modes 0/1/2 (GL loopback not run on the synthesis netlist).
 - Flow lessons: (1) dont_touch INSTANCES break repair_design (RSZ-3006 on rst_n because a dont_touch cell loads it):
   only the clamp pin NETS are dont_touch now; clamp_check.py accepts a resized / pin-swapped AND2. (2) SDC must work
   in hierarchical OpenSTA too (por_path keys). (3) the flow reaches CTS in ~15 min at 4 CPUs.
 - r7a so far (1716 x 1865, core 3.116 mm2): synthesis 1.428 mm2; after GPL + repair 2.061 (66.1 %, incl. 0.093 of
   taps); after CTS 2.194 (70.4 %). Post-CTS, before timing repair, ss_032C_3v15 with 8 % clock OCV: wrx -5.5 (PSEL
   output, an I/O budget: now 2-cycle in the SDC), hddr -4.3 (gearbox prefix -> hr), hcore -4.0 (frame_tx take ->
   safe), ref -3.7 (wtx lt_cnt), sclk -3.5 (reset-seen fan-out -> dbg_obs: now a false path), egress_wtx -3.4, wtx
   -2.9 (lc_tx), fc0-5 -2.0 (fca.fjc prescaler: the clock-source flop was resized to dffrnq_1 and its Q net got a
   gain buffer: 4.5 ns clk->Q), h2d_cap -1.6, fc4 -1.0 (monitor qcnt), hsdr -0.7, h2d -0.7.
   SDC edits made AFTER r7a started (not in r7a): reset-seen false path, picker outputs 2-cycle, wrx sync bit 0.

### r7 progress 08:15 UTC
 - r7a was KILLED at step 33: the post-CTS hold repair was adding buffers for an 11.5 ns "hold violation" on
   sclk -> rf_tx_sample vs rftx_fwd (island_on / reset_seen gating terms of the D-DATAOFF ANDs are SPI statics).
   SDC now: false path sclk -> rftx_fwd / ctdet_out / d2h_fwd / rfhalf; false path from the 8 reset-seen key flops
   (static after reset; their fan-out tree to ~800 gates made sclk -> dbg_obs -3.5 ns); picker outputs two-cycle.
 - r7b = same flow with those SDC fixes and the F1 fix, started 08:02 (go_r7.sh r7b pnr; tag R7B; 1716 x 1865).
   NOT in r7b: pt_wtx_ctl lt_eq (registered lock-time compare; check_wtx_ctl passes with it; pre-edit copy
   r7/pt_wtx_ctl_pre_lteq.sv).
 - Regression on the r7 tree (r7/chk_a.log, chk_b.log): regfile, regfile formal, top modes (incl. the time-base
   section 9b and its mutants), chip-io, por-bypass-chip, observation coverage, contract, readiness, pattern, the
   four formal targets, clocktree-slow: all rc=0. Still running at the time of writing: ctl-blocks (second pass,
   with F1 and lt_eq) and digital-rtl-checks (24 min).
 - Rows written: DG7-1..10 (interface-changes.md "Digital r7"). DG6-7 is answered by WRX10-DG67 and adopted (DG7-8).
   Decisions asked: ATB leaves (coordinator ruling vs PC-10), IX-12 (no 80-bit ingress), USB codec (spec follows quads).
 - Supply trim: libchar has 3 cells at ss_032C_3v50 so far (dffnrnq_1: median delay ratio 0.911 vs 3.15 V, p10
   0.88): 3.5 V buys about 9-12 % delay, i.e. 1.2-1.5 ns on a 12.8 ns path. Not enough alone for paths at -3 ns.
 - Ring monitor for the trim: frequency counter source 3 = ring_osc (analog/timing README: 211 MHz typical, corners
   165-255 MHz). CONCERN: the counter's first stage (digital.fca/fcb fjc prescaler flop) is constrained at 6.4 ns
   (156 MHz) and was -2.0 ns post-CTS in r7a (clock-source flop resized to x1, 4.5 ns clk->Q): a 165-255 MHz ring
   cannot be counted unless that stage closes at <= 3.9 ns at ff and <= 6.0 ns at ss, or the ring output is divided
   in the analog block. To check on the routed macro (sta_signoff fmax of fc0..fc5) and to raise with timing.
 - How to look at a LibreLane STA step: r7/grp.sh <run>/<NN-openroad-sta...> (worst setup / hold per path group).
