#!/usr/bin/env python3
"""Check the actual buffer substitution, acquisition history, static error and current."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];P=ROOT/'projects/programmable_transceiver_platform';B=ROOT/'scratch/transceiver-adc-sar-acquisition'
parser=argparse.ArgumentParser();parser.add_argument('--longmirror',action='store_true');parser.add_argument('--headroom',action='store_true');args=parser.parse_args();assert not (args.longmirror and args.headroom);tag='sample-driver-headroom' if args.headroom else ('sample-driver-longmirror' if args.longmirror else 'sample-driver');W=ROOT/('scratch/transceiver-adc-'+tag)
r=json.loads((W/'result.json').read_text())
if args.headroom:
 original=(P/'analog/adc/sample_driver.spice').read_text()
 changed=(P/'analog/adc/sample_driver_headroom.spice').read_text().replace('pt_sample_driver_headroom','pt_sample_driver').replace('XOUT OUT X VSS VSS nfet_03v3 w=8u l=.5u m=8','XOUT OUT X VSS VSS nfet_03v3 w=8u l=.5u m=32')
 assert changed==original
 r['output_device_only_change_checked']=True
if args.longmirror:
 original=(P/'analog/adc/sample_driver.spice').read_text()
 changed=(P/'analog/adc/sample_driver_longmirror.spice').read_text().replace('pt_sample_driver_longmirror','pt_sample_driver')
 lines=changed.splitlines();changed='\n'.join(line.replace('l=2u m=16','l=.5u m=4') if line.startswith(('XMP ','XMN ')) else line for line in lines)+'\n'
 assert changed==original
 r['mirror_only_geometry_change_checked']=True
for path,digest in r['source_sha256'].items():
 actual=P/'analog'/path.removeprefix('/screen/') if path.startswith('/screen/') else ROOT/'ip/blocks/analog/wifi_80211b'/path.removeprefix('/wifi/')
 assert hashlib.sha256(actual.read_bytes()).hexdigest()==digest
assert len(r['cases'])==4
for c in r['cases']:
 base=(B/f"vin{c['input_difference_v']:g}_r1000_change{int(c['changing'])}.spice").read_text()
 assert hashlib.sha256(base.encode()).hexdigest()==c['baseline_deck_sha256']
 for suffix,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(c['name']+suffix)).read_bytes()).hexdigest()==digest
 d=(W/(c['name']+'.spice')).read_text()
 if args.headroom:d=d.replace('sample_driver_headroom.spice','sample_driver.spice').replace('pt_sample_driver_headroom','pt_sample_driver')
 if args.longmirror:d=d.replace('sample_driver_longmirror.spice','sample_driver.spice').replace('pt_sample_driver_longmirror','pt_sample_driver')
 extra='''.include /screen/adc/sample_driver.spice
VBUF VBUF 0 3.3
IBN VBUF BN 20u
IBP BP 0 20u
XBN BN BN 0 0 nfet_03v3 w=8u l=.5u
XBP BP BP VBUF VBUF pfet_03v3 w=8u l=.5u
XBPDRV GP IP BN BP VBUF 0 pt_sample_driver
XBNDRV GN IN BN BP VBUF 0 pt_sample_driver
'''
 assert extra in d
 reverse=d.replace(extra,'').replace('RIP SP GP 1000','RIP SP IP 1000').replace('RIN SN GN 1000','RIN SN IN 1000').replace(' v(IP) v(IN) v(GP) v(GN) i(VBUF) v(BN) v(BP)','').replace(f"/work/{c['name']}.dat",f"/work/vin{c['input_difference_v']:g}_r1000_change{int(c['changing'])}.dat")
 assert reverse==base

def read(c):
 a=np.loadtxt(W/(c['name']+'.dat'),skiprows=1);assert a.shape[1]==35 and np.isfinite(a).all() and a[-1,0]>=65e-9
 return a
pairs=[]
for c in r['cases']:
 if not c['changing']:continue
 control=next(x for x in r['cases'] if not x['changing'] and x['input_difference_v']==c['input_difference_v'])
 a,b=read(c),read(control);t=a[:,0];held=(t>=64e-9)&(t<=64.8e-9);track=(t>=59.8e-9)&(t<=59.9e-9);alltrack=(t>=50e-9)&(t<=60e-9)
 d=a[:,1]-a[:,2];reference=np.interp(t,b[:,0],b[:,1]-b[:,2]);bdriver=np.interp(t,b[:,0],b[:,28]-b[:,29]);bcurrent=np.interp(t,b[:,0],b[:,32])
 pairs.append(dict(input_difference_v=c['input_difference_v'],paired_held_acquisition_error_v=float(np.mean(d[held]-reference[held])),paired_tracking_error_v=float(np.mean((a[:,28]-a[:,29]-bdriver)[track])),constant_driver_differential_error_v=float(np.mean(bdriver[held])-c['input_difference_v']),constant_held_difference_v=float(np.mean(reference[held])),buffer_output_range_v=[float(a[:,28:30].min()),float(a[:,28:30].max())],quiescent_buffer_current_ma=float(-np.mean(bcurrent[held])*1e3),peak_buffer_current_ma=float(np.max(-a[alltrack,32])*1e3),late_buffer_ripple_pp_v=[float(np.ptp(a[held,col])) for col in (28,29)]))
r['paired_metrics']=pairs;r['buffer_only_substitution_checked']=True;r['driver_qualified']=False
(P/('evidence/adc-'+tag+'-screen.json')).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(pairs,indent=2))
