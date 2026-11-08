"""GDS export with the analog image's Magic 8.3.678 and KLayout GF180 DRC on that GDS.

spec/block-deliverables.md "GDS export rule": the canary image's Magic 8.3.623 drops the HRES
(62/0) marker on ppolyf_u_1k resistors. DRC, LVS and extraction stay on the canary image; the
published GDS comes from this step. Every exported GDS is checked for HRES/RES_MK marker counts
and run through the PDK KLayout deck (sak-drc.sh -k).

Usage: python3 gds_export.py [block ...]
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import circuits
import simulate as S

HERE = Path(__file__).resolve().parent
GEN = HERE / 'generated'
WORK = (HERE.parents[3] / 'scratch/rf_tx/gds_export').resolve()

CONTAINER = r'''
set -u
export PDK=gf180mcuD PDKPATH=/foss/pdks/gf180mcuD
cd /work/$1
cat > export.tcl <<EOF
crashbackups stop
load $2
select top cell
cif ostyle gdsii
gds write $2.gds
quit -noprompt
EOF
magic -dnull -noconsole -rcfile $PDKPATH/libs.tech/magic/gf180mcuD.magicrc export.tcl > export.log 2>&1
magic --version > magic-version.txt 2>&1
cat > layers.py <<EOF
import klayout.db as db, json
ly = db.Layout(); ly.read('$2.gds')
top = ly.top_cell()
out = {}
for li in ly.layer_indexes():
    info = ly.get_info(li)
    n = sum(1 for _ in top.begin_shapes_rec(li))
    out[f'{info.layer}/{info.datatype}'] = n
json.dump(dict(top=top.name, layers=out), open('layers.json', 'w'), indent=1)
EOF
python3 layers.py > layers.log 2>&1 || klayout -b -r layers.py >> layers.log 2>&1
sak-drc.sh -k -w /work/$1/klayout /work/$1/$2.gds > klayout.stage.log 2>&1
echo "KLAYOUT_RC $?" >> klayout.stage.log
'''


def run(blocks):
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / 'flow.sh').write_text(CONTAINER)
    procs = []
    for b in blocks:
        d = WORK / b
        if d.exists():
            shutil.rmtree(d)
        d.mkdir()
        cell = circuits.BLOCKS[b]().name
        shutil.copy(GEN / f'{b}.mag', d / f'{cell}.mag')
        cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '1', '--memory', '4g',
               '--env', 'HOME=/tmp', '--env', 'OMP_NUM_THREADS=1', '--tmpfs', '/tmp:size=1g,mode=1777',
               '--user', f'{_id("-u")}:{_id("-g")}', '-v', f'{WORK}:/work', '--entrypoint', '/bin/bash',
               S.ANALOG_IMAGE, '-lc', f'bash /work/flow.sh {b} {cell}']
        procs.append((b, cell, subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)))
        if len(procs) >= 3:  # at most three containers at a time
            _finish(*procs.pop(0))
    results = {}
    for p in procs:
        b, cell, r = _finish(*p)
    for b in blocks:
        results[b] = summarize(b)
    return results


def _id(flag):
    return subprocess.run(['id', flag], capture_output=True, text=True).stdout.strip()


def _finish(b, cell, proc):
    proc.communicate(timeout=7200)
    return b, cell, proc.returncode


def summarize(b):
    d = WORK / b
    cell = circuits.BLOCKS[b]().name
    gds = d / f'{cell}.gds'
    out = dict(block=b, magic_version=(d / 'magic-version.txt').read_text().strip() if (d / 'magic-version.txt').exists() else None,
               image=S.ANALOG_IMAGE_REF, image_id=S.ANALOG_IMAGE, gds_written=gds.exists())
    lj = d / 'layers.json'
    if lj.exists():
        lay = json.loads(lj.read_text())
        out['top_cell'] = lay['top']
        out['marker_shapes'] = {'HRES 62/0': lay['layers'].get('62/0', 0), 'RES_MK 110/5': lay['layers'].get('110/5', 0)}
    c = circuits.BLOCKS[b]()
    out['ppolyf_u_1k_resistors_in_netlist'] = sum(1 for dv in c.devices if getattr(dv, 'model', '') == 'ppolyf_u_1k')
    lyrdbs = list((d / 'klayout').rglob('*.lyrdb')) if (d / 'klayout').exists() else []
    if lyrdbs:
        items = sum(len(re.findall(r'<item>', f.read_text())) for f in lyrdbs)
        cats = {}
        for f in lyrdbs:
            for m in re.finditer(r'<item>.*?<category>(.*?)</category>', f.read_text(), re.S):
                cats[m.group(1).strip("'")] = cats.get(m.group(1).strip("'"), 0) + 1
        out['klayout_drc'] = dict(violations=items, by_rule=cats, reports=[str(f.relative_to(WORK)) for f in lyrdbs])
    else:
        out['klayout_drc'] = dict(violations=None, note='no lyrdb produced; see klayout.stage.log')
    st = d / 'klayout.stage.log'
    out['klayout_stage_rc'] = (re.findall(r'KLAYOUT_RC (\d+)', st.read_text()) or [None])[-1] if st.exists() else None
    out['hres_ok'] = (out['ppolyf_u_1k_resistors_in_netlist'] == 0 or out.get('marker_shapes', {}).get('HRES 62/0', 0) > 0)
    out['pass'] = bool(out['gds_written'] and out['hres_ok'] and out['klayout_drc'].get('violations') == 0)
    if gds.exists():
        shutil.copy(gds, GEN / f'{b}.gds')
        for f in lyrdbs:
            shutil.copy(f, GEN / f'{b}-klayout-drc.lyrdb')
    (GEN / f'{b}-gds-export.json').write_text(json.dumps(out, indent=1) + '\n')
    return out


if __name__ == '__main__':
    blocks = sys.argv[1:] or ['txmix_i', 'txmix_q', 'txsum', 'rfdriver']
    res = run(blocks)
    for b, r in res.items():
        print(json.dumps({k: r.get(k) for k in ('block', 'magic_version', 'marker_shapes', 'klayout_drc', 'pass')}))
