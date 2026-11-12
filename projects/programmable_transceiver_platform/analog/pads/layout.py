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

def generate(work,family='wired_transmit', *, external_primary=False, serial_tail_units=None, folded_tails=False, fs_high_width_um=20., fs_series_geometry_um=None, trunk_width_overrides_um=None,
             columns=7, port_top_um=None, bond_y_offsets_um=(12.,4.), keep_tracks_of=None, pair_prefixes=(), cap_x_um=166.,
             cap_min_y_um=560., circuit_override=None):
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
            if isinstance(d,Capacitor) or 'fet' not in d.model or not d.name.startswith(tuple(pair_prefixes)):continue
            k=(d.model,d.w_um,d.l_um,d.nodes)
            if k in pend:pair_of[pend.pop(k).name]=d
            else:pend[k]=d
    paired={d.name for d in pair_of.values()}
    def kkey(d):return (d.model,d.w_um,d.l_um)+((2,) if d.name in pair_of else ())
    kinds = sorted({kkey(d) for d in circuit.devices if d.name not in paired}, key=str)
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
        commands += ['units internal', f'set cell [magic::gencell_makecell gf180mcu::{model} w {width} l {length} nf {kind[3] if len(kind)>3 else 1} guard 1 topc 0 botc 1 full_metal 1 gate_to_polycont 0.6 gate_extension 0.8 diff_gate_space 0.3]',
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
        elif len(k)>3:pinloc[k],pairgeo[k]=pair_terminals(work/(name+'.mag'))
        else:pinloc[k]=terminals(work/(name+'.mag'))
    nets = sorted({n for d in circuit.devices for n in d.nodes})
    pitch, row_height = 21., 26.
    if not 1<=columns<=7:raise ValueError('M4 route rows support at most 7 columns per 26 um row')
    folded_names=set();folded_meta=None
    core_reservation_width = 143. if family=="wired_receive_usb" else 150.
    core_devices = [d for d in circuit.devices if not d.name.startswith("ESD_") and d.name not in paired and not isinstance(d,Capacitor)]
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
    for net, x in tracks.items():
        cur[0]=net
        # Widen across the trunk, not past its reserved endpoints.
        rect('metal5',x-trunk_widths[net]/2,net_spans[net][0]-.22,
             x+trunk_widths[net]/2,net_spans[net][1]+.22)
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
        wire('metal1',offset+10,76,offset+60,76,width=2.)
        via(offset+10,76,1,2)
        wire('metal2',offset+10,76,offset+10,active_origin-20,width=2.)
        for dx in (-.6,0,.6):
            for dy in (-.6,0,.6):via(offset+10+dx,78.305+dy,2,5)
        for metal in ('metal2','metal3','metal4','metal5'):
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
        wire('metal2',cx,62,cx,bond_y,width=escape_width)
        for dx in (-.6,0,.6):
            for dy in (-.6,0,.6):via(cx+dx,bond_y+dy,2,4)
        for metal in ('metal2','metal3','metal4'):
            rect(metal,cx-1.,bond_y-1.,cx+1.,bond_y+1.)
        wire('metal4',cx,bond_y,tracks['PAD_'+leg],bond_y,width=6.)
        via(tracks['PAD_'+leg],bond_y,4,5)
        wire('metal5',tracks['PAD_'+leg],bond_y,tracks['PAD_'+leg],active_origin-4,width=trunk_widths['PAD_'+leg])
    for index, port in enumerate(circuit.ports,1):
        x = tracks[port];y=port_heights[port]
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
