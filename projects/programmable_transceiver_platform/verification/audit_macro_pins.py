"""Check macro LEF terminals against qualified GDS metal and net labels.

Run inside the pinned KLayout environment. The manifest supplies copied GDS
and LEF files with hashes; the result identifies physical landing rectangles.
"""
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import pya


def _metal_layers(path):
    layers = {}
    for entry in ET.parse(path).iter('properties'):
        name = (entry.findtext('name') or '').strip()
        source = (entry.findtext('source') or '').strip()
        packed = re.fullmatch(r'(Metal[1-5])\s+(\d+)/(\d+)@\d+', source)
        if packed:
            layers[packed[1]] = (int(packed[2]), int(packed[3]))
        elif re.fullmatch(r'Metal[1-5]', name):
            layers[name] = tuple(map(int, source.split('@')[0].split('/')))
    assert len(layers) == 5, 'Incomplete PDK metal-layer mapping'
    return layers


def audit(manifest_path, report_path):
    work = manifest_path.parent
    inputs = json.loads(manifest_path.read_text())
    properties = Path('/foss/pdks/gf180mcuD/libs.tech/klayout/tech/gf180mcu.lyp')
    layers = _metal_layers(properties)
    errors, pins = [], []
    for item in inputs['cells']:
        for kind in ('gds', 'lef'):
            actual = hashlib.sha256((work/item[kind]).read_bytes()).hexdigest()
            assert actual == item[kind+'_sha256'], (item['cell'], kind)
        layout = pya.Layout()
        layout.read(str(work/item['gds']))
        cell = layout.cell(item['cell'])
        assert cell is not None, item['cell']
        text = (work/item['lef']).read_text()
        metal = {}
        for match in re.finditer(r'\bPIN\s+(\S+)\s+(.*?)\bEND\s+\1(?=\s|$)', text, re.S):
            pin, body = match.groups()
            rectangles, labelled, layer = [], False, None
            tokens = re.finditer(
                r'\bLAYER\s+(\S+)\s*;|\bRECT\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*;', body)
            for shape in tokens:
                if shape[1]:
                    layer = shape[1]
                    continue
                assert layer in layers, (item['cell'], pin, layer)
                rect = pya.Box(*[round(float(v)/layout.dbu) for v in shape.groups()[1:]])
                assert rect.width() > 0 and rect.height() > 0, (item['cell'], pin)
                if layer not in metal:
                    index = layout.find_layer(*layers[layer])
                    metal[layer] = pya.Region(cell.begin_shapes_rec(index)) if index is not None else pya.Region()
                missing = pya.Region(rect)-metal[layer]
                if not missing.is_empty():
                    errors.append(dict(cell=item['cell'], pin=pin, layer=layer,
                                       reason='LEF rectangle outside GDS metal',
                                       rect_dbu=str(rect), missing_area_dbu2=missing.area()))
                for datatype in (0, 10):
                    index = layout.find_layer(layers[layer][0], datatype)
                    if index is None:
                        continue
                    for obj in cell.shapes(index).each():
                        if obj.is_text() and obj.text.string == pin and rect.contains(obj.text.trans.disp):
                            labelled = True
                rectangles.append(dict(layer=layer, box_dbu=[rect.left, rect.bottom, rect.right, rect.top]))
            assert rectangles, (item['cell'], pin)
            if not labelled:
                errors.append(dict(cell=item['cell'], pin=pin,
                                   reason='No matching GDS port label in LEF pin rectangles'))
            pins.append(dict(cell=item['cell'], pin=pin, shapes=rectangles,
                             dbu_um=layout.dbu, matching_port_label=labelled))
    result = dict(status='pass' if not errors else 'fail', scope=inputs['scope'],
                  cells=len(inputs['cells']), pins=len(pins), errors=errors,
                  pin_details=pins, pdk_layers=layers,
                  pdk_layer_properties_sha256=hashlib.sha256(properties.read_bytes()).hexdigest(),
                  input_manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                  auditor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    report_path.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({key: result[key] for key in ('status', 'cells', 'pins', 'errors')}, indent=2))
    assert not errors, 'Physical pin preflight failed'
    return result
