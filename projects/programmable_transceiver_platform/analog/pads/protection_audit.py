"""Compare candidate protection dimensions with published GF180 HV ESD guidance.

The capacitance experiment is a compact-model sizing screen, not ESD simulation
or a replacement layout. TLP current density must not be scaled to qualify a
smaller, differently contacted or independently guarded structure.
"""
import argparse
import hashlib
import json
import subprocess
import shutil
from pathlib import Path
import numpy as np
from circuits import build, FAMILIES, Mos
from screen import run_spice, control

RULES_URL='https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_4_3.html'
TLP_URL='https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_5_5.html'


def isolated_rail_screen(work,pdk):
    """Retain two powered peers and a native clamp during a supply cycle."""
    work.mkdir()
    library=pdk.parent/'gf180mcu_fd_io.spice'
    deck=('Dedicated protection rail with retained powered peers\n'
          f'.include {pdk}/design.ngspice\n'+
          ''.join(f'.lib {pdk}/sm141064.ngspice {s}\n' for s in
                  ('typical','res_typical','diode_typical','moscap_typical'))+
          f'.include {library}\n.temp 27\n')
    deck+='XCL RAIL 0 0 gf180mcu_fd_io__dvdd\n'
    deck+='DFEED VDD RAIL diode_pd2nw_06v0 area=1e-12 pj=4e-6\nRBLEED RAIL 0 10meg\n'
    deck+='VDD VDD 0 PWL(0 0 100n 0 1100n 3.3 2000n 3.3 2100n 0 3000n 0 4000n 3.3 5000n 3.3)\n'
    for leg in ('P','N'):
        deck+=(f'V{leg} SOURCE_{leg} 0 3.3\nR{leg} SOURCE_{leg} PAD_{leg} 50\n'
               f'DLOW{leg} 0 PAD_{leg} diode_nd2ps_06v0 area=22.5e-12 pj=51.8e-6 m=4\n'
               f'DHIGH{leg} PAD_{leg} RAIL diode_pd2nw_06v0 area=22.5e-12 pj=51.8e-6 m=4\n')
    deck+=control(work,'retained','tran 1n 5u uic','v(VDD) v(RAIL) v(PAD_P) i(VDD) i(VP) v(xcl.n4)')
    deck=deck.replace('.control\n','.control\nset numdgt=15\n')
    (work/'retained.spice').write_text(deck)
    (work/'.spiceinit').write_text('set ngbehavior=hs\n')
    result=subprocess.run(['ngspice','-b','retained.spice'],cwd=work,capture_output=True,text=True,timeout=60)
    (work/'retained.log').write_text(result.stdout+result.stderr);result.check_returncode()
    rows=np.atleast_2d(np.loadtxt(work/'retained.dat',skiprows=1))
    complete=bool(np.isfinite(rows).all() and rows[-1,0]>=5e-6*(1-1e-9))
    if not complete:raise RuntimeError('Isolated protection rail did not finish retained supply cycle')
    windows={}
    for name,start,end in [('cold_unpowered',0,100e-9),('powered',1.5e-6,2e-6),
                            ('supply_fall',2e-6,2.1e-6),('unpowered',2.5e-6,3e-6),
                            ('recovery',3e-6,4e-6),('recovered',4.5e-6,5e-6)]:
        a=rows[(rows[:,0]>=start)&(rows[:,0]<=end)]
        if not len(a):raise RuntimeError('Missing isolated-rail state: '+name)
        windows[name]=dict(rail_min_v=float(a[:,2].min()),rail_max_v=float(a[:,2].max()),
            pad_min_v=float(a[:,3].min()),pad_max_v=float(a[:,3].max()),
            peak_functional_supply_backfeed_a=float(max(0,a[:,4].max())),
            peak_peer_source_a=float(max(0,-a[:,5].min())),
            clamp_gate_peak_v=float(a[:,6].max()))
    return dict(status='isolated_rail_architecture_probe_not_adopted',transient_complete=complete,
        native_clamp='gf180mcu_fd_io__dvdd',rail_bleed_ohm=1e7,states=windows,
        decision='Do not adopt as a drop-in protection circuit: ordinary startup activates the clamp and loads the peer. Determine allowed readiness/charging behavior and verify false-trigger immunity before selecting or modifying the clamp.',
        limitations=['Two unchanged 3.3V peers through 50ohm sources; initially discharged rail uses UIC.',
            'Functional VDD feeds the isolated rail through a small PDK diode; reverse displacement current is retained.',
            'Native clamp schematic only; no custom layout, package, well/substrate extraction or attached core.',
            'No RF modulation, ESD pulse, protected-device survival or normal-signal false-trigger qualification.'])


