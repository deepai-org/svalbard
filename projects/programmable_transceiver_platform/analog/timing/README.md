# Timing and clocking family (`analog/timing/`)

Transistor-level clock, PLL and RF-LO blocks (gf180mcuD), built to the
[block deliverable convention](../../spec/block-deliverables.md): one `.spice` per block, a reproducible Magic
layout, Magic and KLayout DRC, Netgen LVS, extracted ngspice simulation and, for the blocks of the standard flow,
a `generated/<block>-evidence.json` record. The generated files are authoritative; numbers here are copied from
the file named next to them.

Performance window: junction 22-32 C, die supply 3.15-3.35 V, all process corners; slow dies may be trimmed up to
a 3.50 V setpoint by the board. Safety window: 0-3.63 V, 0-85 C.

Chip-top pin list, nets, supplies, controls and placement rules of the RF LO: [`LO-INTEGRATION.md`](LO-INTEGRATION.md).
Chip connectivity: `integration/top/pt_chip.conn`; control decode: `integration/top/ctl_ports.txt`.

## Reproduce

```
analog/timing/run_timing.sh                    # the ten standard-flow blocks
analog/timing/run_timing.sh pll_ring,clockmux  # a subset
python3 analog/timing/lo_rows.py <block>       # one LO block with its published row plan
```

`run_timing.sh` builds the compact fast cells (`fastcells.py`), runs `run_timing.py` (layout, DRC, LVS,
nominal / safe / corner simulation; a layout is copied into `generated/` only when it passes) and `evidence.py`
(evidence JSON and the table between the `results` markers below). Layout, DRC and LVS run in
`svalbard/librelane-gf180-canary:2026.08` (Magic 8.3.623, Netgen 1.5.316); simulation and GDS export in
`hpretl/iic-osic-tools@sha256:89641950...` (ngspice 43, Magic 8.3.678). Containers run `--network none`. Decks
and logs go to `<repo>/scratch/timing/`.

| File | Role |
| --- | --- |
| `<block>.spice` | Block netlist, top subcircuit `pt_<block>`; single source for layout, LVS and simulation |
| `timing_cells.spice`, `pll.spice` | Shared cells; PFD library of `pll_ring` |
| `fastcells.py`, `compact.py` | Hand-placed fast cells `generated/fast/ct_*` with their own DRC / LVS and speed benches (`generated/fast/speed.json`) |
| `layout_engine.py`, `netlist.py` | Row / channel layout generator (one PCell per device, private tracks, fast cells as macros); SPICE reader |
| `lo_rows.py` | Row plans of the LO cells. `PUBLISHED` selects the plan the standard flow uses (`r4` for every block) |
| `timing_flow.py`, `run_timing.py`, `evidence.py` | Tool wrappers, testbenches, evidence assembly |
| `lo_ext_pad.py` | External-LO bench through pad and package models |
| `lcvco/` | QVCO netlist generator and layout (`qvco5.spice`, `qvco_layout.py`, `qvco_rf_layout.py`), spiral model (`spiral.py`), loop design (`loop_design.py`, `loop_design.json`), loop benches (`run_loop.py`) |

## Conventions

Every enable and select is active high and **0 is the reset / safe state** (block off, clock stopped). One-hot
selects carry at most one 1; all-zero means stopped. A clock select is changed only through the stopped state
(write 0, wait >= 1 us, write the new code).

## Blocks

Outline = bounding box of the published GDS (`generated/<block>.gds`). Island names are those of
`spec/power-delivery.md` (ten islands) as bound in `pt_chip.conn`.

