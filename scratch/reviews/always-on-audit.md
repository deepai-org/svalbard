# Always-on infrastructure audit: core_bias, island switches/isolation, POR, aosc

Date 2026-11-13. Independent audit; no design file was changed. Work directory:
`scratch/reviews/always-on-audit/` (decks, logs, `results.json` per group).

Scope: the blocks on the un-switched core rail that have never been audited.
Question per block: can it leave die 1 dead or unobservable, and is each README/evidence claim supported?

Legend: **RERAN** = I simulated or re-checked it in this audit (pinned iic-osic-tools image, ngspice,
GF180MCU-D models, `ngbehavior=hsa`). **READ** = I only read the record.
Verdicts: supported / weak / unsupported / wrong.

## 1. Ranked findings

Ranked by dead-chip severity. No finding kills a correctly built die by itself; F1 is the only one where a
single defect leaves die 1 with nothing to debug, and its fix is not yet connected.

| # | Severity | Finding | Key numbers | Owner |
|---|---|---|---|---|
| F1 | **High** (dead die, no debug) | POR is still a single point of failure in the chip netlist. The new `por_bypass` is tied to constant 0 at chip level (`integration/pt_chip.sv:44`), no pad is bound. A POR that never releases still holds the die in reset. The dead state is real and close: a sink of 200–400 pA on the hold-off node `vcap` stops release for ever. | Never releases with: ≥ 200 pA (ss/85 °C/3.15 V), ≥ 300 pA (tt/27, ss/0), ≥ 400 pA (ff/85/3.63). 50 pA already stretches release 39.5 → 177 ms (tt). | digital + pads/assembly (pad for the strap); core_support (note) |
| F2 | **High** (undefined always-on block) | `aosc.EN` is **unbound** in the assembly netlist (`UNBOUND_aosc_EN`; `verification/chip_assembly/netlist.py` has no rule, `inventory.py:535` "aosc EN not yet controllable"). A floating CMOS input on the core rail. The register `core.aosc.enable` exists (`debug_cfg[246]`) and resets to **1**, while `analog/timing/README.md` says 0 is the reset state and the "safe" evidence was taken at EN = 0. | EN held at mid-level (floating-gate proxy): static 0.075–0.67 mA (tt), up to 1.79 mA (ff/85/3.63), and the oscillator does **not** run at EN = 1.4–1.65 V (CLK static). With EN = 1 at reset: 0.373 mA tt, 0.556 mA ff/85/3.63 from power-up, not "≤ 2 nA". | assembly (bind), timing (README/evidence), digital (confirm default) |
| F3 | Medium (block dead until SPI toggle) | aosc has a stable state with no kick: both timing capacitors charged, both latch outputs high. CLK sits at VDD, 12 pA supply, for ever. I could not reach it from a supply ramp, but nothing in the circuit leaves it except EN = 0. | Lock state confirmed (`.ic`, 2 µs, CLK = 3.300 V, X p-p 0.14 pV). Not reached in 29 start cases (6 EN steps; 4 EN = VDD ramps of 1 µs / 10 µs at tt, ss/0, ff/85; 1 gated EN; 17 dwell cases at 0.4–1.5 V; 1 brownout to 0.6 V). | timing |
| F4 | Medium (claim wrong; not a supply risk) | The imported bandgap draws **71 µA with `ena` = 0**. `bgap.ena` (reset 0) does not power it down. Reset-state core_bias current is 91 µA, not the "2.1 nA" + divider the README implies. No disabled-bandgap current is recorded anywhere. A faulty bandgap core cannot be switched off. | core_bias at reset: 91.0 µA tt/27/3.3; 131.9 µA ff/85/3.63; 83.7 µA ss/0/3.63. Split (tt): bandgap 71.0 µA, VCM divider ≈ 20 µA, biasgen 1.2 nA. | core_support |
| F5 | Medium (stress / wrong bias for µs) | `VBG` overshoots to the supply rail when the bandgap is enabled. The README says every enable step settles and reports only the settled tail. Harmless if the README order is followed (sources still on self-reference, trunks off); not enforced anywhere. | VBG peak 3.18 V (tt/3.3 V), 3.26 V (ff/22/3.35), 3.53 V (ff/85/3.63); above 1.3 V for 3.7 µs, settled to 1.212 V 10 µs after `ena`. VREF0 = 5/6·VBG follows (≈ 2.65 V on `refbuf.VREF0`). With `ref_sel_vbg` = 1 the 23 outputs would see ≈ 2.6× for a few µs. | core_support + digital (interlock or documented order) |
| F6 | Medium (provenance) | Tapeout sources of three always-on blocks exist only under gitignored `scratch/`: `isw_*` GDS and PEX (`scratch/island-support-20261108-075605/`), the routed `pt_core_bias` GDS (`scratch/core-bias-routing-20261110-compact/`), POR PEX. The island README's currency statement is wrong (3 source hashes differ). `aosc.gds` no longer matches the hash in its evidence. | Island: `design.py`, `layout.py`, `run.sh` differ from `source_sha256_at_summary` (diff since evidence is additive: iso family only; all 10 GDS/PEX hashes still match). aosc: GDS hash differs; I re-extracted the published GDS, it matches the recorded LVS netlist uniquely. | island_support, timing, assembly |
| F7 | Low–Medium (coverage) | Safety-corner evidence is schematic-only for the POR ramps and for the island-switch default-off / 3.63 V leakage / brownout cases; core_support has no sf/fs corners; aosc "safe" cases do not include its real reset state. | My extracted reruns agree: isw leakage identical to schematic (wired 0.4335 µA); POR extracted releases at 38.8 ms (ff/85/3.63), 41.7 ms (tt), 46.3 ms (ss/0/3.15); POR at sf/fs 34.2–50.9 ms; aosc at sf/fs 43.5–51.5 MHz. | core_support, island_support, timing |
| F8 | Low | Island switch, slow ramp with EN floating: the unloaded island reaches 0.34–0.35 V at ff/85 °C, above the README's "≤ 0.32 V" (which covers 1 µs and 100 µs ramps only). Ends at 0.5 mV, ISO high. | DC sweep (= slow ramp), extracted, 1 GΩ load: wired 0.351, rf 0.348, pll 0.349, debug 0.343, conv 0.340 V at ff/85; ≤ 0.10 V at ff/0, ≤ 0.07 V tt, ≤ 0.004 V ss/0. 1 ms ramp wired ff/85: 0.347 V. | island_support |
| F9 | Low (known, sharper) | On slow ramps the POR gives no usable reset even at tt: it releases at VDD = 1.03 V (tt/27, 1 s ramp), where the macro's 5 V-device cells are not yet functional; at ff it is never low once VDD ≥ 1.0 V. With `por_bypass` high RESET_N is the only reset. The board supervisor B1 is mandatory, not a backup. | 1 s ramp: tt/27 release at 1.03 V; ss/0 at 1.52–1.55 V; ff/0 and ff/85: `porb` = VDD at VDD = 1.0 V (no reset). Matches PWR-02. | board, digital |
| F10 | Low | Vendor behavioural model is wrong about `ena`: with `ena` = 0 the transistor-level POR still releases, and sooner (11.3 ms vs 39.5 ms, tt). `ena` is neither a failure point nor a usable "force reset". | `por/neg_ena0_tt_27_3.3_1ms` | core_support (note only) |
| F11 | Low (observability) | `aosc.ATB_X` is unbound (README lists it as the ATB tap). ATB code 4 `monitor_por_threshold` has a leaf whose NODE is unbound; it must stay off `vcap` (a sense leaf leaks 0.32 nA at 85 °C, which is above the F1 kill level). | binding from `scratch/chip-assembly-v4/run4/binding.json` and current `netlist.py` | assembly, digital (drop code 4 or bind it to a logic-level node) |
| — | Pass | Bias fault isolation (M7 / G4): no fault on one trunk or consumer moved any other trunk by more than 0.1 %. | See section 3.3. | — |
| — | Pass | Always-on current total (G1): ≈ 0.55 mA tt, ≈ 1 mA at ff/85/3.63 V (2.2 mA if aosc.EN floats), against a 4.62 mA stopped-mode allocation. Leakage is not a bring-up risk; a short is. | See section 6. | — |

