"""pt_wiredtx8: block top of the eighth-rate wired transmitter (schematic generator; NOT published).

    pt_wiredtx8 = wtx_ser8d (40-bit word -> 8 streams) + wtx_mux8 (8-phase muxing pre-driver, drives the pad's
                  MAIN / POST switch gates) + wtx8_aux (control glue, two tail-bias DACs, CMOS tap, EXT / idle drivers)

Control glue (static CMOS, all inputs are gates on the wired rail):
    on      = !ISLAND_OFF
    ext     = WTX_EXT & on                         ring-independent fallback: all eight MAIN slices in parallel, data DX
    ENM     = !IDLE & !ext                         stream data enable (MAIN);   ENP = ENM (POST)
    OVP     = ext & !DX  |  idle_mid               OVN = ext & DX | idle_mid,   idle_mid = IDLE & IDLE_MODE & !ext
    EN_MAIN / EN_POST to the mux are ANDed with `on`; the mux itself gates them with its ring-run detector.
  IDLE = 1, IDLE_MODE = 0: both pad gates of each pair at the supply (no slice conducts, loads on);
  IDLE = 1, IDLE_MODE = 1: both legs of the conducting slice on (both gates at mid level).  Differential 0 in both.
  Polarity: logic 1 (word bit, or DX in EXT mode) = MAIN_N high = V(PAD_P) > V(PAD_N).  POST_P / POST_N of this block
  go to the pad's POST_P / POST_N; POST_POL = 0 is de-emphasis, 1 is same sign (three-level).
Tail DACs: cells.IDAC2M x 2 (MAIN, POST) on a 10 uA reference sourced into IBIAS, as in pt_wiredtx.
CMOS tap (TAP_EN): MAIN_P / MAIN_N -> NMOS pair with poly loads -> skewed inverters -> TAP_P / TAP_N (CMOS levels, for
  pt_usb_txdrv.CMD_P / CMD_N); TAP_P follows MAIN_P.

    python3 wtx8_top.py            # writes generated/fast/pt_wiredtx8.spice (intended netlist, hierarchical)
"""
from pathlib import Path

import cells
import wtx_mux8 as mux8
from wtx_mux8 import fet, inv, nand2, nor2

HERE = Path(__file__).resolve().parent
FAST = HERE / 'generated' / 'fast'
NAME = 'pt_wiredtx8'
FROT = 2            # slice k of the mux takes stream (k + FROT) mod 8 (see ser8d_macro.py)
PH = [f'PH{k}' for k in range(8)]
SER_PH = [f'PH{a}' for a in (0, 45, 90, 135, 180, 225, 270, 315)]
TRIM = [f'TR{k}_{b}' for k in range(8) for b in range(mux8.NTR)]
PORTS = (PH + [f'D{i}' for i in range(40)] + ['WORD_CLK40', 'SER_EN', 'IDLE', 'IDLE_MODE', 'WTX_EXT', 'DX', 'POST_POL',
         'EN_MAIN', 'EN_POST', 'ISLAND_OFF', 'TAP_EN', 'IBIAS'] + [f'MAIN_CODE{i}' for i in range(8)]
         + [f'POST_CODE{i}' for i in range(8)] + TRIM
         + ['MAIN_P', 'MAIN_N', 'POST_P', 'POST_N', 'MAIN_BIAS', 'POST_BIAS', 'TAP_P', 'TAP_N', 'TX_RUN', 'WTX_EXT_DATA',
            'ATB_NBIAS', 'ATB_PBIAS', 'ATB_AVGP', 'ATB_AVGN', 'VDD', 'VSS'])
