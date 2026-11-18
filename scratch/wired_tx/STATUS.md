# Wired TX: status and resume point

Working state for a successor. Published facts: `analog/wired_tx/README.md`. Session-12 result table: `s12/TRUTH.md`
(old netlists). Session-13 work: `s13/` (limits declared in `s13/LIMITS.md` before the runs). Review of session 12:
`s12/review/REVIEW.md`. Nothing new is published.

## Ring version behind every real-chain number so far
All real-chain rows (session 12 and the session-13 probes) use the extracted `pt_pll_ring_core` layout of 11 Nov
(`analog/timing/generated/pll_ring_core.ext.spice`), whose ring cell has `XC0b` gated by `ENB`. The committed ring cell
(e7b4d14) gates it by `P1` (risk TIM-12, `scratch/reviews/evidence-audit.md`). Comparison bench: `s13/ringver/cmp.py`
(same extracted netlist with that one gate moved) -> `s13/ringver/cmp.json`. Label every new row with `ring=layout-11Nov`
or `ring=committed-estimate`.

## Root cause of the 3.125 Gb/s failure at the pessimistic slow corner (found, `s13/runs/p1`, `s13/probe.py`)
In `wtx_ser8d` the first retiming hop of streams 0, 5, 6, 7 (flops `XH0_0`, `XH5_0`, `XH6_0`, `XH7_0`, all clocked by
the phase-4 clock `XP4/Q`) samples the stream-register outputs too early. Measured at ss pessimistic, 3.15 V, slot
319.5 ps, times after the PH0 rising edge at the pin: register clock `QK0/QK1` rises at 1.60-1.65 ns, register outputs
`BO` change at 2.45-2.51 ns, the phase-4 hop clock rises at 2.56 ns: 55-110 ps of set-up. The four streams are the
four failing bit positions (errors only in slots 5, 6, 7, 0; `s13/perstream.py`). In ps: needs
4 slots + 1.30 ns (hop clock delay) >= 2.49 ns + set-up, i.e. slot >= about 335 ps: passes at 370 ps (2.7 Gb/s), fails
at 320 ps. Streams 1-4 are captured at phases 5, 6, 7, 0 and have 0.24-1.3 ns.
Fix: new hop plan in `ser8d_macro.py` (first capture at phase 6 or 7, final hop 6 slots before the slice window),
see "Hop plan" below. Not yet laid out.

## RESUME HERE (state at 2026-11-18 07:50 UTC; session 13 ended early: the layout sub-agent hit its usage limit)
1. Layout state. Built and checked from disk (pass 1): `wtx_ser8d` (final HOPS, but `s13/ser8d/verify.py v`, `rc.py`,
   `ctab.py` NOT re-run after the last hop-table change), `wtx_mux8` revision 3, `wtx8_aux` (two parts), `pt_wiredtx8`
   (744.1 x 471.3 um, `s13/top/REPORT.md`). `pt_wiredtx8_layout.py` in analog/wired_tx is the pass-1 generator that matches
   the artefacts in `generated/fast/`. Pass 2 was in progress when the agent stopped: `s13/top/pt_wiredtx8_layout.pass2-wip.py`,
   `s13/top/wtx_mux8_layout.pass2-wip.py` (= the current `analog/wired_tx/wtx_mux8_layout.py`, UNVERIFIED edits: header feed
   under the risers), `s13/top/serm5/` (D trunks to the bottom edge). Pass-2 brief: seam <= 40 um, D pins on the bottom
   edge, trims / codes / statics out beside the mux, bias pins to the pad edge, phase buffers `wtx8_phbuf` at the pin row
   (schematic `wtx8_top.py` already has them: the schematic is AHEAD of the pass-1 layout, LVS of the pass-1 GDS against
   the current `wtx8_top.netlist()` will fail on XPB / PS nets), R+C netlist with the mux bus resistance carried in.
