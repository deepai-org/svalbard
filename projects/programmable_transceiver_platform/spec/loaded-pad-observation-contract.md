# Loaded pad observation contract

The phase-aware network stores complex RMS voltage envelopes in the fixed
2.412 GHz frame. Its input already includes autonomous oscillator phase and
branch phase. An independent observer at frequency f_obs must therefore use

    v_observed(t) = v_pad(t) * exp(j*2*pi*(f_network - f_obs)*t)

It must not multiply by the oscillator phase a second time, reconstruct output
from DAC/filter state, or replace the network voltage with a scalar isolation
transfer. Observation is read-only and requires network.time == chip.time.
The existing generic TX observer does not yet implement this branch.

Reference waveforms must declare the same RMS Thevenin-source normalization and
nominal passive output network. The network's roughly one-half source-to-load
voltage division is physical loading, not an unexplained modulator gain error.
Report pad voltage and gain explicitly; do not renormalize each observed trace
by an oracle monitor transfer. Internal detector power does not determine pad
phase or absolute radiated power.

Verification must include an independently constructed frame transform, a
negative control for double-applied LO phase, observation nonmutation, actual
pad-versus-reconstructed-source distinction, and aligned ideal/actual timestamps.
Full-chain quality requires this observer after managed calibration and stateful
switching; the prior scalar-isolation results do not transfer automatically.

Implemented in `system_model/connected/loaded_pad_observer.py`. The standalone
check passes direct physical-signal frame conversion at2412/2437MHz, complete
state nonmutation, actual-pad-value sensitivity, stale-time rejection and a
double-LO negative control. Report: connected-loaded-pad-observer.json. The
full-chip generic observer wrapper is not yet switched to this implementation.

`loaded_pad_quality.py` now composes the capture wrapper with real managed host
traffic, phase-aware loaded TX, and an ideal source/carrier driving the same
passive network. The initial mode0 run is pending; source hashes and its live
session are recorded in evidence/loaded-pad-quality-mode0-launch.json. The test
keeps the existing10% held-out TX/RX gates and records pad traces before asserting
success. This does not yet cover mode1, retuning or recovery waveform quality.

Parallel retuning investigation: the phase-aware network can keep its fixed
reference frame while physical LO frequency changes. RetunableLoadedTxChip
therefore removes only the historical fixed-frequency guard and retains the
managed coarse-qualification requirement. The first direct unqualified request
was rejected as required; a real2437MHz coarse search/state-continuity test is
running (retunable-loaded-tx-launch.json). No retuning pass is claimed yet.

The original mode0 run is now terminal/passed with unchanged launch source hashes: TX7.44323%, RX5.98506%. The earlier pending statements above are historical. Mode1 and shared-ADC composition remain unqualified.
