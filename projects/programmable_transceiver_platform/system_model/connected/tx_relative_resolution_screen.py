"""Finite monitor resolution limits relative IQ calibration despite gain invariance."""
import json,itertools
import numpy as np
from chip_model import P
from tx_iq_calibration import probes,fit
from tx_output_stage import output_envelope
from tx_dac_correction import DacCorrection
from rf_quality_screen import quality

def main():
    p=probes();params=dict(gain_imbalance_db=.5,phase_error_deg=5.,lo_feedthrough=.0025)
    powers=abs(output_envelope(p,np.ones(len(p)),**params))**2
    z=.22*np.exp(1j*np.arange(2048)*.13)+.09*np.exp(-1j*np.arange(2048)*.37)
    rows=[]
    for bits,gain in itertools.product((8,10,12),(.001,.003,.01,.03,.1,.3,.56,1.)):
        step=.1/((1<<bits)-1);codes=np.rint(powers*gain/step)
        row=dict(bits=bits,monitor_power_gain=gain,peak_code=int(max(codes)),distinct_codes=len(set(codes)))
        try:
            cal=fit(p,codes*step,relative_gain=True);act=DacCorrection(cal,12)
            y=np.array([act(0,v) for v in z]);y=output_envelope(y,np.ones(len(y)),**params)
            q=quality(list(z),list(y));row.update(quality=q,local_2percent_budget_pass=bool(q['corrected_relative_rms']<=.02))
        except ValueError as error:row.update(rejected=str(error),local_2percent_budget_pass=False)
        rows.append(row)
    assert any('rejected' in r for r in rows)
    assert any(not r['local_2percent_budget_pass'] and 'quality' in r for r in rows)
    assert all(r['local_2percent_budget_pass'] for r in rows if r['bits']==12 and r['monitor_power_gain']>=.3)
    report=dict(status='characterized',cases=rows,limitations=['Local quantization-only experiment; 2% correction budget is provisional, not a full-chip or protocol threshold.',
        'No additive detector noise or offset, no settling error, no automatic resolution adequacy gate.',
        'Coarse quantization may produce a plausible invertible fit with unacceptable correction error.'])
    (P/'evidence/connected-tx-relative-resolution.json').write_text(json.dumps(report,indent=2,default=lambda v:v.item())+'\n')
    for r in rows:print(r['bits'],r['monitor_power_gain'],r['peak_code'],r.get('quality',{}).get('corrected_relative_rms'),r['local_2percent_budget_pass'])
if __name__=='__main__':main()
