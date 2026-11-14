#!/usr/bin/env python3
"""Per-clock, per-corner signoff STA of the routed pt_digital_macro (OpenSTA).

For every available 3.3 V-class Liberty corner of gf180mcu_fd_sc_mcu7t5v0 and the matching
extracted SPEF (nom/min/max RC from LibreLane's OpenRCX step), with propagated (CTS) clocks:
  * worst setup and hold slack per capture clock at the SDC targets
    (integration/pt_digital_macro.sdc), plus total negative slack and violating endpoints;
  * fmax per clock domain by bisection of that clock's period (other clocks at target; for
    hword the DDR pin clock h2d follows as 2 x hword);
  * remaining timed clock-to-clock crossings (after the documented CDC exceptions);
  * host-link source-synchronous windows: D2H data and forwarded-clock arrival at the macro
    pins relative to the hword source, H2D capture setup/hold slack;
  * max slew / max capacitance violations.
Signoff is inside the operating envelope (22-32 C, 3.15-3.35 V; scratch/reviews/MANDATE.md).
The PDK's only in-window Liberty is tt_025C_3v30. In-window ss and ff are emulated on it with
the global derates defined in integration/pt_digital_macro.sdc (PT_TIMING_CORNER ss_window
1.54, ff_window 0.71). The out-of-window -40/125 C, 3.0/3.6 V libraries are not timing
criteria. Each reduced-rate fallback setting (debug.host_link.rate; HOST_RATE_DIV 1/2/4) is a
separate mode.
"""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path

LIB = '/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__{}.lib'
# Characterized in-window libraries (libchar.py): 'char:<pvt>' selects
# verification/digital_hardening/liberty/gf180mcu_fd_sc_mcu7t5v0__<pvt>.lib and turns the SDC envelope
# derate off (PT_LIB_CHARACTERIZED). PT_STA_LEGACY_DERATE=1 restores the former tt x 1.54 / 0.71 corners.
CHAR_LIB = str(Path(__file__).resolve().parent / 'liberty' / 'gf180mcu_fd_sc_mcu7t5v0__{}.lib')
CORNERS = [  # (name, liberty pvt, rc, envelope timing corner, host rate divider)
    ('ss32_window_max_rate1', 'char:ss_032C_3v15', 'max', 'ss_window', 1),
    ('ss22_window_max_rate1', 'char:ss_022C_3v15', 'max', 'ss_window', 1),
    ('tt_nom_rate1', 'tt_025C_3v30', 'nom', 'tt', 1),
    ('ff22_window_min_rate1', 'char:ff_022C_3v35', 'min', 'ff_window', 1),
    ('ff32_window_min_rate1', 'char:ff_032C_3v35', 'min', 'ff_window', 1),
    # r7: fast bound for hold = the foundry ff_n40C_3v60 library (133-cell subset, foundry_subset.py), as in the
    # SPI sign-off and the hardening flow's resizer corners; out of the window on purpose (bounds ff / 3.63 V / 0 C).
    ('ffn40_3v60_min_rate1', 'char:ff_n40C_3v60', 'min', 'ff_window', 1),
    # r7: per-chip supply trim point for slow dies (MANDATE 2026-11-14), characterized with libchar.py; the row is
    # skipped while the library file does not exist.
    ('ss32_3v50_max_rate1', 'char:ss_032C_3v50', 'max', 'ss_window', 1),
    ('ss32_window_max_rate2', 'char:ss_032C_3v15', 'max', 'ss_window', 2),
    ('ff22_window_min_rate2', 'char:ff_022C_3v35', 'min', 'ff_window', 2),
    ('ss32_window_max_rate4', 'char:ss_032C_3v15', 'max', 'ss_window', 4),
    ('ff22_window_min_rate4', 'char:ff_022C_3v35', 'min', 'ff_window', 4),
]
if os.environ.get('PT_STA_LEGACY_DERATE') == '1':
    CORNERS = [
        ('ss_window_max_rate1', 'tt_025C_3v30', 'max', 'ss_window', 1),
        ('tt_nom_rate1', 'tt_025C_3v30', 'nom', 'tt', 1),
        ('ff_window_min_rate1', 'tt_025C_3v30', 'min', 'ff_window', 1),
        ('ss_window_max_rate2', 'tt_025C_3v30', 'max', 'ss_window', 2),
        ('ff_window_min_rate2', 'tt_025C_3v30', 'min', 'ff_window', 2),
        ('ss_window_max_rate4', 'tt_025C_3v30', 'max', 'ss_window', 4),
        ('ff_window_min_rate4', 'tt_025C_3v30', 'min', 'ff_window', 4),
    ]


