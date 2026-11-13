#!/usr/bin/env python3
"""SPI-only timing sign-off of pt_digital_macro (integration-plan G6).

SCLK-domain STA with a model of the top-level routes between the south SPI pads (bidir[10..13]) and the
macro, and the provider pad cells, at two bounding corners:
  slow  sc ss_125C_3v00 + io ss_125C_2v97   bounds ss / 3.15 V / 85 C   (hotter and lower supply: slower)
  fast  sc ff_n40C_3v60 + io ff_n40C_3v63   bounds ff / 3.63 V / 0 C    (colder: faster; sc supply 0.03 V
        lower, < 1 % against the ~8 % of the extra 40 C)
  typ   tt_025C_3v30 (information)
The PDK publishes no library at 85 C / 0 C; the two published wide corners enclose the requested ones.

Route model (two-sided, every value an assumption listed in ASSUME): lumped pad load C_wire + C_pin from
the pad Liberty (PAD -> Y of bi_24t, A -> PAD of bi_t PDRV=10 SL=0, extracted by pad.tcl into
pad_delays.json) plus the Elmore delay R (C_wire / 2 + C_pin) of the wire. The input skew between SCLK and
MOSI/CS_N takes one route at the LOW and the other at the HIGH bound (worst for both setup and hold).

Usage: spi_signoff.py --odb <post-CTS odb> --sdc <sdc> --pads <pad_delays.json> --out <dir> [--periods ...]
"""
import argparse
import json
import math
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
IMAGE = 'svalbard/librelane-gf180-guarded:2026.11'
SC = '/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__{}.lib'
CORNERS = {  # name: (sc lib, io lib key in pad_delays.json, tech-LEF RC corner, RC scale of the macro wires)
    'slow': ('ss_125C_3v00', 'ss_125C_2v97', 'max', 1.25),
    'typ': ('tt_025C_3v30', 'tt_025C_3v30', 'nom', 1.0),
    # in-window slow corner (characterized Liberty, MANDATE performance window); pads at the wide slow bound
    'ss32': ('char:ss_032C_3v15', 'ss_125C_2v97', 'max', 1.25),
    'ff22': ('char:ff_022C_3v35', 'ff_n40C_3v63', 'min', 0.8),   # in-window fast corner (characterized), pads at the wide fast bound
    'fast': ('ff_n40C_3v60', 'ff_n40C_3v63', 'min', 0.8),
}
ASSUME = dict(
    route_mm=[2.6, 3.5],              # v6 floorplan estimate 2.6 mm; high bound with a detour
    wire_r_ohm=[50.0, 1400.0],        # wide Metal5 (0.02 ohm/um) .. min-width Metal2 at 3.5 mm (0.39 ohm/um)
    wire_c_pf=[0.19, 1.0],            # 0.19: 2.6 mm x 0.073 fF/um (isolated wide) .. 1.0: 3.5 mm x 0.29 fF/um (2x coupling)
    macro_pin_c_pf=[0.01, 0.05],
    pad_a_pin_c_pf=0.037,
    pad_in_transition_ns=[0.3, 5.0],  # host edge at the die pad (COB + connector)
    miso_board_load_pf=[5.0, 30.0],
    host_tco_ns=[-2.0, 5.0],          # MOSI/CS_N change relative to the SCLK fall, both at the die pads
    host_miso_setup_ns=5.0,           # host setup to its sampling SCLK rise
    host_round_trip_ns=3.0,           # 2 x 1.5 ns board/cable flight (SCLK out, MISO back)
    host_miso_hold_ns=2.0,
    miso_a_transition_ns=[0.2, 3.0],
)


