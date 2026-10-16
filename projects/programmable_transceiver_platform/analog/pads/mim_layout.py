"""Generate and round-trip a standalone MIM primitive with extracted parasitics."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from layout import magic, rectangles


def generate(work, side_um):
    if not 5 <= side_um <= 100:
        raise ValueError('MIM side must be 5..100 um')
    work.mkdir(parents=True, exist_ok=False)
    script = f'''crashbackups stop
load workspace
units internal
set cell [magic::gencell_makecell gf180mcu::cap_mim_2p0fF w {side_um} l {side_um}]
load $cell
save feedforward_mim
select top cell
expand
drc check
drc catchup
puts "MIM_DRC [drc list count total]"
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice
gds write feedforward_mim.gds
quit -noprompt
'''
    (work / 'generate.tcl').write_text(script)
    result = magic(work, 'generate.tcl')
    assert re.search(r'MIM_DRC 0\b', result.stdout), 'MIM layout DRC failed'
    raw = (work / 'feedforward_mim.spice').read_text()
    device = next(line.split() for line in raw.splitlines() if line.startswith('X'))
    assert device[3] == 'cap_mim_2f0_m4m5_noshield'
    def normalized(text):
        dev = next(line.split() for line in text.splitlines() if line.startswith('X'))
        replacements = {dev[1]: 'TOP', dev[2]: 'BOTTOM', 'VSUBS': 'SUB'}
        lines = [[replacements.get(token, token) for token in line.split()]
                 for line in text.splitlines() if line.startswith(('X', 'C'))]
        devices = [' '.join(line) for line in lines if line[0].startswith('X')]
        capacitors = sorted((tuple(sorted(line[1:3])), line[3])
                            for line in lines if line[0].startswith('C'))
        return devices + [f'C{i} {nodes[0]} {nodes[1]} {value}'
                          for i, (nodes, value) in enumerate(capacitors)]

    expected = normalized(raw)
    (work / 'feedforward_mim.mag').rename(work / 'source.mag.saved')
    (work / 'roundtrip.tcl').write_text('''crashbackups stop
gds read feedforward_mim.gds
load feedforward_mim
select top cell
expand
drc check
drc catchup
puts "MIM_DRC [drc list count total]"
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice
quit -noprompt
''')
    result = magic(work, 'roundtrip.tcl')
    assert re.search(r'MIM_DRC 0\b', result.stdout), 'Exported MIM DRC failed'
    actual = normalized((work / 'feedforward_mim.spice').read_text())
    assert actual == expected, 'GDS roundtrip changed device or parasitics'
    (work / 'source.mag.saved').rename(work / 'feedforward_mim.mag')
    physical = '.subckt feedforward_mim TOP BOTTOM SUB\n' + '\n'.join(actual) + '\n.ends\n'
    (work / 'physical.spice').write_text(physical)
    geometry = rectangles(work / 'feedforward_mim.mag')
    boxes = [r for layer, values in geometry.items() if layer != 'checkpaint' for r in values]
    bbox = [min(r[0] for r in boxes), min(r[1] for r in boxes),
            max(r[2] for r in boxes), max(r[3] for r in boxes)]
    report = dict(status='standalone_MIM_extracted_not_integrated', side_um=side_um,
                  drc_count=0, gds_roundtrip_device_and_capacitance_match=True,
                  bbox_um=bbox, envelope_area_um2=(bbox[2]-bbox[0])*(bbox[3]-bbox[1]),
                  physical_sha256=hashlib.sha256(physical.encode()).hexdigest(),
                  limitations=['Integration routes and neighboring-metal coupling absent.',
                               'No voltage-stress or ESD qualification.'],
                  source_sha256={str(Path(__file__).resolve()): hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    (work / 'layout.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--side-um', type=float, required=True)
    args = parser.parse_args()
    generate(args.output_dir.resolve(), args.side_um)
