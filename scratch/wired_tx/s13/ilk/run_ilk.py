"""Stopped-ring interlock on the full mux (m9 bench, no pad, both banks enabled): supply current against time after the
phases stop in a given static state.   python3 run_ilk.py tag corner static [stop_at] [key=value ...]"""
import sys, json
sys.path.insert(0, '..')
import numpy as np
import m9
from chain import S


def case(tag, c, static, stop_at=2.2e-8, tstop=6e-7, **kw):
    r = m9.run(tag, c=c, nbits=64, pad=False, post_bias=1.1, stop_at=stop_at, static=static, tstop=tstop, tstep=2e-11, **kw)
    if not isinstance(r, tuple):
        return r
    o, w = r; t = w['time']; i = -w['I'] * 1e3
    def avg(a, b):
        m = (t >= a) & (t <= b); return round(float(i[m].mean()), 3) if m.any() else None
    out = dict(tag=tag, c=c, static=static, stop_at=stop_at, i_run_ma=avg(8e-9, stop_at - 1e-9) if stop_at else None,
               i_10ns_ma=avg(stop_at + 8e-9, stop_at + 12e-9), i_end_ma=avg(tstop - 20e-9, tstop), run_end=o['run_end'])
    lo = np.nonzero((t > stop_at + 2e-9) & (i < 0.1 + (out['i_end_ma'] or 0)))[0]
    out['t_below_0p1_ns'] = round(float(t[lo[0]] - stop_at) * 1e9, 1) if len(lo) else None
    dn = S.crossings(t, w['RUN'], th=o['vdd'] / 2, rising=False); dn = dn[dn > stop_at]
    out['t_run_low_ns'] = round(float(dn[0] - stop_at) * 1e9, 1) if len(dn) else None
    out['gate_end'] = [round(float(w['MAIN_P'][-1]), 2), round(float(w['MAIN_N'][-1]), 2)]
    return out


if __name__ == '__main__':
    kw = dict(a.split('=') for a in sys.argv[4:])
    kw = {k: json.loads(v) for k, v in kw.items()}
    print(json.dumps(case(sys.argv[1], sys.argv[2], sys.argv[3], **kw)), flush=True)
