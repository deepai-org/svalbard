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
