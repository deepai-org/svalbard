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
    require(u['host_profile']=='ddr156', 'USB selected faster host clock')
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


def bridge_storage_inventory():
    """Selected USB model's coexisting storage; payload subtotal, not cell area.

    Trace: TimedRecordReturn/TimedRecordPlayback, pt_block_fifo and
    RawBurstPlayback. Python object/timestamp sizes are not hardware widths.
    External observation traces and stimulus generators are not chip resources.
    """
    rows = [
        dict(instance='d2h_block_cdc', owner='chip', entries=8, bits_per_entry=84,
             source='rtl/pt_block_fifo.sv', omitted='pointer/reset/fault state'),
        dict(instance='h2d_block_cdc', owner='chip', entries=8, bits_per_entry=84,
             source='rtl/pt_block_fifo.sv', omitted='pointer/reset/fault state'),
        dict(instance='d2h_active_and_prepared_frames', owner='chip', entries=2, bits_per_entry=80,
             source='TimedRecordReturn', omitted='sequence/valid/control state'),
        dict(instance='h2d_pending_commit_frames', owner='chip', entries=3, bits_per_entry=80,
             source='TimedRecordPlayback', omitted='valid/age/control state'),
        dict(instance='raw_playback_data', owner='chip', entries=2048, bits_per_entry=1,
             source='RawBurstPlayback', omitted='16 boundary locations, pointers and status'),
        dict(instance='raw_capture_records', owner='chip', entries=16, bits_per_entry=None,
             source='usb_observed_response: BitEventStream', omitted='record representation and control'),
        dict(instance='h2d_frame_decoder', owner='chip', entries=None, bits_per_entry=None,
             source='TimedRecordPlayback.receiver/frame_records', omitted='decoder/header/partial-record state'),
        dict(instance='fpga_ingress', owner='external_fpga', entries=8, bits_per_entry=None,
             source='usb_observed_response: fpga_ingress', omitted='packed record width, CDC pointers'),
        dict(instance='fpga_packet_payload', owner='external_fpga', entries=1024, bits_per_entry=8,
             source='USBStreamingPacket', omitted='CRC/parser/control and prepared response storage'),
    ]
    for row in rows:
        row['identified_bits'] = (row['entries'] * row['bits_per_entry']
            if row['entries'] is not None and row['bits_per_entry'] is not None else None)
    return dict(configuration='USB short-frame bridge candidate; both directions coexist',
        instances=rows,
        chip_identified_bits=sum(r['identified_bits'] or 0 for r in rows if r['owner']=='chip'),
        external_fpga_identified_bits=sum(r['identified_bits'] or 0 for r in rows if r['owner']=='external_fpga'),
        complete=False,
        scope='Identified data-bank capacity only; not total flip-flops, area or memory allocation. '
              'Unknown widths and omitted state remain open. Do not add these banks again through parent mappings. '
              'Sharing with bulk wired/RF transport and diagnostic memory is not yet resolved.')


def resource_ledger(c):
    """One contract-derived planning ledger; missing implementation is not zero."""
    domains={}
    for domain in c['power']['domains']:
        require(len(domain['supply_pins'])==len(domain['return_pins']), 'unpaired supply domain')
        domains[domain['id']]=dict(supply_pairs=len(domain['supply_pins']),
            allocation_ma=len(domain['supply_pins'])*domain['per_connection_budget_ma'],
            demonstrated_current_ma=None)
    area=[dict(group=name,allocation_um2=value,implemented_area_um2=None)
          for name,value in c['area_um2'].items()]
    return dict(status='open_planning_ledger',closed=False,
        terminals=dict(allocated=len(c['pins']),limit=c['limits']['total_terminals'],
            supply_return=sum(len(x['supply_pins'])+len(x['return_pins']) for x in c['power']['domains'])),
        area=dict(limit_um2=c['limits']['core_area_um2'],allocations=area,
            allocated_um2=sum(c['area_um2'].values()),
            unallocated_um2=c['limits']['core_area_um2']-sum(c['area_um2'].values()),
            explicit_reserve_um2=c['area_um2'].get('reserve',0),implemented_total_um2=None),
        power_domains=domains,total_allocated_current_ma=sum(x['allocation_ma'] for x in domains.values()),
        mode_domains=dict(wire=['CORE','HOST','WIRE','PLL'],rf=['CORE','HOST','RF','PLL']),
        inactive_domain_current_ma=None,
        storage=dict(status=c['transport']['scheduling']['fifo_budget_status'],
            physical_instance_bits=None,selected_bridge=bridge_storage_inventory(),scope='FIFO allocations and isolated mappings do not establish simultaneous physical instances'),
        usb_host_profile=c['transport']['usb_short_frame']['host_profile'],
        unresolved=['implemented physical instances and shared/duplicated ownership',
            'complete digital/analog area including clock trees and isolation',
            'domain current with internal cell/data/clock and inactive leakage',
            'simultaneous storage, CDC and staging instances',
            'pad/protection/package and thermal closure',
            'external FPGA resources and physical host timing'],
        scope='Contract planning values only. Domain allocation sum is not consumption; exclusive modes do not make inactive leakage zero. Isolated cell mapping must not be summed with overlapping parent implementations.')


if __name__ == '__main__':
    print(json.dumps({'scope': 'planning arithmetic only; not implementation qualification',
                      'modes': check(json.loads(CONTRACT.read_text())),
                      'resource_ledger': resource_ledger(json.loads(CONTRACT.read_text()))}, indent=2))
