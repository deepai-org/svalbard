# hsfix2: pad_hspad pad-side / ESD path metal resistance (overlays in hs_pad_compose.py), build f6
Layout designer notes, 2026-11-18. NOT committed, NOT published. Continues `../hsfix/` (state f5, see its STATUS.md).
Edited: `$P/analog/pads/hs_pad_compose.py` only (new `ESD_OPT`, `esd_overlays()`, one call in the `if fix:` block of `assemble_stacked`,
docstring). Everything else is under `scratch/pads-core/hsfix2/` and new files `../hsfix/build/f6*`, `../hsfix/build/flegacy6*`, `../hsfix/res/*f6*`, `../hsfix/res/f5_esd_part.*`, `../hsfix/models/f6_r_*.spice`.

## Tools added here (all run one job at a time, through `../dock.sh` where KLayout is needed)
- `nets.py` / `q.py` / `nview.py` / `pts.py`: trace PAD_P, PAD_N, VSS, ESD_RAIL of a GDS (netres.trace) and list / draw shapes per net in a window.
- `spec2.py <config.json>`: netres spec = `../hsfix/spec_hspad.py` (not edited) + survey from the bond pad, per-row diode groups,
  and two new nets: `VSS_ESD` (ring VSS stacks at (10, 78.3) / (221, 78.3) vs array taps, canonical clamp sources, shunt clamp sources) and
  `ESD_RAIL` (pd2nw cathodes vs shunt clamp drains / canonical clamp drains). `r2.sh <build> [nets]` runs it -> `../hsfix/res/<build>_esd.json|.log`.
- `padcap.py`: PAD_P / PAD_N sum of the Magic C lines of `physical.spice` (same sum as `../hspad/netcap.py`) with partners.
- `viachk.py`: via cuts not covered by both metals, non-0.26 cuts, off-grid cuts.
- `b.sh <leg> <name>`: `../hsfix/build.sh` + removal of the root-owned `__pycache__` of an earlier build of the same name.
- `checks.sh`: copy of `../hsfix/checks.sh` that writes to `hsfix2/checks/` (the f5 records in `../hsfix/checks/` are left alone).
- `run_all.sh f6`: checks.sh, `../hsfix/rflow.sh f6 leg4`, `r2.sh f6`, legacy composition (`flegacy6`) + XOR against the published GDS.

## Log
- Baseline measured on f5 (`./r2.sh f5 VSS_ESD,ESD_RAIL` -> `../hsfix/res/f5_esd_part.json`), typ / high ohm:
  ring VSS stacks -> all 24 array p+ taps 20.82 / 57.70; -> shunt clamp sources 18.87; -> canonical clamp sources 25.84;
  pd2nw cathodes (16) -> shunt clamp drains 10.24; -> canonical clamp drains 19.82 / 48.44. PAD numbers of f5: read from `../hsfix/res/f5.json` (not rerun).
- Geometry facts found (pad_hspad um): the ring ties of VSS are 9-cut Via2 stacks; VSS strip -> Metal4 VSS trunk is ONE Via2 + ONE Via3 at (10, 400) and (221, 400);
  VSS Metal5 strip (136-140, 398-446) has ONE Via4 at each end; canonical clamp rail / VSS reach Metal5 / Metal4 through ONE Via3 / Via4 at (6.055, 715) and ONE Via3 at (12.905, 707);
  diode ring Metal1 (anode of nd2ps, cathode of pd2nw) is 0.23 um wide; the PAD_N Metal5 riser to the N leg is 4 um wide for 232 um (2.3 ohm).
- Rail cell check: `gf180mcu_fd_io__5LM_METAL_RAIL` has Metal1 only as a 0.62 um frame (y 65.5-66.1, 349.2-349.8, x -0.2-0.4, 74.6-75.2) and Metal3 on 93 % of the band.
  Metal1 was NOT used in the band (see findings).
- f6a (first full overlay, Metal4 + Metal5 row bars, 8 um feeders side by side): Magic DRC 0, LVS match, but PAD wiring C +93 fF per pad. Rejected. (build removed)
- Diagnostic builds f6t (two, removed): the VSS / ESD_RAIL overlays cost the pads about 10 fF; the diode-row structures 30-37 fF; feeders + trunk overlays the rest.
  Magic coefficients that matter (gf180mcuD.tech): Metal5 perimeter 30.4 aF/um, area 5.8 aF/um2; Metal3 10.1; Metal2 15.0; Metal1 29.3; adjacent-layer overlap 59 (Metal5/Metal4 39.4);
  Metal5 sidewall 114.9 aF um/um. Every new wire costs about 60 aF/um of fringe whatever its width.
- f6b: Metal3-only row bars (4.4 um), 5 um Metal5 feeders 16 um apart, PAD_N fed from the shell's own Metal4 bar (y 494-506), 3 um clearance to the PAD_P Metal5 trunk: +57.5 fF per pad. (build removed, `../hsfix/res/f6b_esd.*` kept)
- f6 = f6b + Via2 ties between the row bars and the array's own Metal2 bars (the single Via2 at the bus carried 3.0-3.8 %).
- First `./run_all.sh f6`: KLayout precheck main 1 (MSLOT5.1: my Metal5 rail link plate 74 x 44 um; Metal5 wider than 30 um is not allowed), everything else passed.
  Fixed in the composer (plate 28 um), f6 rebuilt, `./run_all.sh f6` rerun completely. Magic does not check MSLOT5.1.