2. After pass 2: probe run at ss pessimistic and ff (`s13/probe.py` style) to confirm the stream timing with the buffer
   delay (stream must change outside -0.1..+0.35 ns (ss pess.) / 0..+0.25 ns (ff) after its slice's phase edge; today
   1.5-1.95 ns ss, 0.65-1.0 ns ff before the buffers add about 0.15 ns).
3. Queues still running detached when the session ended (one simulation each, results land in files): `s13/padr/q.sh`
   (`padr.log`: matrix A pad models, then B requirement sweep -> finish row WT39), `s13/q_x2.sh` (`q_x.log` line
   `x3_cal_ssp` = extracted mux eye with calibrated codes) -> `q_cal.sh` (`cal_*.out`, `calres/*.json`: trim codes with the
   real ring, both ring versions) -> `q_tune.sh` (`q_tune.log`, ring VCTRL for all table rates incl. sf / fs at an ASSUMED
   ring supply of 2.75 V). Stop all with `touch s13/STOPQ` (q_tune does not honour it: kill it).
4. Then the table on the final netlists: `s13/chain13.py` (options `top_ext=generated/fast/pt_wiredtx8.ext.spice`,
   `pad_model` C / RT / RH, `ring_ver`, `n_over`, `codes`, `supply`, `tap`, `idle`), worker `s13/worker13.sh <jobfile>`,
   table `s13/table13.py`. `top_ext` has never been run. Planned rows: 3.125 and 3.24 at tt / ss / ss 3.50 / ff / sf / fs /
   ss pess. 3.15 and 3.50 with the pessimistic ring; 2.5, 2.7, 3.0 at tt / ss / ss pess.; 0.48 (n = 5 at 2.4) and 1.25
   (n = 2) at ss / ss pess. / ff; kill control; pad=RC-typ at 2.7 / 3.125 / 3.24 tt and ss; R+C netlists for what publishes.
5. Not started: supply-impedance rows, Monte Carlo (`m9.py mc_seed=`), interlock stop / stuck / mid-level / ramp rows on
   the extracted netlist, EM current at ff 3.63 V 85 C (`m9.py c=ffhot`), idle and CMOS tap in the real chain (`q_c.sh`),
   POST targets at ff / tt, independent review of session 13 (fresh agent, files not conclusions), publish.

## State at 2026-11-18 07:05 UTC
- `wtx_ser8d` rebuilt with the final hop plan (`ser8d_macro.HOPS`, docstring = timing data): 744.12 x 197.68 um
  (0.147 mm2, was 0.234), DRC 0 / KLayout 0 / LVS unique from the disk GDS with 4 failing negative controls for the
  first hop table (`s13/ser8d/REPORT.md`); after the hop-table change only the generator's own DRC / LVS was run:
  RERUN `s13/ser8d/verify.py v`, `rc.py`, `ctab.py` before using its numbers.
- First real-chain run of the fix (`s13/chain13.py`, tag `c1_3125_ssp`: ss pessimistic 3.15 V, 3.125 Gb/s,
  ring=layout-11Nov pessimistic, pad=C, extracted new `wtx_ser8d`, SCHEMATIC revision-3 mux + aux, trim codes all 0):
  far end 0 errors / 360 bits (was 23 / 200), eye 0.122 V / 0.34 UI = still FAIL on the eye (untrimmed phases).
- `wtx_mux8` revision 3 laid out (`wtx_mux8_layout.py`, `s13/mux3/REPORT.md`): 324.6 x 163.4 um (0.0531 mm2, +23 %),
  DRC 0 / 0, LVS unique from disk, 4 negative controls fail, EM table passes at 26 mA per bank. `wtx8_aux` laid out
  (69.8 x 157 um). Sub-agent is now reworking the tap placement, adding bus resistance to the R+C netlist and building
  the block top `pt_wiredtx8` (`s13/top/`).
