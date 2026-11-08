# Block deliverable convention for tapeout freeze

Every fabricated block in `tapeout-readiness.json` closes its four tapeout
tests (see `tapeout-plan.md`) with the same set of artifacts. Uniform outputs let
top-level assembly, full-chip LVS and the readiness checker consume blocks
without per-block special cases.

## Design stance

The first die is risk-accepted. Prefer the **simplest robust circuit that
does the basic job at a nominal point** over a high-performance circuit that
might not converge in time. Prefer large margins to tight performance: wider
devices, generous bias, conservative swing and protection. The capability
targets in `mathematical-closure.json` stay as targets. Missing them is
recorded, not hidden, and is not a reason to hold a block back from freeze.

Every block must:

- Default to off at reset, with no current path from its island rail to any
  shared node while its island switch is off.
- Expose its bias currents and at least one internal node to the analog test
  bus through an `atb_tap` cell (`analog/island_support/`).
- Expose every digital status bit through the register file, and every clock
  through the `CLK_OBS` divider mux.
- Implement any bypass switch that its fallback route in `tapeout-readiness.json`
  names. Its disabled loading counts toward the block's budget.

## Directory and files

Each block or family lives in `analog/<family>/` with:

| File | Content |
| --- | --- |
| `<block>.spice` | Transistor-level schematic netlist, GF180 `gf180mcuD` devices only. Top subcircuit named `pt_<block>`. |
| `generate_<block>.py` or `.tcl` | Reproducible layout generator (Magic Tcl or Python driving Magic, as in `analog/pads/layout.py`). |
| `generated/<block>.gds`, `.mag` | Layout output. |
| `generated/<block>.ext.spice` | Extracted netlist with parasitic capacitance. |
| `generated/<block>-evidence.json` | Four-test evidence record (schema below). |
| `run_<family>.sh` | One command that regenerates everything inside the pinned images with `--network none`. |
| `README.md` | Honest pass/fail/unverified summary, ports, controls and ATB taps. |

Bulky output (raw waveforms, intermediate databases) goes to the repository
`scratch/` directory and is never committed.

## Ports

- Supplies: `VDD_<ISLAND>_SW` (switched island rail), `VSS`. Core-domain control
  inputs are level-safe: the block must tolerate controls at 0 V when its
  island is off, and `island_off` clamps its outputs to `VSS`.
- Controls: named after the register field in `spec/register-map.*`.
- ATB taps: `atb_<node>` outputs, connected through `atb_tap` cells at the
  integration level.

## Evidence record

```json
{
  "block": "lna",
  "source_hashes": {"lna.spice": "sha256:..."},
  "images": {"analog": "sha256:...", "digital": "sha256:..."},
  "pdk": "gf180mcuD <ciel revision>",
  "tests": {
    "safe":       {"state": "pass|fail|open", "cases": [], "notes": ""},
    "clean":      {"state": "pass|fail|open", "drc": {}, "lvs": {}, "extracted_nominal": {}},
    "observable": {"state": "pass|fail|open", "atb_taps": [], "status_bits": [], "clock_obs": []},
    "fallback":   {"state": "pass|fail|open", "routes": [], "bypass_loading_fF": null}
  },
  "performance_vs_target": [],
  "excluded_coverage": []
}
```

`clean` passes only when Magic DRC reports zero errors, **KLayout GF180 DRC
reports zero errors on the exported GDS** (the file the fab receives), Netgen LVS
reports a unique match, and an extracted transient or AC simulation shows the block's
basic function at the nominal point (tt, 27 °C, 3.3 V) **and** at the operating
envelope check points: tt/ss/ff × 22/32 °C × 3.15/3.35 V at the die. See the
operating envelope in `tapeout-plan.md`. Performance numbers are recorded under
`performance_vs_target` and do not gate freeze. Corners outside the envelope
(for example −40/125 °C or 3.0/3.6 V) are optional exploratory data. The
`safe` test is checked more widely: 0 V to 3.63 V supply ramps, brownout,
0–85 °C.

## GDS export rule

Export GDS with the analog image's Magic (8.3.678), not the canary image's
Magic 8.3.623. The canary's GDS output omits the HRES marker layer (62/0) on
`ppolyf_u_1k` resistors, which the fab would build at roughly a third of the
designed value. Call `cif ostyle gdsii` before `gds write`, because `drc style
drc(full)` changes Magic's output style. DRC, LVS and extraction may stay on
the canary image. KLayout DRC on the exported GDS catches this class of defect
(PRES.1, PRES.5, PP.9), which is why it is part of `clean`.

Exception: `analog/core_support/bandgap` uses the **vendored upstream GDS** as its
tapeout source. It has no `ppolyf_u_1k` resistors, so the
HRES defect does not apply. Re-exporting with Magic 8.3.678 alters the PPLUS
implant inside the PDK's fixed PNP cell and creates 20 KLayout PP.2
violations. KLayout DRC on the vendored GDS is 0.