def lib_path(pvt):
    return CHAR_LIB.format(pvt[5:]) if pvt.startswith('char:') else LIB.format(pvt)


CORNERS = [c for c in CORNERS if not c[1].startswith('char:') or Path(lib_path(c[1])).exists()]
# On-chip variation. The SDC itself derates the CLOCK network early/late by PT_OCV (0.08) in every corner, so
# every `slack` below already contains it (with CRPR). `slack_ocv_all` additionally derates the DATA paths by the
# same +-PT_STA_OCV_ALL (late x(1+v), early x(1-v) on all cell and net delays): the sign-off view for hold at the
# fast corners and for setup at the slow corners. Target (NOTES r5 / spi_signoff.py): hold >= 0 in every domain in
# that view at BOTH fast libraries; SPI >= +0.15 ns.
OCV_ALL = float(os.environ.get('PT_STA_OCV_ALL', '0.08'))
# AC-1 host clocks (transport rework 2026-11-10): hword (pin, host DDR clock line/16), hddr (after the
# reduced-rate select: pad-edge DDR and gearboxes), hcore (hddr/2: 40-bit transport core); shared
# ingress/egress banks have mux clocks.
CLOCKS = ['sclk', 'ref', 'hword', 'hddr', 'hsdr', 'hcore', 'h2d_pin', 'h2d', 'h2d_cap', 'd2h_oddr', 'd2h_osel', 'd2h_fwd', 'ingress_wrx', 'ingress_rfrx', 'egress_wtx',
          'egress_rftx', 'egress_mem_sclk', 'wtx', 'wrx', 'rftx', 'rfhalf', 'rfrx', 'ctw', 'fc0', 'fc1', 'fc2', 'fc3', 'fc4', 'fc5', 'mon_host']
PERIOD_VAR = dict(sclk='SCLK_PERIOD', ref='REF_PERIOD', hword='HWORD_PERIOD', wtx='WTX_PERIOD', wrx='WRX_PERIOD',
                  rftx='RFTX_PERIOD', rfrx='RFRX_PERIOD', ctw='CTW_PERIOD', ctdet='CTDET_PERIOD',
                  fc0='FC_PERIOD')
FMAX_CLOCKS = ['hword', 'wtx', 'wrx', 'ctw', 'rftx', 'rfrx', 'sclk', 'ref', 'fc0']
# Generated host clocks are swept through the host DDR clock period: the reported value is the host
# DDR clock fmax that this domain allows (hddr runs at 1/HOST_RATE_DIV, hcore at half of that).
FMAX_DERIVED = [('hddr', 'HWORD_PERIOD'), ('hcore', 'HWORD_PERIOD')]

