# Chip-top integration notes (owner: chip-top integration, started 2026-11-13)

## 0. "Not on the chip" list for dispatch (user ruling 2026-11-13: only passives, FPGA and a fallback LNA may be off-chip)

Status: FINAL for dispatch (existence audit done 2026-11-13, read-only, file evidence below). None of the four is
absent as hardware; in every case the analog part exists and the digital half, bias, or binding is missing.
Class: (a) exists, uninstanced: instanced in `integration/top/pt_chip.conn`. (b) FPGA-side by a recorded
decision: the chip-side raw path must exist. (c) never built: build demand (TOP- rows in interface-changes.md).
`$P` = projects/programmable_transceiver_platform, IC = scratch/reviews/interface-changes.md.

### LO synthesizer (MW-7)
| Piece | Class | Owner | Evidence / interface |
|---|---|---|---|
| `pt_lc_qvco5` r6b | (a) instanced | timing/LO | GDS `$P/analog/timing/generated/lcvco/pt_lc_qvco5.gds` (11-12; gitignored), DRC 0; LVS only on the core, none on the top with spirals; no extracted netlist of the top (the top binds the schematic pin list `lcvco/qvco5.spice`) |
| `pt_lo_mmd`, `pt_lo_mmd_qdum`, `pt_lo_pfdcp`, `pt_lo_lf`, `pt_lo_obs` | (a) instanced | timing/LO | published GDS + ext netlists, DRC 0, LVS unique; repack of mmd/qdum/obs in flight (`scratch/lo-ap4`): published `lo_mmd` loads the I tank 100-170 fF more than Q |
| Digital control: N[5:0] (16..63, integer; fractional needs a sigma-delta), ICP[1:0], PRE, BAND[3:0] + band search, CMLSEL, enables, lock check | (c) | digital | no RTL anywhere (no MASH, band search, LO sequencer; only a Python model `lcvco/loop_design.py`); all six `rfpll.config.*` fields dropped from the bus. Ports: `c_qvco_*`, `c_lo_*` in `ctl_ports.txt`, frequency via `fc_src[5]` = `lo_mmd.FB` |
| Bias: `qvco.IBIAS`, `lo_pfdcp.IBIAS` | (c) | core_support | `lc_vco_reserved` EN tied low (`integration/core_bias.py:123-128`), no output for the PFD/CP. Demand D-BIAS |
| Quiet QVCO rail (LO20: <= 7 nV/rtHz) | (c) | timing/LO + pads | unconfirmed; the top puts QVCO on `RAIL_pll` with the rings (D-LO) |
| Closed loop with the extracted QVCO | (c) evidence | timing/LO | lock ladder uses a behavioural VCO; rung 4b passes 44.8 us vs 50 us at ss, published r5 filter fails narrowly at ss (50.6 / 52.0 us) |
| Reference | (a) | chip-top | 50 MHz on REF_IN (LO13): same pad as the external LO I leg; bound via clockmux PREF |
Earlier recorded position, superseded by the user ruling: IC:275 (LO3) "characterization vehicle, RF baseline stays B3".

### Wired TX 2.7-3.24 Gb/s (MW-24) (owner: wired TX/USB agent)
| Piece | Class | Evidence / interface |
|---|---|---|
| Published `pt_wiredtx` = all-CMOS quarter-rate `wtx_serq4c`, 4 phases, capped 2.5 Gb/s (WT21) | (a) instanced | bound per published pins |
| CML final 2:1 `wtx_cml2` | (c) not closed | cells DRC/LVS ok; extracted macro failed (34-54 errors / ~140 bits), stopped (`scratch/wired_tx/core/PROGRESS.md:60-68`) |
| Eighth-rate CMOS core `wtx_serq8` | (a)/(c) unpublished, untracked | `$P/analog/wired_tx/generated/fast/wtx_serq8.*` (11-13): DRC 0, LVS unique; extracted ss 3.24 Gb/s 0/161 errors, pessimistic ss 45 errors (fail). Needs 8 phase pins and modes M2/R4/R8: top pin list and D-PHRESTORE change when published |
| CML pre-driver `tx_cml_predriver` (wt24_tr7) + 0.6x pad switches | (c) | scratch only, review NO-GO as a closed fix; the published steering buffer swallows < 400 ps pulses (also blocks 2-2.5 Gb/s at the pad, WT24) |
| Ring BAND bit, 8 ring phase outputs | (c) | `c_pll_tx_band` port in the TOP rows; ring already has PH0..7 |
User decision on record: SESSION-STATE.md:69 "BOTH: retimed CMOS core <= 2.5 Gb/s plus one CML retry for 2.7-3.24".

