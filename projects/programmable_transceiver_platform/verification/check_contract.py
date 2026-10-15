"""Check planning invariants, not physical implementation or tapeout readiness."""
import json
import math
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
            require(p['host_service'] in ('framed', 'direct_stream'), 'wired host service')
            if p['id'] == 'usb2':
                require(set(p['pins']) == {'WIRE_RX_P', 'WIRE_RX_N'} and
                        all(pins[n]['direction'] == 'inout' for n in p['pins']), 'USB bidirectional pair')
                require(p['duplex'] == 'half' and set(p['roles']) == {'host', 'device'}, 'USB roles')
                require(p['host_service'] == 'direct_stream' and
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
    u=t['direct_stream']
    require((u['host_clock_hz'],u['edges'],u['word_bits'],u['payload_bits'])==(100000000,1,10,8), 'USB direct-stream clock/encoding')
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
        selected_service=periodic_stream_bound(arrival_item_hz=float(consumer_hz)*(1+t['source_fast_ppm']/1e6),
            item_bits=item_bits,word_hz=float(d2h_word_hz)*(1-t['host_slow_ppm']/1e6),
            frame_words=t['frame_words'],payload_words=t['frame_words']-t['control_words'],
            staging_frames=1,cdc_words=2)
        selected_service['additional_one_off_gap_budget_s']=(allocation-item_bits)/selected_service['arrival_bps']-selected_service['service_latency_s'] if selected_service['rate_stable'] else None
        selected_service.update(comparison_allocation_bits=allocation,
            backlog_bound_within_comparison_allocation=bool(selected_service['rate_stable'] and selected_service['backlog_bound_bits']<=allocation),
            scheduler='BehavioralChip snapshots available words at slot zero and emits them in that same frame',
            scope='One full frame to the next snapshot, header, two assigned CDC words and one word completion. Conditional selected behavioral scheduler bound; actual RTL CDC/staging and recurring stalls remain unqualified.')
        service['staging_assumption']='Conservative planning staging_frames comparison, not the selected same-frame BehavioralChip scheduler'
        service['comparison_allocation_bits']=allocation
        service['backlog_bound_within_comparison_allocation']=bool(service['rate_stable'] and service['backlog_bound_bits']<=allocation)
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
            selected_snapshot_d2h_service_bound=selected_service,
            conditional_d2h_service_bound=service,
            physical_clock_path_qualified=False,sustained_fifo_verified=False))
    # Frequency-reference synthesis requires separate LO and conversion/host outputs.
    add('rf_reference_synthesized','rf','frequency_reference',None,40e6,24,host_max)
    add('rf_reference_half_d2h_candidate','rf','frequency_reference',None,40e6,24,host_max/2)
    candidate=c['generic_configuration_target']['external_lo_sampling_candidate']
    require(candidate['d2h_ddr_clock_divider']==2*candidate['d2h_word_divider'],
            'RF word and physical DDR clock dividers disagree')
    for lo in candidate['lo_range_hz']:
        for divisor in candidate['uniform_sample_dividers']:
            host_divider=candidate['d2h_word_divider']
            add(f'rf_direct_lo_{int(lo)}_div{divisor}_worddiv{host_divider}','rf','external_lo',lo,
                Fraction(str(lo))/divisor,24,Fraction(str(lo))/host_divider,True)
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
        usb_host_profile='direct_sdr100',
        unresolved=['implemented physical instances and shared/duplicated ownership',
            'complete digital/analog area including clock trees and isolation',
            'domain current with internal cell/data/clock and inactive leakage',
            'simultaneous storage, CDC and staging instances',
            'pad/protection/package and thermal closure',
            'external FPGA resources and physical host timing'],
        scope='Contract planning values only. Domain allocation sum is not consumption; exclusive modes do not make inactive leakage zero. Isolated cell mapping must not be summed with overlapping parent implementations.')