TCL = r'''
read_liberty {lib}
read_verilog {netlist}
link_design pt_digital_macro
read_spef {spef}
proc pt_load_sdc {{}} {{
  global PT_TIMING_CORNER PT_LIB_CHARACTERIZED HOST_RATE_DIV HLINK_PERIOD HDDR_PERIOD HCORE_PERIOD SCLK_PERIOD REF_PERIOD HWORD_PERIOD WTX_PERIOD WRX_PERIOD RFTX_PERIOD RFRX_PERIOD CTW_PERIOD CTDET_PERIOD FC_PERIOD H2D_PERIOD CTREF_PERIOD
  source {sdc}
  set_propagated_clock [all_clocks]
}}
proc pt_slack {{clk dly}} {{
  # intra-domain: launched and captured by the same clock (crossings are reported separately)
  if {{[llength [get_clocks -quiet $clk]] == 0}} {{ return "none" }}
  set ps [find_timing_paths -path_delay $dly -group_path_count 1 -endpoint_path_count 1 -sort_by_slack -from [get_clocks $clk] -to [get_clocks $clk]]
  if {{[llength $ps] == 0}} {{ return "none" }}
  set s [get_property [lindex $ps 0] slack]
  if {{$s eq "" || $s eq "INF"}} {{ return "none" }}
  return $s
}}
proc pt_xslack {{from to dly}} {{
  # launched by clock `from`, captured by `to` (pin I/O windows: h2d_pin -> h2d_cap, hddr -> d2h_fwd)
  if {{[llength [get_clocks -quiet $from]] == 0 || [llength [get_clocks -quiet $to]] == 0}} {{ return "none" }}
  set ps [find_timing_paths -path_delay $dly -group_path_count 1 -endpoint_path_count 1 -sort_by_slack -from [get_clocks $from] -to [get_clocks $to]]
  if {{[llength $ps] == 0}} {{ return "none" }}
  set s [get_property [lindex $ps 0] slack]
  if {{$s eq "" || $s eq "INF"}} {{ return "none" }}
  return $s
}}
proc pt_paths {{clk dly n}} {{
  set out {{}}
  if {{[llength [get_clocks -quiet $clk]] == 0}} {{ return $out }}
  foreach p [find_timing_paths -path_delay $dly -group_path_count $n -endpoint_path_count 1 -sort_by_slack -from [get_clocks $clk] -to [get_clocks $clk]] {{
    lappend out [list [get_property $p slack] [get_full_name [get_property $p startpoint]] [get_full_name [get_property $p endpoint]]]
  }}
  return $out
}}
set PT_TIMING_CORNER {tcorner}
set PT_LIB_CHARACTERIZED {charlib}
set HOST_RATE_DIV {rate}
proc pt_default_periods {{}} {{
  global PT_TIMING_CORNER HOST_RATE_DIV SCLK_PERIOD REF_PERIOD HWORD_PERIOD WTX_PERIOD WRX_PERIOD RFTX_PERIOD RFRX_PERIOD CTW_PERIOD CTDET_PERIOD FC_PERIOD H2D_PERIOD CTREF_PERIOD
  foreach v {{SCLK_PERIOD REF_PERIOD HWORD_PERIOD WTX_PERIOD WRX_PERIOD RFTX_PERIOD RFRX_PERIOD CTW_PERIOD CTDET_PERIOD FC_PERIOD H2D_PERIOD CTREF_PERIOD}} {{ catch {{unset $v}} }}
}}
pt_default_periods
pt_load_sdc
puts "PT_TARGETS [list sclk $SCLK_PERIOD ref $REF_PERIOD hword $HWORD_PERIOD h2d $H2D_PERIOD h2d_cap $H2D_PERIOD d2h_oddr $HDDR_PERIOD d2h_osel $HDDR_PERIOD d2h_fwd $HDDR_PERIOD hlink $HLINK_PERIOD hddr $HDDR_PERIOD hcore $HCORE_PERIOD ingress_wrx $WRX_PERIOD ingress_rfrx $RFRX_PERIOD egress_wtx $WTX_PERIOD egress_rftx $RFTX_PERIOD wtx $WTX_PERIOD wrx $WRX_PERIOD rftx $RFTX_PERIOD rfrx $RFRX_PERIOD ctw $CTW_PERIOD ctref $CTREF_PERIOD ctdet $CTDET_PERIOD]"
foreach c {{{clocks}}} {{
  puts "PT_SLACK $c [pt_slack $c max] [pt_slack $c min]"
  puts "PT_WORST_SETUP $c [list [pt_paths $c max 3]]"
  puts "PT_WORST_HOLD $c [list [pt_paths $c min 3]]"
}}
puts "PT_TNS [total_negative_slack -max] [total_negative_slack -min]"
# remaining timed crossings between different clocks
foreach a [all_clocks] {{
  foreach b [all_clocks] {{
    if {{[get_name $a] eq [get_name $b]}} continue
    set ps [find_timing_paths -path_delay max -group_path_count 1 -sort_by_slack -from $a -to $b]
    if {{[llength $ps]}} {{
      set p [lindex $ps 0]; set s [get_property $p slack]
      if {{$s ne "" && $s ne "INF"}} {{
        puts "PT_XING [get_name $a] [get_name $b] $s [get_full_name [get_property $p startpoint]] [get_full_name [get_property $p endpoint]]"
      }}
    }}
  }}
}}
# host link: D2H pin arrival windows relative to the hword source edge
proc pt_arr {{pins dly}} {{
  set v {{}}
  foreach pin $pins {{
    set ps [find_timing_paths -path_delay $dly -to $pin -group_path_count 4 -endpoint_path_count 4 -unique_paths_to_endpoint]
    foreach p $ps {{ lappend v [get_property [lindex [get_property $p points] end] arrival] }}
  }}
  return $v
}}
puts "PT_D2H_DATA_MAX [pt_arr [get_ports d2h_pin*] max]"
puts "PT_D2H_DATA_MIN [pt_arr [get_ports d2h_pin*] min]"
puts "PT_D2H_CLK_MAX [pt_arr [get_ports d2h_clk_pin] max]"
puts "PT_D2H_CLK_MIN [pt_arr [get_ports d2h_clk_pin] min]"
puts "PT_H2D_SETUP [pt_xslack h2d_pin h2d_cap max] PT_H2D_HOLD [pt_xslack h2d_pin h2d_cap min]"
puts "PT_D2HW_SETUP [pt_xslack d2h_osel d2h_fwd max] PT_D2HW_HOLD [pt_xslack d2h_osel d2h_fwd min]"
puts "PT_WNS_ALL [sta::worst_slack_cmd max] [sta::worst_slack_cmd min]"
report_check_types -max_slew -max_capacitance -violators > {out}/{corner}.drv.rpt
report_checks -path_delay max -group_path_count 1 -format full_clock_expanded -digits 3 > {out}/{corner}.setup.rpt
report_checks -path_delay min -group_path_count 1 -format full_clock_expanded -digits 3 > {out}/{corner}.hold.rpt
report_clock_skew -setup > {out}/{corner}.skew.rpt
report_clock_latency > {out}/{corner}.latency.rpt
# fmax per clock by bisection (setup slack >= 0 on paths captured by that clock)
foreach {{c var}} {{{fmax}}} {{
  pt_default_periods
  set lo 0.5; set hi 400.0
  while {{$hi - $lo > 0.02 * $hi}} {{
    set m [expr {{($lo + $hi) / 2.0}}]
    pt_default_periods; set $var $m
    pt_load_sdc
    set s [pt_slack $c max]
    if {{$s eq "none" || $s >= 0}} {{ set hi $m }} else {{ set lo $m }}
  }}
  puts "PT_FMAX $c $hi"
}}
# OCV on all delays (data as well as clock), at the SDC targets; last, because the derate persists
pt_default_periods
pt_load_sdc
set_timing_derate -early [expr {{1.0 - {ocv}}}]
set_timing_derate -late  [expr {{1.0 + {ocv}}}]
foreach c {{{clocks}}} {{
  puts "PT_SLACK_OCV $c [pt_slack $c max] [pt_slack $c min]"
}}
puts "PT_H2D_OCV [pt_xslack h2d_pin h2d_cap max] [pt_xslack h2d_pin h2d_cap min]"
puts "PT_D2HW_OCV [pt_xslack d2h_osel d2h_fwd max] [pt_xslack d2h_osel d2h_fwd min]"
puts "PT_WNS_ALL_OCV [sta::worst_slack_cmd max] [sta::worst_slack_cmd min]"
report_checks -path_delay min -group_path_count 5 -format full_clock_expanded -digits 3 > {out}/{corner}.hold_ocv.rpt
report_checks -path_delay max -group_path_count 5 -format full_clock_expanded -digits 3 > {out}/{corner}.setup_ocv.rpt
'''


