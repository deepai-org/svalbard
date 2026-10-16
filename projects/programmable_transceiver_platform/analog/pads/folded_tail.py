"""Generate a locally connected parallel NMOS tail bank; not a selected pad.

The PDK supplies shared-diffusion fingers; this generator connects alternating
source/drain contacts and every gate. Full pad placement and timing remain open.
"""
import argparse,hashlib,json,re
from pathlib import Path
from layout import magic,rectangles
import numpy as np
from screen import run_spice
from design import PROJECT


def generate(work,fingers=32,width=20.,length=1.):
    if type(fingers) is not int or fingers<2 or fingers%2:raise ValueError('Require an even positive finger count')
    if width<12 or length<.28:raise ValueError('Geometry outside supported local-routing envelope')
    work.mkdir(parents=True,exist_ok=False)
    (work/'primitive.tcl').write_text(f'''crashbackups stop
load workspace
set cell [magic::gencell_makecell gf180mcu::nfet_03v3 w {width} l {length} nf {fingers} guard 1 topc 0 botc 1 full_metal 1 gate_to_polycont 0.6 gate_extension 0.8 diff_gate_space 0.3]
load $cell
save folded_tail
quit -noprompt
''')
    magic(work,'primitive.tcl');r=rectangles(work/'folded_tail.mag')
    diffusion=sorted(r['ndiffc']);gates=r['polycontact']
    if len(diffusion)!=fingers+1 or len(gates)!=fingers:raise ValueError('Unexpected PCell contact topology')
    c=['crashbackups stop','load folded_tail','units microns']
    def paint(layer,x,y,xx,yy):c.extend([f'box values {x} {y} {xx} {yy}',f'paint {layer}'])
    def contact(x,y):
        paint('metal1',x-.19,y-.19,x+.19,y+.19)
        paint('metal2',x-.2,y-.2,x+.2,y+.2)
        paint('via1',x-.13,y-.13,x+.13,y+.13)
    pins={}
    for parity,name,y in [(0,'S',width*.3),(1,'D',width*.1)]:
        xs=[(v[0]+v[2])/2 for i,v in enumerate(diffusion) if i%2==parity]
        for x in xs:contact(x,y)
        paint('metal2',min(xs)-.2,y-.2,max(xs)+.2,y+.2);pins[name]=(min(xs),y,'metal2')
    xs=[(v[0]+v[2])/2 for v in gates];y=sum((v[1]+v[3])/2 for v in gates)/len(gates)
    for x in xs:contact(x,y)
    paint('metal2',min(xs)-.2,y-.2,max(xs)+.2,y+.2);pins['G']=(min(xs),y,'metal2')
    b=max(r['psubdiffcont'],key=lambda v:v[0]);pins['B']=((b[0]+b[2])/2,0,'metal1')
    for i,name in enumerate(['D','G','S','B'],1):
        x,y,layer=pins[name];c.extend([f'box values {x} {y} {x} {y}',f'label {name} FreeSans 0.3 0 0 0 c {layer}',f'port make {i}'])
    c+=['select top cell','expand','drc check','drc catchup','puts "TAIL_DRC [drc list count total]"','extract all','ext2spice lvs','ext2spice cthresh 0','ext2spice','save','gds write folded_tail.gds','quit -noprompt']
    (work/'connect.tcl').write_text('\n'.join(c)+'\n');out=magic(work,'connect.tcl')
    if not re.search(r'TAIL_DRC 0\b',out.stdout):raise ValueError('Folded tail DRC failed')
    text=(work/'folded_tail.spice').read_text();devices=[l.split() for l in text.splitlines() if l.startswith('X')]
    if len(devices)!=fingers or any(d[2]!='G' or d[4]!='B' or set((d[1],d[3]))!={'D','S'} or d[5]!='nfet_03v3' for d in devices):raise ValueError('Folded tail device graph differs')
    geometry=[v for k,rs in rectangles(work/'folded_tail.mag').items() if k!='checkpaint' for v in rs]
    bounds=[min(v[0] for v in geometry),min(v[1] for v in geometry),max(v[2] for v in geometry),max(v[3] for v in geometry)]
    result=dict(status='local_DRC_and_extracted_parallel_graph_pass_not_pad_integration',fingers=fingers,width_um=width,length_um=length,bounds_um=bounds,area_um2=(bounds[2]-bounds[0])*(bounds[3]-bounds[1]),pins=pins,source_sha256={str(Path(__file__).resolve()):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},netlist_sha256=hashlib.sha256(text.encode()).hexdigest())
    from gds_roundtrip import check
    result['gds_roundtrip']=check(work/'roundtrip',work/'folded_tail.gds',work/'folded_tail.spice','folded_tail')
    if result['gds_roundtrip']['drc_count'] or not result['gds_roundtrip']['device_graph_match']:raise ValueError('Streamed folded-bank graph failed')
    (work/'screen.json').write_text(json.dumps(result,indent=2)+'\n');return result


