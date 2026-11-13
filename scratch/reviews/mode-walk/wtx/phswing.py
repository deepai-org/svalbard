#!/usr/bin/env python3
"""Reviewer check: pt_wiredtx phase-input stage (wtx_qph) driven by ring phases whose high level is the
pt_pll_vreg output (0.9 x rail, 2.57-3.01 V) instead of the full wired rail the block benches use."""
import subprocess, sys, re
P='/home/ubuntu/svalbard/projects/programmable_transceiver_platform'
M='/home/ubuntu/svalbard/scratch/transceiver-pad-pdk/ngspice'
NG='/home/ubuntu/svalbard/scratch/pad-ngspice47/ngspice-47/src/ngspice'
def run(corner,temp,vdd,vph,f=625e6):
    T=1/f
    deck=f"""* phase swing check
.include {M}/design.ngspice
.lib {M}/sm141064.ngspice {corner}
.temp {temp}
.include {P}/analog/wired_tx/wiredtx.spice
VDD VDD 0 {vdd}
VS SERQ 0 {vdd}
BPH PHS 0 V={vph}*(0.5+0.5*tanh(sin(6.283185307*{f}*time)*4))
RPH PHS PH 150
XQ PH SERQ VDD 0 0 0 0 G XN0 XN1 XN2 QW Q VDD 0 wtx_qph
CG G 0 30f
CQW QW 0 60f
CQ Q 0 60f
CX0 XN0 0 20f
CX1 XN1 0 20f
CX2 XN2 0 20f
.tran 5p {12*T} {4*T}
.control
run
meas tran thi trig v(QW) val={vdd/2} rise=2 targ v(QW) val={vdd/2} fall=2
meas tran per trig v(QW) val={vdd/2} rise=2 targ v(QW) val={vdd/2} rise=3
meas tran tpdr trig v(PHS) val={vph/2} rise=3 targ v(QW) val={vdd/2} cross=5
meas tran idd avg i(VDD) from={4*T} to={12*T}
meas tran qmax max v(QW) from={4*T} to={12*T}
meas tran qmin min v(QW) from={4*T} to={12*T}
.endc
.end
"""
    open('phswing.cir','w').write(deck)
    r=subprocess.run([NG,'-b','phswing.cir'],capture_output=True,text=True,timeout=300)
    out=r.stdout+r.stderr
    g=lambda k:(re.search(rf'^{k}\s*=\s*(\S+)',out,re.M) or [None,None])[1]
    try: duty=float(g('thi'))/float(g('per'))
    except Exception: duty=None
    return dict(corner=corner,temp=temp,vdd=vdd,vph=vph,duty_QW=duty,idd_avg=g('idd'),qmax=g('qmax'),qmin=g('qmin'),err=out[-300:] if duty is None else '')
import json
res=[]
for c,t,vdd in (('typical',27,3.3),('ff',22,3.35),('ss',32,3.15),('fs',22,3.35),('sf',32,3.35)):
    for vph in (vdd, 0.9*vdd, vdd-0.5, 2.57):
        res.append(run(c,t,vdd,round(vph,3))); print(res[-1],flush=True)
json.dump(res,open('phswing.json','w'),indent=1)
