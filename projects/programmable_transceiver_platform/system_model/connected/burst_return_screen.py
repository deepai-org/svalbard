"""Finite RF bursts through timed shared return transport and real frame staging."""
import hashlib,json
from pathlib import Path
from chip_model import return_samples,P
from burst_codec import controls

controls();cases=[]
for mode,width,period in ((0,24,6.25),(1,16,15.625)):
    for count in (0,1,2,3,4,5,7,13,31,129):
        samples=[((i*7919)^0xabcdef)&((1<<width)-1) for i in range(count)]
        ticks=[17+i*period for i in range(count)]
        wires=[(i*53)&1023 for i in range(100)]
        wticks=[i*(2 if mode==0 else 1.25) for i in range(100)]
        received=[];arrivals=[]
        report=return_samples(mode,samples,ticks,width,wires,wticks,
            capture=received,capture_ticks=arrivals,burst_count=count)
        assert received==samples and len(arrivals)==count
        assert all(a>=b for a,b in zip(arrivals,ticks))
        # Aligned streams must retain exact prior arrival timing.
        if count*width%10==0:
            original=[];original_ticks=[]
            return_samples(mode,samples,ticks,width,wires,wticks,
                capture=original,capture_ticks=original_ticks)
            assert original==received and original_ticks==arrivals
        cases.append(dict(mode=mode,count=count,transport=report))
    empty=return_samples(mode,[],[],width,[],[],burst_count=0)
    assert empty['maximum_adc_to_host_delay_ticks'] is None
# A delayed last sample must delay its padded-word release, not merely scoring.
a=[];b=[]
return_samples(0,[1],[17],24,[],[],burst_count=1,capture_ticks=a)
return_samples(0,[1],[1000],24,[],[],burst_count=1,capture_ticks=b)
assert b[0]>a[0] and b[0]>=1000
# An allowed near-capacity burst takes more than the old eight-frame tail.
near=[]
for mode,width,count in ((0,24,42),(1,16,63)):
    values=list(range(count));delivered=[]
    result=return_samples(mode,values,[0]*count,width,[],[],burst_count=count,capture=delivered)
    assert delivered==values and result['peak_ingress_bits']['iq']==1010
    near.append(dict(mode=mode,count=count,transport=result))
    try:return_samples(mode,list(range(count+1)),[0]*(count+1),width,[],[],burst_count=count+1)
    except AssertionError as error:
        assert 'capacity exceeded' in str(error)
    else:raise AssertionError('Over-capacity burst was accepted')
# Exercise integer and just-after-tick arrivals over a complete frame. Both
# queues start near capacity; static quotas must preserve each source exactly.
phases=[]
for mode,width,count in ((0,24,42),(1,16,63)):
    for position in range(64):
        for fraction in (0,.25):
            phase=position+fraction
            values=list(reversed(range(count)));wires=[(i*97)&1023 for i in range(102)]
            delivered=[];ticks=[]
            result=return_samples(mode,values,[phase]*count,width,wires,[phase]*102,
                burst_count=count,capture=delivered,capture_ticks=ticks)
            assert delivered==values
            assert result['peak_ingress_bits']=={'wire':1020,'iq':1010}
            assert max(ticks)-phase < 64*result['drain_bound_frames']
            phases.append(dict(mode=mode,phase_ticks=phase,
                last_sample_delay_ticks=max(ticks)-phase,
                drain_bound_frames=result['drain_bound_frames']))
files=[Path(__file__),Path(__file__).with_name('loopback_return.py'),Path(__file__).with_name('burst_codec.py'),P/'verification/stream_codec.py',P/'verification/transport_model.py']
report=dict(status='passed',complete_architecture=False,cases=cases,near_capacity_bursts=near,near_capacity_phase_sweep=phases,
    late_final_sample_control=dict(early_delivery_tick=a[0],late_delivery_tick=b[0]),
    source_hashes={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
    limitations=['One predeclared burst per invocation; descriptor transport and back-to-back epochs remain open.',
      'Timed payload return only; ADC analog waveform, host stalls and reset interactions are not exercised here.',
      'Service-derived drain bound assumes the static frame quotas and no host stalls.'])
(P/'evidence/connected-burst-return.json').write_text(json.dumps(report,indent=2)+'\n')
print('20 timed bursts and256 dual-queue near-capacity phase cases pass')
