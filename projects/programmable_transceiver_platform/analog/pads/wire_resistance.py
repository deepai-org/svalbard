"""PDK-sheet-resistance screen of the generator's bond-to-core signal routes.

This is a traced-route estimate, not 2D/distributed extraction. It deliberately
excludes vias, device access and return resistance; capacitor-only simulations
must not be mistaken for a bond-port impedance result.
Run in the pinned container to read the installed Magic technology file.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
from circuits import build
from design import PROJECT
from layout import trunk_geometry


def screen(generated,tech):
    text=tech.read_text()
    if 'Resistances are in milliohms per square' not in text:
        raise ValueError('Recheck installed extraction resistance units')
    values={i:[float(x)/1000 for x in re.findall(rf'^\s*resist \(allm{i}\)/metal{i}\s+([\d.]+)',text,re.M)] for i in range(1,6)}
    if any(len(v)!=3 for v in values.values()):raise ValueError('Recheck nominal/high/low extraction variants')
    # These are the installed technology's extraction variants, not measured
    # wafer/package bounds. Their order is checked explicitly in the source.
    markers=['variants ()','variants (hrhc),(hrlc)','variants (lrhc),(lrlc)']
    positions=[text.index(m,text.index('# Layer resistance')) for m in markers]
    if positions!=sorted(positions):raise ValueError('Extraction variant ordering changed')
    generator=Path(__file__).with_name('layout.py')
    generator_text=generator.read_text()
    for expression in ["tracks,trunk_widths=trunk_geometry(nets)", "(.22 if layer == 'metal5' else .2)", "('P',37.5,active_origin-12)","('N',37.5+bond_pitch,active_origin-4)"]:
        if expression not in generator_text:raise ValueError('Recheck generator route formulas')
    families={};connected={}
    for family in ('wired_transmit','wired_receive_usb','reference_clock','rf_receive','rf_transmit'):
        stem=family.replace('_','-');meta=generated/(stem+'-layout.json');gds=generated/(stem+'.gds')
        report=json.loads(meta.read_text())
        if report.get('connected_protection'):
            route=generated/(stem+'-route-resistance.json')
            if not route.exists():raise ValueError('Connected RF pad lacks its route model')
            connected[family]=dict(report=route.name,sha256=hashlib.sha256(route.read_bytes()).hexdigest(),
                scope='Use this connected-protection overlay; generic four-device route formulas do not apply.')
            continue
        for relative,digest in report['sources_sha256'].items():
            if hashlib.sha256((PROJECT/relative).read_bytes()).hexdigest()!=digest:
                raise ValueError('Layout metadata is stale: '+relative)
        cell=build(family);nets=sorted({n for d in cell.devices for n in d.nodes});tracks,widths=trunk_geometry(nets)
        if tracks!=report['net_track_x_um'] or widths!=report['net_trunk_widths_um']:
            raise ValueError('Trunk geometry differs from physical report')
        legs={}
        for leg,cx,depth in [('P',37.5,12),('N',37.5+report['bond_pitch_um'],4)]:
            y=report['active_origin_um']-depth;port_y=report['port_heights_um']['PAD_'+leg]
            segments=[dict(layer=2,length_um=y-62,width_um=report['escape_width_um'],role='bond corridor'),
                      dict(layer=4,length_um=abs(cx-tracks['PAD_'+leg]),width_um=report['pad_transverse_width_um'],role='core-side transverse route'),
                      dict(layer=5,length_um=abs(port_y-y),width_um=report['pad_trunk_width_um'],role='trunk to declared core port')]
            corners={}
            for index,name in enumerate(('nominal','high_resistance','low_resistance')):
                contributions=[v['length_um']/v['width_um']*values[v['layer']][index] for v in segments]
                corners[name]=dict(metal_only_ohm=sum(contributions),segment_ohm=contributions)
            legs[leg]=dict(route_segments=segments,corners=corners)
        power_trunks={}
        for net in ('VDD','VSS'):
            if net not in widths:continue
            lo,hi=report['net_trunk_spans_um'][net]
            if net=='VSS':lo=min(lo,report['active_origin_um']-20)
            power_trunks[net]=dict(length_um=hi-lo,width_um=widths[net],
                metal_only_end_to_end_ohm={name:(hi-lo)/widths[net]*values[5][i]
                    for i,name in enumerate(('nominal','high_resistance','low_resistance'))},
                scope='Single M5 trunk only; not branch-to-board resistance, IR-drop simulation or current capacity. Local access, vias, transverse returns, ring and core mesh remain excluded.')
        families[family]=dict(legs=legs,power_trunks=power_trunks,nominal_pair_series_ohm=sum(v['corners']['nominal']['metal_only_ohm'] for v in legs.values()),
            nominal_leg_difference_ohm=abs(legs['P']['corners']['nominal']['metal_only_ohm']-legs['N']['corners']['nominal']['metal_only_ohm']),
            layout_report_sha256=hashlib.sha256(meta.read_bytes()).hexdigest(),gds_sha256=hashlib.sha256(gds.read_bytes()).hexdigest())
    return dict(status='generator_route_sheet_resistance_screen_not_distributed_extraction',families=families,connected_protection_route_reports=connected,
        metal_sheet_ohm_per_square={name:{str(layer):values[layer][index] for layer in values}
            for index,name in enumerate(('nominal','high_resistance','low_resistance'))},
        limitations=['Uses verified current generator geometry and installed PDK sheet values, not measured silicon.',
            'Length/width route estimate omits overlap/current-spreading corrections, vias, device access, branch routes and supply/ground return.',
            'Declared core port is the endpoint; individual branch devices attach at other positions along the trunk. Do not insert this number as a resistor on every branch.',
            'Existing extracted-capacitance simulations do not include these series losses. No broadband or ESD verdict.'],
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),generator,tech)})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--generated',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--tech',type=Path,default=Path('/pdk/gf180mcuD/libs.tech/magic/gf180mcuD.tech'))
    a=p.parse_args();r=screen(a.generated,a.tech);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({k:{leg:v['corners']['nominal']['metal_only_ohm'] for leg,v in d['legs'].items()} for k,d in r['families'].items()}))
