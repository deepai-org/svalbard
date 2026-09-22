# Fast feasibility before expensive connected SPICE

Run `python3 projects/programmable_transceiver_platform/system_model/run_fast_suite.py`
from the repository root. Eleven scripts cover RF complex envelopes, conversion,
wired timing, host transport and shared-supply sensitivity. The aggregate report
is `evidence/fast-suite.json`. A measured run took about nine seconds; this is not
a speedup ratio against an equivalent transistor simulation.

These partially connected models answer which margins the architecture needs.
They do not yet answer whether the complete transistor implementation provides
those margins. Keep the full connected schematic-before-layout requirement.

## Three levels of work

1. **Architecture screening:** use envelopes instead of RF carrier timesteps,
   events instead of every digital transition, and charge/settling models instead
   of every converter transistor. Sweep uncertainty and concurrent operating
   modes. Report clipping, residual distortion, timing margin and queue growth
   separately; a single score can conceal a failure.
2. **Short transistor characterization:** select the uncertain parameter whose
   range most changes the architecture decision. Preserve actual bias, input
   common mode, load, feedback and switching history. Measure both a nominal
   case and an adverse case selected by the fast sweep.
3. **Connected transistor verification:** verify promising combinations with
   their physical drivers, references and clocks. Use long acquisition/startup
   or noise runs when that is the question being answered. Do not substitute a
   short steady-state replay for autonomous lock or startup evidence.

## Calibration and promotion rules

For each imported measurement retain the source artifact hash, circuit revision,
stimulus, supply, temperature, bias, load, time window and numerical resolution.
Label other parameters as assumptions or sensitivity ranges. Never combine
measurements from incompatible fixtures into an allegedly characterized chain.

Validate a reduced model against a held-out transistor waveform or operating
point, with tolerances set for the decision it will support. Check timestep or
envelope-rate convergence before ranking candidates. If the model misses a
polarity, settling mode or decision boundary, narrow its scope or fix it before
using it to eliminate circuit options. Do not claim a fabrication bound from an
unvalidated public model or an assumed package impedance.

Before each expensive run, record its hypothesis, exact circuit difference,
baseline, observation window and success/failure criterion. Reuse immutable
completed waveforms and retain failed variants. Run fast screens after relevant
model changes, rather than rerunning every large SPICE deck.

## Current risk order and next measurements

| Priority | Question | Fast approach | Required physical evidence |
| --- | --- | --- | --- |
| 1 | Autonomous LO quality through conversion | Measured finite LO traces and phase/spur sensitivity | Connected PLL/divider/buffer/receiver; startup, periodic disturbances and noise remain distinct tests |
| 2 | Acquisition and reference settling | Charge and decision-window models | Actual sample driver, sampler, reference pair and controller at several amplitudes and histories |
| 3 | Wired clock recovery | Event-level acquisition and timing-margin sweeps | Actual detector, oscillator, loop and loaded sampling circuit |
| 4 | Useful complete RF chain | Envelope gain/noise/nonlinearity budgets | Matched-condition chain gain, noise, compression and converter measurements |
| 5 | Die/package coexistence | Sensitivity ranges for shared impedance/activity | Connected loads, then parasitic extraction and explicit package uncertainty |

Reorder when new evidence changes the dominant limitation. Narrow supply and
temperature operation is allowed, but does not remove startup, loading, mismatch
or unknown parasitic sensitivity. Digital host capacity and electrical timing
remain separate constraints.

The latest physical-reference ADC experiment illustrates why level 3 matters:
the damped sample driver produced ideal codes 76/179/76 with ideal references at
±0.4 V, but 77/179/76 with the actual reference pair. The original physical
baseline was 78/178/78. At ±0.1 V both physical drivers produced 115/140/115.
This is promising selected-point improvement, not a transfer curve or ENOB
result. See `evidence/sar-driver-physical.json`; no production driver is adopted.

## Next architectural milestone: one connected behavioral chip

The existing suite is a collection of partially connected screens, not this
milestone. Prioritize a single executable reference architecture before further
isolated circuit tuning. Retain already-running physical experiments.

Connect RF RX/TX envelopes and converters, wired TX/RX with autonomous timing
recovery, host transport/queues, clock domains, configuration and calibration.
Drive all paths from one mode configuration and timeline. External FPGA modem
and protocol test partners must remain explicitly outside the chip boundary.
Use ideal functional blocks initially, then replace assumptions with finite
bandwidth, settling, saturation, latency, clock error and shared-supply coupling.
Record assumed versus characterized parameters separately.

Acceptance at this abstraction requires deterministic end-to-end RF waveform
and wired bitstream tests, clock acquisition without oracle timing/data in the
feedback path, bounded host queues for supported modes, and explicit reset and
mode-change behavior. Exercise allowed simultaneous paths. Sweep uncertain
parameters in both directions and adverse combinations; derive required block
margins from failures. Do not claim physical feasibility from ideal-model success.

Replace blocks incrementally with calibrated behavioral models and connected
transistor circuits while retaining the same stimuli and observable contracts.
Full connected transistor schematic verification still precedes new layout.
