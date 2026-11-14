#!/usr/bin/env python3
"""Check rtl/pt_wrx_ctl.sv (wired-RX CDR control plane) with sim/tb_pt_wrx_ctl.sv.

1. The bench must PASS on the real RTL (all tests; T5 again with the edge word on the other half).
2. Every mutant (a one-line change in a temporary copy of the RTL) must make the bench FAIL, and
   with the error the mutant was written for.

Light: iverilog + vvp only, one process at a time.  Exit code 0 only when everything is as expected.
Usage: check_wrx_ctl.py [-k] [name ...]     names: base, base_ewh1, or mutant names; -k keeps the temp dir
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RTL = os.path.join(P, "rtl", "pt_wrx_ctl.sv")
EXTRA = [os.path.join(P, "rtl", "pt_fifo.sv")]
TB = os.path.join(P, "sim", "tb_pt_wrx_ctl.sv")
TOP = "tb_pt_wrx_ctl"

# name, [(old, new), ...] (each old must occur exactly once), test mask, error text that must appear,
# optional extra plusargs
MUTANTS = [
    ("fll_inverted",
     [("wire        a_up  = fc_diff[13] ^ cfg_fll_inv;", "wire        a_up  = !fc_diff[13] ^ cfg_fll_inv;")],
     1 << 2, "first pulse must be FDN"),
    ("fll_manual_dir_swapped",
     [("c_cdr_fup <= cfg_fll_man_dir; c_cdr_fdn <= !cfg_fll_man_dir;",
       "c_cdr_fup <= !cfg_fll_man_dir; c_cdr_fdn <= cfg_fll_man_dir;")],
     1 << 1, "manual FUP pulse length"),
    ("fll_runs_in_manual",
     [("end else if (!cfg_fll_auto) begin", "end else if (1'b0) begin")],
     1 << 9, "FLL pulsed with cfg_fll_auto = 0"),
    ("fll_loss_never",
     [("wire        out_loss = cfg_fll_loss != 12'd0 && mag > {1'b0, cfg_fll_loss};",
       "wire        out_loss = 1'b0;")],
     1 << 8, "frequency loss not flagged"),
    ("picker_stuck",
     [("c_wrx_cap_psel  <= c_wrx_cap_psel - 3'd1;", "c_wrx_cap_psel  <= c_wrx_cap_psel;"),
      ("c_wrx_cap_psel  <= c_wrx_cap_psel + 3'd1;", "c_wrx_cap_psel  <= c_wrx_cap_psel;")],
     1 << 5, "picker did not follow the drift"),
    ("picker_inverted",
     [("wire [5:0] el_x  = cfg_pick_inv ? ~el_sum + 6'd1 : el_sum;",
       "wire [5:0] el_x  = cfg_pick_inv ? el_sum : ~el_sum + 6'd1;")],
     1 << 5, "picker"),
    ("picker_slip_tag_missing",
     [("c_wrx_cap_slipp <= c_wrx_cap_psel == 3'd3;", "c_wrx_cap_slipp <= 1'b0;")],
     1 << 5, "3 -> 4 without SLIPP tag"),
    ("picker_runs_in_manual",
     [("end else if (!pa_sy[1]) begin", "end else if (1'b0) begin")],
     1 << 9, "picker moved with cfg_pick_auto = 0"),
    ("valid_before_freq_lock",
     [("vm_q == 2'd0 ? st_sig_ok && fk_sy[1] :", "vm_q == 2'd0 ? st_sig_ok :")],
     1 << 4, "valid rose without freq_ok"),
    ("valid_before_word_lock",
     [("if (gcnt[cfg_lock_exp]) st_sig_ok <= 1'b1;", "if (1'b1) st_sig_ok <= 1'b1;")],
     1 << 6, "valid rose before 32 clean words"),
    ("valid_held_on_bad_words",
     [("if ({1'b0, bcnt} >= need_m1) begin st_sig_ok <= 1'b0; bcnt <= 3'd0; end",
       "if (1'b0) begin st_sig_ok <= 1'b0; bcnt <= 3'd0; end")],
     1 << 6, "valid held on noise"),
    ("restart_ignored",
     [("wire kick     = rs_sy[2] ^ rs_sy[1];", "wire kick     = 1'b0;")],
     1 << 8, "restart did not clear"),
    ("wclk_stop_ignored",
     [("wrun <= en_s && st_wclk_alive && !kick;", "wrun <= en_s && !kick;")],
     1 << 7, "outputs held without a word clock"),
    ("ew_half1_edge19_violation",
     [("wire [19:0] e_in = cfg_ew_half ? {wire_rx_data[39], wire_rx_edge[18:0]} : wire_rx_edge;",
       "wire [19:0] e_in = wire_rx_edge;")],
     1 << 5, "picker: no valid", ["+EWH=1", "+CEWH=1"]),
    ("disable_ignored",
     [("end else if (!en_s || kick) begin", "end else if (kick) begin")],
     1 << 0, "control output moved while cfg_en = 0"),
]


def run(cmd):
    env = dict(os.environ, OMP_NUM_THREADS="1")
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    return r.returncode, r.stdout


def sim(tmp, name, rtl, plusargs):
    """Compile and run; returns (verdict, log): verdict PASS / FAIL / BROKEN."""
    vvp = os.path.join(tmp, name + ".vvp")
    rc, out = run(["iverilog", "-g2012", "-I", os.path.join(P, "rtl"), "-o", vvp, "-s", TOP, TB, rtl] + EXTRA)
    if rc != 0:
        return "BROKEN", out
    rc, out = run(["vvp", "-n", vvp] + plusargs)
    lines = out.splitlines()
    if rc == 0 and "PASS" in lines and not re.search(r"^(ERROR|FAIL)", out, re.M):
        return "PASS", out
    if rc == 0 and any(l.startswith("FAIL errors=") for l in lines):
        return "FAIL", out
    return "BROKEN", out


def main():
    args = sys.argv[1:]
    keep = "-k" in args
    only = [a for a in args if a != "-k"]
    known = ["base", "base_ewh1"] + [m[0] for m in MUTANTS]
    for a in only:
        if a not in known:
            sys.exit("unknown name %s (known: %s)" % (a, " ".join(known)))
    src = open(RTL).read()
    tmp = tempfile.mkdtemp(prefix="check_wrx_ctl_")
    bad = 0
    try:
        for name, plus in (("base", []), ("base_ewh1", ["+T=32", "+EWH=1", "+CEWH=1"])):
            if only and name not in only:
                continue
            verdict, log = sim(tmp, name, RTL, plus)
            ok = verdict == "PASS"
            bad += not ok
            print("%-28s %-6s %s" % (name, verdict, "ok" if ok else "NOT OK (bench must pass)"), flush=True)
            if not ok:
                print("\n".join("    " + l for l in log.splitlines()[-25:]))
        for name, edits, mask, want, *more in MUTANTS:
            if only and name not in only:
                continue
            text = src
            for old, new in edits:
                if text.count(old) != 1:
                    text = None
                    break
                text = text.replace(old, new)
            if text is None:
                bad += 1
                print("%-28s BROKEN NOT OK (mutation site not found exactly once: %r)" % (name, old), flush=True)
                continue
            mrtl = os.path.join(tmp, name + ".sv")
            with open(mrtl, "w") as f:
                f.write(text)
            verdict, log = sim(tmp, name, mrtl, ["+T=%d" % mask] + (more[0] if more else []))
            hit = [l for l in log.splitlines() if l.startswith("ERROR") and want in l]
            ok = verdict == "FAIL" and bool(hit)
            bad += not ok
            if ok:
                note = "killed: " + hit[0].split(": ", 1)[1]
            elif verdict == "PASS":
                note = "NOT OK (mutant survived)"
            elif verdict == "FAIL":
                note = "NOT OK (failed, but without the expected error '%s')" % want
            else:
                note = "NOT OK (did not compile / run)"
            print("%-28s %-6s %s" % (name, verdict, note), flush=True)
            if not ok:
                print("\n".join("    " + l for l in log.splitlines()[-25:]))
    finally:
        if keep:
            print("kept " + tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    print("check_wrx_ctl: %s" % ("PASS" if bad == 0 else "FAIL (%d)" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