TAP = dict(pair=(2.0, 0.28), tail=(20.0, 2.0), rl=(1.0, 15.0), sk=(4.0, 0.5, 2.0), b1=(1, 2), b2=(4, 8))
AUX_PORTS = ['SER_EN', 'IDLE', 'IDLE_MODE', 'WTX_EXT', 'DX', 'EN_MAIN', 'EN_POST', 'ISLAND_OFF', 'TAP_EN', 'IBIAS'] + \
    [f'MAIN_CODE{i}' for i in range(8)] + [f'POST_CODE{i}' for i in range(8)] + \
    ['INP', 'INN', 'SERQ', 'ENM', 'EXT', 'OVP', 'OVN', 'ENMAIN_G', 'ENPOST_G', 'MAIN_BIAS', 'POST_BIAS', 'TAP_P', 'TAP_N',
     'WTX_EXT_DATA', 'ATB_NBIAS', 'ATB_PBIAS', 'VDD', 'VSS']


def aux(name='wtx8_aux', tap=None):
    t = dict(TAP, **(tap or {}))
    L = [f'.subckt {name} ' + ' '.join(AUX_PORTS)]
    # ---- glue
    L += inv('GON', 'ISLAND_OFF', 'ON', 1, 2) + inv('GDXB', 'DX', 'DXB', 1, 2)
    L += nand2('GEX', 'WTX_EXT', 'ON', 'EXTB', 1, 2) + inv('GEXI', 'EXTB', 'EXT', 4, 8)
    L += nor2('GENM', 'IDLE', 'EXT', 'ENM0', 1, 4) + inv('GENMa', 'ENM0', 'ENM0B', 2, 4) + inv('GENMb', 'ENM0B', 'ENM', 8, 16)
    L += nand2('GIM', 'IDLE', 'IDLE_MODE', 'IMB0', 1, 2) + nor2('GIM2', 'IMB0', 'EXT', 'IMID', 1, 4) + inv('GIM3', 'IMID', 'IMIDB', 1, 2)
    L += nand2('GOP', 'EXT', 'DXB', 'OPB', 2, 4) + nand2('GOP2', 'OPB', 'IMIDB', 'OVP0', 2, 4)
    L += nand2('GON_', 'EXT', 'DX', 'ONB', 2, 4) + nand2('GON2', 'ONB', 'IMIDB', 'OVN0', 2, 4)
    for s in ('P', 'N'):
        L += inv(f'GOV{s}a', f'OV{s}0', f'OV{s}1', 4, 8) + inv(f'GOV{s}b', f'OV{s}1', f'OV{s}', 12, 24)
    L += nand2('GSE', 'SER_EN', 'ON', 'SERB', 1, 2) + inv('GSEI', 'SERB', 'SERQ', 2, 4)
    L += nand2('GEM', 'EN_MAIN', 'ON', 'EMB', 1, 2) + inv('GEMI', 'EMB', 'ENMAIN_G', 2, 4)
    L += nand2('GEP', 'EN_POST', 'ON', 'EPB', 1, 2) + inv('GEPI', 'EPB', 'ENPOST_G', 2, 4)
    L += nand2('GXD', 'DX', 'EXT', 'XDB', 1, 2) + inv('GXDI', 'XDB', 'WTX_EXT_DATA', 2, 4)
    # ---- bias: IBIAS (10 uA sourced) into an NMOS diode behind a switch, used while a bank or the tap is requested
    L += nor2('GBE', 'ENMAIN_G', 'ENPOST_G', 'BE0', 1, 4) + inv('GBT', 'TAP_EN', 'TAPB0', 1, 2)
    L += nand2('GBE2', 'BE0', 'TAPB0', 'BEN', 1, 2) + inv('GBE3', 'BEN', 'BENB', 1, 2)
    L += fet('BSW', 'n', 'IBIAS', 'BEN', 'ATB_NBIAS', 4.0) + fet('BD', 'n', 'ATB_NBIAS', 'ATB_NBIAS', 'VSS', 2.0, l=2.0)
    L += fet('BPD', 'n', 'ATB_NBIAS', 'BENB', 'VSS', 1.0)
    L += ['XDACM ATB_NBIAS ENMAIN_G ISLAND_OFF ' + ' '.join(f'MAIN_CODE{i}' for i in range(8)) + ' MAIN_BIAS ATB_PBIAS VDD VSS wtx_idac2m',
          'XDACP ATB_NBIAS ENPOST_G ISLAND_OFF ' + ' '.join(f'POST_CODE{i}' for i in range(8)) + ' POST_BIAS PBQ VDD VSS wtx_idac2m']
    # ---- CMOS tap
    L += nand2('TEN', 'TAP_EN', 'ON', 'TENB', 1, 2) + inv('TENI', 'TENB', 'TEN', 1, 2)
    L += fet('TT', 'n', 'TS', 'ATB_NBIAS', 'TT1', t['tail'][0], l=t['tail'][1], mmax=4.0) + fet('TTS', 'n', 'TT1', 'TEN', 'VSS', 8.0)
    L += fet('T1', 'n', 'TD1', 'INP', 'TS', t['pair'][0], l=t['pair'][1]) + fet('T2', 'n', 'TD2', 'INN', 'TS', t['pair'][0], l=t['pair'][1])
    L += [f'XTR1 VDD TD1 VSS ppolyf_u_1k r_width={t["rl"][0]}u r_length={t["rl"][1]}u',
          f'XTR2 VDD TD2 VSS ppolyf_u_1k r_width={t["rl"][0]}u r_length={t["rl"][1]}u']
    for s, d in (('P', 'TD1'), ('N', 'TD2')):
        L += fet(f'TK{s}p', 'p', f'TQ{s}', d, 'VDD', t['sk'][0]) + fet(f'TK{s}n', 'n', f'TQ{s}', d, 'VSS', t['sk'][1], l=t['sk'][2])
        L += inv(f'TB{s}a', f'TQ{s}', f'TQ{s}B', *t['b1']) + inv(f'TB{s}b', f'TQ{s}B', f'TAP_{s}', *t['b2'])
    return '\n'.join(L + [f'.ends {name}']) + '\n'


