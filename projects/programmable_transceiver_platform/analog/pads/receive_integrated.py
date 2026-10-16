"""Rebuild the selected RX/USB pad, discharge and primary protection as one model.

Canonical publication is not electrical acceptance: loading, physical controls,
trim, slew and protection qualification remain explicit first-pass gaps.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from design import PROJECT


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(work, publish, pdk, assembly=None):
    from layout import generate as build_base
    from receive_pad_layout import generate as attach_discharge
    from wired_protection_layout import generate as attach_primary
    from extract_audit import export_extracted, converted_graph, extracted_graph
    from protected_assembly import run as place
    from receive_screen import screen
    from loading_audit import screen as loading
    work.mkdir(parents=True,exist_ok=False)
    spec=PROJECT/'spec/schematic-implementation.json'
    selected=json.loads(spec.read_text())['io_pad_first_pass']
    base=work/'base'
    build_base(base,'wired_receive_usb',external_primary=True,
               **selected['generation_parameters']['wired_receive_usb'])
    export_extracted(base/'pad_wired_receive_usb_flat.ext',base/'physical.spice',capacitance=True)
    if converted_graph(base/'pad_wired_receive_usb.spice') != extracted_graph(base/'pad_wired_receive_usb_flat.ext'):
        raise ValueError('Selected RX base differs from generated layout')
    inputs=work/'discharge-inputs';inputs.mkdir()
    for source,name in [('pad_wired_receive_usb_flat.gds','wired-receive-usb.gds'),
                        ('layout-report.json','wired-receive-usb-layout.json'),
                        ('physical.spice','wired-receive-usb-extracted-c.spice')]:
        shutil.copyfile(base/source,inputs/name)
    discharge=work/'discharge'
    attach_discharge(discharge,inputs,publish/'receiver-core-discharge')
    staged=work/'primary-inputs';staged.mkdir()
    for source,name in [('combined.gds','rx_pad_with_discharge.gds'),
                        ('layout-report.json','layout-report.json'),
                        ('physical.spice','pad_wired_receive_usb.spice')]:
        shutil.copyfile(discharge/source,staged/name)
    pad=work/'pad'
    attach_primary(pad,staged,publish/'protection-network',
                   selected['primary_placement_um']['wired_receive_usb'],pdk)
    model=pad/'physical.spice'
    screen(work/'electrical',pdk,model)
    loading(work/'loading',pdk,model,floating_resistance=1e12)
    electrical=json.loads((work/'electrical/screen-report.json').read_text())
    audit=json.loads((pad/'model-audit.json').read_text())
    layout_check=json.loads((pad/'layout-screen.json').read_text())
    metadata=json.loads((pad/'placement-layout.json').read_text())
    if not (electrical['transient_complete'] and electrical['attached_receiver_core']['embedded_in_pad']
            and audit['device_graph_matches'] and metadata['fits_assigned_area']
            and layout_check['drc_count']==0 and layout_check['device_lvs_match']):
        raise ValueError('Incomplete protected RX construction or retained-state evidence')
    place(work/'placement',publish,assembly or publish/'provider-assembly-inputs',
          tx=publish/'wired-primary-protection/double-tails',receive=pad)
    subprocess.run([sys.executable,str(Path(__file__).with_name('render.py')),
        str(pad/'combined_flat.mag'),'--output',str(work/'layout.png'),
        '--title','Protected wired receive / USB with core discharge'],check=True)
    metadata.update(status='selected_protected_RX_model_not_electrically_qualified',
                    connected_protection=True,integrated_receiver_discharge=True)
    metadata.pop('allocation_accounting',None)
    metadata['allocation_basis']='Complete pad/protection/discharge union within wirepad allowance; no separate discharge increment charged.'
    sources=[Path(__file__),spec,PROJECT/'spec/analog-architecture.json',PROJECT/'spec/contract.json',
             Path(__file__).with_name('layout.py'),Path(__file__).with_name('receive_pad_layout.py'),
             Path(__file__).with_name('wired_protection_layout.py'),Path(__file__).with_name('wired_receive.py')]
    metadata['sources_sha256']={str(p.relative_to(PROJECT)):digest(p) for p in sources}
    (work/'layout-report.json').write_text(json.dumps(metadata,indent=2)+'\n')
    reports=[pad/'model-audit.json',pad/'layout-screen.json',work/'electrical/screen-report.json',
             work/'loading/loading-audit.json',work/'placement/assembly-screen.json']
    result=dict(status='selected_protected_RX_model_not_electrically_qualified',
        gds_roundtrip_device_graph_match=True,drc_count=0,device_count=audit['physical_devices'],
        integrated_receiver_discharge=True,area_um2=metadata['area_um2'],
        electrical_scope='Complete extracted protected pad/discharge, behavioral controls and core capacitance; retained external network.',
        limitations=['Serial-bypass loading may exceed the shared allocation; publication does not waive it.',
                     'Physical control guard, trim and slew implementation remain open.',
                     'No whole-ring device LVS, core-stress/current-capacity or ESD qualification.'],
        source_sha256={str(p):digest(p) for p in sources},
        report_sha256={str(p):digest(p) for p in reports})
    (work/'integrated-screen.json').write_text(json.dumps(result,indent=2)+'\n')
    files={'pad/combined.gds':'.gds','pad/physical.spice':'-extracted-c.spice',
           'layout-report.json':'-layout.json','layout.png':'.png',
           'electrical/screen-report.json':'-screen.json','electrical/lifecycle.spice':'-lifecycle.spice',
           'loading/loading-audit.json':'-loading.json','pad/model-audit.json':'-device-audit.json',
           'integrated-screen.json':'-integration.json','placement/assembly-screen.json':'-assembly-screen.json'}
    for source,suffix in files.items():shutil.copyfile(work/source,publish/('wired-receive-usb'+suffix))
    roundtrip=dict(drc_count=0,device_graph_match=True,gds_sha256=digest(pad/'combined.gds'),
        reference_sha256=digest(model),independent_audit=audit,
        scope='Combined streamed GDS imported and checked; physical device graph and nonlinear well correction audited. Not electrical or protection qualification.')
    (publish/'wired-receive-usb-gds-roundtrip.json').write_text(json.dumps(roundtrip,indent=2)+'\n')
    return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['output-dir','generated','pdk-model-dir']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--assembly-dir',type=Path)
    a=p.parse_args();run(a.output_dir.resolve(),a.generated.resolve(),a.pdk_model_dir.resolve(),
                        a.assembly_dir.resolve() if a.assembly_dir else None)
