"""Check planning invariants, not physical implementation or tapeout readiness."""
import json
from fractions import Fraction
from pathlib import Path

CONTRACT = Path(__file__).resolve().parents[1] / 'spec/contract.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def ceil(value):
    return -(-value.numerator // value.denominator)


def check(c):
    pins = c['pins']
    require(len(pins) == c['limits']['total_terminals'] == 50, 'terminal budget')
    require(len({p['name'] for p in pins}) == len(pins), 'duplicate terminal')
    require(sum(p['kind'] in ('supply', 'ground') for p in pins) == 14, 'power budget')
    for bus, direction in [('D2H', 'out'), ('H2D', 'in')]:
        required = {f'{bus}_D[{i}]' for i in range(10)} | {f'{bus}_CLK'}
        actual = {p['name'] for p in pins if p['direction'] == direction}
        require(required <= actual, f'{bus} bus allocation')
    require(all(isinstance(v, int) and v > 0 for v in c['area_um2'].values()), 'area allocations')
    require(sum(c['area_um2'].values()) <= c['limits']['core_area_um2'], 'area budget')
    t = c['transport']
    require(t['word_bits'] == 10 and t['frame_words'] == 64 and t['control_words'] == 5, 'transport geometry')
    scheduling = t['scheduling']
    require(scheduling['control_slots'] == [0, 1, 2, 3, 4], 'control slot allocation')
    require(scheduling['staging_frames'] == 2, 'frame staging allocation')
    require(scheduling['descriptor'] == 'counts6_sequence6_opcode4_argument8_hamming37_tag3_guard10', 'validity descriptor')
    require(scheduling['receive_commit'] == 'stream_after_validated_header', 'receive policy')
    for key in ['host_slow_ppm', 'source_fast_ppm']:
        require(isinstance(t[key], int) and 0 <= t[key] < 1000000, 'frequency margin')
    payload_words = t['frame_words'] - t['control_words']
    results = []
    require(len({m['id'] for m in c['modes']}) == len(c['modes']), 'duplicate mode')
    for mode in c['modes']:
        profile = t['profiles'][mode['profile']]
        require(profile['edges'] in (1, 2) and profile['clock_hz'] > 0, 'clock profile')
        words_per_second = Fraction(profile['clock_hz'] * profile['edges'])
        frame_rate = words_per_second / t['frame_words']
        conservative_slot_bps = frame_rate * t['word_bits'] * Fraction(1000000-t['host_slow_ppm'], 1000000)
        slots = {'d2h': 0, 'h2d': 0}
        allocation = {}
        require(len({s['id'] for s in mode['sources']}) == len(mode['sources']), 'duplicate source')
        for source in mode['sources']:
            require(source['id'] in ('wire', 'iq'), 'source not represented by descriptor')
            require(isinstance(source['sample_bits'], int) and source['sample_bits'] > 0, 'source item width')
            require(isinstance(source['rate_bps'], int) and source['rate_bps'] > 0, 'source rate')
            directions = source['directions']
            require(directions and len(set(directions)) == len(directions) and set(directions) <= set(slots), 'source directions')
            demand = source['rate_bps'] * Fraction(1000000+t['source_fast_ppm'], 1000000)
            reserved = ceil(demand / conservative_slot_bps)
            allocation[source['id']] = reserved
            for direction in directions:
                slots[direction] += reserved
        require(all(n <= payload_words for n in slots.values()), f"{mode['id']}: payload slot overcommit {slots}")
        results.append({'mode': mode['id'], 'profile': mode['profile'], 'reserved_words_per_source': allocation,
                        'used_words_per_direction': slots, 'available_payload_words': payload_words,
                        'nominal_payload_bps_per_direction': float(frame_rate * payload_words * t['word_bits'])})
    return results


if __name__ == '__main__':
    print(json.dumps({'scope': 'planning arithmetic only; not implementation qualification',
                      'modes': check(json.loads(CONTRACT.read_text()))}, indent=2))