def top(name=NAME):
    L = [f'.subckt {name} ' + ' '.join(PORTS)]
    L.append('XSER ' + ' '.join(f'D{i}' for i in range(40)) + ' ' + ' '.join(PH) + ' SERQ ' + ' '.join(f'F{k}' for k in range(8))
             + ' WORD_CLK40 VDD VSS wtx_ser8d')
    L.append('XMUX ' + ' '.join(PH) + ' ' + ' '.join(f'F{(k + FROT) % 8}' for k in range(8)) + ' ' + ' '.join(TRIM)
             + ' ENM ENM POST_POL ENMAIN_G ENPOST_G EXT OVP OVN TX_RUN ATB_AVGP ATB_AVGN MAIN_P MAIN_N POST_N POST_P VDD VSS wtx_mux8')
    L.append('XAUX SER_EN IDLE IDLE_MODE WTX_EXT DX EN_MAIN EN_POST ISLAND_OFF TAP_EN IBIAS ' + ' '.join(f'MAIN_CODE{i}' for i in range(8))
             + ' ' + ' '.join(f'POST_CODE{i}' for i in range(8))
             + ' MAIN_P MAIN_N SERQ ENM EXT OVP OVN ENMAIN_G ENPOST_G MAIN_BIAS POST_BIAS TAP_P TAP_N WTX_EXT_DATA ATB_NBIAS ATB_PBIAS VDD VSS wtx8_aux')
    return '\n'.join(L + [f'.ends {name}']) + '\n'


def aux_text():
    return cells.INV1.spice() + '\n' + cells.IDAC2M.spice() + '\n' + aux()


def netlist(ser_text=None, mux_text=None):
    """complete hierarchical netlist; ser_text / mux_text default to the intended netlists."""
    ser_text = ser_text if ser_text is not None else (FAST / 'wtx_ser8d.spice').read_text()
    mux_text = mux_text if mux_text is not None else mux8.netlist()
    return ser_text + '\n' + mux_text + '\n' + aux_text() + '\n' + top()


if __name__ == '__main__':
    out = FAST / f'{NAME}.spice'
    out.write_text('* generated by wtx8_top.py (intended netlist, hierarchical; not published)\n' + netlist())
    print(out)
