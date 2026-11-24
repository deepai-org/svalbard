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

## RESUME HERE (2026-11-24)
- Block `pt_wiredtx8` handed to assembly (WT57, commit 19367351 + 7cd4956f); bound in wired/chip.conn (WT50). WT53-d final.
- Done 2026-11-24: term_buffer on always-on VDD (257c62da, WT58); pump `wtx8_casbias` starts at every corner
  (b1c79575; extracted results `s18/tran/ext_*.json`).
- Pump is a separate pt_wired instance `cascode_pump` (663437fd, WT59), interim CB_EN = c_wiredtx_post_pol; 100BASE-TX
  986 mV cal. at ss-pess with the extracted 4.12 V (dcd56b93). Island limit superseded by PDS-19 (105 / 131 mA on 2x isw_wired).
- Next, ranked: (1) when digital lands c_wiredtx_cascode_boost, check it binds cascode_pump.CB_EN (not wiredtx);
  (2) 100BASE-TX at ss 85 C 2.97 V (pump 3.84 V); (3) in-block VSS IR 3.95 vs 3.0 mV; (4) lever 2 only if assembly's
  trunk cannot carry the island current.
- Rules: commit with a pathspec; scratch is gitignored (git add -f). Extraction flow: `s16/net/fixcap16.py`.

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
  +16 ps with ideal phases); the trim calibration removes it: codes [1,0,0,0,0,0,0,0] give 0 errors, 0.211 V / 0.64 UI
  (`s13/q_x.log` line `x3_cal_ssp`, mux-level screening, pad=C).
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