### 100BASE-TX (MW-25)
| Piece | Class | Owner | Evidence / interface |
|---|---|---|---|
| `pt_vthdac`, slicer `vsel_*`, CTLE `lf_zero`, wiredtx `POST_POL` | (a) instanced/bound | chip-top | published, DRC 0, LVS unique |
| 4B5B, scrambler, NRZI/MLT-3, oversampling CDR, baseline-wander decisions | (b) | FPGA gateware | `$P/spec/interface-requirements.md:246` ("FPGA, none on chip"); fpga-offload-audit.md:105,147; IC IX-9..IX-13 |
| Chip-side raw path: fields for vthdac A/B/en, vsel, lf_zero, post_polarity, full-rate capture mode + psel; IX-11 fast threshold opcode; IX-12 edge-word lane | (c) | digital | none exists in RTL or the register map. Ports `c_vthdac_*`, `c_slicer_vsel_e*`, `c_ctle_lf_zero`, `c_wiredtx_post_pol`, `c_wrx_cap_b1/b2/psel`, input `wire_rx_edge[19:0]` |

### USB (MW-18) (owner: wired TX/USB agent + digital)
| Piece | Class | Evidence / interface |
|---|---|---|
| USB pad `pad_wirepad` on USB_DP/DN, `pt_wtx_hsbias`, `pt_detect`, termination/rxlevel/rxselect-direct | (a) instanced/bound | published; `hsbias.IBIAS` has no bias output (D-BIAS) |
| Protocol (packets, CRC, bit stuffing) | (b) FPGA | `$P/spec/contract.json:990` direct raw-byte stream; analog-architecture `direct_stream_service` |
| On-die: HS and FS/LS gate drive logic, direct-stream RTL, line state / SE0 / squelch / disconnect from the four detect outputs, chip ports USB_DP/DN | (c) | no USB RTL or driver logic anywhere; `pt_chip.sv` has no USB ports. Ports `c_usb_hs_p/n`, `c_usb_fs_high_p/n`, `c_usb_fs_low_p/n` (reset 0), inputs `s_detect_*` |
| HS receive route | (c)/decision | PD22 asked for a mux at the CTLE input or a separate receiver; the top uses the published rxselect direct path into the slicer (D-USB) |

### Other forgotten items found while building the top (all TOP- rows / `integration/top/decisions.md`)
| Item | Class | Owner |
|---|---|---|
| Converter clock cell `pt_convclk` (MW-3) | (c) | timing + converters |
| Ring-phase level restore into the serializer (MW-31) | (c) | wired TX + timing |
| REF_IN receiver instance `rx_ref` (MW-2) | (a) cell exists, now instanced, not in the floorplan | assembly |
| `pll_vreg2`, `ptrim`, `wrx_cap`, `cdr`, `pll_tx` | (a) instanced | chip-top |
| 153 isolation cells (132 `iso_clamp`, 16 `iso_clamp_x4`, 5 `iso_pd`) | (a) cells exist (x4/pd unpublished in scratch/iso-family), no instances in the floorplan | pads + assembly |
| Refpad VCM source, TX pad buffer REF/BIAS + DETECT_PBIAS, LNA downbond pads and tank spirals, POR_BYPASS strap pad | (c) | pads, rf_rx |
| Supply/clock monitor (`fault`, `monitor.config.*` 75 bits, ATB code 4) | (c) never built | coordinator to name an owner |
| Characterization structures `pt_char_*` (ATB 43-54, CLK_OBS 15) | (a) blocks exist, not in the floorplan | characterization + assembly |
| CDR control plane in the macro: FLL (FUP/FDN), phase picker (PSEL, SLIP), `pt_wrx_cdr_loop.sv` not instantiated (MW-10) | (c) | digital + wired RX |
| HS-pair signal detect, electrical idle, bit repetition (MW-35) | (c) | wired RX, wired TX, digital |

## 1. What exists (all under projects/programmable_transceiver_platform/integration/top/)

- `pt_chip.conn`: the one chip-level connectivity (hand-edited plain text). Every instance, every pin, named nets.
- `masters.txt`: where each block's published pin list is read from (or `inline` / `demand`).
- `ctl_ports.txt`: every control port the macro must present (width, reset, encoding, source field).
- `decisions.md`: build demands (A) and neighbour disagreements with proposed resolution and owner (B).
- `check_top.py` (+ `--selftest`, `--write`, `-v`), `run.sh` = the one regression command.
- `sim/tb_top_boundary.sv`, `sim/gen_defs.py`: stub-level SPI -> register -> analog-pin sim (iverilog), negative control.
- `generated/`: `pt_analog_top.spice` (structural), `pt_analog_top.sv` (black box), `pt_analog_top_stub.sv`, `tb_ctl.svh`, `tb_regs.svh`.

Not touched: `rtl/*`, `integration/pt_chip.sv` (digital has uncommitted edits there), `verification/chip_assembly/netlist.py`
(superseded as connectivity intent; left as is), `Makefile` (modified by another owner; use `integration/top/run.sh`).

## 2. Method notes

