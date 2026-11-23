#!/usr/bin/env python3
"""R+C extraction of a published converter GDS (MANDATE 4a: full-coverage extresist, C rebuilt from the C-only
extraction of the same GDS; method of scratch/wired_tx/s16/net/{extfull16,fixcap16,check16}.py).

  python3 rcext.py <block> [--gds PATH] [--tol 0] [--out DIR]
  -> <out>/pt_<block>.rc.spice (subckt pt_<block>, same ports as generated/<block>.ext.spice) and <out>/rcext.json

Magic (analog image), one flattened copy of the GDS, two extractions in the same run setup:
  conly : extract capacitance + coupling, ext2spice cthresh 0 (reference C)
  full  : + extract resistance, extresist all (simplify off, VDD/VSS/VSUBS ignored), ext2spice extresist on
Repairs of the full netlist (both are ext2spice extresist artefacts found in s14/s16):
  1. ground C: for every net (root + .tN/.nN sub-nodes) the caps to VSS are scaled so their sum equals the C-only
     ground C of that net (extresist writes the root's lumped cap and the sub-node caps: up to 2.4-5x over-count);
  2. coupling caps the full netlist dropped (pairs to unnamed '#' nets) are added between the two root nodes.
Reported: coverage (signal nets with at least one resistor / signal nets), total R, per-net ground-C cross-check
(after repair; max relative error over nets above 1 fF) and the coupling total vs the C-only netlist.
Not covered: VDD/VSS resistance (ignored: the supplies are ideal sources in every bench) - a stated limitation.
"""
import argparse
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'lib'))
import convkit as ck  # noqa: E402

G = ('VSS', 'VSUBS', '0')


def val(s):
    m = {'f': 1e-15, 'p': 1e-12, 'n': 1e-9, 'a': 1e-18, 'u': 1e-6, 'm': 1e-3, 'k': 1e3}
    s = s.lower()
    return float(s[:-1]) * m[s[-1]] if s[-1] in m else float(s)


def base(n):
    return re.sub(r'\.(t|n)\d+$', '', n).rstrip('#').replace('/', '.')


def joined(text):
    out = []
    for line in text.split('\n'):
        if line.startswith('+') and out:
            out[-1] += ' ' + line[1:]
        else:
            out.append(line)
    return out


def fixcap(ref_text, src_text):
    rg, rp = defaultdict(float), defaultdict(float)
    for line in joined(ref_text):
        if not line.startswith('C'):
            continue
        t = line.split()
        a, b, x = base(t[1]), base(t[2]), val(t[3])
        if a == b:
            continue
        if b in G or 'FLOATING' in line:
            rg[a] += x
        elif a in G:
            rg[b] += x
        else:
            rp[tuple(sorted((a, b)))] += x
    L = joined(src_text)
    tok, gidx, fg, fp, end = defaultdict(set), [], defaultdict(float), set(), None
    for i, line in enumerate(L):
        p = line.split()
        if not p:
            continue
        if p[0].lower().startswith('.ends'):
            end = i
        if p[0][0] in 'XRCD' and len(p) > 2:
            for n in (p[1:5] if p[0][0] == 'X' else p[1:3]):
                tok[base(n)].add(n)
        if line.startswith('C'):
            a, b = base(p[1]), base(p[2])
            if b in G or a in G or 'FLOATING' in line:
                n = a if a not in G else b
                gidx.append((i, n))
                fg[n] += val(p[3])
            else:
                fp.add(tuple(sorted((a, b))))

    def root(n):
        ts = tok.get(n, ())
        for t in ts:
            if base(t) == n and t.rstrip('#') == t.replace('/', '.') and not re.search(r'\.(t|n)\d+$', t):
                return t
        for t in sorted(ts):
            if t.endswith('.n0'):
                return t
        return sorted(ts)[0] if ts else None

    before = sum(fg.values())
    after = 0.
    for i, n in gidx:
        p = L[i].split()
        k = rg[n] / fg[n] if (n in rg and fg[n] > 0) else (0. if n not in rg else 1.)
        c = val(p[3]) * k
        after += c
        L[i] = f'{p[0]} {p[1]} {p[2]} {c:.6g}'
    add, addc, miss = [], 0., 0
    for (a, b), x in rp.items():
        if (a, b) in fp:
            continue
        ra, rb = root(a), root(b)
        if ra is None or rb is None:
            miss += 1
            continue
        add.append(f'CX{len(add)} {ra} {rb} {x:.6g}')
        addc += x
    noground = []
    for n, x in rg.items():
        if n not in fg and n not in G and root(n):
            noground.append(f'CGX{len(noground)} {root(n)} VSS {x:.6g}')
    L = L[:end] + add + noground + L[end:]
    info = dict(ground_c_before_pf=round(before * 1e12, 3), ground_c_after_pf=round(after * 1e12, 3),
                ground_c_ref_pf=round(sum(rg.values()) * 1e12, 3), coupling_pairs_added=len(add),
                coupling_added_pf=round(addc * 1e12, 3), coupling_pairs_without_node=miss, nets_given_ground_cap=len(noground))
    return '\n'.join(L) + '\n', info


