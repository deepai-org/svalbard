"""pt_slicer r2: compact StrongARM sampler bank (hand-placed rows, wrx_compact row compiler).

Why: the r1 bank (netlists.py generic gencell layout) passes 3.24 Gb/s quarter rate as a schematic at
ss/22 C/3.15 V but fails extracted (18/33 errors at 3.24 Gb/s, 1/34 at 1.92 Gb/s).  Probed at ss: the
output nodes 2oa/3ob carry ~45 fF of routing each and the shared tail header drops vdd_sa to ~2.87 V,
so the integration phase reaches the NMOS latch threshold only ~450 ps after the clock, after the
next bit has arrived (UI 309 ps at 3.24 Gb/s).

Topology is unchanged from r1 (same function, ports, trims, enable behaviour), sizes as r1 except
the tail (8 x 4 um = 32 um, as r1) is split around the centre and each sampler has its own header:
  ws_sa  one sampler: header PMOS (ENB, 3 x 8 um) -> local VSA rail -> clocked PMOS tail (CK) ->
         PMOS input pair (INP/INN, 3 x 8 um) -> PMOS cross pair (2 x 8 um) on 2oa/3ob, NMOS cross pair
         (2 x 4 um), NMOS resets on 1pa/4pb/2oa/3ob (4 um, gate CK), 2+2 trim diffusion capacitors
         (0.5/1 um NMOS to floating drains), NOR SR latch, Q = NOR(qb, ENB) -> inv -> inv.
         CK is the opposite ring phase CKP(k+4): reset while high, evaluate while low.
  ws_ctl ENB = !slicer_en; QCK = !NAND(CKP0, slicer_en).
Top: 8 x ws_sa + ws_ctl, assembled with timing's layout_engine macro placer.

    python3 slicer_compact.py cells     # build/check the cells (DRC, extraction, LVS)
    python3 slicer_compact.py top       # assemble pt_slicer -> generated/slicer.{mag,gds,ext.spice}
"""
from pathlib import Path
import json
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE.parent / 'timing'))   # append: timing/evidence.py must not shadow wired_rx/evidence.py
sys.path.insert(0, str(HERE))
import wrx_compact as compact                     # noqa: E402
import layout_engine as le                        # noqa: E402
import fastcells as fc                            # noqa: E402

C, BRK, fet = fc.C, fc.BRK, fc.fet
FAST = HERE / 'generated' / 'fast'
SCRATCH = HERE.parents[3] / 'scratch' / 'wired_rx' / 'slicer_compact'


class FixedRow(compact.Row):
    """Row with explicit gap-track indices (track_index: net -> index) instead of greedy sharing, so the
    poly-contact constraints of the dense StrongARM columns can be met."""
    def build(self):
        cols = self.cols
        x0 = [0.6 + i * compact.PITCH / 2 for i in range(len(cols))]
        self._build(x0)
        spots = set(self.spots)
        x = [0.6]
        for i in range(1, len(cols)):
            a, b = cols[i - 1]['k'], cols[i]['k']
            if a == 'g' and b == 'g':
                dx = 0.52
            elif a == 'c' and b == 'c':
                dx = 0.65
            elif (i in spots and b == 'c') or (i - 1 in spots and a == 'c'):
                dx = 0.65
            else:
                dx = 0.44
            x.append(x[-1] + dx)
        self.cmds = []
        return self._build(x)


def c(n, p):
    return dict(k='c', n=n, p=p)


def g(netn, netp, wn=2, wp=4):
    d = dict(k='g', n=netn is not None, p=netp is not None, wn=wn, wp=wp)
    if netn and netp and netn == netp:
        d['net'] = netn
    else:
        d['net'] = netn or netp
        if netn:
            d['netn'] = netn
        if netp:
            d['netp'] = netp
    return d


WP_IN, WP_LAT, WN_LAT, WN_RST, WP_TAIL, WP_HDR, NHDR = 8, 8, 4, 4, 4, 8, 6


