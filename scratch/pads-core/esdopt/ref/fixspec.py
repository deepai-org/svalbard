#!/usr/bin/env python3
"""fixspec_usb.py <spec.json> [site]: TERM_VCM pin = its port label (top edge); with `site`: the four pad-site islands
(SVSS_x: nd2ps anodes / substrate taps -> Metal3 landing on ring DVSS; SVDD_x: pd2nw cathodes -> Metal3 landings on ring DVDD),
traced inside the site window only (the site VSS bar also joins the cell VSS through the Metal1 bridge, outside the window)."""
import json, sys
s = json.load(open(sys.argv[1]))
if len(sys.argv) > 2 and sys.argv[2] == 'site':
    for x, ox in (('P', 0.), ('N', 211.)):
        s['nets'].append(dict(name=f'SVSS_{x}', seed=['M3', ox + 58., 92.], clip=[ox + 43., 62., ox + 75., 150.], max_step=0.5, min_cuts=2, min_width=1.0,
                              terminals=[dict(name='pin', layer='M3', box=[ox + 44., 82.5, ox + 72., 117.]), dict(auto_contacts='c')],
                              groups=dict(far=dict(prefix='c')), pairs=[['pin', 'far']]))
        s['nets'].append(dict(name=f'SVDD_{x}', seed=['M3', ox + 58., 121.5], clip=[ox + 43., 62., ox + 75., 150.], max_step=0.5, min_cuts=2, min_width=1.0,
                              terminals=[dict(name='pin', layer='M3', box=[ox + 44., 118., ox + 72., 149.]), dict(auto_contacts='c')],
                              groups=dict(far=dict(prefix='c')), pairs=[['pin', 'far']]))
json.dump(s, open(sys.argv[1], 'w'), indent=1)