## 2. POR (`gf180mcu_ocd_ip__por`, vendored, unmodified)

Evidence: `analog/core_support/evidence/core_support_evidence.json` (2026-11-10). All 34 source hashes match
the current files (RERAN); the three vendored manifests verify (RERAN).

| Claim (README) | Evidence | Verdict | Audit note |
|---|---|---|---|
| Clean reset on every 1 µs–10 ms ramp, release 34–55 ms | `#por.safety_ramps_3v63`, schematic | **supported** | RERAN 10 µs and 1 ms at tt/27, ff/85/3.63, ff/0/3.63, ss/0/3.15, ss/0/3.63: release 34.0–49.3 ms, `porb` low when VDD passes 1.0 V. Known answer reproduced (39.5 ms vs 38.6 ms reference). |
| 1 s ramps: release 1.05–1.55 V (tt, ss); ff never asserted | same | **supported** | RERAN: tt 1.03 V, ss 1.52–1.55 V, ff/0 and ff/85 not asserted. See F9: the tt case is not a usable reset either. |
| "safe: pass, with the plan's system conditions" | evidence outcome is `fail` (50/54) | **weak** | The pass depends on a board part that is not simulated and, until the strap is bonded, on a POR with no bypass (F1). |
| Extracted function window 13/13, +5.2..5.5 % delay | `#por.function_window_pex` | **supported** | RERAN extracted at tt (41.7 ms), ss/0/3.15 (46.3 ms), ff/85/3.63 (`porb` crosses VDD/2 at 38.8 ms, then ngspice aborts with "timestep too small" on that release edge, the solver fragility the README already notes; the run does not show the settled high level). |
| Safety sweeps extracted | none: "Safety sweeps use the POR schematic netlist" | **unsupported** (declared) | Two extracted safety points now exist in this audit; brownout/power-cycle stay schematic-only (READ). |
| Corners | tt/ss/ff only | **weak** | MANDATE keeps sf/fs. RERAN sf/fs × (0/3.15, 27/3.3, 85/3.63): 34.2–50.9 ms, clean. |
| Supply current 1.96–3.59 µA after release | `supply_current_a_min_max` | **supported** | RERAN 1.89 µA (ss/0/3.15) to 4.25 µA (ff/85/3.63). |
| DRC 0 (Magic, KLayout), LVS unique (hier + GDS flat) | `#clean.por` | **supported** | RERAN GDS-level LVS of the vendored GDS (flattened, vs vendored schematic + Avalon cells): "Circuits match uniquely", no property errors (`lvs/por/lvs_comp.out`). DRC READ (KLayout log: 0 violations, 2026-11-08; GDS unchanged since). |
| "No latch or oscillation in any case" | all POR sims | **supported** for what was simulated | No Monte Carlo. The trickle path uses 0.5/0.28 µm mirror devices, so the release time will spread widely; not quantified. |
| `rst_n = porb & RESET_N`, weak pull-down on RESET_N | RTL / `pt_chip.sv:91` comment | **supported** (READ) | Now `reset_n_pad & (por_n \| por_bypass)` in the working tree. |
| Observable: `por_event` sticky bit and live `porb` | `analog_status[4]`, `por_flag` (READ) | **weak** | State is `open` in the README; with the die held in reset neither is readable (that is F1). |
| Negative control | — | **added here** | The bench fails when the block is broken: 400–600 pA on `vcap` → `porb` stays 0 for 0.4 s at every corner. My first choice (`ena` = 0) did *not* fail: see F10. |

