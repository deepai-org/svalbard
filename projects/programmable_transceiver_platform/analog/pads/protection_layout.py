"""Parametric steering-junction primitives for the pending protection replacement.

These are reusable primitives, not another pad family or an adopted ESD design.
Physical terminal labels and extracted junction dimensions are checked before
publishing their views. Missing well-junction extraction is reported explicitly.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import numpy as np
from layout import magic,rectangles,IMAGE
from screen import control,run_spice

MODELS=('diode_nd2ps_06v0','diode_pd2nw_06v0')


def generate(work,*,junction_width_um=.9,finger_width_um=25.,pdk=None):
    if not .9<=junction_width_um<=5 or not .9<=finger_width_um<=25:
        raise ValueError('Use junction width 0.9..5um and finger width 0.9..25um')
    work.mkdir(parents=True,exist_ok=False)
    commands=['crashbackups stop','load workspace']
    for model in MODELS:
        commands+=['units internal',f'set cell [magic::gencell_makecell gf180mcu::{model} w {junction_width_um} l {finger_width_um} full_metal 1]',
                   'load $cell',f'save {model}','load workspace']
    commands+=['quit -noprompt']
    (work/'primitives.tcl').write_text('\n'.join(commands)+'\n')
    magic(work,'primitives.tcl')
    commands=['crashbackups stop'];report={}
    for model in MODELS:
        geometry=rectangles(work/(model+'.mag'))
        positive=model=='diode_pd2nw_06v0'
        center_layer='mvpdiodec' if positive else 'mvndiodec'
        outer_layer='mvnsubdiffcont' if positive else 'mvpsubdiffcont'
        def center(layer):
            rect=max(geometry[layer],key=lambda r:r[0]);return [(rect[0]+rect[2])/2,(rect[1]+rect[3])/2]
        terminals={'A':center(center_layer if positive else outer_layer),
                   'K':center(outer_layer if positive else center_layer)}
        if positive:terminals['SUB']=center('mvpsubdiffcont')
        commands+=['load '+model,'units microns']
        for number,(name,(x,y)) in enumerate(terminals.items(),1):
            commands += [f'box values {x-.05} {y-.05} {x+.05} {y+.05}',
                         f'label {name} center metal1',f'port make {number}']
        commands += ['save','select top cell','expand','drc check','drc catchup',
                     f'puts "PRIMITIVE_DRC {model} [drc list count total]"',
                     'extract all','ext2spice lvs','ext2spice cthresh 0','ext2spice',
                     f'gds write {model}.gds']
        nwell=geometry.get('nwell',[])
        if len(nwell)>1:raise ValueError('Well perimeter needs polygon union')
        report[model]=dict(terminals_um=terminals,
            nwell_area_um2=sum((r[2]-r[0])*(r[3]-r[1]) for r in nwell),
            nwell_perimeter_um=sum(2*(r[2]-r[0]+r[3]-r[1]) for r in nwell))
    commands+=['quit -noprompt'];(work/'extract.tcl').write_text('\n'.join(commands)+'\n')
    result=magic(work,'extract.tcl')
    for model,entry in report.items():
        match=re.search(r'PRIMITIVE_DRC '+model+r' (\d+)',result.stdout)
        if not match or int(match[1]):raise ValueError('Primitive DRC failed: '+model)
        text=(work/(model+'.spice')).read_text()
        devices=[line.split() for line in text.splitlines() if line.startswith('D')]
        if len(devices)!=1 or devices[0][1:4]!=['A','K',model]:
            raise ValueError('Extracted diode polarity/terminals differ: '+text)
        params=dict(t.split('=') for t in devices[0][4:])
        area=float(params['area'].removesuffix('p'));perimeter=float(params['pj'].removesuffix('u'))
        if abs(area-junction_width_um*finger_width_um)>1e-6 or abs(perimeter-2*(junction_width_um+finger_width_um))>1e-6:
            raise ValueError('Extracted diode dimensions differ')
        entry.update(drc_count=0,extracted_area_um2=area,extracted_perimeter_um=perimeter,
                     well_junction_device_extracted=False,
                     extracted_capacitor_count=sum(line.startswith('C') for line in text.splitlines()))
        subprocess.run([sys.executable,str(Path(__file__).with_name('render.py').resolve()),
                        str(work/(model+'.mag')),'--output',str(work/(model+'.png')),
                        '--title',model,'--primitive'],check=True,timeout=30)
    # Magic includes a linear Nwell area capacitance. Remove exactly that
    # extraction coefficient before inserting the nonlinear PDK well diode.
    # Retain metal fringe/coupling capacitance rather than deleting C(K,SUB).
    command=['docker','run','--rm','--network','none','--entrypoint','python3',IMAGE,
             '-c','from pathlib import Path; print(Path("/pdk/gf180mcuD/libs.tech/magic/gf180mcuD.tech").read_text(),end="")']
    tech=subprocess.run(command,capture_output=True,text=True,check=True,timeout=30).stdout
    changed,count=re.subn(r'(?m)^defaultareacap\s+nwell\s+well\s+120\s*$',
                         'defaultareacap nwell well 0',tech)
    if count!=3:raise ValueError('Reassess Nwell extraction coefficients')
    (work/'no-well-area.tech').write_text(changed)
    model='diode_pd2nw_06v0'
    shutil.copyfile(work/(model+'.spice'),work/(model+'-linear-well.spice'))
    shutil.copyfile(work/(model+'.ext'),work/(model+'-linear-well.ext'))
    commands=['crashbackups stop',f'tech load {work}/no-well-area.tech',
              'load '+model,'extract all','ext2spice lvs','ext2spice cthresh 0','ext2spice','quit -noprompt']
    # Inside the container the output directory is mounted at /work.
    commands[1]='tech load /work/no-well-area.tech'
    (work/'nonlinear-well.tcl').write_text('\n'.join(commands)+'\n')
    magic(work,'nonlinear-well.tcl')
    def well_cap(text):
        return sum(float(t[3].removesuffix('f')) for line in text.splitlines()
                   if (t:=line.split()) and t[0].startswith('C') and set(t[1:3])=={'K','SUB'})
    original=(work/(model+'-linear-well.spice')).read_text()
    residual=(work/(model+'.spice')).read_text()
    entry=report[model];removed=well_cap(original)-well_cap(residual)
    if abs(removed-entry['nwell_area_um2']*.120)>.001:
        raise ValueError('Nwell capacitance removal does not match physical well area')
    entry.update(removed_linear_well_capacitance_ff=removed,
                 residual_well_substrate_capacitance_ff=well_cap(residual),
                 nonlinear_well_model='diode_nw2ps_06v0')
    physical=residual.replace('.ends',f"DWELL SUB K diode_nw2ps_06v0 area={entry['nwell_area_um2']}p pj={entry['nwell_perimeter_um']}u\n.ends")
    (work/(model+'-with-well.spice')).write_text(physical)
    data=dict(status='steering_junction_primitives_not_integrated_or_ESD_qualified',
        junction_width_um=junction_width_um,finger_width_um=finger_width_um,primitives=report,image_id=IMAGE,
        extraction_technology_sha256=hashlib.sha256(tech.encode()).hexdigest(),
        limitations=['Ordinary DRC and extracted junction polarity/geometry checks only, not ESD qualification.',
            'Single-finger units. Finger array, discharge interconnect, rail clamp and secondary protection are not laid out here.',
            'Positive diode well junction is reconstructed from physical Nwell area/perimeter and labeled terminals. Its linear extraction area cap is removed while residual coupling is retained; this supplements, not duplicates, the extractor device graph.',
            'Retained pad layouts still use their declared grounded-gate protection. These primitives are not a replacement circuit.'],
        source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (Path(__file__),Path(__file__).with_name('layout.py'),Path(__file__).with_name('render.py'))})
    if pdk is not None:
        measurements={}
        definitions=(work/'diode_nd2ps_06v0.spice').read_text()+physical
        for mode,pad_ac,rail_ac in [('pad',1,0),('rail',0,1)]:
            deck=(f'Extracted steering junctions\n.include {pdk}/design.ngspice\n'
                  f'.lib {pdk}/sm141064.ngspice diode_typical\n.temp 27\n'+definitions+
                  f'VP PAD 0 DC 1.65 AC {pad_ac}\nVR RAIL 0 DC 3.3 AC {rail_ac}\n')
            for i in range(4):
                deck+=f'XLOW{i} 0 PAD diode_nd2ps_06v0\nXHIGH{i} PAD RAIL 0 diode_pd2nw_06v0\n'
            deck+=control(work,mode,'ac lin 1 1G 1G','real(i(VP)) imag(i(VP)) real(i(VR)) imag(i(VR))')
            row=np.atleast_2d(run_spice(work,mode,deck))[0]
            if not np.isfinite(row).all():raise ValueError('Nonfinite primitive loading')
            measurements[mode]=dict(pad_imaginary_admittance_s=float(-row[2]),
                rail_imaginary_admittance_s=float(-row[4]),
                pad_effective_capacitance_f=float(-row[2]/(2*np.pi*row[0])),
                rail_effective_capacitance_f=float(-row[4]/(2*np.pi*row[0])))
        data['electrical']=dict(fingers_per_diode=4,pad_dc_v=1.65,rail_dc_v=3.3,frequency_hz=1e9,
            measurements=measurements,scope='Extracted primitive capacitance plus nonlinear well junction; ideal rail and no inter-unit routing or clamp.')
        for source in (Path(__file__).with_name('screen.py'),pdk/'design.ngspice',pdk/'sm141064.ngspice',pdk/'sm141064.spice'):
            data['source_sha256'][str(source.resolve())]=hashlib.sha256(source.read_bytes()).hexdigest()
    (work/'protection-primitives.json').write_text(json.dumps(data,indent=2)+'\n')
    return data


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--junction-width-um',type=float,default=.9);p.add_argument('--finger-width-um',type=float,default=25.)
    p.add_argument('--pdk-model-dir',type=Path)
    a=p.parse_args();generate(a.output_dir.resolve(),junction_width_um=a.junction_width_um,finger_width_um=a.finger_width_um,
                             pdk=a.pdk_model_dir.resolve() if a.pdk_model_dir else None)
