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
| `lcvco/` | Autonomous RF LO: quadrature LC VCO r2 and spiral model (schematic level; section below) |

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
| `pt_lo_ext` | `EXT_IP EXT_IN EXT_QP EXT_QN LOI_IP LOI_IN LOI_QP LOI_QN EXT INT LO_IP LO_IN LO_QP LO_QN ATB_VB VDD VSS` | RF LO into the mixer gates.  External mode (`EXT`, RF qualification baseline): board I on REF_IN, Q on AUX_CLK, AC-coupled; per leg NMOS switch → transmission gate → series MOS cap → mixer node biased to VB ≈ 0.70·VDD (2.20–2.35 V; was 0.773·VDD until 2026-11-10).  No active device in the path; the board must not DC-drive the pads while `EXT=1`.  Internal mode (`INT`): `ct_lodrv` drivers from `LOI_*`. |
| `pt_polyphase` | `INP INN EN LOI_IP LOI_QP LOI_IN LOI_QN ATB_N0 VDD VSS` | Two-stage RC polyphase (300 Ω, anti-series MOS caps) + four `ct_lim` limiters into `lo_ext` internal inputs.  Fails extracted (below). |
| `pt_diff_clk_rx` | `INP INN EN SE OUTP OUTN PRESENT ATB_DET VDD VSS` | One receiver design for refinput (REF_IN), aux_clk_rx (AUX_CLK), wired WCLK_IN and WTX_EXT.  Self-biased `ct_rxin` legs (40 kΩ feedback), `ct_rxout` output stage; `SE=1` for single-ended sources; `PRESENT` = both phases toggling.  Use `OUTN` for data (lower edge spread). |
| `pt_clk_obs` | `IN0..IN7 S0 S1 S2 N0 N1 N2 EN OUT VDD VSS` | 8:1 input mux, /2^N (N = 0..7), tristate pad driver (P 80 µm / N 40 µm).  Used for CLK_OBS and WCLK_OBS. |
| `pt_ring_osc` | `EN OUT VDD VSS` | NAND-enabled 21-stage ring, process monitor. |
| `pt_aosc` | `EN CLK ATB_X VDD VSS` | r3: two-capacitor RC relaxation oscillator with an SR latch (each half period = R·C·ln2 to an inverter trip point at ~VDD/2, latch delay), no bias input (core rail). r1 was a Schmitt RC oscillator. |

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
| `diff_clk_rx` | 54 | 22,467 (180000) | 0 | unique | nom_diff_100m_500mv: pass, nom_se_1g_600mv: pass, data_0g5_500mv: pass, data_1g_500mv: pass, data_1g6_500mv: pass, data_1g6_300mv: pass, data_1g6_800mv: pass, data_pre128_0g5_300mv: pass | pass (max avg 0.621 µA) | pass |
| `clk_obs` | 383 | 73,118 (reserve) | 0 | unique | nom: pass | pass (max avg 0.0855 µA) | pass |
| `ring_osc` | 54 | 9,520 (reserve) | 0 | unique | nom: pass | pass (max avg 0.00646 µA) | pass |
| `aosc` | 34 | 12,892 (20000) | 0 | unique | nom: pass | pass (max avg 0.00194 µA) | pass |
| `clockmux` | 5 | 15,238 (80000) | 0 | unique | nom: pass, nom_mode_rf: pass, nom_mode_wired: pass | pass (max avg 0.201 µA) | pass |
| `vco_replica` | 31 | 21,056 (reserve) | 0 | unique | nom_vc1.5: pass, nom_vc2.1: pass, nom_vc3.3: pass | pass (max avg 0.0399 µA) | pass |
| `lo_ext` | 100 | 38,692 (reserve) | 0 | unique | nom_ext_sin_2vpp_pad: pass, nom_int: pass | pass (max avg 0.0664 µA) | pass |
| `polyphase` | 46 | 39,329 (reserve) | 0 | unique | nom_2g45_1vpp: FAIL | pass (max avg 0.0549 µA) | fail |
| `pll_ring` | 236 | 75,772 (reserve) | 0 | unique | closed_480m: pass, closed_625m: pass, closed_810m: pass, closed_hf125m_n4: pass, closed_hf156m_n4: pass | pass (max avg 10.1 µA) | pass |
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
| `pll_ring` (r6a netlist) | Locks at 479.998 / 624.996 / 809.995 MHz (N=16) and 499.95 / 624.96 MHz (host_follow); worst port phase error 9.0 / 10.7 / 10.8°, 9.4–10.4° host_follow (r5 was 4.6–5.5°); 5.0–7.9 mA.  HOLD: +1545 ppm step, 110 ppm/10 µs drift (fail, non-gating).  Open-loop corners at VCTRL 3.3 V: ss 850–916, tt 1041–1115, ff 1255–1334 MHz.  Phase margin estimate 23° (480 MHz) to 40° (62.5–78 MHz PFD rate). |
| `vco_replica` | 258 MHz (VCTRL 0.9 V) to 1093 MHz (3.3 V), 2.35–9.28 mA, K_VCO ≈ 1.2 GHz/V in band.  Every corner covers 480–810 MHz within VCTRL 0.8–3.3 V (ss ≥ 852 MHz at 3.3 V; ss/tt do not oscillate at 0.8 V, which is the 8 failing corner cases, informative). |
| `wordclk` | /5, /10, /20 at 480 and 810 MHz pass; 48/48 corners (810/625 MHz × /5, /20); 1.2–2.3 mA. |
| `clockmux` | WIRE 810 MHz PLL → stop (≤ 7 mV) → 1 GHz REF → stop → 400 MHz WCK; RF passive-LO mode 0.32 mA, wired mode 1.35 mA; 12/12 corners. |
| `lo_ext` | Block bench (ideal 1 pF pad, 100 pF coupling), 4 Vpp open-circuit sine, steady-state levels (see the external-LO section): 12/12 corners pass, RX switch Vgs on 0.94–1.16 V, off 0.09–0.28 V, Q−I 86.0–87.6°.  2 and 1 Vpp and the square wave fail.  Internal mode: 0.13–2.84 V, Q−I 86.3°, 16.0 mA for four lines.  The real-pad + package qualification is `lo_ext_pad.py` (section below). |
| `prescale` | 2.5 GHz /16 = 156.25 MHz, 1.5 GHz /16, 240 MHz /2; 2.0 mA at 2.5 GHz. |
| `diff_clk_rx` | Clock: 100 MHz–1 GHz pass (500 mVpp diff, 600 mVpp SE); 200 mVpp, 2.5 and 3.3 GHz fail.  Data (PRBS7, 10 pF AC coupling): 0 errors 0.5–1.6 Gb/s at 300–800 mVpp in steady state or after a 128-bit preamble; 2 Gb/s fails; start-up from the first bit fails (baseline wander, τ ≈ 40 ns). |
| `clk_obs` | 500 MHz in, /8 → 62.5 MHz into 10 pF; 12/12 corners; 1 GHz input fails. |
| `ring_osc` | 211 MHz; corners 165–255 MHz. |
| `aosc` (r3) | 47.7 MHz tt/27/3.3 V, 0.38 mA; 13/13 envelope points inside 40–60 MHz: tt 47.6–48.1, ss 42.9–43.4, ff 53.8–54.3 MHz (≥ 7 % margin at both ends); duty ≈ 48 %; EN = 0: < 2 nA. The verdict now requires the 40–60 MHz window (r1 passed on f > 10 MHz). r1 extracted ss was 35.4–37.1 MHz; r2 (schematic-sized, R 11 µm) was 38.2–38.7 MHz extracted at ss, so r3 shortens R to 9.4 µm. |
| `polyphase` | Fails: network node swings ~0.2 Vpp extracted and the limiters do not toggle at 2.4–2.5 GHz. |

