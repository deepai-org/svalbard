# Complete LNP64 SoC

LNP64 makes the whole computer a recursively delegable object-capability
system. Programs, OS services, devices, and nested virtual machines use the
same protected Domains, typed resources, communication, lifecycle, and state
transfer mechanisms: every component is a Domain, every resource is an object,
and every authority is a capability.

Build that machine as a complete four-core system on chip for GF180MCU. The
design must execute the entire ISA, implement every architectural engine, boot
from SDHC or UART, use external SDR SDRAM, and connect to a PCIe Gen1 PHY through
PIPE.

This is a whole-system challenge. The hard gates require all 619 active
instruction identities, the three assigned-dark outcomes, SMP and domain
semantics, device integration, synthesis, routing, and nonnegative setup slack
at 200 MHz. Microarchitecture is open; performance and implementation quality
determine the score after correctness.

The package contains no RTL solution. Its tiny `solution/mini_candidate` fixture
is an explicitly incomplete negative control. The bundle freezes the ISA,
oracle, conformance images, platform contract, starter interface, coverage
ledger, and release verifier. It requires no sibling checkout; external sources
are public and commit- or digest-pinned.

```sh
make selftest
make visible OUTPUT=/app/output
```

`selftest` audits the authoring bundle. `visible` checks a candidate's file and
top-level interface shape; it is not the complete architectural verifier.

`source_lock.json` records one catalog-only normalization against the pinned
LNP64 commit: rights 21 and 23 follow the normative ISA prose (`STATE` and
`INSPECT`), and only bits 24–31 are reserved. Encodings and the 619/3
denominator are unchanged.
