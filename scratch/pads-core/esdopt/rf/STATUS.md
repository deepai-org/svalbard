# esdopt/rf: pad_rf_pair, pad_rftxpad, pad_single_leg under ESD option A. NOT committed, NOT published.
Started 2026-11-21. Brief: rebuild the three rf-shell families to reviewable option-A candidates (pt_rf precheck: 905 of 1155
DRC errors are the SO-1 Via3/Via4 ring stacks of these cells). Order: rf_pair (RF_RX, BB_I, BB_Q, WTX_EXT), single_leg (WMON), rftxpad (RF_TX).

## Network input (stated before any build)
`protection_pad_ss.py` cannot regenerate the network (its input `scratch/pads-pd12/v2/macro/` is deleted; pins/STATUS.md).
Not regenerated. The candidates are built by post-processing the pin-move variants `../pins/b/<family>.gds` (published cell
+ top-edge pins, removed area 0 on every layer), i.e. the published network geometry is REUSED unchanged as the
core-side secondary (core diode array to the pad-local ESD_RAIL with its RC clamp, behind the Metal2 neck + route).

## Pass limits (declared 2026-11-21 before any run; not to be moved)
Layout
- Magic DRC 0 (flattened). Read-back LVS from the GDS on disk "match uniquely" against a reference = published reference +
  site diodes; failing controls: one site diode removed from the reference; PAD_P<->PAD_N label swap (pairs).
