"""Collect generated/<block>-evidence.json into generated/rf_rx-summary.json (and print it).

  python3 summarize.py            write generated/rf_rx-summary.json, print it (README.md is NOT touched)
  python3 summarize.py --readme   also re-render the block between the RESULTS:BEGIN / RESULTS:END markers of README.md
  python3 summarize.py --print    print the rendered results section to stdout (no file written)

Read-only on the evidence files.  Two evidence formats are understood: the four-test records written by characterize.py
(rxmix_*, bbfilter_*, bb_tap) and the LNA record written by lna_close.py (tests = named limit groups with a 'pass' field);
the LNA rows are summarised only, the table is README section 5a.  A record whose simulated netlist or layout artefacts no
longer match the files on disk is reported as STALE; a failed row is printed as FAIL, never as pass.
"""
import json
import sys

import rfrx_flow as flow

ALLOC_UM2 = {'lna': 220000, 'rxmix_i': 100000, 'rxmix_q': 100000, 'bbfilter_i': 430000, 'bbfilter_q': 430000,
             'bb_tap': None}
FOUR = ('safe', 'clean', 'observable', 'fallback')
NA = 'not available'


def _load(b):
    p = flow.GENERATED / f'{b}-evidence.json'
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except ValueError:
        return {'unreadable': True}


def _layout(b):
    p = flow.GENERATED / f'{b}-layout.json'
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


def _sha(name):
    p = flow.HERE / name if (flow.HERE / name).exists() else flow.GENERATED / name
    return flow.sha256(p) if p.exists() else None


def is_lna_close(r):
    return 'tests' in r and not all(k in r['tests'] for k in FOUR)


def stale_files(b, r):
    """Files named in the evidence whose sha256 differs from the file on disk (the block's own netlist / GDS / extracted netlist)."""
    if is_lna_close(r):
        return [k for k, v in (r.get('hashes') or {}).items() if k.startswith('lna.') and _sha(k) != 'sha256:' + str(v)]
    hs = {**(r.get('source_hashes') or {}), **(r.get('artifact_hashes') or {}), **(r.get('simulated_netlist_sha256') or {})}
    return sorted(k for k, v in hs.items() if k.startswith(b) and _sha(k) != v)


def perf_state(r):
    """'fail' if any performance row (or any of its corner rows) failed; 'open' if a row is not available; else 'pass'."""
    if 'performance_state' in r:
        return r['performance_state']
    ps = [p.get('pass') for p in r.get('performance_vs_target', [])]
    return 'fail' if any(x is False for x in ps) else ('open' if NA in ps else 'pass')


def block_row(b):
    r = _load(b)
    if r is None:
        return {'missing': True}
    if r.get('unreadable') or 'tests' not in r:
        return {'unreadable': True}
    lay = _layout(b)
    row = dict(area_um2=lay.get('area_um2'), area_allocation_um2=ALLOC_UM2[b], drc_errors=lay.get('drc_count'),
               klayout_drc_violations=(lay.get('klayout_drc') or {}).get('violations'),
               lvs=(lay.get('lvs') or {}).get('final_result'))
    stale = stale_files(b, r)
    row['evidence_matches_files_on_disk'] = not stale
    if stale:
        row['stale_against'] = stale
    if is_lna_close(r):
        row.update(evidence_format='lna_close.py', evidence_area_um2=(r.get('layout') or {}).get('area_um2'),
                   states={k: ('pass' if v.get('pass') is True else 'fail') for k, v in r['tests'].items()},
                   all_pass=bool(r.get('all_pass')), see='README.md section 5a')
    else:
        t = r['tests']
        row.update(evidence_format='characterize.py', evidence_area_um2=(r.get('area') or {}).get('area_um2'),
                   states={k: t[k]['state'] for k in FOUR}, performance_state=perf_state(r),
                   failing_rows=r.get('failing_rows', [p['metric'][:110] for p in r.get('performance_vs_target', []) if p.get('pass') is False]),
                   rows_not_available=r.get('rows_not_available', []), corner_set=(r.get('corner_set') or {}).get('name'))
        row['all_pass'] = bool(all(v == 'pass' for v in row['states'].values()) and row['performance_state'] == 'pass' and not stale)
    return row


