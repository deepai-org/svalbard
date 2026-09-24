# RF tuning envelope, coarse search and retuning contracts

## Fractional tuning evidence and range limits

This retained screen describes the fine-loop model that motivated explicit coarse
search. Its numeric range, defaults and results belong to that model revision;
they do not bound every later clock configuration or establish device coverage.

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

## Finite counter observation

The experimental coarse-startup profile observes a divide-by-16 oscillator
counter as a coherent 12-bit snapshot. The counter wraps modulo 4096. A captured
value arrives after two configured control-clock periods; this delivery delay
is represented by explicit start-wait/end-wait states. The count refers to its
capture event, not its later publication event.

Each endpoint may contain the current prescaled count or its immediate
predecessor. Those two choices are swept independently. For a capture interval
T, differencing ideal floor counts contributes less than one count of frequency
error, and differing endpoint ages contribute at most one additional count.
The conservative frequency error bound is therefore 2 × 16 / T, plus the
separate bank-settling and declared bounded-noise terms. At T = 2 us, the counter
term is 16 MHz. No division by elapsed reply/transport latency is used.

The declared source ceiling is 3 GHz. The observation window is rejected if its
maximum possible count increment plus two uncertainty counts reaches 4096.
This makes a single modular difference unambiguous within the declared envelope;
it does not detect arbitrary multiple wraps outside that envelope. The chip
constructor rejects configured oscillator/bank/fine-control/noise envelopes
above that ceiling. An observed modular interval larger than its declared bound
fails the search, restores the saved bank and leaves the pump held.

Captured but unpublished values have a search-generation tag. Abort, reference
loss and epoch cancellation discard the pending snapshot. Starting a new search
cannot reuse it. Rollback bank settling also gates the next quiet calibration
window; releasing the digital owner does not imply instantaneous analog settling.

These are mathematical interface assumptions. A transistor/digital implementation
must provide coherent snapshot capture, the freshness bound, delivery timing and
counter-frequency capacity. The model does not qualify a CDC circuit or its
metastability failure probability. These counter assumptions alone do not qualify managed retuning/recentering
or combined RF quality; the retuning contract below adds separate obligations.

## Managed retuning candidate

`CoarseRetuningChip` extends the startup-only candidate with a timed passive
fine-filter recentering state. It does not replace the main calibrated candidate
until recovered signal quality and its broader lifecycle envelope are checked.

The host must stop/quiesce traffic, acknowledge host abort and drain, and rearm
receiver detection when it was aborted. `rf_coarse_start` accepts a new carrier
only in the existing quiet reset state with a present reference. Active retuning
is rejected; this is a service interruption, not a phase-coherent frequency hop.

For an already used fine loop, the controller holds the charge pump and closes
two modeled shunts to the fine-control center. It waits 12 times the declared
400 ns upper RC bound. No capacitor voltage, phase, or accumulated charge is
reset. Under the assumed matched-RC passive network, the maximum absolute node
voltage contracts by at least exp(-12). The frequency-error allowance therefore
includes Kvco times the original compliance limit times exp(-12); the controller
does not measure hidden capacitor voltages to decide readiness.

After the guard, the existing finite-counter search chooses a bank and waits for
bank settling. Only a qualified result releases the fine PLL. Mode configuration
then runs normal fine-clock acquisition. `rf_coarse_status` adds state 9 for
centering and retains the existing busy/qualified/bank fields. The same resource
owner excludes calibration throughout centering and counted search.

Abort, epoch change, and reference loss cancel pending centering/search events,
open the centering shunts, restore the previous bank with its settling guard, and
leave the fine pump held. An interrupted centering guard does not confer readiness;
a retry repeats the full timed guard. Analog state continues through cancellation.
Bank rollback is not restoration of the former filter voltage or former lock.

The matched shunt RC constants, bounded resistance, abstract voltage center,
monotonic coarse bank and finite counter observation contract are mathematical
assumptions. Actual switch charge injection, common-mode rail work, mismatch,
phase noise and package coupling require subsequent circuit evidence. This
candidate introduces neither additional package pins nor a hidden external loop
filter. Full-chip waveform quality after retuning remains a separate requirement.
