"""pt_lo_txbuf supply current: schematic, 2.45 GHz differential sine at the inputs (0.5 Vpp per leg, CM 2.5 V, as the
2.1 mm line delivers), each output into the txmix gate load (4 x nfet 10/0.28 + 22 fF). Average i(VDD) over 40 ns."""
import sys, json, shutil
from pathlib import Path
T = '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/timing'
sys.path.insert(0, T)
import timing_flow as tf
H = Path(__file__).resolve().parent
res = []
for c, temp, v in (('ff', 22, 3.5), ('ff', 125, 3.5), ('tt', 27, 3.3), ('ss', 32, 3.15)):
    wd = H / f'{c}_{temp}_{v}'; wd.mkdir(exist_ok=True)
    for f_ in ('lo_txbuf.spice', 'timing_cells.spice'):
        shutil.copy(Path(T) / f_, wd / f_)
    f = 2.45e9; q = 0.25 / f
    src = ''.join(f'V{n} {n} 0 sin(2.5 {s * 0.25} {f} {d} 0)\n' for n, s, d in (('ip', 1, 0), ('in', -1, 0), ('qp', 1, q), ('qn', -1, q)))
    loads = ''.join(f'XL{n} txd {n} txs 0 nfet_03v3 w=10u l=0.28u m=4\nCL{n} {n} 0 22f\n' for n in ('oip', 'oin', 'oqp', 'oqn'))
    mc = 'typical' if c == 'tt' else c
    d = tf.header(c, temp) + f'.lib {tf.MODELS}/sm141064.ngspice mimcap_{mc}\n' + f""".include lo_txbuf.spice
VDD vdd 0 {v}
VTXD txd 0 2.5
VTXS txs 0 1.0
{src}{loads}X1 ip in qp qn oip oin oqp oqn vdd 0 pt_lo_txbuf
.tran 2p 60n
.measure tran idd avg i(VDD) from=20n to=60n
.measure tran ipk min i(VDD) from=20n to=60n
.end
"""
    m = tf.ngspice(wd, 'i', d)
    r = dict(corner=c, temp=temp, vdd=v, idd_ma=-m['idd'] * 1e3 if 'idd' in m else None, peak_ma=-m['ipk'] * 1e3 if 'ipk' in m else None, errors=m['_errors'][:2])
    print(r, flush=True); res.append(r)
(H / 'result.json').write_text(json.dumps(res, indent=1))
