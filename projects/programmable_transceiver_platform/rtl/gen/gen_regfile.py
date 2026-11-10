#!/usr/bin/env python3
"""Generate the control register map, register file and bench headers.

Inputs:  spec/analog-architecture.json:control_fields (analog boundary fields)
         spec/debug-controls.json (island, debug, fallback and consolidation controls,
         illegal-combination rules, break-before-make and fault-forcing lists)
Outputs: spec/register-map.json, spec/register-map.md, rtl/pt_regfile.sv,
         rtl/pt_regmap_defs.svh, rtl/gen/pt_regmap.h, rtl/gen/pt_regmap.py

    python3 rtl/gen/gen_regfile.py           # write outputs
    python3 rtl/gen/gen_regfile.py --check   # fail if any output is stale
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

GEN = Path(__file__).resolve().parent
P = GEN.parents[1]
RUNTIME_SRC = (GEN / 'regmap_runtime.py').read_text()


class SpecError(Exception):
    pass


def hexaddr(text):
    return int(text, 16)


def sv_name(full):
    group, field = full.rsplit('.', 1)
    return group.replace('.', '_') + '__' + field


def encode(f, value):
    if f['values'] is not None:
        if value not in f['values']:
            raise SpecError(f"{f['name']}: unknown value {value!r}")
        return f['values'].index(value)
    if not isinstance(value, int):
        raise SpecError(f"{f['name']}: numeric field needs an integer, got {value!r}")
    return value


def build_model():
    arch = json.loads((P / 'spec/analog-architecture.json').read_text())
    dbg = json.loads((P / 'spec/debug-controls.json').read_text())
    readiness = json.loads((P / 'spec/tapeout-readiness.json').read_text())
    islands = {k: v['bit'] for k, v in sorted(dbg['islands'].items(), key=lambda kv: kv[1]['bit'])}
    if sorted(islands.values()) != list(range(len(islands))):
        raise SpecError('island bits must be dense from 0')
    atb_nodes = dbg['atb_nodes']
    if [n['code'] for n in atb_nodes] != list(range(1, len(atb_nodes) + 1)):
        raise SpecError('ATB node codes must be 1..N in order')
    for n in atb_nodes:
        if n['island'] is not None and n['island'] not in islands:
            raise SpecError(f"ATB node {n['name']}: unknown island")
        if n['force'] not in ('sense_only', 'override', 'allowed'):
            raise SpecError(f"ATB node {n['name']}: bad force policy")

    fields, groups = [], []

    def add_group(gname, g, kind):
        block = gname.split('.')[0]
        if kind == 'analog':
            if block not in dbg['block_islands']:
                raise SpecError(f'{gname}: block {block} has no island assignment')
            group_islands, group_live = dbg['block_islands'][block], False
        else:
            group_islands, group_live = g.get('islands', []), g.get('live', False)
        members = []
        for fname, s in g['fields'].items():
            full = f'{gname}.{fname}'
            f = dict(name=full, group=gname, field=fname, kind=kind, bits=s['bits'], values=s.get('values'),
                     minimum=None, maximum=None, allowed=None, islands=list(s.get('islands', group_islands)),
                     live=bool(s.get('live', group_live)), unit=s.get('unit'),
                     meaning=s.get('meaning') or s.get('description'), update=g.get('update'),
                     split=s['bits'] > 16, sv=sv_name(full), bus=None, bus_lsb=None, chunks=[],
                     atb_bus=s.get('atb_bus'), gate_and=s.get('gate_and'), decode=s.get('decode'))
            for i in f['islands']:
                if i not in islands:
                    raise SpecError(f'{full}: unknown island {i}')
            if f['values'] is not None:
                if len(f['values']) > (1 << f['bits']):
                    raise SpecError(f'{full}: {len(f["values"])} values do not fit {f["bits"]} bits')
                forbidden = s.get('forbidden', [])
                f['allowed'] = [i for i, v in enumerate(f['values']) if v not in forbidden]
            else:
                if 'minimum' not in s or 'maximum' not in s:
                    raise SpecError(f'{full}: numeric field needs minimum/maximum')
                f['minimum'], f['maximum'] = s['minimum'], s['maximum']
                if f['maximum'] >= (1 << f['bits']) or f['minimum'] > f['maximum']:
                    raise SpecError(f'{full}: range does not fit')
            if f['atb_bus'] is not None:
                if f['maximum'] != len(atb_nodes):
                    raise SpecError(f'{full}: maximum must equal the ATB node count')
                tapped = [n for n in atb_nodes if n.get('hardware', True)]
                if f['atb_bus'] == 0:
                    f['allowed'] = [0] + [n['code'] for n in tapped if n['force'] != 'sense_only']
                elif len(tapped) != len(atb_nodes):
                    f['allowed'] = [0] + [n['code'] for n in tapped]
            f['default'] = encode(f, s['default'])
            fields.append(f)
            members.append(f)
        groups.append(dict(name=gname, kind=kind, fields=members, description=g.get('description'), base=g.get('base'),
                           update=g.get('update'), fallback_routes=g.get('fallback_routes', [])))

    for gname, g in dbg['controls'].items():
        add_group(gname, g, 'debug')
    for gname, g in arch['control_fields'].items():
        add_group(gname, g, 'analog')
    by_name = {f['name']: f for f in fields}
    if len(by_name) != len(fields):
        raise SpecError('duplicate field names')
    for need in ['debug.island_power.' + i for i in islands] + ['debug.pgood_override.' + i for i in islands]:
        if need not in by_name:
            raise SpecError(f'missing {need}')

    # Register allocation: each group starts a new register; fields never straddle
    # registers except fields wider than 16 bits, which take dedicated registers.
    policy = dbg['address_policy']
    registers = []

    def allocate(kind, base, limit):
        addr = base
        for g in (g for g in groups if g['kind'] == kind):
            cur = None
            if g.get('base') is not None:
                saved, addr = addr, hexaddr(g['base'])
            g['registers'] = []
            for f in g['fields']:
                if f['split']:
                    for i in range((f['bits'] + 15) // 16):
                        width = min(16, f['bits'] - 16 * i)
                        reg = dict(addr=addr, group=g['name'], kind=kind, chunks=[[f['name'], 16 * i, width, 0]], used=width)
                        registers.append(reg)
                        g['registers'].append(addr)
                        addr += 1
                    cur = None
                    continue
                if cur is None or cur['used'] + f['bits'] > 16:
                    cur = dict(addr=addr, group=g['name'], kind=kind, chunks=[], used=0)
                    registers.append(cur)
                    g['registers'].append(addr)
                    addr += 1
                cur['chunks'].append([f['name'], 0, f['bits'], cur['used']])
                cur['used'] += f['bits']
            if g.get('base') is not None:
                addr = saved
        if addr - 1 > limit:
            raise SpecError(f'{kind} registers overflow 0x{limit:02X} (need a page register)')
        return addr - 1

    last_debug = allocate('debug', hexaddr(policy['debug_base']), hexaddr(policy['debug_limit']))
    # Read-only status registers follow the debug groups.
    status_fields, status_regs = [], []
    addr = hexaddr(policy['status_base']) if 'status_base' in policy else last_debug + 1
    if addr <= last_debug:
        raise SpecError('debug groups overlap the status base')
    for gname, g in dbg.get('status_registers', {}).get('groups', {}).items():
        cur = None
        if g.get('reserved_registers'):
            if g['fields']:
                raise SpecError(f'{gname}: a reserved status slot has no fields')
            addr += g['reserved_registers']
            continue
        for fname, sf in g['fields'].items():
            if sf['bits'] > 16 or sf.get('encoding', 'binary') not in ('binary', 'gray'):
                raise SpecError(f'{gname}.{fname}: status fields are <=16 bits, binary or gray')
            if cur is None or cur['used'] + sf['bits'] > 16:
                cur = dict(addr=addr, group=gname, kind='status', chunks=[], used=0)
                status_regs.append(cur)
                addr += 1
            name = f'{gname}.{fname}'
            status_fields.append(dict(name=name, group=gname, field=fname, bits=sf['bits'], port=sf['port'],
                                      reserved=bool(g.get('reserved', False)),
                                      encoding=sf.get('encoding', 'binary'), meaning=sf.get('meaning'),
                                      addr=cur['addr'], reg_lsb=cur['used']))
            cur['chunks'].append([name, 0, sf['bits'], cur['used']])
            cur['used'] += sf['bits']
    for r in status_regs:
        del r['used']
    if status_regs and 'status_limit' not in policy:
        last_debug = addr - 1
    elif status_regs and addr - 1 > hexaddr(policy['status_limit']):
        raise SpecError('status registers overflow the status block')
        if last_debug > hexaddr(policy.get('status_limit', policy['debug_limit'])):
            raise SpecError(f'status registers overflow the debug range: last 0x{last_debug:02X}, {[(hex(r["addr"]), r["chunks"]) for r in status_regs]}')
    last_analog = allocate('analog', hexaddr(policy['analog_base']), hexaddr(policy['analog_limit']))
    used = [r['addr'] for r in registers] + [r['addr'] for r in status_regs]
    if len(used) != len(set(used)) or min(used) < hexaddr(policy['debug_base']):
        raise SpecError('register addresses overlap or enter the system/legacy space')

    # Hardware trim (pass-2 P2-2): addresses stay; storage and outputs shrink to the bits
    # that drive real ports. Dropped fields read zero and ignore writes.
    trim = dbg.get('hardware_trim', {})
    for name, t in trim.get('forbidden', {}).items():
        f = by_name.get(name)
        if f is None or f['values'] is None:
            raise SpecError(f'hardware_trim.forbidden: {name} is not an enum field')
        f['allowed'] = [i for i in f['allowed'] if f['values'][i] not in t['values']]
        f['trim'] = dict(forbidden=t['values'], source=t['source'], reason=t['reason'])
    for f in fields:
        f['store'] = [f['bits'] - 1, 0]
        f.setdefault('trim', None)
    for name, t in trim.get('fields', {}).items():
        f = by_name.get(name)
        if f is None:
            raise SpecError(f'hardware_trim: unknown field {name}')
        f['trim'] = dict(keep=t['keep'], source=t['source'], reason=t['reason'])
        f['declared_default'] = f['default']
        if t['keep'] is None:
            f['store'] = None
        else:
            hi, lo = t['keep']
            if not (0 <= lo <= hi < f['bits']) or f['values'] is not None or f['minimum'] != 0 or \
                    f['maximum'] != (1 << f['bits']) - 1:
                raise SpecError(f'hardware_trim: {name} slice needs a full-range numeric field')
            f['store'] = [hi, lo]
    for f in fields:
        if f['store'] is None:
            f['store_mask'] = 0
        else:
            hi, lo = f['store']
            f['store_mask'] = ((1 << (hi - lo + 1)) - 1) << lo
        f['default'] &= f['store_mask']
    for reg in registers:
        reg['writable_mask'] = sum(((1 << w) - 1) << rl for _, _, w, rl in reg['chunks'])
        del reg['used']
        for name, field_lsb, width, reg_lsb in reg['chunks']:
            by_name[name]['chunks'].append(dict(addr=reg['addr'], reg_lsb=reg_lsb, field_lsb=field_lsb, width=width))
        reg['reset'] = sum(((by_name[n]['default'] >> fl) & ((1 << w) - 1)) << rl for n, fl, w, rl in reg['chunks'])

    # Output buses. ATB codes are not exported; the decoded, island-gated one-hot
    # switch vectors are the only ATB outputs.
    widths = {'analog': 0, 'debug': 0}
    for f in fields:
        if f['atb_bus'] is not None or f['store'] is None:
            continue
        f['bus'] = f['kind']
        f['bus_lsb'] = widths[f['kind']]
        f['bus_bits'] = f['store'][0] - f['store'][1] + 1
        if f['decode'] == 'thermometer':
            if f['values'] is not None or f['store'] != [f['bits'] - 1, 0]:
                raise SpecError(f"{f['name']}: thermometer decode needs an untrimmed numeric count")
            f['bus_bits'] = f['maximum']
        elif f['decode'] is not None:
            raise SpecError(f"{f['name']}: unknown decode {f['decode']}")
        widths[f['kind']] += f['bus_bits']

    # Rules: specification rules followed by generated ATB force/override rules.
    def compile_cond(c):
        name, op, value = c
        if name not in by_name:
            raise SpecError(f'rule field {name} undefined')
        f = by_name[name]
        if f['store'] is None:
            raise SpecError(f'rule uses dropped field {name}')
        vals = value if op in ('in', 'nin') else [value]
        if op not in ('eq', 'ne', 'in', 'nin'):
            raise SpecError(f'bad op {op}')
        return [name, op, [encode(f, v) for v in vals]]

    rules = []
    for r in dbg['rules']:
        rules.append(dict(id=r['id'], cls=r['class'], node=r.get('node'), if_any=[compile_cond(c) for c in r.get('if_any', [])],
                          if_all=[compile_cond(c) for c in r.get('if_all', [])],
                          then_all=[compile_cond(c) for c in r['then_all']], source='spec/debug-controls.json'))
    for n in atb_nodes:
        if n['force'] == 'override':
            ov = 'debug.bias_override.' + n['override']
            if ov not in by_name:
                raise SpecError(f'ATB node {n["name"]}: no override field {ov}')
            rules.append(dict(id=f'atb0_force_{n["name"]}_needs_override', cls='legality', node=n['name'],
                              if_any=[['debug.atb.atb0', 'eq', [n['code']]]], if_all=[],
                              then_all=[[ov, 'eq', [1]]], source='atb_policy'))
            rules.append(dict(id=f'override_{n["override"]}_needs_atb0_{n["name"]}', cls='legality', node=n['name'],
                              if_any=[[ov, 'eq', [1]]], if_all=[],
                              then_all=[['debug.atb.atb0', 'eq', [n['code']]]], source='atb_policy'))
    if len(rules) > 0x7F:
        raise SpecError('too many rules for ERROR_INFO encoding')

    bbm = list(dbg['break_before_make'])
    for name in bbm:
        if name not in by_name or by_name[name]['store'] is None:
            raise SpecError(f'break_before_make field {name} undefined')
    forced = {}
    for name, value in dbg['fault_forced']['fields'].items():
        if name not in by_name or by_name[name]['store'] is None:
            raise SpecError(f'fault_forced field {name} undefined or dropped')
        forced[name] = encode(by_name[name], value)
    split = [f['name'] for f in fields if f['split'] and f['store'] is not None]

    model = dict(
        schema_version=1,
        generator='rtl/gen/gen_regfile.py',
        sources=dict(analog='spec/analog-architecture.json:control_fields', debug='spec/debug-controls.json'),
        spi_abi=dbg['spi_abi'], islands=islands, atb_nodes=atb_nodes, obs_status=dbg['obs_status'],
        wire_status=dbg['wire_status'], fields=fields, groups=[dict(name=g['name'], kind=g['kind'],
            description=g['description'], update=g['update'], registers=g['registers'],
            fallback_routes=g['fallback_routes'], fields=[f['name'] for f in g['fields']]) for g in groups],
        registers=registers, status_registers=status_regs, status_fields=status_fields, rules=rules, break_before_make=bbm, split_fields=split, fault_forced=forced,
        bus_widths=widths, atb_width=len(atb_nodes), atb_groups=dbg.get('atb_groups', {}),
        atb_switch_dead_time_s=dbg.get('atb_switch_dead_time_s'), last_debug=last_debug, last_analog=last_analog,
        commit_semantics=dbg['commit_semantics'], cdc_semantics=dbg['cdc_semantics'],
        gating_rule=dbg['gating_rule'], atb_policy=dbg['atb_policy'],
        break_before_make_rule=dbg['break_before_make_rule'])
    canonical = json.dumps(model, sort_keys=True, separators=(',', ':')).encode()
    model['map_hash16'] = int(hashlib.sha256(canonical).hexdigest()[-4:], 16)
    validate(model, dbg, readiness)
    return model


def runtime_namespace(model):
    ns = {}
    exec(compile(RUNTIME_SRC, 'regmap_runtime.py', 'exec'), ns)
    ns.update(FIELDS=model['fields'], FIELD_BY_NAME={f['name']: f for f in model['fields']},
              REGISTERS=model['registers'], REGISTER_BY_ADDR={r['addr']: r for r in model['registers']},
              RULES=model['rules'], BREAK_BEFORE_MAKE=model['break_before_make'],
              SPLIT_FIELDS=model['split_fields'], FORCED=model['fault_forced'], ISLANDS=model['islands'],
              ATB_NODES=model['atb_nodes'], STATUS_FIELDS=model['status_fields'], ATB_GROUPS=model['atb_groups'])
    return ns


def validate(model, dbg, readiness):
    ns = runtime_namespace(model)
    by_name = ns['FIELD_BY_NAME']
    reset = ns['reset_config']()
    for f in model['fields']:
        if f['gate_and'] is not None:
            g = by_name.get(f['gate_and'])
            if g is None or g['bits'] != 1 or f['bits'] != 1 or g['islands'] != f['islands'] or f['name'] in model['fault_forced']:
                raise SpecError(f"{f['name']}: gate_and needs a 1-bit field with the same islands")
        if f['store'] is not None and not ns['field_ok'](f, f['default']):
            raise SpecError(f"{f['name']}: default out of range")
    for r in model['rules']:
        if not ns['rule_ok'](r, reset):
            raise SpecError(f"reset defaults violate rule {r['id']}")
        if r['cls'] in ('pad', 'ownership'):
            # Monotone form: island isolation and fault release drive fields to 0,
            # so a pad rule must stay true when any of its fields is forced to 0.
            for c in r['if_any'] + r['if_all']:
                if ns['cond_ok'](c, {c[0]: 0}):
                    raise SpecError(f"pad rule {r['id']}: trigger {c} is true at 0")
            for c in r['then_all']:
                if not ns['cond_ok'](c, {c[0]: 0}):
                    raise SpecError(f"pad rule {r['id']}: requirement {c} is false at 0")
            for c in r['if_any'] + r['if_all'] + r['then_all']:
                if c[0] in model['fault_forced']:
                    v = model['fault_forced'][c[0]]
                    if v != 0:
                        raise SpecError(f"pad rule {r['id']} uses non-zero fault-forced field {c[0]}")
    if ns['commit_code'](reset, reset, 0) != 0:
        raise SpecError('reset configuration does not commit')
    # Safe power-up: every island off; therefore every island-gated output is 0.
    out = ns['outputs'](reset, (1 << len(model['islands'])) - 1, 0)
    if out['island_en'] or out['atb0_sw'] or out['atb1_sw']:
        raise SpecError('reset state powers an island or closes an ATB switch')
    # Every debug.* control named by a readiness fallback route must exist here.
    groups = {g['name']: g for g in model['groups']}
    for route_id, route in readiness['fallback_routes'].items():
        for part in route['control'].split('+'):
            tokens = part.split()
            if not tokens or not tokens[0].startswith('debug.'):
                continue
            g = groups.get(tokens[0])
            if g is None:
                raise SpecError(f'fallback route {route_id}: control {tokens[0]} not defined')
            for value in tokens[1:]:
                if not any(by_name[n]['values'] and value in by_name[n]['values'] for n in g['fields']):
                    raise SpecError(f'fallback route {route_id}: {tokens[0]} has no value {value}')
    for g in model['groups']:
        for route_id in g['fallback_routes']:
            if route_id not in readiness['fallback_routes']:
                raise SpecError(f"{g['name']}: unknown fallback route {route_id}")
    groups_spec = model['atb_groups']
    for bus in ('atb0', 'atb1'):
        for group in groups_spec.get(bus, []):
            if len(group['codes']) > groups_spec.get('max_leaves_per_group', 12):
                raise SpecError(f'atb_groups.{bus}.{group["name"]}: exceeds the physical leaf-load limit')
        f = by_name[f'debug.atb.{bus}']
        legal = set(f['allowed'] if f['allowed'] is not None else range(f['minimum'], f['maximum'] + 1)) - {0}
        codes = [c for g in groups_spec.get(bus, []) for c in g['codes']]
        if sorted(codes) != sorted(legal):
            raise SpecError(f'atb_groups.{bus} must place every legal code exactly once: '
                            f'missing {sorted(legal - set(codes))}, extra {sorted(set(codes) - legal)}')
    sites = [s['name'] for s in readiness['debug_sites']]
    if len(sites) != 19:
        raise SpecError('expected 19 debug sites')
    if len(dbg['obs_status']) != 32 or len(dbg['wire_status']) != 16:
        raise SpecError('obs_status must list 32 and wire_status 16 signals')
    if by_name['debug.dbg_obs.sel0']['maximum'] != 4 + 32 or by_name['debug.wdbg_obs.select']['maximum'] != 2 + 16:
        raise SpecError('observation mux maxima do not match the status vectors')


# ---------------------------------------------------------------- SystemVerilog

def sv_const(width, value):
    return f"{width}'d{value}"


def sv_check(f, expr):
    """Expression true when expr (width f['bits']) is an accepted encoding."""
    w = f['bits']
    if f['allowed'] is not None:
        allowed = f['allowed']
        if allowed == list(range(len(allowed))):
            return '1\'b1' if len(allowed) == (1 << w) else f'({expr}<={sv_const(w, len(allowed) - 1)})'
        return '(' + '||'.join(f'{expr}=={sv_const(w, v)}' for v in allowed) + ')'
    terms = []
    if f['minimum'] > 0:
        terms.append(f'{expr}>={sv_const(w, f["minimum"])}')
    if f['maximum'] < (1 << w) - 1:
        terms.append(f'{expr}<={sv_const(w, f["maximum"])}')
    return '(' + '&&'.join(terms) + ')' if terms else "1'b1"


def sv_cond(c, prefix, by_name):
    name, op, vals = c
    f = by_name[name]
    w = f['bits']
    sig = prefix + f['sv']
    if op == 'eq':
        return f'({sig}=={sv_const(w, vals[0])})'
    if op == 'ne':
        return f'({sig}!={sv_const(w, vals[0])})'
    inner = '||'.join(f'{sig}=={sv_const(w, v)}' for v in vals)
    return f'({inner})' if op == 'in' else f'!({inner})'


def sv_rule(r, prefix, by_name):
    trig = []
    if r['if_any']:
        trig.append('(' + '||'.join(sv_cond(c, prefix, by_name) for c in r['if_any']) + ')')
    trig += [sv_cond(c, prefix, by_name) for c in r['if_all']]
    then = '&&'.join(sv_cond(c, prefix, by_name) for c in r['then_all'])
    return f"(!({'&&'.join(trig)})||({then}))"


def store_reg(f, prefix):
    """(register name, lsb) of the stored bits of a field, or None when dropped."""
    if f['store'] is None:
        return None
    if f['store'] == [f['bits'] - 1, 0]:
        return f'{prefix}_{f["sv"]}', 0
    return f'{prefix}r_{f["sv"]}', f['store'][1]


def emit_sv(model):
    fields, regs, rules = model['fields'], model['registers'], model['rules']
    by_name = {f['name']: f for f in fields}
    islands = model['islands']
    nisl = len(islands)
    natb = model['atb_width']
    aw, dw = model['bus_widths']['analog'], model['bus_widths']['debug']
    L = []
    a = L.append
    a('// GENERATED by rtl/gen/gen_regfile.py from spec/analog-architecture.json:control_fields')
    a('// and spec/debug-controls.json. Do not edit; edit the specifications and regenerate.')
    a(f'// Register map hash 0x{model["map_hash16"]:04X}; see spec/register-map.md.')
    a('//')
    a('// pt_regfile: SPI register file clocked only by SPI SCLK, asynchronously reset by rst_n')
    a('// (RESET_N AND POR). Shadow registers take SPI writes; COMMIT validates and copies shadow to')
    a('// active atomically. Pad/analog outputs are island-isolated (forced to 0) and fault-released.')
    a('// pt_mgmt: pt_spi (unchanged Mode-0 cmd8/addr8/data16 ABI) plus pt_regfile; replaces pt_control.')
    a('`default_nettype none')
    a('module pt_regfile(')
    a(' input wire rst_n,sclk,')
    a(' input wire por_n, // POR alone (rst_n = RESET_N AND por_n); sets the sticky POR flag')
    a(' input wire wr_en,input wire[7:0]wr_addr,input wire[15:0]wr_data,')
    a(' input wire[7:0]rd_addr,output reg[15:0]rd_data,')
    a(' // Legacy pt_control boundary (unchanged addresses 0x01-0x04, 0x10-0x12, 0x20-0x26).')
    a(' input wire[15:0]status,output reg enable,mode8,output reg[15:0]rf_trim,wire_trim,clock_trim,')
    a(' output wire memory_write,output wire[4:0]memory_index,output wire[23:0]memory_wdata,')
    a(' input wire[23:0]capture_data,input wire capture_done,output reg playback_enable,capture_enable,')
    a(' // Generated control boundary.')
    a(f' input wire fault,input wire[{nisl - 1}:0]island_pgood,input wire[31:0]obs_status,input wire[15:0]wire_status,')
    a(f' output wire[{aw - 1}:0]analog_cfg,output wire[{dw - 1}:0]debug_cfg,')
    a(f' output wire[{nisl - 1}:0]island_en,island_on,output wire[{natb - 1}:0]atb0_sw,atb1_sw,')
    a(f' output wire[{len(model["atb_groups"]["atb0"]) - 1}:0]atb0_grp,output wire[{len(model["atb_groups"]["atb1"]) - 1}:0]atb1_grp,output wire atb0_en,atb1_en,')
    a(' output wire rx_en_aux,rx_en_wclk,rx_en_wtx_ext,clk_obs_oe,wclk_obs_oe,')
    a(' output wire dbg_obs0,dbg_obs0_oe,dbg_obs1,dbg_obs1_oe,wdbg_obs,wdbg_obs_oe,')
    a(' output reg commit_toggle,output wire config_error' +
      ''.join(f',\n input wire[{sf["bits"] - 1}:0]{sf["port"]}' for sf in model['status_fields']) + ');')
    a(f' localparam[15:0]ID=16\'h5356,ABI_VERSION=16\'h{0x0002:04X},MAP_HASH=16\'h{model["map_hash16"]:04X};')
    a(' // Legacy state (identical behaviour to pt_control).')
    a(' reg[4:0]index;reg[11:0]play_i;reg rejected;reg[15:0]s1,s2;reg c1,c2;')
    a(' assign memory_index=index;assign memory_wdata={wr_data[11:0],play_i};')
    a(" assign memory_write=wr_en&&wr_addr==8'h22&&!enable;")
    a(' // Commit/status state.')
    a(f' reg view,last_ok;reg[7:0]commit_count,err_code,err_addr;reg[6:0]cfg_err;')
    a(f' reg[{nisl - 1}:0]pg1,pg2,on1,on2;reg f1,f2;')
    a(' assign config_error=|cfg_err;')
    if model['status_fields']:
        a(' // Read-only status: two SCLK flops per bit; Gray-coded counters converted after synchronization.')
    reserved_ports = [sf['port'] for sf in model['status_fields'] if sf['reserved']]
    if reserved_ports:
        a(' /* verilator lint_off UNUSEDSIGNAL */')
        a(' wire unused_reserved_status=^{' + ','.join(reserved_ports) + '}; // reserved status inputs, read 0')
        a(' /* verilator lint_on UNUSEDSIGNAL */')
    for sf in model['status_fields']:
        if sf['reserved']:
            continue
        w, n = sf['bits'], sf['port']
        a(f' reg[{w - 1}:0]st1_{n},st2_{n};wire[{w - 1}:0]stv_{n};')
        if sf['encoding'] == 'gray':
            for i in range(w):
                a(f' assign stv_{n}[{i}]=^st2_{n}[{w - 1}:{i}];')
        else:
            a(f' assign stv_{n}=st2_{n};')
    a(' // Shadow (s_), active (a_) and output (o_) copies of every field.')
    a(' /* verilator lint_off UNUSEDSIGNAL */ // trimmed fields leave output bits without a port')
    a(' // Fields trimmed by hardware_trim keep their address bits: dropped fields are constant 0;')
    a(' // sliced fields store (sr_/ar_) only the bits that drive a real port.')
    for f in fields:
        b = f['bits']
        if f['store'] is None:
            a(f' wire[{b - 1}:0]s_{f["sv"]}={b}\'d0,a_{f["sv"]}={b}\'d0;wire[{b - 1}:0]o_{f["sv"]};')
        elif f['store'] == [b - 1, 0]:
            a(f' reg[{b - 1}:0]s_{f["sv"]},a_{f["sv"]};wire[{b - 1}:0]o_{f["sv"]};')
        else:
            hi, lo = f['store']
            def cat(x):
                parts = ([f"{b - 1 - hi}'d0"] if hi < b - 1 else []) + [x] + ([f"{lo}'d0"] if lo else [])
                return '{' + ','.join(parts) + '}'
            a(f' reg[{hi}:{lo}]sr_{f["sv"]},ar_{f["sv"]};wire[{b - 1}:0]s_{f["sv"]}={cat("sr_" + f["sv"])},'
              f'a_{f["sv"]}={cat("ar_" + f["sv"])};wire[{b - 1}:0]o_{f["sv"]};')
    a(' /* verilator lint_on UNUSEDSIGNAL */')
    # Island gating.
    a(' // Island isolation: a gated output is 0 unless its islands are switched on and powered.')
    for isl, bit in islands.items():
        a(f' assign island_en[{bit}]=a_debug_island_power__{isl}[0];')
        a(f' assign island_on[{bit}]=a_debug_island_power__{isl}[0]&&(island_pgood[{bit}]||a_debug_pgood_override__{isl}[0]);')
    for f in fields:
        gate = '&&'.join(f'island_on[{islands[i]}]' for i in f['islands']) or "1'b1"
        val = f'a_{f["sv"]}'
        if f['gate_and']:
            val = f'(a_{f["sv"]}&a_{by_name[f["gate_and"]]["sv"]})'
        if f['name'] in model['fault_forced']:
            val = f'(fault ? {sv_const(f["bits"], model["fault_forced"][f["name"]])} : {val})'
        if f['islands']:
            a(f' assign o_{f["sv"]}=({gate}) ? {val} : {sv_const(f["bits"], 0)};')
        else:
            a(f' assign o_{f["sv"]}={val};')
    # Buses.
    for bus, width in (('analog', aw), ('debug', dw)):
        for f in fields:
            if f['bus'] == bus:
                hi, lo = f['store']
                if f['decode'] == 'thermometer':
                    n = f['bus_bits']
                    a(f' /* verilator lint_off UNUSEDSIGNAL */ wire[{n}:0]th_{f["sv"]}=({n + 1}\'d1<<o_{f["sv"]})-{n + 1}\'d1; /* verilator lint_on UNUSEDSIGNAL */ // count -> thermometer')
                    a(f' assign {bus}_cfg[{f["bus_lsb"] + n - 1}:{f["bus_lsb"]}]=th_{f["sv"]}[{n - 1}:0];')
                else:
                    a(f' assign {bus}_cfg[{f["bus_lsb"] + f["bus_bits"] - 1}:{f["bus_lsb"]}]=o_{f["sv"]}[{hi}:{lo}];')
    # ATB one-hot decode with node gating.
    a(' // ATB: one-hot switch vectors, bit k-1 = node code k; island nodes open while the island is off.')
    for bus in (0, 1):
        for n in model['atb_nodes']:
            gate = f'&&island_on[{islands[n["island"]]}]' if n['island'] else ''
            a(f' assign atb{bus}_sw[{n["code"] - 1}]=(o_debug_atb__atb{bus}==6\'d{n["code"]}){gate};')
    a(' // ATB group and pad selects: ORs of the island-gated leaf lines (analog/island_support README A1).')
    for bus in (0, 1):
        for gi, grp in enumerate(model['atb_groups'][f'atb{bus}']):
            a(f' assign atb{bus}_grp[{gi}]=' + '|'.join(f'atb{bus}_sw[{c - 1}]' for c in grp['codes']) + f'; // {grp["name"]}')
        a(f' assign atb{bus}_en=|atb{bus}_sw;')
    # Receiver enables and observation pads.
    cs = by_name['debug.clk_select.rf_lo']['values']
    aux, wclk = cs.index('aux_clk'), cs.index('wclk_in')
    clk_sel = [f for f in fields if f['group'] == 'debug.clk_select']
    obs_src = by_name['debug.clk_obs.source']['values']
    wobs_src = by_name['debug.wclk_obs.source']['values']
    a(' assign rx_en_aux=island_on[%d]&&(' % islands['debug'] + '||'.join([f'o_{f["sv"]}==3\'d{aux}' for f in clk_sel] +
                                        [f'o_debug_clk_obs__source==4\'d{obs_src.index("aux_clk")}']) + ');')
    a(' assign rx_en_wclk=island_on[%d]&&(' % islands['debug'] + '||'.join([f'o_{f["sv"]}==3\'d{wclk}' for f in clk_sel] +
                                         [f'o_debug_clk_obs__source==4\'d{obs_src.index("wclk_in")}',
                                          f'o_debug_wclk_obs__source==3\'d{wobs_src.index("wclk_in")}']) + ');')
    a(' assign rx_en_wtx_ext=island_on[%d]&&o_debug_wtx_ext__enable[0]; // debug-pad receivers sit on the debug island' % islands['debug'])
    a(" assign clk_obs_oe=o_debug_clk_obs__source!=4'd0;")
    a(" assign wclk_obs_oe=o_debug_wclk_obs__source!=3'd0;")
    a(" wire[36:0]dbg_src={rst_n,obs_status,commit_toggle,1'b1,1'b0,1'b0};")
    a(" wire[18:0]wdbg_src={wire_status,1'b1,1'b0,1'b0};")
    a(" assign dbg_obs0=dbg_src[o_debug_dbg_obs__sel0];assign dbg_obs0_oe=o_debug_dbg_obs__sel0!=6'd0;")
    a(" assign dbg_obs1=dbg_src[o_debug_dbg_obs__sel1];assign dbg_obs1_oe=o_debug_dbg_obs__sel1!=6'd0;")
    a(" assign wdbg_obs=wdbg_src[o_debug_wdbg_obs__select];assign wdbg_obs_oe=o_debug_wdbg_obs__select!=5'd0;")
    # Commit validation.
    a(' // Sticky reset-cause flags (0x0D, write 1 to clear). Their only asynchronous control is the')
    a(' // reset source itself: por_flag is set by POR alone and survives RESET_N; rst_flag is set by')
    a(' // any reset (RESET_N or POR). Both flops sit in the never-switched core domain.')
    a(' reg por_flag,rst_flag;')
    a(' always @(posedge sclk or negedge por_n)')
    a("  if(!por_n)por_flag<=1'b1;else if(wr_en&&wr_addr==8'h0D&&wr_data[0])por_flag<=1'b0;")
    a(' always @(posedge sclk or negedge rst_n)')
    a("  if(!rst_n)rst_flag<=1'b1;else if(wr_en&&wr_addr==8'h0D&&wr_data[1])rst_flag<=1'b0;")
    a(' // Commit validation on the complete shadow configuration.')
    a(f' wire[{len(rules) - 1}:0]rule_ok_s;')
    for i, r in enumerate(rules):
        a(f' assign rule_ok_s[{i}]={sv_rule(r, "s_", by_name)}; // {r["id"]}')
    split = model['split_fields']
    a(f' wire[{max(len(split), 1) - 1}:0]split_ok;')
    for i, name in enumerate(split):
        f = by_name[name]
        a(f' assign split_ok[{i}]={sv_check(f, "s_" + f["sv"])}; // {name}')
    bbm = model['break_before_make']
    a(f' wire[{len(bbm) - 1}:0]bbm_ok;')
    for i, name in enumerate(bbm):
        f = by_name[name]
        z = sv_const(f['bits'], 0)
        a(f' assign bbm_ok[{i}]=!(a_{f["sv"]}!={z}&&s_{f["sv"]}!={z}&&s_{f["sv"]}!=a_{f["sv"]}); // {name}')
    nonlive = [f for f in fields if not f['live'] and f['store'] is not None]
    a(' wire nonlive_diff=' + '||'.join(f's_{f["sv"]}!=a_{f["sv"]}' for f in nonlive) + ';')
    a(' wire pending=' + '||'.join(f's_{f["sv"]}!=a_{f["sv"]}' for f in fields if f['store'] is not None) + ';')
    a(' reg[7:0]commit_code;')
    a(' always @*begin')
    a("  commit_code=8'h00;")
    for i in reversed(range(len(bbm))):
        a(f"  if(!bbm_ok[{i}])commit_code=8'h{0x80 + i:02X};")
    for i in reversed(range(len(rules))):
        a(f"  if(!rule_ok_s[{i}])commit_code=8'h{1 + i:02X};")
    for i in reversed(range(len(split))):
        a(f"  if(!split_ok[{i}])commit_code=8'h{0xC0 + i:02X};")
    a("  if(enable&&nonlive_diff)commit_code=8'hFF;")
    a(' end')
    a(" wire commit_ok=commit_code==8'h00;")
    a(" wire[6:0]commit_err=(commit_code==8'hFF)?7'h20:(commit_code>=8'hC0)?7'h04:(commit_code>=8'h80)?7'h10:7'h08;")
    # Write-time checks.
    a(' // Write-time checks: reserved bits zero and every non-split field encoding accepted.')
    for reg in regs:
        terms = [f"(wr_data&16'h{(~reg['writable_mask']) & 0xFFFF:04X})==16'h0000"] if reg['writable_mask'] != 0xFFFF else []
        for name, fl, w, rl in reg['chunks']:
            f = by_name[name]
            if not f['split'] and f['store'] is not None:
                c = sv_check(f, f'wr_data[{rl + w - 1}:{rl}]')
                if c != "1'b1":
                    terms.append(c)
        expr = '&&'.join(terms) or "1'b1"
        a(f" wire wok_{reg['addr']:02X}={expr};")
    # Sequential block.
    a(' always @(posedge sclk or negedge rst_n)begin')
    a('  if(!rst_n)begin')
    a('   enable<=0;mode8<=0;rf_trim<=0;wire_trim<=0;clock_trim<=0;index<=0;play_i<=0;')
    a('   rejected<=0;s1<=0;s2<=0;c1<=0;c2<=0;playback_enable<=0;capture_enable<=0;')
    a('   view<=0;last_ok<=0;commit_count<=0;err_code<=0;err_addr<=0;cfg_err<=0;commit_toggle<=0;')
    a('   pg1<=0;pg2<=0;on1<=0;on2<=0;f1<=0;f2<=0;')
    for sf in model['status_fields']:
        if sf['reserved']:
            continue
        a(f'   st1_{sf["port"]}<=0;st2_{sf["port"]}<=0;')
    for f in fields:
        if f['store'] is None:
            continue
        hi, lo = f['store']
        d = sv_const(hi - lo + 1, f['default'] >> lo)
        a(f'   {store_reg(f, "s")[0]}<={d};{store_reg(f, "a")[0]}<={d};')
    a('  end else begin')
    a('   s1<=status;s2<=s1;c1<=capture_done;c2<=c1;')
    a('   pg1<=island_pgood;pg2<=pg1;on1<=island_on;on2<=on1;f1<=fault;f2<=f1;')
    for sf in model['status_fields']:
        if sf['reserved']:
            continue
        a(f'   st1_{sf["port"]}<={sf["port"]};st2_{sf["port"]}<=st1_{sf["port"]};')
    a('   if(wr_en)begin')
    a('    case(wr_addr)')
    a("     8'h01:enable<=wr_data[0];")
    a("     8'h20:index<=wr_data[4:0];")
    a("     8'h02,8'h04,8'h10,8'h11,8'h12,8'h21,8'h22,8'h23:")
    a('      if(enable)begin rejected<=1;cfg_err[6]<=1;err_addr<=wr_addr;end')
    a('      else case(wr_addr)')
    a("       8'h02:mode8<=wr_data[0];8'h04:rejected<=0;")
    a("       8'h10:rf_trim<=wr_data;8'h11:wire_trim<=wr_data;8'h12:clock_trim<=wr_data;")
    a("       8'h21:play_i<=wr_data[11:0];")
    a("       8'h23:begin playback_enable<=wr_data[0];capture_enable<=wr_data[1];end")
    a('       default:begin end')
    a('      endcase')
    a("     8'h05:cfg_err<=cfg_err&~wr_data[6:0];")
    a("     8'h06:if(wr_data==16'h0001)begin")
    a('       if(commit_ok)begin')
    for f in fields:
        if f['store'] is not None:
            a(f'        {store_reg(f, "a")[0]}<={store_reg(f, "s")[0]};')
    a('        commit_toggle<=!commit_toggle;commit_count<=commit_count+1\'b1;last_ok<=1;err_code<=0;')
    a('       end else begin last_ok<=0;err_code<=commit_code;cfg_err<=cfg_err|commit_err;end')
    a("      end else if(wr_data==16'h0002)begin")
    for f in fields:
        if f['store'] is not None:
            a(f'       {store_reg(f, "s")[0]}<={store_reg(f, "a")[0]};')
    a('      end else begin cfg_err[0]<=1;err_addr<=wr_addr;end')
    a("     8'h0D:begin end // RESET_STATUS: write-1-to-clear handled by the flag flops")
    a("     8'h07:if(wr_data[15:1]==15'h0)view<=wr_data[0];else begin cfg_err[0]<=1;err_addr<=wr_addr;end")
    for reg in regs:
        a(f"     8'h{reg['addr']:02X}:if(wok_{reg['addr']:02X})begin")
        for name, fl, w, rl in reg['chunks']:
            f = by_name[name]
            if f['store'] is None:
                continue
            hi, lo = f['store']
            il, ih = max(fl, lo), min(fl + w - 1, hi)   # stored bits within this chunk
            if il > ih:
                continue
            reg_name, base = store_reg(f, 's')
            full = (ih - il + 1) == (hi - lo + 1)
            dst = reg_name if full else f'{reg_name}[{ih}:{il}]'
            a(f'       {dst}<=wr_data[{rl + ih - fl}:{rl + il - fl}];')
        a('      end else begin cfg_err[0]<=1;err_addr<=wr_addr;end')
    a('     default:begin rejected<=1;cfg_err[1]<=1;err_addr<=wr_addr;end')
    a('    endcase')
    a('   end')
    a('  end')
    a(' end')
    # Readback.
    a(' always @*begin')
    a("  rd_data=16'h0000;")
    a('  case(rd_addr)')
    a("   8'h00:rd_data=ID;8'h01:rd_data={15'b0,enable};8'h02:rd_data={15'b0,mode8};8'h03:rd_data=s2;")
    a("   8'h04:rd_data={15'b0,rejected};8'h05:rd_data={9'b0,cfg_err};")
    a("   8'h06:rd_data={commit_count,5'b0,pending,last_ok,commit_toggle};8'h07:rd_data={15'b0,view};")
    a("   8'h08:rd_data=ABI_VERSION;8'h09:rd_data=MAP_HASH;")
    pad = 8 - nisl
    a(f"   8'h0A:rd_data={{{pad}'b0,pg2,{pad}'b0,on2}};8'h0B:rd_data={{15'b0,f2}};8'h0C:rd_data={{err_code,err_addr}};8'h0D:rd_data={{14'b0,rst_flag,por_flag}};")
    a("   8'h10:rd_data=rf_trim;8'h11:rd_data=wire_trim;8'h12:rd_data=clock_trim;")
    a("   8'h20:rd_data={11'b0,index};8'h23:rd_data={14'b0,capture_enable,playback_enable};")
    a("   8'h24:rd_data={15'b0,c2};8'h25:rd_data=capture_data[15:0];8'h26:rd_data={8'b0,capture_data[23:16]};")
    for r in model['status_registers']:
        parts = []
        for name, fl, w, rl in r['chunks']:
            sf = next(x for x in model['status_fields'] if x['name'] == name)
            if not sf['reserved']:
                parts.append(f'rd_data[{rl + w - 1}:{rl}]=stv_{sf["port"]};')
        if parts:
            a(f"   8'h{r['addr']:02X}:begin " + ''.join(parts) + 'end')
    for reg in regs:
        parts = []
        for name, fl, w, rl in reg['chunks']:
            f = by_name[name]
            sel = '' if (fl == 0 and w == f['bits']) else f'[{fl + w - 1}:{fl}]'
            parts.append(f'rd_data[{rl + w - 1}:{rl}]=view ? a_{f["sv"]}{sel} : s_{f["sv"]}{sel};')
        a(f"   8'h{reg['addr']:02X}:begin " + ''.join(parts) + 'end')
    a('   default:begin end')
    a('  endcase')
    a(' end')
    emit_formal(model, a, by_name)
    a('endmodule')
    a('')
    a('module pt_mgmt(input wire rst_n,por_n,sclk,cs_n,mosi,output wire miso,miso_oe,')
    a(' input wire[15:0]status,output wire enable,mode8,output wire[15:0]rf_trim,wire_trim,clock_trim,')
    a(' output wire memory_write,output wire[4:0]memory_index,output wire[23:0]memory_wdata,')
    a(' input wire[23:0]capture_data,input wire capture_done,output wire playback_enable,capture_enable,')
    a(f' input wire fault,input wire[{nisl - 1}:0]island_pgood,input wire[31:0]obs_status,input wire[15:0]wire_status,')
    a(f' output wire[{aw - 1}:0]analog_cfg,output wire[{dw - 1}:0]debug_cfg,')
    a(f' output wire[{nisl - 1}:0]island_en,island_on,output wire[{natb - 1}:0]atb0_sw,atb1_sw,')
    a(f' output wire[{len(model["atb_groups"]["atb0"]) - 1}:0]atb0_grp,output wire[{len(model["atb_groups"]["atb1"]) - 1}:0]atb1_grp,output wire atb0_en,atb1_en,')
    a(' output wire rx_en_aux,rx_en_wclk,rx_en_wtx_ext,clk_obs_oe,wclk_obs_oe,')
    a(' output wire dbg_obs0,dbg_obs0_oe,dbg_obs1,dbg_obs1_oe,wdbg_obs,wdbg_obs_oe,')
    a(' output wire commit_toggle,config_error' +
      ''.join(f',\n input wire[{sf["bits"] - 1}:0]{sf["port"]}' for sf in model['status_fields']) + ');')
    a(' wire wr_en;wire[7:0]wr_addr,rd_addr;wire[15:0]wr_data,rd_data;')
    a(' pt_spi spi(.rst_n(rst_n),.sclk(sclk),.cs_n(cs_n),.mosi(mosi),.miso(miso),.miso_oe(miso_oe),')
    a('  .wr_en(wr_en),.wr_addr(wr_addr),.wr_data(wr_data),.rd_addr(rd_addr),.rd_data(rd_data));')
    a(' pt_regfile regs(.rst_n(rst_n),.por_n(por_n),.sclk(sclk),.wr_en(wr_en),.wr_addr(wr_addr),.wr_data(wr_data),')
    a('  .rd_addr(rd_addr),.rd_data(rd_data),.status(status),.enable(enable),.mode8(mode8),')
    a('  .rf_trim(rf_trim),.wire_trim(wire_trim),.clock_trim(clock_trim),.memory_write(memory_write),')
    a('  .memory_index(memory_index),.memory_wdata(memory_wdata),.capture_data(capture_data),')
    a('  .capture_done(capture_done),.playback_enable(playback_enable),.capture_enable(capture_enable),')
    a('  .fault(fault),.island_pgood(island_pgood),.obs_status(obs_status),.wire_status(wire_status),')
    a('  .analog_cfg(analog_cfg),.debug_cfg(debug_cfg),.island_en(island_en),.island_on(island_on),')
    a('  .atb0_sw(atb0_sw),.atb1_sw(atb1_sw),.atb0_grp(atb0_grp),.atb1_grp(atb1_grp),.atb0_en(atb0_en),.atb1_en(atb1_en),')
    a('  .rx_en_aux(rx_en_aux),.rx_en_wclk(rx_en_wclk),')
    a('  .rx_en_wtx_ext(rx_en_wtx_ext),.clk_obs_oe(clk_obs_oe),.wclk_obs_oe(wclk_obs_oe),')
    a('  .dbg_obs0(dbg_obs0),.dbg_obs0_oe(dbg_obs0_oe),.dbg_obs1(dbg_obs1),.dbg_obs1_oe(dbg_obs1_oe),')
    a('  .wdbg_obs(wdbg_obs),.wdbg_obs_oe(wdbg_obs_oe),.commit_toggle(commit_toggle),.config_error(config_error)' +
      ''.join(f',.{sf["port"]}({sf["port"]})' for sf in model['status_fields']) + ');')
    a('endmodule')
    a('`default_nettype wire')
    return '\n'.join(L) + '\n'


def emit_formal(model, a, by_name):
    """Safety properties, compiled only for formal (yosys read -formal defines FORMAL)."""
    fields, rules, islands = model['fields'], model['rules'], model['islands']
    a('`ifdef FORMAL')
    a(' // P1 reset: asynchronous reset returns every register to its declared default, so every island')
    a(' // switch, ATB switch, debug driver and island-gated output is off.')
    a(' always @*begin')
    a('  if(!rst_n)begin')
    for f in fields:
        a(f'   assert(a_{f["sv"]}=={sv_const(f["bits"], f["default"])}&&s_{f["sv"]}=={sv_const(f["bits"], f["default"])});')
    a('   assert(island_en==0&&island_on==0&&atb0_sw==0&&atb1_sw==0&&atb0_grp==0&&atb1_grp==0&&!atb0_en&&!atb1_en);')
    a('   assert(!clk_obs_oe&&!wclk_obs_oe&&!dbg_obs0_oe&&!dbg_obs1_oe&&!wdbg_obs_oe);')
    a('   assert(!rx_en_aux&&!rx_en_wclk&&!rx_en_wtx_ext&&!enable&&!playback_enable&&!capture_enable);')
    for bus in ('analog', 'debug'):
        image = 0
        for f in fields:
            if f['bus'] == bus and not f['islands']:
                v = f['default'] >> f['store'][1]
                if f['decode'] == 'thermometer':
                    v = (1 << v) - 1
                if f['gate_and']:
                    v &= by_name[f['gate_and']]['default']
                image |= v << f['bus_lsb']
        w = model['bus_widths'][bus]
        a(f"   assert({bus}_cfg=={w}'h{image:X}); // island-gated fields 0, ungated core fields at defaults")
    for f in fields:
        if f['islands']:
            a(f'   assert(o_{f["sv"]}=={sv_const(f["bits"], 0)});')
    a('  end')
    a(' end')
    a(' // P2 every rule holds on the committed (active) configuration at all times, and every')
    a(' // active field (and every shadow field narrower than 17 bits) holds an accepted encoding.')
    a(' always @*begin')
    for f in fields:
        if f['store'] is None:
            continue
        a(f'  assert({sv_check(f, "a_" + f["sv"])});')
        if not f['split']:
            a(f'  assert({sv_check(f, "s_" + f["sv"])});')
    for r in rules:
        a(f'  assert({sv_rule(r, "a_", by_name)}); // {r["id"]}')
    a(' end')
    a(' // P3 every pad/node exclusion rule holds on the pad-facing outputs, for every island,')
    a(' // power-good and fault input combination.')
    a(' always @*begin')
    for r in rules:
        if r['cls'] in ('pad', 'ownership'):
            a(f'  assert({sv_rule(r, "o_", by_name)}); // {r["id"]}')
    a('  assert((atb0_sw&(atb0_sw-1\'b1))==0&&(atb1_sw&(atb1_sw-1\'b1))==0);')
    a('  assert((atb0_grp&(atb0_grp-1\'b1))==0&&(atb1_grp&(atb1_grp-1\'b1))==0); // at most one group per bus')
    a('  assert(atb0_en==(atb0_grp!=0)&&atb1_en==(atb1_grp!=0)); // pad select iff a group is selected')
    for n in model['atb_nodes']:
        if n['force'] == 'override':
            ov = 'o_debug_bias_override__' + n['override']
            a(f'  assert(atb0_sw[{n["code"] - 1}]=={ov}[0]); // {n["name"]}')
        if n['force'] == 'sense_only':
            a(f'  assert(!atb0_sw[{n["code"] - 1}]); // {n["name"]} sense only')
    a(' end')
    a(' // P4 island isolation, fault release and hardware AND gates.')
    a(' always @*begin')
    for f in fields:
        if f['gate_and']:
            a(f'  if(!o_{by_name[f["gate_and"]]["sv"]}[0])assert(o_{f["sv"]}==1\'b0); // {f["name"]} gated by {f["gate_and"]}')
    for f in fields:
        if f['islands']:
            gate = '&&'.join(f'island_on[{islands[i]}]' for i in f['islands'])
            a(f'  if(!({gate}))assert(o_{f["sv"]}=={sv_const(f["bits"], 0)});')
    for name, v in model['fault_forced'].items():
        f = by_name[name]
        a(f'  if(fault)assert(o_{f["sv"]}=={sv_const(f["bits"], 0)}||o_{f["sv"]}=={sv_const(f["bits"], v)});')
    a(' end')
    a(' // P5 commit discipline: non-live fields never change while the payload runs, and')
    a(' // break-before-make fields never move directly between two non-zero codes.')
    a(' // P6 reset-cause flags: POR sets both, any reset sets rst_flag.')
    a(' always @*begin')
    a('  if(!por_n)assert(por_flag&&rst_flag);')
    a('  if(!rst_n)assert(rst_flag);')
    a(' end')
    a(' reg f_past=0;always @(posedge sclk)f_past<=1;')
    a(' always @(posedge sclk)if(f_past&&$past(rst_n)&&rst_n)begin')
    a('  if($past(enable))begin')
    for f in fields:
        if not f['live']:
            a(f'   assert(a_{f["sv"]}==$past(a_{f["sv"]}));')
    a('  end')
    for name in model['break_before_make']:
        f = by_name[name]
        z = sv_const(f['bits'], 0)
        a(f'  assert($past(a_{f["sv"]})=={z}||a_{f["sv"]}=={z}||a_{f["sv"]}==$past(a_{f["sv"]}));')
    a(' end')
    a(' // Non-vacuity: these fallback configurations are reachable through SPI writes and commits.')
    a(' always @*begin')
    a("  cover(island_on[%d]&&o_debug_bb_tap__mode==3'd%d);" % (islands['rf'], by_name['debug.bb_tap.mode']['values'].index('inject_rx')))
    a("  cover(island_on[%d]&&o_debug_wtx_ext__enable==1'b1);" % islands['wired'])
    a("  cover(atb0_sw[0]&&o_core_biasgen__ena==1'b1); // ROOT_REF forced with the biasgen on (idac2 = 0)")
    a("  cover(atb0_sw[54]&&o_core_biasgen__ena==1'b1); // VBG forced with the bandgap off")
    a(' end')
    a('`endif')


# ---------------------------------------------------------------- documents and headers

def field_range_text(f):
    if f['values'] is not None:
        allowed = [f['values'][i] for i in f['allowed']]
        text = ', '.join(f'{i}={v}' for i, v in enumerate(f['values']) if v in allowed)
        bad = [v for v in f['values'] if v not in allowed]
        return text + (f' (rejected: {", ".join(map(str, bad))})' if bad else '')
    if f['allowed'] is not None:
        return 'codes ' + ', '.join(map(str, f['allowed']))
    return f"{f['minimum']}..{f['maximum']}" + (f" {f['unit']}" if f['unit'] and f['unit'] != 'code' else '')


def default_text(f):
    if f['values'] is not None:
        return f"{f['default']} ({f['values'][f['default']]})"
    return str(f['default'])


def emit_markdown(model):
    fields, regs = model['fields'], model['registers']
    by_name = {f['name']: f for f in fields}
    L = []
    a = L.append
    a('# Control register map')
    a('')
    a('Generated by `rtl/gen/gen_regfile.py` from `analog-architecture.json:control_fields` and')
    a('`debug-controls.json`. Do not edit; regenerate. The machine-readable map is')
    a('`register-map.json`; bench headers are `rtl/gen/pt_regmap.h` and `rtl/gen/pt_regmap.py`.')
    a('')
    a(f'Map hash `0x{model["map_hash16"]:04X}` (read at 0x09), ABI version `0x0002` (0x08), ID `0x5356` (0x00).')
    a(f'{len(regs)} generated registers ({sum(1 for r in regs if r["kind"] == "debug")} debug/fallback at '
      f'0x40-0x{model["last_debug"]:02X}, {sum(1 for r in regs if r["kind"] == "analog")} analog at '
      f'0x60-0x{model["last_analog"]:02X}) carrying {len(fields)} fields '
      f'({sum(f["bits"] for f in fields)} bits); {len(model["rules"])} commit rules.')
    a('')
    a('## SPI ABI')
    a('')
    a('Unchanged: SPI mode 0, MSB first, one 32-clock transaction per CS_N low period: command8 /')
    a('address8 / data16. Command 0x80 writes, 0x00 reads (read data is shifted out during the last')
    a('16 clocks). The flat 8-bit address space holds every register, so no page register is used.')
    a('The register file is clocked only by `HOST_SCLK` and works with every PLL and oscillator stopped.')
    a('')
    a('## System and legacy registers')
    a('')
    a('| Addr | Name | Access | Meaning |')
    a('| --- | --- | --- | --- |')
    for row in [
        ('0x00', 'ID', 'R', '0x5356'),
        ('0x01', 'ENABLE', 'RW', 'Legacy payload enable (bit 0). While 1, legacy registers are locked and commits may change only live fields.'),
        ('0x02', 'MODE8', 'RW', 'Legacy 8-bit RF sample mode (bit 0); locked while ENABLE.'),
        ('0x03', 'STATUS', 'R', 'Legacy core status, two-flop synchronized on SCLK.'),
        ('0x04', 'REJECTED', 'RW', 'Legacy rejected-write flag; any write clears it while ENABLE=0.'),
        ('0x05', 'CONFIG_ERROR', 'R/W1C', 'b0 write range/reserved encoding, b1 bad address, b2 split-field range at commit, b3 rule violation at commit, b4 break-before-make at commit, b5 commit while running, b6 legacy register locked.'),
        ('0x06', 'COMMIT', 'RW', 'Write 0x0001 = validate and commit shadow to active; 0x0002 = revert shadow to active; other values rejected. Read: b0 commit toggle, b1 last commit accepted, b2 shadow differs from active, b15:8 accepted-commit count.'),
        ('0x07', 'VIEW', 'RW', 'b0: 0 = generated registers read the shadow copy, 1 = the active copy.'),
        ('0x08', 'ABI_VERSION', 'R', '0x0002 (was 0x0001 for the pt_control map).'),
        ('0x09', 'MAP_HASH', 'R', 'Low 16 bits of the SHA-256 of the generated map; must match the bench header.'),
        ('0x0A', 'ISLAND_STATUS', 'R', 'b5:0 island effective-on (switch and power-good or override), b13:8 island power-good; SCLK-synchronized. Power-good = 1 with debug.island_power = 0 is the back-drive signature. Bit 3 (usb) is reserved and reads 0.'),
        ('0x0B', 'FAULT_STATUS', 'R', 'b0 monitor fault input, SCLK-synchronized.'),
        ('0x0D', 'RESET_STATUS', 'R/W1C', 'b0 POR occurred (set by POR, survives RESET_N), b1 reset occurred (set by POR or RESET_N). b1 with b0 clear after clearing both = a RESET_N-only reset. Flags live in the never-switched core domain; see macro-contract.md.'),
        ('0x0C', 'ERROR_INFO', 'R', 'b7:0 address of the last rejected write; b15:8 last commit result: 0 ok, 0x01-0x7F rule index+1, 0x80+i break-before-make field i, 0xC0+i split field i out of range, 0xFF non-live change while ENABLE=1.'),
        ('0x10-0x12', 'RF/WIRE/CLOCK_TRIM', 'RW', 'Legacy 16-bit trim words (wire_trim[15] selects PRBS, clock_trim[15] starts calibration); locked while ENABLE.'),
        ('0x20-0x26', 'MEMORY', 'mixed', 'Legacy capture/playback memory service, unchanged (SPI capture/playback is the last host-link fallback).'),
        ('0x30-0x3F', 'reserved', '-', 'Reserved for the recovery mailbox (not implemented). Writes rejected, reads 0.'),
    ]:
        a('| ' + ' | '.join(row) + ' |')
    a('')
    a('## Commit, reset and CDC')
    a('')
    a(model['commit_semantics'])
    a('')
    a(model['cdc_semantics'])
    a('')
    a('Reset: `rst_n` = RESET_N AND POR. It asynchronously returns every shadow and active register to')
    a('its declared default (the safe state): every island off, every driver tristated, every')
    a('termination and pull released, every ATB switch open, every clock select stopped. Release')
    a('reset with CS_N high and SCLK idle low; the first SCLK edge must follow reset release by the')
    a('cell recovery time.')
    a('')
    a('## Safety enforcement')
    a('')
    a(model['gating_rule'])
    a('')
    a(model['atb_policy'])
    a('')
    a(model['break_before_make_rule'])
    a('')
    a('Fault forcing (monitor `fault` input high): ' + ', '.join(
        f'`{n}`={v}' for n, v in model['fault_forced'].items()) + '.')
    a('')
    a('### Commit rules')
    a('')
    a('Class `pad` and `ownership` rules are in monotone form (their triggers are false and their')
    a('requirements true at code 0), so island isolation and fault release cannot break them; they')
    a('are proven on both the active registers and the pad-facing outputs. `legality` rules are')
    a('proven on the active registers.')
    a('')
    a('| # | Rule | Class | Node | If any | Then all |')
    a('| --- | --- | --- | --- | --- | --- |')

    def ctext(c):
        f = by_name[c[0]]
        vals = [f['values'][v] if f['values'] else v for v in c[2]]
        return f'{c[0]} {c[1]} {"/".join(map(str, vals))}'
    for i, r in enumerate(model['rules']):
        a(f"| {i + 1} | `{r['id']}` | {r['cls']} | {r['node'] or ''} | {'; '.join(ctext(c) for c in r['if_any'] + r['if_all'])} | {'; '.join(ctext(c) for c in r['then_all'])} |")
    a('')
    a('## Islands')
    a('')
    a('| Bit | Island | Effective-on |')
    a('| --- | --- | --- |')
    for isl, bit in model['islands'].items():
        a(f'| {bit} | {isl} | `debug.island_power.{isl}` AND (power-good[{bit}] OR `debug.pgood_override.{isl}`) |')
    a('')
    a('## ATB nodes')
    a('')
    a('| Code | Node | Island gate | Kind | ATB0 force |')
    a('| --- | --- | --- | --- | --- |')
    for n in model['atb_nodes']:
        force = {'sense_only': 'no (ATB1 only)', 'allowed': 'yes', 'override': f'with `debug.bias_override.{n.get("override")}`'}[n['force']]
        a(f"| {n['code']} | {n['name']} | {n['island'] or '-'} | {n['kind']} | {force} |")
    a('')
    a('## Observation mux codes')
    a('')
    a('DBG_OBS0/1 (`debug.dbg_obs.sel0/1`): 0 tristate, 1 constant 0, 2 constant 1, 3 commit toggle, ' +
      ', '.join(f'{4 + i} {s}' for i, s in enumerate(model['obs_status'])) +
      f', {4 + len(model["obs_status"])} combined reset level rst_n (1 = released).')
    a('')
    a('WDBG_OBS (`debug.wdbg_obs.select`): 0 tristate, 1 constant 0, 2 constant 1, ' +
      ', '.join(f'{3 + i} {s}' for i, s in enumerate(model['wire_status'])) + '.')
    a('')
    if model['status_fields']:
        a('## Read-only status registers')
        a('')
        a('Inputs to `pt_regfile`, synchronized into SCLK by two flops per bit. Gray-coded counters are converted '
          'to binary after synchronization. Writes to these addresses are rejected (CONFIG_ERROR b1).')
        a('')
        a('| Addr | Bits | Field | Port | Encoding | Meaning |')
        a('| --- | --- | --- | --- | --- | --- |')
        for sf in model['status_fields']:
            a(f"| 0x{sf['addr']:02X} | {sf['reg_lsb'] + sf['bits'] - 1}:{sf['reg_lsb']} | `{sf['name']}` | `{sf['port']}` | "
              f"{sf['encoding']} at source, binary on read | {'**RESERVED, reads 0.** ' if sf['reserved'] else ''}{sf['meaning'] or ''} |")
        a('')
    a('## Debug, consolidation and core group notes')
    a('')
    for g in model['groups']:
        if g['kind'] == 'debug' and g['description']:
            a(f"- **`{g['name']}`** (0x{g['registers'][0]:02X}): {g['description']}")
    a('')
    a('## Generated registers')
    a('')
    a('Access is RW to the shadow copy; reads return shadow or active per VIEW. Reset is the shadow')
    a('and active reset value. Island lists name the islands that must be on for the field to reach')
    a('its output; `live` fields may be committed while ENABLE=1.')
    a('')
    a('| Addr | Group | Bits | Field | Reset | Accepted | Islands | Bus |')
    a('| --- | --- | --- | --- | --- | --- | --- | --- |')
    for reg in regs:
        for name, fl, w, rl in reg['chunks']:
            f = by_name[name]
            part = f' [{fl + w - 1}:{fl}]' if f['split'] else ''
            bus = (f"{f['bus']}[{f['bus_lsb'] + f['bus_bits'] - 1}:{f['bus_lsb']}]" if f['bus'] else
                   'none (no hardware)' if f['store'] is None else 'atb one-hot')
            flags = ' (live)' if f['live'] else ''
            if f['store'] is None:
                flags += ' **reads 0, no hardware**'
            elif f['store'] != [f['bits'] - 1, 0]:
                flags += f" (bits {f['store'][0]}:{f['store'][1]} implemented)"
            a(f"| 0x{reg['addr']:02X} | `{reg['group']}` | {rl + w - 1}:{rl} | `{f['field']}`{part}{flags} | "
              f"{default_text(f)} | {field_range_text(f)} | {','.join(f['islands']) or '-'} | {bus} |")
    a('')
    trimmed = [f for f in fields if f['trim'] and 'keep' in f['trim']]
    dropped = [f for f in trimmed if f['store'] is None]
    a('## Hardware trim (pass-2 P2-2)')
    a('')
    a(f"{len(dropped)} fields ({sum(f['bits'] for f in dropped)} bits) have no hardware behind them: they keep their "
      'addresses, read 0, ignore writes and are absent from the output buses. '
      f"{len(trimmed) - len(dropped)} fields store only the bits that drive a port. Stored configuration: "
      f"{sum(f['store'][0] - f['store'][1] + 1 for f in fields if f['store'])} of {sum(f['bits'] for f in fields)} bits.")
    a('')
    a('| Field | Kept | Source | Reason |')
    a('| --- | --- | --- | --- |')
    for f in fields:
        if f['trim']:
            kept = ('forbidden ' + '/'.join(map(str, f['trim']['forbidden']))) if 'forbidden' in f['trim'] else \
                ('none' if f['store'] is None else f"[{f['store'][0]}:{f['store'][1]}]")
            a(f"| `{f['name']}` | {kept} | {f['trim']['source']} | {f['trim']['reason']} |")
    a('')
    a('## Fallback-route controls')
    a('')
    a('| Group | Fallback routes (`tapeout-readiness.json`) |')
    a('| --- | --- |')
    for g in model['groups']:
        if g['fallback_routes']:
            a(f"| `{g['name']}` | {', '.join(g['fallback_routes'])} |")
    return '\n'.join(L) + '\n'


def c_ident(text):
    return ''.join(ch if ch.isalnum() else '_' for ch in text).upper()


def emit_c(model):
    L = []
    a = L.append
    a('/* GENERATED by rtl/gen/gen_regfile.py; do not edit. Programmable transceiver control map. */')
    a('#ifndef PT_REGMAP_H')
    a('#define PT_REGMAP_H')
    a('')
    a('#define PT_SPI_CMD_WRITE 0x80u')
    a('#define PT_SPI_CMD_READ 0x00u')
    a('#define PT_ID_VALUE 0x5356u')
    a('#define PT_ABI_VERSION 0x0002u')
    a(f'#define PT_MAP_HASH 0x{model["map_hash16"]:04X}u')
    a('#define PT_COMMIT_CMD 0x0001u')
    a('#define PT_REVERT_CMD 0x0002u')
    sysaddr = {'ID': 0x00, 'ENABLE': 0x01, 'MODE8': 0x02, 'STATUS': 0x03, 'REJECTED': 0x04, 'CONFIG_ERROR': 0x05,
               'COMMIT': 0x06, 'VIEW': 0x07, 'ABI_VERSION_REG': 0x08, 'MAP_HASH_REG': 0x09, 'ISLAND_STATUS': 0x0A,
               'FAULT_STATUS': 0x0B, 'ERROR_INFO': 0x0C, 'RESET_STATUS': 0x0D, 'RF_TRIM': 0x10, 'WIRE_TRIM': 0x11, 'CLOCK_TRIM': 0x12,
               'MEM_INDEX': 0x20, 'MEM_PLAY_I': 0x21, 'MEM_WRITE': 0x22, 'MEM_CONTROL': 0x23, 'MEM_DONE': 0x24,
               'MEM_CAPTURE_LO': 0x25, 'MEM_CAPTURE_HI': 0x26}
    for k, v in sysaddr.items():
        a(f'#define PT_REG_{k} 0x{v:02X}u')
    for i, name in enumerate(['WRITE_RANGE', 'ADDRESS', 'SPLIT_RANGE', 'RULE', 'BREAK_BEFORE_MAKE', 'RUNNING', 'LEGACY_LOCKED']):
        a(f'#define PT_CONFIG_ERROR_{name} (1u << {i})')
    a('#define PT_RESET_STATUS_POR_OCCURRED (1u << 0)')
    a('#define PT_RESET_STATUS_RESET_OCCURRED (1u << 1)')
    a('#define PT_DBG_OBS_RESET_LEVEL 36u')
    for isl, bit in model['islands'].items():
        a(f'#define PT_ISLAND_{c_ident(isl)} {bit}u')
    a('')
    a('/* Fields: _ADDR is the first (least significant) register; fields wider than 16 bits')
    a('   continue in _ADDR+1, _ADDR+2 with 16 bits each. _SHIFT/_WIDTH locate the field in _ADDR. */')
    for f in model['fields']:
        p = 'PT_' + c_ident(f['name'])
        ch = f['chunks'][0]
        a(f'#define {p}_ADDR 0x{ch["addr"]:02X}u')
        a(f'#define {p}_SHIFT {ch["reg_lsb"]}u')
        a(f'#define {p}_WIDTH {f["bits"]}u')
        if not f['split']:
            a(f'#define {p}_MASK 0x{(((1 << f["bits"]) - 1) << ch["reg_lsb"]):04X}u')
        a(f'#define {p}_DEFAULT {f["default"]}u')
        a(f'#define {p}_IMPL_MASK 0x{f["store_mask"]:X}u  /* implemented bits; 0 = no hardware, reads 0 */')
        if f['values'] is not None:
            for i, v in enumerate(f['values']):
                a(f'#define {p}_{c_ident(str(v))} {i}u')
        else:
            a(f'#define {p}_MIN {f["minimum"]}u')
            a(f'#define {p}_MAX {f["maximum"]}u')
    a('')
    for sf in model['status_fields']:
        p = 'PT_' + c_ident(sf['name'])
        a(f'#define {p}_ADDR 0x{sf["addr"]:02X}u  /* read-only */')
        a(f'#define {p}_SHIFT {sf["reg_lsb"]}u')
        a(f'#define {p}_WIDTH {sf["bits"]}u')
    for n in model['atb_nodes']:
        a(f'#define PT_ATB_{c_ident(n["name"])} {n["code"]}u')
    a('')
    a('#endif')
    return '\n'.join(L) + '\n'


def emit_py(model):
    data = dict(FIELDS=model['fields'], REGISTERS=model['registers'], RULES=model['rules'],
                BREAK_BEFORE_MAKE=model['break_before_make'], SPLIT_FIELDS=model['split_fields'],
                FORCED=model['fault_forced'], ISLANDS=model['islands'], ATB_NODES=model['atb_nodes'],
                OBS_STATUS=model['obs_status'], STATUS_FIELDS=model['status_fields'], ATB_GROUPS=model['atb_groups'],
                STATUS_REGISTERS=model['status_registers'], WIRE_STATUS=model['wire_status'], MAP_HASH=model['map_hash16'],
                BUS_WIDTHS=model['bus_widths'], ATB_WIDTH=model['atb_width'])
    blob = json.dumps(data, sort_keys=True, separators=(',', ':'))
    return ('"""GENERATED by rtl/gen/gen_regfile.py; do not edit. Programmable transceiver control map\n'
            'and reference model for bench software. Data tables plus the semantics in regmap_runtime.py."""\n'
            'import json as _json\n\n'
            f"_DATA = _json.loads(r'''{blob}''')\n"
            'FIELDS = _DATA["FIELDS"]\nREGISTERS = _DATA["REGISTERS"]\nRULES = _DATA["RULES"]\n'
            'BREAK_BEFORE_MAKE = _DATA["BREAK_BEFORE_MAKE"]\nSPLIT_FIELDS = _DATA["SPLIT_FIELDS"]\n'
            'FORCED = _DATA["FORCED"]\nISLANDS = _DATA["ISLANDS"]\nATB_NODES = _DATA["ATB_NODES"]\n'
            'ATB_GROUPS = _DATA["ATB_GROUPS"]\nSTATUS_FIELDS = _DATA["STATUS_FIELDS"]\nSTATUS_REGISTERS = _DATA["STATUS_REGISTERS"]\n'
            'OBS_STATUS = _DATA["OBS_STATUS"]\nWIRE_STATUS = _DATA["WIRE_STATUS"]\nMAP_HASH = _DATA["MAP_HASH"]\n'
            'BUS_WIDTHS = _DATA["BUS_WIDTHS"]\nATB_WIDTH = _DATA["ATB_WIDTH"]\n'
            'FIELD_BY_NAME = {f["name"]: f for f in FIELDS}\n'
            'REGISTER_BY_ADDR = {r["addr"]: r for r in REGISTERS}\n\n'
            '# ---- verbatim copy of rtl/gen/regmap_runtime.py ----\n' + RUNTIME_SRC)


