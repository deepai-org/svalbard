#!/usr/bin/env python3
"""Regenerate the full-chip SPICE binding (stage 6 of the maintained assembly flow) from the CURRENT block
netlists, on the v5 run2 instance list (last full GDS assembly; v6 is outline-only and has no netlist).
pll_host dropped and pll_tx -> pt_pll_ring_core per consolidation X1/X4. Read-only on design files."""
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flow'))
import inventory as inv, netlist
work = os.path.dirname(os.path.abspath(__file__))
fp = json.load(open(work+'/floorplan.json'))
fp['placed'] = [p for p in fp['placed'] if p['name'] != 'pll_host']
for p in fp['placed']:
    if p['name'] == 'pll_tx': p['master'] = 'pll_ring_core'
have = (inv.ROOT/inv.MASTERS['wrx_cap'][0]).exists()
res = netlist.build(work, fp, have)
print(json.dumps(res, indent=1)[:3000])
