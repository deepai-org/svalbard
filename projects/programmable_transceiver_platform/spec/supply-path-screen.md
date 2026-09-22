# Pass 12: shared supply/return model; numerical closure pending

The native GPIO harness now supports a shared output-driver supply and return, each with series R/L. Both pads connect DVSS to the moving return node while their core VSS remains ideal ground. A pin-mapping regression checks that distinction. Signal paths retain the pass-11 unequal inductances and 10 pF receiver load. No extra ideal decoupling is inserted; native pad capacitances remain.

Initial selected stress points were 0.1 ohm/1 nH and 0.25 ohm/2 nH **per rail**, with alternating and PRBS7 patterns, 8 mA drive, nominal process, 3.3 V board supply and 25 C. These R/L values are assumptions, not assembly data. The reference planes are explicit: source and receiver use ideal board ground; output drivers use the shared moving DVSS; internal pre-driver/core rails remain ideal. Supply-pad clamp ring, substrate, mutual coupling and other bank pads are not modeled.

## Observed numerical failure

All four default-integration cases failed to produce final waveforms within the bounded run. The terminal exception was a 90-second per-case subprocess timeout. Last reported simulation times were approximately 8.43–9.82 ns, before stimulus begins at 20 ns. This is incomplete simulation evidence, not a measured electrical failure or a supply-margin result.

A fresh numerical experiment retained one physical PRBS circuit (0.25 ohm/2 nH per rail) and tried Gear-2 with explicit 20 ps and 10 ps maximum steps. Both runs also ended without waveforms; last reported times were 5.71 ns and 2.15 ns. No timestep agreement or electrical margin is established.

The [ngspice manual](https://ngspice.sourceforge.io/docs/ngspice-42-manual.pdf), transient-analysis options, documents the integration choices and warns that added numerical damping can hide ringing. Gear was a diagnostic comparison, not a means of accepting a circuit by suppressing its behavior. The cause remains unknown; model behavior, topology, numerical stiffness and genuine instability must be distinguished with actual startup traces.

## Retained evidence and next action

The [failure ledger](../evidence/supply-path-incomplete.json) records terminal state, last progress time and exact deck/log hashes for all six cases. Scratch directories are retained there. `verification/run_supply_path.sh` reproduces the current Gear comparison, which is **not passing**. Seven native-instance/extractor and three host-analysis tests passed before the runs; those tests do not validate supply behavior.

Next capture a short startup trace before the slowdown and isolate supply versus return impedance. Verify the DC operating point and local rail/reference topology, then compare numerical methods on a tractable circuit before returning to the complete data interval. Do not extend to the full bank or report improved power closure until this numerical issue is understood. Preserve the 50-terminal full companion and all throughput goals. The previous ideal-rail positive results remain scoped to ideal rails.