| Block (version) | Ports | Function | Outline um, mm2 | Rail in `pt_chip.conn` |
| --- | --- | --- | --- | --- |
| `pt_pll_ring` (r9v) | `REF EN N4 N8 HOLD IBIAS PH0..PH7 LOCK FBCK REFO ATB_VCTRL N5 N10 KP0..KP2 FU0..FU3 FD0..FD3 BAND VDD VSS` | CDR ring PLL, also the host_follow PLL. See "`pt_pll_ring`" below | 210.0 x 793.5, 0.167 | `pll_cdr`: `VREG_CDR` (pll island through `pt_pll_vreg2`) |
| `pt_pll_ring_core` (r9d) | `REF EN N4 N8 HOLD IBIAS PH0..PH7 LOCK FBCK REFO ATB_VCTRL BAND VDD VSS` | Line (TX) ring PLL: `pt_pll_ring` without the fast-tune array and the N5 / N10 path | 196.0 x 438.9, 0.086 | `pll_tx`: `VREG_TX` |
| `pt_vco_replica` | `EN VCTRL OUT ATB_VTAIL VDD VSS` | `ct_ring8` ring with VCTRL forced from outside, `OUT` = VCO/16. Characterization structure | 195.5 x 107.1, 0.021 | debug |
| `pt_prescale` | `CK_IN EN D2 D4 D8 D16 CK_OUT VDD VSS` | TSPC divider, one-hot ratio | 198.1 x 63.6, 0.013 | pll, three instances |
| `pt_wordclk` | `CK EN D10 D20 WORD_CLK LDE LD LDB VDD VSS` | Word divider /5, /10 (`D10`), /20 (`D20`); `LDE` is high one CK period before the word boundary | 200.2 x 124.0, 0.025 | `wordclk_rx`: wired_cap |
| `pt_clockmux` | sources `PLLW REF AUX WCK H2D WSI CONV_INT HOST_INT HF`; selects `PS_{REF,AUX,H2D} WS_{PLL,REF,AUX,WCK} SS_{INT,REF,WCK} CS_{INT,REF,AUX,HF} HS_{INT,HF}`; outputs `PREF WIRE WSMP CONV_CLK HOST_CLK`; `VDD VSS` | Five `ct_mux4` domains, single-ended CMOS | 179.8 x 84.3, 0.015 | pll |
| `pt_diff_clk_rx` | `INP INN EN SE OUTP OUTN PRESENT ATB_DET VDD VSS` | Differential clock / data receiver with a clock-present detector. `SE` has no effect in the netlist | 198.0 x 112.8, 0.022 | `rx_ref_in`: core; `rx_aux_clk`, `rx_wtx_ext`: debug |
| `pt_clk_obs16` | `IN0..IN14 IN15A IN15B IN15C S0..S3 N0..N2 EN OUT VDD VSS` | 16:1 mux, /2^N (N = 0..7), tristate pad driver for CLK_OBS; `IN0` = off; inputs <= 500 MHz | 195.7 x 470.3, 0.092 | debug |
| `pt_clk_obs` | `IN0..IN7 S0 S1 S2 N0 N1 N2 EN OUT VDD VSS` | 8-input version; not instantiated at chip top | 195.7 x 370.4, 0.073 | - |
| `pt_obs_pre4` | `CK EN OUT VDD VSS` | /4 in front of `clk_obs16` for sources above 500 MHz | 127.8 x 28.7, 0.0037 | debug, six instances |
| `pt_ring_osc` | `EN OUT VDD VSS` | NAND-enabled 21-stage ring, process monitor | 195.7 x 48.7, 0.0095 | debug |
| `pt_aosc` (r3) | `EN CLK ATB_X VDD VSS` | Two-capacitor RC relaxation oscillator, no bias input | 199.6 x 64.5, 0.013 | core (always on) |
| `pt_lo_ext` | `EXT_IP EXT_IN EXT_QP EXT_QN LOI_IP LOI_IN LOI_QP LOI_QN EXT INT CMLSEL LO_IP LO_IN LO_QP LO_QN ATB_VB VDD VSS` | LO driver onto the mixer gates: one CML driver per phase pair with two inputs (QVCO tank, AC-coupled pad) and a passive pad path | 322.1 x 482.4, 0.155 | lod |
| `pt_lc_qvco5` | `EN CMLSEL VTUNE IBIAS BAND0..BAND3 PRE IP IN QP QN VDD VDDB VSS ATB_EN ATB_VTUNE ATB_ITAIL` | Quadrature LC VCO at the RF carrier, 4-bit band bank, two 300 um spirals | 898.0 x 652.9, 0.586 (includes the 25 um fill keep-out halo) | lo (`VDD_LO`) |
| `pt_lo_mmd` | `LP LN EN N0..N5 FB VDD VSS` | Feedback divider, VCO/FB = 2 x N | 377.8 x 955.8, 0.361 | lod |
| `pt_lo_mmd_qdum` | `LP LN EN QDP QDN VDD VSS` | Q-tank dummy of the divider input | 216.7 x 157.2, 0.034 | lod |
| `pt_lo_pfdcp` | `REF FB EN PRE IBIAS VTUNE VDD VSS ICP0 ICP1` | PFD and charge pump, Icp = 25 uA x (1 + ICP0 + 2 x ICP1) | 257.0 x 482.9, 0.124 | lo |
| `pt_lo_lf` | `CP VT VSS` | Passive loop filter | 402.8 x 482.0, 0.194 | lo |
| `pt_lo_obs` | `LP LN EN OBS VDD VSS` | LO/8 for CLK_OBS, on the tank | 200.3 x 87.0, 0.017 | lod, two instances (Q copy `EN` = VSS) |