def diode_screen(work,pdk):
    """Compare junction loading; ideal rail is an optimistic boundary, not a design."""
    cases={}
    for fingers in (1,2,4):
        # Published HV diode junction minimum and recommended maximum finger width.
        width,length=25.,.9
        area=width*length*1e-12;perimeter=2*(width+length)*1e-6
        devices=(f'DLOW 0 PAD diode_nd2ps_06v0 area={area} pj={perimeter} m={fingers}\n'
                 f'DHIGH PAD RAIL diode_pd2nw_06v0 area={area} pj={perimeter} m={fingers}\n')
        base=(f'Unqualified diode loading probe\n.include {pdk}/design.ngspice\n'
              f'.lib {pdk}/sm141064.ngspice diode_typical\n.temp 27\n'+devices)
        capacitances={}
        for common in (.4,1.65,3.,3.3):
            name=f'diode_{fingers}_{common}'.replace('.','p')
            deck=base+f'VP PAD 0 DC {common} AC 1\nVR RAIL 0 3.3\n'
            deck+=control(work,name,'ac lin 1 1G 1G','real(i(VP)) imag(i(VP))')
            row=np.atleast_2d(run_spice(work,name,deck))[0]
            capacitances[str(common)]=float(-row[2]/(2*np.pi*row[0]))
        name=f'diode_{fingers}_unpowered_functional_rail'
        # A retained powered peer drives through a finite 50 ohm source.
        deck=base+'VS SOURCE 0 3.3\nRS SOURCE PAD 50\nVR RAIL 0 0\n'
        deck+=control(work,name,'op','v(PAD) i(VR) i(VS)')
        row=np.atleast_2d(run_spice(work,name,deck))[0]
        cases[str(fingers)]=dict(fingers_per_diode=fingers,finger_width_um=width,
            junction_length_um=length,area_m2_per_finger=area,perimeter_m_per_finger=perimeter,
            two_diode_capacitance_f=capacitances,
            unpowered_functional_rail=dict(pad_v=float(row[1]),backfeed_a=float(row[2]),
                source_current_a=float(-row[3]),source_v=3.3,source_resistance_ohm=50))
    return dict(status='device_only_alternative_screen_not_adopted',cases=cases,
        rules_source='https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_4_5.html',
        tlp_source='https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_5_8.html',
        decision='Do not steer into functional VDD when powered-off peer drive is required. Evaluate a dedicated isolated protection rail and its real clamp before adopting this topology.',
        limitations=['Finger count is a sensitivity sweep, not a selected ESD rating or extrapolation of published TLP.',
            'AC rail is ideally fixed at 3.3V. Floating-rail rectification, rail impedance and cross-pad coupling are absent.',
            'No Nwell/substrate junction, guard ring, metal, package, rail clamp or secondary protection layout is included.',
            'Ordinary diode models establish nominal loading and backfeed, not ESD survival.'])


