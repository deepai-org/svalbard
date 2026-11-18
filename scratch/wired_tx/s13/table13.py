"""result table of the session-13 real chain (resultsC/*.json) -> markdown on stdout"""
import json, glob
rows = []
for f in sorted(glob.glob('resultsC/*.json')):
    o = json.load(open(f)); fr = o.get('far') or {}
    rate = fr.get('rate_gbps') or round(o.get('target_rate', 0) / 1e9 / o.get('n_over', 1), 3)
    rows.append((o['tag'], rate, o.get('n_over', 1), o['corner'], o['vdd'], 'pess' if o.get('pess') else 'nom', o.get('ring', ''), o.get('padm', 'pad=C'),
                 'top' if o.get('top_ext') else ('mux ext' if o.get('mux_ext') else 'mux sch'), str(o.get('codes')), o.get('kill'),
                 f"{fr.get('errors', '-')} / {fr.get('bits', '-')}", fr.get('eye_h_v', '-'), fr.get('eye_w_ui', '-'), o.get('i_avg_ma', '-'),
                 'PASS' if o.get('ok') else 'FAIL', o.get('reason') or ''))
print('| run | line Gb/s | core bits / line bit | corner | VDD | values | ring | pad | netlist | trim codes | kill | far errors / bits | eye V | eye UI | I mA | result | note |')
print('|' + '---|' * 17)
for r in rows:
    print('| ' + ' | '.join(str(x) if x is not None else '' for x in r) + ' |')
