# Block diagram

`transceiver-block-diagram.svg` (and its PNG preview) is drawn by `generate_normative_diagram.py` from the block
inventory in `spec/analog-architecture.json`.

The diagram is out of date. It shows the inventory's blocks, which include merged and retired ones, not the
instances of the chip connectivity file, and the generator's consistency check fails on the current inventory
(a capability names a control field the inventory no longer has):

```sh
python3 projects/programmable_transceiver_platform/docs/diagrams/generate_normative_diagram.py --check
```

Until the generator is updated, read the chip structure from `spec/block-diagram.md` and
`integration/top/pt_chip.conn`.
