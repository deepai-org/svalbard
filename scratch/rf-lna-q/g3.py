"""G3 (round 3): DC point of the R+C extracted LNA against the C-only extraction, node by node (tt, RX bias, spirals in, no Rg).
Negative control: the C-only netlist with the gate-bias resistor chain opened must fail the same comparison."""
import sys, re, json; sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-q')
from var import *
PORT = {'tail': 'scm_b', 'vtk': 'vtk_b', 'tank_p': 'tkp_b', 'tank_n': 'tkn_b', 'src_p': 'srcp_b', 'src_n': 'srcn_b', 'ibias': 'ibias', 'atb_vdcm': 'atb_vdcm', 'atb_nbias': 'atb_nbias'}
NODES = list(PORT) + ['x_p', 'x_n', 'gi_p', 'gi_n', 'g_p', 'vg', 'vgr', 'vtg', 'vtc', 'vcas', 'tailx', 'pb', 'vtop', 'vgm', 'vtr', 'ncm', 'vlo']
def deck(nl):
    on = '\n'.join(f'V{n} {n} 0 {3.3 if n == "en" else 0}' for n in ('en', 'gain_lo', 'byp', 'island_off', 'se', 'rt', 'lobias', 'att0', 'att1', 'att2', 'att3', 'att4'))
    pr = ' '.join(f'v({PORT[n]})' if n in PORT else f'v(x1.{n})' for n in NODES)
    return f""".include {nl}
VDD VDD 0 3.3
Vibs vib 0 3.3
Ib vib ibias 10u
{on}
Vct0 ct0 0 3.3
Vct1 ct1 0 3.3
Vct2 ct2 0 3.3
Vct3 ct3 0 0
Vm vm 0 1.65
Rmp rf_out_p vm 50
Rmn rf_out_n vm 50
Rmqp rf_outq_p vm 50
Rmqn rf_outq_n vm 50
Rip rf_in_p 0 1e9
Rin rf_in_n 0 1e9
X1 rf_in_p rf_in_n rf_out_p rf_out_n rf_outq_p rf_outq_n ibias en gain_lo byp ct0 ct1 ct2 se rt island_off atb_nbias atb_vdcm VDD 0 ct3 att0 att1 att2 att3 att4 srcp_b srcn_b tkp_b tkn_b lobias scm_b vtk_b pt_lna
{tb.src_net('extpr')}
.control
op
let idd=-i(VDD)
print idd
{chr(10).join('print ' + q for q in pr.split())}
.endc
"""
def one(tag, text):
    W = Q / 'w' / f'g3_{tag}'; W.mkdir(parents=True, exist_ok=True)
    t = tb.with_lna_ind(text)
    p = W / 'lna_in.spice'; p.write_text(t)
    nl = S.prepare(W, p, 'lna.spice')
    log, m = tb.run(W, 'op.cir', deck(nl), TT)
    v = {}
    for l in log.splitlines():
        mm = re.match(r'\s*(v\(\S+\)|idd)\s*=\s*(\S+)', l)
        if mm: v[mm.group(1)] = float(mm.group(2))
    return v
import os
rc = Path(os.environ.get('RCNET', str(Q / 'rc' / 'pt_lna_flat.rc.spice'))).read_text().replace('pt_lna_flat', 'pt_lna')
ref = (flow.GENERATED / 'lna.ext.spice').read_text()
which = sys.argv[1:] or ['c', 'rc']
out = {}
for w in which:
    if w == 'c': out[w] = one('c', ref)
    if w == 'rc': out[w] = one('rc', rc)
    if w == 'neg': out[w] = one('neg', ref.replace('X64 r7_s1 r7_s2 VSS ppolyf_u_1k', 'X64 r7_s1 r7_open VSS ppolyf_u_1k'))
    print(w, json.dumps(out[w]), flush=True)
