# Tapeout plan

One document for what must be true before the GDS is submitted and how far the
design is from it. Rules are in `scratch/reviews/MANDATE.md`; work status is in
`scratch/reviews/SESSION-STATE.md`; risks are in [risk-register.md](risk-register.md).

- **Target:** wafer.space GF180MCU Run 3, 1x1 slot, die 3.932 × 5.122 mm, chip-on-board
  ([package-channel.md](package-channel.md)). Precheck-clean GDS by **16 December 2026**.
- **Scope:** every capability, mode and rate, including the 2.7–3.24 Gb/s wired paths.
  Off-chip only passives, the FPGA and a fallback LNA.
- **Acceptance:** the die is worth fabricating if it is safe, diagnosable and gives a second
  route to every function. Per-capability performance is tracked in
  [performance-requirements.md](performance-requirements.md) and does not gate a block's freeze.
- **Machine-readable block state:** `tapeout-readiness.json`, checked by
  `make transceiver-tapeout-readiness` (currently `ready: false`).

## Operating envelope (user decision: narrow range accepted)

| Quantity | Performance window | Design-check points |
| --- | --- | --- |
| Junction temperature | 22–32 °C (board-controlled, [board-requirements.md](board-requirements.md) B2a) | 22 °C and 32 °C |
| Supply at the die | 3.15–3.35 V | 3.15 V and 3.35 V |
| Per-chip supply trim | Set per die at bring-up from its measured speed: typical dies 3.3 V, slow dies up to a 3.50 V setpoint, fast dies may be trimmed down. Setpoint + tolerance + ripple + overshoot ≤ 3.63 V | Slow-corner results are reported untrimmed and trimmed, with the minimum (at ff, maximum) passing supply; one trim value must satisfy every block in a mode |
| Process | All corners | tt, ss, ff, sf, fs, plus mismatch |

- **Function** is checked only inside the window (plus the nominal point tt, 27 °C, 3.3 V).
  Results at 0, 85 or 125 °C or at wide supply never gate.
- **Safety** holds outside it: supply ramps 0–3.63 V, brownout and repeated ramps, 0–85 °C.
  Nothing may be damaged, latch up, lock up or back-drive the host. Electromigration and IR
  drop are signed off at 85 °C.
- The trim does not excuse passive-limited specs, area, ff hold timing, reliability at
  3.5 V, ESD/clamp behaviour or the IR budget.

## The four tapeout tests

Every block passes all four before it is frozen. A block that misses is not dropped: it is
frozen in its safest state behind its island switch and recorded as `failed` with its
fallback active.

| Test | Meaning | Evidence |
| --- | --- | --- |
| **safe** | Off, unpowered, mis-programmed or broken, the block cannot damage, load, latch or lock up another block, the host interface or the bench. | Reset-default analysis and simulation with the block disabled, unpowered and stuck, including powered-peer and brownout cases at its pads. |
| **clean** | DRC and LVS pass on the GDS read back from disk; extracted simulation shows the function at the nominal point and the envelope check points. | KLayout and Magic DRC, Netgen LVS with device parameters compared and a failing negative control, extracted ngspice runs, all with source hashes matching the published GDS. |
| **observable** | Its state can be seen from the bench: SPI status, analog test bus, `CLK_OBS`, `DBG_OBS0/1` or a data tap. | Register or test-bus code plus a simulation of the observation. |
| **fallback** | Another route performs its function without sharing its likely failure. | A named route in `tapeout-readiness.json` with its control setting and pads. |

Core blocks have no fallback: they reuse silicon-proven or upstream designs, are sized
conservatively and accept reduced performance.

## Must-work core

