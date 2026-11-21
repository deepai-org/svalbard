"""Board side for the 100BASE-TX benches: COB bond (0.23 ohm, 2.82 nH pess.) + COB package chain to the carrier (s13 chain,
placement P4 = 50 mm, 50 ohm per leg), then B39: 49.9 ohm 1 % from each leg to the 3.3 V TX centre tap, 2 x 98 nH series,
19.6 pF differential (Butterworth fc 115 MHz), then the 1:1 magnetics (OCL 350 uH shunt, ideal otherwise) and 100 ohm at the
RJ45 (RJ_P / RJ_N). On-die TX termination off. Leg currents through 0 V sources VILP / VILN (pad -> board positive = the
current the pad leg sinks is -i)."""


def board(pk, vct=3.3):
    """pk: lines of chain.I.pkg_chain(..,'P4') with the bond already set; returns lines with the far end replaced by B39."""
    out = []
    for l in pk:
        if l.startswith(('CAC', 'RFAR_', 'CFARCM')):
            continue
        if l.startswith('RBW'):
            p = l.split(); leg = p[0][-1]
            out += [f'{p[0]} {p[1]} BWI{leg} 0.23', f'VIL{leg} BWI{leg} {p[2]} 0']
            continue
        out.append(l)
    out += [f'VCT CT 0 {vct}', 'RBT_P CT BOARD_P 49.9', 'RBT_N CT BOARD_N 49.9', 'LF_P BOARD_P RJ_P 98n', 'LF_N BOARD_N RJ_N 98n',
            'CF RJ_P RJ_N 19.6p', 'LMAG RJ_P RJ_N 350u', 'RLINE RJ_P RJ_N 100']
    return out


LABEL = ('COB bond 0.23 ohm + 2.82 nH (pess.), COB package chain + 50 mm 50-ohm carrier (s13 P4), B39 49.9 ohm to CT 3.3 V, '
         '2 x 98 nH + 19.6 pF diff (Butterworth 115 MHz), magnetics 1:1 OCL 350 uH, 100 ohm at RJ45; on-die TX termination off')
