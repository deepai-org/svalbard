# Path to tapeout

This is the recommended route from the current state to a submitted die. The
rules are in [`tapeout-plan.md`](tapeout-plan.md), the per-block state is in
[`tapeout-readiness.json`](tapeout-readiness.json), and open issues are in
[`risk-priorities.md`](risk-priorities.md#open-issue-register).

## Where things stand

- The must-work core is done at block level: POR, bias chain, island
  switches, analog test bus, pad protection, register file and safe reset
  defaults. Only the host I/O pad hookup remains, and it is checked at assembly.
- Every fabricated block except the wired CDR has DRC/LVS-clean layout and an
  extracted simulation of its basic function. Many blocks miss their
  performance targets. Each miss is recorded and has a fallback route.
- The digital macro is hardened and clean but does not meet its clock targets,
  and it is larger than its allocation.
- Observability is designed (test bus, status registers, frequency counters)
  but not wired to the blocks.
- No top-level floorplan, full-chip netlist, full-chip DRC/LVS or submission
  package exists yet.

## Recommended order

### 1. Close the blocking functional gaps

These decide whether a function works at all on the first die.

1. **Wired CDR.** Add a `HOLD` input to `pll_ring` so phase-loop handover does
   not step the frequency. Make the phase detector use all four edge samples at
   quarter rate. Build the fast RX capture block in compact cells. Then debug
   extracted tracking.
   - **Also prove the external-clock fallback** (`WCLK_IN` → slicer → capture
     → raw words) on extracted netlists. That gives wired RX a working route
     even if the on-chip CDR does not close.
2. **Wired TX quarter rate.** Port the 4:1 mux, retiming flops and window
   drivers to the compact fast cells in `analog/timing`. This fixed the same
   3× slowdown in the timing blocks.
3. **Slicer at the ss corner.** Rebuild the samplers in compact cells so the
   480–810 MHz ring plan holds at every corner.

### 2. Decide the digital operating point

The hardened macro reaches 53–72 MHz on its fast clocks at tt, against
125–156 MHz targets. Pick one of two options:

- **Pipeline** the FIFO read muxes, stream framer and register commit path,
  then re-harden.
- **Document a reduced-rate first die:** the host link in SDR or reduced-rate
  mode, and wired data limited to what about 54 MHz × 20 bits carries
  (about 1 Gb/s).

The second option is consistent with the risk-accepted plan and costs no new
design. Either way, shrink the macro toward its 2.5 mm² allocation, or move
area from the reserve and record the move.

### 3. Wire observability (closes the observable test for about 40 blocks)

1. Place `atb_tap` leaves at each block's `atb_*` ports and at the bias-bank
   outputs, following the grouping in `spec/debug-controls.json`.
2. Connect every block's status bits and clocks to the register file,
   `CLK_OBS` and the debug status muxes.
3. Add one simulation per island showing a tap and a status read.
4. Mark observable in `tapeout-readiness.json`.

### 4. Finish the small open items

- Design the device-replica and resistor/MIM matching arrays: small cells
  reached through the test bus.
- Add the `usb_hs_bias` register field (8-bit code plus enable).
- Settle the autonomous RF LO: either evaluate the LC VCO with a documented
  spiral-inductor model, or record that the first die relies on the passive
  external LO.
- Regenerate every evidence file marked stale in a block README with that
  block's run script.
- Run each family's `run_*.sh` end to end once, so every published result
  comes from one reproducible run.

### 5. Top-level assembly (freeze stage 4)

1. **Floorplan:** the provider 1×1 template, the pad ring with all 74 sites,
   the five islands with their switches and edge-bar strapping at four or more
   points, the digital macro, bias trunks, the test-bus tree and 1 nF of
   decoupling. MIM over the digital macro needs the Metal1–Metal4 routing
   variant.
2. **Ring-level items:**
   - shared debug-pad protection buses at least 40 µm wide;
   - D2H[0] cell substitution at `clk_pad`;
   - `RESET_N` pull-down;
   - symmetric, shielded LO routing.
3. **Full-chip netlist from `integration/pt_chip.sv`** with every black box
   bound to its block layout.
4. **Checks:** full-chip LVS; KLayout and Magic DRC; density and antenna; seal
   ring; bond-wire geometry against the provider rules.
5. **Integrated simulations:**
   - power-up and reset with every island off;
   - island-by-island power-on current and supply droop;
   - one fallback route per family through the real pads.

### 6. Submission package (freeze stage 5)

Immutable GDS with checksums, the bond map, `board-requirements.md` turned
into a bring-up board schematic checklist, and a bring-up script that follows
the order in `tapeout-plan.md`.

## Working practices that helped

- **Compact, hand-placed layout for every GHz path.** Generic routing slowed
  fast circuits about 3×, and the compact cells brought that to 1.1–1.6×.
- **KLayout DRC on the exported GDS, not just Magic DRC.** Magic missed the
  resistor marker and implant-spacing defects.
- **One owner for each generated artifact:** the register generator, the
  digital top and the architecture bookings. Freeze the RTL while a
  multi-hour hardening run is in progress.
- **Record every shortfall as data with a fallback route.** Don't lower a
  pass criterion to make a block pass.
- **Limit simulation parallelism** (`OMP_NUM_THREADS=1`, at most a few
  containers per job) on a shared host.
