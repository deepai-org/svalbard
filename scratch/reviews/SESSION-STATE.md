# Session state at rate-limit stop (2026-11-09 ~23:40 UTC)

The weekly API limit was hit; it resets at 21:00 UTC. Agents died mid-task. The files are uncommitted and may be half-edited.

| Area | State at stop | Resume from |
|---|---|---|
| Digital (rtl/, digital_hardening) | DPL-0033 fixed (PAD_LIBS={} plus strategy); v3/v4 hardening runs in docker; AC-1 gearbox, line/8, power ≤60 mA, AC-3 CDR controls, W1 bits and FF freeing all requested | check `docker ps` and scratch/dh-x-*; read interface-changes.md |
| Wired RX (analog/wired_rx, timing/pll_ring) | capture r2f and pll_ring r7 extracted flows running; W1 re-capture and AC-3 CDR not started | scratch/wired_rx/cap/run_r2f.log, scratch/timing/pll_ring_r7_run2.log |
| Wired TX/slicer | in progress: ss abort, quarter rate, CML driver, pad C | analog/wired_tx README |
| Assembly (integration/) | floorplan legal with an 8-bank 1.02 nF decap pool; stages 4–7 were running | its scratch run |
| RF chain | died while writing the DAC cascode change (possibly half-edited) | RF/converter dirs; MANDATE.md |
| Characterization/RF LO | died on the always-on oscillator (aosc); the protected-pad LO sim was the priority | analog/characterization |
| Speed test structures (a sub-agent) | died; not built | gf180-device-speed-evidence.md |
| Done | bias routing/LVS, vref/vcm, ATB leaves, observation mapping, spec/power/traceability, reviews | |

Read MANDATE.md, interface-changes.md, physical-limits.md, performance-review.md and consolidation-pass-2.md.

## Update 2026-11-10 ~02:30 UTC: weekly limit hit again (resets 21:00 UTC)
- Assembly round 2: died before the floorplan revision. Next: geometry fixes, then the floorplan revision per MANDATE "Top-level performance gate" plus signal-flow chains (pads may move), then rationale and image, then route, then the perf gate. A reusable PIL floorplan renderer was in progress.
- Wired RX (AC-3/W1): died while writing docs; ss fallback cases may still be running. Check scratch/wired_rx and the r2f/r7 evidence.
- Digital: routed (first full route of current RTL); signoff STA (scratch/dh-x-sta) and Magic DRC were running. Full regression passes on current RTL.
- RF: sim queue scratch/converters/rfconv/queue (adc corners, rf_rx, dac_q/adc_q, 1024-pt FFTs) runs unattended; review its results.
- Char/LO agent: status unknown; check its last outputs (lo_ext-pad evidence is done; aosc r2 extracted; LC VCO start-up; speed structures).
- Image of the first assembly pushed: docs/images/chip-assembly-2026-11-10.png (branch pushed to origin).

## Update 2026-11-10 ~03:30 UTC: assembly round 3 (integration owner)
- Floorplan v3 is legal and assembled. Geometry checks all pass: the isw_debug short is fixed (the cause was orphaned packaging metal in the top cell), and pad overlaps are 0. See scratch/chip-assembly-dev/NOTES-round3.md, floorplan-rationale.md and floorplan-v3-labeled.png.
- Requests I6–I11 are in interface-changes.md: macro pin plan, decap, pad boundary pins/refpad depth/T-coil, core_bias split, DRC attribution, D2H reserve.
- Antenna and full KLayout DRC were running on the v3 GDS (scratch/chip-assembly-dev/antenna, drc-v3). Routing and the performance gate have not started.

