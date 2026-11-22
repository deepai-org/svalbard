"""Characterisation cell wc_char (extracted): inverter chain (2/4, FO2), NAND2, AOI3, one TSPC flop with a local clock buffer.
Gives per-stage delay and TSPC clk->q / setup / hold per corner for the r7f hop budget.  usage: mkchar.py build"""
import sys, json
from pathlib import Path
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H.parent))
import stage, capture as c
def char():
    k = c.Cell('wc_char')
    prev = 'IN'
    for i in range(6):
        k.inv(prev, f'N{i}', 2, 4); k.inv(f'N{i}', f'L{i}', 2, 4); prev = f'N{i}'     # FO2: next stage + dummy
    k.nand([prev, 'VDDA'], 'ND1'); k.nand(['ND1', 'VDDA'], 'ND2')
    k.aoi3([('VSSA', 'X0'), ('VSSA', 'X1'), ('ND2', 'VDDA')], 'AO')
    k.buf('CK', 'CKL')
    k.ff('CKL', 'D', 'Q')
    k.aoi3([('Q', 'VDDA'), ('VSSA', 'X2'), ('VSSA', 'X3')], 'QL')
    k.ff('CKL', 'D', 'Q2', keep=True)
    return k.row(['IN', 'VDDA', 'VSSA', 'X0', 'X1', 'X2', 'X3', 'CK', 'D', 'ENB', 'AO', 'Q', 'QL', 'Q2'])
c.CELLS['wc_char'] = char
if __name__ == '__main__':
    print(c.build_cell('wc_char'))
