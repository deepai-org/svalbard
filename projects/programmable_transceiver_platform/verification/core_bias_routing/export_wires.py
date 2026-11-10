# OpenROAD Python stage. Usage: openroad -python export_wires.py <odb> <def> <json> <expected_regular> <expected_special>
# Exports every routed rectangle (regular dbWire paths, vias, patches and
# special dbSWire boxes) as absolute DBU rectangles, plus boundary pins.
import odb, json, hashlib, collections, re, sys
from pathlib import Path

odb_path, def_path, out_path, want_regular, want_special = sys.argv[-5:]
db = odb.dbDatabase.create(); odb.read_db(db, odb_path); b = db.getChip().getBlock(); u = db.getTech().getDbUnitsPerMicron()
nets = {}; counts = collections.Counter()
# The Python decoder does not expose RECT patch deltas; read them from the
# DEF written from the same database.
patches = {}
for entry in Path(def_path).read_text().split('\n    - ')[1:]:
    name = entry.split()[0]
    for m in re.finditer(r'(?:NEW|ROUTED)\s+(Metal[1-5])\s+(?:TAPER\s+)?\(\s+(-?\d+)\s+(-?\d+)\s+\)\s+RECT\s+\(\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+\)', entry):
        layer, x, y, *rect = m.groups(); patches.setdefault((name, layer, int(x), int(y)), []).append(list(map(int, rect)))
patch_count = sum(map(len, patches.values()))
regular = special = 0
for net in b.getNets():
    shapes = []; vias = []

    def add(layer, rect, kind):
        assert rect[0] < rect[2] and rect[1] < rect[3], (net.getName(), rect)
        shapes.append(dict(layer=layer, box_dbu=list(rect), kind=kind)); counts[kind] += 1

    if net.isSpecial():
        special += 1
        for sw in net.getSWires():
            for box in sw.getWires():
                if box.isVia():
                    x, y = box.getViaXY()
                    via = box.getTechVia() or box.getBlockVia()
                    vias.append(dict(via=via.getName(), tech=box.getTechVia() is not None, x=x, y=y))
                    for vb in via.getBoxes():
                        add(vb.getTechLayer().getName(), [x+vb.xMin(), y+vb.yMin(), x+vb.xMax(), y+vb.yMax()], 'via_shape')
                    counts['via_instances'] += 1
                else:
                    add(box.getTechLayer().getName(), [box.xMin(), box.yMin(), box.xMax(), box.yMax()], 'segment')
        wire = net.getWire()
        assert wire is None, ('special net also has regular wiring', net.getName())
    else:
        wire = net.getWire()
        if wire is None:
            nets[net.getName()] = dict(special=False, shapes=[], vias=[], pins=[]); continue
        regular += 1
        d = odb.dbWireDecoder(); d.begin(wire); layer = None; previous = None; rule = None

        def halfwidth(layer):
            # A non-default layer rule applies only on its own layer; tapered
            # pin-access paths are written without a rule (default width).
            if rule is not None and rule.getLayer().getName() == layer.getName():
                return rule.getWidth()//2
            return layer.getWidth()//2
        while True:
            op = d.next()
            if op == d.END_DECODE:
                break
            if op == d.PATH:
                layer = d.getLayer(); previous = None; rule = None  # getRule() is valid only after a RULE op
            elif op == d.RULE:
                rule = d.getRule()
            elif op in [d.POINT, d.POINT_EXT]:
                v = d.getPoint_ext() if op == d.POINT_EXT else d.getPoint(); x, y = v[:2]
                half = halfwidth(layer)
                ext = v[2] if len(v) > 2 else half
                if previous is not None:
                    px, py, pe, ph = previous
                    if (x, y) != (px, py):
                        assert x == px or y == py, (net.getName(), previous, v)
                        if y == py:
                            rect = [px-pe if px < x else x-ext, y-half, x+ext if px < x else px+pe, y+half]
                        else:
                            rect = [x-half, py-pe if py < y else y-ext, x+half, y+ext if py < y else py+pe]
                        add(layer.getName(), rect, 'segment')
                previous = (x, y, ext, half)
            elif op in [d.TECH_VIA, d.VIA]:
                assert previous is not None
                via = d.getTechVia() if op == d.TECH_VIA else d.getVia(); x, y = previous[:2]
                vias.append(dict(via=via.getName(), tech=op == d.TECH_VIA, x=x, y=y))
                for box in via.getBoxes():
                    add(box.getTechLayer().getName(), [x+box.xMin(), y+box.yMin(), x+box.xMax(), y+box.yMax()], 'via_shape')
                layer = d.getLayer()
                half = halfwidth(layer)
                previous = (x, y, half, half); counts['via_instances'] += 1
            elif op == d.RECT:
                assert previous is not None; x, y = previous[:2]; v = patches[(net.getName(), layer.getName(), x, y)].pop(0)
                add(layer.getName(), [x+v[0], y+v[1], x+v[2], y+v[3]], 'patch')
            elif op in [d.ITERM, d.BTERM]:
                continue
            else:
                raise AssertionError(('Unsupported wire opcode', op, net.getName()))
    pins = []
    for bt in net.getBTerms():
        for pin in bt.getBPins():
            for box in pin.getBoxes():
                pins.append(dict(name=bt.getName(), layer=box.getTechLayer().getName(), box_dbu=[box.xMin(), box.yMin(), box.xMax(), box.yMax()]))
    nets[net.getName()] = dict(special=net.isSpecial(), sig_type=net.getSigType(), shapes=shapes, vias=vias, pins=pins)
assert regular == int(want_regular) and special == int(want_special), (regular, special)
assert counts['patch'] == patch_count and not any(patches.values())
result = dict(status='routed_geometry_export', dbu_per_um=u, nets=nets, counts=counts, regular_routed=regular, special_routed=special,
              source_odb_sha256=hashlib.sha256(Path(odb_path).read_bytes()).hexdigest())
Path(out_path).write_text(json.dumps(result, indent=1)+'\n'); print('EXPORTED_GEOMETRY', regular, special, dict(counts))