def chain_row():
    p = flow.GENERATED / 'rf_rx_chain.json'
    if not p.exists():
        return {'missing': True}
    try:
        c = json.loads(p.read_text())
    except ValueError:
        return {'unreadable': True}
    now = {f'{b}.ext.spice': flow.sha256(flow.GENERATED / f'{b}.ext.spice') for b in ('lna', 'rxmix_i', 'rxmix_q')}
    row = {'evidence_matches_files_on_disk': c.get('netlist_sha256') == now}
    for k, v in c.items():
        if k.startswith('ext_') and isinstance(v, dict):
            row[k] = {x: v.get(x) for x in ('gain_i_db', 'gain_q_db', 'irr_db', 'idd_a', 'error') if v.get(x) is not None}
    nf = c.get('chain_nf')
    if isinstance(nf, dict):
        row['chain_nf'] = {'state': nf.get('state'), 'reason': nf.get('reason'), 'target_dsb_db': nf.get('target_dsb_db'),
                           'nf_dsb_db': [r.get('nf_dsb_db') for r in nf.get('rows', [])]}
    else:
        row['chain_nf'] = {'state': NA, 'reason': 'rf_rx_chain.json has no chain_nf entry (old format)'}
    return row


def main():
    rows = {b: block_row(b) for b in flow.BLOCKS}
    rows['chain'] = chain_row()
    (flow.GENERATED / 'rf_rx-summary.json').write_text(json.dumps(rows, indent=1) + '\n')
    for b, v in rows.items():
        print(b, json.dumps(v))
    return rows


def _f(v, scale=1., fmt='{:.3g}'):
    try:
        return fmt.format(v * scale)
    except (TypeError, ValueError):
        return 'n/a'


def _p(v):
    """Pass column: only a literal True prints as pass."""
    if v is True:
        return 'pass'
    if v is False:
        return '**FAIL**'
    if v in ('info', NA):
        return v
    return '' if v in (None, '') else str(v)


