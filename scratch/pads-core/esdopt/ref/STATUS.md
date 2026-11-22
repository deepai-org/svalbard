# esdopt/ref: pad_refpad (REF_IN / REF_IN_N, AUX_CLK pairs, both chips) under ESD option A. NOT committed, NOT published.
Started 2026-11-22. Brief: baseline-first (MANDATE 1, 4a): option-A cell clean (DRC / LVS / precheck / rail_site_check, core pins on the top
edge) fast, report GDS, then ESD and C evidence, misses recorded (no margin iteration).
Rules: ONE simulation at a time, OMP_NUM_THREADS=1; generator edits only behind options whose default rebuilds the published cell
(XOR 0 vs `$P/analog/pads/generated/stress-safe-families/reference/combined.gds` sha ae893110..., and the USB default vs the published wirepad);
intermediates deleted; no commits.

## Pass limits (declared 2026-11-22 before any run; not to be moved)
Layout
- L1 Magic DRC 0. L2 read-back LVS (GDS from disk, flattened) "match uniquely" vs the generator schematic AND a failing control (PAD_P/PAD_N
  label swap -> mismatch, verdict parsed from output). L3 KLayout precheck main 0 / antenna 0. L4 latch-up 0 um2 uncovered at 15 um.
- L5 `rail_site_check.py` PASS (and --selftest OK).
- L6 core pins (VCM, VSS, ATB_ESD_RAIL if still bound, PAD_P/N access) on the top edge.
- L7 default paths: reference_clock with no new option XOR 0 vs published reference combined.gds; wired_receive_usb default XOR 0 vs published USB.
- L8 outline inside the published bbox; ports as published plus any ring port, stated.
ESD (R+C model of the exact GDS, ring at the bound of ../ring/esd3.py, SITECAP 1 nF at the east-edge site behind 0.7 ohm per rail; typ and high metal)
- E1 every MOS max(|Vg-x|,|Vds|) <= 8.0 V (6 V) / 5.0 V (3.3 V) transient. E2 non-primary junctions reverse < model bv. E3 primary site
  fingers <= 10 mA/um fwd, <= 1 mA/um avalanche. E4 MIM <= 6.0 V. Points: HBM 2 kV, CDM 2 A 1 ns with SITECAP. Known-answer + stripped-site control.
Functional
- F1 pad C per leg (R+C, full-coverage extraction, no extresist C) <= published (same bench) + 0.3 pF; reported at 2.45 GHz with series R
  (external LO path on pt_rf).

## Log
- L7 reference default: `build.sh <n> network-gc` (= stress_safe_compact_layout.py reference_clock <w> .../network-gc) -> XOR 0.0 um2 vs published pad_refpad (network-gc-d2 gives 5229 um2, network 196629: not the published path).
- a1 build: `build.sh a1 network-gc '--esd-a={"site": {"n_up_left": 3}, "tb": {"top_pins": true}}'` (layout.py usb_term_block term_block=False path; generator Magic DRC 0, generator LVS match, 42 devices = 16 + 2 x 13 site diodes). Ports PAD_P PAD_N VSS VCM DVDD (ATB_ESD_RAIL gone with the network). Top pins: PAD_P/N Metal5 at y 911.94, VSS/VCM Metal4 911.19-912.91. bbox (2.78,0)-(285,912.91) inside published (..404). checks.sh a1 running.
- Generator edits (all behind options, defaults unchanged; L7 rerun pending): layout.py `usb_term_block` key `term_block` (default True; False =
  no termination block / links / height, only the site clearing, neck width and top_pins; required for reference_clock), RX_P/RX_N top-pin
  endpoints only if the nets exist, top pins at `port_top_um` when the cell has boundary ports (else at the cell height as before);
  wired_protection_layout_ss.py assemble_esd_a: block-band regions only when term_block; stress_safe_compact_layout.py: --esd-a accepted for
  reference_clock (keys tb / site; tb gets term_block False).
- a1 checks (checks.sh; first run died after rail_site_check when checks.sh was edited in place - remainder rerun by checks_tail.sh):
  rb_pos match, rb_sch match; control "PAD_P/PAD_N label swap" MATCHED (circuit is P/N symmetric: not a valid control) -> replaced by a
  VCM/VSS label swap control (pending); control "one site diode missing in reference" mismatch (valid). kldrc sliver control reports; lu
  control 6.4 um2; rail_site_check ref_a1 PASS (main 0 / antenna 0).
