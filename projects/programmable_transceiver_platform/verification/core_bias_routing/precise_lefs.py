# KLayout (pya) stage: build routing abstracts whose OBS is the masters' real
# GDS routing metal. Signal pins keep their audited rectangles. Supply pins
# (USE POWER/GROUND) also own the master metal polygons that physically touch
# their audited rectangle on the same layer: that metal is the same conductor,
# and marking it OBS makes the router see a "short" against its own rail.
import pya, json, re, hashlib
from pathlib import Path

base = Path('/input'); out = Path('/work/precise'); out.mkdir(parents=True, exist_ok=True)
inputs = json.loads((base/'pin-inputs.json').read_text())
pin_audit = json.loads((base/'pin-audit.json').read_text())
layers = pin_audit['pdk_layers']
assert pin_audit['status'] == 'pass', 'pin audit must pass'
rows = []
# A master pin is a supply pin when its LEF says USE POWER/GROUND or when
# any placed instance ties it to a supply net (IP pins typed SIGNAL, the
# grounded EN3 of the PLL bank, the biasgen ref_in tie).
placement = json.loads((base/'geometry-audit.json').read_text())
terminals = json.loads((base/'physical-terminals.json').read_text())
master_of = {i['name']: i['master'] for i in placement['instances']}
tied = {}
for net, terms in terminals['nets'].items():
    if net in ('VDD', 'VSS') or net.startswith('RAIL_'):
        for t in terms:
            tied.setdefault(master_of[t['instance']], set()).add(t['pin'])


def fmt_poly(poly, dbu):
    box = poly.bbox()
    if (pya.Region(poly) ^ pya.Region(box)).is_empty():
        return 'RECT ' + ' '.join(f'{v*dbu:.3f}' for v in [box.left, box.bottom, box.right, box.top])
    return 'POLYGON ' + ' '.join(f'{v*dbu:.3f}' for p in poly.each_point_hull() for v in [p.x, p.y])


for item in inputs['cells']:
    for kind in ['gds', 'lef']:
        assert hashlib.sha256((base/item[kind]).read_bytes()).hexdigest() == item[kind+'_sha256'], item[kind]
    layout = pya.Layout(); layout.read(str(base/item['gds'])); cell = layout.cell(item['cell']); assert cell is not None
    dbu = layout.dbu
    text = (base/item['lef']).read_text()
    supply_pins = set(re.findall(r'PIN (\S+)\s+DIRECTION \w+ ;\s+USE (?:POWER|GROUND) ;', text)) | tied.get(item['cell'], set())
    pins = {name: pya.Region() for name in layers}
    pg_extra = {}
    metal = {}
    for name, gds in layers.items():
        i = layout.find_layer(*gds)
        metal[name] = pya.Region(cell.begin_shapes_rec(i)) if i is not None else pya.Region()
        metal[name].merge()
    for pin in pin_audit['pin_details']:
        if pin['cell'] != item['cell']:
            continue
        assert pin['dbu_um'] == dbu
        for shape in pin['shapes']:
            box = pya.Box(*shape['box_dbu'])
            pins[shape['layer']].insert(box)
            if pin['pin'] in supply_pins:
                # Clip to a 3 um halo: enough to remove same-conductor notches
                # at the pin, without turning large IP rings into pin shapes
                # (which makes router pin access explode).
                owned = metal[shape['layer']].interacting(pya.Region(box)) & pya.Region(box.enlarged(round(3/dbu), round(3/dbu)))
                pg_extra.setdefault(pin['pin'], {}).setdefault(shape['layer'], pya.Region()).insert(owned)
    owned_all = {name: pya.Region() for name in layers}
    for pin, by_layer in pg_extra.items():
        for layer, region in by_layer.items():
            owned_all[layer] += region
    # Supply pin ports: add the owned polygons to the PORT of that pin.
    added = 0
    for pin, by_layer in pg_extra.items():
        m = re.search(r'(  PIN '+re.escape(pin)+r'\n.*?    PORT\n)(.*?)(    END\n)', text, re.S)
        assert m, (item['cell'], pin)
        extra = []
        for layer, region in by_layer.items():
            region.merge()
            extra.append('      LAYER '+layer+' ;')
            for poly in region.each():
                extra.append('        '+fmt_poly(poly, dbu)+' ;'); added += 1
        text = text[:m.end(2)] + '\n'.join(extra) + '\n' + text[m.end(2):]
    match = re.search(r'\n  OBS\n(.*?)\n  END\n(?=END)', text, re.S); assert match, item['cell']
    blocks = re.split(r'(?=\s*LAYER\s+)', match[1])
    obs = ['  OBS']
    for b in blocks:
        m = re.search(r'LAYER\s+(\w+)', b)
        if m and m[1] not in layers:
            obs.append(b.strip())
    # MIM top plate (FuseTop, GDS 75/0): Metal4 (the MIM bottom-plate layer)
    # must keep MIMTM.1 spacing from it. That spacing is not a Metal4-to-
    # Metal4 rule the router knows, so the plate grown by 1.2 um is Metal4
    # OBS (a Metal4 route 0.75 um from a biasgen C2 plate failed MIMTM.1).
    fi = layout.find_layer(75, 0)
    mim_keepout = (pya.Region(cell.begin_shapes_rec(fi)).merged().sized(round(1.2/dbu))
                   if fi is not None else pya.Region())
    count = 0
    for name in layers:
        region = metal[name] - pins[name] - owned_all[name]
        if name == 'Metal4' and not mim_keepout.is_empty():
            region = (region + (mim_keepout - pins[name] - owned_all[name])).merged()
        if region.is_empty():
            continue
        obs.append('    LAYER '+name+' ;')
        for shape in region.decompose_trapezoids():
            obs.append('      '+fmt_poly(shape.polygon, dbu)+' ;'); count += 1
    obs.append('  END')
    text = text[:match.start()]+'\n'+'\n'.join(obs)+'\n'+text[match.end():]
    (out/item['lef']).write_text(text)
    rows.append(dict(cell=item['cell'], obstruction_shapes=count, mim_keepout_polygons=mim_keepout.count(), supply_pins=sorted(supply_pins),
                     supply_owned_polygons=added, source_gds_sha256=item['gds_sha256'],
                     source_lef_sha256=item['lef_sha256'], precise_lef_sha256=hashlib.sha256(text.encode()).hexdigest()))
(out/'manifest.json').write_text(json.dumps(dict(
    status='precise_abstracts',
    scope='Signal pin rectangles unchanged; supply pins additionally own their touching same-layer master metal; '
          'OBS is all other real GDS routing metal; non-routing process-layer obstructions retained.',
    cells=rows), indent=2)+'\n')
print('PRECISE_ABSTRACTS', len(rows), sum(r['obstruction_shapes'] for r in rows), 'supply-owned', sum(r['supply_owned_polygons'] for r in rows))
