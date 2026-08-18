# Extracted phase-control composition

This flow composes the full-RC dual five-bit DAC with the full-RC phase
interpolator.  It verifies realizable digital control codes rather than driving
the PI with ideal voltage sources.

The calibration search exercises 263 code pairs at each of nine mixed GF180
MOS/resistor/supply/temperature/common-mode environments.  Five nested control
perimeters cover shifts in useful tail-device overdrive; electrically invalid
waveforms are rejected before phase selection.  Calibration retains 31 strictly
ordered codes nearest uniformly spaced targets over the measured phase span.

Run it with:

```sh
make phase-control-integration-smoke
```

The committed full-RC result completes 2,367/2,367 simulations and passes 9/9
environments.  Calibrated phase spans are 199.646--217.354 ps, worst target
error is 2.795 ps, and retained adjacent phase steps are 0.967--11.430 ps.
Depending on environment, 97--263 candidates meet the electrical requirements
before phase selection; this is why an uncalibrated universal code table is not
claimed.

This is a static transfer/calibration proof.  The actual controller/retimer,
phase observable, safe code-update behavior, clock-tree loading, jitter/noise,
shared reference generation, and closed-loop acquisition/tracking remain open.
