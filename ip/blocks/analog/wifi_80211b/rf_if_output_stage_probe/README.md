# Wi-Fi real-IF output-stage feasibility coupon

This narrow screen evaluates the output device bank required by the 12-bit
sampled-input thermal/settling budget. It sweeps a balanced 3.3-V CMOS
push-pull stage at its DC trip point and measures small-signal output impedance
at 100 MHz against the 0.379-ohm acquisition target.

It is not an IF buffer or a sampler. Feedback, input drive, linearity,
common-mode control, output swing, stability, capacitor routing, extraction,
and all ADC claims remain outside this coupon. A positive result only allows
the next step: a complete IF-driver schematic with those omitted mechanisms.

The current PVT coupon is complete but does not meet the target: even the
20-mm effective NMOS stage reaches 4.385 ohm at SS/hot. Simple linear width
extrapolation would require about 232 mm of effective NMOS width there. This
is not a layout estimate or an IF-buffer rejection; it rules out using an
unmodelled single inverter as the required driver. The byte-bound result is
[`output_stage_coupon_result.json`](output_stage_coupon_result.json).

The same run measures the common input-gate load with the output AC-clamped at
its DC trip point. The 20-mm SS/hot bank is 78.009 pF; the same linear
output-impedance extrapolation corresponds to 903.394 pF. This is not a
gate-drive current estimate because a real feedback driver determines its own
gate swing and switching waveform. It does establish that a complete candidate
needs explicit tapered/distributed gate drive rather than treating the output
bank as a lumped transistor symbol.

Run the PVT coupon with:

```sh
./run_probe.sh
```
