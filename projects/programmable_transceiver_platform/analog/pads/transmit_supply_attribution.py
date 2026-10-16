"""Partition retained TX supply current with ideal zero-volt branch probes."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from screen import run_spice,control


def run(work,fixture,stop_ns=220.):
    if stop_ns < 220:raise ValueError("Must retain the complete original lifecycle")
    work.mkdir(parents=True,exist_ok=False);text=fixture.read_text();deck=text.split('.control')[0]
    replacements={'Xpad PAD_P PAD_N VDD VSS ':'Xpad PAD_P PAD_N PAD_VDD VSS ',
                  'XBUF VDD VSS ':'XBUF BUF_VDD VSS ',
                  'RREF1 VDD BUF_REF ':'RREF1 BIAS_VDD BUF_REF ',
                  'RBIAS1 VDD BUF_BIAS ':'RBIAS1 BIAS_VDD BUF_BIAS '}
    for old,new in replacements.items():
        if deck.count(old)!=1:raise ValueError('Unexpected supply topology: '+old)
        deck=deck.replace(old,new)
    deck+='VSENSE_PAD VDD PAD_VDD 0\nVSENSE_BUF VDD BUF_VDD 0\nVSENSE_BIAS VDD BIAS_VDD 0\n'
    vectors='v(TERM_VCM) i(VDD) i(VSENSE_PAD) i(VSENSE_BUF) i(VSENSE_BIAS) v(BUF_ENABLE) v(xbuf.ENABLE_B) v(xbuf.GAIN) v(xbuf.TOP) v(xbuf.BOTTOM) v(xbuf.LOCAL_OUT)'
    deck+=control(work,'supply',f'tran 5p {stop_ns:g}n',vectors)
    x=run_spice(work,'supply',deck)
    if not np.isfinite(x).all() or x[-1,0]<(stop_ns-.01)*1e-9:raise ValueError('Incomplete supply diagnostic')
    residual=float(np.max(abs(x[:,2]+x[:,3]+x[:,4]+x[:,5])))
    if residual>1e-6:raise ValueError('Supply partition does not close KCL')
    windows={}
    labels=['vcm_v','total_source_current_a','pad_draw_a','buffer_draw_a','bias_draw_a','enable_v','enable_b_v','gain_v','top_v','bottom_v','local_out_v']
    intervals=[('reset',27,30),('unpowered',36,43),('main_settled',140,147),('post_settled',184,191),('release',196,199),('after_disable',204,210),('late_disabled',214,219)]
    if stop_ns>230:intervals.append(('extended_disabled',stop_ns-10,stop_ns-1))
    for name,start,end in intervals:
        z=x[(x[:,0]>=start*1e-9)&(x[:,0]<=end*1e-9)]
        windows[name]={label:{'min':float(z[:,i].min()),'max':float(z[:,i].max()),'mean':float(np.trapezoid(z[:,i],z[:,0])/(z[-1,0]-z[0,0]))} for i,label in enumerate(labels,1)}
    reference=fixture.with_suffix('.dat');comparison=None
    if reference.exists():
        y=np.loadtxt(reference,skiprows=1)
        overlap=x[(x[:,0]>=y[0,0])&(x[:,0]<=y[-1,0])]
        expected=np.interp(overlap[:,0],y[:,0],y[:,5])
        comparison={'maximum_vcm_difference_v':float(abs(overlap[:,1]-expected).max()),'scope':'Linear interpolation over overlapping baseline/probed time range only; no baseline waveforms modified.'}
    r={'status':'retained_TX_supply_current_partition','stop_ns':stop_ns,'windows':windows,'maximum_supply_kcl_residual_a':residual,'unprobed_comparison':comparison,'scope':'Zero-volt probes partition pad, buffer and external prototype bias divider supply. Same circuit, controls and external network. Behavioral control-source energy is not included; no reliability or current-capacity verdict.','source_sha256':{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),fixture,work/'supply.spice']}}
    (work/'screen.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('output-dir','fixture'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--stop-ns',type=float,default=220.)
    a=p.parse_args();run(a.output_dir.resolve(),a.fixture.resolve(),a.stop_ns)
