#!/usr/bin/env python3
"""rfdriver layout iteration (RFT-07): generate with LAYOUT overrides -> Magic full-coverage extresist + C-only flat
extraction of the same GDS -> fixcap16 -> driver bench (code 15, 0.3 V) + in-block IR.   (RFTX_IMAGE must be set)
    python3 rfdriver_iter.py <tag> '<json overrides of generate.LAYOUT["rfdriver"]>'      -> scratch/rf_tx/iter/<tag>/"""
import json, os, subprocess, sys, shutil
from pathlib import Path
import generate, layoutlib, simulate as S, run_benches as B, power_check as PC
HERE = Path(__file__).resolve().parent
FIX = '/home/ubuntu/svalbard/scratch/wired_tx/s16/net/fixcap16.py'
RC = """crashbackups stop
drc off
gds read in.gds
load pt_rfdriver
flatten pt_rfdriver_flat
load pt_rfdriver_flat
select top cell
extract do capacitance
extract do coupling
{res}extract all
{post}quit -noprompt
"""
POST_RC = """ext2sim labels on
ext2sim
extresist tolerance 0.001
extresist ignore VSUBS
extresist simplify off
extresist all
ext2spice lvs
ext2spice hierarchy off
ext2spice format ngspice
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist on
ext2spice subcircuit top on
ext2spice -o full.rc.spice
"""
POST_C = """ext2spice lvs
ext2spice hierarchy off
ext2spice format ngspice
ext2spice cthresh 0
ext2spice subcircuit top on
ext2spice -o conly.spice
"""


def magic(d, script):
    subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--cpus', '1', '--memory', '8g', '--user', f'{os.getuid()}:{os.getgid()}',
                    '-e', 'HOME=/tmp', '-v', f'{d}:/w', '--entrypoint', '/bin/bash', layoutlib.DIGITAL_IMAGE, '-c',
                    f'export PATH=$PATH:/foss/tools/bin PDK_ROOT=/foss/pdks; cd /w; magic -dnull -noconsole -rcfile /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc {script} > {script}.log 2>&1'],
                   check=True)


def run(tag, over):
    base = generate.REPO / 'scratch/rf_tx/iter' / tag
    if base.exists(): shutil.rmtree(base)
    L = dict(generate.LAYOUT['rfdriver']); over = dict(over)
    wa = over.pop('wide_all', None); ma = over.pop('multi_all', None)
    L.update(over)
    if wa or ma:
        import circuits
        nets = circuits.rfdriver().nets()
        if wa: L['wide'] = {**{n: wa for n in nets}, **L.get('wide', {})}
        if ma: L['multi_escape'] = {**{n: ma for n in nets}, **L.get('multi_escape', {})}
    if 'supply_nets' in over: L['supply'] = dict(L['supply'], nets=over.pop('supply_nets')); L.pop('supply_nets', None)
    keep = generate.LAYOUT['rfdriver']; generate.LAYOUT['rfdriver'] = L
    try:
        r = generate.generate('rfdriver', base / 'work', base / 'pub')
    finally:
        generate.LAYOUT['rfdriver'] = keep
    x = base / 'x'; x.mkdir(); shutil.copy(base / 'pub/rfdriver.gds', x / 'in.gds')
    (x / 'rc.tcl').write_text(RC.format(res='extract do resistance\n', post=POST_RC)); (x / 'c.tcl').write_text(RC.format(res='', post=POST_C))
    magic(x, 'rc.tcl'); magic(x, 'c.tcl')
    fx = subprocess.run([sys.executable, FIX, str(x / 'conly.spice'), str(x / 'full.rc.spice'), str(x / 'fix.rc.spice')], capture_output=True, text=True).stdout.strip()
    cand = HERE / 'generated/cand' / f'iter_{tag}.rc.spice'
    txt = (x / 'fix.rc.spice').read_text().replace('pt_rfdriver_flat', 'pt_rfdriver')
    feed = os.environ.get('FEED', 'edge')
    nfeed = 0
    if feed == 'edge' and r.get('supply_bars_um'):
        # chip-side feed along the whole south edge (RAIL_rf_tx Metal5 bus, VSS Metal4 plate): every extresist node of a
        # supply net inside its own bottom bar is tied to the port with 1 mohm (Magic .res.ext rnode coordinates, 0.005 um)
        import re as _re
        rn = [(m.group(1), int(m.group(2)) * 0.005, int(m.group(3)) * 0.005) for m in
              _re.finditer(r'^rnode "((?:VDD|VSS)\.[nt]\d+)" \S+ \S+ (-?\d+) (-?\d+)', (x / 'pt_rfdriver_flat.res.ext').read_text(), _re.M)]
        bars = r['supply_bars_um']; add = []
        for nm, xx, yy in rn:
            net = nm.split('.')[0]; L_, b0, b1 = bars[net]
            if b0 - 0.1 <= yy <= b1 + 0.1 and nm in txt:
                add.append(f'Rfeed{len(add)} {nm} {net} 1m')
        nfeed = len(add)
        k = txt.rfind('.ends'); txt = txt[:k] + '\n'.join(add) + '\n' + txt[k:]
    cand.write_text(txt)
    if os.environ.get('GATEFIX', '1') == '1':      # hand gate-poly model instead of the extresist finger chain (gatefix.py)
        subprocess.run([sys.executable, str(HERE / 'gatefix.py'), str(cand), str(cand)], check=True, capture_output=True)
    os.environ['RFTX_VIEWFILES'] = json.dumps({'rfdriver': str(cand.relative_to(HERE))})
    nodes = PC.supply_nodes(cand)
    decks = {'drv': B.driver_deck('ext', amp=0.3, gain=15, out='drv.txt'), 'ir': PC.ir_deck('ext', nodes)}
    work = S.run_decks(decks, f'iter_{tag}')
    m = B.driver_metrics(work, 'drv', 0.3)
    import numpy as np
    y = np.loadtxt(work / 'ir.txt'); t = y[:, 0]; mm = t >= 5e-9 - 8 * S.T_LO; cols = y[:, 1::2]
    vd, vs = cols[mm, 0].mean(), cols[mm, 1].mean(); vn = cols[mm, 2:].mean(axis=0)
    ird = max(vd - v for n, v in zip(nodes, vn) if n.startswith('VDD')); irs = max(v - vs for n, v in zip(nodes, vn) if n.startswith('VSS'))
    out = dict(tag=tag, over=over, drc=r['drc_errors'], lvs=r['lvs_unique_match'], name_eq=r['lvs_name_equivalent'], w=r['width_um'], h=r['height_um'],
               area=r['area_um2'], fixcap=fx[:120], pad_dBm=m['pad_dBm_50ohm'], gain=m['voltage_gain'], supply_mA=m['supply_mA'],
               ir_vdd_mV=round(1e3 * ird, 1), ir_vss_mV=round(1e3 * irs, 1), feed=feed, feed_nodes=nfeed)
    print(json.dumps(out)); (base / 'result.json').write_text(json.dumps(out, indent=1))
    return out


if __name__ == '__main__':
    run(sys.argv[1], json.loads(sys.argv[2]) if len(sys.argv) > 2 else {})
