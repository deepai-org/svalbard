# Fractional RF tuning: model envelope and open evidence

The programmable carrier interface accepts integer MHz targets from 2300 through
2500 MHz. Acceptance of a configuration is not proof of sustained acquisition,
RF waveform quality, or physical tuning range. The current implementation uses
actual integer feedback events, a second-order divider sequence, a compliance-
limited pump/filter model and a VCO with assumed linear frequency sensitivity.

The nominal model starts at 2.4 GHz × 0.96 = 2.304 GHz, with 200 MHz/V sensitivity
and a filter control envelope of ±1 V. Thus its static nominal range is 2.104 to
2.504 GHz. A 2.5 GHz target requires +0.98 V and leaves only 4 MHz of static tuning
headroom. This calculation does not account for transient overshoot, current
rolloff, noise, or lock qualification. It is a model constraint, not a GF180
measurement or an allowed device-bias statement.

The static test is `abs((target - free_frequency) / kvco) < control_limit`.
A target outside that range cannot be repaired by longer acquisition time or a
looser lock detector. Within-range points still require a dynamic test. The
qualifier must acquire by the declared deadline and remain qualified after first
lock; subsequent recovery cannot undo the full chip's earlier loss-of-lock fault.

Current screens:

- `fractional_grid_screen.py`: all 201 accepted MHz targets, nominal free frequency
  and initial phase, 40 us acquisition deadline and observation through 60 us.
  No oscillator noise or supply pulling; reference-edge observations are not an
  intra-reference phase-noise or waveform-quality measurement.
- `fractional_startup_screen.py`: 54 combinations spanning 2300/2437/2500 MHz,
  free-frequency offsets -8%/-4%/+2%, initial phase -0.4/+0.2/+0.4 reference cycles,
  and 0/20 kHz RMS finite-spectrum frequency noise. These are exploratory settings,
  not measured process corners or requirements for every fabricated die.

The startup run completed: 42 of 54 cases retained qualification. The other
12 are exactly the targets outside the assumed static tuning span: -8% free
frequency at 2437 or 2500 MHz, across all tested phases/noise settings. No
inside-span case failed that selected startup screen. The full nominal grid
subsequently found six holes: 2313, 2329, 2353, 2369, 2393 and 2409 MHz. Only
195/201 retained qualification. All six have denominator-40 divider patterns;
reference-edge frequency errors exceed the unchanged 4000 Hz limit (worst about
4431 Hz). Three briefly qualify and then lose lock. These failures are distinct
from the tuning-span problem. Lower bandwidth was tested without relaxing
qualification thresholds: both 325 and 300 kHz retained lock for all six holes
plus four control targets. Worst tail frequency error was 3578 Hz at 325 kHz and
2567 Hz at 300 kHz. The subsequent 300 kHz full-grid run retained qualification at all 201 targets,
and the calibrated combined wideband test passed at 6.50% / 6.75% error. The RF
candidate and profile now default to 300 kHz; the 350 kHz source/profile and
failure evidence are archived. The six unified continuous/recovery lifecycle cases also pass at the new default. Nominal
acquisition coverage still does not qualify every channel's RF waveform quality
or process/noise/loading envelope. Preserve unqualified points; do not replace the declared
tuning range with the passing subset to claim architectural completion.

If the evidence shows insufficient range/headroom, model an explicit coarse VCO
bank and its control/observation sequence, including phase/charge continuity,
settling and failed-bank search. Do not silently assign a different free-running
frequency to each requested carrier. The required bank coverage, resolution and
physical implementation must eventually come from transistor evidence.
