# Pre-tapeout fix plan (2026-11-28)

This is a read-only planning pass. No register row, conn, RTL or layout was edited, and nothing was rerun. It applies
MANDATE 8 as amended on 2026-11-28: every real deficiency is fixed before tapeout unless it is judged impossible or
highly unlikely to solve. Fixes that share a costly step are batched.

Inputs read: `spec/risk-register.md` (all open and demanded-mitigation rows), `risk-triage-2026-11-28.md`,
`pdn02-boot-path-2026-11-28.md`, `int04-observability-2026-11-28.md`, `interface-changes.md` (DG9-11 .. DG9-32),
`scratch/wired_tx/s14/QUEUE.md`, `scratch/wired_rx/r13cap/STATUS.md` (capture r9/r10a/r10b/r10c), `r10cap/STATUS.md`,
`r12/ctle/STATUS.md`, branch `lvs-bb` (PAD-15, f3bb5ab6 / 375f8242), branch `fp-plan-code` (INT-04 F1-F6 already
landed in bec02603 / c179dc8f), and `integration/chips/{ctl_ports.txt, wired/chip.conn}`.

**Cost classes.** TOP = top-level conn and route only. BLOCK = one analog block re-layout plus its own LVS, DRC and
extraction. MACRO = digital RTL plus one re-harden of the digital macro, with the pin plan fixed so the floorplan is
untouched. MODEL = simulation or analysis only. BOARD = a board, gateware or bring-up obligation; it has no tapeout
cost step and is listed only so it is not lost.

**Effort** is in agent-days of focused work, excluding queue time on the shared machine (6-job cap). It is a rough
estimate, not a schedule.

**Pin / outline flag.** **MP** = moves a macro pin or changes the macro outline. No item in this plan needs that.
**BP** = changes a block's pins or outline, so the floorplan has to re-place or re-route that block (not the macro).

---

## 0. Key enabler: spare macro pins already exist (no pin move needed)

There is one macro RTL for both chips, and each macro carries every port of both chips. On `pt_wired`, about 100
RF-only `c_*` outputs exist as LEF pins but are unbound (`c_adc_*`, `c_bbfilter_*`, `c_lna_*`, `c_dac_*`,
`c_bb_tap_*`, `c_bias_dist_en_rf/conv`, `c_clockmux_cs` ...; check of `ctl_ports.txt` against `wired/chip.conn` plus
`common.conn`). On `pt_rf`, the wired-only outputs and inputs (`c_wiredtx_*`, `c_txpad_*`, `s_detect_*`,
`wire_rx_*` ...) are unbound or tied the same way. A new per-chip function can therefore take over an existing
unbound pin through a `PT_CHIP`-selected assignment in RTL. The pin name, side and position stay the same, so the LEF
PIN sections stay diff-equal. The only top-level cost is one new net from that pin to its consumer. Pick the spare pin
nearest the consumer from `fp_plan/<chip>_macro_pin_order.cfg`. The `macroclamp` and isolation rules must cover the
new use (iso audit K-rules).

Rule for the MACRO batch: **no new port and no port removal.** Every new function either stays inside the macro or uses
a spare pin as described above. The `gen_regfile` accept-set check and `chips.json` change with it.

Precondition (coordinator): **decide which `pt_rf` pin set is frozen** before the MACRO batch starts. The choices are
the DG9-29 pins or the DG9-32 plan-order candidate (`scratch/digital-macro-candidate/rf-pinplan/`, accepted waiver,
"assembly to validate"). `pt_wired` stays on the DG9-30 pins, because the DG9-32 `pt_wired` candidate failed. The batch
re-hardens against exactly those pin-order files. MACRO_DIR (7ea03e7f) already lets the floorplan run a candidate.

---

## 1. Per-deficiency judgement

Columns: **Real?** (F = function, S = spec / performance miss, O = observability, R = recovery, C = cosmetic or no
effect, St = stale row). **Fix?** (Y = fixable pre-tapeout; C = conditional, one bounded attempt and then a judgement;
N = judged impossible or highly unlikely, with the reason in section 3). **Step**, **Owner**, **Effort**, **Pin flag**.

### 1a. The named items

