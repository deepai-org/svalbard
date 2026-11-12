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
        x = [0.6 + (0.9 * len(getattr(self, 'left_ports', ())) + 0.9 if getattr(self, 'left_ports', ()) else 0.0)]
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


# r7 (2026-11-11, SLI7): WN_RST (1pa/4pb resets) 4 -> 2 um (less C on 1pa/4pb) and WP_TAIL 4 -> 5 um (8 fingers):
# r7 layout at the pessimistic values (ss/32/3.15, Rg 200 ohm*W/10um, +25 % device C, +15 % wiring C) failed 750 MHz
# on the ws_sae samplers (5/51, 5/59); tail x1.25 -> 0/51, 0/59.  Cost: +8 um of tail gate on each CKPk
# r7f (round 3, full pessimistic incl. junction/overlap C, ss 750 MHz 15/51 errors): the time goes to the StrongARM
# decision (2oa crosses 1.575 V 555 ps after CK in a 667 ps window) with VSA drooping through the 6 x 8 um header.
# Tested on the extraction: tail x1.4 7/51, SR-PMOS x2 21/51 (worse), NMOS cross x1.5 15/51, header x2 1/51,
# header x2 + tail x1.2 0/51 0/59 -> NHDR 6 -> 12 (no clock load), WP_TAIL 5 -> 6 (+8 um per CKPk)
WP_IN, WP_LAT, WN_LAT, WN_RST, WP_TAIL, WP_HDR, NHDR = 8, 8, 4, 2, 5, 8, 6   # published r7 (sl6); r7g candidate (6, 12) NOT adopted, see README
# r4b (2026-11-10, from the r4 extracted tt trim sweep, scratch/wired_rx/r4slicer/trim_tt_*): offset per um of
# switched width ~22.5 mV/um, and the bit-0 pair carried +2.25 mV of layout asymmetry (cell-edge island), so the
# deltas are set for ~1.6/3.2/6.4 mV (r4: 0.1/0.2/0.4 um gave 4.5/3.9/8.4 mV, max gap between fine codes 3.9 mV;
# r4b: -0.02/0.185/0.345 um gave 2.1-2.7/3.3-3.9/7.2-7.5 mV, max gap 2.7 mV; slope ~24 mV/um, bit-0 offset ~+2.5 mV).
# Coarse widths x1.1 (r4: p7 reached only -45.6 mV on e1 against the +/-50 mV target): LSB 9.6-10.5 mV < fine span.
WF_BASE, WF_DELTA = 0.5, (-0.065, 0.155, 0.26)   # r7: f2 0.28 -> 0.26 (ff d1 gap 2.2 mV sat below f2)   # fine trim pairs: 1pa side W, 4pb side W + delta (um)
# r6d (2026-11-11, from the r6c extracted tt 16-code sweep, 0.2 mV resolution): bit weights (f0 f1 f2 f3) were
# 1.4-2.0 / 3.6-4.0 / 7.0-7.8 / 0.6-1.6 mV and all-on codes fall 2.0-2.4 mV short of superposition, so the largest
# gaps (2.0-2.2 mV on d1/d2/d3) sat below the f2 code and below f1: f1/f2 deltas 0.17/0.30 -> 0.155/0.28,
# f3 delta -0.09 -> -0.075 (r4c: 0.17/0.30 with three bits)
# r6 (2026-11-11): fourth fine bit TF3 (target ~1 mV, the new LSB; r4c max gap 2.0-2.4 mV on e0..e3) as an outer
# unequal pair (1pa end / 4pb end, like TF0), base WF3_BASE on 1pa and WF3_BASE + WF3_DELTA on 4pb.
WF3_BASE, WF3_DELTA = 0.6, -0.075
# r7: ws_sa only.  The d-sampler f3 weight FALLS as the delta goes more negative (a base asymmetry dominates):
# -0.075 (r6) 0.6-0.8 mV, -0.09 (r7c) 0.0-0.5 mV at ff -> ff gaps 2.2 mV and coarse seam 2.36 mV; -0.055 (r7d)
WF3_DELTA_D = -0.055
# r6: antenna (KLayout ANT.16_i_ANT.3 = M2 perimeter, 32 on r4c, ratio 434/474): TP0/TN0 carried only a
# 0.55 x 0.28 um gate under ~60 um of in-cell M2; each gets a bare N+ contact column (diode, ~0.7 um^2); in the wider
# ws_sae (131 um) the fine pairs TF0/TF1/TF3 reached 434-539, so TF0..TF3 get one too
# r6 IX-10: auxiliary offset pair on the edge samplers only (ws_sae): PMOS pair on 1pa/4pb sharing the clocked
# tail node x, gates from VTH_A or VTH_B (pt_vthdac) through TGs, or pulled to VDD (off: no current).
NDEC = 8          # r6c ws_aux decap fingers per AX line (4 um each)
WA_AUX = 6.0     # r6 sizing (schematic single cell, CM 0.8 V): +/-1.6 V DAC -> +/-368 mV (tt) / 381 mV (ss), 0.27 V/V at 0
WT = (0.55, 1.1, 2.2)                              # coarse trim widths TP/TN 0..2 (r3/r4: 0.5/1/2 um)
# r7: per side (ss range r6: p7 -45.4..-50.6, n7f15 +43.1..+51.3 mV about a ~-3 mV systematic fine-code-0 offset)
# r7b extracted ss: p7 -49.2..-56.6, n7f15 +56.0..+61.4 (fine code 0 now ~0 mV): p x1.07, n x0.95 (r7c)
WTP = (0.665, 1.33, 2.665)
WTN = (0.635, 1.275, 2.55)


