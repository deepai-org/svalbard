#!/usr/bin/env python3
"""Lay out the fallback's existing CMOS control glue without changing its model.

Run from any directory. Outputs go to generated/ here; intermediate tool files
go to scratch/bringup-control-layout. Uses the timing family's existing offline
GF180 Magic/Netgen/KLayout flow. The live co-simulation remains untouched.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
ROOT = PROJECT.parents[1]
TIMING = HERE.parent/'timing'
sys.path.insert(0, str(TIMING))
import compact
import layout_engine as le
import netlist
import timing_flow as tf


def contact(n, p=None):
    return dict(k='c', n=n, p=n if p is None else p)


def gate(name, wn=2, wp=4):
    return dict(k='g', net=name, wn=wn, wp=wp)


def reference():
    source = PROJECT/'integration/wtx_fallback.py'
    text = source.read_text()
    assignments = [n for n in ast.parse(text).body if isinstance(n, ast.Assign)]
    glue = next(ast.literal_eval(n.value) for n in assignments
                if any(isinstance(t, ast.Name) and t.id == 'GLUE' for t in n.targets))
    instances = re.findall(r"['\"](X\w+ [^'\"\n]*bringup_(?:inv|and))['\"]", text)
    assert len(instances) == 11, 'review changed control topology before laying it out'
    ports = ['L_BRANCH0', 'L_BRANCH1', 'L_STATE0', 'L_STATE1', 'L_IDLE',
             'L_STAGE_TMDS', 'L_EXT_ENABLE', 'ISO_wired', 'FORCE_LEAF',
             'TMDS_REQUEST', 'WIRED_ON', 'FORCE_SELECTED', 'RAIL_wired', 'VDD', 'VSS']
    top = 'pt_wtx_fallback_control'
    schematic = glue+f'\n.subckt {top} '+ ' '.join(ports)+'\n'
    schematic += '\n'.join(instances)+f'\n.ends {top}\n'
    parsed = netlist.parse(schematic)
    assert len(netlist.flatten(parsed, top)) == 50
    return source, schematic, top, ports


def leaf_rows():
    inv = compact.Row('bringup_inv', [contact('VSS', 'VDD'), gate('A'), contact('Y')],
                      ports=['A', 'Y'])
    # Two series NFETs; two parallel PFETs; then the restoring inverter.
    # The uncontacted intermediate NFET diffusion remains internal.
    and2 = compact.Row('bringup_and', [contact('YB', 'VDD'), gate('A', 4, 4),
                       dict(k='c', n=None, p='YB'), gate('B', 4, 4),
                       contact('VSS', 'VDD'), dict(k='c', n='-', p='-'),
                       contact('VSS', 'VDD'), gate('YB'), contact('Y')],
                       ports=['A', 'B', 'Y'])
    return [(inv, ['A', 'Y', 'VDD', 'VSS']),
            (and2, ['A', 'B', 'Y', 'VDD', 'VSS'])]


def check_pass(record):
    assert record['drc_errors'] == 0, record
    assert record['lvs']['unique_match'], record
    assert record['klayout']['ran'] and record['klayout']['violations'] == 0, record


def build(work, generated):
    work.mkdir(parents=True, exist_ok=True)
    generated.mkdir(parents=True, exist_ok=True)
    result = dict(status='incomplete', physical_binding_in_live_simulation=False)
    report_path = generated/'evidence.json'
    report_path.write_text(json.dumps(result, indent=2)+'\n')
    source, schematic, top, ports = reference()
    (generated/'schematic.spice').write_text(schematic)
    leaves = generated/'leaves'
    leaves.mkdir(exist_ok=True)
    leaf_evidence = {}
    for row, order in leaf_rows():
        cell_work = work/row.name
        if cell_work.exists():
            shutil.rmtree(cell_work)
        row.build().emit(cell_work, order)
        record = compact.check(cell_work, row.name, schematic)
        tf.gds_export_analog(cell_work, row.name)
        record['klayout'] = tf.klayout_drc(cell_work, row.name)
        record['size_um'] = [row.width, row.top]
        print(row.name, json.dumps(record), flush=True)
        leaf_evidence[row.name] = record
        check_pass(record)
        for suffix in ('.mag', '.ext.spice', '.lvs.spice'):
            shutil.copyfile(cell_work/(row.name+suffix), leaves/(row.name+suffix))
        shutil.copyfile(cell_work/(row.name+'.a.gds'), leaves/(row.name+'.gds'))
        rails = {}
        for _, (net, yy) in row.rails.items():
            rails.setdefault(net, [.3, yy])
        metadata = dict(ports=order, pins=row.pins, rails=rails,
                        bbox=[-.3, 0., row.width, row.top+.6])
        (leaves/(row.name+'.pins.json')).write_text(json.dumps(metadata, indent=2)+'\n')
        shutil.copyfile(cell_work/'lvs.txt', leaves/(row.name+'-lvs.txt'))
        shutil.copyfile(cell_work/'drc-details.txt', leaves/(row.name+'-drc.txt'))
    # Register macros only in this build process. Existing timing cells and the
    # co-simulation's hashed source files are never modified.
    le.FAST = leaves
    le.SLOT_GAP = 3.0  # Keep independently supplied n-wells separated.
    for path in leaves.glob('*.pins.json'):
        name = path.name[:-len('.pins.json')]
        netlist.MACROS[name] = json.loads(path.read_text())['ports']
    devices = netlist.flatten(netlist.parse(schematic), top)
    macro_work = work/top
    if macro_work.exists():
        shutil.rmtree(macro_work)
    report = le.generate(macro_work, top, ports, devices, max_row_width=110,
                         power_nets=('VDD', 'VSS', 'RAIL_wired'))
    (macro_work/'schematic.spice').write_text(schematic)
    lvs = le.netgen_lvs(macro_work, top+'.lvs.spice', top, 'schematic.spice', top)
    tf.gds_export_analog(macro_work, top)
    klayout = tf.klayout_drc(macro_work, top)
    record = dict(drc_errors=le.drc_errors(report['drc_count_raw']), lvs=lvs, klayout=klayout)
    print(top, json.dumps(record), flush=True)
    check_pass(record)
    for suffix in ('.mag', '.ext.spice', '.lvs.spice'):
        shutil.copyfile(macro_work/(top+suffix), generated/(top+suffix))
    for path in leaves.glob('*.mag'):
        shutil.copyfile(path, generated/path.name)
    shutil.copyfile(macro_work/(top+'.a.gds'), generated/(top+'.gds'))
    shutil.copyfile(macro_work/'lvs.txt', generated/'lvs.txt')
    shutil.copyfile(macro_work/'drc-details.txt', generated/'drc-details.txt')
    inputs = [Path(__file__).resolve(), source, TIMING/'compact.py', TIMING/'layout_engine.py',
              TIMING/'netlist.py', TIMING/'timing_flow.py']
    result.update(status='pass', leaves=leaf_evidence, macro=record, layout=report,
                  transistor_count=50, gate_count=11, ports=ports,
                  tool_images={name: tf.image_id(name) for name in (le.DIGITAL_IMAGE, tf.ANALOG_IMAGE)},
                  source_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                  excluded=['extracted functional/PVT characterization',
                            'binding this extraction into the live assembled simulation',
                            'full-chip placement, routing, DRC/LVS and physical signoff'])
    artifacts = [p for p in generated.rglob('*') if p.is_file() and
                 (p.suffix in ('.gds', '.mag', '.spice') or
                  p.name.endswith(('.pins.json', '-lvs.txt', '-drc.txt')) or
                  p.name in ('lvs.txt', 'drc-details.txt'))]
    result['artifact_hashes'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts}
    report_path.write_text(json.dumps(result, indent=2)+'\n')
    print(f'Physical control macro passed DRC/LVS: {report_path}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=ROOT/'scratch/bringup-control-layout')
    parser.add_argument('--generated', type=Path, default=HERE/'generated')
    args = parser.parse_args()
    build(args.work.resolve(), args.generated.resolve())
