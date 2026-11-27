#!/usr/bin/env python3
"""Connectivity gate of an assembly run (KH-1..KH-3, 2026-11-26): faults that DRC and LVS by name do not see.

  check_conn.py <rf|wired>        (run dir: ASM_RUN)  -> <run>/check_conn.json; exit 1 on any failure

Fails when
  macro    a pin of the digital macro's LEF (pins of the run's lef/pt_digital_macro.lef) that is an input, or that the
           conn / chips/provider_io binds to a net, is on no routed net of route/routed.def (pins the route stage took off
           their net, route/unreachable.txt, count as unwired); c_* outputs with no consumer on this chip are listed only;
  pad      a core pin of a provider cell (chips/provider_io: signal or VDD / VSS tie; 'NC' pins of the model excepted) is
           on no routed net;
  single   place.json single_pin_nets holds a net that is not a chip port (bond net);
  lvs      lvs/chip/lvs.json is missing, or its instances_in_ref_not_bound is not empty (skipped with --no-lvs).
"""
import json, os, re, sys, collections
A = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, A)
import common as C

chip = sys.argv[1]; RUN = os.environ['ASM_RUN']; nolvs = '--no-lvs' in sys.argv
if not C.KH_CONN: print(f'check_conn {chip}: skipped (KH_CONN=1 not set)'); sys.exit(0)
inst, ports, masters = C.load(chip)
F = collections.OrderedDict((k, []) for k in ('macro', 'pad', 'single', 'lvs')); info = {}

# routed nets: (component, pin) on a net that has wiring
txt = open(RUN+'/route/routed.def').read()
nets = txt[txt.index('\nNETS '):txt.index('\nEND NETS')]
wired = set()
for blk in nets.split(';'):
    if '+ ROUTED' not in blk and '+ FIXED' not in blk: continue
    for c, p in re.findall(r'\(\s*(\S+)\s+(\S+)\s*\)', blk.split('+')[0]): wired.add((c, p.replace('\\', '')))
unreach = {l.split()[0] for l in open(RUN+'/route/unreachable.txt') if l.strip()} if os.path.exists(RUN+'/route/unreachable.txt') else set()
for t_ in json.load(open(RUN+'/place.json')).get('io_direct_ties', []): wired.add((t_['inst'], t_['pin']))     # drawn ties (common.PAD_DIRECT_TIE)
info['routed_pins'] = len(wired); info['unreachable_pins'] = len(unreach)

# macro
lef = open(RUN+'/lef/pt_digital_macro.lef').read()
dpins = inst['digital']['pins']; nc_out = []
for name, body in re.findall(r'\n\s*PIN (\S+)(.*?)\n\s*END \1', lef, re.S):
    if re.search(r'USE (POWER|GROUND)', body): continue
    inp = 'DIRECTION INPUT' in body
    net = dpins.get(name, ('', None))[1]
    if net is None: F['macro'].append(f'digital.{name}: LEF pin not in the macro pin list (conn + provider_io.macro_ctl)'); continue
    if net == '-' and not inp: nc_out.append(name); continue
    if net == '-' or ('digital', name) not in wired:
        F['macro'].append(f"digital.{name} ({'input' if inp else 'output'}, net {net}): no routed wire")
info['macro_outputs_without_consumer'] = len(nc_out)

# provider pads
nsite = 0
for r in C.provider_sites(inst, C.bond(chip)):
    io = r['name']
    for p in C.PIO.CORE[r['cell']]:
        n = r['pins'][p]
        if n == 'NC': continue
        nsite += 1
        if (io, p) not in wired: F['pad'].append(f"{io}.{p} ({r['cell']}, {n}): no routed wire")
info['pad_core_pins_checked'] = nsite

# single-pin nets
pl = json.load(open(RUN+'/place.json'))
F['single'] = [f'{n}: single-pin net (not a chip port)' for n in pl['single_pin_nets'] if n not in ports]
info['single_pin_port_nets'] = sum(1 for n in pl['single_pin_nets'] if n in ports)

# lvs binding
if not nolvs:
    lp = RUN+'/lvs/chip/lvs.json'
    if not os.path.exists(lp): F['lvs'].append('lvs/chip/lvs.json missing (run the lvs stage)')
    else:
        lv = json.load(open(lp))
        if 'instances_in_ref_not_bound' not in lv: F['lvs'].append('lvs.json has no by-name result (manifest not used)')
        F['lvs'] += [f'{i}: reference instance not bound to a layout cell' for i in lv.get('instances_in_ref_not_bound', [])]

res = dict(chip=chip, run=RUN, pass_=not any(F.values()), counts={k: len(v) for k, v in F.items()}, info=info, failures=F)
json.dump(res, open(RUN+'/check_conn.json', 'w'), indent=1)
print(f"check_conn {chip}: {'PASS' if res['pass_'] else 'FAIL'} {res['counts']} {info}")
for k, v in F.items():
    for x in v[:8]: print('  ', k, x)
sys.exit(0 if res['pass_'] else 1)
