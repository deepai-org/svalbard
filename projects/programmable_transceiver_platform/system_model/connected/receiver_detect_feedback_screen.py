"""Two-way assumed shared-rail sensitivity in probe stimulus and sensing."""
import json
from chip_model import P
from receiver_detect_supply import SupplyDetectChip


def run(mode,sign,step,pieces=1):
    c=SupplyDetectChip(watchdog_s=100e-6,probe_step_s=step,probe_gain_per_v=sign,
        probe_sensor_v_per_v=sign*.02,rf_hz_per_v=1e6,wire_hz_per_v=1e6)
    c.configure_rx('external_tone',1,5e6,5e6,.2+.1j,250e3)
    c.configure(mode,0);c.advance(8e-6);c.capture(64,c.time+100e-9)
    c.detect_start(c.time,c.epoch);start=c.time
    for i in range(1,pieces+1):c.advance(start+6e-6*i/pieces)
    c.host_decoder.finish()
    assert c.state=='active' and c.host_samples==c.adc_words and len(c.host_samples)==64
    result=c.detect_result(c.epoch);assert result['decision']=='present'
    return dict(mode=mode,sign=sign,step_s=step,charge_c=c.probe_supply_charge,
        samples=result['samples'],minimum_gain=c.probe_minimum_gain,
        sensor_error_v=c.probe_maximum_sensor_error,rail_minimum_v=c.supply.minimum)


def main():
    rows=[]
    for mode in (0,1):
        base=run(mode,0,.5e-9)
        for sign in (-1,1):
            coarse=run(mode,sign,.5e-9);fine=run(mode,sign,.25e-9)
            delta=max(abs(a-b) for a,b in zip(fine['samples'][0],base['samples'][0]))
            refine=max(abs(a-b) for a,b in zip(fine['samples'][0],coarse['samples'][0]))
            assert fine['sensor_error_v']>0 and delta>1e-3
            assert refine<delta*.05,(delta,refine)
            assert abs(fine['charge_c']-base['charge_c'])/base['charge_c']>.001
            split=run(mode,sign,.5e-9,137)
            subdivision=max(abs(a-b) for a,b in zip(split['samples'][0],coarse['samples'][0]))
            assert subdivision<delta*.05
            assert abs(split['charge_c']-coarse['charge_c'])/coarse['charge_c']<.01
            rows.append(dict(subdivision_change=subdivision,baseline=base,coarse=coarse,fine=fine,measurement_change=delta,refinement_change=refine))
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Assumed signed1/V stimulus gain and0.02V/V sensor offset sensitivities, not measured driver/comparator PSRR.',
        'Nominal present loads only; no guarantee across the full detector load/sensor envelope.',
        'Held gain between subnanosecond supply steps; local refinement checks do not prove complete convergence.',
        'Between-event analog common-mode limits, real driver output compliance and sensor dynamics remain open.'])
    (P/'evidence/connected-receiver-detect-feedback.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed both-mode signed probe stimulus/sensor feedback, charge response and step refinement')

if __name__=='__main__':main()
