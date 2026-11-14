"""wtx_ser8d: eighth-rate stream source for the muxing pre-driver wtx_mux8 (NOT published).

The register / hop part of wtx_serq8 without its NAND-OR output tree: 8 five-bit parallel-load stream registers
(the 40-bit word, stream k = D(k + 8 j)), the /5 word divider and the per-stream retiming hops.  Outputs F0..F7:
F k = NOT(bit of stream k), changes about 5.3 slots after phase k and is stable around windows k and k + 1.
Cells, netlist and hop plan are those of serq8_macro.py; only the floorplan and the port list differ.

    python3 ser8d_macro.py        # -> generated/fast/wtx_ser8d.*
"""
import serq4_macro as M
import serq8_macro as Q

NAME = 'wtx_ser8d'
PORTS = [f'D{i}' for i in range(40)] + Q.PH + ['SERQ'] + [f'F{k}' for k in range(8)] + ['WCKQ', 'VDD', 'VSS']
DROP = ('XOA', 'XOB', 'XOF', 'XPP')
ROWS = [['L0', 'H0_0', 'L1', 'H1_0', 'L2', 'H2_0', 'CK', 'CTL'],
        ['P0', 'P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7'],
        ['L3', 'H3_0', 'L4', 'H4_0', 'L5', 'H5_0', 'H5_1'],
        ['L6', 'H6_0', 'H6_1', 'L7', 'H7_0', 'H7_1', 'DV']]
CELLS = [c for c in Q.CELLS if not c.startswith(('wtx_omux8', 'wtx_ofin8', 'wtx_ppost8'))]


def top_spice():
    body = [f'.subckt {NAME} {" ".join(PORTS)}']
    body += [f'{i} {" ".join(c)} {cell}' for i, cell, c in Q.top_instances() if i not in DROP]
    return '\n'.join(body + [f'.ends {NAME}']) + '\n'


def build_top():
    text = ''.join((M.FAST / f'{n}.spice').read_text() for n in CELLS)
    return M.build_le(NAME, PORTS, top_spice(), text, ROWS, CELLS, max_row_width=660.0, workname='ser8d')


if __name__ == '__main__':
    build_top()
