"""Check report source identities; freshness is not functional coverage."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]
reports=['connected-platform','connected-platform-clock-sweep','connected-platform-host-clock-sweep',
         'connected-clock-holdover','connected-transition-density']
rows=[]
for name in reports:
    path=P/('evidence/'+name+'.json')
    if not path.exists():
        rows.append(dict(report=name,status='missing'));continue
    d=json.loads(path.read_text());sources=d.get('source_hashes',d.get('sources_sha256',{}))
    mismatches=[]
    for relative,expected in sources.items():
        source=P/relative
        if not source.exists():mismatches.append(dict(source=relative,reason='missing'))
        elif hashlib.sha256(source.read_bytes()).hexdigest()!=expected:
            mismatches.append(dict(source=relative,reason='changed'))
    rows.append(dict(report=name,status='stale' if mismatches else 'current' if sources else 'no_source_inventory',
        report_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),mismatches=mismatches))
out=dict(status='source_identity_audit_only',reports=rows,
    limitations=['Current hashes do not prove complete dependencies, test validity, or architecture completion.',
                 'Stale reports retain historical value but do not verify current source.'])
(P/'evidence/connected-evidence-freshness.json').write_text(json.dumps(out,indent=2)+'\n')
for r in rows:print(r['report'],r['status'])
