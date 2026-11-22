"""r7f capture staging (r12): points capture.py's FAST/SCRATCH/GEN at scratch/wired_rx/r12/cap/r7f.  No publish.
usage: python3 stage.py cells [wc_x ...] | top"""
import sys, json
from pathlib import Path
W = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_rx'); sys.path.insert(0, str(W))
import capture as c
S = Path(__file__).resolve().parent / 'r7f'
c.FAST = S / 'fast'; c.SCRATCH = S / 'cap'; c.GEN = S / 'gen'
for d in (c.FAST, c.SCRATCH, c.GEN): d.mkdir(parents=True, exist_ok=True)
if __name__ == '__main__':
    if 'cells' in sys.argv:
        f = c.GEN / 'wrx_cap-cells.json'
        cells = json.loads(f.read_text()) if f.exists() else {}
        only = [a for a in sys.argv[1:] if a.startswith('wc_')] or list(c.CELLS)
        cells.update({n: c.build_cell(n) for n in only})
        f.write_text(json.dumps(cells, indent=1, default=str))
    if 'top' in sys.argv:
        r = c.build_top()
        print(json.dumps(dict(drc=r['drc_errors'], lvs=(r['lvs'] or {}).get('unique_match'), size=r['layout'].get('size_um'),
                              area=r['layout'].get('area_um2'), ant=len(r['layout'].get('antenna_diodes') or []), gds=r.get('gds_export')), default=str))
