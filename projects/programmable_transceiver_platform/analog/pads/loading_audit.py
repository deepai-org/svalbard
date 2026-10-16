"""Account pad admittance by branch without removing physical devices or caps.

Ideal zero-volt current probes split pad connections only. The original and
instrumented extracted circuits must have the same port admittance. Attribution
is by device branch versus direct extracted pad capacitances, not an ESD or RF
qualification, and includes conductance/phase effects of each connected branch.
"""
import argparse
import receive_core
from collections import Counter
import hashlib
import json
import re
from pathlib import Path
import numpy as np
from design import PROJECT
from screen import run_spice,control


def instrument(text):
    text=re.sub(r'\n\+\s*',' ',text)
    lines=[];counts=Counter();probes=set()
    cells={l.split()[1] for l in text.splitlines() if l.startswith('.subckt ')}
    for line in text.splitlines():
        t=line.split()
        if not t or t[0][0] not in ('X','C','D'):
            lines.append(line);continue
        if t[0].startswith('X') and t[-1] in cells:
            lines.append(line);continue
        is_cap=t[0].startswith('C')
        is_diode=t[0].startswith('D')
        end=3 if is_cap or is_diode else 4 if t[4].startswith('ppoly') else 5
        nodes=t[1:end]
        if not any(n in ('PAD_P','PAD_N') for n in nodes):lines.append(line);continue
        if is_cap:group='interconnect'
        elif is_diode or t[end].endswith('_dss'):group='protection'
        elif 'BYPASS_ENABLE' in nodes:group='bypass'
        elif any(n.startswith('TERM_') for n in nodes):group='termination'
        elif any(n.startswith('DIV_') for n in nodes):group='divider'
        elif any(n.startswith('HS_') for n in nodes):group='hs_drive'
        elif any(n.startswith('FS_LOW_') for n in nodes):group='fs_low'
        elif any(n.startswith(('FS_P_','FS_N_')) for n in nodes):group='fs_high'
        elif any(n.startswith('PULLUP_') for n in nodes):group='pullup'
        elif any(n.startswith('PULLDOWN_') for n in nodes):group='pulldown'
        else:raise ValueError('Unclassified physical pad device: '+line)
        for i in range(1,end):
            if t[i] in ('PAD_P','PAD_N'):
                leg=t[i][-1];probe=f'SENSE_{group}_{leg}';t[i]=probe;probes.add(probe);counts[group]+=1
        lines.append(' '.join(t))
    ordered=sorted(probes)
    for i,line in enumerate(lines):
        if line.startswith('.subckt '):lines[i]=line+' '+' '.join(ordered)
        elif line.startswith('X') and line.split()[-1] in cells:
            fields=line.split();lines[i]=' '.join(fields[:-1]+ordered+fields[-1:])
    return '\n'.join(lines)+'\n',ordered,dict(counts)


def anchor_floating_conductors(text,resistance):
    """Give capacitor-only extracted conductors a declared numerical DC path."""
    text=re.sub(r'\n\+\s*',' ',text)
    output=[];caps=set();connected=set();cell=None;anchors=[]
    for line in text.splitlines():
        f=line.split()
        if f and f[0]=='.subckt':
            cell=f[1];caps=set();connected=set(f[2:])
        elif f and f[0].startswith('C') and cell:
            caps.update(f[1:3])
        elif f and f[0]=='.ends':
            for node in sorted(caps-connected-{'0','VSS'}):
                output.append(f'RNUM_FLOAT_{len(anchors)} {node} VSS {resistance:g}')
                anchors.append({'cell':cell,'node':node,'resistance_ohm':resistance})
            cell=None
        elif cell and f and not f[0].startswith(('*','.')):
            connected.update(f[1:])
        output.append(line)
    return '\n'.join(output)+'\n',anchors


