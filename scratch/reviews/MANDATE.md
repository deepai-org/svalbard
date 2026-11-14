# Mandate: standing rules for the transceiver chip

Consolidated 2026-11-14 from the dated entries (9–14 Nov). The chronological original is
`archive/MANDATE-2026-11-14-pre-consolidation.md`. Rules are the user's unless marked (coordinator).
Current work status is in `SESSION-STATE.md`, not here.

## 1. Scope and priorities

- **Full scope, no cuts.** Every capability, mode and rate stays, including the 2.7–3.24 Gb/s wired paths
  (DisplayPort HBR 2.7, SATA Gen2 3.0, XAUI/2500BASE-X 3.125). Something missing on chip was forgotten, not
  descoped: build it.
- **Off-chip is allowed only for:** passives (any number), the FPGA, and a fallback LNA in addition to the
  built-in LNA.
- **A miss is accepted only if physically impossible in GF180MCU**, shown by a quantitative proof in
  `physical-limits.md` (device fT/fmax vs bandwidth, pad/ESD capacitance vs return loss, thermal or
  current-density limit). "Hard", "risky", "out of time" and "not enough die area" do not qualify.
- **No dead chip comes first.** Die 1 must power up safely, talk to the FPGA and be observable even if every
  ambitious block fails. Shared infrastructure (supplies, bias, reference, pads, digital, host link, debug) gets
  the most conservative design, isolation and bypasses.
- **On-chip implementations are the design.** Fallbacks (external LO, external LNA, forwarded clocks, bypasses)
  exist to recover a partially working die and to yield data; keep their hooks and observation paths, but they
  are not the plan.
- **Spend risk only where something ambitious happens and no low-risk alternative exists.** Elsewhere use the
  conventional, proven, simplest option even at some cost in area or power. Use the silicon-proven
  gf180mcu_fd_sc (5 V-device) standard cells; custom fast cells only where a path cannot close otherwise, kept
  small, contained, observable and with a fallback. When proposing anything novel, state the low-risk
  alternative and why it is insufficient.
- **Architectural fixes are in scope:** wider host link, pipelining, different topologies, inductive peaking,
  T-coils, CML, interleaving.
- **Area is minimised over time across the whole project.** The die is fixed at 3.932 × 5.122 mm (the only
  slot size offered) and the design is over it (`die-fit.md`). Every owner treats area as a standing objective:
  report the area delta of every change against the die-fit ledger, build new circuitry compact from the start
  (shared guard rings, abutted rows, MIM over devices, no generator-default channels), and keep a short list of
  its next area levers. The coordinator keeps the ledger and reruns the packer.
- **Schedule is the user's concern** (mid-December 2026 shuttle). Do not raise it or trade scope for it.
- **Scope and AI-driven design are intentional.** Counter blind spots with many varied checks and
  cross-references against public data. The user is the gauge of tapeout readiness.

## 2. Operating conditions

- **Performance window:** junction 22–32 °C, die supply 3.15–3.35 V, all process corners (ss/ff/sf/fs). Do not
  require performance at 0, 85 or 125 °C or at wide supply.
- **Per-chip supply trim:** the board sets each die's supply (trimmer + regulator), chosen at bring-up from the
  die's measured speed (ring monitors need readout codes). Slow dies may run up to a 3.50 V setpoint, with
  setpoint + tolerance + ripple + overshoot ≤ 3.63 V; typical dies stay at 3.3 V; fast dies may be trimmed
  down. Every block reports slow-corner results both untrimmed and trimmed and its minimum (and, at ff,
  maximum) passing supply; one trim value must satisfy all blocks in a mode. It does not excuse
  passive-limited specs, area, ff hold timing, reliability at 3.5 V, ESD/clamp behaviour or the IR budget.
- **Safety window stays wide:** 0–3.63 V supply ramps, 0–85 °C, no damage, latch-up or lock-up.
  Electromigration and IR sign-off at 85 °C (coordinator).
- **ESD transient limit:** for ~150 ns ESD events use the transient oxide limit derived from PDK data
  (pessimistic value), not the 3.63 V DC limit.

## 3. Ground truth and models

- **Two risk buckets.** (1) Ground-truth data is guessed or wrong: every number we rely on goes in
  `spec/design-assumptions.md` with value, source, confidence and pessimistic design value. (2) We designed
  badly: extracted results at every in-window corner, checks that can fail, no limits relaxed after seeing a
  result, independent review before "done".
- **Bound uncertain values in both directions.** "Pessimistic" means worst for the specific check. Designs must
  work across the whole range and be optimised for the most likely value.
- **Device-speed guidance** (`gf180-device-speed-evidence.md`): nfet_03v3 fT ≈ 16 GHz at ss/32 °C (11–13 GHz
  usable in layout); pfet ≈ 5.5 GHz; 5/6 V devices 6–9 GHz. Models omit gate resistance: add explicit Rg
  (60–150 Ω per 10 µm device) in RF and high-speed sims. Derate pre-layout timing 1.45× or sign off extracted.
  Quarter-rate samplers; keep pfets out of paths above ~2 GHz. PDK noise models are suspect.
- **Process facts** (`wafer-space-answers.md`): 5 metals, 1.1 µm top metal, MIM option B (2 fF/µm² nominal,
  1.92 measured on Run 1), 1 kΩ/sq high-res poly, native-Vt and 6 V devices allowed. Unconfirmed: deep n-well,
  SAB/`_dss` devices, the ESD implant layer 24/0. Run 1 lot data was close to typical.

## 4. Verification discipline

