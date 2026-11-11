"""TT01 COB package channel for the WIRE_RX pins as a SPICE subcircuit (PKG-W1 qualification).

Element values are the package analysis' (spec/package-channel.md, scratch/cob/channel_model.py and
channel.json, per-pin geometry of WIRE_RX_P/N): bond wire (0.83 nH/mm x length, skin R), finger 0.08 pF,
F.Cu microstrip (86.6 ohm, eeff 3.14), via (L, 0.10 pF), B.Cu microstrip, connector land 0.06 pF, connector
contact (L by distance to GND, 0.25 pF), then the carrier: a 50 ohm line of `carrier_mm` (eeff 3.3) to the
placement point P1..P4 (2/10/30/50 mm, spec section 6) where the user's passives (AC-coupling caps) and source
sit.  Lines are lumped LC ladders (pi sections, <= 15 ps each, cut-off > 10 GHz); the carrier loss (~8 dB/m at 1.25 GHz: 45 ohm/m conductor + FR4
tan d 0.02) is lumped as series R per segment, which is flat in frequency (slightly pessimistic at low f,
optimistic above 1.25 GHz).  Like the package model itself: analytic, not an EM solve.

    subckt(name, pin, carrier_mm, dbond_mm)  ->  '.subckt <name> die board' text
"""
import json
import math
from pathlib import Path

COB = Path('/home/ubuntu/svalbard/scratch/cob')
C0 = 299.792458      # mm/ns
PLACES = dict(P1=2.0, P2=10.0, P3=30.0, P4=50.0)
BONDS = dict(short=-0.3, nom=0.0, long=+0.3)


def _geom(pin):
    return json.loads((COB / 'channel.json').read_text())['geometry'][pin]


def subckt(name, pin, carrier_mm, dbond_mm=0.0, f_skin=1.25e9):
    g = _geom(pin)
    bond = g['bond_mm'] + dbond_mm
    lb = bond * 0.2 * math.log(4 * 0.40 / 0.025)                  # nH (channel_model.wire_L_per_mm)
    rb = 0.05 * bond * math.sqrt(f_skin / 1e9) + 0.05              # ohm at the Nyquist frequency
    conn_nh = g['conn_nH']
    td = lambda mm, eeff: mm * math.sqrt(eeff) / C0                # ns
    nseg = max(1, int(math.ceil(carrier_mm / 5.0)))
    rcar = 45e-3 * carrier_mm / nseg                               # ohm per segment (45 ohm/m)
    def line(tag, a, b, z0, td_ns, nsec):
        # lumped LC ladder (pi sections; each section L = Z0*TD/n, C = TD/(Z0*n)): ngspice lossless T elements
        # with ps delays stalled the transient (timestep too small) on the extracted CTLE decks
        ls, cs = z0 * td_ns / nsec, td_ns / z0 / nsec * 1e3      # nH, pF
        out, prev_ = [], a
        for i in range(nsec):
            nxt = b if i == nsec - 1 else f'{tag}{i}'
            out += [f'C{tag}{i}a {prev_} 0 {cs / 2:.5f}p', f'L{tag}{i} {prev_} {nxt} {ls:.5f}n', f'C{tag}{i}b {nxt} 0 {cs / 2:.5f}p']
            prev_ = nxt
        return out
    L = [f'.subckt {name} die board',
         f'Rb die n1 {rb:.4f}', f'Lb n1 n2 {lb:.4f}n',
         'Cf n2 0 0.08p']
    L += line('f', 'n2', 'n3', 86.6, td(g['f_mm'], 3.14), 1)
    L += [f'Lv n3 n4 {g["via_nH"]:.4f}n', 'Cv n4 0 0.10p']
    L += line('b', 'n4', 'n5', 86.6, td(g['b_mm'], 3.14), 2)
    L += ['Cl n5 0 0.06p', f'Lc n5 n6 {conn_nh:.4f}n', 'Cc n6 0 0.25p']
    prev = 'n6'
    for k in range(nseg):
        a, b = f'c{k}a', ('board' if k == nseg - 1 else f'c{k + 1}')
        L += line(f'k{k}_', prev, a, 50.0, td(carrier_mm / nseg, 3.3), 2) + [f'Rc{k} {a} {b} {rcar:.4f}']
        prev = b
    L.append(f'.ends {name}')
    return '\n'.join(L) + '\n'


if __name__ == '__main__':
    print(subckt('cob_rxp_p3', 'WIRE_RX_P', PLACES['P3']))