Dead-chip mechanisms looked for:

- **Hold-off node.** `vcap` carries only the drain of one PMOS (0.5/0.28), the 36 × 100 µm² MIM and two gates
  (checked in the layout netlist: the only diode in the cell is on `ena`). Junction leakage and photocurrent
  therefore pull `vcap` *up* (earlier release), and MIM dielectric leakage is orders below 50 pA. A sink of
  hundreds of pA needs a defect (MIM pinhole, contamination) or a wrongly attached tap. So the exposure is a
  defect-level one, but its consequence without the strap is a dead die. Reproduce:
  `./run.sh por 'leak_*'` then `python3 collect.py por`.

  | Corner | 50 pA | 100 pA | 200 pA | 300 pA | 400 pA | 600 pA |
  |---|---|---|---|---|---|---|
  | tt/27/3.3 | 177 ms | 217 ms | 315 ms | never | never | never |
  | ss/0/3.15 | 212 ms | 263 ms | 392 ms | never | never | never |
  | ss/85/3.15 | 227 ms | 284 ms | never | never | never | never |
  | ff/85/3.63 | 143 ms | 175 ms | 249 ms | 388 ms | never | never |

  ("never" = `porb` still 0 at 0.4 s with `vcap` falling.) The steep stretch at 50 pA shows the charging
  current near the trip point is far below the "0.4 nA" average the README quotes.
- **`ena` mis-tie.** Bound to VDD in the assembly (READ). Not fatal anyway (F10).
- **Short of the MIM / fill caps.** A shorted XC1 gives `vcap` = 0 = dead without the strap; the cell's
  `fillcap_4` decaps sit across the core rail like every other decap.

## 3. Bias block (`pt_core_bias`: bandgap + patched biasgen + root + banks + vref)

Netlist audited: the assembly's own `integration/core_bias.py` build (C-only extracted bandgap and biasgen,
extracted root/banks/vref, extracted AND gates), written to `always-on-audit/bias/pt_core_bias.spice`.
Consumers modelled as 4/2 µm NMOS diodes behind ammeters. All RERAN unless marked.

### 3.1 Claims

