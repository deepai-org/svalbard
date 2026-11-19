# Independent review: pad_hspad candidate a4 (site primaries, option A)

Reviewer: independent agent, 2026-11-19. Object: `build/a4/pad_hspad.gds`, sha256 `286715686f0c...f19001`
(confirmed from disk, and again by `rail_site_check.py`, `railsite/a4/site.json`).
Numbers below were recomputed from the result JSONs (not from logs or tables). Two ESD cases were rerun here, one at a time.
I formed the verdict before reading STATUS.md beyond "Pass limits". After that I compared: the designer's FINAL block reports the same misses.

## Verdict: NO-GO against the declared limits

Three declared limits are missed and one is missed by a hair:
- 2 kV HBM pad-to-pad: 9.61 V typ / 11.10 V high vs 8.0 V.
- CDM surrogate at every amplitude, with 25 6 V gates over the 8.0 V transient limit.
- Pad capacitance including the under-rail term: 1.30-1.32 pF vs 1.15 pF.
- Single-code termination with low metal: 79.9 ohm vs 80 ohm.

The layout evidence itself is sound: it is on the exact GDS, and its controls fail when they should.
The layout and RF numbers are as good as f6 or better, except the under-rail capacitance.
The ESD misses are the open question, and nobody has shown whether f6 does better or worse on the same bench (finding 4).
Getting to "GO with conditions" needs two things: either budget requests for the misses or a design change, and f6 run through the same ESD bench.

## Findings

1. **HIGH: HBM 2 kV pad-to-pad misses the bond-pad limit.** P+N / P-N: 9.61 V typ, 11.10 V high metal, limit 8.0 V.
   - At 1 kV it passes: 6.33 / 6.96 V. The VSS and VDD cases pass at 2 kV: worst 6.07 V typ, 7.02 V high.
   - No device goes over its transient limit: worst gate 5.78 V typ / 6.63 V high.
   - With high metal, 25 MOS are over the 6.0 V DC screen (reported, not a fail by itself).
   - Rerun here: `esd/rv_a4rt.json` gives 9.606 V, identical to `../esd/a4rt.json`.
   - Do: file a budget request for pad-to-pad, or add site diode area / lower the DVDD return. The return through up-diode, DVDD, ring clamp, VSS and the far down-diode is the long path.
2. **HIGH: CDM surrogate misses at every amplitude.**
   - Without die capacitance, the worst pad (all cases) reaches 11.56 / 16.86 / 19.11 V typ at 1 / 2 / 3 A, and 12.68 / 17.92 / 20.66 V high. P+VSS alone at 1 A is 8.67 V typ.
   - With the 1 nF die capacitance: 8.55 / 14.40 / 18.96 V typ.
   - 25 nfet_06v0 (termination switches, e.g. X266 / X302) exceed 8.0 V from 1 A without Cdie, and from 2 A with Cdie; the worst gate is 12.4-13.0 V.
   - This is a real oxide-limit miss, not only a pad-voltage miss. Evidence: `../esd/a4r{t,h}{,_cdie}.json`.
   - Do: protect the switch gate and drain locally (secondary clamp or series R at the switch drain), or file a budget request with a CDM-to-amperes argument for 250 V.
3. **HIGH: pad capacitance misses (known before the run, since f6 also misses).**
   - With the under-rail term (`a4r{t,h}_rail-ac.json`): leg mean 1.296-1.314 pF typ and 1.258-1.281 pF high; the worst single leg is 1.319 pF. Limit 1.15 pF.
   - The under-rail term is 206 fF per pad, larger than f6's (about 160 fF in `f6rt_rail`), because the site diodes sit under the rail.
   - There is no low-metal `_rail` variant. Low metal reads the highest C (1.142 pF without the rail term), so the true worst case is about 1.34 pF and is not recorded.
   - The C read-out known answer works: `a4rt_rail_ctest` with +100 fF on P gives imbalance 110.9 fF.
   - Do: file a budget request, or shrink diode or metal under the rail; run `a4rl_rail`.
4. **MEDIUM: no f6 baseline on the ESD bench** (`esd/` has no f6 run). This leaves the real decision undetermined: whether a4 is better or worse than the published cell on HBM pad-to-pad and CDM.
   - Do: run f6 through `esd.py` (same ring, typ and high) before deciding.
