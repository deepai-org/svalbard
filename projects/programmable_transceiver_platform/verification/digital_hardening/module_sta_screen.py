#!/usr/bin/env python3
"""Mapped timing screen of the non-core (digital-owner) modules, run inside the guarded LibreLane image.

For each module: Yosys synthesis to gf180mcu_fd_sc_mcu7t5v0 (map with the tt library, ABC delay target
= the tightest clock), then OpenSTA with the requested Liberty: ideal clocks with 0.25 ns uncertainty
(as integration/pt_digital_macro.sdc), 20 fF output loads, no extracted wiring. Two numbers per clock:
  * logic slack: synthesized netlist, no wires;
  * routed allowance: data-path delay x ROUTE_FACTOR (1.30), an allowance for placement, repair
    buffering and wire RC taken from CLOSE_R2 (its routed ss paths average ~1.3x their cell-only sum).
A screen, not signoff: routed closure is established only by the hardening run's STA.

    module_sta_screen.py --lib LIB.lib [--derate 1.54] --out DIR
Writes DIR/screen.json.
"""
import argparse, json, re, subprocess, tempfile
from pathlib import Path

P = Path(__file__).resolve().parents[2]
TT = '/foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib'
ROUTE_FACTOR = 1.30
# module, files, parameters, clocks {name: (port or generated spec, period)}
SCREENS = [
    ('pt_freq_count', ['rtl/pt_freq_count.sv', 'rtl/pt_fifo.sv', 'rtl/pt_cells.sv'], {},
     {'fc': ('src', 6.4), 'ref': ('ref_clk', 10.0), 'sclk': ('sclk', 50.0)},
     [('blk', 'fc', 'blk_clock_buf.cell/Z', 8)]),
    ('pt_vreg_seq', ['rtl/pt_vreg_seq.sv', 'rtl/pt_fifo.sv'], {}, {'ref': ('ref_clk', 10.0)}, []),
    ('pt_interp2x', ['rtl/pt_interp2x.sv', 'rtl/pt_cells.sv'], {}, {'rftx': ('clk_fast', 12.5)},
     [('rfhalf', 'rftx', 'half_clock_buf.cell/Z', 2)]),
    ('pt_mgmt', ['rtl/pt_spi.sv', 'rtl/pt_regfile.sv'], {}, {'sclk': ('sclk', 50.0)}, []),
    ('pt_clocktree_slow', ['rtl/pt_clocktree_slow.sv', 'rtl/pt_fifo.sv', 'rtl/pt_cells.sv'], {},
     {'ctw': ('wclk', 6.4), 'ctref': ('ref_clk', 64.0), 'ctdet': ('det_clk_in', 6.4)}, []),
    ('pt_pattern_check', ['rtl/pt_pattern.sv'], {'W': 40, 'CW': 16}, {'wrx': ('clk', 16.0)}, []),
    ('pt_pattern_gen', ['rtl/pt_pattern.sv'], {'W': 40}, {'wtx': ('clk', 16.0)}, []),
]


# Module-level copies of the macro SDC exceptions that apply inside these modules.
EXTRA = {
    'pt_freq_count': [
        'set evf [concat [get_cells -quiet snap_*] [get_cells -quiet fb_prev*] [get_cells -quiet cfg_r*]]',
        'set evt {}',
        'foreach pat {r_diff* r_count* cur* good* r_locked* locked_ref* r_lost* fb_prev*} '
        '{ set evt [concat $evt [get_cells -quiet $pat]] }',
        'if {[llength $evf] && [llength $evt]} { set_multicycle_path 5 -setup -from $evf -to $evt; '
        'set_multicycle_path 4 -hold -from $evf -to $evt }'],
}


def synth(top, files, params, period, out):
    chp = ''.join(f' -set {k} {v}' for k, v in params.items())
    ys = f'''
read_liberty -lib {TT}
read_verilog -sv -DSYNTHESIS {' '.join(str(P / f) for f in files)}
chparam{chp} {top}
synth -top {top} -flatten
dfflibmap -liberty {TT}
abc -D {int(period * 1000)} -liberty {TT}
setundef -zero
hilomap -hicell gf180mcu_fd_sc_mcu7t5v0__tieh Z -locell gf180mcu_fd_sc_mcu7t5v0__tiel ZN
opt_clean -purge
autoname
stat -liberty {TT}
write_verilog -noattr {out}/{top}.v
'''
    if not params:
        ys = ys.replace(f'chparam {top}\n', '')
    (out / f'{top}.ys').write_text(ys)
    r = subprocess.run(['yosys', '-q', '-l', str(out / f'{top}.synth.log'), str(out / f'{top}.ys')], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-2000:] + (out / f'{top}.synth.log').read_text()[-2000:])
    nl = out / f'{top}.v'
    nl.write_text(re.sub(r'\bwire signed\b', 'wire', re.sub(r'\breg signed\b', 'reg', nl.read_text())))  # OpenSTA reader
    stat = (out / f'{top}.synth.log').read_text()
    ffs = sum(int(n) for n, c in re.findall(r'^\s+(\d+)\s+\S+\s+gf180mcu_fd_sc_mcu7t5v0__(dff\w+)', stat, re.M))
    return ffs


