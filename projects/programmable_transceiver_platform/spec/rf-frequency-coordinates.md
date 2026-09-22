# RF model frequency coordinates

The envelope frame is fixed at2.4GHz. Carrier tuning changes the oscillator,
not this frame. Every tone passed to `configure_rf_input` is expressed relative
to the fixed frame, as is `external_source(..., offset_hz=...)`.

For target carrier F, desired baseband offset b, and blocker offset d from F:

- Desired source argument: F −2.4GHz + b.
- Carrier-relative blocker argument: F −2.4GHz + d.
- Fixed laboratory blocker at absolute frequency B: B −2.4GHz.
- Nominal received blocker offset: B − F.

`fractional-top-profile.json` declares which blocker convention is intended.
The measurement report records both the model-frame frequencies and their
nominal offsets from the target. Actual LO phase/noise remains part of the
simulation; these translations do not cancel oscillator errors.

The preserved fixed-laboratory experiment places one blocker inside the receive
band after tuning and fails the desired-waveform budget. That result must not
be discarded or called equivalent to an out-of-band blocker test. The translated
experiment tests20/30MHz offsets from the configured carrier, retaining amplitude,
filter, nonlinearity, noise, load and quality threshold.

Audit at pass875: the original wideband and pulse-wideband blocker tests retain
a2.4GHz target, so their model-frame offsets already equal carrier-relative
offsets. Tuned single-tone tests have no blockers. Only the new fractional
wideband harness needed an explicit translation.
