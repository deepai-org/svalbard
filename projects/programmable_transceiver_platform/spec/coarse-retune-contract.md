# Coarse RF search and retuning contracts

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