- a1 checks complete: rail_site_check selftest OK; KLayout precheck main 0 / antenna 0 (cell) and 0 / 0 pad-on-rail; latch-up 0.0 um2 at 15 um;
  railconn clean (DVDD only on DVDD bands); floating lines 0. VCM/VSS label-swap control: mismatch (valid failing control).
- L7 rerun at the final generator shas (layout.py ffe71882, wired_protection_layout_ss.py b2e89345, stress_safe_compact_layout.py 0c0f8b61,
  pad_site_primary.py 2bca0b81 = another agent's edit, not mine): reference default XOR 0.0 um2 vs published pad_refpad; USB default
  (wired_receive_usb network-gc-d2 usbfix6v2lsm 14) XOR 0.0 um2 vs published pad_wirepad. Builds deleted.

## BASELINE a1 (2026-11-22). NOT published, NOT committed. Reported to the coordinator.
GDS `scratch/pads-core/esdopt/ref/build/a1/pad/combined.gds`, top `tx_with_primary` (rename to pad_refpad on publish), sha256
a37db1423bbf2115d694f61236935002407a68470900d3359e61ec1b89a612d5. Ports PAD_P PAD_N VSS VCM DVDD (ATB_ESD_RAIL removed with the network).
Command: `build.sh a1 network-gc '--esd-a={"site": {"n_up_left": 3}, "tb": {"top_pins": true}}'`; checks `checks.sh a1` (+ checks_tail.sh).
Evidence queue: q_pub.sh (published R+C + rail), q.sh a1 (R+C models, ESD, pad C).

| Limit | a1 | Result |
|---|---|---|
| L1 Magic DRC (generator, combined) | 0 | PASS |
| L2 read-back LVS (flat GDS from disk) vs generator schematic / vs composer reference | match / match (42 devices) | PASS |
| L2 controls: VCM/VSS label swap; one site diode missing in the reference; (PAD_P/N swap) | mismatch; mismatch; (match: symmetric, not a control) | PASS |
| L3 KLayout precheck main / antenna (cell; pad-on-rail); sliver control | 0 / 0 (0 / 0); control reports | PASS |
| L4 latch-up uncovered at 15 um; isolated-nmos control | 0.0 um2; 6.4 um2 | PASS |
| L5 rail_site_check / --selftest / railconn | PASS / OK / clean (DVDD only on DVDD bands) | PASS |
| L6 core pins on the top edge | PAD_P / PAD_N Metal5 trunk pins at y 911.94 (published boundary pins), VCM Metal4 x 27.22-27.66 / VSS Metal4 x 28.66-36.66, y 911.19-912.91; ATB_ESD_RAIL gone (no network); DVDD = ring landings (Metal3 y 141.4, both sites) | PASS |
| L7 default paths XOR (final generator shas) | reference 0.0 um2; USB 0.0 um2 | PASS |
| L8 outline / ports | bbox (2.78, 0)-(285, 912.91) inside published (.. 404); ports PAD_P PAD_N VSS VCM DVDD (ATB_ESD_RAIL removed, DVDD added) | PASS (port change stated) |
| floating lines | 0 | info |
- Evidence setup (2026-11-22): rflow.sh (mkspec / fixspec site islands / hsfix netres on PAD_P, PAD_N; no extresist), mkmodel.py (= usb
  mkmodel_usb.py), mkrail.py (under-rail C from the checks' railcap extraction: a1 CRAIL 198.8 fF / leg, published 91.2 fF), esd_ref.py
  (= usb esd_usb.py; no MOS in this cell, so every run reports pad - local VSS and pad - core supply), padc_ref.py (new: AC Y at the
  bond node, C, series R and C at 1 and 2.45 GHz, tt / ss / ff 27 C, DVDD 3.3 V, VCM 1.65 V, other pad AC ground).
  R coverage: PAD_P / PAD_N fully traced from the bond opening to every device terminal (site diodes, bias poly heads) + 4 site islands;
  VCM / VSS / BIAS nets C-only (behind 100 kohm poly / ring). The top-edge core pin is not a model terminal (bond->core-pin R not modelled).
- Consumers on PAD_P/N (read from the generated netlists): pt_diff_clk_rx INP/INN = MIM (cap_mim_2f0 10x10) + nfet_06v0 W20/L0.7 drain
  (body VSS); pt_lo_ext EXT_x = MIM + nfet_06v0 W10/L0.7. So the exposure judged is pad - local VSS against 8.0 V (6 V devices) and,
  conservatively (far plate assumed at VSS), against MIM 6.0 V. pad - core VDD is reported (no consumer device spans pad-VDD; the
  model's core supply is the ring supply behind 1 ohm, the real consumer supply is PLL_VDD).
- Bench proofs: 2 ohm toy HBM 2 kV 2.899 V (hand 2.899), CDM 2 A 4.378 V (hand 4.378). Sites stripped (high model): HBM 2 kV pad 86.5 kV,
  CDM 2 A 10.6 kV (control fails as it must).

### a1 evidence (q.sh a1, q_pub.sh; models models/a1_r_{typ,high}[_rail].spice, published models/pub_r_{typ,high}_rail.spice)
| Limit | a1 | Result |
|---|---|---|
| E1 HBM 2 kV (10 cases) pad - local VSS, high / typ metal (6 V consumers <= 8.0 V) | 6.32 / 5.69 V (P+N); pad - core VDD 6.00 / 5.47 | PASS vs 8.0 V |
| E1 CDM 2 A + SITECAP 1 nF / 0.7 ohm, pad - local VSS, high / typ | **8.73 / 7.78 V** (P+N; P+VSS 8.57 high); pad - core VDD 9.11 / 8.30 (P-VDD) | **MISS high metal** (0.73 V over); typ PASS 0.22 V margin |
| E4 MIM 6.0 V (no MIM in the cell; consumer MIM pad plate vs far plate assumed at VSS, conservative) | HBM 2 kV 6.32 V high / 5.69 typ; CDM 2 A 8.73 / 7.78 | **MISS (conservative bound)**: consumer-side MIM stress not simulated |
| E2 non-primary junction reverse < bv | none in cell (0.0 V) | PASS |
| E3 site fingers fwd <= 10 / aval <= 1 mA/um | HBM 2 kV 5.14 / 0.014; CDM 2 A 7.77 / 0.066 (3 A: 11.65 / 0.47 report) | PASS |
| CDM 1 A / 3 A, HBM 1 kV (report, high) | pad-VSS 5.54 / 11.83 V; 4.43 V | report |
| Bench proofs | toy 2 ohm 2.899 V / 4.378 V = hand; sites stripped 86.5 kV / 10.6 kV | PASS |
| F1 pad C per leg at 1 GHz, R+C + rail, vs published same bench + 0.3 pF (tt/ss/ff, typ / high) | 0.870-0.938 pF vs published 0.702-0.780; delta +0.148 .. +0.177 pF | PASS (0.12 pF margin) |
| F1 read-out control CTEST 100 fF on P | +0.100 pF on P, 0.000 on N | PASS |
| F1 at 2.45 GHz (external LO, report): C / series R at the bond node | 0.867-0.936 pF, 0.32-0.47 ohm (published 0.697-0.777 pF, 2.3-4.9 ohm: its array diodes sit behind ~25 ohm of metal) | report |
| Bond -> top-edge core pin metal R (netres, rpin/, report) | PAD_P 14.6 / 29.2 ohm, PAD_N 17.8 / 32.9 ohm typ / high (published 18.8 / 34.0, 22.1 / 37.9) | report |
| context | C-only published 0.61-0.69 pF; under-rail term a1 199 fF / leg (published 91) = most of the C delta | info |

Misses: (1) CDM 2 A high metal: pad - local VSS 8.73 V > 8.0 V at the 6 V consumers (diff_clk_rx / lo_ext nfet_06v0 drains); typ 7.78 V passes.
(2) Consumer MIM (6 V) bound exceeded if its far plate stays at VSS (HBM 6.32 V, CDM 8.73 V) - not simulated with the real consumer.
Levers (not tried, baseline-first): local secondary (series R + small down/up diodes before the core pin; the 14.6-17.8 ohm trunk is already
a series element), more down-row fingers (n_dn_left, as rf-shell), wider neck / Metal1 in parallel.
Not run: consumer cells in the ESD bench (diff_clk_rx / lo_ext extracted netlists), ss / ff / hot device corners in ESD, low-metal corner,
x0.01 self-check model run (models/a1_zero.spice built, not simulated), external-LO amplitude / lo_ext_pad.py rerun with the new pad,
P-N differential stress at the consumers (HBM P+N pad-to-pad 10.5 V), VCM bias-path checks (poly unchanged), EM of the site paths.
