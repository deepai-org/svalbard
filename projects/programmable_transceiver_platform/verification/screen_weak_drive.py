"""8 mA native driver at host-die and added-load stress points."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import numpy as np
from run_gpio_transient import run_case, PAD, crossing, stimulus, START, UI, N


def host_margin(path, pattern):
    t, a, k, d, c, ivd, ivc = np.loadtxt(path/'wave.txt', skiprows=1).T
    cin, cout = crossing(t,k,1.65), crossing(t,c,1.65)
    if len(cout) < sum(x < START+(N-4)*UI for x in cin):
        raise ValueError('lost clock edges')
    # Reject implausibly short/long received half-cycles before pairing edges.
    # This is an explicit diagnostic bound, not an FPGA pulse-width specification.
    intervals=np.diff(cout)
    if np.any(intervals < UI/2) or np.any(intervals > UI*1.5):
        raise ValueError('received clock interval outside diagnostic bounds')
    bits, _ = stimulus(pattern,3.3)
    margins=[]
    for ti,to in zip(cin,cout):
        sample=int(np.floor((ti-START)/UI))
        if not 8<=sample<N-4:
            continue
        lo,hi=to-.2e-9,to+.2e-9
        values=np.concatenate((np.interp([lo,hi],t,d),d[(t>lo)&(t<hi)]))
        margins.append(float(min(values-2.0) if bits[sample] else min(.8-values)))
    if len(margins)!=20:
        raise ValueError('unexpected measured bit count')
    return {'sampled_bits':len(margins),'minimum_margin_v':min(margins),
            'failures':sum(m<0 for m in margins),'vil_max_v':.8,'vih_min_v':2.0,
            'clock_interval_min_ns':float(min(intervals)*1e9),
            'clock_interval_max_ns':float(max(intervals)*1e9),
            'clock_measurement_reference_v':1.65,'assumed_aperture_ns':.4,'qualified':False}


def main():
    work=Path('/work')
    matrix=[(load,pattern) for load in (8,10) for pattern in ('alternating','prbs7')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda case:run_case(work,'typical',3.3,25,case[0],case[1],drive_ma=8),matrix))
    contract_path=Path('/src/spec/contract.json')
    c=json.loads(contract_path.read_text());power=c['power']
    budget=next(d['per_connection_budget_ma'] for d in power['domains'] if d['id']=='HOST')
    for r in results:
        r['host_threshold_screen']=host_margin(work/r['case'],r['pattern'])
        if r['pattern']=='alternating':
            r['host_power_extrapolation']=[]
            for s in power['host_segments']:
                estimate=r['two_pad_dvdd_average_a']*1000/2*len(s['fast_outputs'])*power['screen_output_current_multiplier']+power['screen_other_current_allowance_ma_per_segment']
                r['host_power_extrapolation'].append({'segment':s['id'],'with_allowances_ma':estimate,
                                                     'budget_ma':budget,'within_budget':estimate<=budget})
    report={'scope':'nominal 8 mA native driver characterization, not signoff',
            'results':results,'pad_spice_sha256':hashlib.sha256(PAD.read_bytes()).hexdigest(),
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'runner_sha256':hashlib.sha256(Path('/src/verification/run_gpio_transient.py').read_bytes()).hexdigest(),
            'contract_sha256':hashlib.sha256(contract_path.read_bytes()).hexdigest(),
            'host_threshold_source':'AMD DS181 v1.27.1 Tables 8 and 19; see spec/host-driver-selection.md#artix-load-baseline',
            'limitations':['10 pF is a selected lumped-load stress, not a characterized package/PCB.',
                           'Assumed aperture and clock reference are not receiver setup/hold closure.',
                           'Ideal supplies; no SSO, jitter, mismatch, process spread or H2D.',
                           'Twenty measured bits per pattern; no BER or interoperability qualification.']}
    (work/'weak-drive.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
