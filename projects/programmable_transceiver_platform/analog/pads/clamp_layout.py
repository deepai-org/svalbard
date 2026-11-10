"""Reuse native clamp geometry and replace its MOS capacitors with shared MIMs.

This produces a standalone clamp macro. Pad-array wiring, ESD stress and
assembly integration remain separate checks; native geometry is not assumed
qualified after modification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import re
import sys


def assemble(work):
    import klayout.db as k
    config=json.loads((work/'config.json').read_text())
    source=Path('/pdk/gf180mcuD/libs.ref/gf180mcu_fd_io/gds/gf180mcu_fd_io.gds')
    layout=k.Layout();layout.read(str(source));base=layout.cell('GF_NI_DVDD_BASE')
    def box(x,y,r):return k.DBox(x-r,y-r,x+r,y+r).to_itype(layout.dbu)
    m2=k.Region(base.begin_shapes_rec(layout.layer(36,0)))
    m3=k.Region(base.begin_shapes_rec(layout.layer(42,0)))
    candidates={'timing':[],'rail':[],'ground':[]};removed=[];leaves=set()
    def walk(cell,transform):
        for inst in cell.each_inst():
            child=layout.cell(inst.cell_index);t=transform*inst.dcplx_trans
            if child.name.startswith('nmoscap_6p0_'):
                kind='rail' if child.name.endswith('450') else 'timing' if child.name.endswith('454') else None
                if kind is None:raise ValueError('Reassess native capacitor mapping')
                removed.append(dict(cell=child.name,transform=str(t),role=kind));leaves.add(child.cell_index())
                for ix in layout.layer_indexes():
                    for shape in child.each_shape(ix):
                        if shape.is_text() and shape.text.string in ('G','D'):
                            point=t*k.DPoint(shape.text.x*layout.dbu,shape.text.y*layout.dbu)
                            probe=k.Region(box(point.x,point.y,.35))
                            if (probe-m2).is_empty() and (probe&m3).is_empty():
                                candidates[kind if shape.text.string=='G' else 'ground'].append((point.x,point.y))
            else:walk(child,t)
    walk(base,k.DCplxTrans())
    if sum(r['role']=='rail' for r in removed)!=4 or sum(r['role']=='timing' for r in removed)!=8:
        raise ValueError('Native MOS capacitor count differs')
    # Probe actual metal connectivity from native RC terminal labels. A metal2
    # shape over a capacitor gate can belong to another net; geometric overlap
    # alone is not a valid landing rule.
    flat=layout.create_cell('clamp_trace_flat')
    flat.insert(k.CellInstArray(base.cell_index(),k.Trans()));flat.flatten(False)
    tracer=k.LayoutToNetlist(k.RecursiveShapeIterator(layout,flat,[]))
    trace={n:tracer.make_layer(layout.layer(n,0),'L'+str(n)) for n in (34,35,36,38,42)}
    for layer in trace.values():tracer.connect(layer)
    for a,b in ((34,35),(35,36),(36,38),(38,42)):tracer.connect(trace[a],trace[b])
    tracer.extract_netlist()
    # Native VRC / VPLUS / VMINUS labels, transformed through the mirrored RC cell.
    probes={'timing':(8.18,155.805),'rail':(5.635,235.175),'ground':(37.435,184.05)}
    net_regions={}
    for role,point in probes.items():
        net=tracer.probe_net(trace[34],k.DPoint(*point))
        if net is None:raise ValueError('Native RC terminal probe missed metal')
        layer=34 if role=='timing' else 42
        net_regions[role]=tracer.shapes_of_net(net,trace[layer],True)
    def pick(region):
        for polygon in region.each():
            b=polygon.bbox().to_dtype(layout.dbu);x=(b.left+b.right)/2;y=(b.bottom+b.top)/2
            if (k.Region(box(x,y,.005))-region).is_empty():return (x,y)
        raise ValueError('No electrically identified via landing')
    timing_free=net_regions['timing'].sized(-350)-(m2+m3).sized(500)
    timing_anchor=pick(timing_free)
    rail_anchor=pick(net_regions['rail'].sized(-350)&k.Region(k.DBox(0,274,75,276).to_itype(layout.dbu)))
    ground_anchor=pick(net_regions['ground'].sized(-350)&k.Region(k.DBox(0,266,75,268).to_itype(layout.dbu)))
    # Preserve the parent wiring's landing metal, but remove MOS devices,
    # wells and leaf labels. No other native device geometry changes.
    for index in leaves:
        cell=layout.cell(index)
        for ix in layout.layer_indexes():
            info=layout.get_info(ix)
            if (info.layer,info.datatype) not in {(34,0),(35,0),(36,0),(38,0),(42,0)}:
                cell.shapes(ix).clear()
            else:
                for shape in list(cell.each_shape(ix)):
                    if shape.is_text():shape.delete()
    layout.read(str(work/'clamp_mim.gds'));mim=layout.cell('clamp_mim')
    root=layout.create_cell('pad_isolated_rail_clamp_layout')
    root.insert(k.DCellInstArray(base.cell_index(),k.DTrans()))
    layers={1:34,2:36,3:42,4:46,5:81};vias={1:35,2:38,3:40,4:41}
    def rect(layer,x1,y1,x2,y2):
        root.shapes(layout.layer(layer,0)).insert(k.DBox(min(x1,x2),min(y1,y2),max(x1,x2),max(y1,y2)).to_itype(layout.dbu))
    def wire(layer,a,b,width):
        if a[0]!=b[0] and a[1]!=b[1]:raise ValueError('Non-Manhattan route')
        h=width/2;rect(layer,min(a[0],b[0])-h,min(a[1],b[1])-h,max(a[0],b[0])+h,max(a[1],b[1])+h)
    def stack(x,y,lo,hi):
        for n in range(lo,hi+1):rect(layers[n],x-.24,y-.24,x+.24,y+.24)
        for n in range(lo,hi):
            h=.13  # GDS cut: every via is exactly 0.26 um (KLayout V*.1); Magic re-grows cuts on read
            rect(vias[n],x-h,y-h,x+h,y+h)
    anchors={};placements={}
    for kind,y in [('timing',175.),('rail',245.)]:
        x0,y0=timing_anchor if kind=='timing' else rail_anchor
        anchors[kind]=[x0,y0];placements[kind]=[105.,y]
        root.insert(k.DCellInstArray(mim.cell_index(),k.DTrans(105.,y)))
        stack(x0,y0,1 if kind=='timing' else 3,5)
        wire(81,(x0,y0),(105.,y0),1.)
        wire(81,(105.,y0),(105.,y),1.)
        # Both capacitor bottom plates are on the return net. The PCell's
        # left M4 overhang is outside its top plate, avoiding a via ambiguity.
        wire(46,(80.,y),(89.,y),2.)
    ground=ground_anchor
    stack(*ground,3,4)
    wire(46,ground,(80.,ground[1]),2.)
    wire(46,(80.,175.),(80.,ground[1]),2.)
    for text,(x,y),layer in [('DVSS',ground,46),('DVDD',anchors['rail'],81),('TIMING',anchors['timing'],81)]:
        root.shapes(layout.layer(layer,10)).insert(k.DText(text,k.DTrans(x,y)))
    opts=k.SaveLayoutOptions();opts.add_cell(root.cell_index());layout.write(str(work/'clamp.gds'),opts)
    report=dict(status='generated_clamp_requires_extraction_and_rule_review',native_base=base.name,
        source_gds_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),removed_mos_capacitors=removed,
        preserved_leaf_layers=[34,35,36,38,42],gate_landings_um=anchors,ground_landing_um=ground,mim_centers_um=placements,
        bbox_um=str(root.dbbox()),capacitor_parameters=config,
        limitations=['Native transistor/resistor/diode geometry retained; modified clamp is not inherited ESD qualification.',
            'New interconnect uses single vias and is not discharge-current qualified.',
            'Standalone clamp macro; no pad array, protection rail or whole-ring integration.'])
    (work/'clamp-layout.json').write_text(json.dumps(report,indent=2)+'\n')


def generate(work):
    from layout import magic,IMAGE
    from protection_candidate import CLAMP_CAPACITORS,build_candidate
    from run_first_pass import lvs
    from native_loading import capacitances
    from design import PROJECT
    if CLAMP_CAPACITORS['timing_side_um']!=CLAMP_CAPACITORS['rail_side_um']:
        raise ValueError('Separate MIM masters required for unequal capacitor sizes')
    work.mkdir(parents=True,exist_ok=False)
    (work/'config.json').write_text(json.dumps(CLAMP_CAPACITORS,indent=2)+'\n')
    side=CLAMP_CAPACITORS['timing_side_um'];pcell=CLAMP_CAPACITORS['pcell']
    script=f'''crashbackups stop
load workspace
units internal
set cell [magic::gencell_makecell gf180mcu::{pcell} w {side} l {side}]
load $cell
save clamp_mim
select top cell
expand
drc check
drc catchup
puts "MIM_DRC [drc list count total]"
extract all
ext2spice lvs
ext2spice
gds write clamp_mim.gds
quit -noprompt
'''
    (work/'mim.tcl').write_text(script);magic(work,'mim.tcl')
    (work/'clamp_layout.py').write_text(Path(__file__).read_text())
    subprocess.run(['docker','run','--rm','--network','none','--entrypoint','python3',
        '--mount',f'type=bind,src={work},dst=/work',IMAGE,'/work/clamp_layout.py','--inside','--output-dir','/work'],check=True,timeout=60)
    script='''crashbackups stop
gds read clamp.gds
load pad_isolated_rail_clamp_layout
select top cell
flatten clamp_flat
load clamp_flat
save
select top cell
expand
drc check
drc catchup
puts "CLAMP_DRC [drc list count total]"
puts [drc listall why]
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice
quit -noprompt
'''
    (work/'extract.tcl').write_text(script);result=magic(work,'extract.tcl')
    match=re.search(r'CLAMP_DRC (\d+)',result.stdout)
    if not match or int(match[1]):raise ValueError('Clamp DRC did not pass')
    topology=capacitances(work/'clamp_flat.ext','gf180mcu_fd_io__dvdd')
    pdk=PROJECT.parents[1]/'scratch/transceiver-pad-pdk/ngspice'
    generated=Path(__file__).with_name('generated').resolve()
    candidate,deps=build_candidate(generated/'rf-receive-extracted-c.spice',generated/'protection-primitives',pdk)
    reference=re.search(r'(?ms)^.subckt pad_isolated_rail_clamp .*?^.ends pad_isolated_rail_clamp',candidate).group()
    reference=reference.replace('.subckt pad_isolated_rail_clamp DVDD DVSS VSS','.subckt clamp_reference DVSS DVDD TIMING').replace('.ends pad_isolated_rail_clamp','.ends clamp_reference')
    reference=re.sub(r'\bn8\b','TIMING',reference)
    (work/'reference.spice').write_text(reference+'\n')
    physical=(work/'clamp_flat.spice').read_text()
    (work/'clamp-lvs.spice').write_text('\n'.join(line for line in physical.splitlines() if not line.startswith('C'))+'\n')
    if not lvs(work,'clamp-lvs.spice','clamp_flat','reference.spice','clamp_reference','clamp-lvs.txt'):
        raise ValueError('Clamp device-graph LVS failed')
    subprocess.run([sys.executable,str(Path(__file__).with_name('render.py').resolve()),
        str(work/'clamp_flat.mag'),'--output',str(work/'clamp.png'),'--title','Isolated protection rail clamp','--primitive'],check=True,timeout=30)
    report=json.loads((work/'clamp-layout.json').read_text())
    report.update(status='standalone_clamp_DRC_and_device_LVS_pass_not_ESD_qualification',drc_count=0,
        device_graph_lvs_match=True,topology=topology,extracted_spice_sha256=hashlib.sha256(physical.encode()).hexdigest(),
        extracted_capacitor_count=sum(line.startswith('C') for line in physical.splitlines()),
        source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (Path(__file__),Path(__file__).with_name('protection_candidate.py'),Path(__file__).with_name('layout.py'),
             pdk.parent/'gf180mcu_fd_io.spice')})
    (work/'clamp-layout.json').unlink()
    (work/'clamp-layout.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--inside',action='store_true')
    a=p.parse_args();(assemble if a.inside else generate)(a.output_dir.resolve())
