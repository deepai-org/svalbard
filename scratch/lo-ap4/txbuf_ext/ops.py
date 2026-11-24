import sys; from pathlib import Path
T='/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/timing'
sys.path.insert(0,T); sys.path.insert(0,T+'/lcvco')
import timing_flow as tf, run_loop as rl
wd=Path('ops').resolve(); wd.mkdir(exist_ok=True)
[(wd/f).write_text(Path(T,f).read_text()) for f in ('lo_txbuf.spice','timing_cells.spice')]
nodes=['m1_1372_462#','m1_5604_634#','m1_13074_1878#','m1_18098_3078#','oip']
deck=rl.header('tt',27)+'.include lo_txbuf.spice\n'+"""VDD vdd 0 3.3
VIP ip 0 2.5
VIN in 0 2.5
VQP qp 0 2.5
VQN qn 0 2.5
XB ip in qp qn oip oin oqp oqn vdd 0 pt_lo_txbuf
.control
op
print v(xb.xi.ap) v(xb.xi.bp) v(xb.xi.cp) v(xb.xi.dp) v(oip) i(vdd)
.endc
.end
"""
(wd/'o.spice').write_text(deck)
import subprocess
print(tf.ngspice(wd,'o',deck,timeout=600))
