"""top/REPORT.md from top/out/report.json.  python3 mkreport.py"""
import json
from pathlib import Path
H = Path(__file__).resolve().parent
r = json.loads((H / 'out' / 'report.json').read_text())
m = json.loads((H.parent / 'mux3/out/report.json').read_text())
a = json.loads((H.parent / 'mux3/aux/out/report.json').read_text())
v, z, d, kf = r['verify_from_disk'], r['zones_y'], r['decap'], r['keep_free']
W, Ht = r['size_um']
Y0, Ym = r['seam_um']
L = []
A = L.append
A('# pt_wiredtx8 block top layout: report of the layout sub-agent, 2026-11-18\n')
A('Generator `analog/wired_tx/pt_wiredtx8_layout.py`; reference `wtx8_top.netlist()` (FROT = 2, with the new `wtx8_decap` instance).  Children as published in `generated/fast`: '
  '`wtx_ser8d` (not rebuilt, read), `wtx_mux8`, `wtx8_aux` (both rebuilt today, see `../mux3/REPORT.md`).  Everything below was run by me on the final GDS unless marked.  Nothing committed.\n')
A('## 1. Outline and area\n')
ser = 744.12 * Y0
up = W * (Ht - Ym)
dec = (d['box'][2] - d['box'][0]) * (d['box'][3] - d['box'][1])
bars = 4 * 12.0 * (Ht - r['bar_y'][0])
A('| part | um | um2 |\n|---|---|---|')
A(f"| **bounding box** | **{W} x {Ht}** | **{r['area_um2']:.0f}** (0.351 mm2) |")
A(f"| wtx_ser8d (bottom) | 744.12 x {Y0} | {ser:.0f} |")
A(f"| seam (all top-level signal wiring and the supply rails) | {W} x {Ym - Y0:.2f} | {W * (Ym - Y0):.0f} |")
A(f"| wtx_mux8, origin ({r['mux_origin'][0]}, {r['mux_origin'][1]}) | {m['size_um'][0]} x {m['size_um'][1]} | {m['area_um2']:.0f} |")
A(f"| wtx8_aux side cell, origin ({r['aux_origin'][0]}, {r['aux_origin'][1]}); its tap row lies inside the mux outline | {a['size_um'][0]} x {a['size_um'][1]} | {a['area_um2']:.0f} |")
A(f"| decap rows, box x {d['box'][0]}..{d['box'][2]}, y {d['box'][1]}..{d['box'][3]} | | {dec:.0f} |")
A(f"| four supply edge bars (above the seam) | 12 wide each | {bars:.0f} |")
A(f"| **keep-free rectangle** x {kf['box'][0]}..{kf['box'][2]}, y {kf['box'][1]}..{kf['box'][3]} | {kf['box'][2] - kf['box'][0]:.2f} x {kf['box'][3] - kf['box'][1]:.2f} | **{kf['area_um2']:.0f}** (0.0227 mm2) |")
used = r['area_um2'] - kf['area_um2']
A(f"| used = bounding box - keep-free | | {used:.0f} |\n")
A(f"The keep-free rectangle (right of the mux) has no shape of this block on any layer; above it runs the POST header strap (Metal5, y {r['header_strap']['y'][0]}..{r['header_strap']['y'][1]}), "
  'below it the seam.  About 0.008 mm2 of gaps around the mux / aux / decap are neither used nor offered.\n')
A(f"**The seam is {Ym - Y0:.1f} um high ({W * (Ym - Y0) / 1e6:.3f} mm2): stated as a problem.**  From the bottom: zone B {r['tracks']['B']} Metal4 tracks (40 D pins of ser8d sit on its TOP edge and leave "
  f"sideways, 8 F, SERQ, word clock), zone S 17 tracks (8 phase tracks + VSS between), the phase pins, zone M 33 tracks (two legs per phase, every leg between VSS tracks), zone T 36 um of supply rails "
  f"with {r['tracks']['T']} Metal2 tracks under them (32 trim bits, 16 codes, statics).  Levers, not pulled (sizes are my estimates): ser8d data pins on its bottom edge (-18 um), phase nets without equal-C padding or with one "
  'VSS track per pair (-25 um), trim bits brought out on the mux side.\n')
