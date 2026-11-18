# Pad-site primary ESD cell generator: READY for reuse (2026-11-18, pads / esdopt)

Generator: `$P/analog/pads/pad_site_primary.py` (new file, not committed). Read its docstring first.
State: standalone test cell builds with Magic DRC 0 and netgen LVS "match uniquely" (5 nd2ps + 5 pd2nw), LVS control fails
(reference with one diode removed: property error), clean under the provider rail cell, rail control fails
(a DVDD landing allowed on the DVSS band 126-133 is reported `WRONG BAND`). Integration into `pad_hspad` is in
`../hs/STATUS.md` (in progress when this was written; look there for KLayout precheck / latch-up results of the pattern).

## What it draws (one 75 um pad site, site-local x 0..75, y = depth from the die edge)
- Row 1 (y_dn = 82): `n_dn` x `diode_nd2ps_06v0` (25 um fingers, 6 um pitch) RIGHT of the family's Metal2 neck. PAD = Metal2
  plate from y 62 (overlaps the bond pad plate) to the bar; anodes -> Metal2 VSS bar with a Via2 / Metal3 landing inside the
  ring DVSS band 70-117.
- Row 2 (y_up = 113.5): `n_up` x `diode_pd2nw_06v0`. PAD bar comes from the neck; n-well rings -> Metal2 DVDD bar (y 119.3-148.7)
  with landings inside the ring DVDD bands 118-125 and 134-197; substrate rings -> tap bar, landing in DVSS, Metal2 strap to the VSS bar.
- Metal1 bridge under the neck from the VSS bar to the family's VSS Metal2 strip (cell-level netlist has one VSS).
- Layers used in the band: COMP / Metal1 / Via1 / Metal2, and Via2 + Metal3 ONLY as landings inside one rail band each.
  Nothing beyond x 74.0 (the rail cell has a p-tap frame on COMP / Metal1 at x 74.6-75.2, x -0.2-0.4, y 65.5-66.1).
- New net / label `DVDD` (Metal3 landing). The cell reaches the ring DVDD only when the rail cell lies over it; the two sites
  of a differential pad are joined on DVDD by the ring only. This is a NEW PORT of the pad cell (no routing: it lands on the ring).

## Options (`OPT` in the file; pass a dict with overrides)
| key | default | meaning |
|---|---|---|
| `neck` | (33.5, 41.5) | the family's Metal2 escape neck; fingers start at neck x2 + 4.5 |
| `n_dn`, `n_up` | 5, 5 | fingers per row. 8 um neck: max 5 (x 46..70). 24 um neck (25.5-49.5): max 3 (x 54, 60, 66); 12 um neck (31.5-43.5): 4 |
| `pad_bar` | 7 | PAD bar height um = PAD-side Via1 per finger (3..11); about 2.3 fF per um per row |
| `neck_extra_left` | 0 | widen the neck to the left up to the row-2 PAD bar (6 um: -0.19 ohm on the up path of an 8 um neck, about +22 fF) |
| `vss_strip` | (0.5, 25.5) | the family's VSS Metal2 strip (x1, x2) for the Metal1 bridge; `None` = no bridge. Shells before the hspad overlays have it at (6, 14) |
| `y_dn`, `y_up`, `y_vdd_top`, `plate_y`, `pitch`, `first_x`, `x_max` | 82, 113.5, 148.7, 62, 6, None, 74 | geometry; the generator refuses rows that overlap or landings outside the bands |

## Use in a composer (KLayout python inside the layout image, as `hs_pad_compose.py` does)
```python
import pad_site_primary as sp
sp.load_primitives(layout, prim_dir)                    # the two diode GDS of generated/protection-primitives (copied into the work dir)
opt = dict(sp.OPT, neck=(33.5, 41.5), vss_strip=(.5, 25.5))
for x0, pad in ((0., 'PAD_P'), (211., 'PAD_N')):        # site origins of the family cell
    info = sp.draw(layout, root, x0, opt)
    root.shapes(layout.layer(42, 10)).insert(k.DText('DVDD', k.DTrans(*info['dvdd_label'])))
    ref_lines += sp.reference_lines('S' + pad[-1], pad, 'VSS', 'DVDD', opt)   # D lines for the LVS reference
```
The family's own neck, bond pad plate and VSS strip stay as they are (the site redraws the neck from y 62 to the row-2 bar on top).
Whatever the family has on Metal1 / Metal2 / COMP in x neck_x2 .. 74, y 62 .. 149 of the site must be moved first
(hspad / rf / single-leg shells: nothing there; reference / usb / tx shells: check with `../hs/band.py`).

