"""drv100.py <model> <tag> <vcas list> [k_cas k_sw k_tail]: 100BASE-TX headroom study (coordinator, before redesign).
MAIN + POST both steered to PAD_P (MAIN_P = POST_P = VDD, MAIN_N = POST_N = 0), termination off, 50 ohm to VDD at each pad
(the out-bench load), tail demand I_set = 38 mA (MAIN 3/4 via MAIN_BIAS mirror i/16, POST 1/4 via POST_BIAS i/16... see below), CASCODE at each value
of <vcas list> (V; 'vdd' = the supply). Reports delivered pad current, pad voltage, the cascode source (SUM_P_D) and tail nodes, at ss/32/3.15 and tt/27/3.3.
what-if scaling: k_cas / k_sw / k_tail multiply W of the PAD-side cascodes / MAIN+POST steering switches / MAIN+POST tails (m= on the instance)."""
import sys, json, re
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/pads-core/esdopt/tx')
import numpy as np, tb2
model, tag = sys.argv[1], sys.argv[2]; vlist = sys.argv[3].split(','); kc, ks, kt = (float(v) for v in (sys.argv[4:7] if len(sys.argv) > 6 else (1, 1, 1)))
text, cell, ports = tb2.load(model)
def scale(t):
    o = []
    for l in t.splitlines():
        tk = l.split()
        if len(tk) > 5 and tk[0][0] == 'X' and tk[5] in ('nfet_06v0', 'nfet_03v3'):
            g = tk[2]; k = 1.
            if tk[5] == 'nfet_06v0' and g == 'CASCODE': k = kc
            elif g in ('MAIN_P', 'MAIN_N', 'POST_P', 'POST_N'): k = ks
            elif g in ('MAIN_BIAS', 'POST_BIAS'): k = kt
            if k != 1.: l = l + f' m={k:g}'
        o.append(l)
    return '\n'.join(o) + '\n'
text = scale(text)
W = tb2.HERE / 'bench' / tag; out = dict(model=model, model_sha256=tb2.s.sha(__import__('pathlib').Path(model)), k=[kc, ks, kt], runs={})
I = 38e-3; im, ip = .75 * I, .25 * I
for pr, t, vdd in [('ss', 32, 3.15), ('typical', 27, 3.3)]:
    for vc in vlist:
        vcv = vdd if vc == 'vdd' else float(vc)
        import os as _o
        over = {'TERM_ENABLE': 'VTERM_ENABLE TERM_ENABLE 0 0\n', 'CASCODE': f'VCAS CASCODE 0 {vcv}\n',
                **({'CASCODE100': f"VCAS100 CASCODE100 0 {_o.environ['VC100']}\n"} if _o.environ.get('VC100') else {}),
                'MAIN_BIAS': f'IREF VDD MAIN_BIAS {im / 16}\nXREFA MAIN_BIAS MAIN_BIAS 0 0 nfet_03v3 w=20u l=1u m={kt:g}\nXREFB MAIN_BIAS MAIN_BIAS 0 0 nfet_03v3 w=20u l=1u m={kt:g}\n',
                'POST_BIAS': f'IREFP VDD POST_BIAS {ip / 16 * 3}\nXREFC POST_BIAS POST_BIAS 0 0 nfet_03v3 w=20u l=1u m={kt:g}\nXREFD POST_BIAS POST_BIAS 0 0 nfet_03v3 w=20u l=1u m={kt:g}\n',
                'MAIN_P': 'VMAIN_P MAIN_P VDD 0\n', 'MAIN_N': 'VMAIN_N MAIN_N 0 0\n', 'POST_P': 'VPOST_P POST_P VDD 0\n', 'POST_N': 'VPOST_N POST_N 0 0\n'}
        for k in range(4): over[f'TERM_TRIM{k}'] = f'VT{k} TERM_TRIM{k} 0 0\n'
        d = tb2.header(pr, t) + text + tb2.controls(ports, vdd, over) + 'Xpad ' + ' '.join(ports) + f' {cell}\nVdum dum 0 0\nRdum dum 0 1k\n'
        d += 'VLP LP VDD 0\nVLN LN VDD 0\nRLP LP PAD_P 50\nRLN LN PAD_N 50\n'
        vecs = ['v(pad_p)', 'i(VLP)', 'i(VLN)'] + [f'v(xpad.sum_p_d_{u})' for u in range(8)] + [f'v(xpad.main_tail_{u})' for u in range(8)] + [f'v(xpad.post_tail_{u})' for u in range(8)]
        name = f'd_{pr}_{vc}'.replace('.', 'p'); d += tb2.s.control(W, name, 'dc Vdum 0 0.5 1', ' '.join(vecs))
        x = np.atleast_2d(tb2.s.run(W, name, d, timeout_s=3000))[0]
        r = dict(vcas=vcv, pad_p=round(float(x[1]), 3), i_pad_mA=round(-float(x[2]) * 1e3, 2), i_padn_mA=round(-float(x[3]) * 1e3, 3),
                 v_sum_min=round(float(min(x[4:12])), 3), v_main_tail_min=round(float(min(x[12:20])), 3), v_post_tail_min=round(float(min(x[20:28])), 3))
        out['runs'][f'{pr}_{vc}'] = r; print(pr, vc, r, flush=True)
        for q in list(W.glob('*.dat')) + list(W.glob('*.spice')): q.unlink()
(tb2.HERE / 'bench' / f'{tag}-drv100.json').write_text(json.dumps(out, indent=1))
