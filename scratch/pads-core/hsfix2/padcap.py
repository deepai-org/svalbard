"""padcap.py <physical.spice> ...: PAD_P / PAD_N wiring C (sum of the Magic C lines on the net, as hspad/netcap.py) and its partners."""
import sys, re, collections
U = {'f': 1., 'p': 1e3, 'a': 1e-3, 'n': 1e6}
for path in sys.argv[1:]:
    tot = collections.Counter(); pair = collections.Counter()
    for line in open(path):
        t = line.split()
        if len(t) >= 4 and t[0][0] == 'C' and not t[3].startswith('cap_'):
            m = re.fullmatch(r'([0-9.eE+-]+)([fpan]?)F?', t[3])
            if not m: continue
            v = float(m[1]) * U.get(m[2], 1e15)
            for a, b in ((t[1], t[2]), (t[2], t[1])):
                if a in ('PAD_P', 'PAD_N'): tot[a] += v; pair[(a, b)] += v
    print(path.split('/')[-2], ' '.join(f'{n} {tot[n]:.1f} fF' for n in ('PAD_P', 'PAD_N')))
    for n in ('PAD_P', 'PAD_N'):
        print('   ', n, ' '.join(f'{b}:{v:.1f}' for (a, b), v in sorted(pair.items(), key=lambda q: -q[1]) if a == n and v >= 1.0))
