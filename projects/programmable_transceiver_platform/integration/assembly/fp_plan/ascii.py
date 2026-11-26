import json, sys
E_ = json.load(open(sys.argv[1])); S = float(sys.argv[2]) if len(sys.argv) > 2 else 80.0
W, H = int(3932 / S) + 1, int(5122 / S / 2) + 1     # chars ~2:1 aspect: one row = 2*S um
g = [[' '] * W for _ in range(H)]
def put(r, ch):
    x0, y0, x1, y1 = r
    for yy in range(int(y0 / S / 2), min(H, int(y1 / S / 2 + 0.5))):
        for xx in range(int(x0 / S), min(W, int(x1 / S + 0.5))):
            g[H - 1 - yy][xx] = ch
for k, q in E_['keepouts']: put(q, '#')
for n, q in E_['channels'].items(): put(q, '.')
leg = {}; code = iter('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789')
big = sorted([(i, r) for i, r in E_['rect'].items() if (r[2] - r[0]) * (r[3] - r[1]) >= 15000 and not i.startswith('decap')], key=lambda t: -(t[1][2] - t[1][0]) * (t[1][3] - t[1][1]))
for i, r in E_['rect'].items():
    if i.startswith('decap'): put(r, ':')
for i, r in big:
    c = '@' if i == 'digital' else next(code); leg[c] = i; put(r, c)
print('+' + '-' * W + '+')
for row in g: print('|' + ''.join(row) + '|')
print('+' + '-' * W + '+')
print(f'1 char = {S:.0f} um wide x {2 * S:.0f} um tall; @ digital macro, # pad keep-out, . reserved routing channel, : decap')
print('  '.join(f'{c}={n}' for c, n in leg.items() if c != '@'))
