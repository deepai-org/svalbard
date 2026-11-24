"""Deck (lowered limit) items -> net via the nearest gate terminal; compare with the estimator per (net, level)."""
import sys, json, gzip, re, math
d = sys.argv[1]; rep = sys.argv[2]
terms = json.load(open(f'{d}/terms.json')); dbg = json.load(open(f'{d}/debug.json'))
g = [t for t in terms if t[3] == 'g']
LV = {'3': 2, '4': 3, '5': 4, '6': 5}
x = gzip.open(rep, 'rt').read()
deck = {}
for it in re.findall(r'<item>(.*?)</item>', x, re.S):
    c = re.search(r"ANT\.16_i_ANT\.(\d+)'", it)
    if not c or c.group(1) not in LV: continue
    v = {k: float(z) for k, z in re.findall(r'\[#(\w+)\] float: ([-0-9.e]+)', it)}
    pts = [tuple(map(float, p.split(','))) for p in re.search(r'polygon: \(([^)]*)\)', it).group(1).split(';')]
    cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
    t = min(g, key=lambda t: math.hypot(t[0] - cx, t[1] - cy)); dist = math.hypot(t[0] - cx, t[1] - cy)
    k = (t[2], LV[c.group(1)])
    if dist < 4 and (k not in deck or v['RATIO'] > deck[k]['RATIO']):
        deck[k] = dict(v, dist=round(dist, 2))
TH = {1: .54, 2: .54, 3: .54, 4: .54, 5: .9}
rows = []
for net, n, per, ga, s, di in dbg:
    est = per * TH[n] / (ga + 2 * (s + di))
    k = (net, n)
    if k in deck:
        dk = deck[k]; rows.append((net, n, round(est, 1), round(dk['RATIO'], 1), round(dk['RATIO'] / est, 2), round(per * TH[n], 1), round(dk['ANT_PERIMETER'], 1), ga, round(dk['GATE_AREA'], 2), s + di, round(dk['DIODES_AREA'], 3)))
print('net lvl est deck deck/est | est_per deck_per | est_gate deck_gate | est_diff deck_diff')
for r in sorted(rows, key=lambda r: -r[3]): print(*r)