def sa(aux=False):
    """One StrongARM sampler (see module doc).  Rail_p is the local header rail VSA.
    aux (r6, IX-10): edge-sampler variant ws_sae with the auxiliary threshold pair + its select/TG logic."""
    d3 = WF3_DELTA if aux else WF3_DELTA_D
    cols = [
        # r6: fourth fine bit (outer pair, 1pa end)
        c('f3a', '-'), g('TF3', None, WF3_BASE), c('1pa', '-'), BRK,
        # r3 (MT-01, 2026-11-10): third trim bit per side on its own N island at each end of the core
        # (TP2 at the 1pa end, TN2 at the 4pb end, mirror positions), and a 0.5 um gate on 2oa that
        # balances the +0.70 fF the extraction showed on 3ob
        # r4 (2026-11-10, <= 2 mV trim step): three fine bits TF0..2, each an UNEQUAL pair of switched caps, the
        # base width on 1pa (left island) and base + delta on 4pb (right island, mirror position), so one bit
        # moves the offset by the cap DIFFERENCE (delta 0.1/0.2/0.4 um ~ 2/4/8 mV) with devices >= 0.5 um.
        c('f0a', '-'), g('TF0', None, WF_BASE), c('1pa', '-'), g('TF1', None, WF_BASE), c('f1a', '-'), BRK,
        c('f2a', '-'), g('TF2', None, WF_BASE), c('1pa', '-'), g('TP2', None, WTP[2]), c('t2p', '-'), BRK,
        c('VSS', '-'), g('2oa', None, 0.5), c('VSS', '-'), BRK,
        # r6 antenna: bare N+ diffusion (N+/Psub diode, no device) on TP0 and TN0
        c('TP0', '-'), BRK, c('TN0', '-'), BRK, c('TF0', '-'), BRK, c('TF1', '-'), BRK, c('TF2', '-'), BRK, c('TF3', '-'), BRK,
        c('VSS', '1pa'), g('3ob', '3ob', 4, WP_LAT), c('2oa', '2oa'),
        g('3ob', '3ob', 4, WP_LAT), c('VSS', '1pa'),
        g('CK', 'INP', WN_RST, WP_IN), c('1pa', 'x'), g('TP0', 'INP', WTP[0], WP_IN), c('t0p', '1pa'),
        g(None, 'INP', 2, WP_IN), c('t1p', 'x'), g('TP1', 'CK', WTP[1], WP_TAIL), c('1pa', 'VSA'),
        g(None, 'CK', 2, WP_TAIL), c('VSS', 'x'), g('CK', 'CK', 2, WP_TAIL), c('2oa', 'VSA'),
        g('CK', 'CK', 2, WP_TAIL), c('VSS', 'x'), g('CK', 'CK', 2, WP_TAIL), c('3ob', 'VSA'),
        g('CK', 'CK', 2, WP_TAIL), c('VSS', 'x'), g(None, 'CK', 2, WP_TAIL), c('4pb', 'VSA'),
        g('TN1', 'CK', WTN[1], WP_TAIL), c('t1n', 'x'), g(None, 'INN', 2, WP_IN), c('t0n', '4pb'),
        g('TN0', 'INN', WTN[0], WP_IN), c('4pb', 'x'), g('CK', 'INN', WN_RST, WP_IN), c('VSS', '4pb'),
        g('2oa', '2oa', 4, WP_LAT), c('3ob', '3ob'), g('2oa', '2oa', 4, WP_LAT), c('VSS', '4pb'),
        BRK, c('t2n', '-'), g('TN2', None, WTN[2]), c('4pb', '-'), g('TF2', None, round(WF_BASE + WF_DELTA[2], 3)), c('f2b', '-'),
        BRK, c('f1b', '-'), g('TF1', None, round(WF_BASE + WF_DELTA[1], 3)), c('4pb', '-'), g('TF0', None, round(WF_BASE + WF_DELTA[0], 3)),
        c('f0b', '-'),
        BRK, c('4pb', '-'), g('TF3', None, round(WF3_BASE + d3, 3)), c('f3b', '-'),
        BRK,
        # per-sampler header: VDD -> VSA (gate ENB)
        c('-', 'VDD')] + sum(([g(None, 'ENB', 2, WP_HDR), c('-', 'VSA' if k % 2 == 0 else 'VDD')] for k in range(NHDR)), []) + [
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
            fet('tp0', 't0p', 'TP0', '1pa', 'VSS', WTP[0]), fet('tp1', 't1p', 'TP1', '1pa', 'VSS', WTP[1]),
            fet('tn0', 't0n', 'TN0', '4pb', 'VSS', WTN[0]), fet('tn1', 't1n', 'TN1', '4pb', 'VSS', WTN[1]),
            fet('tp2', 't2p', 'TP2', '1pa', 'VSS', WTP[2]), fet('tn2', '4pb', 'TN2', 't2n', 'VSS', WTN[2]),
            fet('cb2oa', 'VSS', '2oa', 'VSS', 'VSS', 0.5),
            fet('tfa3', 'f3a', 'TF3', '1pa', 'VSS', WF3_BASE), fet('tfb3', '4pb', 'TF3', 'f3b', 'VSS', round(WF3_BASE + d3, 3))]
    for k in range(3):    # r4 fine pairs (see the column list)
        net += [fet(f'tfa{k}', f'f{k}a', f'TF{k}', '1pa', 'VSS', WF_BASE),
                fet(f'tfb{k}', f'f{k}b', f'TF{k}', '4pb', 'VSS', round(WF_BASE + WF_DELTA[k], 3))]
    # NOR SR latch (lq/lqb: SPICE is case-insensitive, so no net may differ from a port only in case),
    # enable gate, output buffer (VDD/VSS)
    S = C('VSS', 'VDD', same=False)

    def nor2(a, b, y, pre, wn=2, wp=8, xa=False):
        # r7 (SLI7): xa = second 4 um NMOS finger on input a (SR latch set/reset from 2oa/3ob).  r6 ss/32/3.15 834 MHz:
        # the ws_sae latch never flipped (2oa/3ob peak 2.29-2.37 V for ~150 ps, lq only down to 0.66 V): 14/51 errors
        cc = [S, g(a, a, wn, wp), dict(k='c', n=y, p=None), g(b, b, wn, wp), C('VSS', y, same=False)]
        nn = [fet(pre + 'n1', y, a, 'VSS', 'VSS', wn), fet(pre + 'n2', y, b, 'VSS', 'VSS', wn),
              fet(pre + 'p1', pre + 'm', a, 'VDD', 'VDD', wp, 'p'), fet(pre + 'p2', y, b, pre + 'm', 'VDD', wp, 'p')]
        if xa:
            cc += [g(a, None, wn), c(y, '-')]
            nn.append(fet(pre + 'n3', y, a, 'VSS', 'VSS', wn))
        return cc, nn

    def inv(a, y, pre, wn, wp):
        return [S, g(a, a, wn, wp), C(y)], [fet(pre + 'n', y, a, 'VSS', 'VSS', wn), fet(pre + 'p', y, a, 'VDD', 'VDD', wp, 'p')]

    def inv3(a, y, pre, wn, wp):
        """three-finger output inverter: holds the long output route low against clock/ENB coupling
        (r2 first cut, 1 finger, let 0.24 V glitches through with the bank disabled)"""
        return ([S, g(a, a, wn, wp), C(y), g(a, a, wn, wp), S, g(a, a, wn, wp), C(y)],
                [fet(pre + f'n{k}', y, a, 'VSS', 'VSS', wn) for k in range(3)] +
                [fet(pre + f'p{k}', y, a, 'VDD', 'VDD', wp, 'p') for k in range(3)])

    for cc, nn in (nor2('2oa', 'lqb', 'lq', 'la', 4, 4, True), nor2('3ob', 'lq', 'lqb', 'lb', 4, 4, True),
                   nor2('lqb', 'ENB', 'o1', 'lo', 2, 4),
                   nor2('lq', 'ENB', 'o1d', 'ld', 2, 4),     # r3: dummy, balances the SR latch load (MT-01)
                   inv('o1', 'o2', 'b1', 4, 8), inv3('o2', 'Q', 'b2', 4, 8)):
        cols += [BRK] + cc
        net += nn
    if aux:
        # IX-10 aux pair (side a sees the N line, side b the P line: decision (INP-INN) > k*(VTP-VTN)) on the tail x,
        # placed right after the core's last 4pb column, so 1pa/4pb/x gain no track length.  The gates AXN/AXP come
        # from a ws_aux select cell (in the control row): r6 first cut had the select/TG logic in this cell, which
        # widened it 89 -> 136 um and grew the SL_P/SL_N wiring 306/287 -> 434/406 fF extracted
        # r6b: mirror-symmetric, one device at each end of the core sharing the core's outer 1pa / 4pb contact column
        # (r6a put both after the core with a new 1pa contact: +6 fF on 1pa only, e-sampler offsets -35..-40 mV)
        kk = next(i for i in range(len(cols) - 1) if cols[i].get('n') == 'VSS' and cols[i].get('p') == '4pb'
                  and cols[i + 1] is BRK and cols[i + 2].get('n') == 't2n')
        cols[kk + 1:kk + 1] = [g(None, 'AXP', 2, WA_AUX), c('-', 'x')]
        k0 = next(i for i in range(len(cols)) if cols[i].get('n') == 'VSS' and cols[i].get('p') == '1pa'
                  and cols[i - 1] is BRK)
        cols[k0:k0] = [c('-', 'x'), g(None, 'AXN', 2, WA_AUX)]
        net += [fet('pxa', '1pa', 'AXN', 'x', 'VDD', WA_AUX, 'p'), fet('pxb', '4pb', 'AXP', 'x', 'VDD', WA_AUX, 'p')]
    # r6: TF3 (and the IX-10 aux controls/lines, all static or quasi-static) between TF2 and ENB
    # r6c: AXN/AXP between the static TN1 / TN2 (r6b had them next to ENB/Q/CK: 17-28 fF from the sampler's own
    # clock onto AXN extracted, -136..-216 mV spread between e-samplers at one DAC code)
    ports = ['TP0', 'TP1', 'TP2', 'TF0', 'INP', 'INN', 'TF1', 'TN0', 'TN1'] + (['AXN', 'AXP'] if aux else []) + \
        ['TN2', 'TF2', 'TF3', 'Q', 'ENB', 'CK']   # r7: ENB pin between Q and CK (r6: Q/CK pins 0.9 um apart, parallel M3)
    row = FixedRow('ws_sae' if aux else 'ws_sa', cols, rail_p='VSA', tap_p='VDD', ports=ports, wn=2, wp=8)
    if aux:   # r7: ws_sae sits right of ws_sa in each row; INP/INN pins on its left edge, next to the SL trunk
        row.left_ports = ('INP', 'INN')         # (r6: SL_P/SL_N 362/338 fF extracted vs r4c 306/287)
    # explicit tracks: split gate columns need the N net below the P net, and each gate's track must
    # clear the drain risers of a neighbouring contact column (gate nets between N and P drain tracks)
    # r4 (MT-01): static TP0 / ENB tracks between the clock and INP/INN (r3: CK beside INP, ~6 fF per sampler
    # from each sampler clock onto SL_P only, 49 fF in total, ~0.3 fF onto SL_N)
    order = ['t0p', 't1p', 't0n', 't1n', '2oa', '3ob', 'lq', 'lqb', 'o1', 'o2', 'TP1', 'TN0', 'TN1', 'CK', 'TP0',
             'INP', 'INN', 'ENB', 'Q', '1pa', '4pb', 'x', 't2p', 't2n', 'TP2', 'TN2', 'o1d',
             'f0a', 'f1a', 'f2a', 'f0b', 'f1b', 'f2b', 'TF0', 'TF1', 'TF2', 'f3a', 'f3b', 'TF3']
    if aux:   # aux gates below 1pa/x/4pb (their poly-contact columns carry P risers from those tracks)
        k = order.index('1pa')
        order = order[:k] + ['AXN', 'AXP'] + order[k:]
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


