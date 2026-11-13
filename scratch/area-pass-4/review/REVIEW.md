# PD-AP4 review: stacked `pad_hspad` (492 x 912.91 um)

Independent reviewer, 2026-11-13. Candidate `scratch/area-pass-4/hspad-stacked/pad_hspad.gds` (sha 32af9d31...),
model `physical.spice` (sha 3cfcc9e0...). Reviewer reruns are in this folder.

## Verdict: GO with conditions

The cell is correct: DRC, LVS, P/N polarity and the RX path all check out. The area gain (-0.088 mm2 of core) is
real. Conditions 1-3 below must be met before it replaces the published cell. Conditions 4-5 can follow publication.

## What I reran
| Check | Result |
|---|---|
| Magic extract + DRC on the final GDS (pad image) | HS_DRC 0 (`lvs/extract.log`) |
| netgen LVS vs the hs_reference netlist | Circuits match uniquely, no property errors (`lvs/lvs.txt`) |
| Negative control: RX_P/RX_N labels swapped | LVS fails (`lvsneg/lvs.txt`), so the polarity is really checked |
| KLayout precheck (kl_block_drc.py, variant D, deep) on the final GDS | main 0 / antenna 0, sha 32af9d31 (`kldrc/pad_hspad/kldrc.json`) |
| LU audit (pads-lu01 lu_audit.py) on the final GDS | 0 um2 uncovered at 15 um, NMOS and PMOS (`lu-final.json`) |
| Geometry/labels (KLayout, `geo.py`) | bbox (-0.055,0)-(492,912.91). Ring band (y<426): M2/M3/M4 identical to published. M5 grows only from x<=294 to x<=339 (the PAD_P strap at y 414-418). Nothing at x>478 in the band. |
| RX path bench (hs_bench.py rxpath), published vs candidate | RX/PAD at 1.25-2.4 GHz: tt -0.297 -> -0.326 dB; ss -0.271 -> -0.297 dB; ff -0.329 -> -0.361 dB. HPF corner and op points identical (`rx-*-rxpath.json`). |
| Per-leg P vs N C, from the designer's ap4pub/ap4new3 AC data | tt CP/CN 1136/1123 -> 1158/1139 fF. P-N 13.3 -> 19.0 fF at every corner (same delta at ss/ff) |

The safe/HBM json (`ap4-hspad-safe-hbm.json`) and the ap4new3 AC run both point at the final model sha 3cfcc9e0. Both are valid.

## Findings
1. **[Condition] The designer's KLayout precheck record is stale.** `scratch/area-pass-4/kldrc/pad_hspad/kldrc.json` has
   gds_sha256 fc928a2f..., which is the **v1** GDS (`hspad-stacked-v1`), not the final build. The final GDS was written
   at 08:55:57, after the kldrc record (08:53:56) and `lu-stacked.json` (08:54:04). My reruns on the final GDS are
   clean, so the result stands, but the publish must carry a record whose sha matches the final GDS (`kl_block_drc.py --publish`).
   Otherwise check_block_kldrc.py reports STALE. Also regenerate the LU evidence from the final GDS. My
   `lu-final.json` gives the same 0 result.
2. **[Condition] RX pins moved from the core edge to the side edge and are now 188 um apart.** Published pins:
   RX_P (290.5, 1110.25) and RX_N (320.5, 1110.25), 30 um apart on the core-facing edge. Candidate pins: RX_P
   (491.5, 623.75) and RX_N (491.5, 811.75), on the side edge. With the mirrored east placement (rect y 735.055-1227.055),
   both pins land on the cell's south edge at chip y ≈ 735, with RX_N 188 um deeper into the die than RX_P. In S1 the
   `detect` block sits 20 um south of that edge (y ≤ 715.26), and the CTLE is ~250-550 um west. In S3 the CTLE is at (470, 3800).
   The cell itself is balanced (extracted RX C 76.4/75.4 fF). But a straightforward chip route adds ~188 um of
   extra length on RX_N. That is ~20-40 fF of imbalance on the high-Z CTLE input, the same size as the +38 fF that
   got v1 rejected. The imbalance just moves from the cell to the chip. `floorplan.py` PORT_LABEL['hspad'] = 'RX_P'
   ("deepest label") models only one pin. Required: (a) the floorplan/assembly accounts for side-edge pins, a south
   routing channel, and both pins; (b) the chip RX_P/RX_N routes are length/C matched (≤ 5 fF), or
   the extracted chip-level imbalance is shown to be acceptable for the CTLE. If (b) can't be met at chip level, put
   the RX pins next to each other in the cell (e.g. bring RX_P up to the channel above the N leg) before publishing.
3. **[Condition] PD48c evidence must be rerun on the new model or explicitly waived.** The 1 kV HBM rerun and the
   CDM-speed surrogate (`scratch/pads-pd48c/cdm.py`: 6.98 V at 2 A, limit 8.0 V) were done on the PD21 netlist. The
   shell is unchanged and the 2 kV HBM result is identical, so I expect ≤ 0.1 V change. The PD48c section and the
   B40 COB RL table (`rl_fix_pd48c.json`) quote hspad C and RL values that now shift by ~+0.02 pF/leg, so they need
   either a rerun or a dated supersede note.
4. **[Info/OK] Ring band.** Local y 414-418 maps to die depth 440-444. That is outside the VDD ring (411-436 depth,
   M3/M4 east/west) and outside the 3 um foreign-metal cut sizing, because kl_assemble's `foreign` set only looks at
   M2-M4, so M5 cuts nothing. No chip-level M5 is generated in that band (the pdn M5 is only island/decap straps).
   M2/M3/M4 in the band are unchanged, so ring fragmentation is unchanged. Acceptable.
5. **[Info] Electrical deltas are within the budget.** Pad C: 1.15 pF/leg tt and 1.19 pF ss, against the 2.8 pF limit in
   design-assumptions (wired RX pad+ESD C). Die RL at 2.4 GHz: tt 8.19 -> 8.03 dB (ac-new2; ap4new3 8.07), ss 7.14 -> 7.0 dB. The
   ss value was already below the README's "8.0-8.5" wording, so update the README range. P/N pad imbalance
   13.3 -> 19.0 fF (1.7 % of leg C), which is about -49 dB mode conversion at 2.4 GHz. That is negligible, but it is
   +5.7 fF worse than published, because the PAD_P route is now longer (≈45 um + 79 um of 4 um M5) than the PAD_N strap (≈41 um).
   The RX-path MIM loss gets 0.03 dB worse.
6. **[Info/OK] EM of the 4 um M5 PAD straps.** The width is the same as the published straps. Under HBM these straps
   carry only the leg's current (MIM displacement ~ 4.9 pF·dV/dt, a few mA; termination switches unpowered/off). The
   amp-level HBM current flows in the shell's unchanged 12 um trunks into the protection, so it does not cross the
   new straps. No concern. If the termination is enabled during a powered event, 5.4 V/24 Ω ≈ 0.22 A (55 mA/um) for
   ~150 ns, which is still well inside short-pulse M5 capability.
7. **[Minor] Code comments.** In `assemble_stacked`, the variable `YN` (= 440) holds the **P** leg and `YP` (= 628) the **N** leg.
   The behaviour is correct (LVS plus the swap negative control prove it), but the names invert the meaning. Rename them before publishing
   so a later edit doesn't swap polarity by mistake. Also, `ltop_x = 152` is hard-coded rather than read from the
   leg bbox.

## Not checked
PEX-level P/N cross-coupling beyond what Magic extraction plus the AC bench capture. Power-up bench (not
expected to change: same devices and nets).
