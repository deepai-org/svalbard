"""Stress-safe drop-in protection network: canonical network + release fix + ATB tap.

Adds, inside the canonical `protection_network` footprint (an all-layer-free
51 x 32 um window at x 75..126, y -2..30 and a metal1 return corridor along the
bottom edge):

- the selected 100 kohm clamp-gate discharge: ppolyf_u_1k_6p0 snake (w 1 um,
  5 x 20 um) from the clamp gate (metal2 gate strap, via a metal3 jog) to VSS
  (metal4 VSS strap);
- an analog-test-bus tap: ppolyf_u_1k_6p0 snake (w 1 um, 20 x 24 um, ~480
  kohm) from RAIL (metal5) to a new metal3 port `ATB_RAIL` at the bottom edge.

Ports RAIL/VSS/PADP/PADN keep their coordinates and the top cell keeps the name
`protection_network`, so family generators can take this directory in place of
`generated/protection-network`. The stress shunt is a separate macro
(`rail_shunt_v2.py`); it does not fit inside this footprint.
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
except ImportError:  # inside the tool container only check_window() runs
    IMAGE = PDK = magic = rectangles = None

HERE = Path(__file__).resolve().parent
GATE_STRAP_X = 63.29        # clamp gate metal2 strap (x 62.79..63.79, y 13.0..133.8)
GATE_TAP_Y = 20.
RAIL_M5_X = 127.            # RAIL metal5 strip x 126..128, y 0..30
VSS_STACK = (134.5, -1.1)   # inside the metal4 VSS strap x 132..141, y -2..
RETURN_Y = (-1.6, -0.6)     # metal1 return corridor along the bottom edge
ATB_PIN_Y = -1.8


def check_window(work):
    """Re-verify, on the actual canonical GDS, that the added geometry lands only
    where the network has no shapes (except the intended taps)."""
    import klayout.db as k
    ly = k.Layout(); ly.read(str(work / 'network.gds')); top = ly.top_cell()
    report = {}
    for name, box, allowed in [('free_window', (75, -2, 126, 30), set()),
                               ('gate_jog_m3', (62.79, 19.4, 77.6, 20.6), set()),
                               ('return_corridor', (75, -1.7, 136, -0.5), {(46, 0)})]:
        hits = {}
        for li in ly.layer_indexes():
            info = ly.get_info(li)
            if info.datatype != 0 or (info.layer, info.datatype) in allowed:
                continue
            if name == 'gate_jog_m3' and info.layer not in (42, 38, 40):
                continue
            r = k.Region(top.begin_shapes_rec(li)) & k.Region(k.DBox(*box).to_itype(ly.dbu))
            if not r.is_empty():
                hits[f'{info.layer}/{info.datatype}'] = r.area() * ly.dbu ** 2
        report[name] = hits
    (work / 'window-check.json').write_text(json.dumps(report, indent=1) + '\n')
    if any(report.values()):
        raise ValueError('Added geometry window is not free: ' + json.dumps(report))


def compose_gds(work):
    """Canonical network GDS untouched; add resistor cells, routes and the ATB label."""
    import klayout.db as k
    cfg = json.loads((work / 'compose.json').read_text())
    ly = k.Layout(); ly.read(str(work / 'network.gds')); top = ly.cell('protection_network')
    for name, (ox, oy) in cfg['cells'].items():
        ly.read(str(work / f'{name}.gds'))
        # Magic writes its layer-0 check boundary (larger than the resistor);
        # it is not a mask layer and would distort the macro bounding box.
        if ly.find_layer(0, 0) is not None:
            ly.cell(name).shapes(ly.find_layer(0, 0)).clear()
        top.insert(k.DCellInstArray(ly.cell(name).cell_index(), k.DTrans(float(ox), float(oy))))
    for layer, x0, y0, x1, y1 in cfg['shapes']:
        top.shapes(ly.layer(layer, 0)).insert(k.DBox(x0, y0, x1, y1))
    name, x, y = cfg['label']
    top.shapes(ly.layer(42, 10)).insert(k.DText(name, k.DTrans(float(x), float(y))))
    opts = k.SaveLayoutOptions(); opts.add_cell(top.cell_index())
    ly.write(str(work / 'network_ss.gds'), opts)


def generate(work, network_dir=HERE / 'generated/protection-network'):
    work.mkdir(parents=True, exist_ok=False)
    for name in ('network.gds', 'network_flat.spice', 'network-layout.json', 'network-with-well.spice'):
        shutil.copy2(network_dir / name, work / name)
    shutil.copy2(Path(__file__), work / 'protection_network_ss.py')
    subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python3',
                    '--mount', f'type=bind,src={work},dst=/work', IMAGE, '/work/protection_network_ss.py',
                    '--inside', '--output-dir', '/work'], check=True, timeout=120)
    (work / 'res.tcl').write_text('''crashbackups stop
load workspace
set cell [magic::gencell_makecell gf180mcu::ppolyf_u_1k_6p0 w 1 l 20 nx 5 snake 1 guard 1 full_metal 1 res_spacing 0.7]
load $cell
save dis_res
gds write dis_res.gds
load workspace
set cell [magic::gencell_makecell gf180mcu::ppolyf_u_1k_6p0 w 1 l 24 nx 20 snake 1 guard 1 full_metal 1 res_spacing 0.7]
load $cell
save atb_res
gds write atb_res.gds
quit -noprompt
''')
    magic(work, 'res.tcl')
    cells = {}
    for name in ('dis_res', 'atb_res'):
        g = rectangles(work / f'{name}.mag')
        shapes = [v for k, vs in g.items() if k != 'checkpaint' for v in vs]
        bb = [min(v[0] for v in shapes), min(v[1] for v in shapes), max(v[2] for v in shapes), max(v[3] for v in shapes)]
        contacts = sorted(g['polycontact'], key=lambda r: (r[1], r[0]))
        if len(contacts) != 2:
            raise ValueError('Expected two snake terminal contacts in ' + name)
        ring = [v for v in g['metal1'] if v[2] - v[0] > 3 and v[1] <= bb[1] + 1.]
        cells[name] = dict(bbox=bb, contacts=contacts, ring_bottom=min(ring, key=lambda v: v[1]) if ring else None)
    # Place the cells so their bounding boxes sit inside the free window.
    db, ab = cells['dis_res']['bbox'], cells['atb_res']['bbox']
    dis_off = (76.0 - db[0], 0.2 - db[1])
    atb_off = (125.6 - ab[2], 0.2 - ab[1])
    for name, off in (('dis_res', dis_off), ('atb_res', atb_off)):
        b = cells[name]['bbox']
        placed = [b[0] + off[0], b[1] + off[1], b[2] + off[0], b[3] + off[1]]
        if placed[0] < 75.5 or placed[2] > 125.7 or placed[1] < -0.3 or placed[3] > 29.8:
            raise ValueError(f'{name} does not fit the free window: {placed}')
        cells[name]['placed'] = placed
        cells[name]['offset'] = off
    if cells['dis_res']['placed'][2] + 1.5 > cells['atb_res']['placed'][0]:
        raise ValueError('Resistors overlap: ' + json.dumps(cells))
    shapes = []
    GDS = dict(metal1=34, via1=35, metal2=36, via2=38, metal3=42, via3=40, metal4=46, via4=41, metal5=81)

    def paint(layer, x0, y0, x1, y1):
        shapes.append([GDS[layer], min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)])

    def via(layer, x, y, size):
        paint(layer, x - size / 2, y - size / 2, x + size / 2, y + size / 2)

    def stack(x, y, lo, hi, half=.8):
        names = {1: 'metal1', 2: 'metal2', 3: 'metal3', 4: 'metal4', 5: 'metal5'}
        cuts = {1: ('via1', .26), 2: ('via2', .28), 3: ('via3', .28), 4: ('via4', .28)}
        for level in range(lo, hi + 1):
            paint(names[level], x - half, y - half, x + half, y + half)
        offsets = (-.4, .4) if half >= .8 else (0.,)
        for level in range(lo, hi):
            name, size = cuts[level]
            for dx in offsets:
                for dy in offsets:
                    via(name, x + dx, y + dy, size)

    def term(name, i):
        r = cells[name]['contacts'][i]; o = cells[name]['offset']
        return ((r[0] + r[2]) / 2 + o[0], (r[1] + r[3]) / 2 + o[1])
    # Discharge: gate strap (m2) -> via2 -> m3 jog -> via2 -> m2 over the
    # resistor guard ring -> via1 onto the upper snake contact. Internal
    # contacts leave their (VSS) guard rings on metal2/metal3 only.
    for dy in (-.3, .3):
        via('via2', GATE_STRAP_X, GATE_TAP_Y + dy, .28)
    paint('metal2', GATE_STRAP_X - .5, GATE_TAP_Y - .5, GATE_STRAP_X + .5, GATE_TAP_Y + .5)
    jx = 77.
    paint('metal3', GATE_STRAP_X - .5, GATE_TAP_Y - .5, jx + .5, GATE_TAP_Y + .5)
    stack(jx, GATE_TAP_Y, 2, 3, half=.5)
    hi_contact = term('dis_res', 1)
    lo_contact = term('dis_res', 0)
    stack(hi_contact[0], hi_contact[1], 1, 2, half=.4)
    paint('metal2', jx - .5, GATE_TAP_Y - .3, hi_contact[0] + .3, GATE_TAP_Y + .3)
    paint('metal2', hi_contact[0] - .3, min(hi_contact[1], GATE_TAP_Y) - .3, hi_contact[0] + .3, max(hi_contact[1], GATE_TAP_Y) + .3)
    # Discharge low end and both guard rings -> metal1 return -> stack into metal4 VSS.
    paint('metal1', lo_contact[0] - .3, RETURN_Y[0], lo_contact[0] + .3, lo_contact[1])
    paint('metal1', lo_contact[0] - .3, RETURN_Y[0], VSS_STACK[0] + .8, RETURN_Y[1])
    for name in ('dis_res', 'atb_res'):
        ring = cells[name]['ring_bottom']; o = cells[name]['offset']
        if ring is not None:
            x = (ring[0] + ring[2]) / 2 + o[0]
            paint('metal1', x - .3, RETURN_Y[0], x + .3, ring[3] + o[1])
    stack(VSS_STACK[0], VSS_STACK[1] + .1, 1, 4)
    # ATB: upper contact -> via1 -> metal2 -> stack into RAIL metal5; lower
    # contact -> via1/via2 -> metal3 pin at the bottom edge.
    a_hi, a_lo = term('atb_res', 1), term('atb_res', 0)
    rail_y = min(a_hi[1] + 1.5, 28.5)
    stack(a_hi[0], a_hi[1], 1, 2, half=.4)
    paint('metal2', a_hi[0] - .3, a_hi[1], a_hi[0] + .3, rail_y + .3)
    paint('metal2', a_hi[0] - .3, rail_y - .3, RAIL_M5_X, rail_y + .3)
    stack(RAIL_M5_X, rail_y, 2, 5, half=.8)
    stack(a_lo[0], a_lo[1], 1, 3, half=.4)
    paint('metal3', a_lo[0] - .4, ATB_PIN_Y - .2, a_lo[0] + .4, a_lo[1])
    from gds_markers import repair
    markers = {name: repair(work, name) for name in ('dis_res', 'atb_res')}
    (work / 'compose.json').write_text(json.dumps(dict(
        shapes=shapes, cells={n: cells[n]['offset'] for n in cells},
        label=['ATB_RAIL', a_lo[0], ATB_PIN_Y]), indent=1))
    subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python3',
                    '--mount', f'type=bind,src={work},dst=/work', IMAGE, '/work/protection_network_ss.py',
                    '--compose', '--output-dir', '/work'], check=True, timeout=120)
    c = ['crashbackups stop', 'gds read network_ss.gds', 'load protection_network', 'select top cell',
         'flatten network_ss_flat', 'load network_ss_flat', 'units microns',
         'select top cell', 'expand', 'drc check', 'drc catchup', 'puts "NETWORK_SS_DRC [drc list count total]"',
         'puts [drc listall why]', 'extract all', 'ext2spice lvs', 'ext2spice', 'quit -noprompt']
    (work / 'compose.tcl').write_text('\n'.join(c) + '\n')
    out = magic(work, 'compose.tcl', allow_failure=True)
    m = re.search(r'NETWORK_SS_DRC (\d+)', out.stdout)
    drc = int(m[1]) if m else None
    from gds_markers import repair
    strip = lambda t: '\n'.join(l for l in t.replace('\n+', ' ').splitlines() if not l.startswith('C')) + '\n'
    extracted = (work / 'network_ss_flat.spice').read_text()
    (work / 'actual.spice').write_text(strip(extracted))
    # Reference: the canonical LVS-verified network extraction plus the two
    # resistors on the canonical gate node.
    base = (network_dir / 'network_flat.spice').read_text()
    gate = 'a_2245_2628#'
    if base.count(gate) < 80:
        raise ValueError('Canonical clamp gate node not found')
    body = re.sub(r'\n\+\s*', ' ', base)
    body = body.replace('.subckt network_flat VSS RAIL PADP PADN', '.subckt network_ss VSS RAIL PADP PADN ATB_RAIL')
    add = (f'XDISCHARGE {gate} VSS VSS ppolyf_u_1k_6p0 r_width=1u r_length=100u\n'
           'XATBTAP RAIL ATB_RAIL VSS ppolyf_u_1k_6p0 r_width=1u r_length=480u\n')
    body = re.sub(r'\n\.ends', '\n' + add + '.ends', body, count=1)
    (work / 'reference.spice').write_text(strip(body))
    from run_first_pass import lvs
    lvs_match = lvs(work, 'actual.spice', 'network_ss_flat', 'reference.spice', 'network_ss', 'lvs.txt')
    shutil.copy2(work / 'network_ss.gds', work / 'network.gds')
    rt_match = lvs_match
    rdrc = m
    joined = re.sub(r'\n\+\s*', ' ', extracted)
    header = next(l for l in joined.splitlines() if l.startswith('.subckt network_ss_flat '))
    if set(header.split()[2:]) != {'VSS', 'RAIL', 'PADP', 'PADN', 'ATB_RAIL'}:
        raise ValueError('Unexpected network ports: ' + header)
    # Fixed port order for every family generator (by name, not extraction order).
    net_ss = joined.replace(header, '.subckt network_flat VSS RAIL PADP PADN ATB_RAIL', 1)
    (work / 'network_flat.spice').write_text(net_ss)
    meta = json.loads((network_dir / 'network-layout.json').read_text())
    image_id = subprocess.run(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}'], capture_output=True, text=True).stdout.strip()
    meta.update(status='stress_safe_network_dropin_DRC_LVS_roundtrip_recorded_not_ESD_qualification',
                drc_count=drc, device_graph_lvs_match=lvs_match,
                gds_roundtrip=dict(method='DRC, extraction and LVS are run on Magic reading the written GDS itself', drc_count=int(rdrc[1]) if rdrc else None, lvs_match=rt_match),
                additions=dict(gate_discharge=dict(model='ppolyf_u_1k_6p0', w_um=1, segments=5, segment_um=20, squares=100, placed_um=cells['dis_res']['placed']),
                               atb_tap=dict(model='ppolyf_u_1k_6p0', w_um=1, segments=20, segment_um=24, squares=480, placed_um=cells['atb_res']['placed'],
                                            port='ATB_RAIL', port_um=[round(a_lo[0], 3), ATB_PIN_Y], layer='metal3')),
                ports=dict(RAIL=[130, 4], VSS=[138, 4], PADP=[186, 4], PADN=[190, 4], ATB_RAIL=[round(a_lo[0], 3), ATB_PIN_Y]),
                high_r_marker_repair=markers, image_id=image_id, pdk=PDK,
                canonical_network_gds_sha256=hashlib.sha256((network_dir / 'network.gds').read_bytes()).hexdigest(),
                gds_sha256=hashlib.sha256((work / 'network.gds').read_bytes()).hexdigest(),
                extracted_spice_sha256=hashlib.sha256(extracted.encode()).hexdigest(),
                source_sha256={Path(__file__).name: hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
                limitations=['Stress shunt is not inside this footprint; it must be attached through RAIL/VSS',
                             'Gate tap is a single 1 um metal3 jog; resistor current is small but the jog is not EM-reviewed',
                             'No ESD rating, core-survival or current-capacity claim'])
    (work / 'network-layout.json').write_text(json.dumps(meta, indent=2) + '\n')
    return meta


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--inside', action='store_true')
    p.add_argument('--compose', action='store_true')
    a = p.parse_args()
    if a.inside:
        check_window(a.output_dir)
    elif a.compose:
        compose_gds(a.output_dir)
    else:
        print(json.dumps(generate(a.output_dir.resolve()), indent=2))
