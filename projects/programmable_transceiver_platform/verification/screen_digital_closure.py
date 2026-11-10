#!/usr/bin/env python3
"""Map a frozen RTL snapshot and report ideal-clock timing before PnR.

This screen uses the GF180 library and the chip SDC, including the 312.5 MHz
host target. It is not extracted timing, placement fit or physical signoff.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
IMAGE = 'svalbard/librelane-gf180-canary:2026.08'
LIBRARY = '/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib'


def screen(source, out, top, period=3.2, boundary_delay=None):
    assert not (out/'report.json').exists(), 'Use a new output directory for each frozen screen'
    out.mkdir(parents=True, exist_ok=True)
    (out/'rtl').mkdir(exist_ok=True)
    sources = sorted(p for p in (source/'rtl').iterdir() if p.suffix in ('.sv', '.svh', '.vh'))
    for p in sources:
        shutil.copy2(p, out/'rtl'/p.name)
    shutil.copy2(source/'integration/pt_digital_macro.sdc', out/'chip.sdc')
    config = json.loads((source/'verification/digital_hardening/config.json').read_text())
    names = [Path(p.removeprefix('dir::')).name for p in config['VERILOG_FILES']]
    if top.startswith('pt_dense_pair'):
        names.append('pt_dense_pair.sv')
    paired_boundary = top.startswith('pt_dense_pair_word_')
    if paired_boundary:
        names.extend(['pt_dense_pair_link.sv', 'pt_dense_pair_word.sv'])
    names = list(dict.fromkeys(names))
    verilog = ' '.join('/out/rtl/'+name for name in names)
    (out/'abc.constr').write_text('set_driving_cell gf180mcu_fd_sc_mcu7t5v0__buf_2\nset_load 0.02\n')
    script = f'''read_verilog -sv -DSYNTHESIS -I/out/rtl {verilog}
synth -top {top} -flatten -noabc
dfflibmap -liberty {LIBRARY}
abc -liberty {LIBRARY} -D {round(period*1000)} -constr /out/abc.constr
read_liberty -lib {LIBRARY}
clean
check -assert
autoname
tee -o /out/stat.json stat -json -liberty {LIBRARY}
write_verilog -noattr /out/mapped.v
'''
    (out/'synth.ys').write_text(script)
    if top == 'pt_digital_macro':
        constraints = 'set HWORD_PERIOD 3.2\nsource /out/chip.sdc\n'
    else:
        constraints = f'create_clock -name clk -period {period} [get_ports clk]\nset_clock_uncertainty 0.25 [all_clocks]\n'
        if paired_boundary:
            constraints += '''set divider_pins [get_pins -hierarchical *boundary.pair_clock_buffer/Z]
if {[llength $divider_pins] != 1} {error "Expected one physical pair-clock divider"}
create_generated_clock -name pair_clk -source [get_ports clk] -divide_by 2 $divider_pins
set_clock_uncertainty 0.25 [get_clocks pair_clk]
'''
            if top.endswith('_tx'):
                constraints += '''# Only the phase-enabled low-word capture reads launch_pair.
# The divider/word-select and capture window are proved by
# verification/formal/pt_pair_word_boundary.sby. Fast register paths remain 3.2 ns.
set launch_pins [get_cells -of_objects [get_pins -hierarchical *boundary.launch_pair*/Q]]
if {[llength $launch_pins] != 20} {error "Expected twenty paired launch bits"}
set_multicycle_path 2 -setup -end -from $launch_pins -to [get_clocks clk]
set_multicycle_path 1 -hold -end -from $launch_pins -to [get_clocks clk]
'''
        if boundary_delay is not None:
            data_clock = 'pair_clk' if paired_boundary and top.endswith('_tx') else 'clk'
            constraints += f'set_input_delay {boundary_delay} -clock {data_clock} [get_ports {{'+\
                ' '.join(['wire_data* iq_data* wire_pairs* iq_pairs* opcode* argument*'] if top.endswith('_tx') else
                         ['in_word* wire_ready iq_ready'] if paired_boundary else
                         ['in_pair* wire_ready iq_ready'])+'}]\n'
            if paired_boundary:
                outputs = 'out_word*' if top.endswith('_tx') else 'data* wire_count* iq_count* command_valid fault locked opcode* argument*'
                constraints += f'set_output_delay 0.5 -clock '+('clk' if top.endswith('_tx') else 'pair_clk')+f' [get_ports {{{outputs}}}]\n'
                if top.endswith('_tx'):
                    constraints += 'set_output_delay 0.5 -clock pair_clk [get_ports {wire_pop iq_pop}]\n'
            else:
                constraints += 'set_output_delay 0.5 -clock clk [all_outputs]\n'
    timing = f'''read_liberty {LIBRARY}
read_verilog /out/mapped.v
link_design {top}
{constraints}
set_input_transition 0.15 [all_inputs]
set_load 0.02 [all_outputs]
report_checks -path_delay max -group_path_count 2 -digits 4
report_checks -path_delay min -group_path_count 1 -digits 4
report_check_types -max_slew -max_capacitance -violators
check_setup -verbose
exit
'''
    (out/'timing.tcl').write_text(timing)
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    hashes.update({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                   [source/'integration/pt_digital_macro.sdc', source/'verification/digital_hardening/config.json',
                    Path(__file__).resolve()]})
    (out/'inputs.json').write_text(json.dumps(hashes, indent=2)+'\n')
    identity = subprocess.run(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}'],
                              check=True, capture_output=True, text=True).stdout.strip()
    command = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '4', '--memory', '8g',
               '-e', 'OMP_NUM_THREADS=1', '--entrypoint', '/bin/sh', '-v', f'{out}:/out', identity, '-c',
               f'set -eu; sha256sum {LIBRARY} > /out/library.sha256; yosys -Q -T -s /out/synth.ys > /out/synth.log 2>&1; sta -exit /out/timing.tcl > /out/timing.log 2>&1']
    subprocess.run(command, check=True)
    timing_log = (out/'timing.log').read_text()
    assert not re.search(r'(?im)^Error:|Tcl error|invalid command name|not a valid (?:start\s*point|end\s*point)', timing_log), 'STA constraint error; inspect timing.log'
    assert 'Path Type: max' in timing_log, 'STA produced no constrained setup paths'
    statistics = json.loads((out/'stat.json').read_text())
    stat = statistics.get('design', statistics['modules']['\\'+top])
    # Preserved phase-driver modules retain their own local flip-flops.
    # Count all leaf cells, excluding hierarchy instances and scope markers.
    hierarchical = {name.removeprefix('\\') for name in statistics['modules']}
    leaf_counts = {name: count for name, count in stat['num_cells_by_type'].items()
                   if name not in hierarchical and not name.startswith('$')}
    result = dict(status='mapped_screen_only', top=top, image_id=identity,
                  primary_clock_period_ns=period,
                  engine_period_ns=period*(2 if paired_boundary else 1),
                  word_period_ns=period if paired_boundary else None,
                  boundary_input_delay_ns=boundary_delay,
                  cell_area_um2=stat['area'], cell_count=sum(leaf_counts.values()),
                  sequential_cells=sum(v for k, v in leaf_counts.items() if '__dff' in k),
                  library_sha256=(out/'library.sha256').read_text().split()[0],
                  source_hashes=hashes,
                  artifact_hashes={name: hashlib.sha256((out/name).read_bytes()).hexdigest()
                                   for name in ['mapped.v', 'stat.json', 'timing.log', 'synth.log']},
                  excluded=['routed parasitics and clock tree', 'all-corner physical rate closure',
                            'macro footprint, DRC/LVS/antenna and full-chip assembly'])
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ['status', 'top', 'cell_area_um2', 'cell_count', 'sequential_cells']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=PROJECT)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--top', choices=['pt_digital_macro',
                                        'pt_dense_pair_tx', 'pt_dense_pair_rx',
                                        'pt_dense_pair_word_tx', 'pt_dense_pair_word_rx'], default='pt_digital_macro')
    parser.add_argument('--period', type=float, default=3.2)
    parser.add_argument('--boundary-delay', type=float)
    args = parser.parse_args()
    screen(args.source_dir.resolve(), args.output_dir.resolve(), args.top, args.period, args.boundary_delay)
