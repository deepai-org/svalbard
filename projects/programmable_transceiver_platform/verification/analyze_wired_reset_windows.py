#!/usr/bin/env python3
"""Measure reset/evaluation timing observations, without inventing gate thresholds."""
import hashlib
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
PROJECT=ROOT/'projects/programmable_transceiver_platform'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
coarse_path=PROJECT/'evidence/wired-coarse-phase-screen.json'
coarse=json.loads(coarse_path.read_text())
rows=[]
for ps in (-200,-300):
    folder=ROOT/f'scratch/transceiver-wired-phase{ps}ps'
    wave=folder/'changing.dat'
    case=next(c for c in coarse['cases'] if c['phase_ps']==ps)
    assert sha(wave)==case['waveform_sha256']
    x=np.loadtxt(wave,skiprows=1); t=x[:,0]; sense=x[:,3]
    def crossings(level,rising):
        mask=((sense[:-1]<level)&(sense[1:]>=level) if rising else
              (sense[:-1]>=level)&(sense[1:]<level))
        return [float(t[i]+(level-sense[i])*(t[i+1]-t[i])/(sense[i+1]-sense[i])) for i in np.where(mask)[0]]
    for bit in (20,30):
        start=1e-9+bit*400e-12+ps*1e-12
        observations=[]
        for level in (.5,.8,1.65):
            falls=[s for s in crossings(level,False) if start<s<start+800e-12]
            assert len(falls)==1
            fall=falls[0]; rise=next(s for s in crossings(level,True) if s>fall)
            at=lambda col:float(np.interp(rise,t,x[:,col]))
            observations.append(dict(observation_level_v=level,fall_s=fall,rise_s=rise,
                below_level_duration_ps=(rise-fall)*1e12,
                raw_rx_at_rise_v=at(14)-at(15),pin_at_rise_v=at(1)-at(2),
                converter_at_rise_v=at(9)-at(10),capture_clock_at_rise_v=at(5)))
        rows.append(dict(phase_ps=ps,bit=bit,bit_start_s=start,observations=observations))
paths=[coarse_path,ROOT/'ip/blocks/analog/wireline_serdes/cdr/cml_to_cmos/cml_to_cmos_fast.spice',
       ROOT/'ip/blocks/analog/wireline_serdes/clock_pulse/clock_pulse_generator.spice']
result=dict(status='waveform_diagnostic_not_reset_qualification',rows=rows,
    source_sha256={str(p.relative_to(ROOT)):sha(p) for p in paths},
    analyzer_sha256=sha(Path(__file__)),
    circuit_interpretation='SENSE low precharges XP/XN and input nodes; SENSE and separate BOOST control parallel tail paths. Held outputs need not reset when the dynamic nodes precharge.',
    unresolved=['Observation levels are not characterized transistor decision thresholds.',
                'Short low interval alone does not prove failed reset.',
                'BOOST and internal XP/XN/NIP/NIN/NTAIL were not exported.',
                'Early raw input polarity does not prove sufficient differential at the actual decision instant.'],
    next_experiment='Repeat the same -200 ps case with BOOST, local SENSE gate and internal regenerative/input/tail node observations; preserve circuit and bit scoring before choosing a timing or device change.')
(PROJECT/'evidence/wired-reset-window-analysis.json').write_text(json.dumps(result,indent=2)+'\n')
for row in rows:
    print(row['phase_ps'],row['bit'],[(o['observation_level_v'],round(o['below_level_duration_ps'],2),round(o['raw_rx_at_rise_v'],4)) for o in row['observations']])
