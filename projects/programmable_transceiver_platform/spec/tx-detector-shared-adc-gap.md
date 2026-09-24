# TX detector conversion resource gap

Current executable state: TxCalibrationChip creates PowerDetector (or its impaired
readout subclass) with its own quantizer and latency. Resource10 is reported busy
under TX calibration owner11; resource0 remains assigned to its usual owner and
not busy. The saved resource audit proves discoverability of this experimental
extra converter, not use of the existing RF ADC. LoadedDetector changes the
analog voltage feeding the detector, but does not change conversion ownership.

The block diagram instead routes the analog detector output through the I-channel
diagnostic selector. AutomaticCalibrationChip already demonstrates quiet12-bit
conversion through convert_adc(), with actual transfer/reference loading and a
single pending result. Integrating TX detection should reuse that physical
conversion path, with an explicit power-to-voltage scale and allowed input range.
The detector's integration capacitor remains separate analog state.

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

Until implemented and checked, resource10 represents an experimental independent
monitor converter and its physical area/power is unclosed. Current waveform tests
must not be used as evidence that the intended shared-ADC architecture is complete.

Experimental implementation: SharedAdcLoadedTxChip replaces detector quantization
with convert_adc() at forced12-bit precision, then restores the normal mode.
Fullscale detector output maps explicitly to+0.8 normalized ADC input. Pending
results retain converted power through ADC latency. Resource0 exposes calibration
ownership; resource10 now denotes the detector front end. The first managed test
passes9 conversions, records2.49326pC total reference charge, rejects concurrent
capture and releases ownership after commit. Existing primary candidates are
unchanged. Analog mux loading/settling, readout impairments, in-flight cancellation,
phase-aware composition and full-chain quality remain open.
Evidence: connected-shared-tx-detector.json.


## Shared ADC in-flight cancellation — 2026-09-21

A reference-loss test interrupts a nonzero shared ADC conversion after four
samples. Pending result is removed, detector epoch advances0→1, ADC resource0
releases, and stale calibration commit rejects. Detector value0.0032840 and
network norm0.118264 are retained at the interruption boundary. Advancing past
the old conversion deadline creates no new conversion or reference charge and
cannot return the cancelled result.

The first test assumption incorrectly treated the serialized start reply as
preceding the second sample; SPI response time had already crossed it. The test
now waits for an actual pending conversion and checks that boundary, preserving
real transport timing. Evidence: connected-shared-tx-cancel.json. Recovery restart,
analog mux settling and phase-aware/shared-ADC full-chain quality remain open.

Mode0 loaded-pad quality remains running in session17675 with active CPU work;
no restart or quality verdict. New screen registration remains deferred until
that frozen-source run completes. Architecture remains partial.


## Shared ADC restart and network runtime profile — 2026-09-21

After cancellation during a nonzero conversion, reference restoration and fresh
coarse search permit a new TX calibration generation3. All9 new shared ADC
samples complete and commit; old generation1 remains rejected. Resource0 releases
and no pending result remains. Evidence: connected-shared-tx-restart.json. This
is quiet calibration restart, not active traffic recovery or phase-aware quality.

A separate100-step reconstruction/nonlinear-network profile (no changes to the
running waveform job) measured0.850s under cProfile. Detector power convolution
accounts for0.549s cumulative; network exponential response decomposition0.265s,
including6525 condition-number evaluations and6625 solves. The next runtime
improvement should preserve the exponential model and validate vectorized power
convolution/batched linear algebra against the current calculation, rather than
relaxing phase steps or dropping loading dynamics. Profile artifact:
evidence/loaded-network-profile.txt. These are instrumented local timings, not
an end-to-end speedup claim.

At that checkpoint, the mode0 loaded-pad run was tracked as session17675 and
registration was deferred to preserve its source snapshot. This historical
identifier does not establish a currently live process or a quality result.

A combined experimental SharedPhaseLoadedTxChip now composes shared maintenance
conversion, autonomous LO forcing, retargetable loaded network and host PHY.
Vectorization changes only detector integration, preserving the shared ADC
request/read callback. The managed calibration check asserts identity of the
controller, network and conversion detector objects. The historical launch
record is shared-phase-calibration-launch.json (session84313); the launch alone
is not a completed calibration/full-chain result or evidence of a live process.
