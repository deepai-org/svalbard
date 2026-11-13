#!/usr/bin/env python3
"""Checks on one power-up bench run (runs/<name>.raw + .cfg.json). Every limit is fixed here, before the runs.

 C_por     por_n low at some point with VDD >= 1.5 V (a real reset pulse) and released by the end ('ramp' shapes)
 C_rst     rst_n (std-cell AND/OR of RESET_N=VDD, por_n, por_bypass) high at the end
 C_island  every island rail stays <= 0.40 V for the whole run (default off; "turns on unintended" otherwise)
 C_en      every island_en / biasgen.ena flop output <= 0.30 V whenever VDD >= 1.0 V (host clocks ones until 20 ms)
 C_iso     ISO_<island> >= 0.8*VDD whenever VDD >= 1.5 V
 C_clamp   iso_clamp output <= 0.30 V whenever VDD >= 1.0 V (its input floats high through 10 Mohm)
 C_vmax    no saved node above 3.63 V (DC oxide limit of the 3.3 V devices) or below -0.30 V (junction)
 inrush    peak bond current and the time it stays above 100 mA (reported; limit 300 mA = one connector contact)
"""
import json, sys, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rawread import read
ISL = ['wired', 'rf', 'pll', 'conv', 'debug']


def analyze(name):
    cfg = json.load(open(f'{HERE}/runs/{name}.cfg.json'))
    d = read(f'{HERE}/runs/{name}.raw')
    t, v = d['time'], d['v(vdd)']
    r = dict(name=name, cfg={k: cfg[k] for k in ('stage', 'corner', 'temp', 'shape', 'tr', 'vfin', 'cdie', 'inject', 'bypass', 'aosc', 'loop')},
             points=len(t), t_end=float(t[-1]), vdd_max=float(v.max()), vdd_end=float(v[-1]))
    ck = {}
    il = d['i(lbond)']
    r['inrush_peak_ma'] = float(np.abs(il).max()*1e3)
    above = np.abs(il) > 0.1
    r['inrush_time_above_100ma_us'] = float(np.sum(np.diff(t)[above[:-1]])*1e6)
    ck['inrush'] = r['inrush_peak_ma'] <= 300.0
    if 'v(por_n)' in d:
        p = d['v(por_n)']
        rel = None
        low_seen = bool(np.any((v >= 1.5) & (p < 0.3*v)))
        for i in range(1, len(t)):
            if v[i] >= 1.0 and p[i] > 0.5*v[i] and (rel is None):
                rel = i
                break
        r['por_release_s'] = float(t[rel]) if rel is not None else None
        r['por_release_vdd'] = float(v[rel]) if rel is not None else None
        r['por_low_seen_at_vdd_ge_1p5'] = low_seen
        # every release / re-assert edge after the first one
        st = (p > 0.5*np.maximum(v, 0.2)) & (v >= 1.0)
        r['por_edges'] = [(float(t[i]), int(st[i])) for i in range(1, len(t)) if st[i] != st[i-1]][:12]
        final_up = v[-1] > 1.5
        long_run = t[-1] >= 0.02     # release checks only apply to runs long enough to reach it (short runs: islands/iso/inrush only)
        r['release_checked'] = bool(long_run)
        ck['por'] = (low_seen and rel is not None and p[-1] > 0.8*v[-1]) if (final_up and long_run and cfg['inject'] != 'por_stuck') else True
    if 'v(rst_n)' in d:
        rst = d['v(rst_n)']
        ck['rst'] = bool(rst[-1] > 0.8*v[-1]) if (v[-1] > 1.5 and t[-1] >= 0.02) else True
        on = v >= 1.0
        on15 = v >= 1.5
        rails = {i: float(d[f'v(rail_{i})'].max()) for i in ISL}
        r['rail_max_v'] = rails
        ck['island'] = all(x <= 0.40 for x in rails.values())
        ens = {i: float(d[f'v(en_{i})'][on].max()) if on.any() else 0.0 for i in ISL}
        ens['biasena'] = float(d['v(en_biasena)'][on].max()) if on.any() else 0.0
        r['en_max_v'] = ens
        ck['en'] = all(x <= 0.30 for x in ens.values())
        r['iso_min_ratio'] = {i: float((d[f'v(iso_{i})'][on15]/v[on15]).min()) if on15.any() else 1.0 for i in ISL}
        ck['iso'] = all(x >= 0.8 for x in r['iso_min_ratio'].values())
        r['clamp_y_max_v'] = {i: float(d[f'v(y_{i})'][on].max()) if on.any() else 0.0 for i in ISL}
        ck['clamp'] = all(x <= 0.30 for x in r['clamp_y_max_v'].values())
        r['pg_max_v'] = {i: float(d[f'v(pg_{i})'].max()) for i in ISL}
    vn = {k: (float(x.max()), float(x.min())) for k, x in d.items() if k.startswith('v(')}
    hi = max(vn.items(), key=lambda kv: kv[1][0]); lo = min(vn.items(), key=lambda kv: kv[1][1])
    r['node_max'] = [hi[0], hi[1][0]]; r['node_min'] = [lo[0], lo[1][1]]; r['nodes_checked'] = len(vn)
    ck['vmax'] = hi[1][0] <= 3.63 and lo[1][1] >= -0.30
    # information only (classification added after the first results): nodes that touch 3.3 V-oxide devices,
    # i.e. everything except the nets that only connect 5 V-oxide std cells (rst_n, sclk, en_*)
    v33 = {k: x for k, x in vn.items() if not k.startswith(('v(rst_n', 'v(sclk', 'v(en_'))}
    h33 = max(v33.items(), key=lambda kv: kv[1][0])
    r['node_max_3v3_oxide'] = [h33[0], h33[1][0]]
    if 'v(aosc_clk)' in d:
        a = d['v(aosc_clk)']
        cr = np.where((a[1:] > 0.5*v[1:]) & (a[:-1] <= 0.5*v[:-1]) & (v[1:] > 1.0))[0]
        r['aosc_first_edge_s'] = float(t[cr[0]]) if len(cr) else None
        r['aosc_f_mhz'] = float(1e-6/np.mean(np.diff(t[cr[-20:]]))) if len(cr) > 21 else None
    if 'i(vsrc)' in d:
        r['isrc_end_ua'] = float(-d['i(vsrc)'][-1]*1e6)
    r['block_current_end_ua'] = {k[5:-1]: float(x[-1]*1e6) for k, x in d.items() if k.startswith('i(vm_')}
    r['checks'] = {k: bool(x) for k, x in ck.items()}
    r['pass'] = all(ck.values())
    return r


if __name__ == '__main__':
    out = {}
    for n in sys.argv[1:]:
        try:
            out[n] = analyze(n)
        except Exception as e:
            out[n] = dict(name=n, error=repr(e), **{'pass': False})
        r = out[n]
        print(n, 'PASS' if r['pass'] else 'FAIL', {k: v for k, v in r.get('checks', {}).items() if not v} or '',
              'por_rel=%s' % r.get('por_release_s'), 'Ipk=%.1fmA' % r.get('inrush_peak_ma', -1), 'vddmax=%.3f' % r.get('vdd_max', -1), r.get('error', ''))
    prev = {}
    p = HERE+'/results.json'
    if os.path.exists(p):
        prev = json.load(open(p))
    prev.update(out)
    json.dump(prev, open(p, 'w'), indent=1)
