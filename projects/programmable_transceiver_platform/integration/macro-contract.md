# Digital macro boundary

The boundary of `rtl/pt_digital_macro.sv`, the one standard-cell macro of the chip, as committed. Every analog
control pin group is driven by one named, decoded macro port; `analog_cfg`, `debug_cfg` and the enable vector are
internal to the macro. The connection of each port is in `integration/top/pt_chip.conn`; widths, reset values and
encodings of the control ports are in `integration/top/ctl_ports.txt`; register fields are in
`spec/register-map.md`. The pad cells are not in the macro: they are provider `gf180mcu_fd_io` cells in the ring
(`integration/pt_provider_io.sv`), and the macro drives their `A` / `OE` / `SL` / `PDRV` pins and takes their `Y`
outputs.

## Contents

SPI and the generated register file, the control decode (`pt_ctl_decode`) and the control blocks for wired
transmit, wired receive and USB (`pt_wtx_ctl`, `pt_wrx_ctl`, `pt_usb`), the framed host transport with its two
storage banks (`spec/streaming-transport-v2.md`), capture and playback memory, the pattern generator and checker,
the optional 8b/10b line code, two frequency counters, the ADC core merge, the supply/clock monitor, the regulated
ring-supply sequencer, the reset path and the clocked half of the host link.

## Ports

### Reset, SPI, host link

| Port | Dir | Meaning |
|---|---|---|
| `reset_n_pad` | in | `RESET_N` pad |
| `por_n` | in | Power-on reset, low = reset |
| `por_bypass` | in | Level of the `POR_BYPASS` strap pad (pad pull-down); high = ignore the POR |
| `spi_sclk`, `spi_cs_n`, `spi_mosi` | in | SPI mode 0, command8 / address8 / data16 |
| `spi_miso`, `spi_miso_oe` | out | SPI data out and its pad enable |
| `host_word_clk` | in | Host DDR clock from the clock tree (156.25 MHz at 312.5 Mword/s), clamped outside the macro |
| `h2d_clk`, `h2d_pin[9:0]` | in | Forwarded H2D clock and data |
| `d2h_pin[9:0]`, `d2h_clk_pin`, `d2h_oe` | out | D2H data, forwarded clock and pad enable |
| `d2h_pdrv[1:0]`, `d2h_sl` | out | Drive strength and slew of the D2H pads |

Reset (`rtl/pt_por_path.sv`): `rst_n` = `RESET_N` AND (`por_n` OR `por_bypass` OR the keyed second path). The second
path needs no pad: a 16-bit key shifted in over `SPI_MOSI` / `SPI_SCLK` with `RESET_N` and `SPI_CS_N` low, then a
`RESET_N` rising edge with `SPI_SCLK` high; the idle SPI state clears it. `RESET_STATUS` shows the raw POR, the
strap and the armed second path. Until one reset has been seen after power-up, every island enable, ATB switch,
receiver enable and observation enable is forced to 0.

### Clocks

| Port | Dir | Source |
|---|---|---|
| `ref_clk` | in | `REF_IN` receiver on the always-on rail |
| `wire_rx_clk` | in | Capture word clock `WCLK40` (line rate / 40) |
| `wire_tx_clk` | in | Serializer word clock `WORD_CLK40` |
| `rf_rx_clk`, `rf_tx_clk` | in | Converter clock `CONV_CLK`; `rf_rx_clk` through an outside clamp shared with `CLK_OBS` |
| `ct_wclk` | in | Prescaled line clock |
| `fc_src[5:0]` | in | Frequency-counter sources: 0 TX ring feedback, 1 CDR ring feedback, 2 ring oscillator, 3 VCO replica, 4 always-on oscillator, 5 LO divider feedback |
| `ct_det_clk` | out | Clock of the signal detector, gated by the wired group |
| `rf_tx_clk_out` | out | Forwarded DAC capture clock, source-synchronous with `rf_tx_sample` |

Clock definitions and I/O constraints: `integration/pt_digital_macro.sdc`.

### Data

| Port | Dir | Meaning |
|---|---|---|
| `wire_rx_data[39:0]` | in | Received quad per `wire_rx_clk` edge; the earliest ten bits on the line in [9:0] |
| `wire_rx_edge[19:0]` | in | Edge-sample word of the capture |
| `wire_tx_data[39:0]` | out | Transmit quad per `wire_tx_clk` edge; forced to 0 while the wired group is off |
| `rf_rx_sample[23:0]`, `rf_rx_sample_b[23:0]` | in | ADC codes of core A and core B, I in [11:0], Q in [23:12] |
| `rf_rx_ph_i`, `rf_rx_ph_q` | in | ADC interleave phase outputs (core select) |
| `rf_tx_sample[23:0]` | out | DAC codes; forced to 0 while the converter group is off |

No analog block produces a valid or a request: the macro makes the wired and RF handshakes itself.

### Supply islands, isolation, fault

Ten supply islands are switched in five enable groups. `island_en`, `island_on` and `island_off` are six bits
wide: bit 0 wired (`wired_rx`, `wired_cap`, `wired_tx`), bit 1 rf (`rf_rx`, `rf_tx`, `lod`, `lo`), bit 2 pll,
bit 3 unused, bit 4 conv, bit 5 debug.

