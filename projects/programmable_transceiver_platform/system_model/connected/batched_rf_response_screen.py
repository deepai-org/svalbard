"""Compare batched response to scalar loaded-network decomposition."""
import json,time
import numpy as np
from chip_model import P
from rf_loaded_detector import voltage_terms as scalar
from batched_rf_response import voltage_terms as batched
from rf_switched_load import SwitchedLoad
from tx_dac_correction_screen import make
from tx_output_terms import output_terms
from tx_output_candidate import PARAMETERS

def main():
    tx=make(12);tx.apply_sample(.15+.1j,0);source=output_terms(tx.transmit_terms(),**PARAMETERS)
    errors=[];n=SwitchedLoad()
    for output,dummy in ((False,True),(True,False),(False,False),(True,True)):
        n.configure(output,dummy);n.voltage=n.steady(.12+.03j)
        for shift in (0.,2*np.pi*25e6,-2*np.pi*112e6):
            terms=[(a,p+1j*shift) for a,p in source]
            a=scalar(n,terms);b=batched(n,terms)
            for t in (0.,1e-12,1e-9,1e-6):
                va=sum(v*np.exp(p*t) for v,p in a);vb=sum(v*np.exp(p*t) for v,p in b)
                error=float(max(abs(va-vb)));assert error<1e-12;errors.append(error)
    timings={}
    for name,fn in (('scalar',scalar),('batched',batched)):
        elapsed=[]
        for _ in range(3):
            start=time.perf_counter()
            for i in range(100):fn(n,source)
            elapsed.append(time.perf_counter()-start)
        timings[name]=float(np.median(elapsed))
    report=dict(status='passed',comparisons=len(errors),max_voltage_difference=max(errors),
        median_100_calls_s=timings,local_speed_ratio=timings['scalar']/timings['batched'],
        limitations=['Local decomposition equivalence only; no whole-chip substitution yet.',
        'Same modal and resonance guards; no term pruning or timestep relaxation.'])
    (P/'evidence/connected-batched-rf-response.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
