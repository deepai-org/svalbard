"""Branched wired-TX signal-metal estimate; not distributed PEX.

Preserve the primary-protection tap before the core branch. Extracted linear
capacitance stays at the core endpoint as an explicit location assumption;
physical steering-diode capacitance stays on the protection branch.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path


def geometry(layout, routes, sheets, corner):
    index={'nominal':0,'high_resistance':1,'low_resistance':2}[corner]
    if len(routes)!=9:raise ValueError('Expected two three-segment primary arms and three return segments')
    def resistance(layer,length,width):
        sheet=sheets[str(layer)][index]
        if not all(math.isfinite(v) for v in (length,width,sheet)) or length<0 or width<=0 or sheet<=0:
            raise ValueError('Invalid route geometry or sheet value')
        return length/width*sheet
    result={}
    for i,leg in enumerate(('P','N')):
        primary=routes[3*i:3*i+3]
        cx=37.5+i*layout['bond_pitch_um']
        tap=primary[0]['start_um']
        if tap[0]!=cx or [s['layer'] for s in primary]!=[4,5,4]:raise ValueError('Unexpected primary tap')
        if any(a['end_um']!=b['start_um'] for a,b in zip(primary,primary[1:])):raise ValueError('Disconnected primary arm')
        # These endpoints are the explicit selected layout.py bond/core recipe.
        bond_top=62.;bend=layout['active_origin_um']-(12 if leg=='P' else 4)
        core_y=layout['port_heights_um']['PAD_'+leg]
        if not bond_top<tap[1]<=bend<=core_y:raise ValueError('Unexpected bond/tap/core ordering')
        common=resistance(2,tap[1]-bond_top,layout['escape_width_um'])
        core=(resistance(2,bend-tap[1],layout['escape_width_um'])+
              resistance(4,abs(cx-layout['net_track_x_um']['PAD_'+leg]),layout['pad_transverse_width_um'])+
              resistance(5,core_y-bend,layout['net_trunk_widths_um']['PAD_'+leg]))
        protection=0.
        for segment in primary:
            a,b=segment['start_um'],segment['end_um']
            if a[0]!=b[0] and a[1]!=b[1]:raise ValueError('Non-Manhattan primary arm')
            protection+=resistance(segment['layer'],abs(a[0]-b[0])+abs(a[1]-b[1]),segment['width_um'])
        result[leg]=dict(common_bond_lead_ohm=common,core_branch_ohm=core,
            protection_branch_ohm=protection,bond_top_y_um=bond_top,tap_y_um=tap[1],
            declared_core_port_y_um=core_y,primary_segments=primary)
    return result


def augment(model, branches):
    lines=re.sub(r'\n\s*\+\s*',' ',model).splitlines()
    definitions=[l.split()[1] for l in lines if l.startswith('.subckt ')]
    if len(definitions)!=2:raise ValueError('Expected protected wrapper and extracted flat cell')
    inner=definitions[1];active=False;result=[]
    counts={leg:dict(protection_diodes=0,core_devices=0,linear_capacitors=0) for leg in branches}
    for line in lines:
        fields=line.split()
        if fields and fields[0]=='.subckt':active=fields[1]==inner
        if active and fields:
            if fields[0]=='.ends':
                for leg,values in branches.items():
                    for label,a,b,key in [('BOND','PAD','TAP','common_bond_lead_ohm'),
                        ('CORE','TAP','ROUTE_CORE','core_branch_ohm'),
                        ('PRIMARY','TAP','ROUTE_PRIMARY','protection_branch_ohm')]:
                        value=values[key]
                        if not math.isfinite(value) or value<=0:raise ValueError('Positive finite branch resistance required')
                        result.append(f'RROUTE_{label}_{leg} {a}_{leg} {b}_{leg} {value:.15g}')
                active=False
            elif fields[0][0] in ('D','X','C'):
                for leg in branches:
                    old='PAD_'+leg
                    if old not in fields[1:]:continue
                    if fields[0][0]=='D':
                        if fields[3] not in ('diode_nd2ps_06v0','diode_pd2nw_06v0'):
                            raise ValueError('Unclassified pad diode')
                        end=3;new='ROUTE_PRIMARY_'+leg;kind='protection_diodes'
                    elif fields[0][0]=='C':
                        end=3;new='ROUTE_CORE_'+leg;kind='linear_capacitors'
                    else:
                        if fields[4].startswith('ppoly'):end=4
                        elif fields[5].startswith(('nfet_','pfet_')):end=5
                        else:raise ValueError('Unclassified pad-connected device')
                        new='ROUTE_CORE_'+leg;kind='core_devices'
                    counts[leg][kind]+=1
                    fields=[new if 0<i<end and token==old else token for i,token in enumerate(fields)]
                line=' '.join(fields)
        result.append(line)
    if any(c['protection_diodes']!=8 or not c['core_devices'] or not c['linear_capacitors'] for c in counts.values()):
        raise ValueError('Re-audit branch classification for changed pad topology')
    return '\n'.join(result)+'\n',counts


def build(output, physical, layout_path, routes_path, sheet_path, corner='nominal'):
    layout=json.loads(layout_path.read_text());routes=json.loads(routes_path.read_text())
    sheets=json.loads(sheet_path.read_text())['metal_sheet_ohm_per_square']
    branches=geometry(layout,routes,sheets,corner)
    text,counts=augment(physical.read_text(),branches)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(text)
    report=dict(status='branched_signal_metal_estimate_not_distributed_PEX',corner=corner,
        branches=branches,classification_counts=counts,
        model_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        limitations=['Linear extracted pad capacitance placed at the core endpoint; no rigorous capacitance-location bound.',
            'Primary steering-diode junctions remain on the protection arm; no clamp or branch is removed.',
            'Omit vias, contacts, spreading, ground returns and internal core buses beyond the declared core port.',
            'PDK sheet variants are extraction assumptions, not measured silicon bounds. No ESD or current-capacity qualification.'],
        source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (physical,layout_path,routes_path,sheet_path,Path(__file__))})
    output.with_suffix('.route.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('output','physical','layout','routes','sheets'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--corner',choices=('nominal','high_resistance','low_resistance'),default='nominal')
    a=p.parse_args();print(json.dumps(build(a.output,a.physical,a.layout,a.routes,a.sheets,a.corner),indent=2))
