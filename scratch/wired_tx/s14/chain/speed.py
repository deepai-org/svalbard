"""timing check: same data-pass deck (ss pess 3.15 V, 3.125 Gb/s, ring layout-11Nov pess, pad=C) for a given top netlist, tstop 40 ns."""
import sys, time, json
import chain14
from chain14 import C13, HERE
net, tag = sys.argv[1], sys.argv[2]
w = HERE / 'runs' / tag; w.mkdir(parents=True, exist_ok=True)
ring = dict(ver='layout', pess=True, vring=2.69, vctrl=1.4823, band=0)
rate = 3.12048e9
words = [[i % 2 for i in range(40)]] * 4
common = dict(corner='ss', temp=32, vdd=3.15, res='ss', pess=True, ring=ring, rate=rate, codes=[0, 1, 3, 3, 4, 5, 3, 7], main_code=160, post_code=0,
              en_post=0, pol=0, idle=0, idle_mode=0, ext=0, dx_bits=None, dx_rate=None, tap=0, mux_ext=None, aux_ext=None,
              ser_ext=str(C13.FAST / 'wtx_ser8d.ext.spice'), bond='pess', kill=None, S_=1.0, probes=(), launch=0.25, supply=None, par=None,
              top_ext=str(HERE / net), pad_model='C')
C13.deck(w, words=words, word_t0=2e-9, tstop=40e-9, full=True, **common)
t = time.time(); C13.tools.ngspice_host(w, 'tb.sp', timeout=40000); dt = time.time() - t
print(json.dumps(dict(tag=tag, net=net, sha=chain14.sha(HERE / net), sec=round(dt), ok=(w / 'wave.txt').exists())))