def sa():
    """One StrongARM sampler (see module doc).  Rail_p is the local header rail VSA."""
    cols = [
        # r3 (MT-01, 2026-11-10): third trim bit per side on its own N island at each end of the core
        # (TP2 at the 1pa end, TN2 at the 4pb end, mirror positions), and a 0.5 um gate on 2oa that
        # balances the +0.70 fF the extraction showed on 3ob
        c('t2p', '-'), g('TP2', None, 2), c('1pa', '-'), BRK,
        c('VSS', '-'), g('2oa', None, 0.5), c('VSS', '-'), BRK,
        c('VSS', '1pa'), g('3ob', '3ob', 4, WP_LAT), c('2oa', '2oa'),
        g('3ob', '3ob', 4, WP_LAT), c('VSS', '1pa'),
        g('CK', 'INP', WN_RST, WP_IN), c('1pa', 'x'), g('TP0', 'INP', 0.5, WP_IN), c('t0p', '1pa'),
        g(None, 'INP', 2, WP_IN), c('t1p', 'x'), g('TP1', 'CK', 1, WP_TAIL), c('1pa', 'VSA'),
        g(None, 'CK', 2, WP_TAIL), c('VSS', 'x'), g('CK', 'CK', 2, WP_TAIL), c('2oa', 'VSA'),
        g('CK', 'CK', 2, WP_TAIL), c('VSS', 'x'), g('CK', 'CK', 2, WP_TAIL), c('3ob', 'VSA'),
        g('CK', 'CK', 2, WP_TAIL), c('VSS', 'x'), g(None, 'CK', 2, WP_TAIL), c('4pb', 'VSA'),
        g('TN1', 'CK', 1, WP_TAIL), c('t1n', 'x'), g(None, 'INN', 2, WP_IN), c('t0n', '4pb'),
        g('TN0', 'INN', 0.5, WP_IN), c('4pb', 'x'), g('CK', 'INN', WN_RST, WP_IN), c('VSS', '4pb'),
        g('2oa', '2oa', 4, WP_LAT), c('3ob', '3ob'), g('2oa', '2oa', 4, WP_LAT), c('VSS', '4pb'),
        BRK, c('4pb', '-'), g('TN2', None, 2), c('t2n', '-'),
        BRK,
        # per-sampler header: VDD -> VSA (gate ENB)
        c('-', 'VDD'), g(None, 'ENB', 2, WP_HDR), c('-', 'VSA'), g(None, 'ENB', 2, WP_HDR), c('-', 'VDD'),
        g(None, 'ENB', 2, WP_HDR), c('-', 'VSA'), g(None, 'ENB', 2, WP_HDR), c('-', 'VDD'),
        g(None, 'ENB', 2, WP_HDR), c('-', 'VSA'), g(None, 'ENB', 2, WP_HDR), c('-', 'VDD'),
    ]
    net = []
    # P side
    net += [fet('pl1', '2oa', '3ob', '1pa', 'VDD', 8, 'p'), fet('pl2', '2oa', '3ob', '1pa', 'VDD', 8, 'p'),
            fet('pi1', '1pa', 'INP', 'x', 'VDD', 8, 'p'), fet('pi2', '1pa', 'INP', 'x', 'VDD', 8, 'p'),
            fet('pi3', '1pa', 'INP', 'x', 'VDD', 8, 'p'),
            fet('pi4', '4pb', 'INN', 'x', 'VDD', 8, 'p'), fet('pi5', '4pb', 'INN', 'x', 'VDD', 8, 'p'),
            fet('pi6', '4pb', 'INN', 'x', 'VDD', 8, 'p'),
            fet('pr1', '3ob', '2oa', '4pb', 'VDD', 8, 'p'), fet('pr2', '3ob', '2oa', '4pb', 'VDD', 8, 'p')]
    net += [fet(f'pt{k}', 'x', 'CK', 'VSA', 'VDD', WP_TAIL, 'p') for k in range(8)]
    net += [fet(f'ph{k}', 'VSA', 'ENB', 'VDD', 'VDD', WP_HDR, 'p') for k in range(NHDR)]
    # N side
    net += [fet('nl1', '2oa', '3ob', 'VSS', 'VSS', 4), fet('nl2', '2oa', '3ob', 'VSS', 'VSS', 4),
            fet('nl3', '3ob', '2oa', 'VSS', 'VSS', 4), fet('nl4', '3ob', '2oa', 'VSS', 'VSS', 4),
            fet('nr1', '1pa', 'CK', 'VSS', 'VSS', WN_RST), fet('nr2', '4pb', 'CK', 'VSS', 'VSS', WN_RST),
            fet('nr3', '2oa', 'CK', 'VSS', 'VSS', 2), fet('nr4', '2oa', 'CK', 'VSS', 'VSS', 2),
            fet('nr5', '3ob', 'CK', 'VSS', 'VSS', 2), fet('nr6', '3ob', 'CK', 'VSS', 'VSS', 2),
            fet('tp0', 't0p', 'TP0', '1pa', 'VSS', 0.5), fet('tp1', 't1p', 'TP1', '1pa', 'VSS', 1),
            fet('tn0', 't0n', 'TN0', '4pb', 'VSS', 0.5), fet('tn1', 't1n', 'TN1', '4pb', 'VSS', 1),
            fet('tp2', 't2p', 'TP2', '1pa', 'VSS', 2), fet('tn2', '4pb', 'TN2', 't2n', 'VSS', 2),
            fet('cb2oa', 'VSS', '2oa', 'VSS', 'VSS', 0.5)]
    # NOR SR latch (lq/lqb: SPICE is case-insensitive, so no net may differ from a port only in case),
    # enable gate, output buffer (VDD/VSS)
    S = C('VSS', 'VDD', same=False)

    def nor2(a, b, y, pre, wn=2, wp=8):
        return ([S, g(a, a, wn, wp), dict(k='c', n=y, p=None), g(b, b, wn, wp), C('VSS', y, same=False)],
                [fet(pre + 'n1', y, a, 'VSS', 'VSS', wn), fet(pre + 'n2', y, b, 'VSS', 'VSS', wn),
                 fet(pre + 'p1', pre + 'm', a, 'VDD', 'VDD', wp, 'p'), fet(pre + 'p2', y, b, pre + 'm', 'VDD', wp, 'p')])

    def inv(a, y, pre, wn, wp):
        return [S, g(a, a, wn, wp), C(y)], [fet(pre + 'n', y, a, 'VSS', 'VSS', wn), fet(pre + 'p', y, a, 'VDD', 'VDD', wp, 'p')]

    def inv3(a, y, pre, wn, wp):
        """three-finger output inverter: holds the long output route low against clock/ENB coupling
        (r2 first cut, 1 finger, let 0.24 V glitches through with the bank disabled)"""
        return ([S, g(a, a, wn, wp), C(y), g(a, a, wn, wp), S, g(a, a, wn, wp), C(y)],
                [fet(pre + f'n{k}', y, a, 'VSS', 'VSS', wn) for k in range(3)] +
                [fet(pre + f'p{k}', y, a, 'VDD', 'VDD', wp, 'p') for k in range(3)])

    for cc, nn in (nor2('2oa', 'lqb', 'lq', 'la', 4, 4), nor2('3ob', 'lq', 'lqb', 'lb', 4, 4),
                   nor2('lqb', 'ENB', 'o1', 'lo', 2, 4),
                   nor2('lq', 'ENB', 'o1d', 'ld', 2, 4),     # r3: dummy, balances the SR latch load (MT-01)
                   inv('o1', 'o2', 'b1', 4, 8), inv3('o2', 'Q', 'b2', 4, 8)):
        cols += [BRK] + cc
        net += nn
    ports = ['CK', 'INP', 'INN', 'TP0', 'TP1', 'TP2', 'TN0', 'TN1', 'TN2', 'ENB', 'Q']
    row = FixedRow('ws_sa', cols, rail_p='VSA', tap_p='VDD', ports=ports, wn=2, wp=8)
    # explicit tracks: split gate columns need the N net below the P net, and each gate's track must
    # clear the drain risers of a neighbouring contact column (gate nets between N and P drain tracks)
    order = ['t0p', 't1p', 't0n', 't1n', '2oa', '3ob', 'lq', 'lqb', 'o1', 'o2', 'TP0', 'TP1', 'TN0', 'TN1', 'CK',
             'INP', 'INN', 'ENB', 'Q', '1pa', '4pb', 'x', 't2p', 't2n', 'TP2', 'TN2', 'o1d']
    row._track_index = {n: k for k, n in enumerate(order)}
    return row, ports + ['VDD', 'VSS'], net


