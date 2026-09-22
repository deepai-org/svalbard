"""Managed loaded calibration, multiple DAC events and stopped charge."""
import json
import numpy as np
from chip_model import P
from managed_resources import command
from vector_loaded_tx import VectorPhaseLoadedTxChip

def main():
    c=VectorPhaseLoadedTxChip(watchdog_s=1e-3,dac_latency_s=100e-9,tx_relative_gain=True)
    assert command(c,'rf_coarse_start',2412000000)['accepted']
    c.advance(c.time+50e-6)
    print('coarse acquisition complete',c.time,flush=True)
    reply=command(c,'tx_cal_start');assert reply['accepted']
    c.advance(c.time+25e-6)
    assert c.tx_cal.state=='ready'
    print('loaded calibration ready',c.time,flush=True)
    assert command(c,'tx_cal_commit',reply['value'])['accepted']
    assert command(c,'configure_mode',0)['accepted'];c.advance(c.time+20e-6)
    assert c.state=='active' and not c.loaded_tx.network.output_on
    powers=list(c.tx_cal.powers);calibration=c.tx_cal.candidate
    try:c.configure_rf_carrier(2437000000)
    except ValueError:pass
    else:raise AssertionError("Unsupported network carrier admitted")
    assert c.tx_cal.valid
    for z in (.2+.1j,-.1+.15j,.05-.1j):assert c.tx.accept(z)
    c.schedule(3,c.time+100e-9)
    # One outer advance crosses all three physical update events.
    c.advance(c.time+2e-6)
    assert c.dac_pipeline_updates==3 and c.loaded_tx.network.output_on
    assert c.tx.time==c.tx_detector.time==c.loaded_tx.network.time==c.time
    before=c.pad_envelope();state=c.loaded_tx.network.voltage.copy()
    c.set_reference(False,c.time)
    assert c.state=='draining' and not c.loaded_tx.network.output_on
    assert np.array_equal(state,c.loaded_tx.network.voltage)
    assert c.pad_envelope()==before
    c.advance(c.time+2e-6)
    assert c.dac_pipeline_updates==3 and not c.tx_cal.valid
    report=dict(status='passed',phase_substeps=c.phase_steps,phase_events=c.phase_events,max_phase_residual=c.phase_residual,probe_powers=powers,correction=calibration,
        before_stop_pad_magnitude=abs(before),after_stop_pad_magnitude=abs(c.pad_envelope()),dac_updates=c.dac_pipeline_updates,
        limitations=['Experimental fixed2412MHz network; Autonomous LO phase included; retuning not integrated.',
        'Source is prescribed Thevenin envelope; no chip DC current feedback or physical qualification.',
        'Managed commands and finite internal queue playback; no full host/wired quality screen.',
        'Detector remains physically connected; shared ADC resource allocation still unresolved.'])
    baseline=json.loads((P/'evidence/connected-phase-loaded-calibration.json').read_text())
    for key in ('probe_powers','correction','dac_updates','phase_substeps','phase_events'):
        assert report[key]==baseline[key],key
    for key in ('before_stop_pad_magnitude','after_stop_pad_magnitude','max_phase_residual'):
        assert abs(report[key]-baseline[key])<1e-12,key
    report['scalar_comparison']='Matching saved scalar codes, coefficients, event counts and pad endpoints'
    (P/'evidence/connected-vector-phase-loaded-calibration.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