def aux():
    """r6 IX-10 per-edge-sampler select (ws_aux, in the control row): SA1 -> VTH_B, SA0 & !SA1 -> VTH_A, 00 -> AXN/AXP
    pulled to VDD (aux pair off, no current).  TGs as separate N-only / P-only islands (a contact column with signal
    risers on both sides leaves no poly-contact spot): N gates on tracks above their contacts, P gates below."""
    S = C('VSS', 'VDD', same=False)

    def inv(a, y, pre, wn, wp):
        return [S, g(a, a, wn, wp), C(y)], [fet(pre + 'n', y, a, 'VSS', 'VSS', wn), fet(pre + 'p', y, a, 'VDD', 'VDD', wp, 'p')]

    def nor2(a, b, y, pre, wn=2, wp=8):
        return ([S, g(a, a, wn, wp), dict(k='c', n=y, p=None), g(b, b, wn, wp), C('VSS', y, same=False)],
                [fet(pre + 'n1', y, a, 'VSS', 'VSS', wn), fet(pre + 'n2', y, b, 'VSS', 'VSS', wn),
                 fet(pre + 'p1', pre + 'm', a, 'VDD', 'VDD', wp, 'p'), fet(pre + 'p2', y, b, pre + 'm', 'VDD', wp, 'p')])
    cols, net = [], []
    for cc, nn in (inv('SA0', 's0b', 'xi0', 1, 2), nor2('s0b', 'SA1', 'ena', 'xe', 1, 2),
                   inv('ena', 'enab', 'xi1', 1, 2), inv('SA1', 's1b', 'xi2', 1, 2), inv('s1b', 's1n', 'xi3', 1, 2)):
        cols += ([BRK] if cols else []) + cc
        net += nn
    # r6c: TGs 2/4 um (r6b 1/2)
    cols += [BRK, c('VTAN', '-'), g('ena', None, 2), c('AXN', '-'), g('s1n', None, 2), c('VTBN', '-'),
             BRK, c('VTAP', '-'), g('ena', None, 2), c('AXP', '-'), g('s1n', None, 2), c('VTBP', '-'),
             BRK, c('-', 'VTAN'), g(None, 'enab', 1, 4), c('-', 'AXN'), g(None, 's1b', 1, 4), c('-', 'VTBN'),
             BRK, c('-', 'VTAP'), g(None, 'enab', 1, 4), c('-', 'AXP'), g(None, 's1b', 1, 4), c('-', 'VTBP'),
             BRK, c('-', 'AXN'), g(None, 'SA1', 2, 2), c('-', 'pu1'), g(None, 'SA0', 2, 2), c('-', 'VDD'),
             g(None, 'SA0', 2, 2), c('-', 'pu2'), g(None, 'SA1', 2, 2), c('-', 'AXP')]
    # r6c: PMOS decaps on AXN/AXP (gate on the line, S/D on VDD; ~45 fF each) against clock kick on the line
    for ln in ('AXN', 'AXP'):
        cols += [BRK, c('-', 'VDD')]
        for k in range(NDEC):
            cols += [g(None, ln, 2, 4), c('-', 'VDD')]
            net.append(fet(f'dc{ln[-1].lower()}{k}', 'VDD', ln, 'VDD', 'VDD', 4, 'p'))
    for tg_, a_, b_ in (('ta', 'VTAN', 'AXN'), ('tb', 'VTAP', 'AXP')):
        net += [fet(tg_ + 'n', a_, 'ena', b_, 'VSS', 2), fet(tg_ + 'p', a_, 'enab', b_, 'VDD', 4, 'p')]
    for tg_, a_, b_ in (('tc', 'AXN', 'VTBN'), ('td', 'AXP', 'VTBP')):
        net += [fet(tg_ + 'n', a_, 's1n', b_, 'VSS', 2), fet(tg_ + 'p', a_, 's1b', b_, 'VDD', 4, 'p')]
    net += [fet('pu1b', 'AXN', 'SA1', 'pu1', 'VDD', 2, 'p'), fet('pu1a', 'pu1', 'SA0', 'VDD', 'VDD', 2, 'p'),
            fet('pu2a', 'VDD', 'SA0', 'pu2', 'VDD', 2, 'p'), fet('pu2b', 'pu2', 'SA1', 'AXP', 'VDD', 2, 'p')]
    ports = ['SA0', 'SA1', 'VTAP', 'VTAN', 'VTBP', 'VTBN', 'AXN', 'AXP']
    row = FixedRow('ws_aux', cols, ports=ports, wn=1, wp=2)
    order = ['SA0', 'SA1', 'enab', 's1b', 's0b', 'VTAN', 'VTBN', 'VTAP', 'VTBP', 'AXN', 'AXP', 'pu1', 'pu2', 'ena', 's1n']
    row._track_index = {n: k for k, n in enumerate(order)}
    return row, ports + ['VDD', 'VSS'], net


