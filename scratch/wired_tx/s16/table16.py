"""s16 result tables (results/*.json rows, cal/res/*.json calibrations) -> markdown on stdout.  Limits: ../s13/LIMITS.md."""
import json, glob
from pathlib import Path
H = Path(__file__).resolve().parent
print('| row | Gb/s line | n | corner | VDD | T | pess | ring | route | pad | pad sha256[:10] | S | netlist sha256[:12] | control | codes (cal, verified) | far errors / bits | eye V | eye UI | I mA | run@ns | result |')
print('|' + '---|' * 21)
for f in sorted(glob.glob(str(H / 'results/*.json'))):
    o = json.load(open(f))
    if 'corner' not in o:
        continue
    fr = o.get('far') or {}
    ctl = ('kill %s' % o['kill'] if o.get('kill') is not None else '') + ('stuck %s' % o['stuck'] if o.get('stuck') is not None else '')
    print('| ' + ' | '.join(str(x) for x in (
        o['tag'], fr.get('rate_gbps', round(o.get('target_rate', 0) / 1e9 / o.get('n_over', 1), 3)), o.get('n_over', 1), o['corner'], o['vdd'], o.get('temp'),
        o.get('pess'), o.get('ring'), o.get('route'), o.get('padm'), (o.get('pad_sha256') or '')[:10], o.get('S'), (o.get('net_sha256') or '')[:12], ctl,
        f"{o.get('codes')} ({o.get('codes_cal', '-')}, {o.get('codes_verified', '-')})", f"{fr.get('errors', '-')} / {fr.get('bits', '-')}",
        fr.get('eye_h_v', '-'), fr.get('eye_w_ui', '-'), o.get('i_avg_ma', '-'), o.get('t_run_ns'),
        ('PASS' if o.get('ok') else 'FAIL') + (' ' + o['reason'] if o.get('reason') else ''))) + ' |')
print('\n| cal | corner | VDD | Gb/s | pess | route | netlist sha256[:12] | codes in | slot error ps (DC method) | slot error ps (probe) | worst ps | <= 8 ps | next codes | gain ratio |')
print('|' + '---|' * 14)
for f in sorted(glob.glob(str(H / 'cal/res/*.json'))):
    o = json.load(open(f)); m = o['meas']
    print('| ' + ' | '.join(str(x) for x in (o['tag'], o['corner'], o.get('vdd'), round(o.get('rate', 0) / 1e9, 3), o['pess'], o.get('route_ohm_F'),
          (o.get('net_sha256') or '')[:12], o['codes_in'], o['slot_err_ps'], m.get('probe_slot_err_ps'), o['worst_slot_ps'], o['residual_ok'], o['codes'],
          o['gain_ratio'])) + ' |')
sp = [json.load(open(f)) for f in glob.glob(str(H / 'results/sp*.json'))]
for o in sp:
    print(f"\nsanity {o['tag']}: TX_RUN rises at {o.get('t_run_ns')} ns, gate {o.get('gate_pp_v')} V pp, pad {o.get('pad_pp_v')} V pp, "
          f"XE0 {o.get('xe0_pp_v')} V pp, {o.get('i_ma')} mA, netlist {o.get('net_sha256', '')[:12]}, route {o.get('route')}")