def ctl():
    S = C('VSS', 'VDD', same=False)
    cols = [S, g('EN', 'EN', 4, 8), C('ENB'), BRK,   # ENB drives 8 x (6 header fingers + NOR)
            S, g('CKP0', 'CKP0', 4, 4), dict(k='c', n=None, p='qb'), g('EN', 'EN', 4, 4), C('qb', 'VDD', same=False), BRK,
            S, g('qb', 'qb', 4, 8), C('QCK')]
    net = [fet('en', 'ENB', 'EN', 'VSS', 'VSS', 4), fet('ep', 'ENB', 'EN', 'VDD', 'VDD', 8, 'p'),
           fet('qn1', 'qm', 'CKP0', 'VSS', 'VSS', 4), fet('qn2', 'qb', 'EN', 'qm', 'VSS', 4),
           fet('qp1', 'qb', 'CKP0', 'VDD', 'VDD', 4, 'p'), fet('qp2', 'qb', 'EN', 'VDD', 'VDD', 4, 'p'),
           fet('on', 'QCK', 'qb', 'VSS', 'VSS', 4), fet('op', 'QCK', 'qb', 'VDD', 'VDD', 8, 'p')]
    ports = ['EN', 'CKP0', 'ENB', 'QCK']
    return compact.Row('ws_ctl', cols, ports=ports, wn=2, wp=4), ports + ['VDD', 'VSS'], net