| Function | Implementation |
| --- | --- |
| SPI and register file | Clocked by `SPI_SCLK` only (≤ 5 MHz, bring-up ≤ 1 MHz); works with every PLL and oscillator stopped. Reset values are the safe state. |
| Reset | `rst_n = RESET_N AND (POR OR strap OR keyed override)` (`rtl/pt_por_path.sv`). The third-party POR covers cold start and full power cycles only; a board supervisor on `RESET_N` covers slow ramps and brownout (B1). Two overrides rescue a die whose POR never releases: the `POR_BYPASS` strap pad (hard pull-down, jumper to supply) and a pad-free SPI key sequence (B49–B51). |
| Bias and references | Bandgap and bias generator from `gf180mcu_ocd_ip`, per-island bias banks (`pt_core_bias`), all overridable from the analog test bus. Bias resets off. |
| Supply | One external supply into the provider ring; ten switched islands that default off ([power-delivery.md](power-delivery.md)). |
| Pads and ESD | Provider cells for host, SPI, strap, observation and ATB pads; custom protected pad families for RF, clock, baseband, wired and USB pins (`analog/pads`). ESD tiers: 2 kV HBM on supplies, host link, debug/ATB, RF_RX, the HS RX pair and USB; 1 kV on RF_TX and WIRE_TX; CDM ≥ 250 V is a target. |
| Safe defaults | Master bias and all trunks off, every island off, every driver tristated, every termination and pull released, every test-bus switch open, every clock mux stopped. Island-to-macro signals are clamped by standard cells inside the digital macro. |

## Second routes

Route names are the keys of `tapeout-readiness.json:fallback_routes`.

| Function | Primary route | Fallback route |
| --- | --- | --- |
| RF LO | On-chip LC QVCO with integer-N loop (`qvco`, `lo_mmd`, `lo_pfdcp`, `lo_lf`) through `lo_ext` | External quadrature LO: I on `REF_IN`, Q on `AUX_CLK`, through `lo_ext` (`rf_lo_external_ref`) |
| RF RX front end | On-chip `lna` | LNA bypass with a board LNA (`rf_lna_bypass`) |
| RX baseband | `bbfilter_i/q` | Per-stage bypass (`rf_bb_stage_bypass`) |
| ADC | `adc_i/q` | Buffered baseband on `BB_I/BB_Q` to an external ADC (`rf_bb_external_adc`) |
| DAC | `dac_i/q` | External baseband into `BB_I/BB_Q` (`rf_tx_external_baseband`) |
| RF TX output | `rfdriver` | Low-power output to a board PA (`rf_tx_low_power_external_pa`), or baseband out to a board upconverter (`rf_tx_external_upconverter`) |
| Wired TX clock and serializer | Ring PLL and `wiredtx` | External serial data on `WTX_EXT` into the output stage (`wire_tx_external_data`); board serializer (`wire_tx_board_serializer`) |
| Wired RX clock recovery | `cdr` on the second ring | Forwarded clock on the `AUX_CLK` pair with raw words to the FPGA; FPGA oversampling at low rates (`wire_cdr_fpga_oversample`); board retimer (`wire_rx_board_retimer`) |
| Equalizer, termination | `ctle`, `termination` | CTLE bypass; board termination |
| Wired front-end observation | `slicer`, `detect` | Buffered monitor on `WMON` (`wire_wmon_scope`, `wire_detect_via_wmon`) |
| USB | `usb_txdrv`, wired RX path | Board USB PHY (`usb_board_phy`; required for low speed, B8) |
| Clocks | Ring PLLs, `clockmux` | Every clock domain can take `REF_IN` or `AUX_CLK` directly (`clk_stop_and_external`) |
| Bias and references | Internal | Force through the analog test bus |
| Any island | Shared supply | Its switch cuts it off |
| Host link | DDR at full rate | SDR and div2/div4 rates (`debug.host_link`) |

`tapeout-readiness.json` still names the deleted `WCLK_IN` pair in `wire_clk_wclk_in`,
`wire_cdr_external_clock`, `wire_rx_board_retimer` and `wire_rx_tmds_forwarded_clock`; the
forwarded wire clock uses the `AUX_CLK` pair (`integration/top/pt_chip.conn`).

## Debug and test pads

From `integration/top/pt_chip.conn` and `package-channel.json`.

