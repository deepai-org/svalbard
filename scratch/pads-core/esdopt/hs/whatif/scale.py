"""scale.py in.spice out.spice k: pad-site diodes (nodes PAD_x__dn / PAD_x__up) get area and pj times k = k x the fingers,
lumped at the same nodes (finger metal not added: optimistic on metal, exact on the diode resistance and junction C)."""
import sys, re
k = float(sys.argv[3]); n = 0; out = []
for l in open(sys.argv[1]).read().splitlines():
    t = l.split()
    if t and t[0][0] == 'D' and any(x.endswith(('__dn', '__up')) for x in t[1:3]):
        l = re.sub(r'(pj|area)=([0-9.]+)([up])', lambda m: f'{m[1]}={float(m[2])*k:g}{m[3]}', l); n += 1
    out.append(l)
open(sys.argv[2], 'w').write('\n'.join(out) + '\n'); print('scaled', n, 'site diodes by', k)
