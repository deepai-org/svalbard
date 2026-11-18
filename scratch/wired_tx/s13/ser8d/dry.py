"""Dry-run floorplan model: le.generate with Magic stubbed out (geometry only).  usage: dry.py  (edit VARIANTS)"""
import sys, json, tempfile, types
from pathlib import Path
WTX = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_tx')
sys.path.insert(0, str(WTX))
import serq4_macro as M, serq8_macro as Q, ser8d_macro as D
le = M.le
import netlist as tn

def dry(rows, tag, **kw):
    le.FAST = M.FAST
    for n in D.CELLS:
        tn.MACROS[n] = json.loads((M.FAST / f'{n}.pins.json').read_text())['ports']
    work = Path(tempfile.mkdtemp(prefix='dry_', dir=str(Path(__file__).parent)))
    text = ''.join((M.FAST / f'{n}.spice').read_text() for n in D.CELLS)
    (work / 'top.spice').write_text(text + D.top_spice())
    ports, devices = tn.load(work / 'top.spice', D.NAME)
    if kw.pop('_noD', False):
        ports = [p for p in ports if not (p[0] == 'D' and p[1:].isdigit())]
    real = le.docker_magic
    le.docker_magic = lambda *a, **k: types.SimpleNamespace(returncode=0, stdout='', stderr='')
    try:
        rep = le.generate(work, D.NAME, ports, devices, rows=rows, **kw)
    finally:
        le.docker_magic = real
    import shutil; shutil.rmtree(work)
    W, H = rep['size_um']
    rs = ' | '.join(f"{r['right']:.0f}w {r['row_top']-r['y_bottom']:.0f}h+{r['channel_top']-r['row_top']:.0f}ch {r['tracks']}t" for r in rep['rows'])
    nd = len([d for d in rep['antenna_diodes'] if d.get('placed')]); nf = len([d for d in rep['antenna_diodes'] if not d.get('placed')])
    print(f'{tag:28s} {W:7.2f} x {H:7.2f} = {W*H/1e6:.4f} mm2  diodes {nd} placed {nf} unplaced\n    {rs}', flush=True)
    return rep

if __name__ == '__main__':
    import variants
    for tag, rows, kw in variants.VARIANTS:
        dry(rows, tag, **kw)
