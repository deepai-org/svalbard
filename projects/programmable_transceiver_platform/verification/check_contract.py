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


def check_protocol_profiles(c):
    """Check physical ownership and capacity targets, never infer compliance."""
    profiles = c['protocol_profiles']
    require(len({p['id'] for p in profiles}) == len(profiles), 'duplicate protocol profile')
    pins = {p['name']: p for p in c['pins']}
    services = c['physical_services']
    rates = services['serial_target_rates_bps']
    require(len(set(rates)) == len(rates) and all(0 < r <= 2500000000 for r in rates),
            'serial rate envelope')
    require(c['operating_policy']['rf_wired_simultaneous_permitted'] is False,
            'exclusive engine ownership')
    for p in profiles:
        require(p['model_status'] in ('requirements_only','phy_primitives') and not p['standards_compliant'],
                'protocol qualification requires implemented model and evidence')
        if p['model_status']=='phy_primitives':
            require(bool(p.get('modeled_primitives')) and bool(p.get('model_sources')), 'executable profile scope')
        require(p['engine'] in ('wire', 'rf'), 'profile engine')
        require(set(p['pins']) <= set(pins), 'profile hidden terminal')
        require(len(set(p['pins'])) == len(p['pins']), 'duplicate profile terminal')
        require({'clock_quality', 'loaded_electrical_path', 'host_service', 'lifecycle',
                 'independent_protocol_waveform'} <= set(p['required_gates']), 'profile closure gates')
        if p['engine'] == 'wire':
            require(p['line_rate_bps'] in rates and p['lanes'] == 1, 'wired rate or lane allocation')
            require(p['duplex'] in ('full', 'half', 'simplex'), 'wired duplex')
            require(p['host_service'] in ('framed', 'short_framed'), 'wired host service')
            if p['id'] == 'usb2':
                require(set(p['pins']) == {'WIRE_RX_P', 'WIRE_RX_N'} and
                        all(pins[n]['direction'] == 'inout' for n in p['pins']), 'USB bidirectional pair')
                require(p['duplex'] == 'half' and set(p['roles']) == {'host', 'device'}, 'USB roles')
                require(p['host_service'] == 'short_framed' and
                        'fpga_response_deadline' in p['required_gates'], 'USB response deadline')
            else:
                require(set(p['pins']) == {'WIRE_RX_P', 'WIRE_RX_N', 'WIRE_TX_P', 'WIRE_TX_N'},
                        'serial pad allocation')
            if p['id'] in ('dvi_single_link','hdmi_tmds'):
                require(p['chip_instances']==p['link_data_lanes']==3 and p['duplex']=='simplex', 'multi-chip video topology')
                require(p['line_rates_bps']==[742500000,1485000000] and
                        set(p['roles'])=={'source','sink'}, 'video timing and roles')
                require({'forwarded_word_clock','multi_chip_alignment','dc_current_sink_electrical'} <= set(p['required_gates']), 'video physical gates')
            if p['id'] == 'displayport_rbr':
                require(p['line_rate_bps'] == 1620000000 and p['duplex'] == 'simplex' and
                        set(p['roles']) == {'source', 'sink'} and 'external_aux' in p['required_gates'],
                        'DisplayPort scope')
        else:
            require(set(p['pins']) == {'RF_RX_P', 'RF_RX_N', 'RF_TX_P', 'RF_TX_N'}, 'RF pad allocation')
            require(2300000000 <= p['carrier_min_hz'] <= p['carrier_max_hz'] <= 2500000000,
                    'RF tuning envelope')
            require(p['spatial_streams'] == 1 and 0 < p['channel_bandwidth_max_hz'] <= 20000000,
                    'RF bandwidth or stream allocation')
            require(p['channel_bandwidth_max_hz'] <= p['complex_sample_rate_max_hz'] <= 40000000
                    and 0 < p['sample_bits_max'] <= 12, 'converter envelope')
            require(p['host_service'] == 'framed_with_timed_events', 'RF timed host service')
    return profiles


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
    check_protocol_profiles(c)
    t = c['transport']
    u=t['usb_short_frame']
    require((u['frame_words'],u['word_bits'],u['control_words'],u['payload_words'])==(8,10,5,3), 'USB reused frame geometry')
    require(u['host_profile']=='ddr125', 'USB reused host clock')
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
