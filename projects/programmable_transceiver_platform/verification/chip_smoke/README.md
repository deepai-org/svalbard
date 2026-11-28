# Chip power-up smoke test (pt_rf, pt_wired)

Why: top-level LVS by name missed macro `c_*` outputs that were never wired (KH-2), untied pad IE / OE / pulls (KH-1)
and a VDD / VSS short (KH-3). This test drives the chip only through its pads, on a bench that is wired **from the
top-level reference netlist** (the LVS reference that `gen_netlist.py` writes from the chip conn), so a missing or
misbound wire *in the conn / reference* makes it fail.

**Default mode validates the conn, not the layout.** A tie or wire that is right in the conn but floats or is cut in the GDS
(e.g. the POR_BYPASS pull-down on `pt_wired` fpw-8) passes the default mode. **`--layout` mode** wires the same bench from
the netlist extracted from the chip GDS (below), so it fails on such a tie.

    run.sh <rf|wired> [--tree DIR] [--netlist F]     test + negative control, exit 0 only if both hold
    smoke.py --chip <rf|wired> [...]                 the test alone; summary scratch/chip_smoke/<chip>/summary.json
    selftest.py --chip <rf|wired> [...]              negative control alone
    signoff_hook.sh <rf|wired> <ASM_RUN> <out>       hook for integration/signoff/signoff.sh (<out>/summary.json)
    run.sh <rf|wired> --layout <ASM_RUN> [--out D]   layout mode: test on the GDS-extracted netlist + layout negative control
    signoff_hook.sh <rf|wired> <ASM_RUN> <out> --layout     the same as a hook (summary mode=layout)
    layout.sh <rf|wired> <ASM_RUN> <work> [cut=i.p,..]      the extraction alone (KLayout, 1 cpu, ~4.5 min)

`--tree` picks the worktree whose conn, ctl_ports, provider_io, register map and gen_netlist are used (default: this
one). The netlist defaults to `KH_CONN=1 integration/signoff/lvs/gen_netlist.py` of that tree (the assembly's LVS
reference). The digital macro is the gate-level netlist `scratch/digital-macro-baseline/<chip>/pt_digital_macro.pnl.v`
(functional cell models of PDK 792ef67, iverilog). Both are untracked data taken from the main checkout (`ASM_DATA`
overrides, as in the signoff harness); their sha256 prefixes are in the summary. A test run takes about 2.5 min (rf) / 4 min (wired), one single-threaded process; run.sh adds the two negative-control runs.

## Bench (gen_bench.py)

- Every X line of the netlist's top subckt is one instance, every net one wire. Nothing is connected by hand.
- Digital macro: the real gate-level netlist; netlist bit pins regrouped into its buses; VDD / VSS (grid, not netlist
  pins) tied to the top VDD / VSS.
- Pad cells: `smoke_pads.v`, behavioural and strict: X / Z on any control pin (IE, OE, PU, PD, CS, SL, PDRV) or a rail
  pin off its level gives X on Y and PAD; pulls modelled (the provider `in_c` model ignores PU / PD).
- Analog blocks: one generated stub per master that only presents its pins; outputs (direction from the conn) drive 0,
  except island switch PG = EN & VDD & !VSS, iso clamp Y = A & !ISO, iso_pd, POR (releases only with its own
  vdd3v3 / vss / ena pins at their levels) and the clockmux HOST_CLK output (bench host clock).
- Expectations come from the conn, not the netlist: for each `c_*` bit of ctl_ports.txt its consumer pins; for each
  pad-cell pin whose net reaches the macro, the macro pin; each stub pin the conn binds to VDD / VSS.

## Sequence (smoke.py) and checks

1. Power up with RESET_N held low, POR release, RESET_N high. Every pad control pin 0/1 after power-up (`pad_tie`).
2. ID / chip id / map hash over SPI; all islands on (island power-good read back over SPI: switch EN -> PG -> macro);
   every consumed `c_*` port at its stub inputs = the documented reset of ctl_ports.txt (`reset_value`).
3. Field walk over SPI: every register field of the chip (except island power / pgood override) is written to a new
   legal value (commit rules satisfied automatically; a multi-bit field that reaches a port also gets every legal
   single-bit flip, so two swapped bits of one bus cannot both follow), committed, read back over the SPI_MISO pad, then restored.
   After every write: every consumer pin equals its macro port and is 0/1 (`ctl_wire`), pad pins equal their macro
   pins (`pad_wire`), rails at level (`rail`); ports that changed other than those documented for the field are
   reported (`side_effect`, warning: decode is checked by verification/decode_table). A second pass sweeps the fields
   of ports whose bits have not yet been seen at 0 and 1 at every consumer. Bias enable + 256 SCLK first (B54).
4. Host link: the RTL has no register read over the host link (bring-up register access is SPI only, spec/bring-up.md),
   so read-back is over SPI_MISO (step 3). The host link output path is checked by enabling D2H at the bring-up rate,
   running the host clock into the clockmux HOST_CLK output (through iso_host_clk) and starting the link: the D2H and
   D2H_CLK pads must be driven, equal the macro's d2h pins at every sample, and toggle (training quads).
5. Pads: POR_BYPASS open -> macro por_bypass 0 and RESET_STATUS strap bit 0; every input pad IE = 1, OE = 0; undriven
   SPI_CS_N reads 1, SPI_SCLK / SPI_MOSI / POR_BYPASS read 0 (pulls). Then a second RESET_N pulse must return every
   port to its first-reset value.

