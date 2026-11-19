import json, sys
for l in open(sys.argv[1]):
    if not l.startswith('{'):
        print(l.strip()[:200]); continue
    o = json.loads(l)
    g = o.get('gate') or {}
    print(o.get('tag'), {k: o.get(k) for k in ('run_end', 't_run_low_ns', 'i_tot_end_ma', 'i_bank_end_ma', 't_bank_below_0p1_ns', 'i_bank_max_after_stop_ma', 'i_bank_max_ma', 'i_tot_ma', 'reason')}, g.get('errors'), g.get('eye_h_v'),
          {k: v for k, v in o.items() if k.startswith('grp_')})
