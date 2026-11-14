#!/usr/bin/env python3
"""M2 substrate mesh (extends A1 a1_multiport.py / substrate_fd.py): uniform p-bulk 300 um, 25 um cells, 7-point resistive mesh.
Normalised units: neighbour conductance g = 1 (physical g = h/rho).  Voltage ratios are rho-independent;
transimpedances scale as  Z_phys = Z_norm * rho / h   (rho two-sided: 5 .. 30 ohm*cm, 10 nominal).
Knobs (two-sided):
  back   : False = floating backside, True = grounded (die-attach), per-cell 2 g (as A1)
  tie    : 'dense'  = every surface cell that is not an aggressor / floating probe ties to ground with 1 g (A1 assumption, optimistic)
           'sparse' = only listed block footprints + the pad ring tie, with 0.3 g; whitespace untied (pessimistic)
  surf   : lateral conductance multiplier of the top layer (1 = uniform bulk, 3 = low-resistivity p-well / field-implant skin)
Self-tests (python3 submesh.py test): 1-D slab known answer, and a must-fail (broken tie) case."""
import os
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"): os.environ.setdefault(_k, "1")   # shared box: threaded BLAS stalls under load
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as la, json, sys, time
import os
H = float(os.environ.get("SUBMESH_H", "25"))

class Mesh:
    def __init__(s, wx, wy, nz=12, surf=1.0):
        s.nx, s.ny, s.nz = int(round(wx/H)), int(round(wy/H)), nz
        nx, ny, nz = s.nx, s.ny, s.nz; s.N = nx*ny*nz
        I, J, K = np.meshgrid(np.arange(nx), np.arange(ny), np.arange(nz), indexing='ij')
        idx = lambda i, j, k: (k*ny+j)*nx+i
        r = []; c = []; v = []; s.diag0 = np.zeros(s.N)
        for (di, dj, dk) in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
            a = idx(I[:nx-di, :ny-dj, :nz-dk], J[:nx-di, :ny-dj, :nz-dk], K[:nx-di, :ny-dj, :nz-dk]).ravel()
            b = idx(I[di:, dj:, dk:], J[di:, dj:, dk:], K[di:, dj:, dk:]).ravel()
            g = np.ones(len(a))
            if dk == 0 and surf != 1.0: g[K[:nx-di, :ny-dj, :nz-dk].ravel() == 0] = surf
            r += [a, b]; c += [b, a]; v += [-g, -g]
            np.add.at(s.diag0, a, g); np.add.at(s.diag0, b, g)
        s.A0 = sp.coo_matrix((np.concatenate(v), (np.concatenate(r), np.concatenate(c))), shape=(s.N, s.N)).tocsr()
    def cells(s, rect):
        i0, i1 = int(np.floor(rect[0]/H)), int(np.ceil(rect[2]/H)); j0, j1 = int(np.floor(rect[1]/H)), int(np.ceil(rect[3]/H))
        m = np.zeros((s.nx, s.ny), bool); m[max(i0, 0):min(i1, s.nx), max(j0, 0):min(j1, s.ny)] = True
        return m
    def solve(s, tie, force=None, inject=None, back=False):
        """tie: (nx,ny) array of surface tie conductances to ground; force: bool mask forced to 1 V; inject: (nx,ny) currents."""
        nx, ny = s.nx, s.ny
        d = s.diag0.copy(); b = np.zeros(s.N)
        t = tie.copy()
        if force is not None: t[force] = 0
        d[:nx*ny] += t.T.ravel()                       # surface layer k=0, index j*nx+i
        if force is not None:
            f = force.T.ravel(); d[:nx*ny][f] += 1e4; b[:nx*ny][f] += 1e4
        if inject is not None: b[:nx*ny] += inject.T.ravel()
        if back: d[-nx*ny:] += 2.0
        A = (s.A0 + sp.diags(d)).tocsc()
        if s.N <= 150000:
            x = la.splu(A).solve(b)                    # direct (coarse meshes)
        else:
            x, info = la.cg(A, b, rtol=1e-10, maxiter=40000, M=sp.diags(1/d))
            assert info == 0, info
        return x[:nx*ny].reshape(ny, nx).T             # surface potential (nx,ny)

def db(x): return round(float(20*np.log10(max(x, 1e-12))), 1)

def selftest():
    # known answer: 1-D column. Whole surface forced to 1 V, backside grounded 2 g per cell, no ties:
    # each column is nz-1 series links + the 2 g back tie -> surface 1 V, bottom node = 1/(1+2*(nz-1))... check the bottom-layer voltage via a probe trick:
    m = Mesh(500, 500, nz=6)
    nx, ny = m.nx, m.ny
    # (a) current injection uniform 1 per cell on the surface, backside grounded: V_surface = I*(sum of (nz-1) links 1/g + 1/(2g)) = 5 + 0.5 = 5.5
    v = m.solve(np.zeros((nx, ny)), inject=np.ones((nx, ny)), back=True)
    ok_a = abs(v.mean()-5.5) < 1e-6
    # (b) lateral divider: left third forced to 1 V, right third tied hard, middle floating, floating back: mid-point of the gap ~ 0.5 by symmetry
    f = np.zeros((nx, ny), bool); f[:6, :] = True
    t = np.zeros((nx, ny)); t[-6:, :] = 1e4
    v = m.solve(t, force=f)
    mid = v[nx//2-1:nx//2+1, :].mean(); ok_b = abs(mid-0.5) < 0.01
    # (c) must-fail: remove the right tie (broken ground) -> everything floats to 1 V, the 0.5 check must FAIL
    t2 = np.zeros((nx, ny)); t2[-1, 0] = 1e-9
    v = m.solve(t2, force=f); ok_c = not (abs(v[nx//2-1:nx//2+1, :].mean()-0.5) < 0.01)
    # (d) point-contact spreading resistance on a thick slab: R ~ rho/(2*d) for a disc of diameter d (here square 100 um on 2 mm slab, grounded back+dense far ties)
    m2 = Mesh(2000, 2000, nz=12)
    f = m2.cells([950, 950, 1050, 1050]); t = np.zeros((m2.nx, m2.ny)); t[0, :] = t[-1, :] = t[:, 0] = t[:, -1] = 1e4
    inj = np.zeros((m2.nx, m2.ny)); inj[f] = 1/f.sum()
    v = m2.solve(t, inject=inj, back=True); Rn = v[f].mean()     # normalised; R_phys = Rn*rho/h
    # analytic: square contact side a on a half-space, uniform current: R = 0.4732*rho/a*... (avg potential) ~ rho*0.473/a -> normalised Rn = 0.473*h/a (thick-slab limit; finite slab/back ground lowers it)
    ana = 0.4732*H/100.0; ok_d = 0.6*ana < Rn < 1.25*ana
    out = dict(a_column=bool(ok_a), b_divider=bool(ok_b), c_mustfail_broken_tie=bool(ok_c), d_spreading=dict(mesh=float(Rn), analytic_halfspace=ana, ok=bool(ok_d)))
    print(json.dumps(out)); json.dump(out, open('selftest.json', 'w'), indent=1)
    assert ok_a and ok_b and ok_c and ok_d

if __name__ == '__main__' and sys.argv[1:] == ['test']: selftest()