def capability_host_service(c,capability,item,clock_rows):
    """Map each target to existing arithmetic, without qualifying its waveform."""
    timing=item['requirements']['timing'];rates=timing.get('line_rates_bps')
    if rates is None and timing.get('line_rate_bps') is not None:rates=[timing['line_rate_bps']]
    rows=[]
    if capability=='lower_frequency_rf_stretch':
        return dict(status='no_selected_direct_tuning_configuration',configurations=[],
            scope='Outside selected direct LO range; no fictitious service point assigned. Requires qualified wider tuning or the separately scoped external conversion route.')
    if capability=='usb2':
        from usb_selected_timing import response_bound
        u=c['transport']['direct_stream'];service=c['physical_services']['usb_selected_service']
        bound=response_bound(host_hz=u['host_clock_hz'],fpga_s=service['fpga_decision_s'])
        return dict(status='conditional_direct_stream_component_model',roles=['host','device'],
            d2h_word_hz=u['host_clock_hz'],h2d_word_hz=u['host_clock_hz'],host_edges=1,
            raw_line_demand_bps=timing['line_rate_bps'],conditional_service_bound=bound,
            scope='Selected SDR byte/control service; causal component model, not canonical full-chip/RTL or physical USB qualification.')
    if rates:
        if capability in ('dvi_single_link','hdmi_tmds'):
            rows=[r for r in clock_rows if r['ref_in_role']=='forwarded_word_clock']
        else:
            rows=[r for r in clock_rows if r['engine']=='wire' and r['ref_in_role']=='frequency_reference'
                  and any(abs(r['payload_demand_bps']-rate)<=1e-9*rate for rate in rates)]
        require(bool(rows),f'{capability}: no wired service configuration')
        scope='Per-lane encoded/raw bits, including line coding supplied by FPGA. Multiply independent ports by chip_instances; shared FPGA feasibility and protocol control deadlines remain unproven.'
    else:
        # Endpoint range requirements, not an assertion that every divider
        # supplies sufficient bandwidth for this capability's waveform.
        rows=[r for r in clock_rows if r['engine']=='rf' and r['ref_in_role']=='external_lo']
        scope='Selected LO-range endpoint envelopes for 24-bit complex I/Q. Not modem bit rates or proof that every divider supports the waveform bandwidth. Carrier-specific rates scale with LO; FPGA resampling, DSP latency and filtering remain required.'
        if capability=='external_frequency_conversion_stretch':
            scope+=' External RF conversion must present an on-chip frequency within the selected range; no direct tuning extension is inferred.'
    return dict(status='conditional_rate_envelope_not_protocol_qualification',
        clock_configurations=[r['configuration'] for r in rows],
        clock_ledger_owner='resource_ledger.operating_clocks.configurations',
        per_chip_demand_range_bps=[min(r['payload_demand_bps'] for r in rows),max(r['payload_demand_bps'] for r in rows)],
        per_chip_d2h_capacity_range_bps=[min(r['d2h_payload_capacity_bps'] for r in rows),max(r['d2h_payload_capacity_bps'] for r in rows)],
        per_chip_d2h_word_range_hz=[min(r['d2h_word_hz'] for r in rows),max(r['d2h_word_hz'] for r in rows)],
        per_chip_d2h_ddr_clock_range_hz=[min(r['d2h_ddr_clock_hz'] for r in rows),max(r['d2h_ddr_clock_hz'] for r in rows)],
        chip_instances=item['requirements']['area']['chip_instances'],
        all_listed_points_fit_bulk_capacity_with_ppm=all(r['d2h_capacity_with_ppm_margin'] and r['h2d_capacity_with_ppm_margin'] for r in rows),
        selected_snapshot_bounds_within_planning_allocation=all(r['selected_snapshot_d2h_service_bound']['backlog_bound_within_comparison_allocation'] for r in rows),
        all_listed_backlog_bounds_within_planning_allocation=all(r['conditional_d2h_service_bound']['backlog_bound_within_comparison_allocation'] for r in rows),
        backlog_bound_scope='Sufficient bound under assigned two-frame staging/CDC assumptions. Exceeding the planning allocation leaves queue closure unproven; it is not an observed overflow or justification to increase physical storage.',
        scope=scope)


def review_evidence_freshness(root=None, closure=None):
    """Read-only provenance audit; matching sources never establish acceptance."""
    import hashlib
    root=CONTRACT.parent.parent if root is None else Path(root)
    if closure is None:
        closure=json.loads((root/'spec/mathematical-closure.json').read_text())
    rows=[];reports={}
    for area,binding in closure['milestone']['review_evidence'].items():
        path=root/binding['file']
        row=dict(area=area,**binding)
        if not path.is_file():
            rows.append(dict(row,status='missing_report'));continue
        if path not in reports:reports[path]=json.loads(path.read_text())
        section=reports[path].get(binding['section'])
        if not isinstance(section,dict):
            rows.append(dict(row,status='missing_section'));continue
        manifest=section.get('sources_sha256')
        if not isinstance(manifest,dict) or not manifest:
            rows.append(dict(row,status='missing_manifest'));continue
        changed=[];missing=[]
        for name,digest in manifest.items():
            source=root/name
            if not source.is_file():missing.append(name)
            elif hashlib.sha256(source.read_bytes()).hexdigest()!=digest:changed.append(name)
        rows.append(dict(row,status='stale' if changed or missing else 'sources_match',
            changed_sources=sorted(changed),missing_sources=sorted(missing),
            recorded_source_count=len(manifest)))
    return dict(areas=rows,
        scope='Only each selected section own source manifest is checked. Nested sections retain independent provenance. Matching hashes do not prove manifest completeness, test acceptance, physical feasibility or milestone completion.')