A('```\n y um\n'
  f" {Ht:7.2f}  top edge = pad edge: MAIN_P / MAIN_N / POST_N / POST_P risers of the mux (Metal5), header VDD straps (Metal5, 7.5 um)\n"
  f" {Ym:7.2f}  bottom edge of mux and aux side cell (their signal pins: Metal3)\n"
  f" {z['vdd_rail'][0]:7.2f}  VDD rail Metal4 10 um            | zone T: Metal2 tracks of the nets that only have pins above\n"
  f" {z['vss_rail'][0]:7.2f}  VSS rail Metal4 25 um            |\n"
  f" {z['M']:7.2f}  zone M: phase nets pin -> mux, out-and-back legs, 0.9 um pitch\n"
  f" {z['pins']:7.2f}  PH0..PH7 pins: Metal5 pads 1.2 um, x = 412 + 4 k\n"
  f" {z['S']:7.2f}  zone S: phase nets pin -> ser8d, 1.0 um pitch\n"
  f" {z['B']:7.2f}  zone B: Metal4 tracks, 0.84 um pitch\n"
  f" {Y0:7.2f}  top edge of wtx_ser8d (pins: Metal3-5 stacks)\n```\n")
A('Vertical wires in the seam: Metal3 from pins above, Metal5 from ser8d pins below (they cannot meet).  The mux is centred on the phase pin row (mux origin x 242.1; block centre 372).\n')
A('## 2. Checks on the final GDS\n')
A(f"`generated/fast/pt_wiredtx8.gds` ({r['sha256']['pt_wiredtx8.gds']}), analog-image export, read back in the fresh directory `top/verify`.\n")
A('| check | result |\n|---|---|')
A(f"| Magic DRC `drc(full)` | **{v['magic_drc']}** |")
A(f"| KLayout DRC (`sak-drc.sh -k`) | **{v['klayout_drc'].get('violations')}** |")
A(f"| LVS vs `wtx8_top.netlist()` (hierarchical, device parameters compared) | **{v['lvs']['summary'].splitlines()[0]}**  top level: {'; '.join(v['lvs']['counts'])}; property errors {v['lvs']['property_errors']} |")
nm = {'neg_ph0_ph1_swapped_at_mux': 'PH0 / PH1 swapped at the mux', 'neg_stream_rotation_plus_one': 'stream rotation off by one (FROT 3)', 'neg_ovp_ovn_swapped_at_mux': 'OVP / OVN swapped at the mux'}
for n, x in v['negative_controls'].items():
    A(f"| negative control: {nm[n]} | {'FAILS as required' if x['fails_as_required'] else '**MATCHES**'}: {x['summary'].splitlines()[0]} |")
A(f"| Magic `antennacheck` (whole block, after extraction) | ran: {v['antenna_magic']['ran']}, violations **{v['antenna_magic']['violations']}** |")
A(f"| flat C netlist: port order = `wtx8_top.PORTS` | {r['c_netlist']['ports_ok']} |\n")
A('The three negative controls are changed REFERENCE netlists (the XMUX line), not changed layouts.  No separate KLayout antenna deck was run.\n')
A('## 3. Phase nets PH0..PH7\n')
A('Each net: Metal5 pin pad in the seam; pin -> mux on two Metal4 legs (out on one track, back on the next but one, Metal3 jumper) so that the drawn resistance pin -> mux pin is the same for all; '
  f"pin -> ser8d on one Metal4 track lengthened by a dummy end to {r['ph_lmax_um']} um for all.  Every Metal4 leg lies between two VSS tracks (tied to each ser8d VSS strap they cross).\n")
