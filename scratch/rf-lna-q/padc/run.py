"""PC-81b: rf_pair +0.28 pF per leg on the RX side. lna_close.band rows (rext, carrier fitted per chip at 2 mm), baseline vs +0.28 pF
added to tb.PAD_RF_PAIR_DC_F (on top of the 0.5 pF allowance + 42/53 fF already in the bench). Same bench, delta is the result."""
import os, sys, json
os.environ['RFRX_LNA_SRC'] = 'rext'
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/rf_rx')
import lna_close as C, tb
from pathlib import Path
base = tb.PAD_RF_PAIR_DC_F
src = Path(C.__file__).read_text()
rows = {}
for tag, extra in (('base', 0.), ('plus280f', 0.28e-12)):
    tb.PAD_RF_PAIR_DC_F = (base[0] + extra, base[1] + extra)
    C.OUT = Path(__file__).parent / tag
    jobs = [('extpr', C.NOM, 2.), ('extpr', C.SS, 2.), ('extpr', C.FF, 2.), ('extpp', C.SS, 2.)]
    # reuse band()'s per-row function by running band on a reduced job list
    import types
    code = src.split('def band():')[1].split('\n\n\n')[0]
    ns = dict(C.__dict__)
    exec('def band():' + code.replace("    jobs = [('extpr', (p, t, v), 2.) for p in PROCS for t, v in ((32, 3.15), (22, 3.35))]\n", "    jobs = JOBS\n").replace(
        "    jobs += [('extpr', NOM, 2.), ('extpr', NOM, 10.), ('extpp', SS, 2.), ('extpp', SS, 10.), ('extpp', ('typical', 32, 3.15), 2.), ('extlo', ('ff', 22, 3.35), 2.)]\n", ""), ns)
    ns['JOBS'] = jobs; ns['OUT'] = C.OUT
    ns['band']()
    rows[tag] = json.loads((C.OUT / 'band.json').read_text())
for a, b in zip(rows['base'], rows['plus280f']):
    print(a['view'], a['corner'], 'S11 %.2f -> %.2f' % (a['s11_worst_db'], b['s11_worst_db']), 'NF', a['nf_db'], '->', b['nf_db'], 'gain', a['gain_db'], '->', b['gain_db'])
json.dump(rows, open(Path(__file__).parent / 'result.json', 'w'), indent=1, default=str)
