#!/usr/bin/env python3
"""mkmodel_band.py <t2 model> <corner> <out> <netres json> : t2 lumped model + the t3/t7 band (rftx_band.py), R from netres of the
band GDS: bond->band up anodes (bond|bup), bond->band down cathodes (bond|bdn), band cathodes->clamp drains (ESD_RAIL bcath|drn),
band VSS->ring (VSS_NET ring|bandv), clamp VSS->ring (VSS_NET ring|clampsrc, replaces the t2 land|clampsrc), + the extra band wiring C
per pad (railcap t7 - t2: P 194.6 fF, N 201.5 fF) to VSS at the bond node. Diode counts from argv[5:7] (n_up n_dn per leg)."""
import sys, re, json
src, corner, out, resf, nu, nd = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]), int(sys.argv[6])
R = lambda net, pair: json.load(open(resf))['nets'][net]['corners'][corner]['resistance_ohm'][pair]
s = open(src).read()
s = re.sub(r'^RNET VSS__net VSS .*$', f'RNET VSS__net VSS {R("VSS_NET", "ring|clampsrc"):.4f}', s, flags=re.M)
add = [f'RXBE ESD_RAIL__b ESD_RAIL {R("ESD_RAIL", "bcath|drn"):.4f}', f'RXBV VSS__b VSS {R("VSS_NET", "ring|bandv"):.4f}']
for p, cx in (('P', 194.6), ('N', 201.5)):
    add += [f'RXBU{p} PAD_{p} PAD_{p}__bu {R("PAD_"+p, "bond|bup"):.4f}', f'RXBD{p} PAD_{p} PAD_{p}__bd {R("PAD_"+p, "bond|bdn"):.4f}', f'CBX{p} PAD_{p} VSS {cx}f']
    add += [f'DBU{p}{i} PAD_{p}__bu ESD_RAIL__b diode_pd2nw_06v0 pj=51.8u area=22.5p' for i in range(nu)]
    add += [f'DBD{p}{i} VSS__b PAD_{p}__bd diode_nd2ps_06v0 pj=51.8u area=22.5p' for i in range(nd)]
open(out, 'w').write(f'* {out}: {src} + rftx_band ({nu} up / {nd} down per leg), R from {resf} ({corner})\n' + s.replace('.ends physical', '\n'.join(add) + '\n.ends physical'))
