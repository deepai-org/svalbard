# Interlock mid-level fix: limits (declared 2026-11-19 11:55 UTC, before any run of this work)

Applies to `wtx_mux8` after the detector change; the rows run on the EXTRACTED R+C mux (same extraction as
`s13/ilk/mux_rc.spice`), bench `ilk.py` in this directory (no pad, 0.45 pF per output, both banks enabled,
EN_MAIN = EN_POST = 1, trim codes 0, ideal phase sources with 150 ohm + 60 fF as `s13/m9.py`).

Definitions
* bank current = current through the PMOS headers of both banks (0 V sense sources inserted in series with every header
  source node), i.e. the sum of all slice-path currents. Total mux supply current is reported beside it.
* "stopped": the phases are held at a static or stalled state from `stop_at` = 22 ns on.

Limits
1. Every static or stalled state (stop 11110000 at ssp and ff; all 0; all 1; all phases at mid level 1.35 V at ssp and ff;
   all phases at 1.35 V with 0.3 V pp residual swing at the ring frequency 300 MHz at ssp and ff; one phase stuck high
   and, separately, one stuck low with the others running): RUN < 0.3 V and bank current < 0.1 mA, reached within 100 us
   of the stop and staying there to the end of the simulated window (the window ends >= 300 ns after the latest of the
   two events; a state reached in the window and held there by DC logic counts as "within 100 us").
   Also: the current through any single slice path <= the Metal1 limit of LIMITS.md (2.09 mA/um x narrowest column)
   at all times after the stop (covered by the bank-current limit when that is met).
2. Supply ramp 0 -> 3.63 V in 12 us, ring stopped (phases at 11110000 scaled with the supply), enables high:
   bank current < 0.1 mA after the ramp (VDD >= 3.6 V) and never above the single-path Metal1 limit during the ramp;
   RUN < 0.3 V at the end.
3. Running ring 240 and 420 MHz at ff 0 C 3.63 V and ss pessimistic 85 C 2.97 V (the window corners): RUN >= VDD - 0.3 V
   throughout the scored window, and the gate-level eye height (MAIN_P - MAIN_N, PRBS7, >= 120 bits) within 5 mV of the
   pre-fix extracted mux (`s13/ilk/mux_rc.spice`) on the same bench and stimulus.
4. Negative control: the same extracted netlist with the detector output forced high (text edit of the extracted
   netlist; RUN and every internal copy of it tied high) must NOT meet limit 1 for the stop 11110000 case at ssp
   (bank current stays above 1 mA).
5. Reported, no limit: total mux supply current in each stopped state (pre-fix: 6.1-6.2 mA at mid level); target
   <= 1 mA at mid level.