| ID | Real? | Fix? | Fix | Step | Owner | Effort | Pin |
|---|---|---|---|---|---|---|---|
| DIG-08a host-rate divider | F (no host link at ss 3.15 V untrimmed; SPI unaffected) | Y | Retime `host_rate.div/gap/cur/hold_n/ne`: decode one cycle early and register it (a few flops), as `pdn02-boot-path` item 3 proposes. Gate: hword ≥ +0.25 ns at ss 3.15 V K 1.20 on both chips. Keep the bring-up rule (SPI first, ≤ 125 MHz word clock) until the new macro is delivered | MACRO | digital | 1 | none |
| DIG-08b REF_IN island sequencers | F at ss 3.15 V / full droop (island bring-up can misfire) | Y | Synchronise the reset release of `vreg_seq.rdy_tx → wtx.ok_s/ser_q/de_q` RN, `wtx.pad_seq` and `wrx.frun → regs.wrx_fll_err` (two-flop reset synchroniser, or registering the source) so recovery becomes a same-domain path. Gate: ref recovery ≥ 0 at ss 3.15 V K 1.20 | MACRO | digital | 1.5 | none |
| DIG-08c wired-RX gearbox reset (`wgear.g_rn`, wstb) | F on `pt_wired` (−1.49 ns at droop) | Y | Release `g_rn` through a synchroniser on WSTB (falling-edge or two-flop), or make it synchronous. Same RTL on both chips | MACRO | digital | 1 | none |
| PDN-02 two-phase launch | S (ripple 212 / 313 mV vs 150 mV; ring PLL jitter 7.3 vs 5 ps; feeds PDN-11, LO-11, PDN-03, SP-01) | C | Two-phase launch (alternate clock-tree banks launch on opposite edges or half-period offset), with bank clock gating of idle islands as the fallback variant. Gate: no slack regression against the delivered macros at ss 3.50 V and the hold corners; PD2 rerun with the routed switching charge shows ≤ 150 mV. If timing regresses beyond the baseline, ship clock gating only and record two-phase as infeasible with that evidence. This is the largest and riskiest MACRO item | MACRO + MODEL (PD2) | digital; power delivery | 6-8 | none |
| WTX-09 no TX_RUN force | R (a detector failure leaves the wired TX bank off with no recovery; WTX_EXT does not bypass the interlock as far as the evidence shows) | Y | (1) `pt_wiredtx8`: add input RUN_FORCE ORed in at the `XMUX.RUNB` point that the netlist-only `ilk_bypass` already uses, and rerun the interlock rows on the 5d73aae8 fullfix netlist (rerun RUN = 29.4 ns, plus force on / off). (2) MACRO: new field `wtx.run_force` (debug, wired island, stopped, reset 0) driven out on a spare `pt_wired` pin (section 0). (3) TOP: one net | BLOCK + MACRO + TOP | wired TX (inactive: needs an agent); digital; pt_wired top | 3 (block) + 0.5 + 0.5 | **BP**: +1 block pin on pt_wiredtx8 (ASM-11a top-pin field is tight; the cascode pump already did not fit). No MP |
| PAD-15 pad_txpad SUB taps without VSS text | C (electrically VSS; block LVS matches; only top LVS by name sees it) | Y, cheap | Add the VSS label in the pad generator, re-export with geometry XOR 0, then drop the name-specific filter in `signoff.py` / `top_lvs_bb.py`. Done because it removes a signoff exception, not for function | BLOCK (text-only re-export) | pads (inactive) or pt_wired owner | 0.5 | none (XOR 0) |
| Wired RX capture r10 (slot-enable chain; WRX-22, TIM-37) | S at the pessimistic bound only (pess ss q625 72/200; nominal ss, ff and 100BASE-TX pass on the bound r8; 2.5 Gb/s needs RCS = 1) | **C** | One bounded attempt at the design that has **not** been built yet: true two-period cross hops (`r13cap` "r10b recommended": hop from slot i-2k plus a local destination flop; 3.2 ns for route + AOI). The skew-only "r10b try", r10a and r10c were different fixes. First add a fixed-pin / fixed-outline option to `layout_engine` so the r8 outline (1241.2 × 260.5) and pins hold. Fold in PWR-01 (safe-state current) and the DCF.1a taps (MT-03). Gates as in `r13cap` (q625 ss/tt/ff nominal, pess ss 3.15 / 3.50, ff hold, f500 ss, bench B RCS = 1). If it fails the gates, record "highly unlikely" with the five variants (r9, r10a, r10b-skew, r10c, r10b-2period) as evidence | BLOCK | wired RX (active) | 4-5 (+1 for the layout_engine option) | must be **no BP** (held r8 pins/outline); any slip is BP and needs the floorplan owner |
| INT-04 F1-F6 | O | done | Already on `fp-plan-code` (bec02603, c179dc8f). Needs check_conn / LVS by name on the next plan run, and the coordinator ruling on the code names (MAP_HASH) | TOP (done) | chip top | 0 | none |
| INT-04 F7: pt_rf TRK_LO, pt_rf CDR VCTRL, pt_wired slicer bias (code 25 now used by F6), VREG_CDR, word clocks on CLK_OBS | O | Y | (a) MACRO: change the `atb_no_leaf` / accept sets (pt_rf: accept 22 = TRK_LO; one code for CDR VCTRL; pt_wired: one code for slicer bias) using the already existing `atb1_sw[59:0]` pins, and update `chips.json`. (b) TOP: place and bind the leaves. (c) BLOCK: VREG_CDR has no tap, so add a 20 k ATB_OUT to the CDR regulator instance, like `pll_vreg2`. (d) TOP: bind WRX/WTX_WCLK40 to `clk_obs` IN0/1/4/7 (tied VSS today) through iso cells (the wired island feeds the debug island) | MACRO + TOP + BLOCK (VREG_CDR) | digital; chip top; power delivery | 1 + 1 + 1.5 | **BP** only for the regulator tap (+1 pin) |

### 1b. Digital / macro rows (register and DG9 "next harden")

