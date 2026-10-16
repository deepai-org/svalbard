"""Insert the pending steering network into the existing complete RF pad bench.

Keep extracted pad routing and the same external/core network. The replacement
junction array, clamp and rail connections have extracted capacitance;
attachment to the physical pads is not yet implemented. This is not the normative generated pad layout.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
import numpy as np
from analog_screen import screen

CLAMP_CAPACITORS = dict(model="cap_mim_2f0_m4m5_noshield", pcell="cap_mim_2p0fF", timing_side_um=31.6, rail_side_um=31.6)


def completion_flags(value,path=''):
    flags={}
    if isinstance(value,dict):
        for key,child in value.items():
            location=path+'/'+key
            if key=='transient_complete':flags[location]=bool(child)
            else:flags.update(completion_flags(child,location))
    return flags


def build_candidate(physical,primitives,pdk,*,timing_cap_side_um=None,rail_cap_side_um=None,clamp_physical=None,array_physical=None,network_physical=None):
    timing_cap_side_um=CLAMP_CAPACITORS["timing_side_um"] if timing_cap_side_um is None else timing_cap_side_um
    rail_cap_side_um=CLAMP_CAPACITORS["rail_side_um"] if rail_cap_side_um is None else rail_cap_side_um
    if not 5<=timing_cap_side_um<=100 or not 5<=rail_cap_side_um<=100:
        raise ValueError('MIM capacitor sides must be 5..100um')
    original=physical.read_text();kept=[];removed=0
    for line in original.splitlines():
        fields=line.split()
        if fields and fields[0].startswith('X') and len(fields)>5 and fields[5]=='nfet_06v0_dss':
            if fields[1] not in ('PAD_P','PAD_N') or fields[2:5]!=['VSS']*3:
                raise ValueError('Unexpected existing protection topology')
            removed+=1
        elif line.startswith('*'):
            continue
        elif line.startswith('.ends '):
            if network_physical is not None:
                kept.append('XPROT_NETWORK VSS ESD_RAIL PAD_P PAD_N network_flat')
            elif array_physical is not None:
                kept.append('XPROT_ARRAY VSS ESD_RAIL PAD_P PAD_N array_flat')
            else:
                for leg in ('P','N'):
                    for i in range(4):
                        kept += [f'XPROT_LOW_{leg}_{i} VSS PAD_{leg} diode_nd2ps_06v0',
                                 f'XPROT_HIGH_{leg}_{i} PAD_{leg} ESD_RAIL VSS diode_pd2nw_06v0']
            if network_physical is None:
                kept.append('XPROT_CLAMP ESD_RAIL VSS VSS pad_isolated_rail_clamp')
            if network_physical is None:
                kept.append('RPROT_BLEED ESD_RAIL VSS 10meg')
            kept.append(line)
        else:kept.append(line)
    if removed!=4:raise ValueError('Expected four existing protection units')
    library=pdk.parent/'gf180mcu_fd_io.spice'
    native=library.read_text().split('.SUBCKT gf180mcu_fd_io__dvdd ',1)[1].split('.ENDS',1)[0]
    clamp=['.subckt pad_isolated_rail_clamp '+native.splitlines()[0]]
    replaced=0
    for line in native.splitlines()[1:]:
        fields=line.split()
        if len(fields)>3 and fields[3]=='cap_nmos_06v0':
            side=timing_cap_side_um if fields[0]=='X3' else rail_cap_side_um
            if fields[0] not in ('X3','X21'):raise ValueError('Unexpected native clamp capacitor')
            line=' '.join(fields[:3])+f' {CLAMP_CAPACITORS["model"]} c_length={side}u c_width={side}u'
            replaced+=1
        clamp.append(line)
    if replaced!=2:raise ValueError('Native clamp topology changed')
    clamp.append('.ends pad_isolated_rail_clamp')
    extra=[]
    if clamp_physical is not None:
        manifest_path=clamp_physical.parent/'clamp-layout.json'
        manifest=json.loads(manifest_path.read_text())
        if not manifest['device_graph_lvs_match'] or manifest['drc_count']!=0:
            raise ValueError('Physical clamp has not passed its implementation checks')
        if hashlib.sha256(clamp_physical.read_bytes()).hexdigest()!=manifest['extracted_spice_sha256']:
            raise ValueError('Physical clamp differs from checked extraction')
        for path,digest in manifest['source_sha256'].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:raise ValueError('Stale clamp source: '+path)
        if manifest['capacitor_parameters']!=CLAMP_CAPACITORS or timing_cap_side_um!=CLAMP_CAPACITORS['timing_side_um'] or rail_cap_side_um!=CLAMP_CAPACITORS['rail_side_um']:
            raise ValueError('Regenerate clamp layout for changed capacitor parameters')
        clamp=['.subckt pad_isolated_rail_clamp DVDD DVSS VSS',
               'XGEOMETRY DVSS DVDD TIMING_LOCAL clamp_flat','.ends pad_isolated_rail_clamp',
               clamp_physical.read_text()]
        extra=[clamp_physical,manifest_path]
    low=primitives/'diode_nd2ps_06v0.spice';high=primitives/'diode_pd2nw_06v0-with-well.spice'
    array_text=low.read_text()+high.read_text()
    if array_physical is not None:
        manifest_path=array_physical.parent/'array-layout.json'
        manifest=json.loads(manifest_path.read_text())
        if manifest['drc_count']!=0 or manifest['diode_count']!=16 or manifest['fingers_per_diode']!=4:
            raise ValueError('Array differs from candidate protection sizing')
        if hashlib.sha256(array_physical.read_bytes()).hexdigest()!=manifest['extracted_spice_sha256']:
            raise ValueError('Array differs from checked extraction')
        for path,digest in manifest['source_sha256'].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:raise ValueError('Stale array source: '+path)
        array_text=array_physical.read_text()
        if '.subckt array_flat VSS RAIL PADP PADN' not in array_text:
            raise ValueError('Array port order changed')
        extra.extend([array_physical,manifest_path])
    if network_physical is not None:
        if clamp_physical is not None or array_physical is not None:
            raise ValueError('Use the combined network or separate macros, not both')
        manifest_path=network_physical.parent/'network-layout.json'
        manifest=json.loads(manifest_path.read_text())
        if manifest['drc_count']!=0 or not manifest['device_graph_lvs_match'] or not manifest.get('physical_bleed_included'):
            raise ValueError('Combined protection network checks failed')
        if hashlib.sha256(network_physical.read_bytes()).hexdigest()!=manifest['extracted_spice_sha256']:
            raise ValueError('Combined network differs from checked extraction')
        for path,digest in manifest['source_sha256'].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:raise ValueError('Stale network source: '+path)
        array_text=network_physical.read_text();clamp=[]
        if '.subckt network_flat VSS RAIL PADP PADN' not in array_text:
            raise ValueError('Network port order changed')
        extra.extend([network_physical,manifest_path])
    text='* Candidate protection substitution; retained pad routing, new primitive junction models.\n'+'\n'.join(kept)+'\n'+array_text+'\n'.join(clamp)+'\n'
    text+=f'\n.lib {pdk}/sm141064.ngspice diode_typical\n.lib {pdk}/sm141064.ngspice mimcap_typical\n'
    return text,[physical,low,high,library,pdk/'sm141064_mim.spice',primitives/'protection-primitives.json']+extra


def run(work,pdk,generated):
    work.mkdir(parents=True,exist_ok=False)
    primitive_dir=generated/'protection-primitives'
    manifest=json.loads((primitive_dir/'protection-primitives.json').read_text())
    for path,digest in manifest['source_sha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:
            raise ValueError('Stale primitive source: '+path)
    # Native IO compact models require HSPICE width/nf semantics. This runner
    # owns its process working directory; existing normative benches are unchanged.
    (work/'.spiceinit').write_text('set ngbehavior=hs\n')
    previous=Path.cwd();results={};sources=[Path(__file__).resolve(),Path(shutil.which('ngspice')).resolve()]
    simulator=Path(shutil.which('ngspice')).resolve()
    try:
        os.chdir(work)
        for family in ('rf_receive','rf_transmit'):
            physical=generated/(family.replace('_','-')+'-extracted-c.spice')
            candidate,dependencies=build_candidate(physical,primitive_dir,pdk,
                network_physical=generated/'protection-network/network-with-well.spice')
            path=work/(family+'.spice');path.write_text(candidate)
            try:
                result=screen(work/family,pdk,path,family)
            except (RuntimeError,ValueError,IndexError,subprocess.TimeoutExpired) as error:
                # ngspice can return zero after an aborted transient. Preserve
                # evidence and continue the other family, never count completion.
                partial={}
                for data in (work/family).glob('*.dat'):
                    rows=np.atleast_2d(np.loadtxt(data,skiprows=1))
                    partial[data.stem]=dict(row_count=len(rows),finite=bool(np.isfinite(rows).all()),
                        last_independent_value=float(rows[-1,0]) if rows.size else None)
                logs={log.name:[line for line in log.read_text().splitlines()
                                if any(token in line.lower() for token in ('aborted','timestep too small','error:'))]
                      for log in (work/family).glob('*.log')}
                result=dict(status='candidate_screen_failed',transient_complete=False,
                    error=f'{type(error).__name__}: {error}',partial_outputs=partial,
                    simulator_errors={name:lines for name,lines in logs.items() if lines})
            results[family]=result;sources.extend(dependencies)
    finally:os.chdir(previous)
    completions=completion_flags(results)
    report=dict(status='RF_network_with_candidate_protection_not_replacement_layout',
        simulator_path=str(simulator),simulator_sha256=hashlib.sha256(simulator.read_bytes()).hexdigest(),
        all_screens_complete=bool(completions) and all(completions.values()),
        transient_completion_checks=completions,
        clamp_capacitors=CLAMP_CAPACITORS,
        rail_strategy='One isolated rail per pair; charged only through steering junctions, no functional-supply feed. Extracted native-derived clamp with the shared MIM timing/rail capacitors; Extracted nominal 10Mohm-class physical bleed remains connected in every state.',
        results=results,
        limitations=['Original extracted signal/ground capacitance retained after removing small grounded-gate MOS devices.',
            'Connected diode-array and clamp network includes extracted rail/return routing and nonlinear array well junctions; pad attachment routing absent.',
            'Core bias/driver remains the existing declared behavioral boundary. Existing warm lifecycle is not cold-start or ESD proof.',
            'No package/distributed wire resistance in this comparison; candidate not adopted.'],
        source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in set(sources)})
    (work/'protection-candidate.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--pdk-model-dir',type=Path,required=True);p.add_argument('--generated',type=Path,required=True)
    a=p.parse_args();r=run(a.output_dir.resolve(),a.pdk_model_dir.resolve(),a.generated.resolve())
    if not r['all_screens_complete']:raise SystemExit(2)
