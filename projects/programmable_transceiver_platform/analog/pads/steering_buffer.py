"""Parametric supply-powered CMOS predriver for a TX steering gate.

A noninverting tapered chain replaces the fixture's zero-impedance output.
Input data/qualification remains a declared upstream boundary. No delay, drive
current or bandwidth is inferred from the sizing recipe alone.
"""
import math
from circuits import Circuit, Mos


def build(n_widths_um=(2.,8.,32.,128.), p_to_n_ratio=2., unit_width_um=16., length_um=.28):
    if len(n_widths_um)<2 or len(n_widths_um)%2:
        raise ValueError('Noninverting driver requires an even number of stages')
    values=[*n_widths_um,p_to_n_ratio,unit_width_um,length_um]
    if any(not math.isfinite(v) or v<=0 for v in values):raise ValueError('Invalid driver geometry')
    if not .8<=unit_width_um<=20 or length_um<.28:raise ValueError('Unsupported driver unit geometry')
    devices=[];incoming='IN'
    for stage,nwidth in enumerate(n_widths_um):
        outgoing='OUT' if stage==len(n_widths_um)-1 else f'STAGE_{stage}'
        for kind,width,rail in [('n',nwidth,'VSS'),('p',nwidth*p_to_n_ratio,'VDD')]:
            count=math.ceil(width/unit_width_um);unit=width/count
            if unit<.8:raise ValueError('Driver finger narrower than supported PCell')
            for finger in range(count):
                devices.append(Mos(f'S{stage}_{kind}{finger}',(outgoing,incoming,rail,rail),
                    ('nfet_' if kind=='n' else 'pfet_')+'03v3',unit,length_um))
        incoming=outgoing
    return Circuit('tx_steering_buffer',['VDD','VSS','IN','OUT'],devices,{},[
        'Supply-powered finite driver; input data gating and qualification are upstream boundaries.',
        'Nominal sizing is not a demonstrated edge-rate, loading, power or PVT specification.',
        'Default-off input behavior, upstream power-domain crossings and shared supply impedance require integration.'])


def generate(work, compact=False):
    """Build the shared selected recipe and verify its physical implementation."""
    import hashlib
    import json
    import subprocess
    import sys
    from pathlib import Path
    from design import PROJECT, build_integration_candidate
    from termination_buffer_layout import generate as layout_generate
    circuit=build_integration_candidate('tx_steering_buffer')
    if compact:   # PD40: multi-finger arrays with OUT power straps (termination_buffer_array_layout.py)
        from termination_buffer_array_layout import generate as array_generate
        array_generate(work,circuit=circuit,cell_name='tx_steering_buffer',power_nets=('OUT',))
    else:
        layout_generate(work,circuit=circuit,cell_name='tx_steering_buffer')
    report_path=work/'layout.json'
    report=json.loads(report_path.read_text())
    report['source_sha256'].update({str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (Path(__file__),Path(__file__).with_name('design.py'),PROJECT/'spec/schematic-implementation.json')})
    report['scope']='One steering buffer; repeated instances and electrical acceptance belong to the connected TX fixture.'
    report_path.write_text(json.dumps(report,indent=2)+'\n')
    subprocess.run([sys.executable,str(Path(__file__).with_name('render.py')),
        str(work/'tx_steering_buffer_flat.mag'),'--output',str(work/'layout.png'),
        '--primitive','--title','TX steering buffer: connected four-stage CMOS chain'],check=True)
    return report


def publish(work, destination):
    import shutil
    destination.mkdir(parents=True,exist_ok=True)
    for name in ('physical.spice','tx_steering_buffer_flat.gds','tx_steering_buffer_flat.mag','layout.json','layout.png'):
        shutil.copyfile(work/name,destination/name)


if __name__=='__main__':
    import argparse
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--compact',action='store_true',help='PD40 compact array layout (generated/steering-buffer-compact/)')
    args=parser.parse_args();generate(args.output_dir.resolve(),args.compact)