| Claim (README) | Evidence | Verdict | Audit note |
|---|---|---|---|
| Chain starts, `vbg` 1.207–1.219 V, outputs 7.6 (ss) – 12.1 (ff) µA, tt 9.5–9.7 | `#bandgap.chain_function_window` (schematic + extracted at tt only) | **supported** | RERAN extracted, README bring-up order: tt/27/3.3 9.49 µA, vbg 1.2120 V, ROOT_REF 0.915 V, TRK 1.998 V, VREF0 1.010 V; ff/22/3.35 11.88 µA, vbg 1.2079; ff/85/3.63 12.52 µA, vbg 1.2069 (safety corner, slightly above the 12.14 µA window figure). ss points: see 3.4. |
| "`ena = 0`: 2.1 nA total supply current" (biasgen); reset state is safe/off | `#biasgen.disabled` (tt/27 only) | **wrong as a statement about the block** | Biasgen alone: 1.2 nA (agrees). But the bandgap at `ena` = 0 draws 71.0 µA and the VCM divider ≈ 20 µA: 91 µA at reset (F4). |
| Bandgap `ena` = 0 → output high-impedance | `#bandgap.atb0_force_1v2` | **supported** | vbg = 0 at reset in every run; force current not re-measured. |
| "All enable steps were simulated abrupt with no oscillation"; "vbg settles < 25 µs" | `#bandgap.fine_step_probes` (tail p-p only) | **weak** | Settles (10 µs), but through a rail-high overshoot the criterion cannot see (F5). |
| Start-up on every 1 µs–1 s ramp, "no zero state" | `#bandgap.startup_safe_range` 28/28, `#biasgen.startup` 33/33 (schematic, enables tied high) | **supported** (RERAN 5 cases extracted, rest READ) | Because the bandgap core runs with `ena` = 0 (F4), start-up of the core happens on the supply ramp, which is the case those runs cover. Stuck-on ramp reruns: section 3.4. |
| Disabled output/trunk ≤ 47 pA; island rail off → no output current | `#distribution.disabled`, `#distribution.island_rail_off` | **supported** | Reset state: every output < 6 fA (tt) and < 6 fA (ff/85). RF rail at 0 V with everything enabled: RF outputs 0, others 9.49 µA. |
| ATB0 force of VBG / current into ROOT_REF / out of TRK as fallbacks | `#bandgap.atb0_force_1v2`, `#distribution.atb_force` | **weak** | Cell-level sims only (READ). In the chip the paths go through `atb_leaf_f` → `atb_grp` → `atb_pad` and need SPI. ROOT_REF shorted low is recoverable per island through TRK force (not re-simulated). |
| Evidence current | hash list | **supported** | All 34 hashes match; `biasgen_tapeout/SHA256SUMS` and `lvs_reference/SHA256SUMS` verify. The assembly uses the patched biasgen GDS and LEF (`verification/place_core_bias.py:147`), so the vendored `dvdd`-on-ground pin cannot reach the die (READ). |
| Extraction | C-only; Magic R+C segfaults | **weak** (declared) | No resistance anywhere in the master bias; trunk RC over ≈ 2–3 mm (v6: core_bias 2.2 mm from the macro) not simulated. |
| Corners | tt/ss/ff, PNP tied to MOS corner, no MC | **weak** (declared, MOD-17) | Not re-done here. |

### 3.2 Enable transient (F5)

`bias2/E_enable_step_tt.sp`: bandgap + biasgen at reset codes, `ena` of both stepped at 100 µs.

| t after `ena` | VBG |
|---|---|
| 2 µs | 0.000 V |
| 4.1 µs | crosses 1.3 V rising |
| 5 µs | 2.99 V (peak 3.18 V) |
| 7.8 µs | crosses 1.3 V falling |
| 10 µs | 1.2120 V |

The same peak appears in every full-chain sequence run (`vbg_pk` 3.21 / 3.26 / 3.53 V at tt / ff 3.35 V / ff 3.63 V).
Nodes that see it: biasgen `vbg` input, `pt_bias_vref` (VREF0 = 5/6 VBG → `refbuf.VREF0` gate), the VBG ATB
leaves. With the README order nothing downstream is enabled yet.

### 3.3 Fault injection (M7 / G4), tt/27/3.3 V, full chain enabled, 1 Ω shorts present from t = 0

Baseline: all 22 live outputs 9.49 µA. "Others" = every output outside the faulted trunk.

