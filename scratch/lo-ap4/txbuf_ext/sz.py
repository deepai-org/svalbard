import sys; from pathlib import Path
T='/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/timing'
sys.path.insert(0,T); sys.path.insert(0,T+'/lcvco')
import timing_flow as tf, run_loop as rl
from concurrent.futures import ThreadPoolExecutor
def leg(n1,n2,n3,n4,R,cw):
    return f"""XC inp a cap_mim_2f0_m4m5_noshield c_width=7u c_length=7u
XR a b VSS ppolyf_u_1k r_width=1u r_length={R}u
XP1 b a VDD VDD pfet_03v3 w={2*n1}u l=0.28u
XN1 b a VSS VSS nfet_03v3 w={n1}u l=0.28u
XP2 c b VDD VDD pfet_03v3 w={2*n2}u l=0.28u
XN2 c b VSS VSS nfet_03v3 w={n2}u l=0.28u
XP3 d c VDD VDD pfet_03v3 w={2*n3}u l=0.28u
XN3 d c VSS VSS nfet_03v3 w={n3}u l=0.28u
XP4 out d VDD VDD pfet_03v3 w={2*n4}u l=0.28u
XN4 out d VSS VSS nfet_03v3 w={n4}u l=0.28u
Ca a 0 {cw[0]}f
Cb b 0 {cw[1]}f
Cc c 0 {cw[2]}f
Cd d 0 {cw[3]}f
Co out 0 {cw[4]}f
"""
def run(tag,corner,temp,v,amp,sz,cw):
    wd=Path('sz',tag+corner).resolve(); wd.mkdir(parents=True,exist_ok=True)
    deck=rl.header(corner,temp)+f"""VDD VDD 0 {v}
VSS VSS 0 0
VIP inp 0 SIN(2.5 {amp} 2.4G)
.subckt L inp out VDD VSS
{leg(*sz,cw)}.ends
X1 inp out VDD VSS L
CL out 0 60f
.tran 2p 20n
.measure tran omax max v(out) from=15n to=20n
.measure tran omin min v(out) from=15n to=20n
.measure tran idd avg i(VDD) from=15n to=20n
.end
"""
    m=tf.ngspice(wd,'t',deck,timeout=3000)
    return tag,corner,amp,{k:m.get(k) for k in ('omax','omin','idd')}
W=[8,36,28,25,25]
jobs=[('base0','typical',27,3.3,0.25,(4,6,12,24,40),[0]*5),('baseW','typical',27,3.3,0.25,(4,6,12,24,40),W),
      ('x2W','typical',27,3.3,0.25,(8,12,24,24,40),[10,45,35,30,25]),('x2Wss','ss',32,3.15,0.17,(8,12,24,24,40),[10,45,35,30,25]),
      ('x3W','ss',32,3.15,0.17,(12,16,24,32,30),[12,50,40,35,30]),('baseWss','ss',32,3.15,0.17,(4,6,12,24,40),W)]
with ThreadPoolExecutor(3) as ex:
    for r in ex.map(lambda j: run(*j), jobs): print(r)
