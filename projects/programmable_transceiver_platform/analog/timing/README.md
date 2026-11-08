# Timing and clocking family (`analog/timing/`)

Transistor-level timing blocks built to the
[block deliverable convention](../../spec/block-deliverables.md): one `.spice`
per block (gf180mcuD `nfet_03v3`, `pfet_03v3`, `ppolyf_u_1k`), a reproducible
Magic layout, Magic + KLayout DRC, Netgen LVS, extracted (parasitic-C) ngspice
simulation, 12-point corners and a `generated/<block>-evidence.json` four-test
record.  The JSON is authoritative; numbers below are copied from it.

## Reproduce

```
analog/timing/run_timing.sh                  # all blocks
analog/timing/run_timing.sh pll_ring,clockmux  # a subset
```

`run_timing.sh` builds the compact fast cells (`fastcells.py`), then runs
`run_timing.py` (layout, DRC, LVS, nominal/safe/corner simulation) and
`evidence.py` (evidence JSON and the results table below).  Layout/DRC/LVS run
in `svalbard/librelane-gf180-canary:2026.08` (Magic 8.3.623, Netgen 1.5.316);
simulation and GDS export run in `hpretl/iic-osic-tools@sha256:89641950…`
(ngspice 43, Magic 8.3.678).  Every container runs `--network none`.  Raw
decks and logs go to `<repo>/scratch/timing/`.

| File | Role |
| --- | --- |
| `<block>.spice` | Block netlist, top subcircuit `pt_<block>`; single source for layout, LVS and simulation |
| `timing_cells.spice` | Shared cells (inverters, gates, C2MOS latches, /2, /5, selectors) |
| `pll.spice` | Loop-piece library for `pll_ring` (PFD `pt_pfd`); not a block |
| `fastcells.py`, `compact.py` | Compact hand-placed fast cells (`generated/fast/ct_*`), with their own netlists, pins and speed benches (`generated/fast/speed.json`) |
| `layout_engine.py`, `netlist.py` | Row/channel layout generator for blocks (places fast cells as macros); SPICE reader |
| `timing_flow.py` | Docker wrappers for Magic, Netgen, KLayout, ngspice |
| `run_timing.py`, `evidence.py` | Testbenches and per-block plan; evidence assembly |
| `lcvco/` | LC VCO evaluation for the autonomous RF LO (schematic level; see Open items) |

Layout method: blocks use one Magic PCell per device with its own guard ring,
private Metal2/3 escapes, private Metal4 tracks and Metal5 trunks, so routing
is short-free by construction (area- and capacitance-inefficient).  Fast cells
(`ct_*`) are painted directly: shared-diffusion N/P strips, one Metal2 track
per net; each is DRC/KLayout clean and LVS unique on its own.  Build, DRC and
extract+GDS run in separate Magic sessions to work around Magic 8.3.623
`ppolyf_u_1k` extraction quirks.

## Conventions

`VDD` is the switched PLL island rail (3.3 V), except `aosc` and `clk_obs`
(always-on core rail).  Every enable/select is active-high and **0 is the
reset/safe state** (block off, clock stopped).  One-hot selects carry at most
one 1; all-zero means stopped.  Clock switching is glitch-safe only through
the stopped state (write all-zero, wait >= 1 us, write the new one-hot).

## Blocks