5. **MEDIUM: the RX core node is not checked in the ESD bench.**
   - `esd.py` checks only devices inside the pad model. RX_P / RX_N load a bare 50 fF and no receiver gate is modelled.
   - My rerun with an added read-out (`esd_r.py`) puts RX_P - VSS at 4.65 V peak at 2 kV HBM, and 6.10 V (P+N) / 6.00 V (P+VSS) at CDM 1 A.
   - If the core receiver input is a 3.3 V device, its 5.0 V transient limit is exceeded at CDM 1 A and nearly reached at HBM 2 kV.
   - Do: add the real receiver input (or its gate) to the bench and report RX - VSS.
6. **MEDIUM: ring model is an unextracted lumped assumption.**
   - It is near/far 0.10/0.30 ohm typ, and the "high" corner is only +25 %. The near dvdd cell is 0.2-0.5 mm away, so 0.1 ohm on DVDD is plausibly optimistic.
   - The ESD matrix covers typical devices at 27 C only (no ss/ff, no hot).
   - The CDM case is a current-injection surrogate, not a charged-die model.
   - Leaving out the DVDD-DVSS decap is stated, and it is pessimistic.
   - Do: extract the rail-cell and ring metal from the pad site to the nearest dvdd/dvss cells, or bound it at 2x.
7. **LOW: model reduction ties terminals.**
   - The 5 down-diode cathodes share one node (`PAD_x__dn`), fed by 5 parallel reduced resistors (0.19 ohm effective). Shorting the fingers is slightly optimistic, and current sharing between fingers is not evaluated.
   - There is no per-finger current-density or failure-current check (about 5 mA/um of perimeter at 1.33 A over 259 um). This also matters because `--no-core-array` removes the core diodes, so the 5+5 site fingers per pad are the only primaries.
   - Do: state the diode It2 / um assumption with a source in design-assumptions.md.
8. **LOW: generator provenance gap.**
   - A `git reset` at 2026-11-19 08:00:30 touched all four edited generators after the a4 build (11-18 08:52) and after `default-xor.txt` (11-18 10:00).
   - The snapshots in `build/a4/` match the current `hs_pad_compose.py` and `pad_site_primary.py`.
   - No snapshot exists for `hs_leg_layout.py`, `circuits.py` or `protection_device_audit.py`. The default-path XOR = 0 is therefore not proven for the current files.
   - Do: rerun the default (no-flag) build and its XOR against the published GDS, plus an a4 rebuild sha check, from the current tree before committing.
9. **LOW: no negative controls for the per-cell precheck or latch-up** in `checks_a.sh`. Both checks report 0.
   - The KLayout path's ability to fail is shown by the `rail_site_check.py --selftest` I ran: clean PASS, Via3 offset FAIL with V3.1 x2, wrong size REFUSED (`selftest/`).
   - The latch-up check has no failing control on record here.
   - Do: add a control, e.g. move a ptap ring away.
10. **LOW: the receive-loss limit cannot be evaluated against f6 at high metal.**
    - At typ, a4 is better than f6.
    - At high metal, a4 is 1.75-1.85 dB at 2.4 GHz, against f6 typ 1.59-1.68 dB plus 0.1, which would be a 0.05-0.17 dB miss.
    - There is no f6 high-metal record, so this is not a fair comparison.
    - Do: run f6rh.
11. **INFO: return-loss comparison depends on the reference.**
    - Like for like, a4 passes: a4rt_rail 7.08-7.37 vs f6rt_rail 7.36-7.65 die RL, and COB 5.46-5.53 vs 5.58-5.66.
    - Against the declared f6 numbers (8.40-8.64, which exclude the rail term), the a4 rail value is 1.2 dB worse.
    - The limit text should say which reference applies.
12. **INFO: limits were not moved.** The "Pass limits" section is byte-identical to commit 42980c36 (2026-11-18 08:53:28), which was committed 1 min after the a4 GDS and before any a4 bench result. The term and AC known answers and negative controls exist: TERM_ENABLE off gives 5.7e10 ohm, the ctest +100 fF reads back, toy 2 ohm gives 2.78 V (expected 2.80 V), and nosite gives 29.6 kV, so the bench fails without the site diodes.

