"""POST bank runs on the extracted mux (m8 bench).  python3 sweep.py name '{"...": ...}' ...  -> runs/<name>, log sweep.log"""
import sys, json
from pathlib import Path
sys.path.insert(0, '../../s12/mux'); sys.path.insert(0, '../../s12')
import m8
m8.RUNS = Path(__file__).resolve().parent / 'runs'
E = '/home/ubuntu/svalbard/scratch/wired_tx/s12/layout/out2/wtx_mux8.ext.spice'
C = dict(tt=dict(corner='typical', temp=27, vdd=3.3, swing=2.95, pess=False),
         ss=dict(corner='ss', temp=32, vdd=3.15, swing=2.69, pess=False),
         ff=dict(corner='ff', temp=22, vdd=3.35, swing=3.01, pess=False),
         ssp=dict(corner='ss', temp=32, vdd=3.15, swing=2.69, pess=True),
         sspT=dict(corner='ss', temp=32, vdd=3.5, swing=3.02, pess=True))
out = open('sweep.log', 'a')
for spec in sys.argv[1:]:
    j = json.loads(spec); tag = j.pop('tag'); c = C[j.pop('c')]
    o = m8.run(tag, rate=j.pop('rate', 3.125e9), nbits=j.pop('nbits', 240), ext=j.pop('ext', E), **c, **j)
    out.write(m8.summ(o) + '\n'); out.flush()
