"""E6: DC operating point of the redesigned schematic LNA (tail, feed) over corners, RX and duplex bias.  usage: e6.py [mods as K=V]"""
import sys, re, json; sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-q')
from var import *
mods = {k: eval(v) for k, v in (x.split('=') for x in sys.argv[1:])}
tag = 'e6_' + ('_'.join(f'{k[4:]}{v}' for k, v in mods.items()) or 'base')
W = variant(tag, mods=mods)
for c in (TT, SS, FF, ('ss', 22, 3.15), ('ff', 22, 3.35)):
    out = []
    for lob in (False, True):
        tb.set_lobias(lob)
        u = tb.lna_ac(W / ('lo' if lob else 'rx'), 'selftest', c, f=2.44e9, ct=7)
        cir = sorted((W / ('lo' if lob else 'rx')).glob('lna_active_2440_u_selftest_%s.cir' % tb._tag(c)))[0]
        t = cir.read_text().replace('print idd vdcm', 'print idd vdcm\nlet vscm=v(scm_b)\nlet vtx=v(x1.tailx)\nlet vg=v(x1.vg)\nlet vx=v(x1.x_p)\nlet vtk=v(vtk_b)\nlet vcas=v(x1.vcas)\nprint vscm vtx vg vx vtk vcas')
        (cir.parent / 'probe.cir').write_text(t); log = flow.ngspice(cir.parent.resolve(), 'probe.cir')
        g = lambda k: (lambda m: float(m.group(1)) if m else None)(re.search(rf'^{k} = (\S+)', log, re.M))
        out.append('%s idd %.2f mA scm %.2f tailx %.2f vg %.2f x %.2f vtk %.2f vcas %.2f' % ('LO' if lob else 'RX', u['idd_a'] * 1e3, g('vscm'), g('vtx'), g('vg'), g('vx'), g('vtk'), g('vcas')) + ('' if lob else ' | Zin %.1f%+.1fj gain_u %.2f nf_u %.2f' % (u['zin_re_ohm'], u['zin_im_ohm'], u['gain_db'], u['nf_db'])))
    tb.set_lobias(False)
    print(tag, c, ' || '.join(out), flush=True)
