#!/usr/bin/env python3
"""Wired-TX launch control check (rtl/pt_wtx_ctl.sv; MW-15/16/17, D-CT, D-TMDS).
Runs sim/tb_pt_wtx_ctl.sv on the RTL (must pass) and on mutated copies that must FAIL:
  ser_before_ready   SER_EN released without the ring-ready flag
  fault_ignored      pad requests not dropped by fault
  pll_en_island      c_pll_tx_en ignores the pll island state
"""
import re, subprocess, sys, tempfile
from pathlib import Path
P = Path(__file__).resolve().parents[1]
SRC = (P/'rtl/pt_wtx_ctl.sv').read_text()
MUTANTS = {
    'ser_before_ready': None,
    'fault_ignored': None,
    'pll_en_island': ('assign c_pll_tx_en      = cfg_ring_en & island_on_pll & vreg_tx_ok;', 'assign c_pll_tx_en      = cfg_ring_en & vreg_tx_ok;'),
}


def run(rtl_text, tmp):
    f = tmp/'pt_wtx_ctl.sv'; f.write_text(rtl_text)
    vvp = tmp/'tb.vvp'
    c = subprocess.run(['iverilog', '-g2012', '-I', str(P/'rtl'), '-s', 'tb_pt_wtx_ctl', '-o', str(vvp), str(P/'sim/tb_pt_wtx_ctl.sv'), str(f),
                        str(P/'rtl/pt_fifo.sv'), str(P/'rtl/pt_tx_pad_sequence.sv'), str(P/'rtl/pt_vreg_seq.sv')], capture_output=True, text=True)
    if c.returncode: sys.exit('WTX_CTL_CHECK_FAIL: compile\n' + c.stderr)
    out = subprocess.run(['vvp', '-n', str(vvp)], capture_output=True, text=True, timeout=900).stdout
    return bool(re.search(r'^TB PASS$', out, re.M)), out


def mutate(name):
    if name == 'ser_before_ready':      # the timer decision is forced true
        old = "2'd0: ring_rdy <= lt_done;"
        assert SRC.count(old) == 1
        return SRC.replace(old, "2'd0: ring_rdy <= 1'b1;")
    if name == 'fault_ignored':
        m = re.search(r'wire\s+gate_w\s*=\s*([^;]+);', SRC)
        assert m and 'fault' in m.group(1), 'gate_w expression not found'
        return SRC.replace(m.group(0), m.group(0).replace('~fault', "1'b1").replace('!fault', "1'b1"))
    old, new = MUTANTS[name][:2]
    assert SRC.count(old) == 1, name
    return SRC.replace(old, new)


def main():
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        ok, out = run(SRC, t)
        if not ok:
            print(out[-2000:]); sys.exit('WTX_CTL_CHECK_FAIL: RTL bench failed')
        print(re.search(r'checks \d+ errors \d+', out).group(0))
        for name in MUTANTS:
            text = mutate(name)
            assert text != SRC, f'mutant {name} did not apply'
            ok, out = run(text, t)
            if ok: sys.exit(f'WTX_CTL_CHECK_FAIL: mutant {name} was not detected')
            print(f'mutant {name}: detected')
    print('WTX_CTL_CHECK_PASS')


if __name__ == '__main__':
    main()
