# hookup.py: supply-hookup check

Checks every block VDD/VSS supply pin against the connection drawn for it. The plate, the Via4/Via3 arrays and the slotting are drawn by `island_trunks._plates` (the place stage, `PLATES=1`), and this tool reuses its limits. It reads the currents from `chips/<chip>/pin_currents.json` (`avg_ma`), the pin shapes from `<run>/masters.json`, and the drawn result from `<run>/place.json` (`grid_plates` and `direct_landings`).

Run it in the tool image, because the edge check reads the block GDS with KLayout. On the host without klayout it says GDS NOT CHECKED.

    R=/home/ubuntu/svalbard/scratch/integration/hk-rf      # place run (inputs copied from the owner's run)
    ASM_DATA=/home/ubuntu/svalbard ASM_RUN=$R ./tool.sh rf -c 2 bash -c "PLATES=1 python3 /asm/kl_place.py" > $R/place.log 2>&1
    ASM_DATA=/home/ubuntu/svalbard ASM_RUN=$R ./tool.sh rf bash -c "python3 /asm/hookup.py --selftest && python3 /asm/hookup.py rf /run --out /run/hookup_report.md [--gate]"

Limits (MANDATE 2): Metal1-4 20.9 mA/um, Metal5 45 mA/um, 5.6 mA per cut, IR 10 mV per connection. IR is recomputed here over the effective (slotted) width and taken as the larger of this value and the generator's.

Verdicts:
- **FIXED**: a plate was drawn and passes the checks.
- **OK**: below 0.5 mA, on a router hook; or a direct Via4 landing with enough cuts.
- **BLOCK EDIT**: the pin itself is the limit. Either its narrow side times the layer limit is below its current, it is Metal1/2 only, or it sits more than 30 um inside the cell edge. Or, for a pin with no landing, the block's own Metal4/5 lies within 0.7 um (the landing clearance) of the pin-wide corridor from the pin to the cell edge, on every layer a plate could land on (the pin's layer and the one above). The report names the blocking shapes in cell coordinates. The fix goes to the block owner.
- **FAIL**: the fix is outside the block but has not been made yet (no path, landing clipped, IR, cuts or width).
- **NOT IN RUN**: the instance is not a placed block in this run.

Plate width: `_plates` sizes the plate for EM, then widens it for IR (up to 160 um) and re-routes when the path's wire drop is over 7 mV. If the widened plate loses its landing, it retries at the EM width.

To fix a pin, change the floorplan or the plate generator, rerun place, then rerun this check. `--gate` exits 1 on any FAIL or BLOCK EDIT.
