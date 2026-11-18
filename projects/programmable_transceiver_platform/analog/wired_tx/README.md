# Wired-TX family (`analog/wired_tx`)

Serializer, pre-driver gating and tail-bias DACs (`pt_wiredtx`), the USB pre-driver (`pt_usb_txdrv`), the USB HS
bias DAC (`pt_wtx_hsbias`) and the fallback receiver instance (`wtx_ext_rx`). Ring phases come from the shared
`pt_pll_ring_core` (owner: wired RX / timing); the pad, steering buffers, interlock and termination are `analog/pads`.
Pin-level connection intent: `INTEGRATION.md` (wired TX) and `USB-INTEGRATION.md` (USB). Nothing here is qualified.
Numbers are from extracted netlists (Magic C) unless marked; `generated/*-evidence.json` is the record.
Working notes and the resume point for a successor: `scratch/wired_tx/STATUS.md`.

## Blocks

| Block | Published outline | DRC (Magic / KLayout) | LVS | Verified function (evidence) |
| --- | --- | --- | --- | --- |
| `pt_wiredtx` (quarter-rate CMOS core `wtx_serq4c`, CMD gating, MAIN / POST tail DACs) | 546.9 x 454.2 um = 0.248 mm2 | 0 / 0 | unique | ideal phases: 2.5 Gb/s 0 errors at ss/32/3.15 and ff/22/3.35 at the CMD pins (`generated/wiredtx-evidence.json`). Real ring phases: 0 errors at tt, **11 errors / 101 bits at ss/32/3.15** (`generated/wiredtx-realring.json`) |
| `tmds` | configuration of `pt_wiredtx` (TMDS levels through the MAIN branch) | (wiredtx) | (wiredtx) | 1.485 Gb/s tt: eye 1050 mV / 604 ps, 0 errors (`generated/wiredtx-evidence.json`) |
| `pt_usb_txdrv` | 116.48 x 270.06 um = 31,457 um2 | 0 / 0, precheck clean | unique | table in `USB-INTEGRATION.md` (`generated/usbdrv-evidence.json`) |
| `pt_wtx_hsbias` | 125.8 x 76.0 um = 9,552 um2 | 0 / 0 | unique | 0-0.58 V full scale at tt, monotonic at all corners, 1 LSB settling 0.47 us (`generated/usb_hs_bias-evidence.json`) |
| `wtx_ext_rx` | instance of timing's `pt_diff_clk_rx` (`wtx_ext_rx.spice`) | timing | timing | through the extracted receiver: 5 / 43 errors at 0.5 Gb/s, no output at 2 Gb/s (`generated/wtx_ext_rx-evidence.json`; risk TIM-08) |

Not published (must not be instanced): the new block top `pt_wiredtx8` and its parts (below), the earlier eighth-rate
core `wtx_serq8` (`serq8_macro.py`), the laid-out mux revision 2 (`mux8.py`, `mux8_layout*.py`, to be deleted when
revision 3 publishes) and the CML pre-driver `wt24_tr7` (`scratch/pads-wt24/`).

## New block `pt_wiredtx8` (not published)

`pt_wiredtx8` = `wtx_ser8d` (40-bit word into eight streams) + `wtx_mux8` (8-phase muxing pre-driver that drives the pad's
MAIN / POST switch gates) + `wtx8_aux` (glue, two tail DACs, CMOS tap for `pt_usb_txdrv`) + phase buffers + decap.
Circuit descriptions are the docstrings of `wtx_mux8.py`, `ser8d_macro.py`, `wtx8_top.py`; pins in `INTEGRATION.md` section 7.

| Cell | Outline | DRC (Magic / KLayout) | LVS on the GDS read from disk | State |
| --- | --- | --- | --- | --- |
| `wtx_ser8d` | 744.1 x 197.7 um = 0.147 mm2 | 0 / 0 | unique, 4 negative controls fail (first hop table); the final hop table has only the generator's own DRC 0 / LVS unique | `scratch/wired_tx/s13/ser8d/REPORT.md`; re-run `verify.py` |
| `wtx_mux8` revision 3 | 324.6 x 163.4 um = 0.053 mm2 | 0 / 0 | unique, 4 negative controls fail, antenna 0 | `scratch/wired_tx/s13/mux3/REPORT.md`; EM table passes at 26 mA per bank (zero margin at 30.1 mA) |
| `wtx8_aux` | side cell 69.8 x 118.5 um + tap row in the mux corner | 0 / 0 | unique, 2 negative controls fail | same report |
| `pt_wiredtx8` (first pass) | 744.1 x 471.3 um = 0.351 mm2 bounding box, of which a 110 um seam (0.082 mm2) and a free 147 x 154 um rectangle | 0 / 0 | unique against the schematic WITHOUT the phase buffers, 3 negative controls fail | `scratch/wired_tx/s13/top/REPORT.md`. **The schematic is ahead of this layout** (`wtx8_phbuf` added afterwards); the second layout pass (seam <= 40 um, D pins on the bottom edge, header feed, bias pins to the pad edge) was started and NOT finished: `scratch/wired_tx/s13/top/*pass2-wip.py`, and `wtx_mux8_layout.py` carries unverified edits of that pass |

