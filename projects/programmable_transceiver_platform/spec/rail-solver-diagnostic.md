# Pass 15: linear solver comparison and invalid snapshot rejection

Four fresh runs compare SPARSE 1.3 and KLU with ideal and shared R/L rails. Physical decks, integration method, tolerances and checkpoint times are identical after normalizing output paths; the comparison checks that equality. KLU is selected through `.spiceinit` using the [documented option](https://ngspice.sourceforge.io/applic.html). Each log confirms the actual solver. No compatibility flags, device parameters or circuit damping are changed.

| Circuit | SPARSE | KLU |
|---|---|---|
| Ideal rails | Completes 12 ns | Completes 12 ns |
| Shared 0.25 ohm/2 nH per rail | Times out; last saved checkpoint 2 ns | Aborts at initial time point, identifying DVSS |

Solver choice does not resolve the shared-rail problem. KLU's initial-step failure and SPARSE's tiny-step progression are numerical outcomes; neither proves physical instability. The ideal control succeeds under both solvers. The full chip and dynamic rail behavior remain unqualified.

## Analyzer defect found and corrected

After KLU's transient abort, subsequent `wrdata` commands wrote single-row operating-point data into the checkpoint filenames. The old parser attempted a timestep minimum on an empty difference array and raised an exception. It did not produce a successful comparison report, and no such artifact is accepted as a transient result.

The parser now rejects single-row, non-finite, non-increasing-time and wrong-endpoint traces before computing statistics. Explicit transient-abort messages mark simulator failure even if ngspice exits with code zero. Normal checkpoint `pause requested` messages are not failures. Four new tests cover valid traces and malformed snapshots. Saved ideal runs exercise normal pause handling; all five shared-rail KLU snapshots are rejected.

The [retained report](../evidence/rail-solver-screen.json) is corrected analysis of the saved run, not a new simulation. Replay checks exact deck and initialization content; the original SPARSE timeout is retained explicitly. Raw files are archived in `scratch/transceiver-rail-solver-artifacts.tar.gz`, with its hash in the report. The initial diagnostic run directory is `scratch/transceiver-rail-solvers.u6A18iuO`.

Reproduce the current experiment with `verification/run_rail_solvers.sh`. It now retains simulator and invalid-snapshot failures instead of crashing during extraction. Diagnostic collection success does not mean all simulations completed.

Next isolate resistive versus inductive rail elements and inspect the native MOS-capacitor/ESD model contributions. Keep the physical model unchanged for solver comparisons; any later simplification must be explicitly a diagnostic and must not become evidence for the complete chip. Both artificially stable and artificially unstable numerical behavior remain concerns.