## Update ~05:00 UTC 2026-11-10: weekly limit hit again (resets 21:00 UTC)
Died: wired RX resume (was updating the timing README with r7; sims may be running), floorplan v4 (not started), risk analyses A1–A8 (not started).
Restart order after the reset:
1. floorplan v4 (risk-register driven: macro↔ADC/bias distance, LO bundle, aosc, decap)
2. risk analyses A1–A8 (A6 audits first)
3. wired RX AC-3/W1
Possibly still alive: digital (signoff + RF-mode items), block DRC cleanup, area recovery r2, LO path, RF queue.
Done this round: risk-register.md/.json (68 risks, 18 demanded), the v3 image pushed, the LO external route qualified, aosc fixed, speed structures built, pads compacted (0.344 mm², unpublished).

## Update 2026-11-10 ~06:30 UTC: risk analyses A1–A8 + TXC done (risk owner)
Register regenerated (69 risks: 29 demanded, 22 maybe, 18 not needed). Scripts/results in physical-limits/analyses/ (RESULTS.md). Demands are RA-1..RA-21 in interface-changes.md, and board obligations B25–B32 are in spec/board-requirements.md.
Still open: extracted adc_i and core_bias substrate transients (A1, 2 sims); the two-ring co-sim (A3/LO-02); the slicer balancing confirmation sim (A8); the top-level antenna check and XT-05 audit on the v4 route.

## Update ~06:10 UTC 2026-11-10: wired RX resume 3 (wired_rx owner)
State and pointers: analog/wired_rx/README.md "Resume 3"; interface-changes.md AC3-W3..W8, MT01-W1, PDN04-W1.
Running: pll_ring nominal subset on the K1 extraction (`scratch/wired_rx/regen/pll_ring_sims2.log`), capture r4 benches
(`cap_r4_benches.log`), then `scratch/wired_rx/regen/queue.sh` (slicer r3 ext nominal → cdr ext unit → fallback r4).
Blocking: the AC-3 nA pump mis-delivers +0.2–0.35 µA at ring-rate votes (README "AC-3 pump"); extracted AC-3 loop not run.

## ~09:30 UTC 2026-11-10: open items needing a (re)started agent
- Digital AC-1 core agent died (weekly limit) while rewriting the transport SDC. Restart first. Also include IX-2: fixed 312.5 MHz host clock option plus optional on-chip 8b/10b decode/encode so 3.0/3.125 Gb/s fit the host link.
- LO owner (no live agent): IX-5, LO phase settling within 2° inside T_FCS−5 µs for Channel Sounding; I/Q trim D-LO-2; termination D-LO-1; VCO layout; frequency-locking loop; review the queue results in scratch/timing/queue.status.

## ~11:30 UTC 2026-11-10: weekly limit hit again
- Digital AC-1 (resume) died during the linecode RX/TX restructure (one-hot insert positions, TX two-stage encoder). Restart first; check its half-done edits and `make transceiver-pattern`. Also: opcode4 fast gain; new CDR `g` meaning (AC3-W12).
- CDR loop: ring r9 is merged (393–834 MHz extracted on the regulated supply, ~920 ppm/vote). Open: 12 ANT.16 antenna violations on pll_ring; pt_cdr corners/layout; closed-loop extracted CDR (latency spec ≤8 still model-only); r7-port users break (LO ring instance, run_timing tb_pll_ring, pll_vreg bench).
- Pending user decision: wired pad capacitance (a) separate low-C SATA/PCIe pads via folded debug pins (recommended), (b) on-chip T-coil, (c) accept ~5 dB return loss. Also tell pads to use 6 V devices for pad-side switches (HBM 2 kV), and shrink or limit pll_vreg (0.285 mm² each).
- Possibly still running: wired TX CML cluster, wired RX front end/capture, RF robustness items.
- RF (agent finished): the promoted split LNA gives 11.87 dB NF EXTRACTED (4.45 was schematic only). Coordinator decision: keep it and fund a layout-aware LNA/stage-2 redesign plus hierarchical relayout (RC-16); don't revert. TX 6 V cascode accepted (−3.7 dB Psat) for reliability (RC-18/19). Open:
  - RXR max-input attenuation must go BEFORE LNA stage 1
  - fine DCOC needs ≥8 bits
  - PGA 42 dB bandwidth regression (RC-17)
  - dac antenna ×3
  - rf_tx evidence rerun
  - power budget missing an rf_tx case (rfdriver ~59 mA, not 28.9)
  - LNA 78k µm² vs 24.6k, rfdriver 133k vs 98k