Extraction: capacitance-only netlists `generated/fast/*.ext.spice`; `*.rc.spice` add resistance (Magic extresist on a
subset of nets plus drawn-width resistance of the mux buses, gate trunks and the top-level phase / stream / supply
wires). No simulation has used the R+C netlists yet.

### What is established (session 13; limits in `scratch/wired_tx/s13/LIMITS.md`, declared before the runs)

Every real-chain number so far uses ring=layout-11Nov (the extracted `pt_pll_ring_core` as laid out; the committed
ring cell differs, row WT38) and pad=C (capacitance-only pad extraction) unless a row says otherwise.

* **Cause of the 3.125 Gb/s failure at the pessimistic slow corner:** in `wtx_ser8d` the first retiming hop of streams
  0, 5, 6, 7 was clocked by phase 4 and sampled the stream-register outputs 55-110 ps after they changed (register
  clock buffer 1.65 ns + register clock-to-output 0.84 ns against 4 slots + 1.30 ns of hop-clock delay): it needs a slot
  of about 335 ps, between the passing 370 ps and the failing 320 ps. The hop plan is replaced (`ser8d_macro.HOPS`).
  Real chain with the rebuilt, extracted `wtx_ser8d` and the SCHEMATIC revision-3 mux, ss pessimistic 3.15 V, pessimistic
  ring, untrimmed phases: 0 errors / 360 bits (was 23 / 200), eye 0.122 V / 0.34 UI: the errors are gone, the eye limit
  is not met without trim (`scratch/wired_tx/s13/resultsC/c1_3125_ssp.json`).
* **Extracted revision-3 mux alone** (ideal phases, ss pessimistic, 3.125 Gb/s, pad=C, 216 bits): 0 errors, 0.194 V with
  equal trim codes (limit 0.200: fail by 6 mV; revision 2 0.219 V). The layout has a systematic 15 ps skew on one
  slice edge, which the calibration below removes (codes [1,0,0,0,0,0,0,0], residual +-3.5 ps): with those codes
  0 errors, 0.211 V / 0.64 UI (passes the screening limit; `scratch/wired_tx/s13/q_x.log`, `x3_cal_ssp`).
* **Pad with metal resistance** (pads' models `scratch/pads-core/txr/models`, mux level, extracted revision-2 mux, ideal
  phases; `scratch/wired_tx/s13/padr/padr.log`), eye in V, pad=C / pad=RC-typ / pad=RC-high: ss 2.7 Gb/s 0.482 / 0.264 / -;
  ss 3.125 0.367 / 0.203 / 4 errors; ss 3.24 0.331 / 0.186 / 10 errors; tt 3.125 0.483 / 0.210 / 0.082.
  The eye roughly halves at typical metal; every pad=C pass is optimistic. The requirement sweep for the reworked pad
  (series resistance, termination, capacitance) was queued behind this matrix (`padr.py B`).
* **Stopped-ring interlock** (`wtx_mux8` run detector): schematic, both banks on, ring stopped in state 11110000:
  supply current 42.9 mA -> 0.0 mA within 203 ns. Detector alone: runs at ff 0 C 3.63 V 240 MHz and ss 85 C 2.97 V
  420 MHz, any single stuck phase gives RUN = 0. Extracted mux: RUN rises 13-22 ns after start at ss pessimistic
  405 MHz, ff 85 C 3.63 V 240 MHz, ss 85 C 2.97 V 405 MHz. Not run: stop / stuck / mid-level / supply-ramp rows on the
  extracted netlist.
* **Phase trim:** 4 bits per phase; schematic 14.4 ps per code and 215 ps range at ss pessimistic, 8.3 ps and 162 ps at
  ff, against 2 x the worst edge span of the ring (98 ps pessimistic with the committed cell, 75 ps at ff).
  **Calibration** (`scratch/wired_tx/s13/cal.py`): the digital sends the eight one-hot words, the DC average of
  `MAIN_N - MAIN_P` on `ATB_AVGN / ATB_AVGP` measures each slot width, all eight equal is the target. Proven on known
  offsets (finds 46.6 ps, leaves +-6.7 ps). With the real ring the first results were wrong for slot 0 (measured
  during ring start-up); the corrected runs were queued and are not in hand.