def run_corner(name, pvt, rc, tcorner, rate, run, sdc, out):
    netlist = next((run / 'final/nl').glob('*.nl.v'))
    spefs = sorted((run / 'final/spef').rglob('*.spef'))
    spef = next((s for s in spefs if f'{rc}_' in s.parent.name or s.parent.name == rc or f'.{rc}' in s.name), spefs[0])
    fmax = ' '.join([f'{c} {PERIOD_VAR[c]}' for c in FMAX_CLOCKS]+[f'{c} {v}' for c, v in FMAX_DERIVED])
    tcl = TCL.format(lib=lib_path(pvt), netlist=netlist, spef=spef, sdc=sdc, clocks=' '.join(CLOCKS), fmax=fmax,
                     out=out, corner=name, tcorner=tcorner, rate=rate, charlib=int(pvt.startswith('char:')), ocv=OCV_ALL)
    (out / f'{name}.tcl').write_text(tcl)
    r = subprocess.run(['sta', '-no_init', '-exit', str(out / f'{name}.tcl')], capture_output=True, text=True)
    (out / f'{name}.log').write_text(r.stdout + r.stderr)
    res = dict(timing_corner=tcorner, host_rate_div=rate, liberty=lib_path(pvt).rsplit('/', 1)[1], spef=str(spef).split('/final/')[-1], netlist=netlist.name,
               slack={}, slack_ocv_all={}, ocv_all=OCV_ALL, worst_setup={}, worst_hold={}, crossings=[], fmax_mhz={}, rc=r.returncode)
    for ln in r.stdout.splitlines():
        t = ln.split()
        if not t:
            continue
        if t[0] == 'PT_TARGETS':
            it = t[1:]
            res['targets_ns'] = {it[i]: float(it[i + 1]) for i in range(0, len(it), 2)}
        elif t[0] == 'PT_SLACK':
            res['slack'][t[1]] = dict(setup=None if t[2] == 'none' else float(t[2]),
                                      hold=None if t[3] == 'none' else float(t[3]))
        elif t[0] == 'PT_SLACK_OCV':
            res['slack_ocv_all'][t[1]] = dict(setup=None if t[2] == 'none' else float(t[2]),
                                              hold=None if t[3] == 'none' else float(t[3]))
        elif t[0] in ('PT_H2D_OCV', 'PT_D2HW_OCV'):
            res['h2d_capture_ocv_all' if t[0] == 'PT_H2D_OCV' else 'd2h_window_ocv_all'] = dict(setup=t[1], hold=t[2])
        elif t[0] == 'PT_WNS_ALL_OCV':
            res['worst_slack_all_paths_ocv_all'] = dict(setup=float(t[1]), hold=float(t[2]))
        elif t[0] in ('PT_WORST_SETUP', 'PT_WORST_HOLD'):
            res['worst_setup' if 'SETUP' in t[0] else 'worst_hold'][t[1]] = ln.split(None, 2)[2][:600]
        elif t[0] == 'PT_TNS':
            res['tns'] = dict(setup=float(t[1]), hold=float(t[2]))
        elif t[0] == 'PT_XING':
            res['crossings'].append(dict(launch=t[1], capture=t[2], slack=float(t[3]), start=t[4], end=t[5]))
        elif t[0] == 'PT_D2HW_SETUP':
            res['d2h_window'] = dict(setup=t[1], hold=t[3])
        elif t[0].startswith('PT_D2H'):
            res[t[0][3:].lower()] = [float(x) for x in t[1:]]
        elif t[0] == 'PT_WNS_ALL':
            res['worst_slack_all_paths'] = dict(setup=float(t[1]), hold=float(t[2]))
        elif t[0] == 'PT_H2D_SETUP':
            res['h2d_capture'] = dict(setup=t[1], hold=t[3])
        elif t[0] == 'PT_FMAX':
            res['fmax_mhz'][t[1]] = round(1000.0 / float(t[2]), 1)
    drv = (out / f'{name}.drv.rpt').read_text() if (out / f'{name}.drv.rpt').exists() else ''
    res['max_slew_cap_violators'] = len(re.findall(r'\(VIOLATED\)', drv))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    ap.add_argument('--sdc', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    run, out = Path(a.run), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    v = subprocess.run(['sta', '-version'], capture_output=True, text=True).stdout.strip()
    report = dict(tool=f'OpenSTA {v}', corners={})
    only = os.environ.get('PT_STA_CORNERS')   # comma list of corner names (default: all)
    for name, pvt, rc, tcorner, rate in CORNERS:
        if only and name not in only.split(','):
            continue
        report['corners'][name] = run_corner(name, pvt, rc, tcorner, rate, run, a.sdc, out)
        c = report['corners'][name]
        print(name, json.dumps(c['slack']), json.dumps(c['fmax_mhz']), flush=True)
    (out / 'sta-report.json').write_text(json.dumps(report, indent=1) + '\n')


if __name__ == '__main__':
    main()
