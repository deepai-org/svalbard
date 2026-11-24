"""r6 capture (bound master) rebuilt with ASM-12 pins: signal pins Metal4 0.8 um wide at the top edge; DX/WCLK40/EW trunks
spaced (net_space 0.4: neighbouring trunk column kept free -> >= 2.4 um pin pitch). LVS vs the r6 schematic."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import capture_r6 as c
c.EM = dict(pin_metal=4, pin_w=0.8)
c.NS = {**{f'DX{i}': 0.4 for i in range(40)}, **{f'EW{i}': 0.4 for i in range(20)}, 'WCLK40': 0.4}
r = c.build_top()
print(json.dumps(dict(drc=r['drc_errors'], lvs=(r['lvs'] or {}).get('unique_match'), size=r['layout'].get('size_um'), gds=r.get('gds_export')), default=str)[:800])
