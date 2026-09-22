# Independent transmit observation and failure diagnostics

The TX observer forecasts a copy of the oscillator to the observation time and
rotates the actual reconstructed DAC envelope against an independent nominal
carrier. It never uses the receiver LO as its reference. The current modeled
output still excludes mixer/driver nonlinearity, I/Q mismatch and LO leakage.

The strict incremental-quality screen fits one complex gain on the first quarter
of samples and evaluates the remaining samples without refitting. The provisional
10% limit is unchanged. A passed receive test or correct TX sample count cannot
replace this measurement. Its ideal comparison shares quantization and the
one-pole reconstruction response, so spectral quality must be checked separately.

New TX runs retain time, complex outputs, baseband and LO-rotation arrays in NPZ
files alongside their JSON report. Use `tx_trace_diagnostics.py TRACE --output
REPORT` for offline analysis. It decomposes the held-out error into a gain shift
between training and validation and residual error within validation. The latter
uses an oracle gain only for diagnosis; it cannot make a failed gate pass. The
sum of the two squared components is checked against the original error squared.
A training-only frequency fit is also diagnostic and is not applied by the gate.

`tx_phase_window_plot.py` renders the retained quarter-fraction / 250-kHz traces
with training and signal-onset boundaries. It requires NumPy and Matplotlib.
The plotted traces show repeatable phase structure as well as an initial shift;
this alone does not attribute every feature to a specific circuit mechanism.

The host-preconditioning experiment compares equal 20-us extensions: quiet wait
versus 64 valid zero-allocation host frames ending at the measurement boundary.
Unallocated payload slots contain a fixed pseudorandom pattern and are discarded
by the actual receiver. They exercise modeled pad switching without delivering
RF/wired data. All 64 sequence numbers wrap back to zero before the real burst.
Assertions check active state, frame alignment, and unchanged sample consumption.
The observer excludes prelude samples, but no analog or oscillator state is reset.
Only the input host bus is preconditioned; this is not a claim that all supplies,
DAC activity or return-bus activity are already at steady state.

Preconditioning remains a diagnostic fixture, not a required operational sequence
or an adopted workaround. Full qualification retains startup cases unless an
explicit implementation contract and its costs are justified and tested.