| Block | Ports | Function |
| --- | --- | --- |
| `pt_pll_ring` | `REF EN N4 N8 HOLD IBIAS PH0..PH7 LOCK FBCK REFO ATB_VCTRL VDD VSS` | The single PLL design (line PLL, host_follow PLL, CDR loop).  PFD → 10/20 µA charge pump → R 20 kΩ / C1 8.8 pF / C2 0.9 pF → `ct_ring8` 4-stage pseudo-differential ring (PH0..PH7 at 45°, VCO rate) with mirrored PMOS header and NMOS tail on VCTRL → TSPC feedback.  N = 16 (`N4=N8=0`), 8 (`N8`), 4 (`N4`; built as REF/2 into the PFD with /8 feedback).  `REFO`/`FBCK` feed the standard-cell lock counter; analog `LOCK` is informative only.  `HOLD` (r6): registered on the falling PFD reference edge, keeps the PFD in reset so the filter floats and the VCO runs on the held VCTRL; an external pump on `ATB_VCTRL` (wired_rx CDR) still acts.  Netlist version tag on line 2 of `pll_ring.spice`. |
| `pt_vco_replica` | `EN VCTRL OUT ATB_VTAIL VDD VSS` | Same ring cells as `pll_ring`, VCTRL forced from the ATB (clamped while `EN=0`), `OUT` = VCO/16 to CLK_OBS.  Coverage vehicle. |
| `pt_prescale` | `CK_IN EN D2 D4 D8 D16 CK_OUT` | TSPC front end for `rtl/pt_clocktree_slow.sv`; one-hot ratio.  Converter/host clocks after host_follow; detector clock on the ring clock. |
| `pt_wordclk` | `CK EN D10 D20 WORD_CLK LDE LD LDB VDD VSS` | Shared TX/RX word divider: /5 (quarter rate), /10 (`D10`), /20 (`D20`) from the ring clock.  `LDE` high one CK period before the word boundary; consumers re-register `LDE` locally (CK→LD ≈ 1.15 ns at tt is close to a period at 810 MHz). |
| `pt_clockmux` | sources `PLLW REF AUX WCK H2D WSI CONV_INT HOST_INT HF`; one-hot `PS_{REF,AUX,H2D}`, `WS_{PLL,REF,AUX,WCK}`, `SS_{INT,REF,WCK}`, `CS_{INT,REF,AUX,HF}`, `HS_{INT,HF}`; outputs `PREF WIRE WSMP CONV_CLK HOST_CLK` | Five `ct_mux4` domains, single-ended CMOS, ≤ 1 GHz.  No RF LO domain (the RF LO is `lo_ext`). `HF` is the host_follow clock (H2D → `pll_ring` N=4 → `prescale`). |
| `pt_lo_ext` | `EXT_IP EXT_IN EXT_QP EXT_QN LOI_IP LOI_IN LOI_QP LOI_QN EXT INT LO_IP LO_IN LO_QP LO_QN ATB_VB VDD VSS` | RF LO into the mixer gates.  External mode (`EXT`, RF qualification baseline): board I on REF_IN, Q on AUX_CLK, AC-coupled; per leg NMOS switch → transmission gate → series MOS cap → mixer node biased to VB ≈ 2.55 V.  No active device in the path; the board must not DC-drive the pads while `EXT=1`.  Internal mode (`INT`): `ct_lodrv` drivers from `LOI_*`. |
| `pt_polyphase` | `INP INN EN LOI_IP LOI_QP LOI_IN LOI_QN ATB_N0 VDD VSS` | Two-stage RC polyphase (300 Ω, anti-series MOS caps) + four `ct_lim` limiters into `lo_ext` internal inputs.  Fails extracted (below). |
| `pt_diff_clk_rx` | `INP INN EN SE OUTP OUTN PRESENT ATB_DET VDD VSS` | One receiver design for refinput (REF_IN), aux_clk_rx (AUX_CLK), wired WCLK_IN and WTX_EXT.  Self-biased `ct_rxin` legs (40 kΩ feedback), `ct_rxout` output stage; `SE=1` for single-ended sources; `PRESENT` = both phases toggling.  Use `OUTN` for data (lower edge spread). |
| `pt_clk_obs` | `IN0..IN7 S0 S1 S2 N0 N1 N2 EN OUT VDD VSS` | 8:1 input mux, /2^N (N = 0..7), tristate pad driver (P 80 µm / N 40 µm).  Used for CLK_OBS and WCLK_OBS. |
| `pt_ring_osc` | `EN OUT VDD VSS` | NAND-enabled 21-stage ring, process monitor. |
| `pt_aosc` | `EN CLK ATB_X VDD VSS` | Schmitt RC relaxation oscillator, no bias input (core rail). |

### Integration interface