def simulation_design_audit(root=None):
    """Locate construction paths; static evidence does not certify full alignment."""
    import ast
    from collections import Counter
    root=Path(root) if root is not None else CONTRACT.parent.parent
    bindings={
        'load_design':'validated_shared_design_snapshot',
        'configured_environment':'resolved_configuration_environment',
        'build_model':'shared_design_packet_adapter',
        'ClientBench':'shared_design_wifi_fixture',
        'hypothetical':'declared_circuit_experiment',
        'Scenario':'explicit_scenario',
        'inventory_environment':'architecture_current_inventory',
        'parameters_from_inventory':'architecture_converter',
        'selected_converter_parameters':'architecture_converter',
        'environment_converter_parameters':'resolved_environment_converter',
        'receiver_inventory_options':'architecture_receiver',
        'from_architecture':'architecture_factory',
        'selected_environment':'current_architecture_environment_entry',
        'SARParameters':'independent_converter_constructor',
        'SharedWiredPad':'independent_pad_constructor',
        'Assumptions':'behavioral_assumptions_constructor',
        'operating_environment':'independent_environment_constructor'}
    files=[];sites=[];errors=[];test_methods=[];role_errors=[]
    for directory in ('verification','system_model'):
        for path in sorted((root/directory).rglob('*.py')):
            if '__pycache__' in path.parts:continue
            relative=str(path.relative_to(root));test=path.name.startswith('test_')
            try:tree=ast.parse(path.read_text())
            except (SyntaxError,UnicodeError) as error:
                errors.append(dict(file=relative,error=str(error)));continue
            start=len(sites);method_start=len(test_methods);local_functions={}
            roles={}
            if test:
                for node in tree.body:
                    if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='TEST_DESIGN_ROLES' for target in node.targets):
                        try:
                            roles=ast.literal_eval(node.value)
                            if not isinstance(roles,dict):raise ValueError('Expected scope-to-role mapping')
                        except (ValueError,TypeError,SyntaxError) as error:
                            role_errors.append(dict(file=relative,error=str(error)));roles={}
            def visit(node,scope):
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                    scope=scope+[node.name]
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    local_functions['.'.join(scope)]=node
                if test and isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name.startswith('test_'):
                    calls=[]
                    for child in ast.walk(node):
                        if not isinstance(child,ast.Call):continue
                        name=(child.func.id if isinstance(child.func,ast.Name) else
                              child.func.attr if isinstance(child.func,ast.Attribute) else None)
                        if name is not None and not name.startswith('assert'):
                            calls.append(name)
                    test_methods.append(dict(file=relative,line=node.lineno,scope='.'.join(scope),
                        calls=sorted(set(calls)),tracked_constructors=sorted(set(calls)&bindings.keys()),
                        module_role_note=ast.get_docstring(tree),
                        classification='requires_semantic_review'))
                if isinstance(node,ast.Call):
                    name=node.func.id if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else None
                    if name in bindings:
                        sites.append(dict(file=relative,line=node.lineno,scope='.'.join(scope) or '<module>',
                            call=name,binding=bindings[name],test_fixture=test,
                            explicit_keywords=[k.arg for k in node.keywords if k.arg]))
                for child in ast.iter_child_nodes(node):visit(child,scope)
            visit(tree,[])
            used_roles=set()
            for method in test_methods[method_start:]:
                owner=method['scope'].rsplit('.',1)[0] if '.' in method['scope'] else ''
                role_scope=method['scope'] if method['scope'] in roles else owner if owner in roles else None
                declaration=roles.get(role_scope)
                method.update(declared_role='unclassified',role_reason=None,role_source=None)
                if role_scope is not None:
                    used_roles.add(role_scope)
                    if (not isinstance(declaration,(list,tuple)) or len(declaration)!=2
                            or declaration[0] not in ('shared_design','independent_fixture')
                            or not isinstance(declaration[1],str) or not declaration[1].strip()):
                        role_errors.append(dict(file=relative,scope=role_scope,error='Explicit known role and nonempty reason required'))
                    else:
                        method.update(declared_role=declaration[0],role_reason=declaration[1],role_source=role_scope)
                roots=[method['scope']]+[(owner+'.' if owner else '')+name
                    for name in ('setUp','setUpClass')]
                pending=[name for name in roots if name in local_functions];seen=set();constructors=set()
                while pending:
                    scope=pending.pop()
                    if scope in seen:continue
                    seen.add(scope)
                    for call in ast.walk(local_functions[scope]):
                        if not isinstance(call,ast.Call):continue
                        name=call.func.id if isinstance(call.func,ast.Name) else call.func.attr if isinstance(call.func,ast.Attribute) else None
                        if name in bindings:constructors.add(name)
                        target=None
                        if isinstance(call.func,ast.Name):
                            parts=scope.split('.')
                            for length in range(len(parts),-1,-1):
                                candidate='.'.join(parts[:length]+[name])
                                if candidate in local_functions:
                                    target=candidate;break
                        elif (isinstance(call.func,ast.Attribute) and isinstance(call.func.value,ast.Name)
                              and call.func.value.id in ('self','cls')):
                            target=(owner+'.' if owner else '')+name
                        if target in local_functions and target not in seen:pending.append(target)
                method['local_helper_scopes']=sorted(seen-{method['scope']})
                method['locally_reachable_constructors']=sorted(constructors)
            for unused in roles.keys()-used_roles:
                role_errors.append(dict(file=relative,scope=unused,error='Role declaration matches no test'))
            files.append(dict(file=relative,test_fixture=test,construction_sites=len(sites)-start))
    architecture_path=root/'spec/analog-architecture.json';drift=[]
    if architecture_path.is_file():
        from converter_dynamics import SARParameters,parameters_from_inventory
        from dataclasses import asdict
        architecture=json.loads(architecture_path.read_text())
        bare=asdict(SARParameters());selected=asdict(parameters_from_inventory(architecture))
        drift=[dict(parameter=k,primitive_default=bare[k],selected=selected[k]) for k in selected if bare[k]!=selected[k]]
    return dict(status='mixed_test_roles_alignment_requires_review',
        python_files=len(files),test_files=sum(f['test_fixture'] for f in files),
        test_methods=test_methods,static_test_method_count=len(test_methods),
        declared_role_counts=dict(Counter(method['declared_role'] for method in test_methods)),
        role_declaration_errors=role_errors,
        role_declaration_scope='Reviewed test intent, not automatic proof of parameter ownership. Method declarations override class declarations; unclassified tests remain explicit work items.',
        test_inventory_scope='Syntactic test_ definitions, not runtime discovery; same-file setup/self helpers are traced conservatively; inheritance, aliases, dynamic calls and imported wrappers require review. Constructor presence is not an acceptance verdict.',
        construction_counts=dict(Counter(s['binding'] for s in sites)),
        non_test_file_construction_counts=dict(Counter(s['binding'] for s in sites if not s['test_fixture'])),
        selected_vs_primitive_converter_differences=drift,parse_errors=errors,sites=sites,
        files_without_tracked_constructors=[f['file'] for f in files if not f['construction_sites']],
        policy='Simplified assumptions and deliberately adverse cases are valid exceptions, not consistency failures. Current-design integration uses architecture inventory/factories plus explicit recorded variations. Unit/analytical tests may instantiate primitives. Legacy and adverse controls retain their assumptions and cannot establish current-design acceptance.',
        scope='Static call-site inventory of Python model/verification trees, not interprocedural proof. Wrappers, aliases, JSON loading and patched parameters require review. A factory call alone does not prove all constants, waveforms or gates match. SPICE/device experiments and files without tracked constructors are not certified by this audit. Use per-section source freshness and runtime resolved parameters as separate evidence.')


