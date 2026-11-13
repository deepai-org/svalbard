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
| `run_capture_rs.py` | Ring-clocked main path with the real slicer: extracted `pt_slicer` + extracted `pt_wrx_cap`, quarter rate, judged by `capture.bench`'s analysis (resume 5) |
| `pkg_channel.py`, `pkg_qual.py` | TT01 COB WIRE_RX channel as SPICE (per-pin LC model, placements P1–P4, bond ±0.3 mm) and the CTLE eye bench through it (PKG-W1, resume 5) |
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

* **r8 iteration 4/5 (same bench).**  Gate-switched stacks: ring-rate vote alternation shifted the ring
  **−6.9 %** (gate charge of ~370 fF stacks into VT/VH, i.e. the AC3-W8 disease again).  With static-gate
  stacks and a minimum switch at the rail end: **alternation +39 ppm** (vs idle) and ±650 ppm/vote at code 7,
  so the injection problem is gone; stacks shortened 8 → 3 devices to put ~600 ppm near code 2–3.
  **Dividers:** `ct_div5` divides by **4** when clocked at VCO/2 = 235 MHz (dynamic TSPC nodes; B falls in the
  clock-low phase).  Standalone it is /5 at 2.13/1.6/1.35/1.23 ns clocks.  So /10 = VCO (ODC, gated and
  buffered as in pt_wordclk) → `ct_div5` → TSPC /2.  **Questionable prior choice:** `ct_div5` has no
  documented minimum clock rate (dynamic logic) and no low-frequency check. (risk: TIM-01)

* **r8 FT final schematic sizing (tt/27/3.3, open loop ~476 MHz):** 8-device static-gate stacks W 0.44 / L 8×42 µm
  with a rail-end minimum switch; code 3: **+567/−547 ppm per vote, ring-rate alternation +11 ppm (0.02 vote)**.
  (3-device stacks: 1020 ppm/vote but alternation +1990 ppm, rejected.)  /10 feedback 9.99 and N5 REF/2 46.875 MHz verified.
  Pending: 625/742/810 MHz points, corners, closed-loop HDMI lock, layout, extraction.

* **Integral path `pt_cdr_int` (draft, scratch `r4pi/cdr_pi/cdr_int.spice`, schematic tt, R_L 50 k):** each vote half-current
  (0.5 µA PMOS) is always flowing and only steered AVP↔AVN, so votes never switch a source on or off.
  Output into VCTRL held at 1.1 V: idle −8.6 nA, static UP×4 +2117 nA, DN×4 −2126 nA, **ring-rate UP/DN
  alternation −8.59 nA (= idle, < 0.01 nA vote-rate error; the r-ac3 pump was +210…+353 nA)**, UP every other
  cycle 100.7 mV = exactly ½ of static (linear).  The AC3-W8 blocker is removed at schematic level.
  Gain issue: the OTA saturated only at ~2.75 votes, and the model then fails SSC (`sweep_circ.json`).  With
  vsat 0.55 vote (R_L 250 k, C/5) every case passes and JTOL ≥ 1.125× the mask at kp 560, latency 5, and
  ≥ 1.09× at latency 8 (`sweep_circ2.json`).  **Design point: KP code 3 (~560 ppm/vote), g = 7 (integral full
  scale ~4.3 µA ≈ 490 ppm/µs).**

* **Integral path retuned (R_L 250 k, C/5, g = 7):** full scale ±4.68 µA (≈ 490 ppm/µs, covers SSC), saturated by 2 votes,
  ring-rate alternation 0.34 nA from idle.  Not yet folded into `netlists.cdr()`; the pll_ring r8 netlist is not
  promoted to `analog/timing/pll_ring.spice` (port change; the LO instance and the timing benches must change together).
* **Capture r4 (running job, `cap_r4_benches.log`): schematic q625/f480/q810_r1 0 errors, but extracted q625 40/200
  data-bit errors and extracted f480p0 1/120.**  This is a real extracted regression (data errors, not the DX-check
  bug).  Re-judge with `run_capture.py --assess-only` when the job ends, then debug (suspect the r4 PD/gear
  load on the octet path).
* **Remaining resume-4 order:** (1) fold `pt_cdr_int` into `netlists.cdr()` (r-pi ports, AC3-W9); 625/742/810 MHz
  and 12-corner Kp/alternation/divider runs; closed-loop schematic CDR with the r8 ring and capture PD; layout of
  ring r8 + pt_cdr r-pi; extraction.  (2) Ring resize (PD9: 810 MHz at ss on ≤ 2.9 V regulated; IX-1: 393–834 MHz
  regulated; gap-free rates incl. 675/750/781 MHz) as one ring r9 change with one regulator per ring.  (3) ptrim
  matched-row layout; slicer Δ-cap fine trim (≤ 2 mV step).  (4) Extracted CDR tracking (±ppm, SSC, JTOL, BER bound)
  with the COB channel at P1–P4.  (5) PKG-W1 (R trim 40–60 Ω, CTLE 0–12 dB, wide CM, package qualification), IX-4.

## Resume 5 (2026-11-10): capture r5, slicer r4, CTLE r2, termination r2, package channel

**Published into `generated/` on 2026-11-10 15:31:** `wrx_cap` r5g (replaced by r5h ~16:50, see below) (`.ext.spice/.lvs.spice/.mag/-layout.json`, and for the
first time `wrx_cap.gds` + `wrx_cap-kldrc.json`), `slicer` r4c, `ctle` r2, `termination` r2; the schematic files
`slicer.spice`, `ctle.spice`, `termination.spice` are regenerated.  The previous files are kept in
`scratch/wired_rx/regen/{cap_r4,slicer_r3,front_r1}_published/`.  Build/staging dirs: `scratch/wired_rx/r5cap`,
`r4slicer`, `r2front`.  Simulation queue (one sim at a time): `scratch/wired_rx/myqueue_master2.sh` (logs next to each step).

### Capture r4 regression: root cause and r5 fix

* **Root cause** (probe `scratch/wired_rx/cap/sim/dbg_r4_q625`, extracted q625): r4 also routed the 20 word outputs
  `DW` to the new `wc_gear` row.  Extracted DW grew from 7–55 fF (r3a) to 165–203 fF, and DW was driven directly by
  the keeper flop's NOR output stage: 1.2–2.0 ns edges after GW and one double switch (DW4 0 → 1 within 0.7 ns).
  EW was not routed to the gear (6–50 fF), hence data errors with zero edge errors.  The lane → slot path was fine
  (DL settled ≤ 0.5 ns after CKP0, GCK at 0.89–1.03 ns).
* **r4 re-judged** (`run_capture.py --assess-only`, stored runs): schematic all pass except safe; extracted q625 40/200,
  f480p0 1/120, h625_r1 36/180, q810_r1 and q810_ss_r1 no word structure (0 words); safe_q625 410 µA schematic /
  543 µA extracted.
* **Other r4 defects found on the way:** (a) the gear never loaded DX extracted: one 2 µm NAND clock per word type
  across the 1.3 mm row filtered the 0.8 ns pulse, and ELWO was a half-period path over ~600 µm; the schematic hid
  both.  (b) The PD votes were registered on CKP1, assuming the octet ~0.5 ns after CKP0.  Extracted, O changes
  1.1–1.3 ns after CKP0 and the XOR of two octet bits glitches for up to ~0.6 ns (probe `dbg_r5f_q625`), so DN was
  active (0.05–0.26) on clean data.  (c) The gear's T flop clock was an inverter of a pulse that is low with EN = 0,
  so the clock sat high and its TSPC reset fought it (+287 µA in the safe state).  (d) The row order loaded CK/CKN
  (162 → 311 / 119 → 260 fF) and the lanes (120 → 200–255 fF).
