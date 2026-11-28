# pt_wired plan convergence (branch fp-wired, worktree /home/ubuntu/svalbard-wired)

## Diagnosis (2026-11-27)
- The plan model (evalp) placed macro pins in the plan order (assign_macro). The DG9-30 macro keeps its old pins: real sides W 324 / E 209 / S 305 / N 128, against the plan's S 528; 404 of 543 planned pins sit on another side.
- West pins must go south through the 25 um gap to pad_aux_clk / pad_ref (y 3052-3760). East pins go down an east side full of decap banks and small cells.
- Router check (plan-wired1 groute): 82 % of the overflow is vertical, in y 3050-3750 at x 300-1300 and x 2300-3400. Top nets: atb*_sw, c_bgap_trim, c_biasgen_*, c_slicer_trim_*. Metal1 demand is 0 even with SIG_M1=1.
- Model check: `REAL_MPINS=1 evalp` reproduces it (V cells over 100 %: 12 -> 165; H: 0 -> 34).
- Fix: macro 140 um east (x 1111, 2 x strap pitch). chan_macro_w 946-1111 and chan_macro_e 2787-2986, both without decap. rx_wtx_ext moved under pad_wtx_ext, clk_obs above it, auto cells and decap re-placed. Model result: V 13 / H 1 over 100 %, side gaps peak 0.59 / 0.58. Coordinator approved the shift (host-link bundle moves as one; report per-bit lengths before / after).

## wiredtx VSS tabs
chanO_1 and chanE_4 are joined inside wiredtx. A KLayout netlist probe of pt_wiredtx8.gds (M1-M5 and vias) puts all six channel tabs and the vss_plate (Metal4/5) in one cluster; a Metal3 net at the plate point probes as a different cluster (negative control). Script: wiredtx_tab_probe.py. No top-level tie needed.

## Runs
- fpw-1: first run on the shifted plan (abstract floorplan place route); macro supply OK VDD 23/23, VSS 22/22.
- fpw-1 groute: overflow 34152 -> 21799 (M2 4043 -> 84), wirelength 6.52 -> 4.97 m, congestion cells 8652 -> 555. 478 of the 555 are c_wiredtx_tr[*]: wiredtx TR* pins sit inside the cell (Metal3 at x 572.8-598.4, y 285-310 block coordinates, in the M5-free channel under the RAIL landing). Asked the coordinator for a ruling to move them to the top edge (block pin change). DRT still running.
- Next: read fpw-1 DRT; rebase onto fp-plan-code 4ea54716; host-link per-bit lengths (hostlink_len.py on routed.def, before = plan-wired2).
- wiredtx TR pins on the top edge (b9ade65d, coordinator ruling): DRC/LVS/antenna clean, DC op identical. Worktree runs need ASM_MOUNTS for the new GDS and report (tool.sh): see fpw-2's command in its run.out header / below.
  ASM_MOUNTS="$W/projects/programmable_transceiver_platform/analog/wired_tx/generated/fast:projects/programmable_transceiver_platform/analog/wired_tx/generated/fast $W/scratch/wired_tx/s13/top/out:scratch/wired_tx/s13/top/out"
- fpw-2: shifted plan + new wiredtx, started.
- 2026-11-28: committed f3166163 (check_padsup island feed + NEG + pad_tlp float), 2b4fd166 (top_lvs pad_tlp float, chip-gated; pieces_members), c147bfbe (tool.sh SLOT_CLEAN), e1caa16a (SLOT_CLEAN, bar-merged pins off routed net, RAIL_wired_rx bar). Uncommitted, pending fpw-11: RAIL_wired_tx bar bridge (block ties only, snapped), PAD_HOOK TMDS pin hooks. HOOK_W = 0.56 (branch default) on every fpw run.
- Open: io_bidir_16 PD/PU direct ties (fix 1b8dc15b, floorplan agent); VSS also touches pad_wire_tx ?DNV/DPV.SUB and por.?unlabelled (signoff counts as real short) — not yet investigated.
