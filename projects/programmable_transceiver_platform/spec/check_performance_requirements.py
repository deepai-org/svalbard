#!/usr/bin/env python3
"""Check (and optionally render) the performance requirements traceability table.

spec/performance-requirements.json is the source; spec/performance-requirements.md
is rendered from it with --write-md. The check fails (exit 1) when:
  - an ID is duplicated or does not appear in its source document;
  - a status is not one of meets/marginal/fails/unverified;
  - an evidence path does not exist;
  - a fallback is not a readiness fallback route, a board requirement ID,
    or a register field present in register-map.md;
  - a row that is not 'meets' has no primary fix (MANDATE: primary route first);
  - the rendered .md is out of date (unless --write-md).
It does not judge whether evidence is current; see source hashes in each evidence file.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / 'spec/performance-requirements.json'
MD = ROOT / 'spec/performance-requirements.md'
STATUSES = ('meets', 'marginal', 'fails', 'unverified')

def render(t):
    rows = t['rows']; cnt = {s: sum(r['status'] == s for r in rows) for s in STATUSES}
    out = ['# Performance requirements traceability', '',
           f'Rendered from `spec/performance-requirements.json` by `spec/check_performance_requirements.py --write-md`. Do not edit by hand.',
           'Status uses the performance-review legend (meets / marginal / fails / unverified), envelope only (Tj 22–32 °C, 3.15–3.35 V, all process corners).',
           'Per MANDATE.md the **primary fix** is the plan; fallbacks are backups.', '',
           'Summary: ' + ', '.join(f'{s} {cnt[s]}' for s in STATUSES) + f' (total {len(rows)}).', '',
           '| ID | Requirement | Owner | Evidence | Status | Basis | Primary fix | Fallback (backup) |',
           '|---|---|---|---|---|---|---|---|']
    esc = lambda s: str(s).replace('|', '\\|')
    for r in rows:
        ev = '<br>'.join(f'`{e}`' for e in r['evidence']) or '—'
        fb = ', '.join(f'`{f}`' for f in r['fallback']) or '—'
        st = r['status'] if r['status'] == 'meets' else f"**{r['status']}**"
        out.append(f"| {r['id']} | {esc(r['requirement'])} | {esc(r['owner'])} | {ev} | {st} | {esc(r['basis'])} | {esc(r['primary_fix'])} | {fb} |")
    return '\n'.join(out) + '\n'

def main():
    t = json.loads(SRC.read_text()); errs = []
    ready = json.loads((ROOT / 'spec/tapeout-readiness.json').read_text())
    routes = set(ready.get('fallback_routes', {}))
    board = (ROOT / 'spec/board-requirements.md').read_text()
    board_ids = set(re.findall(r'^\| (B\d+a?|HL-B\d+) \|', board, re.M))
    regmap = (ROOT / 'spec/register-map.md').read_text() + (ROOT / 'spec/interface-requirements.md').read_text()
    seen = set()
    for r in t['rows']:
        i = r['id']
        if i in seen: errs.append(f'{i}: duplicate id')
        seen.add(i)
        src = ROOT / r['source']
        if not src.exists() or not re.search(r'\b' + re.escape(i) + r'\b', src.read_text()):
            errs.append(f'{i}: id not found in {r["source"]}')
        if r['status'] not in STATUSES: errs.append(f'{i}: bad status {r["status"]}')
        for e in r['evidence']:
            if not (ROOT / e).exists(): errs.append(f'{i}: missing evidence {e}')
        if r['status'] == 'meets' and not r['evidence']: errs.append(f'{i}: meets without evidence')
        if r['status'] != 'meets' and r['primary_fix'].strip() in ('', '—', '-'):
            errs.append(f'{i}: {r["status"]} without a primary fix')
        for f in r['fallback']:
            if f in routes or f in board_ids: continue
            m = re.match(r'(debug\.[a-z_.]+)', f)
            if m and m.group(1).split('.')[-1] in regmap: continue
            errs.append(f'{i}: unknown fallback {f}')
    md = render(t)
    if '--write-md' in sys.argv: MD.write_text(md)
    elif not MD.exists() or MD.read_text() != md: errs.append('performance-requirements.md is stale; run with --write-md')
    cnt = {s: sum(r['status'] == s for r in t['rows']) for s in STATUSES}
    print(json.dumps(cnt), f'rows={len(t["rows"])}')
    for e in errs: print('ERROR', e)
    return 1 if errs else 0

if __name__ == '__main__':
    sys.exit(main())