* **r5g (`capture.py`):** (risk: INT-05)
  * every pair drives DW/EW through a strong buffer;
  * `wc_gear` is clocked only from a private word-load copy `GWT` (from `wc_ctl`) plus 20 inverters (it loads the
    word just written, with a whole word of hold).  The pulse and T are distributed by strong buffers, each 4-bit
    block makes its own NAND clock, and the T-flop clock is NOR-gated with ENB;
  * PD votes are registered `PD_DELAY` = 6 inverters (~1.1 ns) after the next CKP0, through strong buffers.  That
    instant lies in the settled-vote window from 480 to 834 MHz and moves with the corner (see `pd()`);
  * `wc_front` gate groups are mirrored, so the octet stage sits over the lane/PD cells;
  * the lane channel interleaves O with the static PS selects (O–O coupling 107 → 70–81 fF);
  * the gear row is above the pairs.
  **No port change (AC3-W5 stands).**  Top 1426 × 658 µm, Magic DRC 0, LVS unique, KLayout main 0, **KLayout antenna
  22 (ANT.3, in-cell runs: the same K2 class as the slicer's 32; first KLayout antenna run on this macro)**.
* **Results (r5g):** schematic q625 pass.  **Extracted q625: 0/200 data, 0 edge errors, PD votes UP0..3 0.47–0.54 /
  DN 0, all 5 DX words correct: pass** (r4: 40/200).  Safe state: schematic 122.7 µA, the same as the committed
  r3a (122.5 µA schematic / 257 µA extracted), i.e. the r4 excess is gone but the 10 µA limit is still missed;
  extracted 238 µA (r4 543 µA).  Extracted, UP3 also reached 0.6 V with EN = 0 (limit 0.3 V).  Cause: CKP0's new
  trunk to the PD runs beside UP3 (68 fF), which also adds 68 fF to one ring phase.  **r5h** (`scratch/wired_rx/r5h`)
  groups the vote trunks between the static RCS/B2: UP/DN to clock coupling ~0, and CKP0 then sits beside RCS
  (static).  **r5h extracted q625: 0/200 data, 0 edge, PD and DX correct: pass.  Published 2026-11-10 ~16:50**
  (generated/wrx_cap.ext.spice sha256 469357be…; r5g kept in `regen/cap_r5g_published`).  KLayout antenna 22 (ANT.3).
  r5h extracted safe state: outputs ≤ 0.047 V (the UP3 spike is gone), supply 238.5 µA (the pre-existing
  input-toggling current, limit 10 µA: still a fail).  `generated/wrx_cap-evidence.json` is regenerated from the r5h
  runs (q625 and safe only; the other cases are absent, so it reads `clean: fail` until the queue finishes).  This
  is pre-existing (see Questionable choices).  Queued in `myqueue_master2.sh` (status in `r5cap/runcap_r5g.log`,
  `scratch/wired_rx/capture_rs.log`): ext safe, f480p0, q834_r1, q480_ff, and the real-slicer main path
  (`run_capture_rs.py`: extracted slicer r4c + capture r5g on ideal ring phases: rs810_ss_r1, rs834_ss_r1,
  rs480_ff_r0/r1, rs625_tt_r0). (risk: PWR-01)
* `run_capture.py` gains IX-1/hold cases q834_r1, q834_ss_r1, q480_ff, q480_ff_r1.  `run_capture_rs.py` is new: the
  capture benches use an ideal sampler delay (0.3/0.47 ns), but the real slicer is 0.95–1.28 ns (tt) and 1.24–1.63 ns
  (ss).

### WCLK_IN fallback (W1 RCS)

The inherited queue (`regen/queue.sh`) ran the fallback on capture r4 + slicer r3.  fb480_r1 gave 4/200 errors and
fb625_r1 34/180: the r4 DW defect.  fb810_r1 also started on r4.  After the 15:31 publication, its remaining cases
(fb480/625/810_ss_r1, fb625_vd100_r1) copy capture r5g + slicer r4c.  **fb480_ss_r1 (r5g + r4c, ss/32 °C/3.15 V):
0/180, EW == DW: pass.**  fb625_ss_r1, fb810_ss_r1 and fb625_vd100_r1 are still running in that queue
(`regen/queue.log`).  fb480_r1, fb625_r1 and fb810_r1 (tt) are re-run on r5h + r4c by `myqueue_master2.sh`
(`scratch/wired_rx/r5stage/runfb.py`, results `r5stage/fallback_results.json`).  Re-judge with
`run_fallback.py --assess-only`.

### Slicer r4 (MT01-W2)

* **Fine trim:** three bits `trim_<s>_f0..f2` per sampler (+24 ports).  Each bit is an unequal pair of switched
  diffusion caps: base 0.5 µm on `1pa` and 0.5 µm + Δ on `4pb`, so one bit moves the offset by the cap
  difference while every device stays ≥ 0.43 µm wide.  The coarse p/n bits are kept, ×1.1 wider (0.55/1.1/2.2 µm).
* **Iterations, extracted tt, 8 samplers** (`sims.tb_slicer_trim`, 0.2–0.45 mV/decision ramps;
  `scratch/wired_rx/r4slicer/{r4,r4b}/`, current `trim_tt_*`):

  | Rev | Δ (µm) | Fine bit weights (mV) | Max gap (mV) | Range |
  | --- | --- | --- | --- | --- |
  | r4 | 0.1/0.2/0.4 | 4.5/3.9/8.4 | 3.9 | p7 −45.6 mV on e1 (✗) |
  | r4b | −0.02/0.185/0.345 | 2.1–2.7/3.3–3.9/7.2–7.5 | 2.7 | – |
  | r4c | −0.065/0.17/0.30 | – | 1.8 on d0–d3, 2.0 e0, 2.2 e2/e3, 2.4 e1 | −51.6…−55.9 / +64.9…+74.1 mV ✓ |

  In r4, bit 0 carried +2.25 mV of layout asymmetry (its pair sits at the cell edge on one side), so its weight came
  out at 4.5 mV instead of 2.  For r4c the max gap is between achievable codes over ±50 mV, with linear coarse codes.
  **Status: ±50 mV met; ≤ 2 mV met on 5 of 8 samplers, 0.2–0.4 mV over on e1/e2/e3** (at a 0.2 mV measurement
  resolution).  The robust fix is a fourth fine bit (LSB ~1 mV); ss/ff not run yet. (risk: WRX-03)
* **SL_P/SL_N clock coupling (MT-01):**
  * an SL_P/SL_N trunk group flanked by static trims, via a new optional `trunk_groups` argument to timing's
    `layout_engine.generate()` (default unchanged);
  * inside `ws_sa`, static TP0/ENB tracks between CK and INP/INN.

  Extracted clock coupling: SL_P 87 fF (38 fF from CKP5 + ~6 fF from each sampler's own clock) → **4.9 fF; SL_N
  2.5 fF**.  Remaining static imbalance: SL_P 22.5 fF to VDD vs SL_N 4.7 fF.  Outline 191 × 297 µm (r3
  161 × 253).  Magic DRC 0, LVS unique, KLayout main 0, antenna 32 (unchanged K2 item).
* **Real CTLE driving the slicer** (`r4slicer/slicer_ctle.py`, CTLE r2 extracted, code 4, tt, 200 mVppd at the CTLE
  input): ring 810 MHz quarter **0/51**.  At ring 625 MHz with a 60 ps CTLE-delay assumption: 2/68, both on e0
  0.33 UI after an input transition, i.e. the check sat on the delayed transition.  **With the 150 ps CTLE delay:
  0/68.**  The code-0 rerun at 625/810 is queued. (risk: WRX-03)

### PKG-W1

* **(b) CTLE r2** (`netlists.ctle`, +1 port `ctle_peak2`):
  * a 3-bit log-spaced degeneration ladder of 0.4…4.1 kΩ (4.1 kΩ base plus seven thermometer-decoded legs);
  * tail L 0.5 → 1 µm at twice the W/L.  r1's tail sat near triode at ss (input-pair Vsg 1.65 V), and its output
    resistance shunted Rs/2, which is why r1 peaked only 1.6 dB at ss;
  * input pair 48 → 96 µm per side;
  * no source caps (the tail drain capacitance takes their place).

  **Extracted peaking 0.35–0.54 dB (code 0) to 15.0–15.3 dB (code 7) at tt / ss 32 °C 3.15 V / ff 22 °C 3.35 V, steps
  1.4–2.4 dB.  DC gain −11.4…+3.4 dB, gain at 1.25 GHz ≥ +1.5 dB, every `tb_ctle` criterion passes,
  4.3–5.3 mA.**  Outline 149 × 438 µm (r1 105 × 205), DRC 0, LVS unique, KLayout clean.  Input C rises by ~60 fF
  per leg (pad-C budget, IX-3).
* **(c) Common mode.** Schematic window with code 7 still ≥ 12 dB and normal gain: 0.8–1.4 V tt, 0.8–1.2 V ss,
  0.8–1.6 V ff (`scratch/wired_rx/r2front/ctle_cm_schD.json`).  The PMOS pair loses gain below ~0.7 V (drain at the
  ~1.4 V output CM) and the tail runs out of headroom above ~1.3–1.6 V.  For users outside this window, proposed: (risk: WRX-13)
  - optional on-die AC coupling in the pad bank: 10 pF MIM per leg plus 20 kΩ bias to 1.0 V;
  - HPF 0.8 MHz; droop 1 % on an 8b10b run of 5, 6 % on PRBS31's run of 31;
  - a bypass for DC or USB use.

  This needs the pads owner (MIM).  **Bench** (`pkg_qual.py --dc-cm --acc`, P2, code 4, extracted CTLE, 100 Ω
  differential on-die termination): a DC-coupled TX at CM 0 V and at 2.5 V gives the same CTLE eye, 200 mV /
  0.68 UI (board AC caps with shunt termination: 241 mV / 0.70 UI), so the CTLE sees 1.0 V CM whatever the line CM.
  The 3.0 V case is still in the queue.
* **(a) Termination trim:** `pt_termination` r2 passes `term_trim[2:0]` (gated by `term_en`) to new outputs
  `TERM_TRIM0..2` for the pad bank.  The legs are the pads owner's: base 60 Ω plus binary conductance legs of
  840/420/210 Ω, giving 60…40 Ω in ≤ 4 Ω steps.  Layout is DRC/LVS/KLayout clean; `term_run.py` is queued.
* **(d) Return loss** (analytic COB chain, P1–P4 × bond ±0.3 mm, `scratch/wired_rx/pkg_rl_trim.json`): minimum RL
  over 0.1–1.25 GHz

  | Pad C | 40 Ω | 60 Ω |
  | --- | --- | --- |
  | 2.35 pF | 8.4 dB | 9.8 dB |
  | 1.6 pF | 10.0 dB | 15.2 dB |
  | 1.15 pF | 10.3 dB | 18.4 dB |

  **With today's 2.35 pF no trim setting reaches 10 dB.**  Over 1.25–2.5 GHz every C/R combination gives
  2.1–5.6 dB, because the bond plus connector inductance (~3.3–4 nH per leg) dominates.  The package-channel §6
  "≥ 8 dB at 2.5 GHz" therefore needs a compensating structure or a package/board change, not on-die R/C. (risk: WRX-04)
* **(d) Eye through the COB** (`pkg_channel.py` per-pin model + `pkg_qual.py`).  Setup:
  - PRBS7 at 2.5 Gb/s, 400 mVppd TX (50 Ω), user AC caps at the placement point;
  - pad C 2.35 pF, 50 Ω to 1.2 V;
  - extracted CTLE r2, 150 fF slicer load per leg;
  - eye at the CTLE output, tt, nominal bond.

  `scratch/wired_rx/pkg_qual/ext_tt.json`:

  | Code | P1 | P2 | P3 | P4 |
  | --- | --- | --- | --- | --- |
  | 0 | 567 mV / 0.90 UI | 565 / 0.90 | 560 / 0.90 | 555 / 0.90 |
  | 4 | 242 / 0.70 | 241 / 0.70 | 239 / 0.70 | 237 / 0.73 |
  | 7 | 114 / 0.58 | 114 / 0.58 | 113 / 0.58 | 112 / 0.58 |

  The width is the contiguous range with ≥ 40 mV of opening.  At the pad (no CTLE) the eye is 389–398 mV /
  0.93–0.95 UI.  **Every placement passes with every code.**  The COB alone at 2.5 Gb/s needs no peaking, and higher
  codes over-equalize this channel; the 12 dB range is for the standard's reference channels on top, which are not
  modelled here.  The first attempt used ngspice T-lines and stalled ("timestep too small"); the lines are now LC
  ladders.  Queued: bond ±0.3 mm, ss, and DC-coupled at CM 0/2.5/3.0 V with the on-die AC coupling.

### Questionable prior choices (found in resume 5)

1. **Capture r4 was published on schematic evidence only.**  Nothing checks the extracted load of
   boundary/timing nets, although DW grew 4–25× and the CK/CKN/lane nets roughly doubled.  A cap-delta report
   for named nets between revisions would have caught it before a 4 h simulation. (risk: MOD-05)
2. **The r4 gear/PD timing rested on a guessed octet delay** ("O ~0.5 ns after CKP0").  Extracted, it is 1.1–1.3 ns.
   The gear's weak, single-NAND clock fan-out over a 1.3 mm row is a schematic-only design.
3. **The `capture.bench` `*_ss_r1` cases pair an ss capture with a 0.47 ns sampler delay (the ff slicer).**
   That combination cannot occur on one die.  The main-path benches never used the real slicer delay
   (0.95–1.63 ns) until `run_capture_rs.py`.
4. **The safe-state limit (10 µA with S/CKP toggling) has failed since r3a (122 µA schematic, 257 µA extracted).**
   The TSPC first stages see the toggling S inputs even with every clock gated.  Either gate S with EN at the
   front or justify a different limit; the evidence has carried "fail" without a note. (risk: PWR-01)
5. **The slicer offset bench resolution (2.5 mV/decision) could not verify a ≤ 2 mV trim step**, and r3's
   0.5 µm smallest cap gave ~10 mV LSBs.  The unequal-pair Δ is comparable to the layout asymmetry (+2.25 mV on
   bit 0 in r4), so fine trims must be designed from the extracted sweep, not from ΔW alone.
6. **CTLE r1 tail at L = 0.5 µm with the input pair at Vsg 1.65 V.**  At ss/3.15 V the tail sat near triode (0.43 V
   Vsd), and its output resistance (~4 kΩ) shunted Rs/2.  Peaking collapsed to 1.6 dB at ss while the
   binary Rs codes clustered (0/0.6/2.1/7.3 dB).
7. **The 2.35 pF RX pad C makes the RL target unreachable by any termination trim**, and the 2.5 GHz RL target
   is set by the package inductance.  Termination trim alone was listed as the RL fix in PKG-W1. (risk: WRX-04)
8. **The capture bench's DX check** judged against the shortened DW window (fixed earlier).  The PD/gear checks
   only exist for quarter mode (h625/f480 do not exercise them).

## Resume 6 (2026-11-11)

### Resume 6 / CDR (main agent; scratch `scratch/wired_rx/r6cdr/`)

* **Verification of the r-pi / r9 hand-over.**  `fsweep.json` had been corrupted by concurrent writers and rewritten
  with 3 entries, so the ss/32/2.71 V 833 MHz extracted point has no stored evidence (fork RING re-runs it).  The old
  `int/comp.json` compliance evidence was for the 4.68 uA draft OTA, not the r9 nA OTA. (risk: MOD-12)
* **pt_cdr r9 corners (item 2), DC sweep of VCTRL 0.7-2.2 V, 12 corners, g 0/3/7, idle/1 vote/4 UP/4 DN
  (`dccorner.py`, `dc_sch.json`, `dc_ext.json`).**  Schematic and EXTRACTED agree: g7 full scale 67-80 nA, g3 4.4-5.4 nA,
  one vote saturates the OTA (0.92-1.00 of 4 votes), output flat within 4 % from 0.85 to 2.05 V; idle offset <= 6.6 % FS
  inside each corner's operating VCTRL window.  ff: upper compliance only ~1.9 V (reverse conduction through the OTA
  output PMOS; 190 nA at 2.05 V ff/22/3.15); ff needs <= 1.2 V for 834 MHz, so benign, but it is a real limit.
  Ring-rate alternation at corners: started, ss idle -1.26 nA only (not finished).
* **pt_cdr r9 layout (item 2):** generic flow into scratch (`lay/gen`): DRC 0, LVS unique, KLayout main 0 / antenna 0,
  166,969 um^2 (ceiling 300k).  NOT yet published into generated/ (the published cdr.* is still the stale r-ac3 cell). (risk: MOD-12)
* **KP code vs JTOL (questionable prior design point).**  Measured P gain at KP code 3 is 513-995 ppm/vote (schematic r9c,
  extracted tt 930), not 560.  Model (r9 integral, lat 8): 625 MHz code 3 = 0.97x mask (FAIL), code 2 (619) = 1.13x;
  834 MHz code 3 tt/ff 0.98/1.00x, code 2 1.13-1.16x; 393 MHz code 2/3 0.97-1.03x (marginal at lat 8).  KP must be a
  per-rate table: 393 -> 3, 625 -> 2, 834 -> 2 (`kpcode.json`, `kplat.json`). (risk: WRX-10)
* **PD latency, measured on the extracted r5h capture (`caplat.py`):** vote valid 5.25-6.0 ring cycles after each leg's
  data sampling edge at 625 MHz tt, 4.9-5.65 at 480 ff.  834 MHz could not be measured: the stored ext_q834_r1 bench
  FAILS (3 bit errors, pd_ok false).  With the model at the measured latency (6 at 393/625, 7 estimated at 834):
  JTOL >= 1.09x (393, code 3), 1.16x (625, code 2), 1.13-1.19x (834, code 2).  So <= 8 cycles is met with ~2 cycles
  margin at 625; at 393 MHz 8 cycles leaves no JTOL margin. (risk: WRX-11)
* **Closed-loop extracted CDR (item 1): NOT done.**  Bench `cl.py` (r9 ring sch/ext + pt_cdr sch/ext + XSPICE
  bang-bang PD with exact latency) and `cla.py` work, but (a) Kvco ~1225 MHz/V means 1 mV of VCTRL = ~2000 ppm, so the
  start VCTRL must be set to <0.5 mV and the extracted ring's loop-filter node does not take the `.ic` (frequency still
  settling at 200 ns); (b) the open-loop calibration run with the schematic ring gave 1050 MHz at VCTRL 1.24 V
  versus 632 MHz in the r9c P-gain bench: unexplained, must be resolved before any closed-loop result is trusted;
  (c) speed: 4.4 s/ns schematic under the current box load, so a 3 us extracted run is ~15 h. (risk: WRX-01)

### Resume 6 / AREA (fork; scratch `scratch/wired_rx/r6area/`; nothing in generated/ replaced)

- **pt_cdr 288 x 409 um = 117.8k um^2** (r9 layout 167k, published r-ac3 301x693): `wrx_flow.generate_layout(...,
  over_dev=True)` runs each row's Metal4 band and Metal2/3 escapes over the (Metal1-only) primitives, at 20 columns.
  Same netlist; DRC 0, LVS unique, KLayout DRC 0 / HRES ok, precheck main 0 / antenna 0.  DC corners
  (`dccorner.py`, 12 corners x g{0,3,7} x 4 cases) on its extraction = `r6cdr/dc_ext.json` within 1.8 pA.
  Product: `r6area/cdr_c20od/gen`.  Transient CDR-loop checks not rerun on it.
- **pt_wrx_cap: 0.938 mm^2 is ~73% empty** (leaf cells ~0.25 mm^2 total): wc_front (1345 um) and wc_gear (1370 um)
  set the width of an 11-row stack of 420-470 um rows, plus 20-65 um channels.  Changes (scratch copy
  `r6area/capture_area.py`): `split()` folds a single-row cell into k rows at gate-group boundaries (front, gear ->
  3 x 463-503 um, each DRC/LVS clean); `layout_engine.generate(..., over_cell=True)` puts the channel tracks over the
  Metal1/2 macros (default off, unchanged for other users).
  - with gear, best floorplan v3 1013 x 378 = **0.383 mm^2**, DRC 0 / LVS unique.  Extracted q625: **3 bit errors
    (DW13, DW17), DN0 activity 0.05, DX 4/5 wrong** -> not qualified.  Lane nets DL/EL 147-169 fF (r5h 106-149);
    pair clocks GCK12-19 +65..100 fF (P12-19 on one 776 um row): the suspects.  A first 1068 x 352 attempt
    (pairs in 10-wide rows) had DL/EL 250-317 fF and 13 bit errors (the r4 failure mode).
  - without gear (20-bit boundary): 1068 x 245 = **0.261 mm^2**, DRC 0 / LVS unique, not simulated.  The 0.30 target
    is not reachable with the gear in the block: cell row length ~7000 um x ~44 um rows is already ~0.31 mm^2.
  - gear in the digital macro: DW words every 8.0 ns at 2.5 Gb/s (125 MHz = line/20), DW bus skew <= 250 ps
    (r5h ext q625), so ~7.7 ns window for a 60-flop 20->40 gearbox at 125 MHz in the macro; outputs DX0..39 +
    WCLK40 (41 pins) replaced by DW0..19 + a word strobe (21).  Spec S3 (40-bit at line/40) would move inside the
    macro; needs coordinator decision.
