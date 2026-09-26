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
    require(len(pins) == c['limits']['total_terminals'] == 51, 'terminal budget')
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


def assembly_ledger(c):
    """Separate required functions, retained pad sites and unknown board terminals."""
    inventory=c['assembly_policy']['provider_site_inventory']
    sides=inventory['ordered_sites_by_side']
    sites=[site for group in sides.values() for site in group]
    require(len(set(sites))==len(sites), 'duplicate provider site')
    fixed={f'{prefix}_pads[{i}].pad'
           for prefix,count in [('dvdd',6),('dvss',8),('vdd',2),('vss',2)]
           for i in range(count)}
    require(fixed.issubset(sites), 'missing fixed provider supply site')
    signals=[p for p in c['pins'] if p['direction']!='power']
    mapping=c['assembly_policy']['candidate_signal_sites']
    require(set(mapping)=={p['name'] for p in signals},'provider signal mapping coverage')
    require(len(set(mapping.values()))==len(mapping),'duplicate provider signal assignment')
    require(set(mapping.values())<=set(sites)-fixed,'provider signal uses unavailable or fixed supply site')
    locations={site:(side,index) for side,group in sides.items() for index,site in enumerate(group)}
    for prefix in ('RF_RX','RF_TX','WIRE_RX','WIRE_TX'):
        positive=locations[mapping[prefix+'_P']];negative=locations[mapping[prefix+'_N']]
        require(positive[0]==negative[0] and abs(positive[1]-negative[1])==1,'differential pair adjacency')
    positive=locations[mapping['REF_IN']];negative=locations[mapping['REF_IN_N']]
    require(positive[0]==negative[0] and abs(positive[1]-negative[1])==1,'reference pair adjacency')
    neighbors=[]
    for name,site in mapping.items():
        side,index=locations[site]
        grounds=[(abs(index-j),v) for j,v in enumerate(sides[side]) if v.startswith(('dvss_pads','vss_pads'))]
        distance,ground=min(grounds)
        neighbors.append(dict(signal=name,site=site,side=side,nearest_same_edge_ground=ground,
            separation_in_list_positions=distance))
    minimum=len(signals)+len(fixed)
    return dict(status='open_physical_mapping',closed=False,
        provider_sites=len(sites),fixed_supply_return_sites=len(fixed),
        provider_signal_sites=len(sites)-len(fixed),
        required_functional_signals=len(signals),
        spare_signal_sites=len(sites)-len(fixed)-len(signals),
        required_signals_plus_fixed_supply_sites=minimum,
        logical_terminal_target=c['limits']['total_terminals'],
        minimum_excess_over_logical_target=max(0,minimum-c['limits']['total_terminals']),
        retained_site_excess_over_logical_target=max(0,len(sites)-c['limits']['total_terminals']),
        delivered_board_terminal_count=inventory['delivered_board_terminal_count'],
        candidate_signal_assignment=neighbors,
        unused_signal_sites=[s for s in sites if s not in fixed and s not in mapping.values()],
        differential_pairs_adjacent_in_template=True,
        independent_external_domain_rails_proven=False,
        scope='Candidate signal assignment and template-list adjacency only, not physical distance or return impedance. Unused signals do not remove physical sites or bonds; board connector count and electrical qualification remain unknown.')


def periodic_stream_bound(*, arrival_item_hz, item_bits, word_hz,
                          frame_words, payload_words, staging_frames,
                          cdc_words, extra_service_gap_s=0):
    """Arrival b+r*t and guaranteed rate-latency service R*max(0,t-T).

    Requires backlog-aware periodic service and no recurring unpriced stalls.
    This is a sufficient abstract bound, not a model of actual FIFO placement.
    """
    import math
    values=(arrival_item_hz,item_bits,word_hz,frame_words,payload_words,staging_frames,cdc_words,extra_service_gap_s)
    require(all(math.isfinite(v) for v in values),'finite service parameters')
    require(min(arrival_item_hz,item_bits,word_hz,payload_words)>0 and
            frame_words>=payload_words and min(staging_frames,cdc_words,extra_service_gap_s)>=0,
            'positive rate and bounded service geometry')
    arrival=arrival_item_hz*item_bits
    service=word_hz*10*payload_words/frame_words
    # One additional word prices discrete completion, beyond the header gap.
    latency=(staging_frames*frame_words+frame_words-payload_words+cdc_words+1)/word_hz+extra_service_gap_s
    stable=arrival<=service
    return dict(arrival_bps=arrival,guaranteed_service_bps=service,
        service_latency_s=latency,rate_stable=stable,
        backlog_bound_bits=math.ceil(item_bits+arrival*latency) if stable else None,
        delay_bound_s=latency+item_bits/service if stable else None,
        scope='Conditional arrival/service-curve bound; actual scheduler, CDC, queue placement and recurring-stall guarantee unverified')