A('| net | wire C, top-level wiring alone (fF) | of which to VSS | to VDD | to each neighbour phase (largest two) | whole block, wire C (fF) | of which ser8d-internal | R pin -> mux (ohm, drawn) | R pin -> ser8d (ohm) | Metal4 to mux / to ser8d / dummy (um) |\n|---|---|---|---|---|---|---|---|---|---|')
for k in range(8):
    n = f'PH{k}'
    t, f, p = r['wire_c_top_only_fF'][n], r['wire_c_fF'][n], r['ph'][n]
    nb = sorted(((x, c) for x, c in t.items() if x.startswith('PH')), key=lambda kv: -kv[1])[:2]
    A(f"| {n} | **{t['total']}** | {t.get('VSS')} | {t.get('VDD')} | {', '.join(f'{x} {c}' for x, c in nb)} | {f['total']} | {f.get('ser8d')} | {p['r_pin_to_mux_ohm']} | {p['r_pin_to_ser_ohm']} | "
      f"{p['metal4_um']['to_mux']} / {p['metal4_um']['to_ser']} / {p['metal4_um']['of_which_dummy']} |")
tt = [r['wire_c_top_only_fF'][f'PH{k}']['total'] for k in range(8)]
ff = [r['wire_c_fF'][f'PH{k}']['total'] for k in range(8)]
rm = [r['ph'][f'PH{k}']['r_pin_to_mux_ohm'] for k in range(8)]
A(f"\n* Top-level wiring: {min(tt)}..{max(tt)} fF, **spread {max(tt) - min(tt):.1f} fF** (target 3).  Measured on the top-level shapes alone (children removed, same extraction).")
A(f"* Whole block (top wiring + mux internal 10.9 fF each + ser8d internal + coupling to the children): {min(ff)}..{max(ff)} fF, spread {max(ff) - min(ff):.1f} fF; the difference to the line above is mostly "
  "ser8d's own phase wiring, which differs by 5 fF between phases (12.3..17.3 fF to ser8d nets) and is not mine to change.")
A(f"* Drawn resistance pin -> mux pin: {min(rm)}..{max(rm)} ohm, spread {100 * (max(rm) - min(rm)) / min(rm):.2f} % (limit 5 %); computed from lengths and sheet resistance (Metal3 / Metal4 0.4 um: 0.225 ohm/um, Metal5 0.44 um: 0.091 ohm/um), vias not counted (same number on every net).")
A(f"* **Against the ring owner's 60 fF per phase in total: the wiring alone is {min(ff):.0f}..{max(ff):.0f} fF, about twice the whole budget before any gate is counted.**  "
  f"{r['ph_lmax_um']:.0f} um to ser8d (its phase pins are spread over 650 um) + about 135 um to the mux, each with a VSS track on both sides (0.18 fF/um).  What would cut it: no equal-C dummy ends (-40 % of the "
  'ser8d branch on average, then unequal), a wider gap to the shields (costs seam height), ser8d phase pins nearer its centre, or a buffer per phase at the pin.')
A('* The pins are in the seam (Metal5 pads), not on a block edge: the ring has to come over the block.  They sit under the mux (x 412..440), 233 um below the top edge where the MAIN / POST risers end.\n')
A('## 4. Stream nets F0..F7 and the other internal nets\n')
A('| net | Metal4 track (um) | drawn R (ohm) | wire C top-level alone / whole block (fF) |\n|---|---|---|---|')
for k in range(8):
    n = f'F{k}'
    A(f"| {n} | {r['f_wires_um'][n]} | {r['rc_netlist']['f_ohm'][n]} | {r['wire_c_top_only_fF'][n]['total']} / {r['wire_c_fF'][n]['total']} |")
A('\n**Not equal** (26..304 um): one straight track per stream from the ser8d pin to the mux slice that takes it (FROT = 2); I did not pad them.  They lie in zone B, below the lowest VSS track of zone S.  '
  'SERQ, ENM (to the mux ENM and ENP pins), EXT, OVP, OVN, ENMAIN_G, ENPOST_G run between aux and mux / ser8d on single tracks.\n')
A('## 5. Block pins\n')
from collections import Counter
cnt = Counter((x[0], 'left' if x[1] < 10 else 'right' if x[1] > W - 10 else 'inside') for x in r['pins'].values())
A('`top/out/report.json` -> `pins` has every pin (layer, x, y).  ' + '; '.join(f'{n} on {l} {s_}' for (l, s_), n in sorted(cnt.items())) + '.')
A(f"* left / right edge at seam height (track ends; Metal4 y {z['B']:.1f}..{z['S']:.1f}, Metal2 y {z['T']:.1f}..{Ym:.1f}): D0..D39 (nearest side), WORD_CLK40, the 32 trim bits (left for the slices on the left half, "
  'right otherwise), codes, statics, IBIAS, MAIN_BIAS, POST_BIAS, ATB_*, TX_RUN, WTX_EXT_DATA.  MAIN_BIAS / POST_BIAS therefore leave on the left edge, not towards the pad: say if they should go to the top.')
