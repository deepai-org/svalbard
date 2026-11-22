"""2-D resistive raster of the supply nets (from ras.py): Metal1-5 sheets + via cuts, PDK values (Magic tech gf180mcuD:
metal1-4 90 / metal5 40 mohm/sq, via 4.5 ohm/cut; high-end corner 104 / 49 mohm/sq, 15 ohm/cut).  Ties = V 0, loads = current
sinks (uniform over the given boxes on the given layer).  python3 ir.py cfg.json -> json"""
import json, sys, numpy as np, scipy.sparse as sp, scipy.sparse.linalg as sla
cfg = json.load(open(sys.argv[1])); d = cfg['dir']
meta = json.load(open(f'{d}/meta.json')); H, x0, y0, nx, ny = meta['H'], meta['x0'], meta['y0'], meta['nx'], meta['ny']
ML = ['m1', 'm2', 'm3', 'm4', 'm5']; VL = ['v1', 'v2', 'v3', 'v4']
corner = cfg.get('corner', 'nom')
RS = dict(nom=[0.09] * 4 + [0.04], high=[0.104] * 4 + [0.049])[corner]; RV = dict(nom=4.5, high=15.0)[corner]
LIM = [2.09] * 4 + [4.5]; CUT = 0.58
def pix(b):
    return (int(max(0, (b[0] - x0) / H)), int(max(0, (b[1] - y0) / H)), int(min(nx, np.ceil((b[2] - x0) / H))), int(min(ny, np.ceil((b[3] - y0) / H))))
