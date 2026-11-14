#!/usr/bin/env python3
"""POR override strap check (integration-plan G3, interface row DT-10).

Runs sim/tb_por_bypass.sv on the RTL (must pass) and on mutated copies of rtl/pt_digital_macro.sv
(each must FAIL), so the bench is shown to detect a missing or wrong override:
  no_bypass     today's netlist, rst_n = reset_n_pad & por_n          (POR stuck low => dead die)
  ignore_por    rst_n = reset_n_pad                                   (POR never resets)
  bypass_reset  rst_n = (reset_n_pad & por_n) | por_bypass            (strap overrides RESET_N too)
  inverted      rst_n = reset_n_pad & (por_n | ~por_bypass)           (unbonded default = bypass)
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
# The reset expression lives in rtl/pt_por_path.sv since the second (pad-free) rescue path was added; the strap
# mutants are applied there, the two others in rtl/pt_digital_macro.sv.
GOOD = ' assign rst_n=reset_n_pad&(por_n|por_bypass|armed);\n'
MUTANTS = {
    'no_bypass': ' assign rst_n=reset_n_pad&(por_n|armed);\n',
    'ignore_por': ' assign rst_n=reset_n_pad;\n',
    'bypass_reset': ' assign rst_n=(reset_n_pad&(por_n|armed))|por_bypass;\n',
    'inverted': ' assign rst_n=reset_n_pad&(por_n|~por_bypass|armed);\n',
}


# mutants in pt_digital_macro.sv: (name, original text, replacement)
OTHER = [
    # the bypass reaches SPI/regfile but not the host-link reset domain
    ('split_host', 'pt_host_rate_clock host_rate(.clk(host_word_clk), .rst_n(rst_n),',
     'pt_host_rate_clock host_rate(.clk(host_word_clk), .rst_n(reset_n_pad & por_n),'),
    # strap readback missing
    ('no_readback', '.por_path({por_masked, ovr_armed, por_bypass})', ".por_path({por_masked, ovr_armed, 1'b0})"),
]


def run(rtl_dir, work):
    vvp = work/'tb.vvp'
    subprocess.run(['iverilog', '-g2012', '-I', str(rtl_dir), '-s', 'tb_por_bypass', '-o', str(vvp),
                    *map(str, sorted(rtl_dir.glob('*.sv'))), str(PROJECT/'sim/tb_por_bypass.sv')],
                   check=True, capture_output=True)
    out = subprocess.run(['vvp', '-n', str(vvp)], capture_output=True, text=True).stdout
    return bool(re.search(r'^POR_BYPASS_PASS 22 checks$', out, re.M)), out


def main():
    files = {'pt_por_path.sv': (PROJECT/'rtl/pt_por_path.sv').read_text(), 'pt_digital_macro.sv': (PROJECT/'rtl/pt_digital_macro.sv').read_text()}
    assert files['pt_por_path.sv'].count(GOOD) == 1, 'rst_n expression of pt_por_path changed: update this check'
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ok, out = run(PROJECT/'rtl', tmp)
        if not ok:
            print(out)
            sys.exit('POR_BYPASS_CHECK_FAIL: RTL bench failed')
        cases = [(n, 'pt_por_path.sv', GOOD, l) for n, l in MUTANTS.items()]+[(n, 'pt_digital_macro.sv', o, l) for n, o, l in OTHER]
        for name, fname, old, line in cases:
            source = files[fname]
            assert source.count(old) == 1, f'mutant {name}: source text changed'
            rtl = tmp/f'rtl_{name}'
            shutil.copytree(PROJECT/'rtl', rtl, ignore=shutil.ignore_patterns('gen', '__pycache__'))
            (rtl/fname).write_text(source.replace(old, line))
            ok, out = run(rtl, tmp)
            fails = len(re.findall(r'^FAIL ', out, re.M))
            if ok or fails == 0:
                sys.exit(f'POR_BYPASS_CHECK_FAIL: mutant {name} was not detected')
            print(f'mutant {name}: detected ({fails} failing checks)')
    print('POR_BYPASS_CHECK_PASS RTL 22 checks; all mutants detected')


def chip():
    """G3 closure tripwire: fails while the chip top still ties the strap to a constant."""
    top = (PROJECT/'integration/pt_chip.sv').read_text()
    m = re.search(r'\.por_bypass\((\w+)\)', top)
    if not m:
        sys.exit('POR_BYPASS_CHIP_FAIL: pt_digital_macro.por_bypass is not connected in pt_chip.sv')
    if re.search(r'wire\s+%s\s*=\s*1\'b[01]' % m[1], top) or re.fullmatch(r"1'b[01]", m[1]):
        sys.exit(f'POR_BYPASS_CHIP_FAIL: pt_chip.sv ties {m[1]} to a constant: no strap pad is bound (interface row DT-10), G3 is open')
    print('POR_BYPASS_CHIP_PASS strap bound to', m[1])


if __name__ == '__main__':
    chip() if '--chip' in sys.argv else main()
