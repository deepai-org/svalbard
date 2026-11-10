"""ESD-04: gate-coupled rail shunt for the RF_TX pad (rftxpad) and its network drop-in macro.

The stress-safe families clamp their isolated ESD_RAIL with a static stack of three diode-connected
nfet_06v0 banks (rail_shunt_v2): 10 uA onset 2.2 V (ff) .. 3.3 V (ss). The RF_TX pads now rest at
3.3 V and peak near 4.1 V (DC-fed rfdriver), so that stack conducts every RF cycle (risk register
ESD-04, analyses/txc). A static stack cannot meet both limits: the onset must stay >= 4.4 V at
ff/32 C while the 100 mA pulse must stay under the 6 V gate screen at ss/0 C (4 decades of current
plus the process spread across a 1.6 V window).

rftx_shunt replaces the stack by ONE gate-coupled nfet_06v0 bank (GCNMOS):
  drain ESD_RAIL, source VSS, W = 224 x 53.6 um (the LU-01 sub-banked bank of rail_shunt_v2.2),
  gate GC: Cc = 2 x cap_mim_2p0fF 89.4 x 89.4 um (~32 pF) from ESD_RAIL, Rg = ppolyf_u_1k_6p0
  1 x 6 um (~6 kohm) to VSS.
DC: GC sits at VSS, the device is off at any rail voltage below junction breakdown (no 10 uA onset
up to 5.4 V at ff). Fast events couple ~Cc/(Cc+Cg) of the rail step onto GC (hold ~R(Cc+Cg) = 0.3 us).
The protection network (steering diodes, RC-triggered clamp, MIMs, bleed, ATB tap) is unchanged, so
the pad capacitance is unchanged.

Layout (local frame = the bank of rail_shunt_v2 at stages=1): bank, then above it the two MIMs
(bottom plates = GC on metal4, top plates = RAIL on metal5 with a metal5 RAIL bar above them), Rg
right of the MIMs, a metal4 GC bar on the right edge from the gate bus up to the MIM plates.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import rail_shunt_v2 as v2
from layout import IMAGE, magic, rectangles

MIM_UM = 90.             # two MIMs: 2 x 90^2 = 16200 um^2 ~ 32 pF (each <= the MIMTM.8b single-plate area)
RG_L_UM, RG_W_UM = 6., 1.
MIM_CX = (-50., 46.)      # MIM centres (local x)
MIM_GAP_Y = 7.            # top guard extension -> MIM bottom plate (metal5 GC bar runs in this gap)
GC_BAR_X = (116., 119.)    # metal5 GC bar (local x); macro x 271-274, clear of the rf-pair PAD_P/N metal5 stubs at macro x 286-290 / 302-306
RG_X = 108.               # resistor centre x (local)
RAIL_X = (-135., -105.)   # = macro RAIL strap (rail_shunt_v2.RAIL_STRAP_X) in the local frame


def reference(fingers, name='rftx_shunt', ports=('RAIL', 'VSS')):
    a, b = ports
    return [f'.subckt {name} {a} {b}',
            f'XGCN {a} GC {b} {b} nfet_06v0 w={v2.FINGER_UM}u l={v2.LENGTH_UM}u m={fingers}',
            f'XGCR GC {b} {b} ppolyf_u_1k_6p0 r_width={RG_W_UM}u r_length={RG_L_UM}u',
            f'XGCC {a} GC cap_mim_2f0_m4m5_noshield c_width={MIM_UM}u c_length={MIM_UM}u m=2',
            f'.ends {name}', '']


def extra_commands(g):
    """Rg, MIMs, GC bar and RAIL bar above a single gate-coupled bank (local frame)."""
    c = []

    def paint(layer, x0, y0, x1, y1):
        c.extend([f'box values {min(x0,x1):.3f} {min(y0,y1):.3f} {max(x0,x1):.3f} {max(y0,y1):.3f}', f'paint {layer}'])

    def via(layer, x, y, h=.13):
        paint(layer, x - h, y - h, x + h, y + h)
    top_guard = g['top_um']                       # top of the widened top guard row (VSS metal1)
    half = MIM_UM / 2
    m4_half = half + .5                           # PCell metal4 extent (+-45.9 at 89.4)
    cy = top_guard + MIM_GAP_Y + m4_half
    for cx in MIM_CX:
        c.append(f'getcell gc_mim child 0 0 parent {cx:.3f} {cy:.3f}')
    # GC on metal5 only: each MIM's bottom plate reaches metal5 through the PCell's own via4 strip (right
    # edge, x+45.2..45.6). MIMTM.11/(b): bottom plates must not be joined on metal4 (a shared plate may
    # not exceed the MIMTM.8b area) and may only be contacted through the via above them.
    gx0, gx1 = GC_BAR_X
    gy = g['gate_y']
    gb0, gb1 = top_guard + 1.2, top_guard + 4.2           # metal5 GC bar between the bank and the MIMs
    for cx in MIM_CX:
        paint('metal5', cx + half + .45, gb0, cx + half + .89, cy - half + 1.)
    paint('metal5', MIM_CX[0] + half + .45, gb0, gx1, gb1)
    paint('metal5', gx0, gy - .4, gx1, gb1)
    # gate bus (metal2) -> metal3 -> metal4 -> metal5 below the drain plate (which starts at D_REGION[0])
    paint('metal2', g['gate_bus_x1'] - .5, gy - .3, gx1, gy + .3)
    paint('metal3', gx0, gy - .3, gx1, gy + .3)
    paint('metal4', gx0, gy - .4, gx1, gy + .4)
    for k in range(4):
        via('via2', gx0 + .5 + k * .7, gy, .14)
        via('via3', gx0 + .5 + k * .7, gy, .14)
        via('via4', gx0 + .5 + k * .7, gy, .14)
    # Rg: ppolyf_u_1k_6p0, top contact -> GC (metal1..metal5), bottom contact -> its guard ring (VSS),
    # guard ring -> the top guard row of the bank (VSS metal1)
    ry = top_guard + 1.5 + 4.83
    c.append(f'getcell gc_res child 0 0 parent {RG_X:.3f} {ry:.3f}')
    paint('metal1', RG_X - .435, ry - 3.2, RG_X + .435, ry - 4.6)             # bottom end -> ring
    paint('metal1', RG_X - 1.5, top_guard - 2.4, RG_X + 1.5, ry - 4.4)         # ring -> bank top guard row
    yt = ry + 3.27
    paint('metal1', RG_X - .435, yt - .3, RG_X + .435, yt + .3)
    via('via1', RG_X, yt)
    paint('metal2', RG_X - .3, yt - .3, RG_X + .3, yt + .3)
    via('via2', RG_X, yt, .14)
    paint('metal3', RG_X - .3, yt - .3, RG_X + .3, yt + .3)
    via('via3', RG_X, yt, .14)
    paint('metal4', RG_X - .4, yt - .4, RG_X + .4, yt + .4)
    via('via4', RG_X, yt, .14)
    paint('metal5', RG_X - .6, gb0, RG_X + .6, yt + .6)
    # RAIL bar (metal5) above the MIMs with a stub into each top plate (clear of the GC metal5 strip at x+45.2)
    bar_y0 = cy + half + 3.
    paint('metal5', RAIL_X[0], bar_y0, MIM_CX[1] + 40., bar_y0 + 8.)
    for cx in MIM_CX:
        paint('metal5', cx - 30., cy + half - 6., cx + 30., bar_y0 + 1.)
    # RAIL bar -> drain plate (metal3) inside the cell (x clear of the macro's RAIL/VSS strap via fields)
    p0 = g['plates'][0]['drain']
    paint('metal5', -100., p0[1] + .5, -90., bar_y0 + 1.)
    paint('metal4', -100., p0[1] + .5, -90., p0[3] - .5)
    x = -99.5
    while x + .5 <= -90.:
        y = p0[1] + 1.
        while y + .5 <= p0[3] - .5:
            via('via3', x, y, .14); via('via4', x, y, .14)
            y += 1.2
        x += 1.2
    labels = dict(GC=((gx0 + gx1) / 2, (gb0 + gb1) / 2, 'metal5'))
    return c, dict(mim_cy=cy, rail_bar=[RAIL_X[0], bar_y0, MIM_CX[1] + 40., bar_y0 + 8.], top_um=bar_y0 + 8.), labels


def generate(work):
    fingers = v2.SUB_NF * v2.SUB_BANKS
    work.mkdir(parents=True, exist_ok=False)
    (work / 'cells.tcl').write_text(f'''crashbackups stop
load workspace
set cell [magic::gencell_makecell gf180mcu::nfet_06v0 w {v2.FINGER_UM} l {v2.LENGTH_UM} nf {v2.SUB_NF} guard 1 topc 0 botc 1 full_metal 1]
load $cell
save shunt_sub
load workspace
units internal
set cell [magic::gencell_makecell gf180mcu::cap_mim_2p0fF w {MIM_UM} l {MIM_UM}]
load $cell
save gc_mim
load workspace
units internal
set cell [magic::gencell_makecell gf180mcu::ppolyf_u_1k_6p0 w {RG_W_UM} l {RG_L_UM} guard 1 full_metal 1]
load $cell
save gc_res
quit -noprompt
''')
    magic(work, 'cells.tcl')
    comp = v2.sub_bank_layout(rectangles(work / 'shunt_sub.mag'))
    body, g = v2.bank_commands(1, fingers, comp, gate_coupled=True)
    g['gate_bus_x1'] = max(x[2] for x in comp['gates']) + .3
    extra, geo, labels = extra_commands(g)
    g.update(geo)
    p0 = g['plates'][0]['drain']; pl = g['plates'][0]['source']
    c = ['crashbackups stop', 'load rftx_shunt', 'units microns', *body, *extra, 'save rftx_shunt', 'flatten rail_shunt_flat',
         'load rail_shunt_flat', 'units microns',
         f'box values {p0[0]+2:.3f} {(p0[1]+p0[3])/2:.3f} {p0[0]+2:.3f} {(p0[1]+p0[3])/2:.3f}', 'label RAIL FreeSans 0.5 0 0 0 c metal3', 'port RAIL make 1',
         f'box values {pl[0]+2:.3f} {(pl[1]+pl[3])/2:.3f} {pl[0]+2:.3f} {(pl[1]+pl[3])/2:.3f}', 'label VSS FreeSans 0.5 0 0 0 c metal3', 'port VSS make 2',
         *[f'box values {x:.3f} {y:.3f} {x:.3f} {y:.3f}\nlabel {n} FreeSans 0.5 0 0 0 c {l}' for n, (x, y, l) in labels.items()],
         'select top cell', 'expand', 'drc check', 'drc catchup', 'puts "SHUNT_DRC [drc list count total]"', 'puts [drc listall why]',
         'extract all', 'ext2spice lvs', 'ext2spice', 'save', 'gds write rail_shunt_flat.gds', 'quit -noprompt']
    (work / 'compose.tcl').write_text('\n'.join(c) + '\n')
    out = magic(work, 'compose.tcl', allow_failure=True)
    m = re.search(r'SHUNT_DRC (\d+)', out.stdout)
    # the installed Magic GDS writer drops the HRES/DUALGATE enclosure of Rg (see gds_markers.py)
    from gds_markers import repair
    markers = repair(work, 'rail_shunt_flat')
    shutil.copy2(work / 'rail_shunt_flat.gds', work / 'rail_shunt.gds')
    (work / 'reference.spice').write_text('\n'.join(reference(fingers)))
    from run_first_pass import lvs
    ok = lvs(work, 'rail_shunt_flat.spice', 'rail_shunt_flat', 'reference.spice', 'rftx_shunt', 'lvs.txt')
    g['plates'] = {str(k): v for k, v in g['plates'].items()}
    (work / 'geometry.json').write_text(json.dumps(g, indent=1) + '\n')
    rep = dict(status='rftx_gate_coupled_shunt_DRC_LVS_recorded_not_ESD_qualification', version='rftx-1', stages=1, gate_coupled=True,
               fingers_per_stage=fingers, finger_um=v2.FINGER_UM, width_um=fingers * v2.FINGER_UM, lu=g.get('lu'),
               rg=dict(model='ppolyf_u_1k_6p0', w_um=RG_W_UM, l_um=RG_L_UM), cc=dict(model='cap_mim_2p0fF', side_um=MIM_UM, count=2),
               drc_count=int(m[1]) if m else None, netgen_lvs_match=ok, high_r_marker_repair=markers,
               image_id=subprocess.run(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}'], capture_output=True, text=True).stdout.strip(),
               gds_sha256=hashlib.sha256((work / 'rail_shunt.gds').read_bytes()).hexdigest(),
               source_sha256={n: hashlib.sha256((Path(__file__).parent / n).read_bytes()).hexdigest() for n in (Path(__file__).name, 'rail_shunt_v2.py')})
    (work / 'shunt-layout.json').write_text(json.dumps(rep, indent=2) + '\n')
    return rep


def generate_macro(work, network_dir, shunt_dir):
    """rail_shunt_v2.generate_macro with the gate-coupled shunt: same placement and straps, the RAIL
    strap continued on metal5 up to the MIM RAIL bar, and the LVS reference with the GCNMOS devices."""
    sh = json.loads((shunt_dir / 'shunt-layout.json').read_text())
    if sh['drc_count'] or not sh['netgen_lvs_match']:
        raise ValueError('rftx shunt is not DRC/LVS clean')
    g = json.loads((shunt_dir / 'geometry.json').read_text())
    orig_geo = v2.macro_geometry

    def geo(gg, stages):
        cfg, regions, straps = orig_geo(gg, stages)
        dy = cfg['dy']; bar = g['rail_bar']
        rx0, rx1 = v2.RAIL_STRAP_X
        cfg['shapes'].append([81, rx0, 270., rx1, bar[3] + dy])           # RAIL metal5 strap up to the MIM bar
        regions[1][3] = g['top_um'] + dy + .5
        return cfg, regions, straps
    v2.macro_geometry = geo
    try:
        meta = v2.generate_macro(work, network_dir, shunt_dir, shunt_lines=reference_lines(sh['fingers_per_stage']))
    finally:
        v2.macro_geometry = orig_geo
    meta['shunt'].update(gate_coupled=True, version='rftx-1')
    meta['status'] = 'rftx_network_with_gate_coupled_shunt_DRC_LVS_recorded_not_ESD_qualification'
    (work / 'network-layout.json').write_text(json.dumps(meta, indent=2) + '\n')
    return meta


def reference_lines(fingers):
    return [f'XGCN RAIL SHUNT_GC VSS VSS nfet_06v0 w={v2.FINGER_UM}u l={v2.LENGTH_UM}u m={fingers}',
            f'XGCR SHUNT_GC VSS VSS ppolyf_u_1k_6p0 r_width={RG_W_UM}u r_length={RG_L_UM}u',
            f'XGCC RAIL SHUNT_GC cap_mim_2f0_m4m5_noshield c_width={MIM_UM}u c_length={MIM_UM}u m=2']


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--macro', action='store_true')
    p.add_argument('--network-dir', type=Path)
    p.add_argument('--shunt-dir', type=Path)
    a = p.parse_args()
    if a.macro:
        r = generate_macro(a.output_dir.resolve(), a.network_dir.resolve(), a.shunt_dir.resolve())
        print(json.dumps({k: r[k] for k in ('drc_count', 'device_graph_lvs_match', 'allocation_regions_um')}, indent=1))
    else:
        print(json.dumps(generate(a.output_dir.resolve()), indent=1))
