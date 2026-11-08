# TX detector shared-conversion requirements

The selected block diagram routes the analog TX detector through the I-channel
diagnostic selector into the existing RF ADC. The detector integration capacitor
is separate analog state; it does not imply another physical ADC. Quiet TX
calibration must exclude RF capture while it owns this conversion path.

Required behavior before claiming shared conversion:

- Reserve ADC resource0, DAC resource1 and calibration sequencer8 atomically;
  reject RX capture, conflicting diagnostics and other calibration while owned.
- Sample the detector's analog output via the actual ADC transfer/reference path;
  retain pending captured code across later analog switching and conversion latency.
- Keep detector readout gain/offset/curvature separate from ADC quantization;
  document voltage scaling without dividing by an oracle monitor transfer.
- Cancel pending conversions on epoch/reference loss, release ownership, and
  preserve analog detector/network charge. Do not leak stale codes to calibration.
- Include conversion reference charge and supply effects; analog routing/buffering
  must have an explicit load and settling model rather than an ideal zero-cost mux.
- Recheck calibration uncertainty and full loaded-pad quality with this path.

Complete selected-design integration remains unproven. Local detector, loaded
network and conversion fixtures cannot establish full-chain calibration quality.
The analog selector needs explicit capacitance, charge injection, buffer current,
input scaling and settling constraints. Conversion latency, reference charge,
reference loss, restart and cancellation must be exercised through the same
selected lifecycle and resource ownership used for payload operation.

Current completion decisions belong to [risk priorities](risk-priorities.md)
and the [closure inventory](mathematical-closure.json). Output isolation and
calibration uncertainty are specified in [TX output isolation](tx-output-isolation.md)
and [output-stage sensitivity](tx-output-stage-sensitivity.md).
