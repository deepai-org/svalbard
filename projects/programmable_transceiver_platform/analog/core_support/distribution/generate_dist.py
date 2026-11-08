#!/usr/bin/env python3
"""Layout (Magic, via analog/rf_tx/layoutlib.py), Magic DRC, Netgen LVS and
capacitance extraction for the bias-distribution cells (digital image), then GDS
export with the analog image's Magic (cif ostyle gdsii), KLayout DRC and the
HRES check of that exported GDS.

usage: generate_dist.py --scratch DIR --publish DIR
Heavy work in scratch; compact outputs (.mag, .gds.gz, schematic and extracted
netlists, LVS report, layout.json) are copied to --publish.
"""
import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import circuits_dist as cd
import layoutlib  # analog/rf_tx/layoutlib.py (path set up by circuits_dist)

HERE = Path(__file__).resolve().parent
ANALOG_IMAGE = ('docker.io/hpretl/iic-osic-tools@sha256:'
                '89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def klayout_drc(work, gds, top):
    work = Path(work).resolve()
    cmd = ['docker', 'run', '--rm', '--platform', 'linux/arm64', '--network', 'none', '--cpus', '2', '--memory', '4g',
           '--env', 'OMP_NUM_THREADS=1', '--user', f'{os.getuid()}:{os.getgid()}', '--env', 'HOME=/tmp',
           '-v', f'{work}:/work', '-w', '/work', '--entrypoint', '/bin/bash', ANALOG_IMAGE, '-lc',
           f'klayout -b -zz -r /foss/pdks/gf180mcuD/libs.tech/klayout/tech/drc/gf180mcu.drc -rd input=/work/{gds} '
           f'-rd report=/work/klayout_drc.lyrdb -rd feol=True -rd beol=True -rd conn_drc=True -rd wedge=True '
           f'-rd run_mode=deep -rd decks=all,-density -rd thr=2 -rd topcell={top} > /work/klayout_drc.log 2>&1']
    subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    log = (work / 'klayout_drc.log').read_text() if (work / 'klayout_drc.log').exists() else ''
    m = re.findall(r'DRC RESULT: (\w+) \((\d+) violation', log)
    items = (work / 'klayout_drc.lyrdb').read_text().count('<item>') if (work / 'klayout_drc.lyrdb').exists() else None
    return dict(result=m[-1][0] if m else 'no_result', violations=int(m[-1][1]) if m else None, lyrdb_items=items)


def analog_export(work, cell):
    """GDS export with the analog image's Magic 8.3.678 (spec/block-deliverables.md GDS export rule:
    the canary Magic drops the HRES marker), then the HRES coverage check."""
    work = Path(work).resolve()
    (work / 'export.tcl').write_text('crashbackups stop\ndrc off\nload %s\ncif ostyle gdsii\n'
                                     'gds write %s_export.gds\nquit -noprompt\n' % (cell, cell))
    cmd = ['docker', 'run', '--rm', '--platform', 'linux/arm64', '--network', 'none', '--cpus', '2', '--memory', '4g',
           '--user', f'{os.getuid()}:{os.getgid()}', '--env', 'HOME=/tmp', '-v', f'{work}:/work', '-w', '/work',
           '-v', f'{HERE.parent}:/src:ro', '--entrypoint', '/bin/bash', ANALOG_IMAGE, '-lc',
           'magic -dnull -noconsole -rcfile /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc export.tcl '
           '> export.log 2>&1 < /dev/null; magic --version > export_magic_version.txt; '
           f'klayout -b -r /src/flow/hres_check.py -rd gds=/work/{cell}_export.gds -rd top={cell} '
           '-rd out=/work/hres_check.json > hres.log 2>&1']
    subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    hres = json.loads((work / 'hres_check.json').read_text()) if (work / 'hres_check.json').exists() else None
    ver = (work / 'export_magic_version.txt').read_text().strip() if (work / 'export_magic_version.txt').exists() else None
    return f'{cell}_export.gds', hres, ver


def generate(name, scratch, publish):
    c = cd.CELLS[name]()
    work = Path(scratch) / name
    if work.exists():
        shutil.rmtree(work)
    rep = layoutlib.build(c, work)
    (work / 'src.spice').write_text(c.spice())
    layoutlib.docker_netgen(work, f'{c.name}.lvs.spice', c.name, 'src.spice', c.name, 'lvs.txt')
    lvs = (work / 'lvs.txt').read_text() if (work / 'lvs.txt').exists() else ''
    final = [l for l in lvs.splitlines() if l.startswith('Final result')]
    gds, hres, ver = analog_export(work, c.name)
    kl = klayout_drc(work, gds, c.name)
    pub = Path(publish)
    pub.mkdir(parents=True, exist_ok=True)
    (pub / f'{name}.spice').write_text(c.spice())
    shutil.copy(work / f'{c.name}.mag', pub / f'{name}.mag')
    shutil.copy(work / f'{c.name}.ext.spice', pub / f'{name}.ext.spice')
    shutil.copy(work / 'lvs.txt', pub / f'{name}-lvs.txt')
    with open(work / gds, 'rb') as f, gzip.GzipFile(pub / f'{name}.gds.gz', 'wb', mtime=0) as g:
        g.write(f.read())
    bb = rep['bbox_um']
    out = dict(cell=name, layout_image=layoutlib.DIGITAL_IMAGE, layout_image_id=layoutlib.image_id(layoutlib.DIGITAL_IMAGE),
               magic_drc_errors=int(rep['drc_count']), klayout_drc=kl,
               gds_export=dict(tool='analog image Magic %s, cif ostyle gdsii' % ver, hres_check=hres),
               lvs_final=final[-1] if final else 'no result', lvs_unique_match=bool(final) and 'match uniquely' in final[-1],
               width_um=round(bb['x1'] - bb['x0'], 2), height_um=round(bb['y1'] - bb['y0'], 2), area_um2=rep['area_um2'],
               circuit=c.summary(),
               hashes={f'{name}.spice': sha(pub / f'{name}.spice'), f'{name}.gds': sha(work / gds),
                       f'{name}.ext.spice': sha(pub / f'{name}.ext.spice'),
                       'rf_tx/layoutlib.py': sha(cd.RF_TX / 'layoutlib.py'), 'rf_tx/circuits.py': sha(cd.RF_TX / 'circuits.py'),
                       'circuits_dist.py': sha(HERE / 'circuits_dist.py')},
               limitations=['Extraction is capacitance-only (layoutlib ext2spice cthresh 0).'])
    (pub / f'{name}-layout.json').write_text(json.dumps(out, indent=1) + '\n')
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--scratch', required=True)
    ap.add_argument('--publish', default=str(HERE / 'generated'))
    ap.add_argument('cells', nargs='*')
    a = ap.parse_args()
    for n in a.cells or sorted(cd.CELLS):
        r = generate(n, a.scratch, a.publish)
        print(json.dumps({k: r[k] for k in ('cell', 'magic_drc_errors', 'klayout_drc', 'lvs_final', 'area_um2')}))
