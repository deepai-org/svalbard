"""Series-loss screen for the fully connected RF pad candidate.

Geometry-based sheet resistance, not distributed extraction or ESD qualification.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


def augment(model,report_path,capacitance_location,corner):
    report_path=Path(report_path);report=json.loads(report_path.read_text())
    if capacitance_location!='core':raise ValueError('Full-pad route probe puts extracted capacitance at the core endpoint')
    for path,digest in report['source_sha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:raise ValueError('Stale full-pad route source: '+path)
    if hashlib.sha256(model.encode()).hexdigest()!=report['physical_model_sha256']:raise ValueError('Route report belongs to another pad extraction')
    lines=model.splitlines();header=next(i for i,line in enumerate(lines) if line.startswith('.subckt '))
    if lines[header].split()[2:]!=['PAD_P','PAD_N','VSS']:raise ValueError('Unexpected outer RF pad ports')
    lines[header]+=' COREPAD_P COREPAD_N'
    instance=next(i for i in range(header+1,len(lines)) if lines[i].startswith('XPHYSICAL '))
    lines[instance]=' '.join({'PAD_P':'COREPAD_P','PAD_N':'COREPAD_N','VSS':'LOCAL_PAD_RETURN'}.get(t,t) for t in lines[instance].split())
    end=next(i for i in range(header+1,len(lines)) if lines[i].startswith('.ends'))
    lines[end:end]=[f"RBOND_{leg} PAD_{leg} COREPAD_{leg} {report['legs'][leg]['corners'][corner]['metal_only_ohm']:.12g}" for leg in ('P','N')]+[f"RRETURN LOCAL_PAD_RETURN VSS {report['ground_return']['corners'][corner]['external_metal_only_ohm']:.12g}"]
    return '\n'.join(lines)+'\n',dict(status='full_pad_series_metal_probe_not_distributed_PEX',corner=corner,capacitance_location='core',legs=report['legs'],ground_return=report['ground_return'],limitations=report['limitations'])


def run(work,generated,pdk,pad_dir=None):
    from layout import IMAGE
    from analog_screen import screen
    from protection_candidate import completion_flags
    work.mkdir(parents=True,exist_ok=False)
    pad=pad_dir or generated/'protected-rf-pair';meta=pad/'pad-layout.json';physical=pad/'pad-extracted.spice'
    report=json.loads(meta.read_text())
    for path,digest in report['source_sha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:raise ValueError('Stale pad source: '+path)
    if hashlib.sha256(physical.read_bytes()).hexdigest()!=report['extracted_spice_sha256']:raise ValueError('Changed pad extraction')
    generator=Path(__file__).with_name('protection_pad.py')
    tech=subprocess.run(['docker','run','--rm','--network','none','--entrypoint','python3',IMAGE,'-c','from pathlib import Path; print(Path("/pdk/gf180mcuD/libs.tech/magic/gf180mcuD.tech").read_text(),end="")'],check=True,capture_output=True,text=True,timeout=30).stdout
    if 'Resistances are in milliohms per square' not in tech:raise ValueError('Unknown resistance units')
    values={layer:[float(x)/1000 for x in re.findall(rf'^\s*resist \(allm{layer}\)/metal{layer}\s+([\d.]+)',tech,re.M)] for layer in (2,4,5)}
    if any(len(v)!=3 for v in values.values()):raise ValueError('Unexpected extraction corners')
    markers=['variants ()','variants (hrhc),(hrlc)','variants (lrhc),(lrlc)'];positions=[tech.index(m,tech.index('# Layer resistance')) for m in markers]
    if positions!=sorted(positions):raise ValueError('Changed extraction corner order')
    legs={}
    for r in report['geometry']['routes']:
        segments=[]
        for segment in r['segments']:
            a,b=segment['start_um'],segment['end_um']
            if a[0]!=b[0] and a[1]!=b[1]:raise ValueError('Non-Manhattan signal segment')
            segments.append(dict(layer=segment['layer'],length_um=abs(a[0]-b[0])+abs(a[1]-b[1]),width_um=segment['width_um'],role=segment['role']))
        corners={name:dict(metal_only_ohm=sum(t['length_um']/t['width_um']*values[t['layer']][i] for t in segments)) for i,name in enumerate(('nominal','high_resistance','low_resistance'))}
        legs[r['leg']]=dict(segments=segments,corners=corners)
    ground=report['geometry']['ground_routes'];network=report['network_routing']
    if len(ground)!=5 or {(r['a'],r['b']) for r in ground}!={('GND_P','TOP_P'),('TOP_P','JOIN'),('GND_N','TOP_N'),('TOP_N','JOIN'),('JOIN','PAD_RETURN')}:
        raise ValueError('Reassess return topology')
    ground_corners={}
    for i,name in enumerate(('nominal','high_resistance','low_resistance')):
        resistances={}
        for segment in ground:
            a,b=segment['start_um'],segment['end_um']
            length=abs(a[0]-b[0])+abs(a[1]-b[1])
            resistances[(segment['a'],segment['b'])]=length/segment['width_um']*values[segment['layer']][i]
        branches={leg:resistances[('GND_'+leg,'TOP_'+leg)]+resistances[('TOP_'+leg,'JOIN')] for leg in ('P','N')}
        common=resistances[('JOIN','PAD_RETURN')]
        effective=common+1/sum(1/value for value in branches.values())
        ground_corners[name]=dict(external_metal_only_ohm=effective,parallel_branch_ohm=branches,common_segment_ohm=common,
            internal_clamp_return_metal_ohm=network['return_route_length_um']/network['routing_parameters']['return_width_um']*values[4][i],
            internal_rail_metal_ohm=network['rail_route_length_um']/network['routing_parameters']['rail_width_um']*values[5][i])
    ground_return=dict(corners=ground_corners,scope='External ground traces terminate at two ideal retained ground landings. Their parallel equivalent is inserted outside the complete pad network; no additional core/substrate return path is assumed. Internal clamp return/rail estimates are reported separately and are not inserted into this common-return resistor.')
    model=work/'physical.spice';model.write_text(physical.read_text()+f'\n.lib {pdk}/sm141064.ngspice diode_typical\n.lib {pdk}/sm141064.ngspice mimcap_typical\n')
    sources=[Path(__file__),generator,meta,physical,pad/'pad.gds']
    route=dict(status='full_protected_rf_pad_route_resistance',legs=legs,ground_return=ground_return,physical_model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),technology_sha256=hashlib.sha256(tech.encode()).hexdigest(),metal_sheet_ohm_per_square=values,limitations=['Signal and external return metal length/width resistance included; vias, internal clamp/rail branch losses, spreading, substrate network and diode access omitted from transient model.','All extracted pad capacitance is placed after the series resistance as a sensitivity probe; this is not distributed PEX.','No protection-current or ESD stress verdict.'],source_sha256={str(path.resolve()):hashlib.sha256(path.read_bytes()).hexdigest() for path in sources})
    route_path=work/'route-resistance.json';route_path.write_text(json.dumps(route,indent=2)+'\n')
    (work/'.spiceinit').write_text('set ngbehavior=hs\n');previous=Path.cwd();results={}
    try:
        os.chdir(work)
        for family in ('rf_receive','rf_transmit'):
            results[family]=screen(work/family,pdk,model,family,route_report=route_path,capacitance_location='core',resistance_corner='high_resistance')
    finally:os.chdir(previous)
    flags=completion_flags(results)
    expected={'/rf_receive/finite_rx_bias/common_mode_envelope/transient_complete','/rf_receive/transient_complete','/rf_transmit/transient_complete','/rf_transmit/stale_enable_diagnostic/transient_complete'}
    result=dict(status='full_RF_pad_high_resistance_corner_sensitivity',all_screens_complete=set(flags)==expected and all(flags.values()),transient_completion_checks=flags,route=route,results=results,source_sha256={str(path.resolve()):hashlib.sha256(path.read_bytes()).hexdigest() for path in (Path(__file__),Path(__file__).with_name('rf_route.py'),Path(__file__).with_name('analog_screen.py'),route_path,model,Path(shutil.which('ngspice')).resolve())})
    (work/'route-screen.json').write_text(json.dumps(result,indent=2)+'\n')
    if not result['all_screens_complete']:raise ValueError('Route lifecycle incomplete')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--generated',type=Path,default=Path(__file__).with_name('generated'));p.add_argument('--pdk-model-dir',type=Path,required=True);p.add_argument('--pad-dir',type=Path)
    a=p.parse_args();run(a.output_dir.resolve(),a.generated.resolve(),a.pdk_model_dir.resolve(),a.pad_dir.resolve() if a.pad_dir else None)
