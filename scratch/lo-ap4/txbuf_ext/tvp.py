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
.tran 2p 100n
.measure tran omax max v(oip) from=55n to=60n
.measure tran omin min v(oip) from=55n to=60n
.measure tran oqmax max v(oqn) from=55n to=60n
.measure tran oqmin min v(oqn) from=55n to=60n
.measure tran ri1 when v(zi)=0 rise=1 td=80n
.measure tran rq1 when v(zq)=0 rise=1 td=80n
.measure tran fi1 when v(zi)=0 fall=1 td=80n
.measure tran ri2 when v(zi)=0 rise=2 td=80n
.measure tran rq2 when v(zq)=0 rise=2 td=80n
.measure tran fi2 when v(zi)=0 fall=2 td=80n
.measure tran ri3 when v(zi)=0 rise=3 td=80n
.measure tran rq3 when v(zq)=0 rise=3 td=80n
.measure tran fi3 when v(zi)=0 fall=3 td=80n
.measure tran ri4 when v(zi)=0 rise=4 td=80n
.measure tran rq4 when v(zq)=0 rise=4 td=80n
.measure tran fi4 when v(zi)=0 fall=4 td=80n
.measure tran ri5 when v(zi)=0 rise=5 td=80n
.measure tran rq5 when v(zq)=0 rise=5 td=80n
.measure tran fi5 when v(zi)=0 fall=5 td=80n
.measure tran ri6 when v(zi)=0 rise=6 td=80n
.measure tran rq6 when v(zq)=0 rise=6 td=80n
.measure tran fi6 when v(zi)=0 fall=6 td=80n
.measure tran ri7 when v(zi)=0 rise=7 td=80n
.measure tran rq7 when v(zq)=0 rise=7 td=80n
.measure tran fi7 when v(zi)=0 fall=7 td=80n
.measure tran ri8 when v(zi)=0 rise=8 td=80n
.measure tran rq8 when v(zq)=0 rise=8 td=80n
.measure tran fi8 when v(zi)=0 fall=8 td=80n
.measure tran r1 when v(zi)=0 rise=2 td=55n
.measure tran f1 when v(zi)=0 fall=2 td=55n
.measure tran r2 when v(zi)=0 rise=3 td=55n
.measure tran q1 when v(zq)=0 rise=2 td=55n
.measure tran idd avg i(VDD) from=55n to=60n
.end
"""
    m=tf.ngspice(wd,'t',deck,timeout=3000)
    return c,{k:m.get(k) for k in tuple(['idd']+[f'{a}{k}' for a in ('ri','rq','fi') for k in range(1,9)])},m['_errors'][:2]
C=[(c,t,v,a) for (c,t,v) in (('typical',27,3.3),('ss',32,3.15),('ff',22,3.5)) for a in (0.1,0.17,0.25)]
with ThreadPoolExecutor(3) as ex:
    for r in ex.map(one,C): print(TAG,r)
