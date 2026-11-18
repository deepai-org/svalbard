#!/usr/bin/env python3
"""IX-11 fast in-band threshold commands (opcodes 5 / 6) through the AC-1 host link and core:
sim/tb_fast_vth.sv in wired ownership (with and without payload) and I/Q ownership at the full and the reduced host rate. Prints FAST_VTH_PASS."""
import subprocess, sys, tempfile
from pathlib import Path
P = Path(__file__).resolve().parents[1]
RTL = ['pt_host_link.sv', 'pt_core.sv', 'pt_quad_link.sv', 'pt_quad_gearbox.sv', 'pt_linecode.sv',
       'pt_dense_header.sv', 'pt_fifo.sv', 'pt_cells.sv', 'pt_pattern.sv']

def main():
    tmp = tempfile.TemporaryDirectory(prefix='fast-vth-'); work = Path(tmp.name)
    ok = True
    for iq, pay in ((0, 0), (0, 1), (1, 0)):
        for half in (1.6, 3.2):
            vvp = work / f'b{iq}{pay}{half}.vvp'
            subprocess.run(['iverilog', '-g2012', '-I', str(P / 'rtl'), '-s', 'tb_fast_vth', '-P', f'tb_fast_vth.IQ={iq}', '-P', f'tb_fast_vth.PAY={pay}',
                            '-P', f'tb_fast_vth.HOST_HALF={half}', '-o', str(vvp), str(P / 'sim/tb_fast_vth.sv'),
                            str(P / 'sim/pt_transport_harness.sv'), str(P / 'sim/reference/pt_dense_transport.sv'),
                            *[str(P / 'rtl' / r) for r in RTL]], check=True)
            r = subprocess.run(['vvp', '-n', str(vvp)], cwd=work, capture_output=True, text=True)
            good = f'FAST_VTH_PASS iq={iq}' in r.stdout
            print(f'iq={iq} pay={pay} host_half={half}:', 'pass' if good else 'FAIL',
                  '\n  '.join(l for l in r.stdout.splitlines() if 'ERROR' in l or 'FAIL' in l))
            ok &= good
    if ok:
        print('FAST_VTH_PASS')
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()
