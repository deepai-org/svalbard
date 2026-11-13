# Integration check M6: power-up/down, reset and isolation states (2026-11-13)

First chip-level check of `integration-plan.md` (mechanism M6, gaps G1/G3/G5/G8). No design file was changed.
Work directory: `scratch/integration/m6-powerup/` (`chipnet/` netlist, `audit/` script, `sim/` transient bench,
`leak/` provider-cell currents). Demands: rows `INT6-*` in `interface-changes.md`.

Inputs used from the two parallel reviews: `always-on-audit.md` (per-block POR, bias, aosc, switch results; I did
not repeat them) and `mode-walk.md` (census of the unbound chip netlist). This report covers the interactions.

## 1. Verdict

- **Power-up of the always-on set is safe for supply ramps of 10 µs and slower** (10 µs, 1 ms and 1 s ramps,
  tt/27/3.3 V and ff/85/3.63 V; power-down in 1 ms): all five islands stay off, every switch isolates, bond
  current stays under 1 mA. The POR makes a reset on the 10 µs and 1 ms ramps and none on the 1 s ramp at ff.
- **A 1 µs supply edge is not safe.** It fires the 22 provider supply-pad clamps: 8.7–10.3 A through the bonds
  and the die rail rings to 5.7–6.4 V (finding 1). No board rule limits the ramp today.
- **The isolation state of the chip is not built.** The chip netlist has 0 isolation cells; the audit fails on
  67 items. Most are already demanded (LU-02, PD7, PD8, RA-3) but none has reached the netlist, and three
  groups are new (104 macro input bits outside the isolation plan, 11 ungated ATB leaves, unpulled host inputs).
- **The audit can only speak for the bound 77 % of the netlist** (section 3.4). It is a check that the binder
  must pass once the top netlist is real, not a sign-off of today's chip.

## 2. Findings, ranked

