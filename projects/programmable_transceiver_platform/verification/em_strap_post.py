"""PD46 r2: re-score em-*.json strap rows with the per-bar crowding ladder (em_strap_ladder.worst) without re-simulating.
Usage: strap_post.py <layout.json> <em-*.json> ... -> prints worst per corner and writes <em>.crowd.json"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import em_strap_ladder as sl
lay = json.loads(Path(sys.argv[1]).read_text()); tw = lay.get('trunk_widths_um', {})
for f in sys.argv[2:]:
    r = json.loads(Path(f).read_text()); out = {}
    hs = {}
    for s in lay['power_straps']: hs.setdefault((s['unit'], s['net']), []).append(s['strap_um'][3] - s['strap_um'][1])
    kimb = lambda u, n: 1.0 if len(hs[(u, n)]) == 1 else 1.2   # same rule as em_check.py
    for name, c in r['corners'].items():
        rows = []
        for s in c['strap_rows']:   # rows from the r2+ em_check already include via4 crowding (via4_crowding key)
            k0 = s.get('imbalance', 1.2); s = dict(s, bar_mA=s['bar_mA'] / k0 * kimb(s['unit'], s['net']), via4_frac=s['via4_frac'] / k0 * kimb(s['unit'], s['net']))   # rows store their imbalance factor (pre-r2 rows: flat 1.2x)
            m4, v4k, v23 = sl.worst(0., tw.get(s['net'], 8.), s['length_um'], s['bar_h_um'], s['bar_mA'])
            rows.append(dict(unit=s['unit'], net=s['net'], m4_peak_share=round(float(m4), 3), metal_frac=round(s['bar_mA'] * m4 / s['bar_h_um'] / 2.09, 3),
                             via4_frac=round(s['via4_frac'] * (1. if 'via4_crowding' in s else v4k), 3), via23_frac=round(v23 / .58, 3), via1_frac=s['via1_frac'], contact_frac=s['contact_frac']))
        w = {k: max(rows, key=lambda q: q[k]) for k in ('metal_frac', 'via4_frac', 'via23_frac', 'via1_frac', 'contact_frac')}
        out[name] = dict(rows=rows, worst={k: (v[k], v['unit'], v['net']) for k, v in w.items()})
        print(Path(f).parent.parent.name, Path(f).parent.name, name, {k: v[k] for k, v in w.items()}, flush=True)
    Path(f).with_suffix('.crowd.json').write_text(json.dumps(out, indent=1))
