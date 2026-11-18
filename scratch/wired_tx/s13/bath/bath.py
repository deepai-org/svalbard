"""Data-timing bathtub of the extracted mux: far-end eye against tau_F = time of the stream change relative to the rising
edge of the slice's own phase at the mux pin (m8 bench, ideal phases).   python3 bath.py corner rate tau_ns ...
Purpose: the valid range of tau_F, to place the wtx_ser8d hops (no pass / fail limit: a characterisation)."""
import sys, json
from pathlib import Path
sys.path.insert(0, '../../s12/mux'); sys.path.insert(0, '../../s12'); sys.path.insert(0, '../post')
import m8
m8.RUNS = Path(__file__).resolve().parent / 'runs'
E = '/home/ubuntu/svalbard/scratch/wired_tx/s12/layout/out2/wtx_mux8.ext.spice'
C = dict(ssp=dict(corner='ss', temp=32, vdd=3.15, swing=2.69, pess=True), ff=dict(corner='ff', temp=22, vdd=3.35, swing=3.01, pess=False),
         tt=dict(corner='typical', temp=27, vdd=3.3, swing=2.95, pess=False))
c, rate = sys.argv[1], float(sys.argv[2])
ext = E
out = open('bath.log', 'a')
for tau in sys.argv[3:]:
    tau = float(tau); ui = 1e9 / rate
    o = m8.run(f'b_{c}_{rate / 1e9:g}_{tau:+.2f}', rate=rate, nbits=120, ext=ext, dskew=(tau + 3.5 * ui) * 1e-9, **C[c])
    fr = o.get('far', {})
    out.write(json.dumps(dict(c=c, rate=rate, tau_ns=tau, errors=fr.get('errors'), eye_h=fr.get('eye_h_v'), eye_w=fr.get('eye_w_ui'), dj=fr.get('dj_pp_ps'))) + '\n'); out.flush()
    (m8.RUNS / f'b_{c}_{rate / 1e9:g}_{tau:+.2f}' / 'wave.txt').unlink(missing_ok=True)
