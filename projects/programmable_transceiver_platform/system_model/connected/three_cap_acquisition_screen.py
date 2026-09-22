"""Noisy integer-edge acquisition test of the leading linear filter candidate."""
import hashlib,json,math,time
from pathlib import Path
import numpy as np
from chip_model import P
from three_cap_pll import ThreeCapRFClock
from oscillator_noise import FrequencyNoise
from driver_clock_forcing import DriverPulledSpectrum


def main(selection="noise"):
    directory=Path(__file__).parent
    hashes={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.glob('*.py')}
    source=P/'evidence/pll-filter-resynthesis-corrected.json'
    ranked=json.loads(source.read_text())
    if selection=='noise':candidate=ranked['best'][0]
    elif selection=='balanced':
        # Exploratory ranking constraints, not changes to acquisition acceptance.
        eligible=[c for c in ranked['noise_ripple_frontier']
            if c['sampled_phase_margin_deg']>=50 and c['predicted_noise_rms_rad']<.035]
        candidate=min(eligible,key=lambda c:c['transimpedance_4mhz_ohm'])
    else:raise ValueError('Unknown candidate selection')
    values={k:candidate[v] for k,v in [('r','r_ohm'),('cf','cf_f'),('cs','cs_f'),('r3','r3_ohm'),('c3','c3_f')]}
    output=P/('evidence/three-cap-acquisition-screen.json' if selection=='noise' else 'evidence/three-cap-balanced-acquisition-screen.json')
    report=dict(status='running',selection=selection,linear_candidate=candidate,ranking_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),filter_values=values,source_sha256=hashes,cases=[],limitations=[
        'Isolated PLL with held driver rail; not full-chip quality or physical phase-noise qualification.',
        'Original divider sequence, seeded frequency noise and lock gates retained.',
        'Reference-edge phase samples omit inter-edge ripple; startup differs from integrated coarse acquisition.'])
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    for target in (2437000000,2412000000):
        pll=ThreeCapRFClock(filter_values=values,reference_hz=40e6,divider=60,
            free_hz=2.4e9*.92+7*25e6,phase_cycles=.2)
        pll.retarget(0,target)
        noise=FrequencyNoise.seeded(20000.,seed=839)
        pll.set_noise(0,DriverPulledSpectrum(noise.tones,1e6*(3.25799896954-3.3)))
        row=dict(target_hz=target,status='running',steps=0,first_lock_s=None,lock_losses=0,fault=None)
        report['cases'].append(row);tail=[];start=time.monotonic()
        for i in range(1,2401):
            try:
                pll.advance(i/40e6);was=pll.locked;locked=pll.observe_lock()
            except ValueError as error:
                row['fault']=str(error);break
            row['steps']=i
            if locked and row['first_lock_s'] is None:row['first_lock_s']=pll.time
            if was and not locked:row['lock_losses']+=1
            if i>=1601:tail.append((2*math.pi*(pll.output_phase_cycles-target*pll.time),pll.frequency_hz-target,locked))
            if i%100==0:
                row.update(time_s=pll.time,elapsed_s=time.monotonic()-start,nodes_v=pll.filter.state[:3].tolist())
                save();print(target,i,pll.locked,flush=True)
        row.update(status='characterized',time_s=pll.time,elapsed_s=time.monotonic()-start,
            sustained_tail_lock=len(tail)==800 and all(v[2] for v in tail),
            tail_phase_std_rad=float(np.std([v[0] for v in tail])) if tail else None,
            tail_peak_frequency_error_hz=max((abs(v[1]) for v in tail),default=None),
            nodes_v=pll.filter.state[:3].tolist())
        save();print(row,flush=True)
    report['source_hashes_match']=all(hashlib.sha256((P/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    report['status']='characterized' if report['source_hashes_match'] else 'invalid_source_change'
    save()
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--selection',choices=['noise','balanced'],default='noise')
    main(parser.parse_args().selection)