`pll_ring_ft.spice` (`pt_pll_ring_ft`, fast-tune array) is a sub-cell of `pt_pll_ring`.

### Integration interface

* ATB taps: `pll_tx.ATB_VCTRL`, `pll_cdr.ATB_VCTRL` (net `CDR_VCTRL`, shared with `pt_cdr`), `lo_ext.ATB_VB`
  (net `ATBN_quadrature_bias`), `vco_replica.VCTRL` (force). Present on the cells and not bound to a test-bus
  leaf: `vco_replica.ATB_VTAIL`, `diff_clk_rx.ATB_DET`, `aosc.ATB_X` (must stay unloaded), `qvco.ATB_VTUNE`,
  `qvco.ATB_ITAIL`.
* Status: `rx_ref_in.PRESENT` -> `s_ref_present`; ring lock is judged by the frequency counter in the digital
  macro on `FBCK`. The analog `LOCK` pin is informative only (wrong in three of the five evidence cases).
* Bias: each ring `IBIAS` sinks 10 uA (`BIAS_pll_ring_tx`, `BIAS_pll_ring_rx`); `qvco.IBIAS` and
  `lo_pfdcp.IBIAS` take 10 uA each.
* Clock nets: `ref_clk` = `rx_ref_in.OUTN`; `AUX_CK` = `rx_aux_clk.OUTP`, clamped onto the pll island as
  `AUX_CK_P`. **The forwarded wire clock (WCLK_IN) arrives on the AUX_CLK pad pair:** `clockmux.AUX`,
  `clockmux.WCK` and `cdr.WCK_IN` all take `AUX_CK_P`; there is no separate WCLK_IN pad, receiver or
  `obs_pre4` instance. This use needs the debug island on.
* Ring references: both rings take `clockmux.PREF` (`pll_cdr` through `pt_cdr`).
* Prescalers: `prescale` (line ring -> `HOST_INT`), `prescale_conv` (line ring -> `CONV_INT`), `prescale_hf`
  (CDR ring -> `HF`, the host_follow clock).

### Register-map glue (combinational, all outputs reset to 0)

The decode is standard cells inside the digital macro; `integration/top/ctl_ports.txt` is the binding list.