- KLayout precheck (`verification/kl_block_drc.py`) main 0 / antenna 0, with a failing control (copy + Metal1 sliver).
- `rail_site_check.py` PASS on the candidate (pad on the provider rail cells) and its `--selftest` OK.
- Latch-up audit 0 um2 uncovered at 15 um.
- Floating lines (`**FLOATING` in the Magic extraction) not more than the published cell.
- Outline and top-edge pins (Metal4/5, incl. ESD_RAIL, VSS) as the pin-move variant; new port DVDD only as a ring landing (Metal3 under the
  rail cell's DVDD band), stated. rftxpad: no DVDD port (no up-diode to the supply).
ESD (bench = `../ring/esd3.py` copied here, ring bound RN 0.155 / 0.189, RF 0.46 / 0.57 ohm, far 5 dvdd + 7 dvss, SITECAP 1 nF / 0.7 ohm per rail)
- Model: lumped R + C: Magic C (cthresh 0, no extresist) of the composed cell; R from `../../hsfix/netres.py` for bond -> site rows,
  landings -> site diodes, and the neck/route to the core network; return side (landings, ring) in the model. Typical and high metal.
- Judged at the devices: no 6 V MOS gate over 8.0 V transient, no 3.3 V over 5.0 V; junction reverse below the model bv (nd2ps 11 V,
  pd2nw 10.5 V); MIM <= 6 V (none in these cells: stated); primary diodes <= 10 mA/um forward, <= 1 mA/um in avalanche.
- HBM 2 kV (rf_pair, single_leg), 1 kV (rftxpad); all cases P/N +/- vs VSS, vs VDD, P vs N. CDM 2 A (1 ns surrogate) with
  1 nF / 0.7 ohm decap per rail (SITECAP); 1 A / 3 A reported. Bond-pad voltage reported (information).
- Controls before the real runs: toy 2 ohm known answer (2.781 V at 2 kV); site diodes stripped must fail.
C (per leg, Magic cthresh 0, typ, with the rail cell over each site = under-rail term included)
- rf_pair: <= published (same method, same rail cells) + 0.3 pF limit; + 0.1 pF reported as "wanted" (RF_RX). single_leg, rftxpad: <= published + 0.3 pF.
- P/N imbalance reported.
RF_RX
- Series R bond pad -> network/LNA port (PAD_P Metal5 top pin) typ / high reported. S11: only if a bench exists (else "not run").
Not judged here: the LNA / BB / WTX_EXT consumers' own inputs (not in the pad cell).

## Log
- 2026-11-21 Composer `rf_compose.py` (KLayout, post-processes ../pins/b/<family>.gds): deletes the ring-stack Via3/Via4/M4/M5 (38 shapes per site),
  optional `pin_vias` (the single Via4 at the PAD trunk -> top-pin hand-over, (288,416) / (304,432), replaced by a 256-cut array: bond -> PAD pin 13.3 -> 8.7 ohm typ, 27.7 -> 12.6 high),
  then pad_site_primary.draw per site (neck 25.5-49.5, VSS strip 6-14), DVDD label on the landing. Build: `./build.sh <family> <name> '<opt json>'`; checks: `./chk.sh` (summary in chk/<name>/summary.txt, LVS verdict chk/<name>/rbx/verdict).
- Generator `pad_site_primary.py` options added, defaults unchanged (rebuilt r2 XOR 0 after each): `no_up_row` (rftxpad), `n_dn_left` (down finger left of the neck).
- r1 (3 dn + 3+1 up): DRC 0, LVS, precheck, rail PASS. Superseded by r2 (+pin_vias): all layout PASS. ESD r2 (`esd/r2{t,h}.json`): HBM all fine; CDM 2 A high: site pd2nw reverse 11.42 V > bv 10.5 (MISS) -> r3.
- Controls: toy 2 ohm 2.899 V = (2 + 0.189 ring) x 1.3243 A, PASS; site stripped (r2h) P+VSS 164 V, fails as required.
- r3 = r2 + `n_dn_left` 1 (4 dn + 4 up per leg): all layout checks PASS, GDS sent to the coordinator 2026-11-22 (baseline).
- s2 (single_leg, 4 dn + 4 up) and t2 (rftxpad, 4 dn, no up row, no DVDD) both pass every layout check and were sent to the coordinator 2026-11-22. t1 / s1 (3 dn) superseded.
- r3 / s2 / t2 are STAGED for assembly: do not delete or overwrite b/r3.gds, b/s2.gds, b/t2.gds until each family is published.

## rftxpad positive-zap fix: diagnosis (2026-11-24, before any layout)
Published t2 (high metal, bound ring, 1 nF site decap): P+VSS HBM 1 kV pad 13.9 V, CDM 2 A 18.1 V; the 4 site down-diodes
avalanche at 9.15 mA/um (CDM 2 A, 474 mA each, `esd/cur_t2_cdm2.json`) and 5.95 mA/um (HBM 2 kV) against the 1 mA/um
limit: a real 6-9x miss, not a model artefact. The positive path through the shell's core network is resistive in three
places (lumped model: bond -> core diodes 62 ohm, core diodes -> ESD_RAIL 34 ohm, network VSS -> VSS 51 ohm).
What-ifs on the model (`wi/`, P+VSS, pad / site reverse):
  a published 13.9 / 18.1 V; b core 2 ohm 13.7 / 17.9; c ESD_RAIL 1 ohm 13.8 / 18.1; f VSS 0.5 ohm 13.8 / 18.0;
  e core 1 + rail 0.5 13.5 / 17.5; g core 1 + rail 0.5 + VSS 0.5: HBM 1 kV 5.8 V (pass), CDM 2 A 12.8 V (still > 11).
=> Re-routing the shell is not enough: the shell's rail clamp cannot take CDM 2 A even with ideal wiring.
Fix to build: local positive path in each site: pd2nw up-diodes PAD -> local rail XR (not the supply: RF_TX swings
~0.8 V above VDD, PC-31) + an RC-triggered nfet_06v0 clamp XR -> VSS in the freed up-row area and between the two sites
(PC-31 estimate ~8 mm, ~74 % of two sites for 2 kV; target here: pad <= 10 V at CDM 2 A high metal, avalanche 0).
XR charges to the RF peak and stays DC, so the RC trigger does not fire in operation. Costs to declare to rf_tx: added
pad C (up-diode junction + rail), leakage at the RF peak. Diode-stack-to-supply rejected: rf_pair's single up-diode already
reaches 10.9 V at CDM 2 A; a 2-3 stack doubles / triples that drop.
