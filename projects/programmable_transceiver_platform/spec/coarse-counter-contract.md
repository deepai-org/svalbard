# Coarse VCO counter observation contract

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
metastability failure probability. Full live coarse retuning/recentering and
combined RF quality remain separate unfinished work.