* **POST bank** (extracted revision-2 mux): the "28 errors" of same-sign mode were the binary scorer on a three-level
  signal; as three levels: 0 wrong-sign samples, band separation 0.139 V at ss pessimistic and 0.193 V at ff (limit
  0.100). De-emphasis at ss pessimistic: tap ratio 0.18 at POST bias 1.0 V (eye 0.239 V, limit 0.133) and 0.35 at
  1.1 V (0.278 V, limit 0.100); at ff the same biases give 0.46 and 0.67, so the POST code must be set per chip
  (ff 0.28 at 0.9 V: 0.427 V). The 0.20 / 0.33 targets were not re-run at ff / tt bias values. POST costs 20-24 mA.
* **Fallback (EXT):** with the ring running, 1.6 Gb/s passes (0.50 V ss pessimistic, 0.69 V ff, schematic). With the
  ring stopped the all-slices-parallel path passes 0.5 Gb/s (0.87 V) and FAILS 1.6 Gb/s (16 errors / 205).
* **Idle:** with an ideal 1.9 V tail bias neither flavour meets the 100 mV common-mode limit (both gates high:
  -0.20 V; both legs on: +0.34 V); not yet measured with the block's own DAC.
* **Current:** 53 mA for the block at ss pessimistic 3.125 Gb/s, MAIN only (real chain, schematic mux);
  the mux alone 24-26 mA MAIN only, 44-52 mA with POST. The wired_tx island switch is rated 40 mA (row WT40).

Not done: the rate x corner x supply table on the final netlists (2.5, 3.0, 3.24 pessimistic, oversampled rates, sf /
fs, pessimistic ring with calibrated codes), R+C simulations, supply-impedance and Monte Carlo rows (benches exist:
`chain13.py` `supply=`, `m9.py` `mc_seed=`), the CMOS tap and idle in the real chain, the independent review of
session 13's layouts.

## Architecture of `pt_wiredtx`

```
 ring phases WTX_PH0/90/180/270 --> four core phases C0..C3, 1 UI apart
 D0..D39 (D0 first) --> 40 -> 20 word mux --> core wtx_serq4c: 4 x 5-bit parallel-load TSPC shift registers on C2,
                        per-stream retiming hops --> F0..F3 --> 4:1 window muxes (window k = C(k) & C(k-1)):
                        main Y / YB, postcursor DP / DPB (main delayed one line bit)
 DX (pt_diff_clk_rx on WTX_EXT_P/N) --> one-hot select core / EXT (break-before-make)
        --> CMD_MAIN_P/N = data & EN_MAIN, CMD_POST_P/N = post & EN_POST --> pads' gate drivers --> pad switches
 IBIAS (10 uA) --> two 8-bit PMOS DACs --> MAIN_BIAS / POST_BIAS (pad tail gates, ratio 16, LSB about 83 uA)
```

* Rates: quarter rate, 4 bits per ring cycle; lower line rates by bit repetition x2 / x4 in the digital
  (`MODE_H`, `MODE_F` only place the postcursor one line bit late). `WORD_CLK40` = core rate / 40.
* Each mux window closes on the falling edge of the previous phase, so the core is sensitive to the ring's phase
  duty cycle (0.57-0.58 at ss, 625 MHz): the cause of the ss failure with the real ring.
* Polarity: logical 1 = `CMD_MAIN_N` high = `V(PAD_P) > V(PAD_N)`. `POST_POL` 0 = de-emphasis, 1 = same sign (MLT-3).
* Tail DACs: MAIN code 109 = 9.05 mA (reset), 255 = 21 mA.
* `pt_wtx_hsbias`: 10 uA reference, eight binary PMOS sources into an NMOS triode load; `EN` = 0 pulls `HS_PBIAS`
  to VDD, no static current; about 2.3 mV per code at tt, +/- 20 % over PVT.
* All inputs are MOS gates on the wired rail (no current from a live core-domain driver into an unpowered island).

## Results (`pt_wiredtx`, regenerated by `evidence.py`)

<!-- RESULTS:BEGIN (generated by evidence.py) -->
| Run | Rate | Bits/ring cycle | Corner | Result | Detail |
| --- | --- | --- | --- | --- | --- |
| cornerq2.5_ss_32_3.15 | 2.5 Gb/s | 4 | ss 32 C 3.15 V | pass | 0 errors / 140 bits, CMD jitter 162.7 ps pp, post mism. 0 |
| cornerq2.5_ff_22_3.35 | 2.5 Gb/s | 4 | ff 22 C 3.35 V | pass | 0 errors / 141 bits, CMD jitter 112.5 ps pp, post mism. 0 |
| int_tmds_q1g485 | 1.485 Gb/s | 4 | tt 27 C 3.3 V | pass | eye 1050.2 mV / 603.7 ps, 1372.0 mVpp diff, 0 errors / 219 bits |
<!-- RESULTS:END -->

