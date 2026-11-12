# Risk-accepted first-die tapeout plan

The first die keeps the full capability set: all 17 interfaces, RF and wired.
The project accepts that some or all signal chains may fail in silicon. The die
is still worth fabricating if it is **safe, diagnosable and gives several
routes to every function**. Each failure should produce data rather than a dead
chip.

`tapeout-readiness.json` owns the machine-readable state of every block against
the rules below. `verification/check_tapeout_readiness.py` validates it against
the block inventory in `analog-architecture.json` and the provider site
inventory in `contract.json`. Run it from the repository root with `make
transceiver-tapeout-readiness`.

This plan changes the **tapeout acceptance criterion**, not the design
targets. `mathematical-closure.json` still owns per-capability performance
gates, and they stay unresolved until silicon or extracted evidence closes
them. A block may be frozen for tapeout while its capability verdict is still
`unresolved`.

## Operating envelope (user decision: narrow range accepted)

The chip only has to work over a **narrow, controlled temperature and supply
range**. Broad commercial or industrial coverage is not a goal. Do not spend
area, current or design time on it. Optimize for this window:

| Quantity | Functional window | Design-check points |
| --- | --- | --- |
| Junction temperature | **27 °C ±5 °C** (22–32 °C), with board cooling or heating if needed | 22 °C and 32 °C |
| Board supply | **3.3 V ±1%** (3.267–3.333 V), one source | — |
| Rail at the die (after package and PDN drop) | **3.15–3.35 V** design window | 3.15 V and 3.35 V |
| Process | Not narrowed: tt, ss and ff corners and mismatch still apply | tt, ss, ff |

Two different ranges apply:

- **Function** (`clean` test and performance) is checked only inside the
  window above: tt/ss/ff × 22/32 °C × 3.15/3.35 V, plus the nominal point tt,
  27 °C, 3.3 V. Wider corners such as −40 °C/125 °C or 3.0/3.6 V are optional
  exploratory data. They never gate freeze.
- **Safety** (`safe` test) must hold well outside the window, because a
  bench mishap must not destroy the die: supply ramps from 0 V up to the
  3.63 V PDK DC limit, brownout and repeated ramps, 0–85 °C. Nothing may
  latch, overstress devices or back-drive the host when outside the window.
  Function is not required there.

