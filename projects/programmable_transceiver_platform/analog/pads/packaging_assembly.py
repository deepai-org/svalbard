"""Assemble corrected native ring and provider ID macros around unchanged core.

Run with KLayout Python. This is geometric integration, not full-chip DRC/LVS.
The actual PDK seal-ring step is run on this output separately.
"""
import argparse,hashlib,json,re
from pathlib import Path


def build(source, aligned, template, output):
    import klayout.db as k
    layout=k.Layout();layout.read(str(source));top=layout.top_cell()
    reference=k.Layout();reference.read(str(aligned))
    if layout.dbu!=reference.dbu:raise ValueError('Mismatched layout units')
    retained=layout.cell('retained_provider_ring');replacement=reference.cell('retained_provider_ring')
    if retained is None or replacement is None:raise ValueError('Missing native ring hierarchy')
    core=k.Region(k.Box(*[round(v/layout.dbu) for v in (442,442,3490,4680)]))
    before={layout.get_info(i).to_s():k.Region(top.begin_shapes_rec(i))&core for i in layout.layer_indexes()}
    retained.clear();retained.copy_tree(replacement)
    placements={'qrcode_id':(26.,26.,0),'shuttle_id':(26.,175.6,3),
                'project_id':(175.6,26.,0),'marker':(3651.,4841.,0)}
    sources=[source,aligned,Path(__file__)];ids={}
    for name,(x,y,rot) in placements.items():
        cellname='gf180mcu_ws_ip__'+name;gds=template/'ip'/cellname/'gds'/(cellname+'.gds')
        lef=template/'ip'/cellname/'lef'/(cellname+'.lef');sources.extend([gds,lef])
        if layout.cell(cellname) is not None:raise ValueError('ID cell already exists')
        view=k.Layout();view.read(str(gds));cell=layout.create_cell(cellname);cell.copy_tree(view.cell(cellname))
        width,height=map(float,re.search(r'SIZE\s+([\d.]+)\s+BY\s+([\d.]+)',lef.read_text()).groups())
        orient=k.Trans(rot,False,0,0);bounds=k.Box(0,0,round(width/layout.dbu),round(height/layout.dbu)).transformed(orient)
        transform=k.Trans(rot,False,round(x/layout.dbu)-bounds.left,round(y/layout.dbu)-bounds.bottom)
        top.insert(k.CellInstArray(cell.cell_index(),transform))
        ids[name]=dict(cell=cellname,lef_lower_left_um=[x,y],rotation_quarters=rot)
    for i in layout.layer_indexes():
        key=layout.get_info(i).to_s();now=k.Region(top.begin_shapes_rec(i))&core
        if not (now^before.get(key,k.Region())).is_empty():raise ValueError('Packaging operation changed core geometry: '+key)
    options=k.SaveLayoutOptions();options.select_cell(top.cell_index());options.write_context_info=False
    output.parent.mkdir(parents=True,exist_ok=True);layout.write(str(output),options)
    report=dict(status='native_ring_and_real_provider_ID_geometry_integrated_requires_sealring_and_verification',
                core_geometry_unchanged=True,ids=ids,output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
                limitations=['No new active-core routing or physical supervisors. Ring electrical continuity, local DRC and full-chip LVS remain separate checks.',
                'ID coordinates follow the pinned provider template for 1x1; actual ID content is assigned by provider precheck, not invented here.'])
    output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('source','aligned','template','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();print(json.dumps(build(a.source,a.aligned,a.template,a.output),indent=2))
