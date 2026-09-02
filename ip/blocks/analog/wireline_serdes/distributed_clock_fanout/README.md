# Distributed local clock fanout

This physical partition preserves the selected V7 fanout transistor ratios but
lowers its six branches as independently placeable macros. The
source-facing first stage accepts the long event-clock route; the final stage
is intended to sit beside its StrongARM or capture-clock consumer. This makes
the physical partition, rather than another transistor-size search, the
controlled variable.

`run_physical.sh` proves DRC, unique LVS, extraction, and artifact identity for
the sampler and capture branch leaves. It does not prove parent placement or
timing. Promotion requires two sampler and four capture branches co-placed
at the actual consumer pins, one routed-parent extraction, and replay of TT plus SS/hot before the
five-environment and PRBS gates.

The simulation view retains parameterized inverter multiplicities. Because
Netgen does not propagate those parameters through this reusable subcircuit,
`compile_branch.py --flatten-for-lvs` mechanically emits an aggregate-width
LVS view from the same immutable stage tuple. Both views are identity-hashed;
property errors are a hard failure rather than being hidden behind a topology
match.

The v1 pair lowering passed physical checks and isolated composition, but a
consumer-pin audit showed that the 176-um pair pitch could not place both final
drivers locally. V2 therefore exposes one functional branch per macro. A
minimal tied-off 1x dummy phase satisfies the current two-phase placer and is
explicit in schematic, LVS, and PEX; it is not part of the functional output.
Both v2 leaf types now regain zero DRC, property-clean unique LVS, and exact
composed timing. The sampler branch extracts to 1,000R/647C and the capture
branch to 278R/168C. `physical_result.json` retains their artifact identities.
`partition_contract.json` binds the existing 150 ps
high/low rail-valid composition requirement to the placement rule and forbids
reintroducing an interposed level receiver.

`run_composed_screen.sh` regenerates both leaves, verifies their identities,
wraps two sampler plus four capture branches behind the established six-clock
interface, and substitutes that exact isolated PEX composition between the
extracted event and lane parents. This is the TT/SS-hot electrical admission
gate for a routed distributed parent; the wrapper explicitly makes no placed-
interconnect claim.

The compact 72-um-pitch v2 exact screen passes 2/2. TT has at least 209.5 ps
high and 225.0 ps low rail-valid time. SS/125 C has at least 196.2 ps high and 169.2 ps
low; held-data differential is at least 2.806 V and maximum current is
113.3 mA. The slow/hot low interval therefore has 19.2 ps margin to the 150 ps
contract. `composed_screen_checkpoint.json` retains the exact PEX identities
and limiting measurements. This authorizes a compact routed-parent attempt,
not expansion to five PVT environments yet.

Publishing exact MAG pins also exposed the next partition boundary: an entire
sampler branch still overlaps the receiver banks when its output is aligned to
the StrongARM gate. The routed parent must therefore split the 6x/16x
predriver from the 32x final inverter (and the 4x from the 8x capture final),
placing only the final stage at the consumer. The compact whole-branch result
is the electrical reference for that cut, not a claim that parent placement is
already feasible.