- **Prove the bench small first.** Reproduce a known analytic answer and fail a deliberately broken case, then
  swap in one real block at a time. Full extracted runs only after each step agrees.
- **Bench against real neighbours.** Real source and real load (extracted neighbour + route + pad + package),
  not ideal ones. The mode walk found 10 dB gaps between ideal benches and reality.
- **LVS on the GDS read back from disk**, with device parameters compared and a failing negative control.
  Resistance-aware extraction wherever metal resistance is in a signal path (pads, terminations).
- **Evidence must match what ships:** sha-matched records per published GDS; one work directory per precheck.
- **Fill is ours to run** (precheck 1.7.4, PDK 792ef67, density and DCF.1a are gating). Top-level fill with
  block-owned keep-out markers, and fill-aware re-extraction of sensitive blocks (inductors first).
- **Independent review before "done":** a different agent, given artefacts, not the conclusion.
- **Limits do not follow measurements.** A missed limit is reported as a miss or raised as a budget request.
- **Chip-level verification is a first-class workstream:** one connectivity source of truth
  (`integration/top/pt_chip.conn` and its `run.sh`), isolation/off-state audit, power-delivery model,
  substrate and pulling checks, power-up and reset.

## 5. Top level and physical design

- **Floorplan for performance, before routing:** fast nets short, direct and matched; I/Q symmetry; aggressors
  (digital macro, PA, rings) away from LNA, VCO tank, bandgap/bias, ADC inputs; each block next to its pads;
  macro pins facing their consumers; an extracted supply grid inside the 117 mV drop budget with decap at the
  switching loads.
- **Gate before sign-off:** extract critical top-level nets and resimulate each chain; substrate and supply
  coupling; PDN drop and decap response.
- **Mitigations are demand-driven.** Guard rings, deep n-well, shields, separate domains, decap and the like go
  only where an analysis shows a quantified need, citing the risk-register row and the analysis.
- **Shared digital datapath:** one transport/framing path, one set of FIFOs and gearboxes, pattern
  generator/checker, capture/playback, counters, fast-command path and calibration sequencer serving whichever
  mode is active. Mode-specific logic only where the function truly differs.
- **Decode glue lives in the digital macro and the register map follows the analog cells** (coordinator).
  Isolation clamps for island-to-macro signals are standard cells inside the macro.

## 6. Packaging, pads and board

- **Package:** the wafer.space chip-on-board only (bare dice are available but not wanted). 14 × 16 mm board,
  74 fingers, ground paddle, one 70-pin mezzanine connector; die ~250 µm thick, 0.8 mil aluminium wire
  (gold under trial), epoxy glob-top. One fixed 74-wire bond layout: no custom bonds, down-bonds, double bonds
  or extra wires. A customer-modified COB may not be accepted this run, so the unmodified board must work.
  The COB carries eight 1 µF capacitors on the supply nets and nothing on signal pins; the nearest signal
  passive is on the carrier, 5–6 mm of trace plus the connector away (≥ 6.5 nH per leg).
- **Design to tolerate passives at varying distance:** programmable termination, matching and trim; wide-range
  equalisation; LO input tolerant of amplitude and phase spread; on-chip fallbacks where no passive is close.
  The package mostly changes performance; it rarely makes things impossible. Qualify every RF, multi-Gb/s, LO
  and clock path through the whole channel.
- **Off-chip passives** go into `spec/board-requirements.md` with part class, value and tolerance, and their
  pin and parasitic model goes into the sims that rely on them. Board trimmers (set once at build) are preferred
  over on-chip trims that cost noise figure.
- **Per-application carriers are fully acceptable.** A carrier may populate only its application's passives and
  a pad may carry different functions on different carriers. Every carrier still needs bring-up, debug and
  fallback access. A passive needed only in one mode may use pads idle in that mode.
- **Pin and pad assignment is the coordinator's call on technical merit**; escalate only if a capability or
  requirement would be lost.
- **ESD tiering** (`esd-tiering.md`): 2 kV HBM on supplies, host link, debug/ATB, RF_RX, the HS RX pair and
  USB; 1 kV on RF_TX, WIRE_TX and optionally clocks; CDM ≥ 250 V chip-wide; nothing below 500 V. Keep main
  diodes and local secondary clamps. Board TVS on antenna and USB connectors is mandatory. A small TLP site
  stays.
- **Board rules found so far:** supply slew ≤ 0.3 V/µs and no hot-plug (supply-pad clamps fire on fast edges);
  bring-up starts every die at 3.3 V; RESET_N host-drivable and low through power-up when the POR strap is set.

## 7. Bookkeeping

- **One risk register:** `spec/risk-register.md`. READMEs and reviews cite IDs and keep no lists of their own.
- **Cross-ownership changes** are rows in `interface-changes.md`; other owners' files get rows, not edits.
- **Consolidate early and often:** interface rows, risks, inventory, published views.
- **Keep it simple:** plain markdown, small scripts, no schema machinery for bookkeeping.

## 8. Rules for agents on the shared machine (coordinator)

- At most 3 simulations or heavy jobs at once per owner including its sub-agents; `OMP_NUM_THREADS=1`; tool
  threads ≤ 4. No speculative sweeps. No `pgrep -f` wait loops that match themselves.
- The disk is nearly full: keep outputs small and delete intermediates.
- Commit small reviewed steps with explicit paths (`git add -f` under `scratch/`), never `git add -A`; do not
  push; the coordinator pushes. No GDS uploads until a block is really finished.
- Keep a notes/status file current so a successor can resume; write long reports incrementally.
- State plainly what was rerun versus only read, and what failed.
