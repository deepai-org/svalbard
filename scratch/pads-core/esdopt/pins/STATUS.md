# esdopt/pins: ASM-2 pin-move variants (2026-11-21). NOT published, NOT committed.

Pin-move only: same devices, same netlist. Added metal + moved labels in the top cell. Nothing existing is removed or moved
(the per-layer check `sub.py` shows "removed 0.000" on every layer). Bond openings are unchanged, the bbox is unchanged, the top cell name is unchanged.

## How it is built (and why not via the generators)
- `top_pins.py <family> <published.gds> <out.gds>` (KLayout, pad image b6027809...) post-processes the PUBLISHED GDS.
- rf_pair / rftxpad / single_leg: the generator `protection_pad_ss.py` can no longer rebuild the published cells. Its network input
  `scratch/pads-pd12/v2/macro/` was deleted (PC-51 cleanup), and the published cells were renamed and prefixed after generation
  (`pad_rf_pair__svrfpad__*`). So no generator option was added: a default build cannot reproduce the published GDS.
  The default check is replaced by `sub.py`: every published shape is still present (removed area 0 on every layer).
- pad_hspad a6: `hs_pad_compose.py` imports `pad_site_primary.py`. That file has changed since a6 (5ff82d2a -> 4a3b087f) and other
  agents are editing it, so a default rebuild is no longer guaranteed to give the a6 GDS. The same post-processor is used.
  Not done: a `--top-pins` option in hs_pad_compose.py (it can be ported from `top_pins.py`, all hspad coordinates come from config.json).
- Labels: the old inner / side labels of the moved ports are deleted. PAD_P / PAD_N already have Metal5 top-edge pins (unchanged), and
  their inner Metal3 duplicates in the rf shell are deleted. ESD_RAIL (internal) and DVDD (ring landing) labels are kept.
- hspad: the eleven Metal5 channel straps still reach the east edge (x 492) as unlabelled metal (they are not pins any more).

## Pins (all flush with the top edge; y = bbox top)
| Family | GDS | Top | sha256 | Pins: name, layer, x range (um), y (um) |
|---|---|---|---|---|
| pad_rf_pair | `scratch/pads-core/esdopt/pins/b/pad_rf_pair.gds` | pad_rf_pair | 56d1e67ae7d3e3462824f041c833229eaf0c6d69660f6cdb70628a3beee0dcb1 | ATB_ESD_RAIL Metal4 1.0-3.0; VSS Metal4 8.0-18.0; PAD_P Metal5 286-290 (published); PAD_N Metal5 302-306 (published); all at 912.91 |
| pad_rftxpad | `scratch/pads-core/esdopt/pins/b/pad_rftxpad.gds` | pad_rftxpad | 5bb3e71335d67b94f5763c1efd8934f2f88c29fc2369934a3aad793579d01f66 | same as pad_rf_pair (published geometry is identical, XOR 0) |
| pad_single_leg | `scratch/pads-core/esdopt/pins/b/pad_single_leg.gds` | pad_single_leg | 0a7b97d7d257963ed2c736a5fcae9a1ac5a7aa552b856d01b58af66906417f28 | ATB_ESD_RAIL Metal4 1.0-3.0; VSS Metal4 8.0-18.0; PAD_P Metal5 286-290 (published); at 912.91 |
| pad_hspad (a6 + pins) | `scratch/pads-core/esdopt/pins/b/pad_hspad.gds` | pad_hspad | 4d7fae991dc43e632d2847cafde64400228a35e54a2dc2d4f675269103ecbec5 | Metal4 at 912.91: TERM_TRIM0 418.0-419.0, TERM_TRIM1 420.6-421.6, TERM_TRIM2 423.2-424.2, TERM_TRIM3 425.8-426.8, VSS 428.4-431.4, RX_P 435.9-436.5, RX_N 441.0-441.6, VDD 446.1-449.1, TERM_ENABLE 450.7-451.7, TERM_VCM 453.3-456.3, VBIAS 457.9-458.9; PAD_P / PAD_N Metal5 286-290 / 302-306 (published); DVDD stays on the ring landings (Metal3, y 141.4) |

