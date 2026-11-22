"""capture r7e rebuilt with the chip-grid Metal5 channels kept free (ASM-8, assembly phase rule: block LL at 0 mod 70;
VSS axes x = 12.25 + 70k, VDD axes x = 47.25 + 70k, channel 27 um centred).  Cells = the r7e cells (unchanged)."""
import sys, json
from pathlib import Path
W = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_rx'); sys.path.insert(0, str(W))
import capture as c
S = Path(__file__).resolve().parent
c.FAST = S / 'fast'; c.SCRATCH = S / 'cap'; c.GEN = S / 'gen'
for d in (c.SCRATCH, c.GEN): d.mkdir(parents=True, exist_ok=True)
OFF = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0      # engine x of the block's left edge
keep = []
for k in range(-1, 20):
    for ax in (12.25, 47.25):
        x = OFF + ax + 70 * k
        keep.append((x - 13.5, x + 13.5))
r = c.build_top(em=dict(m5_keep=keep))
print(json.dumps(dict(drc=r['drc_errors'], lvs=(r['lvs'] or {}).get('unique_match'), prop=(r['lvs'] or {}).get('property_errors'),
                      size=r['layout'].get('size_um'), ant=len(r['layout'].get('antenna_diodes') or []), gds=r.get('gds_export')), default=str))
