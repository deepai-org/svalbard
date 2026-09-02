# Distributed local clock fanout

This physical partition preserves the selected V7 fanout transistor ratios but
lowers its branches as three independently placeable even/odd macro pairs. The
source-facing first stage accepts the long event-clock route; the final stage
is intended to sit beside its StrongARM or capture-clock consumer. This makes
the physical partition, rather than another transistor-size search, the
controlled variable.

`run_physical.sh` proves DRC, unique LVS, extraction, and artifact identity for
the sampler and capture branch-pair leaves. It does not prove parent placement
or timing. Promotion requires one sampler pair and two capture pairs co-placed
at the actual consumer pins, one routed-parent extraction, and replay of TT plus SS/hot before the
five-environment and PRBS gates.

The simulation view retains parameterized inverter multiplicities. Because
Netgen does not propagate those parameters through this reusable subcircuit,
`compile_branch.py --flatten-for-lvs` mechanically emits an aggregate-width
LVS view from the same immutable stage tuple. Both views are identity-hashed;
property errors are a hard failure rather than being hidden behind a topology
match.

The first physical lowering passes both leaves. The sampler pair is 1,900R /
1,272C extracted and the capture pair is 446R / 285C extracted. Both have zero
DRC errors and unique, property-clean LVS. `physical_result.json` retains the
artifact identities. `partition_contract.json` binds the existing 150 ps
high/low rail-valid composition requirement to the placement rule and forbids
reintroducing an interposed level receiver.

`run_composed_screen.sh` regenerates both leaves, verifies their identities,
wraps one sampler pair plus two capture pairs behind the established six-clock
interface, and substitutes that exact isolated PEX composition between the
extracted event and lane parents. This is the TT/SS-hot electrical admission
gate for a routed distributed parent; the wrapper explicitly makes no placed-
interconnect claim.

The first exact screen passes 2/2. TT has at least 199.6 ps high and 213.7 ps
low rail-valid time. SS/125 C has at least 186.8 ps high and 155.6 ps low;
held-data differential is at least 2.806 V and maximum current is 112.4 mA.
The slow/hot low interval therefore has only 5.6 ps margin to the 150 ps
contract. `composed_screen_checkpoint.json` retains the exact PEX identities
and limiting measurements. This authorizes a compact routed-parent attempt,
not expansion to five PVT environments yet.