| ID | Real? | Fix? | Fix | Step | Owner | Effort | Pin |
|---|---|---|---|---|---|---|---|
| HL-06 (DG9-29/30/31 "kept clkbuf, fc_half2, h2d") | S (no full host rate on slow dies even at 3.50 V) | C / partly N | fc_half2 and h2d logic fixes go in the batch. The kept-clkbuf-after-mux fix was tried (DG9-31) and failed (pt_wired 267 DRC / 154 LVS, worse timing). With the host-link cluster pinned and hand-placed (coordinator ruling), the residual hddr / d2h_oddr / d2h_fwd windows are judged highly unlikely (section 3). div2 / div4 plus FPGA training stay | MACRO | digital | 1.5 | none |
| HL-04 opcodes 5/6 rejected by `legal_n` | F (fast-threshold path unreachable) | Y | Admit 5 and 6 in `pt_quad_link.sv` `legal_n`, add a bench case | MACRO | digital | 0.5 | none |
| WRX-03 per-sampler trim | S (step too coarse; the map cannot program every sampler) | Y | Fourth fine bit plus per-sampler fields. The extra `c_*` bits take spare RF-only pins on pt_wired (section 0). The slicer needs the extra trim bit | MACRO + BLOCK (slicer) + TOP | digital; wired RX | 1 + 3 + 0.5 | **BP** slicer (+bits) |
| USB-02 (RTL part) | F (HS bit repetition not in RTL; LS slow mode with no interlock) | Y | Add the validator rule (LS mode needs `usbhs.bias.enable`) and the bit repetition in RTL. The analog part is under wired TX (section 1d) | MACRO | digital | 1 | none |
| DBG-03 ATB leaves not island-gated | likely St | MODEL | The `int04` read of `pt_regfile.sv` 1319-1364 shows island-node leaves close only with island on and PG. Confirm that it covers the trunk and VREF0_CONV leaves, then close the row. If a leaf is missed, add it to the gate list in the MACRO batch | MODEL (→ MACRO if a gap) | digital | 0.5 | none |
| c_cdr_g reset 2 vs 3 (DG9-31) | C (block is off at reset) | Y | Wired RX settles the value; change the reset in the batch if 3 | MACRO | wired RX; digital | 0.1 | none |
| AON-01 aosc default vs doc | C / doc | Y | Align the document to the RTL (no RTL change) unless K1 rules say otherwise | MODEL (doc) | digital | 0.2 | none |
| PWR-14 bandgap interlock counts SCLK | R-trap, mitigated | Y (no silicon) | 256 SCLK = about 11 status reads, so a polling loop releases it by itself. Confirm that in GLS, and write it into the B54 / sequence.py rule | MODEL | bring-up; digital | 0.3 | none |
| CDC-02 async SAR capture | F (rare corrupted samples) | Y if the capture is in the macro | Capture on the ADC done edge (synchroniser in the macro converter interface) | MACRO | digital; converters | 1 | none |
| SP-03 duplex DAC 80 MS/s vs shared converter clock | S | needs ruling | Coordinator: a second converter clock divider in RTL (a spare pin if a separate clock pin is needed) or FPGA interpolation as the accepted path | MACRO (if built) | coordinator; digital | 2 | none (spare pin) |
| HL-02 long frames / per-direction rates | S for 3.0-3.24 Gb/s streaming | needs ruling | It is capacity work that can look like a new feature. Coordinator to rule; if it is a spec miss, put it in the MACRO batch | MACRO | coordinator; digital | 2-3 | none |
| HL-07 no payload CRC | St for bit slips (negative tests are MODEL); CRC = new feature | MODEL | Negative tests and error budget. A CRC only if the spec requires one (coordinator) | MODEL | digital | 1 | none |
| DIG-03 cmd/response latency 2.4× over the USB HS gate | S | **N** | Section 3 | MODEL (latency model) | digital | 0.5 | none |
| DIG-01 / DIG-07 | S (setup only at the 3.50 V trim; hold without OCV) | Y (evidence) | Routed OCV signoff on the new batch macros, with the foundry ff library as a bound | MODEL | digital | 1.5 | none |
| DIG-05 formal on the final map | verification gap | Y | Rerun formal after the batch | MODEL | digital | 0.5 | none |
| PWR-06 / PWR-11 / PWR-10 | S (current requirement unmeasured) | Y | Per-mode power analysis of the batch macros; recheck the 430 mA ceilings | MODEL | digital; power | 1.5 | none |
| PDN-11 ring PLL regulated mode needs a two-phase macro | S | follows PDN-02 | Rerun the regulated-mode jitter on the batch macro's ripple | MODEL | power; timing | 1 | none |
| DG9-11 (pt_wired macro 40 µm narrower) | C (no deficiency) | excluded | **Would be MP**: not done | - | - | - | MP, excluded |

### 1c. Wired RX (pt_wired)

| ID | Real? | Fix? | Fix | Step | Owner | Effort | Pin |
|---|---|---|---|---|---|---|---|
| WRX-01 CDR closed loop unproven | F (unproven) | Y | Extracted closed loop on r13 with both real rings, tt plus every in-window corner. This is evidence work first; a BLOCK fix only if it fails | MODEL (→ BLOCK) | wired RX | 4 | none unless it fails |
| WRX-20 CTLE gain collapse (r4 NO-GO, r5 fails ss-pess at 3.125 / 3.24 and the G3 spread) | S / F at the pessimistic corner; bypass exists | **C** | One more revision (r6) using the r5 lessons (replica bias plus a regulated output CM, load-return vias, then the r4 follower question). If r6 fails ss-pess at ≥ 2.5 Gb/s, judge highly unlikely at that corner and ship r5 or the current cell with the bypass. Fold in WRX-13 (code) and WRX-05 (input C) | BLOCK | wired RX | 5 | **BP** (pt_ctle / pt_rxselect outline and pins change with the follower) |
| WRX-02 slicer at 0.4 V CM / trim range; MT-01; WRX-07 | S | Y | Requalify at 0.4 V CM with the real CTLE and clocks at the 3.50 V trim; widen the trim (with WRX-03, same re-layout); extracted rows with Rg | BLOCK (with WRX-03) + MODEL | wired RX | in WRX-03 + 2 | BP (shared with WRX-03) |
| WRX-08 signal detect threshold; OOB | F (detect) | Y | Threshold redesign of `pt_detect` (r10detect candidate q27 exists), OOB timing; jitter sims are MODEL | BLOCK + MODEL | wired RX | 4 | BP if detect pins change |
| WRX-19 DP HBR JTOL | S (unproven) | Y | Extracted closed loop at HBR settings (with WRX-01) | MODEL | wired RX | 1 | none |
| WRX-23 CDR ring start | F (no start at pess ss, 1 µs ramp) | Y | Diagnose small-first; if real, add a start kick in the ring (BLOCK) or use a slower enable ramp from the macro (MACRO, a counter on the existing enable) | MODEL → BLOCK / MACRO | wired RX; timing | 2-4 | BP if the ring changes |
| PWR-01 capture safe-state current | F (safe-state spec) | Y | In the capture r10 re-layout | BLOCK (capture) | wired RX | in r10 | (r10) |
| WRX-04 SATA Gen2 return loss | S | **N likely** | Section 3: needs the physical-limits proof (MODEL); a T-coil would be a pad re-layout (BP on the pad ring) | MODEL | pads | 2 | (BP if a T-coil is attempted) |
| TIM-08 forwarded clock on AUX_CLK | F (fallback path unproven; data mode start from a parked level fails) | Y | Receiver bench through the package channel; fix the parked-start case (BLOCK `diff_clk_rx` or a bring-up rule) | MODEL → BLOCK | timing | 3 | BP if the block changes |
| LO-02 TX/CDR ring injection | S (tt only) | Y | ss / ff runs | MODEL | timing | 1 | none |