Fast cells (`generated/fast/speed.json`, tt): `ct_ring8` 1.12 GHz extracted
(1.78 GHz schematic), `ct_tspc2` divides at 3.5 GHz (fails 4 GHz), `ct_lodrv`
2.45 GHz rail-to-rail (tt, ideal input only; not at ss: see the LC VCO section), `ct_rxin` full swing at 2.45 GHz / 600 mVpp.

**Evidence currency:** `run_timing.py` changed after every evidence file
(testbench additions and removal of retired blocks); rerun before relying on
hashes.  `pll_ring-evidence.json` now records the r6a netlist and layout
(2026-11-09 `run_timing.sh pll_ring`; 224 devices, 80,541 µm², DRC 0 /
KLayout 0 / LVS unique).  r6 as laid out failed **safe**: with `EN=0` the
HOLD flop clock (`!REFP`) sat high and `ct_tspcd`'s reset NMOS fought its
pull-up, 509 µA static (schematic and extracted); r6a clocks the flop with
`NOR(REFP, ENB)` and safe is back to the 10 µA IBIAS (tt/ff 85 °C/ss 0 °C).
`run_timing.py` overwrote the HOLD bench verdict with `locked`, so HOLD
cases could never fail; fixed, and the two stored HOLD results were
re-judged with the corrected criterion (`pass_recomputed_note`). (risk: MOD-05)

**`pll_ring` r7 (2026-11-09, this pass): charge-pump current steering.**
Diagnosis from a schematic HOLD bench (`scratch/timing/pll_ring/dbg_hold`):

* r6a's pump switches let the PMOS source node `PS` float to VDD (and `NS`
  to VSS) between pulses.  At switch-on `PS` dumped its charge into VCTRL:
  +35 mV during the 0.64 ns UP/DN overlap, about 48 µA effective against a
  20 µA pump.
* The loop cancelled that with about 1 ns of DN-only every reference cycle.
  The result was 38 mV p-p VCTRL ripple and 6.5 % PFD activity.  The analog
  `LOCK` detector's break-even is about 6.7 % (3 µA charge against 15×
  discharge), which is why LOCK dropped at 625/810 MHz.  The ripple also
  produces part of the HOLD step.
* The 2.0 µs HOLD instant also falls inside the loop's own settling tail: VZ
  moved 1.3 mV between 1.5 and 1.9 µs, against about 2 ppm/µV of Kvco near
  625 MHz.

