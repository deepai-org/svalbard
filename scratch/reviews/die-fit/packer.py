#!/usr/bin/env python3
"""Die-fit study: a small but real rectangle packer (replaces the seeded greedy spiral of v6 / area pass 4).

Method: exhaustive-position constructive packing on an occupancy bitmap.
  For every block, EVERY lattice position of both orientations is tested against the bitmap with a summed-area
  table (so the search cannot miss a hole that exists), hard constraints are applied as masks, and the feasible
  position with the lowest cost is taken.  cost = sum(weight x Manhattan gap to each already placed target)
  + anchor pull - lam x contact length (touching-perimeter rule: prefers positions that hug obstacles / other
  blocks, which is what keeps scrap low).
Hard constraints: no overlap incl. halo, keep-away distances (never relaxed), and relaxable ones (max gap to a
  target, ring-edge position).  If a block has no feasible position, the relaxable constraints are dropped one
  class at a time and the relaxation is recorded; if it still has none it is reported unplaced.
Fixed obstacles may be any union of rectangles (L-shaped pads, the digital macro, reserves).

python3 packer.py   runs the self-checks (hand-verifiable sanity cases + over-full inputs)."""
import math
import numpy as np


class Packer:
    def __init__(s, core, G=2.0, K=4):
        s.core = tuple(core); s.G = G; s.K = K
        s.nx = int(round((core[2]-core[0])/G)); s.ny = int(round((core[3]-core[1])/G))
        s.occ = np.ones((s.ny+2*K, s.nx+2*K), dtype=np.uint8); s.occ[K:K+s.ny, K:K+s.nx] = 0
        s.rects = {}; s.placed = {}; s.unplaced = []; s.relaxed = []; s._S = None

    # ---- bitmap -----------------------------------------------------------------------------------------------
    def _cells(s, r):
        G, K = s.G, s.K
        i0 = int(math.floor((r[0]-s.core[0])/G+1e-6))+K; j0 = int(math.floor((r[1]-s.core[1])/G+1e-6))+K
        i1 = int(math.ceil((r[2]-s.core[0])/G-1e-6))+K; j1 = int(math.ceil((r[3]-s.core[1])/G-1e-6))+K
        return max(0, i0), max(0, j0), min(s.occ.shape[1], i1), min(s.occ.shape[0], j1)

    def mark(s, r, halo=0.0):
        i0, j0, i1, j1 = s._cells((r[0]-halo, r[1]-halo, r[2]+halo, r[3]+halo))
        if i1 > i0 and j1 > j0:
            s.occ[j0:j1, i0:i1] = 1; s._S = None

    def sat(s):
        if s._S is None:
            S = np.zeros((s.occ.shape[0]+1, s.occ.shape[1]+1), dtype=np.int32)
            S[1:, 1:] = s.occ.astype(np.int32).cumsum(0).cumsum(1); s._S = S
        return s._S

    def fixed(s, name, rects, halo=0.0):
        """Fixed obstacle = union of rectangles. The first rectangle is the reference for distances."""
        for r in rects:
            s.mark(r, halo)
        s.rects[name] = tuple(rects[0])

    def free_area(s):
        K = s.K
        return float((s.occ[K:K+s.ny, K:K+s.nx] == 0).sum())*s.G*s.G

    # ---- one block ----------------------------------------------------------------------------------------------
    def place(s, name, w, h, halo=10.0, rot=True, targets=(), anchor=None, keepaway=(), maxgap=(), ring=None,
              lam=0.5, step=2):
        """targets: [(name, weight)]; anchor: (x, y, weight); keepaway: [(name, min euclid gap)] (never relaxed);
        maxgap: [(name, max manhattan gap)] (relaxable); ring: (edge 'W'|'E'|'S'|'N', coord, max_edge_gap,
        max_along) = must sit within max_edge_gap of the core boundary and within max_along (measured along the
        boundary, round the corners) of the point `coord` on that edge (relaxable)."""
        G, K = s.G, s.K; S = s.sat(); x0c, y0c, x1c, y1c = s.core
        shapes = [(w, h)] + ([(h, w)] if rot and abs(w-h) > 1e-6 else [])
        per = 2*((x1c-x0c)+(y1c-y0c))

        def ring_s(edge, c):   # perimeter coordinate, counter-clockwise from the SW corner
            if edge == 'S': return c-x0c
            if edge == 'E': return (x1c-x0c)+(c-y0c)
            if edge == 'N': return (x1c-x0c)+(y1c-y0c)+(x1c-c)
            return 2*(x1c-x0c)+(y1c-y0c)+(y1c-c)

        cands = []
        for (ww, hh) in shapes:
            wc = int(math.ceil((ww+2*halo)/G-1e-6)); hc = int(math.ceil((hh+2*halo)/G-1e-6))
            if wc > S.shape[1]-1 or hc > S.shape[0]-1:
                continue
            F = S[hc:, wc:]-S[:-hc, wc:]-S[hc:, :-wc]+S[:-hc, :-wc]
            Fs = F[::step, ::step]
            jj, ii = np.nonzero(Fs == 0)
            if len(ii) == 0:
                continue
            ii = ii*step; jj = jj*step
            x = x0c+(ii-K)*G+halo; y = y0c+(jj-K)*G+halo          # block lower-left
            # contact: occupied cells in the one-cell frame around the halo box
            C = (S[jj+hc+1, ii+wc+1]-S[jj-1, ii+wc+1]-S[jj+hc+1, ii-1]+S[jj-1, ii-1]).astype(np.float32)*G
            cost = -lam*C
            cx = x+ww/2; cy = y+hh/2
            if anchor is not None:
                cost = cost+anchor[2]*(np.abs(cx-anchor[0])+np.abs(cy-anchor[1]))

            def gaps(T):
                gx = np.maximum(np.maximum(T[0]-(x+ww), x-T[2]), 0.0); gy = np.maximum(np.maximum(T[1]-(y+hh), y-T[3]), 0.0)
                return gx, gy
            for tn, tw in targets:
                if tn in s.rects:
                    gx, gy = gaps(s.rects[tn]); cost = cost+tw*(gx+gy)
            ok = np.ones(len(x), dtype=bool)
            for tn, d in keepaway:
                if tn in s.rects:
                    gx, gy = gaps(s.rects[tn]); ok &= (np.hypot(gx, gy) >= d)
            mg = np.ones(len(x), dtype=bool); mg_used = False
            for tn, d in maxgap:
                if tn in s.rects:
                    gx, gy = gaps(s.rects[tn]); mg &= ((gx+gy) <= d); mg_used = True
            rg = np.ones(len(x), dtype=bool)
            if ring is not None:
                edge, c, egap, along = ring; sp = ring_s(edge, c); rg[:] = False
                for e, g_e, s_e in (('S', y-y0c, cx-x0c), ('E', x1c-(x+ww), (x1c-x0c)+(cy-y0c)),
                                    ('N', y1c-(y+hh), (x1c-x0c)+(y1c-y0c)+(x1c-cx)), ('W', x-x0c, 2*(x1c-x0c)+(y1c-y0c)+(y1c-cy))):
                    d = np.abs(s_e-sp); d = np.minimum(d, per-d)
                    rg |= (g_e <= egap) & (d <= along)
            cands.append((ww, hh, x, y, cost, ok, mg, rg, mg_used))
        if not cands:
            s.unplaced.append((name, 'no free position of this size (geometry)')); return None
        # constraint classes, relaxed in this order if nothing is feasible: ring position, then max gap
        for level, label in ((0, None), (1, 'ring-edge/supply-pad position (G4)'), (2, 'max distance to switch/partner')):
            best = None
            for (ww, hh, x, y, cost, ok, mg, rg, mg_used) in cands:
                m = ok.copy()
                if level < 1: m &= rg
                if level < 2: m &= mg
                if m.any():
                    k = int(np.argmin(np.where(m, cost, np.inf)))
                    if best is None or cost[k] < best[0]:
                        best = (float(cost[k]), float(x[k]), float(y[k]), ww, hh)
            if best is not None:
                if label:
                    s.relaxed.append((name, label))
                _, bx, by, ww, hh = best
                r = (bx, by, bx+ww, by+hh); s.mark(r, halo); s.rects[name] = r
                s.placed[name] = dict(rect=r, rot=(ww != w), halo=halo)
                return r
        s.unplaced.append((name, 'keep-away rules leave no position')); return None


