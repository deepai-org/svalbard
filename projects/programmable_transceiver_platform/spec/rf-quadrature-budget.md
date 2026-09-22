# Quadrature sensitivity: planning calculations, not a performance specification

The split-LNA receiver has ideal-source nominal quadrature in its schematic
bench. That does not establish physical image rejection. This note makes the
phase/gain sensitivity explicit before choosing clock trim resolution or
accepting an I/Q topology.

For a single-frequency linear model, normalize the I phasor to 1 and express
the Q phasor as `j*g*exp(j*epsilon)`. Desired and image combinations are `I-jQ`
and `I+jQ` for the tested upper sideband. Their power ratio is:

```
IRR = (1 + g² + 2*g*cos(epsilon)) / (1 + g² - 2*g*cos(epsilon))
IRR_dB = 10*log10(IRR)
```

Here `g` is the Q/I amplitude ratio, and `epsilon` is deviation from 90 degrees.
For equal gains this reduces to `IRR_dB = -20*log10(abs(tan(epsilon/2)))`.
For a pure relative LO delay, `epsilon = 2*pi*f_LO*delta_t` in radians. These
are algebraic phasor calculations, not simulated or measured implementation
bounds. A ±5 ps delay at 2.4 GHz is ±4.32 degrees, giving about 28.47 dB in
the equal-gain ideal model.

| Illustrative ratio | Phase-only error magnitude | Equivalent delay at 2.4 GHz | Gain-only Q/I amplitude range |
|---|---|---|---|
| 20 dB | 11.4212° | 13.2190 ps | 0.818182–1.222222 |
| 30 dB | 3.6225° | 4.1927 ps | 0.938693–1.065311 |
| 40 dB | 1.1459° | 1.3262 ps | 0.980198–1.020202 |
| 50 dB | 0.3624° | 0.4194 ps | 0.993695–1.006345 |

The columns are alternative single-error limits, not allowances that can all
be consumed simultaneously. These rows are not selected receiver requirements.
Real errors include LO phase/duty/amplitude imbalance, branch gain and frequency
response, ADC aperture skew, DC offsets, feedthrough, nonlinear mixing and noise.
Static error, jitter and phase-noise spectra cannot be treated interchangeably.

The ±5 ps transistor experiment shifts Q and QB together, preserving their
complementary phase and pulse widths. Both signs need testing because the real
switched circuit need not behave symmetrically. It does not establish a bound
on manufacturing variation or verify duty distortion, supply coupling or a
physical LO-generation circuit. Single-tone complex image ratios must not be
advertised as broadband receiver rejection.

Before freezing the implementation, determine an application-derived required
image/noise/EVM budget, measure the physical LO/branch error range, and implement
sufficient analog trim or an exposed FPGA correction path. ADC headroom and
noise must remain acceptable before digital correction; post-processing cannot
restore clipping losses or remove independent noise. The current calibration
registers and sequencer do not yet prove those mechanisms exist.


## First physical-component candidate: passive RC splitter (passes276–277)

The PDK resistor/MIM candidate now has nominal AC evidence, not an adopted
architecture. At2.5GHz matched loading gives90degree phase but Q/I amplitude
ratio1.1713. Deliberately unequal25/100fF branch loads shift phase to81.833degrees;
reversing them gives98.167degrees. The nominal symmetry does not establish
loading tolerance. Next connect actual buffer inputs before choosing trim or
claiming usable LO drive. Ideal common-mode/source and small-signal assumptions
remain; capacitor/resistor process/mismatch and dynamic output timing are open.
[Unequal-load evidence](../evidence/quadrature-rc-asymmetric.json).
