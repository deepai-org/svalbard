# Current fast whole-chip entry point

Use [architecture_fast/README.md](architecture_fast/README.md) and run
`python3 projects/programmable_transceiver_platform/system_model/architecture_fast/run.py`.
The connected functional scenarios pass in approximately 85 seconds on the
current machine. This is the fast architecture reference for further refinement;
physical feasibility and detailed-model closure remain separate. The notes below
are historical and describe earlier stages.

# Exploratory behavioral scaffold — not the chip implementation

This envelope scaffold was created before the user clarified that the requested
full-chip description should consist of actual PDK transistors and passives.
It is retained only as an optional test/reference experiment. Its simulated
connectivity is not implementation or feasibility evidence. Follow
../spec/executable-chip-model.md for the primary schematic-first workflow.

## Fast architecture model — renewed development

User approved a hierarchical fast-model workflow after pass521. Run:
`python3 projects/programmable_transceiver_platform/system_model/fast_screen.py`.
First executable increment sweeps72 RX complex-envelope cases without resolving
GHz carriers. Evidence: ../evidence/fast-system-screen.json. Gain, low-pass
bandwidth, clipping, phase sensitivity, reference modulation and quantization are
connected. Mathematical controls check filter settling and quantizer error and
monotonicity. This is a two-tone sensitivity experiment, not modem compliance.

All parameters currently are hypothetical scenarios. No transistor calibration
is claimed. In particular do not combine gain from a fixed-control receiver with
spur from a different autonomous fixture and label the combination characterized.
The report explicitly lists absent whole-chip paths; it cannot open any gate.

Next increments: connected reference/rail charge dynamics with signed loading;
TX/DAC envelope path; event-level wired serializer/channel/sampler/CDR; host rate
and queues from contract.json; oscillator acquisition and colored phase noise;
shared supply coupling and power/area budgets. Track provenance per parameter,
validate each model against short actual-circuit tests, then use fast sweeps to
select adverse cases for connected transistor verification. Keep cold startup,
real control generation and nonlinear boundary loading visible throughout.

Pass523 adds24 reference-charge cases alongside the72 original cases. Signed
charge impulses act on a differential reservoir and recover through finite R;
conversion samples the resulting span after an explicit decision delay. Positive
charge withdraws from the reservoir, negative returns charge. Analytic impulse,
zero-load and sign-symmetry controls pass. Signal-dependent charge is an explicit
hypothetical proxy, not an extracted SAR switching law. Two physical rails,
common-mode motion, amplifier poles/current limits and shared supplies remain
missing. This captures a causal charge-to-code dependency without claiming a
calibrated reference model. All96 cases execute in approximately0.2s.

Pass524 adds54 TX-to-RX envelope loopbacks: DAC quantization, reconstruction
filter, signed I/Q gain/phase imbalance, radial soft compression, external
attenuation, RX filtering and ADC. Amplitude sweep includes DAC overrange; both
converter clipping fractions are reported separately from fitted-gain EVM.
Identity, radial bound and phase-preservation controls pass. Parameters are
hypothetical. Loopback is an external test connection, not self-interference or
shared-supply coupling. No DAC spectral images, PA impedance, colored clock
noise or Wi-Fi modulation compliance is represented.150 total cases take~0.37s.

Pass525: `python3 projects/programmable_transceiver_platform/system_model/wired_screen.py`
adds108 wired-channel sampling scenarios at1.25/2.5Gb/s. Exact exponential
propagation through a hypothetical one-pole channel replaces fine timesteps.
Signed sampling offset, signed clock-period error and random timing jitter expose
margin loss;84 cases show errors in finite records. Constant-step analytic and
sign-reversal controls pass, as does an ideal-timing wide-band control. Clock
sampling is externally prescribed: no CDR exists here. Neither zero-error cases
nor this channel assumption qualify a link. Connect recovery and host queues in
subsequent passes; shared supply coupling remains absent. Evidence:
../evidence/fast-wired-screen.json. Runtime approximately0.28s.

Pass526: host_screen.py reads the actual contract and checks per-direction
aggregate capacity plus integer static slot requirements under declared ppm
margins. Existing Ethernet/RF and PCIe/RF modes fit this arithmetic with94.24 and
60.29Mb/s spare respectively; this does not qualify host electrical timing,
queues, CDC or scheduling. Crucially, fast_screen's40MS/s8-bit I/Q assumption
cannot run concurrently with raw2.5Gb/s wire traffic even on ddr156: shortage
259.74Mb/s. Use the declared20MS/s PCIe/RF mode for that combination, or explicitly
explore a new architecture; do not silently treat40MS/s as supported everywhere.
Actual waveform packing and event-level queues remain absent. Evidence:
../evidence/fast-host-screen.json. Each physical direction is budgeted separately.