| Fault | Faulted trunk | Others | Core-rail current | Note |
|---|---|---|---|---|
| none | 9.49 µA | 9.49 µA | 145 µA | |
| `BIAS_lna` → VSS | lna 0 (into the short), rest of RF 9.49 | 9.49 | 145 µA | isolated |
| `BIAS_lna` → RF rail | lna diode 603 µA from its own rail, rest of RF 9.49 | 9.49 | 145 µA | isolated |
| `TRK_RF` → VSS | all 8 RF outputs **143 µA** (15×) | 9.49 | 145 µA | confined to the RF island |
| `TRK_RF` → core VDD | RF outputs 0 | 9.49 | 155 µA | confined; the short also forward-biases the bank diode into an unpowered RF rail |
| `TRK_RF` ↔ `TRK_CONV` | 9.49 | 9.49 | 145 µA | no effect |
| RF rail at 0 V, all enables high | 0 | 9.49 | 145 µA | no back-drive |
| `ROOT_REF` → VSS | — | **all 0** | 145 µA | single point; bypass = TRK force per island |
| `VREF0` → VSS | 9.49 | 9.49 | 153 µA | VBG unchanged (1.2120 V) |
| `VCM` → VSS | 9.49 | 9.49 | 165 µA | |
| `VBG` → VSS (negative control) | **all 0.25 µA** | — | 323 µA | bench fails as it must; bypass = none while shorted |

Result: no propagation between trunks. Single points that take all 23 outputs down: VBG, ROOT_REF, the
biasgen `idac2` leg. VBG and ROOT_REF have ATB force access; a hard short on either defeats the force.
Not done: opens, resistive (partial) shorts, the 23 real consumer inputs, refbuf → ADC, pll_vreg2 → rings.

### 3.4 Other reruns

Bring-up sequence at the slow corners (extracted, README order): ss/32/3.15 V 7.75 µA, vbg 1.2187 V; ss/0/3.15 V
(safety range only) 6.68 µA, vbg 1.2173 V. The README already says the coarse loop has no gain at ss/0 °C/3.15 V;
the chain still starts and no output is stuck. Core-rail current with everything enabled: 91–228 µA.

Stuck-on start-up (every enable follows VDD; not the reset state, a register-fault case), extracted full chain:

| Corner | Ramp | Outputs at the end | VBG end | VBG peak |
|---|---|---|---|---|
| tt/27/3.3 | 10 µs | 9.49 µA | 1.2120 V | 3.24 V |
| tt/27/3.3 | 1 ms | 9.49 µA | 1.2120 V | 2.24 V |
| tt/27/3.3 | 1 s | 9.49 µA | 1.2120 V | 1.26 V |
| ss/0/3.15 | 1 ms | 6.68 µA | 1.2173 V | 2.92 V |
| ff/85/3.63 | 1 s | 12.52 µA | 1.2069 V | 1.23 V |

All five start; there is no zero state. The VBG overshoot of F5 also appears on supply ramps up to at least
1 ms when the enables are already high.

Back-drive check (READ): `VCM` (1.65 V, always on, 40 kΩ) enters the unpowered conv island only on NMOS
source/drain with VSS bulk (`adc_i.spice:533-546`), so it cannot forward-bias a well. `VREF0` is 0 while the
bandgap is off.

## 4. Island switches and isolation (`isw_*`, `iso_clamp*`, `iso_pd`)

Evidence: `analog/island_support/evidence.json` (2026-11-08); extracted netlists
`scratch/island-support-20261108-075605/pex/` (all ten GDS and PEX hashes match the evidence: RERAN).

| Claim (README) | Evidence | Verdict | Audit note |
|---|---|---|---|
| Default off, EN floating, 0→3.63 V in 1 µs / 100 µs, 0/85 °C: VISL ≤ 0.32 V, ISO high | `island_switch.*.default_off` (schematic) | **weak** | True for those ramps. RERAN extracted: 10 µs ramps ≤ 0.27 V (wired ff/85), ISO high; slow ramp 0.34–0.35 V at ff/85 (F8). EN floats up to 0.27–0.43 V during fast ramps and returns to 0. |
| Off leakage ≤ 0.43 µA at 3.63 V, 0–85 °C | `off_leakage.safety_max_a_3v63_0to85c` (schematic) | **supported** | RERAN extracted, ff/85/3.63: wired 0.4335, pll 0.3326, rf 0.3104, debug 0.2168, conv 0.1626 µA. **Sum 1.46 µA**; tt/27/3.63 sum 22.6 nA. The current flows ring → pass device → island → ground. |
| "Evidence currency: `source_sha256_at_summary` matches every current source file" | — | **wrong** | `design.py`, `layout.py`, `run.sh` differ (F6). Harmless today: the diff adds the iso family only. |
| Reverse blocking ≤ 0.43 µA into the ring; back-drive fixture ≤ 0.27 µA | `reverse_blocking`, `integration_rf_tx_backdrive_iso` | supported (READ) | Not re-run. |
| Soft start, drop ≤ 20 mV full-RC | `soft_start`, `drop` | supported (READ) | Not a dead-chip item. ISL-01 margin 0.13 mV stands. |
| Physical: DRC 0, LVS match, cross-check | `physical`, `physical_crosscheck_librelane_image` | supported (READ) | Hashes re-verified; DRC/LVS not re-run. |
| Negative control | — | **added here** | EN tied to VDD brings the conv island to 3.63 V and ISO to 0 (`isw/neg_en1_conv_ff_85`), so the default-off check can fail. |
| ISO clamps follow `island_on`; reset → isolated | RTL `island_off = ~island_on` (READ) | supported | A deliberately inverted ISO was not simulated at chip level (M6 must-fail case still open). |