r7 steers each source into `VDUM` while its switch is off.  A unity-gain
PMOS-input OTA (10 µA tail from the pump's PB mirror) holds `VDUM` at VCTRL,
with a 2×10/10 µm MOS cap; `VDUM` is clamped low when EN = 0.

Schematic A/B, same bench (`dbg_base` / `dbg_r7`):

| | r6a | r7 |
| --- | --- | --- |
| VCTRL ripple (p-p) | 38 mV | 3.6 mV |
| DN activity | 6.5 % | 3.15 % |
| UP activity | 2.6 % | 2.6 % |
| HOLD step | +850 ppm | +273 ppm |
| Drift over 0.9 µs held | 0 | 0 |

The OTA offset is +8 mV.  r7 layout: 236 devices, 75,772 µm², Magic DRC 0,
KLayout 0, LVS unique (`generated/pll_ring.{mag,gds,ext.spice,lvs.spice}`
are r7).

**r7 extracted result (2026-11-10, `pll_ring-evidence.json`, ext sha256 0a8024aa…):** closed loop locks
at 479.998 / 624.998 / 809.997 MHz and 499.97 / 624.98 MHz host_follow; worst port phase error
4.5 / 4.9 / 5.7° and 4.9 / 5.3° (r6a: 9.0–10.8°), so the steering also removed most of the phase
skew; VCTRL ripple 7.8–15 mV p-p.  Still above the AC-3 3° target: per-phase trim not built.  The
analog `LOCK` flag is wrong at 810 MHz and host_follow (informative only).  **HOLD got much worse
extracted: +19 636 ppm step at 2.0 µs and +20 490 ppm at 4.0 µs** (VCTRL +10.8 / +9.2 mV at the HOLD
edge; schematic r7 was +273 ppm), held drift 112 / 447 ppm/10 µs, HOLD-from-0 drift 67 ppm/10 µs.  The
step is therefore not the settling tail; it is a charge event at the HOLD edge that the schematic does
not show (suspect: the steering switches dumping VDUM/PS charge into VCTRL when both pump halves are
forced off, through extracted coupling).  Not debugged yet.  Consequence: the wired CDR no longer
uses a HOLD hand-over at all (AC-3, wired_rx README: HOLD=1 from enable, FLL and PD on the same pump);
host_follow still relies on HOLD and is affected. (risk: TIM-04)

**`pll_ring` r7 + K1 antenna diodes (2026-11-10, wired_rx owner):** regenerated from the K1-patched
`layout_engine` (9 antenna diodes on HOLD, REF, UP, DN and PFD internals): 236 devices, 75,772 µm², Magic DRC
0, Netgen unique, KLayout main 0 / antenna 0; flat GDS, so `gds_uniquify` renames nothing.  New extraction
sha256 0c6c0fa2…; the nominal subset (closed 480/625/810 MHz, HOLD-from-0 drift) is being rerun on it
(`scratch/wired_rx/regen/pll_ring_sims2.log`); the open-loop corner and HOLD-step records in
`pll_ring-evidence.json` are still from the pre-diode r7 extraction.  AC-3 follow-ups owned here:
N = 5/10 dividers for HDMI/DVI (not built), a vote-driven proportional input for the CDR (wired_rx README,
"AC-3 pump"), the PDN-04 LDO supply.

## External LO through the real pads (`lo_ext_pad.py`, 2026-11-10)

The first-die RF LO (`rf_lo_external_ref`, board B3): I on `REF_IN`, Q on
`AUX_CLK`, through the drawn pads actually bonded there and the B21 package
model. Evidence: `generated/lo_ext-pad-evidence.json` (verdict pass).

* Pads: `REF_IN` = `refpad` (`tx_protected_pad`, receiver VCM bias to
  bias.vcm = VDD/2); `AUX_CLK` = the `rf_protected_pad` debug pair; both with
  their disabled extracted `diff_clk_rx`. The morning run modelled `REF_IN`
  with the rf pad.
* Package and board: 50 Ω source, 10 pF C0G per leg (B19), 1.5 nH + 0.2 Ω bond
  wire per leg (1.0/2.0 nH tolerance runs), 0.1 pF pad-to-pad.
* Criterion: RX switch Vgs on ≥ 0.9 V and off ≤ 0.5 V for I and Q, with the
  switch source at the mixer VCM = VDD/2 (`rxmix_i.spice`; the old benches
  used a fixed 1.65 V); Q−I from differential zero crossings.
* **Steady state, not the 12 ns snapshot.** The LO node's only DC path is its
  20 kΩ to VB, so in steady state avg(LO) = VB exactly. The benches read
  8–12 ns, which is inside the 20–200 ns bias time constants. A 200 ns run of
  the previous design showed VB still 0.24 V low at 12 ns, recovering
  slowly. The evidence therefore projects each window's waveform about
  VB(t = 0). A 300 ns run of the current design at ss/32/3.15/3 Vpp converges
  to that projection: on 0.66 → 0.92 V by 300 ns, projected 0.949 V. Allow
  ≥ 1 µs after enabling the LO before receiving. (risk: PKG-05)
* **Design change:** VB 0.773·VDD → 0.716·VDD (`lo_ext.spice` divider 12.5k /
  31.5k), which centres Vgs (0.63–0.70 V) between the limits. With the old VB
  the steady state failed the off level at ss/3 Vpp (projected 0.53 V).

| Drive per leg (open-circuit, 50 Ω) | Envelope points | Worst on / off (V) | Q−I | Pad peak |
| --- | --- | --- | --- | --- |
| 2.0 Vpp (sweep, tt/ff/ss) | ss fails (on 0.83 V) | — | — | 1.62 V |
| **3.0 Vpp** | **13/13** | 0.949 (ss/32/3.15) / 0.30 | 90.8–91.2° | 1.81 V |
| **4.0 Vpp** | **13/13** | 1.06 / 0.18 | 90.6–90.9° | 1.99 V |
| 3.0 Vpp, bond wire 1.0 / 2.0 nH, ss/32/3.15 | 2/2 | 0.935 / 0.30 | 90.9–91.2° | 1.76 V |
| 5.0 Vpp (sweep) | pass, but pad troughs −0.65…−0.75 V (ESD diode) | — | — | 2.12 V |

Board window (B3): 3.0–4.0 Vpp open-circuit, +7.5 to +10 dBm available per
leg, target 3.5 Vpp. The pads README `Reference` limit (≤ 0.55 V peak) is for
`REF_IN` used as a clock into `diff_clk_rx`; the LO route keeps the pad peaks
≤ 2.0 V, below the clamp's 2.1 V (ff) 10 µA onset. Open: the pad DC is still
rising at 300 ns (VCM through the 10 pF coupling, about a 1 µs time
constant), so the steady-state pad peak is not simulated directly. The
block-level `tb_lo_ext` (`run_timing.py`) uses the same VCM reference and
steady-state projection: 12/12 corners pass at 4 Vpp with its ideal 1 pF pad. (risk: LO-05)

## Autonomous RF LO: quadrature LC VCO (`lcvco/`, r2, 2026-11-10)

Schematic `pt_lc_qvco` (`lcvco/qvco.spice`): two complementary cross-coupled
LC cores coupled in parallel (P-QVCO), 4-bit switched-MIM bank, NMOS-in-n-well
accumulation varactors on VTUNE, AC-coupled self-biased buffers to
`pt_lo_ext` internal mode. Benches: `lcvco/run_lcvco.py`; results
`lcvco/results.json` (r1 in `scratch/timing/lcvco/results.r1.json`); evidence
`generated/lcvco-evidence.json`.

**Tank inductor model (documented, not EM-verified).** `lcvco/spiral.py`
derives a 3-turn square spiral (300 µm outer, 25 µm Metal5‖Metal4‖Metal3 turns,
Metal2‖Metal1 underpass) from the PDK stack (Magic tech sheet resistances and
heights): Mohan modified-Wheeler L, skin and crowding R, Yue–Wong single-pi
substrate network. FastHenry on the drawn polyline gives 2.65 nH and 3.2 Ω at
2.45 GHz; the model nominal uses L = 2.65 nH (FastHenry) with the larger
closed-form Rs = 4.33 Ω. The layout exists (`generated/lcvco/pt_spiral_ind.gds`,
Magic DRC 0). Variants in `lcvco/spiral.spice` (`spiral.json` lists the
closed-form L before the FastHenry scaling):

| Variant | L (nH) | Rs (Ω) | Substrate | Q_eff at 2.45 GHz |
| --- | ---: | ---: | --- | ---: |
| `pt_spiral` | 2.65 | 4.33 | nominal | 8.5 |
| `pt_spiral_lhi` / `_llo` | 2.91 / 2.38 (±10 %) | 4.33 | nominal | 9.2 / 7.8 |
| `pt_spiral_lowq` | 2.65 | 6.50 (×1.5) | worst (Gsub ×3, Csub /3) | 5.0 |
| `pt_spiral_lhi_lowq` / `_llo_lowq` | 2.91 / 2.38 | 6.50 | worst | 5.2 / 4.6 |

**r1 failure and the fix.** r1 (4 mA per core, NMOS pair 40 µm, PMOS pair
80 µm per side) did not start at ss/32 °C/3.15 V with `pt_spiral_lhi_lowq`
(band 0 at VTUNE 0.3 and band 15), nor at ff with `_llo_lowq` in band 15.
A small-signal tank-impedance bench at the static point
(`scratch/timing/lcvco/zac.py`) showed a net +2.7 mS loss at the worst point,
and more tail current alone (8 mA per core) still left +1.9 mS: the pair was
gm/W-limited, not current-limited. r2: NMOS pair 80 µm and PMOS pair 120 µm per
side, tail 6 mA per core (`ntail` 120), fixed MIM 0.70 → 0.55 pF to return the
added device capacitance. Explicit gate resistance is in every run: 16 Ω per
2 µm double-contacted finger (`rgf`), twice the 8.3 Ω poly/contact estimate
(the mandate's 60–150 Ω per single-finger 10 µm device scales to 7.5–12 Ω per
2 µm double-contacted finger). r2 also gates the eight self-biased buffer
input inverters with EN: with EN = 0 they sat at their trip point and drew
16 mA.

**r2 results** (schematic QVCO, explicit gate R, spiral variants as above;
envelope 22–32 °C, 3.15–3.35 V):

| Check | Result |
| --- | --- |
| Start-up, worst code (band 15, VTUNE 0.3), low-Q +10 % L, all 12 envelope points | 12/12 oscillate, tank 1.17–1.37 V diff peak, quadrature 89.0–89.5°, LOI rail to rail (r1: no start at ss) |
| Band coverage at the extremes (band 0 / VTUNE 3.0 ≥ 2.5 GHz, band 15 / VTUNE 0.3 ≤ 2.4 GHz) | tt/nominal 2.160–2.815 GHz; ss/32/3.15 lhi_lowq 1.964–2.636; ss lhi 1.977–2.615; ff/22/3.35 llo 2.381–3.059; ff llo_lowq 2.377–3.088 GHz: 5/5 cover 2.4–2.5 GHz (tightest margin: at ff, band 15 reaches down to 2.377–2.381 GHz, only 1 % under 2.4 GHz) |
| Band continuity, tt (16 codes × VTUNE 0.3/3.0) | every band overlaps the next (each 160–200 MHz wide, steps 25–40 MHz) |
| Negative checks | EN = 0: no oscillation, buffers < 1 nA, core = the 10 µA IBIAS source; coupling removed: Q−I 148° (fails quadrature as expected) |
| Current | cores 13.4–14.1 mA (both), buffers 6.3–14.9 mA (r1: about 9.3 + 10 mA) |
| Phase noise (Leeson estimate, not simulated) | −124.5 dBc/Hz at 1 MHz nominal Q, −117.7 low Q; 0.05–0.12 ps rms outside a 1 MHz loop (budget 0.52 ps) |
| **Chain: QVCO → extracted `pt_lo_ext` internal mode → mixer gates** | **fails** at tt (LO 1.12–3.21 V, Q−I −75°) and ss/32/3.15 (LO stuck high); passes at ff. |

**Open: the internal LO driver (`ct_lodrv` in `pt_lo_ext`) is too slow at
2.45 GHz.** With ideal 50 %-duty 40 ps-edge inputs, the extracted `pt_lo_ext`
internal mode reaches only 0.17–2.11 V at ss/32/3.15 (on-drive 0.53 V against
0.9 V). With 44 % duty, the QVCO buffers' duty, it stays low at ss. The
schematic cell works at ss (0–3.05 V), so the deficit is the
break-before-make skew of the last pre-drivers plus the compact layout's
parasitics. Simply widening the NOR/NG pull-ups breaks the break-before-make
(output stuck low). Needed: rebalance the PG/NG pre-driver skew for 2.45 GHz at
ss, re-layout `ct_lodrv` and `pt_lo_ext`, and set the QVCO buffer duty to 50 %
(differential-to-single-ended stage). This was never covered before: the
block's internal-mode case ran at tt only with ideal inputs. External mode is
unaffected (the driver is tristated). Also open: the frequency loop (PRE →
prescaler → PFD/CP against the `REF_IN` crystal of B23) and a QVCO layout. (risk: LO-07)

**External tank option (MANDATE "off-chip passives"): evaluated, not used.**
The tank needs 2.4–2.9 nH differential. Two bond wires alone are 3.0 ± 1.0 nH
(B21: 1.5 ± 0.5 nH each), so they would be the whole tank and no external
inductor fits in series. The ±33 % L tolerance moves the frequency ±15 %, more
than the bank's tuning range. The only spare pair (`AUX_CLK`) carries the
stress-safe clamp (10 µA onset 2.1 V at ff), and the tank nodes swing about
1.6 ± 1.2 V. No pin requested (`interface-changes.md` LO4). (risk: LO-04)

## RF LO r-cml2: CML driver, LO observation, B3 on the COB chain (2026-11-10, round 2)

Scratch: `scratch/timing/{lo_ext,lo_obs,obs_pre4,clk_obs16,lo_ext_pad*,loobs}`. The interface changes are LO5–LO9, CO1 and CO2 in `interface-changes.md`.

* **`pt_lo_ext` r-cml2.** `ct_lodrv` is replaced by one CML driver `pt_lo_cml` per pair. Its compact switching core is `ct_locml` (`fastcells.py`; 60×21.6 µm, DRC 0, LVS unique). The driver is DC-coupled onto the mixer LO nodes, and a CM loop sets avg(LO) = VB. VB is on in INT mode too and is now 0.739·VDD (was 0.716). The QVCO tank nodes drive `LOI_*` directly (QVCO r3, no LOI buffers).
  * The benches add explicit gate R: 12.5 Ω per pair side (`run_timing.rg_wrap_locml`).
  * `XRC` is 18u/1u: the study's 10u/0.55u violated HRES.3.
  * The layout uses planned rows (`scratch/timing/lay_loext_rows.py`): LO rows on top, I/Q mirrored. This halved the LO wiring C (169 → 60–81 fF) and restored Q−I. 162 devices, 109.6k µm², Magic 0 / KLayout 0 / LVS unique.
* **Internal mode, extracted tt, 100 ns steady state:** on 1.05–1.11 V, off 0.21–0.28 V, Q−I 91–93.5°, duty 43–47 %, 11.8 mA. The 12-corner run, the QVCO→lo_ext chain and the band extremes with the new tank load are in the queue (`scratch/timing/queue.status`). The pass/fail rows above are not regenerated yet.
* **External mode, `lo_ext_pad.py --refpad/--rfpad` (compact pads) and the COB chain (`CHAIN`, `channel.json`), ss/32/3.15:**

| Drive (Vpp open circuit) | P1 2 mm: worst on / off (V) | P3 30 mm: worst on / off (V) | Q−I | Pad peak, ff |
| --- | --- | --- | --- | --- |
| 3.0 | 0.907 / 0.473 | 0.916 / 0.478 | 93.8–95.1° | 1.75–1.79 V |
| 4.0 | 0.981 / 0.387 | 0.994 / 0.394 | | 1.89–1.95 V |
| 5.0 | 1.051 / 0.307 | 1.066 / 0.317 | | 2.03–2.10 V (clamp onset) |

  * Proposed B3 window: 3.5–4.5 Vpp.
  * With VB 0.716 the CML layout lost the ss/3 Vpp margin: on 0.842–0.878 V, Q−I up to 101.5° before the row plan.
  * The compact refpad costs ≤ 13 mV, so it can be released.
* **`pt_lo_obs` (LO/8 for CLK_OBS)** sits on the I tank pair, with a disabled copy on Q. 49 devices, 17.5k µm², clean. Extracted tt passes at 2.4/2.45/2.5 GHz with 0.3–1.1 V amplitude.
  * The first sizing (750 Ω loads, 6 µm hold pair) did not regenerate.
  * The first extracted CML→CMOS stage (0.6 mA) did not reach logic levels; it now runs at 1.8 mA.
  * Inside `lo_ext` the prescaler loaded the LO and failed extracted, so it is now a separate block.
* **`pt_obs_pre4`** (TSPC /4 at the fast CMOS sources) and **`pt_clk_obs16` r2** (code 15 = OR of the three CH1 outputs): both clean; corners are queued.
* **Open:** D-LO-1/2/4 (termination, amplitude detector, I/Q trim, polyphase fallback; see LO9); QVCO layout and the frequency loop (LO3); the 13-point envelope at P3.

## `pt_pll_ring` r9: ring resize, tail-proportional fast-tune (CDR/pll_ring owner, 2026-11-10)

Scratch: `scratch/wired_rx/r4pi/r9/` (`STATUS.md`, benches `fsweep.py`, `ring9.py`, `gen_r9.py`). Backups of the
files changed here: `r9/backup/`. **Promoted:** `pll_ring.spice` (r9; r8 ports), `fastcells.py` `ct_ring9`,
`generated/fast/ct_ring9.*`, `generated/pll_ring.*` (r9 layout). The LO instance and `run_timing.tb_pll_ring`
still use r7 positional ports and must be updated (see interface-changes AC3-W11). (risk: INT-23)

* **Why the extracted ring was slow:** ct_ring8 cell wiring, 25-30 fF per ring node. ss/32 C/2.835 V, VCTRL = VDD:
  schematic 1307 MHz, ring cell extracted 763, full r7 extracted 759. **ct_ring9** (each stage followed by its own
  restore inverters, ring devices 8/16, keepers 1/2): 945 MHz (cell extracted, 2.835 V); full r9 extracted
  891 MHz at 2.71 V (the pt_pll_vreg output at VIN 3.15 V, ss/32 C, ~6 mA). Magic DRC 0, LVS unique.
* **Range, one band, regulated supply:** 393-834 MHz needs VCTRL 0.87 V (ff/22/3.015 V) .. 2.02-2.03 V
  (ss/32/2.71 V). Full r9 extracted: ss/32/2.71 V 833 MHz at 2.02 V, 891 at VDD (7 % top margin); ff/22/3.015 V 396 MHz at 0.87 V; tt KP=3 930 ppm/vote at 629 MHz. No coarse band.
* **Fast-tune (P) units:** tail/header copies (NMOS W 0.44 L 20 on VT, gate VCTRL through 100 k; PMOS W 0.44
  L 1.75 on VH, gate VPB through 20 k), rail-end switches as r8. KP=3 ppm/vote (schematic, ring cell extracted):
  tt 919 / 932 / 913 at 393 / 630 / 834 MHz; ss 999 / 514; ff 917 / 861. The r8 conductance stacks on this ring
  gave 15-380 ppm/vote (ppm ~ 1/I_ring).
* **Layout (r9):** 202.9 x 921.2 µm, 665 devices, Magic DRC 0, LVS unique, KLayout main 0, **antenna 12
  (ANT.16, M5 trunks of NX/N16B/REFG/S16B/PFD/LOCK/FD2/XHD22_x nets where the diode planner placed no diode):
  not clean, open.** (risk: INT-05)
* Phase error (ring cell extracted, ss 834-945 MHz): up to 7.5 deg (ct_ring8: up to 8.1 deg). Not trimmed here. (risk: WRX-15)

## RF LO owner round 3: queue review, frequency loop, D-LO-1/2 (2026-11-11)

**Queue review (`scratch/timing/queue.status`, all six done).** `lo_ext` full r-cml2, `obs_pre4`,
`lo_obs` and `clk_obs16` completed. Findings on the `lcvco` runs:
- r3 extremes (CML-direct tank, no buffers): the tank moved down about 2 % from r2. Results:
  tt 2.116–2.722 GHz; ss/32/3.15 lhi_lowq 1.927–2.550; ff/22/3.35 llo_lowq 2.322–2.975.
  **All-corner guaranteed 2.33–2.53 GHz** (r2 claimed 2.38–2.615); all-corner span 1.93–2.98 GHz.
- Every ff point was flagged `cml_drive_ok = false`. The cause was the tank common mode of 2.14–2.19 V
  against a 2.1 V criterion edge. New chains at ff with band 0 (`r4_chain_ff22_*`, extracted
  `pt_lo_ext`) show the drive is fine there: on 1.19–1.21 V, off ≤ 0.24 V, 2.80 / 3.00 GHz.
  The CM window is now 1.3–2.2 V and all 20 extremes pass.
- The chain bench clamped its pass to 2.4–2.5 GHz. That is the GX-6 clamp, so it now passes on the
  tank range (1.9–3.1 GHz) and reports `in_ism_band` separately.
- The `codes` and `startup` results were r2 (with the removed buffers). They moved to
  `r2_superseded` and were rerun with the r3 loads:
  - start-up 12/12 envelope points with low-Q +10 % L, band 15 / 0.3 V: 1.93–2.10 GHz, tank 1.13–1.35 V diff peak, Q−I 88.7–89.5°
  - tt codes: every band overlaps the next, 2.117–2.722 GHz
  - `generated/lcvco-evidence.json` regenerated: verdict pass, schematic QVCO only
- **I/Q error through the extracted `pt_lo_ext` is systematic, 2.5–3.7°.** The tank alone is
  89.2–89.5°. On the 5 chain points, Q−I is −92.5 to −93.7° at the LO pins, against RF-LO-JIT
  I/Q skew ≤ 1.16 ps (1.0°). This fails without D-LO-2 trim, and it matches the 93.5° seen in
  external mode, so the skew is in the `pt_lo_ext` layout. (risk: TIM-07)

**D-LO-2 I/Q phase trim (`lcvco/run_lotrim.py`, transistor level, extracted `pt_lo_ext` + schematic QVCO).**
Proposed cell `pt_lo_iqtrim`: a binary bank of NMOS-in-n-well accumulation varactors
(`cap_nmos_03v3_b`) on each `LO_*` mixer-gate node. The well is driven by the trim bit:
0 → accumulation, high C; 1 → low C. There is no series switch. The LO node is common to the
internal and external modes, so one trim covers both. The LSB is 4 µm² (≈ 12 fF swing). Code +k
loads I, −k loads Q.

| Point | code 0 | +4 | −4 | +15 | −15 | on / off at ±15 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| tt/27/3.3, band 6 | −93.3° | −96.5° | **−90.0°** | −104.6° | −82.0° | 1.11 / 0.33 V |
| ss/32/3.15 lhi_lowq, band 0 | −93.7° | | | −105.5° | −81.9° | 1.02 / 0.38 V |
| ff/22/3.35 llo, band 15 | −92.5° | | | −102.5° | −82.5° | 1.14 / 0.30 V |

The slope is 0.67–0.82° per LSB, and 4 bits give ±10–12°. **Proposal: 5 bits with the same LSB
(±20–24°, ≤ 0.82°/step), which meets ±15° in ≤ 1° steps.** Code −4 nulls the tt chain error
(−90.0°). The amplitude cost at full code is ≤ 55 mV of on-level; the worst case, ss, gives
1.02 V against 0.9 V. Not done: the ±1 dB I/Q amplitude trim, a layout, and the 5-bit run.

**D-LO-1 termination (`scratch/lo/dlo1.py`, extracted `pt_lo_ext` + drawn pads + COB chain at P3 = 30 mm).**
The test used a per-leg 50 Ω shunt (NMOS switch + R to a decoupled VDD/2 node) on the existing
passive (transmission-gate) external path: (risk: LO-05)

| Source (Vpp open circuit) | ss/32/3.15 on / off (V) | ff/22/3.35 on / off (V) | Pad peak / trough |
| ---: | --- | --- | --- |
| 4 | 0.77 / 0.58 ✗ | 0.87 / 0.50 ✗ | 3.00 / 0.59 V (ss) |
| 6 | 0.84 / 0.47 ✗ | 0.96 / 0.36 ✓ | 3.10 / 0.09 |
| 8 | 1.00 / 0.33 ✓ | 1.13 / 0.15 ✓ | 3.18 / −0.40 |
| 10 | 1.09 / 0.23 ✓ | 1.27 / 0.05 ✓ | 3.25 / −0.70 (diode) |

With 50 Ω, the passive path needs +18 to +20 dBm per leg. The pad then swings past the 2.1 V
clamp onset and into the ESD diode, and the usable range is < 2 dB. **A shunt termination on the
passive path cannot deliver the ≥ 10 dB amplitude tolerance.** Counter-proposal (interface LO11):
route the external LO through the existing `pt_lo_cml` limiter, i.e. pads → AC-couple → `LOI_*`.
Its output level is set by the tail and load, not by the input. Keep the termination as an
optional match (100/200 Ω) for return loss only. This still needs a bench: the CML input
sensitivity floor and the pad clamp give the range.

**Frequency loop (LO3, GX-6, IX-5): behavioural design `lcvco/loop_design.py` → `lcvco/loop_design.json`.**
No transistor-level loop exists yet. The VCO curves are the r3 extremes.
- Architecture: 50 MHz XO on `REF_IN`. B23 already lists 50.625 MHz; any reference works
  fractionally. Then a PFD at 50 MHz and an extended 2/3 MMD N = 32–127 in custom TSPC. The first
  cell must toggle at ≤ 3.1 GHz; it is not yet checked at ss. A MASH 1-1-1 ΣΔ (16-bit) and the
  band-search FSM run in standard cells at 50 MHz. The 4-step binary band search counts PRE/16
  for 1.28 µs per step, about 6.4 µs total. Last comes the type-II CP loop: Icp 100 µA,
  R 22.1 kΩ, C2 67 pF, C1 5.2 pF (≈ 14.5k µm² as MOS cap), fc 400 kHz, PM 60°.
- **GX-6:** the divider covers 1.75 GHz to the MMD input limit, more than the 1.93–2.98 GHz tank
  at every corner. Over Kvco 39–79 MHz/V and N 38–60, fc stays 0.23–0.63 MHz and PM 56–60°.
  There is no 2.4–2.5 GHz clamp anywhere.
- **IX-5:** the bench is cycle-accurate: exact edge times, 5 % UP/DN mismatch, 150 ps reset,
  2 nA leakage, CP headroom roll-off. After band search, a 78 MHz hop (2402 ↔ 2480 MHz) on
  tt / 40 / 75 MHz/V curves settles to LO phase within 2° of its final trajectory in 7.5–11.9 µs.
  With band search that totals **18.3 µs, against T_FCS − 5 µs = 75 µs (pass, behavioural)**.
  The frequency error at 80 µs is 0 Hz to model precision. Reference spurs are not assessed by
  this model.
- **Phase noise vs RF-RX-LOPN (budget, not simulated):**

  | Offset | Mask (dBc/Hz) | Total | Margin |
  | --- | ---: | ---: | ---: |
  | 1 MHz | −95 | −104.5 | 9.5 dB |
  | 3 MHz | −107 | −114.5 | 7.5 dB |
  | 20 MHz | −115 | −120.2 | 5.2 dB |
  | 40 MHz | −120 | −140.1 | 20 dB |
  | 100 MHz | −130 | −157.7 | 27.7 dB |

  The low-Q VCO Leeson number is −117.7 dBc/Hz at 1 MHz. The other inputs are an XO floor of
  −150 dBc/Hz, an assumed PFD/CP/divider floor of −208 dBc/Hz/Hz, and MASH-1-1-1 quantization.
  At 25 MHz the PFD failed 3 MHz by 5.9 dB (ΣΔ), which is why the loop uses 50 MHz.
  **Integrated 10 kHz–100 MHz: 1.35 ps rms, against RF-LO-JIT ≤ 1.05 ps: FAIL.** The PFD floor
  (in band) and ΣΔ (20 MHz) dominate. Open: a 4th-order filter pole, or a lower ΣΔ order with
  dither, plus a transistor-level PN sim of the QVCO. (risk: LO-04)

## `pt_pll_ring` r9d / `pt_pll_ring_core` (wired_rx RINGAREA, 2026-11-11)

Compact CDR fast-tune array, new line-ring master without FT/N5/N10 (pll_tx), WT21 `BAND` port before `VDD`
(tail 8×10/1 high band, half in low band), pll_host deleted (X1).  Areas, extracted range and the vote-rate
injection finding: `analog/wired_rx/README.md` "Resume 6 / RINGAREA"; interface-changes AC3-W13/W14/W14a.
`generated/pll_ring-evidence.json` predates r9 (not regenerated).

## RF LO owner round 4: jitter closure, QVCO r5 layout, loop blocks, LO11, PD29 (2026-11-11)

Interface rows LO14–LO16; scratch `scratch/lo/r4_*`. Unless stated, "extracted" = Magic C or RC extraction of the promoted layout.

**Round 3 superseded.** The r3 "2.33–2.53 GHz guaranteed" range was a schematic number. The first QVCO layout
(RC-extracted) gave an ss band-0 top of 2.346 GHz and no start at band ≥ 12, as the model-uncertainty audit said.

**Layout capability.** `layout_engine.py` places GF180 `cap_mim_2p0fF` and `nvaractor_3p3` from the Magic PDK
generators (single-finger varactor tiles: the PDK multi-finger generator is broken), with `net_width`, MIM-plate
keep-outs and symmetric trunk groups. Test cell DRC/KLayout 0, LVS unique; existing users byte-identical.

**QVCO r5 (`lcvco/qvco5.spice`, `generated/lcvco/pt_lc_qvco5*`, hand-placed RF tank).** 8 mA/core, 15-cell MIM bank,
rotated spiral (equal 60–67 µm feeds), `CMLSEL` PMOS header, ATB taps `ATB_VTUNE` (20 kΩ + TG) and `ATB_ITAIL`
(1/64 replica). Precheck main/antenna 0. RC-extracted:

| Case | band 15 @ 0.3 V | band 0 @ 3.0 V |
| --- | ---: | ---: |
| PESS: ss/32/3.15, L +10 %, +3 Ω/branch, C ×1.15 | 1.890 GHz | 2.713 GHz |
| OPT: ff/22/3.35, L −10 % | 2.280 GHz | 3.097 GHz |
| tt / ss / ff | 2.077 / 2.008 / 2.155 | 2.881 / 2.856 / 2.914 |

2.40–2.4835 GHz is covered with ≥ 3 % margin both sides at every case (RF-QVCO-RANGE → 2.30–2.70 GHz guaranteed).
All 17 band-end points start (≥ 1.10 V diff), Q−I −86.4…−88.4° (inside the trim), 17–18 mA. PN (tt, injected
tank noise, transient zero-crossing method; no flicker upconversion): −114.6 dBc/Hz @1 MHz, −135.8 @20 MHz.
Kvco 38–122 MHz/V across VTUNE. The full 16-code overlap sweep and the PESS PN point were still running at the
time of writing.

**Frequency loop (`lo_mmd`, `lo_mmd_qdum`, `lo_pfdcp`, `lo_lf`, `lcvco/run_loop.py`, `loop_tl.json`).**
* MMD: a 2/3 cell cannot toggle at 3 GHz in GF180 (zero margin schematic, fails extracted at ss), so the chain is
  CML /2 → 2 CML + 3 CMOS 2/3 cells, ratio 2·N (32–126 even). Extracted 16/16 pass at ss/32/3.15 (2.98, 3.1 GHz),
  tt, ff for N = 32/64/98/126; 19–34 mA. Q-side dummy load block added.
* PFD/CP r2: dynamic PFD, reset overlap 0.11–0.18 ns (DN, extracted; UPB 0.26–0.52 ns); CP 100 µA,
  L = 4 µm degenerated sources, filtered bias. Extracted: mismatch ≤ 1.03 % over VTUNE 0.8–2.5 V (falls apart
  outside it: lock window 0.8–2.5 V); in-band CP noise −123.4…−125.7 dBc/Hz @10 kHz (N = 49). Area 0.31 mm² (open).
* Loop filter: Icp 100 µA, fc 250 kHz, R 13.09 k, C1 6.96 pF MIM, C2 351 pF n-well accumulation varactor
  (valid 0.3–3.0 V), R3 10 k / C3 15.9 pF (pole 1 MHz). Analytic: fc 125 kHz / PM 55.7° at 40 MHz/V,
  303 kHz / 42.6° at 120 MHz/V.
* Lock: **no valid closed-loop result yet.** An earlier "≤ 29 µs" figure is retracted: the audit
  (`scratch/reviews/lo-lock-sim-audit.md`) found that bench started already locked (zero frequency error, preset VTUNE and
  phase), used a lock check that could not fail, stale PFD/CP, C-only parasitics, N = 62 out of band, integer-N only and 2×
  the intended loop gain. The audit's validation ladder (ideal loop vs analytic and must-fail cases, then one extracted block
  at a time, RC-extracted MMD, fractional-N) is in progress.

