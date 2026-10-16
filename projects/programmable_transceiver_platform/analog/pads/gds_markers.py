"""Materialize high-R mask enclosures omitted by the installed Magic exporter.

Select connected exported poly from physical Magic high-R seeds. Never infer
resistor placement from the schematic or paint a device to make LVS pass.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def inside(work):
    import klayout.db as k
    cfg=json.loads((work/'marker-input.json').read_text())
    layout=k.Layout();layout.read(str(work/cfg['gds']));cell=layout.cell(cfg['cell'])
    poly=k.Region(cell.begin_shapes_rec(layout.layer(30,0))).merged()
    additions={62:k.Region(),55:k.Region()};components={}
    for kind,rectangles in cfg['seeds'].items():
        seeds=k.Region()
        for r in rectangles:seeds.insert(k.DBox(*r).to_itype(layout.dbu))
        selected=poly.interacting(seeds)
        if not (seeds-selected).is_empty():raise ValueError('High-R seed is not covered by exported poly')
        components[kind]=selected.count()
        enclosure=selected.sized(round(.4/layout.dbu))
        additions[62]+=enclosure
        if kind=='mvnhighres':additions[55]+=enclosure
    areas={}
    for number,expected in additions.items():
        existing=k.Region(cell.begin_shapes_rec(layout.layer(number,0)))
        added=expected-existing;cell.shapes(layout.layer(number,0)).insert(added)
        areas[str(number)]=added.area()*layout.dbu**2
    layout.write(str(work/cfg['gds']))
    (work/'marker-result.json').write_text(json.dumps(dict(added_area_um2=areas,selected_poly_components=components),indent=2)+'\n')


def repair(work,cell):
    from layout import rectangles,IMAGE
    work=work.resolve();mag=work/(cell+'.mag');gds=work/(cell+'.gds')
    geometry=rectangles(mag)
    kinds={key for key in geometry if 'highres' in key}
    if kinds-{'nhighres','mvnhighres'}:raise ValueError('Unknown high-R Magic layer')
    before=hashlib.sha256(gds.read_bytes()).hexdigest()
    if not kinds:return dict(status='no_high_resistance_devices',before_gds_sha256=before,after_gds_sha256=before)
    (work/'marker-input.json').write_text(json.dumps(dict(cell=cell,gds=gds.name,seeds={kind:geometry[kind] for kind in sorted(kinds)})))
    script=Path(__file__).resolve()
    subprocess.run(['docker','run','--rm','--network','none','--entrypoint','python3','--mount',f'type=bind,src={work},dst=/work','--mount',f'type=bind,src={script},dst=/tool.py,readonly',IMAGE,'/tool.py','--inside','--work','/work'],check=True,timeout=60)
    result=json.loads((work/'marker-result.json').read_text())
    result.update(status='physical_poly_HRES_DUALGATE_enclosures_materialized_requires_roundtrip',rule='Connected high-R poly grown 0.4um; HRES 62/0, and DUALGATE 55/0 for MV only.',before_gds_sha256=before,after_gds_sha256=hashlib.sha256(gds.read_bytes()).hexdigest(),physical_magic_sha256=hashlib.sha256(mag.read_bytes()).hexdigest(),generator_sha256=hashlib.sha256(script.read_bytes()).hexdigest())
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inside',action='store_true');p.add_argument('--work',type=Path,required=True);p.add_argument('--cell')
    a=p.parse_args()
    if a.inside:inside(a.work)
    else:print(json.dumps(repair(a.work,a.cell),indent=2))
