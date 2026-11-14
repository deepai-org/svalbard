#!/usr/bin/env python3
"""M3b/c: mutual inductance between a bond-wire pair loop (RF_TX_P/N or RF_RX_P/N) and the QVCO tank spiral, by the
Neumann double line integral over filament polylines.  Two-sided: with / without the image in the die paddle + board ground
plane (perfect conductor at z = -T_DIE below the die surface), bond pitch 0.15..0.40 mm, loop height 0.15..0.35 mm.
Self-test: two coaxial circular loops (Maxwell closed form) and a must-fail (orthogonal loops -> M = 0)."""
import numpy as np, json, sys
from scipy.special import ellipk, ellipe
MU0 = 4e-7*np.pi

def seg(poly, n_per_mm=60):
    """polyline (k,3) [m] -> midpoints, dl vectors"""
    P = np.asarray(poly, float); mids = []; dls = []
    for a, b in zip(P[:-1], P[1:]):
        n = max(2, int(np.linalg.norm(b-a)*1e3*n_per_mm)); t = (np.arange(n)+0.5)/n
        mids.append(a+(b-a)*t[:, None]); dls.append(np.tile((b-a)/n, (n, 1)))
    return np.vstack(mids), np.vstack(dls)

def neumann(p1, p2, npm=60):
    m1, d1 = seg(p1, npm); m2, d2 = seg(p2, npm)
    r = np.linalg.norm(m1[:, None, :]-m2[None, :, :], axis=2)
    return MU0/(4*np.pi)*np.sum((d1@d2.T)/np.maximum(r, 1e-7))

def spiral(cx, cy, outer=300e-6, turns=3, pitch=30e-6, z=0.0):
    """square spiral, turn width 25 um + 5 um space -> centre-line pitch 30 um"""
    pts = []; h = outer/2-12.5e-6
    for k in range(turns):
        a = h-k*pitch
        pts += [(cx-a, cy-a, z), (cx+a, cy-a, z), (cx+a, cy+a, z), (cx-a, cy+a-pitch, z)] if k < turns-1 else [(cx-a, cy-a, z), (cx+a, cy-a, z), (cx+a, cy+a, z), (cx-a, cy+a, z), (cx-a, cy-a, z)]
    return np.array(pts)

def bond_loop(pitch_die=150e-6, pitch_finger=400e-6, length=2.6e-3, height=0.25e-3, z_finger=-0.3e-3, y_die=0.0, y_finger=0.0):
    """Closed loop: die-edge segment between the two pads (through the driver), wire N out to its finger (arc), finger-to-finger
    closure at the board (the traces beyond run over the ground plane), wire P back.  Die edge at x = 0, wires go to -x, die surface z = 0."""
    n = 12; t = np.linspace(0, 1, n)
    def wire(y0, y1):
        x = -length*t; y = y0+(y1-y0)*t; z = z_finger*t+4*height*t*(1-t)
        return np.c_[x, y, z]
    wn = wire(y_die-pitch_die/2, y_finger-pitch_finger/2); wp = wire(y_die+pitch_die/2, y_finger+pitch_finger/2)[::-1]
    return np.vstack([[(0, y_die+pitch_die/2, 0)], wn, wp])

FAN = 1.55   # finger pitch 0.4 mm vs mean die pad pitch ~0.26 mm on the west edge
def M_pair_pair(dy_die, image=True, t_die=0.3e-3, **kw):
    """two differential bond pairs whose die-pad centres are dy_die apart (fingers fan out by FAN)"""
    a = bond_loop(**kw); b = bond_loop(y_die=dy_die, y_finger=FAN*dy_die, **kw)
    m = neumann(a, b)
    if image: m -= neumann(mirror(a, -t_die), b)
    return m

def mirror(poly, zplane):
    q = np.array(poly, float).copy(); q[:, 2] = 2*zplane-q[:, 2]; return q

def M_bond_spiral(dx, dy, image=True, t_die=0.3e-3, **kw):
    """spiral centre at (dx, dy) from the die-edge midpoint of the pad pair (dx inward, dy along the edge)"""
    b = bond_loop(**kw); s = spiral(dx, dy)
    m = neumann(b, s)
    if image: m -= neumann(mirror(b, -t_die), s)
    return m

def selftest():
    # coaxial circular loops radius a, b, distance d (Maxwell)
    a, b, d = 1e-3, 0.5e-3, 0.8e-3
    k = np.sqrt(4*a*b/((a+b)**2+d**2)); ana = MU0*np.sqrt(a*b)*((2/k-k)*ellipk(k**2)-2/k*ellipe(k**2))
    th = np.linspace(0, 2*np.pi, 721)
    l1 = np.c_[a*np.cos(th), a*np.sin(th), 0*th]; l2 = np.c_[b*np.cos(th), b*np.sin(th), d+0*th]
    num = neumann(l1, l2, 200)
    l3 = np.c_[b*np.cos(th), 0*th, d+b*np.sin(th)]            # orthogonal loop on the axis: M must be ~0
    orth = neumann(l1, l3, 200)
    out = dict(coaxial_num_pH=num*1e12, coaxial_analytic_pH=ana*1e12, err_pct=100*(num/ana-1), orthogonal_pH=orth*1e12,
               ok=bool(abs(num/ana-1) < 0.02 and abs(orth) < 0.01*abs(ana)))
    print(json.dumps(out)); assert out['ok']; return out

if __name__ == '__main__':
    KW = dict(lo=dict(image=True, pitch_die=120e-6, pitch_finger=400e-6, height=0.15e-3),
              nom=dict(image=True, pitch_die=150e-6, pitch_finger=400e-6, height=0.25e-3),
              hi=dict(image=False, pitch_die=300e-6, pitch_finger=400e-6, height=0.35e-3))
    res = dict(selftest=selftest(), bond_to_spiral=[], pair_to_pair=[])
    # spiral centre: dx from the die edge (pad cells are ~940 um deep, QVCO half-width >= 315 um -> dx >= 1300), dy along the edge
    for dx in (1300, 1700, 2200, 3000):
        for dy in (0, 500, 1000, 1500, 2000, 3000):
            vals = {lab: abs(M_bond_spiral(dx*1e-6, dy*1e-6, **kw))*1e12 for lab, kw in KW.items()}
            res['bond_to_spiral'].append(dict(dx_um=dx, dy_um=dy, M_pH=vals)); print('spiral', dx, dy, {k: round(v, 4) for k, v in vals.items()}, flush=True)
    for dy in (300, 450, 600, 900, 1200, 1700, 2100, 3000):
        vals = {lab: abs(M_pair_pair(dy*1e-6, **kw))*1e12 for lab, kw in KW.items()}
        res['pair_to_pair'].append(dict(dy_die_um=dy, M_pH=vals)); print('pair', dy, {k: round(v, 3) for k, v in vals.items()}, flush=True)
    json.dump(res, open('mutual.json', 'w'), indent=1)