## Declared limits vs recomputed numbers

| Limit | Recomputed (source) | Result |
|---|---|---|
| Magic DRC 0, composer LVS match | DRC 0, lvs_match true, device graph match (`build-a4.txt`) | PASS |
| Read-back LVS uniquely + swap control fails | pos / sch: match, unique, 504=504 devices; swap neg: mismatch; neg2 (one diode removed): mismatch (`checks/a4/rb_*.log`) | PASS |
| KLayout precheck main 0 / antenna 0 | cell 0/0; pad-on-rail 0/0; `rail_site_check` (template-aligned) 0/0, sha matches | PASS |
| Latch-up 0 um2 uncovered at 15 um | nmos 0.0, pmos 0.0 (at 10 um, nmos 764.8) (`lu.json`) | PASS |
| Legacy / default XOR 0 | 0.0 / 0.0 (`default-xor.txt`; see finding 8) | PASS* |
| HBM 2 kV bond pad <= 8.0 V | typ 9.61 (P±N), high 11.10; vs VSS/VDD 6.07 / 7.02 | **MISS** |
| HBM 1 kV bond pad <= 8.0 V | typ 6.33, high 6.96 | PASS |
| MOS transient <= 8.0 V (6 V dev) at HBM | 5.78 typ / 6.63 high, 0 over | PASS |
| DC screen count (report) | HBM 2 kV: 0 typ / 25 high | reported |
| CDM 1 / 2 / 3 A pad <= 8.0 V (no Cdie) | typ 11.56 / 16.86 / 19.11; high 12.68 / 17.92 / 20.66 | **MISS** all |
| CDM with 1 nF Cdie | typ 8.55 / 14.40 / 18.96; high 9.76 / 16.58 / 20.68 | **MISS** all |
| MOS transient at CDM | 25 over 8.0 V from 1 A; worst 12.44 typ / 13.01 high | **MISS** |
| Pad C per leg incl. under-rail <= 1.15 pF | 1.296-1.314 typ_rail, 1.258-1.281 high_rail; worst leg 1.319 | **MISS** |
| P/N imbalance <= 20 fF | 10.9 typ, 11.6 high | PASS |
| T-A best code 95-105 ohm (23 corners) | low 95.6-103.8, typ 97.0-103.5, high: PASS | PASS |
| T-B code in 2..13 | low 4-9, typ 5-10, high 8-11 | PASS |
| T-C per-leg P-N <= 1.0 ohm | <= 0.36 | PASS |
| T-D one code 80-120 ohm | typ code 7: 84.8-119.2; high code 9: 82.0-111.8; low code 7: 79.9-114.4 | PASS typ/high, **MISS low** |
| Die RL 2.4 GHz, not worse than f6 by > 0.3 dB | like for like: a4rt 8.32-8.63 vs f6rt 8.34-8.66; rail 7.08-7.37 vs 7.36-7.65 (-0.28 at min) | PASS (marginal on rail) |
| COB RL, same rule | a4rt_rail 5.46-5.53 vs f6rt_rail 5.58-5.66 (bond 0); all bonds 5.21 vs 5.32 | PASS |
| Receive loss not worse than f6 + 0.1 dB | 2.4 GHz rx/pad: typ 1.24-1.33 (f6 1.59-1.68); high 1.75-1.85 (no f6 high) | PASS typ, open high |
| Outline / pins | bbox (-0.055, 0)-(492, 912.91); new port DVDD (Metal3 labels at (57.75, 141.4) and (268.75, 141.4)), declared in STATUS | PASS |
| Known answer + negative control per bench | ESD toy / nosite; term off / pub; AC ctest; LVS swap / neg2 | PASS (no DRC/LU control in checks_a.sh) |

## Reviewer artefacts (this folder)
- `esd_r.py`: copy of `esd.py` with RX_P/RX_N - VSS read-out added; `esd/rv_a4rt.json` holds 4 reruns (HBM 2 kV and CDM 1 A, cases P+N and P+VSS, typ).
- `railsite/a4/site.json`: rail_site_check PASS on the sha-matched GDS. `selftest/`: tool self-test OK.
