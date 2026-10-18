"""Physical rail-window detector candidate; not a complete safety supervisor.

Reference and reset are explicit inputs. No behavioral voltage comparator or
ideal bias source is hidden in the circuit. Readiness, hysteresis, reference
startup and final-enable fanout remain separate implementation requirements.
"""
import math
from dataclasses import dataclass
from circuits import Circuit,Mos,Resistor


@dataclass(frozen=True)
class Junction:
    name: str
    nodes: tuple
    model: str = 'pnp_05p00x05p00'

    def spice(self):return f"X{self.name} {' '.join(self.nodes)} {self.model}"


def build(*, independent_floor=True, floor_ratio=3.55, floor_kind='junction', output_bleed_ohm=100000):
    if floor_kind not in ('mos','junction'):raise ValueError('Unknown floor reference')
    if not math.isfinite(floor_ratio) or floor_ratio<=1:raise ValueError('Floor divider ratio must exceed one')
    if not math.isfinite(output_bleed_ohm) or output_bleed_ohm<=0:raise ValueError('Positive output discharge resistance required')
    devices=[]
    def mos(name,nodes,kind,w,l=.5):devices.append(Mos(name,tuple(nodes.split()),kind,w,l))
    def resistor(name,a,b,ohm):
        count=max(1,int(math.ceil(ohm/12500)))
        for i in range(count):
            end=b if i==count-1 else name+'_R'+str(i)
            devices.append(Resistor(name+'_'+str(i),(a,end,'VSS'),'ppolyf_u_1k',1.,ohm/count/1000));a=end
    def inv(name,source,dest):
        mos(name+'N',f'{dest} {source} VSS VSS','nfet_03v3',2.,.28)
        mos(name+'P',f'{dest} {source} VDD VDD','pfet_03v3',4.,.28)
    resistor('BIAS','VDD','BIAS',100000)
    mos('BIAS_DIODE','BIAS BIAS VSS VSS','nfet_03v3',2.,1.)
    for name,ratio,a,b in (('LOW',2.55,'SENSE_LOW','VREF'),('HIGH',3.45,'VREF','SENSE_HIGH')):
        sense='SENSE_'+name
        resistor(name+'_TOP','VDD',sense,(ratio-1)*100000)
        resistor(name+'_BOTTOM',sense,'VSS',100000)
        mos(name+'_A',f'{name}_MIR {a} {name}_TAIL VSS','nfet_03v3',8.,.5)
        mos(name+'_B',f'{name}_GAIN {b} {name}_TAIL VSS','nfet_03v3',8.,.5)
        mos(name+'_M0',f'{name}_MIR {name}_MIR VDD VDD','pfet_03v3',16.,.5)
        mos(name+'_M1',f'{name}_GAIN {name}_MIR VDD VDD','pfet_03v3',16.,.5)
        mos(name+'_TAIL',f'{name}_TAIL BIAS VSS VSS','nfet_03v3',2.,1.)
        inv(name+'_I0',name+'_GAIN',name+'_B')
        inv(name+'_I1',name+'_B',name+'_OK')
    # A collapsing reference must not scale the allowed supply down with it.
    # This independent threshold-based veto still needs process/trim qualification.
    gates=['LOW_OK','HIGH_OK','RESET_N']
    if independent_floor:
        resistor('FLOOR_TOP','VDD','FLOOR_SENSE',(floor_ratio-1)*100000)
        resistor('FLOOR_BOTTOM','FLOOR_SENSE','VSS',100000)
        if floor_kind=='mos':
            resistor('FLOOR_PULL','VDD','FLOOR_B',100000)
            mos('FLOOR_SENSE','FLOOR_B FLOOR_SENSE VSS VSS','nfet_03v3',8.,1.)
            inv('FLOOR_INV','FLOOR_B','FLOOR_OK')
        else:
            # Grounded collector/base VPNP: no floating substrate assumption.
            resistor('JUNCTION_FEED','VDD','VBE',100000)
            devices.append(Junction('FLOOR_JUNCTION',('VSS','VSS','VBE')))
            resistor('FLOOR_BIAS','PBIAS','VSS',100000)
            mos('PBIAS_DIODE','PBIAS PBIAS VDD VDD','pfet_03v3',4.,1.)
            mos('FLOOR_TAIL','PTAIL PBIAS VDD VDD','pfet_03v3',4.,1.)
            # PMOS input pair permits the roughly 0.65 V input common mode.
            mos('FLOOR_A','FMIR FLOOR_SENSE PTAIL VDD','pfet_03v3',16.,.5)
            mos('FLOOR_B','FGAIN VBE PTAIL VDD','pfet_03v3',16.,.5)
            mos('FLOOR_M0','FMIR FMIR VSS VSS','nfet_03v3',8.,.5)
            mos('FLOOR_M1','FGAIN FMIR VSS VSS','nfet_03v3',8.,.5)
            inv('FLOOR_I0','FGAIN','FLOOR_B')
            inv('FLOOR_I1','FLOOR_B','FLOOR_OK')
        gates.append('FLOOR_OK')
    # NAND followed by inverter: every permission and reset release are required.
    for i,gate in enumerate(gates):
        source='VSS' if i==len(gates)-1 else 'NAND_S'+str(i)
        drain='OK_B' if i==0 else 'NAND_S'+str(i-1)
        mos('VALID_N'+str(i),f'{drain} {gate} {source} VSS','nfet_03v3',6.,.28)
        mos('VALID_P'+str(i),f'OK_B {gate} VDD VDD','pfet_03v3',4.,.28)
    inv('FINAL','OK_B','RAIL_OK')
    resistor('DEFAULT_OFF','RAIL_OK','VSS',output_bleed_ohm)
    return Circuit('rail_window_candidate',['VDD','VSS','VREF','RESET_N','RAIL_OK'],devices,
        dict(reference_nominal_v=1.,nominal_ratio_window=[2.55,3.45],independent_floor=independent_floor,floor_ratio=floor_ratio,floor_kind=floor_kind,output_bleed_ohm=output_bleed_ohm),[
            'Device-model schematic only; comparator offset/headroom move the actual trip levels.',
            'VREF and RESET_N are explicit inputs; reference startup, overshoot and unpowered behavior require integration.',
            'The junction floor uses a grounded-base/collector VPNP and PMOS-input comparator; MOS floor remains an explicit rejected control. No hysteresis or low-voltage clamp is qualified.',
            'No hysteresis or startup hold; RAIL_OK is permission for a separate readiness sequencer, never traffic readiness.',
            'No routing/parasitics, final pad-enable load or protection coordination is included.'])


