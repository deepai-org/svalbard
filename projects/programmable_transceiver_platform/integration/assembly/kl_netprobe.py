# Stage `netprobe` (tool image, KLayout python):  tool.sh <chip> python3 /asm/kl_netprobe.py NET [NET ...]
# Which non-router shapes does a routed top-level net touch? Every wire segment and via of NET in route/routed.def
# (default widths + 0.2 um halo) is queried against chip/pt_chip_top.gds on its own layer; shapes of the router
# wiring cell are skipped. Prints cell and die bbox of each hit: finds supply joins the router could not see
# (block metal missing from the abstract, grid shapes not in pt_pdn's LEF).
import re, sys, collections
import klayout.db as db
nets = set(sys.argv[1:])
LAY = {'Metal2': (36, 0.28), 'Metal3': (42, 0.28), 'Metal4': (46, 0.28), 'Metal5': (81, 0.44)}
VIA = {'Via1': (35, 'Metal2'), 'Via2': (38, 'Metal2'), 'Via3': (40, 'Metal3'), 'Via4': (41, 'Metal4')}
segs = collections.defaultdict(list); cur = None
for l in open('/run/route/routed.def'):
    m = re.match(r'\s*- (\S+) ', l)
    if m: cur = m.group(1) if m.group(1) in nets else None
    if cur is None: continue
    t = re.search(r'(?:ROUTED|NEW)\s+(Metal\d)\s+(.*)', l)
    if not t: continue
    ln, rest = t.group(1), t.group(2)
    pts = re.findall(r'\(\s*(\S+)\s+(\S+)(?:\s+\S+)?\s*\)', rest); px = py = None; P = []
    for x, y in pts:
        x = px if x == '*' else int(x); y = py if y == '*' else int(y); P.append((x, y)); px, py = x, y
    hw = int(LAY[ln][1]*1000/2) + int(float(__import__("os").environ.get("HALO", "0.2"))*1000)
    for a, b in zip(P, P[1:]) if len(P) > 1 else [(P[0], P[0])]:
        segs[(cur, ln)].append(db.Box(min(a[0], b[0])-hw, min(a[1], b[1])-hw, max(a[0], b[0])+hw, max(a[1], b[1])+hw))
    if len(P) >= 1 and re.search(r'\)\s+(\S+)\s*$', rest.strip()) and not rest.strip().endswith(')'):
        x, y = P[-1]; segs[(cur, 'Metal5' if ln == 'Metal4' else ('Metal4' if ln == 'Metal3' else 'Metal3'))].append(db.Box(x-500, y-500, x+500, y+500))
ly = db.Layout(); ly.read('/run/chip/pt_chip_top.gds'); top = ly.cell('pt_chip_top'); dbu = ly.dbu
skip = {'pt_top_wiring'}
hits = collections.Counter(); ex = {}
for (net, ln), boxes in segs.items():
    li = ly.find_layer(LAY[ln][0], 0)
    if li is None: continue
    for b in boxes:
        it = db.RecursiveShapeIterator(ly, top, li, db.Box(int(b.left/1000/dbu), int(b.bottom/1000/dbu), int(b.right/1000/dbu), int(b.top/1000/dbu)), True)
        while not it.at_end():
            path = [e.inst().cell.name for e in it.path()] if hasattr(it, 'path') else []
            cname = it.cell().name; root = path[0] if path else cname
            pg = it.shape().polygon
            ov = (db.Region(pg.transformed(it.trans())) & db.Region(db.Box(int(b.left/1000/dbu), int(b.bottom/1000/dbu), int(b.right/1000/dbu), int(b.top/1000/dbu)))) if pg is not None else db.Region()
            if root not in skip and cname not in skip and not ov.is_empty():
                sb = ov.bbox()
                k = (net, ln, root, cname); hits[k] += 1; ex.setdefault(k, (round(sb.left*dbu, 2), round(sb.bottom*dbu, 2), round(sb.right*dbu, 2), round(sb.top*dbu, 2)))
            it.next()
for k, v in hits.most_common(60): print(k, v, ex[k])
print('NETPROBE DONE', len(hits))