The source decision is the [accepted operating envelope](../../docs/roadmap/programmable-transceiver-pin-plan.md#accepted-operating-envelope);
this section makes it concrete for design checks.

## The four tapeout tests

Every block must pass all four tests before it is frozen.

| Test | Meaning | Evidence that closes it |
| --- | --- | --- |
| **safe** | Off, unpowered, mis-programmed or internally broken, the block cannot damage, load, latch or lock up any other block, the host interface or the bench. | Reset-default analysis and simulation with the block disabled, unpowered and stuck. Includes powered-peer and brownout cases at its pads. |
| **clean** | DRC and LVS pass for the block layout. An extracted simulation shows its basic function at the nominal point and across the operating-envelope check points. | Magic/KLayout DRC report, Netgen LVS report and one extracted ngspice run, with source hashes. |
| **observable** | Its internal state can be seen from the bench through SPI status, the analog test bus, a clock observe output or a data tap. | Register map entry or test-bus mux code plus a simulation showing the observation. |
| **fallback** | At least one other route performs its function if it fails. The route must not share the block's likely failure mode. | A named route in `tapeout-readiness.json` with its control setting and pads. Off-die board routes count when the architecture already permits them. |

Core blocks are the exception to the fallback test. They are the
infrastructure through which all other blocks are measured, so they must work.
Their substitute for a fallback is that they **reuse silicon-proven or
upstream-extracted designs, use conservative sizing and accept reduced
performance**.

## Tier 1: the must-work core

The SPI control path, POR/reset, bias, the supply ring, pad ESD and safe
power-up defaults have to work, or nothing else can be measured.

| Function | Implementation decision |
| --- | --- |
| SPI control and register file | Clocked by `HOST_SCLK` only; works with every PLL and oscillator stopped. All analog settings come from one generated register file whose reset values are the safe state. No register write can enable two drivers on one pad. |
| POR / reset | Internal reset = `porb AND RESET_N`, asynchronous and reset-dominant. Edwards `gf180mcu_ocd_ip__por` covers **cold start and full power cycles only**. On 100 ms–1 s ramps it releases near 1.0–1.5 V or not at all, and it ignores dips that stay above 1.5 V. **A board reset-supervisor IC on `RESET_N` covers slow ramps and brownout** (board requirement B1). `RESET_N` has a weak on-chip pull-down. Sticky "POR occurred" and "reset occurred" bits and the live reset level are observable. |
| Bias and references | Edwards `gf180mcu_ocd_ip__bandgap` and `gf180mcu_ocd_ip__biasgen`. The biasgen carries two local patches: its top-level `dvdd` pin moved off the ground strap, and a 30 pF compensation capacitor on the bandgap-referenced loop. Five per-island trunks deliver 10 µA to each of 23 consumers, trimmed per die. The bandgap node, root reference and every trunk can be forced from the analog test bus, which is the qualified fallback for the core itself. Bias and trunks reset off. |
| Supply ring | Provider ring and fixed power/ground sites unchanged. One external supply. Every non-core island sits behind a local power switch that defaults off. DC drop budget: about 25 mV across bond wires (8 supply, 10 ground bonds at roughly 0.1 Ω each) at 250 mA, leaving about 100 mV for the on-die grid and island switches inside the 3.15–3.35 V window. The 2 Ω `package_r` in the reduced PDN model is an unmeasured AC damping value, not a DC resistance. **Superseded 2026-11-09:** the drop budget is now computed at the worst mode current by `spec/budgets/power_budget.py`; see [power-partition.md](power-partition.md#supply-drop-and-thermal-budget-envelope-2026-11-09). |
| Pad ESD | Provider/OCD primary clamp geometry on every custom signal pad, plus the **stress-safe** additions: a 3 × 12000 µm diode-NMOS shunt from the isolated protection rail to ground and a 100 kΩ clamp-gate discharge resistor. Worst ±100 mA / 2 ns pulse peak is 5.895 V against the 6.0 V gate screen. The cost is pad leakage near 3.3 V at the fast corner; the fallbacks below cover it. Digital and test-bus pads use provider cells. |
| Safe power-up defaults | Master bias and all bias trunks off (SPI, POR and the management oscillator need no bias). Every island off, every driver tristated, every termination and pull released, every test-bus switch open, every clock mux on its stopped input. Checked formally from the generated register file. |

## Tier 2: second routes for each risky block

| Function | Primary route | Fallback route |
| --- | --- | --- |
| RF synthesizer | On-chip LC VCO + polyphase into `lo_ext` internal mode (being evaluated) | **Passive external I/Q LO** (qualification baseline): board I on `REF_IN`, Q on `AUX_CLK`, AC-coupled straight onto the mixer gates through `lo_ext`. Lower bands: ring PH0/PH2 or external I/Q. |
| RF RX front end | On-chip `lna` | LNA bypass switch into the mixers, with an external board LNA. |
| Radio ADC | On-chip SAR `adc_i` / `adc_q` | Buffered I/Q baseband out on the `BB_I` / `BB_Q` debug pads to an external ADC. |
| RX baseband gain/filter | `bbfilter_i/q` (PGA first stage, shared with TX reconstruction) | Per-stage bypass. The external ADC path can also tap before the filter. |
| Radio TX DAC | On-chip `dac_i` / `dac_q` | External baseband injected through the same `BB_I` / `BB_Q` pads into the TX filter or mixer input. |
| RF TX output | On-chip `rfdriver` | Low-power mixer output through the same pad to an external board PA. |
| Wired TX serializer/PLL | `pll_ring` / `wiredtx` | External serial data injected on the `WTX_EXT` debug pair drives the output stage directly. |
| Wired CDR | Dual-loop CDR on a second `pll_ring` (half/quarter rate); 8× oversampling with digital phase pick (full rate) | Slicer samples on an external clock from the `WCLK_IN` debug pair, with raw words to the FPGA over D2H. |
| Equalizer / termination | `ctle` / `termination` | CTLE bypass; on-chip termination off with board resistors. |
| USB HS/FS | `slicer` and `detect` receivers, `wirepad` HS/FS drive | External board PHY (required for LS: board requirement B8). |
| Bias / references | Internal `bias` / `refbuf` | External force through the analog test bus. |
| Each island | Shared supply | Local power switch, so one failed island can be cut off. |
| Host GPIO link | DDR 10-bit at full rate | SDR and reduced-rate modes; SPI capture/playback memory as the last route. |

## Tier 3: debugging access

The 19 spare provider signal sites and area freed by consolidation are spent
on debugging access (`tapeout-readiness.json:reserve_area_mm2`). `tapeout-readiness.json:debug_sites` owns the
assignment. Each site still needs its own loading and isolation check before it
counts as qualified, because the pin plan says spare sites are not qualified
for sensitive nodes. When a debug pad is not selected, its attached switch must
present no more than the allocated disabled loading to the functional node it
taps.

| Edge | Sites | Use |
| --- | --- | --- |
| West (RF island) | `inputs[9]`–`inputs[6]` | `BB_I_P/N`, `BB_Q_P/N`: bidirectional analog baseband taps (RX out to an external ADC, TX in from an external DAC). |
| West | `inputs[3]`, `inputs[2]` | `AUX_CLK_P/N`: second differential clock input, independent of `REF_IN`. |
| North | `analog[0]`, `analog[1]` | `ATB0`, `ATB1`: analog test bus force/sense pair through the provider's analog pads. |
| North | `bidir[37]`–`bidir[39]` | `CLK_OBS`, `DBG_OBS0`, `DBG_OBS1`: divided clock observation and digital status mux. |
| East (wired island) | `bidir[16]`, `bidir[17]` | `WCLK_IN_P/N`: external sampling clock for the CDR fallback. |
| East | `bidir[18]`, `bidir[19]` | `WCLK_OBS`, `WDBG_OBS`: recovered/divided wired clock and wired status. |
| East | `bidir[22]`, `bidir[23]` | `WTX_EXT_P/N`: external serial data into the wired TX output stage. |
| East | `bidir[24]` | `WMON`: buffered, bandwidth-limited wired analog monitor. |
| East | `bidir[25]` (proposed, PD48b) | `TLP_DIODE`: minimal TLP site `pads/generated/tlp-site/pad_tlp_flat` (bond + one leg of primary steering diodes) replacing the dropped ESD_TEST (PD35); pending assembly acceptance. |

Characterization structures in the reserve area, all reached through the
analog test bus (the `ESD_TEST` pad was removed in PD35): NMOS/PMOS device replicas at the sizes used in
the LNA, mixer, sampler and driver; a ring-oscillator speed monitor; one VCO
replica with its own divider to `CLK_OBS`; and resistor and MIM-capacitor
matching arrays. The device replicas and matching pairs are `pt_char_atb` in
`analog/characterization` (ATB codes 43–54).

## Stretch goals (exploratory, never gating)

| Stretch goal | What is checked | Cost allowed |
| --- | --- | --- |
| **5 Gb/s serial (USB 3 Gen1 / PCIe Gen2 class)** | Quarter-rate at 5 Gb/s needs a 1.25 GHz ring, beyond the extracted ring's ~1.1 GHz. The check records how far the ring, slicer and 4:1 mux get. One extracted TX simulation at 5 Gb/s into the selected pad and a short channel records the eye. A best-effort RX simulation (CTLE and slicer) is recorded. | No extra area, current allocation, pins or schedule. A design choice is made for 5 Gb/s only when it costs nothing at the required rates. |
| **40 MHz RF channels (Wi-Fi HT40 class)** | Widest setting of the shared `bbfilter` bank against a 20 MHz baseband corner; ADC and DAC behavior at the matching sample rate; host D2H/H2D rate needed for that sample rate. Records how close each comes to double bandwidth. | Same rule: only free choices; record the shortfall otherwise. |
| **Lower-frequency RF** (also a stretch goal in `exclusive-engine-policy.md`) | LOs of roughly 1.2 GHz and 600 MHz from ring phases PH0/PH2 into `lo_ext` internal mode, or passive external I/Q. LNA, mixer and driver gain is recorded at those frequencies with board matching. | Same rule. No sub-GHz band is guaranteed. |

USB 3 itself would also need an external USB 2 PHY on the board, because the
chip has only two wired pairs. The 2.7 pF pad loading budget is the expected
limit at 5 Gb/s. A failing stretch result is recorded as data, not as a
block failure.

## Freeze order

1. **Control and digital.** Register file, SPI, reset logic, clock observation
   muxes and the digital transport. Gate: synthesis and formal safe-default
   check pass, then hardened with DRC/LVS.
2. **Pads.** Stress-safe protection on every site, including debug sites.
   Gate: per-family DRC/LVS and selected stress screen.
3. **Blocks.** Each block passes the four tests. Core blocks first, then the
   fallback routes, then the primary routes.
4. **Top-level assembly.** Full-chip floorplan, routing, full-chip DRC/LVS,
   density, antenna and package checks.
5. **Submission package.** Immutable GDS, checksums, bond map and bring-up
   plan.

A missed gate does not drop a block from the die. The block is frozen in its
safest state behind its island switch and recorded as `failed` with its
fallback active.

## Bring-up order on silicon

1. Supply current with `RESET_N` held low. Release reset and read the SPI ID.
2. Walk the analog test bus: bias currents, references, supply monitors and
   device replicas.
3. Turn on each island alone and record its supply current.
4. Exercise fallback routes first, because they depend on fewer on-chip
   blocks. Then exercise primary routes.
5. Close each capability using whichever route works.
