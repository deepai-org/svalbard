"""Code-driven connected transistor-core layout for the gated buffer candidate.

Compensation, reference/bias passives and pad hookup are separate integration
work. DRC/connectivity do not establish current capacity or analog performance.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
import shutil
from pathlib import Path
from termination_buffer import build
from layout import magic, terminals, trunk_geometry
from extract_audit import extracted_graph, export_extracted, key


def generate(work, source_width=320., complementary_isolation=False, circuit=None, cell_name="buffer_core", bounded_internal_routes=False):
    work.mkdir(parents=True,exist_ok=False)
    if circuit is None:circuit=build(first_stage_scale=10,gated=True,source_width=source_width,complementary_isolation=complementary_isolation)
    if not cell_name.replace("_","").isalnum():raise ValueError("Invalid cell name")
    kinds=sorted({(d.model,d.w_um,d.l_um) for d in circuit.devices})
    cells={k:f'primitive_{i}' for i,k in enumerate(kinds)}
    commands=['crashbackups stop','load workspace']
    for (model,w,l),name in cells.items():
        if model.startswith('ppoly'):
            commands += ['units internal',f'set cell [magic::gencell_makecell gf180mcu::{model} w {w} l {l} guard 1 full_metal 1]', 'load $cell',f'save {name}','load workspace']
            continue
        commands += ['units internal',f'set cell [magic::gencell_makecell gf180mcu::{model} w {w} l {l} nf 1 guard 1 topc 0 botc 1 full_metal 1 gate_to_polycont 0.6 gate_extension 0.8 diff_gate_space 0.3]',
                     'load $cell',f'save {name}','load workspace']
    commands+=['quit -noprompt'];(work/'primitives.tcl').write_text('\n'.join(commands)+'\n');magic(work,'primitives.tcl')
    pins={k:terminals(work/(name+'.mag')) for k,name in cells.items()}
    nets=sorted({n for d in circuit.devices for n in d.nodes})
    # Give all shared load-current paths the same wide trunk as the supply.
    tracks={};widths={};edge=2.78
    for net in nets:
        width=8. if net in {'VDD','VSS','TOP','BOTTOM','LOCAL_OUT','OUT','BUFFER_COMPLEMENT_WELL'} else .44
        tracks[net]=edge+width/2;widths[net]=width;edge+=width+1.
    if edge>146:raise ValueError('Buffer trunk bank exceeds placement reservation')
    columns=7;origin=4.;height=origin+math.ceil(len(circuit.devices)/columns)*26+6
    commands=['crashbackups stop','load buffer_core','units microns']
    def rect(layer,x1,y1,x2,y2):
        commands.extend([f'box values {min(x1,x2):.4f} {min(y1,y2):.4f} {max(x1,x2):.4f} {max(y1,y2):.4f}',f'paint {layer}'])
    def via(x,y,lo,hi):
        for m in range(lo,hi+1):
            h=.19 if m==1 else .22 if m==5 else .2
            rect(f'metal{m}',x-h,y-h,x+h,y+h)
        for m in range(lo,hi):
            h=.13 if m==1 else .14;rect(f'via{m}',x-h,y-h,x+h,y+h)
    def wire(layer,x1,y1,x2,y2):
        h=.22 if layer=='metal5' else .2
        rect(layer,min(x1,x2)-h,min(y1,y2)-h,max(x1,x2)+h,max(y1,y2)+h)
    access={n:[] for n in nets}
    for i,d in enumerate(circuit.devices):
        row,col=divmod(i,columns)
        for pin,net in enumerate(d.nodes):access[net].append(origin+26*row+1+(4*col+pin)*.8)
    spans={net:([min(access[net])-.5,max(access[net])+.5] if bounded_internal_routes and net not in circuit.ports else [origin-.5,height+.5]) for net in nets}
    for net,x in tracks.items():rect('metal5',x-widths[net]/2,spans[net][0],x+widths[net]/2,spans[net][1])
    for i,d in enumerate(circuit.devices):
        row,col=divmod(i,columns);cx,cy=12+21*col,origin+26*row+13;k=(d.model,d.w_um,d.l_um)
        commands += [f'getcell {cells[k]} child 0 0 parent {cx} {cy}',f'identify X{d.name}']
        for pin,((dx,dy),net) in enumerate(zip(pins[k],d.nodes)):
            x,y=cx+dx,cy+dy;escape=cx+((-2.5,0,4) if d.model.startswith('ppoly') else (2.5,0,-2.5,4))[pin];ry=origin+26*row+1+(4*col+pin)*.8
            via(x,y,1,2);wire('metal2',x,y,escape,y);via(escape,y,2,3)
            wire('metal3',escape,y,escape,ry);via(escape,ry,3,4)
            wire('metal4',escape,ry,tracks[net],ry);via(tracks[net],ry,4,5)
    for net in nets:
        x=tracks[net];label_y=height if net in circuit.ports else spans[net][1]-.5
        commands += [f'box values {x-.2} {label_y-.5} {x+.2} {label_y}',f'label {net} FreeSans 0.3 0 0 0 c metal5']
        if net in circuit.ports:commands += [f'port make {circuit.ports.index(net)+1}']
    commands += ['select top cell','flatten buffer_core_flat','load buffer_core_flat','save','select top cell','drc check','drc catchup','set f [open drc-count.txt w]','puts $f [drc list count total]','close $f','set f [open drc-details.txt w]','puts $f [drc listall why]','close $f','extract all','gds write buffer_core_flat.gds','quit -noprompt']
    (work/'layout.tcl').write_text(('\n'.join(commands)+'\n').replace('buffer_core',cell_name));magic(work,'layout.tcl')
    expected=Counter(key(d.model,d.nodes,d.w_um,d.l_um) for d in circuit.devices)
    actual=extracted_graph(work/(cell_name+'_flat.ext'))
    (work/'schematic.spice').write_text(circuit.spice())
    export_extracted(work/(cell_name+'_flat.ext'),work/'physical.spice',capacitance=True)
    report=dict(status='connected_small_circuit_layout_candidate',circuit=circuit.name,flat_cell=cell_name+'_flat',drc_count=int((work/'drc-count.txt').read_text()),device_count=len(circuit.devices),device_graph_matches=actual==expected,
        envelope_um=[150,height+1],envelope_area_um2=150*(height+1),
        limitations=['Compensation/reference/bias passives and TX pad integration absent.','Load-current trunks are 8um; individual device accesses and total current capacity remain unqualified.','No analog performance or whole-chip area acceptance.'],
        source_sha256={str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),Path(__file__).with_name('termination_buffer.py')]})
    from gds_markers import repair
    report['gds_marker_repair']=repair(work,cell_name+'_flat')
    rt=work/'roundtrip';rt.mkdir();shutil.copyfile(work/(cell_name+'_flat.gds'),rt/(cell_name+'_flat.gds'))
    (rt/'check.tcl').write_text('crashbackups stop\ngds read buffer_core_flat.gds\nload buffer_core_flat\nselect top cell\nexpand\ndrc check\ndrc catchup\nset f [open drc.txt w]\nputs $f [drc list count total]\nclose $f\nextract all\nquit -noprompt\n'.replace('buffer_core',cell_name))
    magic(rt,'check.tcl')
    report['gds_roundtrip']={'drc_count':int((rt/'drc.txt').read_text()),'device_graph_matches':extracted_graph(rt/(cell_name+'_flat.ext'))==actual}
    report['trunk_widths_um']=widths
    report['bounded_internal_routes']=bounded_internal_routes
    report['net_trunk_spans_um']=spans
    report['physical_sha256']=hashlib.sha256((work/'physical.spice').read_bytes()).hexdigest()
    report['gds_sha256']=hashlib.sha256((work/(cell_name+'_flat.gds')).read_bytes()).hexdigest()
    (work/'layout.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if report['drc_count'] or not report['device_graph_matches'] or report['gds_roundtrip']['drc_count'] or not report['gds_roundtrip']['device_graph_matches']:raise ValueError('Buffer core layout verification failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument("--source-width",type=float,default=320.)
    p.add_argument("--complementary-isolation",action="store_true")
    a=p.parse_args();generate(a.output_dir.resolve(),a.source_width,a.complementary_isolation)
