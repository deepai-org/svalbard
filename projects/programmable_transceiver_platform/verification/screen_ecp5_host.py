"""Necessary host rate screen only; no board timing or compatibility proof."""
import hashlib
import json
import argparse
from fractions import Fraction
from check_contract import CONTRACT, ceil


def screen(c, queues=False):
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
    exclusive = []
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
        for source in mode['sources']:
            minimum_clock = (Fraction(source['rate_bps'] * t['frame_words'],
                                     2 * t['word_bits'] * available) *
                             Fraction(1_000_000 + t['source_fast_ppm'],
                                      1_000_000 - t['host_slow_ppm']))
            row=dict(mode=mode['id'], active_source=source['id'],
                reserved_slots=allocation[source['id']], available_slots=available,
                fits=allocation[source['id']] <= available,
                minimum_ddr_clock_hz=float(minimum_clock),
                requires_exclusive_slot_reallocation=True,
                implemented=False, electrical_qualification=False)
            if queues:
                from transport_model import schedule, simulate
                cfg=t['scheduling']
                slots=schedule({source['id']:allocation[source['id']]},
                    frame_words=t['frame_words'],control_slots=cfg['control_slots'])
                cases=[]
                for phase in (Fraction(0),Fraction(1,4),Fraction(1,2),Fraction(999,1000)):
                    cases.append(simulate(slots,source['id'],
                        Fraction(source['rate_bps']*(1_000_000+t['source_fast_ppm']),1_000_000),
                        source['sample_bits'],Fraction(300_000_000*(1_000_000-t['host_slow_ppm']),1_000_000),
                        phase=phase,frames=cfg['simulation_frames'],startup_words=cfg['startup_words'],
                        ingress_bits=cfg['ingress_bits_per_source'],egress_bits=cfg['egress_bits_per_source'],
                        streaming=True))
                row['queue_screen']=dict(status='passed',frames_per_case=cfg['simulation_frames'],
                    source_phases=4,scope='Ideal streaming words after accepted header; no CDC, electrical timing or mode changes',
                    peak_bits={key:max(case[key] for case in cases) for key in
                        ('ingress_high_water_bits','egress_high_water_bits','staging_high_water_bits')})
                # Periodic snapshot service has rate R and latency one frame.
                # A prepared batch finishes within two more frames. Continuous
                # packing may wait one sample for the final partial word.
                r=Fraction(source['rate_bps']*(1_000_000+t['source_fast_ppm']),
                           300_000_000*(1_000_000-t['host_slow_ppm']))
                R=Fraction(allocation[source['id']]*t['word_bits'],t['frame_words'])
                sample=source['sample_bits'];burst=sample+t['word_bits']-1
                if sample<t['word_bits'] or R<r:raise ValueError('Queue-bound assumptions violated')
                delay=3*t['frame_words']+Fraction(burst,R)+Fraction(sample,r)
                ingress=ceil(burst+r*t['frame_words'])
                egress=ceil(r*(cfg['startup_words']-t['frame_words'])+2*sample+t['word_bits'])
                staging=2*allocation[source['id']]*t['word_bits']
                assert delay<cfg['startup_words']
                assert ingress<=cfg['ingress_bits_per_source'] and egress<=cfg['egress_bits_per_source']
                assert all(case['ingress_high_water_bits']<=ingress and
                    case['egress_high_water_bits']<=egress and
                    case['staging_high_water_bits']<=staging for case in cases)
                row['constant_rate_bounds']=dict(max_delivery_host_words=float(delay),
                    ingress_bits=ingress,egress_bits=egress,staging_bits=staging,
                    startup_host_words=cfg['startup_words'],
                    scope='Matched constant producer/consumer rates; no stalls, errors, CDC delays or mode transitions')
            exclusive.append(row)
    return {'scope': 'necessary frequency and bandwidth screen; not electrical qualification',
            'source': {'url': 'https://www.latticesemi.com/view_document?document_id=50461',
                       'revision': 'FPGA-DS-02012-3.4, September 2025',
                       'tables': ['3.21', '3.44'],
                       'pdf_sha256': '26570f8bb2b800123120829cacd75d818d7a985d573797610521b5bda2e293c3'},
            'contract_sha256': hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
            'profiles': profiles, 'hypothetical_ddr150': alternatives,
            'exclusive_hypothetical_ddr150': exclusive}


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--queues',action='store_true')
    args=parser.parse_args()
    print(json.dumps(screen(json.loads(CONTRACT.read_text()),queues=args.queues), indent=2))