### 1d. Wired TX (pt_wired; owner inactive, so an agent must be assigned)

| ID | Real? | Fix? | Fix | Step | Owner | Effort | Pin |
|---|---|---|---|---|---|---|---|
| WTX-08 no TX path at 2.5-3.24 Gb/s at ss extracted | F at ss / full rate | **C** | One re-layout of `pt_wiredtx8` holding every fix: block trim calibration, 0.6× MAIN switch or pad rework, RUN_FORCE (WTX-09), DCF taps. Then the rate × corner table at 3.15 and 3.50 V on extresist. If the R-aware pad still fails at ss-pess 3.15 V at 3.125 Gb/s, the fix is the 3.50 V trim (rows) rather than more layout. Retire the quarter-rate TX only after the table passes | BLOCK | wired TX | 8-10 | **BP** |
| WTX-03 swing / DJ at ss / 3.15 V | S | C | In the same re-layout; report trimmed-supply rows | BLOCK | wired TX | in WTX-08 | BP |
| TIM-13 ring phase spacing ±67 ps vs ±20 | S | C | Coordinator ruling on spacing; size the TX trim for the measured spread (in WTX-08) | MODEL + BLOCK (in WTX-08) | timing; wired TX | 1 | none extra |
| WTX-02 40-bit word boundary sweep | verification gap | Y | Extracted setup/hold sweep against the SDC | MODEL | wired TX; digital | 1 | none |
| USB-02 analog (HS level 351 mV at ss 3.15 V; review) / USB-03 | S | Y | Independent review; trimmed-supply rows; eye / chirp / turnaround | MODEL | wired TX | 2 | none |
| PWR-05 TX tail EM | F risk | Y | EM check at 85 °C | MODEL | wired TX; pads | 0.5 | none |
| WTX-05 AC coupling / wander | board | - | B22 / B12 | BOARD | board | - | - |

### 1e. RF (pt_rf; owners of RF RX / TX / LO / converters inactive, so agents must be assigned)

| ID | Real? | Fix? | Fix | Step | Owner | Effort | Pin |
|---|---|---|---|---|---|---|---|
| RFR-16 LNA routing defect (EM 30×; interim area +0.065 mm²) | F | Y | Placement-level relayout, all-net extresist | BLOCK (lna) | rf_rx | 6 | **BP** (area should come back down: frees pt_rf floorplan) |
| RFR-01 NF 6.3-15 dB vs 4.1 | S | partly **N** | In the same LNA relayout plus resizing the `hib` tail. The 2.4-2.7 dB package loss ahead of the LNA is a floor (section 3). Target the best NF on chip plus the board fallback LNA | BLOCK (lna) | rf_rx | in RFR-16 | BP |
| RFR-10 attenuator margin; RFR-05 IIP3 / blockers; RFR-11 / RFR-13 match refit; RXR-01 headroom | S | Y | Re-verify on the closed LNA with real LO drive; refit the carrier network; fallback-LNA path sim | MODEL (→ BLOCK if the attenuator changes) | rf_rx | 4 | none |
| RXR-09 no pre-filter overload detector | O / R | Y | Latched comparators at the TIA output (new small cell inside or beside bbfilter), status input on a spare wired-only `s_*` pin of pt_rf (section 0) | BLOCK (new cell) + MACRO + TOP | rf_rx; digital | 3 + 0.5 + 0.5 | **BP** (new cell) |
| RFT-01 TX output < 0 dBm at ss; RFT-06 real-LO chain; RFT-03 EVM / mask; MOD-16 | S | Y | Chain with the extracted LO buffer and the real DAC / filter / pad with Rg; calibration rows; recover chain gain if the real-LO run shows the loss is in the summer / mixer | MODEL (→ BLOCK) | rf_tx | 4 | none unless a block changes |
| RFT-05 LO feedthrough symmetry | S | Y | Symmetric shielded routing at assembly | TOP | assembly | 1 | none |
| LO-04 synthesizer not closed (MMD > 2.45 GHz at ss; QVCO top has no netlist/LVS) | F (on-chip LO); external LO fallback exists | Y | QVCO top netlist plus LVS (BLOCK hygiene); MMD v8 or MMD rows at the 3.50 V trim first (MODEL). If ss 3.50 V passes, it becomes a trim rule | MODEL + BLOCK | LO | 5-7 | BP if the MMD outline changes |
| LO-14 lo_obs does not divide at ss 3.15 V | O | Y | Qualify the staged repack and publish | BLOCK | LO | 2 | BP if pins change |
| LO-15 QVCO tank loading 9° | S | Y | Publish the matched staged pair | BLOCK | LO | 2 | BP possible |
| LO-10 range at the spiral bound; LO-12 floating MIM; LO-13 Kvco | S | Y | Re-extract with real loads plus fill; band capacitance if needed; bias off nodes through a large R if the drift is real | MODEL → BLOCK (qvco) | LO | 3 | BP possible |
| LO-11 QVCO regulator not qualified | S | Y | Requalify; depends on the PDN-02 outcome | MODEL (→ BLOCK shrink) | LO; power | 2 | BP if shrunk |
| DBG-02 clk_obs loading the LO | S | Y | Check the minimum-size buffer at the hub | MODEL | LO | 0.5 | none |
| LO-05 / LO-06 / TIM-07 / IQ-03 / PKG-04 / PKG-05 external-LO path | S (unverified) | Y | Co-simulate `lo_ext` with pads and channel; I/Q trim rows; extract both pad legs and equalise in the conn (TOP) or the pad (BLOCK) | MODEL (+ TOP) | LO; pads | 3 | none |
| CNV-02 ADC input buffer not built | F (disabled-input load over limit) | Y | Buffer on the filter output path | BLOCK (bbfilter or new cell) | converters | 4 | **BP** |
| CNV-06 ADC VCM bare divider | S (unverified) | Y | Real-source bench; MIM decap or a buffer if a loss shows | MODEL → BLOCK | converters | 1-3 | BP if decap is added |
| CNV-07 / MOD-04 ADC acquisition window / ENOB at 40 MS/s | S | C | Acquisition trim plus the 39.0625 MS/s / 3.50 V rule; comparator speed work is BLOCK and uncertain | MODEL (+ BLOCK) | converters | 2-5 | BP if relaid |
| CNV-05 / CNV-03 / CNV-09 / SP-04 / MOD-13 | S (unverified) | Y | Mismatch run, dynamic rows on the published GDS, reference buffer in the ADC bench | MODEL | converters | 3 | none |
| MOD-17 bandgap not powered down by its enable (71 µA); VBG overshoot 3.2-3.5 V | F (power-down and overstress at consumers) | Y | Patch the enable gating in core_support (BLOCK); gate consumers until VBG settles (a MACRO timer on the existing bias enables) | BLOCK + MACRO | core_support; digital | 3 + 0.5 | BP possible |

