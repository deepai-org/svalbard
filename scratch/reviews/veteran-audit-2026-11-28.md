# Veteran-reviewer audit, 2026-11-28 (read-only)

This audit was read-only: nothing was rerun, and no design file or register row was edited. Sources are the main tree (`P` = `projects/programmable_transceiver_platform`) and the floorplan tree `/home/ubuntu/svalbard-fp` (fp-plan-code). The freeze rule applied is MANDATE 8 as amended: a real deficiency is fixed before tapeout. Batches are TOP (chip conn and assembly), BLOCK (analog cell), MACRO (digital re-harden) and MODEL (simulation or analysis only).

## 1. SPI independence
| Point | State | Evidence | Class |
|---|---|---|---|
| SPI clock domain | pt_spi runs on SCLK only. The register file is clocked on ~SCLK and reset by rst_n. There is no PLL or core clock in the path. | `P/rtl/pt_spi.sv:66-87`, `P/rtl/pt_regfile.sv:5-7,5262-5268` | OK |
| With every PLL, the core clock and calibration stopped | Registers stay readable. Status is 2-flop synchronised to SCLK. INT-04 item 1 confirms this. | `scratch/reviews/int04-observability-2026-11-28.md` table row 1 | OK |
| Fixed ID / ABI / hash / chip id | 0x00 = 0x5356, 0x08, 0x09, 0xFE | `P/rtl/pt_regfile.sv:74,3109,3131` | OK |
| Scratch register | There is no dedicated one. Any full-width RW shadow field does the job, e.g. 0xE9 freq_count_a.target (16 bit), read back with VIEW=0. | `P/spec/register-map.md:68,412` | OK |
| Reset cause | 0x0D: POR flag, RESET_N flag, live strap and por_path bits | `P/rtl/pt_regfile.sv:1386-1391`, `register-map.md:73` | OK |
| Safe defaults | Every state resets to off/stopped and every clk_select to stopped. Outputs are island-gated. | `register-map.md:346-349`, `pt_regfile.sv:695` | OK |
| External bypass for the core (host) clock | **Missing.** `host_clk` accepts only internal_pll and host_follow; ref_in, aux_clk and wclk_in are rejected. HOST_CLK can therefore only come from a locked ring, so a dead ring means no host link. This is the CM-1 proposal, which was never built. | `register-map.md:349`, `P/analog/timing/README.md:480`, `scratch/reviews/interface-changes.md:1304` | **DEFICIENCY**: wire the two spare XMH inputs of pt_clockmux to H2D and REF (HS_H2D, HS_REF), plus a regfile decode/rule change. BLOCK + TOP + MACRO. |

## 2. Loop / calibration overrides
| Loop | Overrides present | Evidence | Class |
|---|---|---|---|
| LO PLL | `lo_preset` (PFD held in reset, VTUNE forced to VDD/2), `vco_coarse` manual band (16), `band_min/max`, `lo_icp`, `lo_n`. Band search is done by host software, so there is no on-chip calibration to freeze. Fail status: `vt_high` (live), `vt_runaway` (sticky W1C), fc 6 LO_FB count. | `register-map.md:256-257,479-487`; `P/analog/timing/README.md:354-356,386-392` | OK. The preset is one fixed voltage (VDD/2, not adjustable), and there is no lock bit (the fc 6 count is the proxy). |
| Ring PLLs | Per ring: `enable`, `modulus`, `band`, `lock_time`, `ready_select` (incl. override), `kp`, `line_pll`. pll_cdr can be put in HOLD through pt_cdr. There is no VCTRL voltage override (vco_replica characterises f(VCTRL) separately). | `register-map.md:567-575`, `P/analog/timing/README.md:166-175` | OK |
| CDR | `wrx.loop`: restart, freq_source incl. forced, fll_auto, manual FLL pulses (trig/dir/len), tolerance/loss. `wrx.picker`: auto/manual psel/slip, valid_mode forced. `cdr.ac3` loop_bw, otr. Phase trims p0..p7. State and flags at 0xF9/0xFA. | `register-map.md:277-279,534-544,599-625` | OK |
| Manual bias/gain/EQ/TX | ctle peak/lf_zero/bypass, wiredtx current/postcursor/polarity, lna agc/att/match, slicer vth, rfdriver gain | `register-map.md:438-440,529-533,545-556,576-579` | OK |