| Edge | Pads | Use |
| --- | --- | --- |
| West | `BB_I_P/N`, `BB_Q_P/N` | Bidirectional analog baseband taps |
| West | `AUX_CLK_P/N` | Second clock input: external-LO Q phase, forwarded wire clock, independent sample clock |
| North | `ATB0`, `ATB1` | Analog test bus force and sense |
| North | `CLK_OBS`, `DBG_OBS0`, `DBG_OBS1` | Divided clock observation and digital status |
| East | `POR_BYPASS` | Reset strap |
| East | `WTX_EXT_P/N` | External serial data into the wired TX output stage |
| East | `WMON` | Buffered wired analog monitor |
| East | `TLP_TEST` | TLP/ESD test site |
| East | `bidir[17]` | Bonded spare |

Characterization structures (`analog/characterization`): device replicas and matching arrays
on the analog test bus, ring oscillators and a CML divider on `CLK_OBS`, RF FET with
open/short de-embedding. They are in the conn but not in the last floorplan.

## Before submission

Each line is a gate. "Gap" is the state today.

| Gate | Requirement | Gap |
| --- | --- | --- |
| Die fit | Every block placed inside 3.932 × 5.122 mm with routing channels, supply grid and decap | Does not fit: 0.03–0.18 mm² short if every repack target is met, 0.65–0.73 mm² short with cells as staged, after the area levers taken so far (`scratch/reviews/die-fit.md`). No floorplan newer than v6 |
| Connectivity | `pt_chip.conn` regression at zero; every instance bound to a published layout | 0 unbound pins; 12 instances unbuilt and 4 converters staged (`integration/top/check_top.py`: `demand=12 staged=4`) |
| Blocks | Four tests passed per block, at every in-window corner, against real neighbours | Open blocks listed in `SESSION-STATE.md` section 4 |
| Digital macro | Hardened; setup, hold with on-chip variation, 3.5 V and ff views closed; gate-level simulation; clamp cells intact | Not hardened on the current RTL; setup not closed |
| Chip-level analysis | Extracted critical nets resimulated per chain; substrate and supply coupling; supply drop and decap response ([power-delivery.md](power-delivery.md)); power-up, reset and isolation | Models exist; nothing run on a routed top |
| Top routing | Signal, supply and LO routing complete | Not started |
| Fill | Top-level fill run by us, with block-owned keep-out markers; density and DCF.1a clean; fill-aware re-extraction of the inductors and other sensitive blocks | No fill step in the flow; no block GDS carries a keep-out marker; stock fill lands in the QVCO spirals (`scratch/reviews/signoff-gap.md`) |
| Read-back LVS | Every published GDS and the top re-extracted from disk and matched, device parameters compared | Clean on 74 block GDS; the QVCO top cell has no netlist; no top-level LVS |
| Top-level DRC and antenna | KLayout and Magic clean on the filled top, antenna included | Not run on a routed top; `adc_i` has 7 antenna violations |
| Precheck | wafer.space precheck 1.7.4 with PDK `792ef67` passes in one work directory on the submitted file | Project flows use an older deck without DCF.1a; the live image is amd64-only and has not been run |
| Process options | Every layer used is in the wafer.space mask set | ESD implant layer 24/0, deep n-well and SAB devices unconfirmed |
| Evidence | A hash-matched evidence record for every published GDS | Staleness script exists (`scratch/reviews/pre-mortem/`); audit not run |
| Package and board | Bond map and per-pin channel fixed ([package-channel.md](package-channel.md)); board obligations complete ([board-requirements.md](board-requirements.md)) | B18 and B25 not met; carrier, gateware and bring-up software not started |
| Slot | A Run 3 slot is held | Open with the user |
| Submission package | Immutable GDS with checksums, bond map, bring-up board checklist, bring-up script | Not started |

## Bring-up order on silicon

1. Start every die at 3.3 V with no POR override. Measure supply current with `RESET_N`
   low, release reset, read the SPI ID and `RESET_STATUS`.
2. Walk the analog test bus: bias currents, references, supply monitors, device replicas.
   Read the ring monitors and set the supply trim.
3. Turn on each island alone and record its current.
4. Exercise fallback routes first, then primary routes.
5. Close each capability on whichever route works.