def emit_defs(model):
    return ('// GENERATED by rtl/gen/gen_regfile.py; do not edit.\n'
            f'`define PT_ANALOG_CFG_W {model["bus_widths"]["analog"]}\n'
            f'`define PT_DEBUG_CFG_W {model["bus_widths"]["debug"]}\n'
            f'`define PT_ATB_W {model["atb_width"]}\n'
            f'`define PT_ISLAND_W {len(model["islands"])}\n'
            f'`define PT_ATB0_GRP_W {len(model["atb_groups"]["atb0"])}\n'
            f'`define PT_ATB1_GRP_W {len(model["atb_groups"]["atb1"])}\n'
            f'`define PT_MAP_HASH 16\'h{model["map_hash16"]:04X}\n'
            '// Field positions in analog_cfg (PT_A_*) and debug_cfg (PT_D_*): _LSB and _W.\n' +
            ''.join(f'`define PT_{"A" if f["bus"] == "analog" else "D"}_{f["sv"].upper()}_LSB {f["bus_lsb"]}\n'
                    f'`define PT_{"A" if f["bus"] == "analog" else "D"}_{f["sv"].upper()}_W {f["bus_bits"]}\n'
                    for f in model['fields'] if f['bus']))


def emit_json(model):
    out = dict(model)
    out['fields'] = [{k: v for k, v in f.items()} for f in model['fields']]
    return json.dumps(out, indent=1, sort_keys=True) + '\n'


