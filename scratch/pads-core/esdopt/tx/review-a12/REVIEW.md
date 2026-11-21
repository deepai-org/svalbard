# Review a12: pad_txpad (delta review against review-a11)

Reviewer verdict for PUBLICATION: **GO with conditions.**

a12 closes the pads-side a11 conditions (2), (3) and (5). I accept the HBM 1 kV vdd+ bound (4). Nothing regressed. I found one EM issue that the a11 review and earlier reviews did not raise. It is older than a12, not a regression, and is the same class as a11 F2: single-cut vias and 0.4 um Metal2 in the termination trim legs (F1). Condition (1), the wired TX interface, is outside this review.

Reviewed GDS: `sec/b/a12/pad_txpad.gds`, sha256 4fbb84f41e9837051f3145f3504bd00cf0bc9272ddbc07fa80a3f75166562219 (recomputed here; matches STATUS, `sec/r12/res.json` and `sec/checks/a12/lu.json`).
Simulations run in this review: none. Every number below comes from the a12 json, recomputed by me. The one build I ran was the default-path layout rebuild.

## Findings

1. **MEDIUM (EM; pre-existing, new finding): the termination trim-leg straps TU_{P,N}_T0/T1/T2 carry DC common-mode current through single V2 cuts and 0.4 um Metal2.**
   - Source: netres `sec/r12/res.json`, nets TU_P_T0/T1/T2 (and their N mirrors), path `nmos:TERM_VCM_BUS|res:`, high metal.
     - T0: 2 single V2 cuts, each at fraction 1.0 (x 105.02 / 110.62, y 384.67).
     - T1: a single V2 cut at fraction 1.0 (x 100.88, y 383.77).
     - T0 and T1: max run density 2.5 /um.
     - T2: 1.25 /um (0.4 um M2). It has no single cuts.
   - Every unit is the same (ppolyf_u 2 x 2.2 plus one nvt switch), so a leg carries (its units) / (8 + code) of the pad current.
   - At the CM bench's 10.5 mA per pad:
     - ff code 3: T1 carries 2/11 x 10.5 = 1.9 mA through one cut. That is 3.3x the 0.58 mA/cut rating and about 4.8 mA/um in M2 against 2.09. T0 carries 0.95 mA: 1.6x per cut, 2.4 mA/um.
     - ss code 13: T2 carries 2.0 mA, which is 2.5 mA/um (1.2x).
     - ss code 15: T1 carries 0.91 mA per cut (1.6x).
   - Even at a data-averaged 5 mA per pad, the T1 cut stays at about 1.6x.
   - Why nobody saw it: the CM bench runs code 8, which enables T3 only, and T3 has no flag. No limit row covers these nets.
   - Condition: give the T0/T1/T2 straps at least 2 V2 cuts and widen the M2 to 2.5 um or more, or stack M3. Then rerun netres on these nets. The other option is an explicit acceptance ruling, as was done for a11 F2.
2. **Closed, condition (2) TERM_DISCHARGE EM.**
   - The extracted and LVS netlists both show `X22 TERM_VCM VSS ppolyf_u_1k w=2u l=20u`.
   - The cmdrop json gives I_dis at 0 mA: ss 0.135, tt 0.160 mA (ff 0.199 per STATUS).
   - Single cut at fraction 1.0: 0.20 mA against 0.58. M1 0.38 um x 2.5 /um gives 0.50 mA/um against 2.09. PASS.
   - Remaining: the size now differs from the circuits.wired_transmit TERM_DISCHARGE (2 x 2). Wired TX must acknowledge it. The discharge time constant grows about 10x. This is an interface item.
3. **Closed with a correction, condition (3) bus EM.**
   - My recomputed peak over all TERM_VCM -> TU_* paths is **0.065 /um** (high metal, to TU_P_T0, 11 um M3). STATUS says 0.0529.
   - 0.065 x 21 mA = 1.37 mA/um against 2.09, a **34 % margin**. That still meets the 25 % asked for.
   - The pin side is 0.0209 /um. Single cuts on the bus paths: 0. PASS.
