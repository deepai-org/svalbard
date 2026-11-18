# Session 13: limits declared before the runs

Written 2026-11-18 before any session-13 result existed, unless a line carries a later date.

## Real chain (bench `../s12/chain.py`, unchanged from session 12)
Far end, 0 errors over >= 200 scored bits, inner eye >= 0.200 V differential, eye width >= 0.45 UI.
Oversampled rates (n core bits per line bit): scored on the LINE bit (n core bits), same three limits with UI = line UI.
Negative control: one ring phase grounded (kill) must fail; one stream stuck must fail.

## POST bank (bench `../s12/mux/m8.py`, extracted mux, ideal phases, extracted pad + COB channel)
* De-emphasis (POL 0) at the two settings r = post tap / main tap = 0.20 (3.5 dB) and 0.33 (6 dB), set with the POST tail
  bias: tap ratio within +/- 0.05 of the target; far end 0 errors / >= 200 bits; width >= 0.45 UI; inner eye >=
  0.200 V x (1 - r) / (1 + r) (= 0.133 V and 0.100 V): de-emphasis keeps the peak drive and lowers the settled level by
  that factor by definition, so the full-swing 0.200 V limit is scaled, not relaxed. MAIN current may be raised up to
  the pad's 21 mA code range.
* Same sign (POL 1) produces a three-level signal b[n] + b[n-1] by construction (the binary scorer's 28 errors of
  session 12 are that). Limit: with the taps set equal (ratio 1.0 +/- 0.1), at one common sampling phase,
  min |outer level| - max |zero level| >= 0.100 V over >= 200 bits, and no sample in the wrong band (three-level
  errors 0).
* Negative control: POL flipped against the scorer's expectation must fail.

## Stopped-ring interlock
* Any static phase state (all 256 logic combinations are covered by: all low, all high, each single running-ring
  pattern, one phase stuck high / low with the others running, phases at mid level 1.35 V): the DC current through any
  single slice path with EN_MAIN = EN_POST = 1 is <= the Metal1 limit of the narrowest column, i.e. bank current
  <= 2.09 mA/um x column width; target: bank current < 0.1 mA within 100 us of the ring stopping.
* Running ring 240-420 MHz, all corners in the window, 0-85 C, 2.97-3.63 V: detector output high, eye unchanged
  (within 5 mV) against the mux without the interlock.
* Power-up: supply ramp 0 -> 3.63 V in 12 us (0.3 V/us) and 10 ms-equivalent slow ramp (DC sweep), ring stopped,
  enables high: slice current stays under the limit throughout.

## Phase trim
* Range: >= 2 x the worst cumulative phase error of the pessimistic ring (100 ps -> 200 ps at ss; at ff the same
  ratio against the ff ring error) OR, with an assumed +/- 10 ps ring, >= 2 x 20 ps.
* Step <= 15 ps at ss (residual after calibration <= +/- 8 ps).
* Calibration: the method must find codes from on-chip observables only, and the codes it finds must pass the real-chain limit.

## Supply impedance / mismatch
* Supply: bond 2.82 nH + 0.23 ohm per supply and ground, on-chip decap as declared in the block, plus 30 mV pp ripple
  at 1 / 10 / 100 MHz: real-chain limit still met at ss 3.15 V 3.125 Gb/s.
* Mismatch: Monte Carlo (PDK statistical models, >= 30 samples) at ss 3.15 V 3.125 Gb/s, mux-level bench: 0 failing
  samples against 0 errors / 0.45 UI / 0.200 V after per-sample trim calibration; report the spread.

## Added 2026-11-18 05:30 UTC, before any EXT / idle / tap run
* EXT fallback (ring phases static in an arbitrary state, or the ring running): DX at 1.6 Gb/s (top of board
  requirement B12, 0.5-1.6 Gb/s) and 0.5 Gb/s: far end 0 errors / >= 200 bits, eye >= 0.200 V, >= 0.45 UI. Negative
  control: EXT = 0 with the ring stopped must give no output (interlock) and DX stuck must fail.
* Electrical idle (PCIe base spec figures): differential at the pad |V| <= 20 mV, DC common-mode change between data
  and idle <= 100 mV (V_TX-CM-DC-ACTIVE-IDLE-DELTA), entry and exit within one 40-bit word (12.8 ns at 3.125 Gb/s).
  Both idle flavours are measured; the one that meets the limit becomes the documented default.
* CMOS tap (USB HS, 480 Mb/s = 2.4 Gb/s core, 5 core bits per line bit): TAP_P / TAP_N rail to rail (<= 0.3 V,
  >= VDD - 0.3 V), 0 errors / >= 200 line bits, P / N skew <= 150 ps, added load on MAIN_P / MAIN_N <= 10 fF each,
  far-end eye of the 3.125 Gb/s MAIN path changed by <= 5 mV with the tap attached.
* Ring version: every row carries `ring=layout-11Nov` (extracted `pt_pll_ring_core` as laid out) or
  `ring=committed-estimate` (same extraction with XC0b's gate moved to P1 as committed in e7b4d14).
* Publishing: extraction with resistance (R+C) and the corners tt, ss, ff, sf, fs.
