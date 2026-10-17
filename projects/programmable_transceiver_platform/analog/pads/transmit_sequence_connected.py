"""Replay actual RTL sequencer outputs into the retained extracted TX circuit.

Default replay prescribes analog_ready. With --ready-data, the previous analog
detector trace feeds the RTL for one sampled waveform-relaxation iteration.
Acceptance requires convergence and lifecycle coverage; RTL is not physically mapped.
"""
import argparse, hashlib, json, re, subprocess
from pathlib import Path
import numpy as np
from design import PROJECT
from screen import control, run_spice

TB='''`timescale 1ns/1ps
module replay;
reg clk=0,rst_n=1,supply_ok=1,commit=0,analog_ready=1;
reg[4:0]request=0;
wire command_ready,qualified,traffic_ready,buffer_request,fault;wire[4:0]active_request;
pt_tx_pad_sequence #(.PRE_CYCLES(2),.POST_CYCLES(2)) dut(.*);
always #2 clk=~clk;
initial begin
 $monitor("TRACE %0.3f %0d %0d %0d %0d %0d",$realtime,active_request,qualified,buffer_request,rst_n,traffic_ready);
 #0.01;rst_n=0;#0.09;rst_n=1;
 #3.9;request=4;commit=1;#4;commit=0;
 #23;rst_n=0;#0.5;rst_n=1;
 #0.5;supply_ok=0;#20.2;supply_ok=1;analog_ready=0;
 #17.8;request=17;commit=1;#4;commit=0;
 #36;analog_ready=1;
 #30;request=19;commit=1;#4;commit=0;
 #56;request=8;commit=1;#4;commit=0;
 #36;request=0;commit=1;#4;commit=0;
 #56;$finish;
end
endmodule
'''

def feedback_tb(data, scenario="transitions"):
    if scenario not in ("transitions", "hold-main", "hold-main-post", "hold-tmds"):
        raise ValueError("Unknown replay scenario")
    times=np.arange(1.,300.,4.)
    if data.suffix == '.json':
        seed=json.loads(data.read_text())
        if seed.get('scenario') != scenario or seed.get('feedback_sample_times_ns') != times.tolist():
            raise ValueError('Feedback seed scenario or sample times differ')
        raw=seed.get('feedback_output_values', [])
        if len(raw)!=len(times) or any(type(v) is not bool for v in raw):
            raise ValueError('Feedback seed must contain one boolean per detector sample')
        values=np.array(raw,dtype=bool)
    else:
        x=np.loadtxt(data,skiprows=1)
        if x.shape[1] not in (10,13) or x[-1,0]<299.99e-9:raise ValueError('Feedback requires complete readiness replay data')
        values=np.interp(times*1e-9,x[:,0],x[:,8])>2.31
    text=TB.replace('commit=0,analog_ready=1;', 'commit=0;reg measured_ready=0;')
    text=text.replace('pt_tx_pad_sequence #', 'wire analog_ready=active_request[4] ? measured_ready : 1\'b1;\npt_tx_pad_sequence #')
    text=text.replace(';analog_ready=0;', ';').replace('#36;analog_ready=1;', '#36;')
    schedule='send(17,70);send(19,140);send(8,200);send(0,240);'
    if scenario != 'transitions':
        request = {'hold-main':17,'hold-main-post':19,'hold-tmds':4}[scenario]
        schedule=f'send({request},70);wait(traffic_ready);#64;send(0,0);'
    text=re.sub(r'#17\.8;request=17;.*?#56;\$finish;',
                schedule,text,flags=re.S)
    task='''task send(input [4:0] value,input integer earliest_ns);
 begin
  if($realtime<earliest_ns) #(earliest_ns-$realtime);
  wait(command_ready);@(negedge clk);request=value;commit=1;
  @(negedge clk);commit=0;
 end
endtask
initial begin #300;$finish;end
'''
    text=text.replace('endmodule',task+'endmodule')
    events='initial begin\n'+''.join(f'#{1 if i==0 else 4};measured_ready={int(v)};\n' for i,v in enumerate(values))+'end\n'
    text=text.replace('endmodule',events+'always @(posedge clk) if(commit && !command_ready) $display("BUSY_COMMIT %0.3f",$realtime);\nendmodule')
    return text,times,values


