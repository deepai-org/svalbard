"""CML final 2:1 serializer stage of the compact core (wtx_cml2), after a half-rate CMOS 2:1 (wtx_omux2).

Why (scratch/reviews/gf180-device-speed-evidence.md, MANDATE device-speed guidance): the last 2:1 at
3.24 Gb/s must be current-mode.  The earlier core ended in a static-CMOS 4:1 window mux (1-UI window
pulses ANDed with the streams); extracted at ss/22 C/3.15 V it closed to a 12-46 ps eye at 3.24 Gb/s and
21 ps at 2.5 Gb/s (ISI of the window gates).  Here every CMOS signal runs at most at half rate and the
only full-rate node is the CML mux output.

Timing (UI grid, core phase C k rises at k UI; C k high on [k, k+2]; stream F k changes at C(k+2)+tcq):
  CMOS (wtx_omux2):  E = C0 ? F0 : F2,  O = C1 ? F1 : F3      (NAND-NAND, true and complement)
                     E shows F0 on [0, 2] and F2 on [2, 4] as long as 0 < tcq < 2 UI: the select edges,
                     not the flop timing, bound each 2-UI data window.
  CML clock:         CK = XOR(C0, C1): high on [0, 1] and [2, 3].  Built as the current sum of two
                     muxes with the select and data roles swapped, so every edge is the average of a
                     select-path and a data-path transition (no XOR duty-cycle skew).
  E_FF  captures E on CK falling (1, 3): the centre of E's 2-UI window.  -> shows on [2, 3], [4, 5]
  O_FF  captures O on CK rising  (2, 0): centre of O's window.              -> shows on [3, 4], [5, 6]
  Y   = CK ? E_FF : O_FF   (each flop changes only while the mux looks at the other one)
  postcursor (Y one UI later): O2 = O_FF @ CK falling, E2 = E_FF @ CK rising, DP = CK ? O2 : E2.
Line order F0, F1, F2, F3 in windows 2, 3, 4, 5 (latency +2 UI against the CMOS 4:1).

Circuits: NMOS differential pairs on NMOS tails (L 0.5 um), ppolyf_u_1k loads, no PMOS in any CML path;
pair devices in 2 um fingers; pair density 0.4 mA / 6 um = 67 uA/um.  Bias: ppolyf_u_1k reference
resistor into an NMOS diode (I_ref ~ (VDD - VGS) / R, so the swing I*R_L tracks the poly sheet).  The
CML-to-CMOS converters are NMOS-input differential amplifiers with PMOS mirror loads (the only PMOS on
the data path, at <= 1.62 GHz fundamental), two mirrored copies (true / complement) with a weak
cross-coupled inverter pair, then the CMOS pre-driver.  EN = 0 turns every tail and the reference off.

Simulation adds an explicit gate resistance to every device of this block (MANDATE: models have
rgatemod = 0): R_G_PER_FINGER ohm per 2 um finger (gf180-device-speed-evidence: 60-150 ohm per 10 um
device; we use 150 ohm per finger, i.e. per 2 um, which is 5x that density, conservative).
"""
from pathlib import Path

L_TAIL = 0.5
ROWDEF_NAMES = ['wtx_cmlt_lat', 'wtx_cmlt_mux', 'wtx_cmlt_xor', 'wtx_cmlt_buf', 'wtx_cmlt_bufl', 'wtx_cmlt_ckb', 'wtx_cmlt_ckp',
                'wtx_cmlt_lsh', 'wtx_cmlt_c2c']
WF = 2.0            # finger width of every CML pair device (um)
R_G_PER_FINGER = 150.0


class Net:
    def __init__(self, name, ports):
        self.name, self.ports, self.lines = name, ports, []

    def fet(self, name, d, g, s, kind='n', w=WF, l=0.28, nf=1):
        b = 'VSS' if kind == 'n' else 'VDD'
        m = 'nfet_03v3' if kind == 'n' else 'pfet_03v3'
        for f in range(nf):
            n = f'{name}_{f}' if nf > 1 else name
            self.lines.append(f'X{n} {d} {g} {s} {b} {m} w={w:g}u l={l:g}u')

    def res(self, name, p, n, w, l):
        self.lines.append(f'X{name} {p} {n} VSS ppolyf_u_1k r_width={w:g}u r_length={l:g}u')

    def text(self):
        return f'.subckt {self.name} {" ".join(self.ports)}\n' + '\n'.join(self.lines) + f'\n.ends {self.name}\n'