CELLS = dict(ws_sa=sa, ws_sae=lambda: sa(True), ws_ctl=ctl, ws_aux=aux)


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
TRIM_BITS = ('p0', 'p1', 'p2', 'n0', 'n1', 'n2', 'f0', 'f1', 'f2', 'f3')     # r4: + fine f0..f2 (MT01-W2); r6: f3
TRIMS = [f'trim_{s}_{b}' for s in GROUPS for b in TRIM_BITS]
TOP_PORTS = ['VDD_WIRE_SW', 'VSS', 'slicer_en', 'SL_P', 'SL_N'] + [f'CKP{k}' for k in range(8)] + \
            ['QCK', 'D0', 'E0', 'D1', 'E1', 'D2', 'E2', 'D3', 'E3'] + TRIMS + \
            [f'vsel_{e}_{b}' for e in ('e0', 'e1', 'e2', 'e3') for b in range(2)] + ['VTAP', 'VTAN', 'VTBP', 'VTBN']   # r6 IX-10
PLAN = [('SD0', 0, 'D0', 'd0'), ('SE0', 1, 'E0', 'e0'), ('SD1', 2, 'D1', 'd1'), ('SE1', 3, 'E1', 'e1'),
        ('SD2', 4, 'D2', 'd2'), ('SE2', 5, 'E2', 'e2'), ('SD3', 6, 'D3', 'd3'), ('SE3', 7, 'E3', 'e3')]