def netstats(text):
    rnets, nets, rtot, nres = set(), set(), 0., 0
    gc, cc = defaultdict(float), 0.
    for line in joined(text):
        if not line or line[0] in '*.+':
            continue
        t = line.split()
        k = line[0].upper()
        if k == 'R' and len(t) > 3:
            nres += 1
            rtot += val(t[3])
            for n in t[1:3]:
                rnets.add(base(n))
        if k == 'X' and len(t) > 4:
            for n in t[1:5]:
                nets.add(base(n))
        if k == 'C' and len(t) > 3:
            a, b = base(t[1]), base(t[2])
            if b in G or a in G or 'FLOATING' in line:
                gc[a if a not in G else b] += val(t[3])
            elif a != b:
                cc += val(t[3])
    sig = {n for n in nets if n not in G and n not in ('VDD',)}
    return dict(signal_nets=len(sig), nets_with_r=len(rnets & sig), resistors=nres, r_total_ohm=round(rtot, 1),
                coupling_pf=round(cc * 1e12, 3)), gc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('block')
    ap.add_argument('--gds')
    ap.add_argument('--tol', default='0')
    ap.add_argument('--out')
    a = ap.parse_args()
    top = f'pt_{a.block}'
    gds = Path(a.gds or HERE / 'generated' / f'{a.block}.gds').resolve()
    out = Path(a.out or HERE.parents[3] / 'scratch' / 'converters' / f'rc_{a.block}')
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copy(gds, out / 'in.gds')
    common = f"""crashbackups stop
drc off
gds read in.gds
load {top}
flatten {top}_flat
load {top}_flat
select top cell
extract do capacitance
extract do coupling
"""
    (out / 'conly.tcl').write_text(common + f"""extract no resistance
extract all
ext2spice lvs
ext2spice hierarchy off
ext2spice format ngspice
ext2spice cthresh 0
ext2spice subcircuit top on
ext2spice -o conly.spice
quit -noprompt
""")
    (out / 'rc.tcl').write_text(common + f"""extract do resistance
extract all
ext2sim labels on
ext2sim
extresist tolerance {a.tol}
extresist ignore VSS
extresist ignore VDD
extresist ignore VSUBS
extresist simplify off
extresist all
ext2spice lvs
ext2spice hierarchy off
ext2spice format ngspice
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist on
ext2spice subcircuit top on
ext2spice -o full.rc.spice
quit -noprompt
""")
    rc = '/foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc'
    ck.docker(ck.ANALOG_IMAGE, out, f'export PATH=/foss/tools/bin:$PATH; mkdir -p c r; cp in.gds conly.tcl c/; '
              f'cp in.gds rc.tcl r/; cd /work/c && magic -dnull -noconsole -rcfile {rc} conly.tcl > ../conly.log 2>&1; '
              f'cd /work/r && magic -dnull -noconsole -rcfile {rc} rc.tcl > ../rc.log 2>&1; '
              'cp /work/c/conly.spice /work/r/full.rc.spice /work/ 2>/dev/null; true', timeout=4 * 3600)
    for f in ('conly.spice', 'full.rc.spice'):
        assert (out / f).exists(), f'{f} missing, see {out}/*.log'
    conly, full = (out / 'conly.spice').read_text(), (out / 'full.rc.spice').read_text()
    fixed, info = fixcap(conly, full)
    # subckt name: the flattened cell is <top>_flat; publish under <top> with the same port order as the C-only netlist
    fixed = re.sub(rf'\b{top}_flat\b', top, fixed)
    ports_ref = next((line.split()[2:] for line in joined((HERE / 'generated' / f'{a.block}.ext.spice').read_text())
                      if line.lower().startswith('.subckt')), [])
    L = joined(fixed)
    k = next(i for i, line in enumerate(L) if line.lower().startswith('.subckt'))
    ports_full = L[k].split()[2:]
    if sorted(ports_full) == sorted(ports_ref):      # same names: state them in the published port order
        L[k] = f'.subckt {top} ' + ' '.join(ports_ref)
    fixed = '\n'.join(L) + '\n'
    (out / f'{top}.rc.spice').write_text(fixed)
    st, gc_fix = netstats(fixed)
    _, gc_ref = netstats(re.sub(rf'\b{top}_flat\b', top, conly))
    errs = []
    for n, x in gc_ref.items():
        if x > 1e-15:
            errs.append((abs(gc_fix.get(n, 0.) - x) / x, n))
    errs.sort(reverse=True)
    rnets = set()
    for line in joined(fixed):
        if line.startswith('R'):
            t = line.split()
            rnets |= {base(t[1]), base(t[2])}
    routed = [n for n, c in gc_ref.items() if c > 2e-15 and n not in ('VDD', 'VSS', 'VSUBS')]
    miss = sorted(((round(gc_ref[n] * 1e15, 1), n) for n in routed if n not in rnets), reverse=True)
    rec = dict(block=a.block, gds_sha256=ck.sha256(gds), tolerance=a.tol, image=ck.ANALOG_IMAGE, fixcap=info, stats=st,
               coverage_all_nets=round(st['nets_with_r'] / max(1, st['signal_nets']), 3),
               coverage_routed=dict(definition='nets with > 2 fF C-only ground C, supplies excluded', nets=len(routed),
                                    with_r=len(routed) - len(miss), fraction=round(1 - len(miss) / max(1, len(routed)), 3),
                                    without_r=miss[:30]),
               ground_c_check=dict(nets=len(errs), max_rel_err=round(errs[0][0], 4) if errs else None,
                                   worst=[(n, round(e, 4)) for e, n in errs[:5]]),
               ports_match_ext=sorted(ports_full) == sorted(ports_ref), extracted_port_order=ports_full,
               not_covered='VDD/VSS/VSUBS resistance (extresist ignore): supplies are ideal in the benches')
    (out / 'rcext.json').write_text(json.dumps(rec, indent=1) + '\n')
    for f in list(out.glob('c')) + list(out.glob('r')):
        shutil.rmtree(f, ignore_errors=True)
    print(json.dumps(rec)[:1500])


if __name__ == '__main__':
    main()