## Reproduce

```
./run_wired_tx.sh                 # all stages
./run_wired_tx.sh layout          # netlist (cells.py) + layout + DRC / LVS + GDS / KLayout
./run_wired_tx.sh sims [job...]   # extracted simulations; WTX_JOBS=n parallel (default 3)
./run_wired_tx.sh evidence        # generated/*-evidence.json and the results table
python3 usbdrv.py                 # pt_usb_txdrv netlist + layout; sim_usbdrv.py = its bench
python3 sim_realring.py block '{"corner":"ss","temp":32,"vdd":3.15,"vring":2.69,"band":1,"vctrl":1.6,"tag":"x"}'
```

Magic layout / DRC / extraction and Netgen LVS run in `svalbard/librelane-gf180-canary:2026.08`; GDS export, KLayout
DRC and ngspice 43 in the pinned `hpretl/iic-osic-tools` image; decks that contain a pad use the pads family's patched
ngspice 47 (`scratch/pad-ngspice47`). Containers run with `--network none`; raw output goes to `scratch/wired_tx/`.

| File | Role |
| --- | --- |
| `cells.py` | transistor-level cells; writes `wiredtx.spice`, `hsbias.spice` |
| `serq4c_macro.py`, `serq4_macro.py` | hand-placed core macro of the published block |
| `layoutgen.py` | row placement and routing of the block around the macro |
| `usbdrv.py`, `sim_usbdrv.py` | USB pre-driver generator and bench |
| `sim_wiredtx.py`, `sim_core.py`, `sim_integration.py`, `sim_static.py`, `sim_hsbias.py` | serializer, core, pad-integration, static / safety and HS-bias benches |
| `sim_ringsrc.py`, `sim_realring.py` | real phase source (extracted ring on its regulated supply) and benches with it |
| `run_all.py`, `evidence.py`, `run_wired_tx.sh`, `tools.py` | orchestration, evidence, docker wrappers |
| `wtx_mux8.py`, `wtx_mux8_layout.py`, `ser8d_macro.py`, `wtx8_top.py`, `wtx8_aux_layout.py`, `pt_wiredtx8_layout.py` | new block: schematics and layout generators |
| `mux8.py`, `mux8_layout.py`, `mux8_layout2.py` | laid-out mux revision 2 (superseded, kept until revision 3 publishes) |
| `serq8_macro.py`, `sim_core8.py`, `cml_ser.py`, `sim_cml.py`, `wtx_fast.py`, `cells_fastpath_wip.py` | unpublished fast-path work |

## Ownership

| Item | Owner |
| --- | --- |
| Serializer, final mux, pre-driver gating, ext-data select, tail-bias DACs, HS bias DAC, USB pre-driver | this family |
| Pad tails / switches, cascodes, terminations, detect, interlock, protection, steering buffers | `analog/pads` |
| Ring PLL and its phases, `pt_diff_clk_rx` | `analog/timing` (wired RX owner) |
| Pattern generator / checker, mode decode, `SER_EN`, bit repetition, USB logic | `rtl` |

## Open items

1. Published `pt_wiredtx`: 2.5 Gb/s fails at ss with the real ring (rows WT29, WT32); no fix in it. Retiring it is a
   pending decision.
2. `pt_wiredtx8`: second layout pass unfinished and the schematic ahead of the layout (table above); nothing of the
   declared limits is closed on final netlists; no pad=RC row passes at ss above 2.7 Gb/s at mux level.
3. Area: bounding box 0.351 mm2 (first pass) against the 0.22 mm2 reserve; parts 0.147 + 0.053 + 0.008, the rest is
   seam and free area. Levers: seam to <= 40 um (-0.05 mm2), L-shaped outline that returns the area beside the mux.
4. Ring: uneven phase spacing in both ring versions (WT33, WT38); phase load of the block (first pass 114-119 fF of
   wire per phase against a 60 fF assumption; the phase buffers are meant to bring the ring's share to about 65 fF).
5. `wtx_ext_rx` fails from 0.5 Gb/s (TIM-08); fallback input relocation OCP-2 undecided.
6. Block-level `safe` / `observable` / `fallback` tests in `generated/wiredtx-evidence.json` are open; `tmds` and
   `wtx_ext_rx` evidence files describe an older netlist.
7. USB: see the open list in `USB-INTEGRATION.md`.
