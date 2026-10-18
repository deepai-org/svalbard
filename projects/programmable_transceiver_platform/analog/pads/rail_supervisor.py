"""Physical rail-window detector candidate; not a complete safety supervisor.

Reference and reset are explicit inputs. No behavioral voltage comparator or
ideal bias source is hidden in the circuit. Readiness, hysteresis, reference
startup and final-enable fanout remain separate implementation requirements.
"""
import math
from circuits import Circuit,Mos,Resistor


def build(*, independent_floor=True, floor_ratio=3.2):
    if not math.isfinite(floor_ratio) or floor_ratio<=1:raise ValueError('Floor divider ratio must exceed one')
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
        resistor('FLOOR_PULL','VDD','FLOOR_B',100000)
        mos('FLOOR_SENSE','FLOOR_B FLOOR_SENSE VSS VSS','nfet_03v3',8.,1.)
        inv('FLOOR_INV','FLOOR_B','FLOOR_OK')
        gates.append('FLOOR_OK')
    # NAND followed by inverter: every permission and reset release are required.
    for i,gate in enumerate(gates):
        source='VSS' if i==len(gates)-1 else 'NAND_S'+str(i)
        drain='OK_B' if i==0 else 'NAND_S'+str(i-1)
        mos('VALID_N'+str(i),f'{drain} {gate} {source} VSS','nfet_03v3',6.,.28)
        mos('VALID_P'+str(i),f'OK_B {gate} VDD VDD','pfet_03v3',4.,.28)
    inv('FINAL','OK_B','RAIL_OK')
    resistor('DEFAULT_OFF','RAIL_OK','VSS',100000)
    return Circuit('rail_window_candidate',['VDD','VSS','VREF','RESET_N','RAIL_OK'],devices,
        dict(reference_nominal_v=1.,nominal_ratio_window=[2.55,3.45],independent_floor=independent_floor,floor_ratio=floor_ratio),[
            'Device-model schematic only; comparator offset/headroom move the actual trip levels.',
            'VREF and RESET_N are explicit inputs; reference startup, overshoot and unpowered behavior require integration.',
            'Independent floor uses an absolute device threshold; PVT/trim limits are not qualified.',
            'No hysteresis or startup hold; RAIL_OK is permission for a separate readiness sequencer, never traffic readiness.',
            'No routing/parasitics, final pad-enable load or protection coordination is included.'])


def screen(work,pdk,*,reuse_dc=False):
    import hashlib,json,os
    from pathlib import Path
    import numpy as np
    from screen import header,control,run_spice
    work=Path(work).resolve();pdk=Path(pdk).resolve();work.mkdir(parents=True,exist_ok=True)
    (work/'.spiceinit').write_text('set ngbehavior=hs\n');previous=Path.cwd();results=[]
    try:
        os.chdir(work)
        for corner,floor,reset in [('typical',False,3.3),*[(c,True,3.3) for c in ('typical','ff','ss','fs','sf')],('typical',True,0.)]:
            name=f'{corner}_{int(floor)}_{reset}';c=build(independent_floor=floor)
            deck=header(c,pdk).replace('sm141064.ngspice typical','sm141064.ngspice '+corner)
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
            results.append(dict(corner=corner,independent_floor=floor,reset_v=reset,references=references,
                max_supply_current_a=float(max(-x[:,4])),max_output_v=float(max(x[:,3])),
                dc_complete=True,deck_sha256=hashlib.sha256(deck.encode()).hexdigest()))
    finally:os.chdir(previous)
    unsafe=[r['corner'] for r in results if r['independent_floor'] and r['reset_v']>0 and any(x['undervoltage_assertion'] for x in r['references'])]
    return dict(status='rejected_undervoltage_veto' if unsafe else 'unqualified_transistor_supervisor_candidate',
        unsafe_guarded_corners=unsafe,
        decision='Do not connect this candidate to pad enables. Ratio-only detection follows a degraded reference; the MOS-threshold floor fails undervoltage rejection across process corners. Use an independently qualified reference/floor and reset-dominant final controls before adoption.',results=results,
        temperature_c=27,reference_grid_step_v=.2,supply_grid_step_v=.025,
        scope='Transistor/resistor DC corner screen with a 500 fF declared load. Logic-high threshold is 0.7 times supply, not proof that lower voltages cannot partially enable a pad. No hysteresis, reference generation, transient reset/brownout, mismatch, extraction or connected-pad safety qualification.',
        requirements=build().requirements,
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),Path(__file__).with_name('circuits.py'),Path(__file__).with_name('screen.py'),pdk/'design.ngspice',pdk/'sm141064.ngspice',pdk/'sm141064.spice')})
