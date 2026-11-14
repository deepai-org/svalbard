# `spec/package-channel.json`: entries that are stale against `bond_map_current`

2026-11-14, pads owner sub-task (INT23-11). The file was **not** edited. Compared: `pins` of
`projects/programmable_transceiver_platform/spec/package-channel.json` (dated 2026-11-10) against
`spec/contract.json` `assembly_policy.bond_map_current`.

## 1. Stale entries

| `pins` key | Listed at (site, bond pad, contact) | `bond_map_current` has at that site | Where the signal should be |
|---|---|---|---|
| `RF_TX_P` | `inputs[3].pad`, 60, 22 | BB_Q_P | `inputs[1].pad`, bond 56, contact 26 |
| `RF_TX_N` | `inputs[2].pad`, 59, 23 | BB_Q_N | `inputs[0].pad`, bond 55, contact 27 |
| `BB_Q_P` | `inputs[1].pad`, 56, 26 | RF_TX_P | `inputs[3].pad`, bond 60, contact 22 |
| `BB_Q_N` | `inputs[0].pad`, 55, 27 | RF_TX_N | `inputs[2].pad`, bond 59, contact 23 |
| `WCLK_OBS` | `bidir[18].pad`, 24, 56 | USB_DN (`pad_wirepad`) | retired (PD22); the entry should be `USB_DN` |
| `WDBG_OBS` | `bidir[19].pad`, 25, 55 | USB_DP (`pad_wirepad`) | retired (PD22); the entry should be `USB_DP` |
| `ESD_TEST` | `bidir[25].pad`, 33, 47 | TLP/ESD test site (PD48b) | name only (ESD_TEST retired, PD35) |
| `WCLK_IN_P`, `WCLK_IN_N` | `bidir[16].pad` / `bidir[17].pad`, 22 / 23, 58 / 57 | still listed in `bond_map_current`, but deleted by user decision CP4-3 (TOP-22): the sites are free | remove, or rename once the sites are allocated |

All other `pins` entries agree (RF_RX, BB_I, REF_IN, AUX_CLK, WIRE_RX, WIRE_TX, WTX_EXT, WMON, north debug, host/south).

Entries derived from the stale ones:

- `xtalk_dB` (adjacent bond pads only): `RF_TX_P` lists `AUX_CLK_N` and `AUX_CLK_N` lists `RF_TX_P` (the real neighbour
  of AUX_CLK_N, bond 61, is BB_Q_P, bond 60); the `RF_TX_P/N` and `BB_Q_P/N` entries are on each other's sites;
  `BB_Q_N` lists `H2D_D[0]` as the neighbour of bond 55 (the real neighbour across the corner is ATB1, bond 54, and the
  signal on bond 55 is RF_TX_N; see section 1a); `WCLK_IN_N` / `WCLK_OBS` / `WDBG_OBS`; `ESD_TEST` / `WMON` (name).
- `sparams` of the four swapped west pins: computed with the pad capacitance of the wrong class on that site's
  geometry (rf_tx 1.0 pF on the short slot-B traces, debug 1.5 pF on the long slot-A traces).
- `intra_pair_and_group_skew`: `RF_TX` (+0.4 ps, bond 2.60 / 2.69) and `BB_Q` (+1.7 ps, bond 3.02 / 3.16) are swapped;
  `WCLK_IN` is a deleted pin.
- `placement_sweep.rf_tx_match`: uses the `RF_TX_P` geometry of bond 60 (trace 3.12 mm) instead of bond 56 (5.68 mm).
- `pulse_2p5G_and_312M.WCLK_IN_P`: deleted pin.
- Not affected: `lo` (REF_IN and AUX_CLK sites are right), `rf_rx_match`, `supplies_grounds`, `pdn`, `host_ssn`, `thermal`.

## 1a. Also wrong, found while comparing: the whole north edge is mirrored

All 16 north signals carry the bond pad, board net, contact and trace data of the mirror site (bond n listed as 92 - n):

| `pins` key | Site | Listed bond / contact | `bond-audit.json` and the October `packaging-audit.json` |
|---|---|---|---|
| `H2D_D[0]` | `bidir[26].pad` | 54 / 28 | bond 38, `/pad_37`, contact 43 |
| `H2D_D[1]` ... `H2D_D[7]` | `bidir[27..33].pad` | 53 ... 47 | 39 ... 45 |
| `H2D_CLK`, `H2D_D[8]`, `H2D_D[9]` | `bidir[34..36].pad` | 45, 44, 43 | 47, 48, 49 |
| `CLK_OBS`, `DBG_OBS0`, `DBG_OBS1` | `bidir[37..39].pad` | 42, 41, 40 | 50, 51, 52 |
| `ATB0`, `ATB1` | `analog[0].pad`, `analog[1].pad` | 39 / 42, 38 / 43 | 53 (contact 29), 54 (contact 28) |