## Standalone build and checks (ONE job at a time)
```
scratch/pads-core/esdopt/site/build.sh <name> [--n-dn 5 --n-up 5 --neck 33.5 41.5 --vss-strip 0.5 25.5 --opt-json '{"pad_bar": 7}']
   -> site/<name>/pad_site_primary.gds, site-report.json (DRC, LVS, sha), reference.spice     (about 5 s)
scratch/pads-core/dock.sh "cd /work/esdopt/site && python3 railasm.py <pad.gds> <top> <out asm.gds> <x0> [<x0> ...] \
   && python3 railconn.py <out asm.gds> PAD=<label> VSS=VSS DVDD=DVDD [--x x0,x0]"
   -> rail cell placed over the pad cell at each site origin; per net the ring bands it touches; `RESULT clean` / `FAIL`
scratch/pads-core/esdopt/site/railcap.sh <dir with asm.gds>      -> Magic C extraction WITH the rail cell (asm_flat.spice), PAD* sums
```
`5LM_METAL_RAIL.gds` in this folder is the provider cell cut out of the PDK `gf180mcu_fd_io.gds` (texts dropped by railasm.py).

## Lessons from the pad_hspad integration (2026-11-18, details in ../hs/STATUS.md)
- Pad placed ON the provider rail cell, KLayout precheck main deck: the pad-site primaries add NO violation (they have no Via3 / Via4; the rail cell has no Via2).
  What does violate is every family shell's own VSS ring stack (2 x 2 um Metal2..Metal5 at site x 9-11, y 77.3-79.3): its Via3 / Via4 merge with the rail cell's
  cuts (V3.1, V3.2a, V4.1, V4.2a; 66 per site as counted through the hierarchy). With the site primaries VSS reaches ring Metal3 through the Via2 landings, so the
  composer deletes the stack's Via3 / Via4 / Metal4 / Metal5 and keeps Metal2 / Via2 / Metal3 (`hs_pad_compose.py`, search "ring stack"). Do the same in your family.
  Check: `../hs/checks_a.sh` builds the composite with `railasm.py` and runs `$P/verification/kl_block_drc.py --top asm`; rail-only baseline in `../hs/checks/railonly` (clean).
- `protection_device_audit.check(..., ring_wells=('DVDD',))`: the shared device audit otherwise refuses pd2nw wells that are not on ESD_RAIL.
- Benches must drive the new `DVDD` port (ring supply): an unconnected DVDD floats the up-diode cathodes.
- KLayout precheck of the hspad cell with the site primaries: main 0 / antenna 0; latch-up audit 0 um2 uncovered at 15 um; read-back LVS matches.
- Under-rail capacitance of one site (5 + 5 fingers, pad_bar 7), Magic with the rail cell: about +46 fF per pad on top of the 8 um neck's own 160 fF.
- Clamp voltage seen in simulation (ring model of ../hs/esd.py, typical): 2 kV HBM +6.1 V / -3.5 V against VSS, +4.4 / -5.5 V against VDD; the ring's RC clamps
  sit at 3.8 V DVDD-DVSS at 1.33 A, the 5 fingers drop about 2.4 V.

## Numbers so far (test cell s1: 5 + 5 fingers, pad_bar 7, 8 um neck, with plate / neck / strip stubs)
- Devices per site: 5 x nd2ps (22.5 um2, 51.8 um) to VSS, 5 x pd2nw to DVDD. Model junction C per finger at 0 V: 28 fF each;
  nd2ps at 0.4 V reverse about 24 fF, pd2nw at 2.9 V reverse (up-diodes now sit on the 3.3 V ring) about 19 fF. Model series
  resistance 8.9 ohm per finger (rs = 2e-10 ohm m2 / 22.5 um2): 5 fingers = 1.8 ohm, the dominant term of the clamp voltage.
- PAD wiring C of the test cell with the rail cell over it: 207.5 fF (VSS 154, DVDD 49), INCLUDING its plate stub and
  the 8 um neck stub up to y 154.7; the increment against a family cell is in ../hs/STATUS.md.
- Via cuts: 7 Via1 per finger on PAD, 22 on VSS (nd), 12 on DVDD + 10 substrate taps (pd); landings 2090 Via2 per site.