* ATB taps: `pll_ring.ATB_VCTRL`, `pll_ring.IBIAS` (override),
  `vco_replica.VCTRL` (force), `vco_replica.ATB_VTAIL`, `diff_clk_rx.ATB_DET`,
  `aosc.ATB_X`, `lo_ext.ATB_VB`, `polyphase.ATB_N0`.
* Status: `refinput.PRESENT` → `ref_present`; PLL lock from the standard-cell
  REFO-vs-FBCK counter.
* Bias: each `pll_ring.IBIAS` sinks 10 µA (one bias output per instance);
  nothing else needs bias.
* Instances: line `pll_ring`, host_follow `pll_ring` (N=4 from `H2D_CLK`),
  `prescale`, `clockmux`, `wordclk` (shared TX/RX), `lo_ext`, refinput and
  aux `diff_clk_rx`, two `clk_obs`, `ring_osc`, `vco_replica`, `aosc`.
* `pt_wordclk` replaces the TX `/5`; `WORD_CLK` is the TX launch clock and
  the RX word clock.  RX capture stays in wired_rx.

### Register-map glue (combinational, all outputs reset to 0)

| Field | Analog ports |
| --- | --- |
| `debug.clk_select.wire_line` {0, 1 pll, 2 ref, 3 aux, 4 wclk} | `WS_PLL/WS_REF/WS_AUX/WS_WCK = (c==1/2/3/4)` |
| `debug.clk_select.wire_sample` {0, 1 int, 2 ref, 4 wclk} | `SS_INT/SS_REF/SS_WCK = (c==1/2/4)` |
| `debug.clk_select.conv_sample` {0, 1 int, 2 ref, 3 aux, 5 host_follow} | `CS_INT/CS_REF/CS_AUX/CS_HF = (c==1/2/3/5)` |
| `debug.clk_select.host_clk` {0, 1 int, 5 host_follow} | `HS_INT/HS_HF = (c==1/5)` |
| ring-PLL reference (field needed; proposal {0 stopped, 1 ref, 2 aux, 3 h2d}) | `PS_REF/PS_AUX/PS_H2D` |
| ring-PLL modulus per instance (field needed; proposal {16, 8, 4}) | `N8 = (n==8)`, `N4 = (n==4)` |
| `cfg_bits_per_cycle` {4, 2, 1} | `wordclk.D10 = (b==2)`, `D20 = (b==1)` |
| RF LO mode (field needed; proposal {off, ext, internal}) | `lo_ext.EXT` / `lo_ext.INT` |
| `debug.clk_obs.source` (14) + `divider_log2` | two `clk_obs` instances sharing the pad (A: sources 1..7, B: 8..14); `N = min(divider_log2, 7)` |
| `debug.wclk_obs.source` (5) + `divider_log2` (0..7) | `EN = (source != off)`, `S = source-1`, `N = divider_log2` |
| `debug.replica.ringosc_enable`, `vco_enable` | `ring_osc.EN`, `vco_replica.EN` |
| refinput / aux enable and SE (fields needed) | `diff_clk_rx.EN`, `SE` per instance |

## Results

Extracted (Magic C-only parasitics), tt 27 °C 3.3 V unless noted.  Corners:
tt/ss/ff × 22/32 °C × 3.15/3.35 V.  Safe = reset-default controls with clock
and pad inputs toggling at tt/27 °C/3.3 V, ff/85 °C/3.63 V and ss/0 °C/3.63 V.
The table between the markers is regenerated by `evidence.py`.

