# r11/rc_ctle: resistance-aware (R+C) extraction of pt_ctle r4 and pt_rxselect r2 (sub-agent of the wired RX owner, 2026-11-18)

NOT published, NOT committed.  Nothing under P/ or scratch/wired_rx/r10ctle is edited; inputs are read from
r10ctle/stage/gen (ctle.mag b0e28aec..., ctle.gds 469dd090..., ctle.ext.spice 66f9c9ff...; rxselect.mag 4b270962...,
rxselect.gds 8f53c1a7..., rxselect.ext.spice 4c51041e...).  Every ngspice / Magic run goes through ../../slot.sh.

## Limits (written 07:08 UTC, BEFORE any extraction or simulation; not to be relaxed)
Judged quantity = the change from the capacitance-only staged extraction to the R+C extraction, same bench (r11/chain/rc11.py
wrapping r10ctle/ch10.py, pad model physical-r-typ.spice, termination code per corner), same corners (tt, ss315, ss350, ff, ssp315).
- GATE (a change of extraction must not move a gating quantity across its limit):
  eye at SL >= 60 mVppd; eye width at 60 mVppd >= 0.25 UI; SL common mode inside 0.38-0.66 V.
  A cell that already misses with the C-only netlist is reported as "already missing", and the R+C delta is still reported.
- REPORT (every change larger than): 0.3 dB of chain gain (20 MHz, 625 MHz, 1.25 GHz, 1.62 GHz, peak), 5 % of eye height,
  10 mV of SL common mode, 2 % of supply current.  Width change reported when >= 1 grid step (1/16 UI PDA, 1/40 UI transient).
- "Metal resistance matters" = any REPORT threshold exceeded or any GATE crossed -> the wire and the widening are named.
- Extraction validity (deliverable 1), all four must hold for each cell or the netlist is declared unfit:
  (a) device count and every device parameter (model, w, l, ad/as/pd/ps, m, r_width/r_length) equal to the C-only extraction,
      device by device, and the port list identical in name and order;
  (b) known answer: every extracted resistor x1e-6 -> AC response (block bench, 1 MHz-8 GHz, differential gain to SL) within
      0.1 dB of the C-only netlist at every frequency point where the C-only gain is above (peak - 40 dB);
  (c) negative control: every extracted resistor x10 -> the same response must differ by MORE than 0.1 dB somewhere in 1 MHz-3 GHz
      (if it does not, the bench cannot see resistance and (b) proves nothing);
  (d) the two or three largest port-to-terminal resistances agree with a hand sum (length / width x sheet + vias, PDK values) within
      +-30 % (extresist is a lumped-segment approximation; outside +-30 % is reported as a disagreement and investigated).
- Direct/USB path through pt_rxselect (CTLE powered down on SL): -3 dB bandwidth change reported if > 5 %; DC loss change if > 0.3 dB.
- Clocked transient (ideal clocks, ss315, 2.5 and 3.24 Gb/s T3): same GATE; additionally bit errors must stay 0 if they were 0.