def pad_model(pads, io):
    t = pads[io]
    A = ASSUME
    r_lo, r_hi = A['wire_r_ohm']
    c_lo, c_hi = A['wire_c_pf']
    p_lo, p_hi = A['macro_pin_c_pf']
    el_lo = r_lo*(c_lo/2+p_lo)*1e-3      # ohm * pF = ps -> ns
    el_hi = r_hi*(c_hi/2+p_hi)*1e-3
    tr_lo, tr_hi = A['pad_in_transition_ns']
    # table points: load 0.2 pF (low) and 1.05 pF (high)
    lo = [t[f'IN {tr_lo} 0.2 {e}'] for e in ('rise', 'fall')]
    hi = [t[f'IN {tr_hi} 1.05 {e}'] for e in ('rise', 'fall')]
    d_min = min(v[0] for v in lo)+el_lo
    d_max = max(v[0] for v in hi)+el_hi
    s_min = min(v[1] for v in lo)
    s_max = math.hypot(max(v[1] for v in hi), 2.2*el_hi)
    b_lo, b_hi = A['miso_board_load_pf']
    a_lo, a_hi = A['miso_a_transition_ns']
    o_min = min(t[f'OUT {a_lo} {b_lo:g} {e}'][0] for e in ('rise', 'fall'))+r_lo*(c_lo/2+A['pad_a_pin_c_pf'])*1e-3
    o_max = max(t[f'OUT {a_hi} {b_hi:g} {e}'][0] for e in ('rise', 'fall'))+r_hi*(c_hi/2+A['pad_a_pin_c_pf'])*1e-3
    return dict(in_delay_ns=[d_min, d_max], in_slew_ns=[s_min, s_max], out_delay_ns=[o_min, o_max],
                wire_elmore_ns=[el_lo, el_hi])


