"""wtx_mux8: 8-phase one-hot MUXING pre-driver of pt_wiredtx8 (schematic generator, revision 3; NOT published).

The final 8:1 multiplexing happens in the pull-down network that drives the TX pad's MAIN / POST switch gates.
No one-bit-wide pulse travels through a CMOS gate, and both edges of every bit window come from RISING ring-phase
edges, so the ring's phase duty cycle does not enter.

  per phase k (slice):
    PH k -> I0 = NAND(PH k, !EXTF) -> Y k (4-bit binary switched-capacitor delay trim TR k) -> I0b -> I1 -> X k
                                                                                    (X falls at PH k rise)
    start + data :  X k -> TG -> NOR(XT k, U k) = AP k,  NOR(XT k, V k) = AN k                (rise at PH k rise)
    end          :  X k -> I2 -> I3 -> B k-1                                                  (falls at PH k rise)
    stack        :  MB k (gate B k, source VSS) under MP k (gate AP k, drain OUTN) and MN k (gate AN k, drain OUTP)
  slice k conducts from rise(PH k) to rise(PH k+1); the TG makes the one-gate start path as slow as the two-gate
  end path.
  stream gating (static CMOS, eighth-rate):  U k = !(F k & ENM | OVP), V k = !(!F k & ENM | OVN).
    ENM = 0, OVP = OVN = 0: no leg conducts, loads on: both outputs at the top level (idle, both pad gates high);
    ENM = 0, OVP = OVN = 1: both legs of the conducting slice on (idle, both outputs at mid level);
    ENM = 0, EXT = 1, OVP = !DX, OVN = DX: fallback data.  While the ring runs (RUN = 1) the slices work as usual and
      only the data comes from OVP / OVN.  When the ring does not run, EXTF = EXT & !RUN forces every X k high (B high)
      and pulls the MAIN XT k low (window always open): all eight slices conduct in parallel, steered by OVP / OVN;
      each slice carries 1/8 of the bank current, the same average as in normal operation (ring-independent, slow:
      the eightfold pull-down takes the outputs to 0.13 V and the pad gates cross low).
  MAIN and POST are two identical banks on the same X k; POST window k carries stream k-1 (one core bit late),
  XORed with POL (0 = de-emphasis when the POST outputs are wired with the opposite sense, 1 = same sign).
  loads: poly resistors to TOP behind a PMOS header; outputs pulled to VSS when the bank is off.
  stopped-ring interlock: four charge pumps watch the eight conduction windows on private copies of the phase
    inputs PH k (so the detector keeps seeing the ring while EXTF forces the X k; pump j:
    charge moves VDD -> A_j in window 2j and A_j -> N_j in window 2j+1, a long-channel NMOS discharges N_j; the four
    series PMOS gates of a pump include a signal and its complement, so no static state conducts).  RUN = all four
    N_j high.  Bank enables: MAIN = EN_MAIN & (RUN | EXT), POST = EN_POST & RUN & !EXT.
  observation: RUN; AVG_P / AVG_N = MAIN_P / MAIN_N through 100 kohm (slot-width calibration by DC voltage).

    python3 wtx_mux8.py            # writes generated/fast/wtx_mux8.spice (schematic)
"""
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'generated' / 'fast' / 'wtx_mux8.spice'
NTR = 4
# sizes (um): (wn, wp) for gates
P = dict(i0=(6, 6), i0x=1.0, i0b=(8, 16), i1=(20, 40), tg=(8, 16), nor=(4, 44), i2=(4, 12), i3=(28, 10), wt=36.0, wb=70.0,
         ctrim=(3.0, 1.0), wts=1.3, rl=(10.0, 3.4), rcm=(40.0, 0.8), hdr=160.0, gate=(2, 4), gdrv=(3, 6), pd=2.0, ravg=(1.0, 100.0),
         det=dict(buf=(0.5, 1.0), sw=1.0, ca=(4.0, 2.0), cn=(4.0, 3.0), leak=(0.3, 50.0), nleak=2, sense=(2.0, 0.5), sl=0.5))
PORTS = ([f'PH{k}' for k in range(8)] + [f'F{k}' for k in range(8)] + [f'TR{k}_{b}' for k in range(8) for b in range(NTR)]
         + ['ENM', 'ENP', 'POL', 'EN_MAIN', 'EN_POST', 'EXT', 'OVP', 'OVN', 'RUN', 'AVG_P', 'AVG_N',
            'MAIN_P', 'MAIN_N', 'POST_P', 'POST_N', 'VDD', 'VSS'])


