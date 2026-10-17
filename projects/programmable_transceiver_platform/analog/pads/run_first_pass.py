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
    write_coverage(publish,results)


def integrated_model_inventory(publish):
    """Inventory canonical family artifacts; state presence is not acceptance."""
    from design import PROJECT
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
                  for name in ('active','disabled','reset','unpowered','reconfiguration')}
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
            model_bytes_match_recorded_screen_input=any(
                name.endswith('.spice') and digest==hashes['model'] for name,digest in sources.items()),
            stale_screen_sources=stale,stale_layout_sources=stale_layout,
            exported_layout_device_graph_matches_current_model=exported_layout_matches_model,
            source_manifest_present=bool(sources) and bool(layout.get('sources_sha256')),
            scope='Canonical family candidate only; named windows and matching input bytes do not prove performance, safety, or unchanged external-network topology.')
    return inventory


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
    report=dict(first_pass_complete=False,candidates=results,
                integrated_model_inventory=integrated_model_inventory(publish),
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