def run(args, corner, period, pm, host):
    sc, io, tlef, rcs = CORNERS[corner]
    A = ASSUME
    skew = pm['in_delay_ns'][1]-pm['in_delay_ns'][0]
    hb = (A['host_miso_setup_ns']+A['host_round_trip_ns']) if host else 0.0
    sclib = f'/src/verification/digital_hardening/liberty/gf180mcu_fd_sc_mcu7t5v0__{sc[5:]}.lib' if sc.startswith('char:') else SC.format(sc)
    env = dict(SCLIB=sclib, SDC='/sdc/'+Path(args.sdc).name, P=period, TLEF=tlef, RCSCALE=rcs,
               IN_MAX=A['host_tco_ns'][1]+skew, IN_MIN=A['host_tco_ns'][0]-skew,
               OUT_MAX=pm['in_delay_ns'][1]+pm['out_delay_ns'][1]+hb,
               OUT_MIN=pm['in_delay_ns'][0]+pm['out_delay_ns'][0]-A['host_miso_hold_ns'],
               DE=1-args.ocv, DL=1+args.ocv,
               TR_MIN=pm['in_slew_ns'][0], TR_MAX=pm['in_slew_ns'][1],
               CL=A['wire_c_pf'][1]+A['pad_a_pin_c_pf'] if corner not in ('fast', 'ff22') else A['wire_c_pf'][0]+A['pad_a_pin_c_pf'])
    mounts = ['-v', f'{PROJECT}:/src:ro', '-v', f'{Path(args.sdc).resolve().parent}:/sdc:ro']
    if args.odb:
        env['ODB'] = '/db/'+Path(args.odb).name
        mounts += ['-v', f'{Path(args.odb).resolve().parent}:/db:ro']
        tool = 'openroad -no_init -exit'
    else:
        env.update(NL='/db/'+Path(args.nl).name, SPEF='/spef/'+Path(args.spef.format(rc=tlef)).name)
        mounts += ['-v', f'{Path(args.nl).resolve().parent}:/db:ro', '-v', f'{Path(args.spef.format(rc=tlef)).resolve().parent}:/spef:ro']
        tool = 'sta -no_init -exit'
    tag = f'{corner}_p{period:g}_{"host" if host else "chip"}'
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '1', '--memory', '8g', '-e', 'HOME=/tmp']
    for k, v in env.items():
        cmd += ['-e', f'{k}={v}']
    cmd += mounts+['--entrypoint', '/bin/bash', IMAGE, '-lc', f'{tool} /src/verification/digital_hardening/spi_signoff.tcl']
    log = subprocess.run(cmd, capture_output=True, text=True)
    (Path(args.out)/f'{tag}.log').write_text(log.stdout+log.stderr)
    res = {}
    for m in re.finditer(r'^R (max|min) (\w+)\s+(\S+)(.*)$', log.stdout, re.M):
        res[f'{m[1]}:{m[2]}'] = None if m[3] == 'none' else dict(slack=float(m[3]), path=m[4].strip())
    assert len(res) == 12, (tag, 'STA failed, see log')
    clocks = re.search(r'^SPI_CLOCKS (.*)$', log.stdout, re.M)
    assert clocks and clocks[1].split()[0] == 'sclk', (tag, 'sclk clock not found')
    for k in ('max:reg2reg', 'max:in2reg', 'max:miso', 'min:reg2reg', 'min:in2reg', 'min:miso'):
        assert res[k] is not None, (tag, k, 'no timed path: the check would pass vacuously')
    return tag, dict(corner=corner, period_ns=period, host_budget=host, constraints=env, slacks=res)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--odb'); ap.add_argument('--nl'); ap.add_argument('--spef')
    ap.add_argument('--sdc', required=True); ap.add_argument('--pads', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--periods', default='200,100,50,40,30,25,20')
    ap.add_argument('--corners', default='slow,typ,fast')
    ap.add_argument('--jobs', type=int, default=6)
    # On-chip variation (two-sided: early = 1 - ocv, late = 1 + ocv on every cell and net delay, CRPR on).
    # 0.08 = RSS of ~5 % local device mismatch of a clock-buffer delay in 180 nm and ~5-6 % from a supply
    # difference of up to the 117 mV drop budget between two branches (delay ~ 1.5 x dV/V), rounded up.
    ap.add_argument('--ocv', type=float, default=0.08)
    args = ap.parse_args()
    assert args.odb or (args.nl and args.spef), 'give --odb, or --nl and --spef'
    Path(args.out).mkdir(parents=True, exist_ok=True)
    pads = json.loads(Path(args.pads).read_text())
    models = {c: pad_model(pads, CORNERS[c][1]) for c in args.corners.split(',')}
    jobs = [(c, float(p), h) for c in models for p in args.periods.split(',') for h in (False, True)]
    with ThreadPoolExecutor(args.jobs) as ex:
        results = dict(ex.map(lambda j: run(args, j[0], j[1], models[j[0]], j[2]), jobs))
    summary = {}
    for c in models:
        for h in (False, True):
            rows = sorted((r for r in results.values() if r['corner'] == c and r['host_budget'] == h), key=lambda r: r['period_ns'])
            ok = [r['period_ns'] for r in rows if all(v is None or v['slack'] >= 0 for k, v in r['slacks'].items() if k.startswith('max:'))]
            # passing periods must be contiguous from the top (setup slack is monotonic in the period)
            hold_ok = all(v is None or v['slack'] >= 0 for r in rows for k, v in r['slacks'].items() if k.startswith('min:'))
            if not hold_ok:
                ok = []   # hold does not depend on the period: no SCLK rate is safe at this corner
            summary[f'{c}:{"host" if h else "chip"}'] = dict(
                hold_met=hold_ok,
                min_passing_period_ns=min(ok) if ok else None,
                max_sclk_mhz=round(1000/min(ok), 2) if ok else None,
                worst_hold_ns=min(v['slack'] for r in rows for k, v in r['slacks'].items() if k.startswith('min:') and v),
                hold_limited_periods=[r['period_ns'] for r in rows if any(v and v['slack'] < 0 for k, v in r['slacks'].items() if k.startswith('min:'))])
    out = dict(ocv_derate=args.ocv, source=dict(odb=args.odb, nl=args.nl, spef=args.spef, sdc=args.sdc), assumptions=ASSUME, corners=CORNERS,
               pad_route_model=models, summary=summary, runs=results)
    (Path(args.out)/'spi-signoff.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(dict(pad_route_model=models, summary=summary), indent=1))


if __name__ == '__main__':
    main()