def fet(name, typ, d, g, s, w, l=0.28, mmax=10.0):
    nf = max(1, math.ceil(w / mmax - 1e-9)); wf = w / nf
    b, m = ('VSS', 'nfet_03v3') if typ == 'n' else ('VDD', 'pfet_03v3')
    return [f'X{name}_{i} {d} {g} {s} {b} {m} w={wf:.3f}u l={l}u ad={wf * 0.24:.3f}p as={wf * 0.24:.3f}p '
            f'pd={wf + 0.96:.3f}u ps={wf + 0.96:.3f}u' for i in range(nf)]


def inv(n, a, y, wn, wp):
    return fet(n + 'n', 'n', y, a, 'VSS', wn) + fet(n + 'p', 'p', y, a, 'VDD', wp)


def nand2(n, a, b, y, wn, wp):
    return (fet(n + 'na', 'n', y, a, n + '_m', wn) + fet(n + 'nb', 'n', n + '_m', b, 'VSS', wn)
            + fet(n + 'pa', 'p', y, a, 'VDD', wp) + fet(n + 'pb', 'p', y, b, 'VDD', wp))


def nor2(n, a, b, y, wn, wp):
    """a = the clock input, next to the output in the PMOS stack."""
    return (fet(n + 'na', 'n', y, a, 'VSS', wn) + fet(n + 'nb', 'n', y, b, 'VSS', wn)
            + fet(n + 'pb', 'p', n + '_m', b, 'VDD', wp) + fet(n + 'pa', 'p', y, a, n + '_m', wp))


def bank(tag, en, outp, outn, p):
    """header, loads and off-state pull-downs of one output bank (MAIN or POST)."""
    L = inv(f'IE{tag}', en, f'ENB{tag}', 1, 2)
    L += fet(f'HP{tag}', 'p', f'TOP2{tag}', f'ENB{tag}', 'VDD', p['hdr'])
    L += [f'XRCM{tag} TOP2{tag} TOP{tag} VSS ppolyf_u r_width={p["rcm"][0]}u r_length={p["rcm"][1]}u',
          f'XRLP{tag} TOP{tag} {outp} VSS ppolyf_u r_width={p["rl"][0]}u r_length={p["rl"][1]}u',
          f'XRLN{tag} TOP{tag} {outn} VSS ppolyf_u r_width={p["rl"][0]}u r_length={p["rl"][1]}u']
    L += fet(f'PDP{tag}', 'n', outp, f'ENB{tag}', 'VSS', p['pd']) + fet(f'PDN{tag}', 'n', outn, f'ENB{tag}', 'VSS', p['pd'])
    return L



def aoi21(n, a1, a2, b, y, wn, wp):
    """y = !(a1 & a2 | b)"""
    return (fet(n + 'na1', 'n', y, a1, n + '_m', 2 * wn) + fet(n + 'na2', 'n', n + '_m', a2, 'VSS', 2 * wn) + fet(n + 'nb', 'n', y, b, 'VSS', wn)
            + fet(n + 'pb', 'p', n + '_z', b, 'VDD', 2 * wp) + fet(n + 'pa1', 'p', y, a1, n + '_z', 2 * wp) + fet(n + 'pa2', 'p', y, a2, n + '_z', 2 * wp))


def detector(p):
    L = []
    for k in range(8):
        L += inv(f'DA{k}', f'PH{k}', f'XE{k}', *p['buf']) + inv(f'DB{k}', f'XE{k}', f'XD{k}', *p['buf'])      # XE = !PH, XD = PH
    for j in range(4):
        a, b, c = 2 * j, 2 * j + 1, (2 * j + 2) % 8
        L += fet(f'DP1{j}', 'p', f'DM1{j}', f'XE{a}', 'VDD', p['sw']) + fet(f'DP2{j}', 'p', f'DA{j}', f'XD{b}', f'DM1{j}', p['sw'])
        L += fet(f'DP3{j}', 'p', f'DM2{j}', f'XE{b}', f'DA{j}', p['sw']) + fet(f'DP4{j}', 'p', f'DN{j}', f'XD{c}', f'DM2{j}', p['sw'])
        L += fet(f'DCA{j}', 'n', 'VSS', f'DA{j}', 'VSS', p['ca'][0], l=p['ca'][1]) + fet(f'DCN{j}', 'n', 'VSS', f'DN{j}', 'VSS', p['cn'][0], l=p['cn'][1])
        prev = f'DN{j}'
        for i in range(p['nleak']):
            nxt = 'VSS' if i == p['nleak'] - 1 else f'DLK{j}_{i}'
            L += fet(f'DL{j}_{i}', 'n', prev, 'VDD', nxt, p['leak'][0], l=p['leak'][1]); prev = nxt
        L += fet(f'DSN{j}', 'n', f'DRB{j}', f'DN{j}', 'VSS', p['sense'][0], l=p['sl']) + fet(f'DSP{j}', 'p', f'DRB{j}', f'DN{j}', 'VDD', p['sense'][1], l=p['sl'])
    L += nor2('DR01', 'DRB0', 'DRB1', 'DR01', 1, 4) + nor2('DR23', 'DRB2', 'DRB3', 'DR23', 1, 4)
    L += nand2('DRN', 'DR01', 'DR23', 'RUNB', 1, 2) + inv('DRI', 'RUNB', 'RUN', 2, 4)
    return L


