# Wired receive family (`analog/wired_rx`)

Wired receive chain: pad control, equaliser, sampler bank, capture front end, clock-phase trim, line
detectors and the analog cell of the CDR. **Not qualified.** With the real neighbours connected the published
chain does not receive at 2.5 Gb/s or above; the fixes are staged and none is published (see Staged
candidates and Open items 1 to 4).

This file describes what is published in `generated/` and committed. Pin-level bindings are in `PINS.md`
and `integration/top/pt_chip.conn` (the one connectivity source). Risks are in `spec/risk-register.md`
(WRX-01..WRX-23); this file only cites IDs.

Operating window for every performance statement: junction 22–32 °C, die supply 3.15–3.35 V, all process
corners; slow dies may be trimmed up to a 3.50 V setpoint.

## Blocks

Outline, device count and DRC/LVS state are from `generated/<block>-layout.json`; the KLayout precheck
record `generated/<block>-kldrc.json` carries the sha256 of the published GDS (all eight records match
their GDS). Every block: Magic DRC 0, Netgen LVS unique, KLayout GF180 DRC 0. A version is given where the netlist
header, layout record or evidence carries one.

| Block | Cell | Version | Outline µm | Area mm² | Devices | Island | Evidence |
|---|---|---|---|---|---|---|---|
| Pad termination control and bias | `pt_termination` | r3 | 141.1 × 341.9 | 0.048 | 142 | wired_rx | `termination-evidence.json` |
| Pad divider/bypass control | `pt_rxlevel` | – | 77.7 × 169.5 | 0.013 | 70 | wired_rx | `rxlevel-evidence.json` |
| Equaliser | `pt_ctle` | r3 | 224.6 × 594.3 | 0.133 | 260 | wired_rx | `ctle-evidence.json` |
| Slicer input selector | `pt_rxselect` | – | 63.2 × 139.8 | 0.009 | 26 | wired_rx | `rxselect-evidence.json` |
| Sampler bank | `pt_slicer` | r7 | 300.8 × 367.3 | 0.110 | 776 | wired_rx | `slicer-evidence.json` |
| Edge-sampler threshold DACs | `pt_vthdac` | r7 | 140.4 × 170.1 | 0.024 | 166 | wired_rx | `vthdac-evidence.json` |
| WMON source selector | `pt_wmon_sel` | – | 72.4 × 135.8 | 0.010 | 47 | wired_rx | `wmon_sel-evidence.json` |
| Line detectors | `pt_detect` | r7 | 251.3 × 690.4 | 0.173 | 424 | wired_rx | `detect-evidence.json` |
| Clock-phase trim | `pt_ptrim` | – | 449.2 × 645.0 | 0.290 | 576 | wired_cap | none |
| Capture front end | `pt_wrx_cap` | r6 | 1454.3 × 658.1 | 0.957 | 28 instances of 9 cells | wired_cap | stale (Open item 4) |
| CDR integral path | `pt_cdr` | r13 | 259.2 × 319.8 | 0.083 | 488 | pll | `cdr-evidence.json` |

Blocks owned elsewhere that complete the receiver: the RX ring `pt_pll_ring` (instance `pll_cdr`) and the
word divider `pt_wordclk` (instance `wordclk_rx`) in `analog/timing/`; the ring regulator `pt_pll_vreg2` in
`analog/pll_vreg/`; the pads `pad_hspad` and `pad_wirepad` in `analog/pads/`; the observation buffer
`pt_bb_tap` in `analog/rf_rx/`; the control logic `rtl/pt_wrx_ctl.sv` in the digital macro.

## Architecture

```
WIRE_RX_P/N -> pad_hspad (on-die AC coupling, HS termination) -> pt_ctle ----+
USB_DP/DN   -> pad_wirepad (termination, divider/bypass) --------------------+-> pt_rxselect -> pt_slicer -> pt_wrx_cap -> macro
                         |-> pt_detect, pt_wmon_sel                                               ^             |
                                                    pll_cdr PH0..7 -> pt_ptrim -> CKP0..7 --------+             | UP/DN votes
                                                    pll_cdr <- FU/FD (proportional) <---------------------------+
                                                    pll_cdr VCTRL <- pt_cdr (integral) <------------------------+
```