# FINAL f6 (2026-11-18)
`../hsfix/build/f6/pad_hspad.gds` sha256 8c8e2533a57d5bc828ad382d658091080b1eb65da7163ad8aa4f50682530e22b (leg `build/leg4` unchanged),
`physical.spice` 83482787..., `hs_pad_compose.py` 54df77ab7f2acff50361c04cb3334c96a0b9919bfd97998711511ab019367fd5, models `../hsfix/models/f6_r_{typ,high}.spice` (27b35158... / 2e3f5d3d...).

## Results, ohm typ / high (f5 PAD rows read from ../hsfix/res/f5.json; f5 VSS / RAIL rows and all f6 rows run by me)
| path | f5 | f6 | target |
|---|---|---|---|
| PAD_P bond -> feed | 6.92 / 10.23 | 5.17 / 6.36 | 1.5 typ: MISS |
| PAD_N bond -> feed | 8.22 / 11.92 | 6.03 / 7.47 | 1.5 typ: MISS; P - N = -0.86: MISS (0.3) |
| PAD_P / PAD_N bond -> 25 heads | 8.57 / 8.98 (12.80 / 13.40 high) | 6.82 / 6.79 (8.93 / 8.94 high) | P - N 0.04: met |
| PAD_P bond -> 12 diodes | 20.81 / 50.18 | 5.18 / 6.66 | 1.0 / 2.0: MISS |
| PAD_N bond -> 12 diodes | 21.75 / 51.29 | 5.95 / 7.70 | 1.0 / 2.0: MISS |
| largest current share of one cut, bond -> diodes (typ) | 100 % (2 single cuts per pad) | P 3.5 % (array Via1 at (174, 460)), N 3.4 % (array Via2 at (190, 540)) | 3 %: MISS by 0.5 |
| each diode terminal from the bond pad (typ) | not surveyed | P 6.15-7.58, N 7.05-8.28 | within 2x of mean: met |
| VSS ring stacks -> all 24 array p+ taps | 20.82 / 57.70 | 2.08 / 3.75 | 1.0: MISS |
| VSS ring -> nd2ps anodes row 460 (P) / 540 (N) | 26.5 / 30.1 typ | 2.38 / 2.73 (4.61 / 5.03 high) | 1.0: MISS |
| VSS ring -> SUB rings (rows 500, 580, 620, 660) | 28.5-35.7 typ | 11.0-11.7 typ | not strapped (no ESD current; would cost pad C) |
| VSS ring -> shunt clamp sources / canonical clamp sources | 18.87 / 25.84 typ | 3.06 / 4.57 typ (4.54 / 6.87 high) | not a declared target |
| ESD_RAIL 16 cathodes -> shunt clamp drains | 10.24 typ | 0.46 / 1.00 | 1.0 typ: met |
| ESD_RAIL cathodes -> canonical clamp drains | 19.82 / 48.44 | 0.78 / 1.45 | met |
Single-cut vias carrying >= 50 % on any of these paths: none in f6 (f5: 2 per pad, 4-5 on VSS, 2 on the rail). The shell's old single cuts are still there, in parallel.
VSS ring ties: 9-cut Via2 stacks, 5.8 % per cut, cannot be changed without Metal3 in the band.
Pad wiring C (Magic C lines, `padcap.py`): PAD_P 482.3 -> 540.6 fF (+58.3), PAD_N 467.7 -> 525.1 fF (+57.4); of it PAD_P:PAD_N mutual 28.2 -> 36.4. Stopped at the +60 fF limit.

## Checks on f6 (all rerun on GDS 8c8e2533)
- Magic DRC 0, composer LVS match, device audit match: `../hsfix/build/f6/extract.tcl.log`, `layout-screen.json`, `../hsfix/build/f6.log`. Outline (-0.055, 0)-(492, 912.91).
- Read-back LVS "Circuits match uniquely", 508 / 508: `checks/rb/pos/result.json`; RX_P / RX_N swap "Netlists do not match": `checks/rb/neg/result.json`.
- KLayout precheck main 0 / antenna 0, clean: `checks/kldrc/pad_hspad/kldrc.json`.
- Latch-up: 0 um2 uncovered at 15 um: `checks/lu.json`. XOR vs published + pins: `checks/geo.txt` (band y < 396: Metal2 only, the two VSS strips; Metal3 / Via2-4 / Metal5 differences start at y 396.2).
- Legacy leg: `../hsfix/build/flegacy6`, XOR against the published GDS TOTAL 0: `legacy-xor.txt`.
- netres: `../hsfix/res/f6.json` (spec_hspad.py, via rflow.sh), `../hsfix/res/f6_esd.json` + `r2_f6.txt` (spec2.py).

## Why T1 / T2 are missed, and what it would cost
- The Metal2 escape neck (8 um x 355 um, 4.0 ohm typ) is in series with both paths and lies in the ring band where only Metal2 (or Metal1) may be added. It was NOT changed.
  Price in the cell's own extraction: 5.1 fF per um of extra Metal2 width, R = 32 ohm um / width. 1 ohm on the diode path needs a neck of about 0.5 ohm = 64 um wide = +285 fF.
  In the assembly the rail cell's Metal3 covers 93 % of the band at 59 aF/um2 (Magic coefficient, not extracted here): the existing neck already carries about 124 fF to the rails that no pad model has, and each extra um of Metal2 adds about 15 fF more.
  Metal1 under the neck (rail cell Metal1 is only a perimeter frame) would halve the band part for about +54 fF in the cell extraction (estimate, not built).
- Not run: ESD / AC / termination benches on the f6 models, any second-tool check of netres, assembly-level extraction.
