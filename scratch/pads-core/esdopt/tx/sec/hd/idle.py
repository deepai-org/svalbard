"""idle.py <model> <tag>: WT53-c stress screen. CASCODE at 4.2 / 4.6 V, both pads forced to Vpad in {1.0, 2.3, 3.6} V, driver idle (all steering switches off, tails
biased as in 100BASE-TX: MAIN / POST mirrors 38 mA total demand) or driving (MAIN_P = POST_P = VDD), termination off. Reports per MOS model the max
|Vg-x| / |Vds| / junction, and SUM / tail node levels, at ss/32/3.15, tt/27/3.3, ff/22/3.45 and ff/85/3.45 (DC)."""
import sys, json
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/pads-core/esdopt/tx')
import numpy as np, tb2
text, cell, ports = tb2.load(sys.argv[1]); W = tb2.HERE / 'bench' / sys.argv[2]; out = {}
mos = [(a, b) + tuple(v if v.startswith('xpad.') else (v[2:] if v.startswith('c_') else v) for v in c) for a, b, *c in tb2.mos_nodes(text, cell, ports)]
fix = {'rs': '0', 'sp': '0', 'sn': '0', 'dp': 'vdd', 'dn': 'vdd'}
mos = [(a, b) + tuple(fix.get(v, v) for v in c) for a, b, *c in mos]
want = sorted({v for dv in mos for v in dv[2:] if v != '0'} | {'pad_p', 'pad_n', 'cascode'})
for pr, t, vdd in [('ss', 32, 3.15), ('typical', 27, 3.3), ('ff', 22, 3.45), ('ff', 85, 3.45)]:
    for vc in (4.2, 4.6):
        for mode in ('idle', 'drive'):
            for vp in (1.0, 2.3, 3.6):
                over = {'TERM_ENABLE': 'VTERM_ENABLE TERM_ENABLE 0 0\n', 'CASCODE': f'VCAS CASCODE 0 {vc}\n',
                        'MAIN_BIAS': f'IREF VDD MAIN_BIAS {0.75 * 38e-3 / 16}\nXREFA MAIN_BIAS MAIN_BIAS 0 0 nfet_03v3 w=20u l=1u\nXREFB MAIN_BIAS MAIN_BIAS 0 0 nfet_03v3 w=20u l=1u\n',
                        'POST_BIAS': f'IREFP VDD POST_BIAS {0.25 * 38e-3 / 16 * 3}\nXREFC POST_BIAS POST_BIAS 0 0 nfet_03v3 w=20u l=1u\nXREFD POST_BIAS POST_BIAS 0 0 nfet_03v3 w=20u l=1u\n'}
                for g in ('MAIN_P', 'POST_P'): over[g] = f'V{g} {g} ' + ('VDD 0' if mode == 'drive' else '0 0') + '\n'
                for g in ('MAIN_N', 'POST_N'): over[g] = f'V{g} {g} 0 0\n'
                for k in range(4): over[f'TERM_TRIM{k}'] = f'VT{k} TERM_TRIM{k} 0 0\n'
                d = tb2.header(pr, t) + text + tb2.controls(ports, vdd, over) + 'Xpad ' + ' '.join(ports) + f' {cell}\nVPA PAD_P 0 {vp}\nVNA PAD_N 0 {vp}\nVdum dum 0 0\nRdum dum 0 1k\n'
                name = f'i_{pr}_{t}_{vc}_{mode}_{vp}'.replace('.', 'p'); d += tb2.s.control(W, name, 'dc Vdum 0 0.5 1', ' '.join(f'v({n})' for n in want) + ' i(VPA)')
                x = np.atleast_2d(tb2.s.run(W, name, d, timeout_s=3000))[0]; col = {n: float(x[1 + i]) for i, n in enumerate(want)}; col['0'] = 0.; col['vdd'] = vdd
                worst = {}
                for nm, mdl, dd, g, ss_, b in mos:
                    vg = max(abs(col[g] - col[k]) for k in (dd, ss_, b)); vds = abs(col[dd] - col[ss_])
                    w = worst.setdefault(mdl, dict(g=0., ds=0., gdev='', dsdev=''))
                    if vg > w['g']: w['g'], w['gdev'] = round(vg, 3), nm
                    if vds > w['ds']: w['ds'], w['dsdev'] = round(vds, 3), nm
                sums = [v for k, v in col.items() if k.startswith('xpad.sum_')]
                r = dict(mos=worst, sum_max=round(max(sums), 3) if sums else None, i_pad_mA=round(-float(x[-1]) * 1e3, 3))
                out[name] = r
                print(name, 'sum_max', r['sum_max'], 'n03', worst.get('nfet_03v3'), 'n06', worst.get('nfet_06v0'), flush=True)
                for q in list(W.glob('*.dat')) + list(W.glob('*.spice')): q.unlink()
(tb2.HERE / 'bench' / f'{sys.argv[2]}-idle.json').write_text(json.dumps(dict(model=sys.argv[1], model_sha256=tb2.s.sha(__import__('pathlib').Path(sys.argv[1])), runs=out), indent=1))