4. **Closed, condition (5) latch-up.** `sec/checks/a12/lu.json` names the a12 GDS. 0.0 um2 uncovered at 15 um (1411.99 / 502.19 at 5 / 10 um, the same as a11). PASS.
5. **Accepted, condition (4): the HBM 1 kV vdd+ bound.** Reasons:
   - (a) The transient failure is numerical. Every attempt stops at 0.25-0.26 V with no current flowing, at the turn-on of the pad's own up-diode. It is not a device failure.
   - (b) The `dcs` json (model sha matches) reaches 0.650 A, 97.5 % of peak, with no decap credit:
     - MOS <= 1.85 V against 8.0 V.
     - n03 0.36 V against 5.0 V.
     - Primary forward 1.62 mA/um against 10.
     - The extrapolation to 0.667 A is about 1.9 V, along the up-diode's steep forward curve. The remaining 2.5 % cannot close the 4x margin.
   - (c) The dynamic overshoot on the same path is covered by CDM 2 A vdd+ on a12. It completed at 3x the current with ns edges: MOS 3.92 V, pad 5.02 V.
   - Note: the `dcs` json shows `prim_pass: false`. The cause is the energy term (3.9e7 nJ), which integrates a DC sweep as if it were time. It is meaningless for `dcs`, not a failure. Tools should skip the energy check for kind `dcs`.
   - Recorded as BOUNDED, not simulated. A converged transient stays desirable but is not required for publication.
6. **INFO: no regressions** (table below). Every a12 json model_sha256 matches the current file: a12_rh 9a37c571, a12_rt 81504b3d, a12_c cfa58f05. esdka matches its cell model.
   - Rebuilt here: the default path `tx_pad_layout.py review-a12/dflt`. Its GDS, normalised (timestamps zeroed, `gdsnorm.py`), is 3a706943, identical to b/a4. The schematic is byte-identical. The .mag differs only in its header timestamp.

## Limit table (a12, values recomputed from json or rebuilt)

| Limit | a12 | Result |
|---|---|---|
| Termination +-10 %, 23 corners, rt / rh | 23 / 23 corners; worst 4.24 / 4.19 % (best code 3..13 rt) | PASS |
| Termination off | >= 1.46e10 ohm (diff) | PASS |
| Pad C <= 3.223 pF (100 MHz) | rt 3.081, c 2.992 | PASS |
| Gate C | max 0.2994 pF | PASS |
| CM1 <= 5 ohm (ss/3.15/32, rh) | 70.2 mV / 21 mA = 3.34 ohm | PASS |
| Off-leak, TERM_VCM 0 / 1.65 V | 0.00 uA equal pads; <= 0.16 uA with pads 1 V apart | PASS |
| Drop at 21 mA | 53.9 mV | PASS |
| CDM 2 A, 6 V devices <= 8.0 V | vss+ 6.92, vdd+ 3.92, vdd- 0.99, pp+ 7.27, pp- 7.26, vss- 0.99 (tanh); n03 <= 0.84 V; all complete | PASS |
| HBM 1 kV vss+/vss-/vdd-/pp+/pp- | <= 4.35 V (6 V), n03 <= 0.70 V, all complete | PASS |
| HBM 1 kV vdd+ | DC bound 1.85 V at 97.5 % peak; CDM same path 3.92 V | BOUNDED, accepted (F5) |
| Junctions (primary reverse) | <= 7.15 V (CDM pp), all prim_pass | PASS |
| EM discharge path | 0.20 mA/cut (0.58), 0.50 mA/um (2.09) | PASS |
| EM TERM_VCM bus | 1.37 mA/um at 21 mA (2.09), 34 % margin | PASS |
| EM trim legs TU_*_T0/T1/T2 (no declared limit) | up to 1.9 mA per single cut, about 4.8 mA/um M2 | **OVER (F1)** |
| Magic DRC / KLayout DRC / LVS | per progress: kldrc rc 0, rb_pos match, rb_neg control mismatch (expected) | PASS |
| rail_site_check | RAIL-SITE txpad_a12 PASS, main 0, antenna 0 | PASS |
| Latch-up | 0.0 um2 at 15 um, sha-traceable | PASS |
| Default rebuild == a4 | normalised 3a706943 == b/a4 (rebuilt here) | PASS |

## Conditions for publication

- C1 (F1): fix or explicitly accept the trim-leg strap EM, then rerun netres on TU_* nets.
- C2: wired TX acknowledges the TERM_DISCHARGE size change (2 x 20 um) and the about 10x longer discharge time constant (interface, alongside a11 condition 1).
- STATUS should correct the bus peak to 0.065 /um, a 34 % margin.