def pad_behavioral_inventory(*,design=None):
    """Specification coverage and parameter accounting, not pad qualification."""
    import sys
    sys.path.insert(0,str(CONTRACT.parent.parent/'system_model/architecture_fast'))
    from design_definition import load_design
    design=load_design() if design is None else design
    architecture=design.architecture
    pad=architecture['pad_behavioral_contract'];rows=[]
    require(set(pad['states'])=={'active_receive','active_transmit','disabled','reset','unpowered','brownout','reconfiguration'},
            'Pad state coverage incomplete')
    for family,spec in pad['families'].items():
        require(bool(spec['parameter_owner']) and bool(spec['model']) and bool(spec['behavior']),
                'Pad family lacks parameter/model/behavior ownership')
        require(all(block in architecture['blocks'] for block in spec['blocks']),'Unknown pad block')
        rows.append(dict(family=family,parameter_owner=spec['parameter_owner'],model=spec['model'],
                         unqualified=spec['unqualified']))
    n=pad['shared_wired_network'];effective=n['base_shunt_cap_f_per_leg']+n['inactive_branch_cap_f_per_leg']+2*n['mutual_cap_f']
    require(abs(effective-architecture['blocks']['wirepad']['parameters']['capacitance_f_per_leg'])<1e-24,
            'Pad capacitance accounting disagrees with selected wired allocation')
    return dict(design_provenance=design.provenance(),status=pad['status'],families=rows,states=pad['states'],
        wired_odd_mode_capacitance_f_per_leg=effective,unknown_limits=n['unknown_limits'],
        scope='Behavioral specification and partial model bindings only. Unknown limits are not zero; no ESD, device-stress or fabrication qualification follows.')


