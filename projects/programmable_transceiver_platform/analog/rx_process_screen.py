#!/usr/bin/env python3
"""Screen buffered receiver MOS process extremes at a fixed operating point."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
from rf_measure import projection

SRC=Path('/screen')
OUT=Path('/work')
def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

parser=argparse.ArgumentParser()
parser.add_argument('--corners',nargs='+',choices=('typical','ff','ss','fs','sf'),default=['ff','ss'])
args=parser.parse_args()
assert len(set(args.corners))==len(args.corners), 'duplicate process corner'

template=(SRC/'rx_branch_load_tb.spice.in').read_text()
cases=[]
for topology in args.corners:
    for amplitude in (0,.001):
        name=f'{topology}_{amplitude:g}'
        core=SRC/'rx_iq_buffered_core.spice'
        deck=template.replace('@CORE@',str(core)).replace('@AMPLITUDE@',str(amplitude)).replace('@DATA@',f'/work/{name}.dat')
        old='XDUT GATE MIX_RF SOURCE LOI LOIB LOQ LOQB IP IN QP QN 0 pt_rx_iq_core'
        assert deck.count(old)==1
        deck=deck.replace(old,'RDQ VDD DRAIN_Q 300\nRSOURCEQ SOURCE_Q 0 82\nXDUT GATE MIX_RF SOURCE DRAIN_Q SOURCE_Q LOI LOIB LOQ LOQB IP IN QP QN 0 pt_rx_iq_split')
        deck=deck.replace('idiff qdiff v(MIX_RF) i(VDD)','idiff qdiff v(MIX_RF) i(VDD) v(GATE) v(DRAIN_Q)')
        deck=deck.replace('VDD VDD 0 3.3','VDD VDD 0 3.3\nVDDL VDDL 0 3.3')
        deck=deck.replace('IP IN QP QN 0 pt_rx_iq_split','IP IN QP QN VDDL 0 pt_rx_iq_buffered')
        deck=deck.replace('v(GATE) v(DRAIN_Q)','v(GATE) v(DRAIN_Q) i(VDDL)')
        deck=deck.replace('sm141064.ngspice typical',f'sm141064.ngspice {topology}')
        assert '@' not in deck
        path=OUT/f'{name}.spice'
        path.write_text(deck)
        with (OUT/f'{name}.log').open('w') as log:
            run=subprocess.run(['ngspice','-b',str(path)],stdout=log,stderr=subprocess.STDOUT,timeout=600)
        assert run.returncode==0,name
        points=[tuple(map(float,line.split())) for line in (OUT/f'{name}.dat').read_text().splitlines()[1:]]
        assert all(len(p)==8 and all(map(math.isfinite,p)) for p in points)
        assert points[0][0]<1e-12 and points[-1][0]>300e-9
        ph=[[projection(points,col,a,b,freq) for col,freq in ((1,10e6),(2,10e6),(5,2.41e9))]
            for a,b in ((100e-9,200e-9),(200e-9,300e-9))]
        window=[p for p in points if 200e-9<=p[0]<=300e-9]
        current=-sum((b[0]-a[0])*(a[4]+b[4])/2 for a,b in zip(window,window[1:]))/(window[-1][0]-window[0][0])
        cases.append(dict(topology=topology,input_peak_v=amplitude,
            phasor_order=['IF_I','IF_Q','RF_GATE'],phasors_v=[[[z.real,z.imag] for z in row] for row in ph],
            drain_i_range_v=[min(p[3] for p in window),max(p[3] for p in window)],
            drain_q_range_v=[min(p[6] for p in window),max(p[6] for p in window)],
            average_vdd_current_a=current,
            lo_buffer_current_a=-sum((b[0]-a[0])*(a[7]+b[7])/2 for a,b in zip(window,window[1:]))/(window[-1][0]-window[0][0]),deck_sha256=digest(path)))
        print(name,[abs(z) for z in ph[-1]],current,flush=True)
summaries=[]
for topology in args.corners:
    zero,signal=[r for r in cases if r['topology']==topology]
    baseline=[complex(*v) for v in zero['phasors_v'][-1]]
    values=[complex(*v)-b for v,b in zip(signal['phasors_v'][-1],baseline)]
    i,q,gate=values
    summaries.append(dict(topology=topology,gain_i_v_per_v=abs(i)/.001,gain_q_v_per_v=abs(q)/.001,
        source_to_gate_v_per_v=abs(gate)/.001,
        q_relative_to_i_deg=math.degrees(math.atan2((q/i).imag,(q/i).real)),
        amplitude_imbalance_db=20*math.log10(abs(q/i)),
        zero_input_if_max_v=max(abs(baseline[0]),abs(baseline[1])),
        window_change_relative=max(abs(complex(*new)-complex(*old))/abs(value)
            for new,old,value in zip(signal['phasors_v'][-1],signal['phasors_v'][0],values)),
        average_vdd_current_a=signal['average_vdd_current_a'],
        lo_buffer_current_a=signal['lo_buffer_current_a'],
        measured_total_current_a=signal['average_vdd_current_a']+signal['lo_buffer_current_a']))
files=[Path(__file__),SRC/'rf_measure.py',SRC/'rx_branch_load_tb.spice.in',SRC/'rx_iq_buffered_core.spice',SRC/'lo_buffer.spice',SRC/'rx_iq_split_core.spice',
       Path('/src/rf_lna/lna_cs_core.spice'),Path('/src/rf_switch_mixer/mixer.spice')]
result=dict(status='simulation_completed_not_receiver_qualified',processes=args.corners,temperature_c=27,supply_v=3.3,
    rf_hz=2.41e9,lo_hz=2.4e9,if_hz=10e6,max_step_s=2e-12,cases=cases,summaries=summaries,
    image='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305',
    source_sha256={str(p):digest(p) for p in files},
    model_entry_sha256={name:digest(Path('/foss/pdks/gf180mcuD/libs.tech/ngspice')/name)
                        for name in ('design.ngspice','sm141064.ngspice','sm141064.spice')},
    limitations=['Ideal input quadrature source, bias and passives; four transistor LO buffers.',
                 'topology labels identify selected global MOS process corners, not mismatch/yield bounds.',
                 'One real 50-ohm source sees both LNA gates; no ideal isolated RF splitter.',
                 'Two full LNA cores with independent 300-ohm drain and 82-ohm source resistors.',
                 'No physical area estimate, noise/mismatch, PEX, input matching or linearity qualification.',
                 'Separate LNA and LO buffer currents; upstream oscillator/phase generator and bias power excluded.',
                 'Single-ended internal candidate; final differential RF interface and converters absent.'])
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(summaries,indent=2))