A(f"* TAP_P / TAP_N: Metal4 on the left edge at y = {r['pins']['TAP_P'][2]} / {r['pins']['TAP_N'][2]} (12 um below the top edge).")
A('* PH0..PH7: Metal5 pads in the seam (section 3).  MAIN_P / MAIN_N / POST_P / POST_N: the mux risers on the top edge; nothing of the top level runs over them, the header straps end 1.0 um beside the outer risers '
  '(they must reach the header rail segments there), the bridge between the two headers is 8 um from the nearest riser.')
A(f"* VDD / VSS: Metal5 bars 12 um wide on both sides, x {r['supply_bars']['VSS'][0]} / {r['supply_bars']['VDD'][0]} (left) and {r['supply_bars']['VDD'][1]} / {r['supply_bars']['VSS'][1]} (right), y {r['bar_y'][0]}..{r['bar_y'][1]} "
  '(they start above ser8d: its PH315 and F7 pins rise under the right-hand bars).\n')
A('## 6. Supplies and electromigration\n')
A('One VDD and one VSS net by metal: Metal4 rails across the block in the seam (VSS 25 um, VDD 10 um) into the four edge bars; ser8d\'s Metal5 straps continued up into the rails (18 of 19 pairs: the outermost '
  'strap on each side lies under the other net\'s bar and stays inside ser8d); the mux\'s nine VSS straps come down as 2.5 um necks placed clear of ser8d\'s VDD straps, its eight logic VDD straps go straight into the VDD rail; '
  'the two header rails (the mux\'s VDD islands 2 and 3) are fed by Metal5 straps along the top edge from the VDD bars and bridged; the aux side cell\'s bars and the tap row\'s rails are tied in.\n')
A(f'Currents: 2 x {26:g} mA (banks, DC, static data) + {30:g} mA (ser8d and logic).\n')
A('| row | mA | um or cuts | mA/um or mA/cut | limit | margin |\n|---|---|---|---|---|---|')
for n, x in r['em_table']['rows'].items():
    A(f"| {n} | {x['mA']} | {x.get('um', x.get('cuts'))} | {x.get('mA_per_um', x.get('mA_per_cut'))} | {x['limit']} | {x['margin_pct']} % |")
A(f"\nWorst: {r['em_table']['worst'][0]} ({r['em_table']['worst'][1]} %).  **Not covered, stated plainly:** each header rail is cut on Metal3-5 by its two output risers; the strap reaches the outer segment only, the middle "
  'segment hangs on the rail\'s own Metal1 + Metal2 under the risers (6 um, 12.5 mA at the limit) while most of the 26 mA (my estimate: about 85 %) has to pass there with static data.  It is clean only if the pad also feeds the '
  'mux\'s top-edge VDD pins (as revision 2 assumed), or if the mux gets Metal3 / Metal4 under the risers (which you ruled out at top level).  Your decision.\n')
A('## 7. Decoupling\n')
A(f"`wtx8_top.py` now has `DECAP = dict(w=8.0, l=2.0, n={d['fingers']})`, `decap()` and the instance `XDEC VDD VSS wtx8_decap` in `top()` (the subckt text is emitted in front of the top subckt so that existing callers of `top()` keep working).  "
  f"Layout: {d['rows']} rows x {d['per_row']} fingers = **{d['fingers']} NMOS 8 / 2 um, gate on VDD, source = drain = bulk = VSS, {d['gate_area_um2']:.0f} um2 of gate**, left of the aux cell, strapped by the continued ser8d straps "
  '(three VDD / VSS pairs).  By my estimate about 44 pF at 4.3 fF/um2; the value the models give was not simulated.  The right-hand region is left free (section 1) instead of being filled.\n')
