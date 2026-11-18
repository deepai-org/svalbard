"""Wire capacitance per net from a flat Magic C-only netlist (ext2spice hierarchy off, cthresh 0).
usage: ctab.py <flat.spice> [json out]   total = sum of every extracted C with a terminal on the net (fF);
gnd = part to VSS / VDD / substrate; the rest is coupling to other signal nets (largest partner shown)."""
import sys, re, json
from collections import defaultdict
QUIET = {'VSS', 'VDD', 'VSUBS', '0'}
def table(path):
    tot, gnd, cpl = defaultdict(float), defaultdict(float), defaultdict(lambda: defaultdict(float))
    unit = {'f': 1.0, 'a': 1e-3, 'p': 1e3}
    for l in open(path):
        if not l.startswith('C'): continue
        t = l.split()
        m = re.fullmatch(r'([0-9.eE+-]+)([fap])F?', t[3])
        v = float(m.group(1)) * unit[m.group(2)] if m else float(t[3]) * 1e15
        a, b = t[1], t[2]
        for x, y in ((a, b), (b, a)):
            tot[x] += v
            if y in QUIET: gnd[x] += v
            else: cpl[x][y] += v
    return tot, gnd, cpl
def alias(tot):
    """top-level net -> its name in the flat netlist (a port keeps its name; an internal net is named <instance>/<pin>)."""
    sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_tx')
    import ser8d_macro as D, serq4_macro as M
    out = {}
    for inst, cell, conns in D.top_instances():
        ports = json.loads((M.FAST / f'{cell}.pins.json').read_text())['ports']
        for p, n in zip(ports, conns):
            for cand in (n, f'{inst}/{p}'):
                if cand in tot: out.setdefault(n, set()).add(cand)
    return out
def rows(path):
    tot, gnd, cpl = table(path)
    al = alias(tot)
    multi = {n: v for n, v in al.items() if len(v) > 1 and n not in QUIET}
    assert not multi, multi
    for n, v in al.items():
        f = next(iter(v))
        if f != n: tot[n], gnd[n], cpl[n] = tot[f], gnd[f], cpl[f]
    nets = [f'PH{a}' for a in (0, 45, 90, 135, 180, 225, 270, 315)] + [f'F{k}' for k in range(8)] + [f'Q{k}' for k in range(8)] + \
           [f'B{k}_0' for k in range(8)] + sorted(n for n in tot if re.fullmatch(r'R\d_\d', n)) + ['QK0', 'QK1', 'QKN0', 'QKN1', 'QDN', 'QD', 'LDA', 'QRST', 'DC', 'SERQ', 'WCKQ']
    out = {}
    rev = {next(iter(v)): n for n, v in al.items()}
    for n in nets:
        if n not in tot: out[n] = None; continue
        big = max(cpl[n].items(), key=lambda kv: kv[1]) if cpl[n] else ('-', 0.0)
        out[n] = dict(total_fF=round(tot[n], 2), gnd_fF=round(gnd[n], 2), coupling_fF=round(tot[n] - gnd[n], 2), largest_partner=rev.get(big[0], big[0]), partner_fF=round(big[1], 2))
    d = [tot[f'D{i}'] for i in range(40) if f'D{i}' in tot]
    out['D0..D39 (min / mean / max)'] = dict(total_fF=[round(min(d), 1), round(sum(d) / len(d), 1), round(max(d), 1)])
    return out
if __name__ == '__main__':
    r = rows(sys.argv[1])
    if len(sys.argv) > 2: open(sys.argv[2], 'w').write(json.dumps(r, indent=1) + '\n')
    for n, v in r.items(): print(n, v)
