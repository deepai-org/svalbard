"""Autonomous ideal-comparator SAR with reconstructed capacitors/reference memory.
Conditional mechanism screen, not the transistor controller or measured setup.
Usage: python sar_transfer.py MODE [WARMUP_SAMPLES] [REFERENCE_R_OHM] [nominal|span] [SAMPLER_JSON]
"""
import hashlib,json,sys
from pathlib import Path
import numpy as np
from reference_sequence import network,nodes,weights,widths,calibration,paths,root
mode=sys.argv[1] if len(sys.argv)>1 else 'ideal'
assert mode in ['ideal','plate_only','large_partition','small_partition']
count=1024;warmup=int(sys.argv[2]) if len(sys.argv)>2 else 128;tone_bin=511;period=100e-9;acquisition=10e-9;decision_interval=2.75e-9
reference_r=float(sys.argv[3]) if len(sys.argv)>3 else 1000.
assert np.isfinite(reference_r) and reference_r>0
charge_law=sys.argv[4] if len(sys.argv)>4 else 'nominal'
assert charge_law in ['nominal','span']
span_path=root/'evidence/reference-afe-cap-matrix-screen.json'
span_fits=json.loads(span_path.read_text())['reference_span_reduction']
charge_spans=[];charge_midpoints=[];extrapolated=0
amplitude=1.7*.9
sampler_path=Path(sys.argv[5]) if len(sys.argv)>5 else None
sampler=None;sample_common_mode=1.65
if sampler_path:
    sampler=json.loads(sampler_path.read_text())['dynamic_sampling'][0]
    held=sampler['held_samples_v']
    held_p=np.asarray(held['positive']);held_n=np.asarray(held['negative'])
    count=len(held_p);assert len(held_n)==count and count>0
    assert np.all(np.isfinite(held_p)) and np.all(np.isfinite(held_n))
    period=1/sampler['sample_hz']
    tone_bin=round(sampler['input_hz']*count*period)
    assert abs(tone_bin-sampler['input_hz']*count*period)<1e-8
    amplitude=2*sampler['single_ended_peak_v']
    assert max(abs(held_p-held_n))<1.7, 'Sampler waveform exceeds modeled ADC range'

state={n:(2.5 if n not in ['low','p','n'] else {'low':.8,'p':1.65,'n':1.65}[n]) for n in nodes}
status={f'{s}{i}':'high' for s in ['p','n'] for i in range(13)}
codes=[];ideal_code_errors=[];rail_samples=[];max_current=0.;max_residual=0.;max_rail_error=0.
decision_common_modes=[[] for _ in range(14)]
ideal=mode=='ideal'
def driven(sample=None):
    d={} if sample is None else {'p':sample_common_mode+sample/2,'n':sample_common_mode-sample/2}
    if ideal:d.update(high=2.5,low=.8)
    return d

def settle(state,seconds,sample=None):
    return network.relax(state,list(status.items()),{} if ideal else {'high':(2.5,reference_r),'low':(.8,reference_r)},seconds,driven(sample))

def overhead(bit,falling):
    global extrapolated
    if mode not in calibration:return {'high':0.,'low':0.}
    span=state['high']-state['low']
    charge_spans.append(span);charge_midpoints.append((state['high']+state['low'])/2)
    extrapolated+=int(not .5<=span<=2.3)
    scale=1.
    if charge_law=='span':
        transition='high_to_low' if falling else 'low_to_high'
        fit=next(r for r in span_fits if r['common_node']=='floating' and r['transition']==transition)
        a=fit['affine_intercept_pc'];b=fit['affine_slope_pf']
        scale=(a+b*span)/(a+b*1.7)
    return {r:-calibration[mode][falling][r]*widths[bit]/32*scale for r in ['high','low']}

