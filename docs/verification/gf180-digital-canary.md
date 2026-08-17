# GF180 digital canary

`make digital-pnr-smoke` runs two bounded LibreLane flows:

1. A four-bit counter closes from RTL through GDS.
2. OpenROAD replaces its flops, stitches one scan chain, and emits a structural netlist.
3. A strict normalizer removes intermediate tap/endcap instances and replaces the scan-output alias with a GF180 buffer.
4. Yosys proves the scan-disabled structural netlist functionally equivalent to the RTL counter.
5. The scan netlist closes through a second RTL-to-GDS flow.
6. Exhaustive one-cycle patterns must detect both stuck-at values on every derived cell-output fault site.
7. Exhaustive launch-on-capture patterns must detect slow-to-rise and slow-to-fall models on the same sites.
8. A pinned Quaigh image converts the normalized scan netlist to a full-scan model, generates SAT-backed stuck-at patterns, and re-simulates the emitted patterns for 100% unique-fault coverage.

Both layouts must pass nine-corner STA, routing and antenna checks, PDN connectivity, Magic and KLayout DRC, GDS XOR, Netgen LVS, and powered gate simulation. The scan simulation shifts `1010` through the chain and then verifies functional handoff.

The physical container is limited to two CPUs, 4 GiB RAM, and 512 processes. Quaigh is separately limited to one CPU, 512 MiB RAM, and 64 processes. Both run without network access and with read-only roots. Successful detailed outputs are deleted after their hashes and metrics are reduced to `scratch/digital-pnr-smoke-last.json`.

This qualifies a generic core-flow canary only. It does not qualify the public PDK for fabrication, project RTL, pads, SDF or at-speed delay, package-aware IR/EM, or provider precheck.
