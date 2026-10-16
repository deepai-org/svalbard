"""Retained-network diagnostic of the transistor termination-buffer candidate."""
from pathlib import Path
import sys,json,hashlib,re
import numpy as np
from termination_buffer import build
from screen import run_spice
from design import PROJECT

def run(w,src,gated=False,physical=None,bias_divider_scale=1.,bias_cap_pf=0.,external_load="powered_pullups",precharge_extra_ns=0.,drive_calibration=None,model_additions_unextracted=False):
    w.mkdir(parents=True,exist_ok=False)
    s=src.read_text().split('.control')[0]
    assert s.count('VTERM_VCM TERM_VCM 0 1.8')==1
    architecture_path=PROJECT/'spec/analog-architecture.json'
    architecture=json.loads(architecture_path.read_text())
    if external_load=='differential':
        old='RLP PULL BOARD_P 50\nRLN PULL BOARD_N 50\n'
        if s.count(old)!=1:raise ValueError('Unrecognized external load; refuse partial replacement')
        resistance=architecture['blocks']['termination']['parameters']['differential_ohm']
        s=s.replace(old,f'RDIFF_LOAD BOARD_P BOARD_N {resistance}\n')
    elif external_load!='powered_pullups':raise ValueError('Unknown external load')
    drive_settings=None
    if drive_calibration:
        drive_settings=json.loads(drive_calibration.read_text())
        if not drive_settings['both_currents_within_3_percent']:raise ValueError('Loaded drive calibration did not converge')
        if drive_settings['source_sha256'].get(str(src))!=hashlib.sha256(src.read_bytes()).hexdigest():raise ValueError('Drive calibration belongs to another TX fixture')
        for branch,bias in drive_settings['biases_v'].items():
            s,count=re.subn(r'(?m)^BBIAS_'+branch+r' .*$',f'BBIAS_{branch} {branch}_BIAS 0 V={bias}*V(EN_{branch})',s)
            if count!=1:raise ValueError('Missing driver bias')
    c=build(first_stage_scale=10,gated=gated)
    model=physical.read_text() if physical else c.spice()
    definition=next(line.split() for line in model.splitlines() if line.startswith('.subckt '))
    if definition[2:]!=c.ports:raise ValueError('Buffer physical port mismatch')
    cell=definition[1]
    physical_compensation=any(line.startswith('X') and ' cap_mim_' in line for line in model.splitlines())
    if physical_compensation:
        resistors=[line.split() for line in model.splitlines() if line.startswith('X') and ' ppolyf_s ' in line]
        if not any(set(r[1:3])=={'GAIN','COMP'} and r[3]=='VSS' for r in resistors):raise ValueError('MIM present without expected compensation resistor')
    else:
        model,count=re.subn(r'(?m)^\.ends(?: '+re.escape(cell)+r')?[ \t]*$', 'RCOMP GAIN COMP 30\nCCOMP COMP OUT 3p\n.ends '+cell,model)
        if count!=1:raise ValueError('Cannot insert compensation unambiguously')
    s=s.replace('VTERM_VCM TERM_VCM 0 1.8',model+'\nXBUF VDD VSS BUF_REF BUF_BIAS TERM_VCM termination_buffer_candidate\nRREF1 VDD BUF_REF 10k\nRREF2 BUF_REF VSS 10k\nRBIAS1 VDD BUF_BIAS 80k\nRBIAS2 BUF_BIAS VSS 30k\nCLOAD TERM_VCM VSS 10p')
    if not 0<bias_divider_scale<=1 or bias_cap_pf<0:raise ValueError('Invalid bias-network parameters')
    for name,a,b,r in [('RREF1','VDD','BUF_REF',10000),('RREF2','BUF_REF','VSS',10000),('RBIAS1','VDD','BUF_BIAS',80000),('RBIAS2','BUF_BIAS','VSS',30000)]:
        old=next(line for line in s.splitlines() if line.startswith(name+' '))
        s=s.replace(old,f'{name} {a} {b} {r*bias_divider_scale}')
    if bias_cap_pf:s+=f'\nCREF BUF_REF VSS {bias_cap_pf}p\nCBIAS BUF_BIAS VSS {bias_cap_pf}p\n'
    s=s.replace('TERM_VCM termination_buffer_candidate','TERM_VCM '+cell)
    if gated:
        s=s.replace('TERM_VCM '+cell,'TERM_VCM BUF_ENABLE '+cell)
        s+='\nVBUF_REQUEST BUF_REQUEST VSS PWL(0n 0 58n 0 58.1n 3.3 78n 3.3 78.1n 0 100n 0)\nBBUF_ENABLE BUF_ENABLE VSS V=V(BUF_REQUEST)*V(TX_VALID)\n'
    if not 0<=precharge_extra_ns<=40:raise ValueError('Precharge extension must be 0..40ns')
    if precharge_extra_ns:
        def shift_pwl(match):
            fields=match.group(1).split()
            if len(fields)%2:raise ValueError('Malformed PWL source')
            for i in range(0,len(fields),2):
                if not re.fullmatch(r'[0-9.]+n',fields[i]):raise ValueError('Expected explicit ns PWL times')
                t=float(fields[i][:-1])
                if t>=60:fields[i]=f'{t+precharge_extra_ns:g}n'
            return 'PWL('+' '.join(fields)+')'
        s=re.sub(r'PWL\(([^)]*)\)',shift_pwl,s,flags=re.I)
    stop_ns=100+precharge_extra_ns
    s+=f'.control\nset wr_singlescale\nset wr_vecnames\ntran 5p {stop_ns}n\nwrdata {w}/connected.dat v(PAD_P) v(PAD_N) v(VDD) i(VDD) v(TERM_VCM) v(BUF_REF)\nquit\n.endc\n.end\n'
    x=run_spice(w,'connected',s)
    r={'status':'transistor_buffer_connected_gated_candidate' if gated else 'transistor_buffer_connected_diagnostic_no_enable_or_isolation','transient_complete':bool(x[-1,0]>=(stop_ns-.01)*1e-9),'device_count':sum(line.startswith('X') for line in model.splitlines()) if physical else len(c.devices),'windows':{},'gated':gated,'scope':('Transistor enable/isolation with prescribed precharge/hold and behavioral TX_VALID; autonomous supervisor, current limiting, terminal stress and layout remain open. ' if gated else 'No enable/isolation. ')+ 'Same extracted TX and selected external load throughout; Divider bias is a prototype, not a qualified reference. Physical compensation is used only when physical_compensation_used is true; otherwise ideal compensation passives. Core extraction is used only when physical_core_used is true. Pad-to-buffer routing is absent.','source_sha256':{str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest() for f in [src,Path(__file__).with_name('termination_buffer.py'),Path(__file__),w/'connected.spice']}}
    for state,a,b in [('disabled',1,8),('active_tmds',12,23),('reset',27,30),('unpowered',36,43),('active_main',64,67),('active_main_post',69,71),('reconfiguration',76,78)]:
     if a>=60:a+=precharge_extra_ns;b+=precharge_extra_ns
     y=x[(x[:,0]>=a*1e-9)&(x[:,0]<=b*1e-9)]
     r['windows'][state]={'regulation_requested':not gated or state in ('active_main','active_main_post','reconfiguration'),'vcm_min_v':float(y[:,5].min()),'vcm_max_v':float(y[:,5].max()),'max_reference_difference_v':float(abs(y[:,5]-y[:,6]).max()),'reference_min_v':float(y[:,6].min()),'reference_max_v':float(y[:,6].max()),'peak_supply_draw_a':float(max(0,(-y[:,4]).max())),'peak_supply_return_a':float(max(0,y[:,4].max()))}
    end=60+precharge_extra_ns
    z=x[(x[:,0]>=(end-min(1.,(end-58)/2))*1e-9)&(x[:,0]<end*1e-9)]
    r['precharge']={'extra_ns':precharge_extra_ns,'nominal_enable_to_termination_ns':2+precharge_extra_ns,
        'last_window_max_reference_difference_v':float(abs(z[:,5]-z[:,6]).max()),
        'last_window_vcm_min_v':float(z[:,5].min()),'last_window_vcm_max_v':float(z[:,5].max()),
        'scope':'Only PWL events at/after60ns shifted. Data clocks, edge slopes, circuits and external load unchanged; this is a sequencing hypothesis, not an implemented ready detector.'}
    r['device_count_scope']='Buffer only; complete TX fixture devices are additional.'
    r['drive_settings']=None if drive_settings is None else {k:drive_settings[k] for k in ['biases_v','targets_a']}
    if drive_calibration:r['source_sha256'][str(drive_calibration)]=hashlib.sha256(drive_calibration.read_bytes()).hexdigest()
    r['external_load']=external_load
    r['source_sha256'][str(architecture_path)]=hashlib.sha256(architecture_path.read_bytes()).hexdigest()
    r['bias_network']={'divider_scale':bias_divider_scale,'shunt_cap_pf':bias_cap_pf,'scope':'Explicit passive reference/bias hypothesis; not laid out or qualified.'}
    r['physical_compensation_used']=physical_compensation
    r['physical_core_used']=physical is not None and not model_additions_unextracted
    r['extracted_base_with_unextracted_additions']=model_additions_unextracted
    if model_additions_unextracted:r['scope']+=' Candidate includes unextracted device additions; new route and well parasitics are absent.'
    if physical:r['source_sha256'][str(physical)]=hashlib.sha256(physical.read_bytes()).hexdigest()
    (w/'screen.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--fixture",type=Path,required=True)
    p.add_argument("--gated",action="store_true")
    p.add_argument("--physical",type=Path)
    p.add_argument("--bias-divider-scale",type=float,default=1.)
    p.add_argument("--bias-cap-pf",type=float,default=0.)
    p.add_argument("--external-load",choices=["powered_pullups","differential"],default="powered_pullups")
    p.add_argument("--precharge-extra-ns",type=float,default=0.)
    p.add_argument("--drive-calibration",type=Path)
    p.add_argument("--model-additions-unextracted",action="store_true")
    a=p.parse_args();run(a.output_dir.resolve(),a.fixture.resolve(),a.gated,a.physical.resolve() if a.physical else None,a.bias_divider_scale,a.bias_cap_pf,a.external_load,a.precharge_extra_ns,a.drive_calibration.resolve() if a.drive_calibration else None,a.model_additions_unextracted)