def screen(work,pdk,*,reuse_dc=False,floor_kind='junction',floor_ratio=3.55,bjt_corners=('typical','ff','ss')):
    import hashlib,json,os
    from pathlib import Path
    import numpy as np
    from screen import header,control,run_spice
    if any(c not in ('typical','ff','ss') for c in bjt_corners):raise ValueError('Unknown BJT corner')
    if floor_kind=='mos':bjt_corners=('typical',)
    work=Path(work).resolve();pdk=Path(pdk).resolve();work.mkdir(parents=True,exist_ok=True)
    (work/'.spiceinit').write_text('set ngbehavior=hs\n');previous=Path.cwd();results=[]
    try:
        os.chdir(work)
        cases=[('typical',False,3.3,'typical'),*[(c,True,3.3,b) for c in ('typical','ff','ss','fs','sf') for b in bjt_corners],('typical',True,0.,'typical')]
        for corner,floor,reset,bjt in cases:
            name=f'{corner}_{int(floor)}_{reset}'+('_'+bjt if floor_kind=='junction' else '')
            c=build(independent_floor=floor,floor_kind=floor_kind,floor_ratio=floor_ratio)
            deck=header(c,pdk).replace('sm141064.ngspice typical','sm141064.ngspice '+corner)
            if floor_kind=='junction':deck+=f'.lib {pdk}/sm141064.spice bjt_{bjt}\n'
            deck+='VDD VDD 0 3.3\nVREF VREF 0 1\n'+f'VRESET RESET_N 0 {reset}\nCLOAD RAIL_OK 0 500f\n'
            deck+=control(work,name,'dc VDD 0 3.6 .025 VREF 0 1.2 .2','v(VDD) v(VREF) v(RAIL_OK) i(VDD)')
            if reuse_dc:
                if (work/(name+'.spice')).read_text()!=deck:raise ValueError('Saved deck differs from current circuit: '+name)
                if 'Transient op started' in (work/(name+'.log')).read_text():raise ValueError('Saved DC used transient initialization')
                x=np.loadtxt(work/(name+'.dat'),skiprows=1)
            else:x=run_spice(work,name,deck,reject_transient_op=True,timeout_s=120)
            if len(x)!=145*7 or not np.isfinite(x).all():raise ValueError('Incomplete DC grid')
            references=[]
            for ref in np.arange(7)*.2:
                y=x[np.isclose(x[:,2],ref,atol=1e-8)]
                if len(y)!=145:raise ValueError('Missing reference slice')
                high=(y[:,1]>.1)&(y[:,3]>.7*y[:,1]);indices=np.flatnonzero(high)
                groups=np.split(indices,np.where(np.diff(indices)>1)[0]+1) if len(indices) else []
                intervals=[[float(y[g[0],1]),float(y[g[-1],1])] for g in groups]
                references.append(dict(reference_v=float(ref),logic_high_supply_intervals_v=intervals,
                    undervoltage_assertion=bool(np.any(high&(y[:,1]<2.5-1e-8))),
                    output_at_3p3_v=float(y[np.argmin(abs(y[:,1]-3.3)),3])))
            results.append(dict(corner=corner,bjt_corner=bjt if floor_kind=="junction" else None,independent_floor=floor,reset_v=reset,references=references,
                max_supply_current_a=float(max(-x[:,4])),max_output_v=float(max(x[:,3])),
                dc_complete=True,deck_sha256=hashlib.sha256(deck.encode()).hexdigest()))
    finally:os.chdir(previous)
    unsafe=[r['corner']+('/'+str(r['bjt_corner']) if r['bjt_corner'] else '') for r in results if r['independent_floor'] and r['reset_v']>0 and any(x['undervoltage_assertion'] for x in r['references'])]
    return dict(status='rejected_undervoltage_veto' if unsafe else 'dc_window_candidate_not_transient_qualified',floor_kind=floor_kind,
        unsafe_guarded_corners=unsafe,
        decision=('Do not connect this candidate to pad enables: the independent floor still permits undervoltage in tested corners.' if unsafe else 'DC corner screen completed without detected undervoltage permission. Do not connect to pad enables before reference/supply startup, brownout, hysteresis, final loads, mismatch and layout are qualified.'),results=results,
        temperature_c=27,reference_grid_step_v=.2,supply_grid_step_v=.025,
        scope='Transistor/resistor DC corner screen with a 500 fF declared load. Logic-high threshold is 0.7 times supply, not proof that lower voltages cannot partially enable a pad. No hysteresis, reference generation, transient reset/brownout, mismatch, extraction or connected-pad safety qualification.',
        requirements=build(floor_kind=floor_kind,floor_ratio=floor_ratio).requirements,
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),Path(__file__).with_name('circuits.py'),Path(__file__).with_name('screen.py'),pdk/'design.ngspice',pdk/'sm141064.ngspice',pdk/'sm141064.spice')})


