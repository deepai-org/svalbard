"""Generate device PCells and a connected first-pass pad layout in Magic.

Routing is deliberately inspectable. DRC and extracted connectivity are required
outputs, never implied by generating GDS. This standalone pair is not a placed
provider ring: preserving its metal rails and global assembly remains explicit.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import os
import re
import subprocess
import sys
from circuits import build, FAMILIES
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # analog/antenna_diodes.py
from design import PROJECT, resolve

# Locked svalbard/librelane-gf180-canary:2026.08 identity (env/images.lock).
LOCKED_IMAGE = 'sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17'
# A rebuild from the same checked-in recipe may be selected explicitly. Its ID is
# recorded in every report that stores image_id; see env/pad-environment.json.
IMAGE = os.environ.get('SVALBARD_PAD_IMAGE', LOCKED_IMAGE)
PDK = '/pdk/gf180mcuD'



def trunk_geometry(nets, *, power_width_um=8., width_overrides_um=None):
    """Allocate explicit power/return widths without crowding signal tracks."""
    if not .44<=power_width_um<=12:raise ValueError('Power trunk width outside reserved range')
    overrides={} if width_overrides_um is None else dict(width_overrides_um)
    if set(overrides)-set(nets):raise ValueError('Width override names an absent net')
    if any(isinstance(v,bool) or not math.isfinite(v) or not .44<=v<=12 for v in overrides.values()):
        raise ValueError('Trunk width outside reserved range')
    tracks={};widths={};edge=2.78;previous=None
    for net in sorted(nets):
        width=overrides.get(net,power_width_um if net in ('VDD','VSS') else .44)
        if previous is not None:edge+=1. if max(previous,width)>.44 else .56
        tracks[net]=round(edge+width/2,4);widths[net]=width
        edge+=width;previous=width
    if edge>146:raise ValueError('Trunk bank exceeds available width')
    return tracks,widths


# usb_term_block defaults (ESD option A of pad_wirepad, 2026-11-20). Coordinates in the cell frame (um).
_USB_TB = dict(
    neck_w=8.,                    # Metal2 escape neck width (published 4 um); 8 um = the pad-site primary default neck (33.5, 41.5)
    height_um=1434.,              # keep the published cell height (ports at the published y)
    x0=(46., 257.),               # left edge of the first unit (P, N): right of the neck + room for the TERM riser
    gap=1.5,                      # between unit bounding boxes
    rail=(352., 357.5),           # PAD rail (Metal2/3/4) just above the ring band (348.4)
    yp=360.8,                     # poly row centre
    ys_b=365.1,                   # switch row: bottom of the PCell boxes
    vcm=(389.4, 395.),            # TERM_VCM rail (Metal3/4/5), both legs
    strap=(253., 313.),           # TERM_VCM strap (Metal4/5) up to the bar
    bar=(1345., 1432.6),          # TERM_VCM bar (Metal3/4) from the strap to the TERM_VCM trunk at its pin (free above the grid's last row)
    neck_m1=((67., 95.6), (99.8, 348.3)),   # Metal1 under the Metal2 neck (y spans; gap = the site's VSS bridge at 96.3-99.0;
                                  # starts above the rail cell's p-tap frame line at 65.5-66.1), via1 array; None = not drawn
    links=dict(TERM_TRIM0=411., TERM_TRIM1=412.2, TERM_TRIM2=413.4, TERM_GATE_N=414.6, TERM_N_R=415.8,
               TERM_GATE_P=421.6, TERM_P_R=422.4),   # Metal3 link rows to the grid trunks (trunks extended down to them)
    vss_p=420.,                   # P block VSS riser lands on the near-bond ground Metal4 wire (y 420)
    vss_n=398.,                   # N block VSS: Metal3 row to the N VSS Metal2 strip (x 220-222)
    bar_w=.8,                     # source / drain Metal2 bar width
    neck_hi=None,                 # b6 (opt-in, None = neck_w all the way): [y_split, width]: the Metal2 neck is neck_w wide below
                                  # y_split and `width` (centred) above it, to the PAD rail; needs neck_m1 None
    top_pins=False,               # b6 ASM-2 (opt-in): every core port except PAD_P / PAD_N as a Metal4 pin on the top edge (via4 from its
                                  # Metal5 trunk), labelled there on Metal4; RX_P / RX_N trunks run up to the top (no side pins)
    pad_trunk_fill=False,         # b7 (opt-in): PAD_P / PAD_N Metal5 grid trunks widened into the free trunk slots beside them (PAD_P to
                                  # the right, PAD_N to the left), each slot only below the start of the trunk that owns it. The 0.44 um trunks
                                  # (16 / 35 ohm typ / high from the HS switches to the neck) push the HS current cells out of saturation (b6 HS
                                  # shortfall). Track positions unchanged.
    fs=None,                      # b6 (opt-in, None = b5): FS high side per leg out of the grid into a block east of the
                                  # termination block, see _USB_FS / _usb_term_block
    term_block=True,              # (2026-11-22, pad_refpad option A) False = no termination block (and no links / bar / height): only the
                                  # site clearing (M1 bar at y 76, ring-stack Via3+ / Metal4-5), the neck width and top_pins. Required for
                                  # reference_clock (which has no USB termination); height_um None = the grid's own height.
)
# usb_term_block 'fs' defaults (b6, 2026-11-20): per leg, east of the termination block's VSS riser, left to right:
# FS_x_R (ring tied to the block VSS riser, bottom head on the PAD rail), OUT riser, 24 x pfet_03v3 (one 24-finger
# PCell, drains -> Metal3 OUT plate), gate riser, 24 x pfet_06v0 (one 24-finger PCell, drains -> Metal3/Metal4 VDD
# plates -> Metal5 VDD bus joining both legs), WELL riser; sources (+ n-tap guard) -> Metal3 WELL row below the devices.
# VDD: the P block's VDD plate crosses the TERM_VCM rail on Metal2 and lands on a Metal5 bar into the grid VDD trunk
# (extended down to vdd_y). GATE / WELL / OUT link to their grid trunks on Metal3 rows (as the termination links).
_USB_FS = dict(
    yd=371.,                      # device centre row
    r_dx=3.5,                     # FS_x_R centre right of the block VSS riser (R centred on the poly row yp)
    g_r=4., g_ps=3.,              # gaps R ring -> pfet_03v3 nwell, pfet_03v3 -> pfet_06v0 nwell
    wrow=(358.4, 360.4),          # WELL Metal3 row
    bw=(.7, .44),                 # drain / source Metal2 bar width (pfet_06v0, pfet_03v3)
    bus=(363., 383.),             # VDD Metal5 bus (both legs)
    bus_w2=None,                  # None = full bus height; else the bus between the two pfet_06v0 plates is a stripe this wide at the
                                  # top of `bus` (less VDD Metal5 over the N leg's neck, termination block and OUT plate: pad C)
    vdd_x=(121.22, 129.22),       # grid VDD trunk (Metal5) extended down to vdd_y
    vdd_y=(396.2, 409.4),         # VDD Metal5 bar from the trunk to the P block crossing
    links=dict(FS_P_GATE=400.6, FS_P_WELL=401.8, FS_P_OUT=403., FS_N_GATE=404.2, FS_N_WELL=405.4, FS_N_OUT=406.6),
                                  # Metal3 rows between the TERM_VCM rail and the termination links (423-429 holds the neck's PAD stacks)
)


def _usb_tb_kinds(circuit, tb_dev):
    dv = [d for d in circuit.devices if d.name in tb_dev]
    poly = {(d.model, d.w_um, d.l_um) for d in dv if d.model.startswith('ppoly')}
    base = {('nfet_06v0', d.w_um, d.l_um, 10, 'top') for d in dv if re.fullmatch(r'TERM_[PN]_\d+', d.name)}
    trim = {('nfet_06v0', d.w_um, d.l_um, 1, 'top') for d in dv if d.name.startswith('TRIM_') and 'fet' in d.model}
    fs = set()
    for leg in 'PN':   # b6 fs block: one 24-finger PCell per side
        for s in ('SUP', 'PAD'):
            u = [d for d in dv if re.fullmatch(f'FS_{leg}_{s}_\\d+', d.name)]
            if u: fs.add((u[0].model, u[0].w_um, u[0].l_um, len(u), 'top'))
    return poly | base | trim | fs


def magic(work, script, *, allow_failure=False):
    command = ['docker', 'run', '--rm', '--network', 'none', '--entrypoint', '/bin/sh',
               '--mount', f'type=bind,src={work},dst=/work', '-w', '/work', IMAGE,
               '-c', f'magic -dnull -noconsole -rcfile {PDK}/libs.tech/magic/gf180mcuD.magicrc /work/{script}']
    result = subprocess.run(command, capture_output=True, text=True, timeout=int(os.environ.get('SVALBARD_MAGIC_TIMEOUT_S', '60')))
    (work / (script + '.log')).write_text(result.stdout + result.stderr)
    if not allow_failure:result.check_returncode()
    return result


def rectangles(path):
    # Installed Magic format: magscale 1 10 with tech lambda=.05 um.
    layer = None
    result = {}
    for line in path.read_text().splitlines():
        if line.startswith('<< '):
            layer = line[3:-3]
        if line.startswith('rect '):
            result.setdefault(layer, []).append([float(v)*.005 for v in line.split()[1:]])
    return result


def terminals(path):
    r = rectangles(path)
    diffusion = next((k for k in ('mvndiffc', 'ndiffc', 'pdiffc', 'mvpdiffc') if k in r),None)
    body = next(k for k in ('mvpsubdiffcont', 'psubdiffcont', 'nsubdiffcont', 'mvnsubdiffcont',
                           'mvnsdiffc', 'nsdiffc', 'nwellc') if k in r)
    def center(rect):
        a,b,c,d = rect
        return ((a+c)/2, (b+d)/2)
    bodyrect = max(r[body], key=lambda a:a[2])
    bx, _ = center(bodyrect)
    if diffusion is None:
        contacts=r['polycontact']
        return [center(max(contacts,key=lambda a:a[3])),
                center(min(contacts,key=lambda a:a[1])),(bx,bodyrect[3]-.2)]
    source = min(r[diffusion], key=lambda a:a[0])
    drain = max(r[diffusion], key=lambda a:a[2])
    gate = min(r['polycontact'], key=lambda a:a[1])
    return [center(drain), center(gate), center(source), (bx, bodyrect[3]-.2)]


def shared_tracks(nets, base_nets, spans, ports, width_overrides_um=None, margin=1.5, target_x=None, quiet=()):
    """PD28: the canonical allocation of base_nets defines the track slots. Ports of the base set keep their
    canonical slot (x unchanged, exclusive; `ports` may include other pinned nets); every other net (old internal nets, new nets, new ports) is packed
    into the remaining 0.44 um slots by interval partitioning of its y-span (M5 trunks are bounded to their spans,
    >= margin um apart on a shared slot)."""
    base=[n for n in base_nets if n in nets]
    slots,widths0=trunk_geometry(base,width_overrides_um={k:v for k,v in (width_overrides_um or {}).items() if k in base})
    tracks,widths={},{}
    for n in base:
        if n in ports or widths0[n]!=.44:
            tracks[n]=slots[n];widths[n]=widths0[n]
    free=sorted(x for n,x in slots.items() if n not in tracks)
    last={x:-1e9 for x in free}
    for n in sorted((n for n in nets if n not in tracks),key=lambda n:spans[n][0]):
        lo,hi=spans[n]
        ok=[x for x in free if last[x]+margin<=lo]
        # keep repacked nets off the slots next to pinned quiet (pad-side) trunks over the same y range
        near=[x for x in ok if any(abs(x-tracks[q])<1.2 and spans[q][0]<hi and lo<spans[q][1] for q in quiet if q in tracks)]
        ok=[x for x in ok if x not in near] or ok
        # nearest feasible slot to the net's devices keeps the M4 lanes short (target_x: mean device x)
        x=min(ok,key=lambda s:abs(s-target_x[n])) if ok and target_x and n in target_x else (ok[0] if ok else None)
        if x is None:raise ValueError('No shared trunk track for '+n)
        tracks[n]=x;widths[n]=.44;last[x]=hi
    return tracks,widths

def _usb_term_block(tb,circuit,tb_dev,keys,work,tracks,rect,via,commands,keepouts,taps,ant_terms,cur,neck_w,bond_pitch):
    """usb_term_block: draw the two termination blocks, their rails, links and the TERM_VCM strap (generate() docstring).
    Per leg, left to right: base unit (TERM_x poly 16/1.48 under its 10 switches as one 10-finger nfet_06v0), trim units
    k = 2, 1, 0 (poly (4*2^k)/2.4 under a 1-finger switch). Bottom to top: PAD rail (M2/M3/M4, joined to the neck),
    poly row (bottom head PAD, top head TERM_x_R / TRIM_x_k_R), M2 plate, switch row (drains down on 0.8 um M2 bars,
    sources up on 0.8 um M2 bars to the TERM_VCM rail, gate contacts on top -> M2 riser), TERM_VCM rail (M3/M4/M5).
    Every bar carries a Via1 column along its whole contact; heads carry a Via1 row; rails have via arrays."""
    dev={d.name:d for d in circuit.devices if d.name in tb_dev}
    def geom(kind):
        r=rectangles(work/(keys[kind]+'.mag'))
        allr=[a for k,v in r.items() if k not in ('checkpaint','properties') for a in v]
        return r,(min(a[0] for a in allr),min(a[1] for a in allr),max(a[2] for a in allr),max(a[3] for a in allr))
    def varr(lo,hi,x1,y1,x2,y2,pitch=.6):   # via stack array lo..hi on a pitch, pads inside the box
        nx=max(1,int((x2-x1-.44)/pitch)+1);ny=max(1,int((y2-y1-.44)/pitch)+1)
        ax=(x1+x2)/2-(nx-1)*pitch/2;ay=(y1+y2)/2-(ny-1)*pitch/2
        for i in range(nx):
            for j in range(ny):via(round(ax+i*pitch,3),round(ay+j*pitch,3),lo,hi)
        return nx*ny
    bw=tb['bar_w'];info=dict(units={},cuts={})
    y0r,y1r=tb['rail'];yp=tb['yp'];ysb=tb['ys_b'];v0,v1=tb['vcm']
    risers={}   # net -> list of (x, y_from)
    xr_end={}
    for leg,x0 in zip('PN',tb['x0']):
        pad='PAD_'+leg;term='TERM_'+leg+'_R'
        units=[('base',dev['TERM_'+leg],[dev[f'TERM_{leg}_{i}'] for i in range(10)])]
        units+=[(f'k{k}',dev[f'TRIM_{leg}_{k}'],[dev[f'TRIM_{leg}_{k}_0']]) for k in (2,1,0)]
        x=x0;rings=[]
        for name,res,sws in units:
            rk=(res.model,res.w_um,res.l_um);sk=('nfet_06v0',sws[0].w_um,sws[0].l_um,len(sws),'top')
            rr,rb=geom(rk);sr,sb=geom(sk)
            half=max(-rb[0],rb[2],-sb[0],sb[2]);xc=x+half;x+=2*half+tb['gap']
            ysc=ysb-sb[1];node=res.nodes[1]
            for d in sws:
                if d.nodes[0]!=node or d.nodes[2]!='TERM_VCM' or d.nodes[3]!='VSS':raise ValueError('usb_term_block: switch '+d.name)
            if res.nodes[0]!=pad:raise ValueError('usb_term_block: poly '+res.name)
            commands.extend([f'getcell {keys[rk]} child 0 0 parent {xc} {yp}',f'identify X{res.name}',
                             f'getcell {keys[sk]} child 0 0 parent {xc} {ysc}',f'identify X{sws[0].name}'])
            keepouts.append((xc+rb[0],yp+rb[1],xc+rb[2],yp+rb[3]));keepouts.append((xc+sb[0],ysc+sb[1],xc+sb[2],ysc+sb[3]))
            taps.append(keepouts[-1])
            # --- poly heads: bottom = PAD (plate down to the rail), top = node (plate up to the switch)
            hb,ht=sorted(rr['polycontact'],key=lambda a:a[1]);vys={}
            for h,net,down in ((hb,pad,True),(ht,node,False)):
                cur[0]=net;hy=(h[1]+h[3])/2;x1,x2=xc+h[0],xc+h[2]
                ylo,yhi=(yp+hy-.3,yp+h[3]) if down else (yp+h[1],yp+hy+.3)
                rect('metal1',x1,ylo,x2,yhi)
                vy=round(yp+hy+(-.0925 if down else .0925),3);n=0;xx=x1+.3;vys[down]=vy
                while xx<=x2-.3+1e-9:via(round(xx,3),round(vy,3),1,2);xx+=.6;n+=1
                info['cuts'][f'{leg}_{name}_{"pad" if down else "node"}_via1']=n
                if down:rect('metal2',x1,y0r,x2,vy+.2)
            # --- switch columns
            cols=sorted(sr['mvndiffc'],key=lambda a:a[0]);c1,c2=cols[0][1],cols[0][3]
            yplate_top=ysc+c1-.35
            cur[0]=node;rect('metal2',xc+ht[0],vys[False]-.2,xc+ht[2],yplate_top)   # node plate
            for i,c in enumerate(cols):
                cx=xc+(c[0]+c[2])/2;up=(i%2==0)
                cur[0]='TERM_VCM' if up else node
                ant_terms.append((cx,ysc,cur[0],'sd',0.))   # diffusion on the net: not a gate-only partial net
                rect('metal1',cx-.19,ysc+c1,cx+.19,ysc+c2)
                yy=ysc+c1+.25
                while yy<=ysc+c2-.25+1e-9:via(round(cx,3),round(yy,3),1,2);yy+=.6
                if up:
                    rect('metal2',cx-bw/2,ysc+c1,cx+bw/2,v1-.2)
                    yy=v0+.3
                    while yy<=v1-.3+1e-9:via(round(cx,3),round(yy,3),2,3);yy+=.6
                else:rect('metal2',cx-bw/2,yplate_top-.5,cx+bw/2,ysc+c2)
            # --- gate: Metal1 strap over the gate contacts, Via1 on a drain-column x, Metal2 riser up
            g=sorted(sr['polycontact'],key=lambda a:a[0]);gy=(g[0][1]+g[0][3])/2
            gx=xc+(cols[1][0]+cols[1][2])/2 if len(cols)==2 else xc+(cols[5][0]+cols[5][2])/2
            gnet=sws[0].nodes[1];cur[0]=gnet
            rect('metal1',min(xc+g[0][0]-.06,gx-.19),ysc+gy-.2,max(xc+g[-1][2]+.06,gx+.19),ysc+gy+.2)
            via(round(gx,3),round(ysc+gy,3),1,2);risers.setdefault(gnet,[]).append((gx,ysc+gy))
            ant_terms.append((gx,ysc+gy,gnet,'g',sum(d.w_um*d.l_um for d in sws)))
            # --- rings: Metal1 bridge poly ring (top bar) -> switch ring (bottom bar), on the switch ring's left side
            pr=[a for a in rr['metal1'] if a[2]-a[0]>2*abs(a[1]) and a[1]>0];sr1=[a for a in sr['metal1'] if a[2]-a[0]>1. and a[3]<0]
            ptop=min(pr,key=lambda a:a[1]);sbot=min(sr1,key=lambda a:a[1])   # inner edge of the poly ring top bar / switch ring bottom bar
            sl=min(sr['mvpsubdiffcont'],key=lambda a:a[0]);cur[0]='VSS'
            rect('metal1',xc+sl[0],yp+ptop[1],xc+sl[2],ysc+sbot[3])
            rl=min(rr['psubdiffcont'],key=lambda a:a[0]);rrt=max(rr['psubdiffcont'],key=lambda a:a[0])
            rings.append((xc+rl[0],xc+rrt[2]))
            if name=='base':   # TERM node riser in the left margin
                cur[0]=node;xt=xc-half-.75
                rect('metal2',xt-.2,yp+(ht[1]+ht[3])/2-.1,xc+ht[0]+.5,yplate_top)
                risers.setdefault(node,[]).append((xt,yp+(ht[1]+ht[3])/2))
            info['units'][f'{leg}_{name}']=dict(x=round(xc,3),poly=list(rk),switch=list(sk),ysw=round(ysc,3))
        cur[0]='VSS'
        for (a1,a2),(b1,b2) in zip(rings,rings[1:]):rect('metal1',a2-.23,yp-.5,b1+.23,yp+.5)   # poly ring sides
        xv=x-tb['gap']+.75;rect('metal1',rings[-1][1]-.23,yp-.5,xv+.19,yp+.5);via(xv,yp,1,2)
        risers.setdefault('VSS_'+leg,[]).append((xv,yp))
        x_fs_end=None
        if tb['fs'] is not None:x_fs_end=_usb_fs_block(tb,leg,xv,dev,keys,geom,rect,via,varr,commands,keepouts,taps,ant_terms,cur,risers,info)
        # --- PAD rail: Metal2/3/4 from the neck to the block end; Metal1 in parallel with the Metal2 neck through the ring band
        cur[0]=pad;xn=37.5+(0. if leg=='P' else bond_pitch)+(neck_w if tb['neck_hi'] is None else tb['neck_hi'][1])/2;xe=x-tb['gap'] if x_fs_end is None else x_fs_end
        for y1_,y2_ in tb['neck_m1'] or ():
            rect('metal1',xn-neck_w+.3,y1_,xn-.3,y2_);info['cuts'][f'{leg}_neck_via1_{y1_:g}']=varr(1,2,xn-neck_w+.3,y1_,xn-.3,y2_,pitch=2.)
        for m in ('metal2','metal3','metal4'):rect(m,xn-1.,y0r,xe,y1r)
        info['cuts'][f'{leg}_pad_rail']=varr(2,4,xn-1.,y0r,xe,y1r,pitch=.7)   # >= 0.36 um cut spacing in arrays (V2.2b / V3.2b)
        xr_end[leg]=(x0,xe)
    # --- TERM_VCM rail (both legs), strap, bar to the trunk at its pin
    cur[0]='TERM_VCM';xa=tb['x0'][0]-2.;xb=max(xr_end['N'][1]+1.5,tb['strap'][1])
    for m in ('metal3','metal4','metal5'):rect(m,xa,v0,xb,v1)
    info['cuts']['vcm_rail']=varr(3,5,xa,v0,xb,v1,pitch=1.6)
    s1,s2=tb['strap'];b1,b2=tb['bar'];xt=tracks['TERM_VCM']
    rect('metal4',s1,v0,s2,b2)
    sm=(s1+s2)/2;rect('metal5',s1,v0,sm-1.,b2);rect('metal5',sm+1.,v0,s2,b2);rect('metal5',s1,v0,s2,v1)   # Metal5 in two stripes (wide-metal slot rule MSLOT5.1)
    n=0;yy=v1+1.
    while yy+2.<b1:n+=varr(4,5,s1,yy,sm-1.,yy+2.,pitch=2.)+varr(4,5,sm+1.,yy,s2,yy+2.,pitch=2.);yy+=24.
    info['cuts']['strap_via4']=n
    rect('metal3',xt-.6,b1,s2,b2);rect('metal4',xt-.6,b1,s2,b2)
    info['cuts']['bar_via3']=varr(3,4,xt+1.,b1,s2,b2,pitch=3.)
    n=0;yy=b1+.4
    while yy<=b2-.4+1e-9:via(xt,round(yy,3),3,5);yy+=.6;n+=1
    info['cuts']['trunk_via4']=n
    # --- links: Metal2 risers -> Metal3 rows -> Via3/Via4 onto the extended grid trunk
    def riser(x,yf,yt_,net):
        cur[0]=net;rect('metal2',x-.2,yf,x+.2,yt_+.2);via(x,yt_,2,3)
    for net,yl in tb['links'].items():
        xs=[x for x,_ in risers[net]]
        for x,yf in risers[net]:riser(x,yf,yl,net)
        cur[0]=net;xtn=tracks[net]
        rect('metal3',min(xs+[xtn])-.2,yl-.2,max(xs+[xtn])+.2,yl+.2);via(xtn,yl,3,5)
    if tb['fs'] is not None:
        fs=tb['fs']
        for net,yl in fs['links'].items():
            (x,yf),=risers[net];riser(x,yf,yl,net)
            cur[0]=net;xtn=tracks[net]
            rect('metal3',min(x,xtn)-.2,yl-.2,max(x,xtn)+.2,yl+.2);via(xtn,yl,3,5)
        # VDD: Metal5 bus over both pfet_06v0 plates; the P plate crosses the TERM_VCM rail on Metal2 into a Metal5 bar to the trunk
        cur[0]='VDD';b0,b1=fs['bus'];sp_,sn_=info['fs']['P']['sup_x'],info['fs']['N']['sup_x']
        if fs['bus_w2'] is None:rect('metal5',sp_[0],b0,sn_[1],b1)
        else:
            rect('metal5',sp_[0],b0,sp_[1],b1);rect('metal5',sn_[0],b0,sn_[1],b1);rect('metal5',sp_[1]-.5,b1-fs['bus_w2'],sn_[0]+.5,b1)
        for leg in 'PN':
            s0,s1=info['fs'][leg]['sup_x'];info['cuts'][f'fs_{leg}_vdd_via4']=varr(4,5,s0+.5,b0+.5,s1-.5,b1-.5,pitch=2.)
        xc=(sp_[0]+sp_[1])/2;yt=info['fs']['P']['sup_top'];v0_,v1_=fs['vdd_y']
        rect('metal3',xc-4.,yt-2.,xc+4.,v0-.6);rect('metal2',xc-4.,yt+.6,xc+4.,v0_+3.2)   # Metal3 from the plate up to the rail
        info['cuts']['fs_vdd_cross_via2']=varr(2,3,xc-4.,yt+.6,xc+4.,v0-.6,pitch=.7)
        info['cuts']['fs_vdd_up']=varr(2,5,xc-4.,v0_,xc+4.,v0_+3.2,pitch=.7)
        rect('metal5',fs['vdd_x'][0],v0_,xc+4.,v1_)
    (xv,yv),=risers['VSS_P'];riser(xv,yv,tb['vss_p'],'VSS');via(xv,tb['vss_p'],3,4)
    (xv,yv),=risers['VSS_N'];riser(xv,yv,tb['vss_n'],'VSS');cur[0]='VSS'
    rect('metal3',bond_pitch+10.-.2,tb['vss_n']-.2,xv+.2,tb['vss_n']+.2);via(bond_pitch+10.,tb['vss_n'],2,3)
    cur[0]=None
    labels=[]
    for leg,(xa_,xe_) in xr_end.items():
        for k in range(3):
            u=info['units'][f'{leg}_k{k}'];labels.append((f'TRIM_{leg}_{k}_R',u['x'],yp+3.,'metal2'))
    for net,x,y,layer in labels:
        commands += [f'box values {x-.2} {y-.2} {x+.2} {y+.2}',f'label {net} FreeSans 0.3 0 0 0 c {layer}']
    info['risers']={k:[[round(a,3),round(b,3)] for a,b in v] for k,v in risers.items()}
    return info


def _usb_fs_block(tb,leg,xv,dev,keys,geom,rect,via,varr,commands,keepouts,taps,ant_terms,cur,risers,info):
    """usb_term_block 'fs' (b6): the FS high side of one leg as a block east of the termination block (see _USB_FS).
    Returns the x where the PAD rail must reach (FS_x_R bottom head)."""
    fs=tb['fs'];yp=tb['yp'];y0r=tb['rail'][0];yd=fs['yd'];pad='PAD_'+leg
    gate,well,out=f'FS_{leg}_GATE',f'FS_{leg}_WELL',f'FS_{leg}_OUT'
    sup=[dev[f'FS_{leg}_SUP_{i}'] for i in range(24)];pm=[dev[f'FS_{leg}_PAD_{i}'] for i in range(24)];res=dev[f'FS_{leg}_R']
    for d in sup:
        if d.nodes!=('VDD',gate,well,well):raise ValueError('fs block: '+d.name)
    for d in pm:
        if d.nodes!=(out,gate,well,well):raise ValueError('fs block: '+d.name)
    if tuple(res.nodes[:2])!=(out,pad):raise ValueError('fs block: '+res.name)
    ks=(sup[0].model,sup[0].w_um,sup[0].l_um,24,'top');kp=(pm[0].model,pm[0].w_um,pm[0].l_um,24,'top');kr=(res.model,res.w_um,res.l_um)
    rr,rb=geom(kr);pr,pb=geom(kp);sr,sb=geom(ks)
    xR=xv+fs['r_dx'];yR=yp
    xP=xR+rb[2]+fs['g_r']-pb[0];xS=xP+pb[2]+fs['g_ps']-sb[0]
    xo=(xR+rb[2]+xP+pb[0])/2;xg=(xP+pb[2]+xS+sb[0])/2;xw=xS+sb[2]+1.
    for k,xc,yc,nm in ((kr,xR,yR,res.name),(kp,xP,yd,pm[0].name),(ks,xS,yd,sup[0].name)):
        commands.extend([f'getcell {keys[k]} child 0 0 parent {xc} {yc}',f'identify X{nm}'])
    for b,xc,yc in ((rb,xR,yR),(pb,xP,yd),(sb,xS,yd)):
        keepouts.append((xc+b[0],yc+b[1],xc+b[2],yc+b[3]));taps.append(keepouts[-1])
    # --- R: bottom head PAD (Metal2 down to the rail), top head OUT (Via1/Via2 stack under the OUT plate); ring -> VSS riser
    hb,ht=sorted(rr['polycontact'],key=lambda a:a[1])
    for h,net,down in ((hb,pad,True),(ht,out,False)):
        cur[0]=net;hy=yR+(h[1]+h[3])/2;x1,x2=xR+h[0],xR+h[2]
        rect('metal1',x1,hy-.2,x2,hy+.2);n=0;xx=x1+.3
        while xx<=x2-.3+1e-9:via(round(xx,3),round(hy,3),1,2 if down else 3);xx+=.6;n+=1
        rect('metal2',x1,hy-.2,x2,hy+.2)
        info['cuts'][f'fs_{leg}_r_{"pad" if down else "out"}']=n
        if down:rect('metal2',x1,y0r,x2,hy+.2)
        else:yh=hy
    rl=min(rr['psubdiffcont'],key=lambda a:a[0]);cur[0]='VSS'
    rect('metal1',xv-.19,yp-.5,xR+rl[2],yp+.5)
    # --- pfets: columns (even = source = WELL, n-tap guard joined), odd = drain
    wr0,wr1=fs['wrow'];wm=(wr0+wr1)/2;tops={}
    for r_,b,xc,dnet,bw,tag in ((pr,pb,xP,out,fs['bw'][1],'pad'),(sr,sb,xS,'VDD',fs['bw'][0],'sup')):
        ck=[k for k in r_ if k.endswith('diffc') and 'sub' not in k][0]
        cols=sorted(r_[ck],key=lambda a:a[0]);c1,c2=cols[0][1],cols[0][3]
        gbot=min((a for a in r_['metal1'] if a[2]-a[0]>5.),key=lambda a:a[1])   # guard ring bottom bar
        if len(cols)%2!=1:raise ValueError('fs block: even column count')
        for i,c in enumerate(cols):
            cx=xc+(c[0]+c[2])/2;src=(i%2==0);net=well if src else dnet;cur[0]=net
            ant_terms.append((cx,yd,net,'sd',0.))
            rect('metal1',cx-.19,yd+c1,cx+.19,yd+c2)
            if src:rect('metal1',cx-.115,yd+gbot[1],cx+.115,yd+c1)
            yy=yd+c1+.25
            while yy<=yd+c2-.25+1e-9:via(round(cx,3),round(yy,3),1,2);yy+=.6
            if src:
                rect('metal2',cx-bw/2,wr0,cx+bw/2,yd+c2);via(round(cx,3),wm,2,3)
            else:
                rect('metal2',cx-bw/2,yd+c1,cx+bw/2,yd+c2)
                yy=yd+c1+.55
                while yy<=yd+c2-.25+1e-9:via(round(cx,3),round(yy,3),2,3);yy+=.6
        tops[tag]=(xc+b[0],xc+b[2],yd+c1,yd+c2,yd+b[3])
    # --- gate strap (Metal1 over both PCells' gate contacts), riser in the gap
    gp_=sorted(pr['polycontact'],key=lambda a:a[0]);gs_=sorted(sr['polycontact'],key=lambda a:a[0])
    gy=yd+(gp_[0][1]+gp_[0][3])/2
    if abs(gy-(yd+(gs_[0][1]+gs_[0][3])/2))>1e-6:raise ValueError('fs block: gate rows differ')
    cur[0]=gate   # one Metal1 strap inside each guard ring (the ring sides are WELL), Metal2 bridge across the gap
    for g_,xc in ((gp_,xP),(gs_,xS)):
        rect('metal1',xc+g_[0][0]-.06,gy-.2,xc+g_[-1][2]+.06,gy+.2)
    xa_,xb_=xP+gp_[-1][0]+.1,xS+gs_[0][2]-.1;via(xa_,gy,1,2);via(xb_,gy,1,2);rect('metal2',xa_-.2,gy-.2,xb_+.2,gy+.2)
    risers.setdefault(gate,[]).append((xg,gy))
    ant_terms.append((xg,gy,gate,'g',sum(d.w_um*d.l_um for d in sup+pm)))
    # --- WELL row + riser; OUT plate + riser; VDD plates (Metal3 + Metal4) over the pfet_06v0
    cur[0]=well;rect('metal3',xP+pb[0],wr0,xw+.3,wr1);via(xw,wm,2,3);risers.setdefault(well,[]).append((xw,wm))
    cur[0]=out;p0,p1,d1,d2,ptop=tops['pad']
    rect('metal3',xR+ht[0]-.3,yh-.5,p1,d2+.3);via(xo,yd,2,3);risers.setdefault(out,[]).append((xo,yd))
    cur[0]='VDD';s0,s1,d1,d2,stop=tops['sup']
    rect('metal3',s0,d1,s1,d2+.3);b0,b1=fs['bus'];rect('metal4',s0,max(d1,b0),s1,b1)
    info['cuts'][f'fs_{leg}_vdd_via3']=varr(3,4,s0+.3,max(d1,b0)+.3,s1-.3,min(d2,b1)-.3,pitch=.7)
    info.setdefault('fs',{})[leg]=dict(r=[round(xR,3),round(yR,3)],pad=[round(xP,3),yd],sup=[round(xS,3),yd],sup_x=[round(s0,3),round(s1,3)],
                                      sup_top=round(stop+.4,3),risers=dict(out=xo,gate=xg,well=xw))
    cur[0]=None
    return xR+hb[2]


def generate(work,family='wired_transmit', *, external_primary=False, serial_tail_units=None, folded_tails=False, fs_high_width_um=20., fs_series_geometry_um=None, trunk_width_overrides_um=None,
             columns=7, port_top_um=None, bond_y_offsets_um=(12.,4.), keep_tracks_of=None, pair_prefixes=(), cap_x_um=166.,
             cap_min_y_um=560., circuit_override=None, usb_term_block=None):
    # Compact-family options (defaults reproduce the canonical layout exactly):
    #   columns: devices per placement row (the M4 route rows need columns*3.2+2.4 <= 26 um, so <= 7);
    #   port_top_um: draw every cell port's M5 trunk up to this y and label it there (boundary pins);
    #   bond_y_offsets_um: depth of the P/N bond M4 transverses below active_origin.
    #   keep_tracks_of (PD28, opt-in): nets that keep the trunk x of the canonical allocation for exactly that net
    #     set; every other (new) net shares an existing 0.44 um signal track whose y-span it does not overlap
    #     (shared_tracks below). Lets an extended circuit fit the full 146 um trunk bank with unchanged port x.
    #   pair_prefixes (PD46, opt-in): MOS whose names start with one of these and that share model/size/all four
    #     nodes with another such MOS are drawn pairwise as one 2-finger PCell (S-D-S, outer sources strapped on M2,
    #     the two gate contacts strapped on M1): one placement and four M4 rows per pair instead of two. Same devices
    #     and sizes in the extraction (Magic extracts one device per finger).
    #   Capacitor devices (PD46, cap_mim_2f0_m4m5_noshield) sit off-array in the strip right of the trunk bank
    #     (centre x cap_x_um, y >= cap_min_y_um), next to their nets' rows; bottom plate (M4) and top plate (M5 ->
    #     via4 -> M4) each reach their net trunk on an M4 wire in a free inter-row gap (rows use y0+1..y0+22.8).
    #   circuit_override: use this Circuit instead of build(family).
    #   usb_term_block (ESD option A for pad_wirepad, 2026-11-20, opt-in; None = the published geometry): dict, see
    #     _usb_term_block. The HS termination of each leg (TERM_x poly, its 10 switches, the 3 trim polys + switches) leaves
    #     the device grid and is drawn as a low-resistance block between the ring band and the grid (y 352..396), fed
    #     straight from a wider Metal2 neck; TERM_VCM returns on a wide Metal4/5 strap to the TERM_VCM pin. The pad sites
    #     are cleared for the pad-site primaries (M1 bar at y 76 and the ring stacks' Via3/Via4/M4/M5 not drawn).
    #     Same circuit, same devices; the cell height is kept (ports at the published y).
    tb=dict(_USB_TB) if usb_term_block is not None else None
    if tb is not None:
        if set(usb_term_block)-set(tb):raise ValueError('usb_term_block: unknown key')
        tb.update(usb_term_block)
        if not tb['term_block']:tb.update(links={},fs=None)
        if family!='wired_receive_usb' and not (family=='reference_clock' and not tb['term_block']):
            raise ValueError('usb_term_block is for wired_receive_usb (reference_clock: term_block False only)')
        if tb['neck_hi'] is not None and tb['neck_m1']:raise ValueError('usb_term_block: neck_hi needs neck_m1 None')
        if tb['fs'] is not None:
            if set(tb['fs'])-set(_USB_FS):raise ValueError('usb_term_block fs: unknown key')
            tb['fs']=dict(_USB_FS,**tb['fs'])
    if serial_tail_units is not None:
        if family!='wired_transmit':raise ValueError('Serial tail sizing applies only to wired TX')
        from circuits import wired_transmit
        circuit=wired_transmit(serial_tail_units=serial_tail_units)
    else:circuit = build(family) if circuit_override is None else circuit_override
    if (fs_high_width_um!=20. or fs_series_geometry_um is not None) and circuit_override is None:
        if family!='wired_receive_usb':raise ValueError('FS sizing applies only to RX/USB')
        from wired_receive import build as receive_build
        circuit=receive_build(fs_high_width_um=fs_high_width_um,fs_series_geometry_um=fs_series_geometry_um)
    if external_primary:
        if family not in ('wired_transmit','reference_clock','wired_receive_usb'):raise ValueError('Unsupported external-primary family')
        protection=[d for d in circuit.devices if d.name.startswith('ESD_')]
        if len(protection)!=4:raise ValueError('Recheck replacement protection topology')
        circuit.devices=[d for d in circuit.devices if d not in protection]
    escape_width=12. if family in ('rf_receive','rf_transmit') else 4.
    if tb is not None:escape_width=tb['neck_w']
    tb_dev=set()
    if tb is not None and tb['term_block']:
        import re as _re
        tb_dev={d.name for d in circuit.devices if _re.fullmatch(r'(TERM_[PN]|TERM_[PN]_\d+|TRIM_[PN]_\d+|TRIM_[PN]_\d+_\d+)',d.name)}
        if len(tb_dev)!=2*(1+10+3+3):raise ValueError(f'usb_term_block: unexpected termination devices {sorted(tb_dev)}')
        if tb['fs'] is not None:
            fs_dev={d.name for d in circuit.devices if _re.fullmatch(r'FS_[PN]_(SUP_\d+|PAD_\d+|R)',d.name)}
            if len(fs_dev)!=2*(24+24+1):raise ValueError(f'usb_term_block fs: unexpected FS devices {sorted(fs_dev)}')
            tb_dev|=fs_dev
    placement_source=Path(__file__).with_name('generated')/'provider-sites.json'
    reference=json.loads(placement_source.read_text())
    contract=resolve()['assembly_policy']
    if reference['template_commit']!=contract['provider_template_commit'] or reference['image_id'] not in (IMAGE,LOCKED_IMAGE):
        raise ValueError('Regenerate provider-site reference for the pinned template and image')
    pair=[reference['sites'][p['site']] for p in circuit.requirements['pads']]
    bond_pitch=math.dist(pair[0]['bond_center_um'],pair[1]['bond_center_um'])
    if bond_pitch<75:raise ValueError('Provider pair is narrower than the native bond cells')
    candidate_width=75+bond_pitch
    side=circuit.requirements['pads'][0]['side']
    core=reference['core_area_um'];site=pair[0]['bbox_um']
    clearance={'west':core[0]-site[0], 'east':site[2]-core[2],
               'south':core[1]-site[1], 'north':site[3]-core[3]}[side]
    active_origin=max(80.,clearance+24.)
    flat='pad_tx_flat' if family=='wired_transmit' else circuit.name+'_flat'
    work.mkdir(parents=True, exist_ok=True)
    if list(work.glob('*.mag')):
        raise FileExistsError('Use an empty output directory: Magic must not merge a previous layout')
    from circuits import Capacitor
    caps=[d for d in circuit.devices if isinstance(d,Capacitor)]
    pair_of={}
    if pair_prefixes:
        pend={}
        for d in circuit.devices:
            if isinstance(d,Capacitor) or 'fet' not in d.model or not d.name.startswith(tuple(pair_prefixes)) or d.name in tb_dev:continue
            k=(d.model,d.w_um,d.l_um,d.nodes)
            if k in pend:pair_of[pend.pop(k).name]=d
            else:pend[k]=d
    paired={d.name for d in pair_of.values()}
    def kkey(d):return (d.model,d.w_um,d.l_um)+((2,) if d.name in pair_of else ())
    kinds = sorted({kkey(d) for d in circuit.devices if d.name not in paired and d.name not in tb_dev}|(_usb_tb_kinds(circuit,tb_dev) if tb is not None else set()), key=str)
    keys = {k: f'{circuit.name}__primitive_{i}' for i,k in enumerate(kinds)}  # block-unique (chip GDS merge)
    commands = ['crashbackups stop', 'load primitive_workspace']
    for kind, name in keys.items():
        model, width, length = kind[:3]
        if model.startswith('cap_mim'):
            commands += ['units internal', f'set cell [magic::gencell_makecell gf180mcu::cap_mim_2p0fF w {width} l {length}]',
                         'load $cell', f'save {name}', 'load primitive_workspace']
            continue
        if model.startswith('ppoly'):
            commands += ['units internal', f'set cell [magic::gencell_makecell gf180mcu::{model} w {width} l {length} guard 1 full_metal 1]',
                         'load $cell',f'save {name}','load primitive_workspace']
            continue
        if model.endswith('_dss'):
            # Installed DSS PCell paints M1 over unsilicided diffusion without
            # a diffusion contact. Build a contacted ballast geometry instead.
            commands += [f'load {name}', 'units microns']
            def paint(layer,x1,y1,x2,y2):
                commands.extend([f'box values {x1} {y1} {x2} {y2}', f'paint {layer}'])
            h, half = width/2, length/2
            left, right = -half-.72, half+4.22
            paint('pwell',left-1.,-h-1.6,right+1.,h+1.6)
            paint('mvndiff',left,-h,right,h)
            paint('polysilicon',-half,-h-.46,half,h+.46)
            paint('hvnmos',-half,-h,half,h)
            paint('mvndiffres',-half-.28,-h,-half,h)
            paint('mvndiffres',half,-h,half+3.78,h)
            for x in (left+.22,right-.22):
                paint('mvndiffc',x-.115,-h+.1,x+.115,h-.1)
                paint('metal1',x-.18,-h+.04,x+.18,h-.04)
            paint('polycontact',-half+.065,-h-.395,half-.065,-h-.165)
            paint('metal1',-half+.01,-h-.45,half-.01,-h-.11)
            for x in (left-.6,right+.6):
                paint('mvpsubdiff',x-.18,-h-1.,x+.18,h+1.)
                paint('mvpsubdiffcont',x-.115,-h-.9,x+.115,h+.9)
                paint('metal1',x-.18,-h-1.,x+.18,h+1.)
            for y in (-h-1.,h+1.):
                paint('mvpsubdiff',left-.78,y-.18,right+.78,y+.18)
                paint('metal1',left-.78,y-.18,right+.78,y+.18)
            commands += ['save', 'load primitive_workspace']
            continue
        tc='topc 1 botc 0' if len(kind)>4 and kind[4]=='top' else 'topc 0 botc 1'   # usb_term_block switches: gate contacts on top
        commands += ['units internal', f'set cell [magic::gencell_makecell gf180mcu::{model} w {width} l {length} nf {kind[3] if len(kind)>3 else 1} guard 1 {tc} full_metal 1 gate_to_polycont 0.6 gate_extension 0.8 diff_gate_space 0.3]',
                     'load $cell', f'save {name}', 'load primitive_workspace']
    commands += ['quit -noprompt']
    (work/'primitives.tcl').write_text('\n'.join(commands)+'\n')
    magic(work, 'primitives.tcl')
    def cap_terminals(path):   # (top: M5 over the contact, left edge; bottom: left M4 frame column), cell bbox
        r=rectangles(path);c=r['mimcapcontact'][0];f=min(r['metal4'],key=lambda a:(a[0],-(a[3]-a[1])))
        return [(c[0]+.3,(c[1]+c[3])/2),((f[0]+f[2])/2,(f[1]+f[3])/2)],c,f
    def pair_terminals(path):   # 2-finger: drain = centre contact, source = left outer contact
        r=rectangles(path)
        diff=next(k for k in ('mvndiffc','ndiffc','pdiffc','mvpdiffc') if k in r)
        body=next(k for k in ('mvpsubdiffcont','psubdiffcont','nsubdiffcont','mvnsubdiffcont','mvnsdiffc','nsdiffc','nwellc') if k in r)
        cs=sorted(r[diff],key=lambda a:a[0]);g=sorted(r['polycontact'],key=lambda a:a[0])
        if len(cs)!=3 or len(g)!=2:raise ValueError('Unexpected 2-finger PCell')
        ctr=lambda a:((a[0]+a[2])/2,(a[1]+a[3])/2)
        br=max(r[body],key=lambda a:a[2])
        return [ctr(cs[1]),ctr(g[0]),ctr(cs[0]),(ctr(br)[0],br[3]-.2)],dict(sources=[ctr(cs[0]),ctr(cs[2])],src_top=cs[0][3],gates=[ctr(g[0]),ctr(g[1])],gate_box=(g[0][0],g[0][1],g[1][2],g[1][3]))
    pinloc,pairgeo,capgeo={},{},{}
    for k,name in keys.items():
        if k[0].startswith('cap_mim'):pinloc[k],*capgeo[k]=cap_terminals(work/(name+'.mag'))
        elif len(k)>4:pinloc[k]=None   # usb_term_block: geometry read by _usb_term_block
        elif len(k)>3:pinloc[k],pairgeo[k]=pair_terminals(work/(name+'.mag'))
        else:pinloc[k]=terminals(work/(name+'.mag'))
    nets = sorted({n for d in circuit.devices for n in d.nodes})
    if tb is not None:   # block-internal nets (TRIM_x_k_R) get no grid trunk
        nets=sorted({n for d in circuit.devices if d.name not in tb_dev for n in d.nodes}|set(circuit.ports))
    pitch, row_height = 21., 26.
    if not 1<=columns<=7:raise ValueError('M4 route rows support at most 7 columns per 26 um row')
    folded_names=set();folded_meta=None
    core_reservation_width = 143. if family=="wired_receive_usb" else 150.
    core_devices = [d for d in circuit.devices if not d.name.startswith("ESD_") and d.name not in paired and not isinstance(d,Capacitor) and d.name not in tb_dev]
    protection_devices = [d for d in circuit.devices if d.name.startswith("ESD_")]
    bounded_routes = True
    signal_ports={'PAD_P','PAD_N','RX_P','RX_N'}
    if bounded_routes:
        # Pair corresponding P/N front-end devices near the bond-facing edge.
        # Backend controls retain their order; no devices or branches disappear.
        front=[d for d in core_devices if signal_ports.intersection(d.nodes)]
        back=[d for d in core_devices if not signal_ports.intersection(d.nodes)]
        front.sort(key=lambda d:(d.name.replace('_P','_PAIR').replace('_N','_PAIR'),d.name))
        core_devices=front+back

    if folded_tails:
        if family!='wired_transmit' or serial_tail_units!=32:
            raise ValueError('Folded placement currently supports the32-finger TX diagnostic only')
        from folded_tail import generate as generate_folded
        folded_meta=generate_folded(work/'folded-bank',serial_tail_units)
        # Parent routes supply net labels. Child port labels would introduce many
        # duplicate aliases after flattening; preserve geometry, omit labels only.
        primitive_lines=(work/'folded-bank/folded_tail.mag').read_text().splitlines()
        geometry=[];in_labels=False
        for line in primitive_lines:
            if line.startswith('<< '):in_labels=line=='<< labels >>'
            if not in_labels:geometry.append(line)
        (work/'folded_tail.mag').write_text('\n'.join(geometry)+'\n')
        groups={};ordinary=[]
        for device in core_devices:
            if device.name.startswith(('MAIN_TAIL_','POST_TAIL_')):
                groups.setdefault(device.nodes,[]).append(device)
            else:ordinary.append(device)
        if len(groups)!=16 or any(len(v)!=32 for v in groups.values()):raise ValueError('Unexpected tail groups')
        representatives=[v[0] for v in groups.values()]
        folded_names={d.name for d in representatives}
        core_devices=ordinary+representatives
        ordinary_rows=math.ceil(len(ordinary)/columns)
        placements=[(12+(i%columns)*pitch,active_origin+(i//columns)*row_height+13,
                     active_origin+(i//columns)*row_height+1+(i%columns)*4*.8) for i in range(len(ordinary))]
        placements += [(32+(i%2)*65,active_origin+ordinary_rows*row_height+(i//2)*28+13,
                        active_origin+ordinary_rows*row_height+(i//2)*28+1+(i%2)*4*.8) for i in range(len(representatives))]
        height=active_origin+ordinary_rows*row_height+math.ceil(len(representatives)/2)*28+6
    else:
        placements=[(12+(i%columns)*pitch,active_origin+(i//columns)*row_height+13,
                     active_origin+(i//columns)*row_height+1+(i%columns)*4*.8) for i in range(len(core_devices))]
        height = active_origin + math.ceil(len(core_devices)/columns)*row_height + 6
    if tb is not None and tb['height_um'] is not None:height=max(height,tb['height_um'])
    cap_place={}
    if caps:
        nrows=math.ceil(len(core_devices)/columns)
        gap=lambda r:active_origin+r*row_height+24.9
        used=set()
        for cd in caps:
            ys=[placements[i][1] for i,d in enumerate(core_devices) if cd.nodes[1] in d.nodes or cd.nodes[0] in d.nodes]
            want=sum(ys)/len(ys)
            ok=[r for r in range(nrows-1) if gap(r)-2.>=cap_min_y_um and not {r-1,r,r+1,r+2}&used]
            if not ok:raise ValueError('No room for capacitor '+cd.name)
            r=min(ok,key=lambda r:abs(gap(r)+13.5-want));used|={r,r+1}
            cap_place[cd]=(gap(r)+13.2,(gap(r+1),gap(r)))   # (centre y, (top route y, bottom route y))
    layout_spec=PROJECT/'spec/schematic-implementation.json'
    selected_layout=json.loads(layout_spec.read_text())['io_pad_first_pass'].get('layout_parameters',{}).get(family,{})
    if trunk_width_overrides_um is None:trunk_width_overrides_um=selected_layout.get('trunk_width_overrides_um',{})
    tracks,trunk_widths=trunk_geometry(nets if keep_tracks_of is None else [n for n in nets if n in keep_tracks_of],width_overrides_um=trunk_width_overrides_um)  # PD28: new nets placed by shared_tracks below
    port_heights={port:(active_origin-2 if bounded_routes and port in signal_ports else height)
                  for port in circuit.ports}
    if port_top_um is not None:
        if port_top_um<height:raise ValueError('Boundary port height below the device array')
        port_heights={port:port_top_um for port in circuit.ports}
    net_spans={net:(active_origin-4,height) for net in nets}
    if bounded_routes:
        endpoints={net:[] for net in nets}
        for index,device in enumerate(core_devices):
            for terminal,net in enumerate(device.nodes):
                endpoints[net].append(placements[index][2]+terminal*.8)
        for port,y in port_heights.items():endpoints[port].append(y)
        for cd,(cy_,gy) in cap_place.items():
            for net,yy in zip(cd.nodes,gy):endpoints[net].append(yy)
        for net in ('PAD_P','PAD_N','VSS'):endpoints[net].append(active_origin-4)
        if tb is not None:
            for net,yy in tb['links'].items():endpoints[net].append(yy)
            if tb['top_pins']:
                for net in ('RX_P','RX_N'):
                    if net in endpoints:endpoints[net].append(height-.5)   # trunk to the top edge (the discharge macro keeps its access at 438)
            if tb['fs'] is not None:
                for net,yy in tb['fs']['links'].items():endpoints[net].append(yy)
                endpoints['VDD'].append(tb['fs']['vdd_y'][0]+.8)
        if any(not points for points in endpoints.values()):raise ValueError('Unrouted physical net')
        net_spans={net:(min(points)-.5,max(points)+.5) for net,points in endpoints.items()}
    if keep_tracks_of is not None:
        tx={}
        for index,device in enumerate(core_devices):
            for net in device.nodes:tx.setdefault(net,[]).append(placements[index][0])
        for cd in cap_place:
            for net in cd.nodes:tx.setdefault(net,[]).append(140.)
        # pad-side nets (any net of a device touching PAD/RX) keep their canonical x as well, so the pad node
        # parasitics stay those of the canonical allocation; only control/logic nets are repacked.
        padside={n for d in core_devices if signal_ports.intersection(d.nodes) for n in d.nodes}
        tracks,trunk_widths=shared_tracks(nets,keep_tracks_of,net_spans,set(circuit.ports)|(padside&set(keep_tracks_of)),
                                          trunk_width_overrides_um,target_x={n:sum(v)/len(v) for n,v in tx.items()},
                                          quiet=padside&set(keep_tracks_of)-{'VDD','VSS'})
    commands = ['crashbackups stop', f'set ::env(PDKPATH) {PDK}',
                f'path search +{PDK}/libs.ref/gf180mcu_fd_io/mag',
                'load '+circuit.name, 'units microns']
    shapes,cur=[],[None]   # net-tagged rectangles for antenna-diode planning
    def rect(layer, x1,y1,x2,y2):
        commands.extend([f'box values {min(x1,x2):.4f} {min(y1,y2):.4f} {max(x1,x2):.4f} {max(y1,y2):.4f}', f'paint {layer}'])
        shapes.append((layer,min(x1,x2),min(y1,y2),max(x1,x2),max(y1,y2),cur[0]))
    def via(x,y, low, high):
        for metal in range(low, high+1):
            half = .19 if metal == 1 else .22 if metal == 5 else .2
            rect(f'metal{metal}', x-half,y-half,x+half,y+half)
        for metal in range(low, high):
            half = .13 if metal == 1 else .14
            rect(f'via{metal}', x-half,y-half,x+half,y+half)
    def wire(layer,x1,y1,x2,y2,width=None):
        if x1 != x2 and y1 != y2:
            raise ValueError('Manhattan route required')
        half = width/2 if width is not None else (.22 if layer == 'metal5' else .2)
        rect(layer,min(x1,x2)-half,min(y1,y2)-half,max(x1,x2)+half,max(y1,y2)+half)
    keepouts,taps,ant_terms=[],[],[]
    def prim_bbox(cell):
        r=rectangles(work/(cell+'.mag'));allr=[a for k,v in r.items() if k not in ('checkpaint','properties') for a in v]
        return (min(a[0] for a in allr),min(a[1] for a in allr),max(a[2] for a in allr),max(a[3] for a in allr))
    fill_=tb is not None and tb['pad_trunk_fill']
    for net, x in tracks.items():
        if fill_ and net in ('PAD_P','PAD_N'):continue   # drawn by the fill below
        cur[0]=net
        # Widen across the trunk, not past its reserved endpoints.
        rect('metal5',x-trunk_widths[net]/2,net_spans[net][0]-.22,
             x+trunk_widths[net]/2,net_spans[net][1]+.22)
    fill_x={}
    if fill_:   # b7: PAD trunks widened in a staircase into the free 0.44 um slots beside them; the outer edge stays 0.62 um from the next
        # slot's trunk and, where widened, the inner (P-N facing) edge moves in 0.04 um, so the wide parts keep 0.6 um to the other leg (MT.2b)
        for leg,step in (('P',1.),('N',-1.)):
            net='PAD_'+leg;x0_=tracks[net];y0_=net_spans[net][0]-.22;y1_=net_spans[net][1]+.22;cur[0]=net
            others=[(tracks[n],net_spans[n]) for n in tracks if n!=net and trunk_widths[n]==.44]
            s_=x0_;ytop=y1_;steps=[]
            while True:
                s_+=step
                if any(abs(tracks[n]-s_)<.5+trunk_widths[n]/2 for n in tracks if trunk_widths[n]!=.44):break
                lim=min([sp[0]-.22-2.5 for xx,sp in others if abs(xx-s_)<.01 and sp[1]+.22+2.5>y0_]+[ytop])
                if lim-y0_<20. or len(steps)>=5:break   # at most 5 slots (< 30 um wide: MSLOT5.1; P / N alike)
                ytop=lim;steps.append((s_,ytop))
            inner=x0_-step*.18
            if not steps:rect('metal5',x0_-.22,y0_,x0_+.22,y1_);continue
            rect('metal5',x0_-.22,steps[0][1]-1.,x0_+.22,y1_)   # plain trunk above the widened part (1 um overlap)
            for s2,yt in steps:rect('metal5',min(inner,s2+step*.16),y0_,max(inner,s2+step*.16),yt)
            fill_x[leg]=(min(inner,steps[-1][0]+step*.16),max(inner,steps[-1][0]+step*.16))
    for index, device in enumerate(core_devices):
        cx,cy,route_base=placements[index]
        key = kkey(device)
        cell='folded_tail' if device.name in folded_names else keys[key]
        pins=[folded_meta['pins'][n][:2] for n in ('D','G','S','B')] if device.name in folded_names else pinloc[key]
        commands += [f'getcell {cell} child 0 0 parent {cx} {cy}', f'identify X{device.name}']
        bb=prim_bbox(cell);keepouts.append((cx+bb[0],cy+bb[1],cx+bb[2],cy+bb[3]))
        if 'nfet' in device.model:taps.append(keepouts[-1])   # NMOS guard ring = P-substrate tap
        if device.name in pair_of:   # PD46 2-finger pair: strap the outer sources (M2) and the two gate contacts (M1)
            pg=pairgeo[key];(s1x,s1y),(s2x,s2y)=pg['sources'];ys=cy+min(pg['src_top']-1.,s1y+4.)
            cur[0]=device.nodes[2]
            for sx in (s1x,s2x):via(cx+sx,ys,1,2)
            wire('metal2',cx+s1x,ys,cx+s2x,ys)
            cur[0]=device.nodes[1];g0=pg['gate_box']
            rect('metal1',cx+g0[0]-.06,cy+g0[1],cx+g0[2]+.06,cy+g0[3])
        for terminal, ((dx,dy), net) in enumerate(zip(pins,device.nodes)):
            x,y = cx+dx,cy+dy
            cur[0]=net
            mos='fet' in device.model and len(device.nodes)==4
            ant_terms.append((x,y,net,('g' if terminal==1 else 'sd' if terminal in (0,2) else 'x') if mos else 'x',
                              device.w_um*device.l_um*(2 if device.name in pair_of else 1) if mos and terminal==1 else 0.))
            # Distinct local vertical escapes, with a unique M4 row per pin.
            offsets=(-2.5,0.,4.) if len(device.nodes)==3 else (2.5,0.,-2.5,4.)
            escape = cx + offsets[terminal]
            route_y = route_base+terminal*.8
            via(x,y,1,2)
            wire('metal2',x,y,escape,y)
            via(escape,y,2,3)
            wire('metal3',escape,y,escape,route_y)
            via(escape,route_y,3,4)
            wire('metal4',escape,route_y,tracks[net],route_y)
            via(tracks[net],route_y,4,5)
    for cd,(cy,(ytop,ybot)) in cap_place.items():
        key=kkey(cd);cx=cap_x_um;(tx_,ty_),(bx_,by_)=pinloc[key];contact,frame=capgeo[key]
        commands += [f'getcell {keys[key]} child 0 0 parent {cx} {cy}', f'identify X{cd.name}']
        bb=prim_bbox(keys[key]);keepouts.append((cx+bb[0],cy+bb[1],cx+bb[2],cy+bb[3]))
        if not (cy+contact[1]+.3<=ytop<=cy+contact[3]-.3 and cy+frame[1]+.3<=ybot<=cy+frame[3]-.3):raise ValueError('Capacitor route rows miss its plates')
        top,bottom=cd.nodes;xv=cx+bb[0]-3.2   # via4 landing left of the bottom-plate frame
        if xv-.3<146.:raise ValueError('Capacitor strip too close to the trunk bank')
        cur[0]=top
        wire('metal5',xv,ytop,cx+contact[0]+1.,ytop,width=.6)   # onto the top-plate contact (M5)
        via(xv,ytop,4,5);wire('metal4',tracks[top],ytop,xv,ytop);via(tracks[top],ytop,4,5)
        cur[0]=bottom
        wire('metal4',tracks[bottom],ybot,cx+frame[2],ybot);via(tracks[bottom],ybot,4,5)
        ant_terms.append((tracks[top],ytop,top,'x',0.));ant_terms.append((tracks[bottom],ybot,bottom,'x',0.))
    cur[0]=None
    tb_info=None
    if tb is not None and tb['term_block']:
        tb_info=_usb_term_block(tb,circuit,tb_dev,keys,work,tracks,rect,via,commands,keepouts,taps,ant_terms,cur,escape_width,bond_pitch)
    # Keep protection directly behind each bond. M1 local ground wiring and
    # M2 signal wiring fit below the restored M3..M5 rail module. The explicit
    # ground landing is an intended ring join, requiring assembled net checks.
    ground_landings=[]
    for leg,offset in [('P',0.),('N',bond_pitch)]:
        units=[d for d in protection_devices if d.nodes[0]=='PAD_'+leg]
        if len(units)!=(0 if external_primary else 2): raise ValueError('Unexpected near-bond protection unit count')
        for unit,device in enumerate(units):
            cx,cy=offset+25.+25.*unit,90.
            if device.nodes[1:]!=('VSS','VSS','VSS'):
                raise ValueError('Near-bond route requires grounded protection gate/source/body')
            key=(device.model,device.w_um,device.l_um)
            commands += [f'getcell {keys[key]} child 0 0 parent {cx} {cy}',f'identify X{device.name}']
            pins=pinloc[key]
            dx,dy=pins[0]
            via(cx+dx,cy+dy,1,2)
            wire('metal2',cx+dx,cy+dy,offset+37.5,cy+dy,width=1.)
            for index in (1,2,3):
                dx,dy=pins[index];escape=cx+7. if index==3 else cx-3.
                wire('metal1',cx+dx,cy+dy,escape,cy+dy,width=2. if index==1 else .5)
                wire('metal1',escape,cy+dy,escape,76.,width=.5)
        if tb is None:wire('metal1',offset+10,76,offset+60,76,width=2.)   # usb_term_block: the pad-site primaries use this band
        via(offset+10,76,1,2)
        wire('metal2',offset+10,76,offset+10,active_origin-20,width=2.)
        for dx in (-.6,0,.6):
            for dy in (-.6,0,.6):via(offset+10+dx,78.305+dy,2,5 if tb is None else 3)   # usb_term_block: ring stack Metal2/Via2/Metal3 only
        for metal in ('metal2','metal3','metal4','metal5') if tb is None else ('metal2','metal3'):
            rect(metal,offset+9,77.305,offset+11,79.305)
        ground_landings.append([offset+9,77.305,offset+11,79.305])
        via(offset+10,active_origin-20,2,4)
        wire('metal4',offset+10,active_origin-20,tracks['VSS'],active_origin-20,width=1.)
        via(tracks['VSS'],active_origin-20,4,5)
        rect('metal5',tracks['VSS']-trunk_widths['VSS']/2,active_origin-20-.22,
             tracks['VSS']+trunk_widths['VSS']/2,active_origin-4+.22)
    for leg, cx, bond_y in [('P',37.5,active_origin-bond_y_offsets_um[0]),('N',37.5+bond_pitch,active_origin-bond_y_offsets_um[1])]:
        # Preserve the actual library bond opening and via/metal construction.
        # The reference 75um cell places Bondpad_5LM at x=5.5um, putting
        # its 60um glass opening at [7.5,67.5] x [2,62]. Do not redraw it
        # from LEF or copy the reference cell's signal-to-supply ESD diode.
        commands += [f'getcell Bondpad_5LM child 0 0 parent {cx-32} 0',
                     f'identify BOND_{leg}']
        # The native rail module occupies M3..M5 across the pad row. Keep
        # the signal in its own site's M2 corridor until it reaches the core.
        if tb is not None and tb['neck_hi'] is not None:   # usb_term_block neck_hi: narrower neck above y_split
            ys_,wh_=tb['neck_hi'];wire('metal2',cx,62,cx,ys_,width=escape_width);wire('metal2',cx,ys_,cx,bond_y,width=wh_)
        else:wire('metal2',cx,62,cx,bond_y,width=escape_width)
        for dx in (-.6,0,.6):
            for dy in (-.6,0,.6):via(cx+dx,bond_y+dy,2,4)
        for metal in ('metal2','metal3','metal4'):
            rect(metal,cx-1.,bond_y-1.,cx+1.,bond_y+1.)
        wire('metal4',cx,bond_y,tracks['PAD_'+leg],bond_y,width=6.)
        via(tracks['PAD_'+leg],bond_y,4,5)
        if leg in fill_x:   # b7 pad_trunk_fill: the transverse lands on the widened trunk through a Metal4/Metal5 plate and a via4 array
            fx1,fx2=fill_x[leg];cur[0]='PAD_'+leg   # (b6: one via4 + 0.44 um Metal5 here, 4.5 / 15 ohm typ / high in the HS path)
            rect('metal4',fx1,bond_y-3.,fx2,bond_y+3.);rect('metal5',fx1,bond_y-2.8,fx2,net_spans['PAD_'+leg][0]+.5)
            yv=bond_y-2.3
            while yv<=min(bond_y+2.3,net_spans['PAD_'+leg][0])+1e-9:
                xv=fx1+.5
                while xv<=fx2-.5+1e-9:
                    if abs(xv-tracks['PAD_'+leg])>.8 or abs(yv-bond_y)>.8:via(round(xv,3),round(yv,3),4,5)
                    xv+=.8
                yv+=.8
        if leg not in fill_x:wire('metal5',tracks['PAD_'+leg],bond_y,tracks['PAD_'+leg],active_origin-4,width=trunk_widths['PAD_'+leg])   # (fill: the plate replaces it)
    top_pins={}
    for index, port in enumerate(circuit.ports,1):
        x = tracks[port];y=port_heights[port]
        if tb is not None and tb['top_pins'] and port not in ('PAD_P','PAD_N'):   # ASM-2: Metal4 pin on the top edge
            y=height if port_top_um is None else port_top_um;hw=max(.2,trunk_widths[port]/2);cur[0]=port   # boundary-port cells: flush with the trunk tops
            rect('metal4',x-hw,y-1.,x+hw,y+.72)   # flush with the cell top (the Metal5 trunks end at height + 0.72)
            if port=='TERM_VCM':   # carries the termination current: Metal4 strip into the
                rect('metal4',x-.45,tb['bar'][1]-1.,x+1.9,y+.72)              # TERM_VCM Metal3/4 bar (no single via4 in series)
            nv=max(1,int((2*hw-.44)/.6)+1)
            for i in range(nv):
                xv_=round(x-(nv-1)*.3+i*.6,3)
                if port=='VSS' and abs(xv_-x)<.65:continue   # the receiver-discharge VSS access stack lands at (x, height) (V4.2a)
                via(xv_,y-.5,4,5)
            cur[0]=None;top_pins[port]=[round(x-hw,3),round(y-1.,3),round(x+hw,3),round(y+.72,3)]
            commands += [f'box values {x-hw} {y-1.} {x+hw} {y+.72}',
                         f'label {port} FreeSans 0.3 0 0 0 c metal4', f'port make {index}']
            continue
        commands += [f'box values {x-.2} {y-.5} {x+.2} {y}',
                     f'label {port} FreeSans 0.3 0 0 0 c metal5', f'port make {index}']
    for net in sorted(set(nets)-set(circuit.ports)):
        x=tracks[net];y=net_spans[net][1]-.25 if bounded_routes else height
        commands += [f'box values {x-.2} {y-.5} {x+.2} {y}',
                     f'label {net} FreeSans 0.3 0 0 0 c metal5']
    # Antenna diodes (KLayout ANT.16): gate-only partial nets with long M2-M5 get an N+/Psub diode
    # under their own M3-M5 trunk; added to the schematic below so LVS still matches.
    import antenna_diodes as ad
    ant_req=ad.requests_from_shapes(shapes,ant_terms)
    ant_cmds,ant_diodes=ad.plan(ant_req,[s[:5] for s in shapes],keepouts,taps=taps)
    commands += ant_cmds
    commands += ['select top cell', f'flatten {flat}', f'load {flat}', 'save',
                 'select top cell', 'drc on', 'drc check', 'drc catchup', 'set f [open drc-count.txt w]',
                 'puts $f [drc list count total]', 'close $f',
                 'set f [open drc-details.txt w]', 'puts $f [drc listall why]', 'close $f',
                 'extract all', f'gds write {flat}.gds', 'quit -noprompt']
    (work/'layout.tcl').write_text('\n'.join(commands)+'\n')
    sch=circuit.spice();ant_lines=ad.spice_lines(ant_diodes)
    if ant_lines:
        k=sch.index(f'.subckt {circuit.name} ');e=sch.index('.ends',k)
        sch=sch[:e]+'\n'.join(ant_lines)+'\n'+sch[e:]
    (work/(circuit.name+'.spice')).write_text(sch)
    magic(work,'layout.tcl')
    from gds_markers import repair as repair_gds_markers
    marker_export=repair_gds_markers(work,flat)
    # Preserve the physical extraction and GDS even if the stock converter
    # crashes. The independent physical-record export never reads schematics.
    (work/'stock-export.tcl').write_text(f'load {flat}\next2spice lvs\next2spice\nquit -noprompt\n')
    stock=magic(work,'stock-export.tcl',allow_failure=True)
    report = dict(status='generated_candidate_requires_connectivity_and_rule_review',antenna_diodes=ant_diodes,
                  family=family,flat_cell=flat,marker_export=marker_export,serial_tail_units=serial_tail_units,folded_tail_layout=folded_meta,fs_high_width_um=fs_high_width_um,fs_series_geometry_um=fs_series_geometry_um,
                  bond_template=dict(cell='Bondpad_5LM',source='gf180mcu_fd_io',
                                     reference_parent='5LM_METAL_RAIL_PAD_60',
                                     reference_offset_um=[5.5,0],opening_um=[60,60],
                                     scope='Native bond geometry only; ring rails and provider placement remain open.'),
                  stock_export_returncode=stock.returncode,
                  device_count=len(circuit.devices), net_count=len(nets),
                  requires_attached_primary_protection=external_primary,
                  pad_transverse_width_um=6.,pad_trunk_width_um=trunk_widths["PAD_P"],
                  pad_trunk_widths_um={leg:trunk_widths["PAD_"+leg] for leg in ("P","N")},
                  net_track_x_um=tracks,net_trunk_widths_um=trunk_widths,
                  bounded_internal_routes=bounded_routes,net_trunk_spans_um=net_spans,port_heights_um=port_heights,
                  candidate_size_um=[candidate_width,height],columns=columns,port_top_um=port_top_um,bond_y_offsets_um=list(bond_y_offsets_um), reference_pair_size_um=[candidate_width,350],
                  bond_pitch_um=bond_pitch,escape_layer='metal2',escape_width_um=escape_width,active_origin_um=active_origin,core_clearance_depth_um=clearance,reference_sites=[p['site'] for p in circuit.requirements['pads']],
                  fits_reference_height=height<=350,
                  area_um2=candidate_width*height,
                  near_bond_ground_landings_um=ground_landings,
                  protection_device_centers_y_um=90.,
                  allocation_regions_um=[[0,0,75,104],[bond_pitch,0,candidate_width,104],
                    [8.5,104,11.5,active_origin],[8.5+bond_pitch,104,11.5+bond_pitch,active_origin],
                    [37.5-escape_width/2-.2,76,37.5+escape_width/2+.2,max(active_origin,active_origin-4+escape_width/2)],
                    [37.5+bond_pitch-escape_width/2-.2,76,37.5+bond_pitch+escape_width/2+.2,max(active_origin,active_origin-4+escape_width/2)],
                    [0,active_origin-22,core_reservation_width,height+1],[core_reservation_width,active_origin-22,candidate_width,active_origin]]
                    +[[core_reservation_width,cy-16.,cap_x_um+16.,cy+16.] for cd,(cy,_) in cap_place.items()],   # PD46 MIM strip (plates + route stubs)
                  capacitors=[dict(name=cd.name,nodes=list(cd.nodes),centre_um=[cap_x_um,cy],route_y_um=dict(top=ys[0],bottom=ys[1])) for cd,(cy,ys) in cap_place.items()],
                  paired_devices={a:b.name for a,b in pair_of.items()},
                  **({'usb_term_block':dict(options=tb,info=tb_info,top_pins_um=top_pins)} if tb is not None else {}),
                  area_ceiling_um2=circuit.requirements['area_ceiling_um2'],
                  fits_assigned_area=candidate_width*height<=circuit.requirements['area_ceiling_um2'],
                  image_id=IMAGE,
                  sources_sha256={str(p.relative_to(PROJECT)):hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in (Path(__file__),Path(__file__).with_name('gds_markers.py'),placement_source,Path(__file__).with_name('circuits.py'),
                                            Path(__file__).with_name('design.py'),Path(__file__).with_name('wired_receive.py'),Path(__file__).with_name('folded_tail.py'),
                                            PROJECT/'spec/analog-architecture.json',PROJECT/'spec/contract.json',layout_spec)},
                  drc_count=(work/'drc-count.txt').read_text().strip(),
                  pcell_terminal_coordinates={keys[k]:v for k,v in pinloc.items()},
                  limitations=circuit.limitations+['Provider ring metal rails not yet integrated.'])
    (work/'layout-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--family',choices=FAMILIES,default='wired_transmit')
    parser.add_argument('--external-primary',action='store_true',help='Build TX base for an attached primary macro; incomplete standalone pad')
    parser.add_argument("--serial-tail-units",type=int)
    parser.add_argument("--folded-tails",action="store_true")
    parser.add_argument('--fs-high-width-um',type=float,default=20.)
    parser.add_argument('--fs-series-geometry-um',type=float,nargs=2)
    args=parser.parse_args()
    generate(args.output_dir.resolve(),args.family,external_primary=args.external_primary,serial_tail_units=args.serial_tail_units,folded_tails=args.folded_tails,fs_high_width_um=args.fs_high_width_um,fs_series_geometry_um=args.fs_series_geometry_um)
