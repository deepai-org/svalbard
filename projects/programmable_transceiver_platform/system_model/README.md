# Behavioural models

Python models of the transceiver architecture. They read `spec/contract.json` and `spec/analog-architecture.json`
and exercise transport, resource ownership, clocking and signal-quality behaviour with numerical circuit
abstractions. They are not evidence for the transistor design: block results come from the extracted layouts in
`analog/<family>/generated/`, and chip connectivity from `integration/top/pt_chip.conn`.

| Path | Content |
| --- | --- |
| `architecture_fast/` | Whole-chip behavioural model: `behavioral.py` (event-driven transport, queues, ownership, epochs), `design_definition.py` (immutable design snapshot loaded from the two spec files), `acceptance.py` (fast acceptance set) |
| `connected/` | Reusable numerical primitives and scoped experiments (PLL, charge pump, SAR, reference, driver and supply models with their `*_screen.py` runners) |
| `*.py` in this directory | Stand-alone converter, reference and SAR screens |

Run from the repository root:

```sh
make transceiver-behavioral   # architecture_fast/behavioral.py; takes minutes
make transceiver-math-fast    # architecture_fast/acceptance.py
```

Open: the inventory consistency check that shares these inputs
(`docs/diagrams/generate_normative_diagram.py --check`) fails on the current `analog-architecture.json`, so the
model's agreement with the current block inventory is not established.