def transient_screen(work,pdk,*,reuse=False,output_bleed_ohm=100000):
    """Retain the supply/reference/reset transitions, including failed shutdown."""
    from pathlib import Path
    import hashlib,os
    import numpy as np
    from screen import header,control,run_spice
    work=Path(work).resolve();pdk=Path(pdk).resolve();work.mkdir(parents=True,exist_ok=True)
    (work/'.spiceinit').write_text('set ngbehavior=hs\n')
    c=build(floor_kind='junction',floor_ratio=3.55,output_bleed_ohm=output_bleed_ohm)
    deck=header(c,pdk)+f'.lib {pdk}/sm141064.spice bjt_typical\n'
    deck+='VDD VDD 0 PWL(0 0 10n 0 30n 3.3 100n 3.3 110n 1.5 180n 1.5 200n 3.3 300n 3.3 310n 0 380n 0 400n 3.3 500n 3.3)\n'
    deck+='VREF VREF 0 PWL(0 0 40n 0 60n 1 100n 1 110n .5 180n .5 200n 1 500n 1)\nVRESET RESET_N 0 PWL(0 3.3 240n 3.3 241n 0 260n 0 261n 3.3 500n 3.3)\nCLOAD RAIL_OK 0 500f\n'
    deck+=control(work,'lifecycle','tran .1n 500n','v(VDD) v(VREF) v(RESET_N) v(RAIL_OK) i(VDD)')
    previous=Path.cwd()
    try:
        os.chdir(work)
        if reuse:
            if (work/'lifecycle.spice').read_text()!=deck:raise ValueError('Saved transient circuit differs')
            x=np.loadtxt(work/'lifecycle.dat',skiprows=1)
        else:x=run_spice(work,'lifecycle',deck,timeout_s=120)
    finally:os.chdir(previous)
    if not np.isfinite(x).all() or x[-1,0]<499.9e-9:raise ValueError('Incomplete transient')
    windows={}
    for name,a,b in [('startup_reference_absent',30,40),('active',80,99),('brownout',130,179),('recovered',220,239),('reset',245,259),('unpowered_peer_reference_high',330,379),('final_active',450,499)]:
        y=x[(x[:,0]>=a*1e-9)&(x[:,0]<=b*1e-9)]
        if len(y)<2:raise ValueError('Missing lifecycle window')
        windows[name]=dict(output_min_v=float(y[:,4].min()),output_max_v=float(y[:,4].max()),max_supply_backfeed_a=float(np.maximum(y[:,5],0).max()))
    mask=(x[:,1]>.1)&(x[:,1]<2.5)&(x[:,4]>1.65)
    return dict(status='shutdown_overlap_unresolved' if mask.any() else 'scoped_transient_not_pad_safety_qualification',
        windows=windows,undervoltage_above_1p65_duration_s=float(np.trapezoid(mask.astype(float),x[:,0])),
        undervoltage_output_peak_v=float(x[(x[:,1]>.1)&(x[:,1]<2.5),4].max()),last_time_s=float(x[-1,0]),
        deck_sha256=hashlib.sha256(deck.encode()).hexdigest(),
        scope='Typical FET/BJT and resistor models,27C,500fF output load. Duration is sampled integration, not a rigorous timing bound. Supply/reference/reset are prescribed external transitions; output is generated by the physical circuit. High output during invalid supply and retained output after power loss remain failures to resolve. No pad gate fanout, layout, ESD or device-survival qualification.')


