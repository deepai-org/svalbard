"""Compose one physical primary foundation with selectable functional attachments.

Comparison candidates, not selected layouts. Functional branches are instantiated
once and remain connected when disabled. Attached RF cores are explicit loading
assumptions until transistor implementations exist.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from circuits import analog_port, attachment
from design import PROJECT, build_integration_candidate, resolve
from loading_audit import anchor_floating_conductors
from screen import control, run_spice

RECIPES={
    'wired_tx':('wired_transmit',),
    'wired_rx_usb':('wired_receive_usb',),
    'wired_combined':('wired_transmit','wired_receive_usb'),
    'wired_shared_termination':('wired_transmit','wired_receive_usb'),
    'rf_rx':('rf_receive',),
    'reference':('reference_clock',),
    'rf_rx_reference':('rf_receive','reference_clock'),
    'universal':('wired_transmit','wired_receive_usb','rf_receive','reference_clock','rf_transmit'),
}


def compose(name):
    families=RECIPES[name]
    primary=PROJECT/'analog/pads/generated/protection-network/network-with-well.spice'
    text=primary.read_text()
    if '.subckt network_flat VSS RAIL PADP PADN' not in text:
        raise ValueError('Primary foundation interface changed')
    definitions=[text];instances=['XFOUNDATION VSS PRIMARY_RAIL PAD_P PAD_N network_flat']
    ports=['PAD_P','PAD_N','VDD','VSS'];counts={};models={}
    for family in families:
        original=(build_integration_candidate(family) if family.startswith('wired_') else analog_port(family))
        c=attachment(original)
        if name=='wired_shared_termination' and family=='wired_transmit':
            # One RX termination bank serves source/shunt roles. Keep the TX
            # discharge on the shared VCM; removing it would change shutdown.
            c.devices=[d for d in c.devices if not d.name.startswith('TERM_') or d.name=='TERM_DISCHARGE']
            c.ports.remove('TERM_ENABLE')
        definitions.append(c.spice());mapping={p:p if p in ports[:4] else family+'__'+p for p in c.ports}
        if name=='wired_shared_termination' and family=='wired_transmit':
            mapping['TERM_VCM']='wired_receive_usb__TERM_VCM'
        ports.extend(mapping[p] for p in c.ports if mapping[p] not in ports)
        instances.append('X'+family+' '+' '.join(mapping[p] for p in c.ports)+' '+c.name)
        counts[family]=len(c.devices);models[family]=mapping
    # These are shared declared core input/output loads, not RF transistor models.
    arch=json.loads((PROJECT/'spec/analog-architecture.json').read_text())
    assumed={}
    for family,block,key in [('rf_receive','lna','input_capacitance_f_per_leg'),
                             ('reference_clock','refinput','input_capacitance_f_per_leg'),
                             ('rf_transmit','rfdriver','output_capacitance_f_per_leg')]:
        if family not in families:continue
        cap=arch['blocks'][block]['parameters'][key];assumed[family]=cap
        for leg in ('P','N'):instances.append(f'CLOAD_{family}_{leg} PAD_{leg} VSS {cap}')
    definitions.append('.subckt composed_pad '+' '.join(ports)+'\n'+'\n'.join(instances)+'\n.ends composed_pad\n')
    return '\n'.join(definitions),ports,models,dict(attachments=list(families),
        functional_device_counts=counts,assumed_core_capacitance_f_per_leg=assumed,
        termination_sharing=(name=='wired_shared_termination'),
        primary_instances=1,foundation_sha256=hashlib.sha256(primary.read_bytes()).hexdigest())


def run(work,pdk):
    work.mkdir(parents=True,exist_ok=False);cases={}
    receiver_load=json.loads((PROJECT/'spec/analog-architecture.json').read_text())['blocks']['rxlevel']['parameters']['output_cap_budget_f_per_leg']
    for name in RECIPES:
        model,ports,mappings,info=compose(name)
        (work/(name+'.model.spice')).write_text(model)
        cases[name]=dict(composition=info,states={})
        states=[('disabled',3.3),('unpowered',0.)]
        if 'wired_receive_usb' in mappings:states.append(('rx_bypass',3.3))
        if 'wired_transmit' in mappings:states.append(('tx_main',3.3))
        if any(f.startswith('wired_') for f in mappings):states.append(('termination',3.3))
        for state,supply in states:
            preamble='Shared pad composition comparison\n'+f'.include {pdk}/design.ngspice\n'
            preamble+=''.join(f'.lib {pdk}/sm141064.ngspice {c}\n' for c in ('typical','res_typical','diode_typical','mimcap_typical'))
            base=preamble+'.temp 27\n'+model+'XWHOLE '+' '.join(ports)+' composed_pad\nVSS VSS 0 0\n'+f'VDD VDD 0 {supply}\n'
            bias_probes=[];driven=set()
            for family,mapping in mappings.items():
                for port,node in mapping.items():
                    if port in ports[:4] or node in driven:continue
                    driven.add(node)
                    if port in ('RX_P','RX_N'):
                        # Identical declared receiver-interface loading for separate/merged RX.
                        base+=f'C{node} {node} VSS {receiver_load}\n';continue
                    value=(supply if port in ('CASCODE','DETECT_PBIAS','HS_PBIAS') else
                           supply/2 if port in ('TERM_VCM','VCM') else 0.)
                    term_family=('wired_receive_usb' if name=='wired_shared_termination' or 'wired_transmit' not in mappings else 'wired_transmit')
                    if state=='termination' and port=='TERM_ENABLE' and family==term_family:value=supply
                    if state=='rx_bypass' and family=='wired_receive_usb' and port=='BYPASS_ENABLE':value=supply
                    if state=='tx_main' and family=='wired_transmit':
                        if port=='MAIN_P':value=supply
                        if port=='MAIN_BIAS':
                            value=json.loads((PROJECT/'spec/schematic-implementation.json').read_text())['io_pad_first_pass']['tx_integration_fixture']['bias_v']['MAIN']
                    base+=f'V{node} {node} 0 {value}\n'
                    if port in ('VCM','TERM_VCM'):bias_probes.append('V'+node)
            base,anchors=anchor_floating_conductors(base,1e12)
            # Same DC common mode for every recipe; no removed disabled branches.
            fixture=base+'VCOMMON COMMON 0 1.65\nVP PAD_P COMMON DC 0 AC .5\nVN PAD_N COMMON DC 0 AC -.5\n'
            label=name+'_'+state
            x=np.atleast_2d(run_spice(work,label,fixture+control(work,label,'ac lin 3 1G 2.4G',
                'real(i(VP)) imag(i(VP)) real(i(VN)) imag(i(VN))'),reject_transient_op=True))
            if x.shape!=(3,5) or not np.isfinite(x).all():raise ValueError('Incomplete AC comparison')
            y=-(x[:,[1,3]]+1j*x[:,[2,4]])/np.array([.5,-.5])
            labeldc=label+'_dc'
            dc=np.atleast_2d(run_spice(work,labeldc,fixture+control(work,labeldc,'dc VCOMMON 0 3.3 .3',
                'i(VP) i(VN) i(VDD) '+' '.join('i('+n+')' for n in bias_probes)),reject_transient_op=True))
            if dc.shape!=(12,4+len(bias_probes)) or not np.isfinite(dc).all():raise ValueError('Incomplete DC comparison')
            budgets={f:resolve()['families'][f]['electrical_parameters']['capacitance_f_per_leg'] for f in RECIPES[name]}
            cap=y.imag/(2*np.pi*x[:,0,None])
            selected=np.where(np.isclose(dc[:,0],1.5)|np.isclose(dc[:,0],1.8))[0]
            impedance=(-.3/(dc[selected[1],1:3]-dc[selected[0],1:3])).tolist() if state=='termination' else None
            cases[name]['states'][state]=dict(frequency_hz=x[:,0].tolist(),
                effective_capacitance_f_per_leg=cap.tolist(),real_admittance_s_per_leg=y.real.tolist(),
                shared_capacitance_allocations_f_per_leg=budgets,
                exceeds_1ghz_allocation={f:bool(np.max(cap[0])>b) for f,b in budgets.items()},
                incremental_common_mode_resistance_around_1p65v_ohm=impedance,
                dc_common_mode_v=dc[:,0].tolist(),dc_probe_currents_a=dc[:,1:3].tolist(),
                dc_supply_current_a=dc[:,3].tolist(),
                dc_bias_currents_a={n:dc[:,4+i].tolist() for i,n in enumerate(bias_probes)},numerical_anchors=anchors)
            transfer=fixture.replace('VP PAD_P COMMON','VP SOURCE_P COMMON').replace('VN PAD_N COMMON','VN SOURCE_N COMMON')
            transfer+='RSP SOURCE_P PAD_P 25\nRSN SOURCE_N PAD_N 25\n'
            labeltf=label+'_transfer'
            tf=np.atleast_2d(run_spice(work,labeltf,transfer+control(work,labeltf,'ac lin 3 1G 2.4G',
                'real(v(PAD_P)) imag(v(PAD_P)) real(v(PAD_N)) imag(v(PAD_N))'),reject_transient_op=True))
            if tf.shape!=(3,5) or not np.isfinite(tf).all():raise ValueError('Incomplete transfer comparison')
            h=(tf[:,1]+1j*tf[:,2])-(tf[:,3]+1j*tf[:,4])
            cases[name]['states'][state]['source_to_pad']={'source_ohm_per_leg':25.,
                'magnitude_db':(20*np.log10(abs(h))).tolist(),'phase_deg':np.angle(h,deg=True).tolist(),
                'scope':'Linearized voltage transfer with the same 50 ohm differential source. No receiver load, eye, RF noise or distortion qualification.'}
    report=dict(receiver_load_f_per_leg=receiver_load,status='same_foundation_complete_attachment_loading_comparison_not_full_pad_acceptance',cases=cases,
        limitations=['One extracted primary macro; attachment transistor models include device junction geometry but lack new interconnect extraction, bond/package and shared returns.',
        'Disabled controls are applied voltages, not a physical local supervisor. DC points do not preserve stored charge.',
        'RF/clock attached cores are declared capacitance only; RF driver reverse junctions, input admittance and active signal quality remain unknown. Universal is fully populated only with currently implemented attachments.',
        'No duplicate primary protection and no branch removed between states. Separate instances of a shared design remain required for simultaneous independent lanes.',
        'AC admittance and DC backfeed screen cannot establish eye, noise, distortion, ESD or transient off-state safety.'],
        source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),
        *[Path(__file__).with_name(n) for n in ('circuits.py','wired_receive.py','design.py','screen.py','loading_audit.py')],
        PROJECT/'spec/analog-architecture.json',PROJECT/'spec/schematic-implementation.json',PROJECT/'spec/contract.json',
        PROJECT/'analog/pads/generated/protection-network/network-with-well.spice']})
    (work/'comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:{s:v['effective_capacitance_f_per_leg'][0] for s,v in r['states'].items()} for k,r in cases.items()},indent=2))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--pdk-model-dir',type=Path,required=True)
    a=p.parse_args();run(a.output_dir.resolve(),a.pdk_model_dir.resolve())