Routing:
- rf shell: ATB_ESD_RAIL runs from its Metal3 tip (91.6, 438) on Metal3 at y 436.5, west to x 2, then up a 2 um Metal4 riser at x 1-3.
  This column is empty from y 444 to the top. VSS runs from the network's Metal3 VSS band (y 770-800) up a 10 um Metal3 strip
  at x 8-18, with a Via3 array to the Metal4 pin. Both routes stay above y 435, away from the bond / rail band, and at least 260 um from the PAD Metal5 trunks.
- hspad: each strap is tapped in the free column x 418-459 (Via4), then a Metal4 riser runs up the channel (no Metal4 there) to y 633.5.
  From there a Metal5 riser goes to the top, through the empty column x 416.5-461. Metal4 pin with Via4 at the top.
  VSS / VDD / TERM_VCM are 3 um wide; RX_P / RX_N are 0.6 um with 4.5 um clearance and mirror-equal lengths; the other nets are 1 um.

## Checks (scripts in this folder; logs in chk/<fam>/)
| Check | rf_pair | rftxpad | single_leg | hspad |
|---|---|---|---|---|
| Magic DRC (flattened, `mx.sh`) | 0 | 0 | 0 | 0 |
| KLayout precheck (`kl_block_drc.py`) main / antenna | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Read-back LVS (`rb_lvs.py`, flat) vs published reference | match, unique (`rf-pair/reference.spice` pad_reference) | match, unique | match, unique | match, unique (`lvs-reference.spice` pad_hspad_flat) |
| Failing control (label swap) | VSS<->ATB_ESD_RAIL: mismatch | same: mismatch | same: mismatch | RX_P<->RX_N: mismatch |
| Device count (Magic) published / variant | 388 / 388 | 388 / 388 | 388 / 388 | 554 / 554 |
| rail_site_check | FAIL main 132 (V3.1 36, V4.1 36, V3.2a 30, V4.2a 30), antenna 0. The PUBLISHED cell gives the same 132, all at x 9-11 / 220-222, y 77-79 (the shell's ring VSS Via3/Via4 stack, off the rail via grid) | same as rf_pair | FAIL 88, same as published | PASS (0 / 0) |
| Latch-up audit (`pads-lu01/lu.sh`) | identical to published (0.0 um2 at 15 um) | identical | identical | identical |

Pre-existing rail_site_check FAIL on the rf shell families: the fix is the one hs_pad_compose applies under --site-primary, i.e. remove the
Via3 / Via4 / Metal4 / Metal5 of the ring stack at (10, 78.3) / (221, 78.3). That changes how VSS lands on the ring, so it is an electrical
change, outside a pin-move. Left for the option-A rebuild.

## Extracted C (Magic ext2spice cthresh 0, total C per net; `csum.py x/<f>_pub/... x/<f>_new/...`)
| Net | rf_pair / rftxpad pub -> new (delta) | single_leg | hspad |
|---|---|---|---|
| PAD_P | 455.54 -> 455.54 (0.00) | 439.41 (0.00) | 552.17 (0.00) |
| PAD_N | 427.41 -> 427.41 (0.00) | - | 542.57 -> 550.05 (+7.49; +3.5 of it is the TERM_TRIM0 riser over the N leg) |
| VSS | +34.0 | +34.0 | +100.4 |
| ESD_RAIL | +34.6 (VSS riser under the ESD_RAIL Metal5) | +34.6 | 0.0 |
| ATB_ESD_RAIL | 0.86 -> 66.4 (+65.5) | +65.5 | - |
| RX_P / RX_N | - | - | 74.3 -> 100.8 (+26.5) / 74.5 -> 100.6 (+26.1); P/N 0.2 fF apart |
| VDD / TERM_VCM / TERM_ENABLE / VBIAS | - | - | +47.1 / +82.2 / +50.1 / +41.2 |
| TERM_TRIM0..3 | - | - | +41.4 / +52.2 / +51.8 / +53.1 |
PAD limit (<= about 10 fF): PASS for every family.

## Files
`top_pins.py` (generator), `mx.sh` (Magic DRC + extraction), `rb.sh` + `flat_swap.py` (read-back LVS + control), `csum.py` (C),
`sub.py` (published shapes kept), `free.py` / `occ.py` / `nets*.py` / `probe.py` (free-space and net analysis used to place the routes).
Extractions: `x/<fam>_{pub,new}/*_flat.spice`. Build: `docker run ... python3 top_pins.py <family> <published gds> b/<cell>.gds`.
The GDS sha includes KLayout write timestamps, so a rebuild is geometrically identical but has a new sha.