def connected_receive_screen(work,pdk,physical,*,reuse=False):
    """Actual supervisor output drives two retained RX/USB high-side branches.

    A separate zero-volt supply probe prevents supervisor consumption from
    hiding pad-to-supply backfeed. This is a fixture, not protocol operation.
    """
    import os,hashlib,json
    from pathlib import Path
    import numpy as np
    from wired_receive import build as receive
    from design import PROJECT
    from screen import header,control,run_spice
    work=Path(work).resolve();pdk=Path(pdk).resolve();physical=Path(physical).resolve()
    work.mkdir(parents=True,exist_ok=True);(work/'.spiceinit').write_text('set ngbehavior=hs\n')
    pad=receive();core_cap=json.loads((PROJECT/'spec/analog-architecture.json').read_text())['blocks']['rxlevel']['parameters']['output_cap_budget_f_per_leg']
    results={};previous=Path.cwd()
    try:
        os.chdir(work)
        for case,bleed in [('stale_requests',None),('supervised_100k',100000),('supervised_10k',10000)]:
            deck=header(pad,pdk,physical)
            original='Xpad '+' '.join(pad.ports)+' '
            mapped=['PAD_VDD' if p=='VDD' else p for p in pad.ports]
            if deck.count(original)!=1:raise ValueError('Expected one pad instance')
            deck=deck.replace(original,'Xpad '+' '.join(mapped)+' ')
            deck+='VPADFEED VDD PAD_VDD 0\n'
            if bleed is not None:
                supervisor=build(output_bleed_ohm=bleed)
                deck+=supervisor.spice()+f'.lib {pdk}/sm141064.spice bjt_typical\n'
                deck+='XSUP VDD VSS VREF RESET_N RAIL_OK rail_window_candidate\n'
            else:deck+='VSTALE RAIL_OK 0 3.3\n'
            deck+='VDD VDD 0 PWL(0 0 10n 0 30n 3.3 100n 3.3 110n 1.5 180n 1.5 200n 3.3 300n 3.3 310n 0 380n 0 400n 3.3 500n 3.3)\n'
            deck+='VREF VREF 0 PWL(0 0 40n 0 60n 1 100n 1 110n .5 180n .5 200n 1 500n 1)\nVRESET RESET_N 0 PWL(0 3.3 240n 3.3 241n 0 260n 0 261n 3.3 500n 3.3)\nCLOAD RAIL_OK 0 500f\n'
            for port in pad.ports:
                if port in ('PAD_P','PAD_N','VDD','VSS','RX_P','RX_N'):continue
                if port in ('FS_HIGH_P','PULLUP_N'):deck+=f'VCTRL_{port} {port} RAIL_OK 0\n'
                else:deck+=f'V{port} {port} 0 '+('3.3' if port=='HS_PBIAS' else '0')+'\n'
            for leg in ('P','N'):
                deck+=f'VEXT_{leg} EXT_{leg} 0 3.3\nRPULL_{leg} EXT_{leg} BOARD_{leg} 1500\nRLOAD_{leg} BOARD_{leg} 0 15000\nCBOARD_{leg} BOARD_{leg} 0 10p\nRBOND_{leg} BOARD_{leg} BOND_{leg} 1\nLBOND_{leg} BOND_{leg} PAD_{leg} 1n\nRCORE_{leg} RX_{leg} 0 1g\nCCORE_{leg} RX_{leg} 0 {core_cap}\n'
            deck+=control(work,case,'tran .1n 500n','v(VDD) v(RAIL_OK) v(PAD_P) v(PAD_N) i(VDD) i(VPADFEED)')
            if reuse:
                if (work/f'{case}.spice').read_text()!=deck:raise ValueError('Saved connected circuit differs')
                x=np.loadtxt(work/f'{case}.dat',skiprows=1)
            else:x=run_spice(work,case,deck,timeout_s=120)
            if not np.isfinite(x).all() or x[-1,0]<499.9e-9:raise ValueError('Incomplete connected transient')
            windows={}
            for name,a,b in [('active',80,99),('collapse',100,130),('brownout',130,179),('reset',245,259),('power_loss',300,330),('unpowered',330,379),('recovered',450,499)]:
                y=x[(x[:,0]>=a*1e-9)&(x[:,0]<=b*1e-9)]
                if len(y)<2:raise ValueError('Missing connected state')
                backfeed=np.maximum(-y[:,6],0.)
                windows[name]=dict(pad_backfeed_peak_a=float(backfeed.max()),pad_backfeed_charge_c=float(np.trapezoid(backfeed,y[:,0])),
                    net_supply_backfeed_peak_a=float(np.maximum(y[:,5],0).max()),
                    supervisor_mean_supply_draw_a=float(np.mean(-y[:,5]-y[:,6])),
                    pad_voltage_min_v=float(y[:,3:5].min()),pad_voltage_max_v=float(y[:,3:5].max()),
                    control_min_v=float(y[:,2].min()),control_max_v=float(y[:,2].max()))
            results[case]=dict(windows=windows,completed_end_s=float(x[-1,0]),deck_sha256=hashlib.sha256(deck.encode()).hexdigest())
    finally:os.chdir(previous)
    return dict(status='connected_pad_supervisor_diagnostic_not_safety_qualification',cases=results,
        scope='Same extracted RX/USB pad, retained 3.3V peers and 500fF additional control load. Schematic supervisor and ideal control wires; no layout/fanout or latch/blanking sequencer. FS_HIGH_P and PULLUP_N are simultaneous generic branch exercises, not a legal USB transaction. Separate pad supply probe retains displacement/backfeed current even when supervisor consumes supply current. Bias/reference and supply waveforms remain explicit fixture inputs.',
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),physical,PROJECT/'spec/analog-architecture.json',Path(__file__).with_name('wired_receive.py'),Path(__file__).with_name('circuits.py'))})


