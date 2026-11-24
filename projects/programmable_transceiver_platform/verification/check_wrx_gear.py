#!/usr/bin/env python3
"""Check the W7-GEAR word front end (rtl/pt_boundary.sv pt_wrx_gear in the pt_wired macro) with sim/tb_wrx_gear.sv.

1. The bench must PASS on the real RTL.
2. Every mutant (a change in a temporary copy of the RTL) must make the bench FAIL:
   halves swapped, pairing not re-zeroed at a restart (gear held only by reset), the second EW flop missing (EW one
   word off DW), the 40-bit word loaded at every strobe instead of every second one, edge_half inverted, raw lane 2 halves swapped.
   (Taking DW / EW at the WSTB fall is a timing error, not a logic one: zero-delay simulation cannot see it; the SDC
   constrains the inputs to the WSTB rise only.)

Light: iverilog + vvp only, one process at a time. Exit code 0 only when everything is as expected.
"""
import os
import shutil
import subprocess
import sys
import tempfile

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TB = os.path.join(P, 'sim', 'tb_wrx_gear.sv')
# name, file in rtl/, [(old, new), ...] (each old must occur exactly once)
MUTANTS = [
    ('halves_swapped', 'pt_boundary.sv', [('if (gi < 2) begin : l assign src_d = lo_d[gi*10 +: 10];', 'if (gi >= 2) begin : l assign src_d = lo_d[(gi-2)*10 +: 10];'),
                                           ('else begin : h assign src_d = dw_q2[(gi-2)*10 +: 10];', 'else begin : h assign src_d = dw_q2[gi*10 +: 10];')]),
    ('no_restart_rezero', 'pt_digital_macro.sv', [('.run(rst_n & c_wrx_cap_en & c_wordclk_en)', '.run(rst_n)')]),
    ('no_second_ew_flop', 'pt_boundary.sv', [('if (!tc[2+gi]) lo_e[gi*10 +: 10] <= ew_q2[gi*10 +: 10];',
                                              'if (!tc[2+gi]) lo_e[gi*10 +: 10] <= ew_q[gi*10 +: 10];'),
                                             ('assign src_e = ew_q2[(gi-2)*10 +: 10];', 'assign src_e = ew_q[(gi-2)*10 +: 10];')]),
    ('edge_half_inverted', 'pt_digital_macro.sv', [('assign wrx_ew = f_wrx_picker__edge_half ? wrx_ew40[39:20] : wrx_ew40[19:0];',
                                                    'assign wrx_ew = f_wrx_picker__edge_half ? wrx_ew40[19:0] : wrx_ew40[39:20];')]),
    ('lane2_halves_swapped', 'pt_boundary.sv', [('(lane == 2\'d2) ? {ew[19:0], dx[19:0]}', '(lane == 2\'d2) ? {dx[19:0], ew[19:0]}')]),
    ('valid_every_strobe', 'pt_boundary.sv', [('ew_q2 <= ew_q; te <= ~te; end', "ew_q2 <= ew_q; te <= 1'b1; end"),
                                               ('.d(~te), .q(tc[gi])', ".d(1'b1), .q(tc[gi])")]),
]


def run(rtl_dir, work):
    srcs = sorted(os.path.join(rtl_dir, f) for f in os.listdir(rtl_dir) if f.endswith('.sv'))
    vvp = os.path.join(work, 'tb.vvp')
    c = subprocess.run(['iverilog', '-g2012', '-I', rtl_dir, '-s', 'tb_wrx_gear', '-o', vvp, TB] + srcs,
                       capture_output=True, text=True)
    if c.returncode:
        return 'COMPILE', c.stderr[-2000:]
    r = subprocess.run(['vvp', '-n', vvp], capture_output=True, text=True, timeout=600)
    out = r.stdout
    if 'WRX_GEAR_PASS' in out:
        return 'PASS', out
    if 'WRX_GEAR_FAIL' in out:
        return 'FAIL', out
    return 'NONE', out[-2000:]


def main():
    ok = True
    work = tempfile.mkdtemp(prefix='wrx_gear_')
    try:
        rtl = os.path.join(P, 'rtl')
        v, out = run(rtl, work)
        print(f'base: {v}  {[l for l in out.splitlines() if l.startswith("tb_wrx_gear")]}')
        if v != 'PASS':
            ok = False
            print(out[-3000:])
        for name, fname, edits in MUTANTS:
            mdir = os.path.join(work, name)
            shutil.copytree(rtl, mdir)
            f = os.path.join(mdir, fname)
            s = open(f).read()
            for a, b in edits:
                if s.count(a) != 1:
                    print(f'{name}: mutation text found {s.count(a)} times')
                    ok = False
                    break
                s = s.replace(a, b)
            else:
                open(f, 'w').write(s)
                v, out = run(mdir, work)
                first = next((l for l in out.splitlines() if l.startswith('FAIL')), '')
                print(f'mutant {name}: {v} ({"detected" if v == "FAIL" else "NOT detected"}) {first[:120]}')
                if v != 'FAIL':
                    ok = False
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print('check_wrx_gear: ' + ('PASS' if ok else 'FAIL'))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