Dead-chip view: a switch that fails closed or leaks only powers an island whose blocks are all at reset; a
switch that fails open loses that island, not the die. There is no way to feed an island rail from outside
if its switch does not close (the rail ATB leaves are 16 kΩ sense leaves): a per-island single point,
accepted so far, worth stating in the risk register.

## 5. aosc (`pt_aosc` r3)

Evidence: `analog/timing/generated/aosc-evidence.json` (2026-11-10 02:19).

| Claim | Evidence | Verdict | Audit note |
|---|---|---|---|
| 47.7 MHz tt, 13/13 points in 40–60 MHz | `performance_vs_target` (extracted) | **supported** | RERAN extracted: 47.70 MHz tt/27/3.3 (evidence 47.70); 43.59 MHz ss/0/3.15; 52.86 MHz ff/85/3.63; sf/fs 43.5–51.5 MHz. Detector fails with EN = 0 (negative control). |
| "0 is the reset/safe state"; safe pass, EN = 0 < 2 nA | `tests.safe` ("reset-default controls (all 0)") | **wrong** | Register default is 1 (`spec/register-map.json` `core.aosc.enable.default`, `rtl/pt_regfile.sv:1577`, asserted at `:3473`). The block runs from power-up; the EN = 0 measurement (3.6 pA here) is not the reset state. `spec/tapeout-readiness.json` repeats the EN = 0 note. |
| "Gated by register" | `tapeout-readiness.json` | **unsupported** | EN is not connected to anything in the assembly (F2). |
| Evidence current | hashes | **weak** | `aosc.gds` and 4 shared flow scripts no longer match the recorded hashes. RERAN: published GDS re-extracted, matches `aosc.lvs.spice` uniquely (`lvs/aosc/comp.out`). KLayout DRC record is newer than the GDS (READ). |
| "Self-contained so it survives bias/reference faults" | design | **supported** | No bias input. But see F3. |
| Current 0.38 mA | evidence | **supported**, over budget | 0.373 mA tt, 0.556 mA ff/85/3.63, against the 0.22 mA `aosc` allocation in `analog-architecture.json`. |
| Observable: ATB_X, CLK → fc_src[4] | README | **weak** | CLK → `fc_src[4]` bound; ATB_X unbound (F11). |

Start-up with EN following VDD (the real reset state), extracted, RERAN:

| Case | Result |
|---|---|
| VDD 0 → V in 1 µs, 10 µs (tt); 10 µs (ss/0/3.15, ff/85/3.63) | oscillates at 47.70 / 43.58 / 52.86 MHz 1 µs after the ramp |
| EN low until VDD = 1.0 V, then follows (10 µs ramp, tt) | 47.70 MHz |
| Dwell 20 µs at 0.4…1.5 V, then to full supply (9 tt, 4 ss/0, 4 ff/85) | all 17 end at nominal frequency; tt starts oscillating from ≈ 0.7 V |
| Brownout 3.3 → 0.6 V for 10 µs → 3.3 V (schematic, tt) | recovers |
| `.ic` both capacitors high, Q = QB = 1 (schematic) | **stuck**: CLK = 3.300 V, no edges in 2 µs, 12 pA |

Not run: 100 µs, 1 ms and 1 s ramps with the oscillator live (48 M cycles per second of ramp; the dwell cases
stand in for them), and any mismatch between the two halves.

aosc is not on the die-1 critical path: its only consumer is `fc_src[4]` (frequency counter) and status bit
`aosc_div`. A dead aosc does not stop SPI. A floating EN (F2) is the item to fix before tapeout.

## 6. Always-on supply current at reset (G1)