- **Two input pairs.** The high-speed pair feeds the CTLE only. The USB pair feeds the direct branch of
  `pt_rxselect`, `pt_detect` and `pt_wmon_sel`. The HS input is observable through `wire_ctle_bypass` and the
  WMON selector's CTLE taps. There is no signal detector on the HS pair.
- **Sampling.** Eight PMOS-input StrongARM samplers on the eight 45° ring phases: `D0@CKP0, E0@CKP1, D1@CKP2,
  E1@CKP3, D2@CKP4, E2@CKP5, D3@CKP6, E3@CKP7` (`E_i` is the edge sample after `D_i`). Bits per ring cycle are
  selectable: 4 (quarter rate), 2 (half), 1 (full, 8× oversampled with a phase picker). The ring runs
  480–810 MHz. The same bank is the USB 2.0 HS receiver (input common mode about 0.2 V, direct branch).
- **Clock path.** Ring phases `PH0..7` pass through `pt_ptrim` (per-phase 5-bit delay trim) to `CKP0..7`,
  which clock the slicer and the capture. `wordclk_rx` divides `CKP0` and gives the capture its word boundary
  `LDE`.
- **CDR.** No phase interpolator and no nA charge pump. The capture makes per-bit Alexander votes
  `UP0..3/DN0..3`. Proportional path: the votes drive the ring's fast-tune inputs `FU0..3/FD0..3` directly
  (gain set by the ring's `KP[2:0]`). Integral path: `pt_cdr` steers always-on half currents with the votes
  into an RC node and a PMOS-input OTA drives the ring's `VCTRL`. With `pfd_mode = 0` `pt_cdr` holds the ring's
  own PFD (`HOLD_PLL`) and the frequency loop in `pt_wrx_ctl` pulses `FUP/FDN` from a frequency counter until
  the ring is inside the capture range of the votes. With `pfd_mode = 1` the ring locks to `REF_PLL` as a
  plain line PLL and the `pt_cdr` output is off.
- **Forwarded clock.** The forwarded wire clock arrives on the AUX_CLK pad pair (`rx_aux_clk`, debug
  island, then an isolation clamp) and reaches `pt_cdr.WCK_IN` and `clockmux.WCK`. `ref_sel` selects it as the
  ring reference. There is no dedicated WCLK_IN pad, receiver or `obs_pre4_wclk` prescaler.
- **Observation.** `pt_wmon_sel` selects RX_P, RX_N, CTLE_P or CTLE_N onto the shared WMON buffer. ATB taps:
  `atb_ctle_pbias`, `atb_ctle_src`, `atb_det_vref`, `atb_cdr_pbias`, `TERM_VCM`, the ring's `VCTRL`.

## Per-block interface and verified results

Pin order of every cell is its `.subckt` line (`<block>.spice`; for the capture
`generated/wrx_cap.lvs.spice`). Unless stated, numbers are from the extracted netlist at tt/27 °C/3.3 V with
the range over the 12 corners tt/ss/ff × 22/32 °C × 3.15/3.35 V in brackets, as recorded in the block's
evidence file. All block benches use ideal neighbours (150 fF loads, ideal clocks, ideal sources); see
Open item 1 for what changes with the real ones.

### `pt_termination` r3

| Control | Function |
|---|---|
| `term_en`, `term_mode[1:0]` | USB pair: 00 off, 01 shunt to `TERM_VCM` 1.2 V, 10 100 Ω differential, 11 shunt to VSS (USB HS 45 Ω to ground) |
| `hs_en` | HS pair bias on: `HS_TERM_VCM` and `HS_VBIAS` (CTLE input common mode behind the pad capacitor) |
| `hs_term_en`, `hs_trim[3:0]` | `HS_TERM_ENABLE = hs_en & hs_term_en`; `HS_TERM_TRIM = hs_trim & HS_TERM_ENABLE` (register reset code 5) |

Results: `TERM_VCM` 1.225 V (1.16–1.25); USB ground switch 1.98 Ω (1.80–2.24); `HS_TERM_VCM` 0.452 V and
`HS_VBIAS` 0.997 V at nominal; supply 1.25 mA (1.00–1.56) in divider mode. The termination resistors are in
the pads.

### `pt_rxlevel`

`rxlevel_en`, `rxlevel_half` → `DIV_ENABLE`, `BYPASS_ENABLE` of the USB pad (off / bypass / divide by two),
with hardware break-before-make: gap 6.5 ns bypass→divider (5.5–8.3) and 7.0 ns divider→bypass (5.9–8.8).

### `pt_ctle` r3

Source-degenerated PMOS-input stage, 2 × 2.5 mA tails, 480 Ω loads to VSS, bias 10 µA sunk at `IBIAS`.

| Control | Function |
|---|---|
| `ctle_en` | amplifier on |
| `ctle_peak[2:0]` | degeneration code, 0 flat … 7 most peaking |
| `lf_zero[2:0]` | switches a capacitor bank onto the source nodes: low-frequency zero for long-tail channels (0 = off) |
| `wire_ctle_bypass` | amplifier off, transmission gates connect RX to CTLE output |

Results into a 150 fF bench load: DC gain +3.1 dB at code 0 (2.7–3.5) and +1.4 dB at code 1 (1.1–1.8);
peaking 6.4 dB at code 3 (6.1–6.6) and 15.7 dB at code 7 (nominal); gain at 1.25 GHz +2.2 dB at code 1
(1.7–2.5); gain at 2.5 GHz −2.0 dB at code 3 (−2.8 to −1.2); `lf_zero` codes 1…7 at peak code 7 move the zero
from 20.9 to 4.9 MHz (nominal); bypass −1.0 dB at 1.25 GHz, bandwidth 2.46 GHz (2.08–2.74); supply 4.9 mA
(4.3–5.3). Input common mode below about 0.5 V is out of range (use the direct branch).

### `pt_rxselect`

`rxselect_en`, `rxselect_direct`: transmission-gate 2:1 mux onto `SL_P/N` (0 = CTLE output, 1 = USB pair);
disabled = both open, `SL_P/N` clamped to VSS. Bandwidth into 150 fF: CTLE branch 2.43 GHz (2.01–2.75),
direct branch 3.01 GHz (2.67–3.30); off isolation −34 dB at 1 GHz.

### `pt_slicer` r7 and `pt_vthdac` r7

Compact cells `ws_sa` (data samplers), `ws_sae` (edge samplers with an auxiliary threshold pair), `ws_ctl`,
`ws_aux` in `generated/fast/`. Per sampler ten static trim bits `trim_<d|e><0..3>_{p0..2, n0..2, f0..3}`
(coarse per side, fine). Each edge sampler selects a threshold source with `vsel_e<k>_[1:0]` from the two
8-bit DACs of `pt_vthdac` (`A[7:0]`, `B[7:0]`, outputs `VTAP/VTAN`, `VTBP/VTBN`). `slicer_en = 0`: tail
headers off, outputs low. `QCK` is a buffered `CKP0` (unused at chip top).

Slicer results (open loop, ideal 45° clocks, ideal `SL_P/N` sources at 1.0 V common mode, 200 mVppd; run at
nominal, ss/32 °C/3.15 V and ff/22 °C/3.35 V only):

| Check | Result |
|---|---|
| Ring 480/625/810 MHz × quarter/half/full (0.48–3.24 Gb/s) | 0 errors at the three corners |
| USB HS 480 Mb/s, CM 0.2 V, 400 mVppd | 0 errors at the three corners |
| 60 mVppd with fixed trim at 3.24 Gb/s (non-gating) | 0 errors nominal and ff, 3 errors at ss/32 °C/3.15 V |
| Untrimmed offset, worst of eight | −3.8 mV (−4.6 to −2.8) |
| Coarse trim codes p3 / n3 (sampler D0) | −32.6 mV / +27.4 mV |
| Coarse trim codes p7 / n7, worst of eight | −76.3 mV / +68.6 mV |
| Power at 3.24 Gb/s | 29.6 mW (23.8–32.2) |

`pt_vthdac` results (extracted, 700 fF per output line): differential output ±1.43 V full scale, LSB 11.2 mV
at the DAC output (10.0 ss, 11.9 ff), 0→255 settling 41.9 ns (limit 50 ns), supply 0.52 mA.

### `pt_detect` r7

Four clocked PMOS-input comparators sampled on `det_clk`: `DIFF_POS`, `DIFF_NEG` (differential threshold
`det_thr[1:0]`) and `SE_P`, `SE_N` (single-ended threshold `det_se[1:0]`: 0.8 / 1.125 / 1.4 / 2.0 V).
`det_src_tx = 1` senses the wired TX pads instead (receiver detection) and `det_inject` sources a test
current into each TX pad. Line state, SE0 and timing are RTL.

| Check | Result |
|---|---|
| Thresholds, codes 1 / 2 / 3 (nominal) | 66 mV / 116 mV / 566–576 mV |
| USB HS squelch (`det_thr = 2`): fires at 150 mV, silent at 100 mV, line CM −0.05 / 0.2 / 0.5 V | pass at all 12 corners |
| USB HS disconnect (`det_thr = 3`): silent at 525 mV | pass at all 12 corners and CM values |
| USB HS disconnect: fires at 625 mV, CM −0.05 / 0.2 / 0.36 V | pass at all 12 corners |
| USB HS disconnect: fires at 625 mV, CM 0.5 V | **fails**: fire fraction down to 0.31 at the worst corner |
| Receiver-detect current | 118 µA (96–130) per leg |
| Supply | 2.2 mA (2.0–2.4) |

### `pt_wmon_sel`

`wmon_en`, `wmon_sel[1:0]`: 00 RX_P, 01 RX_N, 10 CTLE_P, 11 CTLE_N → `WMON_IN`. Bandwidth into 300 fF: 0.85 GHz
(RX taps), 0.67 GHz (CTLE taps). Off loading 40 fF on RX_P, 38 fF on CTLE_P.

### `pt_ptrim`

Eight channels `PHk → CKPk`: NAND(`PHk`, `ptrim_en`), a trim node with 5-bit binary switched MOS capacitors
(`T<k>_[4:0]`), three inverters. `ptrim_en = 0`: every `CKPk` low. The published layout is DRC/LVS clean but
has no evidence file and does not work with the real clock loads (Open item 2).

### `pt_wrx_cap` r6 (contract)

Fast-cell capture (`capture.py`, cells `wc_*` in `generated/fast/`): re-captures the eight sampler outputs,
assembles 20-bit data and edge words, makes the phase-detector votes and gears to 40 bits.

| Signal | Dir | Meaning |
|---|---|---|
| `S0..S7` | in | slicer D0, E0, D1, E1, D2, E2, D3, E3 |
| `CKP0..7` | in | trimmed ring phases; external-clock fallback: `CKP0..3` = CK, `CKP4..7` = !CK (no route for it exists at chip top) |
| `EN` | in | 0 = internal clock low, flops reset, outputs 0 |
| `LDE` | in | one-period pulse per word from `wordclk_rx`; fixes the word boundary |
| `RCS` | in | re-capture select: 1 re-captures the sampler outputs one ring period later |
| `B2`, `B1` | in | bits per ring cycle: 00 quarter, 10 half, 01 full |
| `PSEL[2:0]`, `SLIPP`, `SLIPM` | in | full rate: data phase and slip tags from `pt_wrx_ctl` |
| `DW0..19`, `EW0..19` | out | data and edge words, bit 0 oldest (`DW` unused at chip top) |
| `SLP`, `SLM` | out | slip tag of the current word |
| `UP0..3`, `DN0..3` | out | per-bit early/late votes, one ring cycle wide |
| `DX0..39`, `WCLK40` | out | 40-bit word and line/40 clock; the macro samples `DX` on `WCLK40` rise |

`LDE` must be synchronous to `CKP0` with a fixed phase: an `LDE` edge that lands on the capture clock edge can
seed a word twice (cell bench in `scratch/wired_rx/r10cap/STATUS.md`; Open item 4).

### `pt_cdr` r13

Integral path of the CDR, on the pll island; 32 pins.

| Pin | Function |
|---|---|
| `cdr_en` | 0 = all currents off, output open and clamped, `REF_PLL` low, `HOLD_PLL` high |
| `pfd_mode` | 0 wired CDR (ring PFD held), 1 line PLL |
| `ref_sel` | `REF_PLL` = `WCK_IN` (1) or `REF_IN` (0) |
| `g[2:0]` | OTA gain (integral rate) |
| `UP0..3`, `DN0..3`, `FUP`, `FDN` | votes from the capture; frequency-loop pulses (2 votes each) |
| `otr[4:0]`, `otrs` | OTA offset trim and sign, static, 0 = untrimmed |
| `VCTRL` | to the ring's `ATB_VCTRL` |
| `IB_PLL` | spare 10 µA bias output, left open at chip top |

Results (`cdr-evidence.json`, extracted, tt/27/3.25, ss/32/3.15, ff/22/3.35 and pessimistic ss):

| Check | tt | ss | ff | pessimistic ss | Limit |
|---|---|---|---|---|---|
| Output current change over `VCTRL` 0.8–2.2 V | 0.083 | 0.073 | 0.099 | 0.073 | < 0.15 |
| Current per vote at `g = 7`, nA | 21.8 | 22.6 | 20.4 | 22.6 | – |
| Idle offset, votes | 0.07 | 0.05 | 0.11 | 0.05 | < 0.25 |
| Ring-rate votes, expected +2 / −2 / +1 / 0 | 1.64 / −1.79 / 0.78 / −0.12 | 1.62 / −1.76 / 0.79 / −0.11 | 1.65 / −1.82 / 0.77 / −0.12 | 1.55 / −1.85 / 0.69 / −0.20 | within 0.45 × max(1, expected) |

Offset trim: LSB 0.13 vote, range ±2.67 (ss) to ±3.05 (ff) votes; the trim compresses the vote gain (93 % at
code 8, 76 % at 16, 37 % at 31), so a die needing more than about code 12 should be flagged. Idle supply
216.6 µA. A negative control (the r10 extraction) fails the same bench.

## Flow

```
./run_wired_rx.sh                                  # all blocks, corners, evidence; then run_capture.py
./run_wired_rx.sh --blocks ctle --no-corners       # one block
python3 run_capture.py [--no-layout] [--assess-only] [--only CASE ...] [--results STORE]
python3 run_fallback.py [--only CASE ...]          # external clock -> slicer -> capture, extracted
```

`run_wired_rx.sh` → `run_family.py`: schematics (`netlists.py`), Magic layout, DRC and extraction, Netgen
LVS, GDS export and KLayout GF180 DRC, extracted ngspice at nominal and the 12 corners, safety cases,
evidence JSON. Tools run in pinned containers without network; raw output goes to `scratch/wired_rx/`.
The flow writes into `generated/`. **Do not run it for `ctle`, `rxselect`, `detect` or `ptrim`**: their committed
sources are the staged candidates, ahead of the published cells, and `sims.py` / `evidence.py` still describe
the published pins and loads.

| File | Role |
|---|---|
| `netlists.py` | schematic generator, writes `<block>.spice` |
| `wrx_flow.py` | row layout generator, DRC/extraction/LVS, GDS export, ngspice runner |
| `sims.py` | testbenches (same bench for schematic and extracted) |
| `run_family.py`, `evidence.py`, `run_wired_rx.sh` | orchestration and evidence |
| `slicer_compact.py`, `wrx_compact.py` | compact sampler cells and slicer assembly |
| `capture.py`, `run_capture.py`, `run_capture_rs.py` | capture cells, top, benches (ideal samplers; real slicer) |
| `ptrim_compact.py` | compact `pt_ptrim` layout (staged, not in `run_family.py`) |
| `run_fallback.py` | external-clock raw-word bench |
| `pkg_channel.py`, `pkg_qual.py` | package channel as SPICE and the CTLE eye bench through it |
| `cdr_model.py`, `cdr_pi_model.py` | behavioural CDR loop models (sizing only; `generated/cdr-model.json`) |
| `rtl/` | retired word-domain CDR logic (Open item 9) |

## Staged candidates (not published)

Nothing below is in `generated/`; the chip top still binds the published cells. Sources of all four are
committed (`netlists.py`, `ctle.spice`, `rxselect.spice`, `detect.spice`, `ptrim.spice`, `ptrim_compact.py`,
`capture.py`). Work directories, benches, declared limits and logs: `scratch/wired_rx/r11/STATUS.md`
(owner), `r10ctle/`, `r10ptrim/`, `r10detect/`, `r10cap/`; independent reviews in `r11/review/`.

| Candidate | Staged at | Outline µm | Layout checks from the GDS on disk | Why not published |
|---|---|---|---|---|
| `pt_ctle` r4 (source-follower output drives `SL` directly) | `r10ctle/stage/gen` | 203.4 × 423.6 | DRC 0, LVS unique without property errors (author and reviewer), precheck 0 / 0 | Review NO-GO: gain and `SL` common mode depend on bias current × load resistance (−1.3 to −6.7 dB at 1.25 GHz with a slow resistor and an absolute 10 µA bias); with metal resistance extracted the chain loses 0.3–1.1 dB; isolated wells need deep n-well (INT-30) |
| `pt_rxselect` r2 (equaliser branch removed) | `r10ctle/stage/gen` | 47.6 × 84.1 | as above | Port change: only together with `pt_ctle` r4; pass path 41–54 Ω per leg with resistance extracted |
| `pt_ptrim` r10 (channel 0 doubled, trim split over two nodes) | `r10ptrim/final/gen` | see `r10ptrim/STATUS.md` | DRC 0, LVS unique incl. read-back, precheck 0 / 0 | No resistance-aware extraction, matrix incomplete, no independent review |
| `pt_detect` r10 (ratio-set thresholds, HS signal detect) | `r10detect/stage/q27/gen` | 167.1 × 541.1 | DRC 0, LVS unique incl. read-back, three negative controls, precheck 0 / 0 | Supply and ground are single 0.44 µm trunks (median 50 Ω to the device sources); fails at the pessimistic slow corner at 3.15 and 3.50 V; USB HS with the real pad and the HS signal detect on the real chain not run |
| `pt_wrx_cap` r7e (compact; `LDE` edge detect, stronger clock drivers) | `r10cap/r7e/gen` | 1241.2 × 242.2 | DRC 0, flat LVS 4856 = 4856 devices without property errors, width control caught, precheck 0 / 0 | Fails a gating case of its own flow (full rate); review GO with conditions |

Chain results with real neighbours (`scratch/wired_rx/r11/chain/tran.json`, `capb.json`, `clk.json`): transmitter 120 mVppd →
chip-on-board → republished `pad_hspad` (resistance-aware model) → `pt_ctle` r4 → sampler bank, clocked by
the extracted ring's phases (settled, replayed) through `pt_ptrim` r10; capacitance-only extractions of our
own cells. Eye at `SL` in mVppd / width in UI at 60 mVppd, wrong decisions on the data samplers.

| Rate (mode, ring) | tt/27/3.30 | ss/32/3.15 | ss/32/3.50 | ff/22/3.35 | ss pessimistic 3.15 | ss pessimistic 3.50 |
|---|---|---|---|---|---|---|
| 0.48 Gb/s (full, 480 MHz) | not run | not run | not run | not run | not run | not run |
| 1.25 Gb/s (half, 625 MHz) | not run | 109 / 0.80, 0 of 108: pass | not run | not run | not run | not run |
| 2.5 Gb/s (quarter, 625 MHz) | 109 / 0.63, 0 of 112: pass | 108 / 0.53, 0 of 112: pass; capture r7e behind the real sampler bank and clocks: 0 errors in 200 bits | not run | not run | 94 / 0.43, 0 of 112: pass (the capture alone fails at this bound) | not run |
| 2.7 Gb/s (quarter, 675 MHz) | not run | not run | not run | not run | not run | not run |
| 3.24 Gb/s (quarter, 810 MHz) | 103 / 0.45, 0 of 112: pass | 88 / 0.35, 36 of 110 wrong: **fail** (0 of 112 with ideal 50 % clocks: the ring's 0.60–0.63 duty) | 90 / 0.40, 1 of 112 wrong: **fail**, not rescued by the supply trim | not run | not run | not run |

Not run at all: sf / fs, the 6 dB-channel stimulus, uncalibrated trim codes, the high-metal pad, our own cells
with resistance extracted (linear estimate: −5 to −17 % of eye), bench B beyond the one cell and its control.
The eye-at-sampler margins of this bench below 0.15 UI and its error count as a system statement are not
trusted by the bench review (`r11/review/capture/REVIEW.md`): the data phase is placed on a linear-estimate
eye centre, not on the real crossings, and the error count reads the sampler outputs at the best phase.
The eye at `SL`, the trim numbers and the ss 3.24 Gb/s failure are trusted.

## Open items

1. **The published chain does not receive at ≥ 2.5 Gb/s with its real load** (WRX-20): −8.0 dB at 1.25 GHz
   into the sampler bank. The fix (`pt_ctle` r4, `pt_rxselect` r2) is staged and not publishable as it is:
   bias scheme (per-die bias code observed at `SL`, or a regulated output common mode), wider load-return,
   follower-output, tail and input wiring, then resistance-aware extraction, sf/fs and resistor cross
   corners. The equaliser has no spare gain at 1.6 GHz: its peak codes only cut low-frequency gain, so the
   republished pad's extra 1.5 dB comes straight off the eye.
2. **`pt_ptrim` (published) cannot drive the real clock loads** (WRX-21, WRX-15). The staged r10 does; with
   the extracted ring it equalises the eight clock edges to 2–6 ps (ring spread 40–54 ps at the sampler,
   trim range 96 ps at ss 625 MHz but only 61 ps for a need of 54 ps at ss 810 MHz). Its clock duty at
   ss 810 MHz is 0.60–0.63 (the ring's own duty). Supply current 24–31 mA.
3. **2.7–3.24 Gb/s is not received at the slow corner with the built architecture** (quarter rate on a
   675–810 MHz ring, one sampler bank): the eye is open (88 mV) but the sampler bank does not deliver
   decisions at ss/3.15 V on an 810 MHz ring, and the capture's slot-enable chain has no margin above
   625 MHz at the slow corner. The eighth-rate architecture is not designed. The rate × corner table above
   is incomplete (see `scratch/wired_rx/r11/STATUS.md` for what was not run).
4. **Capture**: the published r6 has no current evidence and double-seeds a word for a band of `LDE`
   phases. The staged r7e removes that (one `LDE` phase under 1 ps wide can still drop a word; minimum
   `LDE` width is the period minus 300 ps) and drives its clocks rail to rail, but: full rate is a race
   between the 8:1 phase multiplexer and the slot clock (fails at tt for phase select 0, passes at ff;
   quarter and half rate do not use that path); the pessimistic slow corner fails at ring 625 MHz at 3.15
   and 3.50 V (slot-enable chain); nominal ss/3.15 V at 625 MHz passes on thin margin. 0.48 Gb/s can be
   received in quarter mode at ring 480 MHz with the phase picked in the digital macro (not verified
   end to end). The fix (selected sample registered before the lanes, pipelined slot enables) is a new
   capture revision (WRX-09, WRX-12, WRX-22).
5. **CDR closed loop is not run on r13** (WRX-01): the integral path of r13 is slower than the revision the
   loop was last run on. Also open: mismatch Monte Carlo with trim, the enable/safe sweep, sf/fs corners, the
   source of an idle `VCTRL` drift on the ring side, ring start-up with a slow enable ramp (WRX-23). The
   `cdr.spice` header comment still quotes the trim as "1/8 vote, ±3.9 votes".
6. **`pt_detect`**: the published r7 fails disconnect at 0.5 V line common mode at slow corners and its
   thresholds depend on layout parasitics. The staged r10 fixes both at the nominal corners with a
   supply-dependent threshold code (01 at 3.15 V, 00 at 3.3 V, 10 at 3.50 V) and adds the HS signal detect
   (taps of 5 kΩ on `SL`, not built in any cell), but needs wide supply trunks and a fix for the
   pessimistic slow corner (WRX-08).
7. **Forwarded clock on the AUX_CLK pair**: the 25–810 MHz receiver bench, the 3.1 mm differential route and
   the pad-exclusion rule are not done; the path needs the debug island on.
8. **Stale evidence**: every evidence file except `cdr-evidence.json` hashes flow scripts (`netlists.py`,
   `wrx_flow.py`, `sims.py`, `run_family.py`, `evidence.py`) that have changed since; the block netlists,
   extractions and GDS still match. `slicer-window.json` is a superseded measurement.
9. **Retired RTL**: `rtl/pt_wrx_cdr_loop.sv`, its testbench and `generated/cdr-rtl-check.json` describe a
   control scheme that `rtl/pt_wrx_ctl.sv` replaced; `run_family.py` still runs them.
10. **Not verified at 3.50 V**: no published block has results at the trimmed-supply setpoint.
11. **Package**: `pkg_channel.py` models an earlier chip-on-board assumption and has not been checked against
    `spec/package-channel.md`; return loss and eye through the package are unverified (WRX-04, WRX-05).
12. **Not simulated anywhere**: noise, metastability, BER, jitter tolerance on extracted netlists (WRX-08,
    WRX-14). USB pad termination at ss/ff is outside 45 Ω ± 10 % (owned by pads).
