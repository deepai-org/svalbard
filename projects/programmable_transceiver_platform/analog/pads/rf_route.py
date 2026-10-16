"""Geometry-derived RF signal resistance, with explicit capacitance-location probes.

Not distributed PEX: via/return resistance and spatial capacitance are unknown.
Protection taps are kept near the bond instead of behind the entire core route.
"""
import hashlib
import json
from pathlib import Path
from design import PROJECT


def augment(model, family, report_path, capacitance_location='bond', corner='nominal'):
    if family not in ('rf_receive', 'rf_transmit'):
        raise ValueError('Only the four-device RF protection topology is supported')
    if capacitance_location not in ('bond', 'core'):
        raise ValueError('Capacitance location must be bond or core')
    if corner not in ('nominal', 'high_resistance', 'low_resistance'):
        raise ValueError('Unknown metal resistance corner')
    report_path=Path(report_path)
    report=json.loads(report_path.read_text())
    if report.get('status')=='full_protected_rf_pad_route_resistance':
        from protected_rf_route import augment as augment_protected
        return augment_protected(model,report_path,capacitance_location,corner)
    root=report_path.parent; stem=family.replace('_','-')
    route=report['families'][family]
    for suffix,key in [('-layout.json','layout_report_sha256'),('.gds','gds_sha256')]:
        if hashlib.sha256((root/(stem+suffix)).read_bytes()).hexdigest()!=route[key]:
            raise ValueError('Stale resistance geometry: '+stem+suffix)
    meta=json.loads((root/(stem+'-layout.json')).read_text())
    for relative,digest in meta['sources_sha256'].items():
        if hashlib.sha256((PROJECT/relative).read_bytes()).hexdigest()!=digest:
            raise ValueError('Stale layout source: '+relative)
    if len(meta['pcell_terminal_coordinates'])!=1:
        raise ValueError('Recheck RF primitive topology')
    dx,dy=next(iter(meta['pcell_terminal_coordinates'].values()))[0]
    tap_y=meta['protection_device_centers_y_um']+dy
    sheet=report['metal_sheet_ohm_per_square'][corner]['2']
    segments={}; extra=[]
    for leg in ('P','N'):
        data=route['legs'][leg]; corridor=data['route_segments'][0]
        if corridor['role']!='bond corridor' or corridor['layer']!=2:
            raise ValueError('Unknown corridor topology')
        before=(tap_y-62)/corridor['width_um']*sheet
        total=data['corners'][corner]['metal_only_ohm']
        if not 0<before<total:raise ValueError('Protection tap outside route')
        arms=[abs(x+dx-37.5)*sheet for x in (25.,50.)]  # 1um M2 arms
        segments[leg]=dict(bond_to_tap_ohm=before,tap_to_core_ohm=total-before,
                           protection_arm_ohm=arms,core_path_total_ohm=total)
        extra += [f'Rroute_{leg}_bond PAD_{leg} TAP_{leg} {before:.12g}',
                  f'Rroute_{leg}_core TAP_{leg} COREPAD_{leg} {total-before:.12g}']
        for i,resistance in enumerate(arms):
            extra.append(f'Rroute_{leg}_clamp{i} TAP_{leg} CLAMP_{leg}_{i} {resistance:.12g}')
    lines=[];counts={'P':0,'N':0};device_records=[];cap_records=[]
    for line in model.splitlines():
        fields=line.split()
        if not fields:continue
        if fields[0]=='.subckt':
            if fields[2:]!=['PAD_P','PAD_N','VSS']:raise ValueError('Unexpected RF ports')
            line+=' COREPAD_P COREPAD_N'
        elif fields[0].startswith('X'):
            if fields[1] not in ('PAD_P','PAD_N') or fields[2:6]!=['VSS','VSS','VSS','nfet_06v0_dss']:
                raise ValueError('Unexpected RF device branch')
            leg=fields[1][-1];i=counts[leg];counts[leg]+=1
            fields[1]=f'CLAMP_{leg}_{i}'
            device_records.append(fields[2:]);line=' '.join(fields)
        elif fields[0].startswith('C'):
            cap_records.append(fields)
            if capacitance_location=='core':
                fields=[f.replace('PAD_P','COREPAD_P').replace('PAD_N','COREPAD_N') if i in (1,2) else f for i,f in enumerate(fields)]
            line=' '.join(fields)
        elif fields[0]=='.ends':lines.extend(extra)
        elif not fields[0].startswith('*'):
            raise ValueError('Unhandled physical netlist record '+fields[0])
        lines.append(line)
    if counts!={'P':2,'N':2}:raise ValueError('Expected two protection devices per leg')
    if device_records[1:]!=device_records[:-1]:
        raise ValueError('Protection units differ; cannot infer physical ordering')
    if len(cap_records)!=3:raise ValueError('Recheck extracted RF capacitance topology')
    return '* Segmented signal-metal estimate; capacitance placement is a sensitivity probe.\n'+'\n'.join(lines)+'\n',dict(
        status='segmented_metal_estimate_not_distributed_extraction',corner=corner,
        extracted_capacitance_location_probe=capacitance_location,segments=segments,
        limitations=['Via, device contact, metal spreading and ground-return resistance omitted.',
                     'All extracted interconnect capacitance placed at one endpoint as a sensitivity probe, not a rigorous bound.',
                     'Protection compact-model capacitance remains at its near-bond branch.',
                     'Nominal/high/low sheet values are PDK extraction variants, not measured silicon bounds.'],
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                      (report_path,root/(stem+'-layout.json'),Path(__file__))})