**Integrated jitter (`loop_design.py r4` → `loop_design.json["r4"]`): OPEN, depends on the VCO flicker corner.**
The r3 budget used one −208 dBc/Hz FOM; the measured r1 CP (−84 dBc/Hz in-band @10 kHz, flicker) gave ≈ 1.4 ps.
Audit rebuild (`["r4"]["audit_rebuild"]`): extracted worst-corner CP (ff, −123.4 dBc/Hz @10 kHz), LO18 Icp scaling,
N 44–56, Kvco 38–200 MHz/V, MASH 1-1-1 with the 2-cycle step, XO −150 dBc/Hz × N², 0.3 ps divider jitter (assumed),
2.2 ns fractional-N on-time (assumed), 4th-order pole. Worst case vs RF-LO-JIT ≤ 1.05 ps:

| VCO L(1 MHz) | no flicker upconversion | 1/f³ corner 300 kHz | 1 MHz |
| --- | ---: | ---: | ---: |
| −112 (bound) | 0.86 ps (fc 250 kHz) | 1.10 ps (best fc ≈ 400 kHz) | 1.63 ps |
| −114.6 (r5 tt, no flicker) | 0.65 ps | 1.13 ps (fc 250 kHz) | 1.81 ps (fc 250 kHz) |

With the r5 RC-extracted **PESS** point (−105.7 dBc/Hz @1 MHz, b8 at 2.16 GHz, no flicker) the worst case is **1.65 ps** (best fc ≈ 400 kHz, Kvco 25–150 MHz/V).