def extended_brownout_screen(work,*,reuse=False):
    """Hold the connected 10k diagnostic's brownout for another microsecond."""
    from pathlib import Path
    import hashlib,re,os
    import numpy as np
    from screen import control,run_spice
    work=Path(work).resolve()
    baseline=(work/'supervised_10k.spice').read_text()
    lines=[]
    for line in baseline.split('.control')[0].splitlines():
        if line.startswith(('VDD VDD','VREF VREF','VRESET RESET_N')):
            line=re.sub(r'(\d+)n',lambda m:str(int(m[1])+1000)+'n' if int(m[1])>=180 else m[0],line)
        lines.append(line)
    name='extended_brownout'
    deck='\n'.join(lines)+'\n'+control(work,name,'tran .2n 1500n','v(VDD) v(RAIL_OK) v(PAD_P) v(PAD_N) i(VDD) i(VPADFEED)')
    previous=Path.cwd()
    try:
        os.chdir(work)
        if reuse:
            if (work/f'{name}.spice').read_text()!=deck:raise ValueError('Saved extended circuit differs')
            x=np.loadtxt(work/f'{name}.dat',skiprows=1)
        else:x=run_spice(work,name,deck,timeout_s=120)
    finally:os.chdir(previous)
    if not np.isfinite(x).all() or x[-1,0]<1499.9e-9:raise ValueError('Incomplete extended hold')
    windows={}
    for label,a,b in [('early',130,179),('middle',500,600),('late',1000,1179)]:
        y=x[(x[:,0]>=a*1e-9)&(x[:,0]<=b*1e-9)]
        if len(y)<2:raise ValueError('Missing extended state')
        windows[label]=dict(pad_backfeed_peak_a=float(np.maximum(-y[:,6],0).max()),
            pad_backfeed_end_a=float(max(-y[-1,6],0)),pad_p_end_v=float(y[-1,3]),
            pad_n_end_v=float(y[-1,4]),control_max_v=float(y[:,2].max()))
    return dict(status='pad_loading_unresolved',windows=windows,last_time_s=float(x[-1,0]),
        baseline_deck_sha256=hashlib.sha256(baseline.encode()).hexdigest(),
        deck_sha256=hashlib.sha256(deck.encode()).hexdigest(),
        scope='Diagnostic 10k supervisor only; same retained pad branches and peers. Early supply backfeed decays, but settled pads remain near 1.55V instead of the unloaded external divider level of 3V. The remaining current path is unidentified. Not steady-state leakage or safety qualification.')


