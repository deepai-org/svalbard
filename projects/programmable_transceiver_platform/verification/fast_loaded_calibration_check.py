"""Loaded-monitor calibration: preserve attenuation and explicit gain semantics."""
import hashlib,json
from fast_loaded_output import LoadedOutputChip,P
from managed_resources import command

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    rows=[]
    for relative in (False,True):
        c=LoadedOutputChip(tx_relative_gain=relative);c.advance(8e-6)
        start=command(c,'tx_cal_start');assert start['accepted']
        c.advance(c.time+25e-6)
        state=c.tx_cal.state;reason=getattr(c.tx_cal,'reason',None)
        commit=command(c,'tx_cal_commit',start['value'])
        assert c.tx_adc_samples==9
        assert c.output_network.time==c.tx.time==c.tx_detector.time==c.time
        if relative:
            assert state=='ready' and commit['accepted'] and c.tx_cal.valid
        else:
            assert state=='cancelled' and not commit['accepted'] and not c.tx_cal.valid
        rows.append(dict(relative_gain=relative,state_before_commit=state,reason=reason,
            commit_accepted=commit['accepted'],shared_adc_samples=c.tx_adc_samples,
            monitor_power=c.tx_detector.value,pad_voltage_magnitude=abs(c.output_network.voltage[1])))
    files=list((P/'system_model/connected').glob('*.py'))+list((P/'system_model/architecture_fast').glob('*.py'))+[P/'verification/fast_loaded_output.py',P/'verification/fast_loaded_calibration_check.py']
    report=dict(status='passed',source_sha256={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},cases=rows,
        physical_qualification=False,limitations=['Relative gain mode does not estimate absolute pad gain or validate calibration accuracy.',
            'Loaded monitor and shared ADC are connected; loaded RX loopback and traffic remain unqualified.'])
    (P/'evidence/fast-loaded-calibration.json').write_text(json.dumps(report,indent=2)+'\n')
    print(rows)
if __name__=='__main__':main()