**The PESS QVCO point fails RF-LO-JIT even without flicker** (−105.7 dBc/Hz @1 MHz, −128.6 @20 MHz; low-Q tank,
L +10 %, +3 Ω/branch). Closing it needs a better pessimistic-corner tank Q / swing (or a narrower loop with a
lower CP/ΣΔ floor). With fc ≈ 400 kHz and the tt VCO, a 1/f³ corner ≤ 100 kHz gives 0.89 ps. Kvco (r5, C-only
16-code sweep) is 25–40 MHz/V below VTUNE 1.65 V and 95–150 MHz/V above it: the loop must cover 25–150 MHz/V (LO18
Icp scaling) or the band search must keep VTUNE in the low-Kvco half. The QVCO flicker corner is not yet simulated (the
injected-noise PN method has no flicker), so the jitter requirement is **not** closed. Mask (RF-RX-LOPN) passes in
every case. Options rejected by numbers: integer-N (2–5 MHz compare raises the in-band floor 10–14 dB), MASH-4
(≤ 0.03 ps), 100 MHz compare (needs the shared `REF_IN` XO changed). IX-5 (behavioural, r4 3rd-order filter): 41 µs
including band search, limit 75 µs; not yet confirmed at transistor level. Reference spurs (4th pole, analytic):
mismatch 3 % × 0.2 ns −127 dBc, 100 nA leakage −117 dBc, 5 % bleed −83 dBc.