- Not changed: real capture.py, generated/*.  `wrx_flow.py` (over_dev) and `timing/layout_engine.py` (over_cell)
  carry default-off options.

### Resume 6 / RING (fork; scratch `scratch/wired_rx/r6ring/`)

* **r9 range re-verified, extracted** (published r9 `pll_ring.ext.spice` e48b306e…, open loop, HOLD=1, 20 fF/phase,
  `r6ring/range.json`; supply = pt_pll_vreg VOUT, ss/32 at VIN 3.15 V / ~6 mA interpolates to **2.69 V**, not 2.71):
  ss/32/2.69: 815 / 827 / **831 MHz at VCTRL 1.95 / 2.02 / 2.05 V → 834 MHz is NOT reached inside the pt_cdr
  integral compliance (≤ 2.05 V); needs ≈ 2.07 V. FAIL by ~3 MHz / ~20 mV.**  sf/32 1038, fs/32 1044 MHz at 2.02.
  Low end: ff/22/3.015 275 / 360 / 396 MHz at 0.80 / 0.85 / 0.87 (393 at ≈ 0.865 V, 65 mV above the 0.8 V floor);
  sf/22 179 / 317 MHz at 0.95 / 1.05 (stopped at 0.85), fs/22 236 / 377 / 520 at 0.85 / 0.95 / 1.05; tt/27/2.925
  390 / 839 MHz at 1.03 / 1.39.  Fast-tune KP=3, tt, 4 votes: **+897…+903 / −897…−909 ppm per vote** at 390/839 MHz
  (symmetric, flat over range; the model design point was 560–600, i.e. KP=2 is the matching code).
  Phase-port error (20 fF): tt ≤ 9°, ss/32 up to −17°, **fs/32 up to −21° (spread 19.4°)** – inside the ptrim 26°
  span only if ptrim can delay every early phase by the full spread; not checked here.
* **pt_cdr integral compliance (schematic merged pt_cdr, `r6ring/int/ibcdr.json`):** ss/32/3.15 at VCTRL 2.02 g7:
  idle −2.5, UP +67.1, DN −70.0 nA; at 2.05 g3: −0.25 / +4.35 / −4.74 nA (−16 % vs tt); ff/22/3.35 at 0.85 g7:
  −0.76 / +78.0 / −78.9 nA, g3 −0.10 / +5.12 / −5.26 nA.  Works at both edges.  (The prior "0.8–2.05 V OK" claim
  was measured on the superseded µA r4 integral, `r9/int/comp.json`, not on the r9 nA OTA.)
* **Port users (AC3-W12):** `run_timing.tb_pll_ring` and `pll_vreg.ring_ripple` tie the 13 r9 pins to 0;
  chip_assembly `netlist.py` ties them to VSS on `pll_tx`/`pll_host` (superseded if RINGAREA moves those to
  `pt_pll_ring_core`).  Extracted r9 at 3.3 V: open VCTRL 1.2 V 614 MHz /15.81 feedback, port error 8.4°, 6.0 mA;
  closed 625 MHz (REF 39.06 MHz, precharge 1.0 V for 0.2 µs, 1 µs): **locked 625.95 MHz (N 15.98), pass** but VCTRL
  still moving 1.18–1.25 V over the last 300 ns (short run; not a settling claim).
* **Antenna (12 × ANT.16_i_ANT.6):** not the diode sizes: nets NX and N16B are each driven by one small inverter
  (drain 1.32 µm², counted by the deck as a finite diode) and run ~880 µm M5 trunks (ratio 426–427).  The planner
  treated any S/D landing as full protection.  Fix: `layout_engine.ANTENNA_IGNORE_SD = {'pt_pll_ring'}` (gate nets
  get diodes regardless of a driver).  Scratch rebuild (it picked up RINGAREA's compact `pll_ring.spice`, 202.9 ×
  662.7 µm, 419 devices): 49 diodes, Magic DRC 0, LVS unique, **KLayout main 0 / antenna 0**.  Not published
  (RINGAREA owns the publish).

### Resume 6 / FRONT (fork; scratch `scratch/wired_rx/r6front/`)

Items 8 (IX-13), 9 (USB after PD22) and 10 (CTLE r2 +60 fF).  Benches: `hsq.py` (published `pad_hspad` model +
COB chain + CTLE, RL and eye), `usbq.py` (USB path), `cin.py` (CTLE input C with a 150 fF/leg load), `run_blk.py`,
`stage_layout.py`/`publish_front.py` (staged layout; generated/ written only when clean, without
`netlists.write_all()`, which rewrites every owner's netlist).  Results: `hsq.json`, `usbq.json`, `blk.json`, `cin.json`.

* **Item 10: CTLE input C, extracted, with the published `pad_hspad` model and the COB chain.**  The real CTLE r2 input is
  **255–264 fF per leg** at 1–2.5 GHz (150 fF load; r1 175 fF), not the 120 fF PD21 budgeted: 98 fF of it is wiring
  (48 fF to VDD), plus the 96 µm pair and the 2 × 20 µm bypass TG.  Behind the 4.9 pF MIM it adds ≈ 0.13 pF to the
  1.11 pF PD21 figure (≈ 1.24 pF, IX-3 ceiling 1.15 pF).  Impact, per leg RL at the carrier end (tt): r2 actual 14.1/14.3 dB
  (0.1–1.25 GHz, P1/P4) and 4.7/5.1 dB (1.25–2.5 GHz) vs 14.3/14.6 and 5.1/5.6 dB with the 120 fF budget; ss 13.1/13.4,
  ff 13.4/13.7 dB low band.  **The r1→r2 +60 fF alone costs −0.15 dB (low) / −0.19 dB (high band) RL and −4…−5 mV
  (≈ 1 %) eye height, −0.025 UI width** (2.5 Gb/s PRBS7, P1/P4, codes 0/4, tt and ss; 3 Gb/s the same).  Eyes at the CTLE
  output stay 195–456 mV / 0.65–0.85 UI.  No fix needed: the high band is set by the package inductance (PD26), and
  the low band keeps ≥ 13 dB.  The IX-3 1.15 pF figure is exceeded on paper (to pads/spec, interface-changes FR-1). (risk: WRX-04)
* **Item 8: CTLE r3 (IX-13, `lf_zero[2:0]`).**  Per side, 1/2/4 NMOS gate caps (80 × 6.2 µm, channel at VSS) switched
  onto each source node by PMOS 8/16/32 µm (68 Ω per side all on, 136 Ω floating equivalent), with gates pulled to VSS
  when off.  This is the differential equivalent of the floating MIM bank.  The generic flow has no MIM, and a floating
  MOS cap between the two ~2.3 V source nodes would sit at Vgs ≈ 0.  The placement order is set in `ctle()`: the bank
  rows go below the r2 rows, so the RX/CTLE port trunks keep their r2 length.  The first try put the bank in the middle
  and cost +58 fF input C; the second moved the pair to the top and cost +1 dB code-0 peaking through longer sp/src.
  **Extracted (tt / ss 32 °C 3.15 V / ff 22 °C 3.35 V):** (risk: WRX-13)
  - zero (+3 dB point at peak code 7) for codes 1…7:
    - tt 20.9 → 4.9 MHz
    - ss 19.0 → 4.55 MHz
    - ff 24.4 → 5.6 MHz
  - the zero is monotonic; boost (peak − 10 kHz) is 15.0–17.3 dB.
  - with code 0 (bank off), peaking moves +0.28…+0.47 dB against r2 extracted at every peak code (limit 0.5 dB), the
    1.25 GHz gain rises +0.17…+0.29 dB, and the input C is unchanged (255–261 fF).
  - The 12-corner extracted `tb_ctle` (21 cases) passes, and safe passes as in r2.  133,483 µm² (r2 65k, ceiling
    200k), 225 × 594 µm, DRC 0, LVS unique, KLayout main 0 / antenna 0.  Published (`ctle.*`, `ctle-evidence.json`).
  - **Gap:** code 1 reaches only 19–24 MHz, not the 35 MHz end of the IX-13 window.  Every code stays inside 4.4–35 MHz.
  - lf_zero ≠ 0 with peak code 0 gives a mild +3.4–3.8 dB LF shelf (zero 55–86 MHz), which is harmless.
  - Port change: +`lf_zero0..2` (FR-2).
* **Item 9: USB after PD22 (USB on `pad_wirepad` bond 24/25, HS pair on `pad_hspad` bond 20/21).**  Decision: **no
  CTLE input mux and no new USB receiver.**  USB HS already bypasses the CTLE (`rxselect_direct=1`, RX → slicer).
  USB squelch/disconnect/FS-LS use `pt_detect`, and the wmon RX taps hang off the USB pad.  So the only change is a
  net split at integration:
  - `USB_RX_P/N` (wirepad RX) → rxselect.RX, detect.RX, wmon_sel.RX;
  - `HS_RX_P/N` (hspad RX) → ctle.RX only, which adds 0 fF to the hspad node (PD21 allows ≤ 20 fF);
  - the HS input remains observable via `wire_ctle_bypass=1` + wmon sel CTLE_P/N.

  This is the conventional option (no new circuit).  A mux would add ≥ 2 TG junctions on the 1.15 pF-budget node.
  * **`pt_termination` r3** (PD27) drives both pads:
    - USB: `term_mode` as before;
    - HS: `hs_en`, `hs_term_en`, `hs_trim[3:0]` → `HS_TERM_ENABLE`, `HS_TERM_TRIM0..3` (= trim & enable),
      `HS_TERM_VCM` (0.43–0.47 V), `HS_VBIAS` (0.95–1.01 V, the CTLE input CM behind the MIM).

    r2's `TERM_TRIM0..2` are removed.  They collided in case with `term_trim0..2`: **ngspice merged input and output
    into one net, so the r2 trim "pass" was meaningless**, and pad_wirepad has no trim legs.  Extracted nominal + 12
    corners pass, safe passes, DRC 0, LVS unique, KLayout 0/0, 48,249 µm².  Published. (risk: PAD-03, HL-04, MOD-05)
  * **HS-pair squelch / SATA OOB / PCIe idle:** `pt_detect` cannot take the CTLE output.  I tried a `det_src_ctle` tap
    (schematic, tt), and the ±100 mV burst at CM 1.2 V never fired.  The PMOS comparators compare (P−N) against
    ladder taps at ~0.5 V CM, so a 0.7 V CM mismatch swamps the threshold.  The change was reverted, and `pt_detect`
    is unchanged.  Route: IX-10 e-sampler threshold DACs (owned by the slicer fork) + IX-12 raw capture with FPGA
    burst/gap counting (FR-3).
  * **USB HS receive bench** (`usbq.py`): 45 Ω host → P1/P4 carrier → COB (bond 24/25 geometry) → published wirepad
    model (termination on, VCM 0 V) → extracted rxselect (direct) → 150 fF.  DC termination per leg is 46.2 Ω (tt), 53.3 Ω (ss),
    39.6 Ω (ff): **the ss/ff values are outside USB's 45 Ω ±10 % (40.5–49.5 Ω)**.  This is the PD23 6 V-conversion
    regression, owned by pads (FR-4).  Eye at SL (480 Mb/s PRBS7, 400 mV lines): **tt P1 806 mV / 0.975 UI and ss P1
    862 mV / 1.0 UI**, SL CM 0.20–0.22 V.  P4 (tt, ss) and ff P1 did not converge: the transient stalls in an ESD diode's
    internal node or the VDD branch once the line reflections reach the pad model.  This is open; a cable model and
    the slicer itself are not in this bench.

### Resume 6 / RINGAREA (fork; scratch `scratch/wired_rx/r6ringarea/`)

* **Area split (r9 published 201.9 × 920.2 = 186.9k µm², generic row placer, 200 µm rows):** core without the FT
  array 201.75 × 459.5 (92.7k); core without FT and without the N5/N10 /10 path 201.05 × 389.7 (78.3k).  So the FT
  array (313 of 665 devices, only 583 µm² of gate) cost ~94k µm² (≈ 460 µm of rows: per-device PCell + channel
  overhead, plus a 103 µm tall row for the unfolded 100 kΩ VCTRL→VCF resistor); the /10 path ~14k.
* **Published (analog/timing, r9d):** `pt_pll_ring_core` (new, `pll_ring_core.spice`, pll_tx; consolidation X4)
  198.0 × 438.4 µm = 86.8k; `pt_pll_ring` (pll_cdr) with compact FT (per leg/side 3 binary copies behind static KP
  switches + one vote switch; no per-unit logic; 100 kΩ folded 5 × 20 µm) 198.6 × 664.1 = 131.9k.  Both DRC 0 / LVS
  unique / KLayout main 0 antenna 0.  pll_host deleted (X1, inventory default 2 rings).  Two rings 218.7k vs 560.8k.
  **≤ 201 × 400 per ring not met** (core 438, CDR 664).  r9 sources/layout kept in `r6ringarea/backup_r9/`.
* **Speed (extracted, regulated 2.69 V ss/32):** r9 and compact r9c identical (831 @ VCTRL 2.05, 838 @ 2.10).
  Pessimistic (+15 % C on ct_ring9/ct_phbuf8, Rg 150 Ω·W/10 µm) r9c: 790 / 797 / 807 MHz @ 2.05 / 2.10 / 2.20 —
  **fails 810**.  r9d resize (tail 8 × 10/1, replica 6.67) + WT21 BAND bit: HI ss 869.6, HI pessimistic 826.0 @ 2.05
  (810 ✓, 834 needs ≈ 2.10 V: pt_cdr is flat to 2.2 V at ss, `r6cdr/dc_ext.json`); LO ff/22/3.015 333 @ 0.90
  (≤ 360 ✓); LO pessimistic ss top 724; overlap > 200 MHz.  pll_ring_core r9c pessimistic 825 @ 2.05.
  Phase spacing at ss/32 is −10…−19° on PH2/PH7 in r9/r9c (ptrim range ±13°: open, timing owner).
* **P gain:** r9 KP3 926 ppm/vote (tt 629 MHz) → r9c 868, r9c-T8 849 @ 577 MHz.  The per-rate KP table must be
  rechecked against the CDR JTOL model (code 2 ≈ 570).
* **Blocking finding (pre-existing in r9, not caused by compaction): vote-rate injection.**  tt/2.925 V, KP3,
  all four legs: FU/FD alternating each 1.6 ns (net 0 votes) shifts the ring **+6580 ppm (≈ 7 votes) in r9**,
  +4360 ppm (≈ 5 votes) in r9c; FU toggling at ring rate (ideal +2 votes) gives +5.3 votes in r9.  Static ppm/vote
  hides it.  The offset depends on vote activity (transition density), so the integral path cannot treat it as a
  constant: the CDR loop model must include it, and the FT switch/gate charge needs a fix (CDR owner).
* Not done: BAND-mode ppm/vote and alternation on r9d; ss LO-band minimum; full 12-corner range table; closed-loop
  lock on r9d; ANTENNA_IGNORE_SD not keyed on `pt_pll_ring_core` (layouts are antenna-clean as built).


### Resume 7 / RING (fork RING7, 2026-11-11; scratch `scratch/wired_rx/r7ring/`, see STATUS.md; nothing in generated/ replaced)
* Vote injection mechanism (r9d schematic): switched-source long-L FT copies recharge their source node while off; alternation +4834 ppm.
  Header-side current steering + VHD follower (r9k/r9m) gives -90 ppm schematic (810 ppm/vote KP3), but **extracted r9m -5010 ppm**
  (vote-synchronous bench) from FU/FD/FUB/FDB coupling into VHD/steered drains (-475 ppm with those caps removed). Open, WRX-16.
* 1050 vs 632 MHz: schematic `generated/fast/ct_ring9.spice` is the intended netlist (no wiring): 1158 MHz at 1.21 V tt vs 614-727 extracted.
* `cdr_pi_model.run(inj_alt_ppm=)` models the injection: 625 MHz JTOL 1.19x -> 0.73-0.80x at +-4360 ppm; unchanged at -240 ppm.
* ptrim (schematic, 834 MHz) 29.1 deg ss/fs covers the 17-21 deg ring spread; published ptrim.ext.spice does not toggle.
* Antenna planner: finite driver diffusion rule (RG7-1). Ring table / evidence regen not done (ring not republished).

### Resume 7 / RING ECO (2026-11-12; scratch `scratch/wired_rx/r8ring/`, see STATUS.md; **published `pt_pll_ring` r9v**)
* **What changed.** The published r9d layout is kept **exactly as routed** (every generic re-layout doubled the ss phase error);
  an ECO in Magic deletes the 139 old FT instances (112 legs, 11 inverters as 22 halves, 5 VCF resistors) and their 91 FT-only
  nets (`select net` from each deleted instance's pcell port points; `eco/mkeco.py`). VH and VPBF are brought out on Metal3 at
  the core's left edge (y 547.9 / 360.4 um) into a shielded left channel (VSS|VH|VSS|VPBF|VSS); EN/IBIAS drop from the core
  bottom. The FT array is now the macro `pt_pll_ring_ft` (`analog/timing/pll_ring_ft.spice`, header current steering, r9h
  scheme) placed **below** the core (away from the phase ports): 8 hand-placed slices (`ftmac.py`: inverter at the switch gates,
  FX/FXB local pair in their own channel, Y = 2.2 um Metal2 link + Metal4 riser with VSS shield tracks, VH/VHD/VPBF buses two
  rows away from the votes) + the follower/replica/KP-inverter sub-macro `pt_ft_fol` (layout_engine). `pll_ring.spice` = r9v.
* **Interface (row RING-ECO in interface-changes.md):** KP0..2, FU0..3, FD0..3 move to the new bottom edge (Metal5,
  y = -127.98 um); other ports unchanged. Block 198.1 x 664.6 -> 210.0 x 792.6 um (+34.9k um2). Port order unchanged.
* **Clean (gate a):** Magic DRC 0; netgen unique match vs r9v (core flat + XFT hierarchical, 20 core antenna diodes mapped);
  KLayout precheck main 0 / antenna 0 (`pll_ring-kldrc.json`), sak-drc 0. Macro alone also DRC 0 / LVS unique.
* **Phase spacing (gate b, extracted, ss/32/2.69, VCTRL 1.9, 33 fF, deg vs PH0):** r9v 848.1 MHz
  [-7.0 -9.1 -13.7 -0.8 -9.3 -14.5 -9.0] vs r9d 847.3 MHz [-6.3 -8.0 -12.2 -0.1 -8.8 -14.1 -6.6]: per-port change 0.4..2.4 deg
  (PH7 2.4: the removed FU0 route ran beside it), spread 13.7 deg (ptrim range 29).
* **Vote injection (gate c, tt/27/2.925, VCTRL 1.21, KP3, ring-synchronous votes, 33 fF, ppm vs idle):**
  | netlist | alt | rnd0.5 | tog - up/2 | up (per vote) | spread |
  |---|---|---|---|---|---|
  | r9d published (r7ring) | +4279 | +2948 | | | |
  | ftA generic macro + schematic core (r7ring) | -863 | -387 | -139 | 852 | 724 |
  | hand macro + schematic core | -307 | -58 | -282 | 851 | 249 |
  | **r9v full extracted top** | **-228** | **+32** | **-259** | **858** | **291 (<= 300)** |
  Extracted vote coupling in the hand macro: vote->Y 0.03 fF/slice (ftA: dominant), vote->VH 1.0/0.26 fF (FX/FXB), the rest to
  VDD/VSS shields. Bisection (macro + schematic core): all macro caps removed -80 ppm (device floor), Y wiring caps removed
  -265: the remaining layout share is spread over many nets, not a single coupling.
* **Range (gate e, extracted r9v, 33 fF, KP3, MHz; ring supply = corner value):**
  | corner | LO@0.85 | LO@2.05 | HI@0.85 | HI@2.05 |
  |---|---|---|---|---|
  | ss/32/2.69 | stall (0.95 V: <50 MHz, 0.65 mA); **145.6 @1.05** | 753.8 | 192.6 @1.0, 383.6 @1.15 | **866.7** |
  | ss/22/2.69 | stall | 770.6 | stall | 885.0 |
  | ss/32/2.89 | stall | 804.3 | stall | 933.6 |
  | tt/27/2.925 | stall; **140.4 @0.9**, 252.3 @1.0 | 1047.3 | stall (1 mA) | 1202.4 |
  | tt/27/2.835 | stall | 1022.1 | stall | 1169.8 |
  | ff/22/3.015 | **257.2** (optimistic **280.7**) | 1355.8 | 400.9 | 1539.2 |
  | ff/22/2.835 | slow (<233) | 1300.7 | 397.6 | 1469.8 |
  | ff/32/3.015 | slow (<233) | 1325.7 | 406.3 | 1507.0 |
  | sf/27/2.835, 3.015 | stall | 996.1, 1038.4 | stall | 1155.1, 1213.5 |
  | fs/27/2.835, 3.015 | stall | 1027.1, 1081.8 | 249.1, 250.9 | 1159.5, 1230.2 |
  "stall" = no oscillation at 0.85 V (ring current < 1 mA); "slow" = oscillating below the 60 ns window's 233 MHz (long-window
  value given where run). Low-band minimum: <= 360 MHz at every corner checked, including the **optimistic** bound (wiring C
  x0.85, Rg 0, junction C x0.75; the BSIM gate-oxide C cannot be lowered, so this bound is partial) at ff/22/3.015: 280.7 MHz
  @ 0.85 V. Stop VCTRL: ss/32 between 0.95 and 1.05 V (145.6 MHz just above), tt ~0.85-0.9 V (140.4 MHz @ 0.9). Band continuity:
  every LO top (>= 753.8) is far above the HI bottom (<= 401 / stall) -> > 350 MHz overlap at every corner.
  Average gain (MHz/V): LO 608 (ss/32) .. 789 (tt) .. 915 (ff/22); HI 642 (ss/32) .. 949 (ff/22).
  ppm/vote (all four FU on, KP3, band ends): 160 (HI@2.05 tt) .. 283 (HI@0.85 ff/22); 858 at tt VCTRL 1.21 (alt.py up).
* **Pessimistic HI top: NOT obtained.** With `pess.py` (+15 % wiring C, Rg 200 ohm/10 um, +25 % device C as CGX/CDX) the ring
  does not oscillate at HI@2.05 (tt or ss; 2-2.9 mA, phases flat) - and the **published r9d extraction fails the same way**
  (r7ring/d_ext.spice), so the r9d README "HI pessimistic 826 MHz" figure is not reproducible with the current pess.py. Rg alone
  or +15 % wiring C alone: runs; CGX/CDX at 40 % (+10 % device C) with Rg and wiring: runs. Start-up/latch threshold between
  +10 % and +25 % device C. **Partial pessimistic bound** (wiring +15 %, Rg, device C +10 %): HI@2.05 ss/32/2.69 = **727.9 MHz**
  (r9d published, same derate: 728.5 MHz) vs 866.7 nominal -> the high-band top misses 810/834 MHz at pessimistic C/Rg on the
  unchanged r9d core as well (pre-existing, not an ECO effect). Open: ring speed at the pessimistic bound, and the start-up failure
  at +25 % device C.
* **Evidence regenerated** (`generated/pll_ring-evidence.json`, `evid.py`: run_timing gating benches on the published r9v
  extraction, tt/27/3.3): closed loop 480 / 625 / 810 MHz and host-follow N=4 125 / 156.25 MHz all frequency-locked (pass),
  port phase error max 6.7-7.3 deg; analog LOCK flag high at 480/625, low at 810 and N=4 (demoted indicator, as before); safe
  tt/ff85/ss0 10.0 uA (= IBIAS); clean pass (DRC 0, LVS unique, KLayout precheck 0/0). Not rerun on r9v (listed as excluded):
  cold start, HOLD, open-loop VCTRL-end cases and the 24 run_timing corner cases (the range table above replaces them).
* r9d backup: `scratch/wired_rx/r8ring/r9d_backup/`. Reproduce: `eco/mkeco.py` -> `ftmac.py` -> `asm.py` -> `check_top.py` -> `publish.py`.

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

### Resume 6 / SLICER+CAPTURE (2026-11-11; scratch `scratch/wired_rx/r6slicap/`)

* **Capture r6 (antenna, published):** bare N+ diode columns (no device, LVS unchanged) on CKP0 (wc_ctl), ELQ6..9
  (wc_slot1), GWT ×3 and DW0..19 (wc_gear) (`Cell.diode`).  Top DRC 0, LVS unique, KLayout main 0 / **antenna 0** (was 22).
  Extracted q625: 0/200 data, 0 edge errors, PD and gear OK.  Previous r5h files: `scratch/wired_rx/r6slicap/cap_r5h_published/`.
* **Safe state (item 5):** solved as a system state (interface W6-SAFE): capture EN=0 implies slicer_en=0 (S low) and
  ptrim_en=0 when the RX is off.  Extracted, EN=0 with S static and CKP toggling at 625 MHz: **9.66 µA** (limit 10 µA,
  outputs ≤ 0.022 V); the S-toggling stress case stays 238 µA (unsupported state).  Bench: `capture.bench(s_static=True)`.
  Front-end EN gating of S was rejected (adds two gate delays on the RCS=1 path, no margin at 834 MHz ss).
* **Slicer r6 (NOT published; `generated/slicer.*` is still r4c).**  `slicer_compact.py` now has: 4th fine bit TF3
  (outer unequal pair), N+ antenna diodes on TP0/TN0/TF0..3, IX-10 ws_sae (aux PMOS pair 6 µm/side on the tail node,
  mirror-symmetric at the core ends) + ws_aux select cells (TGs, pull-ups, 8×4 µm PMOS decap per AX line) in the control
  row.  Staged layout: DRC 0, LVS unique, KLayout main 0 / **antenna 0** (was 32), 300.8 × 339.3 µm.  Extracted results:
  * fine trim, all 16 codes measured (0.15–0.2 mV resolution): max gap **tt 2.0 mV, ss 1.59, ff 2.2 (d1; d0/d2/d3 2.0)**;
    e-samplers ≤ 1.98 everywhere; fine span 8.6–14.2 mV covers the coarse LSB (7–11.2 mV) at every corner.
  * range p7 / n7f15: tt −57.6…−63.7 / +53.7…+61.2; ss −45.4…−50.6 / +44.8…+51.3; ff −64.7…−71.8 / +59.6…+68.1 mV.
  * mismatch MC (PDK fets_mm, 50 runs, extracted ws_sa, tt): mean −4.6 mV, σ 4.95 mV; |sys| + 3·(2σ) = 34 mV < ss range ✓.
  * IX-10 tt: ±(393–412) mV range, LSB 3.45–3.59 mV at mid-scale, monotonic at 7 codes, B path = A path.  r6b had the aux
    pair asymmetric (−35…−40 mV offsets) and AX lines next to the sampler clocks (17–28 fF, ±40 mV spread); fixed in r6c.
  * aperture (834 MHz, 0.5 ps steps): e-vs-d relative shift vs r4c ≤ 1 ps; all samplers 6–8 ps later than r4c.
  * **Regression (blocking): ring-plan 834 MHz at ss/32/3.15 fails 14/51 quarter, 10/59 half (r4c same bench 0/51, 0/59);**
    with explicit Rg (150 Ω·W/10 µm, 760 devices) 10/51, 11/59.  tt and ff pass (ff trimmed 60 mVpp 1/51; r4c ss trimmed
    case also fails 23/51 on this bench).  CTLE-driven tt (CTLE r3 code 4, lf_zero 0): 834 MHz 1/51, 625 MHz 0/68.
    Cause not isolated: SL_P/SL_N wiring 306/287 → 362/338 fF and the extra TF3/diode/aux diffusion on 1pa/4pb.
* **pt_vthdac (IX-10 DACs, new block, NOT published; `vthdac.spice`, `netlists.vthdac()`):** layout DRC/LVS/KLayout clean,
  80.9k µm²; schematic+700 fF load LSB 10.4/11.7/12.4 mV (ss/tt/ff), 263–481 µA, DNL ≈ 1.14 LSB at mid; **settling to 1 LSB
  42–50 ns schematic but 97–109 ns extracted (fails 50 ns)**.
* Open: fix the r6 ss regression (or move the aux/TF3 load off 1pa/4pb) before publishing; DAC load R / settling and area;
  re-run evidence flow on the published r6 slicer; d1 fine gap 2.2 mV at ff.

### Resume 7 / SLICER (fork SLI7, 2026-11-11; scratch `scratch/wired_rx/r7slicer/`)

`pt_slicer` r7 and `pt_vthdac` r7 **published** (`generated/slicer.*`, `generated/vthdac.*`, `vthdac-evidence.json`).
r6 source changes (TF3, N+ antenna diodes, IX-10 ws_sae/ws_aux) kept.  "Pessimistic" below = spec/design-assumptions.md:
ss/32 °C/3.15 V, Rg 200 Ω·W/10 µm on all 760 3.3 V devices, +25 % device C (extra 0.25·Cox·W·L gate–source cap),
+15 % on every extracted C (`r7slicer/pess.py`).
* **Cause of the r6 834 MHz ss regression (isolated, extracted probes):** only the e-samplers (ws_sae) failed (E1–E3; D0–D3
  0 errors).  Their StrongARM still resolved (2oa/3ob cross 1.5 V 440–520 ps after CK, as the d-samplers), but 2oa/3ob
  peaked at only 2.29/2.37 V (d: 2.43/2.45) before reset, and the 4 µm NMOS of the NOR SR latch could not flip it in that
  pulse (lq only down to 0.66 V, lqb ≤ 0.86 V → E2/E3 stuck high).  The extra ws_sae load (aux pair diffusion on x/1pa/4pb,
  x routed to both core ends, +6 fF x wiring) was the last straw on a marginal latch.  Removing the aux devices alone
  did not fix it (still 6/35 errors); doubling the SR NMOS did (0 errors).  SL_P/SL_N C is irrelevant to this bench
  (ideal sources).
* **Fix (r7):** second 4 µm NMOS finger on the SR-latch set/reset inputs (2oa→lq, 3ob→lqb); 1pa/4pb reset NMOS 4 → 2 µm;
  tail 8 × 4 → 8 × 5 µm (needed at the pessimistic values: 750 MHz e-samplers 5/51 errors without it).  **Cost: +8 µm of
  PMOS tail gate on every CKPk (≈ +11–13 fF per ring phase, all eight phases equally; ring/phase-buffer owner to note).**
* **Ring plan, extracted r7 (gating cases, 834 MHz):** ss/32/3.15 0/51 quarter, 0/59 half; ss + Rg 150 Ω·W/10 µm 0/0;
  tt 0/0; ff 0/0 (r6: 14/51, 10/59 at ss).  **Pessimistic:** 625 MHz 0/51, 0/59; 750 MHz 0/51, 0/59; **834 MHz FAILS
  23/51, 28/59** (StrongARM 2oa peak only ~1.9 V within the 600 ps evaluation half-period).  WT21 caps the ring in use
  at 625 MHz, and 742.5/750 MHz (WRX-06) pass, so 834 MHz is beyond the rate plan; it is not claimed at the pessimistic values.
  Non-gating 60 mVpp trimmed case at 834 MHz (fixed TRIM_NOMINAL code, not re-derived for the r7 weights): tt 0/51,
  ss 6/51, ff 4/51 (r4c on the same bench: ss 23/51).
* **Input C:** SL_P/SL_N wiring **291.7 / 288.9 fF** before the safe-bench fix below, **282.6 / 300.7 fF published**
  (r6 361.7 / 337.8, r4c 305.6 / 286.5; sum 583 vs r4c 592).  Two changes: ws_sae INP/INN pins
  on the cell's LEFT edge next to the SL trunk (`wrx_compact.Row.left_ports`, default off; in-cell INP 19.1 → 13.1 fF) and
  SL_P/SL_N taken out of the trunk group and given `net_space` 1 µm (a free trunk column on each side; SL_P–SL_N mutual
  158 → 106 fF, to trims 100 → 57 fF).  Clock coupling onto SL_P/N ≤ 0.64 fF per CKP (r4c ≤ 0.69).
* **Trim (all 16 fine codes, extracted r7, 200 ns ramps, 0.22 mV resolution; `trimfast2.py`, `trim16_<c>_summary.json`):**
  - max fine step **tt 1.54, ss 1.31, ff 1.76 mV** (r6 2.0 / 1.59 / 2.2).  Coarse/fine seams: p side overlaps at every
    corner (p0+f15 ≥ f0 by 0.07–2.3 mV); n side n0 − f15 ≤ 0.42 mV.
  - **range ss: p7 −55.5…−62.6, n7f15 +51.0…+56.9 mV** (target ±50 ✓; r6 −45.4 / +43.1); tt −68.9 / +62.1; ff −77.4 /
    +68.3 mV (r7c, coarse widths unchanged in r7d).
  - Changes: per-side coarse widths TP (0.665, 1.33, 2.665) / TN (0.635, 1.275, 2.55) µm (fine-code-0 offset moved from
    ≈ −3 mV to ≈ 0 with the r7 core); f2 delta 0.28 → 0.26; d-sampler (ws_sa) f3 delta −0.055 (ws_sae keeps −0.075).
    Measured: the ws_sa f3 weight falls as its delta goes more negative (−0.09 gave 0.0–0.5 mV at ff).
  - Caveat: the 200 ns-ramp (r7) and 400 ns-ramp (r6/r7b) methods differ by up to ~0.6 mV on single weights at ff;
    the published numbers are from one method on the published layout.
* **IX-10 on r7 (extracted slicer, ss/32/3.15, extracted r7 DAC end points):** e-sampler threshold −393…−397 /
  +385…+388 mV (A and B paths equal), 3.3 mV/LSB at mid-scale, aux off = A128 within 0.4 mV.
* **pt_vthdac r7:** R_B 94 → 63 kΩ (current × 1.5), R_L 8 → 5.33 kΩ (same swing), steering switches 2 µm (bits 0–5),
  8 µm (bit 6), 2 × 8 µm (bit 7) (r6c: 130 µm of drain per line); layout `over_dev` + all ports quiet
  (`run_family.LAYOUT_OPTS`), 16 columns.  **140.4 × 170.1 µm = 23.9k µm²** (r6c 80.9k; target ≤ 25k), DRC 0, LVS unique,
  KLayout main 0 / antenna 0.  **Extracted, 700 fF per line, 0 → 255 step to 1 LSB: tt 41.9, ss 42.8, ff 37.4 ns**
  (≤ 50 ✓; r6c 97–109).  LSB 11.2 / 10.0 / 11.9 mV at the DAC (tt/ss/ff), mid-scale DNL step 1.15–1.18 LSB,
  current 525 / 388 / 695 µA (r6c 263–481) with vth_en = 1, 0 with vth_en = 0.
* **Evidence flow (reduced, `r7slicer/evflow.py`):** layout published through `run_family.layout_block('slicer')`;
  schematic + extracted nominal and extracted ss/32/3.15 + ff/22/3.35 (the envelope speed extremes) with the standard
  ring-plan/trim benches, plus safe; the other 9 envelope corners were not rerun (box load), recorded in
  `slicer-evidence.json` `corner_set`.  `netlists.write_all()` was NOT used (it rewrites every wired_rx netlist,
  incl. the unpublished detect work); only `slicer.spice` and `vthdac.spice` were regenerated.
* **Safe "off" bench (slicer_en = 0, clocks running) — pre-existing failure found and fixed.**  `sims.tb_safe` could not
  bind the r6 ports (f3 trims, vsel, VT lines; fixed: ctrl/ain lists), so r6 never ran it.  Run on r7 it failed: D0/E0
  kicked to ±0.21 V (limit 0.1 V).  The r4c netlist fails the same bench (0.175 V), so the published r4c "4 mV" safe evidence
  was stale.  Cause: the trunk planner put every D/E trunk beside its own sampler clock trunk (CKP4→D0 45 fF), and the cell's
  Q and CK pins were 0.9 µm apart.  Fix: `net_space` 1 µm on D0..E3 and the ENB pin moved between Q and CK
  (internal sampler nets unchanged to 0.01 fF, so the trim data stand): CKP→D0 17.7 fF; off 0/27/85 °C: max 0.074 /
  0.099 / 0.095 V (D0/E0; other outputs ≤ 0.072 V) — **passes, thin margin**.  Cost: SL_N 300.7 fF (SL_P 282.6; r4c 286.5 /
  305.6), outline 300.8 × 367.3 µm.  Ring plan rerun on this final layout: 834 MHz ss / ss+Rg / tt / ff 0 errors,
  pessimistic 625 and 750 MHz 0 errors.
* Port lists unchanged from r6 (MT01-W3, IX10-W1).  Open: independent review; 834 MHz at the pessimistic values;
  the CKPk tail-load increase in the ring/phase-buffer budget; safe-off margin 5 %.
* **Review round (SLI7, conditions from the independent review):**
  - Provenance: the pessimistic 834 MHz 23/51 figure is from r7c (sl2); the trimmed ss 834 MHz case is 5/51 on the published
    layout (sl6); trim and IX-10 numbers are from r7d (sl3), whose sampler internals match sl6 to 0.01 fF.
    `slicer-window.json` is marked superseded (r4c data). `slicer-layout.json` revision label fixed. ws_sae/ws_aux added
    to `source_hashes`. `tests.clean` = "partial (2/12 envelope corners + nominal)"; the other 10 corners were not rerun.
  - **pess.py fixed:** it now also derates S/D junction C (ad/as/pd/ps ×1.25) and overlap C (+0.025 fF/µm gate–drain and
    gate–source). On the published sl6: 625 MHz 0/51, 0/59 ✓; **750 MHz 15/51, 19/59 FAIL; 810 MHz 25/50, 27/58 FAIL;
    834 MHz 28/50, 31/58 FAIL.**  The earlier "750 MHz passes pessimistic" claim (Cgs-only derate) is withdrawn.  At the
    full pessimistic values the slicer is qualified only to ring 625 MHz (2.5 Gb/s, the WT21 core maximum).  DP HBR 2.7 and SATA G2 3.0 (to 3.24 Gb/s) are NOT dropped:
    OPEN: architecture change in progress (r8arch, `scratch/wired_rx/r8arch/decision.md`).  The WRX-06
    742.5/750 MHz CDR points are therefore NOT covered at the pessimistic values (open; needs a faster sampler core).
    810 MHz stays in the nominal-corner gating set (it passes there); it is not claimed at the pessimistic values.
  - IX-10 LSB at ff (extracted sl6, r7 DAC end points): 3.45–3.6 mV at mid-scale (≤ 4 ✓).
  - r7 per-sampler calibrated trim codes (`r7slicer/trim_r7_cal.json`, |residual| ≤ 0.5 mV): 60 mVpp trimmed at ss
    810 MHz 0/51 ✓, 834 MHz 5/51 (non-gating).
  - **Safe bench at ss/32 °C, 3.63 V, slicer_en = 0 with ring-rate clocks (625 MHz, 8 phases in real order, 30 ps edges):
    FAILS — D0/E0 kicked to 0.215/0.222 V (limit 0.1 V), E1 0.17, E2 0.12; I_rail 2.7 µA.**  The standard bench
    (one 250 MHz clock, 0.1 ns edges) passes at 0.099 V.  Open: needs either more CKP→D/E isolation or a stronger
    output hold, or the W6-SAFE rule that the ring phases are gated (ptrim_en = 0) whenever slicer_en = 0.
  - Not done (box load): tt mismatch MC and the CTLE-driven kick-back rerun on r7.
* **Round 3 (pessimistic 750 MHz speed-up attempt, NOT published; candidate source `r7slicer/slicer_compact.r7g.py`, layout `r7slicer/sl7`):**
  where the 667 ps window goes (full pessimistic, ss/32/3.15, 750 MHz, extracted probe of D2): 2oa crosses 1.575 V 555 ps
  after CK (VSA droops through the 6 × 8 µm header), lq falls at 626 ps, lqb rises at 980 ps, Q at 1160 ps.  Levers tried on
  the extraction (errors /51 quarter): tail ×1.4 7, SR-NOR PMOS ×2 21 (worse: more 2oa/3ob load), NMOS cross pair ×1.5 15,
  header ×2 1, header ×2 + tail ×1.2 0/0.  Built as r7g (NHDR 12, tail 8 × 6 µm, **+8 µm tail gate ≈ +11 fF per CKPk over
  r7, ≈ +24 fF over r6**): pessimistic 625 MHz 0/0; **750 MHz 1/51, 1/59 (not 0)** (with tail 7 µm or header 16 also 1–6
  errors: at the edge of this topology); nominal 834 MHz ss 0/0, ss+Rg 0/0, tt 0/0, ff 0/0 with the measured aperture
  (5/51 with the fixed 100 ps aperture assumption, i.e. the sampling instant moves ~13 ps earlier at ff); safe 0.092 V @ 85 °C;
  ss trim max step 1.54 mV, range −61.8/+55.9 mV; **ff trim fails: max step 2.2 mV and p-seam up to 5.9 mV (f0/f3 weights
  collapse to ≈ 0 on the ws_sa samplers)**.  So r7g is not publishable; `slicer_compact.py` is back at the published r7 values.
  Low-risk alternative for the pessimistic 750 MHz point: a separate header per sampler pair is already in place; the next
  options are an NMOS-input StrongARM (needs CM ≥ 1.2 V from the CTLE), or keeping 750 MHz for nominal corners only and
  running the 1.485/1.5 Gb/s modes ×1 (one bit per sampler, quarter-rate sampling) on a 371–375 MHz ring (BAND=0, WT21; no ring above 625 MHz).
* Safe state: relies only on the SLI7-R hardware interlock (requested, pending digital acceptance) (ptrim_en forced low whenever slicer_en is low); the
  ring-clock-running 'off' case is not a supported state.
* Not done (box load): optimistic fast/low-C bounds (hold/race to capture, SR metastability window, trim at optimistic ff).
* **Round 4 (decision: pessimistic gate ring ≤ 625 MHz; 742.5/750/810/834 MHz nominal-corner only; interface row SLI7-G):**
  the reverted source rebuilds the published layout exactly (776 devices, every net C identical; DRC 0, LVS unique, KLayout 0/0).
  **Fast-side bounds on the published r7** (optimistic netlist `r7slicer/opt.py`: extracted C ×0.85, S/D junction ×0.75,
  no Rg; ff/22/3.35):
  - ring plan with the measured aperture (80.5–80.8 ps): 625 and 834 MHz quarter/half 0 errors.
  - **minimum sampler clock-to-output** (sampling instant → D/E edge): 327 ps (D1) … 402 ps (E0), i.e. 0.20 T at 625 MHz
    and 0.27 T at 834 MHz; outputs then hold for one ring period.  This is the hold/race bound the pt_wrx_cap
    re-capture select (k) must clear (capture owner: check against the CKP(j+k) edge plus capture hold at its own fast corner).
  - trim at optimistic ff: max fine step 1.76 mV; coarse/fine seam measured directly (p0+f15 vs fine minimum) ≤ 1.25 mV
    (e3), n side ≤ 0.86 mV; range −80.8 / +69.7 mV.
  - SR-latch metastability window: NOT measured (needs a dedicated sub-mV static-input bench; open).
* **Round 5: StrongARM/SR-latch metastability (published r7; `r7slicer/meta.py`, static input, ring 625 MHz, sampler D0):**
  regeneration τ from the exponential growth of |2oa−3ob|: **ss/32/3.15 75.5–78.9 ps; optimistic ff/22/3.35 42.8–45.2 ps.**
  Resolution time (|2oa−3ob| = 0.3 V after CK) for 10 mV beyond the trip point: ss 579 ps, ff-opt 311 ps.
  The ramp-measured offset was off for the static bench (the effective δ of the "≈0" runs was 1.2 mV at ss and 6.7 mV at ff),
  so the window comes from t(δ) = t10 + τ·ln(10 mV/δ), not from a measured sub-mV sweep.
  - Unresolved-input window when the StrongARM resets (half-period 800 ps): **ss ≈ 0.6 mV, ff-opt ≈ 0.15 µV.**
  - If the SR latch continues with the same τ up to the re-capture (~1.1 ns, assumption: SR τ not separately measured):
    ss ≈ 14 µV.
  - Rate: D samplers sample mid-eye (≥ tens of mV), so metastable events there are negligible for an open eye.
  - **Edge samplers sample the transitions by design.** With a 4 mV/ps data edge and transitions spread over ±200 ps,
    the estimate is P ≈ 1.7e-5 per edge sample at ss → ~2e4 metastable E events/s at 625 MHz quarter rate
    (MTBF ≈ 50 µs; at the 800 ps window ~1e6/s).
  - The E bits feed only the bang-bang phase detector, which already treats them as random at the crossing.  But the
    capture flops must not see an unresolved level, so pt_wrx_cap / digital must re-time E0..E3 through a second flop
    stage before any logic (capture owner).
  - Not done: a dedicated SR-only τ and the capture-flop τ.
* **Round 6 (re-review conditions):**
  - Trim data provenance: the published-layout trim numbers are `r7slicer/sl3/tf2_<c>_fine16.json` (sl3 sampler internals ==
    sl6), summarized per stage in `r7slicer/trim16_sl3_<c>_summary.json`; optimistic ff in `trim16_sl6opt_ff_summary.json`.
  - **Fine-weight disclosure:** at optimistic ff the ws_sa (d) samplers' f0/f3 weights shrink to 0.0–0.66 mV, and e3's f0/f3
    weights are slightly negative (−0.21/−0.22 mV), so the fine code is NOT monotonic there.  Not fixed (cheap fixes move other
    corners); calibration must search the 16 measured codes per sampler and must not assume monotonicity (as MT01-W3 already
    states).  The coarse/fine seam: the **real gap is the directly measured one, ≤ 1.25 mV** (|p0+f15 − min(fine)|, e3,
    optimistic ff); the 4.0 mV "seam_p" figure is the additive estimate coarse_p − span, which ignores that p0+f15 is measured
    together and overlaps — it is not a gap.
  - BAND=0 rate (WT21 1.485/1.5 Gb/s ×1): ring 371 MHz ss/32/3.15 extracted, ideal stand-in ring clocks: 0/68 quarter, 0/68 half.
  - **E-sampler τ at the pessimistic values (ss, Rg 200, +25 % device incl. junction/overlap, +15 % wiring; E0, 625 MHz):
    96 ps**, 10 mV beyond trip resolves (|2oa−3ob| = 0.3 V) at 744 ps of the 800 ps window; at δ ≈ 0 it did not resolve
    within the window (expected).  Window at the StrongARM reset ≈ 5.6 mV; with SR continuation to ~1.1 ns re-capture
    ≈ 0.25 mV → many E-sampler metastable events per second at 625 MHz (≈ 3e5/s with the round-5 edge-slope model).
    The E0..E3 re-time stage (interface row SLI7-M) is therefore mandatory.

### Resume 7 / DETECT (fork DET7, 2026-11-11; scratch `scratch/wired_rx/r7detect/`; published `generated/detect.*`)

`pt_detect` r7, ports unchanged (interface DT7-1..3).  **173.5k µm² (≤ 180k), Magic DRC 0, LVS unique (424 dev), KLayout
main 0 / antenna 0.**  Not yet independently reviewed.
* **HBM (PD29 item 4, risk PAD-02):** per TX leg, series poly R (3 → 6 kΩ injection branch TXF, 20 kΩ sense branch TXS) +
  a 7-high string of p+/nwell junction diodes to VSS (pfet_06v0, S=D=anode, G=B=cathode, own well; injection branch 2×
  area) + an off nfet_06v0 negative clamp; every device on TXF/TXS is 6 V.  A rail diode (TXF→VDD) was rejected: it
  back-feeds the island from an unpowered 3.63 V TX pad.  `pads/hbm_core_screen.py` on the extraction:
  **wire_tx_detect 0 of 340 MOS over the screen** (tt27 / ss0 P_pos, ss0 P_neg; worst 5.57 V on a 6 V gate at ss0 vs
  6.0 V, was 6.89 V with 4 exceedances in r6); **wirepad_rx_core 0 of 658**.  The junction diodes are BSIM S/D
  junctions, not a qualified diode model: pads asked for a qualified secondary-clamp cell / diode support (DT7-2).
* **Receiver detect at ss (was failing):** injection mirror 10→12×, 6 V switch 20→40 µm: inject 96–130 µA over the 12
  corners (limit 60–160), present/absent discrimination passes everywhere.  6-diode strings leaked 1.75 µA unpowered;
  7-high: **unpowered `i_ain` 0.72 µA (≤ 1 µA)**, off 0/27/85 °C pass.
* **USB squelch/disconnect level shift:** the r6 4-input comparators compared the RX pair (line CM) with ladder taps at
  0.5 V CM; extracted thresholds moved 32 %/V with line CM (disconnect 446–616 mV over CM −0.05…0.45 V vs the
  525–625 window).  r7: matched 400 µA PMOS source followers (own wells) feed the diff comparators; their reference
  VTHP/VREFN = CM ± Vthr/2 floats on the followers' CM (100k sense pair + 5T-OTA buffer), Vthr = poly ratio × the VDD-ratio
  ladder tap via an OTA V-to-I (10 µA).  Equal 0.45 pF on both reference nodes (kick-back; undecoupled they sat ~180 mV
  below the inputs at the decision edge); RX transfer gates 3× (DP edge was TG-RC limited, ~1 ns).  **Extracted
  thresholds** (ramp bench): squelch (code 2) 116–126 mV, disconnect (code 3) 557–605 mV over ss/32/3.15 CM −0.05 …
  ff/22/3.35 CM 0.5 (CM sensitivity ≈ 2 %/V).
* **Gating benches tightened to the USB edges** (`tb_detect`): squelch fires at 150 mV / silent at 100 mV, disconnect
  fires at 625 / silent at 525 mV (r6 used 300/60 and 800/400 mV), at line CM −0.05 / 0.2 / 0.5 V (squelch) and −0.05 /
  0.2 / 0.36 V (disconnect; current-mode CM = Vdiff/2 + 50 mV offset).  **12 corners + nominal extracted: all gating
  cases pass** (min fire fraction 0.99, max silent-window fraction 0), FS line state and receiver detect pass, supply
  ≤ 2.38 mA (budget 4).  **FAIL (gating, coordinator restored it): disconnect at CM 0.5 V at ss/22 and ss/32 3.15 V**
  (fire fraction 0.31; follower output ~1.75 V is above the PMOS comparators' working CM range).  It was briefly
  made non-gating; that was reverted, and the evidence now lists both corners as failures.
* **Enable time (new):** DIFF_POS/DIFF_NEG valid 100 ns after `det_en` (bias/reference settling); benches start the
  stimulus at 100 ns.  Digital masks DIFF_* for ≥ 100 ns (DT7-1).
* **Open / weaknesses (for the reviewer):** (1) **schematic nominal fails the disconnect cases** (schematic code 3 =
  674 mV vs extracted 566–586): the threshold depends on comparator kick-back into the LS/reference nodes, i.e. on
  the extracted LS wiring C; the calibration is on the extraction.  This is a parasitic-sensitive design point.
  (2) USB RX loading with detect off 154 fF (published r5 93 fF), TX 142 fF (111): pads to recheck the v9 2.7 pF USB
  C budget (DT7-3).  (3) Not simulated with the v9 wirepad model in the loop (ideal line sources at the RX port);
  480 Mb/s data patterns, mismatch MC and noise not run.  (4) The −0.05 V CM disconnect case is not physical for a
  current-mode bus (one line at −0.36 V) but passes.
* **Follow-up attempt (not published; `scratch/wired_rx/r7detect/netlists.r7h_wip.py`).** I tried three fixes for the
  CM 0.5 V failure and the kick-back sensitivity:
  - **Follower + I·R down-shift.** A single fixed shift cannot cover the range: line −0.36…0.81 V plus the PMOS Vsg
    corner spread (~0.3 V) is wider than the 0.2…1.6 V window of the comparator and chain sink.
  - **0.75 poly divider after the followers, chain scaled by the same ratio.** In schematic, CM 0.5 and −0.05 V
    disconnect pass at ss and ff (thresholds 124 / 574 mV at tt).  Extracted: thresholds 8 % low (526–536 mV at tt,
    497 mV at ss) and 1.5 ns edges (fire fraction ~0.52).
  - **Removing the decoupling caps** (10× chain current to match the node impedances): schematic code 3 moves to
    694 mV.

  Conclusion: the 4-input comparator's threshold depends on kick-back into the four input nodes, so the ×0.85/×1.15
  extracted-C requirement cannot be met by tuning.  The proposed fix is an architecture change.  Insert ±Vthr/2 as
  I·R offsets on each follower output (sink/source currents from the V-to-I converter, selected by code), so each
  diff comparator becomes a symmetric 2-input comparator: the same structure on both inputs, a ratio-set threshold,
  and no CM dependence.  Not built yet.  Also not done: the v9 wirepad-in-the-loop check.
* **r7i (approved I·R threshold-shift architecture), not published; `scratch/wired_rx/r7detect/STATUS.md`.**
  - Schematic: CM-independent (code 3 714 mV at both CM 0.2 and −0.05 before calibration).  After calibration:
    124–134 mV / 554–604 mV over tt, ss CM 0.5 and ff CM −0.05.  All gating cases pass at tt and ss, but the
    disconnect fire fraction is only about 0.52.
  - Extracted, 20 µA strings in w2 poly (178.7k µm²): disconnect never fires at ss/ff, squelch fires in 25 % of the
    silent window, and pos/neg thresholds split by up to 50 mV.  The tap nodes sit at ~8.7 kΩ against the routing C.
  - The fast version (100 µA, w10 strings) is 240–258k µm², over the 180k ceiling.  Blocked pending a decision on
    area vs current (see the report to the coordinator).


### Resume 7 / CAPTURE (fork CAP7, 2026-11-11/12; scratch `scratch/wired_rx/r7cap/`, see STATUS.md; generated/ NOT replaced)

* **Gearbox moved to the digital macro (coordinator decision 1; interface W7-GEAR).**  `wc_gear` is deleted from
  `capture.py`; ports `DX0..39`/`WCLK40` → one `WSTB` (wc_ctl's private GW copy GWT).  The macro registers
  DW/EW/SLP/SLM on the WSTB rise (= the word loaded at the previous strobe), puts a second flop on EW (metastability),
  and does the 2:1 gear and S3 40-bit boundary itself.  The bench now checks that consecutive WSTB-rise samples are
  consecutive 20-bit PRBS words (replaces the DX check) and reports the DW/EW change time after the WSTB rise.
* **Floorplan:** `split(fn, cuts, rev)` folds `wc_front` into 2 rows at gate group 102, where only H/Z (into the CKP0
  P/Q stage) and static nets cross (asserted: no gated clock crosses).  A first column-balanced 3-way cut put
  CKF2/CNF/CKQ2 across rows (ext q625 15 errors, wrong PD votes); a clock-safe 3-way cut also crossed FR0..7/F5..7
  (half-period RCS=1 paths).  Piece 1 is mirrored (snake).  Pair rows hold one slot cell's pairs each, grouped by lane
  and lane-aligned, directly below SL0/SL1 (a lane-ordered build with SL1 four rows away gave 1 error on pair 2).
  Antenna: N+ diodes on gate-only crossing nets, on mirrored static ports (RCS, ENB) and on the pair GCK input.
  **1181.3 × 241.5 µm = 0.285 mm²** (r6 published 0.938), Magic DRC 0, LVS unique, KLayout main 0 / antenna 0.
* **Safe state:** an intermediate build drew 15.9 µA (EN=0, S static); a per-instance supply probe showed 8.7 µA in
  `wc_cnt` (LDE toggling into the transparent TSPC input stage) and 6.9 µA in the front input piece.  `wc_cnt` now
  gates LDE with EN (NAND, LDE on the ground-side device).  Final: **7.31 µA**, outputs ≤ 0.03 V (limit 10 µA).  The
  interlock is now a hardware AND in the macro (W7-SAFE).
* **Extracted results, final layout** (`stage/results.json`; ideal ring phases and sampler outputs):

  | case | corner | result |
  |---|---|---|
  | q625 (RCS 0) | tt/27/3.3 | 0/200 data, 0 edge, PD ok, strobe words ok; DW after WSTB 0.955–1.069 ns |
  | safe, S static | tt | 7.31 µA, outputs ≤ 0.03 V |
  | q480_r1, d_lat 327 ps | ff/22/3.35, extracted C × 0.9 | 0/200, 0 edge, PD ok; DW after WSTB 0.752–0.854 ns |
  | q480, q625_lde60, q625_r1 ff/opt, q625_ss_r1 | | see STATUS.md / results.json (filled in on completion) |

  327 ps is slicer r7's earliest output edge at its optimistic fast corner (RCS=1 hold check: local clock delay +
  hold < slicer minimum delay).
* **q834 fails (pre-existing, not an area regression).**  On the pre-LDE-gate build of the same floorplan: ext q834_r1 tt
  21/200 data, 30 edge errors, PD DN votes 0.20–0.34 (must be 0); ss/32/3.15 q834_r1: no word ever loads (WSTB never
  rises).  The published r5h never passed it either (stored ext q834_r1: 3 data / 8 edge, DN 0.22–0.29).  The PD
  failure is common to both, so the front/PD at T = 1.2 ns is the limiter; the r7 split adds wire on the H/Z
  crossings.  Not fixed here: WT21 caps the ring at 625 MHz and SLI7-R passes only 625 MHz at the pessimistic values.
  Coordinator decision needed: drop the q834 gate (publish r7) or a front/PD re-pipelining round for 834 MHz.
* **Capture flop τ** (`r7cap/tau`, schematic ss/32/3.15, keeper TSPC, 10 fF): 0.19–0.22 ns (clock-to-Q 0.53 → 0.78 ns as the
  data edge approaches the 36.5 ps boundary).  MTBF in W7-GEAR.
* **r7j–r7m (follow-up on the coordinator's directions), not published.**  80 µA strings (tap R / 4), strings interleaved
  by comparator pair, delayed strobe 1.5–2.1 ns, TG 3/4: 179.7k µm² clean.  Extracted gating still fails (squelch fire
  fraction 0.48–0.50, disconnect 0.22–0.26).  The limit is LT settling (τ about 2–3 ns: string-node C through the 750 Ω
  divider), and iavg is 3.78 mA of the 4 mA budget.  Details in `scratch/wired_rx/r7detect/STATUS.md`.


### Resume 7 / CDR (main agent, 2026-11-12; scratch `scratch/wired_rx/r7cdr/`, `r8impl/`)

* **1050 vs 632 MHz explained (small bench):** cl.py used the SCHEMATIC r9 ring; the 632 MHz point (fsweep tag `r9extp`) is the
  EXTRACTED ring. Schematic ring, ideal VCTRL: 1055.6 MHz / 4.28 mA @ 1.236 V = cl.py (1050, 4.28 mA). Wiring C: 1.59-1.66x.
  `r7cdr/discrepancy.json`. Schematic-ring CL runs and the 1225 MHz/V Kvco are not representative.
* **Bench ladder (`r7cdr/cl.py`, small first):** ideal 8-phase ring + ideal votes vs `cdr_pi_model` (same gains): +600 ppm locks in
  both (49 ns, margin 0.42 UI); +3000 ppm fails in both (beyond P range); inverted votes (broken case) 788 slips; SJ 5 MHz 0.18 UI
  passes / 0.39 UI fails in both.  Ideal ring + extracted pt_cdr (r9 compact, `r6area/cdr_c20od`): locks, margin 0.40 UI.
  Note: `cdr_pi_model` preloads the integral with the offset (fll_res_ppm default) - earlier model "acquisition" assumed the FLL.
* **Extracted closed loop (published r9v ring + extracted pt_cdr, tt, 33 fF/phase, ring 585.4 MHz, start = FLL window):**
  bench fixes first: REF kick pulses latch HOLD (else the ring PFD pumps VCTRL down), 60 ns ideal VCTRL precharge, 80 ps vote/data
  edges and 10 fF on floating outputs (cured the timestep aborts; tolerances NOT loosened).
  - +500 ppm, P path only (pt_cdr off): **locks, 250 ns, margin 0.41 UI**, pk phase 0.087 UI.  g1: locks, margin 0.40 UI.
  - g3 from +1000: locks then drifts away (VCTRL falls while UP votes 52 %); g4/g6 run away (-12400 ppm at g6).
  - **Root cause (blocking, pt_cdr r9 design bug):** standalone extracted pt_cdr, g3: UP static +4.7 nA, UP toggling at 585 MHz
    (50 % random) **-4.8 nA**, 25 % **-6.0 nA**; AVP-AVN collapses (+1.2 V static -> -63 mV toggling).  The 0.6 uA steered halves
    cannot re-steer within a ring cycle (source node ~5 fF x 0.3 V / 0.6 uA ~ 2.5 ns > 1.7 ns), so votes at ring rate do not
    integrate and switch asymmetry decides the sign.  Fix = pt_cdr r10 (NOT built): ~20 uA steered halves (75 ps re-steer),
    averaging R/C scaled (7.5 kOhm || 7.3 pF/side, same 55 ns tau, ~0.15 V/vote), +~160 uA; ports unchanged.  (risk: WRX-01)
* **Ring vote injection fixed** (r9v, published by the ring ECO agent, row RING-ECO): extracted full top tt sync votes alt -228,
  rnd +32, tog -259 ppm, spread 291 ppm (<= 300), 858 ppm/vote (r9d: +4279 / +2948).  Phase spacing at ss = r9d within 2.4 deg.
* **Ring low band <= 300 MHz (WT21 update), extracted r9v BAND=0:** ss/32 110 MHz @ 1.0 V, ss/22 193 @ 1.1, sf/27 128 @ 0.95,
  tt 200 @ 0.95, ff/22 261 @ 0.85 (295 @ 0.875), ff optimistic 243-247 @ 0.85; top HI ss/32 867, LO ss/32 754 @ 2.05 V; ff HI
  starts 398 @ 0.85 and LO reaches 1356 @ 2.05 (bands overlap).  Pessimistic HI top: rerun needed (60 ns window too short).
* **CDR model, two-sided gain (quarter/half):** uncalibrated KP fails (340 ppm/vote 0.73-1.06x); per-die KP calibration (row
  CDR7-KP): quarter 430-710, half 1700-1980 ppm/vote, integral 800-1600 ppm/us; lat 7 (with SLI7-M re-time) 1.03-1.19x.  The
  extracted runs show the model is optimistic on integral stability (g4 ~2400 ppm/us unstable extracted) - recalibrate after r10.
* **Eighth rate (R8-ARCH) JTOL with the real masks** (design-assumptions DA-JTOL-SATA2 / DA-JTOL-HBR; masks are pk-pk, model uses
  peak = pk-pk/2): SATA G2 (ring 375) **1.9-2.75x** at 200-400 ppm/vote, lat 4-6.  **DP HBR (ring 337.5) fails at 0.5 MHz**
  (mask 6.95 UI pk-pk): best 0.63x (750 ppm/vote, lat 3, 3200 ppm/us); 1-100 MHz pass (>= 1.06x).  A fast integral OTA
  (pole 420 -> 30 cycles) does not fix it (0.5 MHz 0.59-0.91x, then 1-2 MHz peaking).  0.5 MHz needs ~+-4000 ppm tracking
  (2 pi 0.5 MHz x 3.5 UI); the BB P path gives ~(transitions/cycle ~4) x KP.  OPEN: loop architecture for HBR LF (see report).
* **Update (later 2026-11-12):**
  - **pt_cdr r10 built** (netlists.cdr(), cdr.spice regenerated; r9 backup `scratch/wired_rx/r8impl/cdr.r9.spice`): steered halves
    ~10 uA (8/2 PMOS), switches 2/0.28, AVP/AVN 1.25 kOhm || 20x20x8 MOS cap, OTA mirror kept 0.5/2 (0.5/0.5 gave -0.22 vote idle
    offset).  Scratch layout `r8impl/cdr_r10_c20/gen`: **174,363 um2 (288x409 r9 compact 117,842), DRC 0, LVS unique, KLayout 0/0.
    NOT published to generated/ (generated/cdr.* is still the stale r-ac3 cell).**  Extracted steering (tt): g7 idle -1.16, 1 leg
    +20.3, 2 legs +38.8, toggling 25 % +16.1, 50 % +34.7 nA; g3 idle -0.13, 1 leg +1.56, toggling 50 % +2.60 nA -> correct sign;
    residual toggling offset ~ -0.2 vote.
  - **Ring r9w** (common-mode-latch fix, row RING-ASYM, published): full-pessimistic start ss 641 / tt 541 MHz extracted.
  - **First extracted closed-loop lock with the integral path** (r9w + r10 ext, tt, 580.7 MHz data, KP code 2, g5): from +1000 ppm
    lock 97 ns, margin 0.43 UI, pk phase 0.07 UI, ring 0 ppm vs data, VCTRL steady (run ends 1.14 us on a timestep abort).
    From -1000 ppm: acquires late (710 ns, 18 wraps), margin 0.24 UI, ring drifting to -800 ppm at 0.82 us, abort at 1.01 us:
    NOT clean.  Per-leg votes are pinned (leg0 UP only, leg3 DN mostly) because the bench has no ptrim and the r9w port phase
    errors (to -15 deg) place the legs on different sides of the edge -> reduced effective P gain; next: add the ptrim stand-in
    (per-leg delay calibration) to the bench, then HBR settings (lat 2, high integral rate).

## Resume 9 (2026-11-13/14): area pass 4 (AP4-1) and mode-walk findings (MW-8..14, MW-23, MW-31)

State of each block after this resume (details below; pin list and connection intent for chip-top: `PINS.md`):

| block | outline before | outline now | state |
|---|---|---|---|
| `pt_wrx_cap` | 1452 × 659 µm, 0.956 mm² (r6) | unchanged in `generated/` (r6) | r7 compact 1199 × 242 = 0.290 mm² clean but review NO-GO (ss/625 PD votes); r7b fix built, extracted verification running; outline given to assembly (AP4-1-CAP) |
| `pt_ptrim` | 449 × 645, 0.290 | unchanged (published cell is not functional) | compact layout of the present circuit staged at 126 × 205 = 0.026 mm², NOT published: MW-14 needs a circuit fix first, one layout for both |
| `pt_cdr` | 428 × 320, 0.137 (r11, unreviewed) | unchanged in `generated/` | r13 staged at 259 × 320 = 0.083 mm², DC checks pass, 14 ring-rate transients + review pending |
| `pt_detect` | 251 × 690, 0.173 | unchanged | layout-only repack fails extracted thresholds; needs the r7i threshold redesign |
| `pt_ctle` | 225 × 594, 0.133 | unchanged | repack staged at 194 × 354 = 0.069 mm², review NO-GO (antenna) and on hold for the MW-13 output-stage fix |
| CDR `pt_pll_ring` | 210 × 794, 0.167 | unchanged | no floorplan-only saving (core alone 0.132 mm²) |

### Resume 9 / PTRIM (scratch `scratch/wired_rx/r9ptrim/`; nothing published)

* **MW-14 reproduced (extracted, `sims.tb_ptrim`, 625 MHz).**  Real per-phase loads summed from `generated/slicer.ext.spice`
  and the r7 capture extraction: **CKP0 965 fF** (590 fF of it is capture wiring), CKP1..7 371–482 fF, plus a 30 / 150 fF
  routing bound (`r9ptrim/load.json`).  The published layout does not work at all with them (tt: CKP1..7 low level
  0.31–0.64 V, code 31 does not toggle).  The compact layout of the same circuit: CKP0 swings 0.58–2.74 V (tt) and lags the
  other phases by 61–135 ps; at ss/32/3.15 CKP0 0.81–2.52 V and the trim range collapses (−8..+39 ps on CKP1..7).  The 8/16
  output inverter cannot drive the real load.
* **Sizing tried (scratch only, `r9ptrim/proposal/`):** middle inverter 4/8 → 12/24, output 8/16 → 32/64.  Rail-to-rail at
  ss/tt/ff, trim range 103–117 ps (23°), 18–21 mA for the eight channels.  **Open:** CKP0 still lags 45–81 ps because of its
  2× load, which leaves ~25 ps of its range at ss (ring spread needs ~50 ps).  Fix at the load (capture CKP0 wiring 590 fF →
  a local CKP0 buffer or split in `wc_front`) or a doubled channel 0; neither is simulated.  Pessimistic bounds, 810 MHz and
  the 12-corner set are not run on the proposal.
* **Compact layout (`ptrim_compact.py`, new, not wired into `run_family`):** one compact row per channel, eight identical
  rows, PHk/CKPk/Tk on Metal2 at the east edge of their own row: 126.4 × 205.2 µm, DRC 0, LVS unique, KLayout 0/0;
  channel-to-channel skew 0.015° at equal loads (a first top with all pins on the top edge through Metal5 trunks had 15 ps
  skew: do not use).  With the 150 fF bench load: 625 MHz tt and ss pass (22.3–22.9°, step ≤ 0.91°); **810 MHz fails the
  existing criterion** (step 1.06° at tt/32/3.35; ss/22/3.15 non-monotonic at the top codes): the trim node carries ~45 fF of
  layout parasitic and the schematic had < 5 % headroom, so the redesign must retune the unit cap / NAND as well.  CKP duty
  changes with the trim code (fall delay moves 187 ps vs 86 ps for rise at tt).
* The published `generated/ptrim.*` stays as it was (not functional, WRX-15).  Next: one redesign (output stage, unit cap,
  CKP0 load) laid out once with `ptrim_compact.py`, benched against the extracted slicer + capture clock pins.

### Resume 9 / CDR and RING (scratch `scratch/wired_rx/r9cdr/`, see STATUS.md; nothing published)

* **State found:** `generated/cdr.*` is r11 (copied in by the previous agent, unreviewed; its evidence fails VCTRL
  compliance at ff/22/3.35: 0.159 vs 0.15).  The tree source was already r12 (5-bit + sign offset trim `otr0..4`/`otrs`,
  six new static pins, never built).
* **r13 = r12 + output mirror 0.5/2 → 1/4** (`netlists.cdr()`, `cdr.spice`).  Staged layout (rows filled to 260 µm with the
  new opt-in `wrx_flow` `row_width`, tracks and trunks over devices): **259.2 × 319.8 µm = 0.0829 mm²**, 488 devices,
  Magic DRC 0, LVS unique, KLayout 0/0 (row widths 300/360 leave ANT.16 violations; the precheck must be re-run alone before
  publishing, see the CTLE review).  Extracted, criteria unchanged from r11: compliance tt 0.083 / ss 0.073 / ff 0.099 /
  pessimistic ss 0.073 (limit 0.15), idle offset 0.05–0.11 vote, 20.4–22.6 nA/vote, trim LSB 0.13 vote, range ±2.7–3.05
  votes; tt ring-rate dn50 −1.79 (−2), bias 0.78 (1).  Control: r10 extracted fails compliance on the same bench; the bench
  reproduces the published r11 numbers.  **Pending:** 14 ring-rate transients (`r9cdr/queue.sh`, one at a time), judge with
  `mkev.py r13_rw260to b_r13 r13`, independent review, then `publish_cdr.sh r13_rw260to`.  Closed loop, mismatch MC and the
  EN/safe sweep are not rerun on r13.  **Until then the tree source (r13) and `generated/` (r11) disagree.**
* **Closed loop (previous agent's finished runs, r11 extracted + r9w ring, tt):** HBR settings (lat 2, KP 4, g7) lock from
  +1000 ppm in 161 ns and from −1000 ppm in 574 ns, margin 0.36 UI, phase error 0.06 UI mean / 0.14 pk; both runs aborted
  at 1.04 / 1.18 µs.  Quarter (lat 8, KP 2, g5) from −1000 ppm acquires only at 1149 ns after 37 wraps: not clean.
  Open-loop idle VCTRL drift −1.45 mV/µs (g3) and −1.21 mV/µs (g7): it does not scale with g, so it is ~8–9 nA on the
  ring / bench side (not the pt_cdr OTA offset), ≈ 0.4 vote at g7 and more at lower g.  The FUP step is correct
  (+5.7 mV/µs at g7).  Not yet located (ring loop-filter / PFD leakage in HOLD, or the bench precharge source).
* **CDR ring outline:** unchanged, 210.0 × 793.5 µm.  The core alone is 198.1 × 664.6 = 0.1317 mm² (> the 0.115 target);
  the fast-tune macro, gap band and left channel (0.035 mm²) are already tight.  The only slack is a device-free band at
  y ≈ 258–447 inside the core left by the fast-tune ECO (~39k µm²); collapsing it gives ≈ 0.127 mm² and needs a core ECO
  plus full ring requalification (vote-injection spread is 291 vs 300 ppm): not started.
* `analog/timing/fastcells.py` `ASYM_RESET` regenerates the published r9w `ct_ring9` netlist exactly (and
  `ASYM_RESET = False` does not).
* **Ring start-up checks (previous agent, `scratch/wired_rx/r9pub/ringstart/`, pessimistic ss/32/2.69 HI 2.05 V):** supply
  ramp 1 µs and four mismatch seeds (A_Vt 14 mV·µm) start in differential mode at 649–651 MHz; **the 1 µs EN ramp case does
  not start (outputs flat)** and pessimistic tt band 0 at VCTRL 0.95 V with mismatch does not oscillate.  Neither is
  diagnosed (bench or circuit); open.

### Resume 9 / DETECT (scratch `scratch/wired_rx/r9detect/`, see STATUS.md; nothing published)

* The working-tree `detect.spice` is the published r7f cell (it matches the evidence source hash and `netlists.detect()`
  regenerates it).  Published cell today: all gating passes at 13 corners except disconnect at CM 0.5 V at ss/22 and
  ss/32 3.15 V (fire fraction 0.31), which is pre-existing.
* **Layout-only repack fails.**  178.3 × 426.7 µm = 76.1k µm² is DRC/LVS/KLayout clean, but extracted at tt the squelch at
  150 mV never fires and disconnect at 625 mV fires 0.19–0.50 of the window: ramp thresholds move from 116 / 566–576 mV
  (published) to 165 / 635 (tt), 137 / 587 (ss), 195 / 665 (ff).  Restoring node capacitance (explicit caps, ideal ground C,
  all C × 1.5) does not recover them and no coupling grew by more than 3 fF; the cause is not found.  The thresholds are
  tuned to the published extraction (weakness 1), so the 0.09 mm² target waits for the r7i threshold redesign.

### Resume 9 / CTLE (scratch `scratch/wired_rx/r9ctle/`; review `scratch/reviews/ap4-ctle-review/review.md`; nothing published)

* Same netlist, 22 columns, tracks and Metal5 trunks over the devices (`wrx_flow` `trunks_over`, default off):
  194.2 × 353.9 µm = 68.7k µm².  Extracted 13 corners × 18 AC cases all pass (as published); 2.5 GHz gain +1.2 dB, code-0
  peaking 0.77 → 1.05 dB, bypass bandwidth 2.46 → 2.83 GHz, input C 203–208 fF per leg (was 261–267).
* **Independent review: NO-GO as staged.**  The staged GDS has 2 antenna violations (`ena_b`, ratio 408.9 vs 400): the
  recorded "antenna 0" came from two prechecks sharing `scratch/kl-block-drc/flows/ctle/`.  Flow gaps found:
  `antenna_diodes.plan` can return unplaced requests that `wrx_flow`/`run_family` never check, `evidence.write` ignores
  the precheck, and the precheck sha is taken from the source path.  Also new with over-device routing: asymmetric
  Metal4/5 over the matched input pair (not modelled; the CTLE has no offset trim), and the `sp`/`atb_ctle_src`
  wiring asymmetry grows from 4.4 % to 10.4 %.
* **On hold for MW-13 / MW-23** (CTLE with its real load, output common mode): the output stage has to change, and the
  repack and the fix are to be one layout.  See Resume 9 / MODE WALK.

### Resume 9 / MODE WALK (coordinator rows MW-8..14, MW-23, MW-31; scratch `scratch/wired_rx/r9chain/`, `r9ptrim/`)

Every block bench so far used ideal neighbours (150 fF loads, ideal clocks, 1.0 V common mode).  Reproductions with the
real extracted neighbour:

* **MW-13 reproduced: the CTLE cannot drive its real load.**  Extracted `pt_ctle` → extracted `pt_rxselect` (CTLE branch) →
  extracted `pt_slicer` SL_P/N (+ `pt_wmon_sel` off, 30 fF route), gain at SL in dB (`r9chain/res.json`):

  | case (code 0) | DC | 625 MHz | 1.25 GHz | 1.62 GHz | −3 dB |
  |---|---|---|---|---|---|
  | bench 150 fF, tt | +3.1 | +3.8 | +2.1 | +0.8 | 1.82 GHz |
  | chain, tt | +3.1 | −4.0 | **−8.0** | −10.1 | **248 MHz** |
  | chain, ss/32/3.15 | +3.4 | −5.0 | −9.6 | −12.1 | 196 MHz |
  | chain, ff/22/3.35 | +2.8 | −3.4 | −7.1 | −8.9 | 302 MHz |
  | chain, ss pessimistic | +3.4 | −6.1 | −11.4 | −14.2 | 160 MHz |
  | chain, ff optimistic | +2.8 | −3.0 | −6.6 | −8.2 | 332 MHz |

  Code 7 peaks at −2.5 dB: no absolute gain above 300 MHz at any code.  Transient (PRBS7, 200 mVppd flat input, tt, code 0):
  26 mV inner eye at 2.5 Gb/s, closed at 3.24 Gb/s (150 fF bench: 285 mV).  **The published wired RX chain is closed at
  2.5 Gb/s and above**; every CTLE/slicer result in this README above 1 Gb/s was obtained with a load or a source that the
  chip does not have.
* **Cause:** CTLE output resistance 584 Ω (tt) – 689 Ω (ss) into ~1 pF (τ ≈ 0.7 ns).  Split at 1.25 GHz, tt: rxselect
  (two TGs' C and series R) 3.8 dB, wmon_sel 0.3–0.5 dB, slicer 7.5 dB (SL input 600 fF/leg: 390 fF wiring + 210 fF gates).
  TG series R 224 Ω tt / 328 Ω ss at the real common mode.  The repacked CTLE is 0.3 dB better: the layout is not the problem.
* **MW-23 confirmed:** CTLE output common mode 1.47 V tt, 1.51 V ss/32/3.15, 1.32 V ff/22/3.35 (the slicer gating benches
  use 1.0 V).
* **Fix candidates (schematic follower + lumped wiring, AC at 1.25 / 1.62 GHz, code 0, dB):**

  | candidate | tt | ss | ss pessimistic | ff optimistic |
  |---|---|---|---|---|
  | today | −8.0 / −10.0 | −9.6 / −12.1 | −11.4 / −14.2 | −6.6 / −8.2 |
  | no TG in the fast path + SL wiring cut to 150 fF | −4.1 / −5.7 | −4.8 / −6.5 | −6.0 / −7.8 | −3.4 / −4.8 |
  | NMOS follower 60 µm, 3 mA/side, body at VSS | −1.7 / −3.6 | −3.5 / −5.6 | −4.9 / −7.4 | −0.7 / −2.0 |
  | **same follower, isolated well (body = source)** | **−0.3 / −2.4** | **−2.1 / −4.4** | **−3.7 / −6.4** | **+0.8 / −0.6** |
  | isolated-well follower + SL wiring 150 fF | +0.3 / −1.4 | −1.5 / −3.5 | −2.8 / −5.2 | +1.2 / 0.0 |

  With the isolated-well follower: eyes 229 mV (tt 2.5 Gb/s), 190 mV (tt 3.24), 105 mV (ss pessimistic 3.24; 127 mV with
  the SL re-route); code 7 keeps 13–14 dB of boost; code-0 peaking ≤ 1 dB at the optimistic bound.  A bigger follower does
  not help (the CTLE core then limits).  Shunt peaking would need ~90 nH per leg: not worth the area.
* **Proposed r4 CTLE (NOT implemented):** (1) NMOS source-follower pair at the CTLE output in an isolated well, 60/0.28 µm,
  3 mA per side (+6.3 mA, ~0.003–0.005 mm²); (2) the follower drives SL directly and is powered down in direct mode,
  `pt_rxselect` keeps only the direct (USB) gate; (3) SL_P/N re-route in the slicer 390 → ~150 fF (0.6–1.2 dB, optional);
  (4) SL common mode becomes 0.38–0.46 V (same region as the USB HS direct path): the slicer ring-plan cases must be
  requalified at ~0.4 V.  **Residual gap:** ss pessimistic at 3.24 Gb/s is −5.2..−6.4 dB at 1.62 GHz, a 120 mVppd eye
  lands at 57–66 mV (the slicer's 60 mV edge); closing it needs a lower CTLE load R with more tail current, or one
  follower per slicer bank (R8-ARCH).  No physical limit: the follower pole into 630 fF is above 3 GHz.  Caveats: follower
  is schematic devices, flat channel (no package / reference-channel loss), static slicer clocks.
* **MW-14 reproduced:** see Resume 9 / PTRIM.  The capture's CKP0 pin (965 fF, 590 fF of wiring in `wc_front`/top) is
  the worst load; a local CKP0 buffer in the capture (or a doubled ptrim channel 0) is part of the ptrim redesign.
* **MW-31** (ring phases at the regulated 0.9 × rail into 3.3 V logic): for the RX side the ptrim input NAND is the
  receiver; the mode walk measured +20 ps at tt with 2.9 V / 150 ps edges.  Corners not run; `pt_pll_vreg2` must be
  instanced for `pll_cdr` (assembly).
* **Wiring (MW-8..12):** `PINS.md` gives the exact pin list, the net list view and the missing register fields
  (hs_en / hs_term_en / hs_trim[3:0], ctle peak bit 2 and lf_zero[2:0], KP[2:0], pfd_mode, ref_sel, N5/N10, BAND, B2/B1,
  PSEL, SLIPP/SLIPM, RCS, capture EN, slicer trim widths), the missing producers (`wire_rx_valid`, the RX word clock / LDE =
  a second `pt_wordclk` on the RX ring, the FLL / FUP / FDN driver) and the island crossings without isolation cells.

### Resume 9 / CAPTURE (scratch `scratch/wired_rx/r7cap/`; review `scratch/reviews/ap4-wrxcap-review/review.md`; generated/ NOT replaced)

* **r7 compact rebuilt from the tree source (`r7cap/pub/`)**: 1199.09 × 242.21 µm (GDS bbox 1197.09 × 242.71), nine cells
  and top Magic DRC 0 / LVS unique, uniquified GDS XOR 0 against the LVS-checked layout, KLayout precheck main 0 /
  antenna 0 run alone (sha 9173d75c…, re-run by the reviewer in an isolated work dir).  The rebuild equals the earlier
  `r7cap/stage/` build (same .mag; extraction identical except capacitor numbering and one 1e-5 fF value).
* **Extracted results on that layout (ideal ring phases and sampler outputs):** q625 tt 0/200 data, 0 edge, PD ok;
  q480 tt pass; ff/22/3.35 with C × 0.9 and d_lat 327 ps: q480_r1 and q625_r1 pass; safe (EN = 0, S static) 7.10 µA;
  negative control (S2 stuck low) reported failing with 11 data errors on exactly the D1 bit positions.
  **ss/32/3.15 q625 FAILS:** data 0/200, but 1 edge error (EW16), **DN vote activity 0.11–0.29 (must be 0)**, DW/EW change
  0.975–1.672 ns after WSTB (pair 16 resolves late).  r6 has the same PD cell and no ss run on its final layout (the last
  ss run of an earlier revision had 2 data / 3 edge errors), so this is not an area regression, but it is an in-window
  failure at a production rate: **the AP4-1 premise "blocked only by q834" was wrong.**
* **PD root cause (full-top probes `pd_tt625`, `pd_ss625`, `pd_an.py`):** the vote flops' D inputs keep changing from
  0.46 to 1.17 ns (tt) / 0.65 to 1.52 ns (ss) after the octet launch; the vote clock arrives 1.38 (tt) / 1.33 ns (ss)
  after the launch (mod T = 1.6 ns), i.e. 0.21 ns after the last change at tt and inside the changing zone at ss.  The
  slow part is the O → On 1/2 inverters driving the XOR NANDs across the 450 µm cell.
* **r7b fix (in `capture.py`: `PD_DELAY` 6 → 10, `PD_INV` (1,2) → (2,4)).**  Cell-level bench `pdv/pdcell.py` (extracted
  `wc_pd`, octet launch time and bit skew from the probes; **known answer: reproduces the full-top r7 result, tt 0 vote
  errors, ss 36 errors**): r7b tt/ss/ff 0 errors, D settled 0.73 / 0.50 / 0.90 ns before the vote clock and next change
  0.42 / 0.53 / 0.31 ns after it (a 12-inverter variant left only 0.21 ns on the hold side at ff).  r7b top: same outline
  and pins, DRC 0, LVS unique.  Extracted top-level runs in progress (`r7cap/r7b/results.json`): q625 ss and tt first,
  then half rate, safe, ff hold, ss RCS=1, LDE edge, full rate.  Not yet addressed: the pair-16 R → W hand-off at ss
  (needs a probe), the pessimistic-value case, and the CKP0 pin load (Resume 9 / PTRIM).
* **Review verdict: NO-GO for r7 as built** (ss/625 failure; 12 of 16 gating cases never run on the layout, incl. every
  RCS=1 case at tt/ss although the j = 4..7 RCS=1 path was re-timed; a publish-script bug, fixed: `run_capture.py
  --results` now implies `--no-layout`).  Conditions carried over to the r7b publish: W7-GEAR timing numbers updated (row
  W7-GEAR-T: macro hold < 0.596 ns), evidence must record the netlist the runs were made on, integration views still use
  `WRX_WCLK40` and the macro has no WSTB front end (DT-9).
* `run_capture.py`: the gate is now the extracted netlist at ring ≤ 625 MHz (`NON_GATING`: 810/834 MHz cases and the
  S-toggling safe case, SLI7-G / W6-SAFE); a gating case that was not run counts as failing and is listed; a negative
  control is required; `--results STORE` builds the evidence from a results store without layout or simulation.
