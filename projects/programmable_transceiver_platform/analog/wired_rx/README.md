# Wired receive family (`analog/wired_rx`)

Wired receive chain, risk-accepted and **not qualified**.  All numbers are
from Magic-extracted netlists (parasitic C) in ngspice; the per-block
`generated/<block>-evidence.json` is the record of truth.

| Block | Function |
| --- | --- |
| `pt_termination` | Termination control and the TERM_VCM common-mode source (resistors are in the pad bank) |
| `pt_rxlevel` | Divider/bypass control with hardware break-before-make |
| `pt_ctle` | CTLE with the `wire_ctle_bypass` switch |
| `pt_rxselect` | Input selector (CTLE or direct) |
| `pt_slicer` | Eight PMOS-input StrongARM samplers on ring phases `CKP0..7`; also the USB 2.0 HS receiver |
| `pt_detect` | Signal/threshold detect, USB HS squelch/disconnect, USB FS/LS single-ended receivers |
| `pt_cdr` | Dual-loop CDR analog cell (hand-over control + weak bang-bang pump on the RX `pt_pll_ring` loop filter) |
| `pt_wmon_sel` | WMON source selector for the shared `bb_tap` buffer |
| `pt_wrx_cap` (`capture.py`) | Fast-cell 1:N capture front end (8 samples per ring cycle → 20-bit data/edge words) |
| `rtl/pt_wrx_cdr_loop.sv` | Word-domain CDR logic (FLL step, bang-bang phase loop, full-rate phase picker, raw mode) |

## Reproduce

```
./run_wired_rx.sh                          # all analog blocks + CDR RTL check + evidence
./run_wired_rx.sh --blocks ctle --no-corners
python3 run_capture.py [--no-layout] [--assess-only] [--only q625 ...]   # pt_wrx_cap only
python3 run_fallback.py [--only fb625 ...]                # WCLK_IN -> slicer -> capture, extracted
```

`run_wired_rx.sh` → `run_family.py`: schematic generation (`netlists.py`),
Magic layout/DRC/extraction and Netgen LVS (`svalbard/librelane-gf180-canary:2026.08`,
Magic 8.3.623, Netgen 1.5.316), GDS export with the analog image's Magic
8.3.678 plus KLayout GF180 DRC, extracted ngspice (`hpretl/iic-osic-tools@sha256:89641950…`)
at nominal (tt/27 °C/3.3 V) and the 12-point envelope (tt/ss/ff × 22/32 °C ×
3.15/3.35 V), max-rate sweeps (non-gating), safety cases, the extracted CDR
runs with timing's `generated/pll_ring.ext.spice`, the CDR RTL check
(iverilog + yosys) and evidence JSON.  Containers run `--network none`; raw
output goes to `scratch/wired_rx/`.  With no arguments it then runs `run_capture.py`: the `pt_wrx_cap` compact
cells and top (Magic DRC, Netgen LVS, GDS export + KLayout GF180 DRC) and the
schematic and extracted capture benches (`capture.bench`: ideal ring phases and
ideal sampler outputs, PRBS7, every bit compared) into
`generated/wrx_cap-evidence.json`.

| File | Role |
| --- | --- |
| `netlists.py` | Schematic generator: `<block>.spice` (top `pt_<block>`, gf180mcuD devices only); rejects net names that differ only in case |
| `wrx_flow.py` | Layout generator (compact PCell rows, per-row Metal4 tracks, Metal5 trunks), DRC/extraction/LVS, GDS export, ngspice runner |
| `sims.py` | Testbenches, instantiating blocks by port name (same bench for schematic and extracted) |
| `run_family.py`, `evidence.py`, `run_wired_rx.sh` | Orchestration and evidence |
| `run_capture.py` | `pt_wrx_cap` flow and `generated/wrx_cap-evidence.json` (`--assess-only` re-judges stored runs) |
| `run_fallback.py` | `WCLK_IN` raw-word fallback bench (extracted slicer + extracted capture) and `generated/wrx_fallback-evidence.json` |
| `capture.py`, `wrx_compact.py` | `pt_wrx_cap` cells and top (compact rows from timing's `compact.py`/`fastcells.py` patterns, placed with timing's `layout_engine`) |
| `rtl/` | `pt_wrx_cdr_loop.sv` and its behavioural closed-loop testbench |
| `slicer_compact.py` | `pt_slicer` r2: compact sampler cells `ws_sa` / `ws_ctl` (`generated/fast/ws_*`), macro assembly with timing's `layout_engine`, flat extraction; `netlists.slicer()` emits its flattened intended netlist |

Layout style (all blocks except `pt_slicer` r2 and `pt_wrx_cap`, which are compact rows): single-finger PCells in rows, one Metal4 track per net per row,
Metal5 trunks for multi-row nets, static ports interleaved between switching
ports, StrongARM integrating nodes guarded, one sampler/comparator per row.

## Architecture

Quarter-rate wired clocking with selectable bits per ring cycle (4 quarter,
2 half, 1 full) and no phase interpolator.  The RX ring is a second instance
of timing's `pt_pll_ring` (480–810 MHz, PH0..PH7 at 45°), driving the slicer
`CKP0..7`.

* **Frequency loop:** with `freq_hold=0` the PLL's own PFD/pump locks the ring
  to the reference.  `pt_cdr` supplies its 10 µA bias (`IB_PLL` → `IBIAS`)
  and passes `REF_IN → REF_PLL`.
* **Hand-over:** at the first `FBCK_IN` falling edge after `freq_hold`,
  `pt_cdr` holds `REF_PLL` low and clamps `IB_PLL` together, so the PFD parks
  onto an unbiased pump.  (`pt_pll_ring` r6 has a `HOLD` input; `pt_cdr`
  does not use it yet and the benches tie it low.)
