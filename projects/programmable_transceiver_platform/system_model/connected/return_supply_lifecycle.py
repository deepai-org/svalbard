"""Both physical host-bus directions drive the same assumed supply state."""
import json
from chip_model import P
from shared_supply_lifecycle import CoupledChip,controls
from sustained_lifecycle import run

def main():
    controls()
    probe=CoupledChip(return_charge_per_transition=1e-15)
    for i,w in enumerate((0,1023,1023,0)):probe.emitted_return_word(w,i*1e-9)
    assert probe.return_transitions==24 and abs(probe.return_charge-24e-15)<1e-28
    rows=[]
    for mode in (0,1):
        for sensitivity in (0,-2,2):
            old=lambda **kw:CoupledChip(coupling_per_v=sensitivity,**kw)
            both=lambda **kw:CoupledChip(coupling_per_v=sensitivity,return_charge_per_transition=100e-15,**kw)
            baseline=run(mode,100,chip_factory=old,disturbance_sign=1)
            row=run(mode,100,chip_factory=both,disturbance_sign=1)
            m=row['reference_metrics']['supply'];b=baseline['reference_metrics']['supply']
            assert m['return_charge_c']>0 and m['return_transitions']>0
            assert abs(m['total_charge_c']-m['return_charge_c']-m['transitions']*100e-15)<1e-19
            if sensitivity==0:assert row['adc_sha256']==baseline['adc_sha256']
            else:assert row['adc_sha256']!=baseline['adc_sha256']
            row['input_only_minimum_delta_v']=b['minimum_delta_v']
            rows.append(row)
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Same assumed RC rail for both host directions; no extracted domain/package network.',
        'Clock/data transition charge ignores direction-dependent pad current and internal combinational activity.',
        'Supply currently affects sampled receiver gain only; PLL and DAC supply response remain open.',
        'Output activity depends on earlier ADC values, but no physical stability/yield claim follows.'])
    (P/'evidence/connected-return-supply-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed six bidirectional switching cases, zero-coupling and charge-accounting controls')

if __name__=='__main__':main()
