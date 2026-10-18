"""Reproduce provider-compatible reference site placement with the installed IO library.

This is a reference ring, not a substituted or electrically verified custom ring.
The actual installed LibreLane placement script determines coordinates.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import math
import shutil
import yaml
from design import PROJECT,resolve
from retained import binding as retained_binding
from layout import IMAGE,PDK


def build(work,template,generated=None,placement_only=False):
    generated=generated or PROJECT/'analog/pads/generated'
    work.mkdir(parents=True,exist_ok=True)
    contract=json.loads((PROJECT/'spec/contract.json').read_text())
    expected=contract['assembly_policy']['provider_template_commit']
    actual=subprocess.check_output(['git','-C',str(template),'rev-parse','HEAD'],text=True).strip()
    if actual!=expected:raise ValueError('Provider template must match the pinned contract commit')
    for relative in ('librelane/slots/slot_1x1.yaml','src/chip_top.sv'):
        pinned=subprocess.check_output(['git','-C',str(template),'show','HEAD:'+relative])
        if (template/relative).read_bytes()!=pinned:
            raise ValueError('Provider source differs from pinned commit: '+relative)
    slot=template/'librelane/slots/slot_1x1.yaml'
    config=yaml.safe_load(slot.read_text())
    sites=resolve()['provider_inventory']
    for side,ordered in sites.items():
        if [s.replace('\\','') for s in config['PAD_'+side.upper()]]!=ordered:
            raise ValueError('Provider site inventory differs: '+side)
    def master(site):
        if site=='clk_pad':kind='in_s'
        elif site=='rst_n_pad' or site.startswith('inputs['):kind='in_c'
        elif site.startswith('bidir['):kind='bi_24t'
        elif site.startswith('analog['):kind='asig_5p0'
        elif site.startswith(('dvdd_pads[','vdd_pads[')):kind='dvdd'
        elif site.startswith(('dvss_pads[','vss_pads[')):kind='dvss'
        else:raise ValueError('Unknown provider cell '+site)
        return 'gf180mcu_fd_io__'+kind
    all_sites=[s for ordered in sites.values() for s in ordered]
    die=config['DIE_AREA']
    definitions=['VERSION 5.8 ;','DIVIDERCHAR "/" ;','BUSBITCHARS "[]" ;','DESIGN provider_reference ;',
        'UNITS DISTANCE MICRONS 2000 ;',f'DIEAREA ( {die[0]*2000} {die[1]*2000} ) ( {die[2]*2000} {die[3]*2000} ) ;',
        f'COMPONENTS {len(all_sites)} ;']
    definitions += [f'- {s} {master(s)} ;' for s in all_sites]
    definitions += ['END COMPONENTS','END DESIGN']
    (work/'reference.def').write_text('\n'.join(definitions)+'\n')
    commands=[f'read_lef {PDK}/libs.ref/gf180mcu_fd_sc_mcu7t5v0/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef',
        f'foreach f [glob {PDK}/libs.ref/gf180mcu_fd_io/lef/*.lef] {{read_lef $f}}',
        'read_def /work/reference.def',
        'if {[[[ord::get_db] getTech] getDbUnitsPerMicron] != 2000} {error {Unexpected database units}}',
        'set ::env(PAD_CELL_LIBRARY) gf180mcu_fd_io',
        f'source {PDK}/libs.tech/librelane/gf180mcu_fd_io/config.tcl',
        'unset ::env(PAD_PLACE_IO_TERMINALS)',
        'make_fake_io_site -name GF_IO_Site -width 0.1 -height 355',
        'make_fake_io_site -name GF_COR_Site -width 355 -height 355',
        'set ::env(DIE_AREA) {'+' '.join(map(str,die))+'}']
    for side,ordered in sites.items():commands += ['set ::env(PAD_'+side.upper()+') {'+' '.join(ordered)+'}']
    commands+=['source /work/reference-pad-placement.tcl','write_def /work/placed.def',
        'write_db /work/placed.odb','set f [open /work/sites.tsv w]',
        'foreach inst [[ord::get_db_block] getInsts] {',
        ' set b [$inst getBBox]',
        ' puts $f "[$inst getName]\t[[$inst getMaster] getName]\t[$inst getOrient]\t[$b xMin]\t[$b yMin]\t[$b xMax]\t[$b yMax]"',
        '}','close $f','exit']
    (work/'place.tcl').write_text('\n'.join(commands)+'\n')
    # Reuse installed placement with explicit half-micron arithmetic correction.
    # Omit power-net hookup, which
    # is outside this geometric reference fixture. Record original and derived
    # scripts so the exclusion cannot be mistaken for electrical integration.
    prepare=r"""import pathlib,librelane
