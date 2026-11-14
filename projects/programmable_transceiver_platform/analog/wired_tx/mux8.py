"""wtx_mux8: 8-phase one-hot MUXING pre-driver (schematic generator; NOT laid out, NOT published).

The final 8:1 multiplexing happens in the pull-down network that drives the TX pad's MAIN / POST switch gates.
No one-bit-wide pulse travels through a CMOS gate, and both edges of every bit window come from RISING ring-phase
edges, so the ring's phase duty cycle does not enter.

  per phase k (slice):
    PH k -> I0 -> Y k (3-bit binary switched-capacitor delay trim TR k) -> I0b -> I1 -> X k   (X falls at PH k rise)
    start + data :  X k -> TG -> NOR(XT k, U k) = AP k,  NOR(XT k, V k) = AN k                (rise at PH k rise)
    end          :  X k -> I2 -> I3 -> B k-1                                                  (falls at PH k rise)
    stack        :  MB k (gate B k, source VSS) under MP k (gate AP k, drain OUTN) and MN k (gate AN k, drain OUTP)
  slice k conducts from rise(PH k) to rise(PH k+1); the TG makes the one-gate start path as slow as the two-gate
  end path (overlap about +10 ps at ss / tt / ff).
  data gating (static CMOS, eighth-rate):  U k = NAND(F k, ENM), V k = NAND(!F k, ENM); ENM = 0 turns both legs off
  with the loads still on = electrical idle (differential 0, common mode unchanged).
  MAIN and POST are two identical banks on the same X k; POST window k carries stream k-1 (one core bit late),
  XORed with POL (0 = de-emphasis when the POST outputs are wired with the opposite sense).
  loads: poly resistors to TOP behind a PMOS header (EN); outputs pulled to VSS when EN = 0.

    python3 mux8.py            # writes generated/fast/wtx_mux8.spice (schematic)
"""
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'generated' / 'fast' / 'wtx_mux8.spice'

# sizes (um): (wn, wp) for gates
P = dict(i0=(3, 6), i0b=(8, 16), i1=(20, 40), tg=(8, 16), nor=(4, 44), i2=(4, 12), i3=(28, 10), wt=36.0, wb=70.0,
         ctrim=(1.4, 1.0), rl=(10.0, 3.4), rcm=(40.0, 0.8), hdr=160.0, gate=(2, 4), pd=2.0)
PORTS = ([f'PH{k}' for k in range(8)] + [f'F{k}' for k in range(8)] + [f'TR{k}_{b}' for k in range(8) for b in range(3)]
         + ['ENM', 'ENP', 'POL', 'EN_MAIN', 'EN_POST', 'MAIN_P', 'MAIN_N', 'POST_P', 'POST_N', 'VDD', 'VSS'])


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


def netlist(par=None, name='wtx_mux8', post=True):
    p = dict(P); p.update(par or {})
    g = p['gate']
    L = [f'.subckt {name} ' + ' '.join(PORTS)]
    L += inv('IPOL', 'POL', 'POLB', 1, 2)
    L += bank('M', 'EN_MAIN', 'MAIN_P', 'MAIN_N', p)
    if post:
        L += bank('Q', 'EN_POST', 'POST_P', 'POST_N', p)
    for k in range(8):
        km = (k - 1) % 8
        # phase path
        L += inv(f'I0_{k}', f'PH{k}', f'Y{k}', *p['i0'])
        for b in range(3):
            L += fet(f'TS{b}_{k}', 'n', f'Y{k}', f'TR{k}_{b}', f'YC{b}_{k}', 1.0 * 2 ** b)
            L += fet(f'TC{b}_{k}', 'n', 'VSS', f'YC{b}_{k}', 'VSS', p['ctrim'][0] * 2 ** b, l=p['ctrim'][1])
        L += inv(f'I0b_{k}', f'Y{k}', f'Z{k}', *p['i0b']) + inv(f'I1_{k}', f'Z{k}', f'X{k}', *p['i1'])
        # stream gating (static)
        L += inv(f'GF_{k}', f'F{k}', f'FB{k}', *g)
        L += nand2(f'GU_{k}', f'F{k}', 'ENM', f'U{k}', *g) + nand2(f'GV_{k}', f'FB{k}', 'ENM', f'V{k}', *g)
        if post:
            L += nand2(f'GX1_{k}', f'F{k}', 'POLB', f'N1_{k}', *g) + nand2(f'GX2_{k}', f'FB{k}', 'POL', f'N2_{k}', *g)
            L += nand2(f'GX3_{k}', f'N1_{k}', f'N2_{k}', f'FP{k}', *g) + inv(f'GX4_{k}', f'FP{k}', f'FPB{k}', *g)
            L += nand2(f'GP_{k}', f'FP{k}', 'ENP', f'UP{k}', *g) + nand2(f'GQ_{k}', f'FPB{k}', 'ENP', f'VP{k}', *g)
        for tag, u, v, op, on in (('M', f'U{k}', f'V{k}', 'MAIN_P', 'MAIN_N'),) + ((('Q', f'UP{km}', f'VP{km}', 'POST_P', 'POST_N'),) if post else ()):
            en, enb = ('EN_MAIN', 'ENBM') if tag == 'M' else ('EN_POST', 'ENBQ')
            # bank off: TG open, XT held high (NOR outputs low), E high (B low): no clock-path switching in that bank
            L += fet(f'TGn{tag}_{k}', 'n', f'XT{tag}{k}', en, f'X{k}', p['tg'][0]) + fet(f'TGp{tag}_{k}', 'p', f'XT{tag}{k}', enb, f'X{k}', p['tg'][1])
            L += fet(f'TGk{tag}_{k}', 'p', f'XT{tag}{k}', en, 'VDD', 1.0)
            L += nor2(f'NP{tag}_{k}', f'XT{tag}{k}', u, f'AP{tag}{k}', *p['nor']) + nor2(f'NN{tag}_{k}', f'XT{tag}{k}', v, f'AN{tag}{k}', *p['nor'])
            L += nand2(f'I2{tag}_{k}', f'X{k}', en, f'E{tag}{k}', 2 * p['i2'][0], p['i2'][1]) + inv(f'I3{tag}_{k}', f'E{tag}{k}', f'B{tag}{km}', *p['i3'])
            L += fet(f'MB{tag}_{k}', 'n', f'S{tag}{k}', f'B{tag}{k}', 'VSS', p['wb'])
            L += fet(f'MP{tag}_{k}', 'n', on, f'AP{tag}{k}', f'S{tag}{k}', p['wt'])
            L += fet(f'MN{tag}_{k}', 'n', op, f'AN{tag}{k}', f'S{tag}{k}', p['wt'])
    L += [f'.ends {name}']
    return '\n'.join(L) + '\n'


if __name__ == '__main__':
    OUT.write_text('* generated by mux8.py (schematic, not laid out)\n' + netlist())
    t = netlist()
    print(OUT, sum(1 for l in t.splitlines() if 'fet_03v3' in l), 'fet fingers')