<!-- results:start -->
| Block | Devices | Area µm² (ceiling) | DRC | LVS | Extracted nominal (gating) | Safe (reset-default) | clean |
| --- | ---: | ---: | ---: | --- | --- | --- | --- |
| `diff_clk_rx` | 33 | 14,671 (180000) | 0 | unique | nom_diff_100m_500mv: pass, nom_se_1g_600mv: pass, data_0g5_500mv: pass, data_1g_500mv: pass, data_1g6_500mv: pass, data_1g6_300mv: pass, data_1g6_800mv: pass, data_pre128_0g5_300mv: pass | pass (max avg 0.0197 µA) | pass |
| `clk_obs` | 383 | 73,118 (reserve) | 0 | unique | nom: pass | pass (max avg 0.0853 µA) | pass |
| `ring_osc` | 54 | 9,520 (reserve) | 0 | unique | nom: pass | pass (max avg 0.00646 µA) | pass |
| `aosc` | 17 | 5,097 (20000) | 0 | unique | nom: pass | pass (max avg 0.00111 µA) | pass |
| `clockmux` | 5 | 15,238 (80000) | 0 | unique | nom: pass, nom_mode_rf: pass, nom_mode_wired: pass | pass (max avg 0.201 µA) | pass |
| `vco_replica` | 31 | 21,056 (reserve) | 0 | unique | nom_vc1.5: pass, nom_vc2.1: pass, nom_vc3.3: pass | pass (max avg 0.0399 µA) | pass |
| `lo_ext` | 100 | 39,169 (reserve) | 0 | unique | nom_ext_sin_2vpp_pad: pass, nom_int: pass | pass (max avg 0.0664 µA) | pass |
| `polyphase` | 46 | 39,329 (reserve) | 0 | unique | nom_2g45_1vpp: FAIL | pass (max avg 0.0549 µA) | fail |
| `pll_ring` | 211 | 68,562 (reserve) | 0 | unique | closed_480m: pass, closed_625m: pass, closed_810m: pass, closed_hf125m_n4: pass, closed_hf156m_n4: pass | pass (max avg 10.1 µA) | pass |
| `prescale` | 46 | 12,627 (reserve) | 0 | unique | nom_2g5_d16: pass, nom_240m_d2: pass | pass (max avg 0.0405 µA) | pass |
| `wordclk` | 53 | 24,969 (reserve) | 0 | unique | nom_480m_d5: pass, nom_480m_d10: pass, nom_480m_d20: pass, nom_810m_d5: pass, nom_810m_d10: pass, nom_810m_d20: pass | pass (max avg 0.0568 µA) | pass |
<!-- results:end -->

Four-test states: every block is **safe pass** (`pll_ring` 10.0–10.1 µA is
the 10 µA IBIAS test source); **clean pass** for all but `polyphase`
(fail); **observable** pass for `pll_ring` and `diff_clk_rx`, open elsewhere
(register map); **fallback** open (waived for `aosc`).  All blocks: Magic DRC 0,
KLayout GF180 DRC 0, LVS unique.

| Block | Key extracted numbers |
| --- | --- |
| `pll_ring` (r5 netlist) | Locks at 480.003 / 625.002 / 810.004 MHz (N=16) and 499.93 / 624.95 MHz (host_follow, 125/156.25 MHz × 4); worst port phase error 4.6 / 4.9 / 5.5° (810 MHz misses ±5° by 0.5°), 4.5° host_follow; 4.8–7.9 mA.  Open-loop corners at VCTRL 3.3 V: ss 850–916, tt 1041–1115, ff 1255–1334 MHz.  Phase margin estimate 23° (480 MHz) to 40° (62.5–78 MHz PFD rate). |
| `vco_replica` | 258 MHz (VCTRL 0.9 V) to 1093 MHz (3.3 V), 2.35–9.28 mA, K_VCO ≈ 1.2 GHz/V in band.  Every corner covers 480–810 MHz within VCTRL 0.8–3.3 V (ss ≥ 852 MHz at 3.3 V; ss/tt do not oscillate at 0.8 V, which is the 8 failing corner cases, informative). |
| `wordclk` | /5, /10, /20 at 480 and 810 MHz pass; 48/48 corners (810/625 MHz × /5, /20); 1.2–2.3 mA. |
| `clockmux` | WIRE 810 MHz PLL → stop (≤ 7 mV) → 1 GHz REF → stop → 400 MHz WCK; RF passive-LO mode 0.32 mA, wired mode 1.35 mA; 12/12 corners. |
| `lo_ext` | External 2.45 GHz, ~2 Vpp at the pad: RX switch Vgs on 1.19 V / off 0.30 V, Q−I 87.3°; 12/12 corners (on 0.96–1.31 V, off 0.14–0.39 V).  ~1 Vpp at the pad and square-wave sources fail (off level, pump-up).  Internal mode: 0.13–2.84 V, Q−I 86.3°, 16.0 mA for four lines. |
| `prescale` | 2.5 GHz /16 = 156.25 MHz, 1.5 GHz /16, 240 MHz /2; 2.0 mA at 2.5 GHz. |
| `diff_clk_rx` | Clock: 100 MHz–1 GHz pass (500 mVpp diff, 600 mVpp SE); 200 mVpp, 2.5 and 3.3 GHz fail.  Data (PRBS7, 10 pF AC coupling): 0 errors 0.5–1.6 Gb/s at 300–800 mVpp in steady state or after a 128-bit preamble; 2 Gb/s fails; start-up from the first bit fails (baseline wander, τ ≈ 40 ns). |
| `clk_obs` | 500 MHz in, /8 → 62.5 MHz into 10 pF; 12/12 corners; 1 GHz input fails. |
| `ring_osc` | 211 MHz; corners 165–255 MHz. |
| `aosc` | 44.9 MHz, 0.16 mA; ss 35.4–37.1 MHz (below the 40 MHz allocation), ff ≈ 55 MHz. |
| `polyphase` | Fails: network node swings ~0.2 Vpp extracted and the limiters do not toggle at 2.4–2.5 GHz. |

