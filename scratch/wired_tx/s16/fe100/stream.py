"""100BASE-TX line stream: scrambled idle (keystream x^11 + x^9 + 1, data all ones) -> MLT-3 (1 = step 0,+1,0,-1)."""
import numpy as np


def keystream(n, seed=0x5A5):
    s = [(seed >> i) & 1 for i in range(11)]          # s[0] = x^1 ... s[10] = x^11
    out = []
    for _ in range(n):
        b = s[10] ^ s[8]                              # x^11 xor x^9
        out.append(b); s = [b] + s[:-1]
    return np.array(out)


def mlt3(n, seed=0x5A5):
    data = 1 ^ keystream(n, seed)                     # scrambled idle
    seq, k, sy = [0, 1, 0, -1], 0, []
    for d in data:
        if d:
            k = (k + 1) % 4
        sy.append(seq[k])
    return np.array(sy)


def runs(sy):
    """list of (start, length, level) of held levels"""
    r, i = [], 0
    while i < len(sy):
        j = i
        while j < len(sy) and sy[j] == sy[i]:
            j += 1
        r.append((i, j - i, int(sy[i]))); i = j
    return r


def stats(n=2047 * 8):
    sy = mlt3(n)
    rr = runs(sy)
    pm = [r for r in rr if r[2] != 0]
    return dict(n_symbols=n, frac={str(k): float(np.mean(sy == k)) for k in (-1, 0, 1)},
                longest_hold_any_sym=max(r[1] for r in rr), longest_hold_pm1_sym=max(r[1] for r in pm),
                longest_hold_0_sym=max(r[1] for r in rr if r[2] == 0))


def window(nsym, search=2047):
    """start index of an nsym window with the longest +-1 hold, both +1 and -1 held >= 2 symbols and a 0 present"""
    sy = mlt3(search + nsym)
    best = None
    for s in range(search):
        w = sy[s:s + nsym]; rr = runs(w)
        if w[0] != 0:
            continue
        hp = max([r[1] for r in rr if r[2] == 1] or [0]); hm = max([r[1] for r in rr if r[2] == -1] or [0])
        h0 = max([r[1] for r in rr if r[2] == 0] or [0])
        if min(hp, hm) < 2 or h0 < 2:
            continue
        sc = (max(hp, hm), min(hp, hm))
        if best is None or sc > best[0]:
            best = (sc, s)
    return best[1], sy[best[1]:best[1] + nsym]


def core_bits(sy, n=20):
    """MAIN data per core bit; POST = MAIN one core bit later (same sign, POST_POL 1): +1 ones, -1 zeros, 0 = 1010.."""
    b = []
    for s in sy:
        b += [1] * n if s > 0 else [0] * n if s < 0 else [1, 0] * (n // 2)
    return b


if __name__ == '__main__':
    import json
    print(json.dumps(stats())); print(window(26))