### 1f. Timing / support blocks (both chips)

| ID | Real? | Fix? | Fix | Step | Owner | Effort | Pin |
|---|---|---|---|---|---|---|---|
| TIM-10 ring PLL safe state 87-162 µA | F (safe-state spec) | Y | Fix the off-state leakage path | BLOCK (pll_ring) | timing | 2 | none expected |
| TIM-04 ring PLL HOLD fails extracted | F | Y (rule) | Host-follow must not use HOLD: that is a register validator rule in MACRO, plus the owners' confirmation | MACRO (rule) | timing; digital | 0.5 | none |
| TIM-05 / SP-02 ring PLL jitter / spurs | S (unverified) | Y | Chip-level jitter sim with the regulator and the batch-macro ripple | MODEL | timing | 2 | none |
| TIM-11 vco_replica 12/48 no start | O | Y | State the usable control range in the ATB / characterisation docs (no layout) | MODEL | timing | 0.3 | none |
| TIM-03 aosc out of window; reference receiver at 200 mVpp | S | Y | Report and rerun the corners; trim rule | MODEL | timing | 1 | none |
| TIM-01 TSPC /5 hazard | F risk | Y | Extracted ff run | MODEL | timing | 0.5 | none |
| TIM-12 / MOD-20 evidence records | evidence | Y | R+C records for both rings; evidence files for the 8 timing / LO cells | MODEL | timing; LO | 2 | none |
| ISL-04 no feed for an open switch | R | ruling | Coordinator decides whether to add a debug feed. If yes, it is a TOP item (an ATB force to the rail through an existing leaf) | TOP (if yes) | island_support | 1 | none |
| PWR-02 / PWR-13 POR ramps | R | Y | Run the brownout and slow-corner ramps of the power-up check | MODEL | core_support | 1 | none |
| AON-02 aosc no-kick state | F risk | Y | Start check in the evidence | MODEL | timing | 0.5 | none |
| MT-03 DCF.1a in four blocks (`pt_wrx_cap`, `pt_slicer`, `pt_wiredtx`, `pt_vco_replica`) | DRC | Y | COMP taps (the tapped GDS exist in `scratch/timing/drc12` except wrx_cap); fold into each block's re-layout; fill-aware re-extract of the QVCO and rings | BLOCK (shared) + MODEL | block owners | 1 per block | none (taps add no nets) |
| PAD-02 / RXR-ESD-1 / PAD-12 / ESD-06 / PAD-06 core HBM / CDM screens | S (unverified at the basic class) | Y | Rerun the screens at the basic class on the current blocks | MODEL | pads | 2 | none |

### 1g. Top level (floorplan / pt_wired owners; most already in convergence)

| ID | Real? | Fix? | Fix | Step | Owner | Effort |
|---|---|---|---|---|---|---|
| INT-13, INT-32, INT-33, INT-34, INT-36, PDN-12, PDN-13, AN-01, VER-KL2, INT-05, INT-31 | F | Y, in flight | Signoff merge of `fp-plan-code` / `fp-wired`; pt_wired fpw-11 island_rail wiredtx.VDD and POR_BYPASS ties (4cb46fe6, 007449c2) | TOP | chip assembly (both agents); verification | in flight |
| PDN-09 grid coverage 133 mV | S | Y | Widen ME/SE straps to 12 %, re-stitch; extract per chip at 85 °C | TOP | assembly; power | 2 |
| PDN-06 EM / IR at 85 °C | F risk | Y | All-net extresist of current-carrying nets; EM on straps | TOP + MODEL | assembly; block owners | 3 |
| PAD-13 ≥ 1 nF decap at the east HS pads | F (CDM evidence void otherwise) | Y | Place tiles; verify on the GDS | TOP | assembly | 0.5 |
| PDN-03 / PKG-06 decap | S | Y | The plan places 36/36 (rf) and 69/69 (wired) tiles; the PDN-02 row text ("16 do not place") is stale against the plan | TOP | assembly | 0.2 |
| HL-09 host inputs float with the FPGA unconfigured (CS_N can select SPI) | F | Y | Set PU on CS_N and pulls on the other host inputs in the provider tie list (KH-1 mechanism); no pad change | TOP | pads / assembly | 0.5 |
| XT-01 / XT-02 / XT-03 / XT-04 / XT-05 / XT-07 / RFR-07 shields and bundles | S | Y | Shielded coplanar LO bundle with fill keep-out; shields on bias trunks and D2H lanes; equal-length phase bus | TOP | assembly | 4 |
| LO-01 QVCO placement rule; SUB-01 / SUB-12 / SUB-13 macro distances | S | Y | Placement in the plan (adc_q 709 vs 782 µm is open: move within the channels, standing ruling) | TOP | floorplan | 1 |
| MOD-02 / SUB-11 chip-level extraction of critical nets and substrate | S (unverified) | Y | Extract and resimulate the chains; reduced substrate mesh | MODEL (on the TOP GDS) | assembly | 4 |
| MT-03 fill on the assembled GDS | DRC | Y | Fill flow on each chip | TOP | assembly | 1 |
| PKG-09 bond audit; INT-10 / INT-20 / MOD-06 / MOD-18 / INT-29 / AON-03 | F risk / hygiene | Y | Bond audit with the real die; regenerate the spec JSON from the conns; ring-level checks; uniquify; commit the layout_engine fix; sha manifest | TOP + MODEL | pads; chip top; coordinator | 4 |
| RFT-05 | S | Y | See 1e | TOP | assembly | in XT |

