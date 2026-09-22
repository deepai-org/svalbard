"""Four-path sensitivity to opposite bounded ADC/DAC timing errors."""
import json
from chip_model import P
from sample_clock import controls
from wired_return_lifecycle import run

def main():
    controls();rows=[]
    for mode in (0,1):
        baseline=run(mode,.3,100)
        for jitter in (-2e-9,-100e-12,100e-12,2e-9):
            row=run(mode,.3,100,jitter_s=jitter)
            row['changed_adc_words']=sum(a!=b for a,b in zip(row['adc_words'],baseline['adc_words']))
            rows.append(row)
        assert any(r['mode']==mode and r['changed_adc_words']>0 for r in rows)
        # Loss of reference must still terminate both jittered event streams.
        rows.append(run(mode,-.3,-100,interrupt=True,jitter_s=2e-9))
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Four-edge periodic modulation is a timing sensitivity input, not calibrated random jitter or phase-noise spectrum.',
        'Opposite ADC/DAC modulation exposes differential timing; shared/common timing noise is not yet swept.',
        'Small bursts and ideal coherent RF receiver remain; no EVM/BER acceptance budget is implied.'])
    (P/'evidence/connected-jitter-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed ten jittered four-path/recovery scenarios and clock controls')

if __name__=='__main__':main()
