# SENSE level receiver

This role-specific variant restores the active-low event/fanout waveform as an
active-high `OUTN` pulse for the exact StrongARM SENSE input. It is lowered
deterministically from the qualified reference-receiver template by
`reference_level_receiver/compile_variant.py`; only the gain stage and required
OUTN driver are enlarged. OUTP remains physically present for layout-template
identity but is outside this role's functional contract.

The lowered cell is zero-DRC, uniquely LVS-matched, device-parameter identical,
and extracts to 37 MOS, 472 resistors, and 229 capacitors. The first
role-specific matrix jointly searches tail bias and reference offset. It covers
TT, FF/cold, FF/hot, and SS/cold, but deliberately remains failed at SS/hot.

The failure exposed an invalid environment assumption. The 290 ps
below-reference interval came from TT; a new exact SS/hot parent run measures
only 218 ps despite the upstream event block's roughly 522 ps nominal SENSE
width. Fine calibration, a proportionally larger matched front end, a
hysteretic restorer, a three-inverter active-low path, and a skewed two-stage
non-inverting path are retained as rejections. The latter toggles under the
exact StrongARM load but reaches only 0.422--2.891 V and recrosses in 721 ps.

`run_physical.sh` is intentionally still a failing promotion gate: after
physical legality it requires five-environment single-output coverage, selects
minimum-current controls, and then substitutes the exact StrongARM PEX. The
next circuit needs either a locally stored/stretched event or a producer-side
full-swing pulse contract. None of this is routed-parent, mismatch-yield, or
PCIe-compliance evidence.
