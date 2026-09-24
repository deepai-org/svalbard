# RF model frequency coordinates

One RF chain serves 20 MHz single-stream Wi-Fi including HE waveforms, BLE,
BR/EDR, 2.4 GHz O-QPSK/DSSS and LoRa through per-profile gain, filter and channel
contexts. The following frequency conventions apply to every waveform and hop.
Protocol envelopes and unimplemented status are recorded in `contract.json`.

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


## RF waveform and channel configuration

**Selectable bandwidth and gain.** Use coarse analog RC/gm-C bandwidth banks
   plus FPGA decimation/channel filtering; explore roughly 0.2/0.5/1/2/5/10 MHz
   complex-baseband half-bandwidth settings. These are exploration points, not
   LoRa filter cutoffs or flat-passband guarantees. Do not demand a continuously
   tunable 100:1 analog filter. Preserve the wide Wi-Fi path, DC-offset correction,
   programmable low-IF placement and optional DC-servo freeze for long chirps.

**Timed RF direction and gain control.** Keep LO/reference warm during packet
   exchanges, gate TX/RX locally, preload gain ramps and freeze AGC during payload.
   Model antenna-switch/PA settling and FPGA decision latency. RF-to-wired engine
   changes remain slow stopped transitions; RX-to-TX within one RF profile must
   not repeat whole-engine startup. Provide sample timestamps, overload flags,
   RSSI/energy measurements and channel-ready events using shared observation.


## Executable waveforms

`system_model/connected/protocol_signals.py` supplies FPGA-side modulation fixtures:
HE20 BPSK DATA with 256-point transforms and selectable guard interval; LE 1M/2M
GFSK and supplied coded-symbol streams; BR GFSK and EDR differential phase symbols
with RRC shaping; 802.15.4 half-sine O-QPSK supplied chips; and cyclic LoRa chirps.
These are analog stimuli, not complete packets or on-chip modem implementations.
HE preambles/FEC/pilot polarity, BLE FEC/whitening/packet framing, the 802.15.4
DSSS mapper and LoRa coding/header processing remain external and unverified.

Independent FFT, phase-discriminator, differential-phase, staggered-chip and
dechirp observers recover noiseless symbols and detect deliberately corrupted
waveforms. `ProtocolService.project_receive/project_transmit` provide fast,
frozen-reference/rail reductions using the canonical RX bank, reconstruction
filter, quantization and TX impairment parameters. These projections do not use
a perfect LO correction or fit away phase noise. They are not end-to-end EVM/PER
or an alternative full-chip composition. Chirp-rate samples are a modulation
representation; they do not qualify a new native converter clock.

`install_external_waveform` connects immutable sampled envelopes to the canonical
external RX route; the scheduler splits at sample boundaries. Absolute carrier
coordinates, actual autonomous LO phase, nonlinear input terms, loaded RX filter
and shared ADC reference remain in the path. `protocol-model-coupled.json` checks
2 ns nonzero excerpts and one diagnostic ADC/DAC operation per RF profile during
startup. It explicitly rejects normal RF transport before coarse acquisition;
the diagnostic converter format does not set lock/ready or bypass that interlock.
These probes check connectivity, not useful packet reception or spectral quality.

Channel contexts store requested carrier/gain plus a profile epoch and invoke
the existing coarse-retune service. They cannot manufacture instant lock or
calibrated trim validity. Fast warm hops, filter-bank switching, continuous packet
RX/TX and independent packet error measurements remain open.