def netlist(par=None, name='wtx_mux8', interlock=True):
    p = dict(P); p.update(par or {})
    p['det'] = dict(P['det'], **(p.get('det') or {}))
    g = p['gate']
    L = [f'.subckt {name} ' + ' '.join(PORTS)]
    L += inv('IPOL', 'POL', 'POLB', 1, 2) + inv('IEXT', 'EXT', 'EXTB', 1, 2)
    # EXTF = EXT & !RUN: the static (all slices parallel) path is used only when the ring does not run
    L += nor2('GXF', 'EXTB', 'RUN', 'EXTF', 2, 8) + inv('GXFI', 'EXTF', 'EXTFB', 4, 8)
    # block-level enables (static CMOS)
    if interlock:
        L += detector(p['det'])
        L += nor2('GRE', 'RUN', 'EXT', 'RXB', 1, 4) + inv('GEMI', 'EN_MAIN', 'ENMAINB', 1, 2)
        L += nor2('GEM', 'RXB', 'ENMAINB', 'ENM0', 1, 4) + inv('GEM2', 'ENM0', 'ENMIB', 2, 4) + inv('GEM3', 'ENMIB', 'ENMI', 4, 8)   # enM = EN_MAIN & (RUN | EXT)
        L += fet('GEQa', 'n', 'ENQN', 'EN_POST', 'GEQ_m', 2) + fet('GEQb', 'n', 'GEQ_m', 'RUN', 'GEQ_n', 2) + fet('GEQc', 'n', 'GEQ_n', 'EXTB', 'VSS', 2)
        L += fet('GEQd', 'p', 'ENQN', 'EN_POST', 'VDD', 2) + fet('GEQe', 'p', 'ENQN', 'RUN', 'VDD', 2) + fet('GEQf', 'p', 'ENQN', 'EXTB', 'VDD', 2)
        L += inv('GEQ2', 'ENQN', 'ENQI', 4, 8)                                                                                       # enQ = EN_POST & RUN & !EXT
    else:
        L += inv('GEMa', 'EN_MAIN', 'ENMXb', 1, 2) + inv('GEM3', 'ENMXb', 'ENMI', 4, 8) + inv('GEQa', 'EN_POST', 'ENQXb', 1, 2) + inv('GEQ2', 'ENQXb', 'ENQI', 4, 8)
        L += ['RRUN RUN VDD 1']
    # ENMI / ENQI: internal bank enables.  tgM = ENMI & !EXT, extM = ENMI & EXT
    L += nand2('GTG', 'ENMI', 'EXTFB', 'TGMB', 2, 4) + inv('GTGI', 'TGMB', 'TGM', 4, 8)
    L += nand2('GXM', 'ENMI', 'EXTF', 'EXTMB', 2, 4) + inv('GXMI', 'EXTMB', 'EXTM', 4, 8)
    L += inv('GQB', 'ENQI', 'ENQIB', 4, 8)
    L += bank('M', 'ENMI', 'MAIN_P', 'MAIN_N', p) + bank('Q', 'ENQI', 'POST_P', 'POST_N', p)
    L += [f'XRAVGP MAIN_P AVG_P VSS ppolyf_u_1k r_width={p["ravg"][0]}u r_length={p["ravg"][1]}u',
          f'XRAVGN MAIN_N AVG_N VSS ppolyf_u_1k r_width={p["ravg"][0]}u r_length={p["ravg"][1]}u']
    for k in range(8):
        km = (k - 1) % 8
        # phase path: Y = NAND(PH, EXTB), PH next to the output
        L += fet(f'I0na_{k}', 'n', f'Y{k}', f'PH{k}', f'I0m_{k}', p['i0'][0]) + fet(f'I0nb_{k}', 'n', f'I0m_{k}', 'EXTFB', 'VSS', p['i0'][0])
        L += fet(f'I0pa_{k}', 'p', f'Y{k}', f'PH{k}', 'VDD', p['i0'][1]) + fet(f'I0pb_{k}', 'p', f'Y{k}', 'EXTFB', 'VDD', p['i0x'])
        for b in range(NTR):
            L += fet(f'TS{b}_{k}', 'n', f'Y{k}', f'TR{k}_{b}', f'YC{b}_{k}', p['wts'] * 2 ** b)
            L += fet(f'TC{b}_{k}', 'n', 'VSS', f'YC{b}_{k}', 'VSS', p['ctrim'][0] * 2 ** b, l=p['ctrim'][1])
        L += inv(f'I0b_{k}', f'Y{k}', f'Z{k}', *p['i0b']) + inv(f'I1_{k}', f'Z{k}', f'X{k}', *p['i1'])
        # stream gating (static)
        L += inv(f'GF_{k}', f'F{k}', f'FB{k}', *g)
        L += aoi21(f'GU_{k}', f'F{k}', 'ENM', 'OVP', f'U{k}', *p['gdrv']) + aoi21(f'GV_{k}', f'FB{k}', 'ENM', 'OVN', f'V{k}', *p['gdrv'])
        L += nand2(f'GX1_{k}', f'F{k}', 'POLB', f'N1_{k}', *g) + nand2(f'GX2_{k}', f'FB{k}', 'POL', f'N2_{k}', *g)
        L += nand2(f'GX3_{k}', f'N1_{k}', f'N2_{k}', f'FP{k}', *g) + inv(f'GX4_{k}', f'FP{k}', f'FPB{k}', *g)
        L += nand2(f'GP_{k}', f'FP{k}', 'ENP', f'UP{k}', *g) + nand2(f'GQ_{k}', f'FPB{k}', 'ENP', f'VP{k}', *g)
        for tag, u, v, op, on in (('M', f'U{k}', f'V{k}', 'MAIN_P', 'MAIN_N'), ('Q', f'UP{km}', f'VP{km}', 'POST_P', 'POST_N')):
            en, tg, tgb = ('ENMI', 'TGM', 'TGMB') if tag == 'M' else ('ENQI', 'ENQI', 'ENQIB')
            L += fet(f'TGn{tag}_{k}', 'n', f'XT{tag}{k}', tg, f'X{k}', p['tg'][0]) + fet(f'TGp{tag}_{k}', 'p', f'XT{tag}{k}', tgb, f'X{k}', p['tg'][1])
            L += fet(f'TGk{tag}_{k}', 'p', f'XT{tag}{k}', en, 'VDD', 1.0)
            if tag == 'M':
                L += fet(f'TGx{tag}_{k}', 'n', f'XT{tag}{k}', 'EXTM', 'VSS', 2.0)
            L += nor2(f'NP{tag}_{k}', f'XT{tag}{k}', u, f'AP{tag}{k}', *p['nor']) + nor2(f'NN{tag}_{k}', f'XT{tag}{k}', v, f'AN{tag}{k}', *p['nor'])
            L += nand2(f'I2{tag}_{k}', f'X{k}', en, f'E{tag}{k}', 2 * p['i2'][0], p['i2'][1]) + inv(f'I3{tag}_{k}', f'E{tag}{k}', f'B{tag}{km}', *p['i3'])
            L += fet(f'MB{tag}_{k}', 'n', f'S{tag}{k}', f'B{tag}{k}', 'VSS', p['wb'])
            L += fet(f'MP{tag}_{k}', 'n', on, f'AP{tag}{k}', f'S{tag}{k}', p['wt'])
            L += fet(f'MN{tag}_{k}', 'n', op, f'AN{tag}{k}', f'S{tag}{k}', p['wt'])
    L += [f'.ends {name}']
    return '\n'.join(L) + '\n'


if __name__ == '__main__':
    t = netlist()
    OUT.write_text('* generated by wtx_mux8.py (schematic, revision 3)\n' + t)
    print(OUT, sum(1 for l in t.splitlines() if 'fet_03v3' in l), 'fet fingers')
