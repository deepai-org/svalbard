"""Wire-length metric from a dry run (M4 track + M5 trunk length per net, um)."""
import sys, re
import dry, ser8d_macro as D
def wl(rep):
    out = {}
    for t in rep['routes']['tracks']:
        if t['net'] in ('VDD', 'VSS'): continue
        out[t['net']] = out.get(t['net'], 0) + t['hi'] - t['lo']
    for t in rep['routes']['trunks']:
        out[t['net']] = out.get(t['net'], 0) + t['hi'] - t['lo']
    return out
def show(tag, rows, **kw):
    kw.setdefault('em', {}); rep = dry.dry(rows, tag, **kw)
    w = wl(rep)
    g = lambda pat: [round(w.get(n, 0)) for n in sorted((n for n in w if re.fullmatch(pat, n)), key=lambda s: [int(x) for x in re.findall(r'\d+', s)])]
    print('    PH', g(r'PH\d+'), '\n    Q ', g(r'Q\d'), '\n    F ', g(r'F\d'), '\n    B ', g(r'B\d_0'), ' R', g(r'R\d_\d'),
          '\n    D sum', round(sum(v for n, v in w.items() if re.fullmatch(r'D\d+', n))), 'LDA', round(w.get('LDA', 0)), 'QK', g(r'QK\d'), 'QRST', round(w.get('QRST', 0)), 'total', round(sum(w.values())))
    px = {n: rep['trunk_x'][n] for n in rep['trunk_x'] if re.fullmatch(r'PH\d+|F\d', n)}
    print('    pin x F', [round(px[f'F{k}']) for k in range(8)], 'PH', [round(px[p]) for p in D.PORTS if p.startswith('PH')])
    return rep
if __name__ == '__main__':
    import variants2
    for tag, rows, kw in variants2.VARIANTS:
        show(tag, rows, **kw)
