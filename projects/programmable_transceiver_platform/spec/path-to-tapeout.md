# Path to tapeout

The acceptance rules are in [tapeout-plan.md](tapeout-plan.md), block states
in [tapeout-readiness.json](tapeout-readiness.json), and open issues in
[risk-priorities.md](risk-priorities.md#open-issue-register).

## Resume from here

Work is paused. [closure-handoff.json](closure-handoff.json) records the checked
artifacts, terminal process states, output paths and collection commands.
All background jobs are stopped at the user's request. Resume explicitly before
starting replacements. The detailed scratch checkpoint is
`scratch/digital-closure/checkpoint.json`.

1. The IDAC1 SMU campaign has completed and passes its independent audit
   (`checkpoint-2-audit.json`); keep this fixture result separate from
   full-chip observation gates.
2. Digital: legalization is resolved and the flow completes with routed DRC, LVS and antenna
   clean (section 1, CLOSE_R1). Setup does not close: in-window ss WNS is −15.1 ns. Next:
   - collect CLOSE_R2 (current sources, GLS);
   - implement the AC-1/S2/S3 core (40-bit at word/4);
   - pipeline the rate-independent domains.
3. Core-bias routing is a maintained flow (`make transceiver-core-bias-routing`).
   Its last run (`scratch/core-bias-routing-20261109-101927/`) passes all 11
   checks, with supply EM/IR judged against GF180MCU DRM 14.2.
   `make transceiver-core-bias-device-lvs` runs device-level LVS of that routed
   GDS (flat Magic extraction, all masters included) against a schematic-leaf
   reference built without any layout input. It matches uniquely (1546
   devices, 977 nets) and rejects three negative controls. The only property
   differences are two MIM capacitors with c_width/c_length transposed, the
   same ones the per-master LVS showed.
4. Assemble the complete provider-core floorplan and real payload/control/
   observation bindings, then close the full-chip checks below.

The maintained digital flow builds its pinned guarded tool image automatically.
The FIFO read alternatives remain scratch experiments; main RTL retains its
validated binary read implementation. No tapeout gate is being closed on the
basis of an unfinished run.

## Current state

The core infrastructure is qualified at block level: POR, bias chain, island
switches, analog test bus, pad protection and register control. The assembled
nominal bring-up check demonstrates physical power-up, SPI, island enable,
debug observation and a 500 Mb/s external wired-TX fallback. Its digital
control is RTL; current digital hardening and full-chip signoff remain open.

The selected digital implementation uses paired transport engines at
156.25 MHz behind the 312.5 MHz ten-bit host boundary. Functional checks pass
2.5 Gb/s bidirectional wired service and 40 MS/s I/Q service. The current
main RTL has a routed 1580 × 1580 µm run (CLOSE_R1) with DRC, LVS and antenna clean. Hold
meets in every in-window mode. Setup misses by 15.1 ns at in-window ss and 7.0 ns at tt.
The routed netlist contains 8149 flip-flops against the 8192 cap.

All five island power-good outputs are observable through the real SPI pads.
The observation ledger has 4 passed, 41 open and 2 retired entries. Most
payload-node, clock and status paths still need assembled verification.

A 36-cell core-bias placement and five validated distribution LEFs are
available. The complete chip still needs a floorplan, a fully bound netlist,
routing, full-chip physical checks and a submission package.

## 1. Close digital rate and area

Keep the selected rate contract: 312.5 Mword/s host, 125 MHz wired double
words and 40 MS/s complex I/Q. All 59 payload words in each 64-word frame
belong to the stopped-selected wired or I/Q owner (`0x91` bit 0).

The core uses a 64-pair wired ingress FIFO, eight-sample RF ingress FIFO,
twelve-pair I/Q TX queue, seven-pair I/Q RX queue and shared 32-entry, 24-bit
egress FIFO. Disable flushes the shared bank even with clocks stopped;
release is synchronized in each domain. The RX queue uses registered full
status for admission, independently of downstream unpacker readiness. The
transport contract is in [streaming-transport-v2.md](streaming-transport-v2.md).

### Status 2026-11-10 (routed run CLOSE_R1, scratch/digital-hardening-closure-r1)

The physical flow now completes end to end on the current RTL in the pinned guarded image.
Physical signoff passes. Timing does not close.

| Item | Result |
| --- | --- |
| Footprint | 1580 × 1580 µm (2.496 mm²), standard-cell area 1.555 mm², utilization 64.1 % |
| Flip-flops | 8149 in the flattened routed netlist (cap 8192) |
| DRC | Magic 0, KLayout 0 (flow GDS), KLayout 0 on the Magic 8.3.678 export, routing DRC 0 |
| LVS | Netgen 0 errors |
| Antenna | 0 violating nets/pins (46 diodes) |
| Hold | met in every in-window mode (worst +0.04 ns at ss_window) |
| Setup, full rate (rate1) | WNS −15.08 ns at ss_window, −7.01 ns at tt, −3.31 ns at ff_window |
| Setup, /2 and /4 fallback | hcore/hpair close at /4 (hcore −1.13 ns, hpair +4.1 ns at ss_window), but the rate-independent domains (wired, ref, freq-counter, SPI) still fail, so no mode closes |
| fmax at tt (MHz) | hword 189, wtx 96, wrx 72, ctw 120, rftx 51, rfrx 76, ref 64, fc 85, sclk 19 |
| GLS | invalid for this run: the netlist predates two later RTL edits (map 0x097D vs 0x179E). CLOSE_R2 repeats the flow on the current sources. |

Timing is judged inside the operating envelope only (22–32 °C, 3.15–3.35 V). The PDK ships one
in-window Liberty (tt_025C_3v30). In-window ss/ff are global derates on it, defined in
`integration/pt_digital_macro.sdc`: ss_window 1.54, ff_window 0.71. They are interpolated
from the PDK's ss/ff libraries. The -40/125 °C libraries are not criteria.

What changed to get here:

- **Placement legalization (DPL-0033).** The cause was electrical repair inserting 20–64k
  buffers (+60–93 % area, up to 97 % utilization). It was not the legalizer. The fixes:
  - max transition 1.0 → 2.0 ns and cap 0.1 → 0.15 pF (1.0 ns is below the X1 cells'
    intrinsic output slew);
  - no wire-length repeater rule;
  - a pin plan instead of random IO placement (`verification/digital_hardening/pin_order.cfg`),
    which cut repair to about 9k buffers and SCLK slack from −78.9 to −7.0 ns pre-repair.
- **Toolchain.** The guarded image's LibreLane does not match its engine:
  - The scene-object API broke STA steps; this is now patched in `prepare_toolchain.py`.
  - The odb layer area units broke custom pin placement; explicit IO pin lengths avoid it.
  - Stray pad libraries broke multi-corner repair (`PAD_LIBS={}`).
  
  The canary image cannot be used: its `repair_design` runs away (23 GiB) at any transition below 3 ns.
- **Constraints.**
  - Reset-synchronizer RN pins are cut as CDC.
  - The rate-switch hold release is cut to the non-host domains.
  - Repair and STA run only in-window corners (`RSZ_CORNERS`/`STA_CORNERS` tt).
  - The envelope derate is applied to timing but not to electrical repair, where it makes `repair_design` chain buffers without bound.
- **RTL (all functional/formal checks pass).**
  - Reduced-rate fallback `debug.host_link.rate` (`pt_host_rate_clock`; reset full rate;
    stopped-only; holds host link and core in reset across the switch; `tb_host_rate_clock`).
  - 90-FF reclaim of the header data delay line (`pt_dense_header ALIGN=0`; the encoded
    value is held four clocks before publish).
  - Registered PRBS-checker saturation flag.
  - `en_eff`/`island_off` assembly decode outputs.
  - W1 `cdr.config.cap_rcsel`.
  - Slow-slew host-pad reset.
  - Static DAC bus when no sample is valid.

Remaining worst paths (tt): wired-ingress FIFO read and Gray count into the frame engine
(hpair_tx), frame RX guard into the egress write (hpair_rx), PRBS-checker pend arithmetic
(wrx), 8-entry H2D FIFO read (hcore), freq-counter carry chains and tolerance compare
(fc/ref), and egress read/valid (wtx). The 20-bit core at 156.25 MHz needs about 2.4× at
in-window ss. The adopted closure architecture is AC-1/S2/S3
(`spec/interface-architecture-changes.md`): pad-edge DDR plus a 1:4 gearbox, a 40-bit core at
word/4 (78.125 MHz), and a 40-bit wired boundary at line/40. That needs about 1.4× from the
pipelining listed above. It is the next RTL task, and every functional/formal check must be
re-proven on it.

Open items:

1. Implement AC-1/S2/S3 in RTL, then re-harden and close setup in all in-window modes, including /2 and /4.
2. Pipeline the rate-independent domains (freq counter, PRBS checker, clocktree slow, SPI
   memory readback), which AC-1 does not slow down.
3. Run GLS on a source-consistent netlist (CLOSE_R2).
4. Decap: the library `fillcap` gives about 0.4 nF in the macro, against 2.5–4.7 nF required. A thin-oxide decap cell is proposed (interface-changes.md).
5. Activity-based power (S9). The flow's vectorless figure is 258 mW, all clocks at target.

Useful checks:

| Command | Evidence scope |
| --- | --- |
| `make transceiver-dense-pair` | Codec, odd-word carry and malformed-frame handling |
| `make transceiver-dense-pair-link` | Training, word alignment and capture phase |
| `make transceiver-dense-service` | Wired queues at target rate and overload rejection |
| `make transceiver-dense-rf-service` | Both I/Q widths at 40 MS/s across clock phases |
| `make transceiver-dense-rf-burst` | Actual full-quota host frames and sustained RF service |
| `make transceiver-pair-gearbox` | Ordered conversion, backpressure and reset |
| `make transceiver-pair-gearbox-formal` | Factored gearbox arithmetic equivalence |
| `make transceiver-pair-word-formal` | Launch phase and capture-window proof |
| `make transceiver-freq-count-formal` | Counter range/saturation equivalence |
| `make transceiver-shared-egress-lifecycle` | Owner changes with stopped clocks |
| `make transceiver-transport-budget` | Fresh functional evidence and nominal service budget |
| `make transceiver-area-budget` | Planning allocation reconciliation |
| `make transceiver-digital-hardening` | Physical implementation and signoff stages |

Functional queue tests and mapped screens do not establish physical rate closure.

## 2. Finish physical assembly

The host/debug pad binding is `integration/pt_provider_io.sv`, selected with
`PT_EXTERNAL_IO`. `integration/core_bias.py` binds the extracted references,
root and five banks. `integration/atb_tree.py` assembles extracted ATB leaves,
groups and pad switches. The physical wired-fallback control is in
`analog/bringup_control/generated/`.

1. Bind every payload macro's real bias load and effective enable, including
   the USB bias DAC at `0xD7`. Replace fixture loads and ideal boundary
   stimuli with actual consumers, isolation clamps, POR and power-good.
2. Finish routing the core-bias slice and export accessible boundary pins. Its 36
   instances and 120-pin net map occupy 908.65 × 276.99 µm before routing.
   `make transceiver-core-bias-placement` checks cell separation and zero
   geometric difference from qualified masters. Its pin audit checks every
   LEF landing rectangle and port label against qualified GDS metal. The
   physical terminal map covers 278 instance pins, 150 nets and all 120
   boundary signals. `make transceiver-core-bias-routing` routes the seven
   supply nets first (VDD/VSS 4 µm, rails 2 µm, Metal2–Metal4) with every
   supply via filled with a cut array of up to 5×5. It then routes the 143 signal nets around
   that fixed special wiring, with POWER/GROUND roles restored.
   Run `scratch/core-bias-routing-20261109-101927/` has these results:
   - zero router violations;
   - an independent audit of all 150 nets, 278 terminals and 120 pins, which
     includes route shorts into master-internal metal;
   - all five negative controls rejected;
   - zero DEF/GDS XOR and zero geometric difference for all eight masters;
   - zero GF180 KLayout DRC violations;
   - unique black-box routing LVS, with a bridge control rejected;
   - Magic C extraction.

   Supply IR drop is at most 8.8 mV and via-cut use at most 0.19 of the
   DRM 14.2 85 °C rating (0.61 at 125 °C), using VDD 1.0 mA and VSS equal to VDD
   plus all rail currents. Device-level LVS of the assembly also remains open. `make transceiver-bias-abstracts`
   validates distribution pin roles, GDS bounds and OpenROAD LEF import.
   Full-chip assembly is a maintained flow: `make transceiver-chip-assembly`
   (`verification/run_chip_assembly.py`, `verification/chip_assembly/`). Its
   last run, `scratch/chip-assembly-dev/` (2026-11-10), has these results:
   - **Placement.** 145 instances are placed legally on true GDS bounds. This
     covers all 74 sites, 12 custom pad cells, 5 switches, core-bias, 104 ATB
     cells, the 1580 µm digital abstract and 4 interface reserves, and an
     independent pairwise check passes.
   - **Decoupling.** There is a 1.02 nF MIM pool on core VDD in 8 banks, each
     with a 10 × 20 µm FIB strap, plus 5 × 20 pF behind the switches.
   - **Bond map.** The wired pad families are wider than two sites and collide
     with the debug pairs at bidir[16] and [22]. They are mirrored, so WIRE_RX
     and WIRE_TX have their P and N bonds swapped.
   - **Checks that pass.** Each has a negative control:
     - the debug buses join BB_I+BB_Q and WTX_EXT+WMON (Metal5 rail, Metal4
       return, 40 µm);
     - the core-ring corners show no VDD/VSS short;
     - 4-point strapping is clean on 4 of the 5 switches;
     - the RESET_N tie connects PD to VDD and PU to VSS;
     - D2H[0] is on bi_t at clk_pad.
   - **Checks that fail.** The isw_debug straps short VDD to VISL through the
     cell's Metal5. There are 11 unintended ring/stub overlaps on four
     pad-family cells.
   - **Netlist.** `pt_chip_full.spice` binds 150 instances and 2613 ports. The
     USB bias DAC at 0xD7 is bound, but 485 ports are still unbound.
   - **Provider precheck.** Top cell, size and CoB pad mask pass. Zero-area
     polygons are 0. Density has 4 violations because no fill has been added.
     The antenna deck crashed while saving its report.
   - **Not done.** Signal routing, block supply hookup, LO routing, full-chip
     LVS and Magic DRC.

3. Place the complete design in the provider 1×1 template: all 74 pad sites,
   five islands and their switches, digital macro, bias trunks, ATB tree and
   1 nF of decoupling. Use validated LEF/GDS bounds including straps and pins.
   Island supplies need edge-bar strapping at four or more points.
4. Complete the ring details: debug protection buses at least 40 µm wide,
   D2H[0] substitution at `clk_pad`, `RESET_N` pull-down and symmetric shielded
   LO routing. MIM above digital requires a clean Metal1–Metal4 routing
   implementation; close its timing and antenna issues before booking Metal5.
5. Bind every black box in `integration/pt_chip.sv` to its actual layout and
   generate the full-chip electrical netlist.
6. Run full-chip LVS, Magic/KLayout DRC, density, antenna, seal-ring and
   provider bond-wire geometry checks.
7. Verify assembled power-up with every island off, island-by-island inrush
   and droop, and one fallback per family through real pads. Repeat cold
   startup with extracted control glue and the current digital implementation.

| Command | Assembly boundary |
| --- | --- |
| `make transceiver-chip-io` | Real provider pad models; digital SPI/reset/status |
| `make transceiver-chip-power` | Physical POR, pads and island switches; fixture loads |
| `make transceiver-chip-fallback` | Nominal cold-start/SPI/external wired-TX sequence |
| `make transceiver-chip-fallback-layout-route` | Extracted control and preset-state fallback route |
| `make transceiver-bringup-control` | Control-cell physical and loaded PVT qualification |

The audited nominal fallback result is in
`scratch/chip-fallback-burst/milestone-audit.json`: zero errors in 64 payload
bits at 500 Mb/s and 473.3 mV minimum differential sample margin. It uses
schematic control glue and its recorded frozen sources. The extracted-control
route result is in `scratch/chip-fallback-layout-route/route-report.json`.
Neither closes full-chip, PVT or statistical BER qualification.

## 3. Wire and verify observation

1. Assign each required block port, status signal and clock to an explicit
   ATB code or observation-mux selection in `debug-controls.json`. Keep every
   local test bus at twelve leaves or fewer.
2. Connect those paths to real nodes, `CLK_OBS`, SPI status and debug pads.
   Shared physical implementations need mode/channel-specific assignments.
3. Record tap/mux selection, island state and expected bench-visible result
   per block. Verify one assembled case per island, then every mapped path.
4. Update each observable ledger entry only when that path has assembled
   evidence. Power-good qualification is recorded in
   [assembled-power-observation.json](../evidence/assembled-power-observation.json).

`debug-controls.json:block_observation` assigns every output port of every
non-retired block to an ATB code, status mux, clock/monitor/BB-tap selection, SPI
register, payload or pad, with shared-cell mode, islands and expected bench result.
`make transceiver-observation-paths` checks each selection in assembled RTL
(pt_chip with the provider pads) up to the black-box analog boundary and the
debug pads. It runs 118 entries; 24 bench, payload or digital-internal entries
are not simulated. Six negative controls must fail.
`make transceiver-observation-coverage` validates the assignment and writes
`scratch/observation-coverage/checklist.txt`. It grades each entry as mapped,
rtl_selection or analog_fixture and never changes ledger states.
`make transceiver-atb-tree` verifies 57 sense and 20 force codes with finite
source/meter impedances. Its DC fixture does not close payload-node bindings.

`make transceiver-core-bias-observation` checks the reference chain and banks
through real SPI pads and extracted ATB switches. The completed campaign is in
`scratch/core-bias-observation-checkpointed/`; its independent waveform auditor
is `verification/audit_core_bias_observation.py`. The final audit passes register
identity, all-five-island status, settled VBG and bank currents, all fifteen
voltage-sense codes, external VBG force and final SPI checks.
`make transceiver-core-bias-idac1-observation`
checks code 57 with a 1 V SMU load and SPI-commanded off/4/8/off current steps.
In `scratch/core-bias-idac1-observation-current/`, the producer report and the
independent audit (`checkpoint-2-audit.json`) pass. Measured currents are
-0.76 nA, 3.753 µA, 7.506 µA and -0.76 nA, or 0.938 µA/LSB. The simulation had
finished, but the producer crashed because `audit()` returned nothing. This is
fixed; `--assess-only` re-assesses without rerunning.
The auditor no longer reads the producer's schedule. It takes the ATB code from
`debug-controls.json`, the off/4/8/off plan and 1 µA unit from this section and the
register map, and the step times from the SPI stimulus decoded out of the simulated
deck. Each window runs from 3 µs after the commit to the next SPI activity, about 5 µs.
Its re-audit (`spec-independent-audit.json`) passes, and wrong codes, a wrong LSB, a
wrong node or no settling time each fail it.
The fixture uses warm reset, diode consumer loads and unbound payload nodes.

## 4. Close remaining block work

- Wired CDR: add PLL HOLD for phase-loop handover, use all four quarter-rate
  edge samples, build compact RX capture and qualify extracted tracking.
  Also qualify `WCLK_IN` → slicer → capture → raw words as the RX fallback.
- Wired TX: implement the 4:1 mux, retiming flops and window drivers with the
  compact timing cells and qualify quarter-rate operation.
- Slicer: qualify compact samplers at ss for the 480–810 MHz ring plan.
- Add device replicas and resistor/MIM matching arrays reachable through ATB.
  Done 2026-11-09: `analog/characterization` `pt_char_atb` (codes 43–54), DRC/LVS/KLayout
  clean, LEF, extracted force/sense through the extracted ATB chain at 5 corners.
  Open: VCO replica VCTRL has no ATB code (register request).
- (Settled 2026-11-09: first die depends on the passive external LO through
  REF_IN/AUX_CLK; `lo_ext` rerun passes 12/12 corners. No autonomous LO.)
  Settle autonomous RF LO qualification with a documented spiral model, or
  record the first-die dependence on passive external LO.
- Refresh stale block evidence and run each family's reproducible flow once
  against the final source set.

Status 2026-11-09 (evidence produced in this pass):

- Core-bias routing passes: `make transceiver-core-bias-routing` run
  `scratch/core-bias-routing-20261109-101927/` (all 11 checks). Supply EM/IR is
  judged against GF180MCU DRM 14.2 (Via1-4 0.58 mA/cut, Metal1-4 2.09 mA/um at
  85 C; 125 C values reported) with max-corner resistance, VDD 1.0 mA (bias
  budget), rails (outputs + TRK leg) x 12.14 uA x 2, VSS = VDD + rails. VDD/VSS
  widened to 4 um and every supply via filled with a cut array; IR <= 8.8 mV,
  cut use <= 0.19 (0.61 at 125 C). Device-level LVS of the assembly stays open.
- `pll_ring` r6 failed safe (509 uA with EN=0, HOLD flop reset fight); r6a
  fixes it (10 uA) and is resimulated: locks 480/625/810 MHz and host_follow,
  cold start locks, but port phase error grew to 9-10.8 deg and HOLD fails
  its own criterion (+1545 ppm step, 110 ppm/10 us drift). The HOLD verdict
  had been overwritten by `locked` in `run_timing.py`; fixed.
- Wired-RX CDR cell resimulated with r6a: cell clean at 12/12 corners, but
  extracted tracking still fails (quarter 560/3588, half 104/1768 errors) and
  the REF-gate hand-over drifts 5883 ppm.
- `pt_wrx_cap` now has a flow (`run_capture.py`, run by `run_wired_rx.sh`) and
  evidence: DRC/LVS clean, schematic 0 errors, extracted fails above 480 MHz
  (errors at word-boundary slots).
- Wired TX (2026-11-10): the ss/22 C/3.15 V abort was a bench artifact
  (ngspice cannot converge source branch currents at the tiny step after
  PWL/PULSE corners; ngspice 43 and 47 alike; no floating node in the DUT);
  fixed with breakpoint-free stimuli and driver resistance, no tolerance
  changed. The old failing case then passes 0/61. The serializer is rebuilt as
  a compact TSPC core (`wtx_serq4`, quarter/half/full; generic serializer
  kept as rate-code-11 fallback): schematic 0 errors at 3.24 Gb/s on
  tt/ss/ff/sf/fs, 1.62 half and 0.81 full at ss. Layout DRC 0 / KLayout 0 /
  LVS unique, 0.337 mm2 (over 0.30). **Extracted fails** (generic placement
  skews the core phases: 2.5 Gb/s 57/221, 1.62 Gb/s 31/221 errors); next step
  is a hand-placed core macro. Evidence now hashes the extracted netlist and
  drops stale runs; envelope is 20 points (sf/fs added).
- Slicer (2026-11-10): compact hand-placed samplers (`ws_sa`), 0 errors
  extracted across the 480-810 MHz ring plan in quarter/half/full and USB HS
  at ring 480 MHz, nominal + 12-point envelope (sf/fs not run); DRC/LVS
  clean, 30,069 um2. Output delay changed; capture/CDR/WCLK_IN runs need a
  rerun.
- Not started: HOLD hand-over in the CDR, four-edge PD, WCLK_IN fallback
  simulation.

Status 2026-11-09, second pass (wired RX + pll_ring; details in the
wired_rx and timing READMEs):

- **`pt_wrx_cap` r2.**  The extracted failure above 480 MHz was the slot
  decode, not LDE: counter → global decode → enable took about 1.7 ns, more
  than the 1.6 ns period at 625 MHz.  r2 replaces it with a one-hot enable
  chain, adds strong buffers on the front and lane outputs, a local
  word-load enable through a latch, and weak keepers on the word flops.
  Ideal-sampler benches with r2b–r2d run 0 errors extracted at
  480/625/810 MHz quarter, 625 MHz half and 480 MHz full rate.  The
  revisions differed only at ss and 810 MHz (table in the wired_rx README).
  r2f is the current netlist and its run is in progress, so
  `wrx_cap-evidence.json` is still r1.  Benches now also check edge words
  (never checked before), an EN = 0 safe case and a 95 % BER bound.
- **Slicer → capture timing is open.**  Extracted slicer clock-to-output
  delay is 0.95–1.28 ns at tt and 1.24–1.63 ns at ss; the fixed T/2
  re-capture fails at 480 MHz.  The fix (static re-capture select
  k ∈ {2, 4, 6}) is specified in wired_rx Known limitations 0.
- **`WCLK_IN` fallback simulated** (`run_fallback.py`, extracted slicer +
  r2c capture): fail.  480 MHz 43/180 (re-capture race), 625 MHz DW 0/180
  but 23 EW mismatches, 810 MHz 8/180 (bit-0 race, fixed in r2d).
- **`pll_ring` r7 (charge-pump steering).**  Schematic: VCTRL ripple
  38 → 3.6 mV, PFD activity 6.5 → 3.2 % (below the analog LOCK break-even
  of about 6.7 %), HOLD step +850 → +273 ppm.  Layout DRC 0 / KLayout 0 /
  LVS unique.  The extracted rerun is in progress, so
  `pll_ring-evidence.json` is still r6a.
- **CDR:** not reworked in this pass.  It is superseded by AC-3 (per-UI
  analog Alexander PD, continuous integral path, no HOLD hand-over) and by
  consolidation R2 (remove `pt_cdr`'s REF gating).  The extracted CDR runs
  still use r6a, while `generated/pll_ring.ext.spice` is now r7.

## 5. Submit

Freeze checked GDS with checksums, the bond map, a bring-up board schematic
checklist derived from `board-requirements.md`, and a bring-up script following
`tapeout-plan.md`. Complete the submission gate only after the current-source
physical, safety, observation and fallback evidence is accounted for.