if __name__=='__main__':
    import argparse
    from analog_screen import screen
    parser=argparse.ArgumentParser()
    parser.add_argument('--generated',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--pdk-model-dir',type=Path,required=True)
    args=parser.parse_args()
    work=args.output_dir.resolve();generated=args.generated.resolve()
    if work.exists() and any(work.iterdir()):
        raise ValueError('Use an empty output directory to exclude stale waveforms')
    results={}
    for family in ('rf_receive','rf_transmit'):
        for corner in ('nominal','high_resistance'):
            for location in ('bond','core'):
                name=f'{family}-{corner}-{location}'
                target=work/name
                screen(target,args.pdk_model_dir.resolve(),
                       generated/(family.replace('_','-')+'-extracted-c.spice'),family,
                       route_report=generated/'wire-resistance.json',
                       capacitance_location=location,resistance_corner=corner)
                results[name]=json.loads((target/'screen-report.json').read_text())
    complete=all(r['transient_complete'] and r.get('stale_enable_diagnostic',{}).get('transient_complete',True) and all(s['status']=='window_reached_not_acceptance'
                 for s in r['states'].values()) for r in results.values())
    architecture=json.loads((PROJECT/'spec/analog-architecture.json').read_text())
    maximum_gain=architecture['blocks']['rfdriver']['parameters']['gain_range'][1]
    gain_cases={}
    for corner in ('nominal','high_resistance'):
        for location in ('bond','core'):
            name=f'rf_transmit-{corner}-{location}-maximum_gain'
            gain_cases[name]=screen(work/name,args.pdk_model_dir.resolve(),
                generated/'rf-transmit-extracted-c.spice','rf_transmit',
                route_report=generated/'wire-resistance.json',capacitance_location=location,
                resistance_corner=corner,rf_tx_gain=maximum_gain)
    complete=complete and all(r['transient_complete'] and r.get('stale_enable_diagnostic',{}).get('transient_complete',True) and all(s['status']=='window_reached_not_acceptance'
                 for s in r['states'].values()) for r in gain_cases.values())
    (work/'rf-route-screen.json').write_text(json.dumps(dict(
        status='geometry_derived_metal_loss_sensitivity_not_PEX',
        all_retained_windows_reached=complete,cases=results,maximum_gain_cases=gain_cases),indent=2)+'\n')
    if not complete:raise RuntimeError('RF route campaign did not reach all retained windows')
