# Clock startup verification obligations

The connected PLL is seeded and prebiased. Its current transient fixtures do not
implement chip startup or establish a lock indication. Preserve this distinction
when integrating timing with the RF and wired blocks.

## Reset and initial phase

The reduced PFD fixture releases external reset over 90--90.1 ns. With feedback
10 ns ahead of the reference, its first rising edge occupies that same interval.
The completed waveform shows wide UP pulses rather than a clean 10 ns DN pulse.
A controlled 80--80.1 ns release test instead produces predominantly DN pulses
and negative pump charge. The comparison supports startup phase-branch selection
in this fixture; it does not qualify autonomous acquisition from either branch.

A deterministic initial branch is not itself a requirement for a correct PLL:
a real closed loop can acquire from either phase branch. Required evidence is
successful acquisition from the declared initial phase/frequency states, without
rail trapping or a false lock indication. A forced equal-frequency feedback
fixture cannot establish that behavior.

Before calling startup implemented, the transistor schematic and tests must cover:

- Actual bias/reference establishment, power ramp and reset generation; no credit
  for a precharged loop filter, seeded oscillator or prebiased RF input.
- Reset release relative to both reference and divided-feedback edges, including
  coincidence and offsets on either side. Nominal transient sweeps alone cannot
  prove metastability probability or silicon recovery/removal bounds.
- Initial VCO frequency on both sides of target, filter states near both usable
  control limits, and both phase branches. Test missing/delayed reference and
  restarting after an interruption.
- Correct pump direction from measured PFD pulses and integrated current, followed
  by frequency/phase correction in the autonomous loop. A small mean frequency
  error alone is insufficient evidence of lock or low jitter.
- A physically implemented qualification signal and downstream enable sequence.
  The RF mixer, ADC phase generator, serializer and recovered-clock consumers
  must not assume valid timing merely because simulation time has elapsed.

Use explicit uncertainty scenarios for model and startup conditions; do not
present chosen sweep endpoints as guaranteed bounds on undisclosed fab behavior.
This file is a verification contract, not evidence that these circuits exist.

## Measure phase at detector inputs (pass 309)

Retained buffered source-offset tests requested±10ps at ideal sources, but measured
reference-buffer rising delay is~127.75ps. Actual REF-minus-FB at PFD pins is
+137.75ps and+117.75ps: reference arrives later in both cases. Over11 complete
reference cycles, mean pump current into the filter is+0.373/+0.381uA. These are
finite-history observations with changing filter voltage, not a static detector
gain, lock offset, or diagnosis of pump mismatch. Preserve input-buffer latency
when interpreting polarity or near-zero-phase behavior.
[Measured phase and charge](../evidence/pfd-buffered-phase.json).

## Late phase history before any lock claim (pass 342)

The shared loop checker now reports the last21 ordinal REF/FB edge pairs when
available: actual observation window, both frequencies, total unwrapped phase
drift, fitted slope and detrended peak-to-peak residual. Do not replace this with
nearest-edge or modulo pairing that hides a cycle slip. Startup-dependent ordinal
alignment remains explicit. The historical failed loop drifts5.780ns over its last
20 reference periods even though its frequency is near target. Detrended transient
residual is deterministic behavior, not intrinsic jitter or phase noise. These
metrics have no allocated lock threshold and cannot assert lock; incomplete-run
windows also end near a numerical failure rather than a qualified steady state.
