"""Repeat physical SAR with additional observations only."""
import argparse,hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3]
ap=argparse.ArgumentParser();ap.add_argument('--small',action='store_true');args=ap.parse_args()
B=R/('scratch/transceiver-sar-driver-physical-100-prepared' if args.small else 'scratch/transceiver-sar-driver-physical-400-prepared')
O=R/('scratch/transceiver-sar-bottom-plates-small-prepared' if args.small else 'scratch/transceiver-sar-bottom-plates-prepared')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((B/'manifest.json').read_text())
assert sha(B/'baseline.spice')==m['artifacts_sha256']['baseline.spice']
s=(B/'baseline.spice').read_text()
line=next(l for l in s.splitlines() if l.startswith('wrdata '))
extra=''.join(f' v(xd.x{side}{bit}.bot)' for bit in range(7) for side in ('p','n'))
candidate=s.replace(line,line+extra)
assert candidate.replace(line+extra,line)==s
O.mkdir()
(O/'baseline.spice').write_text(candidate)
m.update(candidate='Observation-only repeat: add fourteen missing CDAC bottom plates.',
    baseline_preparation_sha256=sha(B/'manifest.json'),
    artifacts_sha256={'baseline.spice':sha(O/'baseline.spice')},
    qualification_plan=['Require clean full transient and identical circuit/stimulus.',
        'Compare original saved vectors and final codes against source run.',
        'Reconstruct weighted differential bottom-plate movement relative to held anchor.'],
    limitations=['Observation only; no circuit improvement or predictive-model qualification.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
print(O)