**I/Q (`pt_lo_ext`).** The ~3° skew came from the LOI wiring load (I ≈ 7.5 fF/node heavier) converted by the QVCO,
not the driver (0.3–0.8°). Chain Q−I on the promoted r4h: −90.29 / −90.13 / −89.94° (tt/ss/ff). 5-bit + sign
phase trim (`run_lotrim.py`): ±19°, 0.55–0.75°/LSB, monotonic, best code 0 on r4h (residual ≤ 0.30°, simulated).
±1 dB amplitude trim fails in the LO (CML Rc trim ±0.4–0.55 dB; CM loop pins the tail) → baseband (LO14).

**LO11 (`pt_lo_ext` r4h, promoted).** Dual-input CML driver: EXT pair on the AC-coupled pad node, tail steered by
the new `CMLSEL` port. Extracted, COB chain at 30 mm: usable source **1.0–4.5 Vpp (≥ 13 dB)** at ss/tt/ff
(on ≥ 0.922 V, off ≤ 0.484 V, Q−I 92.5–94.4°); 20–40 mm / ±0.6 mm bond move the level ±0.6 dB, Q−I ±1°.
The passive external path is backup only (ss 4.5 Vpp fails by 3 mV). Terminate to VPAD or AC-couple (a 50 Ω
shunt to VDD/2 drives the pad to 3.0 V). 297k µm².