- Extracted revision-3 mux, ideal phases, ss pessimistic 3.125 Gb/s, pad=C, codes all equal: 0 errors, 0.194 V (fail by
  6 mV; extracted revision 2: 0.219). Both layouts have a systematic slice skew (crossing of slot 3 about -20 ps, slot 4
  +16 ps with ideal phases); the trim calibration removes it: run `q_x2.sh` (calibrated codes) before judging.
- Trim calibration from DC averages (`s13/cal.py`, method in its docstring): proven on known offsets (ideal phases:
  finds 46.6 ps of slot error, leaves +-6.7 ps). With the real ring the first pattern must not be measured during ring
  start-up (LEAD in cal.py; the first real-ring results were wrong for slot 0 and are deleted).
- Pad with metal resistance (`s13/padr/padr.py`, pads' models `scratch/pads-core/txr/models`): first row, mux level ss
  3.125 Gb/s: eye 0.367 V (pad=C) -> 0.203 V (pad=RC-typ). Matrix A (pad models) and B (requirement sweep) running.
- Fallback: with the ring running 1.6 Gb/s passes (ss pess. 0.50 V, ff 0.69 V, schematic); with the ring stopped the
  all-slices-parallel path passes 0.5 Gb/s and FAILS 1.6 Gb/s (16 errors: the eightfold pull-down takes the gates to
  0.13 V and the pad switches cross low).
- Idle: neither flavour met the 100 mV common-mode limit in the mux bench with the ideal 1.9 V tail bias (both gates
  high -0.20 V, both legs on +0.34 V); to be measured with the block's own DAC (`q_c.sh` rows c2 / c4, not yet run).
- Interlock (schematic): bank current 42.9 mA -> 0.0 mA 203 ns after the ring stops in state 11110000; detector alone at
  ff 0 C 3.63 V 240 MHz and ss 85 C 2.97 V 420 MHz runs, any stuck phase gives RUN = 0 (`s13/ilk/`).
- Queues (one simulation each): `s13/padr/q.sh`, `s13/q_x.sh` -> `q_x2.sh` -> `q_cal.sh` -> `q_tune.sh`; not yet
  started: `q_c.sh` (idle and USB tap in the real chain).

## Schematic work of session 13 (not laid out)
- `analog/wired_tx/wtx_mux8.py`: revision-3 schematic of the mux (docstring = the circuit): stopped-ring interlock
  (run detector), 4-bit trim (ss pessimistic 14.4 ps / code, 215 ps range; ff 8.3 ps, 162 ps), EXT fallback through all
  eight slices in parallel, idle (two flavours), AVG_P / AVG_N calibration taps. `mux8.py` + `mux8_layout*.py` are
  the laid-out revision 2 and stay until revision 3 is laid out, then they are deleted.
- `analog/wired_tx/wtx8_top.py`: block top `pt_wiredtx8` = `wtx_ser8d` + `wtx_mux8` + `wtx8_aux` (glue, two tail
  DACs, CMOS tap for the USB pre-driver).
- Benches: `s13/m9.py` (revision-3 mux, ideal phases, real pad + channel), `s13/ilk/det.py` and `s13/ilk/run_ilk.py`
  (interlock), `s13/trimchar.py`, `s13/post/sweep.py` + `s13/post4.py` (POST bank on the extracted revision-2 mux),
  `s13/bath/bath.py` (data-timing bathtub of the extracted mux).

## POST bank (extracted revision-2 mux, ideal phases)
- The "28 errors" of same-sign mode are the binary scorer applied to a three-level signal (b[n] + b[n-1]); scored as
  three levels the session-12 run has 0 wrong-sign samples and 0.139 V between the outer and zero bands (limit 0.100).
- De-emphasis tap ratio against the POST tail bias at ss pessimistic (MAIN bias 1.9 V): 0.9 V -> 0.085, 1.0 V -> 0.18,
  1.1 V -> 0.35, 1.2 V -> 0.56 (`s13/post/sweep.log`, `post4.py`).

## Open, in order
See the final report of session 13 / the README open list.
