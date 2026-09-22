# Pass 11: lumped signal-path impedance and clock-edge integrity

Two fresh nominal native-pad simulations retain the 8 mA candidate, 312.5 Mb/s/pin, 10 pF load, 3.3 V, 25 C and PRBS7 data. Each signal now has 1 ohm series resistance; clock inductance is 1 nH and data inductance is either 1 or 2 nH. These values are deliberately selected sensitivity points, not extracted package parameters. Receiver load remains a capacitor to ideal ground; the core and output supplies remain ideal.

| Data / clock series inductance | Minimum host-threshold margin | Received clock edge intervals | Data extrema in measurement region |
|---|---:|---:|---:|
| 1 / 1 nH | 0.665 V | 3.002–3.331 ns | −0.041 to 3.342 V |
| 2 / 1 nH | 0.674 V | 3.002–3.331 ns | −0.042 to 3.343 V |

Each case checks 20 bits against the same host boundaries and assumed ±0.2 ns aperture used in pass 10. No threshold failures occur. Slightly increased margin with added inductance does not establish a monotonic benefit; this is a short matched-pattern experiment with an unqualified receiver model. Voltage extrema are observations, not overshoot/reliability acceptance.

## Measurement correction

The previous host analyzer checked for missing clock edges but did not explicitly reject extra ringing-induced edges before pairing input/output crossings. It now rejects received edge intervals outside 0.5–1.5 UI (1.6–4.8 ns). This deliberately broad diagnostic screen is not an FPGA minimum pulse-width specification and cannot rule out every clock impairment. The new negative test inserts a short extra clock pulse and verifies rejection. Missing-edge and interior data-glitch tests continue to pass.

Six native-instance/extractor tests plus three host-analysis tests passed inside the pinned analog image. Reanalysis of all four saved pass-10 waveforms passes the additional interval check with exactly unchanged voltage margins; this is replay analysis, not four new simulations. The [recheck record](../evidence/weak-drive-clock-recheck.json) is tied to the raw archive hash in the pass-10 specification.

## Evidence and boundaries

Run `verification/run_signal_path.sh` from this project. The [retained report](../evidence/signal-path-screen.json) records source, deck, waveform and log hashes. Raw waveforms: `scratch/transceiver-signal-path-waveforms.tar.gz`. This characterization's successful execution does not assert signoff.

No receiver-clamp model, transmission-line model, rail/ground impedance, coupling, full-bank simultaneous switching, process spread or FPGA implementation is included. The package is still unselected. The prior current comparison remains a two-pad extrapolation; this PRBS-only path experiment does not update worst-case bank current.

Next introduce a shared supply/return network and then replace the pair with the actual switching bank. Keep explicit separation between chosen stress parameters and provider/assembly-qualified values. Preserve the full data interface and terminal count throughout this work.

Raw archive SHA-256: `9358e6eff098b33bfb7d45e682d2660e2e630aefd9f44a3f72b9d31263b2188d`.
