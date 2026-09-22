"""Common forwarded-reference payload pacing with independent host service."""
import json
from fractions import Fraction
from chip_model import P
from shared_supply_lifecycle import CoupledChip
from sustained_lifecycle import run

def main():
    rows=[]
    for mode in (0,1):
        for reference_ppm in (-100,100):
            for host_ppm in (-100,100):
                row=run(mode,reference_ppm,chip_factory=CoupledChip,disturbance_sign=1,
                        matched_reference=True,host_ppm=host_ppm)
                rows.append(row)
    # Exact arithmetic proves zero secular rate slope under the declared common
    # reference ratio, not bounded queue occupancy under every service pattern.
    contracts=[]
    contract=json.loads((P/'spec/contract.json').read_text())
    for mode,ratios,quotas in [(0,[(1,2,10),(4,25,24)],[33,25]),(1,[(4,5,10),(8,125,16)],[52,7])]:
        spec=contract['modes'][mode];profile=contract['transport']['profiles'][spec['profile']]
        forwarded=profile['clock_hz']*profile['edges']
        for source,(n,d,bits),quota in zip(spec['sources'],ratios,quotas):
            production=Fraction(n,d)
            assert source['sample_bits']==bits
            consumption=Fraction(source['rate_bps'],source['sample_bits']*forwarded)
            assert production-consumption==0
            worst_arrival=production*bits*Fraction(1000100,999900)
            service=Fraction(quota*10,64)
            assert worst_arrival<service
            contracts.append(dict(mode=mode,bits_per_sample=bits,production_per_forwarded_edge=str(production),
                                  worst_payload_bits_per_service_edge=str(worst_arrival),reserved_service_bits_per_edge=str(service)))
    report=dict(status='passed',cases=rows,rate_contracts=contracts,complete_architecture=False,physical_qualification=False,
        limitations=['Common reference guarantees matching average rates by assumption; independent free-running payload clocks do not satisfy this contract.',
        'Capacity inequality and zero slope do not bound all service gaps/CDC phase/lock transients.',
        'Rational source generation is sampled at host frame boundaries; variable visibility and backpressure remain open.',
        'Physical clock synthesis must realize these ratios; this test does not prove that hardware capability.'])
    (P/'evidence/connected-matched-rate-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed eight common-reference sustained cases and exact rate/capacity checks')

if __name__=='__main__':main()