def reconstruct_reported_design(base, provenance):
    """Verify a recorded variant by replaying its declared changes from the base."""
    current=base
    for experiment in provenance.get('circuit_experiments',[]):
        if experiment.get('kind')!='hypothetical_circuit' or experiment.get('parent_design_fingerprint')!=current.fingerprint:
            raise ValueError('Unverifiable circuit experiment parent')
        changes=experiment['changes']
        paths=[entry['path'] for entry in changes]
        if len(set(paths))!=len(paths):raise ValueError('Duplicate circuit experiment changes')
        for entry in changes:
            value=current.architecture
            for part in entry['path'].split('.'):value=value[part]
            if value!=entry['before']:raise ValueError('Circuit experiment before-value differs from parent')
        current=current.hypothetical(reason=experiment['reason'],changes={entry['path']:entry['after'] for entry in changes})
    if current.provenance()!=provenance:
        raise ValueError('Recorded design provenance does not match reconstructed snapshot')
    return current


def verify_reported_configuration(design, record):
    """Recompute derived rates and ownership rather than trusting saved fields."""
    from dataclasses import fields
    from design_definition import ResolvedConfiguration
    if not isinstance(record,dict):raise ValueError('Resolved configuration record required')
    settings={field.name:record[field.name] for field in fields(ResolvedConfiguration)
              if field.name!='design' and field.name in record}
    configuration=design.configure(**settings)
    if configuration.record()!=record:
        raise ValueError('Recorded configuration differs from resolved shared design')
    return configuration