## 3. Serial test
| Point | State | Evidence | Class |
|---|---|---|---|
| Error count | 16-bit, saturating, Gray-coded at the source | `register-map.md:255`, `P/rtl/pt_pattern.sv:135-141` | OK |
| Sync status, sticky lock loss | `locked` (live), `lost_lock` (sticky) | `register-map.md:253-254` | OK |
| Bits-checked count | **Missing.** BER has to be inferred from host timing and the rate, and that is not tied to the time the checker was actually locked. | `register-map.md:253-255` | **DEFICIENCY** (small): a 32-bit saturating locked-word counter with snapshot, read through the same Gray/handshake. MACRO. |
| Loopbacks | External TX to RX by cable (bring-up W5), H2D digital loopback, converter DAC to ADC (rf). There is no internal near-end serial or pattern loopback. | `P/spec/observation.md:19,86`, `P/spec/bring-up.md:216,230` | **DEFICIENCY** (small): a digital pattern-generator-to-checker internal loopback mux, so the checker can be tested without the analog path. MACRO. An analog near-end loopback would be a new feature and is not proposed. |
| Independent TX/RX clocks | Yes. TX ring (ring_l) and CDR ring (ring_c) are separate, and `clk_select.wire_line` and `wire_sample` are separate selects, each able to take an external clock. | `register-map.md:346-347,567-575` | OK |

## 4. Quiet mode, enables, sticky events, observation mux
| Point | State | Evidence | Class |
|---|---|---|---|
| Per-block enables and quiet mode | Every block has an off/warm/active `state`. There is per-island power, and each clock domain can be set to `stopped`. Quiet mode is reached by stopping the domains; there is no single bit for it. | `register-map.md:336-349,433-440` | OK |
| Sticky events | lost_lock (pattern, fc a/b), vt_runaway, monitor cause and cause_clk, h2d ovf/unf, POR/RST, CONFIG_ERROR W1C | `register-map.md:66,73,253-291` | OK |
| Divided-clock / status mux | CLK_OBS: 18 sources with /2^0..7. DBG_OBS sel0/sel1 cover 55 signals. | `register-map.md:307,361-364` | OK |

## 5. Frequency counters
| Point | State | Evidence | Class |
|---|---|---|---|
| Reference independence | The counters use `ref_clk` = REF_IN (board). None of the 7 sources is ref_clk itself. The ring and LO sources are derived from REF by design, and aosc is independent. If REF is dead, `mon_ref_alive` shows it. | `P/rtl/pt_digital.sv:94-106`, `P/rtl/pt_freq_count.sv:3-6` | OK |
| Snapshot / overflow / CDC | Johnson + Gray counters, 2-flop sync. The window snapshot is held through the evaluation. Results saturate. SCLK readout uses a req/ack handshake from a held register. There is a formal check (pt_count_metrics). | `P/rtl/pt_freq_count.sv:9-31` | OK |

## 6. Supply overstress at the 3.50 V trim
Scope (user, via the coordinator): there is no lifetime requirement, only 22-32 °C. The trim is judged against prompt damage (breakdown, latch-up) and function, not the 3.63 V lifetime figure. The digital core uses 5 V-device cells (mcu7t5v0), so the 3.3 V thin-oxide limit applies only to the analog blocks.

- **The trim does raise the analog supply.** There is one supply source per die (B2), and the pad ring joins all 8 supply bonds into one net (`P/spec/board-requirements.md:19`, `P/analog/pads/README.md` packaging table "Supplies"). Every unregulated 3.3 V analog block therefore sees the trimmed rail. The rails behind `lo_vreg` and `pll_vreg2` see it only through their regulator.
- **Stack-up at the 3.50 V setpoint:**

| Contribution | Value |
|---|---|
| Setpoint +1 % tolerance (B2) | 3.535 V DC |
| DC IR budget | 117 mV, which only lowers the rail (ignored here, conservative) |
| Ripple at the analog taps, single-phase, pessimistic (`P/spec/power-delivery.md:588-604`) | 60-92 mV peak |
| Ripple at the macro (`power-delivery.md:450-470`) | 212 / 313 mV pk-pk, i.e. +106 / +157 mV peak |

