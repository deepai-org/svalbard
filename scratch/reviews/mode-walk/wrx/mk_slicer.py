#!/usr/bin/env python3
"""Slicer extracted, quarter rate, per-UI pattern 1100 (D0=D1=1, D2=D3=0), polarity flipped half way. args: tag corner vdd cm f_ring vd"""
import re,sys
tag,corner,vdd,cm,f,vd=sys.argv[1],sys.argv[2],float(sys.argv[3]),float(sys.argv[4]),float(sys.argv[5]),float(sys.argv[6])
PD='/home/ubuntu/svalbard/scratch/digital-closure/frozen-pdk/gf180mcuD/libs.tech/ngspice'
W='/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_rx/generated'
SRC=(W+'/slicer.ext.spice') if len(sys.argv)<8 else sys.argv[7]
t=re.sub(r'\n\+\s*',' ',open(SRC).read())
ports=re.search(r'^\.subckt\s+pt_slicer\s+(.*)$',t,re.M).group(1).split()
T=1/f; ui=T/4; N=8; t0=1e-9; ap=100e-12
m=dict(VDD_WIRE_SW='vdd',VSS='0',slicer_en='vdd',SL_P='inp',SL_N='inn',QCK='qck',D0='d0',E0='e0',D1='d1',E1='e1',D2='d2',E2='e2',D3='d3',E3='e3',VTAP='vt',VTAN='vt',VTBP='vt',VTBN='vt')
m.update({f'CKP{k}':f'ck{k}' for k in range(8)})
L=[f'* slicer {tag}',f'.include {PD}/design.ngspice',f'.lib {PD}/sm141064.ngspice {corner}',f'.lib {PD}/sm141064.ngspice res_{corner}',f'.lib {PD}/sm141064.ngspice diode_{corner}',
   '.option temp=32 gmin=1e-12 reltol=1e-3',f'.include {SRC}',f'VDD vdd 0 {vdd}','VT vt 0 0.8']
tr=T/40
for k in range(8): L.append(f'VCK{k} ck{k} 0 PULSE(0 {vdd} {t0+k*T/8:.5e} {tr:.3e} {tr:.3e} {T/2-tr:.5e} {T:.5e})')
pp=[(0,cm)];pn=[(0,cm)]
def bit(n): # per-UI bit index n -> value
    cyc=n//4; b=1 if (n%4)<2 else 0
    return b if cyc<N//2 else 1-b
for n in range(4*N):
    ts=t0+ap+(n-0.5)*ui; v=vd/2 if bit(n) else -vd/2
    pp+=[(ts,pp[-1][1]),(ts+30e-12,cm+v)]; pn+=[(ts,pn[-1][1]),(ts+30e-12,cm-v)]
pw=lambda p:'PWL('+' '.join(f'{a:.5e} {b:.4f}' for a,b in p)+')'
L+=[f'VIP inp 0 {pw(pp)}',f'VIN inn 0 {pw(pn)}','X1 '+' '.join(m.get(p,'0') for p in ports)+' pt_slicer']
c=['.control',f'tran {T/200:.3e} {t0+N*T:.4e}']
# windows: skip 3 cycles after start and after flip
a1,b1=t0+2*T,t0+(N//2)*T; a2,b2=t0+(N//2+2)*T,t0+N*T
for s in ('d0','d1','d2','d3','e0','e1','e2','e3'):
    c+=[f'meas tran {s}_h1 avg v({s}) from={a1:.4e} to={b1:.4e}',f'meas tran {s}_h2 avg v({s}) from={a2:.4e} to={b2:.4e}']
c+=[f'meas tran idd avg i(VDD) from={a1:.4e} to={b2:.4e}','.endc','.end']
open(f'sl_{tag}.cir','w').write('\n'.join(L+c)+'\n')
