"""Compare native driver choices at unchanged rate/load; not physical signoff."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
from run_gpio_transient import run_case, PAD

def main(*,design=None):
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
    from design_definition import load_design
    design=load_design() if design is None else design
    work=Path('/work')
    matrix=[(drive, pattern) for drive in (12,16) for pattern in ('alternating','prbs7')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda case:run_case(work,'typical',3.3,25,8,case[1],drive_ma=case[0]),matrix))
    c=design.contract
    power=c['power']
    budget=next(d['per_connection_budget_ma'] for d in power['domains'] if d['id']=='HOST')
    for r in results:
        if r['pattern']=='alternating':
            r['host_power_extrapolation']=[{
                'segment':s['id'],
                'with_allowances_ma':r['two_pad_dvdd_average_a']*1000/2*len(s['fast_outputs'])*power['screen_output_current_multiplier']+power['screen_other_current_allowance_ma_per_segment'],
                'budget_ma':budget}
                for s in power['host_segments']]
    report={'scope':'native driver selection experiment at 312.5 Mb/s/pin, 8 pF; ideal rails and assumed thresholds/aperture',
            'design_provenance':design.provenance(),
            'model_role':'shared_budget_with_independent_native_pad_characterization',
            'results':results,'pad_spice_sha256':hashlib.sha256(PAD.read_bytes()).hexdigest(),
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'runner_sha256':hashlib.sha256(Path('/src/verification/run_gpio_transient.py').read_bytes()).hexdigest(),
            'contract_sha256':design.provenance()['documents']['spec/contract.json'],
            'contract_sha256_format':'canonical-json-sha256-v1',
            'limitations':['No package, SSO, H2D, extracted routing or FPGA timing closure.',
                           'Only typical process at 3.3 V and 25 C, 20 measured bits per case.',
                           '0.3/0.7 VDD thresholds and +/-0.2 ns aperture remain assumptions.']}
    (work/'drive-strength.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