| Item | tt/27/3.3 V | ff/85/3.63 V | Source |
|---|---|---|---|
| core_bias (bandgap 71 µA + VCM divider + nA) | 91.0 µA | 131.9 µA | RERAN |
| POR after release | 2.65 µA | 4.25 µA | RERAN |
| aosc, EN = 1 (register reset) | 373 µA | 556 µA | RERAN |
| aosc, EN floating (as assembled today) | 75–670 µA | up to 1.79 mA | RERAN |
| isw × 5, off | 0.02 µA | 1.46 µA | RERAN |
| Custom pad clamps (22 legs) + 3 refpad bias resistors | ≈ 80 µA | ≈ 130 µA (3.6 V) | READ (`pd37-clamp-leakage-dc.json`; instance count from `inventory.py`) |
| Digital macro leakage, 62,778 cells | ≈ 3 µA | ≈ 130 µA | ESTIMATE: mean per-state `leakage_power` of the 7T 5 V library × cell count (tt_025C_3v30: 0.157 nW; ff_125C_3v60: 7.3 nW). No leakage figure exists in `digital-hardening-evidence.json`. |
| ATB cells, iso clamps, decap tiles, provider pads | not recorded | not recorded | — |
| **Total** | **≈ 0.55 mA** | **≈ 0.95 mA** (≈ 2.2 mA with EN floating) | |

No bring-up supply limit is stated anywhere (`board-requirements.md`, `tapeout-plan.md`). The stopped-mode
allocation is 4.62 mA. Leakage therefore cannot trip a sensible limit; a proposed bring-up rule is: limit
20 mA, expect < 1.5 mA in reset with RESET_N low, treat > 3 mA as a fault before releasing reset.
What can kill the die on this rail is a short, and the exposure there is area: the digital macro, the decap
pool (≥ 3 nF demanded, none placed in v6) and the pad clamps. None of that is in these four blocks.

## 7. For the digital owner (POR override strap, DT-10) — to cover, not done here

1. `integration/pt_chip.sv:44` ties `por_bypass` to 0. Until a provider pad with a pull-down is bound, bonded
   (one of the 70 connected pads) and on the board as a strap, G3 is open in silicon.
2. Prove it at transistor level in the existing co-simulation (`verification/check_chip_power.py` uses an
   external reset at 2 µs, "not the real cold-start POR"): real POR with `vcap` held low (the audit's
   `por/por_leak.spice` with 600 pA does this) → SPI ID unreadable with the strap low, readable with it high.
3. With the strap high RESET_N is the only reset; slow ramps give no POR reset even at tt (F9). State B1 as
   mandatory and keep the weak RESET_N pull-down.
4. `core.aosc.enable` resets to 1; the analog documentation and evidence assume 0. Decide one, and make the
   assembly bind `aosc.EN` to `debug_cfg[246]` (F2). If 1 stays, the POR hold-off runs with a 48 MHz
   oscillator on (v6 places them 2.65 mm apart, which is fine; v4 had 12 µm).
5. Bandgap enable overshoot (F5): either an interlock in the register file (reject `bgap_ena` 0→1 while
   `ref_sel_vbg` = 1 or any `dist_en` = 1) or a bring-up rule with the README order.
6. ATB code 4 `monitor_por_threshold`: remove it or bind it to a logic-level node. Never to `vcap`.
7. `por_flag` must stay readable and must reflect the raw `por_n` with the strap high (already the intent).

## 8. Proposed fixes

| # | Fix | Owner |
|---|---|---|
| F1 | Bind `por_bypass` to a bonded provider pad with pull-down; add the co-sim must-fail/must-pass pair; add a risk row for the hold-off node tolerance (200 pA). | digital, pads, assembly |
| F2 | Add the `aosc.EN` binding rule (`core.aosc.enable`), fail the assembly on any unbound input of a core-rail instance; correct the timing README and re-take the "safe" evidence at EN = 1. Optionally add a weak pull-down on EN inside `pt_aosc`. | assembly, timing |
| F3 | Add a kick: detect DA = DB = 0 (both capacitors above threshold) and discharge both, or reset the latch from the AND of the two detectors. Otherwise document "toggle `core.aosc.enable`" as the recovery. | timing |
| F4 | Record the disabled-bandgap current in the evidence; correct the README and the 2.1 nA statement; decide whether a series switch on the bandgap supply is wanted (it would give a way to remove a faulty bandgap, at the cost of touching vendored IP: default is to leave it). | core_support |
| F5 | Add the VBG peak to the enable-step criterion; check `refbuf.VREF0` and the biasgen input for 3.63 V tolerance (gates only, expected fine); interlock or rule as in 7.5. | core_support, digital |
| F6 | Publish `isw_*`, `atb_*`, `iso_clamp` GDS/PEX/LVS and the routed `pt_core_bias` GDS under the project tree with hashes; regenerate the island summary so the currency line is true; refresh `aosc-evidence.json` hashes. | island_support, core_support, timing |
| F7 | Add extracted safety points (POR ramps, isw default-off and 3.63 V leakage) and sf/fs to the campaigns; decks exist in this work directory. | core_support, island_support |
| F8 | Add a slow ramp (or DC sweep) to the default-off criterion and restate the limit (0.35 V unloaded at ff/85). | island_support |
| F11 | Bind or drop `aosc.ATB_X`; resolve ATB code 4. | assembly, digital |