def instrument_macro_supplies(deck):
    """Insert zero-volt probes only at top-level macro VDD ports."""
    deck=re.sub(r'\n\+\s*',' ',deck)
    definitions={line.split()[1]:line.split()[2:] for line in deck.splitlines()
                 if line.lower().startswith('.subckt ')}
    lines=[];probes=[];depth=0
    for line in deck.splitlines():
        fields=line.split()
        if fields and fields[0].lower()=='.subckt':depth+=1
        elif fields and fields[0].lower()=='.ends':depth-=1
        elif depth==0 and fields and fields[0].upper().startswith('X'):
            ports=definitions.get(fields[-1])
            if ports is None or len(fields)!=len(ports)+2:raise ValueError('Unknown top-level macro interface')
            if 'VDD' in ports:
                index=ports.index('VDD')+1
                if fields[index]!='VDD':raise ValueError('Unexpected macro supply domain')
                node='MEASURE_'+fields[0]+'_VDD';probe='VSUPPLY_'+fields[0]
                fields[index]=node;line=' '.join(fields)
                probes.append(dict(instance=fields[0],source=probe,node=node))
        lines.append(line)
    if not probes:raise ValueError('No macro supplies observed')
    lines.extend(f"{p['source']} VDD {p['node']} 0" for p in probes)
    return '\n'.join(lines)+'\n',probes


def macro_supply_summary(x,measured,probes,intervals):
    if measured.shape!=(len(x),len(probes)+1) or not np.isfinite(measured).all() or not np.array_equal(measured[:,0],x[:,0]):
        raise ValueError('Macro observations differ from lifecycle timebase')
    dt=np.diff(x[:,0]);modes={}
    for mode,windows in intervals.items():
        selected=np.zeros(len(dt),dtype=bool)
        for lo,hi in windows:selected|=(x[:-1,0]>=lo*1e-9)&(x[1:,0]<=hi*1e-9)
        weights=dt*selected;duration=float(weights.sum())
        if duration<=0:
            modes[mode]=dict(observed_duration_s=0,mean_currents_a=None);continue
        average=lambda v:float(np.sum((v[:-1]+v[1:])*.5*weights)/duration)
        currents={p['instance']:average(measured[:,i+1]) for i,p in enumerate(probes)}
        total=average(-x[:,6])
        modes[mode]=dict(observed_duration_s=duration,mean_currents_a=currents,
            mean_total_vdd_draw_a=total,mean_other_top_level_vdd_draw_a=total-sum(currents.values()))
    return dict(status='measured_macro_supply_currents_not_sustained_power_acceptance',modes=modes,
        probes=probes,scope='Positive current flows from VDD into each macro. Time-weighted means include only observed traffic-ready intervals. The remainder includes top-level bias passives; separate ideal source energy is not folded into VDD current. No package impedance, driver tuning or power-budget waiver.')


def ideal_drive_sources(deck):
    """Only top-level behavioral voltage drivers, excluding later observers."""
    sources=[];depth=0
    for line in deck.splitlines():
        fields=line.split()
        if not fields:continue
        if fields[0].lower()=='.subckt':depth+=1
        elif fields[0].lower()=='.ends':depth-=1
        elif depth==0 and fields[0].upper().startswith('B'):
            if len(fields)<4 or not fields[3].upper().startswith('V='):
                raise ValueError('Unsupported behavioral source observation: '+line)
            sources.append(dict(name=fields[0],positive=fields[1],negative=fields[2]))
    return sources


def ideal_drive_summary(data,sources):
    if data.ndim!=2 or data.shape[1]!=1+2*len(sources) or not np.isfinite(data).all():
        raise ValueError('Incomplete ideal-driver observations')
    time=data[:,0];duration=time[-1]-time[0]
    if duration<=0 or np.any(np.diff(time)<0):raise ValueError('Invalid observation times')
    integrate=np.trapezoid if hasattr(np,'trapezoid') else np.trapz
    results={}
    for index,source in enumerate(sources):
        voltage=data[:,1+index*2];current=data[:,2+index*2]
        delivered=-voltage*current
        results[source['name']]=dict(output_node=source['positive'],
            peak_absolute_current_a=float(np.max(abs(current))),
            delivered_energy_j=float(integrate(np.maximum(delivered,0),time)),
            absorbed_energy_j=float(integrate(np.maximum(-delivered,0),time)),
            net_delivered_energy_j=float(integrate(delivered,time)))
    return dict(status='ideal_driver_burden_not_physical_driver_power',observation_duration_s=float(duration),
        sources=results,total_positive_delivered_energy_j=sum(v['delivered_energy_j'] for v in results.values()),
        scope='Energy supplied by top-level ideal voltage drivers is not charged to VDD. This is a transient load burden, not actual driver dissipation or a sustained-data power budget. Positive and absorbed energy are separated; no energy recovery is assumed. Observers added by the replay are excluded.')