### 1h. Model / evidence and board rows (no tapeout cost step)

MODEL, to run in parallel with everything above: MOD-00, MOD-01, MOD-05 (freshness gate), MOD-07, MOD-19, MOD-21
(rerun the rcov C with `fixcap.py`), MOD-15, VER-KL1, PKG-08 / HL-03 / HL-01 (FPGA training spec), SP-01 (host-clock
plan), RXR-02 / RXR-05 / RXR-08 / RXR-10 / RXR-14, RFR-06, PDN-08 (procedure), PWR-12 (register text to the `CLAMP.md`
numbers), and WTX-09 part 1 (rerun the interlock rows on the fullfix netlist).

BOARD / gateware (real, but they do not touch tapeout): PWR-12 (B52 soft start), PWR-13 (B49), LU-03 (B53),
PKG-07 / TH-04 (thermal), BRD-01 / BRD-02, HL-05, RXR-04 / RXR-06 / RXR-07 / RXR-11 / RXR-12, EMI-01, OTH-01, PAD-08,
WTX-05, DIG-08 bring-up rule (≤ 125 MHz word clock until trimmed), PWR-14 (B54), PKG-11 and ESD-07 / INT-30 / SUB-10
(written questions to wafer.space).

Stale or close: CSP-01 (code 58 exists on both chips, per int04), PDN-02 text "16 decap tiles do not place", WTX-09
"cause unknown" (found: substrate-C double count), the `ctl_ports.txt` MW-29 note on `c_obs_pre4_en`, TIM-09 (align the
field text: documentation only), RFR-04 (needs a coordinator ruling: HT40 ACR and 10BASE-T are new features or
physical limits, not fixes).

---

## 2. Batches

### Batch M: one MACRO re-harden, both chips (pin plan frozen, no port added or removed)

RTL changes (all in the shared RTL; per-chip behaviour through `PT_CHIP`):

1. DIG-08a `host_rate` divider retime (hword).
2. DIG-08b REF_IN-domain island-sequencer reset synchronisers (`vreg_seq`, `wtx.pad_seq`, `wrx.frun`).
3. DIG-08c `wgear.g_rn` reset release on WSTB.
4. PDN-02 two-phase launch (clock-tree bank split), or clock gating of idle banks as the fallback.
5. WTX-09 `wtx.run_force` field → spare pt_wired pin.
6. INT-04 F7 ATB accept-set changes (pt_rf TRK_LO 22, pt_rf CDR VCTRL, pt_wired slicer bias); `chips.json`.
7. HL-06 fc_half2 and h2d logic fixes (no clock-mux buffer).
8. HL-04 `legal_n` admits opcodes 5 / 6.
9. WRX-03 per-sampler slicer trim fields plus the fourth bit → spare pt_wired pins.
10. USB-02 LS-mode validator rule plus HS bit repetition.
11. RXR-09 overload-detector status input on a spare pt_rf `s_*` pin.
12. MOD-17 VBG-settle gate on the bias enables (timer).
13. TIM-04 validator rule: host-follow never uses HOLD.
14. CDC-02 SAR capture on the done edge.
15. `c_cdr_g` reset value (if wired RX picks 3).
16. Conditional on coordinator rulings: SP-03 (second converter clock divider), HL-02 (long frames), DBG-03 (only if
    the gate list has a gap), HL-07 CRC (only if the spec requires it).

Pin check: items 5, 9 and 11 reuse unbound pins that already exist on that chip's LEF. All others are internal. Items 1-4,
7, 8, 10 and 12-15 add no port. **None moves a macro pin or changes the outline.** Gate before delivery: LEF PIN
sections and Metal5 strap pins diff-equal to the frozen pin set; route / Magic / KLayout DRC 0, LVS 0, XOR 0, antenna
0; GLS pass (with new cases for 1-3, 5, 8, 10, 13 and 14); STA at ss 3.15 V K 1.20 / ss 3.50 V / ff hold not worse
than the delivered macros on any domain; regression green; formal (DIG-05); then the per-mode power (PWR-06) and PD2
ripple rerun (PDN-02, PDN-11, LO-11) on the delivered result.

Count: **15 changes plus 4 conditional.** Effort about 15-20 agent-days, of which PDN-02 is 6-8. The rest is 1-2 days
each in RTL and bench, with one harden pair plus GLS (two runs, one heavy job each).

If item 4 does not converge, deliver the batch without it rather than hold the other 14. That is the only split
allowed, and it needs the coordinator.

### Batch B: BLOCK items, one re-layout per block (each block batches all its own fixes)

| Block | Chip | Items in the one re-layout | Effort | Pin / outline |
|---|---|---|---|---|
| `pt_wiredtx8` | wired | WTX-08, WTX-03, WTX-09 RUN_FORCE, TIM-13 trim sizing, DCF taps | 10-12 | BP (+RUN_FORCE; output stage) |
| `pt_wrx_cap` r10 | wired | WRX-22 / TIM-37 two-period hops, PWR-01, DCF taps; layout_engine fixed-pin option first | 5-6 | must hold r8 (no BP) |
| `pt_ctle` / `pt_rxselect` r6 | wired | WRX-20, WRX-13, WRX-05 | 5 | BP |
| `pt_slicer` | wired | WRX-02 trim range, WRX-03 fourth bit, MT-01 dummies, DCF taps | 3-4 | BP (+trim pins) |
| `pt_detect` | wired | WRX-08 threshold redesign | 4 | BP possible |
| CDR ring / `pll_ring`, `diff_clk_rx` | wired (+rf) | WRX-23 (if diagnosed real), TIM-10 safe state, TIM-08 parked start | 2-5 | BP possible |
| CDR regulator (pll_vreg instance) | both | INT-04 F7 VREG_CDR ATB tap | 1.5 | BP (+1 pin) |
| `lna` | rf | RFR-16, RFR-01, (RFR-10 if the attenuator changes) | 6 | BP (area down) |
| `qvco` top / `lo_mmd` / `lo_obs` / QVCO pair / `lo_vreg` | rf | LO-04, LO-14, LO-15, LO-10, LO-12, LO-11 (one LO pass) | 8-10 | BP possible |
| bbfilter / new overload cell / ADC buffer | rf | RXR-09 comparators, CNV-02 buffer, (CNV-06 decap) | 6-7 | BP (new cells) |
| ADC (conditional) | rf | CNV-07 / MOD-04 acquisition / comparator speed | 3-5 | BP if relaid |
| core_support bandgap | both | MOD-17 enable gating | 3 | BP possible |
| `pad_txpad` | wired | PAD-15 VSS text (XOR 0) | 0.5 | none |
| `pt_vco_replica` | wired | DCF taps (tapped GDS exists) | 0.3 | none |