out = {}
for net in cfg['nets']:
    cov = [np.fromfile(f'{d}/{net}_{l}.bin', dtype=np.float32).reshape(ny, nx) for l in ML]
    on = [c > 0.2 for c in cov]
    idx = np.full((5, ny, nx), -1, np.int64); n = 0
    for k in range(5):
        m = on[k]; c_ = int(m.sum()); idx[k][m] = np.arange(n, n + c_); n += c_
    A_r, A_c, A_v = [], [], []
    for k in range(5):
        c = np.minimum(cov[k], 1.0)
        for ax in (0, 1):
            a = idx[k][:, :-1] if ax == 1 else idx[k][:-1, :]
            b = idx[k][:, 1:] if ax == 1 else idx[k][1:, :]
            ca = c[:, :-1] if ax == 1 else c[:-1, :]
            cb = c[:, 1:] if ax == 1 else c[1:, :]
            m = (a >= 0) & (b >= 0)
            g = np.minimum(ca[m], cb[m]) / RS[k]
            A_r.append(a[m]); A_c.append(b[m]); A_v.append(g)
    for k, vl in enumerate(VL):
        for i, j, cnt in json.load(open(f'{d}/{net}_{vl}.json')):
            if i < nx and j < ny and idx[k][j, i] >= 0 and idx[k + 1][j, i] >= 0:
                A_r.append(np.array([idx[k][j, i]])); A_c.append(np.array([idx[k + 1][j, i]])); A_v.append(np.array([cnt / RV]))
    a = np.concatenate(A_r); b = np.concatenate(A_c); g = np.concatenate(A_v)
    off = sp.coo_matrix((-g, (a, b)), shape=(n, n)); off = off + off.T
    diag = -np.asarray(off.sum(axis=1)).ravel()
    G = (off + sp.diags(diag)).tocsr()
    I = np.zeros(n)
    loads = {}
    for ld in cfg['loads'][net]:
        k = ML.index(ld['layer']); sel = []
        for bx in ld['boxes']:
            i0, j0, i1, j1 = pix(bx); s = idx[k][j0:j1, i0:i1]; sel.append(s[s >= 0])
        sel = np.concatenate(sel)
        if len(sel) == 0: raise SystemExit(f'load {ld["name"]}: no pixels')
        I[sel] += ld['mA'] * 1e-3 / len(sel); loads[ld['name']] = sel
    tie = []
    for t in cfg['ties'][net]:
        k = ML.index(t['layer']); i0, j0, i1, j1 = pix(t['box']); s = idx[k][j0:j1, i0:i1]; tie.append(s[s >= 0])
    tie = np.unique(np.concatenate(tie))
    if len(tie) == 0: raise SystemExit('no tie pixels')
    free = np.setdiff1d(np.arange(n), tie)
    # connectivity: drop nodes not connected to a tie (floating metal of the net only through devices)
    ncomp, lab = sp.csgraph.connected_components(off != 0, directed=False)
    good = np.isin(lab, np.unique(lab[tie]))
    lost = float(I[~good].sum()) * 1e3
    free = free[good[free]]
    V = np.zeros(n)
    Gf = G[free][:, free]
    V[free] = sla.spsolve(Gf.tocsc(), I[free])
    res = dict(nodes=int(n), tie_px=int(len(tie)), load_mA_unconnected=round(lost, 3), tie_current_mA=round(float(I[good].sum()) * 1e3, 2))
    res['loads'] = {k_: dict(max_mV=round(float(V[s].max()) * 1e3, 2), mean_mV=round(float(V[s].mean()) * 1e3, 2)) for k_, s in loads.items()}
    res['max_mV'] = round(float(V.max()) * 1e3, 2)
    inj = G.tocsr() @ V - I                      # session 18: current drawn from each tie group (V = 0 at ties)
    grp = {}
    for t in cfg['ties'][net]:
        k = ML.index(t['layer']); i0, j0, i1, j1 = pix(t['box']); s = idx[k][j0:j1, i0:i1]; s = np.unique(s[s >= 0])
        grp[t.get('name', 'tie')] = grp.get(t.get('name', 'tie'), 0.0) + float(-inj[s].sum()) * 1e3
    res['tie_split_mA'] = {k_: round(v, 2) for k_, v in grp.items()}
    # EM: current per um of width in each layer (lateral), current per cut in each via layer
    em = {}
    Vm = np.zeros((5, ny, nx)); Vm[idx >= 0] = V[idx[idx >= 0]]
    for k in range(5):
        c = np.minimum(cov[k], 1.0); m = idx[k] >= 0
        jx = np.zeros((ny, nx)); jy = np.zeros((ny, nx))
        mm = m[:, :-1] & m[:, 1:]; jx[:, :-1][mm] = np.abs(Vm[k][:, :-1] - Vm[k][:, 1:])[mm] / RS[k] / H   # A per um of width
        mm = m[:-1, :] & m[1:, :]; jy[:-1, :][mm] = np.abs(Vm[k][:-1, :] - Vm[k][1:, :])[mm] / RS[k] / H
        j = np.hypot(jx, jy) * 1e3
        jv = j[m & (c > 0.9)]
        if len(jv):
            p = np.argmax(np.where(m & (c > 0.9), j, 0)); jj, ii = divmod(p, nx)
            em[ML[k]] = dict(max_mA_per_um=round(float(jv.max()), 3), p999=round(float(np.percentile(jv, 99.9)), 3), at=[round(x0 + ii * H, 1), round(y0 + jj * H, 1)],
                             limit=LIM[k], margin_pct=round(100 * (1 - jv.max() / LIM[k]), 1))
    for k, vl in enumerate(VL):
        worst = (0, None)
        for i, j, cnt in json.load(open(f'{d}/{net}_{vl}.json')):
            if i < nx and j < ny and idx[k][j, i] >= 0 and idx[k + 1][j, i] >= 0:
                ic = abs(Vm[k][j, i] - Vm[k + 1][j, i]) / RV * 1e3   # mA per cut
                if ic > worst[0]: worst = (ic, [round(x0 + i * H, 1), round(y0 + j * H, 1)])
        em[vl] = dict(max_mA_per_cut=round(worst[0], 3), at=worst[1], limit=CUT, margin_pct=round(100 * (1 - worst[0] / CUT), 1))
    res['em'] = em
    if cfg.get('map'):
        np.save(f'{cfg["map"]}_{net}.npy', (Vm.max(axis=0) * 1e3).astype(np.float32)); np.save(f'{cfg["map"]}_{net}_layers.npy', (Vm * 1e3).astype(np.float32))
    out[net] = res
print(json.dumps(out, indent=1))