def branch_trace_screen(work,*,reuse=False):
    """Identify retained pad loading without deleting disabled devices."""
    from pathlib import Path
    import os,hashlib
    import numpy as np
    from screen import control,run_spice
    w=Path(work).resolve();base=(w/'extended_brownout.spice').read_text().split('.control')[0]
    lines=[];probes=[];inside=False
    for line in base.splitlines():
     if line.startswith('.subckt combined_flat '):inside=True
     if line.startswith('.ends'):inside=False
     f=line.split()
     if inside and f and f[0][0] in 'XD' and 'PAD_P' in f:
      original=line
      for i in range(1,len(f)):
       if f[i]=='PAD_P':
        node=f'TRACE_{f[0]}_{i}';v=f'VTRACE_{f[0]}_{i}'
        f[i]=node;lines.append(f'{v} PAD_P {node} 0');probes.append((v,original))
      line=' '.join(f)
     lines.append(line)
    name='branch_trace';vectors='v(VDD) v(PAD_P) '+ ' '.join(f'i(v.xpad.xphysical.{v.lower()})' for v,_ in probes)
    deck='\n'.join(lines)+'\n'+control(w,name,'tran .2n 1500n',vectors)
    previous=Path.cwd()
    try:
     os.chdir(w)
     if reuse:
      if (w/(name+'.spice')).read_text()!=deck:raise ValueError('Saved branch trace differs')
      x=np.loadtxt(w/(name+'.dat'),skiprows=1)
     else:x=run_spice(w,name,deck,timeout_s=120)
    finally:os.chdir(previous)
    if not np.isfinite(x).all() or x[-1,0]<1499.9e-9:raise ValueError('Incomplete branch trace')
    y=x[(x[:,0]>=1000e-9)&(x[:,0]<=1179e-9)]
    r=dict(deck_sha256=hashlib.sha256(deck.encode()).hexdigest(),pad_mean_v=float(y[:,2].mean()),branches=sorted([dict(probe=v,device=line,mean_current_a=float(y[:,i+3].mean())) for i,(v,line) in enumerate(probes)],key=lambda a:abs(a['mean_current_a']),reverse=True))
    r['scope']='Zero-volt current probes at all non-capacitive PAD_P device terminals in the unchanged extracted subcircuit; all branches retained. Late brownout means, not ESD qualification or a corrected design.'
    return r


def clamp_state_screen(work,*,reuse=False,long_hold=False,gate_discharge=False):
    """Observe the extracted primary clamp without forcing its internal state."""
    from pathlib import Path
    import os,re,hashlib
    import numpy as np
    from screen import control,run_spice
    w=Path(work).resolve();base=(w/'extended_brownout.spice').read_text().split('.control')[0]
    nodes=['ESD_RAIL','a_42245_162628#','a_44789_189064#','a_41005_203545#','a_43813_189064#']
    if long_hold:
        lines=[]
        for line in base.splitlines():
            if line.startswith(('VDD VDD','VREF VREF','VRESET RESET_N')):
                line=re.sub(r'(\d+)n',lambda m:str(int(m[1])+9000)+'n' if int(m[1])>=1180 else m[0],line)
            lines.append(line)
        base='\n'.join(lines)+'\n'
    if gate_discharge:
        lines=[];inside=False
        for line in base.splitlines():
            if line.startswith('.subckt combined_flat '):inside=True
            if inside and line.startswith('.ends'):
                node='a_42245_162628#'
                for i in range(8):
                    end='VSS' if i==7 else f'CLAMP_DISCHARGE_{i}'
                    lines.append(f'XCLAMP_DISCHARGE_{i} {node} {end} VSS ppolyf_u_1k r_width=1u r_length=12.5u')
                    node=end
                inside=False
            lines.append(line)
        base='\n'.join(lines)+'\n'
    name='clamp_long_hold' if long_hold else 'clamp_state'
    if gate_discharge:name+='_discharge'
    deck=base+control(w,name,'tran 2n 10500n' if long_hold else 'tran .2n 1500n','v(VDD) v(PAD_P) '+' '.join(('v(xpad.esd_rail)' if n=='ESD_RAIL' else 'v(xpad.xphysical.'+n+')') for n in nodes))
    previous=Path.cwd()
    try:
     os.chdir(w)
     if reuse:
      if (w/(name+'.spice')).read_text()!=deck:raise ValueError('Saved clamp state differs')
      x=np.loadtxt(w/(name+'.dat'),skiprows=1)
     else:x=run_spice(w,name,deck,timeout_s=120)
    finally:os.chdir(previous)
    if not np.isfinite(x).all() or x[-1,0]<(10499.9e-9 if long_hold else 1499.9e-9):raise ValueError('Incomplete clamp state trace')
    r={}
    windows=[('active',80,99),('late_brownout',1000,1179),('recovered',1450,1499)]
    if long_hold:windows=[('early_brownout',1000,1179),('middle_brownout',4000,5000),('late_brownout',9000,10179),('recovered',10450,10499)]
    for label,a,b in windows:
     y=x[(x[:,0]>=a*1e-9)&(x[:,0]<=b*1e-9)]
     if len(y)<2:raise ValueError('Missing clamp state window')
     r[label]={n:float(y[:,i+1].mean()) for i,n in enumerate(['VDD','PAD_P']+nodes)}
    return dict(windows=r,gate_discharge_nominal_ohm=100000 if gate_discharge else None,deck_sha256=hashlib.sha256(deck.encode()).hexdigest(),scope='Connected diagnostic with all extracted devices retained; optional100k gate discharge uses eight schematic PDK resistors without added layout routing. Window averages do not establish final equilibrium or ESD survival.')


