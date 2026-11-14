# Block deliverables

Every fabricated block delivers the same set of files and one evidence record, so that chip-top binding, full-chip
LVS and the readiness check can consume blocks without special cases. The tapeout tests are defined in
`tapeout-plan.md`; per-block state is in `tapeout-readiness.json`.

## What every block must do

- Be off at reset, with no current path from its island rail to any shared node while its island switch is off.
  Tolerate control inputs at 0 V while its island is off.
- Expose its bias currents and at least one internal node on the analog test bus, every digital status bit through
  the register file, and every clock through the `CLK_OBS` mux.
- Contain every bypass switch its fallback route needs; the loading of a disabled bypass counts against the block.
- Be compact: shared guard rings, abutted rows, MIM over devices. Report the area change against the die-fit
  ledger with every revision.

## Files

Each family lives in `analog/<family>/`:

| File | Content |
| --- | --- |
| `<block>.spice` | Transistor-level netlist, `gf180mcuD` devices only, top subcircuit `pt_<block>` |
| Layout generator (Python or Magic Tcl) | Reproducible layout |
| `generated/<block>.gds` | The layout that ships |
| `generated/<block>.ext.spice` | Extracted netlist with parasitics |
| `generated/<block>-lvs.txt`, `-drc.txt`, `-kldrc.json` | LVS, Magic DRC and precheck-deck KLayout DRC results |
| `generated/<block>-evidence.json` | Evidence record |
| `run_<family>.sh` | One command that regenerates the family |
| `README.md` | Current pass / fail / unverified state, pins, controls, test-bus taps |

Bulky output (waveforms, intermediate databases) goes to the repository `scratch/` directory and is not committed.
A pin name at the chip top is the published subcircuit's pin; `integration/top/masters.txt` reads it from there.

## Evidence record

Keys: `block`, `source_hashes`, `output_hashes`, `images`, `pdk`, `area`, `tests` (`safe`, `clean`, `observable`,
`fallback`, each with a `state` of pass, fail or open), `performance_vs_target`, `excluded_coverage`.

- **The record must match what ships:** `output_hashes` are the hashes of the published GDS and netlists. A record
  whose hashes differ from the files is stale.
- **`clean`** needs: Magic DRC with zero errors; KLayout DRC and antenna with the precheck decks on the exported GDS
  with zero errors (`make transceiver-block-kldrc BLOCK=<name>`); LVS on the GDS read back from disk, with device
  parameters compared and a failing negative control; and an extracted simulation of the basic function at every
  in-window corner: ss / ff / sf / fs and tt, 22 and 32 °C, 3.15 and 3.35 V. Use resistance-aware extraction where
  metal resistance is in a signal path.
- **Slow-corner results are reported twice:** at the untrimmed supply and at the trimmed supply (up to 3.50 V),
  with the minimum passing supply and, at ff, the maximum.
- **`safe`** is checked over the wide window: 0 to 3.63 V supply ramps, brownout, 0 to 85 °C.
- **Benches use real neighbours:** the extracted source and load (neighbour, route, pad, package), not ideal ones.
- **Limits do not follow results.** A missed limit is recorded in `performance_vs_target` as a miss.
- **Independent review** by a different agent, given the artefacts and not the conclusion, before a block is
  called done.

## GDS export rule

Export GDS with the analog image's Magic 8.3.678, not the canary image's Magic 8.3.623: the canary's GDS output
omits the high-resistance marker layer (62/0) on `ppolyf_u_1k` resistors, which would then be built at roughly a
third of the designed value. Call `cif ostyle gdsii` before `gds write`, because `drc style drc(full)` changes
Magic's output style. KLayout DRC on the exported GDS catches this class of defect, which is why it is part of
`clean`. Vendored cells keep their upstream GDS (`analog/core_support/UPSTREAM.md`).
