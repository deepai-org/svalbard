"""E8: stability matrix of the current schematic LNA (netlists.py as it stands) or the extracted one.
usage: e8.py sch|ext set  ; set = sup | states | views | neg"""
import sys, os, re; sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-q')
from var import *
src, which = sys.argv[1], sys.argv[2]
def run(tag, view, c, deg, **kw):
    r = LM.stability(W if src == 'sch' else Q / 'w' / 'e8_ext', 'selftest' if src == 'sch' else view, c, deg=deg, **kw)
    print(src, tag, view, c, deg, kw, fmt(r), flush=True)
def mk(view, patch=None, tag=''):
    global W
    if src == 'sch': W = variant(f'e8_{view}{tag}', like=view, patch=patch)
if which == 'sup':
    mk('extpr')
    for st in (dict(), dict(att=63)):
        for kw in (dict(), dict(lsup=0.25e-9), dict(lsup=2e-9), dict(cdec=100e-12), dict(cdec=500e-12), dict(cdec=100e-12, lsup=2e-9), dict(cdec=500e-12, lsup=0.25e-9)):
            run('sup', 'extpr', FF, 'lowr', **st, **kw)
elif which == 'states':
    mk('extpr')
    for st in (dict(mode='off'), dict(mode='bypass'), dict(ct=0), dict(ct=15), dict(rt=True), dict(att=31), dict(att=1)):
        run('st', 'extpr', FF, 'lowr', **st)
    tb.set_lobias(True); run('lobias', 'extpr', FF, 'lowr'); tb.set_lobias(False)
elif which == 'views':
    for v, c, dg in (('extlo', FF, 'lowr'), ('extlo', ('ff', 22, 3.35), 'lowr'), ('extpr', TT, None), ('extpp', SS, None), ('extpr', SS, 'lowr'), ('extlo', ('ff', 22, 3.35), None)):
        mk(v); run('view', v, c, dg)
elif which == 'neg':
    # negative control: the original failure mechanism restored (tail AC-shorted to VSS, tank feed shorted to VDD, CM network open)
    def patch(t):
        i = t.index('.subckt pt_lna '); e = t.index('.ends', i)
        t = t[:e] + 'Cnegt tail VSS 1u\nRnegf vtk VDD 1m\n' + t[e:]
        return sub_in(t, ' ncm VSS ppolyf_u_1k', ' ncm ncm_open ppolyf_u_1k', 1)
    assert src == 'sch'
    mk('extpr', patch, '_neg'); run('NEG', 'extpr', FF, 'lowr'); run('NEG', 'extpr', FF, 'lowr', cdec=100e-12)
