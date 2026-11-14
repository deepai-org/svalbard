#!/usr/bin/env python3
"""pt_monitor check: bench (must pass), mutants (bench must fail on each), yosys structural check.

Usage: python3 verification/check_monitor.py [--no-yosys]
Exit status is non-zero on any failure. Light: iverilog only, one job at a time.
"""
import os, re, shutil, subprocess, sys, tempfile

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RTL = os.path.join(P, "rtl", "pt_monitor.sv")
SYNC = os.path.join(P, "rtl", "pt_fifo.sv")          # pt_sync_bit
TB = os.path.join(P, "sim", "tb_pt_monitor.sv")
ENV = dict(os.environ, OMP_NUM_THREADS="1")

# (name, exact text in rtl/pt_monitor.sv, replacement)
MUTANTS = [
    ("fault_not_sticky", "c <= (c & ~clr) | trip[i];", "c <= trip[i];"),
    ("watchdog_on_watched_clock", "always @(posedge mon_clk or negedge rst_n) // ref watchdog timer",
     "always @(posedge ref_clk or negedge rst_n) // ref watchdog timer"),
    ("requirement_ignored", "assign g[2] = rf_s;", "assign g[2] = 1'b1;"),
    ("clear_is_level", "wire clr = clr_s & ~clr_d;", "wire clr = clr_s;"),
    ("mon_clk_loss_ignored", "| (mon_dead_q & arm_r);", "| 1'b0;"),
    ("timeout_ignored", "else if (icnt >= cfg_loss_timeout_ticks) in_alive_q <= 1'b0;",
     "else if (icnt >= 12'd8) in_alive_q <= 1'b0;"),
    ("no_qualification", "assign q_done = q_run & pre_tick & (qcnt >= cfg_qualification_ticks);",
     "assign q_done = q_run;"),
    ("pgood_ignored", "(PGOOD_IMPL[i] ? island_pgood[i] : 1'b1)", "1'b1"),
    ("fault_not_gated_by_arm", "assign fault = arm_any & (fault_m | mon_lost);",
     "assign fault = (fault_m | mon_lost);"),
]


def sim(rtl, work):
    out = os.path.join(work, "tb.vvp")
    c = subprocess.run(["iverilog", "-g2012", "-Wall", "-s", "tb_pt_monitor", "-o", out, rtl, SYNC, TB],
                       capture_output=True, text=True, env=ENV)
    if c.returncode != 0:
        return None, c.stdout + c.stderr
    r = subprocess.run(["vvp", "-n", out], capture_output=True, text=True, env=ENV, timeout=600)
    return ("TB_PASS" in r.stdout and "TB_FAIL" not in r.stdout and r.returncode == 0), r.stdout + r.stderr


def main():
    bad = 0
    work = tempfile.mkdtemp(prefix="check_monitor_")
    try:
        ok, log = sim(RTL, work)
        print("bench:", "PASS" if ok else "FAIL", "|", [l for l in log.splitlines() if l.startswith("TB_")])
        if not ok:
            print(log)
            bad += 1
        src = open(RTL).read()
        for name, old, new in MUTANTS:
            if src.count(old) != 1:
                print(f"mutant {name}: pattern not found exactly once -> ERROR")
                bad += 1
                continue
            mp = os.path.join(work, name + ".sv")
            open(mp, "w").write(src.replace(old, new))
            ok, log = sim(mp, work)
            if ok is None:
                print(f"mutant {name}: does not compile -> ERROR\n{log}")
                bad += 1
            elif ok:
                print(f"mutant {name}: bench PASSED -> ERROR (bench cannot see this defect)")
                bad += 1
            else:
                first = next((l for l in log.splitlines() if l.startswith("FAIL")), "")
                print(f"mutant {name}: killed | {first[:110]}")
        if "--no-yosys" not in sys.argv:
            if shutil.which("yosys") is None:
                print("yosys: not on PATH -> ERROR (use --no-yosys to skip)")
                bad += 1
            else:
                y = subprocess.run(["yosys", "-q", "-p",
                                    f"read_verilog -sv {RTL} {SYNC}; hierarchy -top pt_monitor; proc; opt_clean; "
                                    "check -assert; select -assert-none t:$dlatch t:$dlatchsr; flatten; simplemap; tee -o "
                                    + os.path.join(work, "stat.txt") + " stat"],
                               capture_output=True, text=True, env=ENV)
                if y.returncode != 0:
                    print("yosys: FAIL\n" + y.stdout + y.stderr)
                    bad += 1
                else:
                    st = open(os.path.join(work, "stat.txt")).read()
                    flops = 0
                    for m in re.finditer(r"^\s+(\$_\w*DFF\w*_)\s+(\d+)\s*$|^\s+(\d+)\s+(\$_\w*DFF\w*_)\s*$", st, re.M):
                        flops += int(m.group(2) or m.group(3))
                    print(f"yosys: check -assert clean, no latches; flops (bits) {flops}")
                    if flops == 0 or flops >= 150:
                        print("yosys: flop count outside 1..149 -> ERROR\n" + st)
                        bad += 1
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("RESULT:", "FAIL" if bad else "PASS")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
