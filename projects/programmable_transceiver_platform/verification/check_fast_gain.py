#!/usr/bin/env python3
"""RXR-D2 fast gain command (opcode4) through the AC-1 host link and core: sim/tb_fast_gain.sv for
both sample widths at the full and the reduced (div2, RF modes) host rate. Prints FAST_GAIN_PASS."""
import subprocess, sys, tempfile
from pathlib import Path
P = Path(__file__).resolve().parents[1]
RTL = ['pt_host_link.sv', 'pt_core.sv', 'pt_quad_link.sv', 'pt_quad_gearbox.sv', 'pt_linecode.sv',
       'pt_dense_header.sv', 'pt_fifo.sv', 'pt_cells.sv', 'pt_pattern.sv']

def main():
    work = Path(tempfile.mkdtemp(prefix='fast-gain-'))
    samples = [((i * 123457 + 0xabc123) ^ (i << 7)) & 0xffffff for i in range(20000)]
    (work / 'samples.hex').write_text(''.join(f'{s:06x}\n' for s in samples))
    results = []
    for mode8 in (0, 1):
        for half in (1.6, 3.2):
            vvp = work / f'b{mode8}{half}.vvp'
            subprocess.run(['iverilog', '-g2012', '-I', str(P / 'rtl'), '-s', 'tb_fast_gain', '-P', f'tb_fast_gain.MODE8={mode8}',
                            '-P', f'tb_fast_gain.HOST_HALF={half}', '-o', str(vvp), str(P / 'sim/tb_fast_gain.sv'),
                            str(P / 'sim/pt_transport_harness.sv'), str(P / 'sim/reference/pt_dense_transport.sv'),
                            *[str(P / 'rtl' / r) for r in RTL]], check=True)
            r = subprocess.run(['vvp', '-n', str(vvp)], cwd=work, capture_output=True, text=True)
            ok = 'FAST_GAIN_PASS' in r.stdout
            print(f'mode8={mode8} host_half={half}:', '\n  '.join(l for l in r.stdout.splitlines() if 'gain' in l or 'ERROR' in l or 'FAST' in l))
            results.append(ok)
    if all(results):
        print('FAST_GAIN_PASS')
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()
