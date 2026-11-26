import json, sys, collections, plan_lib as P
E_ = json.load(open(sys.argv[1])); D = json.load(open(sys.argv[2])); run = sys.argv[3]
L = P.read_lef(run); R = E_['rect']; O = E_['orient']; C = D['comp']
def pin(i, p):
    m = C[i]['master']; pp = L[m]['pins'].get(p); r = R[i]
    if not pp: return ((r[0]+r[2])/2, (r[1]+r[3])/2)
    a, b = P.tr(O[i], pp[0], pp[1], L[m]['w'], L[m]['h']); return (r[0]+a, r[1]+b)
res = E_['res']
print('keepaway', [(a, v, d, g) for a, v, d, g, ok in res['keepaway']])
print('adjacency', [(a, b, d, g, ok) for a, b, d, g, ok in res['adjacency']])
print('g4', res['g4']); print('decap', res['decap_placed'], '/', res['decap_total'], 'unplaced small', res['unplaced_small'])
# island rails: switch -> farthest load (Manhattan between rect centres)
for n, v in D['nets'].items():
    if not n.startswith('RAIL_'): continue
    ends = [e[0] for e in v['ends'] if e[0] in R]
    sw = [e for e in ends if e.startswith('isw')]
    if not sw: continue
    s = R[sw[0]]; sc = ((s[0]+s[2])/2, (s[1]+s[3])/2)
    d = {e: round(abs((R[e][0]+R[e][2])/2-sc[0])+abs((R[e][1]+R[e][3])/2-sc[1])) for e in ends if e not in sw and not e.startswith(('atb', 'iso', 'pdn'))}
    print('island', n, sw, 'max', max(d.items(), key=lambda t: t[1]) if d else None)
for n in ('LO_IP', 'LO_QP', 'LOI_IP', 'REF_IN', 'AUX_CLK_P', 'TXS_P', 'TXI_P', 'BBI_TX_P', 'DACI_P', 'ADCI_P', 'ADCQ_P', 'VREG_TX', 'VREG_CDR', 'LO_VTUNE', 'RF_RX_P', 'RF_TX_P', 'HSRX_P', 'WIRE_TX_P'):
    v = D['nets'].get(n)
    if not v: continue
    pts = [(e[0], pin(e[0], e[1]) if e[0] in R else (e[2], e[3])) for e in v['ends'] if not e[0].startswith('antd')]
    src = pts[0]
    print('net', n, [(q[0], round(abs(q[1][0]-src[1][0])+abs(q[1][1]-src[1][1]))) for q in pts[1:]], 'from', src[0])
print('macro pins per side', collections.Counter(s for s, x, y in E_['mpins'].values()))
cs = collections.Counter(s for n, (s, x, y) in E_['mpins'].items() if n.startswith('c_')); print('c_* per side', cs)