| Field | Macro port | Analog pins |
| --- | --- | --- |
| `debug.clk_select.wire_line` {0, 1 pll, 2 ref, 3 aux, 4 wclk} | `c_clockmux_ws[3:0]` | `WS_PLL / WS_REF / WS_AUX / WS_WCK = (c == 1 / 2 / 3 / 4)` |
| `debug.clk_select.wire_sample` {0, 1 int, 2 ref, 4 wclk} | `c_clockmux_ss[2:0]` | `SS_INT / SS_REF / SS_WCK = (c == 1 / 2 / 4)` |
| `debug.clk_select.conv_sample` {0, 1 int, 2 ref, 3 aux, 5 host_follow} | `c_clockmux_cs[3:0]` | `CS_INT / CS_REF / CS_AUX / CS_HF = (c == 1 / 2 / 3 / 5)` |
| `debug.clk_select.host_clk` {0, 1 int, 5 host_follow} | `c_clockmux_hs[1:0]` | `HS_INT / HS_HF = (c == 1 / 5)` |
| `clockmux.config.ring_ref` {0 stopped, ref, aux, h2d} | `c_clockmux_ps[2:0]` | `PS_REF / PS_AUX / PS_H2D` |
| `clockmux.config.host_prescale`, `conv_prescale`, `hf_prescale` | `c_prescale*_en`, `c_prescale*_d[3:0]` | `EN`, one-hot `D2 D4 D8 D16` of each prescaler |
| `ring_l.config.enable`, `modulus` {16, 8, 4}, `band` | `c_pll_tx_en`, `_n4`, `_n8`, `_band` | `pll_tx` `EN N4 N8 BAND` (band resets to 1) |
| `cdr.state` or `ring_c.config.line_pll`; `ring_c.config.modulus` {16, 8, 4, 10, 5}, `kp`, `band` | `c_pll_cdr_en`, `_n4`, `_n8`, `_n5`, `_n10`, `_kp[2:0]`, `_band` | `pll_cdr` `EN N4 N8 N5 N10 KP0..KP2 BAND` |
| word divider | `c_wordclk_en`, `c_wordclk_d10`, `c_wordclk_d20` | `wordclk_rx` `EN D10 D20` |
| `rfpll.config.lo_mode` and the other `rfpll` fields | `c_lo_*`, `c_qvco_*` | see `LO-INTEGRATION.md` section 4 |
| `refinput.state` and `lo_mode` | `c_rx_ref_en` | `rx_ref_in.EN` (0 in LO modes 1 and 3) |
| `debug.clk_obs.source`, `divider_log2` | `c_clk_obs_en`, `c_clk_obs_s[3:0]`, `c_clk_obs_n[2:0]`, `c_obs_pre4_en[5:0]`, `c_lo_obs_en` | `clk_obs16` `EN S N`; the `obs_pre4` of the selected source; `lo_obs.EN` when source = rf_lo |
| `debug.replica.ringosc_enable`, `vco_enable` | `c_ring_osc_en`, `c_vco_replica_en` | `ring_osc.EN`, `vco_replica.EN` |
| `core.aosc.enable` | `c_aosc_en` | `aosc.EN` |

`clk_obs16` sources: 1 rf_lo (`lo_obs`), 2 wire_line, 3 wire_sample, 4 conv_sample, 5 ref_in, 6 aux_clk, 8 pll_vco,
9 pll_feedback, 10 ring_osc, 11 vco_replica, 12 aosc, 13 host word clock, 14 cdr_recovered, 15 characterization
rings; input 7 is tied to VSS (the forwarded wire clock is observed as source 6).

## Results

Extracted (Magic C-only parasitics), tt 27 C 3.3 V unless noted. Corners: tt / ss / ff x 22 / 32 C x 3.15 / 3.35 V.
Safe = reset-default controls with clock and pad inputs toggling at tt/27 C/3.3 V, ff/85 C/3.63 V and
ss/0 C/3.63 V. The table between the markers is written by `evidence.py`.