* **Phase loop (half/quarter):** a weak bang-bang pump on `VCTRL`
  (= `pt_pll_ring.ATB_VCTRL`), about ±50 nA (×2 with `bb_gain`), source-side
  switches; the PLL's 20 kΩ gives the proportional path and its capacitors
  integrate.  `pt_wrx_cdr_loop` makes one early/late decision per word.
* **FLL step (`cfg_fll_en`):** after the hand-over the RTL counts ring words
  over 5·2^k reference cycles and pulses `bb_up/bb_dn` for |error|·2^shift
  words per window until |error| ≤ `cfg_fll_tol`, then starts the phase loop.
  The bang-bang loop alone captures about ±2000 ppm.
* **Full rate (480–810 Mb/s, USB HS):** the ring stays locked to the
  reference; 8× oversampling with a blind phase picker (`psel`, ≤ 1 step per
  3 words, hysteresis `cfg_pick_hyst`).  The 3↔4 wrap is reported as a one-bit
  slip (`SLIPP`/`SLIPM` → `SLP`/`SLM`) that the FPGA absorbs.
* **Raw mode (`cfg_raw`):** words pass through without loop action
  (external-clock / FPGA fallback).

### `pt_wrx_cap` contract

The capture front end runs at ring rate in compact fast cells (standard
cells cannot capture at 480–810 MHz at ss).  The word clock comes from
timing's `pt_wordclk`.

Revision r2 (2026-11-09; `capture.py` docstrings carry the reasons):

* **Slot enables are a one-hot chain** of the per-pair `ELQ` flops
  (`ELQ_i <= BQ·ELQ_(i-4) | BH·ELQ_(i-2) | BF·ELQ_(i-1)`, `INJ` seeds slot 0).
  r1's binary /5,/10,/20 counter with a global slot decode took about 1.7 ns
  extracted from counter clock to enable input (slot decode inverters 2/4 µm
  driving 12+ NAND inputs across the macro), more than one 1.6 ns period at
  625 MHz.  Slot 0 and slot 4 then fired in the same cycle and slot 0 fired
  twice, so bits 0–3 and 16–19 were wrong.  The chain has no wrap-around,
  re-seeds every word, and flushes a corrupted enable within one word.
* `LDE` is registered twice (`INJ1`, `INJ`), which keeps r1's LDE → slot-0
  latency and resolves an LDE edge that lands on the capture clock.
* The front `O`/`OP` outputs and the lane `DL`/`EL` outputs have strong
  buffers.  r1 measured 1.1 ns (`O`) plus 1.3 ns (`DL`, NAND3 with a 2 µm
  pull-up driving 5 pairs) and violated setup at the slot clock.
* Each slot flop's own output drives only its clock gate and a buffer.  The
  buffered copy feeds the chain and the cross-cell exports.
* The word-load enable `ELW` is a static mux latch, transparent while CK is
  low, fed by a **local** copy of pair 19's enable in `wc_ctl`.  r1 and r2b
  used a CK-fall flop on the remote `ELQ19`, which needs about half a period:
  at ss extracted it missed words.  r2c's latch on the remote, buffered
  `ELQ19` raised `GW` so late at 810 MHz that it raced slot 0 (bit-0
  errors).
* The word flops `W` have a weak keeper (`QB = NOR(Q, ENB)`, 1/1 µm).  A
  W flop clocks once per word and its TSPC `QB` otherwise floats for 5–20
  periods.  At ss extracted, `EW16` drifted to mid-rail mid-word.  The keeper
  is a NOR with `ENB` so that it agrees with the reset when EN = 0.  r2e also
  kept the slot flops `R`, which slowed R enough to miss the half-period
  R → W hand-off at 810 MHz (pair 16); r2f keeps W only.
* **Slicer-to-capture timing is not closed (open, see Known limitations 0).**
  The front re-captures `S_j` on `CKP(j+4)`, half a period after sampling.
  Extracted `pt_slicer` clock-to-output delay is 0.95–1.28 ns at tt and
  1.24–1.63 ns at ss/32 °C/3.15 V (`scratch/wired_rx/slicer_delay/`, 200 mV,
  2026-11-09).  So the T/2 re-capture is valid only while
  T/2 + hold < delay < 1.5 T − setup.  At tt that means about 590 MHz–1 GHz,
  so 480 MHz fails.  The capture benches drive ideal sampler outputs with a
  300 ps delay and do not see this. (risk: WRX-09)

