#!/usr/bin/env python3
"""pt_usb regression: bench on the real RTL must pass, every mutant must make the bench fail,
and yosys must accept the module (check -assert). Light jobs only, one at a time.

usage: python3 verification/check_usb.py [--no-yosys]
exit status 0 only if everything holds.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

P = Path(__file__).resolve().parent.parent
RTL = P / 'rtl' / 'pt_usb.sv'
TB = P / 'sim' / 'tb_pt_usb.sv'
ENV = dict(os.environ, OMP_NUM_THREADS='1')

# (name, exact source text, replacement): each must occur exactly once in rtl/pt_usb.sv
MUTANTS = [
    ('fs_overlap: D+ high side ignores the low side (no break-before-make)',
     'g_fh_p <= fs_act && s_dp          && !g_fl_p && age_fl_p >= cfg_bbm;',
     'g_fh_p <= fs_act && s_dp;'),
    ('fs_overlap_low: D- low side ignores the high side',
     'g_fl_n <= fs_act && s_oe && !s_dn && !g_fh_n && age_fh_n >= cfg_bbm;',
     'g_fl_n <= fs_act && s_oe && !s_dn;'),
    ('hs_fs_together: HS enable does not wait for the FS side to be off',
     'hs_en_q  <= sel_hs && fs_clear;',
     'hs_en_q  <= sel_hs;'),
    ('fs_hs_together: FS enable does not wait for the HS side to be off',
     'fs_en_q  <= sel_fs && hs_clear;',
     'fs_en_q  <= sel_fs;'),
    ('polarity: D+ / D- swapped',
     "wire s_dp = sym == 2'b01;\n    wire s_dn = sym == 2'b10;",
     "wire s_dp = sym == 2'b10;\n    wire s_dn = sym == 2'b01;"),
    ('fault_ignored: fault does not clear the drivers',
     'wire kill_n = rst_n & island_on & ~fault;',
     'wire kill_n = rst_n & island_on;'),
    ('island_ignored: island off does not clear the drivers',
     'wire kill_n = rst_n & island_on & ~fault;',
     'wire kill_n = rst_n & ~fault;'),
    ('no_rearm: drive resumes by itself after a fault',
     "wire sel_fs = req_fs && armed && !term_on_s;",
     "wire sel_fs = req_fs && !term_on_s;"),
    ('term_interlock: FS allowed with the pad termination on',
     "wire sel_fs = req_fs && armed && !term_on_s;",
     "wire sel_fs = req_fs && armed;"),
    ('se1: released symbol drives both lines high',
     "g_fh_n <= fs_act && s_dn          && !g_fl_n && age_fl_n >= cfg_bbm;",
     "g_fh_n <= fs_act && (s_dn || !s_oe) && !g_fl_n && age_fl_n >= cfg_bbm;"),
    ('no_debounce: line state follows every sample',
     'else if (cnt == n) q <= cand;',
     "else if (1'b1) q <= cand;"),
    ('rx_phase: symbol taken at the edge instead of the bit centre',
     'wire stb     = rph == half;',
     "wire stb     = rph == 8'd0;"),
    ('squelch_polarity',
     'assign st_squelch = !diff_db && !thr_disc_s;',
     'assign st_squelch = diff_db && !thr_disc_s;'),
    ('disconnect_unqualified: disconnect without HS transmit',
     "else if (diff_db && hsdrv_s) st_disconnect <= 1'b1;",
     "else if (diff_db) st_disconnect <= 1'b1;"),
]


def run_bench(rtl, work, tag):
    """returns (passed, failed, log): passed = bench printed PASS; failed = it printed a FAIL verdict."""
    out = work / f'{tag}.vvp'
    c = subprocess.run(['iverilog', '-g2012', '-o', str(out), str(TB), str(rtl)],
                       capture_output=True, text=True, env=ENV)
    if c.returncode != 0:
        return False, False, 'COMPILE ERROR\n' + c.stdout + c.stderr
    r = subprocess.run(['vvp', '-n', str(out)], capture_output=True, text=True, env=ENV, timeout=600)
    log = r.stdout + r.stderr
    return 'TB_PT_USB PASS' in log, bool(re.search(r'TB_PT_USB FAIL', log)), log


def main():
    bad = 0
    src = RTL.read_text()
    work = Path(tempfile.mkdtemp(prefix='check_usb_'))
    try:
        ok, _, log = run_bench(RTL, work, 'real')
        print(log.rstrip())
        print(f'[{"ok" if ok else "FAIL"}] bench on rtl/pt_usb.sv')
        bad += not ok
        for i, (name, old, new) in enumerate(MUTANTS):
            if src.count(old) != 1:
                print(f'[FAIL] mutant {i} ({name}): source text found {src.count(old)} times, expected 1')
                bad += 1
                continue
            m = work / f'mut{i}.sv'
            m.write_text(src.replace(old, new))
            ok, failed, log = run_bench(m, work, f'mut{i}')
            caught = failed and not ok
            first = next((l.strip() for l in log.splitlines() if 'FAIL @' in l), log.strip().splitlines()[-1] if log.strip() else '')
            print(f'[{"ok" if caught else "FAIL"}] mutant {i} {name}: {"caught: " + first if caught else "NOT caught: " + first}')
            bad += not caught
        if '--no-yosys' not in sys.argv:
            if shutil.which('yosys'):
                y = subprocess.run(['yosys', '-q', '-p',
                                    f'read_verilog -sv {RTL}; hierarchy -top pt_usb; proc; opt_clean; check -assert; '
                                    'flatten; opt; techmap; opt; tee -o ' + str(work / 'stat.txt') + ' stat'],
                                   capture_output=True, text=True, env=ENV)
                txt = (work / 'stat.txt').read_text() if (work / 'stat.txt').exists() else ''
                flops = sum(int(n) for n, c in re.findall(r'^\s*(\d+)\s+\S*?(\$_[A-Z]*DFF[A-Z0-9_]*)\s*$', txt, re.M)) or \
                    sum(int(n) for c, n in re.findall(r'^\s*(\$_[A-Z]*DFF[A-Z0-9_]*)\s+(\d+)\s*$', txt, re.M))
                latch = bool(re.search(r'LATCH', txt))
                good = y.returncode == 0 and flops > 0 and not latch
                print((y.stdout + y.stderr).strip()[-2000:])
                print(f'[{"ok" if good else "FAIL"}] yosys check -assert rc={y.returncode}, flops={flops}, latches={"yes" if latch else "none"}')
                bad += not good
            else:
                print('[FAIL] yosys not on PATH (use --no-yosys, or the docker image as scratch/digital-timing-close/chk.sh)')
                bad += 1
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print('CHECK_USB', 'PASS' if not bad else f'FAIL ({bad})')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