<!-- results:start -->
| Block | Devices | Area µm² (ceiling) | DRC | LVS | Extracted nominal (gating) | Safe (reset-default) | clean |
| --- | ---: | ---: | ---: | --- | --- | --- | --- |
| `diff_clk_rx` | 54 | 22,467 (180000) | 0 | unique | nom_diff_100m_500mv: pass, nom_se_1g_600mv: pass, data_0g5_500mv: pass, data_1g_500mv: pass, data_1g6_500mv: pass, data_1g6_300mv: pass, data_1g6_800mv: pass, data_pre128_0g5_300mv: pass | pass (max avg 0.621 µA) | pass |
| `clk_obs` | 383 | 73,118 (reserve) | 0 | unique | nom: pass | pass (max avg 0.0855 µA) | pass |
| `ring_osc` | 54 | 9,520 (reserve) | 0 | unique | nom: pass | pass (max avg 0.00646 µA) | pass |
| `aosc` | 34 | 12,892 (20000) | 0 | unique | nom: pass | pass (max avg 0.00194 µA) | pass |
| `clockmux` | 5 | 15,238 (80000) | 0 | unique | nom: pass, nom_mode_rf: pass, nom_mode_wired: pass | pass (max avg 0.201 µA) | pass |
| `vco_replica` | 31 | 21,056 (reserve) | 0 | unique | nom_vc1.5: pass, nom_vc2.1: pass, nom_vc3.3: pass | pass (max avg 0.0399 µA) | pass |
| `lo_ext` | 100 | 38,692 (reserve) | 0 | unique | nom_ext_sin_2vpp_pad: pass, nom_int: pass | pass (max avg 0.0664 µA) | pass |
| `pll_ring` | 408 | 166,446 (reserve) | 0 | unique | closed_480m: pass, closed_625m: pass, closed_810m: pass, closed_hf125m_n4: pass, closed_hf156m_n4: pass | fail (max avg 162 µA) | pass |
| `prescale` | 46 | 12,627 (reserve) | 0 | unique | nom_2g5_d16: pass, nom_240m_d2: pass | pass (max avg 0.0405 µA) | pass |
| `wordclk` | 53 | 24,969 (reserve) | 0 | unique | nom_480m_d5: pass, nom_480m_d10: pass, nom_480m_d20: pass, nom_810m_d5: pass, nom_810m_d10: pass, nom_810m_d20: pass | pass (max avg 0.0568 µA) | pass |
<!-- results:end -->

The `lo_ext` row describes a superseded cell (its evidence file predates the published layout; Open items).

Every published GDS in `generated/` (the 18 blocks of the table in "Blocks" except the QVCO) has Magic DRC 0
(`<block>-drc.txt`), LVS unique (`<block>-lvs.txt`) and a clean KLayout precheck, main 0 / antenna 0
(`<block>-kldrc.json`). The QVCO records are in `generated/lcvco/` (below).

| Block | Verified numbers | Evidence |
| --- | --- | --- |
| `pll_ring` | See the next section | `generated/pll_ring-evidence.json` |
| `vco_replica` | 258 MHz (VCTRL 0.9 V) to 1093 MHz (3.3 V), 2.35-9.28 mA. At VCTRL 3.3 V: ss 852-918, tt 1043-1117, ff 1257-1336 MHz. 12 of 48 corner cases do not oscillate (ss at 0.9 V; tt and ss at 0.8 V) | `generated/vco_replica-evidence.json` |
| `wordclk` | /5, /10, /20 at 480 and 810 MHz; 48 of 48 corner cases; 1.2-2.4 mA; CK to LD 1.15 ns | `generated/wordclk-evidence.json` |
| `clockmux` | WIRE: 810 MHz, stop (<= 11 mV), 1 GHz, stop, 400 MHz; 12 of 12 corners; 0.32 mA (RF mode) to 1.55 mA | `generated/clockmux-evidence.json` |
| `prescale` | 2.5 GHz /16, 1.5 GHz /16, 240 MHz /2 at tt; 2.0 mA at 2.5 GHz. No corner runs | `generated/prescale-evidence.json` |
| `diff_clk_rx` | Clock, differential: 10 MHz to 1 GHz at 200 mVpp to 1.2 Vpp; single-ended 1 GHz at 600 mVpp; 2.5 and 3.3 GHz fail. Data (PRBS): 0 errors at 0.5-2 Gb/s, 300-800 mVpp, also when starting from electrical idle; a source parked at a data level before the first bit fails. 12 of 12 corners; 2.6-5.1 mA enabled | `generated/diff_clk_rx-evidence.json` |
| `clk_obs` | 500 MHz in, /8 into 10 pF: 12 of 12 corners, 4.6-5.1 mA; 1 GHz input fails | `generated/clk_obs-evidence.json` |
| `ring_osc` | 211 MHz at tt; 165-255 MHz over corners; 0.42 mA | `generated/ring_osc-evidence.json` |
| `aosc` | 47.7 MHz, 0.38 mA; 12 of 12 corners inside 40-60 MHz (ss 42.9-43.4, tt 47.6-48.1, ff 53.8-54.3 MHz); off current < 1 nA | `generated/aosc-evidence.json` |