- **Peaks this gives:** analog taps about 3.63 V; macro (5 V cells) up to about 3.69 V; clamp-edge transient 3.48-3.88 V for about 0.13 µs, and only on a fast ramp, which is forbidden by B52 (CLAMP.md).
- **Prompt damage:** 3.3 V gate-oxide breakdown and junction breakdown are several volts above this, and latch-up triggering needs injection well beyond a 0.1-0.3 V supply excursion. No node approaches either limit.
- **Function:** blocks are required to report trimmed results (MANDATE "Per-chip supply trim"). That is open per block (e.g. `P/analog/timing/README.md:486` item 13), and those items are already tracked.

**Verdict: OK for prompt damage at 3.50 V.** One stale-text item remains. MANDATE line 58 and B2 still say "setpoint + tolerance + ripple + overshoot ≤ 3.63 V", and the single-phase ripple breaks that line (the macro reaches about 3.69 V). The wording should be aligned with the user's ruling. This is a spec/MANDATE text fix for the coordinator, not a design change.

## 7. Supply clamp after a false trigger (PWR-12)
| Point | State | Evidence | Class |
|---|---|---|---|
| Mechanism | RC timer (360 kΩ, tau 1.1-2.1 µs) driving 3 inverters and the big NMOS. The bench reads no latch/feedback element from the netlist. A negative control without the timer cap does not fire, so the firing is the RC timer. | `scratch/reviews/pads-core/CLAMP.md:5-7,39-40` | — |
| Turn-off with a current-limited regulator | **No evidence.** All benches use an ideal or stiff source. "NOT shown: that a fired event is survivable." There is no current-limited-source or turn-off waveform. | `CLAMP.md:41-47` | **UNKNOWN**: run the stage-C ring with a current-limited source (0.5 / 1 / 2 A limit, the 8 × 1 µF COB caps), a 1 µs edge, and 50-100 µs of simulation. Show that clamp current returns to µA and the rail recovers without re-firing; recovery slew = I_lim/C, about 0.06-0.25 V/µs, below the 0.9 V/µs firing slew. MODEL. |

## 8. Bonding and circuit under pad
| Point | State | Evidence | Class |
|---|---|---|---|
| Bond type | Aluminium wedge, 0.8 mil, for run 1. Gold thermosonic is being trialled for later runs. | `P/spec/package-channel.md:27-29`, `scratch/reviews/wafer-space-answers.md:32,161` | — |
| Circuit under pad | **Not established.** The precheck runs `all,-antenna,-density,-cup`, so CUP is not checked. The shared protection macro alone gives 174 CUP.3 hits (refpad). That shows bond-pad metal structure is present there, but not whether active devices or poly sit under the openings. | `wafer-space-answers.md:232`, `scratch/reviews/interface-changes.md:356` | **UNKNOWN**: run a geometry AND of the PAD layer (37/0) with COMP/Poly2/active layers on the assembled GDS, for every custom pad family (refpad, rf_pair, txpad, wirepad, hspad, single_leg) and the provider cells. Also run the cup deck once. If anything sits under a wedge opening, that is a DEFICIENCY (BLOCK, pads). MODEL. |

## 9. Metal slotting
| Point | State | Evidence | Class |
|---|---|---|---|
| Deck coverage | `mslot.rb` is tagged `all`, so the precheck main deck runs MSLOT1-5.x. The latest pt_rf full-chip precheck (11-28) has 0 MSLOT hits; the only hits are 4 V4.1 and 2 V4.2a. | PDK `rule_decks/mslot.rb:129-135`; `scratch/integration/precheck-1128/rf/summary.txt` | OK (deck checks it) |
| 10.5 µm grid straps (22 µm max on pt_wired) | Below 30 µm | `svalbard-fp/.../assembly/strap_widths.json` | OK |
| Wide Metal5 bars / trunks | 3×3 µm holes on a 24 µm pitch where the bar is wider than 28 µm. This clears the deck's MSLOT.1 (the 15 µm open/close removes the area). | `kl_place.py:245-250`, `island_trunks.py:320-324` | OK |
| fp plates (plates-hook) | `_plates` draws **no holes**. Width alone is not the test: MSLOT.1 flags only metal wider than 30 µm in both directions. pl-rf `lo_txbuf.VSS` is a Metal5 plate 37.6 µm wide with 240 µm of length, so it will flag. isw_lod (39 × 16), wiredtx.VSS (52 × 8), isw_wired_cap (38 × 28 M4) and isw_wired_tx_a/b (35 × 12) stay under 30 µm in one dimension and pass. | `island_trunks.py:452-560` (no hole code), `scratch/integration/pl-rf/place.json` grid_plates | **DEFICIENCY**: apply the same hole pattern in `_plates` for Metal4 and Metal5, then confirm with a precheck on the fp tip. TOP. |