| # | Severity | Finding | Numbers | Reproduce | Known as |
|---|---|---|---|---|---|
| 1 | **High** (damage on hot-plug; one bench, needs confirmation) | **New:** a 1 µs supply edge triggers the RC clamps in the provider supply cells (8 `dvdd`, 10 `dvss`, 4 corners, each a 4 mm nfet behind a 360 kΩ × MOS-cap timer). They crowbar the rail for longer than the 3.5 µs simulated and the bond inductance rings the die rail above its limit. A 10 µs edge does nothing. The block-level "1 µs ramp" safety evidence (island switches) does not include these cells. | 1 µs to 3.63 V, ff/85: 10.3 A peak, 7.7 A still flowing at 3.5 µs, VDD peak 6.44 V (200 pF die) / 6.06 V (1 nF + 0.5 Ω), above 3.63 V for 0.41–0.45 µs. tt/27 to 3.3 V: 8.7 A, 5.73 V. 10 µs to 3.63 V: 0.2 mA, 3.630 V. | `sim/` runs `ring_*` (supply + provider cells only) | New. PDN-07 covers island turn-on only. |
| 2 | **High** | No isolation cell exists at any island crossing. Nets driven only from a switched island reach gates in another domain with nothing to hold them when the driver is off. | 0 `iso_clamp`/`iso_pd` instances. 10 nets in the netlist (LO_IP/IN/QP/QN, WMON_IN, WTX_EXT_DATA, ct_wclk, fc_src[1..3]) = 14 receiver pins, 4 of them always-on macro inputs. `ISO_rf/pll/conv/debug` have no consumer. | `audit/iso_audit.py` → rule K1 | LU-02, PD7 placement list (13 nets), mode-walk. Still not in the binder. |
| 3 | **High** | **New:** 19 groups of digital-macro inputs (104 bits) come from switched islands per `pt_chip.sv`, are in no isolation plan, and are not bound at all: `wire_rx_data[39:0]`, `rf_rx_sample[23:0]`, `wire_analog_status[12:0]`, `analog_status[11:0]`, 8 clocks (`wire_rx_clk`, `wire_tx_clk`, `rf_rx_clk`, `rf_tx_clk`, `host_word_clk`, `ref_clk`, `ct_ref_clk`, `ct_det_clk_in`) and 6 single bits. The macro is always on; with the island off these inputs are held only by a dead driver. | 104 bits; PD7 covers 13 nets, of which 6 are macro inputs. | K1, entries marked `contract_level` | New (mode-walk MW-33 names `ref_clk`, `host_word_clk` only) |
| 4 | **High** (with strap set) | `por_bypass` = 1 removes the only power-on reset unless RESET_N is low at power-up. With RESET_N held high by the host and SCLK toggling, all five island-enable flops and `biasgen.ena` load 1 and every island turns on during the ramp. The strap itself works: with the POR stuck low and bypass = 1, `rst_n` releases; with bypass = 0 it never does. | bypass=1, RESET_N=VDD: 5/5 rails at 3.30 V, inrush 1.3 mA (unloaded rails). POR stuck, bypass=0: `rst_n` low for 60 ms. POR stuck, bypass=1: `rst_n` high. | `sim/` runs `info_bypass_no_reset`, `nc_por_stuck`, `ok_por_stuck_bypass` | DT-10 (strap), always-on F1/F9. The RESET_N-low condition is new. |
| 5 | Medium | 11 ATB leaves sit on a node with p-diffusion in an island-rail well but their select is not gated by that island: the five `TRK_<island>` trunk nodes on both buses (ATB0 is the force bus) and `VREF0_CONV` on ATB1. A closed leaf with the island off lets the bench drive a diode into the dead rail. Of the 32 bound leaves on island nodes, 15 are gated, 6 are supply-monitor taps (exempt by policy, wells on the core rail) and these 11 are not. | 10 + 1 leaves; 35 of 77 leaves have an unbound node. | K7 | RA-3 interlock exists for island nodes; these 11 are classed "core" in the register map. New. |
| 6 | Medium | 14 host inputs have no pull (SPI_SCLK, SPI_CS_N, SPI_MOSI, H2D[9:0], H2D_CLK: provider `bi_24t`, IE=1, PU=PD=0). With the FPGA unconfigured they float; RESET_N alone has a pull-down. | One pad at mid-rail draws 21 µA (tt/27/3.3) / 40 µA (ff/85/3.63) from the core rail: up to 0.57 mA for 14 pads. A floating CS_N can select the SPI slave once reset is released. | `leak/ioleak.py` (`bi24_in_padmid`), audit pad table | New |
| 7 | Medium | Pad back-drive into an off island (p-diffusion on the pad net with its well on, or resistively tied to, a switched rail): RF_TX_P/N (rfdriver), WIRE_TX_P/N (txpad on RAIL_wired, detect through a resistor), USB_DP/DN (wirepad on RAIL_wired, then WRX_P/N into ctle, detect, rxselect, wmon_sel). | 6 pads, 12 victim pins. All other custom pads end on an isolated ESD rail (no path to a supply). | K2, pad table | LU-03 / board B26 (power before drive). Listed for completeness. |
| 8 | Medium | Cross-island diffusion: `WTX_EXT_DATA` (debug ↔ wired, both directions) and `ct_word_clk` (pll ↔ wired). | 2 nets, 4 pins | K2 | A6, PD7/PD8 |
| 9 | Medium | Two nets still have two push-pull drivers in the binder: `island_on[0]` (macro and `wtx_fallback_control.WIRED_ON`) and `ct_word_clk` (macro and `pt_wordclk`). The RTL side was fixed (`wired_on_ext`); the binding was not. `wtx_fallback_control` also has its `VDD` pin on RAIL_wired, so it cannot assert WIRED_ON while the wired island is off. | 2 nets | K5 | PD8/D8, MW-33. The supply pin is new. |
| 10 | Medium | Three always-on control gates float: `aosc.EN`, `core_bias.EN_pll_ring_tx`, `core_bias.EN_pll_ring_host`. | See always-on F2 for the aosc current (up to 1.79 mA). | K6 | always-on F2; the two core_bias pins are new |
| 11 | Low | At a 3.63 V source there is no headroom: the die rail peaks 0.1–0.8 mV above 3.63 V at the ramp knee, so my fixed "no node above 3.63 V" check fails in every 3.63 V run. `rst_n` (5 V-oxide std cells, 6 flop loads in the bench) peaks 3.69 V; in the macro it carries thousands of loads. | VDD max 3.6301–3.6308 V; rst_n 3.690–3.696 V | `sim/results.json`, check `vmax` | New, no action beyond keeping the source ≤ 3.6 V |
| 12 | Low | `island_pgood[0]` glitches to 0.51 V for the wired switch on a 1 ms ramp at ff/85/3.63 V (below any logic threshold; reset is asserted). Island rails peak 0.33 V at ff/85. | PG 0.507 V; rails ≤ 0.326 V against my 0.40 V limit | run `s2_ff85_r1m_363` | Rail value matches always-on F8 |

