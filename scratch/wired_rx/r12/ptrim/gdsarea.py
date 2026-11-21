"""Area per GDS layer (sum of BOUNDARY polygon areas, overlaps counted twice) + x/y extent: usage gdsarea.py GDS -> json.
Minimal GDSII reader (no external modules).  GF180MCU: Metal4 46/0, Metal5 81/0."""
import struct, sys, json, collections
b = open(sys.argv[1], 'rb').read(); i = 0; L = None; D = None; out = collections.defaultdict(lambda: [0.0, [1e18, -1e18, 1e18, -1e18]]); uu = 1e-3; inb = False
while i < len(b):
    n, rt = struct.unpack('>HH', b[i:i + 4]); dat = b[i + 4:i + n]; i += n
    if n == 0: break
    if rt == 0x0305:          # UNITS (8-byte reals): user unit -> um: db in m / 1e-6
        def r8(x):
            s = -1 if x[0] & 0x80 else 1; e = (x[0] & 0x7f) - 64; m = int.from_bytes(x[1:], 'big') / 2 ** 56; return s * m * 16 ** e
        uu = r8(dat[8:16]) / 1e-6
    elif rt == 0x0800: inb = True; L = D = None
    elif rt == 0x0D02 and inb: L = struct.unpack('>h', dat)[0]
    elif rt == 0x0E02 and inb: D = struct.unpack('>h', dat)[0]
    elif rt == 0x1003 and inb and L is not None:
        xy = struct.unpack('>%di' % (len(dat) // 4), dat); P = [(xy[j] * uu, xy[j + 1] * uu) for j in range(0, len(xy), 2)]
        a = abs(sum(P[j][0] * P[j + 1][1] - P[j + 1][0] * P[j][1] for j in range(len(P) - 1))) / 2
        o = out[f'{L}/{D}']; o[0] += a; bx = o[1]
        bx[:] = [min(bx[0], min(p[0] for p in P)), max(bx[1], max(p[0] for p in P)), min(bx[2], min(p[1] for p in P)), max(bx[3], max(p[1] for p in P))]
    elif rt == 0x1100: inb = False
print(json.dumps({k: dict(area_um2=round(v[0], 2), bbox=[round(x, 2) for x in v[1]]) for k, v in sorted(out.items())}))