| Signal | Dir | Meaning / timing |
| --- | --- | --- |
| `S0..S7` | in | pt_slicer D0,E0,D1,E1,D2,E2,D3,E3 (phase order) |
| `CKP0..CKP7` | in | ring phases (pt_pll_ring PH0..7); external-clock fallback: CKP0..3 = CK, CKP4..7 = !CK |
| `EN` | in | 0 = clocks low, every flop reset, outputs 0 |
| `LDE` | in | pt_wordclk LDE (one CK period, once per word); fixes the word boundary |
| `B2`, `B1` | in | bits per ring cycle: 00 quarter, 10 half, 01 full |
| `PSEL[2:0]` | in | full rate data phase from pt_wrx_cdr_loop; applied from the next word |
| `SLIPP`, `SLIPM` | in | full rate: one word, with the PSEL step 3→4 (+1) or 4→3 (−1) |
| `DW0..19`, `EW0..19` | out | data/edge double word, bit 0 = oldest; change once per word and are sampled on `WORD_CLK` rise |
| `SLP`, `SLM` | out | slip of the word on DW (`SLP`: first bit duplicates the previous word's last bit; `SLM`: one bit lost before it) |

Mode mapping: quarter DW = D0..D3, EW = E0..E3 per cycle; half DW = D0, D2,
EW = D1, D3; full DW = phase PSEL (previous cycle for PSEL 4..7), EW = half a
UI later.  Edge k lies between data k and k+1.

## Ports, controls and register-map mapping (proposed)

| Block port(s) | Register field (proposed) | Notes |
| --- | --- | --- |
| `term_en`, `term_mode[1:0]` | `termination.config.*` | 00 off, 01 shunt to TERM_VCM 1.2 V, 10 100 Ω differential, 11 shunt to VSS (USB HS).  No per-leg trim hardware. |
| `rxlevel_en`, `rxlevel_half` | `rxlevel.config.path` | 0 off, 1 bypass, 2 half; break-before-make ≥ 5.7 ns in hardware |
| `ctle_en`, `ctle_peak[1:0]` | `ctle.state.state`, `ctle.config.zero_trim[1:0]` | 2-bit degeneration code |
| `wire_ctle_bypass` | `debug.wire_bypass.ctle` | |
| `rxselect_en`, `rxselect_direct` | `rxselect.state.state`, `rxselect.select.branch` | |
| `slicer_en`, `trim_<s>_{p0,p1,n0,n1}` | `slicer.state.state`, `slicer.offset.*` | 4 bits per sampler phase |
| `det_*`, `det_clk` | `detect.config.*` | 2-bit threshold codes; `det_src_tx` has no field yet |
| `cdr_en`, `bb_gain` | `cdr.config.enable`, `cdr.config.loop_gain_code[0]` | `freq_hold`, `BB_UP`, `BB_DN` from the RTL |
| RTL `cfg_bits_per_cycle`, `cfg_acq_words`, `cfg_raw`, `cfg_bb_invert`, `cfg_pick_hyst`, `cfg_fll_*` | `cdr.config.*` (new fields needed) | |
| `wmon_en`, `wmon_sel[1:0]` | `debug.wmon_select.select` | |

Supplies: `VDD_WIRE_SW`, except `pt_cdr` on `VDD_PLL_SW`.  IBIAS (ctle,
detect, cdr) is 10 µA sunk through an NMOS series switch (no current when
off).  Static control decode is hand-built gates.

### Hookups

* **Pad** (`analog/pads` wired_receive) owns the termination resistors,
  divider/bypass switches and USB pulls; this family drives `TERM_ENABLE`,
  `DIFF_ENABLE`, `TERM_VCM`, `DIV_ENABLE`, `BYPASS_ENABLE`.  `RX_P/N` feed
  ctle, rxselect, detect and wmon_sel.
* **WCLK_IN:** timing's `pt_diff_clk_rx` → clockmux → RX ring PLL reference
  or slicer clocks (integration item).
* **WMON:** rf_rx `pt_bb_tap` (`in_p = WMON_IN`, `in_n = VSS`); an NMOS
  follower, so USB HS levels (0–0.4 V) do not pass.
* **WCLK_OBS:** timing `pt_clk_obs` IN0 = QCK, IN1 = CKP0, IN2 = WCLK_CK,
  IN3 = word_clk.  WDBG_OBS comes from the register-file RTL.
* **ATB:** `atb_ctle_pbias` → `ctle_bias` (24), `TERM_VCM` →
  `termination_vcm` (27), `atb_det_vref` → proposed 28, `atb_cdr_pbias`;
  `VCTRL` is timing's `pll_ring.ATB_VCTRL` tap.

### USB settings

* HS receive: termination 11, rxlevel bypass, `rxselect_direct=1`, slicer at
  480 Mb/s (CM 0.2 V); squelch `det_thr=2` (≈125 mV, window 100–150 mV);
  disconnect `det_thr=3` (536–546 mV extracted, window 525–625 mV).
* FS/LS: `det_se=2` (1.4 V), SE_P/SE_N sampled on `det_clk`; SE0 in RTL.

## Results

Every block: Magic DRC 0, KLayout GF180 DRC 0 on the analog-image GDS, LVS
unique, HRES 62/0 present on every `ppolyf_u_1k`.  Extracted tt/27 °C/3.3 V;
ranges cover the 12-point envelope.

| Block | Devices | Area µm² (ceiling) | Key results | safe / clean / observable / fallback |
| --- | --- | --- | --- | --- |
| termination | 82 | 21 395 (200k) | TERM_VCM 1.225 V (1.16–1.25); USB ground switch 1.98 Ω; 1.0 mA | pass / pass / open / pass |
| rxlevel | 70 | 13 174 (50k) | break-before-make 6.5/7.0 ns (≥ 5.5) | pass / pass / open / open |
| rxselect | 26 | 8 841 (80k) | BW 2.43 GHz (≥ 2.0), direct 3.0 GHz | pass / pass / open / open |
| wmon_sel | 47 | 9 835 | BW 0.85 / 0.67 GHz into 300 fF; off loading 40 / 38 fF | pass / pass / open / open |
| ctle | 77 | 21 437 (200k) | DC gain +0.7 / −0.9 dB (codes 0/1); peaking up to 7.3 dB; −1.0 dB at 1.25 GHz, −4.1 dB at 2.5 GHz (code 3); 4.8 mA; RX_P load 180 fF | pass / pass / open / pass |
| slicer (r2 compact) | 472 | 30 069 (360k) | ring plan 480/625/810 MHz × quarter/half/full and USB HS 480 Mb/s (CM 0.2 V): 0 errors at all 13 extracted points (nominal + 12 corners); 7.4 mA at 3.24 Gb/s; offset +14 mV untrimmed (+12..+15), 4 mV with p0; trim −23..+42 mV | pass / pass / open / open |
| detect | 258 | 96 819 (180k) | code 1 at 66 mV; squelch 125.5 mV; disconnect 536–546 mV; FS/LS line state OK; receiver-detect 103 µA | pass / pass / open / open |
| cdr (analog cell) | 113 | 40 094 (300k) | IB_PLL 9.37 µA in acquisition, 0 in hold/off; BB pump +49.9 / −51.6 nA (+99.5 / −103.6 with bb_gain); off current 0 | pass / **fail** / open / open |
| cdr RTL | yosys generic synth OK | — | behavioural, 18/22 cases pass (below) | — |

**Slicer r2 ring-plan qualification (2026-11-10)** (`pt_slicer` r2, `slicer_compact.py`;
`generated/slicer-evidence.json`; open loop, ideal 45° ring clocks, data centred on clock edge + 100 ps,
all eight samplers checked, 51–65 decisions per run; not a BER).  Gating at nominal and all 12
envelope corners, extracted (flat Magic C extraction): ring 480/625/810 MHz × quarter (1.92/2.5/3.24
Gb/s), half (0.96/1.25/1.62) and full (0.48/0.625/0.81) at 200 mVppd CM 1.0 V, and USB HS 480 Mb/s
(ring 480 MHz full rate) at CM 0.2 V 400 mVppd: **0 errors at every point**; 60 mVppd trimmed (p0)
also 0 errors everywhere (non-gating).  Margin (non-gating `maxrate`): 3.6 Gb/s quarter passes at all
corners (200 mVppd); 4.0 Gb/s fails at ss/22/3.15 and ss/32/3.15 (8/34 errors at ss/22/3.15, 7/34 at ss/32/3.15) and the
60 mVppd 3.6 Gb/s point fails at ss/32/3.15; tt/27 passes 5 Gb/s with ideal clocks.  Window probe
(`generated/slicer-window.json`, 3.24 Gb/s, ss/22/3.15 and tt): data shifted ±0.2/0.3/0.4 quarter-UI
against the assumed instant still 0 errors.  Output: D0 changes 0.47–0.58 ns (ff), 0.59–0.72 ns (tt),
0.69–0.95 ns (ss) after QCK rises (r1: 0.95–1.63 ns) — `pt_wrx_cap`/fallback/CDR benches that use
`slicer.ext.spice` must be rerun against r2. (risk: WRX-03)

Why r1 failed and what changed: r1 passed 3.24 Gb/s at ss as a schematic but failed extracted (18/33
errors at ss/22/3.15; 1/34 even at 1.92 Gb/s).  Probed: ~45 fF routing on each StrongARM output node
and a shared tail header that sagged `vdd_sa` to ~2.87 V delayed regeneration to ~450 ps after the
clock, past the next bit.  r2 keeps the topology (PMOS-input StrongARM, NMOS resets, 2+2 diffusion
trims, NOR SR latch, enable gating) in one hand-placed row per sampler (`ws_sa`, 58 devices, 55.9 ×
33.4 µm) with its own 48 µm header, a faster SR latch (4/4 µm NORs) and a 3-finger output driver
(needed to hold the outputs below 0.1 V against ~12–30 fF clock/ENB coupling of the macro routing
when the bank is disabled with all clocks running; worst 0.087 V).

**CDR extracted runs** (tt; `pll_ring.ext` r5 + `cdr.ext` [+ `slicer.ext`],
analog-behavioural phase detector standing in for the RTL): (risk: WRX-01)

| Run | Result |
| --- | --- |
| `acq_625m` (gating) | Lock 624.59 MHz (−656 ppm), FB−REF 637 ps; hand-over +1430 ppm, then stable; BB UP 100 ns −86 ppm (wrong sign), DN −2080 ppm → **fail** |
| `track_quarter` (gating) | 354 errors / 3424 bits; PD drives DN 41 % vs UP 17 %, ring runs to 611 MHz → **fail** |
| `track_half` (gating) | 33 errors / 1744 bits; ring within +0.3 % → **fail** |
| `dual_quarter_2g5_no_fll` (non-gating) | 579 errors / 3888 bits; ring drifts to 602.5 MHz |
| `dual_half_1g25_no_fll` (non-gating) | 189 errors / 1942 bits |

**CDR behavioural check** (`rtl/tb_pt_wrx_cdr_loop.sv`: RTL + analog loop model,
K_VCO 0.64 GHz/V, R 20 kΩ, C1 9 pF, C2 1 pF, 50 nA pump): 0 errors for
quarter/half at 0/±300 ppm and −5000 ppm SSC, full rate at 0/±500 ppm,
±2000 ppm hand-over steps, and with the FLL at +3.5 % (quarter, half) and
−2 % +300 ppm (quarter) with ±1 nA leak.  Fail: +4000 ppm step without FLL
(quarter, half); half −2 % −300 ppm with FLL (residual at the capture edge);
quarter +3.5 % with FLL during SSC.

**`pt_wrx_cap` (2026-11-09, this pass).**  Extracted capture benches with
ideal ring phases and ideal sampler outputs (300 ps delay), tt/27 °C/3.3 V
unless noted.  DW is data bit errors and EW is edge-word errors; EW was not
checked before r2c, and every r1 result was DW only.  Raw logs are in
`scratch/wired_rx/cap/run_r2*.log`.

| Rev | q480 | q625 | q810 | h625 | f480 psel 0/3/5 | q625 ss/32 °C/3.15 V | q625 LDE on CK edge |
| --- | --- | --- | --- | --- | --- | --- | --- |
| r1 (prior evidence) | 0/200 | 47/200 | 44/200 | 31/180 | 9, 5, 0 /60 | 44/200 | – |
| r2b chain + buffers | 0 | 0 | 0 | 0 | 0 /100 each | **fail**: words missed (20 bits) | 0, 0 |
| r2c + light ELQ, ELW latch | 0/0 | 0/0 | **5/7** (bit 0) | 0/0 | 0/0 each | 0/0 | 0/0, 0/0 |
| r2d + local ELQ19 | 0/0 | 0/0 | 0/0 | 0/0 | not completed | **32/33** (EW16 mid-rail) | 0/0, 0/0 |
| r2e + keepers on R and W | – | 0/0 | **2/4** (pair 16) | – | – | – | – |
| r2f keepers on W only (current) | 0/0 | 0/0 | **0/1** (EW16) | 0/0 | 0/0 (p0, p3, p5) | **2/3** | 0/0, 0/0 |

r2f (the current `capture.py`) finished 2026-11-10 (`scratch/wired_rx/cap/run_r2f.log`,
`generated/wrx_cap-evidence.json`): **clean fail and safe fail**.  Every
schematic bench passes; extracted q480/q625/h625/f480/LDE-edge pass, but
q810 has 1 edge error (EW16, the same pair that failed in r2d/r2e, so the
W keeper did not cure pair 16) and q625 at ss/32 °C/3.15 V has 2 data + 3
edge errors.  The EN = 0 safe case draws 7.9 mA (schematic) / 10.2 mA
(extracted) against 10 µA.  A DC operating point with the ring phases parked
(`scratch/wired_rx/w1/safe/`) shows 1.14 mA static and 5.6 mA at a 62.5 MHz
toggle: the front flops' capture clocks are buffered ring phases that are not
gated by EN, and a TSPC flop whose clock is high while EN = 0 has its reset
NMOS fighting the QB pull-up (the r6 `pll_ring` HOLD-flop failure mode).
Fixed in the W1 working copy below (7.3 nA static).  Cells and top for r2c–r2f: Magic DRC 0,
LVS unique.  Every r2 revision was 0 errors in schematic.  The bench now also
checks EW (EW_k must equal data bit k+1; negative controls fail with 95 and 10
errors), runs an EN = 0 safe case (< 10 µA, outputs < 0.3 V), and reports a
95 % BER bound (3/bits checked, about 0.75 % for 400 bits).  That bound is
weak; it is not a BER qualification. (risk: WRX-12)

**`WCLK_IN` fallback** (`run_fallback.py`, extracted slicer + extracted r2c
capture, half mode, CKP0..3 = CK, CKP4..7 = !CK, eye centred on the CK
edges, 2026-11-09): (risk: WRX-09)

| Case | DW errors | EW ≠ DW |
| --- | --- | --- |
| 480 MHz, 200 mV | 43/180 | 0 |
| 625 MHz, 200 mV | 0/180 | 23 |
| 625 MHz, 100 mV | 0/180 | 0 |
| 810 MHz, 200 mV | 8/180 (bit 0) | 0 |

810 MHz fails on the r2c bit-0 race (fixed in r2d).  480 MHz and the
625 MHz EW mismatches come from the slicer-to-capture re-capture race in
Known limitations 0.  `generated/wrx_fallback-evidence.json` records this
r2c run and is **fail**; rerun after the front fix.

**Evidence currency:** `cdr.spice` (regenerated, now 125 devices,
51,673 µm² in `generated/cdr-layout.json`), `generated/cdr.ext.spice`,
`cdr.gds`, `netlists.py`, `sims.py` and both `rtl/*.sv` changed after
`cdr-evidence.json` and `cdr-rtl-check.json`; `netlists.py`, `sims.py`,
`run_family.py` and `evidence.py` changed after every other evidence file
(the block netlists and layouts themselves match).  Rerun
`run_wired_rx.sh`. (risk: MOD-12)

## W1 r3 and AC-3 status (2026-11-10 resume)

**`pt_wrx_cap` r3 (W1, `capture.py` `front()`):** the W1 working copy in `scratch/wired_rx/w1`
(clock-muxed re-capture plus the PD inside `wc_front`) is **not adopted**: extracted with ideal samplers
it failed q810 with 49 DW / 71 EW errors (`scratch/wired_rx/w1/ext1.log`), the fallback failed at
810 MHz with both RCS values, and the PD inside it never passed extracted (`w1/pd/pd8.log`, 99–112 vote
errors at 810 MHz ss).  r3 keeps r2f's capture path untouched for RCS=0, adds a second front flop per
sampler on its own phase CKP(j) (re-capture one full period after sampling) and a data mux on a
full-period CKP0 path only (docstring has the timeline); every front clock is NAND-gated by EN.
Port `RCS` (binding to the allocated 2-bit `cdr.config.cap_rcsel`: `RCS = cap_rcsel[1]`, see
interface-changes.md W1-r3).  Why RCS=1 is needed: the r2 slicer's clock-to-output is 0.47–0.95 ns, so
the T/2 re-capture (0.62 ns at 810 MHz, 0.80 ns at 625 MHz) lands inside it; one period (1.23 ns at
810 MHz) clears 0.95 ns + setup and the 0.15 ns local clock delay is below the 0.47 ns minimum delay.
Layout: wc_front 1264 devices, 1356 × 45 µm; all cells and top Magic DRC 0, LVS unique.
Simulation results: see the r3 table below (filled in as runs finish). (risk: WRX-12)

**AC-3 loop sizing (`cdr_model.py`, behavioural, not circuit evidence):** PFD held off from enable,
RTL FLL and PD votes on the same pump legs (no hand-over), 4 legs × 32 nA into the existing 20 kΩ /
8.8 pF filter, 6 ring-cycle vote latency.  Linearised BB bandwidth 0.52/1.04/2.08 MHz at 8/16/32 nA per
leg (0.05 UI rms); 4 MHz needs 64 nA.  Model cases (0.02 UI rms RJ, 720k–1.5M bits each): +600 and
−5600 ppm static (FLL residual ±1000 ppm), SSC 0…−5000 ppm with +600 ppm, 40-bit CID, SJ 2 UI at
100 kHz, 0.3 UI at 1.5 MHz, 0.15 UI at 5 MHz: 0 errors (BER < 4.2e-6, 95 %).  Integral slew at full
vote density ≈ 3500 ppm/µs (≥ 400 required).  `generated/cdr-model.json`.

## Resume 3 (2026-11-10, in progress; this section supersedes "W1 r3 and AC-3 status" where they differ)

* **K-fixes regenerated (task 1).** `pt_ctle`, `pt_cdr` (old cell, then r-ac3) and timing's `pt_pll_ring` r7
  were regenerated from the K1/K4-patched generators: Magic DRC 0, Netgen unique, KLayout main 0 / antenna 0
  on each (pll_ring 9 diodes, ctle 4, cdr 10 on the old cell).  The published GDS are flat (no subcells),
  so the `gds_uniquify` prefixing is a no-op on them.  `pt_ctle` extracted nominal + 12 corners + safe
  rerun: pass (evidence regenerated).
* **`pt_wrx_cap` r3a restored and rebuilt.**  `capture.py` had a half-done 2-bit "r3b" edit (7T/8 option)
  that was never laid out; the published r3a (1-bit `RCS`) source was recovered and restored, and r3b is
  parked in `scratch/wired_rx/regen/capture.py.r3b`.  `build_top` did not add the K1 antenna diodes to its
  LVS reference (top LVS "failed pin matching" with 51 diodes); fixed, and the r3a top now has 51 diodes,
  DRC 0, LVS unique, KLayout 0.  The extraction therefore changed: the WCLK_IN fallback runs are being
  redone on it (`scratch/wired_rx/regen/fallback_newcap.log`).  On the pre-diode r3a extraction, RCS=1
  passed 480/625/810 MHz at tt and 480/625 MHz at ss/32 °C/3.15 V (810 ss was not finished).
* **`pt_cdr` r-ac3 (AC-3 loop, netlists.cdr()):** HOLD-free continuous path (HOLD_PLL=1 keeps the RX
  ring's PFD in reset; FLL and per-bit votes share the pump legs), 4 legs × 8–64 nA (3-bit code),
  WCLK_IN/REF select into the ring reference, `pfd_mode` for HDMI/DVI.  Layout: 457 devices,
  199,746 µm² (ceiling 300k), DRC 0, LVS unique, KLayout 0.  Port change: interface-changes.md AC3-W3.
  New benches: `sims.tb_cdr` (static legs, codes, ring-rate vote toggling and UP/DN alternation, which
  exposes switch charge injection), `sims.tb_cdr_ac3` + `run_family.run_ac3` (extracted closed loop).

* **AC-3 pump: vote-rate error (blocking, found by the new `tb_cdr` dynamic cases, schematic tt).**
  Static legs are accurate after balancing the P/N unit widths (UP 8.1/255.6 nA for 8/256 expected,
  DN −65.1/−133.3 for −64/−128, UP+DN all legs −4.5 nA).  But when the votes change every ring cycle
  (625 MHz, the AC-3 operating point) the average current into VCTRL is wrong by **+0.21 … +0.35 µA**
  (alt625 c7/c3/c0: +212/+353/+319 nA, ideal 0; tog625 c3: +365 nA for +64 expected), i.e. 3–40× one
  leg's current.  Probed (`scratch/wired_rx/regen/injdbg`): the 0.6 µA follower cannot hold VDUMP
  against the steering charge (VDUMP 0.91 V vs VCTRL 1.10 V, source nodes swinging 0.70–1.17 V), and each
  toggle shares the source-node charge into VCTRL.  Tighter solver tolerances (reltol 1e-4, gear, 5 ps)
  give the same +340 nA, so it is not numerical.  Tried and rejected: (a) matched complementary drive
  with a cross-coupled pair: +0.22…+0.58 µA; (b) a 10 µA follower with 1 pF on VDUMP: +0.9…+1.6 µA (the
  make-before-break overlap then shorts a stiff VDUMP to VCTRL).  A bang-bang loop cannot absorb an
  offset larger than its full vote current (4 × 32 nA at the default code), so **the r-ac3 pump as built
  cannot close the AC-3 loop** and the extracted AC-3 closed-loop runs (`run_family.run_ac3`) were not
  started.  Not a physical limit: the vote charge (8–64 nA × 1.6 ns = 13–100 aC) is simply far below the
  fC-level charge a 3.3 V switch moves.  Fix candidates, in order: (1) give the CDR its own proportional
  input on the ring (a small fine-tune port in `pt_pll_ring`, e.g. a switched tail-current trim on the
  ring cells driven directly by the votes) so votes no longer have to be nA charge packets on the 20 kΩ
  filter, leaving only a slow integral pump; (2) aggregate votes over M ring cycles before the pump
  (M = 8 cuts toggling 8×, adds 8 cycles of latency); (3) break-before-make steering with cascoded
  sources (source-node C ~1.5 fF instead of ~10 fF).  Estimate for (3) alone: still ~50 nA error at c3,
  not enough. (risk: MOD-12)
* **Capture r4 (AC-3 PD + 40-bit boundary), schematic only so far.**  `capture.py` r4 adds `wc_pd`
  (per-bit Alexander votes UP0..3/DN0..3 from the aligned octet O/OP, registered on CKP1 one ring cycle
  later; quarter/half/full mode select) and `wc_gear` (2:1 after the 20-bit word: `DX[39:0]` = {later,
  earlier word}, `WCLK40` = line/40, DX changes while WCLK40 is high, macro samples on its rise).  Top
  pt_wrx_cap r4: DRC 0, LVS unique, KLayout 0 (51 antenna diodes), 1385 × 631 µm.  The capture bench
  now checks the votes (with edge samples just after each boundary every transition must give UP on
  its leg and no DN, unused legs quiet) and the DX words (consecutive stream words).  PD latency from
  the sampling edge is about 5 ring cycles: **AC-3's ≤ 2 ring cycles is not met** (the loop model passes
  with 6, but the requirement stands). (risk: WRX-11)
* **Phase trim `pt_ptrim` (new block, AC-3 ≤ 3°):** 8 channels PHk → CKPk, NAND + 5-bit binary switched
  MOS caps (~1.8 fF unit) + 3 inverters.  Schematic code sweep at 810 MHz, 150 fF load
  (`scratch/wired_rx/regen/ptrim_sch.json`): monotonic, step 0.80–0.86° (tt), 0.84–0.96° (ss/32/3.15),
  0.72–0.80° (ff/22/3.35), range 26.0/28.4/24.0°, so any error within ±5.7° trims to ≤ 0.5° (schematic;
  not extracted, trim-stage jitter not simulated).
  The generic row layout is DRC/LVS/KLayout clean but **290,000 µm² and not symmetric** (generic
  router on clock nets): not usable as laid out; it needs a compact matched-row layout like the slicer. (risk: WRX-15)

* **Slicer r3 (MT-01, coordinator request):** per-sampler trims (48 ports, 3+3 bits; r2 shared a code between
  the two samplers of a phase pair), dummy NOR balancing the SR-latch load, 0.5 µm balance gate on 2oa.
  `ws_sa` 65 devices, 68.4 × 37.2 µm; top DRC 0, LVS unique, KLayout main 0, **antenna 32** (ANT.3 on the
  in-cell trim runs, the K2 item, was 16).  The SL_P→CKP5 34 fF coupling is **not** fixed (no per-net
  track control in the top router).  The r2 extraction and cells are kept in
  `scratch/wired_rx/regen/slicer_r2_published/`.  Requalification is pending: offsets/trim range and the
  ring plan at nominal (queued, `scratch/wired_rx/regen/queue.log`), then the 12 corners and a run with
  the extracted CTLE driving SL_P/N. (risk: INT-05)
* **Queue (one sim at a time, `scratch/wired_rx/regen/queue.sh`):** slicer r3 extracted nominal → pt_cdr
  r-ac3 extracted unit bench → WCLK_IN fallback on capture r4 + slicer r3 (RCS=1, 480/625/810 MHz tt and
  ss/32 °C/3.15 V, 100 mV).  Capture r4 benches (schematic + extracted: q625, q810/h625 RCS=1, f480,
  q810 ss, EN=0 safe) run first (`cap_r4_benches.log`).  `generated/wrx_cap-evidence.json` written by that
  run still mixes in older r2f/r3a records for the tags it did not rerun.  **First result, schematic q625
  r4: 0 data / 0 edge errors, votes UP0..3 activity 0.46–0.54 and DN 0 (correct sign), 5 DX words all
  consecutive 40-bit pairs.**  The running process judged it fail through a DX-check bug (it compared
  against the shortened DW window); the check is fixed in `capture.py`, so re-judge the stored runs with
  `python3 run_capture.py --assess-only --only <tags>` once the run ends.

* **Package demands (coordinator, spec/package-channel.md), open:** RX RL is 10.0 dB at 1.25 GHz (0 dB margin). The
  demands are 40–60 Ω termination trim (none today), CTLE 0–12 dB (extracted 1.6–8.1 dB today), a wide input CM, and
  qualification at P1–P4 (carrier 2/10/30/50 mm, bond ±0.3 mm; channel ISI 9–12 % at 2.5 Gb/s). No wired_rx bench
  includes the package model yet.  Tracked as interface-changes.md PKG-W1. (risk: WRX-04)

## Resume 4 (2026-11-10, in progress): CDR r-pi architecture (fixes AC3-W8)

* **Architecture (behavioural first, `cdr_pi_model.py`; scratch `scratch/wired_rx/r4pi/`).**  The votes no
  longer go through a nA charge pump.  (P) Proportional: `UPk/DNk` drive a fast-tune port on the RX
  `pt_pll_ring` (r8 `FT` legs: gate-switched tail/replica current legs, one ring cycle per vote, gain from a
  3-bit current `IFT` made in `pt_cdr`).  Switch charge there only gives a static frequency offset,
  which the integral path absorbs.  (I) Integral: two options were modelled.  (a) Decimated sign packets
  (16-cycle sum) on a pump.  (b) **Chosen: continuous analog.**  µA-level differential steering of the
  votes into an RC averaging node (tau ~32 cycles), then a slow saturating OTA into VCTRL.  The steering
  current is ~10–100× the old 8–64 nA legs, so switch injection is a few % vote bias, not 3–40× the
  signal.  Decimated packets of ≥ 10 ppm would need ≥ 50 µA×1.6 ns at the ring rate; the SSC slope
  (333 ppm/µs) rules out nA packets.
* **Model results (decimated integral, ki 10 ppm/16 cycles, `sweep2.json`).**  kp = 150 ppm/vote is
  unstable (cycle slips: integral too strong vs P).  kp = 300 is stable but below the mask at
  0.5–1.5 MHz (0.84–0.94×).  **kp = 600 ppm/vote:** JTOL ≥ 1.13× the mask at every point for latency ≤ 6
  ring cycles, ≥ 1.06× at 8, 0.61× at 5 MHz with 24.  kp = 1200 fails at latency 24 (limit cycle).
  So the latency limit scales as ~1/kp, and AC-3's ≤ 2 cycles is not needed (see item 2 in the report).

* **Model results, chosen analog integral (`sweep_an.json`; tau 32 cycles, OTA full scale 0.8 ppm/cycle =
  500 ppm/µs, kz 88 ppm R-zero term, 0.3-vote injection bias, ring random walk up to 2 ps/cycle, COB ISI
  0.088 UI, 3° trim residual, half-eye 0.42 UI, RJ 0.02 UI).**  Every static/SSC/bias case passes (BER bound
  < 1e-26).  JTOL (× mask, worst point): kp 600 ppm/vote → 1.19 (lat 2), 1.19 (4), 1.09 (6), 1.03 (8), 0.97
  (12, 15 MHz), 0.58 (24, 5 MHz).  kp 300 → 0.92 at 1.5 MHz for any latency (P gain too low).  **Derived
  requirement: PD latency ≤ 8 ring cycles at kp ≥ 600 ppm/vote (≥ 1.03× mask), ≤ 6 for ≥ 1.09×.**  The
  measured ~5 cycles meets it; AC-3's ≤ 2 is not needed.  Proposal for the main session, not applied.
* **pll_ring r8 schematic (scratch `r4pi/pll_r8/pll_ring.spice`, not promoted):** N5/N10 via VCO/2 →
  `ct_div5` (/10; N5 = REF/2 + /10, same trick as N4), and switched-conductance FT legs (`KP0..2` binary,
  `FU0..3/FD0..3`) on the tail (VT) and header replica (VPB).  Sizes pending the Kp bench.

* **pll_ring r8 FT legs, schematic tt/27/3.3 open loop (`r4pi/kp/`, VCTRL 0.9 V, ~462 MHz).**  Three iterations:
  (1) legs on the tail plus header-replica (VPB): **the ring stopped** (the replica-side legs sink µA from the
  1/12 replica diode).  (2) Tail-only: very asymmetric (+1370/−12,500 ppm per vote at code 7, header-limited).
  (3) **Tail NMOS + header PMOS (gate = complement), each unit an 8-device stack 0.22/8×42 µm:** symmetric,
  +2860/−2600 ppm per vote at code 7 and +334 ppm per vote at code 1, so code 2 gives ≈ 600–700 ppm.  Pending:
  ring-rate alternation (average offset), the 625/810 MHz operating points, corners, N10/N5.

## Known limitations and open items

0. **`pt_wrx_cap`: the slicer → capture re-capture phase is not closed.**
   The ideal-sampler benches pass at 480/625/810 MHz from r2b on (table
   above).  The real slicer, however, has 0.95–1.28 ns (tt) and 1.24–1.63 ns
   (ss) clock-to-output delay, and the fixed T/2 re-capture on `CKP(j+4)` is
   valid only for T/2 + hold < delay < 1.5 T − setup.  The fallback bench
   confirms this: 43/180 errors at 480 MHz.  There is no physical limit here.
   The window is T − spread − setup − hold ≈ 0.7 ns at 810 MHz/tt, but its
   position moves through the whole cycle with rate and corner.  Proposed
   fix: a static re-capture select k ∈ {2, 4, 6} (`CKP(j+k)`, T/4 steps
   spanning 0.62 ns at 810 MHz, which is more than the 0.46–0.54 ns forbidden
   zone).  Each sampler's octet-alignment path is chosen by u = j + k: via a
   CKP0 flop for u ≤ 4, via the CKP4 `B` flop for 5 ≤ u ≤ 8 (5 and 9 have
   equal margin either way, as today), direct to `O` for u ≥ 9; the octet
   latency is unchanged.  k is calibrated from raw words.  Two more items
   are pending and open: the `WORD_CLK`-to-word-load offset with the real
   `pt_wordclk`, and the AC-3 40-bit/62.5 MHz boundary (an extra 2:1 stage). (risk: WRX-09)
1. **CDR is not demonstrated end to end extracted** (half/quarter).  Rerun
   2026-11-09 with `pll_ring` r6a extracted (`pll_ring_ext_sha256`
   e0fc5063… in `scratch/wired_rx/cdr-closed.json`): `acq_625m` passes its criterion but the
   hand-over drifts 5883 ppm; `track_quarter` 560/3588 errors, `track_half`
   104/1768, no-FLL dual loops 929/4216 and 193/2046.  Earlier: the
   hand-over step (≈ ±0.4 %) exceeds the bang-bang capture range; the FLL
   that removes it is verified only behaviourally (needs > 100 µs ring time);
   the extracted tracking runs fail.  Suspects: the PD stand-in timing and
   formula, ring port-phase skew, one-word decision latency.  Open: SSC
   acquisition after a hand-over, half-rate FLL margin, lock at corners,
   use of `pt_pll_ring.HOLD`. (risk: WRX-01)
2. **`pt_wrx_cap` r2f evidence pending** (flow running, see above).  The
   capture benches are short (12 words); BER and jitter tolerance are not
   measured. (risk: WRX-12)
3. **Redesigned `pt_cdr` is unsimulated** (see Evidence currency). (risk: MOD-12)
4. Slicer r2: ring plan closed at every corner (open loop, ideal clocks).  Open: margin above the plan is
   thin at ss/3.15 V (4 Gb/s fails); trim range is −23..+42 mV around a +14 mV systematic offset (target
   ±50 mV not met); ring phase error/jitter and the CKPk clock-tree load are not in the bench; the macro
   routing couples 12–21 fF between CKPk and outputs/trims/other phases and **34 fF CKP5→SL_P**: the
   bench drives SL_P/N from ideal sources, so clock kick-back into the CTLE/rxselect output is not
   covered (rerun with the extracted CTLE/rxselect driving SL_P/N, or reroute SL_P/N away from CKP5). (risk: WRX-03)
5. CTLE loses ~4.1 dB at 2.5 GHz; 5 Gb/s is exploration only. (risk: WRX-13)
6. Not implemented: termination trim, 8-bit detect thresholds, test-current
   trim, burst samplers, 96-bin phase bank, holdover, SSC qualification.
   Not simulated: noise, metastability, mismatch Monte Carlo. (risk: WRX-14)
7. Fallback routes `wire_wmon_scope`, `wire_detect_via_wmon`,
   `wire_cdr_external_clock`, `wire_cdr_fpga_oversample` are open
   (integration items); `wire_ctle_bypass` and `wire_board_termination` pass.
