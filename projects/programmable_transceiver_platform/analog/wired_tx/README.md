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

Not published (must not be instanced): the new fast path `wtx_ser8d` + `wtx_mux8` (below), the earlier eighth-rate
core `wtx_serq8` (`serq8_macro.py`) and the CML pre-driver `wt24_tr7` (`scratch/pads-wt24/`).

## Measured with the real ring and the real pad (`scratch/wired_tx/s12/TRUTH.md`)

Source: extracted `pt_pll_ring_core` on the regulator's output voltage (ss 3.15 V -> 2.69 V, ss 3.50 V -> 3.02 V).
Load: extracted published TX pad, COB bond 2.82 nH / 0.23 ohm, connector, 50 mm line, 100 nF, 50 ohm.
Limit: far end 0 errors over >= 200 bits, eye >= 0.200 V and >= 0.45 UI. Bench `scratch/wired_tx/s12/chain.py`.

| Path | Rate | tt 3.3 V | ss 3.15 V | ss 3.50 V | ff 3.35 V | ss pessimistic 3.15 / 3.50 V |
| --- | --- | --- | --- | --- | --- | --- |
| published `pt_wiredtx` + `tr7` | 2.5 Gb/s | pass (0.73 V, 0.72 UI) | **fail** (44 errors; 23 at the CMD pins) | **fail** (26 errors; CMD pins clean) | pass (0.73 V, 0.78 UI) | not run |
| `wtx_serq8` + CMD stage + `tr7` | 3.125 Gb/s | **fail** (2 errors) | **fail** (20 errors) | **fail** (12 errors) | not run | not run |
| `wtx_serq8` + CMD stage + `tr7` | 2.7 Gb/s | not run | **fail** (13 errors) | not run | not run | not run |
| `wtx_ser8d` + `wtx_mux8` (both extracted) | 2.7 Gb/s | not run | not run | not run | not run | pass at 3.15 V (0.25 V, 0.61 UI) |
| `wtx_ser8d` + `wtx_mux8` (both extracted) | 3.125 Gb/s | pass (0.43 V, 0.77 UI) | pass (0.25 V, 0.59 UI) | not run | pass (0.42 V, 0.78 UI) | **fail** (23 errors) / **fail** (0 errors, 0.148 V, 0.48 UI) |
| `wtx_ser8d` + `wtx_mux8` (both extracted) | 3.24 Gb/s | pass (0.39 V, 0.73 UI) | pass (0.21 V, 0.56 UI) | pass (0.28 V, 0.63 UI) | not run | not run |

Negative controls: one ring phase grounded gives 31 errors / 120 bits on the published block and 24 errors / 120 bits
on the new path.
`wtx_mux8` alone (extracted, ideal phases and streams, same load, 160 bits, screening only): 3.125 Gb/s passes at
tt, ss, ff, sf, fs, ss 3.50 V and ss pessimistic at 3.15 V (0.22 V) and 3.50 V (0.26 V); 3.24 Gb/s ss pessimistic
0.18 V at 3.15 V (fail), 0.23 V at 3.50 V; a stuck stream gives 9 errors (`scratch/wired_tx/s12/mux/corners_x2.log`).

## New fast path (not published)

| Cell | Outline | DRC (Magic / KLayout) | LVS | Files |
| --- | --- | --- | --- | --- |
| `wtx_ser8d`: 40-bit word into 8 streams F0..F7 (registers, /5 divider and hops of `wtx_serq8`, no output tree) | 744.1 x 315.1 um = 0.234 mm2 | 0 / 0 | unique | `ser8d_macro.py`, `generated/fast/wtx_ser8d.*` |
| `wtx_mux8`: 8-phase one-hot muxing pre-driver, drives the pad's MAIN / POST switch gates | 291.0 x 148.3 um = 0.043 mm2 | 0 / 0 | unique | `mux8.py` (circuit in its docstring), `mux8_layout.py`, `mux8_layout2.py`, `scratch/wired_tx/s12/layout/out2/` |

* Bit windows run from the rising edge of phase k to the rising edge of phase k + 1, so the ring's duty cycle does
  not enter; no one-bit pulse passes through a CMOS gate. Slice k takes stream (k + 5) mod 8.
* A 3-bit delay trim per phase corrects the ring's phase spacing (errors up to -44 / +70 ps at ss); the codes used
  are hand-derived and the range has no margin.
* Supply current of `wtx_mux8`: 22-28 mA with MAIN only (ss ... ff), about 44-52 mA with POST enabled, 6 mA disabled.
* It would replace the output tree, the CMD stage, the four steering buffers and `tr7`, and can serve every line
  rate (lower rates by oversampling in the digital), which would retire the quarter-rate core.
* Independent review (`scratch/wired_tx/s12/review/REVIEW.md`): layouts verified from the GDS on disk; `wtx_mux8`
  not ready to publish, `wtx_ser8d` publishable with conditions.

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
| `mux8.py`, `mux8_layout.py`, `mux8_layout2.py`, `ser8d_macro.py` | new fast path: schematic, layout and data macro generators |
| `serq8_macro.py`, `sim_core8.py`, `cml_ser.py`, `sim_cml.py`, `wtx_fast.py`, `cells_fastpath_wip.py` | unpublished fast-path work |

## Ownership

| Item | Owner |
| --- | --- |
| Serializer, final mux, pre-driver gating, ext-data select, tail-bias DACs, HS bias DAC, USB pre-driver | this family |
| Pad tails / switches, cascodes, terminations, detect, interlock, protection, steering buffers | `analog/pads` |
| Ring PLL and its phases, `pt_diff_clk_rx` | `analog/timing` (wired RX owner) |
| Pattern generator / checker, mode decode, `SER_EN`, bit repetition, USB logic | `rtl` |

## Open items

1. 2.5 Gb/s fails at ss with the real ring in the published block (duty cycle; at 3.50 V the block's CMD outputs
   are clean and the pre-driver + pad fail). No fix in the published block (row WT29, WT32).
2. New path: 3.125 Gb/s fails at the pessimistic values in the real chain (23 errors at 3.15 V, eye 0.148 V at
   3.50 V; 2.7 Gb/s passes at 3.15 V); cause
   of the errors not yet found. Review conditions open: trim range and calibration, POST bank evidence, stopped-clock
   interlock, supply impedance, mismatch, 3.24 Gb/s at the pessimistic values (rows WT32-WT35).
3. No block top for the new path (tail DACs, idle, fallback slice, CMOS tap for the USB pre-driver).
4. Area: new path 0.278 mm2 against the 0.22 mm2 reserve; net of the parts it retires (quarter-rate core macro
   0.158, four steering buffers 0.035) +0.085 mm2.
5. `wtx_ext_rx` fails from 0.5 Gb/s (TIM-08); fallback input relocation OCP-2 undecided.
6. Block-level `safe` / `observable` / `fallback` tests in `generated/wiredtx-evidence.json` are open; `tmds` and
   `wtx_ext_rx` evidence files describe an older netlist.
7. USB: see the open list in `USB-INTEGRATION.md`.