Not a finding: integration-plan G1 assumed every custom pad's shunt loads the always-on rail. It does not. The
custom pads clamp to isolated `ESD_RAIL_*` nets; only the provider supply cells and the pads on RAIL_wired
touch a supply.

## 3. (a) Isolation-state audit

### 3.1 What is authoritative, and why

`chipnet/pt_chip_full.spice` + `binding.json`, regenerated today by the maintained binder
(`verification/chip_assembly/netlist.py`, stage 6 of the assembly flow) from the **current** extracted block
netlists, on the v5 run2 instance list (v6 is outline-only and has no netlist). `pll_host` dropped and `pll_tx`
on `pt_pll_ring_core` per X1/X4. Reset and off-state values come from `rtl/pt_digital_macro.sv`,
`rtl/pt_regfile.sv` and `spec/register-map.json`, read fresh (the RTL already carries
`rst_n = reset_n_pad & (por_n | por_bypass)`).

Reason: `pt_chip.sv` keeps the analog side as one black box and `contract.json` has no device terminals. Only
the binder resolves each block pin to a net and carries the transistors, which the diffusion test needs
(a p-diffusion is traced through the hierarchy to the top-level net of its n-well).

### 3.2 Rules and result on the netlist as it is

`python3 audit/iso_audit.py` → `audit/iso_audit.json`, exit 1.

| Rule | Checks | Fails |
|---|---|---|
| K1 float | island-driven net into gates of another domain needs a clamp whose ISO pin is an isolate-high net of the driving island | 33 (14 pins on 10 nets + 19 contract-level groups) |
| K2 diffusion (LU-02) | p-diffusion in an island well on a net a pad, the core or another island can pull high | 18 |
| K3 switch | `isw_X.EN` = `island_en[bit]` (resets 0), PG and rails correct | 0 (all 5 correct) |
| K4 glue | every `EN_EFF_*` net has an RTL `en_eff` with the same island gate | 0 |
| K5 contention | macro output sharing a net with another driver | 2 |
| K6 always-on float | unbound control gate on a core block | 3 |
| K7 ATB (G8) | leaf on an island node must have its select gated by that island | 11 |