## Method (how the R+C netlists are made)
- Magic 8.3.678 (pinned analog image sha256:bd7a702b..., tech gf180mcuD of that image, extract style ngspice() = typical), flat .mag
  from r10ctle/stage/gen copied to ext/<cell>/pt_<cell>.mag; mkext.sh: `extract all; ext2sim labels on; ext2sim; extresist simplify off;
  extresist all; ext2spice lvs; cthresh 0; rthresh 0; extresist on`.  `simplify off` is what makes Magic write EVERY net: with the
  default (and with the deprecated `tolerance`, any value) only nets above its delay threshold are written (rxselect: 1 net of 12;
  the detect sub-agent's `tolerance 10` run wrote 40 of 364 nets -> its netlist has resistance on a minority of nets only: told to owner).
- The raw extresist netlist is NOT used as is: its capacitors are wrong (lumped net C written AND per-node C again: rxselect `enb`
  25.0 fF against 9.47 fF C-only).  mkrc.py builds <cell>.rc.ext.spice = C-only devices + C-only capacitors verbatim + the extresist
  resistors, device terminals moved to the extresist terminal nodes.  Capacitors stay on the net-name node (pin / label end).
- Dropped: substrate / n-well resistance to BULK terminals (bulk -> own source node if same net, else the net node), dangling branches.
  Kept: Metal1-5 (90 / 90 / 90 / 90 / 40 mohm/sq), via1-4 4.5 ohm/cut, contacts 6.3 (n) / 5.2 (p) / 8 (poly) ohm, gate poly 7.3 ohm/sq.
- Variants (mkvar.sh -> v/<var>/): c = staged C-only, rc = deliverable, r0 = R x1e-6, r10 = R x10, rcf = capacitors at the far terminal
  of each net, rcng = no resistance on gate-only nets.  cmp.py runs the owner's benches on a variant (own cache ac/, results res/<var>/).

## State
- 07:08 limits written.  07:14-07:19 rxselect extracted; 07:26 ctle extracted (116 Magic nets, 84 with resistors = every net with a
  device terminal except 5 poly-resistor series links sp_rl*_r*).  Deliverables built 07:30 (mkvar.sh, sha256.txt):
  ctle.rc.ext.spice 28cb832b... (315 devices, 1410 C verbatim, 3176 R of 3399 raw), rxselect.rc.ext.spice 9b94aeef... (14 / 63 / 127 of 136).
  One raw-vs-C-only difference: X8 (MOS capacitor, D = S = B = VSS) as/ps (C-only lumps the whole VSS diffusion on it; electrically nil).
- Check (a): by construction + verified against the raw extresist netlist device by device (nets, model, w, l, m): PASS both cells.
- Check (d) hand sums (typical: M1-4 90 mohm/sq, M5 40, via 4.5 ohm/cut; geometry from trace.py):
  * ctle load return cn_rl, 6 resistor feet -> 6 enable-switch drains: branches 21.9/6 + M4 1.6 um x 137.9 um (7.76) + Via4 3 cuts (1.5)
    + M5 0.9 um x 106.5 um (4.73) + Via4 (1.5) + M4 35.1 um (1.97) + branches 19.3/6 = 24.3 ohm; extresist 23.4 (+4 %).
  * ctle follower P sources -> CTLE_P pin: 8 M3 risers 0.4 x 30.7 um + single Via3 each (1.43) + pad/via2/contacts (0.56) + M4 1.9 um x
    105.5 um (5.00) + Via4 (0.75) + M5 1.5 um x 81.6 um (2.17) = 9.9 ohm; extresist 9.77 (+1.4 %).
  * ctle RX_P pin -> gate branch point: M5 0.44 um x 108.3 um (9.85) + single Via4 (4.5) + M4 0.40 um x 41.8 um (9.41) = 23.76;
    extresist segment 23.75.  Whole pin -> six gate stacks (metal + vias) 31.9 by hand, 30.6 extresist (+4 %).
  * rxselect RX_P pin -> first branch: 18.8 by hand, 18.69 extresist.
  All within the +-30 % declared.  Gate poly: extresist puts the gate terminal at mid-finger (223 ohm for the 16 um input finger =
  half of the 417 ohm end-to-end; a distributed gate contacted at one end is 1/3 = 139 ohm): gate-poly part is ~1.5x pessimistic.
- Resistance table: rtab.py -> rtab.json (see final report).  Largest metal terms: load return cn_rl / cp_rl 23.4 / 20.8 ohm in series with
  the 480 ohm loads (+ 8.1 ohm on cn / cp), follower source -> pin 9.8 / 10.8 ohm, tail drain -> pair source 12.6 / 9.6 ohm,
  RX pin -> gates 30.6 / 24.6 ohm metal (0.44 / 0.40 um wires, single vias), rxselect pass path 54 / 41 ohm of metal per leg.
- 07:44 first validation job (capacitors on the net-name node, variant now called rcb): ctle R x1e-6 within 0.019 dB of C-only (PASS);
  R x10 changes -7.7 ... -15 dB (control works).  R x1e-6 in the DIRECT bench: operating point did not converge (numerical, 1e-8 ohm
  elements) -> known answer for rxselect rerun at x1e-3 (variant r0m; the 0.1 dB limit is unchanged).
- FOUND: capacitor placement matters.  All C at the net-name node (rcb) vs all C at the farthest terminal (rcf, unphysical extreme:
  behind a single via stack / gate poly): 0.6-0.8 dB apart at 1.25-1.62 GHz (source nodes sp / atb_ctle_src carry 410-440 fF of
  wiring C that sets the peaking).  So mkrc.py cap=dist is now the deliverable: each C-only capacitor is spread over the resistor nodes
  of its nets in proportion to the per-node capacitance extresist assigned (totals per net pair conserved, checked).
  Deliverables REBUILT 07:52: ctle.rc.ext.spice d1d1ede5... (10024 C elements), rxselect.rc.ext.spice 99d68434... (sha256.txt).
- Bench note: the chain / block benches' I(VDD) is NOT usable for the 2 % current threshold (it contains the sampler bank at a
  metastable DC point: 10.5-21 mA depending on microvolts of offset).  The CTLE's own supply-pin current is measured with a 0 V
  source in cmp.py op and is what the threshold is judged on.