def top_instances():
    out = [('XCTL', 'ws_ctl', ['slicer_en', 'CKP0', 'enb', 'QCK', 'VDD_WIRE_SW', 'VSS'])]
    for e in ('e0', 'e1', 'e2', 'e3'):    # r6 IX-10 select cells
        out.append((f'XA{e[1]}', 'ws_aux', [f'vsel_{e}_0', f'vsel_{e}_1', 'VTAP', 'VTAN', 'VTBP', 'VTBN', f'axn_{e}', f'axp_{e}',
                                            'VDD_WIRE_SW', 'VSS']))
    for inst, k, q, t in PLAN:
        m = dict(CK=f'CKP{(k + 4) % 8}', INP='SL_P', INN='SL_N', ENB='enb', Q=q, VDD='VDD_WIRE_SW', VSS='VSS',
                 AXN=f'axn_{t}', AXP=f'axp_{t}')
        m.update({f'T{b[0].upper()}{b[1]}': f'trim_{t}_{b}' for b in TRIM_BITS})
        cell = 'ws_sae' if t.startswith('e') else 'ws_sa'     # r6 IX-10: aux pairs on the edge samplers only
        out.append((f'X{inst}', cell, [m[p] for p in CELLS[cell]()[1]]))
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
    rows = [['SD0', 'SE0'], ['SD1', 'SE1'], ['SD2', 'SE2'], ['SD3', 'SE3'], ['CTL', 'A0', 'A1', 'A2', 'A3']]
    # r4 (MT-01): SL_P/SL_N trunks side by side, flanked by static trim trunks (r3: CKP5's trunk beside SL_P, 31 fF)
    rep = le.generate(work, 'pt_slicer', ports, devices, rows=rows, max_row_width=400.0,
                      power_nets=('VDD_WIRE_SW', 'VSS'),
                      # r7: SL_P/SL_N keep a free column/track each side (r6: 145 fF SL_P-SL_N, ~100 fF to trims)
                      # r7: outputs also spaced (the planner put each D/E trunk beside its own sampler clock trunk:
                      # 30-47 fF CKP->D/E; safe 'off' bench with clocks running: outputs kicked to +/-0.2 V)
                      net_space={'SL_P': 1.0, 'SL_N': 1.0, **{q: 1.0 for q in ('D0', 'E0', 'D1', 'E1', 'D2', 'E2', 'D3', 'E3')}},
                      trunk_groups=[['trim_d0_f0', 'trim_d0_p0', 'trim_d0_n0', 'trim_d0_f1']] +   # r7: SL_P/SL_N placed by net_space
                      # r6c: each aux gate pair flanked by static trims (r6b: 17-28 fF clock -> AXN)
                      [[f'trim_{e}_n1', f'axn_{e}', f'axp_{e}', f'trim_{e}_n2'] for e in ('e0', 'e1', 'e2', 'e3')])
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
    res = dict(revision='r7 compact (r6 TF3/antenna/IX-10 + SR-latch 2nd NMOS finger, WN_RST 2, WP_TAIL 5, per-side coarse trims, ws_sae left INP/INN pins, SL net_space)', drc_errors=le.drc_errors(rep['drc_count_raw']), lvs=lvs,
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
