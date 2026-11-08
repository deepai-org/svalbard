"""Collect generated/<block>-evidence.json into generated/rf_rx-summary.json (and print it)."""
import json

import rfrx_flow as flow

ALLOC_UM2 = {'lna': 220000, 'rxmix_i': 100000, 'rxmix_q': 100000, 'bbfilter_i': 430000, 'bbfilter_q': 430000,
             'bb_tap': None}


def main():
    rows = {}
    for b in flow.BLOCKS:
        p = flow.GENERATED / f'{b}-evidence.json'
        if not p.exists():
            rows[b] = {'missing': True}
            continue
        r = json.loads(p.read_text())
        t = r['tests']
        lay = json.loads((flow.GENERATED / f'{b}-layout.json').read_text())
        if 'klayout_crosscheck' not in t['clean']['drc']:      # older characterize runs
            t['clean']['drc']['klayout_crosscheck'] = lay.get('klayout_drc')
            p.write_text(json.dumps(r, indent=1, default=str) + '\n')
        rows[b] = dict(area_um2=r['area']['area_um2'], area_allocation_um2=ALLOC_UM2[b],
                       drc_errors=t['clean']['drc']['errors'],
                       klayout_drc_violations=(t['clean']['drc']['klayout_crosscheck'] or {}).get('violations'),
                       lvs=t['clean']['lvs']['result'],
                       states={k: v['state'] for k, v in t.items()})
    (flow.GENERATED / 'rf_rx-summary.json').write_text(json.dumps(rows, indent=1) + '\n')
    for b, v in rows.items():
        print(b, json.dumps(v))


if __name__ == '__main__':
    main()


def _f(v, scale=1., fmt='{:.3g}'):
    try:
        return fmt.format(v * scale)
    except (TypeError, ValueError):
        return 'n/a'


def results_markdown():
    """Section 5 of README.md, rendered from the evidence files."""
    G = flow.GENERATED
    ev = {b: json.loads((G / f'{b}-evidence.json').read_text()) for b in flow.BLOCKS if (G / f'{b}-evidence.json').exists()}
    out = ['<!-- RESULTS:BEGIN (rendered by summarize.py from generated/*.json) -->', '## 5. Results', '',
           '### Physical and four-test status', '',
           '| Block | Area (um2) | Allocation (um2) | Magic DRC | KLayout DRC | LVS | safe | clean | observable | fallback |',
           '| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- |']
    for b, r in ev.items():
        t = r['tests']
        k = (t['clean']['drc'].get('klayout_crosscheck') or {}).get('violations')
        out.append(f"| {b} | {r['area']['area_um2']:.0f} | {ALLOC_UM2[b] or 'none'} | {t['clean']['drc']['errors']} | {k} | "
                   f"{'unique match' if t['clean']['lvs']['unique_match'] else t['clean']['lvs']['result']} | "
                   + ' | '.join(t[x]['state'] for x in ('safe', 'clean', 'observable', 'fallback')) + ' |')
    out += ['', '### Extracted performance vs target (tt, 27 C, 3.3 V unless a corner table is given)', '']
    for b, r in ev.items():
        out.append(f'**{b}**')
        out.append('')
        out.append('| Metric | Target | Extracted | Schematic |')
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
            out.append(f"| {p['metric']} | {p.get('target', '')} | {v} | {_f(p.get('schematic_nominal'))} |")
        for p in r['performance_vs_target']:
            if 'rows' not in p:
                continue
            keys = [k for k in p['rows'][0] if k not in ('corner',)]
            out += ['', f"{p['metric']}: min / max over {len(p['rows'])} corners (tt/ss/ff x 22/32 C x 3.15/3.35 V)", '',
                    '| Quantity | min | max |', '| --- | --- | --- |']
            for k in keys:
                vals = [row.get(k) for row in p['rows'] if isinstance(row.get(k), (int, float))]
                if vals:
                    out.append(f'| {k} | {_f(min(vals))} | {_f(max(vals))} |')
            errs = [row for row in p['rows'] if 'error' in row]
            if errs:
                out.append(f'| failed corner runs | {len(errs)} | |')
        out.append('')
    ch = G / 'rf_rx_chain.json'
    if ch.exists():
        c = json.loads(ch.read_text())
        out += ['### RF chain (extracted LNA + both extracted mixers, ideal LO)', '',
                '| Case | LO (Hz) | I gain (dB) | Q gain (dB) | Supply (mA) |', '| --- | --- | --- | --- | --- |']
        for k, v in c.items():
            if isinstance(v, dict) and 'gain_i_db' in v:
                out.append(f"| {k} | {_f(v.get('f_lo_hz'))} | {_f(v.get('gain_i_db'))} | {_f(v.get('gain_q_db'))} | {_f(v.get('idd_a'), 1e3)} |")
            elif isinstance(v, dict) and 'lna_nf_matched_db' in v:
                out.append(f"| NF estimate (board match): LNA {_f(v.get('lna_nf_matched_db'))} dB, chain "
                           f"{_f(v.get('nf_chain_db'))} dB | 2.4e9 | | | |")
            else:
                out.append(f'| {k} | error | | | |')
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
    render_readme()