- 07:58 C-only chain rows rerun in my own cache (res/c): tt code 0 gdc -0.63 / g625 1.48 / g1g25 0.70 / g1g62 -1.36 dB, SL CM 0.457 V =
  the owner's chain_ac.json row (bench reproduced).  CTLE own supply current (C-only): tt 10.74, ss315 9.24, ss350 11.29, ff 11.53 mA.
- 08:12 validation of the DELIVERABLE netlists (valcmp.py -> valcmp.json; block benches, 1 MHz-8 GHz):
  (b) R x1e-3: ctle code 0 / 7 within 0.020 / 0.016 dB of C-only, rxselect direct within 0.003 dB -> PASS (limit 0.1 dB).
      R x1e-6 (as first declared): passed on the first build for ctle (0.019 dB) but the direct bench did not converge, and on the final
      build the ctle run did not finish in 220 s (killed, slot released): numerical only; x1e-3 is the recorded known answer.
  (c) R x10: -7.7 dB at 1 MHz, -13.8 dB at 1.25 GHz (ctle), -11.4 dB at 1.25 GHz (direct) -> the bench sees resistance: PASS.
  Capacitor placement: distributed (deliverable) vs all on the net-name node: 0.02 dB apart (the 0.6-0.8 dB of the far-terminal extreme
  is not physical).  Gate-poly hops zeroed (rcnp): within 0.05 dB of the deliverable -> the change is metal + vias, not gate poly.
  R+C vs C-only at block level (tt, 25 ohm source): code 0 -0.37 dB at 1 MHz, -0.20 at 625 MHz, -0.58 at 1.25 GHz, -0.82 at 1.62 GHz;
  SL CM +17 mV; direct/USB path -1.13 dB at 625 MHz, -1.92 dB at 1.25 GHz.  ABOVE the 0.3 dB / 10 mV report thresholds.
- 08:13 OWNER SCOPE CUT: deliverables 1 + 2, operating points and chain AC C-only vs R+C; transients / direct bench skipped.
- 08:19 job_lin.sh rc finished for all five corners, codes 0-7, picks and operating points (it had started before the cut).
  compare.py -> compare.out (tables), op_compare_rc.json; rtab.py -> rtab.out / rtab.json.  Nothing of mine is queued or running.

## Result (R+C vs C-only, same bench, both rerun here)
- Chain gain: -0.33 ... -0.50 dB at 20 MHz (code 0), -0.47 ... -0.92 dB at 1.25 GHz, -0.73 ... -1.08 dB at 1.62 GHz (five corners).
- SL common mode +13.5 ... +20.5 mV (tt 0.457 -> 0.474, ss315 0.406 -> 0.420, ss350 0.583 -> 0.596, ff 0.431 -> 0.452): inside 0.38-0.66.
- New static offset: SL P-N +4.7 ... +6.7 mV (C-only 0), from the P/N difference of the load-return and follower-output wires.
- CTLE supply current -1.6 ... -1.8 % (below the 2 % threshold).  Tail Vsd -45 ... -54 mV.
- Linear eye: -4 ... -19 %.  GATE CROSSED: ssp315 3.24 Gb/s T3 63.8 -> 52.8 mVppd (limit 60; its width 0.19 UI already missed C-only).
  Every other cell stays above 60 mVppd / 0.25 UI.
- Cause = metal + vias (gate-poly variant within 0.05 dB).  Largest terms: load return cn_rl / cp_rl 23.4 / 20.8 ohm, follower source ->
  pin 9.8 / 10.8 ohm, tail drain -> pair source 12.6 / 9.6 ohm, supply to tail sources 22-27 mV.

## NOT RUN
- Clocked transients (ideal clocks, ss315, 2.5 and 3.24 Gb/s T3), C-only and R+C: not run (scope cut).
- Direct / USB and bypass mode benches (ac10 modes) with R+C: not run (C-only rows exist in res/c/ac.json).  Only the block-level
  direct AC at tt exists for R+C (val bench: -1.13 dB at 625 MHz, -1.92 dB at 1.25 GHz against C-only).
- Attribution runs (job_attr.sh, variants v/a_*, v/x_* are built): not run.  The per-wire cause is from the resistance table only.
- Known answer at R x1e-6 on the final netlists: did not complete (see above); x1e-3 recorded instead.
- ssp350, sf, fs corners; high / low metal corner (extract style hrhc / lrhc); the pad metal bounds (R11_PAD=high|low).
- Extraction from the GDS read back (the .mag of stage/gen was extracted, as the staged C-only flow does); no netres.py 2-D solve.
- No independent review of this work.