def sta(top, lib, clocks, gens, derate, out):
    t = [f'read_liberty {lib}', f'read_verilog {out}/{top}.v', f'link_design {top}']
    for name, (port, per) in clocks.items():
        t.append(f'create_clock -name {name} -period {per} [get_ports {port}*]')
    for name, master, pin, div in gens:
        t.append(f'create_generated_clock -name {name} -source [lindex [get_ports {clocks[master][0]}*] 0] -master_clock {master} '
                 f'-divide_by {div} [get_pins -hierarchical *{pin}]')
    t += EXTRA.get(top, [])
    t += ['set_clock_uncertainty 0.25 [all_clocks]', 'set_clock_transition 0.15 [all_clocks]',
          'set_load 0.02 [all_outputs]', 'set_input_transition 0.3 [all_inputs]']
    if derate != 1.0:
        t += [f'set_timing_derate -early {derate}', f'set_timing_derate -late {derate}']
    # only register-to-register paths inside the module: boundary I/O budgets belong to the macro SDC
    t += ['set_false_path -from [all_inputs]', 'set_false_path -to [all_outputs]']
    # Asynchronous reset release (recovery/removal): synchronizer outputs fan out unbuffered here; the
    # flow buffers them and the macro SDC treats them separately.
    t += ['set_false_path -to [get_pins -hierarchical */RN]', 'set_false_path -to [get_pins -hierarchical */SETN]']
    if top == 'pt_interp2x':   # halfband mode (bypass: FIR unused and false-pathed in the macro SDC)
        t += ['set_case_analysis 1 [get_pins -hierarchical *core_clock_mux.cell/S]']
    names = list(clocks) + [g[0] for g in gens]
    for a in names:
        for b in names:
            if a != b:
                t.append(f'set_false_path -from [get_clocks {a}] -to [get_clocks {b}]')
    t.append('proc ws {c} { set ps [find_timing_paths -path_delay max -group_path_count 1 -to [get_clocks $c]]; '
             'if {[llength $ps]==0} {return "none"}; set p [lindex $ps 0]; '
             'return "[get_property $p slack] [get_full_name [get_property $p startpoint]] [get_full_name [get_property $p endpoint]]" }')
    for c in names:
        t.append(f'puts "SCREEN {c} [ws {c}]"')
    t.append(f'report_checks -path_delay max -group_path_count 3 -digits 3 > {out}/{top}.paths.rpt')
    (out / f'{top}.sta.tcl').write_text('\n'.join(t) + '\n')
    r = subprocess.run(['sta', '-no_init', '-exit', str(out / f'{top}.sta.tcl')], capture_output=True, text=True)
    (out / f'{top}.sta.log').write_text(r.stdout + r.stderr)
    res = {}
    rpt = (out / f'{top}.paths.rpt').read_text() if (out / f'{top}.paths.rpt').exists() else ''
    for ln in r.stdout.splitlines():
        m = re.match(r'SCREEN (\S+) (\S+)(?: (\S+) (\S+))?', ln)
        if m and m.group(2) != 'none':
            res[m.group(1)] = dict(slack=float(m.group(2)), start=m.group(3), end=m.group(4))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lib', required=True)
    ap.add_argument('--derate', type=float, default=1.0)
    ap.add_argument('--out', required=True)
    ap.add_argument('--only', default='')
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    report = dict(lib=a.lib, derate=a.derate, route_factor=ROUTE_FACTOR, modules={})
    for top, files, params, clocks, gens in SCREENS:
        if a.only and top not in a.only.split(','):
            continue
        per = min(p for _, p in clocks.values())
        ffs = synth(top, files, params, per, out)
        logic = sta(top, a.lib, clocks, gens, a.derate, out)
        routed = sta(top, a.lib, clocks, gens, a.derate * ROUTE_FACTOR, out)
        periods = {**{k: p for k, (_, p) in clocks.items()},
                   **{g[0]: clocks[g[1]][1] * g[3] for g in gens}}
        mods = {}
        for c in logic:
            mods[c] = dict(period_ns=periods[c], logic_slack=round(logic[c]['slack'], 3),
                           routed_allowance_slack=round(routed[c]['slack'], 3) if c in routed else None,
                           margin_pct=round(100 * routed[c]['slack'] / periods[c], 1) if c in routed else None,
                           worst=f"{logic[c]['start']} -> {logic[c]['end']}")
        report['modules'][top] = dict(flip_flops=ffs, clocks=mods)
        print(top, ffs, json.dumps(mods), flush=True)
    (out / 'screen.json').write_text(json.dumps(report, indent=1) + '\n')


if __name__ == '__main__':
    main()