Fast cells (`generated/fast/speed.json`, tt): `ct_ring8` 1.12 GHz extracted (1.78 GHz schematic); `ct_tspc2`
divides at 3.5 GHz.

## `pt_pll_ring`

The single ring-PLL design. `pll_cdr` is the full cell (r9v); `pll_tx` is `pt_pll_ring_core` (r9d, same loop
without fast tune and N5 / N10). Both run on a `pt_pll_vreg2` output (`../pll_vreg/README.md`).

* Loop: PFD, charge pump with current steering, passive filter, `ct_ring9` 4-stage pseudo-differential ring
  (`PH0..PH7` at 45 degree steps at the VCO rate), TSPC feedback divider.
* Modulus: 16 (default), 8 (`N8`), 4 (`N4`: REF/2 into the PFD with /8 feedback), 10 (`N10`), 5 (`N5`: REF/2
  with /10 feedback). `N5` / `N10` have priority over `N4` / `N8`.
* `BAND`: 1 = high band (reset value at chip top), 0 = half tail current.
* `HOLD`: holds the PFD in reset so the filter floats; a pump on `ATB_VCTRL` still acts. `pt_cdr` drives
  `HOLD` and the shared `VCTRL` node of `pll_cdr`; `pll_tx.HOLD` is tied to VSS.
* `KP0..KP2`, `FU0..FU3`, `FD0..FD3`: proportional (fast-tune) path of the CDR, a header-side current-steered
  array (`pt_pll_ring_ft`); `FU` / `FD` are the capture votes, `KP` the gain (0 = off).
* `REFO`, `FBCK`: reference and feedback for the lock counter. `LOCK`: informative only.

Extracted, closed loop, tt/27 C/3.3 V on an ideal supply (`generated/pll_ring-evidence.json`, hashes match the
published GDS and extraction):

| Case | VCO | Worst port phase error | Current | Analog `LOCK` |
| --- | --- | --- | --- | --- |
| N = 16, 30 MHz reference | 480.02 MHz | 5.4 deg | 5.3 mA | correct |
| N = 16, 39.0625 MHz | 624.99 MHz | 5.9 deg | 6.9 mA | correct |
| N = 16, 50.625 MHz | 810.00 MHz | 7.6 deg | 8.5 mA | wrong |
| N = 4, 125 MHz (host_follow) | 500.2 MHz | 5.0 deg | 5.7 mA | wrong |
| N = 4, 156.25 MHz (host_follow) | 624.9 MHz | 5.7 deg | 6.9 mA | wrong |

VCTRL ripple is 136-142 mV peak to peak in these runs. **Safe test: fail.** With every control at 0 and the
inputs toggling the cell draws 87-162 uA average (114 uA at tt), against the 1 uA criterion.

Frequency range over corners and regulated supply, vote gain and CDR closed-loop behaviour are wired RX results:
`../wired_rx/README.md`. `pt_pll_ring_core` has DRC / LVS / precheck records only.

## RF LO

Two LO sources drive the mixer gates through `pt_lo_ext`; the mode table is in `LO-INTEGRATION.md` section 4.1.

| Source | State |
| --- | --- |
| External I/Q LO on the REF_IN / AUX_CLK pad pairs through the CML driver (`lo_mode` 3) | The RF baseline for a die whose synthesizer does not work. Usable source 1.0-4.5 Vpp per leg at tt / ss / ff on the level criterion (`scratch/lo/r4_lo11/results.json`); that criterion does not guarantee mixer gain (below) |
| External, passive path (`lo_mode` 1) | Backup; fails ss at 4.5 Vpp |
| On-chip synthesizer: `pt_lc_qvco5`, `pt_lo_mmd`, `pt_lo_pfdcp`, `pt_lo_lf` (`lo_mode` 2) | Every cell is published. Integer-N under register control (f_LO = 2 N f_ref, band search by software); no fractional-N modulator and no band-search state machine exist in RTL. Not qualified as a loop (Open items) |