# unit currents: tail W (um, L 0.5) per 0.1 mA at the reference density
REF_W = 2.0                  # reference diode finger W (L 0.5), 4 fingers, ~0.4 mA (0.1 mA per finger)
R_REF = (2, 10.5)            # ppolyf w, l (um) -> ~5.3 kohm (0.1 mA / 21 kohm settled NB in ~30 ns)
import os as _os
R_LOAD = (2, float(_os.environ.get('CML_RL', 3.0)))       # ~1.5 kohm (0.6 V at 0.4 mA)
# impedance scale (session 5): latches (KL) and data / clock-input buffers (KB) run at K x current with
# R / K loads and K x pair / tail fingers (same current density, same swing).  Only the wire part of each
# node's capacitance shrinks in relative terms: tau_wire = (R / K) * C_wire.  Pre-layout bench
# (sim_cml --wirec): at K = 1 the stage tolerates ~20 fF per net at ss 3.24 Gb/s (40 fF: 24 errors).
KL = int(_os.environ.get('CML_KL', 2))   # session 5: 2 (extracted latch clk->Q ~210 ps at K=1, tt)
KM = int(_os.environ.get('CML_KM', 2))   # output muxes (session 5: 2; extracted MY delay ~150 ps at K=1)
KB = int(_os.environ.get('CML_KB', 2))   # session 5: 2 (XOR inputs only +-0.37 V extracted at K=1)
R_LOAD_LAT = (2 * KL, 3.0)
# CML -> CMOS converter (session 5, scratch/wired_tx/core_s5/convbench.py, real CML mux input + 40 fF):
# the PMOS mirror (4 x 4 um at ~50 uA/um, Vsg ~1.65 V at ss) was the slow pole and YU swung rail to rail,
# slew-limited and pattern-dependent: 53 ps pp at Y from 16 ps at the mux output (ss).  Now: smaller
# mirror (2 x 4 um), pair 6 fingers, and a feedback resistor R_F across the first inverter (YV -> YU)
# that clamps YU around the inverter's own threshold (DC-coupled, tracks the inverter trip point):
# ss 29 / tt 15 / ff 11 / sf 19 / fs 16 ps pp at Y (bench), 0 errors.
C2C_NF = 6
C2C_PNF = 2
R_F = (1, 6.0)               # ~6 kohm
R_LOAD_BUF = (2 * KB, 3.0)
R_LOAD_MX = (2 * KM, float(_os.environ.get('CML_RMX', 2.0)))    # ~1 kohm (output mux, 0.6 mA)
R_LOAD_X = (3, 1.0)          # ~0.33 kohm (XOR, 1.8 mA: 0.6 V; session 5: was 0.5k / 1.2 mA, extracted KX only +-0.35 V).  Was 0.75k / 0.8 mA (session 4: see XOR note)
XOR_NF = 6                   # pair fingers per side (session 5, was 4)
XOR_TAIL_NF = 9              # tail fingers per XOR half (0.9 mA; pairs 12 um/side -> 75 uA/um)
# common-mode drop resistors (VDD -> VT -> both loads): lower the output CM of the stages that drive the
# LOWER level of a stacked pair (latch / mux clock pairs, XOR lower pairs), so the lower pair stays in
# saturation under the upper pair.  ckb: 1.2 mA x ~0.42k = 0.5 V; bufl: 0.4 mA x ~1.6k = 0.65 V.
# clock drivers / pre-driver scale (session 5): KC = 2 drivers (latch clock load doubled by KL = 2), ckp x1.5
KC = int(_os.environ.get('CML_KC', 2))
CKP_NF = int(_os.environ.get('CML_CKP_NF', 42))
R_CM_CK = (4 * KC, 1.7)
R_CM_BUFL = (2, 3.2)
R_LOAD_CKP = (4 * CKP_NF // 28, 1.2)   # ~0.3 kohm at 28 fingers (2.8 mA); 42 -> 0.2 kohm / 4.2 mA
R_LOAD_CK = (2 * KC, float(_os.environ.get('CML_RCK', 1.2)))   # ~0.75 kohm (clock driver, 1.2 mA: 0.9 V; 0.5 kohm gave
                                                           # 0.52 V and the latches did not hold, tt 30/111 errors)


def cml_lib():
    """Subcircuits of the CML stage (hierarchy kept small and regular for a matched layout)."""
    out = []
    # latch: transparent while CK > CKB.  Q follows D.
    n = Net('wtx_cml_lat', ['D', 'DB', 'CK', 'CKB', 'Q', 'QB', 'NB', 'VDD', 'VSS'])
    n.res('RLP', 'VDD', 'Q', *R_LOAD_LAT); n.res('RLN', 'VDD', 'QB', *R_LOAD_LAT)
    n.fet('MD', 'QB', 'D', 'SA', nf=3 * KL); n.fet('MDB', 'Q', 'DB', 'SA', nf=3 * KL)
    n.fet('MR', 'QB', 'Q', 'SB', nf=3 * KL); n.fet('MRB', 'Q', 'QB', 'SB', nf=3 * KL)
    # clock pair 6 x 2 um: at 3 x 2 um the hold-side device needed VGS ~1.5 V (source 1.6 V, body
    # effect) and the 0.6 V clock swing left the track-side device on at VGS 0.95 V: the slave drifted
    # toward the master during hold (tt 3.24 Gb/s: 1-UI flop transitions, 150 ps pp jitter)
    n.fet('MC', 'SA', 'CK', 'T', nf=6 * KL); n.fet('MCB', 'SB', 'CKB', 'T', nf=6 * KL)
    n.fet('MT', 'T', 'NB', 'VSS', w=2.0, l=L_TAIL, nf=4 * KL)
    out.append(n)
    # 2:1 mux: Y = S ? A1 : A0
    n = Net('wtx_cml_mux', ['A1', 'A1B', 'A0', 'A0B', 'S', 'SB', 'Y', 'YB', 'NB', 'VDD', 'VSS'])
    n.res('RLP', 'VDD', 'Y', *R_LOAD_MX); n.res('RLN', 'VDD', 'YB', *R_LOAD_MX)
    n.fet('M1', 'YB', 'A1', 'S1', nf=4); n.fet('M1B', 'Y', 'A1B', 'S1', nf=4)
    n.fet('M0', 'YB', 'A0', 'S0', nf=4); n.fet('M0B', 'Y', 'A0B', 'S0', nf=4)
    n.fet('MS', 'S1', 'S', 'T', nf=8); n.fet('MSB', 'S0', 'SB', 'T', nf=8)
    n.fet('MT', 'T', 'NB', 'VSS', w=2.0, l=L_TAIL, nf=6)
    out.append(n)
    # XOR clock: Y = A xor B as the current sum of mux(S=A: !B, B) and mux(S=B: !A, A), half tail each,
    # into one load pair (each edge is the mean of a select-path and a data-path transition)
    n = Net('wtx_cml_xor', ['A', 'AB', 'B', 'BB', 'Y', 'YB', 'NB', 'VDD', 'VSS'])
    n.res('RLP', 'VDD', 'Y', *R_LOAD_X); n.res('RLN', 'VDD', 'YB', *R_LOAD_X)
    for h, (s, sb, d, db) in enumerate((('A', 'AB', 'B', 'BB'), ('B', 'BB', 'A', 'AB'))):
        # S high -> Y = !D ; S low -> Y = D
        n.fet(f'M1_{h}', 'Y', d, f'S1_{h}', nf=4); n.fet(f'M1B_{h}', 'YB', db, f'S1_{h}', nf=4)
        n.fet(f'M0_{h}', 'YB', d, f'S0_{h}', nf=4); n.fet(f'M0B_{h}', 'Y', db, f'S0_{h}', nf=4)
        n.fet(f'MS_{h}', f'S1_{h}', s, f'T_{h}', nf=4); n.fet(f'MSB_{h}', f'S0_{h}', sb, f'T_{h}', nf=4)
        n.fet(f'MT_{h}', f'T_{h}', 'NB', 'VSS', w=2.0, l=L_TAIL, nf=4)
    out.append(n)
    # buffer (CMOS rail input or CML input), 0.4 mA
    n = Net('wtx_cml_buf', ['A', 'AB', 'Y', 'YB', 'NB', 'VDD', 'VSS'])
    n.res('RLP', 'VDD', 'Y', *R_LOAD_BUF); n.res('RLN', 'VDD', 'YB', *R_LOAD_BUF)
    n.fet('M', 'YB', 'A', 'S', nf=3 * KB); n.fet('MB', 'Y', 'AB', 'S', nf=3 * KB)
    n.fet('MT', 'S', 'NB', 'VSS', w=2.0, l=L_TAIL, nf=4 * KB)
    out.append(n)
    # clock driver, 1.2 mA, 0.5 kohm
    n = Net('wtx_cml_ckb', ['A', 'AB', 'Y', 'YB', 'NB', 'VDD', 'VSS'])
    n.res('RLP', 'VDD', 'Y', *R_LOAD_CK); n.res('RLN', 'VDD', 'YB', *R_LOAD_CK)
    n.fet('M', 'YB', 'A', 'S', nf=14); n.fet('MB', 'Y', 'AB', 'S', nf=14)
    n.fet('MT', 'S', 'NB', 'VSS', w=2.0, l=L_TAIL, nf=14)
    out.append(n)
    # clock pre-driver, 2.8 mA, ~0.3 kohm (drives the four drivers)
    n = Net('wtx_cml_ckp', ['A', 'AB', 'Y', 'YB', 'NB', 'VDD', 'VSS'])
    n.res('RLP', 'VDD', 'Y', *R_LOAD_CKP); n.res('RLN', 'VDD', 'YB', *R_LOAD_CKP)
    n.fet('M', 'YB', 'A', 'S', nf=28); n.fet('MB', 'Y', 'AB', 'S', nf=28)
    n.fet('MT', 'S', 'NB', 'VSS', w=2.0, l=L_TAIL, nf=28)
    out.append(n)
    # level shift for the converters: NMOS source followers (0.2 mA each), CML CM ~3.0 V -> ~1.8 V.
    # (Without it the converter pair sat at ~1.9 V source / 2.1 V drain: its output could not go below
    # ~1.8 V, the CMOS inverter behind it never switched cleanly; tt 3.24 Gb/s 30/111 errors with a
    # bit-exact CML output.)
    n = Net('wtx_cml_lsh', ['A', 'AB', 'AS', 'ABS', 'NB', 'VDD', 'VSS'])
    n.fet('MFA', 'VDD', 'A', 'AS', nf=3); n.fet('MFB', 'VDD', 'AB', 'ABS', nf=3)
    n.fet('MTA', 'AS', 'NB', 'VSS', w=2.0, l=L_TAIL, nf=3); n.fet('MTB', 'ABS', 'NB', 'VSS', w=2.0, l=L_TAIL, nf=3)
    out.append(n)
    # CML -> CMOS: NMOS pair on the shifted levels, PMOS mirror; Y = NOT A (A high pulls Y low).  0.6 mA.
    n = Net('wtx_cml_c2c', ['A', 'AB', 'Y', 'NB', 'VDD', 'VSS'])
    n.fet('MA', 'X', 'AB', 'S', nf=C2C_NF); n.fet('MB', 'Y', 'A', 'S', nf=C2C_NF)
    n.fet('MPX', 'X', 'X', 'VDD', 'p', w=4.0, nf=C2C_PNF); n.fet('MPY', 'Y', 'X', 'VDD', 'p', w=4.0, nf=C2C_PNF)
    n.fet('MT', 'S', 'NB', 'VSS', w=2.0, l=L_TAIL, nf=8)
    out.append(n)
    return out


def cml2():
    """wtx_cml2: E/EB, O/OB (CMOS, half rate), QW0..QW3 (CMOS core phases) -> Y/YB, DP/DPB (CMOS)."""
    ports = ['E', 'EB', 'O', 'OB', 'QW0', 'QW1', 'QW2', 'QW3', 'EN', 'Y', 'YB', 'DP', 'DPB', 'VDD', 'VSS']
    n = Net('wtx_cml2', ports)
    # bias (EN = 1 enables): VDD - pfet switch - R_REF - diode
    n.fet('PEN', 'RT', 'ENB', 'VDD', 'p', w=4.0, nf=4)
    n.fet('NEI', 'ENB', 'EN', 'VSS', w=1.0); n.fet('PEI', 'ENB', 'EN', 'VDD', 'p', w=2.0)
    n.res('RREF', 'RT', 'NB', *R_REF)
    n.fet('MREF', 'NB', 'NB', 'VSS', w=REF_W, l=0.28, nf=4)     # same L as the compact-row tails
    n.fet('MOFF', 'NB', 'ENB', 'VSS', w=1.0)
    X = lambda inst, cell, *pins: n.lines.append(f'X{inst} {" ".join(pins)} NB VDD VSS {cell}')
    # clock: CMOS phases -> CML, XOR -> CK, driver
    X('BC0', 'wtx_cml_buf', 'QW0', 'QW2', 'P0', 'P2')
    X('BC1', 'wtx_cml_buf', 'QW1', 'QW3', 'P1', 'P3')
    X('BL0', 'wtx_cml_bufl', 'QW0', 'QW2', 'P0L', 'P2L')      # low-CM copies for the XOR lower pairs
    X('BL1', 'wtx_cml_bufl', 'QW1', 'QW3', 'P1L', 'P3L')
    X('XK', 'wtx_cml_xor', 'P0', 'P2', 'P1', 'P3', 'P0L', 'P2L', 'P1L', 'P3L', 'KX', 'KXB')
    # clock tree: XOR -> pre-driver -> four identical drivers, one per flop pair (+ one output mux
    # each for the E/O groups): one driver for all eight latches and both muxes (~600 fF per side)
    # left a 0.3 V near-sine clock at ss (3.24 Gb/s: errors).  Every latch / mux clock input sees the
    # same driver and the same load (two latches + one mux select or dummy mux select).
    X('DK', 'wtx_cml_ckp', 'KX', 'KXB', 'KP', 'KPB')
    for g in 'EOPQ':
        X(f'DK{g}', 'wtx_cml_ckb', 'KP', 'KPB', f'CK{g}', f'CKB{g}')
    # flops: E_FF on CK falling (master transparent CK high), O_FF on CK rising
    # data delay match (session 4): E / O reach the flops through two CML buffers, so the data path has
    # CML stages as the clock path (BC/XOR/ckp/ckb) does and the sample point tracks PVT and wiring.
    # Without them the extracted CK falling edge sat at 0.83 of E's 2-UI window (tt 3.24G; schematic
    # 0.62): the four-stage clock chain is slowed more by wire C than the CMOS omux2 data path.
    X('DE1', 'wtx_cml_buf', 'E', 'EB', 'EA1', 'EA1B')
    X('DE2', 'wtx_cml_buf', 'EA1', 'EA1B', 'EA2', 'EA2B')
    X('DO1', 'wtx_cml_buf', 'O', 'OB', 'OA1', 'OA1B')
    X('DO2', 'wtx_cml_buf', 'OA1', 'OA1B', 'OA2', 'OA2B')
    X('EM', 'wtx_cml_lat', 'EA2', 'EA2B', 'CKE', 'CKBE', 'EMQ', 'EMQB')
    X('ES', 'wtx_cml_lat', 'EMQ', 'EMQB', 'CKBE', 'CKE', 'EF', 'EFB')
    X('OM', 'wtx_cml_lat', 'OA2', 'OA2B', 'CKBO', 'CKO', 'OMQ', 'OMQB')
    X('OS', 'wtx_cml_lat', 'OMQ', 'OMQB', 'CKO', 'CKBO', 'OF', 'OFB')
    # postcursor flops: O2 = OF @ CK falling, E2 = EF @ CK rising
    X('PM', 'wtx_cml_lat', 'OF', 'OFB', 'CKP', 'CKBP', 'PMQ', 'PMQB')
    X('PS', 'wtx_cml_lat', 'PMQ', 'PMQB', 'CKBP', 'CKP', 'O2', 'O2B')
    X('QM', 'wtx_cml_lat', 'EF', 'EFB', 'CKBQ', 'CKQ', 'QMQ', 'QMQB')
    X('QS', 'wtx_cml_lat', 'QMQ', 'QMQB', 'CKQ', 'CKBQ', 'E2', 'E2B')
    # output muxes driven straight from the flops.  Each flop changes on the CK edge that deselects it, so
    # it has the whole opposite CK phase (~1 UI) to settle.  Session 4: the earlier extra CML buffers
    # (BEF/BOF/BO2/BE2, meant to delay the change past the select edge) pushed the extracted change
    # (latch clk->Q 120-250 ps + buffer ~80 ps, tt) past the next select edge: 160-190 ps glitches on YC.
    X('MY', 'wtx_cml_mux', 'EF', 'EFB', 'OF', 'OFB', 'CKE', 'CKBE', 'YC', 'YCB')
    X('MD', 'wtx_cml_mux', 'O2', 'O2B', 'E2', 'E2B', 'CKP', 'CKBP', 'DC', 'DCB')
    # dummy mux selects on the O / Q clocks (equal driver loads); tails off (NB = VSS)
    for g in 'OQ':
        n.lines.append(f'XMX{g} VSS VSS VSS VSS CK{g} CKB{g} VDD VDD VSS VDD VSS wtx_cml_mux')
    # CML -> CMOS (true / complement copies), weak cross-coupled pair, buffers
    X('LY', 'wtx_cml_lsh', 'YC', 'YCB', 'YCS', 'YCBS')
    X('LD', 'wtx_cml_lsh', 'DC', 'DCB', 'DCS', 'DCBS')
    for o, a, ab in (('Y', 'YCS', 'YCBS'), ('YB', 'YCBS', 'YCS'), ('DP', 'DCS', 'DCBS'), ('DPB', 'DCBS', 'DCS')):
        n.lines.append(f'X{o}C {a} {ab} {o}U NB VDD VSS wtx_cml_c2c')
        n.fet(f'{o}I1N', f'{o}V', f'{o}U', 'VSS', w=2.0); n.fet(f'{o}I1P', f'{o}V', f'{o}U', 'VDD', 'p', w=4.0)
        n.fet(f'{o}I2N', o, f'{o}V', 'VSS', w=4.0); n.fet(f'{o}I2P', o, f'{o}V', 'VDD', 'p', w=8.0)
        n.res(f'{o}RF', f'{o}V', f'{o}U', *R_F)
    for a, b in (('YV', 'YBV'), ('DPV', 'DPBV')):
        for x, y in ((a, b), (b, a)):
            n.fet(f'K{x}N', y, x, 'VSS', w=0.5); n.fet(f'K{x}P', y, x, 'VDD', 'p', w=1.0)
    return n


def rows_text():
    import serq4_macro as M
    return ''.join(M.subckt(n, *row_cell(n)[1:]) for n in ROWDEF)


def spice(compact_rows=True):
    """Simulation / LVS netlist.  compact_rows: leaves as the laid-out compact rows (+ poly loads)."""
    if compact_rows:
        return rows_text() + ''.join(c.text() for c in lib_compact()) + cml2().text()
    return ''.join(c.text() for c in cml_lib()) + cml2().text()


def add_gate_r(text, cells=tuple(ROWDEF_NAMES) + ('wtx_cml_lat', 'wtx_cml_mux', 'wtx_cml_xor', 'wtx_cml_buf', 'wtx_cml_bufl', 'wtx_cml_ckb', 'wtx_cml_c2c', 'wtx_cml_lsh', 'wtx_cml_ckp'),
               r_per_finger=R_G_PER_FINGER):
    """Simulation-only: a series gate resistor on every MOS device inside the CML subcircuits
    (per finger, r_per_finger * w / 2 um)."""
    out, cur, k = [], None, 0
    for line in text.splitlines():
        t = line.split()
        if t and t[0].lower() == '.subckt':
            cur = t[1]
        elif t and t[0].lower() == '.ends':
            cur = None
        if cur in cells and t and t[0].upper().startswith('X') and len(t) >= 6 and 'fet_03v3' in t[5]:
            w = next((float(x[2:].rstrip('u')) for x in t if x.startswith('w=')), WF)
            k += 1
            g = f'rg_{k}'
            out.append(f'RG{k} {t[2]} {g} {r_per_finger * w / 2.0:g}')
            t[2] = g
            line = ' '.join(t)
        out.append(line)
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    import sys
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('generated') / 'fast' / 'wtx_cml2.spice'
    p.write_text('* generated by cml_ser.py (intended netlist)\n' + spice())
    print(p)


# ------------------------------------------------------------------------------------------ layout
LEAVES = ['wtx_cml_lat', 'wtx_cml_mux', 'wtx_cml_xor', 'wtx_cml_buf', 'wtx_cml_ckb', 'wtx_cml_ckp',
          'wtx_cml_lsh', 'wtx_cml_c2c']


def build_leaf(name, max_row_width=60.0):
    import serq4_macro as M
    c = next(x for x in cml_lib() if x.name == name)
    return M.build_le(name, c.ports, c.text(), '', None, [], max_row_width=max_row_width)


def build_cml2():
    """wtx_cml2 floorplan (rows bottom to top): bias + clock input buffers + XOR + pre-driver centred,
    then the four clock drivers each directly under its own flop pair, the flop/postcursor latches,
    the output buffers and muxes, the level shifters / converters / CMOS output inverters on top.
    The four driver->latch clock nets are identical by construction (same driver cell, same
    relative placement, same two latch loads + one mux select)."""
    import serq4_macro as M
    n = cml2()
    lib = ''.join((M.FAST / f'{c}.spice').read_text() for c in LEAVES)
    names = [l.split()[0][1:] for l in n.lines]
    bias = [x for x in names if x in ('PEN', 'NEI', 'PEI', 'RREF', 'MREF_0', 'MREF_1', 'MREF_2', 'MREF_3', 'MOFF')]
    inv = [x for x in names if x[:2] in ('YI', 'YB', 'DP', 'KY', 'KD') and x not in bias and not x.startswith('YBC')
           and not x.endswith('C')]
    rows = [bias + ['BC0', 'BC1', 'XK', 'DK'],
            ['DKE', 'DKO', 'DKP', 'DKQ'],
            ['EM', 'ES', 'OM', 'OS', 'PM', 'PS', 'QM', 'QS'],
            ['BEF', 'BOF', 'MY', 'MXO', 'MXQ', 'MD', 'BO2', 'BE2'],
            ['LY', 'YC', 'YBC', 'LD', 'DPC', 'DPBC'],
            inv]
    used = {x for r in rows for x in r}
    rest = [x for x in names if x not in used]
    if rest:
        rows[-1] += rest
    return M.build_le('wtx_cml2', n.ports, n.text(), lib, rows, LEAVES, max_row_width=420.0)


if __name__ == '__main__' and False:
    pass


# ------------------------------------------------------------------- compact transistor rows (layout)
# Each CML leaf = one compact NMOS row (shared diffusion, interdigitated pairs, tails, timing's
# compact.Row) + its two ppolyf_u_1k loads placed as PCells by the parent.  The row netlist is derived
# from the columns, so schematic = layout.  Tails are L = 0.28 um here (compact rows have one gate
# length); the reference diode is in a row of the same kind, so the mirror ratios are unchanged.
def _cn(n):
    return dict(k='c', n=n, p='-')


def _g(net, w=WF):
    return dict(k='g', net=net, n=True, p=False, wn=w)


def _cp(n):
    return dict(k='c', n='-', p=n)


def _gp(net, w):
    return dict(k='g', net=net, n=False, p=True, wp=w)


def seg_pair(a, ab, yb, y, s, nf):
    """nf fingers per side, interdigitated: yb a s ab y ab s a yb ... (a drains yb, ab drains y)."""
    cols = [_cn(yb)]
    for f in range(nf):
        if f % 2 == 0:
            cols += [_g(a), _cn(s), _g(ab), _cn(y)]
        else:
            cols += [_g(ab), _cn(s), _g(a), _cn(yb)]
    return cols


def seg_rep(g, d, s, nf, w=WF):
    """nf parallel fingers, drains d / sources s alternating (shared)."""
    cols = [_cn(d)]
    for f in range(nf):
        cols += [_g(g, w), _cn(s if f % 2 == 0 else d)]
    return cols


def seg_prep(g, d, s, nf, w):
    cols = [_cp(d)]
    for f in range(nf):
        cols += [_gp(g, w), _cp(s if f % 2 == 0 else d)]
    return cols


def row_net(cols):
    """MOS lines from a column list (gate between two contact columns)."""
    out, k = [], 0
    for i, c in enumerate(cols):
        if c['k'] != 'g':
            continue
        l_, r_ = cols[i - 1], cols[i + 1]
        if c.get('n', True) and c.get('wn'):
            out.append(f'Xn{k} {l_["n"]} {c["net"]} {r_["n"]} VSS nfet_03v3 w={c["wn"]:g}u l=0.28u'); k += 1
        if c.get('p', True) and c.get('wp'):
            out.append(f'Xp{k} {l_["p"]} {c["net"]} {r_["p"]} VDD pfet_03v3 w={c["wp"]:g}u l=0.28u'); k += 1
    return out


def _join(segs):
    import compact  # noqa: F401  (timing path set by serq4_macro)
    from fastcells import BRK
    cols = []
    for sg in segs:
        if cols:
            cols.append(BRK)
        cols += sg
    return cols


ROWDEF = {
    'wtx_cmlt_lat': (['D', 'DB', 'CK', 'CKB', 'Q', 'QB', 'NB'],
                     lambda: [seg_pair('D', 'DB', 'QB', 'Q', 'LA', 3 * KL), seg_pair('Q', 'QB', 'QB', 'Q', 'LB', 3 * KL),
                              seg_pair('CK', 'CKB', 'LA', 'LB', 'T', 6 * KL), seg_rep('NB', 'T', 'VSS', 4 * KL)]),
    'wtx_cmlt_mux': (['A1', 'A1B', 'A0', 'A0B', 'S', 'SB', 'Y', 'YB', 'NB'],
                     lambda: [seg_pair('A1', 'A1B', 'YB', 'Y', 'S1', 4 * KM), seg_pair('A0', 'A0B', 'YB', 'Y', 'S0', 4 * KM),
                              seg_pair('S', 'SB', 'S1', 'S0', 'T', 8 * KM), seg_rep('NB', 'T', 'VSS', 6 * KM)]),
    # XOR: each half's lower (select) pair is driven by the low-CM copy (AL / BL) of its input.
    # Session 4: with both levels on the same ~2.85 V CM the extracted lower pairs sat in triode under
    # the upper pairs and the XOR output collapsed to +-0.1 V (ss 3.24G, inputs +-0.45 V).
    'wtx_cmlt_xor': (['A', 'AB', 'B', 'BB', 'AL', 'ALB', 'BL', 'BLB', 'Y', 'YB', 'NB'],
                     lambda: [seg_pair('B', 'BB', 'Y', 'YB', 'S1_0', XOR_NF), seg_pair('B', 'BB', 'YB', 'Y', 'S0_0', XOR_NF),
                              seg_pair('AL', 'ALB', 'S1_0', 'S0_0', 'T_0', XOR_NF), seg_rep('NB', 'T_0', 'VSS', XOR_TAIL_NF),
                              seg_pair('A', 'AB', 'Y', 'YB', 'S1_1', XOR_NF), seg_pair('A', 'AB', 'YB', 'Y', 'S0_1', XOR_NF),
                              seg_pair('BL', 'BLB', 'S1_1', 'S0_1', 'T_1', XOR_NF), seg_rep('NB', 'T_1', 'VSS', XOR_TAIL_NF)]),
    'wtx_cmlt_bufl': (['A', 'AB', 'Y', 'YB', 'NB'],
                      lambda: [seg_pair('A', 'AB', 'YB', 'Y', 'S', 3 * KB), seg_rep('NB', 'S', 'VSS', 4 * KB)]),
    'wtx_cmlt_buf': (['A', 'AB', 'Y', 'YB', 'NB'],
                     lambda: [seg_pair('A', 'AB', 'YB', 'Y', 'S', 3 * KB), seg_rep('NB', 'S', 'VSS', 4 * KB)]),
    'wtx_cmlt_ckb': (['A', 'AB', 'Y', 'YB', 'NB'],
                     lambda: [seg_pair('A', 'AB', 'YB', 'Y', 'S', 14 * KC), seg_rep('NB', 'S', 'VSS', 14 * KC)]),
    'wtx_cmlt_ckp': (['A', 'AB', 'Y', 'YB', 'NB'],
                     lambda: [seg_pair('A', 'AB', 'YB', 'Y', 'S', CKP_NF), seg_rep('NB', 'S', 'VSS', CKP_NF)]),
    # converter path doubled in session 4: extracted (tt 3.24G) the mux output YC was bit-correct but the
    # 0.6 mA PMOS-mirror converter could not slew its ~25 fF output (YU 0.5-2.7 V, mean far off the
    # inverter threshold): 30 % errors at the CMOS output.  lsh 0.6 mA per side, c2c 1.2 mA.
    'wtx_cmlt_lsh': (['A', 'AB', 'AS', 'ABS', 'NB', 'VDDN'],
                     lambda: [seg_rep('A', 'VDDN', 'AS', 6), seg_rep('NB', 'AS', 'VSS', 6),
                              seg_rep('AB', 'VDDN', 'ABS', 6), seg_rep('NB', 'ABS', 'VSS', 6)]),
    'wtx_cmlt_c2c': (['A', 'AB', 'Y', 'NB'],
                     lambda: [seg_pair('AB', 'A', 'X', 'Y', 'S', C2C_NF), seg_rep('NB', 'S', 'VSS', 16),
                              seg_prep('X', 'X', 'VDD', C2C_PNF, 4.0), seg_prep('X', 'Y', 'VDD', C2C_PNF, 4.0)]),
}


def row_cell(name):
    import compact
    ports, fn = ROWDEF[name]
    cols = _join(fn())
    r = compact.Row(name, cols, ports=ports, wn=WF, wp=4.0)
    # diffusion-only nets on the low tracks, then outputs, then gate-only nets: a gate's poly contact
    # sits at its own track in a neighbouring contact column, above that column's M1 strip
    low = ['LA', 'LB', 'T', 'S', 'S1', 'S0', 'S1_0', 'S0_0', 'T_0', 'S1_1', 'S0_1', 'T_1', 'AS', 'ABS']
    r.track_order = low + ['Q', 'QB', 'Y', 'YB', 'X']
    return r, ports + ['VDD', 'VSS'], row_net(cols)


def lib_compact():
    """Leaf subcircuits as (compact transistor row macro + two ppolyf loads)."""
    out = []
    for leaf, rl, rcm in (('lat', R_LOAD_LAT, None), ('mux', R_LOAD_MX, None), ('xor', R_LOAD_X, None),
                          ('buf', R_LOAD_BUF, None), ('bufl', R_LOAD_BUF, (R_CM_BUFL[0] * KB, R_CM_BUFL[1])), ('ckb', R_LOAD_CK, R_CM_CK),
                          ('ckp', R_LOAD_CKP, None)):
        ports = ROWDEF[f'wtx_cmlt_{leaf}'][0]
        y, yb = ('Q', 'QB') if leaf == 'lat' else ('Y', 'YB')
        n = Net(f'wtx_cml_{leaf}', ports + ['VDD', 'VSS'])
        top = 'VT' if rcm else 'VDD'
        if rcm:
            n.res('RCM', 'VDD', 'VT', *rcm)
        n.res('RLP', top, y, *rl); n.res('RLN', top, yb, *rl)
        n.lines.append(f'XT {" ".join(ports)} VDD VSS wtx_cmlt_{leaf}')
        out.append(n)
    for leaf in ('lsh', 'c2c'):
        ports = [p for p in ROWDEF[f'wtx_cmlt_{leaf}'][0] if p != 'VDDN']
        n = Net(f'wtx_cml_{leaf}', ports + ['VDD', 'VSS'])
        full = ROWDEF[f'wtx_cmlt_{leaf}'][0]
        n.lines.append(f'XT {" ".join("VDD" if p == "VDDN" else p for p in full)} VDD VSS wtx_cmlt_{leaf}')
        out.append(n)
    return out
