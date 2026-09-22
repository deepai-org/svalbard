# Pass 14: intermediate quiet-rail traces

The startup harness now saves checkpoints at 1, 2, 4 and 8 ns before a requested 12 ns endpoint. The [ngspice stop/resume commands](https://ngspice.sourceforge.io/docs/ngspice-manual.pdf) preserve transient state; the circuit is not restarted at each checkpoint. Saved endpoint times are checked against the requested times, and 16-digit output preserves small rail changes. The ideal case exercises all checkpoints successfully.

Physical conditions match pass 13: quiet low inputs, native 8 mA pads, 10 pF loads, unequal signal inductances, and zero or selected 0.25 ohm/2 nH paths on supply/return. Integration is default trapezoidal, maximum step 10 ps. Each case has a 60-second wall-time bound.

| Case | Execution | Last saved checkpoint | Saved rows at that point | Median / minimum saved timestep |
|---|---|---:|---:|---:|
| Ideal rails | Completed | 12 ns | 1,220 | 10 ps / 100 fs |
| Supply only | Timeout | 1 ns | 329 | 1.25 ps / 9.77 fs |
| Return only | Timeout | 2 ns | 590 | 2.5 ps / 78.1 fs |
| Both | Timeout | 2 ns | 753 | 1.25 ps / 9.77 fs |

The last saved checkpoint is not the exact point at which the run timed out. Logs continued to report progress after those checkpoints. Intermediate traces are retained despite the timeout.

Supply-only VDD varies by approximately 0.062 nV in the saved interval. Return-only VSS varies by approximately 0.000367 nV. With both paths, VDD and VSS variations remain below 0.5 nV. These are model residuals, not predictions of physical noise. They show no large rail excursion in the captured intervals; later behavior is not available.

## Interpretation and next test

The slowdown is not unique to the interaction of two moving rails: either rail impedance can expose it. Tiny timestep selection while terminal voltages remain nearly constant is consistent with numerical sensitivity, but does not identify the cause or rule out hidden internal-node behavior. The checkpoint interruptions also affect timestep history, so elapsed progress is not directly comparable with uninterrupted runs.

Next compare the installed simulator's linear solvers on the same circuit and timestep controls, retaining both successful and unsuccessful outcomes. Inspect internal-node behavior or tolerance sensitivity if solver choice does not resolve it. Do not change circuit damping or relax electrical requirements merely to obtain a completed run. Both false stability and false instability remain possible until the numerical result is cross-checked.

Reproduce with `verification/run_rail_checkpoints.sh`. The [report](../evidence/rail-checkpoint-screen.json) records execution state and hashes. Raw decks, logs and snapshots are in `scratch/transceiver-rail-checkpoint-artifacts.tar.gz`. The wrapper reports completion of the diagnostic collection; only the ideal electrical simulation reached its requested endpoint. No switching, bank-current or FPGA timing claim is established.

Archive SHA-256: `9da1c7c81542d60c5239a5922c1d4a247fc9c1ded50ffd883c96a10995138329`.
