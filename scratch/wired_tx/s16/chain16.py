"""Session-16 real-chain bench: ../s14/chain/chain14.py (= ../s13/chain13.py + labels) with

  * netlist: net/pt_wiredtx8.fullfix16.rc.spice (current block, GDS sha in net/SHA256; Magic extresist + fixcap16.py);
  * ring route per phase: route=[ohm, F] (default TIM-23 nominal 30 ohm + 75 fF, split 1/2 + 1/2 around the R as in chain13;
    bound 45 ohm + 110 fF); the old bench default 30 ohm / 60 fF is never used;
  * stuck=j: stream j (D inputs j, j+8, ..) held at 0 for the data pass (negative control); kill=k as in chain13;
  * pad_file=<path>: pad model registered as pad_model 'TA' (reworked pad option A, label pad=optA:<file name>);
  * results in s16/results, runs in s16/runs.

    python3 chain16.py '{"tag":..., "corner":"ss", "pess":true, "vdd":3.15, "rate":3.125e9, "codes":[...], "pad_model":"C"}'
    python3 chain16.py sanity <tag>     # 40 ns, ss pess. 3.15 V, 3.125 Gb/s, pad=C: TX_RUN rise time
"""
import sys, json, time
from pathlib import Path
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H.parent / 's14' / 'chain'))
import chain14
from chain14 import C13, tools
import numpy as np

NET = H / 'net' / 'pt_wiredtx8.fullfix16.rc.spice'
ROUTE_NOM = (30.0, 75e-15)
C13.RUNS = H / 'runs'
chain14.RES = H / 'results'
_route = list(ROUTE_NOM)
_stuck = None
_deck = C13.deck


def deck(work, **kw):
    kw['ring'] = dict(kw['ring'], route=tuple(_route))
    if _stuck is not None and kw.get('full'):
        kw['words'] = [[0 if i % 8 == _stuck else b for i, b in enumerate(w)] for w in kw['words']]
    return _deck(work, **kw)


C13.deck = deck
_save14 = chain14._save


def _save(out):
    out['route_ohm_F'] = list(_route)
    out['route'] = 'route=TIM-23 nom 30ohm/75fF' if tuple(_route) == ROUTE_NOM else f'route={_route[0]:g}ohm/{_route[1] * 1e15:g}fF'
    out['stuck'] = _stuck
    return _save14(out)


C13._save = _save


def setup(kw):
    """common job preprocessing (also used by cal16): route, stuck, pad_file, netlist."""
    global _route, _stuck
    _route = list(kw.pop('route', ROUTE_NOM))
    _stuck = kw.pop('stuck', None)
    pf = kw.pop('pad_file', None)
    if pf:
        C13.PADFILE['TA'] = Path(pf); C13.PADLABEL['TA'] = 'pad=optA:' + Path(pf).name
        kw['pad_model'] = 'TA'
    kw.setdefault('top_ext', str(NET))
    return kw


def run(**kw):
    return chain14.run(**setup(kw))


def sanity(tag, tstop=40e-9):
    """40 ns data-pass deck, ss pess. 3.15 V, 3.125 Gb/s ring (pess tune), pad=C, nominal route: when does TX_RUN rise."""
    tn = C13.tune('ss', 32, 2.69, 0, 3.125e9 / 8, True)
    ring = dict(ver='layout', pess=True, vring=2.69, vctrl=tn['vctrl'], band=0)
    w = H / 'runs' / tag; w.mkdir(parents=True, exist_ok=True)
    common = dict(corner='ss', temp=32, vdd=3.15, res='ss', pess=True, ring=ring, rate=8 * tn['f_hz'], codes=[0, 1, 3, 2, 3, 5, 2, 6], main_code=160,
                  post_code=0, en_post=0, pol=0, idle=0, idle_mode=0, ext=0, dx_bits=None, dx_rate=None, tap=0, mux_ext=None, aux_ext=None,
                  ser_ext=str(C13.FAST / 'wtx_ser8d.ext.spice'), bond='pess', kill=None, S_=1.0, probes=('XTOP.XMUX.XE0', 'XTOP.XMUX.DN0'),
                  launch=0.25, supply=None, par=None, top_ext=str(NET), pad_model='C')
    names = deck(w, words=[[i % 2 for i in range(40)]] * 4, word_t0=2e-9, tstop=tstop, full=True, **common)
    t = time.time(); tools.ngspice_host(w, 'tb.sp', timeout=40000); dt = time.time() - t
    o = dict(tag=tag, net=str(NET), net_sha256=chain14.sha(NET), route=list(_route), sec=round(dt))
    if (w / 'wave.txt').exists():
        a = tools.read_wrdata(w / 'wave.txt', names); tt = a['time']
        up = C13.S.crossings(tt, a['TX_RUN'], th=3.15 / 2, rising=True)
        late = tt > tt[-1] - 5e-9
        o.update(t_run_ns=round(float(up[0]) * 1e9, 2) if len(up) else None,
                 gate_pp_v=round(float(np.ptp((a['MAIN_P'] - a['MAIN_N'])[late])), 3), pad_pp_v=round(float(np.ptp((a['PAD_P'] - a['PAD_N'])[late])), 3),
                 xe0_pp_v=round(float(np.ptp(a['XTOP.XMUX.XE0'][late])), 2) if 'XTOP.XMUX.XE0' in a else None,
                 i_ma=round(float(-np.mean(a['I'][late])) * 1e3, 1))
    for f in w.glob('*'):
        if f.name != 'tb.sp':
            f.unlink()
    (H / 'results').mkdir(exist_ok=True)
    (H / 'results' / f'{tag}.json').write_text(json.dumps(o, indent=1))
    return o


if __name__ == '__main__':
    if sys.argv[1] == 'sanity':
        print(json.dumps(sanity(sys.argv[2])), flush=True)
    else:
        print(C13.summ(run(**json.loads(sys.argv[1]))), flush=True)
