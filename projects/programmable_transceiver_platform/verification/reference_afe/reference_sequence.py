"""Fast forced-sequence comparison against recovered two-conversion MOS replay.
No autonomous decisions: uses measured-in-simulation stage times and stored words.
Reference source values and capacitor geometry are conditional, not silicon fits.
"""
import hashlib,json,sys
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'system_model/connected'))
from capacitor_network import CapacitorNetwork
paths={n:root/'evidence'/('reference-afe-'+n+'.json') for n in ['cap-geometry','controller-references','reference-transient','reference-drivers']}
data={n:json.loads(p.read_text()) for n,p in paths.items()}
reference=data['controller-references']['repeated_conversion_1kohm']
weights=[data['cap-geometry']['bit_geometry'][f'B{i}']['m3_m4_overlap_um2']*.0394e-15 for i in range(13)]
widths=[next(r['nmos_w_um'] for r in data['reference-drivers']['drivers'] if r['array_index']==0 and r['bit_label']==f'B{i}') for i in range(13)]
nodes=['high','low','p','n']+[f'{s}{i}' for s in ['p','n'] for i in range(13)]
branches=[('high',None,100e-12),('low',None,100e-12)]+[(s,f'{s}{i}',c) for s in ['p','n'] for i,c in enumerate(weights)]
network=CapacitorNetwork(nodes,branches)
# Independent injection sign/group conservation check, not sequence validation.
check=CapacitorNetwork(['a','b'],[('a',None,1e-12),('b',None,3e-12)])
v,q=check.redistribute({'a':1.,'b':1.},[('a','b')],injected_charge={'a':2e-12})
assert abs(v['a']-1.5)<1e-14 and abs(sum(q.values())-2e-12)<1e-25
# Nominal endpoint overhead split: subtract ideal plate charge from selected rail.
calibration={}
for mode in ['large_partition','small_partition']:
    calibration[mode]={}
    for falling in [False,True]:
        transition='high_to_low' if falling else 'low_to_high'
        if mode=='large_partition':
            replay=data['reference-transient']['high_to_low_replay'] if falling else data['reference-transient']
            row=replay['cases'][-2];ideal=.375*1.7;scale=1
        else:
            row=next(r for r in data['reference-transient']['small_bit_replay']['cases'] if r['bit_label']=='B12' and r['common_node']=='floating' and r['transition']==transition)
            ideal=row['ideal_plate_switching_charge_pc'];scale=4
        q={rail:row['reference_charge_5_to_20ns'][rail]['net_charge_to_switch_network_pc'] for rail in ['high','low']}
        q['low' if falling else 'high']-=(-1 if falling else 1)*ideal
        calibration[mode][falling]={rail:value*scale*1e-12 for rail,value in q.items()}
if __name__=='__main__':
    results=[]
    for mode in ['plate_only','large_partition','small_partition']:
     for delay_ns in [0,.4,.8]:
        state={n:(2.5 if n not in ['low','p','n'] else {'low':.8,'p':1.655,'n':1.645}[n]) for n in nodes}
        status={f'{s}{i}':'high' for s in ['p','n'] for i in range(13)}
        def connections():return list(status.items())
        driven={};time=5.1;events=[];observations=[];injected_total=0.;max_current=0.
        for cycle_no,cycle in enumerate(reference['cycles']):
            for i,word in enumerate(cycle['stored_positive_decisions'][:13]):
                events.append((cycle['stage_rises_ns'][i][0]+delay_ns,'switch',(i,'p' if word else 'n')))
            for i,t in enumerate(cycle['valid_rises_ns']):events.append((t,'observe',(cycle_no,i)))
        events += [(50.1,'sample',None),(50.1+delay_ns,'reset',None),(55.1,'release',None)]
        events.sort(key=lambda e:(e[0],{'sample':0,'reset':1,'release':2,'switch':3,'observe':4}[e[1]]))
        for t,action,payload in events:
            assert t>=time
            state=network.relax(state,connections(),{'high':(2.5,1000),'low':(.8,1000)},(t-time)*1e-9,driven)
            time=t
            injection={rail:0. for rail in ['high','low']}
            if action=='sample':driven={'p':1.655,'n':1.645}
            elif action=='release':driven={}
            elif action=='switch':
                bit,side=payload;status[f'{side}{bit}']='low'
                if mode!='plate_only':injection={rail:-calibration[mode][True][rail]*widths[bit]/32 for rail in injection}
            elif action=='reset':
                for node,rail in status.items():
                    if rail=='low' and mode!='plate_only':
                        bit=int(node[1:])
                        for r in injection:injection[r]-=calibration[mode][False][r]*widths[bit]/32
                    status[node]='high'
            if action!='observe':
                state,_=network.redistribute(state,connections(),driven,injection)
                injected_total+=sum(injection.values())
            else:
                cycle_no,i=payload;truth=reference['cycles'][cycle_no]['reference_voltages_at_valid_edges'][i]
                observations.append(dict(cycle=cycle_no,decision=i,high_v=state['high'],low_v=state['low'],transistor_high_v=truth[0],transistor_low_v=truth[1]))
            max_current=max(max_current,abs(2.5-state['high'])/1000*1e6,abs(.8-state['low'])/1000*1e6)
        errors=[(r[rail+'_v']-r['transistor_'+rail+'_v'])*1000 for r in observations for rail in ['high','low']]
        results.append(dict(mode=mode,driver_delay_ns=delay_ns,reference_error_rms_mv=float(np.sqrt(np.mean(np.square(errors)))),reference_error_max_mv=max(map(abs,errors)),maximum_event_sampled_source_current_ua=max_current,
            net_injected_reference_charge_pc=injected_total*1e12,opposite_gate_body_charge_pc=-injected_total*1e12,
            observations=observations))
    print(json.dumps(dict(cases=results,source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in list(paths.values())+[root/'system_model/connected/capacitor_network.py',Path(__file__)]},
     limitations=['Forced measured-in-simulation stage times and words: not autonomous SAR or ADC accuracy validation.',
     'Area-only capacitors, ideal switches/sampling, linear1kohm reference recovery. Peak source current is checked at events, not certified over continuous time.',
     'Overhead impulses calibrated from10ohm isolated-switch endpoints, scaled by drawn width at nominal span; no nonlinear instantaneous span correction or preamp loading.',
     'All reset transitions assigned one event while sample held. Delay0/0.4/0.8ns is a sensitivity, not recovered gate timing.',
     'Gate/body countercharge is an accounting ledger, not simulated supply impedance. Reference rail partition is bracketed by large/small-driver calibrations; no silicon fit.']),indent=2))
