# Killer hunt: dead-die faults that pass DRC and name-based LVS (2026-11-26)

Independent review, analysis only (no design or assembly code changed). Looked for faults of the same class as PDS-25
(macro supply not on the grid; single 0.56 um hooks): a die that is dead or non-functional while DRC and
`top_lvs.py` by name pass.

Layouts: pt_rf `scratch/integration/assembly-rf/` (chip GDS 2026-11-26 03:47, LVS 04:02); pt_wired
`scratch/integration/assembly-wired/` (chip GDS 2026-11-26 00:11, LVS 00:29). Evidence comes from the routed DEF
(`route/routed.def`), the placer manifest (`place.json`), the LVS reference and result (`lvs/pt_chip_top.ref.spice`,
`lvs/chip/lvs.json`), and one KLayout probe on each chip GDS (`assembly-<chip>/kh_padpins.py`, output
`padpins_review.json`: the Metal1/Via1/Metal2/Via2 shapes from outside the pad cell that touch each provider-pad pin, using
the LEF pin rectangles).

## Why the checks miss these

`top_lvs.py` binds only the black-box instances it can place. Per `lvs.json` (`instances_in_ref_not_bound`), the
provider host pads (`host`), `debug_pads`, `pad_por_bypass`, `atb*_io` and every supply pad are not bound, and the
digital macro is not bound either (SO-4). The reference netlist (`gen_netlist.py`) and the assembly netlist
(`common.load` -> `check_top.parse`) both build the macro pin list from the conn alone, and the conn leaves out every
`c_*` port ("every c_* net is a macro output port of the same name ... not repeated here"). So any net whose only
driver is the macro or a provider pad is either a single-pin net in the reference, which matches itself, or a net
between two analog pins that matches the reference. Faults 1 and 2 below sit entirely in that blind spot.

## Ranked faults

### 1. Provider pad control pins are never tied, and the 12 host output pads are not connected at all (both chips): no host link, no SPI readback

- `pt_provider_io.sv` defines the pad settings: inputs IE=1, OE=0, PU/PD per strap; outputs OE/PDRV/SL from the macro, IE=0.
  Nothing in assembly draws these. On both chip GDS files, the probe finds **no** top-level metal on IE, OE, PU, PD, CS
  or A of any `bi_24t` input pad (SPI_SCLK/CS_N/MOSI, H2D[0:9], H2D_CLK, POR_BYPASS), and none on PU / PD of the
  RESET_N `in_c`. Only Y is wired. The bi_24t input buffer is gated by IE: with IE floating, `Y` is undefined, and
  with OE floating (A floating) the 24 mA driver can switch on against the FPGA. The SPI, H2D and H2D_CLK inputs do not
  reliably reach the macro.
- The 12 output sites (SPI_MISO, D2H[0:9], D2H_CLK; `selected_host_output` = `gf180mcu_fd_io__bi_t`, south side)
  have **no** connection on any core pin (A, OE, IE, PU, PD, CS, SL, PDRV). Cause: `kl_place.py` builds `iomap` only
  for pad cells listed in `masters.json`. `selected_host_output` is not listed, so `provider_pins` ends get dropped, and
  `spi_miso`, `spi_miso_oe`, `d2h_pin[0:9]`, `d2h_clk_pin`, `d2h_oe`, `d2h_pdrv[0:1]` and `d2h_sl` end up in
  `place.json` `single_pin_nets`. None of them appears in `routed.def`.
- The CLK_OBS / DBG_OBS0/1 pads have A and OE routed, but their IE, PU, PD, CS and PDRV pins float too.
- Effect: the chip cannot talk to the FPGA (MANDATE 1, "no dead chip comes first"). Same on pt_wired.
- Owner: chip assembly (tie-offs and output-pad binding in `kl_place.py` / `common.provider_pins`). Pads owner
  confirms the tie list per site. Signoff: bind the provider pads in LVS.

### 2. No `c_*` control output of the digital macro is connected (both chips): every analog enable, trim and select floats