## 10. Loop-tap leakage in hold states
| Node | C | Hold/idle states | Drift at 0.3 nA | Class |
|---|---|---|---|---|
| LO VTUNE (`pt_lo_lf`) | C1 5.45 pF and C2 489.6 pF on CP, C3 8.84 pF on VT through 10 kΩ, about 504 pF total | Preset: driven to VDD/2, so no drift. Locked: the loop absorbs it; the static offset is 0.3 nA / 100 µA Icp, about 3e-6 of a cycle. There is no CP-off hold state. | ≤ 0.6 mV/ms if floating | OK (`P/analog/timing/lo_lf.spice:2-3`, README 354-356) |
| CDR_VCTRL (`pll_cdr`) | XC2A about 1 pF direct plus XC1 about 9 pF through 20 kΩ, about 10 pF (nmos cap, about 4.5-5 fF/µm²) | CDR mode: driven by the pt_cdr OTA, so the leak is absorbed. Idle data means zero votes; the RC node is inside pt_cdr and away from the tap. Line-PLL mode: the pump corrects it. Only cdr_en=0 with ring on and line_pll=0 leaves the filter floating (HOLD high, output open). | about 30 mV/ms, about 11 MHz/ms at about 380 MHz/V, in that one floating state only | OK. The floating state has no function. Whether a commit rule rejects it is not checked (UNKNOWN, minor). (`P/analog/timing/pll_ring.spice:60-66,113-117`, `P/analog/wired_rx/README.md:199-204`) |
| Taps | The LO VTUNE leaf is still unbound (INT-04 F1). The CDR_VCTRL leaf exists on pt_wired in fp only (`chip.conn:295`). It is absent on pt_rf. | | See the INT-04 fixes |

## 11. Hold timing
| Point | State | Evidence | Class |
|---|---|---|---|
| Uncertainty | `set_clock_uncertainty 0.25 [all_clocks]`, with no -setup/-hold flag, so it applies to hold as well | `P/integration/pt_digital_macro.sdc:344` | — |
| Repair margin | PL/GRT_RESIZER_HOLD_SLACK_MARGIN 0.3 ns | `P/verification/digital_hardening/config.json:113-114` | — |
| Result | The worst reg-to-reg hold slack is +0.020 / +0.027 ns at ffn40/3.60 V, on top of the 0.25 ns uncertainty, so about 0.27 ns of effective margin. Repair did not reach its 0.3 ns target. There is no OCV, the Liberty is self-characterised, and hold under ripple is +0.027 ns (DIG-07, PDN-02). The corner is colder and higher in voltage than the 22-32 °C window, so it bounds the trimmed case. | `P/spec/risk-register.md:24,69` | OK. The residual risk is already DIG-07; no new fix. |

## Ranked deficiencies
1. **No PLL-free host/core clock (CM-1).** A dead ring means no host link on either chip. Fix: pt_clockmux HS_H2D/HS_REF on the spare XMH inputs, plus the regfile decode/rule. Batches BLOCK + TOP + MACRO, in the same macro re-harden as items 3 and 4.
2. **Missing ATB leaves (INT-04 F1-F6).** LO VTUNE, regulator outputs, and CDR_VCTRL on pt_rf. TOP (rebinds already proposed and awaiting the coordinator); F7 needs MACRO.
3. **fp plates with no MSLOT holes.** pl-rf `lo_txbuf.VSS` Metal5 plate (37.6 × 240 µm) will fail MSLOT5.1. TOP (`island_trunks._plates`), then a precheck.
4. **No bits-checked counter in the PRBS checker.** MACRO.
5. **No internal pattern-generator-to-checker loopback.** MACRO.

UNKNOWN, to settle before freeze: the clamp turn-off with a current-limited source (MODEL); circuit under the wedge pad openings (MODEL geometry check plus the cup deck); a commit rule for the floating CDR filter state (minor). Text fix for the coordinator: the MANDATE line 58 / B2 "≤ 3.63 V incl. ripple" wording against the user's prompt-damage ruling.