**PD29 HBM.** `lo_ext` pad switches: 6 V nfet with a bootstrapped gate (100 kΩ + 200 fF to pad); a plain 6 V
device still sees 6.5 V. `diff_clk_rx` r5 (see limitation 8): bootstrapped 6 V series nfet. Screen:
`ref_lo_ext`, `aux_clk`, `wclk_wtx_ext` 0 exceedances.

**RF-QVCO-RANGE decision.** 2.30–2.70 GHz is guaranteed at every corner including the pessimistic losses, and
covers 2.4–2.4835 GHz plus ≥ 3 % band-search margin. A still wider guarantee is not worth it: it would need a
larger switched-cap ratio (lower Q and higher Kvco, both of which cost jitter), and sub-bands are served by the
external LO path.

## Known limitations and open items

1. **`pll_ring` HOLD fails extracted (r7: +19 636 ppm step, limit 200; see above).**  r7 schematic gave +273 ppm.  Under
   AC-3 (`spec/interface-architecture-changes.md`) the CDR uses a continuous
   integral path with no HOLD hand-over; HOLD stays for host_follow.  r6a record: at
   625 MHz the hand-over step is +1545 ppm (limit 200) and the held drift
   110 ppm/10 µs (limit 100); with HOLD from t=0 the drift is 267 ppm/10 µs.
   Cold start locks at 480 and 810 MHz.  r6a port phase error is 9.0–10.8°
   (r5: 4.6–5.5°) and the analog `LOCK` flag is wrong at 625/810 MHz and
   host_follow (informative only).  Closed-loop lock is nominal-only;
   jitter/phase noise and reference spurs are not covered. (risk: TIM-04, TIM-05)
