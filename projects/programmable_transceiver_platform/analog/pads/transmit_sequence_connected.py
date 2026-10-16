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
    if scenario not in ("transitions", "hold-main", "hold-main-post"):
        raise ValueError("Unknown replay scenario")
    x=np.loadtxt(data,skiprows=1)
    if x.shape[1]!=10 or x[-1,0]<299.99e-9:raise ValueError('Feedback requires complete readiness replay data')
    times=np.arange(1.,300.,4.)
    values=np.interp(times*1e-9,x[:,0],x[:,8])>2.31
    text=TB.replace('commit=0,analog_ready=1;', 'commit=0;reg measured_ready=0;')
    text=text.replace('pt_tx_pad_sequence #', 'wire analog_ready=active_request[4] ? measured_ready : 1\'b1;\npt_tx_pad_sequence #')
    text=text.replace(';analog_ready=0;', ';').replace('#36;analog_ready=1;', '#36;')
    schedule='send(17,70);send(19,140);send(8,200);send(0,240);'
    if scenario != 'transitions':
        request = 17 if scenario == 'hold-main' else 19
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


def run(work,fixture,ready_data=None,scenario="transitions"):
    if scenario != "transitions" and ready_data is None:
        raise ValueError("Hold scenarios require sampled feedback input")
    work.mkdir(parents=True,exist_ok=False)
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
    deck=fixture.read_text().split('.control')[0]
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
    deck+='VTRAFFIC_READY TRAFFIC_READY 0 '+wave(5,3.3)+'\n'
    architecture=json.loads((PROJECT/'spec/analog-architecture.json').read_text())
    readiness=architecture['blocks']['txpad']['parameters']['termination_readiness']
    error=readiness['max_reference_error_v'];tau=readiness['detector_time_constant_s'];threshold=readiness['detector_assert_threshold']
    if error<=0 or tau<=0 or not 0<threshold<1:raise ValueError('Invalid shared readiness parameters')
    deck+=f'BREADY_WINDOW READY_WINDOW 0 V=(abs(V(TERM_VCM)-V(BUF_REF))<={error})*(V(BUF_ENABLE)>1.65)\n'
    deck+=f'RREADY_FILTER READY_WINDOW READY_FILTER 1000\nCREADY_FILTER READY_FILTER 0 {tau/1000}\n'
    deck+=f'BMEASURED_READY MEASURED_READY 0 V=V(VDD)*(V(READY_FILTER)>={threshold})\n'
    deck+=control(work,'connected','tran 5p 300n','v(TERM_VCM) v(BUF_REF) v(TX_QUALIFIED) v(BUF_ENABLE) v(TERM_ENABLE) i(VDD) v(TRAFFIC_READY) v(MEASURED_READY) v(READY_WINDOW)')
    x=run_spice(work,'connected',deck)
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
    r['scenario']=scenario
    r['traffic_ready_intervals_ns']={name:[[a[0],b[0]] for a,b in zip(rows,rows[1:]+[[300]]) if a[1]==value and a[5]] for name,value in [('TMDS',4),('MAIN',17),('MAIN_POST',19),('DETECT',8)]}
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
        r['feedback_input_sha256']=hashlib.sha256(ready_data.read_bytes()).hexdigest()
        r['scope']='Prior analog detector trace sampled1ns before each RTL clock edge; one waveform-relaxation iteration. Zero feedback mismatches establishes sampled consistency only for this fixture. Busy commit events and missing configurations invalidate lifecycle coverage. Nontermination readiness is assumed true; detector and RTL physical implementation absent.'
    (work/'screen.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--fixture',type=Path,required=True)
    p.add_argument('--ready-data',type=Path)
    p.add_argument('--scenario',choices=['transitions','hold-main','hold-main-post'],default='transitions')
    a=p.parse_args();run(a.output_dir.resolve(),a.fixture.resolve(),a.ready_data.resolve() if a.ready_data else None,a.scenario)