def clamp_release_pulse_screen(work,*,gate_discharge=False,reuse=False,direct_trigger=False,feedforward=False):
    """Compare a diagnostic protection pulse after the retained brownout hold."""
    from pathlib import Path
    import os,hashlib
    import numpy as np
    from screen import control,run_spice
    w=Path(work).resolve()
    source=w/('clamp_long_hold_discharge.spice' if gate_discharge else 'clamp_long_hold.spice')
    base=source.read_text().split('.control')[0]
    name='release_pulse_discharge' if gate_discharge else 'release_pulse_control'
    if direct_trigger:
        if not gate_discharge:raise ValueError('Direct trigger diagnostic requires gate discharge')
        lines=[];inside=False
        for line in base.splitlines():
            if line.startswith('.subckt combined_flat '):inside=True
            if inside and line.startswith('.ends'):
                node='ESD_RAIL'
                for i in range(3):
                    end='a_42245_162628#' if i==2 else f'DIRECT_TRIGGER_{i}'
                    lines.append(Mos(f'DIRECT_TRIGGER_{i}',(node,node,end,'VSS'),'nfet_06v0',100.,.7).spice())
                    node=end
                inside=False
            lines.append(line)
        base='\n'.join(lines)+'\n';name+='_direct_trigger'
    if feedforward:
        if not gate_discharge or direct_trigger:raise ValueError('Feed-forward comparison uses discharge only')
        lines=[];inside=False
        for line in base.splitlines():
            if line.startswith('.subckt combined_flat '):inside=True
            if inside and line.startswith('.ends'):
                lines.append('XCLAMP_FEEDFORWARD ESD_RAIL a_42245_162628# cap_mim_2f0_m4m5_noshield c_width=44.72u c_length=44.72u')
                inside=False
            lines.append(line)
        base='\n'.join(lines)+'\n';name+='_feedforward'
    deck=base+'IINJECT VSS PAD_P PULSE(0 .1 1000n .1n .1n 2n 20u)\n'
    nodes=['PAD_P','PAD_N','RX_P','RX_N','xpad.ESD_RAIL','xpad.xphysical.a_42245_162628#']
    deck+=control(w,name,'tran .05n 1500n',' '.join('v('+n+')' for n in nodes))
    previous=Path.cwd()
    try:
        os.chdir(w)
        if reuse:
            if (w/(name+'.spice')).read_text()!=deck:raise ValueError('Saved release pulse differs')
            x=np.loadtxt(w/(name+'.dat'),skiprows=1)
        else:x=run_spice(w,name,deck,timeout_s=120)
    finally:os.chdir(previous)
    if not np.isfinite(x).all() or x[-1,0]<1499.9e-9:raise ValueError('Incomplete release pulse')
    windows={}
    for name,a,b in [('before',990,999),('pulse',1000,1002.2),('after',1002.2,1010),('recovery',1450,1499)]:
        y=x[(x[:,0]>=a*1e-9)&(x[:,0]<=b*1e-9)]
        if len(y)<2:raise ValueError('Missing pulse state')
        windows[name]={n:dict(min_v=float(y[:,i+1].min()),max_v=float(y[:,i+1].max())) for i,n in enumerate(nodes)}
    return dict(windows=windows,gate_discharge=gate_discharge,direct_trigger=direct_trigger,feedforward=feedforward,deck_sha256=hashlib.sha256(deck.encode()).hexdigest(),
        source_deck_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        scope='100mA positive2ns diagnostic into PAD_P after1us startup/brownout, all pad attachments and board peers retained. Typical models27C, schematic gate-discharge option and optional three100um diode-connected6V NMOS trigger devices with grounded bodies; optional44.72um-square MIM feed-forward capacitor from isolated rail to main clamp gate; no added layout routing. Not a standardized ESD waveform, current-density/thermal qualification, core survival or settled-DC acceptance; transient operating-point initialization is permitted for this lifecycle comparison.')