def brownout_summary(x, low):
    """Observe the retained supply transition, without inferring device safety."""
    if x.ndim != 2 or x.shape[1] != 13 or not np.isfinite(x).all():
        raise ValueError('Expected finite full connected TX waveform')
    mask=(x[:,12]>=.1)&(x[:,12]<low)
    y=x[mask]
    result=dict(status='observed_not_electrical_acceptance' if len(y) else 'not_reached',
                samples=len(y), duration_s=float(np.sum(np.diff(x[:,0])*mask[:-1])),
                scope='Includes rail ramps and undervoltage plateau. Supply qualification is behavioral; this is not physical supervisor or core-survival evidence.')
    if len(y):
        result.update(supply_min_v=float(y[:,12].min()),supply_max_v=float(y[:,12].max()),
            pad_min_v=float(y[:,10:12].min()),pad_max_v=float(y[:,10:12].max()),
            pad_above_local_supply_max_v=float(max(0,np.max(y[:,10:12]-y[:,12,None]))),
            pad_below_local_ground_max_v=float(max(0,-y[:,10:12].min())),
            qualified_max_v=float(y[:,3].max()),buffer_enable_max_v=float(y[:,4].max()),
            termination_enable_max_v=float(y[:,5].max()),traffic_ready_max_v=float(y[:,7].max()),
            peak_supply_draw_a=float(max(0,-y[:,6].min())),
            peak_supply_return_a=float(max(0,y[:,6].max())))
    return result


def refresh_brownout(report_path, waveform):
    """Reanalyze saved data; preserve the simulation's original source hashes."""
    report=json.loads(report_path.read_text())
    deck=waveform.with_suffix('.spice')
    expected=report['source_sha256'].get(str(deck.resolve()))
    if not expected or hashlib.sha256(deck.read_bytes()).hexdigest()!=expected:
        raise ValueError('Saved deck does not match recorded simulation')
    x=np.loadtxt(waveform,skiprows=1)
    if x[-1,0]<299.99e-9 or not report.get('transient_complete'):
        raise ValueError('Incomplete saved simulation')
    arch=PROJECT/'spec/analog-architecture.json'
    if hashlib.sha256(arch.read_bytes()).hexdigest()!=report['source_sha256'].get(str(arch)):
        raise ValueError('Shared architecture differs from recorded simulation')
    low=json.loads(arch.read_text())['blocks']['monitor']['parameters']['supply_window_v'][0]
    report['states']['brownout']=brownout_summary(x,low)
    report['brownout_reanalysis']=dict(
        scope='Postprocessing saved waveform, not a new simulation. Original source hashes retained. Waveform digest recorded at reanalysis, not at original simulation.',
        source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (waveform,deck,Path(__file__))})
    report_path.write_text(json.dumps(report,indent=2)+'\n')


