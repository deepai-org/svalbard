"""Effective DC resistance on one net of an extracted R+C netlist: port node -> each listed node, and the parallel
'all sinks' resistance (unit current shared by equal-voltage sinks is not assumed: reports each and the min/median).
usage: netr.py <rc.spice> <net> <port-node> [regex of target nodes]"""
import sys, re, numpy as np
f, net, port = sys.argv[1:4]; rx = re.compile(sys.argv[4]) if len(sys.argv) > 4 else None
b = lambda n: re.sub(r'\.(t|n)\d+$', '', n)
R = [l.split() for l in open(f) if l.startswith('R')]
R = [(a, c, float(v)) for _, a, c, v, *_ in R if b(a) == net and b(c) == net]
nodes = sorted({x for a, c, _ in R for x in (a, c)}); ix = {n: i for i, n in enumerate(nodes)}
N = len(nodes); G = np.zeros((N, N))
for a, c, v in R:
    i, j = ix[a], ix[c]; g = 1 / max(v, 1e-6); G[i, i] += g; G[j, j] += g; G[i, j] -= g; G[j, i] -= g
p = ix[port]; keep = [i for i in range(N) if i != p]; Gr = G[np.ix_(keep, keep)]
Z = np.linalg.pinv(Gr)
tg = [n for n in nodes if n != port and (rx is None or rx.search(n))]
rs = sorted((Z[keep.index(ix[n]), keep.index(ix[n])], n) for n in tg)
print(f'{net}: {len(R)} R, {N} nodes; R(port->node) min {rs[0][0]:.3f} median {rs[len(rs)//2][0]:.3f} max {rs[-1][0]:.3f} ({rs[-1][1]})')
if len(sys.argv) > 5:
    sel = [keep.index(ix[n]) for n in sys.argv[5].split(',')]
    # all listed nodes shorted together and driven by 1 A from them to the port
    Zs = Z[np.ix_(sel, sel)]; print('parallel (sinks tied):', 1 / np.linalg.inv(Zs).sum())