- `check_top.parse` gives `digital` 396 pins and no `c_*` port. `common.load` passes the same instance list to
  `kl_place.py`. So no `c_*` net has a macro end. `routed.def` has **0** `( digital c_...` connections on both chips.
  pt_rf: 35 `c_*` nets are routed between analog pins only (for example `c_lna_en ( core_bias EN_lna ) ( lna en )`, which
  has no driver), and about 250 are single-pin and unrouted (`place.json` `single_pin_nets`: `c_aosc_en`, `c_rx_ref_en`,
  `c_biasgen_ena`, `c_bgap_ena`, `c_bgap_trim[*]`, `c_bias_dist_en_*`, `c_lo_*`, `c_qvco_*`, `c_clockmux_*`,
  `c_pll_*`, `c_cdr_*`, `c_clk_obs_*` and others). pt_wired: 9 routed without a driver and 400 single-pin.
  The macro LEF has the pins (`PIN c_adc_acq[0]` ...).
- Effect: the bandgap, bias generator and distribution enables, REF_IN receiver, clock mux, ring PLLs, LO, LNA,
  converters and debug clock outputs all have floating CMOS gates. There is no bias, no reference clock and no LO, and
  random enables can draw crowbar current. Only `island_en`, `island_on` / `island_off`, the `atb*` selects and the
  datapath pins are wired.
- LVS: the reference `Xdigital` line has 398 pins and no `c_*`, so `c_biasgen_ena` and the others are one-pin
  reference nets, and the 35 analog-to-analog nets "match".
- Owner: chip-top integration (`check_top.parse` or `common.load` must add the `ctl_ports.txt` ports to `digital`),
  then assembly reroute. Signoff: `gen_netlist.py` must use the same pin list. A check that fails on any macro LEF
  output pin with no net would have caught this.

### 3. The latest pt_rf layout has VDD shorted to VSS (LVS catches it, listed for completeness)

`assembly-rf/lvs/chip/lvs.json` (2026-11-26 04:02): VDD is "short+internal" with VSS. RAIL_lod is joined to the same
net (internal `isw_lod.?GATE`, `digital.?VDD/VSS`, `por`). RAIL_rf_tx is shorted to TXLO_QP (`lo_txbuf.OQP`,
`txmix_q.lo_p`). LVS fails, so this cannot slip through, but the current pt_rf GDS is a dead die. It is probably the
in-progress Metal5-strap / island-bar run (DG9-29, PDS-25). Owner: chip assembly.

### 4. POR_BYPASS strap has no pull-down in layout (both chips)

The conn says `pad_por_bypass` is a provider `in_c` with PD tied to VDD (pad pull-down, D-POR, analog/pads README
"PD hard-tied to VDD"). The layout places a `bi_24t` (bidir[16]) with only Y wired. PD, PU, IE and OE all float
(fault 1). On a board that leaves the strap open, `por_bypass` is undefined, so POR may be bypassed or the
input may never read low. Owner: chip assembly, with pads. The fix is part of the fault 1 tie list.

## Checked and found sound (as far as this review goes)

- Island-switch enables are default-safe: `island_en = island_en_reg & reset_seen` (rtl/pt_digital_macro.sv:323).
  `island_en[*]` and `island_off[2]` are routed from the macro to every switch / clamp, on both chips.
- POR: `por_n ( digital por_n ) ( por porb )` routed. `reset_n_pad` reaches the macro (in_c Y wired).
- `ref_clk`: the rx_ref_in OUTN reaches clockmux, the macro, lo_pfdcp and obs_pre4 (but its EN is a dead `c_*`, fault 2).
- Core bias analog outputs (`BIAS_*`) are bound in the conn and match by name. Their enables are fault 2.
- ATB pad SEL / leaf SEL come from the macro and are routed (78 `( digital atb...` ends on pt_rf).

Not covered (time): substrate / well ties of the RF blocks (not extracted by `top_lvs.py`, so the same class of risk:
the next check to do), and latch-up / back-powering of islands through clamps.

## Suggested gate

Add a flow-level check that fails when: (a) any macro LEF pin or provider-pad core pin has no top-level metal
(`kh_padpins.py` generalised); (b) `place.json` `single_pin_nets` holds anything other than bond-port nets; or
(c) `lvs.json` `instances_in_ref_not_bound` is not empty.
