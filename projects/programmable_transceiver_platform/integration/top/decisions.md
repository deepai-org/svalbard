# Chip top: open items

Open build demands and open decisions at the chip top. `pt_chip.conn` binds the unambiguous part of each and
quotes the D- tag in a comment; "Bound as" is what the conn does until the owner answers. Decided items are not
listed: they are in the conn, in `ctl_ports.txt` and in `../macro-contract.md`. Risks are in
`../../spec/risk-register.md`. Regression: `run.sh`.

## A. Build demands and bindings that lag the design

`demand` and `staged` masters in `masters.txt` keep the regression non-zero until they are replaced.

| ID | Open item | Owner | Needed |
|---|---|---|---|
| D-BIAS | `pt_bias_ext` (10 µA outputs for `qvco.IBIAS`, `lo_pfdcp.IBIAS`, `hsbias.IBIAS`, each with an enable) does not exist, and the conn places it on the wrong rails: an output must sit on the rail of its trunk diode | core_support, power delivery, chip-top | Bank outputs restated per island, then rebind |
| D-BIAS (b) | `pt_cdr.IBIAS` takes the spare `BIAS_pll_ring_host` output; the CDR ring takes `BIAS_pll_ring_rx`; `cdr.IB_PLL` is left open | wired RX, core_support | Confirm an open `IB_PLL` is safe, or move the ring to `IB_PLL` |
| D-REFVCM | `pt_refvcm` (common-mode source for `pad_ref.VCM` and `pad_aux_clk.VCM`, separate from the ADC `VCM_MASTER`) is still a `demand` master | chip-top | Bind the published cell |
| D-TXTERM | `pt_txpad_bias` is still a `demand` master and is bound without its `EN`, `EN_DET`, `IBIAS_DET` and `DETECT_PBIAS` pins. Pad `DETECT_PBIAS` is tied to the wired rail, so receiver detection through the TX pad is not available as bound | chip-top, pads, wired TX | Bind the published cell with all pins; state the detect bias source |
| D-LNA | LNA tank and degeneration spirals (`pt_lna_ind`, `pt_lna_deg`) are `demand` masters: no published cell, no LVS netlist | rf_rx | Publish the cells |
| D-AGND | The conn instantiates `pad_agnd_rx_{0:1}` as down-bond pads and binds `AGND_RX`. Down-bonds and extra bond openings are impossible under the fixed bond layout. The mixers' `VSS` is on `VSS` while the LNA is on `AGND_RX` | rf_rx, pads, power delivery | Re-plan the LNA ground on standard fingers; one ground rule for LNA and mixers; then rebind |
| D-LOVREG | `pt_lo_vreg` (quiet rail `VDD_LO` for the QVCO core and the charge pump) is a `demand` master. With the regulator enabled only in the on-chip LO mode, `VDD_LO` is 0 V in the external-LO modes while `lo_ext` biases the tank nodes: a forward path from the QVCO's PMOS wells into the dead rail is possible (netlist reading, not simulated) | LO | Publish the regulator; state the `VDD_LO` state per LO mode |
| D-POR | The strap pad (`pad_por_bypass`, east site `bidir[16]`, provider input pad with hard pull-down) is still a `demand` master `pad_strap` | chip-top | Bind the provider cell |
| D-FAULT | The macro derives the fault from its own supply/clock monitor. Its `fault` pin is tied to `VSS` and the monitor's supply-window inputs are constant 0: no analog supply window comparator exists. ATB code 4 has no node and is tied to `VSS` | coordinator, pads / core_support | Build the comparator or delete the pin and the supply-window fields |
| D-CONV | The four converters are `staged` masters: the conn follows the owner's staged pin contract (one CMOS `CLK`, `ACQ[1:0]`, `PH`), the published cells still have the old pins. The ADC clock crosses pll → conv through one `iso_clamp_x4` | converters | Publish the staged cells; accept the clamp inside the clock jitter budget or state a rule instead; `VCM_MASTER` under two ADC loads (CNV-06) |
| D-CHAR | Characterization cells are instanced but in no floorplan. `char_cmldiv.BIAS` has no ATB code. `ring_osc` and `pt_char_ro33` may be the same structure | characterization, assembly | Place them; answer the duplicate question |
| D-ISOCELL | `iso_clamp_x4` and `iso_pd` are used from `scratch/iso-family` | pads | Publish the cells |
| D-FLOOR | Instances the last floorplan (v6) lacks: `rx_ref_in`, `prescale_conv`, `prescale_hf`, five more `obs_pre4`, `lo_obs_q`, every isolation cell, the demand blocks, one more ATB0 fast leaf (code 58) | assembly | Place them in the next floorplan |
| D-POLY | `pt_polyphase` is deleted from the conn but still named in `check_top.py` and in `verification/chip_assembly/` (`inventory.py`, `netlist.py`, `floorplan_rules.py`) | chip-top, assembly | Remove it there |

## B. Open decisions

