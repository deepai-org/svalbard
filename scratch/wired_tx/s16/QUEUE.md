# Session 16: publishing real-chain table on the current pt_wiredtx8 (state 2026-11-20 16:00 UTC; nothing published)

Table: `python3 table16.py`. Queue: `q16.py q16.jobs` (one simulation at a time, log `q16.jobs.log`). Stop: `touch STOPQ`
(the current job finishes first). Restart: `nohup python3 q16.py q16.jobs > q16.out 2>&1 &` (finished jobs are skipped; you can edit the job file while it runs).

## Netlist (net/, sha256 in net/SHA256)
* GDS snapshot `generated/fast/pt_wiredtx8.gds` (written 15:07, commit 8114f8d3; the tracked rc/lvs/spice files are byte-identical to the commit), sha 101f6002....
* Full extraction: `net/extfull16.py` (s14 extfull flow, flat, extresist tol 0.001), Magic nets extracted 1782/1798 (99.1 %),
  nets with R 1117 (XSER 550, XMUX 165, XAUX 3, top 399), 15665 R. Ports 124: same names and order as the drawn netlist and the C-only netlist. Device counts are identical (5279 X, 39 D).
* **`net/fixcap16.py` replaces s14 fixcap.py.** It uses the C-only flat extraction of the same GDS (`pt_wiredtx8.conlyflat.spice`) as the reference. It fixes two artifacts:
  1. Port nets: the root's substrate cap is written to VSS WITHOUT the **FLOATING tag, so s14 fixcap did not scale it (MAIN_CODE5 87 fF vs 14 fF).
  2. ext2spice extresist drops 6424 coupling caps to unnamed '#' nets (1.28 pF, e.g. OVN-a_51268_56632 25 fF).
  Result `pt_wiredtx8.fullfix16.rc.spice` sha 08338a4c...: every net's ground C and every coupling pair equal the C-only flat run; total 27.60 pF vs generator C-only 26.90 pF (+2.6 %). For comparison, s14-style fixcap gave 30.19 pF and raw 44.03 pF.
  Per-net example: PH0 35.5 fF (s14 fixcap 56.9; WT47 33.7-35.4), MAIN_P/N 128/129 fF (s14 fixcap 177/197).
  The s14 qE/qF netlists (fullfix 1fddfc3a / 72ba3f88) carry the same two errors.
* Sanity `sp16_ssp` (40 ns, ss pess. 3.15 V, 3.125 Gb/s, ring layout-11Nov pess., route 30 ohm/75 fF, pad=C): TX_RUN rises at 29.46 ns. Gate 1.55 V pp, pad 0.54 V pp, XE0 3.09 V pp, 51.8 mA. Run time 2100 s.

## Bench (chain16.py / cal16.py on s14 chain14 + blkcal, unchanged methods)
Ring route per phase: 30 ohm + 75 fF (TIM-23 nominal), split C/2 on each side of the R. One bound row at 45 ohm + 110 fF (`R_ssp3125_RT_bound`).
The ring tune (vctrl) comes from s12/tune.json; scoring and calibration use the measured period.
Corners: ss 32 C 3.15 V, ss pess. the same, tt 27 C 3.3 V, ff 22 C 3.35 V, sf/fs 27 C 3.3 V (vring per tune.json).
Calibration per condition: `_0` starts from the s14 codes. If its residual is > 8 ps, `_1` runs with its next codes. Rows take the codes that a cal verified <= 8 ps (`codes_verified`). If the residual is still > 8 ps after `_1`, rows take its next codes and are marked unverified.
0.48 Gb/s (2.4 core, n=5) and 1.25 Gb/s (2.5 core, n=2) use the 2.5 Gb/s cal of the same corner (labelled with `codes_cal`).
Pad option A: not published (txr/models holds only tx_rt/rh/zero; esdopt/tx a4/a5 are candidates). Before each job the runner logs a NOTICE if a new model or a txpad commit appears. Then add rows with `"pad_file": <path>` and `"S_": 1.0 / 0.6`.

## Queue order (q16.jobs, 34 cal lines of which about half run only if needed, 47 rows)
1. Step 3: ssp 3.125 (cal, C, RT, RT bound) -> ss 3.24 Gb/s -> tt 3.24 -> ss 2.7 (cal, C, RT each).
2. Step 4, pad=RT: 2.5 / 3.0 at tt/ss/ssp; 0.48 and 1.25 at ss/ssp/ff; 3.125 / 3.24 at ff/sf/fs.
3. Negative controls (pad=C, ssp 3.125): kill=3, stuck=2 (both must FAIL).
4. pad=C duplicates of the step-4 rows.
Durations (s14): cal about 3.9 h, row about 2 h. Step 3 takes about 34 h (up to 50 h if second cal iterations are needed). Everything takes about 6-9 days.

## State: queue STOPPED (coordinator ruling 2026-11-20)
The phase buffers' first gate becomes NAND(PH, SER_EN) on all eight PH inputs, so pt_wiredtx8 is rebuilt; the pin list is unchanged.
This snapshot was a dry run of the flow. c_ssp3125_0 was killed after 2 min and its files were deleted. STOPQ is set.
When the new GDS commit arrives:
1. Copy the GDS to net/ and update SHA256.
2. Run `python3 net/extfull16.py pt_wiredtx8`, then the C-only run (xk/conly/c.tcl).
3. Rename `_flat` in the netlists, then run `fixcap16.py` and `check16.py`.
4. Run the sanity: `chain16.py sanity <tag>`.
5. Delete STOPQ and start q16.py.