Faults (exit 1): structure, pad_tie, pad_ie, pad_oe, pad_pull, pad_wire, ctl_wire, rail, por, reset_pad, por_bypass,
spi_id, chip_id, island_pg, reset_value (stub != reset while the macro port has it), readback, d2h_*, host_link,
reset_again, island_rail. Warnings: map_hash, side_effect, direct_value, reset_value with the macro itself off the documented reset.

## Negative control (selftest.py)

Two runs on mutated copies of the netlist, each must fail naming exactly the broken wires: (A) one `c_*` consumer pin
unbound (`c_lna_ct[2]` on pt_rf, `c_ctle_peak[1]` on pt_wired) plus the IE pin of the SPI_MOSI input pad unbound;
(B) two bits of that trim bus swapped at the consumer (both still driven, only the register walk can see it).
`smoke.py --mutate` takes `c_port[bit]`, `pad:<PAD net>:<pin>` and `swap:<inst>:<pinA>:<pinB>`, comma-separated.

## Layout mode (layout.sh, layout_netlist.py)

`layout_netlist.py` extracts the top level of `<run>/chip/pt_chip_top.gds` exactly as `integration/signoff/lvs/top_lvs.py`
does (Metal1-5, Via1-4, MIM plate, labels; the run's flatten list; every direct child of the top cell a black box whose pins
are its labels) and writes a netlist with the reference's instance names, masters and pin order but **every net extracted**
(`L<id>`). From the reference it takes only names, pin order and which pad terminal is bonded to which package pin:
- package pin P = the bond terminal of its pad cell (PAD / PAD_P / PAD_N / ASIG5V; VDD = DVDD of every `gf180mcu_fd_io__dvdd`,
  VSS = DVSS of every `gf180mcu_fd_io__dvss`). The layout nets of those terminals are merged into P (bond wires / board); all
  other nets stay as extracted. So a ring or grid piece that reaches no supply pad is its own undriven net (Z in the bench).
- a reference pin no top-level metal touches gets its own floating net `NC_<inst>_<pin>`; a layout net on one pin only
  (a dangling stub) is `NC_L<id>`. The bench then sees Z there: `pad_tie` on a pad control pin, `ctl_wire` at a c_* consumer,
  `rail` at a block VDD / VSS pin.
- the digital macro gets its VDD / VSS grid pins (block labels) on their extracted nets, monitored as `rail` (the
  gate-level cell models ignore power, so this is what shows a macro on a dead grid piece).
- `<work>/layout.spice.json`: instances not in the layout (stand-ins such as `char_rffet*`), pins floating, pins split over
  several layout nets (the bench takes the port piece, else the first; listed), port shorts.

Negative control (`selftest.py --layout-cut`): the extraction is repeated with the metal erased at two pins in the in-memory
copy of the GDS (`cut=`: every top-level shape on the terminal's metal that touches the terminal, and every via landing on it):
the POR_BYPASS pad pull-down tie `io_bidir_16.PD`, one c_* trim consumer pin (`lna.ct2` / `ctle.ctle_peak2`) and one block
supply pin (`aosc.VSS`: a floating rail pin other than the named `pad_tlp` exception must still fail). The test on it must
FAIL naming every pin. The run dir is only read (mounted read-only).

Island rails (`island_rail`, both modes, structural): every pin the conn binds to an island rail (the VISL net of an `isw_*`
switch) must be on the netlist net of that rail's switch VISL pin; a floating or misrouted island-rail pin fails (e.g.
`wiredtx.VDD` off RAIL_wired_tx on pt_wired fpw-8 / fpw-11).

Named float exception (pt_wired only, coordinator 2026-11-27, as LVS by name and check_padsup): `pad_tlp` VDD / VSS (TLP test
site, reaches neither ring nor grid). A `rail` z there is listed in the summary (`float_exceptions`) instead of a fault, only
while the pin is isolated (an `NC_` net); joined to anything else, or X, it is a fault as before.

What layout mode sees: opens and floating pieces of top-level wires, ties and supply (pad ring, PDN, direct lands, island
bars) between black-box pins; a top-level short between two driven nets (X); a misbound top-level wire (pin on the wrong
net), all through the same functional checks as the default mode. What it cannot see: anything inside a black box (block
internals, the macro's own stripes: `place.log` "macro supply" check), shorts onto nets the stubs leave undriven (analog,
island rails: VISL is not driven by the switch stub, a floating island-rail pin is caught structurally by `island_rail` instead), resistance / IR drop / ESD, device-level LVS (`run_top_lvs_bb.sh`),
and a block pin split into several layout pieces beyond the one the bench takes (listed in the json).

## Limits

- The reference netlist comes from the conn, so it shows conn / KH_CONN binding faults, not layout opens or shorts.
  A layout-extracted netlist with the same instance and pin names can be passed with `--netlist`.
- Ports driven by clocked sequencers (CDR FUP / FDN, wired capture slips, USB, TX pad requests, wiredtx SER_EN) are
  checked for presence at every consumer (driven 0/1, equal to the macro) but are not toggled: the stubs give no
  clocks. The summary lists every port not seen at both 0 and 1 (`coverage.untoggled`).
- Stub outputs are constant 0 apart from the cases above: analog -> macro status paths other than island power-good,
  POR and the host clock are not exercised.
