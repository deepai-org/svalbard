"""Fractional pulse clock in full-chip independent-tone/converter transport."""
import cmath,json,math
from chip_model import P,decode_iq
from fractional_rf_chip import FractionalRFChip
from managed_resources import command
from rf_quality_screen import quality

def run(mode,target,bandwidth,rf_noise_rms_hz=0.,noise_seed=830):
    c=FractionalRFChip(rf_noise_rms_hz=rf_noise_rms_hz,noise_seed=noise_seed,
        wire_noise_rms_hz=rf_noise_rms_hz/2,rf_pulse_bandwidth_hz=bandwidth,watchdog_s=100e-6,load_capacitance=1e-12,adc_latency_s=30e-9,
        return_charge_per_transition=50e-15,rf_hz_per_v=1e6,wire_hz_per_v=1e6)
    amplitude=.25+.1j;beat=250e3
    c.configure_rx('external_tone',1,5e6,5e6,amplitude,target-2.4e9+beat)
    assert command(c,'configure_rf_carrier',target)['accepted']
    c.configure(mode,c.time);c.advance(c.time+40e-6)
    if c.state!='active' or not c.rf_pll.locked:
        return dict(mode=mode,target_hz=target,bandwidth_hz=bandwidth,qualified=False,
            failure='acquisition/lock',state=c.state,events=c.events,
            good_comparisons=c.rf_pll.good,lock_tail=c.rf_lock_history[-160:])
    c.capture(256,c.time+100e-9,gain=1)
    words=[17,801,0,511]*4
    for word in words:c.accept_wire(word)
    c.schedule_wire(len(words),c.time+100e-9)
    c.advance(c.time+16e-6)
    if c.state!='active':
        return dict(mode=mode,target_hz=target,bandwidth_hz=bandwidth,qualified=False,
            failure='run-time fault',state=c.state,events=c.events,
            completed_samples=len(c.adc_words),lock_tail=c.rf_lock_history[-160:])
    c.host_decoder.finish()
    assert c.state=='active' and c.host_samples==c.adc_words and len(c.host_samples)==256
    assert c.wired_output==words
    reference=[amplitude/(1+1j*beat/5e6)*cmath.exp(2j*math.pi*beat*t) for t in c.sample_times]
    measured=[decode_iq(w,c.bits) for w in c.adc_words]
    q=quality(reference,measured)
    return dict(mode=mode,target_hz=target,bandwidth_hz=bandwidth,qualified=q['screen_pass'],quality=q,locked=c.rf_pll.locked,
        rail_events=c.oscillator_supply_events,reference_minimum_v=c.adc_reference.minimum,
        divider_counts=c.rf_pll.sequence.emitted)

def main():
    rows=[]
    for bandwidth in (500e3,350e3):
        for m in (0,1):
            for t in (2412000000,2437000000):
                row=run(m,t,bandwidth);rows.append(row)
                print(bandwidth,m,t,row.get('quality',{}).get('corrected_relative_rms'),row['qualified'],flush=True)
    viable=[bw for bw in (500e3,350e3) if all(r['qualified'] for r in rows if r['bandwidth_hz']==bw)]
    passed=bool(viable)
    (P/'evidence/connected-fractional-rf-quality.json').write_text(json.dumps(dict(status='passed' if passed else 'failed',cases=rows,viable_bandwidths_hz=viable,
        complete_architecture=False,physical_qualification=False,
        limitations=['Two1MHz-grid carrier targets and one independent tone; wideband modulation remains untested.',
        'Reference loading, quantization, return-bus rail pulling and wired traffic are connected; device noise is absent.',
        'First-quarter complex gain calibration;10% provisional held-out waveform-error budget, not modem EVM.']),indent=2)+'\n')
    assert passed,'Fractional RF conversion quality exceeds candidate budget'
if __name__=='__main__':main()
