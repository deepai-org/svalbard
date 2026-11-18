"""Transmit pad with metal resistance: eye loss and requirement sweep (m8 bench: extracted revision-2 mux, ideal phases,
pad + COB bond + connector + 50 mm line).   python3 padr.py A | B     -> padr.log (one json line per run)
  pad model  C = published capacitance-only extraction; RT / RH = scratch/pads-core/txr/models/tx_rt / tx_rh.spice
  sweep B (pad C + lumped elements): rs = series ohm per leg between bond wire and pad pin; rterm = ideal differential
  termination (pad's own switched off); cpad = extra F per leg at the pad pin; S = MAIN switch scale."""
import sys, json, re
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 's12' / 'mux')); sys.path.insert(0, str(HERE.parent.parent / 's12'))
import m8
from m8 import CH, B
m8.RUNS = HERE / 'runs'
E = '/home/ubuntu/svalbard/scratch/wired_tx/s12/layout/out2/wtx_mux8.ext.spice'
PADS = dict(C=B.PAD, RT=Path('/home/ubuntu/svalbard/scratch/pads-core/txr/models/tx_rt.spice'), RH=Path('/home/ubuntu/svalbard/scratch/pads-core/txr/models/tx_rh.spice'))
C = dict(tt=dict(corner='typical', temp=27, vdd=3.3, swing=2.95, pess=False), ss=dict(corner='ss', temp=32, vdd=3.15, swing=2.69, pess=False),
         ssp=dict(corner='ss', temp=32, vdd=3.15, swing=2.69, pess=True), ff=dict(corner='ff', temp=22, vdd=3.35, swing=3.01, pess=False))
orig = CH.chain_lines
MOD = {}


def chain_lines(*a, **k):
    L = orig(*a, **k); out = []
    for l in L:
        p = l.split()
        if MOD.get('rs') and p and p[0].startswith('RBW'):
            l = f'{p[0]} {p[1]} {p[2]} {0.23 + MOD["rs"]}'
        if MOD.get('rterm') and p and p[0] == 'VTE':
            l = 'VTE TERM_ENABLE 0 0'
        out.append(l)
    if MOD.get('rterm'):
        out += [f'RXTP PAD_P XVCM {MOD["rterm"] / 2}', f'RXTN PAD_N XVCM {MOD["rterm"] / 2}', 'VXV XVCM 0 1.65']
    if MOD.get('cpad'):
        out += [f'CXP PAD_P 0 {MOD["cpad"]}', f'CXN PAD_N 0 {MOD["cpad"]}']
    return out


CH.chain_lines = chain_lines
log = open(HERE / 'padr.log', 'a')


def one(tag, c, rate, pad='C', S_=1.0, **mod):
    MOD.clear(); MOD.update(mod); B.PAD = PADS[pad]
    o = m8.run(tag, rate=rate, nbits=240, ext=E, S_=S_, **C[c])
    fr = o.get('far', {})
    log.write(json.dumps(dict(tag=tag, c=c, rate=rate, pad=pad, S=S_, **mod, errors=fr.get('errors'), bits=fr.get('bits'), eye_h=fr.get('eye_h_v'),
                              eye_w=fr.get('eye_w_ui'), amp=fr.get('amp_pp_v'), ok=o.get('ok'), i_ma=o.get('i_ma'), reason=str(o.get('reason', ''))[-80:])) + '\n'); log.flush()
    (m8.RUNS / tag / 'wave.txt').unlink(missing_ok=True)


if sys.argv[1] == 'A':
    for c, rate in (('ss', 3.125e9), ('tt', 3.125e9), ('ss', 3.24e9), ('ss', 2.7e9), ('tt', 3.24e9), ('tt', 2.7e9), ('ssp', 3.125e9)):
        for pad in ('C', 'RT', 'RH'):
            one(f'A_{c}_{rate / 1e9:g}_{pad}', c, rate, pad)
else:
    for k, vals in (('rs', (2, 5, 10, 18)), ('rterm', (85, 100, 115, 150, 350)), ('cpad', (0.2e-12, 0.5e-12))):
        for v in vals:
            one(f'B_{k}_{v:g}', 'ssp', 3.125e9, 'C', **{k: v})
    one('B_S0.6', 'ssp', 3.125e9, 'C', S_=0.6)
    one('B_S0.6_RT', 'ssp', 3.125e9, 'RT', S_=0.6)
log.write('{"done": "%s"}\n' % sys.argv[1])