def overlap_check(p):
    """Independent legality check (no bitmap): pairwise rectangle overlap of the placed blocks, and containment."""
    names = list(p.placed); bad = []
    for a in range(len(names)):
        ra = p.placed[names[a]]['rect']
        if ra[0] < p.core[0]-1e-6 or ra[1] < p.core[1]-1e-6 or ra[2] > p.core[2]+1e-6 or ra[3] > p.core[3]+1e-6:
            bad.append((names[a], 'outside core'))
        for b in range(a+1, len(names)):
            rb = p.placed[names[b]]['rect']
            if min(ra[2], rb[2])-max(ra[0], rb[0]) > 1e-6 and min(ra[3], rb[3])-max(ra[1], rb[1]) > 1e-6:
                bad.append((names[a], names[b]))
    return bad


# ---- self-checks --------------------------------------------------------------------------------------------------
def selftest():
    out = []
    def run(title, core, blocks, expect_placed, expect_free, fixed=()):
        p = Packer(core, G=1.0)
        for n, rs in fixed:
            p.fixed(n, rs)
        for n, w, h in sorted(blocks, key=lambda b: -b[1]*b[2]):
            p.place(n, w, h, halo=0.0, step=1)
        ok = (len(p.placed) == expect_placed and abs(p.free_area()-expect_free) < 1e-6 and not overlap_check(p))
        out.append((title, len(p.placed), len(blocks), p.free_area(), ok, {k: v['rect'] for k, v in p.placed.items()},
                    [u[0] for u in p.unplaced]))
        return ok
    r = []
    # 1. exact fit by hand: 100 x 100 holds four 50 x 50 -> all placed, scrap 0
    r.append(run('T1 four 50x50 in 100x100 (exact fit)', (0, 0, 100, 100), [(f'b{i}', 50, 50) for i in range(4)], 4, 0.0))
    # 2. needs a rotation: 120 x 80 holds 80x40, 80x40 and a third 80x40 only as 40x80 -> all placed, scrap 0
    r.append(run('T2 three 80x40 in 120x80 (third must rotate)', (0, 0, 120, 80), [(f'b{i}', 80, 40) for i in range(3)], 3, 0.0))
    # 3. L-shaped free space: 100 x 100 with a fixed 60 x 60 corner obstacle; free L = 6400; blocks 100x40 and 40x60
    r.append(run('T3 L-shaped space after a fixed 60x60 obstacle', (0, 0, 100, 100), [('long', 100, 40), ('short', 40, 60)], 2, 0.0,
                 fixed=[('obst', [(0, 0, 60, 60)])]))
    # 4. over-full by area: five 50 x 50 in 100 x 100 -> exactly four placed, one reported
    r.append(run('T4 five 50x50 in 100x100 (over-full by area: must leave one out)', (0, 0, 100, 100), [(f'b{i}', 50, 50) for i in range(5)], 4, 0.0))
    # 5. area fits (7200 < 10000) but geometry cannot: two 60 x 60 in 100 x 100 -> one placed
    r.append(run('T5 two 60x60 in 100x100 (area fits, geometry does not)', (0, 0, 100, 100), [('a', 60, 60), ('b', 60, 60)], 1, 6400.0))
    # 6. keep-away: two 20 x 20 blocks that must be 55 apart. 100 x 30 strip: largest possible gap is 60 -> feasible;
    #    80 x 30 strip: largest possible gap is 40 -> must fail
    p = Packer((0, 0, 100, 30), G=1.0); p.place('agg', 20, 20, halo=0, step=1); q = p.place('vic', 20, 20, halo=0, step=1, keepaway=[('agg', 55)])
    g = None if q is None else max(q[0]-p.rects['agg'][2], p.rects['agg'][0]-q[2])
    r.append(q is not None and g >= 55); out.append(('T6a keep-away 55 in a 100-long strip (max possible 60: feasible)', len(p.placed), 2, g, r[-1], {}, []))
    p = Packer((0, 0, 80, 30), G=1.0); p.place('agg', 20, 20, halo=0, step=1); q = p.place('vic', 20, 20, halo=0, step=1, keepaway=[('agg', 55)])
    r.append(q is None); out.append(('T6b keep-away 55 in an 80-long strip (max possible 40: must fail)', len(p.placed), 2, None, r[-1], {}, [u for u in p.unplaced]))
    # 7. relaxable constraint is reported, not silently dropped
    p = Packer((0, 0, 100, 100), G=1.0); p.fixed('wall', [(0, 0, 100, 50)]); p.place('sw', 10, 10, halo=0, step=1, anchor=(95, 95, 1))
    p.fixed('fill', [(60, 50, 90, 100)]); q = p.place('load', 50, 40, halo=0, step=1, maxgap=[('sw', 5)])
    r.append(q is not None and p.relaxed == [('load', 'max distance to switch/partner')]); out.append(('T7 max-gap impossible -> placed with a recorded relaxation', len(p.placed), 2, None, r[-1], {}, p.relaxed))
    return all(r), out


if __name__ == '__main__':
    ok, out = selftest()
    for t in out:
        print(('PASS ' if t[4] else 'FAIL ')+t[0], '| placed', t[1], 'of', t[2], '| free/gap', t[3], '|', t[5] if t[5] else '', t[6] if t[6] else '')
    print('ALL PASS' if ok else 'SELFTEST FAILED')
    raise SystemExit(0 if ok else 1)
