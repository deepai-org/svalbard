#!/usr/bin/env python3
"""esdtab.py <tag> ...: worst numbers per stimulus from esd/<tag>.json (pad-VSS / pad-VDD = core-gate stand-ins, site currents, junction, MIM)."""
import json, sys
for t in sys.argv[1:]:
    d = json.load(open(f'esd/{t}.json'))['results']
    for st in sorted({r['stimulus'] for r in d}):
        rs = [r for r in d if r['stimulus'] == st]; ok = [r for r in rs if r.get('complete')]
        g = lambda k: max((r.get(k) or 0) for r in ok) if ok else None
        sc = [r['site_current'] for r in ok if r.get('site_current')]
        print(t, st, f'{len(ok)}/{len(rs)} complete', 'pad peak %.2f' % g('pad_peak_abs_v'), 'pad-VSS %.2f' % g('pad_minus_local_vss_abs_v'),
              'pad-VDD %.2f' % g('pad_minus_core_vdd_abs_v'), 'MOS over', g('mos_over_transient_limit'), 'nonprim rev %.2f' % g('worst_nonprimary_diode_rev_v'),
              'MIM %.2f' % g('worst_mim_v'), 'site fwd %.2f rev %.3f mA/um' % (max(c['max_fwd_ma_per_um'] for c in sc), max(c['max_rev_ma_per_um'] for c in sc)) if sc else '',
              'worst case', max(ok, key=lambda r: max(r['pad_minus_local_vss_abs_v'], r.get('pad_minus_core_vdd_abs_v') or 0))['case'] if ok else '')
