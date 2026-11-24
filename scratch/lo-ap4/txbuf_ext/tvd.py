import sys; from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
T='/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/timing'
sys.path.insert(0,T); sys.path.insert(0,T+'/lcvco')
import timing_flow as tf, run_loop as rl
SRC=sys.argv[1]; TAG=sys.argv[2]
def one(c):
    corner,temp,v,amp=c
    wd=Path('tv',TAG,f'{corner}_{v}_{amp}').resolve(); wd.mkdir(parents=True,exist_ok=True)
    (wd/'b.spice').write_text(Path(SRC).read_text())
    deck=rl.header(corner,temp)+'.include b.spice\n'+f"""VDD vdd 0 {v}
VIP ip 0 SIN(2.5 {amp} 2.4G)
VIN in 0 SIN(2.5 -{amp} 2.4G)
VQP qp 0 SIN(2.5 {amp} 2.4G 104p)
VQN qn 0 SIN(2.5 -{amp} 2.4G 104p)
EZI zi 0 oip oin 1
EZQ zq 0 oqp oqn 1
XB ip in qp qn oip oin oqp oqn vdd 0 pt_lo_txbuf
XTip vdd oip vdd 0 nfet_03v3 w=10u l=0.28u m=4
XTin vdd oin vdd 0 nfet_03v3 w=10u l=0.28u m=4
XTqp vdd oqp vdd 0 nfet_03v3 w=10u l=0.28u m=4
XTqn vdd oqn vdd 0 nfet_03v3 w=10u l=0.28u m=4
C1 oip 0 30f
C2 oin 0 30f
C3 oqp 0 30f
C4 oqn 0 30f
.tran 2p 20n
.measure tran omax max v(oip) from=15n to=20n
.measure tran omin min v(oip) from=15n to=20n
.measure tran oqmax max v(oqn) from=15n to=20n
.measure tran oqmin min v(oqn) from=15n to=20n
.measure tran r1 when v(zi)=0 rise=30
.measure tran f1 when v(zi)=0 fall=30
.measure tran r2 when v(zi)=0 rise=31
.measure tran q1 when v(zq)=0 rise=30
.measure tran idd avg i(VDD) from=15n to=20n
.end
"""
    m=tf.ngspice(wd,'t',deck,timeout=3000)
    return c,{k:m.get(k) for k in ('omin','omax','oqmin','oqmax','r1','f1','r2','q1','idd')},m['_errors'][:2]
C=[('typical',27,3.3,0.25),('ss',32,3.15,0.17),('ff',22,3.5,0.2)]
with ThreadPoolExecutor(3) as ex:
    for r in ex.map(one,C): print(TAG,r)