The pad table (every pad's state before SPI is alive) is in `iso_audit.json:pads`. Summary:
- RESET_N: input with pull-down. SPI and H2D inputs: no pull (finding 6). MISO, D2H, D2H_CLK and the five
  observation pads: hi-Z (their enables reset 0).
- ATB0/ATB1: pad switch open, wells on the core rail.
- RF_RX, BB_I/Q, REF_IN, AUX_CLK, WCLK_IN, WTX_EXT, WMON, ESD_TEST, WIRE_RX: hi-Z, diode to an isolated ESD
  rail only.
- RF_TX, WIRE_TX, USB: back-drive path into an off island (finding 7).

### 3.3 Negative control

`python3 audit/iso_audit.py --selftest` → `SELFTEST OK`. It adds a clamp on every netlist-level K1 net
(9 clamps, ISO = the switch's own `ISO_<island>`), confirms those crossings pass, then injects four errors:

| Injected error | Detected |
|---|---|
| clamp ISO pin moved to `island_on[2]` (inverted polarity) | K1 +1 |
| one clamp removed | K1 +2 |
| `isw_rf.EN` tied to VDD (forced-on island) | K3 +1 |
| island gate removed from one ATB select | K7 +1 |

The overlay is a test vehicle, not the fix: the LO nets need the `iso_pd` pull-down of PD7, which the audit
also accepts.

### 3.4 What the audit can and cannot conclude

- It walks 147 instances and 2,139 nets. **653 of 2,892 ports (23 %) are unbound**, worst on slicer (109),
  wiredtx (68), bbfilter_i/q (82), adc_i/q (59), clockmux (30). An unbound port cannot fail K1/K2, so a pass
  on those blocks means nothing yet.
- Blocks in the v6 list but not in the binder are not audited: qvco, lo_mmd, lo_pfdcp, lo_lf, cdr, wrx_cap,
  ptrim, vthdac, pll_vreg2, and the HS receive pad (present but with every control pin unbound).
- The digital macro is a black box with the pin list of the AC1_R4 LEF: `por_bypass`, `rf_tx_clk_out` and
  `wire_rx_ptrim_en` are in the RTL but not in that list.
- Macro inputs with no driver are judged from a hand table of source islands (finding 3), not from devices.
- Domain of a gate inside a mixed-supply instance (island switch, core_bias) is set by a two-line table.
- The audit is static. It does not see sequencing (which island rises first) or analog levels.

So: K3/K4 passes are real, the K1/K2/K5/K6/K7 fails are real, and the absence of a fail on an unbound pin is
not evidence. Rerun on the chip-top owner's netlist.

## 4. (b) Power-up transient

Bench: `sim/pu_bench.py` (decks), `sim/run.sh` (pinned iic-osic-tools image, ngspice 46), `sim/analyze.py`
(checks with limits fixed before the runs), results in `sim/results.json`.

Supply model: source ramp → feed 0.1 Ω / 2 nH → board 1 µF (20 mΩ, 1 nH) → bond 22.5 mΩ (0.1 Ω/8 + 0.1 Ω/10) and
loop inductance 2.2 nH (`package-channel.json` pdn, carrier at 30 mm; 1.0 nH with the strip capacitors) → die
1 nF with 0.5 Ω.

Built up in steps:

| Step | Content | Result |
|---|---|---|
| s0 | RLC only, 0.1 ns step | 107.30 MHz and 97.5 % overshoot, analytic 107.30 MHz / 97.5 %. A deck with the wrong C (2 nF) is rejected (75.9 MHz). |
| s1 | + extracted POR | release 39.9 ms (tt, 10 µs ramp); core_support README 34–55 ms, always-on audit 39.5 ms |
| s2 | + 5 extracted island switches, reset OR/AND and 6 flops from the 5 V std-cell library, an `iso_clamp` per island whose input floats high through 10 MΩ. RESET_N held high by the host; SCLK clocks ones into the flops for the first 20 ms. | table below |
| s4 | + `pt_core_bias` at its reset values + 8 `dvdd`, 10 `dvss`, 4 corner provider cells; aosc present but disabled | table below |

The switch pass arrays (660–1,760 identical fingers) are merged into one device with a multiplier; nothing
else is simplified.

| Run | POR release | Peak bond current | Island rail max | ISO / clamp / flops | Result |
|---|---|---|---|---|---|
| s2 tt/27, 10 µs to 3.3 V | 39.9 ms | 0.57 mA | 0.22 V | ISO = VDD, clamp 0 V, flops 0 V | pass |
| s2 tt/27, 1 ms to 3.3 V | 40.3 ms | 0.54 mA | 0.12 V | same | pass |
| s2 ff/85, 10 µs to 3.63 V | 37.2 ms | 0.77 mA | 0.33 V | same | pass except `vmax` (finding 11) |
| s2 ff/85, 1 ms to 3.63 V | 37.5 ms | 0.77 mA | 0.32 V | same | pass except `vmax` |
| s4 tt/27, 10 µs to 3.3 V (110 µs) | not reached | 0.60 mA | 0.22 V | same | pass |
| s4 ff/85, 10 µs to 3.63 V (110 µs) | not reached | 0.90 mA | 0.33 V | same | pass except `vmax` |

No island turned on in any of these, and nothing exceeded 1 mA through the bonds: the provider supply clamps
do not fire on a 10 µs ramp, and the die capacitance alone needs 0.33 mA at that slope.
The clamp-to-island interplay on a 1 µs edge (clamps and switches in one bench) did not finish: the full
bench ran at about 1 µs of simulated time per 15 minutes.

Must-fail cases, all detected:

| Case | Failing check |
|---|---|
| `isw_rf.EN` forced to VDD | island (RAIL_rf 3.30 V), iso, clamp |
| inverted ISO on the rf clamp | clamp (output 3.30 V) |
| POR stuck low, no override | rst (never released in 60 ms) |
| POR stuck low, `por_bypass` = 1 | rst passes: the override reaches the flops |

Other shapes:

| Run | Result |
|---|---|
| s2 ff/85, 1 s ramp to 3.63 V | `por_n` is already high when VDD reaches 1.0 V (0.275 s) and is never low above 1.5 V: no reset (my `por` check fails; known, PWR-02, always-on F9). Islands stay off (rails ≤ 0.12 V), ISO high, clamps 0 V. The flops woke at 0, but nothing forced them: in silicon their state is undefined without RESET_N. |
| s2 tt/27, power-down 3.3 V → 0 in 1 ms after release | pass. `por_n` falls with the rail, islands stay off, lowest node −0.11 V, bond current below 4 µA. |
| supply + provider cells only, 1 µs edge | fail (finding 1): 8.7–10.3 A, 5.7–6.4 V |
| supply + provider cells only, 10 µs edge, ff/85/3.63 V | pass: 0.2 mA, 3.630 V |

## 5. (c) Always-on current against a current-limited bring-up supply (G1)

The always-on audit already totals this (≈ 0.55 mA tt, ≈ 1 mA at ff/85/3.63 V). My assembled bench gives the
same block numbers independently and adds the parts it did not have.

| Part, ff/85 °C/3.63 V | Current | Source |
|---|---|---|
| core_bias at reset (bandgap 71 µA at tt does not switch off) | 131.9 µA (91.0 µA tt) | my s4 run with per-block ammeters; always-on audit F4 has 131.9 / 91.0 |
| POR | 4.2 µA | s4 |
| five island switches, off | 1.5 µA | s4 |
| provider supply cells (8 + 10 + 4 corners) | 1.8 µA | s4 |
| provider signal cells, about 57 | 0.15 µA (2.6 nA each) | `leak/ioleak.txt` |
| aosc (enable resets to 1) | 556 µA | always-on audit F2 |
| digital macro leakage | ≤ 82 µA | 5.6 µW post-route at tt/25/3.3 V × 48 (median library ratio at ff/125 °C/3.6 V; no 85 °C library, so this is an upper bound) |
| **Total** | **≈ 0.78 mA** | |
| + 14 host inputs floating at mid-rail | + 0.57 mA | finding 6 |
| + `aosc.EN` floating | up to + 1.8 mA | always-on audit F2 |

Worst case ≈ 2.6 mA, inside the 4.62 mA stopped-mode allocation. A 10 mA limit on the bring-up supply is safe for
the always-on set and would still expose a short. The ramp itself adds under 1 mA at 10 µs or slower; a 1 µs edge is finding 1.

## 6. Covered and not covered

Covered: POR release against ramp with the real reset gates and flops; default-off of all five switches;
switch ISO and clamp output during the ramp; back-drive and float paths as a netlist audit; pad states;
static always-on current; four transient and four audit negative controls.

Not covered:
- Brownout dips (to 2.0 V and 1.0 V), the ss/0/3.15 V ramps and the tt 1 s ramp: decks exist
  (`s2_tt_dip2`, `s2_tt_dip1`, `s2_ss0_*`, `s2_tt_r1s`) but were stopped when the box was throttled to two
  simulations. Block-level brownout results exist in the island_support and core_support READMEs.
- The 1 µs edge with the island switches and POR in the same bench as the provider clamps (above).
- Finding 1 rests on the PDK's CDL netlist of the provider cells (devices re-fingered to fit the model bins),
  a lumped supply and an ideal 0.1 Ω source. No extracted ring, no metal resistance in the clamp path.
- aosc running inside the combined bench (48 MHz makes the 80 ms run impractical); its start-up is in the
  always-on audit.
- Provider signal pads during the ramp (their level shifters before the rail is valid).
- The digital macro itself: 6 flops stand in for it; its rail capacitance and inrush are not in the bench.
- ISO release when an island is switched on (PDN-08), brownout with an island on.
- sf/fs corners.
- Everything on the unbound 23 % of the netlist (section 3.4).

## 7. Dependencies

- RTL read at 2026-11-13 ~20:50 UTC, with `por_bypass` already in `pt_digital_macro.sv`; `pt_chip.sv` still ties it
  to 0. A change of the strap polarity or of the reset expression needs `sim/pu_bench.py` (`Xor`/`Xand`) updated.
- The audit must be rerun on the chip-top owner's netlist (TOP rows) and on any binder change.