There is no polyphase network: the external I/Q LO is the only fallback.

**Drive at the mixers** (extracted `pt_lo_ext`, internal mode, into extracted `rxmix_i` / `rxmix_q`, IF 5 MHz;
conversion gain relative to an ideal 0 / VDD square LO; `scratch/lo-ap4/mw20/`):

| Tank amplitude per side | tt/27/3.3 | ff/22/3.35 | ss/32/3.15 | ss, `ATB_VB` forced to 2.45 V |
| --- | ---: | ---: | ---: | ---: |
| 0.58 V | -3.3 dB | -1.9 dB | -9.8 dB | -3.4 dB |
| 0.40 V | - | - | -11.6 dB | - |

LO at the mixer gates: 0.72 / 0.81 / 0.62 Vpp per side (tt / ff / ss), 11.1 mA at tt. Forcing `ATB_VB` per die
is the available mitigation. The external modes have not been run with the mixers.

**QVCO** (`generated/lcvco/`): Magic DRC 0, KLayout precheck main 0 / antenna 0 (`lcvco5-kldrc.json`); top-level
LVS on the GDS read back from disk, unique, with the spirals as documented shorts (`pt_lc_qvco5-lvs.txt`,
`pt_lc_qvco5_core-lvs-readback.txt`). Fill keep-out markers cover both spirals plus 25 um, the feeds, the tank
core and the tank channel; stock fill leaves no dummy within 25 um of spiral metal
(`pt_lc_qvco5-fillcheck.json`). 12 mA tail per core with an RC-filtered tail gate: wait 1.5 ms from `EN` to use.

With its real loads (extracted `pt_lo_ext`, `pt_lo_mmd`, `pt_lo_mmd_qdum`, both `pt_lo_obs`, top wiring, 0-40 fF
of route; `scratch/lo-ap4/q7/env.log`):

| Case | Result | Limit |
| --- | --- | --- |
| tt, band 8, VTUNE 1.65 V | 2.255 GHz, Q-I -98.7 deg, 2.11 / 2.31 V differential peak (I / Q), 24.7 mA | Q-I 90 +- 10 deg |
| Top of range: ss/32/3.15, L +15 %, Q 4, C x1.15, band 0, VTUNE 3.0 V | 2.488 GHz, **fail** | >= 2.558 GHz |
| Bottom of range: ff/22/3.35, L -15 %, C x0.9, band 15, VTUNE 0.3 V | 2.275 GHz, pass | <= 2.330 GHz |
| Start-up, weakest tanks, band 15, VTUNE 0.3 V | 0.62-1.13 V differential peak, pass | >= 0.5 V |

The quadrature error and the I/Q amplitude imbalance come from unequal wiring on the I and Q tanks (the
published `pt_lo_mmd` puts 201 / 126 fF on the I tank, the dummy 22 / 31 fF on the Q tank).

**Loop** (`lcvco/loop_design.json["r5"]`, behavioural with extracted block data): filter R 10.38 k, C1 5.43 pF,
C2 486 pF, R3 10 k, C3 8.84 pF; design point fc 300 kHz at Kvco 90 MHz/V. Worst synthesizer jitter 0.80 ps rms
against 0.923 ps (RF-LO-JIT 1.05 ps less a 0.5 ps LO-path share), worst phase margin 41 deg, over Kvco
80-200 MHz/V, N 44-56 and the component tolerances. The result holds only for Kvco <= 200 MHz/V with VTUNE
preset at 2.1 V (risk LO-13).

**Lock time** (`scratch/lo-ap4/lock/lock_rc.json`): about 6-7 x R x C2. 40.5 us nominal, 21-60 us over R +-25 % and
C2 +-15 %, up to 65 us at Kvco 200 MHz/V, against a 50 us limit: the slow filter corner misses.

