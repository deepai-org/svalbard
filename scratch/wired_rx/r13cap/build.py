"""capture r8 = r7e + DF/EF registered in wc_lane (full-rate race fix), grid channels (ASM-8), ASM-12 pins:
Metal4 0.8 um at the top edge, DW/EW/WSTB trunks spaced (>= 2.4 um pitch)."""
import sys, json
from pathlib import Path
W = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_rx'); sys.path.insert(0, str(W))
import capture as c
S = Path(__file__).resolve().parent
c.FAST = S / 'fast'; c.SCRATCH = S / 'cap'; c.GEN = S / 'gen'
for d in (c.SCRATCH, c.GEN): d.mkdir(parents=True, exist_ok=True)
if 'cells' in sys.argv:
    print('wc_lane', json.dumps(c.build_cell('wc_lane'), default=str)[:400], flush=True)
keep = [(ax + 70 * k - 13.5, ax + 70 * k + 13.5) for k in range(-1, 20) for ax in (12.25, 47.25)]
ns = {**{f'DW{i}': 0.4 for i in range(20)}, 'WSTB': 0.4}
r = c.build_top(em=dict(m5_keep=keep, pin_metal=4, pin_w=0.8), net_space=ns)
print(json.dumps(dict(drc=r['drc_errors'], lvs=(r['lvs'] or {}).get('unique_match'), size=r['layout'].get('size_um'),
                      gds=r.get('gds_export')), default=str)[:900])
