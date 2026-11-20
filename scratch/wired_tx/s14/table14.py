"""s14 result tables (chain/results/*.json rows, cal/res/*.json calibrations) -> markdown on stdout"""
import json, glob
from pathlib import Path
H = Path(__file__).resolve().parent
print('| row | Gb/s | corner | VDD | pess | ring | pad | S | netlist sha256[:12] | ilk bypass | ideal phases | codes | far errors / bits | eye V | eye UI | I mA | result |')
print('|' + '---|' * 17)
for f in sorted(glob.glob(str(H / 'chain/results/*.json'))):
    o = json.load(open(f)); fr = o.get('far') or {}
    print('| ' + ' | '.join(str(x) for x in (o['tag'], fr.get('rate_gbps', '-'), o['corner'], o['vdd'], o.get('pess'), o.get('ring'), o.get('padm'), o.get('S'),
          (o.get('net_sha256') or '')[:12], o.get('ilk_bypass'), bool(o.get('ideal_phases')), o.get('codes'), f"{fr.get('errors', '-')} / {fr.get('bits', '-')}",
          fr.get('eye_h_v', '-'), fr.get('eye_w_ui', '-'), o.get('i_avg_ma', '-'), ('PASS' if o.get('ok') else 'FAIL') + (' ' + o['reason'] if o.get('reason') else ''))) + ' |')
print('\n| cal | corner | VDD | pess | netlist sha256[:12] | codes in | slot error ps (DC method) | slot error ps (probe) | worst ps | next codes | gain ratio |')
print('|' + '---|' * 11)
for f in sorted(glob.glob(str(H / 'cal/res/*.json'))):
    o = json.load(open(f)); m = o['meas']
    print('| ' + ' | '.join(str(x) for x in (o['tag'], o['corner'], m.get('vdd', ''), o['pess'], (o.get('net_sha256') or '')[:12], o['codes_in'], o['slot_err_ps'],
          m.get('probe_slot_err_ps'), o['worst_slot_ps'], o['codes'], o['gain_ratio'])) + ' |')
