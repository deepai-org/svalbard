"""Connect a physical poly resistor and MIM compensation to the buffer core."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from layout import magic,terminals
from protection_device_audit import check


def generate(work,core,mim):
    work.mkdir(parents=True,exist_ok=False)
    for src,name in [(core/'buffer_core_flat.gds','core.gds'),(mim/'feedforward_mim.mag','comp_mim.mag')]:shutil.copyfile(src,work/name)
    # Match the approximate 30-ohm probe with an explicit foundry resistor;
    # its actual resistance must be measured, not assumed equal to the probe.
    (work/'resistor.tcl').write_text('crashbackups stop\nload workspace\nunits internal\nset cell [magic::gencell_makecell gf180mcu::ppolyf_s w 1 l 1.2 guard 1 full_metal 1]\nload $cell\nsave comp_res\nquit -noprompt\n')
    magic(work,'resistor.tcl');pins=terminals(work/'comp_res.mag')
    labels={}
    for line in (core/'buffer_core_flat.mag').read_text().splitlines():
        f=line.split()
        if f and f[0]=='flabel':labels[f[-1]]=((float(f[2])+float(f[4]))*.0025,(float(f[3])+float(f[5]))*.0025)
    public=next(line.split()[2:] for line in (core/'physical.spice').read_text().splitlines() if line.startswith('.subckt'))
    top=labels['VSS'][1]+.25
    shift=top-790.
    cmd=['crashbackups stop','gds read core.gds','load buffer_core_flat','units microns',f'getcell comp_res child 0 0 parent 35 {810+shift}',f'getcell comp_mim child 0 0 parent 100 {840+shift}']
    def box(layer,x1,y1,x2,y2):cmd.extend([f'box values {min(x1,x2):.4f} {min(y1,y2):.4f} {max(x1,x2):.4f} {max(y1,y2):.4f}',f'paint {layer}'])
    def wire(level,a,b,width=.5):
        if a[0]!=b[0] and a[1]!=b[1]:raise ValueError('Non-Manhattan route')
        h=width/2;box(f'metal{level}',min(a[0],b[0])-h,min(a[1],b[1])-h,max(a[0],b[0])+h,max(a[1],b[1])+h)
    def via(x,y,lo,hi):
        for level in range(lo,hi+1):box(f'metal{level}',x-.25,y-.25,x+.25,y+.25)
        for level in range(lo,hi):
            h=.13 if level==1 else .14;box(f'via{level}',x-h,y-h,x+h,y+h)
    # Unique M4 lanes connect resistor contacts to GAIN, COMP and substrate.
    for i,((dx,dy),net,ry) in enumerate(zip(pins,['GAIN','COMP','VSS'],[804.+shift,808.+shift,816.+shift])):
        x,y=35+dx,810+shift+dy;ex=35+(-3.,0.,5.)[i]
        via(x,y,1,2);wire(2,(x,y),(ex,y));via(ex,y,2,3)
        wire(3,(ex,y),(ex,ry));via(ex,ry,3,4)
        if net=='COMP':
            wire(4,(ex,ry),(100.,ry));via(100.,ry,4,5);wire(5,(100.,ry),(100.,840.+shift))
        else:
            nx,ny=labels[net];wire(4,(ex,ry),(nx,ry));via(nx,ry,4,5);wire(5,(nx,ny),(nx,ry))
    # Bottom-plate contact is the PCell's right-hand M4/M5 landing.
    bottom=(120.035,840.+shift);wire(5,bottom,(140.,840.+shift));wire(5,(140.,840.+shift),(140.,800.+shift));via(140.,800.+shift,4,5)
    nx,ny=labels['OUT'];wire(4,(nx,800.+shift),(140.,800.+shift));via(nx,800.+shift,4,5);wire(5,(nx,ny),(nx,800.+shift))
    for i,net in enumerate(public,1):
        x,y=labels[net];cmd += [f'box values {x-.1} {y-.1} {x+.1} {y+.1}',f'label {net} center metal5',f'port make {i}']
    cmd += [f'box values 99.9 {807.9+shift} 100.1 {808.1+shift}','label COMP center metal5','select top cell','flatten buffer_compensated_flat','load buffer_compensated_flat','save','select top cell','drc check','drc catchup','set f [open drc.txt w]','puts $f [drc list count total]','close $f','set f [open drc-details.txt w]','puts $f [drc listall why]','close $f','extract all','ext2spice lvs','ext2spice cthresh 0','ext2spice','gds write buffer_compensated_flat.gds','quit -noprompt']
    (work/'assemble.tcl').write_text('\n'.join(cmd)+'\n');magic(work,'assemble.tcl')
    raw=work/'buffer_compensated_flat.spice'
    reference=(core/'physical.spice').read_text();reference=reference.replace('.ends buffer_core_flat_physical','XRC GAIN COMP VSS ppolyf_s r_width=1u r_length=1.2u\nXCMIM COMP OUT cap_mim_2f0_m4m5_noshield c_width=38.73u c_length=38.73u\n.ends buffer_core_flat_physical')
    (work/'expected.spice').write_text(reference)
    intended=check(work/'buffer_compensated_flat.ext',work/'expected.spice',work/'intended-audit.json')
    exported=check(work/'buffer_compensated_flat.ext',raw,work/'export-audit.json')
    report=dict(status='connected_buffer_compensation_candidate',drc_count=int((work/'drc.txt').read_text()),intended_device_graph_matches=intended['device_graph_matches'],export_device_graph_matches=exported['device_graph_matches'],device_count=intended['physical_devices'],limitations=['No resistor trim or resistance acceptance; no bias-passive layout, pad hookup or current-capacity qualification.','Electrical rerun required before adoption; no resistance extraction.'],source_sha256={str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),core/'physical.spice',core/'buffer_core_flat.gds',mim/'feedforward_mim.mag']})
    from gds_markers import repair
    report['gds_marker_repair']=repair(work,'buffer_compensated_flat')
    rt=work/'roundtrip';rt.mkdir();shutil.copyfile(work/'buffer_compensated_flat.gds',rt/'buffer_compensated_flat.gds')
    (rt/'check.tcl').write_text('crashbackups stop\ngds read buffer_compensated_flat.gds\nload buffer_compensated_flat\nselect top cell\nexpand\ndrc check\ndrc catchup\nset f [open drc.txt w]\nputs $f [drc list count total]\nclose $f\nextract all\nquit -noprompt\n')
    magic(rt,'check.tcl');audit=check(rt/'buffer_compensated_flat.ext',raw,work/'roundtrip-audit.json')
    report['gds_roundtrip']={'drc_count':int((rt/'drc.txt').read_text()),'device_graph_matches':audit['device_graph_matches']}
    report['physical_sha256']=hashlib.sha256(raw.read_bytes()).hexdigest()
    report['gds_sha256']=hashlib.sha256((work/'buffer_compensated_flat.gds').read_bytes()).hexdigest()
    (work/'layout.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    if report['drc_count'] or not report['intended_device_graph_matches'] or not report['export_device_graph_matches'] or report['gds_roundtrip']['drc_count'] or not report['gds_roundtrip']['device_graph_matches']:raise ValueError('Compensated layout verification failed')
    shutil.copyfile(raw,work/'physical.spice')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['output-dir','core-dir','mim-dir']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();generate(a.output_dir.resolve(),a.core_dir.resolve(),a.mim_dir.resolve())
