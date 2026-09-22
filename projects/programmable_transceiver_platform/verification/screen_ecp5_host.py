"""Necessary host rate screen only; no board timing or compatibility proof."""
import hashlib
import json
from fractions import Fraction
from check_contract import CONTRACT, ceil


def screen(c):
    t = c['transport']
    available = t['frame_words'] - t['control_words']
    profiles = {}
    for name, p in t['profiles'].items():
        # Clock is forwarded in both directions, including SDR profiles.
        profiles[name] = {
            'd2h_within_documented_input_clock_limit': p['clock_hz'] <= 200_000_000,
            'h2d_within_documented_output_clock_limit': p['clock_hz'] <= 150_000_000,
            'qualified': False,
        }
    alternatives = []
    for mode in c['modes']:
        # Hypothetical 150 MHz DDR: not added to the design contract.
        slot_rate = Fraction(150_000_000 * 2 * t['word_bits'], t['frame_words'])
        slot_rate *= Fraction(1_000_000 - t['host_slow_ppm'], 1_000_000)
        allocation = {s['id']: ceil(Fraction(s['rate_bps']) *
                      Fraction(1_000_000 + t['source_fast_ppm'], 1_000_000) / slot_rate)
                      for s in mode['sources']}
        totals = {d: sum(allocation[s['id']] for s in mode['sources'] if d in s['directions'])
                  for d in ('d2h', 'h2d')}
        alternatives.append({'mode': mode['id'], 'reserved_slots': allocation,
                             'slots_per_direction': totals,
                             'fits': all(n <= available for n in totals.values())})
    return {'scope': 'necessary frequency and bandwidth screen; not electrical qualification',
            'source': {'url': 'https://www.latticesemi.com/view_document?document_id=50461',
                       'revision': 'FPGA-DS-02012-3.4, September 2025',
                       'tables': ['3.21', '3.44'],
                       'pdf_sha256': '26570f8bb2b800123120829cacd75d818d7a985d573797610521b5bda2e293c3'},
            'contract_sha256': hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
            'profiles': profiles, 'hypothetical_ddr150': alternatives}


if __name__ == '__main__':
    print(json.dumps(screen(json.loads(CONTRACT.read_text())), indent=2))
