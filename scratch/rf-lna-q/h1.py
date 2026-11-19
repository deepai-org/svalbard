"""H1 (round 3): band rows (S11 / gain / NF on the real channel, per-chip carrier fit) on the new layout, C-only (ext) vs metal-aware (rext).
usage: RFRX_LNA_SRC=ext|rext python3 h1.py"""
import os, sys, json
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/rf_rx')
from pathlib import Path
import lna_close as L
src = os.environ.get('RFRX_LNA_SRC', 'ext')
L.OUT = Path('/home/ubuntu/svalbard/scratch/rf_rx/r3') / src
jobs = [('extpr', L.NOM, 2.), ('extpr', L.FF, 2.), ('extpr', L.SS, 2.), ('extpp', L.SS, 2.)]
import types
rows = []
def one(j):
    try: return L.band.__code__ and None
    except Exception: pass
# reuse band()'s inner function by running band with a patched job list
src_code = L.band
L.PROCS_SAVE = L.PROCS
import inspect
code = inspect.getsource(L.band).replace("    jobs = [('extpr', (p, t, v), 2.) for p in PROCS for t, v in ((32, 3.15), (22, 3.35))]\n", "    jobs = JOBS\n").replace(
    "    jobs += [('extpr', NOM, 2.), ('extpr', NOM, 10.), ('extpp', SS, 2.), ('extpp', SS, 10.), ('extpp', ('typical', 32, 3.15), 2.), ('extlo', ('ff', 22, 3.35), 2.)]\n", "")
ns = dict(vars(L)); ns['JOBS'] = jobs; exec(code, ns); ns['band']()
print(json.dumps([{k: r[k] for k in ('view', 'corner', 'zpad_ohm', 's11_worst_db', 'gain_db', 'nf_db', 'nf_own_ideal_match_db', 'gain_ideal_lossless_match_db')} for r in json.loads((L.OUT / 'band.json').read_text())], indent=0))
