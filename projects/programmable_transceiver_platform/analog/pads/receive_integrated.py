"""Build and publish the connected RX pad, preserving its base as a build component."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def run(work, publish, pdk, assembly=None):
    from design import PROJECT
    from receive_pad_layout import generate, verify_provider_placement
    from receive_screen import screen
    from loading_audit import screen as loading
    from gds_roundtrip import check
    work.mkdir(parents=True, exist_ok=False)
    base=publish/'receiver-pad-base'
    base.mkdir(exist_ok=True)
    current=json.loads((publish/'wired-receive-usb-layout.json').read_text())
    if not current.get('integrated_receiver_discharge'):
        for suffix in ('.gds','-layout.json','-extracted-c.spice'):
            name='wired-receive-usb'+suffix
            shutil.copyfile(publish/name,base/name)
    integration=work/'integration'
    generate(integration,base,publish/'receiver-core-discharge')
    if assembly:verify_provider_placement(work/'placement',integration,assembly)
    model=integration/'physical.spice'
    roundtrip=check(work/'roundtrip',integration/'combined.gds',model,'rx_pad_with_discharge')
    if roundtrip['drc_count'] or not roundtrip['device_graph_match']:
        raise ValueError('Integrated RX exported device graph failed')
    screen(work/'electrical',pdk,model)
    loading(work/'loading',pdk,model)
    electrical=json.loads((work/'electrical/screen-report.json').read_text())
    if not electrical['transient_complete'] or not electrical['attached_receiver_core']['embedded_in_pad']:
        raise ValueError('Integrated RX lifecycle or embedded discharge missing')
    subprocess.run([sys.executable,str(Path(__file__).with_name('render.py')),
        str(integration/'rx_pad_with_discharge.mag'),'--output',str(work/'layout.png'),
        '--title','Wired receive / USB with core discharge'],check=True)
    metadata=json.loads((integration/'layout-report.json').read_text())
    metadata['status']='integrated_receiver_pad_scoped_checks_complete_not_qualified'
    metadata['sources_sha256'].update({str(Path(__file__).relative_to(PROJECT)):
        hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        str(Path(__file__).with_name('receive_pad_layout.py').relative_to(PROJECT)):
        hashlib.sha256(Path(__file__).with_name('receive_pad_layout.py').read_bytes()).hexdigest()})
    (work/'layout-report.json').write_text(json.dumps(metadata,indent=2)+'\n')
    files={'integration/combined.gds':'.gds','integration/physical.spice':'-extracted-c.spice',
           'layout-report.json':'-layout.json','layout.png':'.png',
           'roundtrip/gds-roundtrip.json':'-gds-roundtrip.json',
           'electrical/screen-report.json':'-screen.json','loading/loading-audit.json':'-loading.json',
           'integration/layout-screen.json':'-integration.json',
           'integration/allocation-screen.json':'-allocation.json'}
    for source,suffix in files.items():shutil.copyfile(work/source,publish/('wired-receive-usb'+suffix))
    return dict(gds_roundtrip_device_graph_match=True,drc_count=0,
                integrated_receiver_discharge=True,
                electrical_scope='connected_pad_and_discharge_with_behavioral_control_and_core_capacitance')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--generated',type=Path,required=True)
    p.add_argument('--pdk-model-dir',type=Path,required=True)
    p.add_argument('--assembly-dir',type=Path)
    a=p.parse_args()
    run(a.output_dir.resolve(),a.generated.resolve(),a.pdk_model_dir.resolve(),
        a.assembly_dir.resolve() if a.assembly_dir else None)
