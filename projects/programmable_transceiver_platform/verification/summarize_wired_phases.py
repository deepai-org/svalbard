#!/usr/bin/env python3
"""Bind four phase points and retain raw stage observations for the new runs."""
import hashlib
import json
from pathlib import Path
import re
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
PROJECT=ROOT/'projects/programmable_transceiver_platform'
BASE=ROOT/'scratch/transceiver-wired-pulse-data-gf180'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
oldpath=PROJECT/'evidence/wired-phase-screen.json'
old=json.loads(oldpath.read_text())
base_deck=(BASE/'changing.spice').read_text()
def canonical(text):
    text=re.sub(r'^VRX[PN] .*$', '', text, flags=re.M)
    text=text.replace('/baseline/pex/','/work/pex/')
    return text.replace(' isupply v(RXOP) v(RXON)',' isupply')
rows=[]; sources={str(oldpath.relative_to(ROOT)):sha(oldpath)}
for ps in (0,-100,-200,-300):
    if ps in (0,-100):
        r=old; item=r['baseline' if ps==0 else 'shifted']
        folder=BASE if ps==0 else ROOT/'scratch/transceiver-wired-phase'
        deck_hash=r['source_sha256']['baseline_deck' if ps==0 else 'shifted_deck']
    else:
        folder=ROOT/f'scratch/transceiver-wired-phase{ps}ps'
        path=folder/'result.json'; r=json.loads(path.read_text()); item=r['shifted']
        sources[str(path.relative_to(ROOT))]=sha(path)
        deck_hash=r['source_sha256']['shifted_deck']
    assert item['data_phase_ps']==ps
    assert r['environment']==old['environment']
    assert all(r['source_sha256'][k]==old['source_sha256'][k] for k in ('pulse','bridge','lane','baseline_deck'))
    assert sha(folder/'changing.spice')==deck_hash
    assert sha(folder/'changing.dat')==item['waveform_sha256']
    assert canonical((folder/'changing.spice').read_text())==canonical(base_deck)
    # A fixed-delay fit must not skip or duplicate bits as clock drift moves
    # samples across source boundaries. Require a real consecutive stream.
    valid=[]
    for candidate in item['latency_scan']:
        stream=[]
        for branch,d in item['branches'].items():
            ids=candidate['branches'][branch]['bit_indices'] if 'bit_indices' in candidate['branches'][branch] else candidate['branches'][branch]['expected_bit_indices']
            stream.extend(zip(d['sample_times_s'],ids))
        ordered=[bit for _,bit in sorted(stream)]
        if all(b==a+1 for a,b in zip(ordered,ordered[1:])):
            valid.append(candidate)
    assert valid, 'No consistent consecutive-bit association'
    best=min(valid,key=lambda c:(c['below_500mv'],c['wrong_polarity'],-c['minimum_signed_v']))
    row=dict(phase_ps=ps,best=best,unconstrained_best=item['best'],
             valid_mapping_count=len(valid),rejected_mapping_count=len(item['latency_scan'])-len(valid),current_a=item['current_a'],
             scored_samples=sum(len(d['sample_times_s']) for d in item['branches'].values()),
             waveform_sha256=item['waveform_sha256'])
    if ps<=-200:
        x=np.loadtxt(folder/'changing.dat',skiprows=1); assert x.shape[1]==16
        observations=[]
        for bit in (20,30):
            start=1e-9+bit*400e-12+ps*1e-12
            for delta_ps in (100,200,300,400,600,800,1200):
                time=start+delta_ps*1e-12
                at=lambda col:float(np.interp(time,x[:,0],x[:,col]))
                observations.append(dict(bit=bit,offset_ps=delta_ps,time_s=time,
                    pin_diff_v=at(1)-at(2),raw_rx_diff_v=at(14)-at(15),
                    even_converter_diff_v=at(9)-at(10),even_sense_v=at(3),
                    even_capture_clock_v=at(5),even_output_diff_v=at(7)))
        row['stage_observations']=observations
    rows.append(row)
result=dict(status='coarse_phase_diagnostic_not_lane_qualification',environment=old['environment'],
    cases=rows,source_sha256=sources,analysis_source_sha256=sha(Path(__file__)),
    zero_error_points=[r['phase_ps'] for r in rows if r['best']['below_500mv']==0],
    limitations=['Fixed 40-bit pattern, about 25 scored outputs per point',
                 'Retrospective shared latency search, not hardware calibration',
                 'Four discrete phases do not establish a continuous timing aperture',
                 'Ideal upstream clocks, pin data, biases and supplies; no channel or TX',
                 'No process/mismatch/noise or frequency-offset coverage'])
(PROJECT/'evidence/wired-coarse-phase-screen.json').write_text(json.dumps(result,indent=2)+'\n')
for r in rows:
    print(r['phase_ps'],r['scored_samples'],r['best']['wrong_polarity'],r['best']['minimum_signed_v'],r['current_a'])