def connected_check(work,dc_work,primitive):
    """Diagnostic substitution; full-pad layout is not regenerated here."""
    work.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((dc_work/'screen.json').read_text())
    arch=PROJECT/'spec/analog-architecture.json'
    tx=json.loads(arch.read_text())['blocks']['wiredtx']['parameters']
    main_target=max(tx['current_range_a']);post_target=main_target*max(tx['postcursor_fraction'])
    for name,digest in manifest['source_sha256'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Stale DC source '+name)
    results={}
    for case in ('main','main_post'):
        source=dc_work/(case+'.spice')
        s=source.read_text();lines=s.splitlines();groups={};out=[]
        for line in lines:
            f=line.split()
            if len(f)>6 and f[0].startswith('X') and f[5]=='nfet_03v3' and f[1].startswith(('MAIN_TAIL_','POST_TAIL_')) and f[2] in ('MAIN_BIAS','POST_BIAS'):
                nodes=tuple(f[1:5]);groups[nodes]=groups.get(nodes,0)+1
            else:out.append(line)
        assert len(groups)==16 and set(groups.values())=={4}
        start=next(i for i,l in enumerate(out) if l.startswith('.subckt combined_flat '))
        out[start+1:start+1]=['XTAILBANK'+str(i)+' '+' '.join(nodes)+' folded_tail' for i,nodes in enumerate(groups)]
        s='\n'.join(out)+'\n';s=s.replace('.control',primitive.read_text()+'\n.control',1)
        for branch,bias in [('MAIN',.873),('POST',.802)]:
            s,n=re.subn(r'(^BBIAS_'+branch+r' .*? V=)[0-9.]+',lambda m:m[1]+str(bias),s,flags=re.M);assert n==1
        s=re.sub(r'(?m)^wrdata .*? ',f'wrdata {work}/{case}.dat ',s)
        x=run_spice(work,case,s,reject_transient_op=True)
        results[case]=dict(main_a=x[:,9].tolist(),post_a=x[:,10].tolist(),vcm_v=x[:,1].tolist(),main_target_error_fraction=(x[:,9]/main_target-1).tolist(),post_target_error_fraction=(x[:,10]/post_target-1).tolist() if case=='main_post' else None)
    result=dict(status='hybrid_folded_bank_connected_DC_probe_not_whole_pad_extraction',cases=results,scope='Replace four independent original tail devices per group with a 32-finger extracted bank. Retain old full-pad routing capacitance. New bank placement/interconnect not included; no transient or AC acceptance.',source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),arch,primitive,dc_work/'main.spice',dc_work/'main_post.spice']})
    (work/'screen.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--fingers',type=int,default=32)
    p.add_argument('--dc-screen-dir',type=Path)
    a=p.parse_args();print(json.dumps(generate(a.output_dir.resolve(),a.fingers),indent=2))
    if a.dc_screen_dir:
        if a.fingers!=32:raise ValueError('Connected diagnostic biases target32 fingers only')
        connected_check(a.output_dir.resolve()/'connected',a.dc_screen_dir.resolve(),a.output_dir.resolve()/'folded_tail.spice')
