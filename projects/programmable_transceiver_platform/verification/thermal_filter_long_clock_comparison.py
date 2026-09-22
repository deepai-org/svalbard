"""Compare autonomous integer-edge clocks with reference and batched filters."""
import copy
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
import numpy as np
import thermal_filter_batched
from thermal_filter_local_guard import safe_region
thermal_filter_batched.safe_region=safe_region
from thermal_filter_batched import batched_step
from thermal_filter_guard_screen import ResistorNoiseFilter,BALANCED_FILTER
from three_cap_pll import ThreeCapRFClock
from oscillator_noise import FrequencyNoise
P=Path(__file__).resolve().parents[1]

class BatchedFilter(ResistorNoiseFilter):
    def advance(self,stop,command,max_step=1e-9):
        if max_step!=1e-9:
            return super().advance(stop,command,max_step=max_step)
        # Base-class copy prevents fallback recursion and preserves the original
        # source object if integration raises an exception.
        base=copy.copy(self);base.__class__=ResistorNoiseFilter
        result,route=batched_step(base,stop,command)
        self.state=result.state;self.time=result.time
        self.routes[route]+=1
    def __copy__(self):
        out=super().__copy__();out.routes=self.routes.copy();return out
    def __init__(self,**kwargs):
        super().__init__(**kwargs);self.routes=Counter()


def main():
    files=list((P/'system_model/connected').glob('*.py'))+[Path(__file__)]+[
        P/'verification'/f for f in ('thermal_filter_batched.py','thermal_filter_guard_screen.py','thermal_filter_local_guard.py',
          'thermal_filter_energy_screen.py','thermal_filter_exact_step_screen.py')]
    hashes={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    output=P/'evidence/thermal-filter-long-clock-comparison.json'
    report=dict(status='running',source_sha256=hashes,cases=[],limitations=[
        '60 us isolated acquisition and tail comparison; not full-chip qualification.',
        'Nominal component values, one thermal seed and one fractional carrier.'])
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        traces=[]
        for cls in (ResistorNoiseFilter,BatchedFilter):
            pll=ThreeCapRFClock(filter_values=BALANCED_FILTER,reference_hz=40e6,divider=60,
                free_hz=2.4e9*.92+7*25e6,phase_cycles=.2)
            pll.filter=cls(noise_bins=128,noise_seed=1249,**BALANCED_FILTER)
            pll.retarget(0,2437000000)
            pll.set_noise(0,FrequencyNoise.seeded(20000.,seed=839))
            trace=[];start=time.perf_counter()
            for i in range(1,2401):
                pll.advance(i/40e6);lock=pll.observe_lock()
                trace.append([pll.output_phase_cycles,pll.frequency_hz,float(lock),*pll.filter.state])
                if i%100==0:print(cls.__name__,i,flush=True)
            traces.append(np.array(trace))
            report['cases'].append(dict(solver=cls.__name__,elapsed_s=time.perf_counter()-start,
                routes=dict(getattr(pll.filter,'routes',{}))))
            save()
        delta=abs(traces[0]-traces[1]);maximum=delta.max(axis=0)
        assert maximum[0]<1e-6 and maximum[1]<1.,maximum
        assert maximum[2]==0 and max(maximum[3:6])<1e-8,maximum
        assert maximum[6]<1e-16 and maximum[7]<1e-18 and max(maximum[8:])<1e-21,maximum
        assert np.all(traces[0][-800:,2]==1) and np.all(traces[1][-800:,2]==1), 'Tail did not sustain lock'
        report.update(status='acquisition_tail_clock_comparison_passed',max_trace_errors=maximum.tolist(),
                      reference_to_batched_runtime_ratio=report['cases'][0]['elapsed_s']/report['cases'][1]['elapsed_s'])
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:
        report['source_hashes_match']=all(hashlib.sha256((P/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
        if not report['source_hashes_match']:report['status']='invalid_source_change'
        save()
    print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2))

if __name__=='__main__':main()
