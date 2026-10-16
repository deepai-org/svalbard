"""Read actual installed IO geometry and protection topology before generating cells.

Run inside the pinned librelane GF180 container (klayout.db is available there).
No library cells are modified. Output is compact evidence, not a replacement PDK.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import klayout.db as kdb

parser = argparse.ArgumentParser()
parser.add_argument('--pdk', type=Path, default=Path('/pdk/gf180mcuD'))
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root = args.pdk / 'libs.ref/gf180mcu_fd_io'
gds = root / 'gds/gf180mcu_fd_io.gds'
spice = root / 'spice/gf180mcu_fd_io.spice'
lef = root / 'lef/gf180mcu_fd_io__asig_5p0.lef'
layout = kdb.Layout()
layout.read(str(gds))
name = 'gf180mcu_fd_io__asig_5p0'
cell = layout.cell(name)
if cell is None:
    raise RuntimeError('Expected analog cell absent from installed GDS')
subckt = re.search(r'(?ims)^\.SUBCKT ' + name + r'\s.*?^\.ENDS[^\n]*', spice.read_text()).group()
layers = []
for index in layout.layer_indexes():
    region = kdb.Region(cell.begin_shapes_rec(index))
    if not region.is_empty():
        info = layout.get_info(index)
        layers.append(dict(layer=info.layer, datatype=info.datatype,
                           area_um2=region.area() * layout.dbu ** 2,
                           bbox_um=str(region.bbox().to_dtype(layout.dbu))))
size = re.search(r'SIZE ([\d.]+) BY ([\d.]+)', lef.read_text())
# Locate a near-bond protection pocket using the retained rail itself, not its
# bounding rectangle (the lower layers form a border around substantial space).
rail = layout.cell('5LM_METAL_RAIL')
if rail is None: raise RuntimeError('Native rail module missing')
def region(layer):
    return kdb.Region(rail.begin_shapes_rec(layout.layer(layer,0)))
def box_um(values):
    return kdb.Box(*(round(v/layout.dbu) for v in values))
obstacles = kdb.Region()
for layer in (22,31,34): obstacles.insert(region(layer))
obstacles.merge()
pockets=[]
for cx in (25.,50.):
    bounds=[cx-7.,78.,cx+7.,102.]
    overlap=obstacles & kdb.Region(box_um(bounds))
    pockets.append(dict(center_um=[cx,90.],reservation_um=bounds,
        lower_layer_overlap_um2=overlap.area()*layout.dbu**2,
        clear=overlap.is_empty()))
# This is a geometric landing check; text identifies the rail, but full
# extracted net connectivity/current capacity is still a separate obligation.
landing=[9.,77.305,11.,79.305]
landing_region=kdb.Region(box_um(landing))
landing_layers={str(layer):(landing_region-region(layer)).is_empty()
                for layer in (42,46,81)}
labels=[dict(layer=str(layout.get_info(i)),text=shape.text.string,
             x_um=shape.text.x*layout.dbu,y_um=shape.text.y*layout.dbu)
        for i in layout.layer_indexes() for shape in rail.each_shape(i)
        if shape.is_text() and shape.text.string=='DVSS' and shape.text.y*layout.dbu<85]
near_bond=dict(native_rail_cell=rail.name,protection_unit_pockets=pockets,
    tested_obstacle_layers=[22,31,34],ground_landing_um=landing,
    landing_fully_covered_by_native_metals=landing_layers,nearby_ground_labels=labels,
    recommended_next_layout='Place two protection units in the checked pockets per bond; route pad locally on M2 and connect the local return through a via array to the checked DVSS landing. Preserve the M2 signal corridor to the core.',
    limits=['Reservations are candidate envelopes, not instantiated devices or a DRC result.',
            'Rail labels and metal coverage do not prove net connectivity or legal via landing.',
            'Device enclosure, spacing, return current capacity, net-aware assembly LVS and ESD performance still require verification.'])
report = dict(
    status='installed_reference_cell_audit_not_custom_pad_qualification',
    near_bond_protection=near_bond,
    cell=name, dbu_um=layout.dbu, gds_bbox_um=str(cell.dbbox()),
    lef_size_um=[float(size[1]), float(size[2])], layers=layers,
    bond_template=dict(cell='Bondpad_5LM',
                       bbox_um=str(layout.cell('Bondpad_5LM').dbbox()),
                       reference_parent='5LM_METAL_RAIL_PAD_60',
                       instances=[dict(cell=layout.cell(i.cell_index).name,transform=str(i.dtrans))
                                  for i in layout.cell('5LM_METAL_RAIL_PAD_60').each_inst()],
                       glass_layer='37/0 (GLASS in installed Magic technology)',
                       glass_bbox_um=str(kdb.Region(cell.begin_shapes_rec(layout.layer(37,0))).bbox().to_dtype(layout.dbu))),
    protection_subcircuit=subckt,
    decision='Do not substitute this complete analog cell for power-off-tolerant custom signal cells: D3 connects ASIG5V to DVDD. Preserve packaging geometry only after reconciling provider placement and opening layers.',
    limits=['GDS bounding box is not a bond opening',
            'LEF signal rectangle is not proof of passivation opening',
            'No extracted capacitance, ESD qualification or custom layout result'],
    sources_sha256={str(path.relative_to(args.pdk)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in (gds, spice, lef)},
)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({key: report[key] for key in ('cell', 'gds_bbox_um', 'lef_size_um')}))