- Pin lists come from each block's published netlist (`generated/*.ext.spice` etc.), not from READMEs. Where the
  source is ahead of the published cell (wrx_cap r7, cdr r12 otr pins, rxmix without `hib`, new LNA) the top binds
  the PUBLISHED pins; the `unbound` check fails the day a cell is republished with different pins.
- Control boundary: one named macro port per cell control (decision: decode in the macro, map follows the cells).
- Owners' intent files used: `analog/timing/LO-INTEGRATION.md` (MW-1a/2a/7a), `analog/rf_rx/chip-top-pins.md` (RC-16r/s/t),
  `scratch/iso-family/publish/iso-placement.json`, `integration/wtx_fallback.py`, INT6 rows.
- Boundary sim finding: island fields read 0 at the pins while the island is off (regfile gating), so "reset value"
  in `ctl_ports.txt` means the value with the island on. The bench checks both.

## 3. Counts (see the final table at the end of this file)

| Count | Before (netlist.py binding of 2026-11-13, mode walk) | After (`integration/top/run.sh`, 2026-11-13) |
|---|---|---|
| instances / pins bound | 147 / 2892 | 346 / 3310 (340 inside the analog top; 863 analog-top port bits) |
| unbound ports | 653 | 0 |
| dangling nets | 1170 | 0 (146 intentional no-connects, each written `-` in the conn) |
| undriven / multiply driven nets | not checked (`ct_word_clk` x3, `island_on[0]` x2, `ref_clk`, `host_word_clk`, ... undriven) | 0 / 0 |
| v6 floorplan blocks with no instance | 14 | 0 |
| island crossings without iso cell or waiver | no iso cells at all | 0 (153 iso cells; 4 waivers with the gating rule stated) |
| always-on inputs floating or fed from an island | not checked (`aosc.EN`, two bias enables, ...) | 0 |
| supply-vs-island, clamp ISO index / domain | not checked | 0 / 0 |
| cfg: control pin groups with no field / wrong width / orphan fields (cfg_map.py) | 39 / 12 / 80 | every control pin is bound to a named macro port (214 ports, 522 bits; ctl=0). Against the register map: 143 ports still need work in digital (78 no field, 64 decode not in the macro, 1 width); 71 are direct fields that match |
| macro port diff (RTL vs top) | 4 PINMISSING at chip top | 276 (238 ports the macro lacks, 38 macro ports with no partner): rows TOP-1..4, TOP-10..18 |
| build demands / staged contracts | - | 9 demand instances (7 blocks) / 4 staged (converters) |
| regression exit status | - | FAIL until cfg, macro, demand, staged reach 0; everything owned by chip-top is 0 |

Boundary sim (`sim/tb_top_boundary.sv`, real `rtl/pt_digital_macro.sv` + generated stub): PASS. Checks reset
values at the pins, island gating, a direct 4-bit field (lna ctrim), an enable with and without its island (lna),
a one-hot select (ATB1 code 5: leaf, group, pad switch), an always-on live field (aosc), "no other control pin
moved" on each write, power-good read back over SPI, reset. Negative controls: unrelated write; mis-bound interim
bit (must FAIL: does); two LNA trim pins swapped in a copy of the conn (must FAIL: does). Limit: the macro has no
`c_*` ports yet, so 5 ports are exercised through an interim map in the bench (`PT_MACRO_HAS_CTL` removes it).

## 4. Independent review (2026-11-13, separate agent, given the artefacts and no conclusions)

Verdict at the time: not authoritative. Acted on:
- converters rebound to the owner's staged contract (single CLK, ACQ, no clock cell); `DONE` is not the sample valid;
- WTX fallback: request ORed into `c_txpad_req_main`; interlock RESET/QUALIFIED/SUPPLY_OK per the wired TX owner;
- ring phases straight to the serializer (owner's WT25/WT29), level-restore demand withdrawn;
- `clk_obs` tri-state output gets a pull-down in front of the always-on clamp;
- dead `SE` pins tied, decode notes fixed, checker extended (supply-vs-island, clamp ISO index and domain, staged
  masters, analog-crossing list, conn-mutation negative control, analog -> macro readback in the sim);
- new decisions for what cannot be bound: D-HF, D-EXTCLK, D-PHLOAD, D-PWR, D-ANA, D-TXREF, D-CDRCTL, D-100B, D-D2H, D-PADS.
Not re-reviewed after these edits. Known blind spots of the regression are section C of `decisions.md`.

## 5. State of "authoritative"

`pt_chip.conn` is complete (every pin of every published or staged block bound; nothing floating) and is the only
place connectivity intent should be edited. It is NOT yet proven right: direction markers and pin meanings are one
author's reading plus one review pass; the open D- rows (D-HF and D-EXTCLK in particular) mean two clocking modes do
not close even as bound; supplies are a single VDD/VSS. `pt_chip.sv` and `netlist.py` have not been switched over.