Waveform references: [Bluetooth radio PHY](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-62/out/en/low-energy-controller/radio-physical-layer-specification.html),
[Bluetooth EDR radio](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core_v6.3/out/en/br-edr-controller/radio-physical-layer-specification.html),
[TI CC2420 modulation](https://www.ti.com/lit/ds/symlink/cc2420.pdf),
[MathWorks HE RU allocation](https://www.mathworks.com/help/wlan/gs/he-mu-transmission.html),
and [Semtech CSS description](https://www.semtech.com/lora/what-is-lora).
The fixtures deliberately implement only the modulation scope stated above.

### External FPGA receiver reduction

`TrainedBlockEqualizer` in `system_model/connected/protocol_signals.py` is a
generic frequency-domain observer for cyclic-prefix blocks. It estimates each
requested bin from known training samples only, rejects unilluminated bins or
near-zero gain, freezes the estimate for payload observation, and invalidates
old estimates if retraining fails. It receives no payload labels.

The current HE20 experiment supplies two synthetic training blocks followed by
ten independently generated payload blocks. This is not a standards preamble.
FFT size, guard length and bins are parameters; this adds no protocol-specific
silicon. Fixed sample timing and frozen rails remain explicit assumptions. The unequalized failures remain in the report alongside held-out
equalized EVM and symbol errors. EDR3 amplitude probes likewise leave chip
defaults unchanged; finite recovery is not an operating-envelope guarantee.

The generic `repeated_training_frequency` observer estimates fine CFO from two
received repeated intervals; it receives neither the injected frequency nor
clean transmitted samples. The HE20 diagnostic uses three repeated synthetic
blocks, discards the first for filter settling, corrects carrier phase, then
trains the existing equalizer before observing ten independent payload blocks.
At 20 MS/s and a 272-sample repetition, the unambiguous offset is strictly below
±36.765 kHz. High coherence does not detect integer-cycle aliasing: an explicit
alias test preserves this limitation. Missing-energy and incoherent-training
inputs are rejected. Actual packet detection, coarse CFO, sampling-clock
recovery, standards preambles and coupled-clock packet operation remain open.

### Shared bandwidth, gain and sample-clock configuration

Reuse the existing I/Q chain with selectable RC filter banks, reference-clock
divisors and PGA trims. The behavioral target has 5/10/20/40 MS/s conversion,
12-bit I and Q transport independent of rate, RX gain 0.5–2, RX one-sided cutoff
0.1–9.157407 MHz and TX cutoff 0.1–20 MHz. Both cutoffs must be at most half
the selected sample rate. These are bounded model parameters, not demonstrated
continuous physical tuning ranges or anti-alias guarantees. Physical implementation
should use a small calibrated bank of overlapping settings, not a new general DSP.

External fixtures exercise HE20, BLE 1M/2M, BR and both EDR orders, 802.15.4,
250-kbit/s proprietary GFSK, and 2.4 GHz LoRa at 203.125/812.5 kHz bandwidth.
Zigbee and Thread reuse the 802.15.4 PHY; this does not implement their stacks or
Matter. LoRa here does not extend coverage to sub-GHz bands. Gain is independent
of modulation. Narrower bandwidth may reduce integrated noise/blockers in silicon,
but the present fixed input-noise hypothesis does not claim that sensitivity gain.
The causal waveform model applies chosen filters, gain, quantization and sampling;
the same rate drives finite host queues. No on-chip decimator or resampler is added.
Timing recovery, packet acquisition, blocker/alias rejection and filter settling
remain unqualified, and existing waveform failures remain visible.

### Blocker evidence and filter-order gap

The fast model injects a baseband tone at the mixer output before the RX filter,
with power referenced to the desired input RMS. A 3 MHz tone on the selected
10 MS/s BLE path is tested from -20 to +40 dB at 1 and 4 MHz RX cutoffs.
The equal-power case produces bit errors even with the narrower one-pole filter;
stronger tones clip the ADC. This is evidence that cutoff selection alone does
not establish blocker rejection. Reintroduce a reduced multipole filter response
and frontend compression/intermodulation before sensitivity or adjacent-channel
claims. The injected tone is inside the sampled Nyquist interval; this screen
does not represent RF aliasing, LNA/mixer saturation or standard blocker masks.

A fast fifth-order Butterworth comparison now confirms that filter order matters:
at 1 MHz cutoff the selected BLE fixture tolerates the 3 MHz +20 dB tone without
bit errors or ADC clipping, versus failure with one pole. EVM remains about 11%;
no support claim is upgraded. Retain the multipole RX target, and validate its
selectable pole frequencies, group delay, noise, linearity and area before
substituting it into all whole-chip configurations.

### Pre-filter frontend compression

The blocker diagnostic optionally applies `y=x/sqrt(1+|x/Vsat|^2)` to the
combined desired/blocker envelope before RX filtering. Vsat is an internal
modeled voltage coordinate, not antenna power or a GF180 IIP3/P1dB claim. The
limiter has unity small-signal gain and preserves phase; it omits AM/PM and
memory. Sweeps at Vsat=0.5/1/2 V show that the five-pole filter can prevent ADC
clipping while frontend compression still corrupts the desired signal. With
a +20 dB blocker the 0.5 V case has 27/64 bit errors and no ADC clipping.
Use this to require frontend linearity/headroom evidence, not to choose a
transistor voltage target without mapping the actual internal signal levels.
