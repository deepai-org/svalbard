"""Rebuild the current pad candidates and publish compact, scoped artifacts.

The coverage report is deliberately incomplete until every required family and
branch exists. Successful generation or a matching LVS is not a performance
verdict. Large transient waveforms stay in the specified scratch directory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from circuits import FAMILIES,build
from layout import generate,IMAGE,PDK
from extract_audit import audit
from analog_screen import screen as analog_screen


def lvs(work,left,left_cell,right,right_cell,output):
    # Paths and cell names are produced locally, not shell-interpolated user text.
    args=['docker','run','--rm','--network','none','--entrypoint','netgen',
          '--mount',f'type=bind,src={work},dst=/work','-w','/work',IMAGE,
          '-batch','lvs',f'{left} {left_cell}',f'{right} {right_cell}',
          f'{PDK}/libs.tech/netgen/gf180mcuD_setup.tcl',output]
    result=subprocess.run(args,capture_output=True,text=True,timeout=45)
    (work/(output+'.log')).write_text(result.stdout+result.stderr)
    result.check_returncode()
    text=(work/output).read_text()
    return 'Final result: Circuits match uniquely.' in text


def run(work,pdk,publish,families):
    work.mkdir(parents=True,exist_ok=True)
    publish.mkdir(parents=True,exist_ok=True)
    results={}
    rf_metadata=publish/'rf-receive-layout.json'
    connected_rf=(rf_metadata.exists() and json.loads(rf_metadata.read_text()).get('connected_protection')
                  and any(family in ('rf_receive','rf_transmit') for family in families))
    for family in families:
        if family in ('reference_clock','wired_receive_usb','wired_transmit'):continue
        if connected_rf and family in ('rf_receive','rf_transmit'):continue
        cell=build(family)
        root=work/family
        generate(root,family)
        audit(root,family)
        flat=cell.name+'_flat'
        from gds_roundtrip import check as check_gds_roundtrip
        exported=check_gds_roundtrip(root/'gds-roundtrip',root/(flat+'.gds'),root/'physical.spice',flat)
        if exported['drc_count'] or not exported['device_graph_match']:
            raise RuntimeError('Exported GDS differs from simulated physical devices: '+family)
        match=lvs(root,'physical-lvs.spice',flat+'_physical',cell.name+'.spice',cell.name,'physical-lvs.txt')
        if not match:raise RuntimeError('Physical-record LVS mismatch: '+family)
        extract=json.loads((root/'extraction-audit.json').read_text())
        if not extract['extractor_matches_schematic'] or not extract['independent_export_matches_extractor']:
            raise RuntimeError('Independent extracted graph mismatch: '+family)
        stock=json.loads((root/'layout-report.json').read_text())['stock_export_returncode']
        raw_match=None
        if stock==0:
            raw_match=lvs(root,flat+'.spice',flat,cell.name+'.spice',cell.name,'stock-lvs.txt')
        subprocess.run([sys.executable,str(Path(__file__).with_name('render.py')),str(root/(flat+'.mag')),
                        '--output',str(root/'layout.png'),'--title',family.replace('_',' ')],check=True,timeout=30)
        electrical=root/'electrical'
        analog_screen(electrical,pdk,root/'physical.spice',family)
        stem=family.replace('_','-')
        files={'gds-roundtrip/gds-roundtrip.json':stem+'-gds-roundtrip.json',flat+'.gds':stem+'.gds',cell.name+'.spice':stem+'.spice',
               'physical.spice':stem+'-extracted-c.spice','layout.png':stem+'.png',
               'layout-report.json':stem+'-layout.json','extraction-audit.json':stem+'-extraction.json',
               'physical-lvs.txt':stem+'-physical-lvs.txt','stock-export.tcl.log':stem+'-stock-export.log',
               'electrical/screen-report.json':stem+'-screen.json'}
        if stock==0:files['stock-lvs.txt']=stem+'-lvs.txt'
        for source,target in files.items():shutil.copyfile(root/source,publish/target)
        results[family]=dict(gds_roundtrip_device_graph_match=exported['device_graph_match'],physical_record_lvs_match=match,stock_export_lvs_match=raw_match,
                            stock_export_returncode=stock,
                            drc_count=json.loads((root/'layout-report.json').read_text())['drc_count'],
                            electrical_scope='extracted_capacitance_with_behavioral_core_boundary')
        print('Published '+family,flush=True)
    if 'wired_transmit' in families:
        from transmit_integrated import run as integrate_transmit
        results['wired_transmit'] = integrate_transmit(work/'connected-transmitter', publish, pdk)
        from transmit_loaded_dc import run as tx_loaded_dc
        tx_loaded_dc(work/'transmit-loaded-current', work/'connected-transmitter/fixture.spice')
        shutil.copyfile(work/'transmit-loaded-current/screen.json', publish/'wired-transmit-loaded-current.json')
        from wired_tx_loading import screen as tx_loading
        tx_loading(work/'transmit-loading', pdk, publish/'wired-transmit-extracted-c.spice')
        shutil.copyfile(work/'transmit-loading/wired-transmit-loading.json', publish/'wired-transmit-loading.json')
    if 'wired_receive_usb' in families:
        from receive_integrated import run as integrate_receive
        results['wired_receive_usb'] = integrate_receive(work/'connected-receiver', publish, pdk)
    if 'reference_clock' in families:
        from reference_integrated import run as integrate_reference
        reference = integrate_reference(work/'connected-reference', publish, pdk)
        results['reference_clock'] = dict(drc_count=0,
            device_count=reference['device_count'],
            electrical_scope='connected_primary_protection_with_behavioral_reference_receiver',
            integrated_report='reference-clock-integrated-screen.json')
    if connected_rf:
        from rf_integrated import run as build_rf
        from protected_assembly import run as assemble_rf
        from rf_publish import publish as publish_rf
        rfwork=work/'connected-rf';build_rf(rfwork,publish,pdk)
        assembled=work/'connected-rf-assembly'
        assemble_rf(assembled,publish,publish/'provider-assembly-inputs',rfwork/'pad')
        publish_rf(rfwork,publish,assembled/'assembly-screen.json')
        for family in ('rf_receive','rf_transmit'):
            results[family]=dict(gds_roundtrip_device_graph_match=True,drc_count=0,
                electrical_scope='connected_RF_protection_with_routing_overlay_and_behavioral_core')
    from design import PROJECT
    subprocess.run(['docker','run','--rm','--network','none','--entrypoint','python3',
        '--mount',f'type=bind,src={PROJECT},dst=/project,readonly',
        '--mount',f'type=bind,src={publish.resolve()},dst=/output',IMAGE,
        '/project/analog/pads/core_area.py','--project','/project',
        '--output','/output/attached-core-area.json'],check=True,timeout=60)
    write_coverage(publish,results)


def integrated_model_inventory(publish):
    """Inventory canonical family artifacts; state presence is not acceptance."""
    from design import PROJECT, resolve
    requirements=resolve()["families"]
    inventory={}
    for family in FAMILIES:
        stem=family.replace('_','-')
        paths={kind:publish/(stem+suffix) for kind,suffix in
               [('model','-extracted-c.spice'),('layout','-layout.json'),
                ('gds','.gds'),('screen','-screen.json')]}
        absent=[kind for kind,path in paths.items() if not path.exists()]
        if absent:
            inventory[family]=dict(missing_artifacts=absent)
            continue
        screen=json.loads(paths['screen'].read_text())
        layout=json.loads(paths['layout'].read_text())
        sources=screen.get('source_sha256',screen.get('sources_sha256',{}))
        states=screen.get('states',screen.get('lifecycle_states',{}))
        required={name:([key for key in states if key=='active' or key.startswith('active_')]
                        if name=='active' else [name] if name in states else [])
                  for name in requirements[family]['required_states']}
        hashes={kind:hashlib.sha256(path.read_bytes()).hexdigest() for kind,path in paths.items()}
        stale=[]
        for name,digest in sources.items():
            path=Path(name)
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                stale.append(name)
        stale_layout=[]
        for name,digest in layout.get('sources_sha256',{}).items():
            path=PROJECT/name
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                stale_layout.append(name)
        roundtrip_path=publish/(stem+'-gds-roundtrip.json')
        roundtrip=json.loads(roundtrip_path.read_text()) if roundtrip_path.exists() else {}
        exported_layout_matches_model=(roundtrip.get('drc_count')==0
            and roundtrip.get('device_graph_match') is True
            and roundtrip.get('gds_sha256')==hashes['gds']
            and roundtrip.get('reference_sha256')==hashes['model'])
        inventory[family]=dict(artifacts={kind:str(path.name) for kind,path in paths.items()},
            artifact_sha256=hashes,reported_transient_complete=screen.get('transient_complete',False),
            required_state_windows=required,all_required_state_names_present=all(required.values()),
            missing_required_states=[name for name,windows in required.items() if not windows],
            model_bytes_match_recorded_screen_input=any(
                name.endswith('.spice') and digest==hashes['model'] for name,digest in sources.items()),
            stale_screen_sources=stale,stale_layout_sources=stale_layout,
            exported_layout_device_graph_matches_current_model=exported_layout_matches_model,
            source_manifest_present=bool(sources) and bool(layout.get('sources_sha256')),
            scope='Canonical family candidate only; named windows and matching input bytes do not prove performance, safety, or unchanged external-network topology.')
    return inventory


def electrical_findings(publish):
    """Surface recorded failures without treating missing safety limits as passes.

    These are scoped observations, not a replacement for report provenance or
    a complete acceptance specification. Never promote a candidate to canonical.
    """
    from design import resolve
    requirements=resolve()['families']
    findings={}
    for family in FAMILIES:
        path=publish/(family.replace('_','-')+'-screen.json')
        if not path.exists():
            findings[family]={'status':'missing_screen'}
            continue
        data=json.loads(path.read_text())
        limits=[]
        if family=='wired_receive_usb':
            budget=requirements[family]['electrical_parameters']['capacitance_f_per_leg']
            for mode,values in data.get('loading',{}).items():
                measured=values['odd_mode_effective_capacitance_f_per_leg']
                limits.append(dict(quantity='odd_mode_capacitance_f_per_leg',mode=mode,
                    measured=measured,limit=budget,
                    status='recorded_limit_miss' if any(v>budget for v in measured) else 'recorded_within_limit'))
        if family=='rf_transmit':
            for mode,values in data.get('tx_load_power',{}).get('windows',{}).items():
                limits.append(dict(quantity='fundamental_tone_power',mode=mode,
                    measured_dbm=values['fundamental_power_dbm'],
                    status='recorded_within_limit' if values['meets_target_power'] else 'recorded_limit_miss',
                    scope='Recorded tone target only; not modulated RF acceptance.'))
        observations={}
        if family=='reference_clock':
            observations['bias_settling']=data.get('reference_bias_envelope')
        if family=='rf_transmit':
            startup_path=publish/'rf-transmit-startup-screen.json'
            if startup_path.exists():
                startup=json.loads(startup_path.read_text())
                observations['guarded_startup']=dict(
                    report=startup_path.name,
                    report_sha256=hashlib.sha256(startup_path.read_bytes()).hexdigest(),
                    source_hashes_current=bool(startup.get('source_sha256')) and all(
                        Path(name).exists() and hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest
                        for name,digest in startup.get('source_sha256',{}).items()),
                    guard_s=startup['guard_s'],gain=startup['gain'],
                    power_dbm=startup['power_dbm'],meets_tone_target=startup['meets_tone_target'],
                    shared_supply_gain_state_retained=startup['shared_supply_gain_state_retained'],
                    scope='Fixture-imposed cold-start guard, quiet peer and tone at stated gain. Not physical supervisor, nominal-gain or modulated acceptance.')
        findings[family]=dict(status='incomplete_electrical_acceptance',
            source_report=path.name,source_report_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            recorded_limit_checks=limits,observations=observations,
            unresolved=['core_terminal_voltage_current_duration_limits',
                        'physical_local_safe_state_controls',
                        'complete_supply_return_and_package_integration'],
            scope='Read with integrated_model_inventory source freshness. A recorded pass is neither current revalidation nor family acceptance; absent checks remain unassessed.')
    return findings


def tx_current_bus_estimate(publish):
    """Trunk-only sheet estimates, not distributed extraction or branch impedance."""
    from design import PROJECT
    geometry_path=publish/'wired-transmit-layout.json'
    sheet_path=publish/'rf-transmit-route-resistance.json'
    spec_path=PROJECT/'spec/schematic-implementation.json'
    if not geometry_path.exists() or not sheet_path.exists():return None
    geometry=json.loads(geometry_path.read_text());sheet=json.loads(sheet_path.read_text())
    selected=json.loads(spec_path.read_text())['io_pad_first_pass']['layout_parameters']['wired_transmit']['trunk_width_overrides_um']
    values=sheet['metal_sheet_ohm_per_square']['5']
    if len(values)!=3:raise ValueError('Unexpected PDK sheet resistance variants')
    nets={}
    for name,width in selected.items():
        actual=geometry['net_trunk_widths_um'][name]
        low,high=geometry['net_trunk_spans_um'][name]
        squares=(high-low)/actual
        nets[name]=dict(actual_width_um=actual,selected_width_um=width,
            selected_width_present=actual==width,trunk_span_um=high-low,
            nominal_ohm=squares*values[0],high_resistance_ohm=squares*values[1],
            low_resistance_ohm=squares*values[2])
    return dict(status='geometry_sheet_estimate_not_distributed_PEX',nets=nets,
        pdk_metal5_sheet_ohm_per_square=values,
        scope='End-to-end uniform trunk only. Does not include transverse/device access, vias, spreading, returns or current distribution among taps. Not total termination impedance or a guarantee of modeled performance.',
        model_gap='Current connected wired extraction includes capacitance but does not insert these signal-metal resistances.',
        source_sha256={str(p.resolve().relative_to(PROJECT)):hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (geometry_path,sheet_path,spec_path)})


def tx_macro_power_budget(publish):
    """Compare measured supply currents with allocations, not silicon ratings."""
    from design import PROJECT
    path=publish/'wired-transmit-screen.json'
    if not path.exists():return None
    screen=json.loads(path.read_text())
    if 'macro_supply_currents' not in screen:return None
    arch_path=PROJECT/'spec/analog-architecture.json'
    spec_path=PROJECT/'spec/schematic-implementation.json'
    contract_path=PROJECT/'spec/contract.json'
    architecture=json.loads(arch_path.read_text())
    allocations=json.loads(spec_path.read_text())['io_pad_first_pass']['tx_attached_macro_allocations']
    contract=json.loads(contract_path.read_text())
    wire=next(v for v in contract['power']['domains'] if v['id']=='WIRE')
    ceiling=wire['per_connection_budget_ma']*len(wire['supply_pins'])
    modes={}
    for mode,result in screen['macro_supply_currents']['modes'].items():
        if result['mean_currents_a'] is None:continue
        owners={}
        for instance,current in result['mean_currents_a'].items():
            if instance=='Xpad':owner='detect' if mode=='DETECT' else 'txpad'
            elif instance=='XBUF':owner=allocations['buffer']['block']
            elif instance=='XCTL':owner=allocations['interlock']['block']
            elif instance.startswith('XDRIVE_TMDS_'):owner=architecture['blocks']['tmds'].get('merged_into',{}).get('block','tmds')
            elif instance.startswith('XDRIVE_'):owner=allocations['steering_driver']['block']
            else:raise ValueError('Unmapped macro current: '+instance)
            owners[owner]=owners.get(owner,0)+current*1000
        overrides=architecture['resource_policy']['branch_current_overrides_ma'].get('wired_tmds',{}) if mode=='TMDS' else {}
        budget=lambda name:overrides.get(name,architecture['blocks'][name]['resource_allocation']['current_budget_ma']['wired'])
        other=sum(budget(name) for name,b in architecture['blocks'].items() if b['supply']=='wire' and name not in owners)
        blocks={name:dict(measured_macro_mean_ma=value,
            wired_mode_allocation_ma=budget(name),
            measured_macro_alone_exceeds_allocation=value>budget(name))
            for name,value in owners.items()}
        total=result['mean_total_vdd_draw_a']*1000
        modes[mode]=dict(blocks=blocks,observed_tx_mean_ma=total,
            wire_domain_allocation_ma=ceiling,headroom_for_other_wire_blocks_ma=ceiling-total,
            other_wire_block_allocations_ma=other,
            observed_tx_plus_other_allocations_ma=total+other,
            combined_allocation_screen_exceeds=total+other>ceiling)
    return dict(status='short_window_measurement_against_design_allocations_not_pin_ratings',modes=modes,
        scope='Macro currents are partial block burdens. Other wire blocks use allocations, not measurements, and are included as a simultaneous-operation planning screen. Top-level fixture bias current remains in total TX draw. No power-budget increase, sustained-current guarantee or package rating is inferred.',
        source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in (path,arch_path,spec_path,contract_path)})


def rf_supply_planning(publish):
    from design import PROJECT
    architecture=json.loads((PROJECT/'spec/analog-architecture.json').read_text())
    contract=json.loads((PROJECT/'spec/contract.json').read_text())
    domain=next(d for d in contract['power']['domains'] if d['id']=='RF')
    ceiling=domain['per_connection_budget_ma']*len(domain['supply_pins'])
    modes={}
    for mode in ('rf_rx','rf_tx'):
        branch=architecture['resource_policy']['primary_current_case_by_mode'].get(mode)
        overrides=architecture['resource_policy']['branch_current_overrides_ma'].get(branch,{})
        blocks={name:overrides.get(name,b['resource_allocation']['current_budget_ma'][mode])
                for name,b in architecture['blocks'].items() if b['supply']=='rf'}
        total=sum(blocks.values())
        modes[mode]=dict(primary_current_case=branch,block_allocations_ma=blocks,
            total_block_allocations_ma=total,domain_allocation_ma=ceiling,allocations_exceed_domain=total>ceiling)
    path=publish/'rf-transmit-screen.json'
    evidence=json.loads(path.read_text()) if path.exists() else {}
    return dict(status='RF_domain_planning_consistency_not_measured_pin_capacity',modes=modes,
        modeled_driver_active_bias_floor_a=evidence.get('finite_tx_driver',{}).get('active_bias_current_floor_a'),
        scope='Warm block allocations are retained; the RF driver current floor is an assigned behavioral load, not measured transistor performance. Supply/return distribution and current capacity remain unqualified.')


def write_coverage(publish,results):
    retained_path=publish/'retained-screen.json'
    retained_evidence=None
    if retained_path.exists():
        data=json.loads(retained_path.read_text())
        current=all(Path(p).exists() and hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
                    for p,h in data['source_sha256'].items())
        retained_evidence=dict(status=data['status'],transient_complete=data['transient_complete'],
            source_hashes_current=current,report_sha256=hashlib.sha256(retained_path.read_bytes()).hexdigest(),
            scope='Combined representative host/control cells and all eighteen native supply pads; DC is not retained-state coverage.')
    tx_loading_evidence=None
    tx_loading_path=publish/'wired-transmit-loading.json'
    if tx_loading_path.exists():
        data=json.loads(tx_loading_path.read_text())
        current=all(Path(p).exists() and hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
                    for p,h in data['source_sha256'].items())
        tx_loading_evidence=dict(source_hashes_current=current,
            report_sha256=hashlib.sha256(tx_loading_path.read_bytes()).hexdigest(),
            cases_exceeding_1ghz_odd_budget=[name for name,case in data['cases'].items()
                if max(case['modes']['odd']['at_1ghz']['effective_capacitance_f_per_leg'])>data['assigned_budget_f_per_leg']],
            scope='Biased small-signal characterization; exceeding the loading allocation is not by itself a protocol-failure verdict.')
    protection_evidence=None
    protection_path=publish/'protection-audit.json'
    if protection_path.exists():
        data=json.loads(protection_path.read_text())
        current=all(Path(p).exists() and hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
                    for p,h in data['source_sha256'].items())
        protection_evidence=dict(status=data['status'],source_hashes_current=current,
            report_sha256=hashlib.sha256(protection_path.read_bytes()).hexdigest(),
            minimum_widths_met=all(v['minimum_finger_width_met'] and v['minimum_total_width_met']
                for family in data['current_families'].values() for v in family.values()),
            scope='Published dimensional comparison and compact-model loading estimate; not ESD qualification.')
    compliance_evidence=None
    compliance_path=publish/'wired-transmit-compliance.json'
    if compliance_path.exists():
        data=json.loads(compliance_path.read_text())
        current=all(Path(p).exists() and hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
                    for p,h in data['source_sha256'].items())
        compliance_evidence=dict(source_hashes_current=current,
            report_sha256=hashlib.sha256(compliance_path.read_bytes()).hexdigest(),
            all_loaded_currents_within_3_percent=all(c['loaded_current_within_3_percent'] for c in data['cases'].values()),
            scope='Nominal extracted-circuit DC check, including aligned maximum MAIN+POST; not timing or variation qualification.')
    pullup_evidence=None
    pullup_path=publish/'wired-transmit-pullup-screen.json'
    pullup_closure=publish/'wired-transmit-pullup-closure.json'
    if pullup_path.exists() and pullup_closure.exists():
        data=json.loads(pullup_path.read_text());closure=json.loads(pullup_closure.read_text())
        digest=hashlib.sha256(pullup_path.read_bytes()).hexdigest()
        pullup_evidence=dict(external_network=data['external_network'],
            source_hashes_current=all(Path(name).exists() and hashlib.sha256(Path(name).read_bytes()).hexdigest()==value
                for name,value in data['source_sha256'].items()),
            report_sha256=digest,closure_binds_report=digest in closure['source_sha256'].values(),
            sampled_lifecycle_gate_pass=closure['lifecycle_gate_pass'],
            contiguous_ready_hold_ns=closure['observed_contiguous_ready_hold_ns'],
            active_peer_mean_draw_a=data['external_peer_states']['active_tmds']['peer_mean_draw_a'],
            scope='Recorded extracted TX components with an independent continuously powered split pull-up network. Consult source freshness: this can predate the selected geometry. Not eye-mask, protocol or protection acceptance.')
    area_path=publish/'attached-core-area.json'
    area_evidence=None
    if area_path.exists():
        from design import PROJECT
        data=json.loads(area_path.read_text())
        current=all((PROJECT/name).exists() and hashlib.sha256((PROJECT/name).read_bytes()).hexdigest()==digest
                    for name,digest in data['source_sha256'].items())
        area_evidence=dict(all_reservations_fit=data['all_reservations_fit'],
            source_hashes_current=current,report_sha256=hashlib.sha256(area_path.read_bytes()).hexdigest(),
            scope='Selected attached TX macro footprints and reservations only; not whole-ring placement or routing acceptance.')
    routing_evidence=None
    routing_path=publish/'attached-core-steering-routing.json'
    routed_oas=publish/'attached-core-steering-routed.oas'
    if routing_path.exists():
        from design import PROJECT
        data=json.loads(routing_path.read_text())
        routing_evidence=dict(status=data['status'],route_count=len(data['routes']),
            report_sha256=hashlib.sha256(routing_path.read_bytes()).hexdigest(),
            source_hashes_current=all((PROJECT/name).exists() and hashlib.sha256((PROJECT/name).read_bytes()).hexdigest()==digest
                for name,digest in data['source_sha256'].items()),
            routed_artifact_matches=routed_oas.exists() and hashlib.sha256(routed_oas.read_bytes()).hexdigest()==data['routed_oas_sha256'],
            scope='Six steering output routes only; supplies, control and buffer hookups, DRC/LVS and routed timing remain incomplete.')
    steering_connectivity=None
    connectivity_path=publish/'attached-core-steering-connectivity.json'
    if connectivity_path.exists():
        from design import PROJECT
        data=json.loads(connectivity_path.read_text())
        steering_connectivity=dict(status=data['status'],faults_detected=data['faults_detected'],
            report_sha256=hashlib.sha256(connectivity_path.read_bytes()).hexdigest(),
            source_hashes_current=all((PROJECT/name).exists() and hashlib.sha256((PROJECT/name).read_bytes()).hexdigest()==digest
                for name,digest in data['source_sha256'].items()),
            scope='Geometry-only extraction of six routes in the complete TX cluster. Not whole-ring connectivity, transistor LVS, spacing DRC or routed timing.')
    report=dict(first_pass_complete=False,candidates=results,attached_core_area=area_evidence,
                attached_core_steering_routes=routing_evidence,
                attached_core_steering_connectivity=steering_connectivity,
                wired_tx_macro_power=tx_macro_power_budget(publish),
                wired_tx_current_bus_estimate=tx_current_bus_estimate(publish),wired_tx_pullup_evidence=pullup_evidence,
                rf_supply_planning=rf_supply_planning(publish),
                integrated_model_inventory=integrated_model_inventory(publish),
                electrical_findings=electrical_findings(publish),
                combined_retained_screen=retained_evidence,
                protection_design_audit=protection_evidence,wired_tx_loading=tx_loading_evidence,
                wired_tx_current_compliance=compliance_evidence,
                missing=[
                    'protection-to-core voltage/current-versus-duration contracts and coordinated circuits; discharge-current capacity remains unqualified',
                    'physical local reset/brownout/readiness and safe power-domain crossings, including independent-host backfeed isolation or enforced sequencing',
                    'physical attached RF LNA/driver, reference receiver and TX bias/control interfaces with accounted loading, headroom and power',
                    'whole-ring device connectivity, core macro area/placement, distributed supply/return paths, bounded package coupling and full-bank host switching',
                    'representative electrical acceptance with actual external networks: TMDS pull-up load, AC-coupled wired lane, USB bidirectional operation, RF and differential reference',
                    'canonical wired TX current regulation, RX bypass loading, RF TX margin and reference startup; candidate improvements are not canonical acceptance',
                    'wired RX/USB trim, slew and physical termination exclusion; wired TX termination trim and buffer/interlock integration',
                    'floating-conductor initial charge bounds; current screens reject transient operating-point fallback but numerical anchors are not physical discharge paths'],
                scope='Only listed candidates were rebuilt. Other artifacts must retain their original source hashes.')
    (publish/'coverage.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--pdk-model-dir',type=Path,required=True)
    parser.add_argument('--publish-dir',type=Path,required=True)
    parser.add_argument('--families',nargs='+',choices=FAMILIES,default=FAMILIES)
    a=parser.parse_args()
    run(a.output_dir.resolve(),a.pdk_model_dir.resolve(),a.publish_dir.resolve(),a.families)
