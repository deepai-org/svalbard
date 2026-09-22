"""Edge-driven follow-up to exploratory worst-margin loading/component stress."""
import hashlib,json,math,time
from pathlib import Path
import numpy as np
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/connected'))
from chip_model import P
from three_cap_pll import ThreeCapRFClock
from oscillator_noise import FrequencyNoise
from driver_clock_forcing import DriverPulledSpectrum


def main():
    directory=P/'system_model/connected'
    hashes={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.glob('*.py')}
    source=P/'evidence/three-cap-sensitivity.json'
    stress=json.loads(source.read_text())
    case=stress['rows'][-1]
    candidate=case['worst_margin_case']
    scales=candidate['scales']
    values={k:v*scales[k] for k,v in stress['nominal_filter'].items()}
    values['c3']+=case['added_tuning_capacitance_f']
    selection='worst_linear_margin_2pf_exploratory_stress'
    output=P/'evidence/three-cap-stressed-acquisition-screen.json'
    report=dict(status='running',selection=selection,linear_candidate=candidate,ranking_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),filter_values=values,source_sha256=hashes,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),gain_scales={k:scales[k] for k in ('icp','kvco')},cases=[],limitations=[
        'Isolated PLL with held driver rail; not full-chip quality or physical phase-noise qualification.',
        'Original divider sequence, seeded frequency noise and lock gates retained.',
        'Component and load stress is exploratory, not a PDK corner or yield estimate.',
        'Reference-edge phase samples omit inter-edge ripple; startup differs from integrated coarse acquisition.'])
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    for target in (2437000000,2412000000):
        pll=ThreeCapRFClock(filter_values=values,reference_hz=40e6,divider=60,
            free_hz=2.4e9*.92+7*25e6,phase_cycles=.2)
        # Fresh clock only: change physical pump amplitude and VCO gain before any edge.
        assert pll.time==0 and not pll.reference_history
        pll.current_amplitude*=scales['icp']
        pll.gains.kvco*=scales['kvco']
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
if __name__=='__main__':main()
