"""Explicit converter clipping telemetry with valid saturated sample transport."""
import json,math,random
from chip_model import P,encode_iq,decode_iq
from diagnostic_lifecycle import DiagnosticChip
from playback_memory_lifecycle import ready
from whole_chip_lifecycle import expect_rejection


def controls():
    for mode in (0,1):
        c=DiagnosticChip();c.configure(mode,0);scale=1 << (c.bits-1)
        rng=random.Random(817)
        values=[complex(rng.uniform(-2,2),rng.uniform(-2,2)) for _ in range(1000)]
        values += [complex(x,0) for x in (-1,1,1-1/scale,1-.5/scale,-1-.5/scale)]
        for value in values:assert c.quantize_adc(value)==encode_iq(value,c.bits)
        before=dict(c.adc_diagnostics)
        expect_rejection(lambda:c.quantize_adc(complex(math.nan,0)))
        expect_rejection(lambda:c.quantize_adc(complex(0,math.inf)))
        assert c.adc_diagnostics==before
        c.clear_adc_diagnostics();assert not any(c.adc_diagnostics.values())
        for x in (-1,-1-.49/scale,-1-.5/scale,-1-.51/scale,1-1/scale,1-.51/scale,1-.5/scale):
            c.quantize_adc(complex(x,0))
        assert c.adc_diagnostics['i_low']==c.adc_diagnostics['i_high']==1
        assert c.adc_diagnostics['clipped_samples']==2


def run(mode,sign):
    c=DiagnosticChip(watchdog_s=20e-6,adc_latency_s=80e-9)
    c.configure_rx('external_tone',2,10e6,10e6,complex(1.5*sign,-1.5*sign),0)
    ready(c,mode);start=c.time+100e-9;c.capture(32,start,gain=1)
    c.advance(c.next_adc)
    assert c.adc_diagnostics['clipped_samples']==1 and not c.adc_words and c.capture_bank.count==0
    expect_rejection(c.clear_adc_diagnostics)
    c.advance(start+32*c.adc_period+2e-6);c.host_decoder.finish()
    assert len(c.host_samples)==32 and c.host_samples==c.adc_words and c.capture_bank.done
    d=c.diagnostic(c.time)['adc_quantization'];assert d['conversions']==d['clipped_samples']==32
    assert d['i_high' if sign>0 else 'i_low']==32 and d['q_low' if sign>0 else 'q_high']==32
    scale=1 << (c.bits-1)
    expected=complex(1-1/scale,-1) if sign>0 else complex(-1,1-1/scale)
    assert all(decode_iq(w,c.bits)==expected for w in c.adc_words)
    c.set_reference(False,c.time);c.acknowledge_host_abort(c.epoch,c.time);c.acknowledge_drain(c.epoch,c.time)
    assert c.adc_diagnostics==d
    c.clear_adc_diagnostics();assert not any(c.adc_diagnostics.values()) and d['clipped_samples']==32
    return dict(mode=mode,sign=sign,diagnostics=d,valid_saturated_samples=32)


def main():
    controls();rows=[run(m,s) for m in (0,1) for s in (-1,1)]
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        contract=['Round to nearest, ties to even; saturation is reported only if the rounded integer exceeds a code rail.',
        'Clipping preserves sample validity and conversion latency; per-component signed counts and clipped-sample count accumulate.',
        'Nonfinite input is rejected; diagnostics persist across receive epochs until explicitly cleared while disarmed.'],
        limitations=['Counters are named model diagnostics, not allocated hardware/SPI registers or per-sample host flags.',
        'Clipping threshold is a mathematical quantizer contract; comparator overload recovery and input common-mode limits remain unmodeled.',
        'DAC clipping/glitch and complete converter validity/operating envelopes remain open.'])
    (P/'evidence/connected-adc-clipping-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed four delayed saturated-conversion cases, rail/tie equivalence and diagnostic lifecycle controls')

if __name__=='__main__':main()
