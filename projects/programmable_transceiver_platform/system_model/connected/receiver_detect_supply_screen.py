"""Probe current affects actual shared rail, oscillator phase and RF capture."""
import json
from chip_model import P
from receiver_detect_supply import SupplyDetectChip


def run(mode,scale,step):
    c=SupplyDetectChip(watchdog_s=100e-6,probe_load_scale=scale,probe_step_s=step,
        rf_hz_per_v=1e6,wire_hz_per_v=1e6,coupling_per_v=1.)
    c.configure_rx('external_tone',1,5e6,5e6,.2+.1j,250e3)
    c.configure(mode,0);c.advance(8e-6)
    c.capture(64,c.time+100e-9);c.detect_start(c.time,c.epoch)
    c.advance(c.time+6e-6);c.host_decoder.finish()
    assert c.state=='active' and len(c.host_samples)==64 and c.host_samples==c.adc_words
    assert c.detect_result(c.epoch)['decision']=='present'
    assert c.probe.drive is None
    if scale:assert c.probe_supply_charge>0 and c.oscillator_supply_events>0 and c.supply.minimum<0
    else:assert c.probe_supply_charge==0 and c.supply.minimum==0
    return dict(mode=mode,scale=scale,step_s=step,charge_c=c.probe_supply_charge,
        peak_a=c.probe_supply_peak,minimum_rail_delta_v=c.supply.minimum,
        rf_pull_hz=c.maximum_rf_pull,samples=64),c.analog_samples


def main():
    rows=[]
    for mode in (0,1):
        zero,z=run(mode,0.,.5e-9)
        coarse,a=run(mode,1.,.5e-9)
        fine,b=run(mode,1.,.25e-9)
        delta=max(abs(x-y) for x,y in zip(a,z));refine=max(abs(x-y) for x,y in zip(a,b))
        assert delta>1e-5 and refine<delta*.1,(delta,refine)
        assert abs(coarse['charge_c']-fine['charge_c'])/fine['charge_c']<.02
        rows.append(dict(mode=mode,zero=zero,coarse=coarse,fine=fine,rf_change=delta,refinement_change=refine))
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Assumed linear driver mapping:100uA enabled bias and10% sink overhead; no physical efficiency or bias estimate.',
        'Subnanosecond charge impulses approximate continuous driver load; two-step refinement is local evidence, not a complete convergence proof.',
        'Probe circuit source voltage remains ideal0.2V; shared rail affects other chip circuits but not yet the probe stimulus/comparator itself.',
        'Nominal present load only, one coupling sign, finite RF capture; full electrical coexistence envelope remains open.'])
    (P/'evidence/connected-receiver-detect-supply.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed both-mode probe supply/clock/RF coupling, zero-load controls and timestep refinement')

if __name__=='__main__':main()