| ID | Question | Bound as | Owner | Needed |
|---|---|---|---|---|
| D-ISO | (1) CDR votes `UP/DN[3:0]` cross wired → pll through 8 clamps with pulses one ring cycle wide (1.2–2.5 ns). (2) The outside clamps follow the macro's `island_off[group]`; power delivery (PD2-2) asks for each switch's own `ISO` | 16 outside clamps and 2 pull-downs; macro `island_off` | pads, wired RX, power delivery | Bench clamp delay and pulse fidelity or make a fast clamp; choose the `ISO` source |
| D-CLK | Whether the host clock may come straight from `H2D_CLK` / `REF_IN` without a ring (CM-1: two more clockmux selects) | Three prescalers: `prescale` (line ring → `HOST_INT`, macro `ct_wclk`), `prescale_conv` (→ `CONV_INT`), `prescale_hf` (CDR ring → `HF`) | coordinator, timing | Yes or no |
| D-CLKSRC | Host and converter prescalers take `clockmux.WIRE`, so `HOST_INT` / `CONV_INT` run only when `debug.clk_select.wire_line` selects a source (reset = stopped) | `prescale.CK_IN` = `prescale_conv.CK_IN` = `WIRE_CK` | timing | Confirm, or take the TX ring phase directly |
| D-HF | Host-follow runs on the TX ring (`clockmux.config.ring_ref` = h2d) as the RF baseline | CDR ring → `prescale_hf` → `HF` remains bound as the second route | timing, converters | Confirm the clock plan numbers for 39.0625 / 40 MS/s |
| D-TXREF | TX ring reference | `pll_tx.REF` = `clockmux.PREF` (selects `ref_clk`, AUX or H2D) | timing, wired TX | Confirm |
| D-EXTCLK | External wire clocks (`clockmux.WIRE`, `WSMP`) reach only prescalers and observation. The serializer takes ring phases only, and the capture's external-clock fallback has no route into `CKP[7:0]` | Not bound | wired RX, wired TX, timing, coordinator | Build a phase/external selector in front of `ptrim` and `pt_wiredtx`, or declare those selects observation-only and remove the codes |
| D-AUXWCK | The forwarded wire clock shares the `AUX_CLK` pad pair: `clockmux.WCK` and `cdr.WCK_IN` take the clamped `rx_aux_clk` output; `clockmux.AUX` and `WCK` are one net; `clk_obs` source 7 is dead | As stated | timing, pads, digital | Receiver bench 25–810 MHz; check of the ~3.1 mm differential route; clamp bandwidth at 810 MHz; a register rule excluding external LO and forwarded clock together; the debug island must be on (40 mA rule) |
| D-PADS | Pad family of `AUX_CLK`; what `ATB_ESD_RAIL` pins should see | `pad_aux_clk` is a `refpad` with `VCM`; `ESD_RAIL` shared within `pad_bb_i/q` and within `pad_wtx_ext` / `pad_wmon`; `ATB_ESD_RAIL` open | pads | Confirm both |
| D-PHLOAD | Ring phases are unequally loaded (phase 0 carries one to three extra gate loads) and every ring output swings to the regulated supply (2.57–3.01 V high) into full-rail gates | TX ring `PH0/2/4/6` straight to the serializer, `PH1/3/5/7` dummy routes; CDR ring phases to `ptrim` | timing, wired TX, wired RX | A buffered tap with dummies or the skew it costs; state whether the reduced high level is acceptable |
| D-PTRIM | `ptrim` → slicer and capture clock load is 0.45–1.0 pF against 150 fF benched | Direct | wired RX | Buffer split in the cell; no connectivity change |
| D-WORDCLK | `wordclk_rx` taps `CKP[0]`, the most loaded phase | `wordclk_rx` on `wired_cap`, `LDE` straight to `wrx_cap.LDE` (`analog/wired_rx/PINS.md` section 2, `wordclk_rx`) | wired RX, timing | Tap `CDRPH[0]` instead, or move the word counter into the capture cell |
| D-CAP | The published capture is `pt_wrx_cap` r6 (`DX[39:0]`, `WCLK40`, `EW[19:0]`); the compact capture has one word strobe instead (`analog/wired_rx/PINS.md` section 5, item 1) | r6 pins; `DW` open | wired RX, digital | When a compact capture is published: strobe-domain front end and 20 → 40 gear in the macro, then rebind |
| D-TRIMISL | `cdr.phase_trim` and the word-divider controls are register fields of the pll island but drive cells on `wired_cap`; `wordclk_rx` is not in that island's current budget | Bound | digital, wired RX, power delivery | Move the fields' island; add the cell to the budget |
| D-LO | (1) Rail of `rx_aux_clk`: debug island here, always-on in `analog/timing/LO-INTEGRATION.md`. (2) QVCO and regulator ATB taps have no ATB codes. (3) No QVCO top-level LVS with spirals | Per `LO-INTEGRATION.md`; taps open | LO, assembly, digital | Decide the rail; assign codes; produce the LVS |
| D-USB | `pad_usb.TERM_ENABLE` has two claimed drivers: `pt_termination` (wired RX) and the USB field. The `CMD_MAIN` nets carry two loads (steering buffers and the USB pre-driver) | `TERM_ENABLE` / `DIFF_ENABLE` / `TERM_VCM` from `pt_termination` | wired RX, wired TX / USB | Agree the one driver |
| D-TMDS | The fallback request reaches the interlock `REQ_MAIN` through the macro decode (`c_txpad_req_main`); the fallback control cell's own request output is open. TMDS branch pins of the TX pad are tied off | As stated | wired TX, pads, bring-up | Keep, or add an OR cell on the wired rail so the fallback does not depend on the macro; remove the two unused steering buffers |
| D-WMON | Second leg and inject path of `bb_tap_wmon` are unused | `in_n` = `VSS`, `pad_n` open, `inj_*` open, `inj_en` = `VSS` | rf_rx | Confirm the ties are safe |
| D-ATB | (1) 13 trunk leaves (codes 14, 22, 29, 35, 56 on both buses; ATB1 2 and 3) are not gated by the island their node reaches (isolation audit K7); the coordinator's ruling (do not gate in RTL) conflicts with the pads proposal. (2) Codes whose node differs from its name in `debug-controls.json`: 15 is the LNA drain common mode, 18 is `bbfilter_i.atb_vcm`, 28 is `detect.atb_det_vref`, 32 is `REF_VCM`, 58 is on the debug island. (3) Codes 4, 25, 41 have no node | Dead codes tied to `VSS` | coordinator, digital, wired RX, timing | One decision on the leaves; rename or re-gate the fields; name a node for 25 |
| D-FC | `ring_osc` (165–255 MHz) feeds `fc_src[2]`, whose limit is 156.25 MHz | As is | timing, digital | Divide by two in the cell or relax the constraint |
| D-OBS | `clk_obs` island (cell header says core rail, inventory says debug); `clk_obs.source` codes the register file still forbids; `obs_pre4_pll` / `obs_pre4_cdr` duplicate the rings' `FBCK` | `clk_obs` on the debug island with a pull-down on its output in front of the core clamp; six `obs_pre4` | timing, digital, assembly | Confirm the island; lift the forbidden list; drop the two redundant prescalers |
| D-PWR | (1) `pad_usb`, `usb_txdrv`, `hsbias` are on `wired_tx` where power delivery lists RX pad blocks under `wired_rx`. (2) ATB supply-sense codes exist for six rails; `wired_cap`, `rf_tx`, `lod`, `lo` have none. (3) Which supply pad feeds which switch is not in the conn (one ring net) | Ten islands on five switch masters in five enable groups | power delivery, pads, assembly | Agree (1); add codes or accept; supply-pad table with the floorplan |
| D-ANA | Analog nets span two switched islands with no isolation: `DAC*_P/N` (conv → rf), `ADC*_P/N` (rf → conv), `BB*_OBS/INJ` (rf ↔ debug) | No isolation; the checker lists the 16 nets and does not fail | converters, rf_rx, rf_tx, pads | For each pair, the case "driver island on, receiver island off": a rule or an `iso_pd` |
| D-100B | 100BASE-TX raw path: analog side bound and control ports defined; the in-band threshold opcodes are decoded but rejected by the frame receiver (`../../spec/streaming-transport-v2.md`, Commands) | Ports bound | digital | Admit the opcodes; full-rate capture mode |
| D-D2H | The macro launches D2H DDR itself; the floorplan reserves an empty pad-edge gearbox | Macro pins straight to the host pads | digital, assembly | Drop the reservation or build the cell |

## C. What the regression does not see

`run.sh` checks completeness, self-consistency and what can be derived from names and device terminals.

- **Supplies:** only pins named `VDD`, `VDD_*_SW`, `vdd3v3`, `DVDD` and the ground pins are checked against the
  island. `VDDB`, `VIN`, `VISL`, bias-bank rail pins, `CASCODE` and spiral terminals are not. States inside one
  enable group (one switch failed, `VDD_LO` off, regulated ring supplies) are invisible.
- **Polarity and order** are derived from names. Not seen: single-ended polarity, UP/DN, D/E and MAIN/POST
  crossings, the macro side of the sample buses, a constant bus offset, a wrong field split.
- **Direction:** an output marker on a gate-only pin fails; an input marker on a diffusion-only pin is only listed;
  `~` pins and boxes without a netlist (demand cells, the macro, provider pads, inline masters) are not checked.
- **Control ports:** existence, width, reset, and that the island in the encoding matches the consumer's enable
  group. The decode itself is checked by the boundary and mode simulations only for the ports they exercise.
- **Isolation audit:** the macro-internal clamps and the off-state of `c_*` ports are requirements on the macro,
  shown to the audit as present.
- **Inline pin lists** other than `pt_core_bias` are not compared with a file.