Fast cells (`generated/fast/speed.json`, tt): `ct_ring8` 1.12 GHz extracted
(1.78 GHz schematic), `ct_tspc2` divides at 3.5 GHz (fails 4 GHz), `ct_lodrv`
2.45 GHz rail-to-rail, `ct_rxin` full swing at 2.45 GHz / 600 mVpp.

**Evidence currency:** `run_timing.py` changed after every evidence file
(testbench additions and removal of retired blocks); rerun before relying on
hashes.  `pll_ring.spice` (r6, `HOLD` port), `pll.spice` (retired
subcircuits removed, `pt_pfd` unchanged) and the `pll_ring` layout changed
after `pll_ring-evidence.json`, which records the r5 netlist (no `HOLD`).  The
r6 layout is DRC 0 / KLayout 0 / LVS unique, 222 devices, 80,372 µm²
(`scratch/timing/pll_ring/results.json`), but no r6 simulation has run
(including the new `cold_*` and `hold*` cases); rerun
`run_timing.sh pll_ring`.

## Known limitations and open items

1. **`pll_ring` r6 is unsimulated** (see Evidence currency).  Closed-loop
   lock is nominal-only with VCTRL pre-charged; cold-start acquisition,
   jitter/phase noise and reference spurs are not covered.  High K_VCO makes
   reference-ripple FM the main jitter risk.  Port phase residual (PH3/PH7
   ~4° early, PH4 ~3° late) is port-routing skew in the generic layout.
2. **`polyphase` fails extracted.**  The autonomous-LO plan (P3-4) uses the
   passive network only, without limiters; the block in this directory
   still carries the limiters.
3. **LC VCO (`lcvco/`) evaluation is incomplete:** schematic VCO with an
   analytical 2.86 nH spiral model (Q_eff ≈ 7.4, 400 µm octagon, not laid
   out).  Recorded run (`lcvco/results.json`, which predates the last
   `lcvco.spice` edit): oscillates at 2.17–2.18 GHz for VTUNE 0–0.8 V
   (below 2.45 GHz), no oscillation at 1.65–3.3 V, buffer outputs not
   switching.  Not a deliverable.
4. `lo_ext` internal mode draws 16.0 mA; external mode needs ≥ ~2 Vpp sine
   at the pad.
5. `clk_obs` has 8 inputs and /2^0..7, smaller than `debug.clk_obs`
   (two instances needed; `divider_log2` 8..15 unsupported).
6. `vco_replica` has no `vco_coarse` DAC or divider select (VCTRL from ATB,
   fixed /16).
7. `aosc` is below 40 MHz at ss.
8. `diff_clk_rx` data mode needs a ≥ 128-bit DC-balanced preamble after
   idle; no hysteresis.
9. Not covered: mismatch/Monte Carlo, IR drop and RC clock skew (C-only
   extraction), substrate coupling, ESD (pads family), integration with
   `atb_tap` and the island switch.
