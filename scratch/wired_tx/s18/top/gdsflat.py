"""minimal GDS reader: flatten boundaries/boxes and texts (SREF/AREF translation + rotation 0/90/180/270 + reflection)."""
import struct, sys, math
from collections import defaultdict

def records(b):
    i = 0
    while i < len(b):
        n, t = struct.unpack('>HH', b[i:i + 4])
        if n == 0: break
        yield t >> 8, t & 0xff, b[i + 4:i + n]
        i += n

def r8(d):
    out = []
    for k in range(0, len(d), 8):
        x = d[k:k + 8]
        s = -1 if x[0] & 0x80 else 1
        e = (x[0] & 0x7f) - 64
        m = int.from_bytes(x[1:], 'big')
        out.append(s * m * 16.0 ** e / 2 ** 56)
    return out

def parse(path):
    b = open(path, 'rb').read()
    cells, cur, el, unit = {}, None, None, 1e-3
    for rt, dt, d in records(b):
        if rt == 0x03: unit = r8(d)[0]
        elif rt == 0x06: cur = cells.setdefault(d.rstrip(b'\0').decode(), dict(b=[], t=[], r=[]))
        elif rt in (0x08, 0x2d): el = dict(k='b')
        elif rt == 0x0c: el = dict(k='t')
        elif rt == 0x0a: el = dict(k='s', st=0, mag=1, ang=0)
        elif rt == 0x0b: el = dict(k='a', st=0, mag=1, ang=0)
        elif el is None: continue
        elif rt == 0x0d or rt == 0x16: el['l'] = struct.unpack('>h', d)[0]
        elif rt == 0x0e or rt == 0x17 or rt == 0x2e: el['d'] = struct.unpack('>h', d)[0]
        elif rt == 0x12: el['sn'] = d.rstrip(b'\0').decode()
        elif rt == 0x1a: el['st'] = struct.unpack('>H', d)[0]
        elif rt == 0x1c: el['ang'] = r8(d)[0]
        elif rt == 0x13: el['cr'] = struct.unpack('>hh', d)
        elif rt == 0x10:
            v = struct.unpack('>%di' % (len(d) // 4), d)
            el['xy'] = [(v[k] * unit, v[k + 1] * unit) for k in range(0, len(v), 2)]
        elif rt == 0x19: el['s'] = d.rstrip(b'\0').decode()
        elif rt == 0x11:
            if el['k'] == 'b': cur['b'].append(el)
            elif el['k'] == 't': cur['t'].append(el)
            else: cur['r'].append(el)
            el = None
    return cells

def xf(p, el, o):
    x, y = p
    if el['st'] & 0x8000: y = -y
    a = math.radians(el['ang']); c, s_ = round(math.cos(a)), round(math.sin(a))
    return (o[0] + x * c - y * s_, o[1] + x * s_ + y * c)

def flatten(cells, top):
    boxes, texts = defaultdict(list), []
    def go(name, f):
        c = cells[name]
        for e in c['b']:
            pts = [f(p) for p in e['xy']]
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            boxes[(e['l'], e.get('d', 0))].append((round(min(xs), 3), round(min(ys), 3), round(max(xs), 3), round(max(ys), 3), len(pts) > 5))
        for e in c['t']:
            texts.append((e['l'], e.get('d', 0), *[round(v, 3) for v in f(e['xy'][0])], e['s'], name))
        for e in c['r']:
            if e['k'] == 's':
                offs = [e['xy'][0]]
            else:
                (x0, y0), (x1, y1), (x2, y2) = e['xy']; nc, nr = e['cr']
                offs = [(x0 + i * (x1 - x0) / nc + j * (x2 - x0) / nr, y0 + i * (y1 - y0) / nc + j * (y2 - y0) / nr) for i in range(nc) for j in range(nr)]
            for o in offs:
                go(e['sn'], (lambda e_, o_: (lambda p: f(xf(p, e_, o_))))(e, o))
    go(top, lambda p: p)
    return boxes, texts
