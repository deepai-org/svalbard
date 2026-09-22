"""Repeated-step correctness and timing of complete guarded prototype."""
import copy
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
import numpy as np
from thermal_filter_guard_screen import ResistorNoiseFilter,BALANCED_FILTER
from thermal_filter_batched import batched_step as guarded_step
P=Path(__file__).resolve().parents[1]


def main():
    rows=[]
    for dt in (.1e-9,1e-9,10e-9):
        original=ResistorNoiseFilter(noise_bins=128,**BALANCED_FILTER)
        original.time=120e-6;original.state[:3]=[.03,-.01,.015]
        # Identical predetermined physical command edges in both integrations.
        commands=np.tile([100e-6,0.,-100e-6,0.],25)
        stops=original.time+dt*np.arange(1,len(commands)+1)
        reference=copy.copy(original)
        start=time.perf_counter()
        for stop,command in zip(stops,commands):reference.advance(stop,command)
        reference_s=time.perf_counter()-start
        candidate=copy.copy(original);routes=Counter()
        start=time.perf_counter()
        for stop,command in zip(stops,commands):
            candidate,route=guarded_step(candidate,stop,command);routes[route]+=1
        candidate_s=time.perf_counter()-start
        error=abs(candidate.state-reference.state)
        assert max(error[:3])<1e-9 and error[3]<1e-17 and error[4]<1e-19
        assert max(error[5:])<1e-22
        rows.append(dict(step_s=dt,steps=len(commands),routes=dict(routes),
            reference_seconds=reference_s,guarded_seconds=candidate_s,
            speed_ratio=reference_s/candidate_s,max_voltage_error_v=float(max(error[:3])),
            integrated_voltage_error_vs=float(error[3]),max_energy_error_j=float(max(error[5:]))))
    files=[Path(__file__)]+[P/'verification'/x for x in ('thermal_filter_guard_screen.py','thermal_filter_batched.py',
            'thermal_filter_energy_screen.py','thermal_filter_exact_step_screen.py')]
    files+=list((P/'system_model/connected').glob('three_cap*.py'))
    report=dict(status='repeated_step_comparison_complete',rows=rows,
        limitations=['Fixed synthetic pump commands, not autonomous clock or full-chip traffic.',
                     'Timing is machine/load dependent and includes no performance guarantee.',
                     'No live-model substitution performed.'],
        source_sha256={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (P/'evidence/thermal-filter-batched-benchmark.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(rows,indent=2))

if __name__=='__main__':main()
