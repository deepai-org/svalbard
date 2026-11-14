#!/usr/bin/env python3
"""Reset path with the strap and the pad-free keyed POR override (rtl/pt_por_path.sv, interface row DT-10).

1. sim/tb_por_path.sv must pass on the RTL and on a copy whose ovr clock pin is delayed by 0.5 ns
   (review B1: in zero-delay RTL the clear released at the RESET_N edge hides what D is).
2. Each mutated copy must FAIL the bench, in zero-delay form or (if it survives that) in the
   delayed-clock form. The line printed per mutant says which form detected it.
3. yosys: no combinational loop (`check -assert`, with a deliberately inserted loop as self-test),
   exactly 17 storage elements, all flops with asynchronous reset to 0 (no set, no latch), and after
   flatten/techmap only $_DFF_PN0_ / $_DFFE_PN0P_ cells as storage.
4. If the hardening liberty is present: the module maps onto it with 17 dffrnq and no other storage.
Usage: check_por_path.py [--structure-only]   (--structure-only: yosys part only, for debugging)
Light: iverilog + yosys on one 30-line module (the bench enumerates 2^21 static states, ~10 s per run).
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SRC = PROJECT/'rtl/pt_por_path.sv'
LIB = PROJECT/'verification/digital_hardening/liberty/gf180mcu_fd_sc_mcu7t5v0__ss_032C_3v15.lib'
IDLE = " wire idle=spi_cs_n&~spi_mosi;\n"
KCLR = " wire kclr_n=~idle;\n"
OCLR = " wire oclr_n=~(idle|(~reset_n_pad&~spi_sclk));\n"
SHIFT = " wire shift=~reset_n_pad&~spi_cs_n;\n"
KSH = "  else if(shift)key<={key[14:0],spi_mosi};\n"
KALW = " always @(posedge spi_sclk or negedge kclr_n)\n"
OALW = " always @(posedge reset_n_pad or negedge oclr_n)\n"
OD = "  else ovr<=spi_sclk;\n"
KEYC = " localparam [15:0] KEY=16'hC3A5;\n"
MATCH = " wire match=key==KEY;\n"
ARMED = " wire armed=ovr&match;\n"
RST = " assign rst_n=reset_n_pad&(por_n|por_bypass|armed);\n"
OARM = " assign ovr_armed=armed;\n"
MASK = " assign por_masked=~por_n&(por_bypass|armed);\n"
DELAY = (OALW, " wire #0.5 ck_dly=reset_n_pad;\n always @(posedge ck_dly or negedge oclr_n)\n")
MUTANTS = {
    # reset equation
    'override_reset': (RST, " assign rst_n=(reset_n_pad&(por_n|por_bypass))|armed;\n"),
    'level_key': (RST, " assign rst_n=reset_n_pad&(por_n|por_bypass|armed|spi_sclk);\n"),
    'ignore_por': (RST, " assign rst_n=reset_n_pad;\n"),
    'no_strap': (RST, " assign rst_n=reset_n_pad&(por_n|armed);\n"),
    'no_second': (RST, " assign rst_n=reset_n_pad&(por_n|por_bypass);\n"),
    # key register (review P1 / P2 fix)
    'no_key_compare': (ARMED, " wire armed=ovr;\n"),
    'no_ovr': (ARMED, " wire armed=match;\n"),
    'wrong_key_lsb': (KEYC, " localparam [15:0] KEY=16'hC3A4;\n"),
    'wrong_key_a53c': (KEYC, " localparam [15:0] KEY=16'hA53C;\n"),
    'key_compare_high_byte': (MATCH, " wire match=key[15:8]==KEY[15:8];\n"),
    'key_compare_low_byte': (MATCH, " wire match=key[7:0]==KEY[7:0];\n"),
    'key_shifts_reset_high': (SHIFT, " wire shift=~spi_cs_n;\n"),
    'key_shifts_only_reset_high': (SHIFT, " wire shift=reset_n_pad&~spi_cs_n;\n"),
    'key_ignores_csn': (SHIFT, " wire shift=~reset_n_pad;\n"),
    'key_no_idle_clear': (KCLR, " wire kclr_n=1'b1;\n"),
    'key_cleared_like_ovr': (KALW, " always @(posedge spi_sclk or negedge oclr_n)\n"),
    'key_lsb_first': (KSH, "  else if(shift)key<={spi_mosi,key[15:1]};\n"),
    'key_inverted_data': (KSH, "  else if(shift)key<={key[14:0],~spi_mosi};\n"),
    'key_falling_edge': (KALW, " always @(negedge spi_sclk or negedge kclr_n)\n"),
    # ovr flop
    'no_deadman_ovr': (OCLR, " wire oclr_n=~(~reset_n_pad&~spi_sclk);\n"),
    'no_lowclear': (OCLR, " wire oclr_n=~idle;\n"),
    'lowclear_any': (OCLR, " wire oclr_n=~(idle|~reset_n_pad);\n"),
    'lowclear_needs_cs': (OCLR, " wire oclr_n=~(idle|(~reset_n_pad&~spi_sclk&spi_cs_n));\n"),
    'set_by_sclk': (OALW, " always @(posedge spi_sclk or negedge oclr_n)\n"),
    'wrong_edge': (OALW, " always @(negedge reset_n_pad or negedge oclr_n)\n"),
    'ovr_d_const1': (OD, "  else ovr<=1'b1;\n"),
    'ovr_d_inverted': (OD, "  else ovr<=~spi_sclk;\n"),
    # dead-man
    'idle_cs_only': (IDLE, " wire idle=spi_cs_n;\n"),
    'idle_mosi_only': (IDLE, " wire idle=~spi_mosi;\n"),
    'idle_needs_sclk0': (IDLE, " wire idle=spi_cs_n&~spi_mosi&~spi_sclk;\n"),
    # status
    'armed_not_keyed': (OARM, " assign ovr_armed=ovr;\n"),
    'armed_gated': (OARM, " assign ovr_armed=armed&~por_n;\n"),
    'armed_const0': (OARM, " assign ovr_armed=1'b0;\n"),
    'masked_no_strap': (MASK, " assign por_masked=~por_n&armed;\n"),
    'masked_no_ovr': (MASK, " assign por_masked=~por_n&por_bypass;\n"),
    'masked_not_keyed': (MASK, " assign por_masked=~por_n&(por_bypass|ovr);\n"),
}


def sim(text, work, delayed):
    """Run the bench on `text` (zero delay) or on its delayed-ovr-clock copy."""
    if delayed:
        assert text.count(DELAY[0]) == 1
        text = '`timescale 1ns/1ps\n' + text.replace(*DELAY)
    src = work/'dut.sv'
    src.write_text(text)
    vvp = work/'tb.vvp'
    subprocess.run(['iverilog', '-g2012', '-s', 'tb_por_path', '-o', str(vvp), str(src),
                    str(PROJECT/'sim/tb_por_path.sv')], check=True, capture_output=True)
    out = subprocess.run(['vvp', '-n', str(vvp)], capture_output=True, text=True).stdout
    return bool(re.search(r'^POR_PATH_PASS \d+ checks$', out, re.M)), out


def yosys(script):
    r = subprocess.run(['yosys', '-p', script], capture_output=True, text=True)
    return r.returncode, r.stdout+r.stderr


def cell_counts(log):
    """Cell name -> count from the last yosys `stat` table (old and new table layouts)."""
    tail = log[log.rindex('Number of cells'):] if 'Number of cells' in log else log[log.rindex(' cells'):]
    cells = {}
    for line in tail.splitlines():
        m = re.match(r'^\s+(\S*[A-Za-z_$]\S*)\s+(\d+)\s*$', line) or None
        if m:
            cells[m[1]] = int(m[2])
            continue
        m = re.match(r'^\s+(\d+)\s+(?:[\d.eE+-]+\s+)?(\S*[A-Za-z_$]\S*)\s*$', line)
        if m and m[2] != 'cells':
            cells[m[2]] = int(m[1])
    return cells


def main():
    source = SRC.read_text()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for delayed in (() if '--structure-only' in sys.argv else (False, True)):
            ok, out = sim(source, tmp, delayed)
            if not ok:
                print(out[-3000:])
                sys.exit(f'POR_PATH_CHECK_FAIL: RTL bench failed ({"delayed ovr clock" if delayed else "zero delay"})')
            print(('RTL, ovr clock pin delayed 0.5 ns: ' if delayed else 'RTL, zero delay: ')
                  + re.search(r'^S10 \d+ of.*$', out, re.M)[0] + '; ' + re.search(r'^POR_PATH_PASS.*$', out, re.M)[0])
        for name, (old, new) in ({} if '--structure-only' in sys.argv else MUTANTS).items():
            assert source.count(old) == 1, f'mutant {name}: source text changed'
            text = source.replace(old, new)
            for delayed in (False, True):
                ok, out = sim(text, tmp, delayed)
                fails = re.findall(r'^FAIL (.*?) \(t=', out, re.M)
                if not ok and fails:
                    break
            else:
                sys.exit(f'POR_PATH_CHECK_FAIL: mutant {name} was not detected')
            print(f'mutant {name}: detected {"with the delayed ovr clock only" if delayed else "(zero delay)"} '
                  f'({len(fails)}{"+" if "stopped early" in out else ""} failing checks; first: {fails[0]})', flush=True)
        # structure
        rc, log = yosys(f'read_verilog -sv {SRC}; hierarchy -top pt_por_path; proc; opt_clean; check -assert; '
                        'select -assert-count 2 t:$adff; '  # word level: ovr (1 bit) and key (16 bits)
                        'select -assert-none t:$dlatch t:$adlatch t:$dlatchsr t:$sr t:$dffsr t:$dffsre t:$aldff t:$aldffe '
                        't:$dff t:$dffe t:$adffe t:$sdff t:$sdffe t:$sdffce %u; '
                        'flatten; opt; techmap; opt; stat')
        cells = cell_counts(log) if rc == 0 else {}
        storage = {c: n for c, n in cells.items() if re.search(r'DFF|LATCH|_SR_|FF_', c.upper())}
        if rc or sum(storage.values()) != 17 or any(not re.fullmatch(r'\$_DFFE?_P[NP]0P?_', c) for c in storage):
            print(log[-3000:])
            sys.exit('POR_PATH_CHECK_FAIL: yosys structural check (loop / storage count / flop class)')
        print('yosys: check -assert clean (no combinational loop); storage after techmap: '
              + ', '.join(f'{n} {c}' for c, n in sorted(storage.items()))
              + f' (asynchronous reset to 0 only, no latch); {sum(cells.values())} generic cells in total')
        # a loop must be reported by the same command (self-test of the check)
        loop = tmp/'loop.sv'
        loop.write_text(source.replace(RST, " assign rst_n=reset_n_pad&(por_n|por_bypass|armed|(rst_n&spi_mosi));\n"))
        rc, log = yosys(f'read_verilog -sv {loop}; hierarchy -top pt_por_path; proc; opt_clean; check -assert')
        if rc == 0 or 'loop' not in log.lower():
            sys.exit('POR_PATH_CHECK_FAIL: yosys did not report a deliberately inserted loop')
        print('yosys: deliberately inserted loop through rst_n is reported (check is live)')
        if LIB.exists():
            rc, log = yosys(f'read_liberty -lib {LIB}; read_verilog -sv {SRC}; synth -top pt_por_path; '
                            f'dfflibmap -liberty {LIB}; abc -liberty {LIB}; opt_clean; check -assert; stat')
            cells = {c: n for c, n in (cell_counts(log) if rc == 0 else {}).items() if c.startswith('gf180mcu_')}
            flops = {c: n for c, n in cells.items() if re.search(r'dff|lat|sdff', c)}
            if rc or sum(flops.values()) != 17 or any('__dffrnq_' not in c for c in flops) \
                    or any(c.startswith('$') for c in cell_counts(log)):
                print(log[-3000:])
                sys.exit('POR_PATH_CHECK_FAIL: liberty mapping is not 17 dffrnq + gates')
            print(f'liberty mapping ({sum(cells.values())} cells):', ', '.join(f'{n} {c.split("__")[1]}' for c, n in sorted(cells.items())))
        else:
            print('liberty mapping: SKIPPED (hardening liberty not present)')
    if '--structure-only' in sys.argv:
        print('POR_PATH_STRUCTURE_ONLY_PASS (bench and mutants NOT run)')
        return
    print(f'POR_PATH_CHECK_PASS RTL bench (zero delay and delayed ovr clock), all {len(MUTANTS)} mutants detected, no loop, 17 reset-to-0 flops')


if __name__ == '__main__':
    main()
