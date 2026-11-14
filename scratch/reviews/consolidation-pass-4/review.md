# Consolidation pass 4: adversarial review (2026-11-14)

Read-only paper review. No simulation was run. Scripts: the `check_top.py` parser on `pt_chip.conn`, grep, JSON reads.
`P` = `projects/programmable_transceiver_platform`. Checked against the working tree (the regfile, register map and
`pt_regmap.py` are modified and uncommitted, so line numbers are the working tree's).

## Summary

| ID | Verdict | Decisive fact |
|---|---|---|
| CP4-1 | SURVIVES WITH CONDITIONS | 3 of the 132 clamp outputs also feed `clk_obs` outside the macro; 129 can move, not 132 |
| CP4-2 | SURVIVES (delete) | Inert as bound and fails extracted; the "keep the learning" alternative does not work |
| CP4-3 | SURVIVES WITH CONDITIONS (heavy; three premises wrong) | Not the same pad family, 810 MHz not 340 MHz, exclusion not proven by the rule, 0 mA saved |
| CP4-4 | SURVIVES WITH CONDITIONS | FBCK runs in every enabled ring state; collides with CP4-1 on `fc_src[0/1]` |
| CP4-5 | SURVIVES WITH CONDITIONS (weak; prefer AP4-7) | Straight route crosses the digital macro; WMON bandwidth becomes hostage to the BB_Q board load |
| CP4-6 | SURVIVES WITH CONDITIONS, mostly already done | 136+ of the ~250 bits are already `live` in the working tree; two rules do read biasgen codes |
| CP4-7 | SURVIVES WITH CONDITIONS | Shared chain cannot be reset for a CONV ratio change without stopping the host clock |
| CP4-8 | SURVIVES | Today's LDE crossing is a one-ring-cycle pulse through a 2.08 ns clamp; local counter is strictly better |
| CP4-9 | Option A BROKEN as a "drive from PRE" wiring change; option B SURVIVES | PRE is single-ended CMOS, `lo_obs` is a differential CML /2 that already fails 4 of 24 corners |
| CP4-11 | SURVIVES WITH CONDITIONS | `aosc` (the monitor time base) is forced off during RF payload; the mission clock has no present detector |

## CP4-1: 132 island -> macro clamps as standard-cell AND2 in the macro

Verdict: SURVIVES WITH CONDITIONS. The premise is right and the standard cell is electrically the better clamp.

Checked:
- Count (parser on `pt_chip.conn`): 121 `iso_clamp` + 12 `iso_clamp_x4` in group `core`. 11 of the x4 drive a macro pin;
  the twelfth (`iso_clk_obs`, conn:412) drives `debug_pads.clk_obs`. So 132 is right, and **15 clamps stay, not 14**
  (8 + 2 + 1 + 1 + 2 island-rail receivers, plus `iso_clk_obs`).
- **Three of the 132 outputs have a second receiver outside the macro**: `rf_rx_clk` -> `clk_obs.IN4`,
  `host_word_clk` -> `clk_obs.IN13`, `fc_src[0]` -> `clk_obs.IN9` (conn:404-405). If the clamp moves inside the macro the
  clamped net no longer exists outside. Either those three stay custom, or the macro exports the clamped copy, or
  `clk_obs` takes the raw island net (a new pll -> debug crossing with its own clamp). CP4-4 adds `fc_src[1]` to this list.
- Corrected saving: 129 cells (121 x 906 + 8 x 1025) = **0.118 mm2**, 0.117 with CP4-4. Not 0.121.
- Same rail: custom core clamps are on `VDD` (conn:245-270, 338, 353), the macro's rail (`iso-placement.json` "supply").
- Drive: the x4 cells are placed "at the macro pin" / "within 30 um" (`iso-placement.json` placements), so the island
  driver already drives the long route today. Nothing loses a driver.
- Crowbar: the custom cell is an **ungated inverter on A** followed by a NOR (`P/analog/island_support/design.py:332-338`).
  A floating or mid-rail A does draw crowbar current in it today. A NAND-based AND2 with the other input low does not.
  The README's ISO = 1 checks report Y only, not supply current (`island_support/README.md` section 2a table).
- M6: the audit needs a clamp on every K1 net with ISO from the driving island (`integration-m6.md:65,83-89`); it does
  not require the cell to be outside the macro. `island_off = ~island_on` is a macro signal in both cases.
- `rf_rx_clk` and `rf_tx_clk` are two clamps on the same `CONV_CLK` (conn:267-270): one AND2 inside the macro.

Conditions:
1. Keep (or re-export) the three shared nets above; settle together with CP4-4.
2. "dont_touch on the cell" is not enough. The net from the macro pin to AND2.A must be excluded from port buffering,
   resizer repair and hold fixing, or a buffer lands on the floating input and the crowbar returns. Add a post-route
   netlist check: each of the pins fans out to exactly one AND2 A pin and nothing else.
3. The clock crossings (8 x4) need the AND2 output declared as the clock root for CTS.
4. Rerun the M6 s2 float case and the inverted-ISO must-fail case with the standard cell (`integration-m6.md:127,152`;
   `always-on-audit.md:172` lists the inverted-ISO case as still open).
5. Ring outputs (`LOCK`, `FBCK`) swing to 0.9 x rail (D-PHLOAD, decisions.md:56) into a 5 V-library gate at 3.15-3.35 V:
   state the static current of the AND2 at A = 2.57 V. The custom cell has the same exposure.

## CP4-2: `polyphase`

Verdict: SURVIVES as a deletion. User decision because of the no-scope-cut memory, but nothing is cut.

Checked: bound with `INP/INN/EN = VSS` and all outputs open (conn:313-314); fails extracted, limiters do not toggle
(`P/analog/timing/README.md:117,141`, risk TIM-06 `spec/risk-register.md:181`, which already offers "drop");
`LO-INTEGRATION.md:42` forbids connecting it; `spec/consolidation-pass.md:83` books no functional route for it. No
mode, rate or fallback reaches it. Current is 0 with EN = 0 (the inventory's 2.8 mA is the enabled figure).

The proposal's alternative is wrong: `obs_pre4` is specified for CMOS sources up to 1 GHz (`obs_pre4.spice` header),
the polyphase outputs are 2.4-2.5 GHz, and with limiters that do not toggle there is nothing to observe. An AUX_CLK
input would also add a load to the LO Q pad only. Do not build it.

Condition: update the documents that still name it as the autonomous-LO route (`spec/tapeout-plan.md:84`,
`spec/analog-architecture.json:2339`, TIM-06).

## CP4-3: `WCLK_IN` onto the `AUX_CLK` pair

Verdict: SURVIVES WITH CONDITIONS, heavy. I found no specified mode that needs both pins at once, but three of the
proposal's premises are wrong and it is not ready for a user decision as written.

No simultaneous need found:
- CDR ring reference is `ref_sel ? WCK_IN : PREF` (conn:367, `wired_rx/PINS.md:264`); TX ring takes `PREF` (conn:349).
  TX on REF_IN and CDR on the forwarded clock still works. Both-rings-dead fallback (TX external, RX external) still
  has two pins (REF_IN + AUX). host_follow uses H2D (D-HF). `conv_sample` and `host_clk` forbid `wclk_in`
  (`spec/debug-controls.json:866-890`), so WCLK_IN has no RF use today.
- Lost: three external clocks at once, and `wire_line = aux_clk` with `wire_sample = wclk_in` as distinct sources
  (legal today, `debug-controls.json:832-860`; D-EXTCLK says they reach only prescalers and observation).

Wrong premises:
1. **"Same pad family"**: `pad_wclk_in` is `pad_rf_pair` on the debug island (conn:165); `pad_aux_clk` is `pad_refpad`
   on the pll island with a `VCM` pin fed by a block that does not exist (conn:175-178, D-REFVCM). `pads/README.md:292`
   and the LO bench say AUX_CLK is an rf pair. D-PADS (decisions.md:65) is open. `pads/README.md:268` limits a clock
   into `diff_clk_rx` on the refpad to 0.55 V peak and names AUX_CLK as the way out, which assumed the rf pair.
2. **"25-340 MHz"**: WCLK_IN also carries the B13 retimer clock (line, /2 or /4 of 1.25-2.5 Gb/s,
   `spec/board-requirements.md:28`) and its benches are 480 / 625 / 810 MHz (`wired_rx/README.md:285-296`).
   `diff_clk_rx` is benched for clocks at 100 MHz-1 GHz only (`timing/README.md:137`); 25 MHz was never benched.
3. **Exclusion is not proven by `rf_wired_payload_exclusive`**. The rule (`pt_regfile.sv:1082`) names adc, dac, lna,
   rfdriver against wiredtx, cdr, usbdrive. It does not cover `lo_mode`, rxmix, bbfilter, `debug.clk_select`, the CDR
   ring, capture or WMON. The all-fallback RF receive (external LNA with rule 5 forcing lna off, external ADC on BB_I/Q,
   external LO on REF/AUX) activates none of the six blocks, so it is legal together with `cdr` active on WCLK_IN.
   `rx_en_aux` has no `lo_mode` term (`pt_regfile.sv:1047`) although `LO-INTEGRATION.md:106-108` requires the receiver
   off in modes 1 and 3.

Other findings:
- **Current saving is 0, not 4.5 mA.** Both receivers and both `obs_pre4` have enables; the surviving one is on instead.
- Area 0.174 is right (146008 + 22341 + 3667 + 1931 um2).
- Route: `rx_wclk_in` (2850,1550) to `cdr` (2900,1900) is about 0.35 mm today; from `rx_aux_clk` (1050,3150) it is about
  3.1 mm (`v6_floorplan.py:79,80,86`), along the south edge of the digital macro. For HDMI/DVI RX this is the primary
  route's phase reference (B16, `board-requirements.md:35`), not a fallback. `iso_aux_ck` is characterised for about 1 mm.
- Pad load in wired modes: `lo_ext` leaves a 2 pF MIM into 2 k and floating EXT gates with `CMLSEL = 0`
  (`LO-INTEGRATION.md:113-124`, MW-20 not fixed).
- Board: one pin fed by the LO hybrid Q output and by the TMDS or retimer clock needs a selection element or stub on
  the Q leg only. B3 gives a +/-1.2 dB amplitude window and BP-2 demands I/Q delay match (`board-requirements.md:14,41,71`).
- Pad sites: the freed sites are east (`contract.json` bond map `east/bidir[16,17]`); the LNA ground split wants west
  sites. It helps only by moving the POR strap east.

Conditions: resolve D-PADS first; bench 25-810 MHz through the real pad, the `lo_ext` off load and the 3.1 mm route,
with the TMDS reference jitter stated; add a pad-class rule (external LO excludes any AUX receiver use); write the
board selection scheme into B3/B13/B16 and mirror it on REF_IN; fix MW-20; user decision, since the pin disappears.

## CP4-4: `obs_pre4_pll` / `obs_pre4_cdr` -> FBCK

Verdict: SURVIVES WITH CONDITIONS.

Checked:
- FBCK is the feedback divider output through two inverters (`pll_ring.spice:140-166`). The dividers are reset only by
  `ENB`; HOLD only holds the PFD in reset and "the VCO keeps running" (`pll_ring.spice:60-66`). So FBCK runs in HOLD and
  in CDR bang-bang mode.
- **Ratio is wrong in the proposal**: FBCK is VCO/8 (N4 or N8), VCO/16, or VCO/10 (N5 or N10), not N = 4/8/5/10.
  At most 104 MHz (`PINS.md:282` gives 52 / 83 MHz), inside the 500 MHz `clk_obs16` limit.
- FBCK is what the qualified lock check uses (`pll_ring.spice:167-168`, `ctl_ports.txt:204`).
- PH1 has no other load than the `obs_pre4` (D-PHLOAD); on the TX ring PH3/5/7 are open dummy routes
  (`wired_tx/INTEGRATION.md:81`). Removing it makes the odd phases equal.
- `fc_src[1]` is a core-rail net; core -> debug needs no new clamp, same as `IN9 = fc_src[0]` today.
- Divider-dead case: the VCO stays observable without FBCK through `clockmux` -> `WIRE_CK` / `WSMP_CK` ->
  `obs_pre4_wire` / `obs_pre4_wsmp` (conn:321-327, 398-399). The proposal's "only ATB_VCTRL" is too pessimistic.

Conditions:
1. Lift the regfile ban on CLK_OBS codes 2 and 3 (D-OBS, decisions.md:51); otherwise the divider-dead observation is lost.
2. PH1 gets the same dummy route as PH3/5/7.
3. Settle with CP4-1: `fc_src[0]` and `fc_src[1]` must exist outside the macro.
4. Document that code 14 now passes a core-rail clamp beside the macro, so it is a frequency check, not a jitter
   measurement; code 3 is the clean path. Rename codes 8 / 14 and the divide ratio in `debug-controls.json`.

## CP4-5: `WMON` onto a BB_Q pad leg

Verdict: SURVIVES WITH CONDITIONS, weak. Prefer AP4-7; if AP4-7 lands this saves no core area.

Findings:
- Route: `bb_tap_wmon` (3300,3500) to `bb_tap_q` (1050,3500); the digital macro occupies x 1262-2978, y 3030-4670
  (`v6_floorplan.py:49,50,192-193`). The straight line crosses the macro. The detour is 3 mm or more, past the ADC and
  capture area.
- The wire is a permanent stub on BB_Q_P only, in RF observe and inject modes too. BB_I/Q is the external-ADC fallback
  for receive, so it is a data path, not only a debug view.
- **Output resistance is about 220 ohm, not 100 ohm**: 71.3 MHz into 10 pF extracted (`rf_rx/README.md:545`).
  WMON's source is 0.67-0.85 GHz (`wired_rx/README.md:203`). On a shared net the board load of BB_Q (external ADC /
  DAC, B10) sets the WMON bandwidth: 10 pF gives 71 MHz.
- Exclusion is not proven (same rule gap as CP4-3: bbfilter and rxmix are not in the rule). `obs_en` is one bit for both
  taps (`c_bb_tap_obs_en`, conn:223), so I-only observation while WMON uses the Q pad is impossible as bound. With
  `inj_en` set, the WMON follower would drive the bbfilter inject node.
- 0.142 mm2 is right for `pad_wmon`.

Conditions: an isolating switch at the pad end of the long wire, or accept the stub with a number; a new pad rule
(`wmon_obs_en` excludes any `bb_tap` mode); a board scheme that keeps the BB_Q_P net low-capacitance for WMON use.

## CP4-6: calibration fields as `live`

Verdict: SURVIVES WITH CONDITIONS, and mostly already done.

- In the working tree `slicer.offset.trim_d0..e3` (80 bits), `cdr.phase_trim.p0..p7` (40), `slicer.threshold.vth_a/b`
  (16) and the bbfilter trims (50) are already `live` / `live_trim` (`spec/register-map.json` fields 172-179, 214-221,
  234-241, 252-253), single rank in the RTL (`pt_regfile.sv:260`: `a_` is a wire of `s_`).
- Remaining candidates: vsel 8, hsbias 8, termination trim 4, bandgap trim 16, biasgen codes about 30. That is about
  65 flops, roughly **0.008 mm2, not 0.03**.
- Island gating is kept for live fields (`pt_regfile.sv:547`), so the "regfile forces island outputs to 0" assumption
  of D-ISO holds. Readback is unchanged (`:2763`).
- **"None of the 16 rules reads a trim" is wrong twice**: the RTL has 42 rules, and rule 27 `biasgen_fine_needs_coarse`
  and rule 29 `root_ref_force_needs_idac2_off` (`pt_regfile.sv:1096`) read biasgen codes.

Conditions: keep `core.biasgen.*` select and idac codes shadow + active (or check those rules on live writes). Live
fields have no revert; say so for the bandgap trim, which moves every reference on the chip in one write.

## CP4-7: `prescale` + `prescale_conv` on one chain

Verdict: SURVIVES WITH CONDITIONS.

Checked: both take `WIRE_CK` (conn:332-335), power-of-two taps only (`prescale.spice` header), so every ratio pair
remains. `prescale_hf` is on the CDR ring and is untouched. 0.013 mm2 and 2 mA are right.

Problem: today a ratio change can be made cleanly by EN = 0, change, EN = 1 on that cell. On a shared chain a reset
also stops `PRE_CK`, which is `HOST_INT` and the macro's `ct_wclk` (conn:321, 338). `debug.clk_select` requires
break-before-make.

Conditions: each tap has its own stop (all-zero select, re-timed so it gives no runt pulse) and the chain reset is the
OR of both enables; the first stages drive two mux inputs, so the extracted rerun is at the top input rate; the
"one more mux" jitter note in the proposal is not needed if each tap has its own mux.

## CP4-8: `wordclk` counter into `pt_wrx_cap`

Verdict: SURVIVES. Checked:
- `LDE` is one ring period wide (`wordclk.spice` header) and crosses through a plain `iso_clamp` (conn:343) whose worst
  delay is 2.08 ns into 200 fF (`island_support/README.md` section 2a) against a 1.2-2.5 ns period. The existing
  arrangement is the risk; the header itself tells far consumers to re-register locally.
- `WORD_CLK`, `LD`, `LDB` are open (conn:342). D10 / D20 carry the same information as the capture's B2 / B1.
- A counter on CKP follows an external clock if D-EXTCLK is ever built.

Notes: net saving is below 0.025 mm2 (the counter moves, it does not vanish). The counter adds clock load to one CKP
phase on a `ptrim` output that is already loaded 3-6 times its bench value (D-PTRIM): balance it or show the trim
range covers it. Only with the next capture revision, as the proposal says.

## CP4-9: `lo_obs` from `qvco.PRE`, or gate PRE off

- Option A, BROKEN as described. `PRE` is a single-ended CMOS output on `VDDB`, a tap of I+ only, with a 30 fF load
  limit (`LO-INTEGRATION.md:62`, `lcvco/loop_design.py:11`). `lo_obs` is a CML /2 clocked by the differential tank pair
  at 1.7 V common mode, and the published cell does not divide at ss / 3.15 V (`LO-INTEGRATION.md:73`). This is a new
  input stage on a failing cell, in CMOS at 2.45 GHz, which already failed once at ss (`lo_ext.spice` header, `ct_lodrv`).
- Option B, SURVIVES: gate the PRE buffer off. It needs a QVCO pin or netlist change (no enable today), saves about
  3 mA and removes an unloaded 2.4 GHz CMOS stage from `RAIL_pll`. Do it with the LO26 revision.
- `rf_lo` observation exists only for the on-chip LO (the tank is off in external-LO modes), so neither option changes
  what the external-LO baseline can observe.

## CP4-11: `fault` made in the macro

Verdict: SURVIVES WITH CONDITIONS. No supply-level function is lost; one clock function is missing in both versions.

Checked:
- Fields: require_reference, require_input_clock, require_rf_lock, require_wire_lock, a 6-bit supply mask and two tick
  counts (`spec/register-map.json` `monitor.config.*`). The supply mask is 6 bits wide, the width of `island_pgood`.
- Supply level: pgood is a ratiometric rail-up flag (`register-map.json` `gating_rule`), the POR ignores dips above
  1.5 V, and brownout is assigned to the board supervisor B1 (`spec/tapeout-plan.md:74`, `board-requirements.md:11`).
  An on-chip absolute-level monitor was never specified, so none is removed.
- `fault` acts combinationally on the outputs (`pt_regfile.sv:390-534`), so a level-type condition needs no clock.

Gaps in "every input already exists":
1. **Time base.** The tick counters use `aosc` (`debug-controls.json:1728`), and the regfile forces `aosc` off while an
   RF payload runs (`pt_regfile.sv:456`). In RF modes the only clocks left are the ones being monitored.
2. **No present detector on the mission clock.** `s_aux/wclk/wtx_ext_present` come from debug-island receivers
   (conn:375-388), zero when that island is off. `s_ref_present` needs `rx_ref_in` on, which is off in external-LO
   modes. H2D_CLK, the only clock in the die-1 RF baseline (mode-walk MW-7), has none. If it stops, the macro stops and
   the RF driver keeps transmitting the last sample.
3. RF lock has no analog indicator; `fc_src[5]` needs a counter gate and does not exist in external-LO modes.

Conditions: define each condition as asynchronous level or clocked, and name the clock; decide whether "TX mutes when
the sample clock dies" is required. If yes, one more instance of the existing `diff_clk_rx` PRESENT detector on
`CONV_CLK` or `host_word_clk`, on the always-on rail, is the whole analog part. Update the expected result
"1 under an injected supply fault" (`debug-controls.json:3168`) to say island rail, not VDD.

## Section 5 spot checks

1. **"Dropping `lo_mmd_qdum` now: no evidence until LO26."** Fair for deletion, but a zero-area option was skipped. Its
   enable is tied to `c_lo_mmd_en` (conn:300-301). The dummy does not balance today anyway: 200.7 / 125.9 fF of wiring on the
   I tank against 22.1 / 30.5 fF on Q (`timing/README.md:664`). A separate enable bit lets silicon measure quadrature
   with the 8 mA on and off, the same treatment `lo_obs_q` already gets (EN tied low, `LO-INTEGRATION.md:29`).
2. **"WMON onto WTX_EXT or WCLK_IN: all three can be in use together."** Asserted, not shown. Rule 8 already excludes
   the detect test current with `wtx_ext`, so `wire_detect_via_wmon` and WTX_EXT are exclusive; the remaining conflict
   is the RX scope during an external-TX loopback, and WMON with WCLK_IN during the B13 fallback, which is real. The
   rejection stands, but note that `pad_wmon` already shares its ESD rail with `pad_wtx_ext` and sits beside it
   (east bidir[22-24]); that neighbour needs no cross-die route, unlike CP4-5.

## Factual errors in consolidation-pass-4.md

- "The 14 clamps ... stay": 15 (`iso_clk_obs`). Three of the 132 also feed `clk_obs`; CP4-1 area is 0.118, not 0.121.
- "None of the 16 rules": 42 rules in `pt_regfile.sv`; rules 27 and 29 read biasgen codes.
- The rule is called "the proof of mutual exclusion": it covers six RF and three wired state fields only.
- CP4-3: "same pad family" (refpad vs rf_pair), "25-340 MHz" (up to 810 MHz), "3.5 + 1 mA" (0).
- CP4-4: FBCK is VCO/8, /16 or /10. "Observable only through ATB_VCTRL" ignores the clockmux paths.
- CP4-5: "100 ohm follower" is about 220 ohm; the route cannot be straight.
- CP4-6: "the fields do not exist yet" is stale for 186 bits that are already live in the working tree.
- CP4-2: the `obs_pre4` alternative cannot take a 2.4 GHz input.
- Section 2.6 / CP4-11: `island_pgood[5:0]` and the present flags are listed as sufficient; the time base and the
  mission-clock detector are missing.
- `decisions.md:58` cites the rule at `pt_regfile.sv:1179`; it is at 1082 (the pass-4 file has it right).