Pass527: mode_screen.py uses contract sample widths/rates for both RF loopback
and transport arithmetic. Six cases execute.12-bit mode words do not establish
12-bit circuits/ENOB. This is common configuration, not connected queue dynamics.
Before spectral ranking, oversample reconstruction/receive filters and test
convergence: the current sample-grid recurrence changes its effective response
with sample rate. Evidence:../evidence/fast-mode-screen.json.

Pass528 changes loopback default to16x oversampled DAC holds with fixed
end-of-hold ADC phase. check_envelope_convergence.py compares1/8/16/32/64x at
both contract rates. Largest32->64 EVM change0.00156; no acceptance threshold or
waveform convergence claim. Coarse1x was optimistic. Use explicit refinement
for consequential ranking; quantization makes some trends discontinuous.150-case
and mode reports regenerated. Runtime rises modestly, still far below SPICE.

Pass531 adds12 simultaneous supply-to-phase/gain/reference sensitivity cases.
Current activity and impedance are hypothetical; signed VCO/gain coefficients
are swept, zero impedance reproduces uncoupled control exactly. No PLL feedback,
physical PDN or actual host/wired activity drives this model yet. DC frequency
shift accumulates in phase and can dominate EVM; do not interpret as intrinsic
phase noise.162 total cases take~2.75s. Shared-supply *qualification* remains absent.

Pass532 adds optional type-I linear phase feedback to voltage-induced frequency
error. Exact held-input integration is checked against constant-error solution
and signed/free-running controls. Eight scenarios sweep correction bandwidth and
VCO sensitivity sign. This is not the implemented type-II PLL; static phase offset,
no saturation/acquisition and uncalibrated coefficients remain explicit.170 cases
run in~2.8s. Replace this approximation with characterized loop dynamics before
using it to predict actual suppression or clock quality.

## Repeatable fast screening workflow

Run all eleven screens and their mathematical controls with:

```sh
python3 projects/programmable_transceiver_platform/system_model/run_fast_suite.py
```

The aggregate report is `../evidence/fast-suite.json`; individual reports retain
scenario results and limitations. A successful run means the scripts and controls
completed, not that every scenario meets requirements. The measured LO screen
requires the existing completed replay reports. Python and NumPy are required.

See [the fast feasibility workflow](../spec/fast-feasibility-workflow.md) for
calibration rules, selection of short transistor tests, and current risk priorities.
The aggregate report records coverage explicitly; execution success is not a
whole-chip feasibility verdict.

Use these results to prioritize short transistor experiments:

1. Sweep uncertain gain, reference loading, clock response and transport activity.
2. Check numerical convergence before ranking promising configurations.
3. Characterize the most consequential uncertain parameter in a small transistor
   fixture; preserve its bias, loading and stimulus scope alongside the result.
4. Update the behavioral model and select adverse connected transistor cases.
5. Reassess the leading risks before launching another expensive simulation.

Highest physical priorities remain autonomous LO disturbances through conversion,
ADC reference settling/loading, and actual wired clock recovery. Most model
parameters remain hypothetical. The suite has some connected paths, but lacks
complete shared activity, calibrated noise/nonlinearity and a physical package
model. Complete connected transistor schematic verification still precedes layout.

Clock alignment scoring uses an early training window and a fixed held-out mapping.
All 72 current idealized cases have zero held-out errors; 24 have ambiguous shifts.
No transmitted data enters clock feedback. This is neither a BER bound nor a
replacement for real framing, acquisition and oscillator/detector characterization.

`extract_lo_disturbance.py` is an optional characterization step outside the fast
suite: it reads and hashes the large existing baseline SPICE replay and produces
`../evidence/lo-disturbance-trace.npz` plus provenance/fit diagnostics. It retains
finite-time I/Q phase and distortion omitted by the fundamental-only sensitivity
screen. Do not tile this trace into a long simulation or treat zero-RF addition
as a validated receiver model. The extraction compares 100ps and 50ps grids and
checks known coefficient recovery; it does not characterize ADC sampling physics.

Pass543 adds `trace_conversion_screen.py` to the suite (now eleven scripts).
It requires the extracted finite LO trace and verifies its hash. Full waveform,
phase-preserving fundamental fit, and quantization-only results are compared at
32 sampling phases without extrapolation. The short record yields only 10/20 ADC
samples per phase; results must not be interpreted as modem EVM or worst-case
bounds. The fundamental approximation can be optimistic or pessimistic, depending
on rate and phase. Repairing the underlying LO path remains a physical priority.

`reference_window_trace.py` optionally extracts48 two-rail ADC decision windows
from the completed single-converter reservoir fixtures, checking waveform hashes.
Its compact trace preserves common mode as well as differential span and uses
time-weighted means on native adaptive timesteps. This is characterization data,
not a predictive reference model or simultaneous-I/Q result. It remains outside
the routine suite because it depends on archived transistor waveforms.
