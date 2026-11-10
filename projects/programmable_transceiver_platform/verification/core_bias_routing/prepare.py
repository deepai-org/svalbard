# OpenROAD Python stage. Usage: openroad -python prepare.py power|signal
#
# power : fresh database from the audited placement. All 152 nets and 122
#         boundary pins exist, but only the seven supply nets are connected to
#         their instance terminals, so the router builds the power network
#         first in an otherwise empty channel set. Supply nets are temporarily
#         routed as non-special nets with a wide non-default rule (NDR).
# signal: start from the routed power database. Convert every supply wire to
#         FIXED special wiring (electrical POWER/GROUND role restored,
#         master terminal types restored), then connect the 145 signal nets so
#         the signal router treats the finished power network as fixed metal.
import odb, json, hashlib, re, sys
from pathlib import Path

mode = sys.argv[-1]; assert mode in ('power', 'signal'), mode
base = Path('/input'); work = Path('/work')
placement = json.loads((base/'geometry-audit.json').read_text())
terminals = json.loads((base/'physical-terminals.json').read_text())
pins = json.loads((base/'pin-inputs.json').read_text())
TLEF = '/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef'
SUPPLY = lambda n: n in ('VDD', 'VSS') or n.startswith('RAIL_')
ROLE = lambda n: 'GROUND' if n == 'VSS' else 'POWER'
# Wide rule: 2 um on Metal2-Metal4 (EM/IR margin, see supply_ir.py). Metal5 stays
# minimum width: the bank supply pins are 0.44 um strips at 0.6 um gaps, and a
# 2 um Metal5 wire there produced an unreported short (VSS/RAIL_wired) in trial 1;
# spacing never below the technology minimum (MT.2a = 0.46 um on Metal5).
NDR_WIDTH = {1: .23, 2: 2.0, 3: 2.0, 4: 2.0, 5: .44}
NDR_SPACE = {1: .23, 2: .28, 3: .28, 4: .28, 5: .46}
# VDD/VSS carry the whole block current (1 mA budget + returned rail current):
# at 2 um their max-corner IR drop exceeded 10 mV, so they get 4 um on
# Metal2-Metal4 (supply_ir.py). Rails (<= 0.22 mA) keep 2 um.
MAIN_WIDTH = {1: .23, 2: 4.0, 3: 4.0, 4: 4.0, 5: .44}
PG_PIN_HALF = 2.0
SIG_PITCH = 2.8
# Die size: the placement's die_um (compact I9 placement) or the original 1000 x 400 um.
DIE_W, DIE_H = placement.get('die_um', [1000., 400.])


def term_geoms(it, u):
    return [(l.getName(), tuple(round(v/u*1000) for v in [r.xMin(), r.yMin(), r.xMax(), r.yMax()]))
            for l, r in it.getGeometries()]


def contains(outer, inner):
    return outer[0] <= inner[0] and outer[1] <= inner[1] and outer[2] >= inner[2] and outer[3] >= inner[3]


