# RF model frequency coordinates

One programmable RF chain serves the radio targets in `contract.json` through
numeric carrier, gain, filter, direction and sample-clock settings. Protocol
names identify external FPGA waveform fixtures, not chip presets. The
[architecture inventory](analog-architecture.json) owns realizable settings;
[the model guide](../system_model/architecture_fast/README.md) owns executable
compositions and their limitations.

## Coordinate contract

Every bench must identify its complex-envelope frame frequency `Fframe`,
requested LO carrier `F`, and whether blocker frequencies are carrier-relative
or fixed laboratory frequencies. For desired baseband offset `b`, blocker offset
`d` relative to the carrier, and a fixed laboratory blocker at `B`:

- Desired envelope frequency is `F - Fframe + b`.
- Carrier-relative blocker envelope frequency is `F - Fframe + d`.
- Fixed laboratory blocker envelope frequency is `B - Fframe`.
- Its nominal downconverted frequency is `B - F`.

A carrier-centered bench has `Fframe = F`; a fixed-frame circuit experiment
must translate its sources when tuning. Do not impose the former 2.4 GHz frame
on every current waveform model. Reports must declare the convention. These
coordinate translations do not remove actual LO phase, noise or frequency
error. A fixed blocker that moves into the receive band during a retune must
remain there; it cannot silently become a different out-of-band test.

## Waveforms, sampling and gain

[`protocol_signals.py`](../system_model/connected/protocol_signals.py) supplies
FPGA-side modulation fixtures and independent symbol observers. They include
HE20 data blocks, GFSK, differential EDR symbols, half-sine O-QPSK and LoRa
chirps. Modulation fixtures are not automatically complete standards packets.
Packet benches such as [`ble_packet.py`](../verification/ble_packet.py) have
separate framing, acquisition and observer scopes. Do not transfer their
coverage to the other radio targets.

The external-LO clock path uses the selected divider and actual carrier to
set converter timestamps. FPGA resampling supplies modem coordinates.
Arbitrary fixture sample rates and chirp-rate representations do not qualify
new native converter clocks. Read legal divider, converter, PGA and filter
settings from the normative inventory; transported I/Q width is not ADC ENOB.
Standalone quantizer, fixed-clock or frozen-rail experiments are valid when
their simplifications are explicit.

Use limited early gain, channel filtering and then the main PGA. Gain range,
noise, early compression, filter internal headroom and ADC clipping must agree
with one enabled-stage/current inventory. A selectable cutoff is not a claim
of continuously tunable ideal filtering or a flat passband. Narrower bandwidth
only earns a sensitivity benefit when the model includes the corresponding
noise bandwidth and preserves the signal and acquisition interval.

Keep LO and host/sample clocks warm for same-channel RX/TX exchanges when the
selected timing contract requires it. Model switch/driver settling and FPGA
latency; do not substitute whole-engine startup for local direction control.
RF-to-wired changes remain stopped ownership transitions. Saved contexts and
ready events do not manufacture instantaneous lock or valid calibration.

## Observer limits

`TrainedBlockEqualizer` estimates frequency-bin response from known training
only, freezes it for payload, rejects missing training energy and invalidates
failed retraining. `repeated_training_frequency` estimates CFO from repeated
received intervals without injected-frequency knowledge. Neither observer may
receive payload labels or oracle phase correction.

For a repeated interval of duration `T`, the unambiguous CFO range is strictly
below `1/(2T)` in magnitude. Coherence alone cannot detect an integer-cycle
alias. Synthetic training is a useful control, but cannot establish acquisition
within a real protocol preamble. A fitted gain can hide absolute gain error;
independent clipping, headroom and power checks remain necessary.

## Blockers and complete-chain evidence

A mixer-output tone before the RX filter tests baseband selectivity. It does
not establish RF preselection, LNA/mixer compression, reciprocal mixing or
alias rejection. Strong-blocker evidence must include the relevant pre-filter
nonlinearity, delivered LO spectrum, filtering and converter behavior together.
Preventing ADC clipping does not prove that upstream distortion is acceptable.

An optional envelope limiter such as `y=x/sqrt(1+|x/Vsat|²)` is a mathematical
sensitivity case. Its internal voltage coordinate is not antenna power or a
GF180 IIP3/P1dB result; it omits AM/PM and memory. Keep its assumptions visible.
Use the selected electrical and packet compositions for joined evidence rather
than the retired ProtocolService projections. Current failures and missing
protocol qualification belong in [risk priorities](risk-priorities.md) and the
[closure inventory](mathematical-closure.json).