def screen(work,pdk,physical,floating_resistance=None):
    if work.exists() and any(work.iterdir()):raise FileExistsError('Use an empty output directory')
    work.mkdir(parents=True,exist_ok=True)
    original=physical.read_text();anchors=[]
    if floating_resistance is not None:
        if not np.isfinite(floating_resistance) or floating_resistance<1e12:raise ValueError('Numerical anchor must be at least1Tohm')
        original,anchors=anchor_floating_conductors(original,floating_resistance)
    modified,probes,counts=instrument(original)
    architecture=json.loads((PROJECT/'spec/analog-architecture.json').read_text())
    cap=architecture['blocks']['rxlevel']['parameters']['output_cap_budget_f_per_leg']
    cases={};frequency=1e9
    for name,settings,dc_difference in [('disabled',{},0),('serial_bypass',{'BYPASS_ENABLE':3.3},0),
                          ('usb_terminated',{'TERM_ENABLE':3.3},0),('differential_terminated',{'DIFF_ENABLE':3.3},.001),
                          ('differential_terminated_reverse',{'DIFF_ENABLE':3.3},-.001),
                          ('balanced_differential_diagnostic',{'DIFF_ENABLE':3.3},0)]:
        data={}
        for kind,model in [('baseline',original),('probed',modified)]:
            definition=next(l.split() for l in model.splitlines() if l.startswith('.subckt '))
            ports=definition[2:];cell=definition[1]
            deck='Connected pad admittance attribution\n'+f'.include {pdk}/design.ngspice\n.lib {pdk}/sm141064.ngspice typical\n.lib {pdk}/sm141064.ngspice res_typical\n.temp 27\n.options reltol=1e-7 abstol=1e-16 vntol=1e-9 itl1=500\n'+model
            deck+=receive_core.model(physical)+receive_core.loads(physical)
            deck+='Xpad '+' '.join(ports)+' '+cell+'\nVDD VDD 0 3.3\nVSS VSS 0 0\n'
            for port in ports:
                if port in ('PAD_P','PAD_N','VDD','VSS','RX_P','RX_N') or port.startswith('SENSE_'):continue
                value=settings.get(port,3.3 if port=='HS_PBIAS' else 0)
                deck+=f'V{port} {port} 0 {value}\n'
            for leg,sign in [('P',.5),('N',-.5)]:
                deck+=f'VPAD{leg} PAD_{leg} 0 DC {1.65+sign*dc_difference} AC {sign}\n'
            vectors='real(i(VPADP)) imag(i(VPADP)) real(i(VPADN)) imag(i(VPADN))'
            if kind=='probed':
                for probe in probes:
                    deck+=f'V{probe} PAD_{probe[-1]} {probe} 0\n'
                    vectors+=f' real(i(V{probe})) imag(i(V{probe}))'
            run=name+'_'+kind;deck+=control(work,run,'ac lin 1 1G 1G',vectors)
            data[kind]=np.atleast_2d(run_spice(work,run,deck))[0]
        base=data['baseline'];row=data['probed'];contributions={};summed={'P':0j,'N':0j}
        for i,probe in enumerate(probes):
            current=complex(row[5+2*i],row[6+2*i]);leg=probe[-1];voltage=.5 if leg=='P' else -.5
            group=probe.removeprefix('SENSE_')[:-2];y=current/voltage
            contributions.setdefault(group,{})[leg]=dict(effective_capacitance_f=y.imag/(2*np.pi*frequency),conductance_s=y.real)
            summed[leg]+=current
        port_error=float(np.max(abs(base[1:5]-row[1:5])))
        residual=max(abs(summed[leg]+complex(row[1+2*i],row[2+2*i])) for i,leg in enumerate(('P','N')))
        scale=max(abs(complex(row[1],row[2])),abs(complex(row[3],row[4])))
        # Zero probes change matrix ordering; allow 10ppm numerical variation,
        # much tighter than the circuit performance budgets.
        equivalent=port_error<=1e-5*max(scale,1e-12)
        if residual>1e-6*max(scale,1e-12) or (not equivalent and name!='balanced_differential_diagnostic'):
            raise RuntimeError('Current probes changed admittance or attribution does not close KCL')
        cases[name]=dict(branches=contributions,dc_differential_v=dc_difference,probe_equivalence_verified=equivalent,
                        relative_port_current_change=port_error/max(scale,1e-12),maximum_port_current_change_a=port_error,
                        maximum_kcl_residual_a=residual,port_equivalence_relative_tolerance=1e-5,total_capacitance_f_per_leg=[-row[2]/(2*np.pi*frequency*.5),row[4]/(2*np.pi*frequency*.5)])
    report=dict(numerical_floating_conductor_anchors=anchors,status='connected_branch_admittance_accounting',frequency_hz=frequency,common_mode_v=1.65,cases=cases,
        instrumented_pad_terminal_counts=counts,
        balanced_bias_probe_equivalence_verified=cases['balanced_differential_diagnostic']['probe_equivalence_verified'],
        limitations=['Every transistor/resistor/capacitor remains; zero-volt probes partition currents without removing branches.',
                    'Interconnect category contains direct extracted PAD-node capacitances. Internal extracted capacitance remains behind each branch.',
                    'Effective capacitance is Im(Y)/omega at this bias/frequency; it is not a standalone physical capacitor or a broadband model.',
                    'Exactly balanced differential bias is a separate diagnostic: if probe equivalence fails there, its branch attribution is unverified. Differential main cases use explicit +/-1mV DC offsets; no claim of a resolved model discontinuity.',
                    'No process variation, noise, distributed resistance or control timing qualification.'],
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(receive_core.__file__),receive_core.PRIMITIVE,receive_core.LAYOUT,physical,PROJECT/'spec/analog-architecture.json',Path(__file__).with_name('screen.py'),pdk/'design.ngspice',pdk/'sm141064.ngspice',pdk/'sm141064.spice']})
    (work/'loading-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({name:case['total_capacitance_f_per_leg'] for name,case in cases.items()}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--pdk-model-dir',type=Path,required=True);p.add_argument('--physical',type=Path,required=True)
    p.add_argument('--floating-resistance',type=float)
    a=p.parse_args();screen(a.output_dir.resolve(),a.pdk_model_dir.resolve(),a.physical.resolve(),a.floating_resistance)
