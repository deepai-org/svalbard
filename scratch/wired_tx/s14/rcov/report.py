import json, re
CELLS = ['wtx_ser8d', 'wtx_mux8', 'wtx8_aux', 'pt_wiredtx8']
WHY = [(r'(^|\.)PH\d+$|^PS\d', 'phase/clock distribution into the serializer: RC adds skew between phases (timing net)'),
       (r'\.CK$|QK\d|QKN\d|\.QD|QDN|XN\d', 'register clock / clock-divider net: RC delays & skews the clock edge'),
       (r'\.LDB?$|LDO|QRST|XCTL', 'serializer load/reset control: RC delays the parallel-load window against the phase clocks'),
       (r'^D\d+$|^DX$|WTX_EXT', 'parallel data input (word-rate): large R*C slows the setup into the load latches'),
       (r'ENB[MQ]|ENMI|ENM$|EN_|ENP|ENMAIN|ENPOST|TX_RUN|RUN|EXT|SER_EN|IDLE|ISLAND|POL', 'static/slow enable or mode line: RC only matters at enable/mode change (low criticality)'),
       (r'CODE|BIAS|ATB|TAP', 'static code / bias / test line: DC after settling (low criticality unless switched at speed)'),
       (r'^(XMUX\.)?[UV]P\d|XS\d\.Y|OV[PN]', 'mux slice pre-driver / per-slice control: RC adds slice-to-slice skew at the output'),
       (r'', 'internal node (unnamed): series R exceeds 5 % of its driver Ron and RC > 2 ps')]
def why(n):
    return next(w for p, w in WHY if re.search(p, n))
out = dict(thresholds='THRESHOLDS.md', cells={})
md = []
for c in CELLS:
    d = json.load(open(f'x/{c}.json'))
    nets = d['nets']
    tot = len(nets); ind = sum(v['in_drawn'] for v in nets.values())
    fails = {k: v for k, v in nets.items() if not v['in_drawn'] and not v['ok']}
    fails_stub = [k for k, v in nets.items() if not v['in_drawn'] and not (v['R_incl_stubs'] * v['C_fF'] * 1e-3 < 2 if v['timing'] else ((v['ron'] and v['R_incl_stubs'] < .05 * v['ron']) or v['R_incl_stubs'] * v['C_fF'] * 1e-3 < 2))]
    out['cells'][c] = dict(nets_total=tot, nets_in_drawn_R=ind, nets_audited=tot - ind, nets_fail=len(fails),
                           nets_fail_if_device_stubs_counted=len(fails_stub), negative_control=d['negative_control'],
                           failing=[dict(net=k, why=why(k), **v) for k, v in sorted(fails.items(), key=lambda kv: -kv[1]['RC_ps'])],
                           all_audited={k: v for k, v in nets.items() if not v['in_drawn']})
json.dump(out, open('rcov.json', 'w'), indent=1)
for c in CELLS:
    x = out['cells'][c]
    print(f"| {c} | {x['nets_total']} | {x['nets_in_drawn_R']} | {x['nets_audited']} | {x['nets_fail']} | {x['nets_fail_if_device_stubs_counted']} |")
for c in CELLS:
    print(f'\n### {c}\n\n| net | R wire (ohm) | R incl. device stubs | C (fF) | RC (ps) | driver (Ron) | timing | why it matters |\n|---|---|---|---|---|---|---|---|')
    for f in out['cells'][c]['failing']:
        print(f"| {f['net']} | {f['R']:.1f} | {f['R_incl_stubs']:.0f} | {f['C_fF']:.1f} | {f['RC_ps']:.2f} | {f['driver']}" + (f" ({f['ron']:.0f} ohm)" if f['ron'] else '') + f" | {'yes' if f['timing'] else 'no'} | {f['why']} |")