def operating_clock_ledger(c):
    """Whole-path rate obligations; this does not establish realizable PLLs."""
    t=c['transport']
    payload_fraction=Fraction(t['frame_words']-t['control_words'],t['frame_words'])
    host_max=max(Fraction(p['clock_hz'])*p['edges'] for p in t['profiles'].values())
    rows=[]
    def add(name,engine,source,ref_hz,consumer_hz,item_bits,d2h_word_hz,
            converter_tracks_lo=False):
        consumer_hz=Fraction(str(consumer_hz));d2h_word_hz=Fraction(str(d2h_word_hz))
        demand=consumer_hz*item_bits
        capacity=d2h_word_hz*t['word_bits']*payload_fraction
        ratio=consumer_hz/d2h_word_hz
        # Compare worst independent tolerances; a shared source may cancel some.
        demand_worst=demand*Fraction(1000000+t['source_fast_ppm'],1000000)
        capacity_worst=capacity*Fraction(1000000-t['host_slow_ppm'],1000000)
        service=periodic_stream_bound(arrival_item_hz=float(consumer_hz)*(1+t['source_fast_ppm']/1e6),
            item_bits=item_bits,word_hz=float(d2h_word_hz)*(1-t['host_slow_ppm']/1e6),
            frame_words=t['frame_words'],payload_words=t['frame_words']-t['control_words'],
            staging_frames=t['scheduling']['staging_frames'],cdc_words=2)
        allocation=t['scheduling']['ingress_bits_per_source']
        service['comparison_allocation_bits']=allocation
        service['additional_one_off_gap_budget_s']=(allocation-item_bits)/service['arrival_bps']-service['service_latency_s'] if service['rate_stable'] else None
        if engine=='rf':
            # Diagnostic deadline only. Residual must cover DSP/resampling,
            # decision work and real analog/board settling together.
            overhead=(service['delay_bound_s']+64/float(host_max)+8/float(host_max)+2/40e6+
                      64/float(d2h_word_hz)) if service['rate_stable'] else None
            service['diagnostic_response_deadline_s']=10e-6
            service['response_transport_overhead_s']=overhead
            service['remaining_fpga_and_analog_budget_s']=10e-6-overhead if overhead is not None else None
        rows.append(dict(configuration=name,engine=engine,ref_in_role=source,
            ref_in_hz=ref_hz,consumer_item_hz=float(consumer_hz),item_bits=item_bits,
            d2h_word_hz=float(d2h_word_hz),d2h_ddr_clock_hz=float(d2h_word_hz/2),
            h2d_word_hz=float(host_max),payload_demand_bps=float(demand),
            d2h_payload_capacity_bps=float(capacity),
            d2h_capacity_with_ppm_margin=bool(demand_worst<=capacity_worst),
            h2d_capacity_with_ppm_margin=bool(demand_worst<=host_max*t['word_bits']*payload_fraction*Fraction(1000000-t['host_slow_ppm'],1000000)),
            d2h_within_host_rate_ceiling=bool(d2h_word_hz<=host_max),
            fpga_tx_items_per_d2h_word=[ratio.numerator,ratio.denominator],
            fpga_tx_pacing='D2H-derived rational enables; independent H2D only transports prepared items',
            converter_tracks_lo=converter_tracks_lo,
            same_channel_turnaround='preserve source, conversion and host clocks' if engine=='rf' else None,
            retune_changes_conversion_and_d2h=converter_tracks_lo if engine=='rf' else None,
            frame_duration_s=float(Fraction(t['frame_words'])/d2h_word_hz),
            conditional_d2h_service_bound=service,
            physical_clock_path_qualified=False,sustained_fifo_verified=False))
    # Frequency-reference synthesis requires separate LO and conversion/host outputs.
    add('rf_reference_synthesized','rf','frequency_reference',None,40e6,24,host_max)
    add('rf_reference_half_d2h_candidate','rf','frequency_reference',None,40e6,24,host_max/2)
    candidate=c['generic_configuration_target']['external_lo_sampling_candidate']
    for lo in candidate['lo_range_hz']:
        for divisor in candidate['uniform_sample_dividers']:
            for host_divider in (candidate['candidate_d2h_clock_divider'],2*candidate['candidate_d2h_clock_divider']):
                add(f'rf_direct_lo_{int(lo)}_div{divisor}_hostdiv{host_divider}','rf','external_lo',lo,
                    Fraction(str(lo))/divisor,24,Fraction(str(lo))/host_divider*2,True)
    for rate in c['physical_services']['serial_target_rates_bps']:
        add(f'wire_reference_{rate}','wire','frequency_reference',None,Fraction(str(rate))/10,10,host_max)
    for pixel in (Fraction(74250000),Fraction(148500000),Fraction(74250000000,1001),Fraction(148500000000,1001)):
        add(f'wire_forwarded_x10_{float(pixel)}','wire','forwarded_word_clock',float(pixel),pixel,10,2*pixel)
    return dict(configurations=rows,closed=False,
        ref_in_consumers_mutually_exclusive=True,
        independent_external_fixed_converter_clock_allocated=False,
        wire_rx_clock_owner='independent incoming transitions, on-chip CDR; external TX reference does not replace it',
        supply_topology='shared external feed until compatible map proves otherwise',
        source_frequency_reference_hz=None,
        scope='Rate and source-ownership requirements only. Dense I/Q packing assumed; finite scheduling/CDC, source spectra, synthesizer ratios, power, electrical input and FPGA implementation remain unqualified. USB short-frame response service is separate from this bulk capacity screen.')


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
        assembly=assembly_ledger(c),
        operating_clocks=operating_clock_ledger(c),
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
