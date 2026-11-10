"""Summarize a provider precheck run: per step, every report database's item counts."""
import json
import re
from collections import Counter
from pathlib import Path


def lyrdb_counts(path):
    text = path.read_text(errors='replace')
    items = re.findall(r'<item>.*?<category>(.*?)</category>', text, re.S)
    return Counter(c.strip().strip("'") for c in items)


def summarize(work):
    work = Path(work)
    runs = sorted((work/'precheck-run'/'runs').glob('*')) if (work/'precheck-run'/'runs').exists() else []
    out = dict(run=str(runs[-1]) if runs else None, steps={})
    if not runs:
        log = (work/'precheck.log').read_text(errors='replace') if (work/'precheck.log').exists() else ''
        out['log_tail'] = log[-3000:]
        return out
    for step in sorted(p for p in runs[-1].iterdir() if p.is_dir()):
        rep = {}
        for db in list(step.rglob('*.lyrdb'))+list(step.rglob('*.xml')):
            c = lyrdb_counts(db)
            rep[db.name] = dict(total=sum(c.values()), top=c.most_common(25))
        for f in step.rglob('*.rpt'):
            t = f.read_text(errors='replace')
            m = re.findall(r'Total DRC errors found:\s*(\d+)|\[INFO\]: COUNT: (\d+)', t)
            rep[f.name] = dict(size=len(t), counts=m[:5])
        metrics = step/'state_out.json'
        if metrics.exists():
            try:
                st = json.loads(metrics.read_text())
                rep['metrics'] = {k: v for k, v in st.get('metrics', {}).items()
                                  if any(s in k for s in ('drc', 'antenna', 'density', 'zero', 'error', 'violation'))}
            except Exception as e:   # noqa: BLE001
                rep['metrics_error'] = str(e)
        out['steps'][step.name] = rep
    log = (work/'precheck.log').read_text(errors='replace')
    out['errors'] = [l for l in log.splitlines() if 'ERROR' in l or 'error' in l.lower() and 'failed' in l.lower()][-20:]
    return out
