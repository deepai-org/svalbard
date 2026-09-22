"""Small staged noisy-acquisition comparison; not full-chip qualification."""
import json
from chip_model import P
from fractional_rf_chip import ShapedRFClock
from oscillator_noise import FrequencyNoise

def main():
    rows=[]
    for target in (2412000000,2437000000):
      for seed in (830,831,832):
       for fraction in (.35,.30):
        p=ShapedRFClock(reference_hz=40e6,divider=60,free_hz=2.4e9*.96,phase_cycles=.2,bandwidth_hz=300e3,fast_fraction=fraction)
        p.retarget(0,target);p.set_noise(0,FrequencyNoise.seeded(20000,seed=seed))
        first=None;losses=0;fault=None;tail=True
        for i in range(1,2401):
            try:p.advance(i/40e6);previous=p.locked;locked=p.observe_lock()
            except ValueError as error:fault=str(error);break
            if locked and first is None:first=p.time
            if previous and not locked:losses+=1
            if i>=1600:tail=tail and locked
        row=dict(target_hz=target,seed=seed,fast_fraction=fraction,first_lock_s=first,losses=losses,fault=fault,
            sustained=fault is None and first is not None and first<=40e-6 and losses==0 and tail)
        rows.append(row);print(row,flush=True)
        (P/'evidence/connected-pll-fraction-seeds.json').write_text(json.dumps(dict(status='characterized' if len(rows)==12 else 'running',cases=rows,
            scope='Two carriers, three noise phases, one initial phase/free frequency; no supply forcing, coarse sequencing or waveform quality.'),indent=2)+'\n')
if __name__=='__main__':main()