def pulse_terminal_exposure(work,*,direct_trigger=False):
    """Lower-bound device exposure from saved nodes; unknown terminals stay unknown."""
    from pathlib import Path
    import re,hashlib
    import numpy as np
    work=Path(work).resolve()
    # Validate the exact regenerated fixture before interpreting its waveform.
    verified=clamp_release_pulse_screen(work,gate_discharge=True,direct_trigger=direct_trigger,reuse=True)
    name='release_pulse_discharge'+('_direct_trigger' if direct_trigger else '')
    deck=(work/(name+'.spice')).read_text()
    x=np.loadtxt(work/(name+'.dat'),skiprows=1)
    known={'0':np.zeros(len(x))}
    for i,node in enumerate(['PAD_P','PAD_N','RX_P','RX_N','ESD_RAIL','a_42245_162628#'],1):known[node]=x[:,i]
    def value(token):
        m=re.fullmatch(r'([+-]?(?:\d*\.)?\d+(?:[eE][+-]?\d+)?)([numk]?)',token)
        if not m:raise ValueError('Unsupported fixture numeric token: '+token)
        return float(m[1])*{'':1.,'n':1e-9,'u':1e-6,'m':1e-3,'k':1e3}[m[2]]
    sources=[];inside=False;devices=[]
    for line in deck.splitlines():
        if line.startswith('.subckt combined_flat '):inside=True
        elif line.startswith('.ends'):inside=False
        f=line.split()
        if inside and len(f)>5 and f[0].startswith('X') and f[5] in ('nfet_03v3','pfet_03v3','nfet_06v0','pfet_06v0'):
            devices.append(f)
        if line.startswith('V'):
            if 'PWL(' in line:
                points=line.split('PWL(',1)[1].split(')',1)[0].split()
                t=np.array([value(v) for v in points[::2]])
                v=np.array([value(v) for v in points[1::2]])
                sources.append((f[1],f[2],np.interp(x[:,0],t,v)))
            elif len(f)==4:sources.append((f[1],f[2],value(f[3])))
    for _ in range(len(sources)):
        changed=False
        for a,b,v in sources:
            if a not in known and b in known:known[a]=known[b]+v;changed=True
            elif b not in known and a in known:known[b]=known[a]-v;changed=True
        if not changed:break
    # The zero-volt pad-feed probe maps the internal supply onto external VDD.
    if 'PAD_VDD' not in known:raise ValueError('Missing actual pad supply mapping')
    known['VDD']=known['PAD_VDD']
    mask=(x[:,0]>=990e-9)&(x[:,0]<=1499e-9)
    records=[];missing={};full=0
    for f in devices:
        nodes=dict(zip('DGSB',f[1:5]));pairs={}
        for pair in ('GS','GD','GB','DS','DB','SB'):
            a,b=(nodes[c] for c in pair)
            if a in known and b in known:
                z=(known[a]-known[b])[mask]
                pairs[pair]=float(np.max(np.abs(z)))
        if len(pairs)==6:full+=1
        else:missing[f[0]]=[n for n in nodes.values() if n not in known]
        if pairs:records.append(dict(device=f[0],model=f[5],nodes=nodes,max_abs_terminal_v=pairs))
    records.sort(key=lambda row:max(row['max_abs_terminal_v'].values()),reverse=True)
    return dict(status='partial_terminal_exposure_not_survival_qualification',
        deck_sha256=verified['deck_sha256'],waveform_sha256=hashlib.sha256((work/(name+'.dat')).read_bytes()).hexdigest(),
        mos_count=len(devices),fully_observed_mos_count=full,partly_observed_mos_count=len(records)-full,
        worst_terminal_exposures=records[:8],unobserved_mos_count=len(devices)-len(records),
        unobserved_internal_node_count=len({n for nodes in missing.values() for n in nodes}),
        scope='990..1499ns includes pulse and recovery. Only measured waveform nodes or exact fixture voltage-source relations are used. Unknown internal voltages are not inferred from off controls or nominal supply. Device voltage class is not a transient survival limit. Full internal-node traces and terminal current/duration limits remain required.')
