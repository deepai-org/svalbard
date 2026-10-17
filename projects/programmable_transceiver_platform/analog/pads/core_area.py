"""Measure attached TX macro footprints against shared block allocations.

Run in the existing layout-tool container (klayout required). This is a lower
bound on placement demand, not placement/routing or whole-chip fit signoff.
"""
import argparse
import hashlib
import json
from pathlib import Path
import klayout.db as db


def run(project, output):
    spec_path=project/'spec/schematic-implementation.json'
    arch_path=project/'spec/analog-architecture.json'
    spec=json.loads(spec_path.read_text())['io_pad_first_pass']
    architecture=json.loads(arch_path.read_text())
    sources=[spec_path,arch_path,Path(__file__)]
    macros={}
    for name,allocation in spec['tx_attached_macro_allocations'].items():
        model=project/spec['tx_integration_fixture']['models'][name]
        layout_path=model.parent/'layout.json'
        layout_report=json.loads(layout_path.read_text())
        files=list(model.parent.glob('*.gds'))
        if len(files)!=1:
            raise ValueError('Expected one selected GDS for '+name)
        gds=files[0]
        digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        if layout_report.get('physical_sha256')!=digest(model) or layout_report.get('gds_sha256')!=digest(gds):
            raise ValueError('Selected macro model/layout hash mismatch: '+name)
        layout=db.Layout();layout.read(str(gds))
        cells=layout.top_cells()
        if len(cells)!=1:raise ValueError('Ambiguous macro top cell: '+name)
        bounds=cells[0].dbbox()
        block=allocation['block']
        budget=architecture['blocks'][block]['resource_allocation']['area_ceiling_um2']
        reservation=allocation['reservation_um2']
        macros[name]=dict(block=block,model=str(model.relative_to(project)),
            gds=str(gds.relative_to(project)),
            bbox_um=[bounds.left,bounds.bottom,bounds.right,bounds.top],
            minimum_rectangular_footprint_um2=bounds.area(),reservation_um2=reservation,
            fits_reservation=bounds.area()<=reservation,owner_block_budget_um2=budget)
        sources.extend([model,gds,layout_path])
    owners={}
    for block in sorted({m['block'] for m in macros.values()}):
        group=[m for m in macros.values() if m['block']==block]
        reserved=sum(m['reservation_um2'] for m in group)
        budget=group[0]['owner_block_budget_um2']
        owners[block]=dict(reserved_um2=reserved,budget_um2=budget,
            unreserved_um2=budget-reserved,reservations_fit=reserved<=budget)
    report=dict(status='attached_macro_area_accounting_not_placement_signoff',macros=macros,owners=owners,
        all_reservations_fit=all(m['fits_reservation'] for m in macros.values()) and all(o['reservations_fit'] for o in owners.values()),
        limitations=['Bounding rectangles exclude additional routing, guard separation, bias passives and missing control/monitor circuits.',
                     'Unreserved owner area must also fund its other circuitry; it is not free die reserve.',
                     'No placement or connectivity to the assembled pad ring is established.'],
        source_sha256={str(p.relative_to(project)) if p.is_relative_to(project) else str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(all_reservations_fit=report['all_reservations_fit'],macros=macros,owners=owners),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.project.resolve(),args.output.resolve())
