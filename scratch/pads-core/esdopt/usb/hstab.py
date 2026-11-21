#!/usr/bin/env python3
"""hstab.py tag ...: summary of bench/<tag>-hseye.json / -hsrl.json (hseye.py)."""
import json, sys, os
for tag in sys.argv[1:]:
    for kind in ('hseye', 'hsrl'):
        fn = f'bench/{tag}-{kind}.json'
        if not os.path.exists(fn): continue
        d = json.load(open(fn)); r = d['result']; c = '/'.join(map(str, d['corner']))
        if kind == 'hseye':
            t = r['template1_tp']
            print(f"{tag:16s} eye {c:16s} code {d['term_code']} bond {d['bond']} tb {d['tb_mm']:g}mm: TP level {r['tp_level_mv']} host {r['host_level_mv']} "
                  f"tpl1 {'PASS' if t['ok'] else 'FAIL'} inner {t['inner_margin_mv']} outer {t['outer_margin_mv']} mV jit {t['crossing_jitter_pp_ps']} ps "
                  f"edges {r['edge_10_90_ps']} level {'ok' if r['level_ok'] else 'MISS'}")
        else:
            print(f"{tag:16s} rl  {c:16s} code {d['term_code']} bond {d['bond']}: RL min to 480 MHz {r['rl_min_db_to_480MHz']} dB, to 1 GHz {r['rl_min_db_to_1GHz']} dB; "
                  f"{r['rl_db']}; TDR Zdiff {r['tdr_zdiff_ohm']}; |Zdd| 10 MHz {r['zdd_ohm_10MHz']}")