p=pathlib.Path(librelane.__file__).parent/'scripts/openroad/common/pad_cfg.tcl'
s=p.read_text();pathlib.Path('/work/provider-pad-placement.tcl').write_text(s)
s='\n'.join(l for l in s.splitlines() if not l.startswith('source ') and l.strip()!='set_global_connections')
# This installed Tcl version divides integers before converting the placement
# to float, losing the horizontal half-micron. Keep the original script above;
# preserve fractional arithmetic and let the placer rebuild the filler rows.
needle='($space_for_fill - $space_between_pads_min_filler * ([llength $::env($side)] - 1)) / 2 * 1000) / 1000'
if s.count(needle)!=1:raise ValueError('Re-audit changed provider placement arithmetic')
s=s.replace(needle,needle.replace('/ 2 *','/ 2.0 *').replace('/ 1000','/ 1000.0'))
check='floor($space_side / $pad_site_width) * $pad_site_width * 1000) / 1000'
if s.count(check)!=1:raise ValueError('Re-audit changed site-grid check')
s=s.replace(check,check.replace('/ 1000','/ 1000.0'))
pathlib.Path('/work/reference-pad-placement.tcl').write_text(s+'\n')
"""
    (work/'prepare.py').write_text(prepare)
    cmd=['docker','run','--rm','--network','none','--entrypoint','/bin/sh',
         '--mount',f'type=bind,src={work},dst=/work','-w','/work',IMAGE,
         '-c','python3 /work/prepare.py && openroad -exit /work/place.tcl']
    result=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
    (work/'placement.log').write_text(result.stdout+result.stderr);result.check_returncode()
    inverse={v:k for k,v in contract['assembly_policy']['candidate_signal_sites'].items()}
    placements={}
    for line in (work/'sites.tsv').read_text().splitlines():
        name,cell,orientation,*bbox=line.split('\t')
        if name in all_sites:
            placements[name]=dict(master=cell,orientation=orientation,bbox_um=[int(v)/2000 for v in bbox],signal=inverse.get(name))
    if set(placements)!=set(all_sites):raise ValueError('Reference placement lost provider sites')
    report=dict(status='placed_provider_reference_not_custom_ring_or_board_map',die_area_um=die,
        core_area_um=config['CORE_AREA'],db_units_per_micron=2000,template_commit=actual,image_id=IMAGE,sites=placements,
        limitations=['No custom pad substitution or core placement yet.','Power-net hookup deliberately omitted; abutment is geometric evidence only.',
          'Installed flow/PDK reproduces a reference; this is not provider-confirmed assembly coordinates.',
          'Bond opening coordinates require transformed library geometry; macro boxes are not bond centers.'],
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [slot,template/'src/chip_top.sv',Path(__file__),Path(__file__).with_name('retained.py'),PROJECT/'spec/contract.json',work/'provider-pad-placement.tcl',work/'reference-pad-placement.tcl']})
    (work/'assembly-report.json').write_text(json.dumps(report,indent=2)+'\n')
    for family in resolve()['families']:
        source=generated/(family.replace('_','-')+'.gds')
        shutil.copyfile(source,work/('candidate_'+family+'.gds'))
        shutil.copyfile(source.with_name(family.replace('_','-')+'-layout.json'),work/('candidate_'+family+'-layout.json'))
    geometry=Path(__file__).with_name('assembly_geometry.py')
    (work/'assembly_geometry.py').write_text(geometry.read_text())
    subprocess.run(['docker','run','--rm','--network','none','--entrypoint','python3',
         '--mount',f'type=bind,src={work},dst=/work',IMAGE,'/work/assembly_geometry.py'],check=True,timeout=60)
    report=json.loads((work/'assembly-report.json').read_text())
    provider_sites=dict(template_commit=report['template_commit'],image_id=report['image_id'],
        die_area_um=report['die_area_um'],core_area_um=report['core_area_um'],sites=report['sites'],
        library_gds_sha256=report['geometry_sources']['library_gds_sha256'],
        placement_algorithm_sha256=hashlib.sha256((work/'provider-pad-placement.tcl').read_bytes()).hexdigest(),
        slot_sha256=hashlib.sha256(slot.read_bytes()).hexdigest(),
        scope='Installed-library reference coordinates, not provider-confirmed assembly or custom rail integration.')
    (work/'provider-sites.json').write_text(json.dumps(provider_sites,indent=2)+'\n')
    pairs={}
    for family,definition in resolve()['families'].items():
        p,n=[report['sites'][pad['site']]['bond_center_um'] for pad in definition['pads']]
        pitch=math.dist(p,n)
        candidate=report['candidate_geometry'][family]['bond_pitch_um']
        pairs[family]=dict(provider_reference_pitch_um=pitch,current_candidate_pitch_um=candidate,
            bond_pitch_matches_reference=abs(pitch-candidate)<.001,
            required_adaptation='Pitch alone is insufficient: preserve individual bond coordinates and polarity, and integrate the active macro, rail corridors and package returns.')
    report['custom_pair_fit']=pairs
    (work/'assembly-report.json').write_text(json.dumps(report,indent=2)+'\n')
    custom_map={family:[pad['site'] for pad in definition['pads']] for family,definition in resolve()['families'].items()}
    (work/'retained-binding.json').write_text(json.dumps(retained_binding(),indent=2)+'\n')
    (work/'custom-map.json').write_text(json.dumps(custom_map,indent=2)+'\n')
    (work/'placement_audit.py').write_text(Path(__file__).with_name('placement_audit.py').read_text())
    subprocess.run(['docker','run','--rm','--network','none','--entrypoint','python3',
         '--mount',f'type=bind,src={work},dst=/work',IMAGE,'/work/placement_audit.py'],check=True,timeout=60)
    rail_inputs=work/'rail-inputs';rail_inputs.mkdir(exist_ok=True)
    for family in resolve()['families']:
        stem=family.replace('_','-')
        shutil.copyfile(work/('candidate_'+family+'.gds'),rail_inputs/(stem+'.gds'))
        shutil.copyfile(work/('candidate_'+family+'-layout.json'),rail_inputs/(stem+'-layout.json'))
    (work/'rail_connectivity.py').write_text(Path(__file__).with_name('rail_connectivity.py').read_text())
    subprocess.run(['docker','run','--rm','--network','none','--entrypoint','python3',
         '--mount',f'type=bind,src={work},dst=/work',IMAGE,'/work/rail_connectivity.py',
         '--generated','/work/rail-inputs','--output','/work/rail-connectivity.json'],check=True,timeout=60)
    if placement_only:
        preview(report,work/'provider-reference-ring.png')
        physical_preview(work,report)
        print('Placement and local rail checks complete; electrical estimates not requested')
        return
    resistance_script=Path(__file__).with_name('wire_resistance.py')
    subprocess.run(['docker','run','--rm','--network','none','--entrypoint','python3',
         '--mount',f'type=bind,src={work},dst=/work',
         '--mount',f'type=bind,src={PROJECT},dst={PROJECT},readonly',IMAGE,str(resistance_script),
         '--generated','/work/rail-inputs','--output','/work/wire-resistance.json'],check=True,timeout=60)
    preview(report,work/'provider-reference-ring.png')
    physical_preview(work,report)
    print(f'Placed {len(placements)} reference sites and transformed native bond openings')


def preview(report,output):
    from PIL import Image,ImageDraw,ImageFont
    scale=.26;margin=65
    width,height=report['die_area_um'][2:]
    im=Image.new('RGB',(round(width*scale)+2*margin,round(height*scale)+2*margin),'white')
    draw=ImageDraw.Draw(im)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',11)
    def box(b):return [margin+b[0]*scale,margin+(height-b[3])*scale,margin+b[2]*scale,margin+(height-b[1])*scale]
    draw.rectangle(box(report['die_area_um']),outline='#333333',width=2)
    draw.rectangle(box(report['core_area_um']),outline='#cccccc',width=1)
    for name,p in report['sites'].items():
        signal=p['signal'] or ''
        fast=signal.startswith(('RF_','REF_','WIRE_'))
        power=any(name.startswith(prefix) for prefix in ('vdd_','vss_','dvdd_','dvss_'))
        color='#ffa660' if fast else '#8fbc8f' if power else '#b9cce6'
        draw.rectangle(box(p['bbox_um']),fill=color,outline='#555555')
        draw.rectangle(box(p['bond_opening_bbox_um']),fill='white',outline='#333333')
        if fast:
            cx,cy=p['bond_center_um'];y=margin+(height-cy)*scale
            x=margin+420*scale if cx<width/2 else margin+(width-420)*scale
            draw.text((x,y),signal,fill='#222222',font=font,anchor='lm' if cx<width/2 else 'rm')
    draw.text((margin,18),'Provider reference ring — native bond openings; custom cells NOT substituted',font=font,fill='black')
    draw.text((margin+120,margin+height*scale/2),'Orange: custom sites   Green: fixed supply/ground   Blue: retained/unassigned IO',font=font,fill='black')
    draw.text((margin+120,margin+height*scale/2+22),'Core outline is a placement boundary, not a completed core layout.',font=font,fill='black')
    im.save(output)


def physical_preview(work,report):
    from PIL import Image,ImageDraw,ImageFont
    layers=json.loads((work/'assembly-polygons.json').read_text())
    audit=json.loads((work/'placement-audit.json').read_text())
    colors={'metal1':'#438ad6','metal2':'#63af7a','metal3':'#d2bd53','metal4':'#cc8650','metal5':'#945d9e','glass':'#ffffff'}
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',12)
    for name,bounds,scale in [('custom-assembly-candidate',report['die_area_um'],.25),
            ('custom-assembly-wired-rx',audit['custom_cells']['wired_receive_usb']['bbox_um'],1.5)]:
        x0,y0,x1,y1=bounds;margin=35
        im=Image.new('RGBA',(round((x1-x0)*scale)+2*margin,round((y1-y0)*scale)+2*margin),'white')
        def point(p):return (margin+(p[0]-x0)*scale,margin+(y1-p[1])*scale)
        for layer,polygons in layers.items():
            overlay=Image.new('RGBA',im.size);draw=ImageDraw.Draw(overlay)
            color=colors[layer];rgb=tuple(int(color[i:i+2],16) for i in (1,3,5))+(230 if layer=='glass' else 135,)
            for hull,holes in polygons:
                if max(p[0] for p in hull)<x0 or min(p[0] for p in hull)>x1 or max(p[1] for p in hull)<y0 or min(p[1] for p in hull)>y1:continue
                draw.polygon([point(p) for p in hull],fill=rgb)
                for hole in holes:draw.polygon([point(p) for p in hole],fill=(0,0,0,0))
            im=Image.alpha_composite(im,overlay)
        draw=ImageDraw.Draw(im)
        draw.text((10,8),'Actual assembly metal + bond openings; local ground joins checked, full-ring extraction pending',font=font,fill='black')
        if name=='custom-assembly-candidate':
            for family,cell in audit['custom_cells'].items():
                a,b,c,d=cell['bbox_um'];draw.rectangle([point((a,d)),point((c,b))],outline='#d00000',width=2)
                draw.text(point((a,d+50)),family,font=font,fill='#b00000')
        im.convert('RGB').save(work/(name+'.png'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--template',type=Path,required=True)
    p.add_argument('--publish-dir',type=Path)
    p.add_argument('--generated',type=Path)
    p.add_argument('--placement-only',action='store_true',help='Build placement/local rails without unrelated electrical estimates; not electrical signoff')
    a=p.parse_args()
    if a.placement_only and a.publish_dir:p.error('Placement-only run cannot publish the full electrical bundle')
    build(a.output_dir.resolve(),a.template.resolve(),a.generated.resolve() if a.generated else None,a.placement_only)
    if a.publish_dir:
        a.publish_dir.mkdir(parents=True,exist_ok=True)
        for name in ('assembly-report.json','rail-connectivity.json','wire-resistance.json','provider-sites.json','provider-reference-ring.png','placement-audit.json','custom-assembly-candidate.oas','custom-assembly-candidate.png','custom-assembly-wired-rx.png'):
            shutil.copyfile(a.output_dir/name,a.publish_dir/name)
