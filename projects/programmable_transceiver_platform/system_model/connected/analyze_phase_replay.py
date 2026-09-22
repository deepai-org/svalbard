"""Read-only phase attribution screen; never substitutes for original quality gates."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def analyze(baseline, replay, phase):
    with np.load(baseline) as old, np.load(replay) as new, np.load(phase) as obs:
        for key in ('time_s', 'ideal_pad', 'actual_pad'):
            if not np.array_equal(old[key], new[key]):
                raise ValueError('Replay changed baseline trace: '+key)
        t=new['time_s'];x=new['ideal_pad'];y=new['actual_pad']
        if not np.array_equal(t,obs['time_s']):
            raise ValueError('Phase and pad observation times differ')
        theta=obs['lo_phase_rad'];rail=obs['driver_rail_v'];ref=obs['reference_v']
        if not all(np.all(np.isfinite(a)) for a in (x,y,theta,rail,ref)):
            raise ValueError('Nonfinite observations')
        split=len(x)//4
        def score(v):
            gain=np.vdot(x[:split],v[:split])/np.vdot(x[:split],x[:split])
            expected=gain*x[split:]
            return float(np.linalg.norm(v[split:]-expected)/np.linalg.norm(expected))
        # A counterfactual instantaneous derotation is not an actual PLL fix:
        # the RF network retains memory of prior oscillator phase.
        corrected=y*np.exp(-1j*(theta-theta[0]))
        windows=[]
        for indices in np.array_split(np.arange(len(x)),4):
            weight=abs(x[indices])**2
            lo_mean=np.sum(weight*np.exp(1j*theta[indices]))/np.sum(weight)
            pad_mean=np.vdot(x[indices],y[indices])
            windows.append(dict(samples=len(indices),lo_phase_rad=float(np.angle(lo_mean)),
                pad_phase_rad=float(np.angle(pad_mean)),rail_min_v=float(np.min(rail[indices])),
                rail_max_v=float(np.max(rail[indices])),reference_min_v=float(np.min(ref[indices]))))
        return dict(status='diagnostic_only',exact_pad_replay=True,
            original_relative_rms=score(y),instantaneous_derotation_relative_rms=score(corrected),
            windows=windows,input_sha256={str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest()
                for p in (baseline,replay,phase)},limitations=[
                'Derotation uses internal LO state unavailable to an external receiver; it is not a passing PHY result.',
                'Both scores fit gain on the first quarter only; no held-out fitting or dropped samples.',
                'Network memory prevents instantaneous derotation from uniquely isolating causal PLL error.',
                'Window phase means use signal-energy weights; phase is circular, not an unwrapped timing measurement.'])

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for key in ('baseline','replay','phase','output'):parser.add_argument('--'+key,required=True,type=Path)
    args=parser.parse_args();result=analyze(args.baseline,args.replay,args.phase)
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