CELLS = dict(ws_sa=sa, ws_ctl=ctl)


def subckt(name, ports, net):
    nets = {t for l in net for t in l.split()[1:5]} | set(ports)
    low = {}
    for n in nets:
        if low.setdefault(n.lower(), n) != n:
            raise ValueError(f'{name}: nets {n} and {low[n.lower()]} differ only in case')
    return f'.subckt {name} {" ".join(ports)}\n' + '\n'.join(net) + f'\n.ends {name}\n'


def build_cell(name):
    row, ports, net = CELLS[name]()
    row.build()
    work = SCRATCH / 'cells' / name
    if work.exists():
        shutil.rmtree(work)
    row.emit(work, ports)
    sch = subckt(name, ports, net)
    res = compact.check(work, name, sch)
    FAST.mkdir(parents=True, exist_ok=True)
    for suf in ('.mag', '.ext.spice', '.lvs.spice', '.gds'):
        f = work / f'{name}{suf}'
        if f.exists():
            shutil.copy(f, FAST / f'{name}{suf}')
    (FAST / f'{name}.spice').write_text('* generated by slicer_compact.py (intended netlist)\n' + sch)
    rails = {}
    for key, (net_, yy) in row.rails.items():
        if net_ in ports:            # VSA (ws_sa local header rail) is internal
            rails.setdefault(net_, [0.3, yy])
    (FAST / f'{name}.pins.json').write_text(json.dumps(dict(ports=ports, pins={k: list(v) for k, v in row.pins.items()},
                                                           rails=rails, bbox=[0.0, 0.0, round(row.width, 3), round(row.top, 3)]),
                                                      indent=1))
    res.update(size_um=[round(row.width, 2), round(row.top, 2)], area_um2=round(row.width * row.top, 1), devices=len(net))
    (FAST / f'{name}-check.json').write_text(json.dumps(res, indent=1, default=str))
    print(name, json.dumps({k: (v if k != 'lvs' else v.get('unique_match')) for k, v in res.items()}, default=str), flush=True)
    return res


# ----------------------------------------------------------------------------------------- top
# r3: one trim code per sampler (r2 shared one code between the two samplers of a phase pair), 3+3 bits
GROUPS = ('d0', 'e0', 'd1', 'e1', 'd2', 'e2', 'd3', 'e3')
TRIM_BITS = ('p0', 'p1', 'p2', 'n0', 'n1', 'n2')
TRIMS = [f'trim_{s}_{b}' for s in GROUPS for b in TRIM_BITS]
TOP_PORTS = ['VDD_WIRE_SW', 'VSS', 'slicer_en', 'SL_P', 'SL_N'] + [f'CKP{k}' for k in range(8)] + \
            ['QCK', 'D0', 'E0', 'D1', 'E1', 'D2', 'E2', 'D3', 'E3'] + TRIMS
PLAN = [('SD0', 0, 'D0', 'd0'), ('SE0', 1, 'E0', 'e0'), ('SD1', 2, 'D1', 'd1'), ('SE1', 3, 'E1', 'e1'),
        ('SD2', 4, 'D2', 'd2'), ('SE2', 5, 'E2', 'e2'), ('SD3', 6, 'D3', 'd3'), ('SE3', 7, 'E3', 'e3')]


def top_instances():
    out = [('XCTL', 'ws_ctl', ['slicer_en', 'CKP0', 'enb', 'QCK', 'VDD_WIRE_SW', 'VSS'])]
    for inst, k, q, t in PLAN:
        out.append((f'X{inst}', 'ws_sa', [f'CKP{(k + 4) % 8}', 'SL_P', 'SL_N', f'trim_{t}_p0', f'trim_{t}_p1',
                                          f'trim_{t}_p2', f'trim_{t}_n0', f'trim_{t}_n1', f'trim_{t}_n2', 'enb', q,
                                          'VDD_WIRE_SW', 'VSS']))
    return out