Cause: `contract.json` `ordered_sites_by_side.north` is listed west to east (`analog[1]` first), and line 24 of
`channel_model.py` reverses only the west list (`south + east + north + reversed(west)`). Counter-clockwise numbering
needs north reversed too. `bond_audit.py` sorts by coordinate and is not affected; the north ground site (bond 46) is in
the middle, so a net check cannot see the error. `verification/audit_provider_cob.py` line 50 has the same expression.
Consequence in the file: `H2D_group` skew and every north `sparams` / `xtalk_dB` entry belong to the mirror pin, and the
corner pair in `xtalk_dB` is `H2D_D[0]` - `BB_Q_N` where the board has ATB1 - RF_TX_N.

## 2. Are the per-site numbers still valid?

Yes for everything that is geometry. `site`, `bond_pad`, `board_net`, `connector_contact`, `bond_mm`, `bond_nH_*`,
`trace_F_mm`, `trace_B_mm`, `vias`, `via_nH`, `connector_nH`, `connector_dist_to_gnd_mm`, `min_spacing_*` and `cob_delay_ps`
are computed per bond pad from the board file and stay with the site when only the name moves. So the corrected RF_TX
figures are today's `BB_Q` rows and the reverse. `LO-PAD-OPTIONS.md` reads the table by bond pad for that reason.

No for anything that uses the signal class: `cls`, `sparams` (pad C per class) and the partner names in `xtalk_dB`.

One more difference, not a naming issue: `bond_mm` here comes from the generator's own pad-centre estimate (die
3.93 x 5.12 mm, 211 um pitch, 75 um inset), not from the GDS openings. Against `BOND-AUDIT.md` (finger-centre landing)
it is 0.03 mm long on most pads and 0.17 mm long at the corner (bond 55: 3.16 mm here, 2.991 mm audited).

## 3. Generator and how to regenerate

- Generator: `scratch/cob/channel_model.py` (run-1 board, `raw.json` from `kparse.py`). It writes
  `scratch/cob/channel.json`. The signal-to-site map is the hard-coded `SIG` dict at lines 31 to 40 ("current v4 bond
  map"); only the host/south sites are read from `contract.json` (`candidate_signal_sites`).
- The other sections come from `placement.py` (`placement.json`), `lo_sweep.py` (`lo_sweep.json`), `lo_term.py`
  (`lo_term_skew.json`, the skew table) and `pdn_thermal.py` (`pdn_thermal.json`).
- **No script that merges these into `spec/package-channel.json` exists on disk** (searched the repository for its key
  names). The spec file was assembled by hand or inline on 2026-11-10 06:07, six minutes after `channel.json`; the keys
  were renamed in that step (`f_mm` -> `trace_F_mm`, and so on). The merge has to be repeated or scripted.

Edit in `scratch/cob/channel_model.py`:

```python
# line 24, was: order = sides['south'] + sides['east'] + sides['north'] + list(reversed(sides['west']))
order = sides['south'] + sides['east'] + list(reversed(sides['north'])) + list(reversed(sides['west']))
# line 34, was: 'RF_TX_P': 'inputs[3].pad', 'RF_TX_N': 'inputs[2].pad', 'BB_Q_P': 'inputs[1].pad', 'BB_Q_N': 'inputs[0].pad',
    'RF_TX_P': 'inputs[1].pad', 'RF_TX_N': 'inputs[0].pad', 'BB_Q_P': 'inputs[3].pad', 'BB_Q_N': 'inputs[2].pad',
# line 35: drop 'WCLK_IN_P': 'bidir[16].pad', 'WCLK_IN_N': 'bidir[17].pad' (CP4-3)
# line 36, was: 'WCLK_OBS': 'bidir[18].pad', 'WDBG_OBS': 'bidir[19].pad',
    'USB_DN': 'bidir[18].pad', 'USB_DP': 'bidir[19].pad',
# line 38: 'ESD_TEST' -> 'TLP_TEST'
# CLASS (lines 47 to 56): add a class for USB_DP/USB_DN (pad_wirepad, 2.35 pF like wired_rx), else they fall into 'debug' 1.5 pF
# line 295: remove 'WCLK_IN_P' from the pulse list;  scratch/cob/lo_term.py line 19: remove the ('WCLK_IN_P', 'WCLK_IN_N') pair
```

A more durable edit is to build `SIG` from `contract.json` `bond_map_current` (west, east, north) instead of the literal,
after `bond_map_current` itself is corrected for CP4-3 (it still lists WCLK_IN and LNA_SRC, TOP-22).

Then, one job at a time:

```sh
cd /home/ubuntu/svalbard/scratch/cob
python3 channel_model.py && python3 placement.py && python3 lo_sweep.py && python3 lo_term.py && python3 pdn_thermal.py
# then repeat the merge of channel.json / placement.json / lo_sweep.json / lo_term_skew.json / lo_bigC.json /
# pdn_thermal.json into spec/package-channel.json (no script; keep the existing key names)
```

Not run here (the task was not to edit or regenerate). The model has adjacent-pin crosstalk only; INT23-11 also asks
for pair-to-pair mutual inductance between non-adjacent RF/LO pairs, which is what `lo_pad_options.py` computes with
the M2/M3 filament model.