def results_markdown():
    """Section 5 of README.md, rendered from the evidence files."""
    G = flow.GENERATED
    ev = {b: r for b in flow.BLOCKS for r in [_load(b)] if r and 'tests' in r}
    out = ['<!-- RESULTS:BEGIN (rendered by summarize.py from generated/*.json) -->', '## 5. Results', '',
           '### Physical and four-test status', '',
           '| Block | Area (um2) | Allocation (um2) | Magic DRC | KLayout DRC | LVS | safe | clean | observable | fallback | performance rows | evidence = files on disk |',
           '| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- | --- |']
    for b, r in ev.items():
        s = block_row(b)
        if is_lna_close(r):
            st = ['see 5a'] * 4 + ['pass' if s['all_pass'] else '**FAIL** (section 5a)']
        else:
            st = [s['states'][x] if s['states'][x] == 'pass' else f"**{s['states'][x].upper()}**" for x in FOUR]
            st.append({'pass': 'pass', 'fail': '**FAIL**', 'open': 'open (rows not available)'}[s['performance_state']])
        out.append(f"| {b} | {_f(s['area_um2'], fmt='{:.0f}')} | {ALLOC_UM2[b] or 'none'} | {s['drc_errors']} | {s['klayout_drc_violations']} | "
                   f"{s['lvs']} | " + ' | '.join(st) + f" | {'yes' if s['evidence_matches_files_on_disk'] else '**STALE**'} |")
    out += ['', '### Extracted performance vs target (tt, 27 C, 3.3 V unless a corner table is given)', '']
    for b, r in ev.items():
        out.append(f'**{b}**')
        out.append('')
        if is_lna_close(r):
            out += ['LNA rows: section 5a (`generated/lna-evidence.json`, written by `lna_close.py`). Limit groups: '
                    + ', '.join(f"{k} {_p(v.get('pass') is True)}" for k, v in r['tests'].items()) + '.', '']
            continue
        out.append('| Metric | Target | Extracted | Pass |')
        out.append('| --- | --- | --- | --- |')
        for p in r['performance_vs_target']:
            if 'rows' in p:
                continue
            v = p.get('extracted_nominal')
            if isinstance(v, dict):
                v = {k: v[k] for k in ('dc_gain_db', 'f3db_hz', 'peak_gain_db', 'gain_i_db', 'gain_q_db') if k in v}
                v = ', '.join(f'{k}={_f(x)}' for k, x in v.items())
            elif isinstance(v, list):
                v = ', '.join(_f(x) for x in v)
            else:
                v = _f(v)
            if v == 'n/a' and isinstance(p.get('extracted'), (list, dict)):
                v = 'see generated/' + b + '-evidence.json'
            out.append(f"| {p['metric']} | {p.get('target', '')} | {v} | {_p(p.get('pass'))} |")
        for p in r['performance_vs_target']:
            if 'rows' not in p or not isinstance(p['rows'], list):
                continue
            rows = [row for row in p['rows'] if isinstance(row, dict)]
            keys = []
            for row in rows:
                keys += [k for k in row if k not in ('corner', 'rows', 'pass') and k not in keys]
            nfail = sum(row.get('pass') is False for row in rows)
            out += ['', f"{p['metric']}: min / max over {len(rows)} rows (corners x cases). Target: {p.get('target', 'none stated')}. "
                        f"{p.get('corners', '')} Pass: {_p(p.get('pass'))}" + (f' ({nfail} failing rows)' if nfail else ''), '',
                    '| Quantity | min | max |', '| --- | --- | --- |']
            flat = lambda x: x if isinstance(x, list) else [x]
            for k in keys:
                vals = [y for row in rows for y in flat(row.get(k)) if isinstance(y, (int, float)) and not isinstance(y, bool)]
                if vals:
                    out.append(f'| {k} | {_f(min(vals))} | {_f(max(vals))} |')
            errs = [row for row in rows if 'error' in row]
            if errs:
                out.append(f'| failed corner runs | {len(errs)} | |')
        out.append('')
    ch = G / 'rf_rx_chain.json'
    if ch.exists():
        c = json.loads(ch.read_text())
        s = chain_row()
        out += ['### RF chain (extracted LNA + both extracted mixers, ideal square LO)', '',
                'Record matches the extracted netlists on disk: ' + ('yes' if s['evidence_matches_files_on_disk'] else '**STALE**') + '.', '',
                '| Case | LO (Hz) | I gain (dB) | Q gain (dB) | IRR (dB) | Supply (mA) |', '| --- | --- | --- | --- | --- | --- |']
        for k, v in c.items():
            if not k.startswith('ext_'):
                continue
            if isinstance(v, dict) and v.get('gain_i_db') is not None:
                out.append(f"| {k} | {_f(v.get('f_lo_hz'))} | {_f(v.get('gain_i_db'))} | {_f(v.get('gain_q_db'))} | {_f(v.get('irr_db'))} | {_f(v.get('idd_a'), 1e3)} |")
            else:
                out.append(f'| {k} | error | | | | |')
        nf = c.get('chain_nf') if isinstance(c.get('chain_nf'), dict) else {'state': NA, 'reason': 'old record format'}
        out.append('')
        if nf.get('rows'):
            out.append(f"Chain NF, DSB, real channel, LO as delivered (target <= {nf.get('target_dsb_db')} dB; {nf.get('source')}): "
                       + '; '.join(f"{r.get('view')} {r.get('corner')} LO {r.get('lo')}: {_f(r.get('nf_dsb_db'))} dB" for r in nf['rows'])
                       + f". State: {_p(nf.get('state') == 'pass')}.")
        else:
            out.append(f"Chain NF: {NA} for the cells on disk ({nf.get('reason')}).")
        out.append('')
    out.append('<!-- RESULTS:END -->')
    return '\n'.join(out)


def render_readme():
    import re
    p = flow.HERE / 'README.md'
    t = p.read_text()
    sec = results_markdown()
    if 'RESULTS_PLACEHOLDER' in t:
        t = t.replace('RESULTS_PLACEHOLDER', sec)
    else:
        t = re.sub(r'<!-- RESULTS:BEGIN.*?<!-- RESULTS:END -->', lambda m: sec, t, flags=re.S)
    p.write_text(t)


if __name__ == '__main__':
    if '--print' in sys.argv:
        print(results_markdown())
    else:
        main()
        if '--readme' in sys.argv:
            render_readme()