def top_netlist(include_cells=True):
    txt = ''
    if include_cells:
        for n in CELLS:
            txt += subckt(n, *CELLS[n]()[1:])
    txt += f'.subckt pt_slicer {" ".join(TOP_PORTS)}\n'
    for inst, cell, conns in top_instances():
        txt += f'{inst} {" ".join(conns)} {cell}\n'
    return txt + '.ends pt_slicer\n'


def flat_lines():
    """Flattened intended device lines of pt_slicer (for netlists.py / slicer.spice)."""
    lines = []
    defs = {n: CELLS[n]() for n in CELLS}
    for inst, cell, conns in top_instances():
        ports, net = defs[cell][1], defs[cell][2]
        m = dict(zip(ports, conns))
        for line in net:
            tok = line.split()
            name, nodes, rest = tok[0], tok[1:5], tok[5:]
            nodes = [m.get(x, f'{inst[1:].lower()}_{x}') for x in nodes]
            lines.append(' '.join([f'{name}_{inst[1:]}'] + nodes + rest))
    return lines


def build_top():
    import netlist as tn
    for n in CELLS:
        tn.MACROS[n] = json.loads((FAST / f'{n}.pins.json').read_text())['ports']
    le.FAST = FAST
    work = SCRATCH / 'top'
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    (work / 'top.spice').write_text(top_netlist(include_cells=False))
    ports, devices = tn.load(work / 'top.spice', 'pt_slicer')
    rows = [['SD0', 'SE0'], ['SD1', 'SE1'], ['SD2', 'SE2'], ['SD3', 'SE3'], ['CTL']]
    rep = le.generate(work, 'pt_slicer', ports, devices, rows=rows, max_row_width=400.0,
                      power_nets=('VDD_WIRE_SW', 'VSS'))
    defs = ''.join((FAST / f'{m}.spice').read_text() for m in CELLS)
    top_sp = tn.flat_spice(ports, devices, 'pt_slicer')
    ant = le.ad.spice_lines(rep.get('antenna_diodes', []))   # layout_engine antenna diodes -> LVS reference
    if ant:
        k = top_sp.rstrip().rfind('.ends')
        top_sp = top_sp[:k] + '\n'.join(ant) + '\n' + top_sp[k:]
    (work / 'schematic.spice').write_text(defs + top_sp)
    lvs = le.netgen_lvs(work, 'pt_slicer.lvs.spice', 'pt_slicer', 'schematic.spice', 'pt_slicer')
    import wrx_flow as wf
    # Published extraction is flat (hierarchy off, C to substrate and coupling, cthresh 0): the family's
    # parse_spice/benches (and the CDR closed-loop runs) expect transistors at the top level.
    (work / 'flat.tcl').write_text('\n'.join(['crashbackups stop', 'load pt_slicer', 'select top cell', 'extract all',
                                              'ext2spice default', 'ext2spice format ngspice', 'ext2spice scale off',
                                              'ext2spice subcircuit top on', 'ext2spice hierarchy off', 'ext2spice cthresh 0',
                                              'ext2spice rthresh 0', 'ext2spice -o pt_slicer.flat.spice',
                                              'quit -noprompt']) + '\n')
    le.docker_magic(work, 'flat.tcl')
    gen = HERE / 'generated'
    shutil.copy(work / 'pt_slicer.flat.spice', gen / 'slicer.ext.spice')
    for suf in ('.mag', '.lvs.spice'):
        f = work / f'pt_slicer{suf}'
        if f.exists():
            shutil.copy(f, gen / f'slicer{suf}')
    try:
        gx = wf.export_gds(work, 'pt_slicer', 0)
        shutil.copy(work / 'pt_slicer.gds', gen / 'slicer.gds')
        from gds_uniquify import publish_checked   # analog/ (on sys.path via layout_engine)
        gx['klayout_precheck'] = publish_checked(gen / 'slicer.gds', 'slicer', 'pt_slicer')
    except Exception as exc:
        gx = dict(error=repr(exc)[:300])
    res = dict(revision='r2 compact', drc_errors=le.drc_errors(rep['drc_count_raw']), lvs=lvs,
               layout={k: v for k, v in rep.items() if k != 'cmds'}, gds_export=gx,
               devices=sum(len(CELLS[c_]()[2]) for _, c_, _ in top_instances()))
    (gen / 'slicer-layout.json').write_text(json.dumps(res, indent=1, default=str) + '\n')
    print(json.dumps({k: v for k, v in res.items() if k != 'layout'}, default=str)[:1500])
    return res


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'cells'
    if what == 'cells':
        for n in sys.argv[2:] or CELLS:
            build_cell(n)
    elif what == 'top':
        build_top()
