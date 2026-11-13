"""rxmix passive quad conversion (current into ideal TIA virtual grounds at VDD/2) for the LO the rf_rx
benches assume (0/VDD square) vs the LO pt_lo_ext actually delivers (sine about VB=0.739 VDD)."""
import subprocess, math, sys
P='/home/ubuntu/svalbard/scratch/digital-closure/frozen-pdk/gf180mcuD/libs.tech/ngspice'
FLO=2.4e9; FIF=50e6; VDD=3.3
def deck(lo, corner='typical'):
    per=1/FLO
    if lo=='square':
        l=(f'Vlp lo_p 0 PULSE(0 {VDD} 0 20p 20p {per/2-20e-12} {per})\nVln lo_n 0 PULSE({VDD} 0 0 20p 20p {per/2-20e-12} {per})\n')
    else:
        vb,a=lo
        l=(f'Vlp lo_p 0 SIN({vb} {a} {FLO})\nVln lo_n 0 SIN({vb} {-a} {FLO})\n')
    return f"""* quad
.include {P}/design.ngspice
.lib {P}/sm141064.ngspice {corner}
.option temp=27 reltol=1e-4
Vs s 0 SIN(0 0.01 {FLO+FIF})
Ep sp 0 s 0 0.5
En sn 0 s 0 -0.5
Rsp sp rp 300
Rsn sn rn 300
Ccp rp rf_p 4p
Ccn rn rf_n 4p
{l}
Vxp x_p 0 {VDD/2}
Vxn x_n 0 {VDD/2}
"""+''.join(f'M{i} {a} {g} {b} 0 nfet_03v3 w=5u l=0.28u m=6\n' for i,(a,g,b) in enumerate([('rf_p','lo_p','x_p'),('rf_n','lo_p','x_n'),('rf_p','lo_n','x_n'),('rf_n','lo_n','x_p')]))+f"""
.tran 5p 100n 20n 5p
.control
run
linearize i(Vxp) i(Vxn)
wrdata out.dat i(Vxp)-i(Vxn)
.endc
.end
"""
def tone(path,f):
    t=[];v=[]
    for line in open(path):
        p=line.split()
        if len(p)>=2:
            t.append(float(p[0]));v.append(float(p[1]))
    n=len(t); c=sum(v[i]*math.cos(2*math.pi*f*t[i]) for i in range(n))*2/n; s=sum(v[i]*math.sin(2*math.pi*f*t[i]) for i in range(n))*2/n
    return math.hypot(c,s)
cases=[('square 0/VDD (rf_rx benches)','square'),
       ('sine VB=2.44 on-Vgs 1.16 (best ext window / tt)',(2.44,0.37)),
       ('sine VB=2.44 on-Vgs 1.05 (CML int / ext 4 Vpp ss)',(2.44,0.26)),
       ('sine VB=2.44 on-Vgs 0.90 (criterion floor)',(2.44,0.11)),
       ('sine 1.65+-1.65 (rail-to-rail sine, reference)',(1.65,1.65))]
ref=None
for name,lo in cases:
    open('mix.cir','w').write(deck(lo))
    subprocess.run(['ngspice','-b','mix.cir'],capture_output=True,timeout=900)
    a=tone('out.dat',FIF)
    g=a/0.01   # A/V differential conversion transconductance (source 300 ohm/leg)
    if ref is None: ref=g
    print(f'{name:55s} Iif/Vrf = {g*1e3:7.4f} mS  rel {20*math.log10(g/ref):+6.1f} dB',flush=True)
