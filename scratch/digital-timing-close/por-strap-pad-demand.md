# POR_BYPASS strap pad: demand to the pads owner (DT-10, D-POR, MW-26)

From: digital. Date: 2026-11-13. Status: demand, nothing built.

## What

One of the two in-ring sites released by the LNA redesign (LNA_SRC_P / LNA_SRC_N, RC-16t; the
source degeneration is on-chip now, `analog/rf_rx/chip-top-pins.md`) becomes the POR override strap
`POR_BYPASS` (`pad_por_bypass`, master `pad_strap` in `integration/top/pt_chip.conn`). Pick whichever
of the two is easier to bond to a package pin / board pad; the other stays released.

## Cell and pin ties

| item | value |
|---|---|
| cell | `gf180mcu_fd_io__in_c` (same proven binding as RESET_N). `in_s` (Schmitt) is acceptable if you prefer hysteresis; not `bi_t` / `bi_24t`, no output driver on this pad |
| `PAD` | chip pin `POR_BYPASS` |
| `Y` | macro input `por_bypass` (nothing else; see "never") |
| `PD` | hard tie to VDD_CORE (pull-down ON) |
| `PU` | hard tie to VSS_CORE (pull-up OFF) |
| `DVDD`, `VDD` | VDD_CORE (always-on core rail, same as `reset_pad`) |
| `DVSS`, `VSS` | VSS_CORE |

Ties are metal ties to the rails (or tieh/tiel cells on the always-on rail), never a register bit,
never a net of a switched island.

## Electrical

- Level meaning: 0 (default, unbonded, jumper open) = POR in the reset path. 1 = POR ignored,
  RESET_N alone resets the die.
- Unbonded / floating must read 0: show pull-down current against pad leakage at ff / 85 C /
  3.63 V (quote both numbers), and add this pad to the `kl_assemble` / `kl_checks` tie check that
  today covers only `rst_n_pad`. The provider Verilog model of `in_c` ignores PU/PD, so RTL
  simulation cannot show this.
- ESD: the 2 kV tier (supplies / host / debug class), provider cell as is, no series element removed.
  The site sits in the RF_RX part of the ring: the pad must still be on the VDD_CORE / VSS_CORE
  ring segment (or have its DVDD/VDD/DVSS/VSS strapped to it), not on RAIL_rf or any island rail,
  otherwise the strap reads garbage while that island is off.
- `Y` is static. Route to the macro south edge (`por_bypass`, next to `reset_n_pad` / `por_n`);
  `Y` max load 0.5 pF (Liberty), so one buffer on the always-on rail within ~200 um of the pad if
  the route is longer than ~2 mm. Keep it away from the LNA input and tank routing.
- Include a floating-strap case and a strap-high case in the M6 power-up transient.

## Bond / board

- Bond the pad to a package pin. Board: do-not-populate jumper (or DNP 1 kOhm) from the pin to
  VDD_CORE; nothing else on the net; no test point that a probe could short to a supply by accident.
- With the jumper fitted the die has no power-on reset: RESET_N must be low until the supply is
  valid (supervisor B1 mandatory, INT6-3). Needs an entry in `spec/board-requirements.md`.

## Never connect to this pad or its `Y` net

- any output driver, debug / observation mux, ATB switch or analog net (the previous shared-pad
  proposal was rejected for self-reset, silent POR removal and a loop through the pad);
- anything powered from a switched island or behind the POR;
- a register or any logic whose state depends on `rst_n`;
- a second load on `Y` other than the macro pin (and its one repeater).

## Open

- Which of the two sites (pads + package/bond owner).
- A second, pad-free override exists in RTL (`rtl/pt_por_path.sv`, SPI pin level sampled at the
  RESET_N release); it does not replace this pad.
