"""r12 ptrim staging (copy of r10ptrim/stage.py for the fixed-offset variant): scratch/wired_rx/r12/ptrim/<NAME>/, never generated/.
usage: stage12.py NAME FIX=[f0,..,f7] [cell] [top]
Family (LVS reference) = netlists.ptrim() with PTRIM_FIX = FIX, written to <NAME>/family.spice."""
import sys, json, ast
from pathlib import Path
W = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_rx'); sys.path.insert(0, str(W))
H = Path(__file__).resolve().parent
import ptrim_compact as p, netlists
p.STRAP_M5 = False          # r12: Metal5 kept free (ASM-8)
name = sys.argv[1]; S = H / name
fix = ast.literal_eval([a for a in sys.argv if a.startswith('FIX=')][0][4:])
p.FIX = list(fix); netlists.PTRIM_FIX = tuple(fix)
p.FAST = S / 'fast'; p.SCRATCH = S / 'work'; p.GEN = S / 'gen'
for d in (p.FAST, p.SCRATCH, p.GEN): d.mkdir(parents=True, exist_ok=True)
(S / 'family.spice').write_text(netlists.BLOCKS['ptrim']().emit()); p.FAMILY = S / 'family.spice'
short = lambda r: {k: (v if k != 'lvs' else v.get('unique_match')) for k, v in r.items()}
if 'cell' in sys.argv:
    for c in sorted({p.cell_of(k) for k in range(8)}): print(c, json.dumps(short(p.build_cell(c)), default=str), flush=True)
if 'top' in sys.argv:
    r = p.build_top()
    print(json.dumps(dict(drc=r['drc_errors'], lvs=(r['lvs'] or {}).get('unique_match'), lvs_family=(r['lvs_family'] or {}).get('unique_match'),
          size=r['layout'].get('size_um'), area=r['layout'].get('area_um2'), gds=r.get('gds_export')), default=str))