- USER DECISIONS (2026-11-10):
  - (1) Pad C: SEPARATE low-C SATA/PCIe pad pairs, freeing pins by folding debug observation pins into the CLK_OBS mux; bond-map change.
  - (2) Wired TX: BOTH. A retimed CMOS core as the guaranteed path ≤2.5 Gb/s, plus one CML retry (half-rate CML clock straight from the ring + a CML pre-driver) for 2.7–3.24 Gb/s.
- Coordinator: pads to use 6 V pad-side switches (HBM 2 kV); shrink or limit pll_vreg.
- Wired RX (finished): capture r5h fixed (q625 0/200 extracted). Open:
  - safe-state 238 µA vs 10 µA (failing since r3a)
  - slicer fine step 2.0–2.4 mV on 3 edge samplers (needs a 4th bit)
  - CTLE r2 +60 fF/leg
  - return loss above 1.25 GHz is limited by bond+connector inductance (2–6 dB), so ≥8 dB at 2.5 GHz needs a T-coil or a package/board change even with low-C pads
  - antenna violations: capture 22, slicer 32
  - queue scratch/wired_rx/myqueue_master2.sh is running
- 100BASE-TX approved via generalizations IX-9..IX-13 (10BASE-T rejected: TX can't reach 2.2 V). IX-9 was sent to wired TX. Still to dispatch on restart:
  - IX-10 (two signed 7-bit threshold DACs on the edge samplers) and IX-13 (CTLE low-frequency zero) → wired RX front end
  - IX-11 (fast threshold-update command) and IX-12 (raw dual-lane capture) → digital
- Pads (PD21–PD27, finished):
  - pad_hspad, the low-C HS RX pair (1.11–1.14 pF, 40–60 Ω trim, on-die AC coupling, 2 kV clean), is PUBLISHED on bond 20/21; USB moves to bond 24/25; WCLK_OBS and WDBG_OBS folded, DBG_OBS1 kept.
  - Board-side return loss above 1.25 GHz is package-limited (5.7–6.5 dB); optional carrier ladder B40.
  - Coordinator accepts PD25: regulate only pll_tx and pll_cdr, plus the 0.241 mm² shrink after extracted reruns.
  - Open:
    - USB pad 6 V conversion regresses HS term (56–68 Ω) and FS edges; redo with the USB/wired RX owner
    - TX pad still has 8 overstressed termination switches; the SST driver proposal needs a wired TX decision
    - wired RX needs a CTLE input mux or a separate USB receiver (USB moved off the shared pad)
    - core-side gates on pad nets (e.g. the LNA gate on RF_RX) were never HBM-screened; add that screen
    - assembly needs the new bond map
- Radio generalizations GX-1..GX-9 (accepted by coordinator; dispatch on restart). Owners:
  - RF: GX-1 wide filter code, GX-8 antenna-switch analysis, GX-9 TX+RX isolation sim
  - digital: GX-2 host-fed 80 MS/s DAC mode, GX-3 config validator allowing TX+RX, GX-4 hop-boundary profile switch, GX-5 62.5 MHz core clock for GNSS, GX-7 cross-die sample sync
  - LO: GX-6, don't clamp the VCO frequency loop to 2.4–2.5 GHz
- FPGA offload audit done (fpga-offload-audit.md); recommendations sent to the AC-1 agent. Spec owner to-do on next spec pass:
  - cap streamable wired rate at ~3.15 Gb/s (3.24 needs 101% even with 8b/10b) or add idle deletion
  - reword IX-8 as chip marks + FPGA counters
  - note the full-rate exception to the RF div2 power rule
  - write the FPGA reference-design gateware spec (10 items; never a safety layer)
  - board must route DBG_OBS0/1 to FPGA pins

## ~06:00 UTC 2026-11-11: digital AC-1 transport (resume 2) — stopped after its 2 hardening runs
- Notes: scratch/transport-ac1/NOTES.md (R2-*); interface rows T13–T24 at the end of interface-changes.md.
- Done: lane boundary; S1 (pt_memory deleted, MEMORY v3 SPI-only); HB-1 stagger; pt_calibrator removed; timing restructures. All RTL checks and formal PASS.
- AC1_R4 hardened at 1716×1455: DRC/LVS/antenna clean; GLS RTL==GL. Timing NOT closed (ss32: egress_wtx −15.6, hcore −14.4, wrx −12.0).
- Queue: timing (enable fanout, registered pops, playback empty), S3, S2 (needs IX-10 fields), S5/FPGA-5, HB-2/4/5/6, FPGA-1..4, HL-SCALE (b), limp mode, GX-3/4/5/7.

## 2026-11-11 ~22:00 UTC: weekly limit hit (resets Nov 17 21:00 UTC). Restart list
Branch: main. Shared agent rules: scratchpad preamble (copy in this file's MANDATE). New rules: two-sided pessimistic bounds, prove benches small first, bench audit before long runs, independent review before "done", ≤2 waiting shells.
- LO: follow scratch/reviews/lo-lock-sim-audit.md ladder; retract "≤29 µs"; rebuild jitter budget; CP 0.31→≤0.15 mm², lo_ext 297k→~150k µm²; CMLSEL bit to digital; run_timing.py must not write into generated/ on failure. Committed through 5f41ee4.
- RF: LNA input-stage redesign for in-band match + ≥30 dB attenuator + evidence cleanup, then re-review; TIA noise (≤4.1 dB DSB); rxmix compact; bbfilter rework (fork U had 5 review NO-GO items); DAC accuracy 4.36 vs 4 LSB; rfdriver power-budget current 60.01 mA; LoRa gap report. Nothing of the new LNA committed (scratch/rf-lna*, scratch/review-lna).
- Pads: EM at 85 °C (M1 columns), real USB LS slew control 50–450 pF, termination calibration method, review nits. Committed through ef2b69d; check scratch/pads-pd42/.
- Wired RX (round 7 agent may still run): vote-switching ring shift first; wrx_cap without gearbox; pt_detect secondary clamp; DAC settling/area; slicer r6 regression; ring ≤360 MHz at ss; closed-loop CDR via the small-first ladder.
- Wired TX: designed slot overlap; WT20 reruns; X5; TMDS; USB-02/03; wtx_ext_rx driver path; two-sided bench.
- Digital (closure r3 agent may still run): TC8+, ≥10% margin at 1716×1640; TERM_TRIM AND, LS_SLOW interlock, ready timeout; then the HL-SCALE/limp/FPGA-1..5/HB/GX queue.
- Next: assembly v6 once areas land; adversarial evidence audit of every block's key claims.
- LO update (committed): honest jitter is 0.65 ps at tt but 1.65 ps FAIL at the pessimistic QVCO (−105.7 dBc/Hz at 1 MHz). Fix tank Q/swing at the pessimistic corner, measure the flicker corner (add a tail filter if >100 kHz). Sweep optimistic bands 5–15. LO17/LO18 go to digital.
- Pads update (docs committed; sim work in scratch/pads-pd42/usb/): the USB termination calibration method passes; the LS slew topology works in sim but needs layout, DRC/LVS, HBM and review. USB pad C with the RX bypass load is 2.8–3.6 pF against 2.7 → re-derive a USB-only budget from the USB HS eye/return-loss requirement and fix it if the budget fails. Area 352k vs 340k. Wired RX needs ATB leaves on USB_RX_P/N.
- DAC (scratch/rf-dac-t/): the bench is validated. The 4.36 LSB bow is real and comes from CK/CLKN coupling onto ATB_BIAS (21 fF) and HG (7.6 fF), giving a ±5.5% FS 40 MHz ripple. Fix: 1 pF decaps on ATB_BIAS and VCASC (schematic ≤1.7 LSB) or route isolation; bench t0 600 ns, per-chunk endpoints; extracted confirmation pending. Also investigate EN=0 supply current reading −32 µA (safe=fail).
- LNA input-stage redesign agent hit its 200-turn limit mid-rerun (new views, stability screen, self-tests, harmonic term). Its work is in scratch/rf-lna*/ and uncommitted. Resume from there after the reset; don't trust anything until it is re-reviewed.
- Digital (TC12 committed; routing in scratch/digital-timing-close/run12/): placement-stage slack is −0.85..+0.46 ns, short of the ≥10% margin. Coordinator decision for D2H: build a small hand-placed D2H output block with FIXED placement and identical launch-flop, mux and buffer cells on the clock and data paths, and no synthesis port buffers. The h2d input hold window needs the same treatment. Next: more closure rounds; reclaim fanout-buffer area (0.25 mm²; tighten the 80% buffer allowance); review open items (select-change assertion, lifecycle bench with varying data). Assembly: bind TERM_ENABLE (analog_cfg 573 bits).
- Pads PD47 (2026-11-12, uncommitted): wirepad Miller LS slew laid out + published (LS 94.7–201 ns 50–450 pF extracted, HBM 0/615, KLayout clean), USB pad-C budget = USB 2.0 die 5.0 pF/line (cell 3.37 pF → pass), area 316k/340k (pass), reviewed GO with conditions (digital ls_slow ⇒ bias.enable interlock, host LS load). EM fork (tbuf/steer) running. Next: ESD tiering (1 kV) per coordinator.

## 2026-11-12 ~02:00 UTC: weekly limit hit again (resets Nov 17 21:00 UTC)
Committed: wired RX r7 (24b945c), digital r4 (d0395fb). New since the last list:
- USER DECISIONS: board trimmers for the LNA match; ESD tiering (MANDATE) plus a transient oxide limit plus a TLP test site; full scope means DP HBR 2.7 and SATA G2 are NOT dropped.
- TOP WIRED RISK: at the pessimistic gate the slicer is ≤625 MHz and the TX core ≤2.5 Gb/s, so 2.7–3.24 Gb/s is uncovered on RX and TX. A "2.7–3.24 Gb/s architecture study" agent died at the limit; restart it (eighth-rate/more phases, interleaved slicers, faster final 2:1, compact CML), or produce a physical-impossibility proof for the user.
- LNA: fix the review-lna2 items (band-edge bench bug, ff S11, attenuator at extpp/ss, pessimistic NF, stability), plus board trimmer spec; then re-review. Work in progress in rf_rx (uncommitted).
- Digital: the D2H forwarded clock built like a data lane (same flop, edge, mux, placement); wired RX en_r fanout −2.5 ns; AGC override test; SLI7-R (slicer_en interlock), SLI7-M (E0..E3 re-time), W7-GEAR (capture gearbox into digital).
- Wired RX: extracted closed-loop CDR on r9v; detect r7j; independent reviews (ring r9v, capture, detect, CDR); capture q834; phase spacing/ptrim.
- Pads: USB LS slew layout, pad-C budget, EM at 85 °C, ESD tiering re-tune (PD48 review died), TLP site, oxide limit.
- LO r5, DAC, RF baseband/TIA/rfdriver, wired TX: check each agent's scratch notes; they may have died too.

## 2026-11-12 ~04:00 UTC: rate limits are biting; keep ≤3–4 agents at a time
Waiting to restart: v6 assembly (scratch/chip-assembly-v5 as the base, full brief in conversation), the adversarial evidence audit (output scratch/reviews/evidence-audit.md), digital closure (NOTES.md r4c: D2H rise/fall sizing, H2D custom CTS, R8-ARCH+W7-GEAR capture front-end, lc_tx ready chain, egress hold), LO r5.
In progress: wired RX (CDR ±1000 ppm pulls in then drifts with a ~13 nA leak on VCTRL, diagnosing; ring ≤300 MHz met at ss/sf/ff-opt), wired TX (eighth-rate dual-mode core), WT24 (CML pre-driver: 309 ps bits pass in schematic, swing 0.36–0.38 vs 0.40 V; going with a 0.6× switch at 11 mA), pads EM.
Committed since: PD48c 9103707, digital 895bfd0, wired TX 172c923.

## 2026-11-13: v6 committed (87c2b1e). The die is FIXED (user). Area is short by 1.42 mm² (3.0 with routing and decap); area pass 4 is running.
Queue for the next digital agent (no digital agent is running): POR override strap/bond-option pad (rst_n = reset_n_pad & por_n has no override; POR may never release); SPI-only timing sign-off over the 2.6 mm top-level routes; also everything in NOTES.md r4c.
Integration plan: scratch/reviews/integration-plan.md. First three checks: power-up/isolation (including POR), a top-level supply model, and a substrate + ring/QVCO pulling co-sim.

## 2026-11-13 ~20:50 UTC: session resumed; 7 agents restarted
Running: digital (POR override first, SPI-only STA, closure r4c, AP4-8), always-on audit (bias/isw/POR/aosc -> scratch/reviews/always-on-audit.md), integration M6 power-up/isolation (-> scratch/reviews/integration-m6.md), wired RX (publish wrx_cap r7, AP4-1 repacks, then CDR/eighth-rate), converters AP4-4 (scratch/converters-ap4/), LO AP4-5 (scratch/lo-ap4/), RF LNA/TIA finish (scratch/rf-lna-p/NOTES.md; pessimistic NF 7.66 dB open).
Not restarted yet: wired TX (s10, eighth-rate + driver review fixes), pads (AP4-6/7, stacked hspad publish conditions), bbfilter repack AP4-3 (after the LNA agent leaves rf_rx), assembly re-pack AP4-9/10 (after >=60% of tier-B outlines land), evidence audit, bring-up software, integration checks M1-M3.
~21:00 UTC: user wants big-picture checks. Added 4 read-only agents: end-to-end mode interface walk (scratch/reviews/mode-walk.md, MW- rows), outside-view pre-mortem (scratch/reviews/pre-mortem.md), PDN model M1/M4 (scratch/reviews/integration-m1.md, INT1-), substrate + pulling M2/M3 (scratch/reviews/integration-m23.md, INT23-). 11 agents total. Evidence audit still not restarted (pre-mortem includes an all-block evidence-staleness script).
~22:30 UTC: pre-mortem done (scratch/reviews/pre-mortem.md, b65be06) and mode walk done (scratch/reviews/mode-walk.md, MW-0..36, 65a6c2e). KEY FINDING: no analog top exists; chip netlist 653/2892 ports unbound, 14 blocks uninstanced, register map behind the cells, no decode glue -> no payload mode can run. Decisions: decode glue lives in the digital macro; register map follows the cells. New agents: chip-top integration owner (scratch/chip-top/NOTES.md, TOP- rows), signoff-gap (GDS read-back LVS, fill, live precheck -> scratch/reviews/signoff-gap.md). MW rows forwarded to digital, wired RX (MW-13 CTLE real load -8 dB, MW-14 ptrim), LO (MW-20 mixer with real LO -4.6..-16 dB, MW-7), converters (MW-3 clock, MW-6 VREF), RF RX. User: mid-Dec shuttle, schedule is the user's concern; no GDS uploads until a block is really finished.
Not yet assigned: wired TX rows MW-15..17/24, USB data path MW-18, 100BASE-TX digital MW-25, pads (por_bypass pad, HS pad bias register), debug paths MW-28/29.
