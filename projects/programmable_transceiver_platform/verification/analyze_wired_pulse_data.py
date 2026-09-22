#!/usr/bin/env python3
"""Diagnostic polarity and common-latency search; never a lane qualification gate."""
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'scratch/transceiver-wired-pulse-data-gf180'
report=json.loads((WORK/'result.json').read_text())
by_name={c['id']:c for c in report['cases']}
for case in report['cases']:
    wave=WORK/(case['id']+'.dat')
    assert hashlib.sha256(wave.read_bytes()).hexdigest()==case['waveform_sha256']
    assert hashlib.sha256((WORK/(case['id']+'.spice')).read_bytes()).hexdigest()==case['deck_sha256']
static={}
for name,sign in [('static_positive',1),('static_negative',-1)]:
    static[name]={branch: min(sign*v for v in d['differential_output_v'])
                  for branch,d in by_name[name]['branches'].items()}
rows=[]
for delay_ps in range(0,2401,25):
    margins=[]; detail={}
    for branch,d in by_name['changing']['branches'].items():
        indices=[int(np.floor((t-delay_ps*1e-12-1e-9)/400e-12)) for t in d['sample_times_s']]
        assert all(0<=i<len(report['stimulus_bits']) for i in indices)
        signed=[v*(2*report['stimulus_bits'][i]-1) for i,v in zip(indices,d['differential_output_v'])]
        detail[branch]=dict(expected_bit_indices=indices,wrong_polarity=sum(v<=0 for v in signed),
                           below_500mv=sum(v<.5 for v in signed),minimum_signed_v=min(signed))
        margins.extend(signed)
    rows.append(dict(delay_ps=delay_ps,wrong_polarity=sum(v<=0 for v in margins),
                     below_500mv=sum(v<.5 for v in margins),minimum_signed_v=min(margins),branches=detail))
best=min(rows,key=lambda r:(r['below_500mv'],r['wrong_polarity'],-r['minimum_signed_v']))
report['analysis']=dict(
    static_signed_minimum_v=static,
    static_both_polarities_above_500mv=all(v>=.5 for d in static.values() for v in d.values()),
    changing_samples=sum(len(d['sample_times_s']) for d in by_name['changing']['branches'].values()),
    best_common_latency_diagnostic=best,
    latency_scan=rows,
    interpretation='Exploratory shared delay 0..2400 ps in 25 ps increments, fixed noninverting polarity, samples 100 ps after actual capture fall. No per-bit or per-branch latency fitting. Best fit does not establish timing aperture, acquisition, BER, or correct operation for other patterns.')
report['analysis_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
report['reproduction']='make transceiver-wired-pulse-data; python3 projects/programmable_transceiver_platform/verification/analyze_wired_pulse_data.py'
report['container_image_id']='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'
report['physical_records']={
    'pulse':json.loads((WORK/'pulse-physical.json').read_text()),
    'bridge':json.loads((ROOT/'ip/blocks/analog/wireline_serdes/capture_clock_bridge/physical_result.json').read_text()),
    'lane':json.loads((ROOT/'ip/blocks/analog/wireline_serdes/lane_rx_regenerative_capture/physical_result.json').read_text())}
output=ROOT/'projects/programmable_transceiver_platform/evidence/wired-pulse-data-screen.json'
output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(static=static,best=best),indent=2))