def outputs(model):
    return {
        P / 'spec/register-map.json': emit_json(model),
        P / 'spec/register-map.md': emit_markdown(model),
        P / 'rtl/pt_regfile.sv': emit_sv(model),
        P / 'rtl/pt_regmap_defs.svh': emit_defs(model),
        P / 'rtl/gen/pt_regmap.h': emit_c(model),
        P / 'rtl/gen/pt_regmap.py': emit_py(model),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--check', action='store_true', help='fail if any generated output is stale')
    args = ap.parse_args()
    try:
        model = build_model()
    except SpecError as e:
        print(f'specification error: {e}', file=sys.stderr)
        return 2
    stale = []
    for path, text in outputs(model).items():
        if args.check:
            if not path.is_file() or path.read_text() != text:
                stale.append(str(path.relative_to(P)))
        else:
            path.write_text(text)
    regs = model['registers']
    print(json.dumps(dict(registers=len(regs), fields=len(model['fields']),
                          field_bits=sum(f['bits'] for f in model['fields']), rules=len(model['rules']),
                          debug_registers=f"0x40-0x{model['last_debug']:02X}",
                          analog_registers=f"0x60-0x{model['last_analog']:02X}",
                          analog_cfg_bits=model['bus_widths']['analog'], debug_cfg_bits=model['bus_widths']['debug'],
                          atb_nodes=model['atb_width'], map_hash=f"0x{model['map_hash16']:04X}",
                          stale=stale)))
    return 1 if stale else 0


if __name__ == '__main__':
    sys.exit(main())
