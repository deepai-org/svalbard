"""Session-14 block rows: ../../s13/chain13.py unchanged, with results under s14/chain and extra labels / options.

  * every result carries net_sha256 (the top_ext netlist actually simulated), pad_sha256, ring and pad labels;
  * netlists are the snapshots in net/ (the generated/fast files are rewritten by another worker);
  * pad_model 'TA' = reworked pad_txpad option A, only when its model file exists (set PADFILE['TA'] then);
  * ideal=dict(tr=ps) replaces the ring by ideal 8-phase sources at the ring's measured frequency (attribution rows);
  * edge_probe=True saves PS0..7 and the mux slice nodes XMUX.XS k.X (phase residual after trim).

    python3 chain14.py '{"tag":..., "top_ext":"net/pt_wiredtx8.full.rc.spice", ...}'
"""
import sys, json, hashlib
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 's13'))
import chain13 as C13
from chain13 import tools

C13.RUNS = HERE / 'runs'
RES = HERE / 'results'
TA = Path('/home/ubuntu/svalbard/scratch/pads-core/txr/models/tx_ta.spice')   # placeholder name; checked per row
if TA.exists():
    C13.PADFILE['TA'] = TA; C13.PADLABEL['TA'] = 'pad=optA'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest() if p and Path(p).exists() else None


_ideal = {}
_bypass = False
_ng = tools.ngspice_host


def _ngspice(w, d, timeout=40000):
    """optionally swap the ring for ideal phase sources before the run (data pass and phase pass alike)."""
    if _ideal:
        p = Path(w) / d; t = p.read_text().split('\n')
        f = _ideal['f']; T = 1 / f; tr = _ideal.get('tr', 60e-12); v = _ideal['v']
        keep = [l for l in t if not l.startswith(('.include ring.spice', 'VRGS ', 'VRGC ', 'RRGC ', 'IRGB ', 'VRGE ', 'XRG '))]
        src = [f'VIP{k} RG{k} 0 PULSE(0 {v} {1e-9 + k * T / 8:.6e} {tr} {tr} {T / 2 - tr:.6e} {T:.6e})' for k in range(8)]
        i = next(n for n, l in enumerate(keep) if l.startswith('RRT0'))
        p.write_text('\n'.join(keep[:i] + src + keep[i:]))
    if _bypass and (Path(w) / 'topx.spice').exists():      # diagnostic: run detector output forced to RUN
        tp = Path(w) / 'topx.spice'; tx = tp.read_text()
        node = 'XMUX.RUNB' if ' XMUX.RUNB' in tx else 'XMUX__RUNB'
        if 'VFRUNB' not in tx:
            i = tx.rfind('.ends'); tp.write_text(tx[:i] + f'VFRUNB {node} VSS 0\n' + tx[i:])
    return _ng(w, d, timeout=timeout)


def _save(out):
    out['net_sha256'] = sha(out.get('top_ext'))
    pm = {v: k for k, v in C13.PADLABEL.items()}.get(out.get('padm'))
    out['pad_sha256'] = sha(C13.PADFILE.get(pm))
    out['ideal_phases'] = dict(_ideal) or None
    out['ilk_bypass'] = _bypass       # True: XMUX.RUNB forced low (run detector bypassed, diagnostic)
    RES.mkdir(exist_ok=True)
    (RES / f'{out["tag"]}.json').write_text(json.dumps(out, indent=1, default=str))
    return out


C13._save = _save


def run(**kw):
    global _ideal, _bypass
    _ideal = kw.pop('ideal', None) or {}
    _bypass = bool(kw.pop('ilk_bypass', False))
    if _ideal:      # ideal phases at the frequency the real ring is tuned to (same rate as the ring row), swing = vring
        kw.setdefault('vring', 2.69)
        pess = kw.get('pess', False); rp = kw.get('ring_pess', pess); rate = kw.get('rate', 3.125e9); f = rate / 8
        tn = C13.tune(kw.get('corner', 'ss'), kw.get('temp', 32), kw['vring'], (1 if f > 480e6 else 0), f, rp)
        _ideal.update(f=tn['f_hz'], v=kw['vring'])
    if kw.pop('edge_probe', False):
        kw['probes'] = list(kw.get('probes', ())) + [f'XTOP.PS{k}' for k in range(8)] + [f'XTOP.XMUX.XS{k}.X' for k in range(8)]
    if kw.get('top_ext') and not Path(kw['top_ext']).is_absolute():
        kw['top_ext'] = str(HERE / kw['top_ext'])
    o = C13.run(**kw)
    return o


# chain13.run sets tools.ngspice itself; route its host call through the ideal-phase hook
tools.ngspice_host = _ngspice

if __name__ == '__main__':
    print(C13.summ(run(**json.loads(sys.argv[1]))), flush=True)
