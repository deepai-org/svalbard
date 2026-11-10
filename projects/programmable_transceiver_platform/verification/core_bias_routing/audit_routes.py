# KLayout stage, independent of the router: usage
#   klayout -b -rd wires=<json> -rd report=<json> -r audit_routes.py
# For every one of the 152 nets, using only exported rectangles, the audited
# terminal map and the qualified master GDS:
#  * the net's route metal, its terminal rectangles and boundary pins form ONE
#    component (vias must land on metal both below and above);
#  * every instance terminal and boundary pin is touched;
#  * route metal never touches another net's route, terminal or boundary metal;
#  * route metal never touches master metal other than polygons that carry
#    that net's own terminal (catches shorts into IP-internal conductors that
#    a DRC run merges silently).
import pya, json, hashlib
from pathlib import Path

source = Path('/input'); out = Path('/work')
wires_path = Path(wires); report_path = Path(report)  # noqa: F821  (klayout -rd)
w = json.loads(wires_path.read_text()); terminals = json.loads((source/'physical-terminals.json').read_text())
placement = json.loads((source/'geometry-audit.json').read_text())
LAYERS = {'Metal1': (34, 0), 'Metal2': (36, 0), 'Metal3': (42, 0), 'Metal4': (46, 0), 'Metal5': (81, 0)}
METALS = list(LAYERS)
assert set(w['nets']) == set(terminals['nets']) and len(w['nets']) == 152

# Master metal of the whole placement, in route DBU (2 per GDS DBU).
gds = pya.Layout(); gds.read(str(source/'pt_core_bias_placement.gds')); top = gds.cell('pt_core_bias_placement')
master = {}
for name, (ln, dt) in LAYERS.items():
    i = gds.find_layer(ln, dt)
    r = pya.Region(top.begin_shapes_rec(i)) if i is not None else pya.Region()
    master[name] = r.transformed(pya.ICplxTrans(2.0)).merged()

errors = []; checked = 0; bpins = 0; polygons = 0; route_regions = {}; own_regions = {}
for name, net in w['nets'].items():
    regions = {m: pya.Region() for m in METALS}; cuts = []; route = {m: pya.Region() for m in METALS}
    for shape in net['shapes']:
        box = pya.Box(*shape['box_dbu'])
        if shape['layer'].startswith('Via'):
            cuts.append((int(shape['layer'][-1]), box))
        else:
            regions[shape['layer']].insert(box); route[shape['layer']].insert(box)
    own = {m: pya.Region() for m in METALS}
    for term in terminals['nets'][name]:
        for shape in term['shapes']:
            box = pya.Box(*[2*v for v in shape['box_dbu']])
            regions[shape['layer']].insert(box)
            own[shape['layer']] += master[shape['layer']].interacting(pya.Region(box))
    for pin in net['pins']:
        regions[pin['layer']].insert(pya.Box(*pin['box_dbu'])); route[pin['layer']].insert(pya.Box(*pin['box_dbu']))
    # Owned master polygons are real conductors of this net: include them so
    # a route that lands on a supply ring away from the audited rectangle is
    # still recognised as connected.
    for m in METALS:
        regions[m] += own[m]
    nodes = []
    for layer, r in regions.items():
        for p in r.merged().each():
            nodes.append((layer, p))
    polygons += len(nodes)
    parent = list(range(len(nodes)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    index = {m: [(i, pya.Region(p)) for i, (l, p) in enumerate(nodes) if l == m] for m in METALS}

    def hits(layer, box):
        rb = pya.Region(box)
        return [i for i, r in index[layer] if not (r & rb).is_empty()]
    for level, box in cuts:
        below = hits('Metal'+str(level), box); above = hits('Metal'+str(level+1), box)
        if len(below) != 1 or len(above) != 1:
            errors.append(dict(net=name, reason='via without metal landing', level=level, box=list(box.to_s().split(';'))))
            continue
        parent[root(above[0])] = root(below[0])
    roots = {root(i) for i in range(len(nodes))}
    if len(roots) != 1:
        errors.append(dict(net=name, reason='disconnected net', components=len(roots)))
    for term in terminals['nets'][name]:
        touched = []
        for shape in term['shapes']:
            touched += hits(shape['layer'], pya.Box(*[2*v for v in shape['box_dbu']]))
        if not touched:
            errors.append(dict(net=name, instance=term['instance'], pin=term['pin'], reason='terminal not reached'))
        checked += 1
    for pin in net['pins']:
        bpins += 1
        # attached = touches this net's route metal (not merely itself)
        wire_only = pya.Region([pya.Box(*x['box_dbu']) for x in net['shapes'] if x['layer'] == pin['layer']])
        if wire_only.interacting(pya.Region(pya.Box(*pin['box_dbu']))).is_empty():
            errors.append(dict(net=name, pin=pin['name'], reason='boundary pin unattached'))
    # Route metal of this net against foreign master metal.
    for m in METALS:
        if route[m].is_empty():
            continue
        foreign = master[m].interacting(route[m]) - own[m]
        if not foreign.is_empty():
            errors.append(dict(net=name, layer=m, reason='route touches master metal of another conductor',
                               at=[str(p.bbox()) for p in list(foreign.each())[:3]]))
    route_regions[name] = route; own_regions[name] = {m: own[m] + regions[m] for m in METALS}
# Distinct nets must never touch: route vs route/terminal/pin of every other net.
names = list(route_regions)
for m in METALS:
    for i, a in enumerate(names):
        ra = route_regions[a][m]
        if ra.is_empty():
            continue
        for b in names:
            if b == a:
                continue
            rb = own_regions[b][m]
            if not rb.is_empty() and not ra.interacting(rb).is_empty():
                errors.append(dict(net=a, other_net=b, layer=m, reason='metal contact between distinct nets'))
supply = [n for n in names if n in ('VDD', 'VSS') or n.startswith('RAIL_')]
result = dict(status='pass' if not errors else 'fail',
              scope='Independent union/via connectivity and short check of all 152 nets (145 signal + 7 supply) against '
                    'the audited terminal map, exported boundary metal and the qualified master GDS metal.',
              nets=len(names), supply_nets=supply, instance_terminals_checked=checked, boundary_pins_checked=bpins,
              metal_components=polygons, errors=errors[:200], error_count=len(errors),
              source_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                             [wires_path, source/'physical-terminals.json', source/'pt_core_bias_placement.gds', Path(__file__)]})
report_path.write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps({k: v for k, v in result.items() if k not in ('source_hashes', 'errors')}), errors[:3])