def audit(work,pdk,generated):
    work.mkdir(parents=True,exist_ok=False)
    families={}
    for family in FAMILIES:
        circuit=build(family)
        legs={}
        for leg in ('P','N'):
            devices=[d for d in circuit.devices if d.name.startswith('ESD_') and d.nodes[0]=='PAD_'+leg]
            if not devices or any(d.model!='nfet_06v0_dss' or d.nodes[1:]!=('VSS','VSS','VSS') for d in devices):
                raise ValueError('Reassess protection topology: '+family)
            legs[leg]=dict(unit_count=len(devices),widths_um=[d.w_um for d in devices],
                lengths_um=[d.l_um for d in devices],total_width_um=sum(d.w_um for d in devices),
                minimum_finger_width_met=all(d.w_um>=20 for d in devices),
                minimum_total_width_met=sum(d.w_um for d in devices)>=200,
                recommended_minimum_length_met=all(d.l_um>=.8 for d in devices))
        families[family]=legs
    configurations={(leg['unit_count'],tuple(leg['widths_um']),tuple(leg['lengths_um']))
                    for family in families.values() for leg in family.values()}
    if len(configurations)!=1:raise ValueError('Protection dimensions differ; require a separate loading delta per family')
    count,widths,lengths=configurations.pop()
    if len(set(widths))!=1 or len(set(lengths))!=1:raise ValueError('Mixed protection units require individual loading analysis')
    tx_path=generated/'wired-transmit-loading.json'
    tx_loading=json.loads(tx_path.read_text())
    capacitance_by_common_mode={}
    for common in sorted({1.65}|{case['pad_common_mode_v'] for case in tx_loading['cases'].values()}):
        experiments={}
        for name,units,width,length in [('current',count,widths[0],lengths[0]),('minimum_width_candidate',10,20.,.8)]:
            label=name+'_'+str(common).replace('.','p')
            deck=(f'Protection loading sizing screen {label}\n.include {pdk}/design.ngspice\n'
                  f'.lib {pdk}/sm141064.ngspice typical\n.temp 27\nVSS VSS 0 0\nVP PAD 0 DC {common} AC 1\n')
            for i in range(units):deck+=Mos(f'ESD{i}',('PAD','VSS','VSS','VSS'),'nfet_06v0_dss',width,length).spice()+'\n'
            deck+=control(work,label,'ac lin 1 1G 1G','real(i(VP)) imag(i(VP))')
            row=np.atleast_2d(run_spice(work,label,deck))[0]
            experiments[name]=dict(unit_count=units,width_um=width,length_um=length,
                device_only_capacitance_f=float(-row[2]/(2*np.pi*row[0])),
                model='nfet_06v0_dss',drain_sab_um=3.78,source_sab_um=.28)
        capacitance_by_common_mode[str(common)]=experiments
    experiments=capacitance_by_common_mode['1.65']
    delta=experiments['minimum_width_candidate']['device_only_capacitance_f']-experiments['current']['device_only_capacitance_f']
    estimates={};sources=[Path(__file__),Path(__file__).with_name('circuits.py'),Path(__file__).with_name('wired_receive.py')]
    for family in ('reference_clock','rf_receive','rf_transmit'):
        p=generated/(family.replace('_','-')+'-screen.json');r=json.loads(p.read_text());sources.append(p)
        estimates[family]=dict(current_extracted_odd_capacitance_f_per_leg=r['capacitance_f_per_leg']['odd'],
            estimated_capacitance_f_per_leg=[v+delta for v in r['capacitance_f_per_leg']['odd']],
            assigned_budget_f_per_leg=r['assigned_budget_f_per_leg'])
    p=generated/'wired-receive-usb-screen.json';r=json.loads(p.read_text());sources.append(p)
    estimates['wired_receive_usb']={name:dict(estimated_capacitance_f_per_leg=[v+delta for v in case['odd_mode_effective_capacitance_f_per_leg']],assigned_budget_f_per_leg=case['budget_f_per_leg']) for name,case in r['loading'].items()}
    sources.append(tx_path)
    estimates['wired_transmit']={}
    for name,case in tx_loading['cases'].items():
        measurements=capacitance_by_common_mode[str(case['pad_common_mode_v'])]
        extra=measurements['minimum_width_candidate']['device_only_capacitance_f']-measurements['current']['device_only_capacitance_f']
        baseline=case['modes']['odd']['at_1ghz']['effective_capacitance_f_per_leg']
        estimates['wired_transmit'][name]=dict(pad_common_mode_v=case['pad_common_mode_v'],
            current_effective_capacitance_f_per_leg=baseline,
            estimated_capacitance_f_per_leg=[v+extra for v in baseline],
            assigned_budget_f_per_leg=tx_loading['assigned_budget_f_per_leg'])
    sources += [Path(__file__).with_name('design.py'),Path(__file__).with_name('screen.py'),
                Path(__file__).resolve().parents[2]/'spec/analog-architecture.json',
                Path(__file__).resolve().parents[2]/'spec/contract.json',pdk/'design.ngspice',pdk/'sm141064.ngspice',pdk/'sm141064.spice']
    simulator=Path(shutil.which('ngspice')).resolve();sources.append(simulator)
    report=dict(status='current_protection_dimensions_do_not_meet_published_HV_ESD_guidance',
        simulator_path=str(simulator),simulator_sha256=hashlib.sha256(simulator.read_bytes()).hexdigest(),
        published_rules=dict(source=RULES_URL,minimum_finger_width_um=20,minimum_total_width_um=200,
            recommended_minimum_channel_length_um=.8,required_marker='ESD_MK',
            note='Dimensional subset only; recommended rules distinguished from minima. Full marker, ballast, contacts, guard-ring and interconnect checks remain required.'),
        published_tlp=dict(source=TLP_URL,trigger_v_approx=10.7,holding_v_approx=6.2,
            second_breakdown_current_a_per_um_approx=.007,second_breakdown_v_approx=8,
            applicability='Published no-ESD-implant HV NMOS characterization, not qualification of our geometry or an HBM rating. Do not extrapolate these values to the current 32um candidate.'),
        current_families=families,device_capacitance_experiments=experiments,
        device_capacitance_by_common_mode=capacitance_by_common_mode,
        added_device_capacitance_f=delta,loading_estimates=estimates,
        diode_alternative=diode_screen(work,pdk),
        isolated_rail_alternative=isolated_rail_screen(work/'isolated-rail',pdk),
        limitations=['Minimum-width candidate has no generated layout or verified multi-finger triggering/current sharing.',
            'Additive device-capacitance estimate holds current wiring fixed; replacement geometry and mode-dependent nonlinear loading are absent. Not a physical bound or integrated compliance result.',
            'Ordinary compact models do not establish snapback, second breakdown, oxide survival or discharge-path current capacity.',
            'Positive trigger and holding voltages require explicit coordination with protected-device transient limits and any secondary clamp.',
            'No ESD qualification is implied by ordinary DRC/LVS or normal-voltage lifecycle completion.'],
        source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in sources+[pdk.parent/'gf180mcu_fd_io.spice']})
    (work/'protection-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(device_capacitance_experiments=experiments,loading_estimates=estimates),indent=2))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--pdk-model-dir',type=Path,required=True)
    parser.add_argument('--generated',type=Path,required=True)
    a=parser.parse_args();audit(a.output_dir.resolve(),a.pdk_model_dir.resolve(),a.generated.resolve())