for sample_index in range(-warmup,count):
    vin=amplitude*np.cos(2*np.pi*tone_bin*sample_index/count)
    if sampler is not None:
        index=sample_index%count
        vin=float(held_p[index]-held_n[index])
        sample_common_mode=float((held_p[index]+held_n[index])/2)
    # Ideal acquisition starts before reset restores bottom plates. Source charge
    # and finite references remain coupled through the actual plate network.
    state,_=network.redistribute(state,list(status.items()),driven(vin))
    injection={'high':0.,'low':0.}
    for node,rail in status.items():
        if rail=='low' and mode in calibration:
            extra=overhead(int(node[1:]),False)
            for r in injection:injection[r]+=extra[r]
        status[node]='high'
    state,_=network.redistribute(state,list(status.items()),driven(vin),injection)
    state=settle(state,acquisition,vin)
    decisions=[]
    for bit in range(14):
        state=settle(state,decision_interval)
        if sample_index>=0:
            cm=(state['p']+state['n'])/2
            decision_common_modes[bit].append(cm)
            if ideal:
                expected_cm=sample_common_mode-.5*1.7*sum(weights[:bit])/sum(weights)
                assert abs(cm-expected_cm)<1e-10
        sign=1 if state['p']>=state['n'] else -1
        decisions.append(sign)
        if bit<13:
            status[f'{"p" if sign>0 else "n"}{bit}']='low'
            injection=overhead(bit,True)
            state,_=network.redistribute(state,list(status.items()),driven(),injection)
        if not ideal:max_current=max(max_current,abs(2.5-state['high'])/reference_r*1e6,abs(.8-state['low'])/reference_r*1e6)
    if sample_index>=0:
        codes.append(sum(sign*2**(13-bit) for bit,sign in enumerate(decisions)))
        if ideal:
            residual=vin;expected=0
            for bit in range(14):
                sign=1 if residual>=0 else -1
                expected+=sign*2**(13-bit)
                if bit<13:residual-=sign*weights[bit]/sum(weights)*1.7
            ideal_code_errors.append(abs(codes[-1]-expected))
            assert abs(codes[-1]-expected)<=2  # At most one output LSB at numerical ties.
        rail_samples.append([state['high'],state['low']])
        max_residual=max(max_residual,abs(state['p']-state['n']))
        max_rail_error=max(max_rail_error,abs(2.5-state['high']),abs(.8-state['low']))
    state=settle(state,period-acquisition-14*decision_interval)

spectrum=abs(np.fft.rfft(codes));fundamental=spectrum[tone_bin]
mask=np.ones(len(spectrum),dtype=bool);mask[[0,tone_bin]]=False
power=sum(spectrum[mask]**2)
# All bins exceptNyquist occur as complex conjugate pairs in a real FFT.
power-=spectrum[-1]**2/2
harmonics=[]
for h in [3,5,7]:
    index=(h*tone_bin)%count;index=min(index,count-index)
    harmonics.append(float(20*np.log10(max(spectrum[index],1e-30)/fundamental)))
print(json.dumps(dict(decision_input_common_mode_ranges_v=[[float(min(v)),float(max(v))] for v in decision_common_modes],sampler_source_sha256=hashlib.sha256(sampler_path.read_bytes()).hexdigest() if sampler_path else None,sampler_connection="One-way periodic held-waveform replay; no CDAC feedback into sampler" if sampler_path else None,switch_charge_law=charge_law,charge_evaluation_span_range_v=[min(charge_spans),max(charge_spans)] if charge_spans else None,maximum_charge_midpoint_deviation_v=max(abs(v-1.65) for v in charge_midpoints) if charge_midpoints else None,span_extrapolation_evaluations=extrapolated,reference_resistance_ohm=None if ideal else reference_r,ideal_scalar_max_code_difference=max(ideal_code_errors) if ideal_code_errors else None,mode=mode,samples=count,warmup_samples=warmup,sample_rate_msps=1/period/1e6,tone_frequency_mhz=tone_bin/count/period/1e6,
 input_differential_peak_v=amplitude,ideal_comparator=True,acquisition_ns=acquisition*1e9,decision_interval_ns=decision_interval*1e9,
 noiseless_sndr_db=float(10*np.log10(fundamental**2/power)),sfdr_db=float(20*np.log10(fundamental/max(spectrum[mask]))),harmonics_3_5_7_dbc=harmonics,
 maximum_final_comparator_residual_mv=max_residual*1000,maximum_decision_sampled_source_current_ua=max_current,maximum_end_conversion_rail_error_mv=max_rail_error*1000,
 reference_span_range_v=[float(min(h-l for h,l in rail_samples)),float(max(h-l for h,l in rail_samples))],
 source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in list(paths.values())+[span_path,root/'system_model/connected/capacitor_network.py',Path(__file__).with_name('reference_sequence.py'),Path(__file__)]},
 limitations=['Autonomous ideal-sign decisions with fixed timing and natural binary output; no preamp/comparator noise,offset,kickback or metastability. Not the recovered transistor timing model.',
 'Ideal top-plate acquisition, area-only caps,100pF rails. Finite modes use the stated linear source resistance and conditional charge impulses; no real bootstrap/full capacitance matrix.',
 'Tone and sample rate approximateFigure7, but amplitude90percent of modeled range and references2.5/0.8V are scenarios, not recovered characterization settings.',
 'Switch charge uses nominal or span-adjusted endpoint law as reported. The span fit was characterized at fixed1.65V midpoint; midpoint and rail-partition variation remain unmodeled. Drawn-width scaling is conditional.',
 'Optional sampler replay preserves both held legs but ideal-clamps them during acquisition. It omits bidirectional loading, reset interaction and common-mode sensitivity of a real comparator. Its periodic record is an assigned steady-state input.',
 'No silicon fit or standards claim; inspect discrepancies, not just completed conversions.']),indent=2))
