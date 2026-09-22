"""Sustained four-path workload on the dynamic-lock, loop-driven controller."""
import json
from chip_model import P
from loop_driven_edges import PhasedChip
from sustained_lifecycle import run

def main():
    rows=[run(mode,ppm,chip_factory=PhasedChip,disturbance_sign=sign)
          for mode in (0,1) for ppm in (-100,100) for sign in (-1,1)]
    assert all(len(r['interventions'])==2 for r in rows)
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Finite128-frame workloads with two bounded interventions; no infinite drift or arbitrary fault guarantee.',
        'ADC/DAC track the linear loop; serializer and host clocks remain independently prescribed.',
        'Ideal coherent RF gain and simplified reference/converter behavior remain.',
        'Queue capacities are declared planning budgets, not verified physical or RTL resources.'])
    (P/'evidence/connected-clocked-sustained-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed eight sustained dynamic-lock cases with16 active clock interventions')

if __name__=='__main__':main()