A('## 8. Extracted netlists\n')
cn = r['c_netlist']
A(f"* `generated/fast/pt_wiredtx8.ext.spice` ({r['sha256']['pt_wiredtx8.ext.spice']}): ONE flat C-only netlist of the whole block, port order `wtx8_top.PORTS`, {cn['devices']['nfet_03v3']} nfet + {cn['devices']['pfet_03v3']} pfet + "
  f"{cn['devices']['ppolyf_u']} resistors, node names `XSER/...`, `XMUX/...`, `XAUX/...`.  {cn['vsubs_lines_fixed']} lines had a child substrate node (`.../VSUBS`) and were put on VSS by `fix_vsubs`; none left.  Not tried in `chain13.py`.")
rc = r['rc_netlist']
A(f"* `generated/fast/pt_wiredtx8.rc.spice` ({r['sha256']['pt_wiredtx8.rc.spice']}): the same netlist plus the DRAWN top-level resistance, {rc['resistors_added']} resistors, by `pt_wiredtx8_layout.add_top_r` (documented in its docstring): "
  'PH k split into pin / `#m` (mux side) / `#s` (ser8d side) with the resistances of section 3; F k: ser8d side behind the track resistance of section 4; VDD / VSS: one lumped resistor per child '
  f"(ohm: {rc['supply_ohm']}; rail taken as distributed from both bars, straps in parallel; coarse).  **It does NOT contain the mux-internal bus / trunk resistance of `wtx_mux8.rc.spice`** (different node naming in the flat block netlist) "
  'and no Magic extresist was run on the block.')
A(f"* `generated/fast/pt_wiredtx8.lvs.spice` ({r['sha256']['pt_wiredtx8.lvs.spice']}): hierarchical LVS netlist of the read-back GDS.\n")
A('## 9. Reproduce\n')
A('```\ncd projects/programmable_transceiver_platform/analog/wired_tx\nOMP_NUM_THREADS=1 python3 wtx_mux8_layout.py        # 25 s\nOMP_NUM_THREADS=1 python3 wtx8_aux_layout.py        # needs the mux report\n'
  'OMP_NUM_THREADS=1 python3 pt_wiredtx8_layout.py     # 40 s; needs both reports and generated/fast/wtx_ser8d_mag; writes DECAP n into wtx8_top.py if it differs\n'
  'python3 ../../../../scratch/wired_tx/s13/top/mkreport.py\n```\nGDS hashes change with every run (time stamp): regenerate the reports after a rebuild.\n')
A('## 10. What failed, what is open\n')
A('* Open: seam height (section 1); phase wiring C twice the ring budget (3); F nets unequal (4); header middle segments (6); PH pins inside the block; MAIN_BIAS / POST_BIAS on the left edge; the tap\'s unexplained 1.7 fF '
  'MAIN_P / MAIN_N difference (`../mux3/REPORT.md` section 6).')
A('* Not done: any simulation; extresist on the block; KLayout antenna deck; fill; independent review; negative controls as changed layouts.')
A('* On the way: the first decap rows were 9 um wider than computed and ran into the aux cell (415 DRC errors); edge bars first covered the PH315 / F7 risers of ser8d and shorted them to VSS (found by LVS); '
  'shield vias on a strap that was not continued left 54 Metal5 islands under minimum area; the output pin labels needed top-level metal to attach.  The first phase routing had the two legs of a net side by side: '
  'top-level C spread was 9 fF; with a VSS track between all legs it is 2 fF, at 7 um more seam.')
A('* Files touched: new `pt_wiredtx8_layout.py`; `wtx8_top.py` (DECAP / decap() / top(), as asked); `wtx8_aux_layout.py` and `wtx_mux8_layout.py` (aux rework, `add_wire_r`); `generated/fast/pt_wiredtx8.{gds,ext.spice,rc.spice,lvs.spice}` '
  'and the rebuilt mux / aux artefacts.  `wtx_ser8d` and everything outside `analog/wired_tx` and `scratch/wired_tx`: read only.')
(H / 'REPORT.md').write_text('\n'.join(L) + '\n')
print('ok', len(L))