Count: **14 block lots, 30 register items.** Effort about 60-75 agent-days in total, about 35 of it on wired blocks and
about 30 on RF blocks. Six of these blocks belong to owners who are not active (wired TX, LO, RF RX, converters, pads,
timing), so agents must be assigned to them.

### Batch T: TOP items (floorplan and pt_wired owners)

Already in flight: INT-13 / 32 / 33 / 34 / 36, PDN-12 / 13, AN-01, VER-KL2, INT-05, INT-31. New for this plan:
INT-04 F7 leaves and clk_obs word-clock iso (wired), WTX-09 RUN_FORCE net, WRX-03 trim nets, RXR-09 status net, HL-09
pulls, PAD-13 decap, PDN-09 straps, PDN-06 EM, XT-01/02/03/04/05/07 / RFR-07 / RFT-05 shields, LO-01 / SUB-01 / 12 / 13
placement, MT-03 fill, PKG-09 bond audit, the hygiene rows (INT-10, INT-20, MOD-06, MOD-18, INT-29, AON-03), ISL-04 if
ruled, and IQ-03 equalisation. Each BP block lands as a re-place within the plan's channels (standing ruling) on one
integration run per chip.

Count: **11 rows in flight plus 21 new items.** About 25 agent-days beyond the in-flight convergence.

### Batch E: MODEL / evidence

About 45 rows (section 1h plus the MODEL rows of 1b-1f), about 40 agent-days. These can run any time within the 6-job
cap. Some gate block decisions and must come first: WRX-01, WRX-23 diagnosis, the LO-04 MMD at 3.50 V, the RFT-06
real-LO chain, the CNV-06 real-source bench, DBG-03 confirmation, the WTX-09 interlock rerun, and the WRX-04 limits
proof.

### Order (keeps both chips level and does not disturb floorplan convergence)

1. **Now, in parallel with the floorplan convergence (no floorplan input):** the coordinator freezes the pt_rf pin set
   (DG9-29 vs DG9-32) and gives the rulings (SP-03, HL-02, ISL-04, TIM-13 spacing, RFR-04, INT-04 code names). The
   deciding MODEL runs start, as listed in Batch E. Agents are assigned to the inactive block owners: wired TX first
   (laggard chip), then LO / RF RX.
2. **Batch M RTL plus benches** (about 2 weeks of digital work). It touches both chips equally, and the harden runs only
   after the pin set is frozen. Delivery is a GDS / LEF swap with identical pins, so the floorplan branches drop it in
   without re-planning.
3. **Batch B in two interleaved queues:** a wired queue (wiredtx8, wrx_cap r10, ctle r6, slicer, detect) and an RF queue
   (lna, LO pass, bbfilter / buffer / overload cell). Run one block per queue at a time, so both chips advance at the
   same rate within the 3-jobs-per-owner limit. Each block publishes only when its own gates pass and its pins / outline
   are fixed.
4. **Batch T, once per chip:** one integration run that takes the batch macro, every BP block that has landed, and the
   new TOP nets. Then `signoff.sh` for both chips. Do not land BP blocks one at a time into the floorplan; one re-place
   per chip, at the end, keeps convergence stable.
5. **Re-sign** the chip-level MODEL rows (MOD-02, PDN-02 PD2, PDN-11, SP-01) on the final GDS.

---

## 3. Judged impossible or highly unlikely (the coordinator must confirm; reasons go into the register rows)

| ID | Judgement | Evidence |
|---|---|---|
| RFR-01 (part) | The 4.1 dB on-chip NF is a physical limit at the chip input | Package loss 2.4-2.7 dB comes before the LNA (register). LNA NF incl. channel tt 5.20-5.53 dB with `pad_rf_pair` r4. The relayout is still done; the residual goes to the board fallback LNA |
| RXR-14 LoRa sensitivity −3.9 dB | Follows the RFR-01 floor | Same chain; fallback LNA |
| WRX-04 SATA Gen2 return loss through the COB | Likely a physical limit; to be proven by MODEL (pad + ESD + bond C against 8 dB) before judging | 6.67 dB at the die, 4.98 dB through the COB vs 8 dB; PCIe / DP / 3G1 pass |
| HL-06 (residual) | Full host rate on slow dies at 3.50 V with the host cluster pinned is highly unlikely | DG9-31: kept clkbuf after the muxes gave pt_wired 267 DRC / 154 LVS and worse timing; pt_rf not better. DG9-32: plan pin order made the pt_wired host gearbox worse (d2h_oddr −3.31). The root cause is wire load on the fixed hand-placed cluster. div2 / div4 plus FPGA training stay |
| DIG-03 cmd/response latency vs USB HS turnaround | Highly unlikely without undoing the timing pipelines | 2.4× over the 400 ns gate; DG9-1 / DG9-LC-* added stages for closure. Board USB PHY (B8) |
| MOD-00, MOD-03, MOD-08, MOD-11, PAD-14, SUB-10 | Cannot be resolved before silicon (need measurement or the foundry) | Mitigated by pessimistic bounds and on-die structures |
| PDN-02 two-phase (conditional) | Infeasible **only if** the batch attempt regresses timing | To be decided by the batch gate; bank clock gating remains |
| Capture r10, CTLE r6, WTX-08 at ss-pess 3.15 V (conditional) | Only after one more bounded attempt each | Capture: r9 (nominal broke, 15/200), r10a (7/200 nominal, 77/200 pess), r10b-skew (0 words nominal, 12 pins moved), r10c (65/180 pess, +9.6 µm) all failed; the two-period hop design was never built. CTLE: r4 NO-GO, r5 fails ss-pess at 3.125 / 3.24 Gb/s (47.4 / 40.7 mV vs 60) and the G3 spread. WTX-08: R-aware pad eye 0.090 V at ss-pess 3.15 V, 3.125 Gb/s |
| DG9-11 | Excluded (an outline change with no deficiency) | - |

