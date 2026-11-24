import sys; from pathlib import Path
T='/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/timing'
sys.path.insert(0,T); sys.path.insert(0,T+'/lcvco')
import timing_flow as tf, run_loop as rl
for view in ('sch','ext'):
    wd=Path(view).resolve(); wd.mkdir(exist_ok=True)
    if view=='ext': (wd/'b.spice').write_text(Path(T,'generated/lo_txbuf.ext.spice').read_text()); inc='.include b.spice\n'
    else:
        for f in ('lo_txbuf.spice','timing_cells.spice'): (wd/f).write_text(Path(T,f).read_text())
        inc='.include lo_txbuf.spice\n'
    deck=rl.header('tt',27)+inc+"""VDD vdd 0 3.3
VIP ip 0 SIN(2.5 0.25 2.4G)
VIN in 0 SIN(2.5 -0.25 2.4G)
VQP qp 0 SIN(2.5 0.25 2.4G 104p)
VQN qn 0 SIN(2.5 -0.25 2.4G 104p)
XB ip in qp qn oip oin oqp oqn vdd 0 pt_lo_txbuf
C1 oip 0 60f
C2 oin 0 60f
C3 oqp 0 60f
C4 oqn 0 60f
.tran 2p 20n
.measure tran omax max v(oip) from=15n to=20n
.measure tran omin min v(oip) from=15n to=20n
.measure tran idd avg i(VDD) from=15n to=20n
.end
"""
    m=tf.ngspice(wd,'t',deck,timeout=3000)
    print(view,{k:m.get(k) for k in ('omax','omin','idd')},m['_errors'][:3])
