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