**Supply limit of the QVCO rail:** each supply-borne tone <= -60 dBc and <= 0.2 ps rms in total; noise
<= 7 nV/rtHz from 100 kHz to 1 MHz (pushing -60 MHz/V, risk LO-11).

**Placement:** the QVCO runs at the RF carrier, so its position is constrained; the rules are in
`LO-INTEGRATION.md` section 7.

## Open items

Risks: `spec/risk-register.md` LO-02, LO-03, LO-10, LO-11, LO-12, LO-13, SP-02, PKG-04, PKG-05, BW-02, XT-01,
DBG-02, MT-03. LO-01 is listed there as closed but applies again (the QVCO runs at the carrier).

1. Evidence currency. `run_timing.py`, `timing_flow.py` and `layout_engine.py` changed after every evidence
   file. `lo_ext-evidence.json`, `lo_ext-pad-evidence.json` and `lcvco-evidence.json` describe superseded cells
   (netlist and GDS hashes differ) and are not quoted here. The GDS hash differs from the evidence record for
   `aosc`, `clockmux`, `prescale`, `vco_replica`, `wordclk` (GDS re-exported; `.mag` and extraction unchanged)
   and `ring_osc` (layout rebuilt after the evidence). `generated/polyphase.ext.spice` is a leftover of the
   deleted block.
2. No evidence JSON exists for `pll_ring_core`, `clk_obs16`, `obs_pre4`, `lo_mmd`, `lo_mmd_qdum`, `lo_pfdcp`,
   `lo_lf`, `lo_obs` or the QVCO; their bench results are in `scratch/` only.
3. `pll_ring`: safe test fails (87-162 uA at reset); no corner, cold-start or HOLD runs on r9v; phase error
   5-7.6 deg; analog `LOCK` wrong. Jitter, reference spurs (SP-02) and ring-to-ring coupling are not covered.
4. `pt_lo_ext` under-drives the RX mixers (-3.3 dB tt, -9.8 dB ss). A revised cell is staged in
   `scratch/lo-ap4/loext3/`, not published. The internal node VLI floats when `CMLSEL` = 0. External modes are
   not benched with the mixers, nor on the `pad_refpad` AUX_CLK pad and the fixed COB bond map.
5. QVCO with real loads: top of the range fails and Q-I is 9 deg off with the published `pt_lo_mmd` pair.
   Repacked `pt_lo_mmd`, `pt_lo_mmd_qdum`, `pt_lo_obs`, `pt_clk_obs16` and `pt_lo_ext` (row plan `ap4`) are
   staged in `scratch/lo-ap4/`, not published; the staged `pt_lo_mmd` awaits its bench and review.
6. No QVCO regulator is published. `lo_vreg.spice` (`pt_lo_vreg`) is in-flight work: staged at 0.44 mm2, not
   reviewed, and the tank-connected cells are verified only at a 1.7 V tank common mode. `pt_chip.conn`
   instances it as a build demand.
7. Loop: lock time at the slow filter corner; `pt_lo_pfdcp` presets VTUNE to VDD/2, not to the 2.1 V the jitter
   and lock analyses assume; no transistor-level closed-loop lock result; Kvco bound not extracted (LO-13).
8. `pt_lo_obs` does not divide at ss / 3.15 V (4 of 24 corner cases).
9. Electromigration has not been checked on the engine-routed CML current paths of the LO cells.
10. AUX_CLK receiver as the forwarded-wire-clock path (25-810 MHz, 3.1 mm route): bench in progress in
    `scratch/lo-ap4/auxrx/`; unbuffered, the published `pt_diff_clk_rx` does not drive that route at 810 MHz.
11. `HOST_CLK` can only come from a locked ring; a direct H2D / REF host clock is proposed (interface row CM-1),
    not built.
12. Uncommitted edits to `layout_engine.py` and `lo_rows.py` belong to items 4 and 5.
13. Not covered anywhere in this family: mismatch, sf / fs corners, results at a 3.50 V trimmed supply,
    substrate coupling, resistance-aware extraction (the QVCO tank excepted).