2. **`polyphase` fails extracted.**  The autonomous-LO plan (P3-4) uses the
   passive network only, without limiters; the block in this directory
   still carries the limiters. (risk: TIM-06)
3. **Autonomous RF LO (`lcvco/`, r5; section "round 4"):** QVCO r5 is laid out and
   RC-extracted (2.28–2.71 GHz guaranteed incl. the pessimistic case); the
   frequency-loop blocks exist at transistor level but the closed-loop lock
   sim and the CP noise fix are still open, so it is not yet a qualified LO.
   The first-die RF LO baseline is the external route through the CML
   driver (`CMLSEL`, 1.0–4.5 Vpp). (risk: LO-04)
4. `lo_ext` (r4h): ext-CML window 1.0–4.5 Vpp per leg; the passive external
   path is backup only (fails ss/4.5 Vpp by 3 mV). (risk: LO-07)
5. `clk_obs` has 8 inputs and /2^0..7, smaller than `debug.clk_obs`
   (two instances needed; `divider_log2` 8..15 unsupported). (risk: TIM-09)
6. `vco_replica` has no `vco_coarse` DAC or divider select (VCTRL from ATB,
   fixed /16).
7. ~~`aosc` is below 40 MHz at ss.~~ Fixed in r3 (above); `scratch/aosc/` keeps the r1/r2 evidence.
8. `diff_clk_rx` (r5, 2026-11-11): data mode qualified extracted at 0.5–2 Gb/s,
   300–800 mVpp, AC-coupled 10 pF, with ±18–20 mV hysteresis. It starts from
   electrical idle without a preamble. Run length is limited to ≤ 20 UI at
   2 Gb/s and ≥ 50 UI at 0.5 Gb/s, set by edge timing after a long run rather
   than threshold. A source parked at a data level before the first bit is not
   supported. Current is 2.6–5.1 mA when enabled. Through `wtx_ext_rx`, 2 Gb/s
   is limited by the wired_tx driver path, not the receiver. PD29 HBM screen
   `wclk_wtx_ext`: 0/105 over (bootstrapped 6 V series nfet). (risk: TIM-08)
9. Not covered: mismatch/Monte Carlo, IR drop and RC clock skew (C-only
   extraction), substrate coupling, ESD (pads family), integration with
   `atb_tap` and the island switch. (risk: MOD-02)