## 4. Pin / outline consequences

- **Macro (MP): none.** Every MACRO item either stays internal or reuses an already existing, unbound pin. DG9-11 is
  excluded for that reason.
- **Block (BP), each needs one re-place by the floorplan owner:** `pt_wiredtx8` (+RUN_FORCE; output stage),
  `pt_ctle` / `pt_rxselect`, `pt_slicer` (+trim bits), CDR regulator (+ATB_OUT), `lna` (area should shrink),
  new cells for RXR-09 and CNV-02, and possibly `pt_detect`, the LO cells, the ADC, the bandgap and the CDR ring.
  `pt_wrx_cap` r10 must hold the r8 outline and pins. `pad_txpad` (PAD-15) has no geometry change.
- **Pad ring:** none, unless a T-coil is attempted for WRX-04, which would be a pad outline change. That is not
  recommended until the limits proof is done.

## 5. Totals

Batch M 15 changes (+4 conditional), about 15-20 days. Batch B 14 block lots / 30 items, about 60-75 days. Batch T 11
in flight plus 21 new, about 25 days. Batch E about 45 rows, about 40 days. Infeasible: 5 firm (RFR-01 floor, RXR-14, HL-06
residual, DIG-03, and the pre-silicon model group counted once), 1 pending a limits proof (WRX-04), and 4 conditional
on one more attempt (PDN-02 two-phase, capture r10, CTLE r6, WTX-08 at ss-pess). Board / gateware obligations: about 25 rows, outside tapeout. Stale or close: 6.

## Addendum 2026-11-28: block supply pins too small for their current (assembly agent 2, plates-hook 74b4442a)

Capacity = pin narrow dimension × layer EM limit at 85 °C (Metal1-4 2.09 mA/um, Metal5 4.5 mA/um). Pin shape = label polygon; owners confirm. All VSS. BLOCK batch items (pin width/layer change ripples into one re-place per chip).

| Chip | Pin | mA | Pin today | Over by | Change needed |
|---|---|---|---|---|---|
| rf | lo_txbuf VSS | 59.3 | M5 2.0 um | 6.6x | M5 >= 14 um |
| rf | lo_vreg VSS | 27.5 | M1 1.0 um only | 13x | M5 >= 7 um (or M4 >= 14) |
| rf | lo_mmd VSS | 34.8 | M5 2.0 | 3.9x | M5 >= 8 |
| rf | rfdriver VSS | 24.3 | M5 2.0, no plate path | 2.7x | M5 >= 6 on a reachable edge |
| both | pll_vreg2 VSS | 20.9 | M4 4.0 | 2.5x | M4 >= 10 or M5 >= 5 |
| rf | rxmix_i/q VSS | 3.1 | M3 0.8, no path | 1.9x | M3 >= 1.5 |
| rf | adc_i/q VSS | 6.3 | M4 2.0 | 1.5x | M4 >= 3 |
| rf | lo_ext VSS | 13.7 | M5 2.0 | 1.5x | M5 >= 3.1 |
| both | vco_replica VSS | 11.8 | M5 2.0 | 1.3x | M5 >= 2.7 (also IR 31/59 mV) |
| rf | bbfilter_i/q VSS | 5.3 | M3 2.0, no path | 1.3x | M3 >= 2.6 |
| rf | lo_mmd_qdum VSS | 10.0 | M5 2.0, no path | 1.1x | M5 >= 2.3 |
| rf | lna VSS | 21.4 | M3 9.4 | 1.1x | M3 >= 10.3 |
| wired | wrx_cap VSS | 46.6 | M5 2.0 | 5.2x | M5 >= 11 |
| wired | usb_txdrv VSS | 20.0 | M5 1.6 | 2.8x | M5 >= 4.5 |
| wired | ptrim VSS | 21.0 | M4 5.0 | 2.0x | M4 >= 10 or M5 >= 5 |
| wired | detect VSS | 2.4 | M5 0.44 | 1.2x | M5 >= 0.6 |
| wired | slicer VSS | 9.8 | M5 2.0 | 1.1x | M5 >= 2.2 |

## Addendum 2: veteran-review audit (scratch/reviews/veteran-audit-2026-11-28.md)

- MACRO + BLOCK + TOP: host/core clock bypass (CM-1): pt_clockmux host-clock mux spare inputs (tied VSS today) to H2D / REF, regfile decode allows ref_in / aux_clk / wclk_in, so a dead ring PLL does not strand the host link. Both chips.
- MACRO: PRBS checker bits-checked counter (BER needs locked time); internal pattern-generator -> checker loopback.
- TOP: plate slotting (island_trunks._plates draws no holes; pt_rf lo_txbuf.VSS M5 plate 37.6 x 240 um fails MSLOT5.1).
- MODEL: circuit-under-pad with aluminium wedge bonding (run 1): CUP deck on every custom pad family (protection macro alone 174 CUP.3 hits; precheck skips CUP).
- MODEL: supply clamp turn-off with a current-limited source (0.5/1/2 A, board caps, 50-100 us).
- RTL rule: reject the CDR state where the loop filter floats (CDR off, ring on, line-PLL off).
