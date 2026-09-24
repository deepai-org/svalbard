#!/usr/bin/env python3
"""Fixed-environment integration screen; external LO/passives, schematic only."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

BASE = Path('/src/rf_rx_external_lo_parent')
sys.path.insert(0, str(BASE))
from run_parent import fill

OUT = Path('/work')
TEMPLATE = BASE / 'parent_tb.spice.in'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

from rf_measure import projection

cases = []
for corner in ('typical', 'ff', 'ss'):
    for amplitude in (0.0, .001, .010):
        name = f'{corner}_{amplitude:g}'
        data = OUT / f'{name}.dat'
        deck = fill(TEMPLATE.read_text(), {
            'MOS_CORNER': corner, 'DUT_INCLUDE': str(BASE/'rf_rx_external_lo_parent.spice'),
            'DUT_SUBCKT': 'wifi_rx_external_lo_parent', 'TEMP_C': '27',
            'VDD_V': '3.3', 'LO_HIGH_V': '3.3', 'WAVE_DATA': str(data),
        })
        deck = deck.replace('SIN(0 10m 2.4gig)', f'SIN(0 {amplitude} 2.4gig)')
        # Exact 2.3 GHz period, complementary LO; preserve finite 10 ps edges.
        deck = deck.replace('207p 434.783p', '207.391304347826p 434.782608695652p')
        deck = deck.replace('217.391p', '217.391304347826p')
        deck = deck.replace('tran 1p 80n 40n', 'set numdgt=15\ntran 1p 101n 0 1p')
        deck = deck.replace(' if_diff\n', ' if_diff v(MIX_RF) v(LNA_SOURCE) i(VDD)\n')
        path = OUT / f'{name}.spice'
        path.write_text(deck)
        with (OUT/f'{name}.log').open('w') as log:
            run = subprocess.run(['ngspice', '-b', str(path)], stdout=log,
                                 stderr=subprocess.STDOUT, timeout=300)
        assert run.returncode == 0, name
        points = []
        for line in data.read_text().splitlines()[1:]:
            row = tuple(map(float, line.split()))
            assert len(row) == 5 and all(map(math.isfinite, row))
            points.append(row)
        assert points[0][0] <= 1e-12 and points[-1][0] >= 100e-9
        ph = [projection(points, 1, start, stop, 100e6)
              for start, stop in ((40e-9, 60e-9), (60e-9, 80e-9), (80e-9, 100e-9))]
        last = [row for row in points if row[0] >= 80e-9]
        cases.append(dict(process=corner, input_peak_v=amplitude, sample_count=len(points),
                          if_phasors_v=[[z.real,z.imag] for z in ph],
                          mixer_rf_range_v=[min(r[2] for r in last),max(r[2] for r in last)],
                          source_range_v=[min(r[3] for r in last),max(r[3] for r in last)],
                          deck_sha256=digest(path)))
        print(name, abs(ph[-1]), flush=True)

summaries = []
for corner in ('typical', 'ff', 'ss'):
    rows = [c for c in cases if c['process'] == corner]
    zero = complex(*rows[0]['if_phasors_v'][-1])
    gains = []
    for row in rows[1:]:
        ph = [complex(*v) for v in row['if_phasors_v']]
        gain = abs(ph[-1]-zero)/row['input_peak_v']
        gains.append(gain)
        row['baseline_subtracted_conversion_gain_v_per_v'] = gain
        row['last_window_phasor_change_relative'] = abs(ph[-1]-ph[-2])/abs(ph[-1]-zero)
    summaries.append(dict(process=corner, zero_input_if_peak_v=abs(zero),
                          gain_at_1mv=gains[0], gain_at_10mv=gains[1],
                          gain_change_db=20*math.log10(gains[1]/gains[0])))
result = dict(schema_version=1, status='simulation_completed_not_receiver_qualified',
              supply_v=3.3, temperature_c=27, rf_hz=2.4e9, lo_hz=2.3e9, if_hz=100e6,
              image='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305',
              assumptions=['schematic GF180 compact models', 'ideal external bias and LO sources',
                           'external resistors and capacitors from existing parent bench',
                           'single real IF, not integrated I/Q or target ADC architecture'],
              cases=cases, summaries=summaries,
              source_sha256={str(p):digest(p) for p in (
                  Path(__file__).with_name('rf_measure.py'), TEMPLATE, BASE/'run_parent.py', BASE/'rf_rx_external_lo_parent.spice',
                  Path('/src/rf_lna/lna_cs_core.spice'), Path('/src/rf_switch_mixer/mixer.spice'),
                  Path(__file__))})
(OUT/'result.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(summaries, indent=2))
