"""Static CMOS TX mode exclusion; supply qualification remains an explicit input."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from circuits import Circuit,Mos
from transmit_controls import CONFLICTS
from screen import run_spice,control

REQUESTS=('MAIN','POST','TMDS','DETECT','TERM')

def build(*, tolerant_inputs=False, tolerant_logic=False):
    devices=[];index=0
    def mos(name,d,g,s,kind,w):
        external_gate = g in {'RESET', 'QUALIFIED', 'SUPPLY_OK'} or g.startswith('REQ_')
        thick = tolerant_logic or (tolerant_inputs and external_gate)
        model = ('pfet_' if kind=='p' else 'nfet_') + ('06v0' if thick else '03v3')
        devices.append(Mos(name,(d,g,s,'VDD' if kind=='p' else 'VSS'),model,w*(2.5 if thick else 1),.7 if thick else .28))
    def invert(a,out):
        nonlocal index
        n=f'G{index}';index+=1
        mos(n+'P',out,a,'VDD','p',4.);mos(n+'N',out,a,'VSS','n',2.)
    def binary(a,b,out,operation):
        nonlocal index
        n=f'G{index}';index+=1;inv=n+'_INV';mid=n+'_MID'
        if operation=='and':
            mos(n+'P0',inv,a,'VDD','p',4.);mos(n+'P1',inv,b,'VDD','p',4.)
            mos(n+'N0',inv,a,mid,'n',4.);mos(n+'N1',mid,b,'VSS','n',4.)
        else:
            mos(n+'P0',mid,a,'VDD','p',8.);mos(n+'P1',inv,b,mid,'p',8.)
            mos(n+'N0',inv,a,'VSS','n',2.);mos(n+'N1',inv,b,'VSS','n',2.)
        invert(inv,out)
    binary('REQ_MAIN','REQ_POST','DATA_REQUEST','or')
    binary('DATA_REQUEST','REQ_TERM','ORDINARY_REQUEST','or')
    binary('REQ_TMDS','REQ_DETECT','SPECIAL_REQUEST','or')
    binary('ORDINARY_REQUEST','SPECIAL_REQUEST','MIXED_CONFLICT','and')
    binary('REQ_TMDS','REQ_DETECT','SPECIAL_CONFLICT','and')
    binary('MIXED_CONFLICT','SPECIAL_CONFLICT','CONFLICT','or')
    invert('CONFLICT','NO_CONFLICT');invert('RESET','NO_RESET')
    binary('QUALIFIED','SUPPLY_OK','QUALIFIED_SUPPLY','and')
    binary('NO_RESET','NO_CONFLICT','LEGAL_REQUEST','and')
    binary('QUALIFIED_SUPPLY','LEGAL_REQUEST','VALID','and')
    for name in REQUESTS:binary('REQ_'+name,'VALID','EN_'+name,'and')
    return Circuit('tx_mode_interlock',['VDD','VSS']+['REQ_'+n for n in REQUESTS]+['RESET','QUALIFIED','SUPPLY_OK','CONFLICT','VALID']+['EN_'+n for n in REQUESTS],devices,{},[
        'Full-rail logic interface; legacy0/1 behavioral enables require explicit boundary conversion.',
        'SUPPLY_OK and QUALIFIED are supplied inputs, not implemented monitors.',
        'Combinational exclusion only: no hazard-free guarantee, break-before-make sequencing or buffer-ready detector.',
        'Output loading, propagation delay, physical layout and PVT require verification.'])


def run(work,pdk,physical=None):
    work.mkdir(parents=True,exist_ok=False);c=build();model=physical.read_text() if physical else c.spice();definition=next(l.split() for l in model.splitlines() if l.startswith('.subckt '))
    if definition[2:]!=c.ports:raise ValueError('Control physical port mismatch')
    (work/'circuit.spice').write_text(model);results=[]
    for reset in (0,1):
      for qualified in (0,1):
       for supply_ok in (0,1):
        name=f'dc_{reset}{qualified}{supply_ok}'
        deck=(f'TX transistor control truth table\n.include {pdk}/design.ngspice\n.lib {pdk}/sm141064.ngspice typical\n.temp 27\n'+model+
              'XCTL '+' '.join(c.ports)+' '+definition[1]+'\nVDD VDD 0 3.3\nVSS VSS 0 0\nVCODE CODE 0 0\n'+
              f'VRESET RESET 0 {3.3*reset}\nVQUAL QUALIFIED 0 {3.3*qualified}\nVOK SUPPLY_OK 0 {3.3*supply_ok}\n')
        for bit,n in enumerate(REQUESTS):deck+=f'BREQ_{n} REQ_{n} 0 V=3.3*(floor(V(CODE)/{2**bit})-2*floor(V(CODE)/{2**(bit+1)}))\n'
        deck+=control(work,name,'dc VCODE 0 31 1','v(CONFLICT) v(VALID) '+' '.join('v(EN_'+n+')' for n in REQUESTS))
        x=run_spice(work,name,deck)
        if len(x)!=32 or not np.isfinite(x).all():raise ValueError('Incomplete truth table')
        expected=[]
        for code in range(32):
            req={n:bool(code&(1<<i)) for i,n in enumerate(REQUESTS)}
            conflict=any(req[a] and req[b] for a,b in CONFLICTS)
            valid=bool(qualified and supply_ok and not reset and not conflict)
            expected.append([conflict,valid]+[valid and req[n] for n in REQUESTS])
        error=float(np.max(abs(x[:,1:]-3.3*np.array(expected))))
        if error>.033:raise ValueError('Transistor control truth-table mismatch')
        results.append({'reset':reset,'qualified':qualified,'supply_ok':supply_ok,'cases':32,'max_rail_error_v':error})
    report={'physical_extraction_used':physical is not None,'status':'transistor_control_DC_truth_table_verified_not_dynamic_or_layout_qualified','device_count':len(c.devices),'cases':results,'total_cases':256,'limitations':c.limitations,'source_sha256':{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('transmit_controls.py'),work/'circuit.spice']}}
    (work/'screen.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('output-dir','pdk-model-dir'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--physical',type=Path)
    a=p.parse_args();run(a.output_dir.resolve(),a.pdk_model_dir.resolve(),a.physical.resolve() if a.physical else None)
