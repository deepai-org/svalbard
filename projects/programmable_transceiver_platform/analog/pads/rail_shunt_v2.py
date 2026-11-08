"""Low-resistance stress-safe rail shunt (v2) and its network drop-in macro.

Devices: 3 series banks of 240 x 50 um / L 0.7 diode-connected nfet_06v0 from
the isolated ESD_RAIL to VSS. Wiring (strap_resistance() bounds it, because the
device-level extraction carries no wiring resistance):
- banks are stacked upward; every bank has its drain region at the bottom
  (y -22.5..-1) and source region at the top (y 1..22.5), each covered by a
  metal2 plate (via1 columns on every strip) and a metal3 plate (via2 grid);
- source(k) and drain(k+1) are one continuous metal3 plate across the gap;
- bank 0's drain plate is RAIL, bank 2's source plate is VSS, guard rings tie to
  the bank 2 source plate.
The drop-in macro places the shunt 14 um above the protection network and uses
a 30 um metal5 RAIL strap and 30 um metal4 + metal5 VSS straps.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

try:
    from layout import IMAGE, PDK, magic, rectangles
except ImportError:
    IMAGE = PDK = magic = rectangles = None

FINGER_UM, LENGTH_UM, GAP_UM = 50., .7, 6.
D_REGION, S_REGION = (-22.5, -1.), (1., 22.5)
SHEET = {1: .090, 2: .090, 3: .090, 4: .090, 5: .040}      # nominal ohm/sq (Magic tech)
SHEET_HI = {1: .104, 2: .104, 3: .104, 4: .104, 5: .049}
CUT_OHM, CUT_OHM_HI = 4.5, 15.


def reference(stages, fingers_per_stage, name='rail_shunt', ports=('RAIL', 'VSS')):
    """LVS reference: diode-connected series nfet_06v0 stack from ports[0] to ports[1]."""
    lines, node = [f'.subckt {name} {" ".join(ports)}'], ports[0]
    for stage in range(stages):
        end = ports[1] if stage == stages - 1 else f'MID{stage}'
        lines.append(f'XS{stage} {node} {node} {end} {ports[1]} nfet_06v0 w={FINGER_UM}u l={LENGTH_UM}u m={fingers_per_stage}')
        node = end
    return lines + [f'.ends {name}', '']


def bank_commands(stages, fingers, r):
    strips = sorted(r['mvndiffc']); gates = sorted(r['polycontact']); guard = sorted(r['mvpsubdiffcont'])
    if len(strips) != fingers + 1 or len(gates) != fingers or len(guard) != 2:
        raise ValueError('Unexpected nfet_06v0 PCell contact topology')
    gl, gr = guard[0][0], guard[1][2]
    shapes = [v for k, vs in r.items() if k != 'checkpaint' for v in vs]
    pitch = max(v[3] for v in shapes) - min(v[1] for v in shapes) + GAP_UM
    gate_y = sum((g[1] + g[3]) / 2 for g in gates) / len(gates)
    rows = sorted([v for v in r['metal1'] if v[2] - v[0] > 5], key=lambda v: v[1])
    gb, gt = rows[0], rows[-1]
    strap_x = gl - 1.5
    drains = [(v[0] + v[2]) / 2 for i, v in enumerate(strips) if i % 2 == 1]
    sources = [(v[0] + v[2]) / 2 for i, v in enumerate(strips) if i % 2 == 0]
    gate_xs = [(v[0] + v[2]) / 2 for v in gates]
    c = []

    def paint(layer, x0, y0, x1, y1):
        c.extend([f'box values {min(x0,x1):.3f} {min(y0,y1):.3f} {max(x0,x1):.3f} {max(y0,y1):.3f}', f'paint {layer}'])

    def cut_column(x, y0, y1):
        y = y0 + .3
        while y + .3 <= y1:
            paint('metal1', x - .19, y - .19, x + .19, y + .19)
            paint('via1', x - .13, y - .13, x + .13, y + .13)
            y += .7

    def via2_grid(x0, y0, x1, y1, step=2.):
        x = x0 + .6
        while x + .6 <= x1:
            y = y0 + .6
            while y + .6 <= y1:
                paint('via2', x - .14, y - .14, x + .14, y + .14)
                y += step
            x += step
    plates = {}
    for k in range(stages):
        oy = k * pitch
        c.append(f'getcell shunt_bank child 0 0 parent 0 {oy:.3f}')
        for x in drains:
            cut_column(x, oy + D_REGION[0], oy + D_REGION[1])
        for x in sources:
            cut_column(x, oy + S_REGION[0], oy + S_REGION[1])
        for x in gate_xs:
            paint('metal1', x - .19, oy + gate_y - .19, x + .19, oy + gate_y + .19)
            paint('via1', x - .13, oy + gate_y - .13, x + .13, oy + gate_y + .13)
        dx0, dx1 = strap_x - .5, max(drains) + .3
        sx0, sx1 = min(sources) - .3, max(sources) + .3
        paint('metal2', dx0, oy + D_REGION[0], dx1, oy + D_REGION[1])
        paint('metal2', sx0, oy + S_REGION[0], sx1, oy + S_REGION[1])
        paint('metal2', strap_x - .5, oy + gate_y - .3, max(gate_xs) + .3, oy + gate_y + .3)      # gate bus
        paint('metal2', strap_x - .5, oy + gate_y - .3, strap_x + .5, oy + D_REGION[0] + 1.)      # gate -> drain
        # metal3 plates; source(k) joins drain(k+1) across the gap
        x0m, x1m = min(dx0, sx0) + 1., max(dx1, sx1) - 1.
        paint('metal3', x0m, oy + D_REGION[0], x1m, oy + D_REGION[1])
        via2_grid(max(x0m, dx0), oy + D_REGION[0], min(x1m, dx1), oy + D_REGION[1])
        top = (oy + pitch + D_REGION[1]) if k < stages - 1 else oy + S_REGION[1]
        paint('metal3', x0m, oy + S_REGION[0], x1m, top)
        via2_grid(max(x0m, sx0), oy + S_REGION[0], min(x1m, sx1), oy + S_REGION[1])
        plates[k] = dict(drain=[x0m, oy + D_REGION[0], x1m, oy + D_REGION[1]], source=[x0m, oy + S_REGION[0], x1m, oy + S_REGION[1]])
        if k:
            # join guard rings of adjacent banks (metal1, below the metal3 plate)
            paint('metal1', gb[0], oy - pitch + gt[1], gb[2], oy + gb[3])
    # guard rings -> last source plate (VSS): widen the last top guard row
    oy = (stages - 1) * pitch
    paint('metal1', gt[0], oy + gt[1], gt[2], oy + gt[3] + 2.4)
    y = oy + gt[3] + .6
    x = max(gt[0], plates[stages - 1]['source'][0]) + 1.
    while x + 1. <= min(gt[2], plates[stages - 1]['source'][2]):
        paint('via1', x - .13, y + .5 - .13, x + .13, y + .5 + .13)
        paint('via2', x - .14, y + 1.2 - .14, x + .14, y + 1.2 + .14)
        x += 2.
    paint('metal2', gt[0], oy + gt[3] + .3, gt[2], oy + gt[3] + 2.4)
    paint('metal3', plates[stages - 1]['source'][0], oy + S_REGION[1], plates[stages - 1]['source'][2], oy + gt[3] + 2.4)
    geo = dict(pitch=pitch, gate_y=gate_y, strap_x=strap_x, guard_left=gl, guard_right=gr, guard_top=gt, guard_bottom=gb,
               plates=plates, bank_width_um=x1m - x0m, top_um=oy + gt[3] + 2.4, bottom_um=gb[1])
    return c, geo


def generate(work, stages=3, width_per_stage_um=12000.):
    fingers = int(round(width_per_stage_um / FINGER_UM))
    work.mkdir(parents=True, exist_ok=False)
    (work / 'bank.tcl').write_text(f'''crashbackups stop
load workspace
set cell [magic::gencell_makecell gf180mcu::nfet_06v0 w {FINGER_UM} l {LENGTH_UM} nf {fingers} guard 1 topc 0 botc 1 full_metal 1]
load $cell
save shunt_bank
quit -noprompt
''')
    magic(work, 'bank.tcl')
    body, g = bank_commands(stages, fingers, rectangles(work / 'shunt_bank.mag'))
    p0 = g['plates'][0]['drain']; pl = g['plates'][stages - 1]['source']
    c = ['crashbackups stop', 'load rail_shunt', 'units microns', *body, 'save rail_shunt', 'flatten rail_shunt_flat',
         'load rail_shunt_flat', 'units microns',
         f'box values {p0[0]+2:.3f} {(p0[1]+p0[3])/2:.3f} {p0[0]+2:.3f} {(p0[1]+p0[3])/2:.3f}', 'label RAIL FreeSans 0.5 0 0 0 c metal3', 'port RAIL make 1',
         f'box values {pl[0]+2:.3f} {(pl[1]+pl[3])/2:.3f} {pl[0]+2:.3f} {(pl[1]+pl[3])/2:.3f}', 'label VSS FreeSans 0.5 0 0 0 c metal3', 'port VSS make 2',
         'select top cell', 'expand', 'drc check', 'drc catchup', 'puts "SHUNT_DRC [drc list count total]"', 'puts [drc listall why]',
         'extract all', 'ext2spice lvs', 'ext2spice', 'save', 'gds write rail_shunt.gds', 'quit -noprompt']
    (work / 'compose.tcl').write_text('\n'.join(c) + '\n')
    out = magic(work, 'compose.tcl', allow_failure=True)
    m = re.search(r'SHUNT_DRC (\d+)', out.stdout)
    (work / 'reference.spice').write_text('\n'.join(reference(stages, fingers)))
    from run_first_pass import lvs
    ok = lvs(work, 'rail_shunt_flat.spice', 'rail_shunt_flat', 'reference.spice', 'rail_shunt', 'lvs.txt')
    from gds_roundtrip import check
    rt = check(work / 'roundtrip', work / 'rail_shunt.gds', work / 'rail_shunt_flat.spice', 'rail_shunt_flat')
    g['plates'] = {str(k): v for k, v in g['plates'].items()}
    (work / 'geometry.json').write_text(json.dumps(g, indent=1) + '\n')
    rep = dict(status='v2_shunt_macro_DRC_LVS_roundtrip_recorded_not_ESD_qualification', version=2, stages=stages,
               fingers_per_stage=fingers, drc_count=int(m[1]) if m else None, netgen_lvs_match=ok, gds_roundtrip=rt,
               gds_sha256=hashlib.sha256((work / 'rail_shunt.gds').read_bytes()).hexdigest(),
               image_id=subprocess.run(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}'], capture_output=True, text=True).stdout.strip(),
               source_sha256={Path(__file__).name: hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    (work / 'shunt-layout.json').write_text(json.dumps(rep, indent=2) + '\n')
    return rep


# ---------------------------------------------------------------- drop-in macro
MACRO_GAP_UM, MACRO_DX = 14., 155.
RAIL_STRAP_X, VSS_STRAP_X = (20., 50.), (100., 130.)
VSS_BASE_X = (80., 143.)
VSS_M5_START = 290.   # v2.1: was 300 (metal4-only stretch 288..300 ran 1.9x an assumed EM limit)


def macro_geometry(g, stages):
    shapes = []
    M = {1: 34, 2: 36, 3: 42, 4: 46, 5: 81}
    V = {1: (35, .26), 2: (38, .28), 3: (40, .28), 4: (41, .28)}

    def box(layer, x0, y0, x1, y1):
        shapes.append([layer, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)])

    def vias(level, x0, y0, x1, y1, step=1.):
        layer, size = V[level]; n = 0; x = x0 + .5
        while x + .5 <= x1:
            y = y0 + .5
            while y + .5 <= y1:
                box(layer, x - size / 2, y - size / 2, x + size / 2, y + size / 2); n += 1; y += step
            x += step
        return n
    dy = 288. + MACRO_GAP_UM - g['bottom_um']
    off = lambda b: [b[0] + MACRO_DX, b[1] + dy, b[2] + MACRO_DX, b[3] + dy]
    d0 = off(g['plates']['0']['drain']); sl = off(g['plates'][str(stages - 1)]['source'])
    cuts = {}
    rx0, rx1 = RAIL_STRAP_X
    # RAIL: metal5 from the network RAIL plane into bank 0's drain plate (metal3).
    box(M[5], rx0, 270., rx1, d0[3] - .5)
    box(M[4], rx0, d0[1] + .5, rx1, d0[3] - .5)
    cuts['rail_via4'] = vias(4, rx0, d0[1] + .5, rx1, d0[3] - .5)
    cuts['rail_via3'] = vias(3, rx0, d0[1] + .5, rx1, d0[3] - .5)
    vx0, vx1 = VSS_STRAP_X
    # VSS: metal4 from the network VSS plane to the last source plate, metal5 in
    # parallel above the network only (the network's metal5 is RAIL).
    box(M[4], vx0, 265., vx1, sl[3] - .5)
    # v2.1: widen the metal4 base (inside the network VSS plane, x<=143.9, and the
    # 2 um gap to the metal5 overlay) so no section is a single 30 um strap.
    box(M[4], VSS_BASE_X[0], 265., VSS_BASE_X[1], VSS_M5_START + 2.)
    # metal5 VSS overlay starts 11 um above the network's metal5 RAIL plane (top y=279)
    box(M[5], vx0, VSS_M5_START, vx1, sl[3] - .5)
    cuts['vss_via4_low'] = vias(4, vx0, VSS_M5_START, vx1, VSS_M5_START + 10.)
    cuts['vss_via4_high'] = vias(4, vx0, sl[1] + .5, vx1, sl[3] - .5)
    cuts['vss_via3'] = vias(3, vx0, sl[1] + .5, vx1, sl[3] - .5)
    top = g['top_um'] + dy
    sbox = [MACRO_DX + g['guard_left'] - 2., g['bottom_um'] + dy - 1., MACRO_DX + g['guard_right'] + 1., top + .5]
    regions = [[-.055, -2., 274.5, 288.], sbox, [rx0, 288., rx1, sbox[1]], [vx0, 288., vx1, sbox[1]]]
    straps = dict(rail=dict(layer='metal5', width_um=rx1 - rx0, length_um=d0[3] - .5 - 270., cuts={k: v for k, v in cuts.items() if k.startswith('rail')}),
                  vss=dict(layers=['metal4', 'metal5 (above y=290)'], width_um=vx1 - vx0, metal4_length_um=sl[3] - .5 - 265.,
                           metal5_length_um=sl[3] - .5 - VSS_M5_START, metal4_only_um=VSS_M5_START - 288., metal4_base_width_um=VSS_BASE_X[1] - VSS_BASE_X[0], cuts={k: v for k, v in cuts.items() if k.startswith('vss')}))
    return dict(dx=MACRO_DX, dy=dy, shapes=shapes), regions, straps


def strap_resistance(straps, g, stages):
    """Lumped worst-path wiring resistance (ohm) from the network RAIL plane to its VSS plane."""
    out = {}
    for corner, sheet, cut in (('nominal', SHEET, CUT_OHM), ('high', SHEET_HI, CUT_OHM_HI)):
        r = straps['rail']; v = straps['vss']
        rail = sheet[5] * r['length_um'] / r['width_um'] + cut / r['cuts']['rail_via4'] + cut / r['cuts']['rail_via3']
        m4 = sheet[4] * v['metal4_length_um'] / v['width_um']; m5 = sheet[5] * v['metal5_length_um'] / v['width_um']
        vss = 1 / (1 / m4 + 1 / (m5 + cut / v['cuts']['vss_via4_low'] + cut / v['cuts']['vss_via4_high'])) + cut / v['cuts']['vss_via3']
        width = g['bank_width_um']
        plate = 1 / (1 / sheet[2] + 1 / sheet[3]) * width / (D_REGION[1] - D_REGION[0])   # m2||m3 end-to-end, one plate
        # Per bank, the farthest finger sees at most one plate end-to-end on each of drain and source.
        banks = stages * 2 * plate
        out[corner] = dict(rail_strap_ohm=rail, vss_strap_ohm=vss, plate_end_to_end_ohm=plate, banks_bound_ohm=banks,
                           total_bound_ohm=rail + vss + banks, drop_at_100mA_v=.1 * (rail + vss + banks))
    return out


def compose_macro(work):
    import klayout.db as k
    cfg = json.loads((work / 'compose.json').read_text())
    ly = k.Layout(); ly.read(str(work / 'network.gds')); top = ly.cell('protection_network')
    ly.read(str(work / 'rail_shunt.gds')); shunt = ly.cell('rail_shunt_flat')
    for li in ly.layer_indexes():
        for s in list(shunt.each_shape(li)):
            if s.is_text():
                s.delete()
    shunt.name = 'stress_safe_rail_shunt_v2'
    top.insert(k.DCellInstArray(shunt.cell_index(), k.DTrans(float(cfg['dx']), float(cfg['dy']))))
    for layer, x0, y0, x1, y1 in cfg['shapes']:
        top.shapes(ly.layer(layer, 0)).insert(k.DBox(x0, y0, x1, y1))
    opts = k.SaveLayoutOptions(); opts.add_cell(top.cell_index())
    ly.write(str(work / 'network_shunt.gds'), opts)


def generate_macro(work, network_dir, shunt_dir):
    work.mkdir(parents=True, exist_ok=False)
    net_meta = json.loads((network_dir / 'network-layout.json').read_text())
    sh = json.loads((shunt_dir / 'shunt-layout.json').read_text())
    if net_meta['drc_count'] or not net_meta['device_graph_lvs_match'] or sh['drc_count'] or not sh['netgen_lvs_match']:
        raise ValueError('Inputs are not DRC/LVS clean')
    g = json.loads((shunt_dir / 'geometry.json').read_text())
    stages, fingers = sh['stages'], sh['fingers_per_stage']
    for name in ('network.gds', 'network-with-well.spice'):
        shutil.copy2(network_dir / name, work / name)
    shutil.copy2(shunt_dir / 'rail_shunt.gds', work / 'rail_shunt.gds')
    shutil.copy2(Path(__file__), work / 'rail_shunt_v2.py')
    cfg, regions, straps = macro_geometry(g, stages)
    (work / 'compose.json').write_text(json.dumps(cfg, indent=1))
    subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python3',
                    '--mount', f'type=bind,src={work},dst=/work', IMAGE, '/work/rail_shunt_v2.py', '--compose-macro', '--output-dir', '/work'],
                   check=True, timeout=900)
    (work / 'extract.tcl').write_text('crashbackups stop\ngds read network_shunt.gds\nload protection_network\nselect top cell\n'
                                      'flatten network_shunt_flat\nload network_shunt_flat\nselect top cell\nexpand\ndrc check\ndrc catchup\n'
                                      'puts "NETSHUNT_DRC [drc list count total]"\nputs [drc listall why]\nextract all\n'
                                      'ext2spice lvs\next2spice cthresh 0\next2spice\nquit -noprompt\n')
    out = magic(work, 'extract.tcl', allow_failure=True)
    m = re.search(r'NETSHUNT_DRC (\d+)', out.stdout)
    strip = lambda t: '\n'.join(l for l in re.sub(r'\n\+\s*', ' ', t).splitlines() if not l.startswith('C')) + '\n'
    raw = (work / 'network_shunt_flat.spice').read_text()
    (work / 'actual.spice').write_text(strip(raw))
    base = re.sub(r'\n\+\s*', ' ', (network_dir / 'network_flat.spice').read_text())
    node, lines = 'RAIL', []
    for s in range(stages):
        end = 'VSS' if s == stages - 1 else f'SHUNT_MID{s}'
        lines.append(f'XSHUNT{s} {node} {node} {end} VSS nfet_06v0 w=50u l=0.7u m={fingers}'); node = end
    (work / 'reference.spice').write_text(strip(re.sub(r'\n\.ends', '\n' + '\n'.join(lines) + '\n.ends', base, count=1)))
    from run_first_pass import lvs
    ok = lvs(work, 'actual.spice', 'network_shunt_flat', 'reference.spice', 'network_flat', 'lvs.txt')
    joined = re.sub(r'\n\+\s*', ' ', raw)
    header = next(l for l in joined.splitlines() if l.startswith('.subckt network_shunt_flat '))
    if set(header.split()[2:]) != {'VSS', 'RAIL', 'PADP', 'PADN', 'ATB_RAIL'}:
        raise ValueError('Unexpected ports: ' + header)
    (work / 'network_flat.spice').write_text(joined.replace(header, '.subckt network_flat VSS RAIL PADP PADN ATB_RAIL', 1))
    shutil.copy2(work / 'network_shunt.gds', work / 'network.gds')
    meta = dict(net_meta)
    meta.update(status='stress_safe_network_with_v2_shunt_dropin_DRC_LVS_recorded_not_ESD_qualification',
                drc_count=int(m[1]) if m else None, device_graph_lvs_match=ok,
                gds_roundtrip=dict(method='DRC, extraction and LVS run on Magic reading the written GDS', drc_count=int(m[1]) if m else None, lvs_match=ok),
                shunt=dict(version=2, stages=stages, fingers_per_stage=fingers, offset_um=[cfg['dx'], cfg['dy']], gds_sha256=sh['gds_sha256']),
                straps=straps, wiring_resistance=strap_resistance(straps, g, stages), allocation_regions_um=regions,
                image_id=sh['image_id'], gds_sha256=hashlib.sha256((work / 'network.gds').read_bytes()).hexdigest(),
                extracted_spice_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                source_sha256={Path(__file__).name: hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    (work / 'network-layout.json').write_text(json.dumps(meta, indent=2) + '\n')
    return meta


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--compose-macro', action='store_true')
    p.add_argument('--macro', action='store_true')
    p.add_argument('--network-dir', type=Path)
    p.add_argument('--shunt-dir', type=Path)
    a = p.parse_args()
    if a.compose_macro:
        compose_macro(a.output_dir)
    elif a.macro:
        r = generate_macro(a.output_dir.resolve(), a.network_dir.resolve(), a.shunt_dir.resolve())
        print(json.dumps({k: r[k] for k in ('drc_count', 'device_graph_lvs_match', 'straps', 'wiring_resistance', 'allocation_regions_um')}, indent=1))
    else:
        print(json.dumps(generate(a.output_dir.resolve()), indent=1))