def run(work,fixture,ready_data=None,scenario="transitions",spice_timeout_s=120):
    if scenario != "transitions" and ready_data is None:
        raise ValueError("Hold scenarios require sampled feedback input")
    work.mkdir(parents=True,exist_ok=False)
    component_sources={};external_network=None
    manifest_path=fixture.with_suffix('.json')
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text())
        if manifest.get('fixture_sha256')!=hashlib.sha256(fixture.read_bytes()).hexdigest():
            raise ValueError('Fixture differs from its build manifest')
        external_network=manifest.get('external_network')
        component_sources=manifest['source_sha256']
        for name,digest in component_sources.items():
            if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:
                raise ValueError('Stale composed fixture input: '+name)
        component_sources[str(manifest_path)]=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    rtl=PROJECT/'rtl/pt_tx_pad_sequence.sv';tb=work/'replay.sv'
    feedback=None
    if ready_data is not None:
        text,times,values=feedback_tb(ready_data,scenario);tb.write_text(text);feedback=(times,values)
    else:tb.write_text(TB)
    subprocess.run(['iverilog','-g2012','-s','replay','-o',str(work/'replay.vvp'),str(rtl),str(tb)],check=True,capture_output=True,text=True)
    result=subprocess.run(['vvp',str(work/'replay.vvp')],check=True,capture_output=True,text=True)
    (work/'rtl.log').write_text(result.stdout)
    rows=[]
    for l in result.stdout.splitlines():
        if l.startswith('TRACE '):
            f=l.split()[1:]
            if any(v.lower() in ('x','z') for v in f):continue
            rows.append([float(f[0])]+[int(v) for v in f[1:]])
    if not rows or rows[0][0]>0.1:raise ValueError('Missing initialized RTL trace')
    def wave(column,scale=1,bit=None,invert=False):
        events=[(0,0)];old=None
        for row in rows:
            value=row[column] if bit is None else (row[column]>>bit)&1
            if invert:value=1-value
            value*=scale
            if value!=old:
                t=row[0]
                if t==0:events=[(0,value)]
                else:events.extend([(t,events[-1][1]),(t+.02,value)])
                old=value
        events.append((300,events[-1][1]))
        return 'PWL('+' '.join(f'{t:g}n {v:g}' for t,v in events)+')'
    from loading_audit import anchor_floating_conductors
    deck, anchors = anchor_floating_conductors(fixture.read_text().split('.control')[0], 1e12)
    low,high=json.loads((PROJECT/'spec/analog-architecture.json').read_text())['blocks']['monitor']['parameters']['supply_window_v']
    replacements={'VTX_RESET':'VTX_RESET TX_RESET 0 '+wave(4,3.3,invert=True),
                  'VTX_QUALIFIED':'VTX_QUALIFIED TX_QUALIFIED 0 '+wave(2,3.3),
                  'VBUF_REQUEST':'VBUF_REQUEST BUF_REQUEST VSS '+wave(3,3.3),
                  'BBUF_ENABLE':f'BBUF_ENABLE BUF_ENABLE VSS V=V(BUF_REQUEST)*(V(VDD)>={low})*(V(VDD)<={high})'}
    for bit,n in enumerate(('MAIN','POST','TMDS','DETECT')):
        replacements['VEN_'+n]=f'VEN_{n} REQ_EN_{n} 0 '+wave(1,bit=bit)
    replacements['VTERM_ENABLE']='VTERM_ENABLE REQ_TERM_ENABLE 0 '+wave(1,3.3,bit=4)
    for name,new in replacements.items():
        deck,count=re.subn(r'^'+name+r' .*$',new,deck,flags=re.M)
        if count!=1:raise ValueError('Unexpected source '+name)
    deck,supply_probes=instrument_macro_supplies(deck)
    drive_sources=ideal_drive_sources(deck)
    deck+='VTRAFFIC_READY TRAFFIC_READY 0 '+wave(5,3.3)+'\n'
    architecture=json.loads((PROJECT/'spec/analog-architecture.json').read_text())
    readiness=architecture['blocks']['txpad']['parameters']['termination_readiness']
    error=readiness['max_reference_error_v'];tau=readiness['detector_time_constant_s'];threshold=readiness['detector_assert_threshold']
    if error<=0 or tau<=0 or not 0<threshold<1:raise ValueError('Invalid shared readiness parameters')
    deck+=f'BREADY_WINDOW READY_WINDOW 0 V=(abs(V(TERM_VCM)-V(BUF_REF))<={error})*(V(BUF_ENABLE)>1.65)\n'
    deck+=f'RREADY_FILTER READY_WINDOW READY_FILTER 1000\nCREADY_FILTER READY_FILTER 0 {tau/1000}\n'
    deck+=f'BMEASURED_READY MEASURED_READY 0 V=V(VDD)*(V(READY_FILTER)>={threshold})\n'
    deck+=control(work,'connected','tran 5p 300n','v(TERM_VCM) v(BUF_REF) v(TX_QUALIFIED) v(BUF_ENABLE) v(TERM_ENABLE) i(VDD) v(TRAFFIC_READY) v(MEASURED_READY) v(READY_WINDOW) v(PAD_P) v(PAD_N) v(VDD)')
    drive_vectors=' '.join((f"v({v['positive']})" if v['negative']=='0' else f"v({v['positive']},{v['negative']})")+f" i({v['name']})" for v in drive_sources)
    deck=deck.replace('\nquit\n',f'\nwrdata {work}/ideal-drive.dat {drive_vectors}\nquit\n')
    supply_vectors=' '.join(f"i({p['source']})" for p in supply_probes)
    deck=deck.replace('\nquit\n',f'\nwrdata {work}/macro-supply.dat {supply_vectors}\nquit\n')
    peer_present=bool(re.search(r'^VPEER ',deck,re.M))
    if peer_present:deck=deck.replace('\nquit\n',f'\nwrdata {work}/peer.dat v(BOARD_P) v(BOARD_N) i(VPEER)\nquit\n')
    x=run_spice(work,'connected',deck,reject_transient_op=True,timeout_s=spice_timeout_s)
    if not np.isfinite(x).all() or x[-1,0]<299.99e-9:raise ValueError('Incomplete connected replay')
    windows={}
    trace=np.array(rows)
    trace_indices=np.clip(np.searchsorted(trace[:,0]*1e-9,x[:,0],side='right')-1,0,len(trace)-1)
    actual_requests=trace[trace_indices,1].astype(int)
    for a,b in [(27,30),(36,43),(90,109),(125,139),(175,195),(225,239),(280,299)]:
        z=x[(x[:,0]>=a*1e-9)&(x[:,0]<=b*1e-9)]
        mode_mask=(x[:,0]>=a*1e-9)&(x[:,0]<=b*1e-9)
        windows[f'{a:g}-{b:g}ns']={'actual_request_values':sorted(set(map(int,actual_requests[mode_mask]))),'vcm_min_v':float(z[:,1].min()),'vcm_max_v':float(z[:,1].max()),'max_reference_error_v':float(abs(z[:,1]-z[:,2]).max()),'qualified_max_v':float(z[:,3].max()),'buffer_enable_max_v':float(z[:,4].max()),'termination_enable_max_v':float(z[:,5].max()),'traffic_ready_max_v':float(z[:,7].max()),'measured_ready_max_v':float(z[:,8].max())}
    loaded=(x[:,5]>2.31)&(x[:,3]>2.31)
    premature=loaded&(x[:,7]>2.31)&(x[:,8]<2.31)
    premature_s=float(np.sum(np.diff(x[:,0])*premature[:-1]))
    r={'observed_request_values':sorted({row[1] for row in rows}),'busy_commit_events':[l for l in result.stdout.splitlines() if l.startswith('BUSY_COMMIT')],'loaded_traffic_ready_without_detector_ready_s':premature_s,'readiness_parameters':readiness,'status':'RTL_to_extracted_TX_open_loop_replay','windows':windows,'scope':__doc__,'clock_period_ns':4,'pre_post_cycles':2,'edge_translation_ns':.02,'external_network_unchanged':True,'source_sha256':{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),rtl,tb,fixture,PROJECT/'spec/analog-architecture.json',work/'connected.spice']}}
    qualified_modes={int(row[1]) for row in rows if row[2]}
    traffic_modes={int(row[1]) for row in rows if row[5]}
    r['mode_coverage']={name:{'qualified':value in qualified_modes,'traffic_ready':value in traffic_modes} for name,value in [('TMDS',4),('MAIN',17),('MAIN_POST',19),('DETECT',8)]}
    r['source_sha256'].update(component_sources)
    r['spice_timeout_s']=spice_timeout_s
    r['transient_complete']=True
    r['states']={}
    r['external_network']=external_network
    peer=np.loadtxt(work/'peer.dat',skiprows=1) if peer_present else None
    if peer is not None and (peer.shape!=(len(x),4) or not np.isfinite(peer).all() or not np.array_equal(peer[:,0],x[:,0])):
        raise ValueError('External peer observations differ from lifecycle timebase')
    powered=x[:,12]>=low
    reset=trace[trace_indices,4]==0
    masks={'disabled':(actual_requests==0)&powered&~reset,
           'reset':reset&powered,'unpowered':x[:,12]<.1,
           'reconfiguration':(actual_requests!=0)&(x[:,3]<2.31)&powered&~reset}
    for name,request in [('active_tmds',4),('active_main',17),('active_main_post',19),('active_detect',8)]:
        masks[name]=(actual_requests==request)&(x[:,3]>2.31)&(x[:,7]>2.31)&powered
    for name,mask in masks.items():
        y=x[mask]
        r['states'][name]={'status':'observed_not_electrical_acceptance' if len(y) else 'not_reached',
                          'samples':len(y)}
        if len(y):r['states'][name].update(
            pad_min_v=float(y[:,10:12].min()),pad_max_v=float(y[:,10:12].max()),
            differential_min_v=float((y[:,10]-y[:,11]).min()),
            differential_max_v=float((y[:,10]-y[:,11]).max()),
            vcm_min_v=float(y[:,1].min()),vcm_max_v=float(y[:,1].max()),
            peak_supply_draw_a=float(max(0,-y[:,6].min())),
            peak_supply_return_a=float(max(0,y[:,6].max())))
    r['states']['brownout']=brownout_summary(x,low)
    if peer is not None:
        r['external_peer_states']={}
        masks['brownout']=(x[:,12]>=.1)&(x[:,12]<low)
        for name,mask in masks.items():
            y=peer[mask]
            if not len(y):continue
            weights=np.diff(x[:,0])*(mask[:-1]&mask[1:]);duration=float(weights.sum())
            draw=-peer[:,3]
            r['external_peer_states'][name]=dict(board_min_v=float(y[:,1:3].min()),board_max_v=float(y[:,1:3].max()),
                peer_peak_draw_a=float(max(0,-y[:,3].min())),peer_peak_return_a=float(max(0,y[:,3].max())),
                observed_duration_s=duration,peer_mean_draw_a=float(np.sum((draw[:-1]+draw[1:])*.5*weights)/duration) if duration else None)

    drive_data=np.loadtxt(work/'ideal-drive.dat',skiprows=1)
    if len(drive_data)!=len(x) or not np.array_equal(drive_data[:,0],x[:,0]):
        raise ValueError('Driver observations do not match lifecycle timebase')
    r['ideal_driver_burden']=ideal_drive_summary(drive_data,drive_sources)
    r['numerical_floating_conductor_anchors']=anchors
    r['operating_point_policy']='Reject transient operating-point fallback; numerical anchors are not physical resistors.'
    for helper in ['loading_audit.py','screen.py']:
        path=Path(__file__).with_name(helper)
        r['source_sha256'][str(path.resolve())]=hashlib.sha256(path.read_bytes()).hexdigest()
    r['scenario']=scenario
    r['traffic_ready_intervals_ns']={name:[[a[0],b[0]] for a,b in zip(rows,rows[1:]+[[300]]) if a[1]==value and a[5]] for name,value in [('TMDS',4),('MAIN',17),('MAIN_POST',19),('DETECT',8)]}
    supply_data=np.loadtxt(work/'macro-supply.dat',skiprows=1)
    r['macro_supply_currents']=macro_supply_summary(x,supply_data,supply_probes,r['traffic_ready_intervals_ns'])
    r['requested_loaded_hold_ns']=64 if scenario != 'transitions' else None
    r['disabled_end_observed']=bool(rows[-1][1]==0 and rows[-1][2]==0 and rows[-1][3]==0)
    if feedback is not None:
        times,values=feedback;new_values=np.interp(times*1e-9,x[:,0],x[:,8])>2.31
        r['status']='sampled_readiness_feedback_iteration_not_closed_loop_until_consistent'
        mismatches=np.flatnonzero(new_values!=values)
        r['feedback_sample_mismatches']=int(len(mismatches))
        r['first_feedback_mismatch_ns']=float(times[mismatches[0]]) if len(mismatches) else None
        r['consistent_prefix_sample_count']=int(mismatches[0]) if len(mismatches) else len(times)
        r['sampled_feedback_consistent']=not bool(len(mismatches))
        r['feedback_sample_times_ns']=times.tolist()
        r['feedback_output_values']=new_values.tolist()
        r['feedback_input_sha256']=hashlib.sha256(ready_data.read_bytes()).hexdigest()
        r['scope']='Prior analog detector trace sampled1ns before each RTL clock edge; one waveform-relaxation iteration. Zero feedback mismatches establishes sampled consistency only for this fixture. Busy commit events and missing configurations invalidate lifecycle coverage. Nontermination readiness is assumed true; detector and RTL physical implementation absent.'
    (work/'screen.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--fixture',type=Path,required=True)
    p.add_argument('--ready-data',type=Path)
    p.add_argument('--scenario',choices=['transitions','hold-main','hold-main-post','hold-tmds'],default='transitions')
    p.add_argument('--spice-timeout-s',type=float,default=120)
    a=p.parse_args();run(a.output_dir.resolve(),a.fixture.resolve(),a.ready_data.resolve() if a.ready_data else None,a.scenario,a.spice_timeout_s)