if mode == 'power':
    (work/'tech.lef').write_bytes(Path(TLEF).read_bytes())  # for the KLayout DEF cross-check
    db = odb.dbDatabase.create(); odb.read_lef(db, TLEF)
    for item in pins['cells']:
        odb.read_lef(db, str(work/'precise'/item['lef']))
    tech = db.getTech(); u = tech.getDbUnitsPerMicron()
    chip = odb.dbChip.create(db, tech); block = odb.dbBlock.create(chip, 'pt_core_bias')
    block.setDefUnits(u); block.setDieArea(odb.Rect(0, 0, round(DIE_W*u), round(DIE_H*u)))
    nets = {name: odb.dbNet.create(block, name) for name in terminals['nets']}
    instances = {}
    for place in placement['instances']:
        inst = odb.dbInst.create(block, db.findMaster(place['master']), place['name'])
        inst.setOrient('R0'); inst.setLocation(round(place['bbox_um'][0]*u), round(place['bbox_um'][1]*u))
        inst.setPlacementStatus('FIRM'); instances[place['name']] = inst
    # Every audited terminal rectangle must be present at its audited place.
    # Signal pins match exactly; supply pins may additionally own touching
    # master metal (precise_lefs.py) but must still contain the audited shapes.
    errors = []; coordinates = {}; checked = 0
    for name, terms in terminals['nets'].items():
        for term in terms:
            it = instances[term['instance']].findITerm(term['pin']); assert it is not None, term
            actual = term_geoms(it, u)
            expected = [(s['layer'], tuple(s['box_dbu'])) for s in term['shapes']]
            supply_pin = SUPPLY(name)
            ok = all(any(l == el and contains(b, eb) for l, b in actual) for el, eb in expected) if supply_pin \
                else sorted(actual) == sorted(expected)
            if not ok:
                errors.append(dict(instance=term['instance'], pin=term['pin'], actual=actual, expected=expected))
            coordinates.setdefault(name, []).extend([((b[0]+b[2])/2000, (b[1]+b[3])/2000) for _, b in expected])
            if SUPPLY(name):
                it.connect(nets[name])
            checked += 1
    assert not errors, errors[:3]
    # Boundary pins: supply pins first (4 x 4 um), then signal pins on free
    # tracks at >= 2.8 um pitch and clear of the wide supply pins.
    occupied = {s: [] for s in ['left', 'right', 'top', 'bottom']}; boundary = []
    order = sorted(terminals['boundary_pins'], key=lambda n: (not SUPPLY(n), n))
    for name in order:
        points = coordinates[name]; x = sum(v[0] for v in points)/len(points); y = sum(v[1] for v in points)/len(points)
        half = PG_PIN_HALF if SUPPLY(name) else .28
        candidates = []
        for side, dist, desired, limit in [('left', x, y, DIE_H), ('right', DIE_W-x, y, DIE_H), ('bottom', y, x, DIE_W), ('top', DIE_H-y, x, DIE_W)]:
            positions = [.28+.56*k for k in range(18, round((limit-10)/.56))]
            positions = [v for v in positions if all(abs(v-o) >= SIG_PITCH+max(0, half-.28)+max(0, oh-.28)-1e-8 for o, oh in occupied[side])]
            if positions:
                pos = min(positions, key=lambda v: abs(v-desired)); candidates.append((dist+abs(pos-desired), side, pos))
        _, side, pos = min(candidates); occupied[side].append((pos, half))
        if side in ['left', 'right']:
            layer = tech.findLayer('Metal3'); cx = 5 if side == 'left' else DIE_W-5; cy = pos; dx = .56; dy = .28
        else:
            layer = tech.findLayer('Metal4'); cx = pos; cy = 5 if side == 'bottom' else DIE_H-5; dx = .28; dy = .56
        if SUPPLY(name):
            dx = dy = PG_PIN_HALF
        bt = odb.dbBTerm.create(nets[name], name)
        bt.setIoType('INOUT' if SUPPLY(name) else 'INPUT' if name.startswith(('C_', 'EN_', 'ON_')) else 'OUTPUT')
        bp = odb.dbBPin.create(bt); bp.setPlacementStatus('FIRM')
        rect = [round(v*u) for v in [cx-dx, cy-dy, cx+dx, cy+dy]]
        odb.dbBox.create(bp, layer, *rect)
        boundary.append(dict(net=name, side=side, layer=layer.getName(), rect_um=[v/u for v in rect],
                             electrical_use=ROLE(name) if SUPPLY(name) else 'SIGNAL'))
    assert checked == 283 and len(boundary) == 122 and len(nets) == 152, (checked, len(boundary), len(nets))
    ndr = odb.dbTechNonDefaultRule.create(block, 'core_bias_supply_2um')  # block NDR: decoder resolves rules per block
    ndr_main = odb.dbTechNonDefaultRule.create(block, 'core_bias_main_4um')
    for rule_set, widths in ((ndr, NDR_WIDTH), (ndr_main, MAIN_WIDTH)):
        for level in range(1, 6):
            rule = odb.dbTechLayerRule.create(rule_set, tech.findLayer('Metal'+str(level)))
            rule.setWidth(round(widths[level]*u)); rule.setSpacing(round(NDR_SPACE[level]*u))
    mterm_roles = {}
    for name in nets:
        if SUPPLY(name):
            net = nets[name]; net.setSigType('SIGNAL'); net.setNonDefaultRule(ndr_main if name in ('VDD', 'VSS') else ndr)
            for it in net.getITerms():
                mt = it.getMTerm(); mterm_roles.setdefault(mt.getMaster().getName()+'/'+mt.getName(), mt.getSigType()); mt.setSigType('SIGNAL')
            for bt in net.getBTerms():
                bt.setSigType('SIGNAL')
    # Keep supply wires from running along the biasgen bottom edge under the
    # avdd pin: a wide wire there leaves a 0.19 um same-net notch to the pin.
    # Removed again before signal routing.
    keepouts = []
    for inst_name, pin_name in [('Xbiasgen', 'avdd'), ('Xbiasgen', 'avss')]:
        bb = instances[inst_name].findITerm(pin_name).getBBox()
        ob = odb.dbObstruction.create(block, tech.findLayer('Metal4'), bb.xMin()-u, 0, bb.xMax()+u, bb.yMin())
        keepouts.append([inst_name, pin_name, bb.xMin()-u, 0, bb.xMax()+u, bb.yMin()])
    odb.write_db(db, str(work/'power-placed.odb')); odb.write_def(block, str(work/'power-placed.def'))
    report = dict(status='power_database_prepared', dbu_per_um=u, instances=len(instances), nets=len(nets),
                  instance_terminals=checked, supply_terminals=sum(len(terminals['nets'][n]) for n in nets if SUPPLY(n)),
                  boundary_pins=len(boundary), boundary=boundary, power_stage_keepouts_dbu=keepouts, mterm_roles=mterm_roles,
                  ndr=dict(name='core_bias_supply_2um', width_um=NDR_WIDTH, spacing_um=NDR_SPACE, main_name='core_bias_main_4um', main_width_um=MAIN_WIDTH),
                  pin_geometry_match='signal terminals exact; supply terminals contain every audited rectangle',
                  source_hashes={str(base/f): hashlib.sha256((base/f).read_bytes()).hexdigest() for f in
                                 ['geometry-audit.json', 'placement-inputs.json', 'physical-terminals.json', 'pin-inputs.json']},
                  tech_lef_sha256=hashlib.sha256(Path(TLEF).read_bytes()).hexdigest())
    (work/'import-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print('CORE_BIAS_POWER_DB', checked, 'terminals', len(boundary), 'boundary pins', len(nets), 'nets')
else:
    db = odb.dbDatabase.create(); odb.read_db(db, str(work/'power-routed.odb'))
    tech = db.getTech(); block = db.getChip().getBlock(); u = tech.getDbUnitsPerMicron()
    report = json.loads((work/'import-report.json').read_text())
    arrays = {}; converted = {}; cuts = {}; tcl = ['set b [ord::get_db_block]', 'set t [[ord::get_db] getTech]']
    data = json.loads((work/'power-wires.json').read_text())['nets']
    for net in block.getNets():
        name = net.getName()
        if not SUPPLY(name):
            continue
        wire = net.getWire(); assert wire is not None, ('supply not routed', name)
        # Rebuild the identical routed geometry as FIXED special wiring.
        # odb's Python binding lacks dbWireShapeType, so emit Tcl for it.
        tcl.append(f'set sw [odb::dbSWire_create [$b findNet {name}] FIXED]')
        n = 0
        for s in data[name]['shapes']:
            if s['kind'] in ('segment', 'patch'):
                tcl.append(f"odb::dbSBox_create $sw [$t findLayer {s['layer']}] {' '.join(map(str, s['box_dbu']))} NONE"); n += 1
        metal = [(s['layer'], s['box_dbu']) for s in data[name]['shapes'] if s['kind'] in ('segment', 'patch')]
        for v in data[name]['vias']:  # every router cut is fixed: seed the spacing check
            mv = re.match(r'Via(\d)', v['via'])
            if mv:
                cuts.setdefault((name, int(mv[1])), []).append((v['x'], v['y']))
        for v in data[name]['vias']:
            finder = '$t' if v['tech'] else '$b'
            tcl.append(f"odb::dbSBox_create $sw [{finder} findVia {v['via']}] {v['x']} {v['y']} NONE"); n += 1
            # Router vias are single cuts. Fill the overlap of the widest
            # same-net routed rectangles on both layers that contain the cut
            # with a cut array on the router cut's grid (0.26 um cuts; 0.52 um
            # pitch up to 3 x 3, else 0.62 um pitch = 0.36 um array spacing,
            # Vn.2b; 0.06 um enclosure on both layers, all four sides), so every
            # supply transition carries its current on as many cuts as fit
            # (supply_ir.py: GF180 DRM 14.2 per-cut EM rating and max-corner
            # 15 ohm/cut).
            m = re.match(r'Via(\d)', v['via'])
            if not m:
                continue
            level = int(m[1]); x, y = v['x'], v['y']; h = round(.13*u); enc = round(.06*u)
            def holders(layer):
                return [b for l, b in metal if l == layer and b[0] <= x-h-enc and b[1] <= y-h-enc and b[2] >= x+h+enc and b[3] >= y+h+enc]
            best = None
            for a in holders(f'Metal{level}'):
                for b in holders(f'Metal{level+1}'):
                    r = [max(a[0], b[0])+enc+h, max(a[1], b[1])+enc+h, min(a[2], b[2])-enc-h, min(a[3], b[3])-enc-h]
                    if best is None or (r[2]-r[0])*(r[3]-r[1]) > (best[2]-best[0])*(best[3]-best[1]):
                        best = r
            if best is None:
                continue
            def grid(pitch):
                xs = [x+k*pitch for k in range(-40, 41) if best[0] <= x+k*pitch <= best[2]]
                ys = [y+k*pitch for k in range(-40, 41) if best[1] <= y+k*pitch <= best[3]]
                return xs, ys
            xs, ys = grid(round(.52*u))
            if len(xs) > 3 or len(ys) > 3:
                xs, ys = grid(round(.62*u))
            added = 0
            placed = cuts[(name, level)]
            for cx in xs:
                for cy in ys:
                    # Arrays filled from two nearby router cuts sit on offset
                    # grids; skip any cut closer than the 0.62 um array pitch
                    # (0.36 um spacing, Vn.2b) to one already placed.
                    if (cx, cy) != (x, y) and all(max(abs(cx-px), abs(cy-py)) >= round(.62*u) for px, py in placed):
                        placed.append((cx, cy))
                        tcl.append(f"odb::dbSBox_create $sw [$t findLayer Via{level}] {cx-h} {cy-h} {cx+h} {cy+h} NONE"); n += 1; added += 1
            if added:
                arrays.setdefault(name, []).append(len(xs)*len(ys))
        odb.dbWire.destroy(wire)
        net.setSpecial(); net.setSigType(ROLE(name))
        for bt in net.getBTerms():
            bt.setSigType(ROLE(name))
        converted[name] = n
    (work/'supply-sboxes.tcl').write_text('\n'.join(tcl)+'\n')
    for key, role in report['mterm_roles'].items():
        master, pin = key.split('/'); db.findMaster(master).findMTerm(pin).setSigType(role)
    for ob in list(block.getObstructions()):
        odb.dbObstruction.destroy(ob)
    instances = {i.getName(): i for i in block.getInsts()}
    connected = 0
    for name, terms in terminals['nets'].items():
        if SUPPLY(name):
            continue
        net = block.findNet(name)
        for term in terms:
            instances[term['instance']].findITerm(term['pin']).connect(net); connected += 1
    roles = {n.getName(): n.getSigType() for n in block.getNets() if SUPPLY(n.getName())}
    assert all(roles[n] == ROLE(n) for n in roles) and len(converted) == 7, roles
    attached = sum(1 for n in block.getNets() for _ in n.getITerms())
    assert attached == 283, attached
    odb.write_db(db, str(work/'signal-placed.odb')); odb.write_def(block, str(work/'signal-placed.def'))
    (work/'signal-import-report.json').write_text(json.dumps(dict(
        status='signal_database_prepared', supply_special_boxes=converted, supply_via_arrays_cuts=arrays, supply_roles=roles,
        signal_terminals_connected=connected, instance_terminals=attached), indent=2)+'\n')
    print('CORE_BIAS_SIGNAL_DB', connected, 'signal terminals', converted)
