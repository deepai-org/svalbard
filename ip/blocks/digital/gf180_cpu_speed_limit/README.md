# GF180 5 GHz CPU feasibility bound

This experiment measures an intentionally optimistic native-3.3 V inverter
and unloaded three-stage ring oscillator across three model environments. It is
a transistor-speed sanity check, not a CPU benchmark. Run `./run.sh` from this
directory; the pinned container flow copies the new result to
`scratch/gf180-cpu-speed-limit-last.json`. Promote reviewed evidence to
`result-last.json`.

The schematic omits layout parasitics, interconnect, clock distribution, supply
impedance, mismatch, and useful logic. Consequently, any realizable synchronous
CPU must be slower than these bounds.
