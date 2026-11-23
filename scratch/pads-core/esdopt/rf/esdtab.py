"""esdtab.py <esd json> ...: per stimulus, worst over cases: MOS gate (6 V / 3.3 V), count over the transient limit, diode reverse
(site primaries vs bv; non-primary as fraction of bv), MIM, bond pad |V| (info), incomplete runs."""
import json, sys, collections
for f in sys.argv[1:]:
    d = json.load(open(f)); rows = collections.defaultdict(list)
    for r in d['results']: rows[r['stimulus']].append(r)
    print(f"== {d['tag']}  ring {d.get('ring_ohm')} sitecap {d.get('sitecap')}")
    for s, rs in rows.items():
        ok = [r for r in rs if r.get('complete')]; inc = len(rs) - len(ok)
        g = max(ok, key=lambda r: (r.get('worst_mos') or {}).get('gate_v', 0))
        over = sum(r['mos_over_transient_limit'] for r in ok)
        dv = max(ok, key=lambda r: r['worst_diode_reverse_v']); npd = max(ok, key=lambda r: r['worst_nonprimary_frac_bv'])
        pad = max(ok, key=lambda r: r['pad_peak_abs_v']); mim = max(r['worst_mim_v'] for r in ok)
        print(f"{s:8s} n={len(ok)}{' INCOMPLETE %d' % inc if inc else ''} gate {(g.get('worst_mos') or {}).get('gate_v')} ({(g.get('worst_mos') or {}).get('model')}, {g['case']}) over-limit {over} | "
              f"diode rev {dv['worst_diode_reverse_v']} ({dv['worst_diode'].split()[1] if dv['worst_diode'] else ''}, {dv['case']}) nonprim {npd['worst_nonprimary_diode_rev_v']} V = {npd['worst_nonprimary_frac_bv']} bv | "
              f"mim {mim:.2f} | pad {pad['pad_peak_abs_v']:.2f} ({pad['case']}) | ring {max(r['ring_dvdd_minus_dvss_site_v'][1] for r in ok):.2f}")