def rf_chain_evidence_audit(root=None):
    """Independent, scoped audit of the first RF-chain matrix; not RF signoff."""
    import hashlib
    root=Path(root) if root is not None else CONTRACT.parent.parent
    path=root/'evidence/selected-revision-check.json'
    cases=json.loads(path.read_text()).get('rf_chain_first_version',{}).get('cases',{}) if path.exists() else {}
    expected={'wideband_nominal','wideband_weak','wideband_adverse','wideband_failure_control',
        'wideband_gain36','wideband_mid_gain36','wideband_weak_gain36','wideband_gain36_rf_corner',
        'narrowband_nominal','narrowband_weak','narrowband_adverse','narrowband_failure_control',
        'narrowband_rf_corner','tx_nominal','tx_adverse'}
    needed={'wideband_mid_gain36','wideband_weak_gain36','narrowband_nominal','narrowband_weak','tx_nominal','tx_adverse'}
    from dataclasses import asdict
    from converter_dynamics import parameters_from_inventory
    import sys
    sys.path.insert(0,str(CONTRACT.parent.parent/'system_model/architecture_fast'))
    from rf_quality_budget import current_allocation
    architecture_path=root/'spec/analog-architecture.json'
    architecture=json.loads(architecture_path.read_text()) if architecture_path.is_file() else None
    from design_definition import DesignDefinition
    contract_path=root/'spec/contract.json'
    expected_provenance=(DesignDefinition.from_documents(json.loads(contract_path.read_text()),architecture).provenance()
                         if architecture is not None and contract_path.is_file() else None)
    expected_converter=json.loads(json.dumps(asdict(parameters_from_inventory(architecture)))) if architecture else None
    required_sources={'spec/analog-architecture.json','spec/contract.json',
        'verification/baseline_envelope.py','verification/converter_dynamics.py',
        'verification/selected_revision_check.py'}
    digests={};rows=[];usable=set();current=set();bound=set()
    def rail_ok(interval):return len(interval)==2 and 2.5<=min(interval)<=max(interval)<=3.6
    for name in sorted(expected & cases.keys()):
        r=cases[name];manifest=r.get('sources_sha256',{});changed=[]
        for filename,digest in manifest.items():
            if filename not in digests:
                source=root/filename
                digests[filename]=hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None
            if digests[filename]!=digest:changed.append(filename)
        fresh=bool(manifest) and not changed
        if fresh:current.add(name)
        row=dict(name=name,status=r['status'],sources_match=fresh,changed_sources=changed,
            claimed_accepted=r.get('accepted',False),reason=r.get('reason'))
        binding=r.get('design_binding',{})
        inventory_mode='rf_tx' if r.get('mode')=='tx' else 'rf_rx'
        expected_current=(current_allocation(architecture,inventory_mode,branch='external_rf_clock')
                          if architecture else None)
        provenance=r.get('design_provenance',{})
        # Unbound synthetic audit fixtures may use their supplied architecture.
        # A claimed design must reconstruct before any physical limit is trusted.
        evaluation_architecture=architecture if not provenance else None
        provenance_ok=(expected_provenance is not None and all(
            provenance.get(key)==expected_provenance[key] for key in ('design_fingerprint','documents')))
        binding_ok=(architecture is not None and provenance_ok and required_sources<=manifest.keys()
            and r.get('mode')==name.split('_',1)[0]
            and binding.get('inventory_mode')==inventory_mode
            and binding.get('current_report')==expected_current
            and binding.get('converter_parameters')==expected_converter
            and r.get('inventory_current_ma')==expected_current['total_ma'])
        if binding_ok:bound.add(name)
        row['selected_design_binding_matches']=binding_ok
        row['shared_design_provenance_matches']=provenance_ok
        # Variant lineage is separate from nominal acceptance. A valid adverse
        # snapshot must not silently count as the selected implementation.
        row['declared_variant_provenance_verified']=False
        row['resolved_configuration_verified']=False
        row['declared_variant_binding_matches']=False
        if architecture is not None and contract_path.is_file():
            try:
                reconstructed=reconstruct_reported_design(
                    DesignDefinition.from_documents(json.loads(contract_path.read_text()),architecture),provenance)
                row['declared_variant_provenance_verified']=True
                evaluation_architecture=reconstructed.architecture
                row['declared_variant_is_nominal']=reconstructed.fingerprint==expected_provenance['design_fingerprint']
                try:
                    configuration=verify_reported_configuration(reconstructed,r.get('resolved_configuration'))
                    row['resolved_configuration_verified']=True
                    variant_architecture=reconstructed.architecture
                    variant_current=current_allocation(variant_architecture,configuration.inventory_mode,branch='external_rf_clock')
                    variant_converter=json.loads(json.dumps(asdict(parameters_from_inventory(variant_architecture))))
                    row['declared_variant_binding_matches']=(
                        required_sources<=manifest.keys()
                        and binding.get('inventory_mode')==configuration.inventory_mode==inventory_mode
                        and binding.get('current_report')==variant_current
                        and binding.get('converter_parameters')==variant_converter
                        and r.get('inventory_current_ma')==variant_current['total_ma'])
                except (ValueError,KeyError,TypeError) as error:
                    row['resolved_configuration_error']=str(error)
            except (ValueError,KeyError,TypeError,AttributeError) as error:
                row['declared_variant_provenance_error']=str(error)
        checks={};metrics={}
        if 'receiver' in r:
            wide=r['mode']=='wideband';rx=r['receiver']
            if wide:
                frontend=rx['analog']['receiver'];gain=frontend['gain_cases'][0];adc=gain['adc']
                checks=dict(payload=rx['payload_correct'],feedback=rx['analog']['numerical_feedback_converged'])
                rails=frontend['observed_rail_interval_v'];clips=gain['pga_clipped_samples_during_source']
                compression=frontend['frontend_nonlinearity']['within_assigned_small_compression_range']
            else:
                adc=rx['converter'];rails=adc['evaluated_supply_interval_v'];clips=rx['gain_control']['pga_clipped_samples']
                compression=rx['frontend_nonlinearity']['within_assigned_small_compression_range']
                checks=dict(payload=rx['correct_request'],feedback=rx['reference_feedback']['numerical_feedback_converged'])
            peak=(frontend if wide else rx).get('pga_nominal_peak_limit_v')
            peak_bound=(isinstance(peak,(int,float)) and not isinstance(peak,bool)
                and math.isfinite(peak) and peak>0 and evaluation_architecture is not None
                and all(peak==evaluation_architecture['blocks'][lane]['parameters']['differential_peak_limit_v']
                        for lane in ('pga_i','pga_q')))
            checks.update(rail_domain=rail_ok(rails) and rail_ok(adc['evaluated_supply_interval_v']),
                pga_not_clipped=clips==0,frontend_model_valid=compression,
                converter_schedule=adc['schedule_margin_s']>=0 and adc['actual_completion_margin_s']>=0,
                reference_current=(evaluation_architecture is not None and adc['reference_with_bias_peak_a']<=
                    evaluation_architecture['blocks']['refbuf']['resource_allocation']['current_budget_ma'][inventory_mode]/1000),
                pga_headroom_design_binding=peak_bound,
                adc_headroom=peak_bound and peak*max(rails)/evaluation_architecture['model_assumptions']['rf_receive_supply']['parameters']['headroom_reference_v']<min(adc['reference_interval_v']))
            metrics.update(wanted_dbm=r['wanted_dbm'],blocker_dbm=r['blocker_dbm'],pga_clipped_samples=clips,
                converter_completion_margin_s=adc['actual_completion_margin_s'],rail_interval_v=rails)
            if not wide:
                tx=r.get('transmitter',{});electrical=tx.get('electrical',{})
                actual_rf_budget=r.get('tx_clock',{}).get('ledger',{}).get('owner_current_a',{}).get('rf')
                checks.update(reply_decode=tx.get('peer_correct_response',False),
                    reply_rail=rail_ok(tx.get('evaluated_supply_interval_v',[])),
                    reply_electrical=bool(electrical.get('checks')) and all(electrical.get('checks',{}).values()),
                    actual_driver_allocation=actual_rf_budget is not None and electrical.get('driver_bias_current_a',float('inf'))<=actual_rf_budget,
                    reply_tx_configuration=r.get('tx_resolved_configuration',{}).get('direction')=='tx',
                    same_rf_pad_network=tx.get('reactive_load') is not None,
                    reply_mixer_headroom=bool(r.get('tx_checks',{}).get('mixer_headroom')))
        elif 'transmitter' in r:
            tx=r['transmitter'];e=tx['electrical']
            checks=dict(rail_domain=rail_ok(tx['observed_rail_interval_v']),electrical=all(e['checks'].values()),
                driver_allocation=e['driver_bias_current_a']<=r['clock']['ledger']['owner_current_a']['rf'],
                driver_not_clipped=tx['driver_current_clipped_samples_during_source']==0,
                host_not_clipped=tx['host_input_clipped_components']==0,
                diagnostic_bpsk=tx['observation']['bpsk_errors']==0,
                target_power=(evaluation_architecture is not None and r['loaded_mean_power_dbm']>=
                    evaluation_architecture['blocks']['rfdriver']['parameters']['target_mean_power_dbm']),
                mixer_headroom=r['checks']['mixer_headroom'],
                rf_pad_network=tx.get('reactive_load') is not None)
            metrics.update(loaded_mean_power_dbm=r['loaded_mean_power_dbm'],diagnostic_evm_rms=tx['observation']['evm_rms'])
        accepted=bool(checks) and all(checks.values())
        row.update(independent_checks=checks,conditional_point=accepted,metrics=metrics)
        row['nominal_evidence_usable']=bool(fresh and accepted and binding_ok
            and row['resolved_configuration_verified'] and row['declared_variant_binding_matches'])
        if row['nominal_evidence_usable']:usable.add(name)
        rows.append(row)
    common=[cases[n] for n in needed if n in cases]
    common_environment=len(common)==len(needed) and all(
        next(row['selected_design_binding_matches'] for row in rows if row['name']==name)
        and next(row['resolved_configuration_verified'] for row in rows if row['name']==name)
        and cases[name].get('carrier_hz')==2.426e9 and
        cases[name].get('package')==dict(return_l_h=.25e-9,die_esl_h=.2e-9) for name in needed)
    complete=expected<=current and expected<=bound and needed<=usable and common_environment
    return dict(first_version_complete=complete,missing_cases=sorted(expected-cases.keys()),
        stale_or_missing_cases=sorted(expected-current),
        missing_selected_design_bindings=sorted(expected-bound),missing_usable_anchors=sorted(needed-usable),
        common_environment=common_environment,cases=rows,
        scope='First-version sampled conditional RF region only. Wideband diagnostic coded BPSK uses legacy acquisition and nonstandard HE DATA training; narrowband is LE1M. One seed per mode, not PER or standards compliance. Fixed package and assigned source/device laws; no continuous uncertainty enclosure, physical implementation proof, full RF startup/turnaround or spectral-mask qualification. All other transceiver milestone gates remain open.')