## 9. What I could not check

- No Monte Carlo / mismatch on any block (POR trickle mirrors, bandgap, aosc symmetry, bank mirrors).
- Bias: resistance extraction (tool segfault), trunk RC across the floorplan, real consumer inputs, opens
  and partial shorts, PNP corner independent of MOS corner.
- POR brownout, power-cycle and falling-rail cases: read only. POR coupled to a real PDN: not done.
- Island switches: reverse blocking, back-drive fixture, soft start, full-RC drop: read only. DRC/LVS of the
  island cells and of the bias distribution cells: not re-run (hashes verified). KLayout DRC not re-run on
  any block.
- aosc ramps slower than 10 µs with the oscillator live; fs/sf start-up from a ramp.
- The chip-level M6 transient (POR + bias + aosc + switches + pads on a lumped PDN) and the must-fail
  inverted-ISO case: not built. Latch-up of the vendored cells at power-up: not checkable with these tools.
- Leakage of the digital macro at the worst corner is an estimate from liberty data, not a sign-off number;
  ATB, iso-clamp, decap and provider-pad leakage have no record.
- The assembly binding I read is `scratch/chip-assembly-v4/run4/binding.json` (2026-11-10) plus the current
  `netlist.py`; v6 is outline-only and has no netlist.

## 10. Proposed risk-register rows (not written; the register is outside this audit's write scope)

| Proposed ID | Risk | Block | Status | Mitigation / owner |
|---|---|---|---|---|
| PWR-02 (update) | Add: strap `por_bypass` exists in RTL but is tied 0 at chip level; POR hold-off node tolerates only 200–400 pA; no usable POR reset on ≥ 1 s ramps even at tt | core_support, digital, pads | open | F1, F9 |
| AON-01 | `aosc.EN` unbound in the assembly; register default 1 vs analog documentation 0 | timing, assembly, digital | open | F2 |
| AON-02 | aosc lock state with no kick (not reached from 29 start cases) | timing | open | F3 |
| MOD-17 (update) | Bandgap not powered down by `ena` (71 µA); VBG rail-high overshoot at enable (3.2–3.5 V, 3.7 µs) | core_support, digital | open | F4, F5 |
| AON-03 | Tapeout sources of isw/atb/iso cells and routed core_bias only in gitignored scratch; stale currency statements | island_support, core_support, timing | open | F6 |
| ISL-04 | No external feed for an island whose switch fails open; slow-ramp VISL 0.35 V at ff/85 | island_support | open | F8, section 4 |

## 11. Reproduce

```
cd scratch/reviews/always-on-audit
python3 mk_core_bias.py                   # bias/pt_core_bias.spice, bias2/models.spice (not committed, 1.4 MB each)
python3 gen.py aosc por isw bias          # rewrites the gen.py decks (reads design files only)
./run.sh por  '{kn,neg,ramp,leak,pex}_*' 3
./run.sh isw  '{leak,dcfloat,neg,ramp}_*' 3
./run.sh aosc '{step,neg,lockic,ramp_ext_*_1e-0[56],rampgate_ext_tt*_1e-05,dwell,enfloat_dc,enmid}_*' 3
./run.sh bias '{reset,seq,fault,stuck}_*' 4
./run.sh bias2 '*' 2 ; ./run.sh skew '*' 2
python3 collect.py por isw aosc bias2 skew ; python3 bias_table.py
./dock.sh 'bash /work/lvs/aosc_lvs.sh' ; ./dock.sh 'bash /work/lvs/por_lvs.sh'
```

- Every deck that was run is committed as `<group>/<name>.sp`; the numbers quoted here are in
  `<group>/results.json`. ngspice logs are not committed (`*.log` is gitignored).
- The `aosc/dwell_*`, `aosc/enmid_*`, `aosc/enfloat_dc_*`, `bias2/*` and `skew/*` decks were written by one-off
  snippets, not by `gen.py`; rerun them from the committed `.sp` files.
- Only decks that were run are kept. `gen.py` also writes variants that were not run (slow on the shared box:
  aosc ramps of 100 µs and 1 ms, most brownout depths, isw 1 s transient ramps, a few extra bias faults and
  stuck-on corners); they have no entry in `results.json` and are not part of this audit.
- `por/por_leak.spice` is an audit copy of the vendored schematic netlist with one added current source on
  `vcap`. `bias/pt_core_bias.spice` sha256 `f928b562…38da2` at audit time.
