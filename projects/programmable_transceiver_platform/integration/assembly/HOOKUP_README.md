# hookup.py: supply-hookup check

Checks every block VDD/VSS supply pin against the connection drawn for it. The plate, the Via4/Via3 arrays and the slotting are drawn by `island_trunks._plates` (the place stage, `PLATES=1`), and this tool reuses its limits. It reads the currents from `chips/<chip>/pin_currents.json` (`avg_ma`), the pin shapes from `<run>/masters.json`, and the drawn result from `<run>/place.json` (`grid_plates` and `direct_landings`).

    python3 hookup.py --selftest                      # negative tests; exits 1 if any is broken
    python3 hookup.py rf    <place run dir> --out ../chips/rf/hookup_report.md    [--gate]
    python3 hookup.py wired <place run dir> --out ../chips/wired/hookup_report.md [--gate]

Limits (MANDATE 2): Metal1-4 20.9 mA/um, Metal5 45 mA/um, 5.6 mA per cut, IR 10 mV per connection. IR is recomputed here over the effective (slotted) width and taken as the larger of this value and the generator's.

Verdicts:
- **FIXED**: a plate was drawn and passes the checks.
- **OK**: below 0.5 mA, on a router hook; or a direct Via4 landing with enough cuts.
- **BLOCK EDIT**: the pin itself is the limit. Either its narrow side times the layer limit is below its current, it is Metal1/2 only, or it sits more than 30 um inside the cell edge. The fix goes to the block owner.
- **FAIL**: the fix is outside the block but has not been made yet (no path, landing clipped, IR, cuts or width).
- **NOT IN RUN**: the instance is not a placed block in this run.

To fix a pin, change the floorplan or the plate generator, rerun place, then rerun this check. `--gate` exits 1 on any FAIL or BLOCK EDIT.