def milestone_coverage(c, closure=None):
    """Coverage inventory only; passing structure is not milestone acceptance."""
    if closure is None:
        closure=json.loads((CONTRACT.parent/'mathematical-closure.json').read_text())
    milestone=closure['milestone']
    intended=c['generic_control_surface']['external_interface_requirements']
    coverage=milestone['capability_coverage']
    require(set(coverage)==set(intended),'milestone must retain every intended capability')
    require(set(milestone['scope_inventory']['capability_ids'])==set(intended),
            'scope inventory differs from generic interface requirements')
    dimensions=set(milestone['acceptance_dimensions'])
    required={'electrical','timing','signal_quality','power','area','fpga_service'}
    require(dimensions==required,'milestone acceptance dimensions incomplete')
    rows=[];clock_rows=operating_clock_ledger(c)['configurations']
    for name,services in intended.items():
        item=coverage[name]
        require(item['generic_services']==services,f'{name}: stale generic service mapping')
        require(set(item['acceptance_dimensions'])==required,f'{name}: missing acceptance dimension')
        bindings=item.get('requirements',{})
        require(set(bindings)==required,f'{name}: concrete requirement mappings missing')
        require(bindings['area']['per_die_allocation_um2']==c['limits']['core_area_um2'],
                f'{name}: stale per-die area allocation')
        for dimension,entry in bindings.items():
            require(bool(entry.get('owner')),f'{name}/{dimension}: missing requirement owner')
            require((CONTRACT.parent.parent/entry['owner'].split(':')[0]).is_file(),
                    f'{name}/{dimension}: missing owner file')
        require(bool(item.get('primary_open_decision')) and bool(item.get('decision_family')),
                f'{name}: missing architectural decision')
        # Owners identify where requirements belong, not whether they are satisfied.
        rows.append(dict(capability=name,verdict=item['verdict'],requirements=bindings,
            decision_family=item['decision_family'],primary_open_decision=item['primary_open_decision'],
            promotion_gate=item['evidence_gate'],
            host_service=capability_host_service(c,name,item,clock_rows),
            dimension_status={key:milestone['acceptance_dimensions'][key]['status'] for key in sorted(required)},
            dimension_scope='Shared inventory statuses; no per-capability numerical acceptance inferred.',
            selected_clock_mapping=item.get('selected_clock_mapping'),
            roles=milestone['scope_inventory'].get('role_obligations',{}).get(name,[])))
    open_criteria=[dict(id=x['id'],status=x['status'],gap=x['current_gap'])
                   for x in milestone['criteria'] if x['status']!='complete']
    unresolved=[x['capability'] for x in rows if x['verdict']=='unresolved']
    require(not (milestone['complete'] and (open_criteria or unresolved)),
            'milestone completion contradicts recorded open requirements')
    return dict(scope='Structural coverage and recorded gaps only; not independent performance verification.',
        declared_complete=milestone['complete'],capabilities=rows,
        unresolved_capabilities=unresolved,open_criteria=open_criteria,
        next_priority='One selected shared analog operating envelope and persistent lifecycle; protocol acceptance tuples remain incomplete.')


if __name__ == '__main__':
    import sys
    sys.path.insert(0,str(CONTRACT.parent.parent/'system_model/architecture_fast'))
    from design_definition import load_design
    design=load_design()
    print(json.dumps({'scope': 'planning arithmetic only; not implementation qualification',
                      'design_provenance': design.provenance(),
                      'modes': check(design.contract),
                      'resource_ledger': resource_ledger(design.contract),
                      'milestone_coverage': milestone_coverage(design.contract),
                      'review_evidence': review_evidence_freshness(),
                      'pad_behavioral_inventory': pad_behavioral_inventory(design=design),
                      'simulation_design_audit': simulation_design_audit(),
                      'rf_chain_first_version': rf_chain_evidence_audit()}, indent=2))