| Port | Dir | Meaning |
|---|---|---|
| `island_en[5:0]` | out | Switch enables |
| `island_on[5:0]`, `island_off[5:0]` | out | Group is on and good (or overridden) and its complement; `island_off` drives the isolation cells outside the macro |
| `s_pg_wired_rx`, `s_pg_wired_cap`, `s_pg_wired_tx`, `s_pg_rf_rx`, `s_pg_rf_tx`, `s_pg_lod`, `s_pg_lo`, `s_pg_pll`, `s_pg_conv`, `s_pg_debug` | in | Power-good of each switch; a group is good when all of its switches are |
| `wired_on_ext` | in | Request from the bring-up fallback control, ORed into `island_on[0]` |
| `fault` | in | External fault level, ORed with the internal monitor's fault |

Isolation of island-to-macro signals is inside the macro: 130 input bits from switched islands are ANDed with
`island_on` of their group on the first gate after the pin (`pt_iso_and`; list in
`integration/top/generated/macro_clamps.txt`). The hardening flow must not buffer those pins.

The fault comes from the macro's supply/clock monitor (`rtl/pt_monitor.sv`): reference and input clock activity,
the two lock indications from the frequency counters, and the island power-goods, on the always-on oscillator as
time base in the committed RTL. A fault forces the transmit paths off.

### Analog status

Raw asynchronous levels, synchronised inside the macro.

| Port | Meaning |
|---|---|
| `s_pll_tx_lock`, `s_pll_cdr_lock` | Ring PLL lock outputs |
| `s_ref_present`, `s_aux_present`, `s_wtx_ext_present` | Clock receiver activity |
| `s_refbuf_ready` | Converter reference buffer ready |
| `s_adc_{i,q}_ovl`, `s_adc_{i,q}_b_ovl`, `s_adc_{i,q}_done`, `s_adc_{i,q}_b_done` | ADC overload and conversion-done flags of both cores |
| `s_detect_diff_pos`, `s_detect_diff_neg`, `s_detect_se_p`, `s_detect_se_n` | Signal detector comparators (also the USB FS/LS receive data) |
| `s_wrx_slp`, `s_wrx_slm` | Capture `SLP` / `SLM` outputs |
| `s_wtx_ext_data` | Data from the external transmit fallback receiver |

### Test bus and observation

| Port | Dir | Meaning |
|---|---|---|
| `atb0_sw[57:0]`, `atb1_sw[57:0]` | out | One-hot leaf switches of the two analog test buses (bit k−1 = node code k) |
| `atb0_grp[1:0]`, `atb1_grp[4:0]`, `atb0_en`, `atb1_en` | out | Trunk group switches and pad switches |
| `rx_en_aux`, `rx_en_wtx_ext` | out | Enables of the `AUX_CLK` and `WTX_EXT` receivers |
| `rx_en_wclk` | out | Constant 0: the forwarded wire clock uses the `AUX_CLK` pair |
| `clk_obs_oe`, `dbg_obs0`, `dbg_obs0_oe`, `dbg_obs1`, `dbg_obs1_oe` | out | Observation pad data and enables |
| `wire_rx_ptrim_en` | out | Interlock that lets ring phases reach the slicer |

### Decoded control ports

216 output ports `c_*`, 531 bits, one per analog control pin group, with the net name used in `pt_chip.conn`.

| Group | Ports | Bits |
|---|---|---|
| Always-on (oscillator, bias generator, bandgap, bias distribution) | 19 | 53 |
| RF receive | 36 | 100 |
| Converters | 12 | 15 |
| RF transmit | 10 | 13 |
| LO | 14 | 23 |
| Clocks | 43 | 84 |
| Wired receive | 51 | 186 |
| Wired transmit | 18 | 41 |
| USB pad | 13 | 16 |

Rules:

- The register map follows the cells: a port is either the bits of one register field unchanged ("direct") or a
  decode the macro implements. The reset value is the cell's safe state.
- An enable is `(state == active) AND island_on` of the consumer's group. "Warm" keeps the configuration and
  leaves the cell off.
- Every port into a switched island reads 0 while that group is off.
- Ports are static (they change only while the consumer is stopped) except `c_cdr_fup`, `c_cdr_fdn`,
  `c_vthdac_a`, `c_wrx_cap_psel`, `c_wrx_cap_slipp`, `c_wrx_cap_slipm`, `c_usb_hs_drv`, `c_usb_tx_dp`,
  `c_usb_tx_dn` and `c_usb_tx_oe`.
- A ring whose regulator is out of bypass is held off for at least 50 µs after the pll island powers up or the
  regulator leaves bypass (`rtl/pt_vreg_seq.sv`).

## Checks

| Check | What it covers |
|---|---|
| `integration/top/run.sh` | Port list against the conn and `ctl_ports.txt`, boundary simulation of the real macro against the generated stub with two negative controls, isolation audit |
| `make transceiver-top-modes` | Generated `pt_chip.sv` is current, register map against cell pins, per-mode chip simulation, clamp list, decode table |
| `make transceiver-ctl-blocks` | Monitor, USB, wired control blocks, POR path, SPI chip-select race |
| `make transceiver-regfile` | Generator outputs are current, register file behaviour |
| `make transceiver-digital-hardening` | Synthesis, place and route, timing |

Open items at this boundary are in `integration/top/decisions.md` (D-FAULT, D-CAP, D-ATB, D-100B, D-TRIMISL).
The working tree may hold RTL edits that are not committed; this file describes the committed macro.
