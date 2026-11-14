#!/usr/bin/env python3
"""Chip-top connectivity regression (one command, exits non-zero on any finding).

Reads pt_chip.conn (the one chip-level connectivity), masters.txt (where each block's published pin list is),
ctl_ports.txt (every control port the digital macro must present) and compares against the block netlists,
the v6 floorplan, spec/register-map.json and rtl/pt_digital_macro.sv.

Checks (each has a count; all must be 0 for PASS):
  unbound      pin of a published subckt that pt_chip.conn does not bind, or a bound pin the subckt lacks
  dangling     net with one connection that is not a bond pad
  undriven     net with loads (=) and no driver (>), no analog member (~), not a supply
  multidrive   net with more than one driver (>)
  missing      v6 floorplan block without an instance (and instances the floorplan lacks, reported separately)
  crossing     digital signal leaving a switched island without an iso cell or a waiver
  alwayson     input of an always-on (core/chip) instance driven from a switched island, or not driven
  pn           P/N or I/Q crossed between a block's pin names and its net names, or a *_P chip pin bonded to an N pad leg
               (`swap <inst>.<pin-regex> <reason>` declares an intended swap)
  order        a pin bus (ct0..3, CODE0..9) bound to a net bus out of order
  ctl          c_* net vs ctl_ports.txt (unknown port, width, gaps), table rows nobody uses
  cfg          ctl_ports.txt vs spec/register-map.json: second, independent derivation of the cfg binding
               (field missing / dropped from the bus, width or reset different, decode not in the macro)
  macro        target macro port list (conn) vs rtl/pt_digital_macro.sv
  supply       an instance's supply pin is not the rail of its declared island
  iso          clamp ISO is not island_off[] of the island that drives it, or the clamp is not in the receiver's island
  demand       instances of blocks that do not exist yet
  staged       instances bound to an owner's staged pin contract that the published netlist does not match yet
Also runs the three mode-walk scripts' self-tests (scratch/reviews/mode-walk) when present.
--selftest injects one fault per check into a copy of the inputs and requires each to be reported.
--write regenerates generated/pt_analog_top.spice and generated/pt_analog_top.sv.
"""
import re, sys, os, json, itertools, collections, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.dirname(os.path.dirname(HERE)); ROOT = os.path.dirname(os.path.dirname(P))
PREFIX = {'A/': P+'/analog/', 'IS/': ROOT+'/scratch/island-support-20261108-075605/', 'IF/': ROOT+'/scratch/iso-family/'}
SUPPLY = re.compile(r'^(VDD|VSS|AGND_RX|RAIL_\w+|VREG_\w+|VDD_LO)$')
# supply island -> enable group bit (island_en / island_on / island_off index); spec/power-delivery.md section 2
GROUP_BIT = {'wired_rx': 0, 'wired_cap': 0, 'wired_tx': 0, 'rf_rx': 1, 'rf_tx': 1, 'lod': 1, 'lo': 1, 'pll': 2, 'conv': 4, 'debug': 5}
GROUP_NAME = {0: 'wired', 1: 'rf', 2: 'pll', 4: 'conv', 5: 'debug'}
ALWAYS_ON = ('core', 'chip')
FP6 = ROOT+'/scratch/chip-assembly-v6/run/floorplan-v6.json'
# floorplan name -> instance name where they differ; floorplan entries that are not blocks
FP_ALIAS = {'clk_obs16': 'clk_obs', 'obs_pre4': 'obs_pre4_wire', 'wordclk': 'wordclk_rx', 'isw_wired': 'isw_wired_cap', 'isw_rf': 'isw_rf_rx', 'atb0_pad': 'atb0_pad', 'atb1_pad': 'atb1_pad'}
FP_SKIP = re.compile(r'^(leaf_[fs]\d+|atb_grp\d+|.*_rsv|digital|polyphase|rx_wclk_in)$')     # deleted by user decisions CP4-2 / CP4-3 (2026-11-14)


MC = '<macroclamp>'
SW = '<swap>'


def expand_items(body):
    out = []
    for it in body.split(','):
        m = re.fullmatch(r'(-?\d+):(-?\d+)', it)
        out += [str(k) for k in range(int(m.group(1)), int(m.group(2))+1)] if m else [it]
    return out


def groups(s):
    return [expand_items(b) for b in re.findall(r'\{([^{}]*)\}', s)]


def subst(s, vals):
    def r(m):
        v = vals[int(m.group(2))-1]
        return v.upper() if m.group(1) else v
    return re.sub(r'\\(U?)(\d)', r, s)


def fill(s, choice):
    it = iter(choice)
    return re.sub(r'\{[^{}]*\}', lambda m: next(it), s)


def parse(text):
    """-> instances {name: dict(master, group, flags, pins{pin: (kind, net)})}, ports set, waivers [(regex, text)], errors"""
    inst, ports, waive, err = collections.OrderedDict(), [], [], []
    cur = []           # list of (instance name, name-group values, index, count)
    for ln, raw in enumerate(text.split('\n'), 1):
        line = raw.split('#')[0].rstrip()
        if not line.strip():
            continue
        t = line.split()
        if not raw[0].isspace():
            if t[0] == 'port':
                g = groups(t[1])
                ports += [fill(t[1], c) for c in itertools.product(*g)]
                cur = []
            elif t[0] == 'waive':
                waive.append((t[1], ' '.join(t[2:])))
                cur = []
            elif t[0] == 'swap':
                waive.append((SW, t[1], ' '.join(t[2:])))
                cur = []
            elif t[0] == 'macroclamp':
                waive.append((MC, t[1], t[2]))
                cur = []
            elif t[0] == 'inst':
                g = groups(t[1]); combos = list(itertools.product(*g)); cur = []
                for i, c in enumerate(combos):
                    name = fill(t[1], c)
                    if name in inst:
                        err.append(f'line {ln}: duplicate instance {name}')
                    inst[name] = dict(master=subst(t[2], c), group=subst(t[3], c), flags=t[4:], pins=collections.OrderedDict(), line=ln)
                    cur.append((name, c, i, len(combos)))
            else:
                err.append(f'line {ln}: unknown statement {t[0]}')
            continue
        for tok in t:
            m = re.fullmatch(r'([^=>~]+)([=>~])(.+)', tok)
            if not m or not cur:
                err.append(f'line {ln}: bad token {tok}'); continue
            lhs, kind, rhs = m.groups()
            lg = groups(lhs); lcomb = list(itertools.product(*lg)); M = len(lcomb)
            for name, ic, ii, N in cur:
                for pi, pc in enumerate(lcomb):
                    vals = list(ic)+list(pc)
                    pin = subst(fill(lhs, pc), vals)
                    r = rhs; rg = groups(r)
                    if rg:
                        ch = []
                        for items in rg:
                            n = len(items)
                            if n == M*N and N > 1 and M > 1: ch.append(items[ii*M+pi])
                            elif M > 1 and M % n == 0: ch.append(items[pi % n])
                            elif n == N: ch.append(items[ii])
                            else:
                                err.append(f'line {ln}: {tok}: right-side group of {n} does not fit {M} pins x {N} instances'); ch.append(items[0])
                        r = fill(r, ch)
                    net = subst(r, vals)
                    if pin in inst[name]['pins']:
                        err.append(f'line {ln}: {name}.{pin} bound twice')
                    if net == '-' and kind == '=':
                        err.append(f'line {ln}: {name}.{pin}: an input cannot be a no-connect')
                    inst[name]['pins'][pin] = (kind, net)
    return inst, set(ports), waive, err


def load_masters(text):
    out = {}
    for line in text.split('\n'):
        t = line.split('#')[0].split()
        if not t or t[0] != 'master':
            continue
        if t[2] == 'inline': out[t[1]] = dict(kind='inline', pins=t[3:])
        elif t[2] == 'demand': out[t[1]] = dict(kind='demand', owner=t[3], pins=t[4:])
        elif t[2] == 'target': out[t[1]] = dict(kind='target', pins=None)
        elif t[2] == 'staged':
            path, sub = t[3].rsplit(':', 1)
            for k, v in PREFIX.items():
                if path.startswith(k): path = v+path[len(k):]
            out[t[1]] = dict(kind='staged', path=path, sub=sub, pins=t[4:])
        else:
            path, sub = t[2].rsplit(':', 1)
            for k, v in PREFIX.items():
                if path.startswith(k): path = v+path[len(k):]
            out[t[1]] = dict(kind='file', path=path, sub=sub, pins=None)
    return out


_cache = {}
def subckt_pins(path, sub):
    if path not in _cache:
        try: _cache[path] = re.sub(r'\n\+\s*', ' ', open(path).read())
        except OSError: _cache[path] = None
    if _cache[path] is None: return None
    m = re.search(r'^\.subckt\s+'+re.escape(sub)+r'[ \t]+([^\n]*)', _cache[path], re.M | re.I)
    return [p for p in m.group(1).split() if '=' not in p] if m else None


def rtl_macro_ports(text):
    head = re.sub(r'//[^\n]*', '', text[text.index('module pt_digital_macro('):])
    head = head[:head.index(');')]
    defs = dict(re.findall(r'`define\s+(PT_\w+_W)\s+(\d+)', open(P+'/rtl/pt_regmap_defs.svh').read()))
    out, d, w = {}, None, 1
    for tok in re.findall(r'\[[^\]]*\]|[A-Za-z_]\w*', head.split('(', 1)[1]):
        if tok in ('input', 'output', 'inout'): d, w = tok, 1
        elif tok == 'wire': w = 1
        elif tok.startswith('['):
            e = tok[1:-1].split(':')[0]
            for k, v in defs.items(): e = e.replace('`'+k, v)
            w = eval(e)+1
        else: out[tok] = (d, w)
    return out


def c_key(p):
    m = re.fullmatch(r'(\w+)\[(\d+)\]', p)
    return (m.group(1), int(m.group(2))) if m else (p, -1)


def bus(net):
    m = re.fullmatch(r'(\w+)\[(\d+)\]', net)
    return (m.group(1), int(m.group(2))) if m else (net, None)


def load_ctl(text):
    rows = collections.OrderedDict()
    for line in text.split('\n'):
        if not line.strip() or line.startswith('#'): continue
        c = [x.strip() for x in line.split('|')]
        rows[c[0]] = dict(width=int(c[1]), reset=int(c[2], 0), enc=c[3], field=c[4], note=c[5] if len(c) > 5 else '')
    return rows


def check(conn, masters_txt, ctl_txt, regmap, rtl, fp6):
    R = collections.OrderedDict((k, []) for k in ('syntax unbound dangling undriven multidrive missing crossing alwayson supply iso pn order ctl cfg macro demand staged'.split()))
    info = collections.OrderedDict()
    inst, ports, waive, err = parse(conn)
    R['syntax'] += err
    masters = load_masters(masters_txt)
    # --- pins vs published subckts
    for name, i in inst.items():
        m = masters.get(i['master'])
        if m is None:
            R['unbound'].append(f'{name}: master {i["master"]} not in masters.txt'); continue
        if m['kind'] == 'target': continue
        pins = m['pins'] if m['kind'] != 'file' else subckt_pins(m['path'], m['sub'])
        if m['kind'] == 'staged' and subckt_pins(m['path'], m['sub']) != pins:
            R['staged'].append(f'{name} ({i["master"]}): bound to the owner\'s staged pin list; the published {os.path.relpath(m["path"], P)} still differs')
        if pins is None:
            R['unbound'].append(f'{name}: cannot read .subckt {m["sub"]} in {m["path"]}'); continue
        for p in pins:
            if p not in i['pins']: R['unbound'].append(f'{name}.{p} ({i["master"]}) not bound')
        for p in i['pins']:
            if p not in pins: R['unbound'].append(f'{name}.{p}: {i["master"]} has no such pin (stale binding)')
        if m['kind'] == 'demand' or 'demand' in i['flags']:
            R['demand'].append(f'{name} ({i["master"]}, owner {m.get("owner", "?")})')
    # --- nets
    nets = collections.defaultdict(list)
    for name, i in inst.items():
        for p, (k, n) in i['pins'].items():
            if n != '-': nets[n].append((name, p, k))
    ctl = load_ctl(ctl_txt)
    cbits = collections.defaultdict(set)
    mc_used = {}
    for n, users in nets.items():
        base, idx = bus(n)
        if base.startswith('c_'):
            cbits[base].add(idx)
            bad = [u for u in users if u[2] != '=']
            if bad: R['multidrive'].append(f'{n}: control net also driven/analog at {bad[0][0]}.{bad[0][1]}')
            continue
        if SUPPLY.match(n): continue
        drv = [u for u in users if u[2] == '>']; ana = [u for u in users if u[2] == '~']; ld = [u for u in users if u[2] == '=']
        if len(users) == 1 and n not in ports and not n.startswith('ESD_RAIL_'):     # ESD_RAIL_* = pad-local clamp rail
            R['dangling'].append(f'{n}: only {users[0][0]}.{users[0][1]}')
        if len(drv) > 1: R['multidrive'].append(f'{n}: ' + ', '.join(f'{a}.{b}' for a, b, _ in drv))
        if ld and not drv and not ana and n not in ports: R['undriven'].append(f'{n}: loads {ld[0][0]}.{ld[0][1]}' + (f' +{len(ld)-1}' if len(ld) > 1 else ''))
        if drv and not ld and not ana and len(users) > 1: R['dangling'].append(f'{n}: drivers only')
        # island crossings and always-on inputs (digital signals only)
        if drv:
            dname, dpin, _ = drv[0]; dg = inst[dname]['group']
            for lname, lpin, _ in ld:
                lg = inst[lname]['group']
                if dg in ALWAYS_ON or dg == lg or GROUP_BIT.get(dg, -1) == GROUP_BIT.get(lg, -2): continue      # same enable group
                if inst[lname]['master'].startswith('iso_') and lpin == 'A': continue
                if any(re.fullmatch(w[0], f'{lname}.{lpin}') for w in waive if w[0] not in (MC, SW)): continue
                if lname == 'digital':      # CP4-1: clamped inside the macro, if a macroclamp line of the DRIVING island names the pin
                    hit = [w for w in waive if w[0] == MC and re.fullmatch(w[2], lpin)]
                    if hit and hit[0][1] == GROUP_NAME[GROUP_BIT[dg]]: mc_used[lpin] = hit[0][1]; continue
                    if hit: R['iso'].append(f'digital.{lpin}: macroclamp says island {hit[0][1]} but the driver {dname}.{dpin} is on {dg}'); continue
                (R['alwayson'] if lg in ALWAYS_ON else R['crossing']).append(f'{n}: {dname}.{dpin} ({dg}) -> {lname}.{lpin} ({lg}) without an iso cell')
    for name, i in inst.items():        # every input of an always-on instance must have a defined source
        if i['group'] in ALWAYS_ON:
            for p, (k, n) in i['pins'].items():
                if k == '=' and not SUPPLY.match(n) and not bus(n)[0].startswith('c_') and not any(u[2] == '>' for u in nets[n]):
                    R['alwayson'].append(f'{name}.{p}: always-on input on net {n} has no driver')
    BIT = GROUP_BIT
    def rail_ok(g, n):
        return n == 'VDD' if g in ALWAYS_ON else (n == 'RAIL_'+g or (g == 'pll' and n in ('VREG_TX', 'VREG_CDR')) or (g == 'lo' and n == 'VDD_LO'))
    for name, i in inst.items():
        if i['group'] not in ALWAYS_ON and i['group'] not in GROUP_BIT: R['supply'].append(f'{name}: unknown island {i["group"]}')
    for name, i in inst.items():        # supply pin net must match the instance's declared island
        for p in ('VDD', 'VDD_WIRE_SW', 'VDD_PLL_SW', 'vdd3v3', 'DVDD'):
            if p in i['pins'] and not rail_ok(i['group'], i['pins'][p][1]) and i['master'] != 'pt_wtx_fallback_control':
                R['supply'].append(f'{name}.{p} = {i["pins"][p][1]} but the instance is declared on island {i["group"]}')
        for p in ('VSS', 'vss', 'DVSS', 'GND'):        # grounds: VSS everywhere; AGND_RX only where power-delivery 5.2 puts it
            if p in i['pins'] and i['pins'][p][1] not in ('VSS', '-'):
                if not (i['pins'][p][1] == 'AGND_RX' and name in ('lna', 'pad_rf_rx')):
                    R['supply'].append(f'{name}.{p} = {i["pins"][p][1]}: ground pin not on VSS (AGND_RX is allowed on lna and pad_rf_rx only)')
        if i['master'].startswith('iso_clamp'):     # ISO = island_off[bit of the island that drives A]; supply = receiver island
            a, iso, y = i['pins']['A'][1], i['pins']['ISO'][1], i['pins']['Y'][1]
            d = [u for u in nets.get(a, []) if u[2] == '>']
            dg = inst[d[0][0]]['group'] if d else None
            # an already-clamped core net (e.g. CONV_CLK from the pll island) keeps its source island
            if dg in BIT and iso != f'island_off[{BIT[dg]}]':
                R['iso'].append(f'{name}: A is driven from island {dg} but ISO = {iso} (must be island_off[{BIT[dg]}])')
            if dg not in BIT:
                R['iso'].append(f'{name}: A net {a} is not driven from a switched island (clamp has no purpose or the driver is missing)')
            lg = {inst[u[0]]['group'] for u in nets.get(y, []) if u[2] == '=' }
            lg = {('core' if g in ALWAYS_ON else g) for g in lg}
            mine = 'core' if i['group'] in ALWAYS_ON else i['group']
            if y != '-' and mine != 'core' and lg and {GROUP_BIT.get(g, g) for g in lg} != {GROUP_BIT[mine]}:     # a core-rail clamp output may go anywhere
                R['iso'].append(f'{name}: clamp is on {mine} but its output loads are on {sorted(lg)}')
            if mine == dg or GROUP_BIT.get(mine, -1) == GROUP_BIT.get(dg, -2):
                R['iso'].append(f'{name}: clamp sits in the enable group that drives it ({dg}); it must be in the receiver domain')
        if i['master'] == 'iso_pd' and not re.fullmatch(r'island_off\[\d\]|c_\w+', i['pins']['ISO'][1]):
            R['iso'].append(f'{name}: iso_pd ISO = {i["pins"]["ISO"][1]}')
    # --- polarity and bit order, derived from the names on both sides (decisions.md section C)
    def partner(name):          # 'rf_out_p' <-> 'rf_out_n', 'INP' <-> 'INN', 'LOI_IP' <-> 'LOI_IN', 'USB_DP' <-> 'USB_DN'
        m = re.fullmatch(r'(.*?)([PpNn])((?:\[\d+\])?)', name)
        if not m: return None, None
        c = m.group(2); o = {'P': 'N', 'N': 'P', 'p': 'n', 'n': 'p'}[c]
        return m.group(1)+o+m.group(3), c.upper()
    swaps = [w[1] for w in waive if w[0] == SW]
    for name, i in inst.items():
        pins = i['pins']
        for p, (k, n) in pins.items():
            q, pol = partner(p)
            if pol != 'P' or q not in pins or n == '-' or SUPPLY.match(n): continue
            n2 = pins[q][1]; nq, npol = partner(n)
            if nq is None or n2 not in (nq, n): continue          # the two nets are not a named P/N pair: nothing to derive
            if n2 == n: R['pn'].append(f'{name}: {p} and {q} are both on {n}'); continue
            sw = any(re.fullmatch(rx, f'{name}.{p}') for rx in swaps)
            if (npol == 'N') != sw:
                R['pn'].append(f'{name}: {p} -> {n} and {q} -> {n2}: P/N ' + ('declared swapped but bound straight' if sw else 'swapped (no `swap` line)'))
        m = re.fullmatch(r'.*_([iq])(_\d+)?', name)             # I/Q: an instance named *_i must not sit on a Q-named net
        if m and not i['master'].startswith(('iso_', 'atb_')):
            for p, (k, n) in pins.items():
                mm = re.match(r'(?:BB|ADC|DAC|TX|RFA_|LO_|BIAS_\w+_)([IQiq])(?:[_PN\[]|$)', n)
                if mm and mm.group(1).lower() != m.group(1) and not n.startswith('BIAS_'):
                    R['pn'].append(f'{name}.{p} is on {n}: I/Q crossed')
                mm = re.fullmatch(r'(?:c_|BIAS_)\w*?_([iq])(?:_\w+)?(?:\[\d+\])?', n)      # control / bias nets named for the other channel
                if mm and mm.group(1) != m.group(1) and re.search(r'_[iq](_|$|\[)', n):
                    R['pn'].append(f'{name}.{p} is on {n}: I/Q crossed (control or bias net of the other channel)')
        grp = collections.defaultdict(list)                     # pin buses: ct0..ct3, CODE0..9, T3_0..4, D0..39
        for p, (k, n) in pins.items():
            mp = re.fullmatch(r'(.*?)(\d+)', p); b, idx = bus(n)
            if mp and idx is not None: grp[(mp.group(1), b)].append((int(mp.group(2)), idx))
        for (stem, b), v in grp.items():
            if len(v) < 2: continue
            v.sort(); d = [(v[j+1][1]-v[j][1], v[j+1][0]-v[j][0]) for j in range(len(v)-1)]
            even = len({dp for _, dp in d}) == 1         # D2/D4/D8/D16-style names: only the order can be checked
            if any(dn <= 0 or (even and dn != d[0][0]) for dn, dp in d):
                R['order'].append(f'{name}: pins {stem}{v[0][0]}..{v[-1][0]} -> {b}{[x[1] for x in v]}: not in rising order with a constant step')
    for port in sorted(ports):                                  # bond pads: a *_P chip pin must land on a pad cell's P leg
        for u in nets.get(port, []):
            if inst[u[0]]['master'].startswith('pad_') and re.fullmatch(r'PAD_[PN]', u[1]):
                q, pol = partner(port)
                if pol and u[1][-1] != pol and q in ports: R['pn'].append(f'{port} is bonded to {u[0]}.{u[1]}')
    try:        # bond map (spec/contract.json bond_map_current) vs the chip ports of the conn: names only, information
        bm = json.load(open(P+'/spec/contract.json'))
        def find(o):
            if isinstance(o, dict):
                if 'bond_map_current' in o: return o['bond_map_current']
                for v in o.values():
                    r = find(v)
                    if r: return r
        bm = find(bm) or {}
        names = {re.split(r'[ (]', v)[0] for side in ('west', 'east', 'north') for v in bm.get(side, {}).values()}
        names = {x for x in names if re.fullmatch(r'[A-Z][A-Z0-9_]*', x)}
        host = {p for p in ports if re.match(r'(RESET_N|SPI_|H2D|D2H|VDD$|VSS$)', p)}
        info['bond map vs conn ports'] = dict(in_map_not_in_conn=sorted(names-ports), in_conn_not_in_map=sorted(ports-names-host))
    except Exception as e:
        info['bond map vs conn ports'] = f'not checked ({e})'
    ana = []
    for n, users in nets.items():       # analog nets that span two switched islands with no iso_pd on them (information, D-ANA)
        if SUPPLY.match(n) or n in ports: continue
        gs = {GROUP_NAME[GROUP_BIT[inst[u[0]]['group']]] for u in users if u[2] == '~' and inst[u[0]]['group'] in GROUP_BIT and not inst[u[0]]['master'].startswith(('atb_', 'iso_pd', 'pad_'))}
        if len(gs) > 1 and not any(inst[u[0]]['master'] == 'iso_pd' for u in users): ana.append(f'{n} ({"/".join(sorted(gs))})')
    info['analog nets across two islands without iso_pd'] = sorted(ana)
    info['intentional no-connects'] = sum(1 for i in inst.values() for k, n in i['pins'].values() if n == '-')
    info['waived crossings'] = [f'{w[0]}: {w[1]}' for w in waive if w[0] not in (MC, SW)]
    info['declared P/N swaps'] = [f'{w[1]}: {w[2]}' for w in waive if w[0] == SW]
    info['macro-internal clamps (CP4-1)'] = dict(collections.Counter(mc_used.values()))
    for p in inst['digital']['pins']:       # a macroclamp line that names a pin not driven from that island is stale
        hit = [w for w in waive if w[0] == MC and re.fullmatch(w[2], p)]
        if hit and p not in mc_used: R['iso'].append(f'digital.{p}: macroclamp line ({hit[0][1]}) but the pin is not driven from a switched island')
    info['_macroclamp'] = mc_used
    # --- missing instances
    want = [w for w in list(fp6['placed'])+list(fp6['failures']) if not FP_SKIP.match(w)]
    for w in want:
        if FP_ALIAS.get(w, w) not in inst: R['missing'].append(f'v6 floorplan block {w} has no instance')
    fpn = {FP_ALIAS.get(w, w) for w in want}
    info['instances not in the v6 floorplan'] = sorted({re.sub(r'_?\d+$', '', n) if n.startswith('iso_') else n for n, i in inst.items()
        if n not in fpn and i['group'] != 'chip' and not n.startswith(('atb', 'pad_'))})
    # --- control ports
    for base, idxs in sorted(cbits.items()):
        w = 1 if idxs == {None} else (max(idxs)+1 if None not in idxs else -1)
        if base not in ctl: R['ctl'].append(f'{base}[{w}] used in pt_chip.conn but not in ctl_ports.txt'); continue
        if w != ctl[base]['width']: R['ctl'].append(f'{base}: conn uses width {w}, ctl_ports.txt says {ctl[base]["width"]}')
        if w > 1 and idxs != set(range(w)): R['ctl'].append(f'{base}: bits {sorted(set(range(w))-idxs)} have no consumer')
    for base in ctl:
        if base not in cbits: R['ctl'].append(f'{base}: in ctl_ports.txt, no consumer pin in pt_chip.conn')
    cons = collections.defaultdict(set)
    for n, users in nets.items():
        b0 = bus(n)[0]
        if b0.startswith('c_'): cons[b0] |= {GROUP_BIT[inst[u[0]]['group']] for u in users if inst[u[0]]['group'] in GROUP_BIT}
    for base, c in ctl.items():         # an island_on[k] named in the encoding must be the enable group of a consumer
        named = {int(x) for x in re.findall(r'island_on\[(\d)', c['enc'])}
        if named and cons.get(base) and not named & cons[base] and '[2 or 5]' not in c['enc']:
            R['ctl'].append(f'{base}: encoding gates with island_on{sorted(named)} but its consumers are on enable group(s) {sorted(cons[base])}')
    # --- second derivation: register map -> ports
    fields = {f['name']: f for f in regmap['fields']}
    for base, c in ctl.items():
        if c['field'] in ('', '-'):
            R['cfg'].append(f'{base}: no register field exists ({c["enc"]})'); continue
        for fn in c['field'].split('+'):
            f = fields.get(fn)
            if f is None: R['cfg'].append(f'{base}: field {fn} not in register-map.json'); continue
            if f['bus'] is None: R['cfg'].append(f'{base}: field {fn} is dropped from the bus'); continue
            if c['enc'] == 'direct':
                if f['bus_bits'] != c['width']: R['cfg'].append(f'{base}: width {c["width"]} vs field {fn} {f["bus_bits"]} bus bits')
                elif (f.get('default') or 0) != c['reset']: R['cfg'].append(f'{base}: cell-safe reset {c["reset"]} vs field {fn} default {f.get("default")}')
        if c['enc'] != 'direct' and base not in rtl: R['cfg'].append(f'{base}: needs "{c["enc"]}" of {c["field"]}; no such decode port on the macro')
    # --- macro ports
    target = collections.defaultdict(set)
    for p in inst['digital']['pins']:
        b, i = bus(p); target[b].add(i)
    for b in cbits: target[b] |= cbits[b]
    for b, idxs in sorted(target.items()):
        w = 1 if idxs == {None} else max(i for i in idxs if i is not None)+1
        if b not in rtl: R['macro'].append(f'macro lacks port {b}[{w}]')
        elif rtl[b][1] != w: R['macro'].append(f'macro port {b}: width {rtl[b][1]} in RTL, {w} in the top')
    for b in rtl:
        if b not in target: R['macro'].append(f'macro port {b}[{rtl[b][1]}] has no connection in the top (remove, or state its consumer)')
    info['instances'] = len(inst); info['pins bound'] = sum(len(i['pins']) for i in inst.values())
    info['control ports (c_*)'] = f'{len(cbits)} ports, {sum(len(v) for v in cbits.values())} bits'
    return R, info, inst, masters, nets, ports


def write_outputs(inst, masters, nets, ports):
    OUT = os.environ.get('PT_TOP_OUT', HERE+'/generated'); os.makedirs(OUT, exist_ok=True)
    inside = {n for n, i in inst.items() if i['group'] != 'chip'}
    top = []      # nets that leave the analog top
    for n, users in nets.items():
        if SUPPLY.match(n) and not n in ('VDD', 'VSS'): continue
        if n in ports or any(u[0] not in inside for u in users) or bus(n)[0].startswith('c_'):
            if any(u[0] in inside for u in users): top.append(n)
    key = lambda n: (bus(n)[0], bus(n)[1] or 0)
    top = sorted(set(top), key=key)
    L = ['* pt_analog_top: GENERATED from integration/top/pt_chip.conn by check_top.py --write. Do not edit.',
         '* Structural only: block subckts come from the files in masters.txt. NC_* = intentional no-connect.',
         '.subckt pt_analog_top '+' '.join(top)]
    nc = 0
    order = [n for n in inst if n in inside]
    for name in order:
        i = inst[name]; m = masters[i['master']]
        pins = m['pins'] if m['kind'] != 'file' else subckt_pins(m['path'], m['sub'])
        row = []
        for p in pins or list(i['pins']):
            n = i['pins'].get(p, ('', 'UNBOUND'))[1]
            if n == '-': nc += 1; n = f'NC_{name}_{p}'
            row.append(n)
        L.append(f'X{name} '+' '.join(row)+' '+(m.get('sub') or i['master'])+('   * DEMAND' if m['kind'] == 'demand' else ''))
    L.append('.ends pt_analog_top')
    open(OUT+'/pt_analog_top.spice', 'w').write('\n'.join(L)+'\n')
    b = collections.OrderedDict()
    for n in top:
        base, idx = bus(n); b.setdefault(base, set()).add(idx)
    def direction(base):
        us = [u for n in nets if bus(n)[0] == base for u in nets[n]]
        if base in ports or any(u[2] == '~' for u in us) or SUPPLY.match(base): return 'inout'
        return 'output' if any(u[2] == '>' and u[0] in inside for u in us) else 'input'
    V = ['// pt_analog_top black box: GENERATED from integration/top/pt_chip.conn by check_top.py --write. Do not edit.',
         '(* blackbox *) module pt_analog_top(']
    V.append(',\n'.join(f' {direction(base)} wire{"" if idxs == {None} else " ["+str(max(idxs))+":0]"} {base}' for base, idxs in b.items()))
    V.append(');\nendmodule')
    open(OUT+'/pt_analog_top.sv', 'w').write('\n'.join(V)+'\n')
    # behavioural stub for the boundary sim (sim/tb_top_boundary.sv): every block input is a named probe wire
    # p_<inst>__<pin>; island switch PG = EN; iso clamp Y = A & !ISO; POR released; every other output 0.
    vn = lambda n: n if bus(n)[1] is None else f'{bus(n)[0]}[{bus(n)[1]}]'
    S = ['// pt_analog_top_stub: GENERATED from pt_chip.conn by check_top.py --write (stub for sim/tb_top_boundary.sv). Do not edit.',
         '`default_nettype wire', 'module pt_analog_top_stub(']
    S.append(',\n'.join(f' {direction(base)} wire{"" if idxs == {None} else " ["+str(max(idxs))+":0]"} {base}' for base, idxs in b.items()))
    S.append(');')
    internal = collections.OrderedDict()
    for n in nets:
        base, idx = bus(n)
        if base not in b and not SUPPLY.match(base): internal.setdefault(base, set()).add(idx)
    for base, idxs in internal.items():
        S.append(f' wire{"" if idxs == {None} else " ["+str(max(idxs))+":0]"} {base};')
    S.append(' wire ' + ', '.join(f'{n} = {"VSS" if n == "AGND_RX" else "VDD"}' for n in sorted(nets) if SUPPLY.match(n) and n not in ('VDD', 'VSS')) + ';')
    for name in order:
        i = inst[name]; pin = i['pins']
        for p, (k, n) in pin.items():
            if k == '=': S.append(f' wire p_{name}__{re.sub(chr(92)+"W", "_", p)} = {vn(n)};')
            elif k == '>' and n != '-':
                if i['master'].startswith('isw_'): e = pin['EN'][1]; v = vn(e) if p == 'PG' else '~'+vn(e)
                elif i['master'].startswith('iso_clamp'): v = f'{vn(pin["A"][1])} & ~{vn(pin["ISO"][1])}'
                elif i['master'] == 'por': v = "1'b1"
                else: v = "1'b0"
                S.append(f' assign {vn(n)} = {v};')
    S.append('endmodule')
    open(OUT+'/pt_analog_top_stub.sv', 'w').write('\n'.join(S)+'\n')
    cs = sorted(k for k in b if k.startswith('c_'))
    wid = {k: (1 if b[k] == {None} else max(b[k])+1) for k in cs}
    open(OUT+'/tb_ctl.svh', 'w').write('// GENERATED by check_top.py --write: every control port of the analog top\n'
        + ''.join(f'wire{"" if wid[k] == 1 else " ["+str(wid[k]-1)+":0]"} {k};\n' for k in cs)
        + f'wire [{sum(wid.values())-1}:0] ctl_all = {{{", ".join(cs)}}};\n'
        + '`define PT_CTL_CONNECT ' + ', '.join(f'.{k}({k})' for k in cs) + '\n'
        + '`define PT_CTL_WEAK0 ' + ' '.join(f"assign (weak1, weak0) {k} = 0;" for k in cs) + '\n')
    return len(top)


def load():
    rd = lambda f: open(f).read()
    return (rd(os.environ.get('PT_TOP_CONN', HERE+'/pt_chip.conn')), rd(HERE+'/masters.txt'), rd(HERE+'/ctl_ports.txt'),
            json.load(open(P+'/spec/register-map.json')), rtl_macro_ports(rd(P+'/rtl/pt_digital_macro.sv')), json.load(open(FP6)))


def selftest():
    conn, mt, ct, reg, rtl, fp = load()
    base, *_ = check(conn, mt, ct, reg, rtl, fp)
    def new(kind, **kw):
        args = dict(conn=conn, mt=mt, ct=ct, reg=reg, rtl=rtl, fp=fp); args.update(kw)
        got, *_ = check(args['conn'], args['mt'], args['ct'], args['reg'], args['rtl'], args['fp'])
        return [x for x in got[kind] if x not in base[kind]]
    cases = [
        ('unbound', dict(conn=conn.replace(' gain_lo=c_lna_gain_lo', '', 1)), 'lna.gain_lo'),
        ('unbound', dict(conn=conn.replace(' byp=c_lna_byp', ' byp=c_lna_byp bogus=VSS', 1)), 'lna.bogus'),
        ('dangling', dict(conn=conn.replace('LOCK>PLL_TX_LOCK', 'LOCK>PLL_TX_LOCKX', 1)), 'PLL_TX_LOCKX'),
        ('undriven', dict(conn=conn.replace('LOCK>PLL_TX_LOCK', 'LOCK>-', 1)), 'PLL_TX_LOCK'),
        ('multidrive', dict(conn=conn.replace('OUTP>AUX_CK OUTN>-', 'OUTP>AUX_CK OUTN>AUX_CK', 1)), 'AUX_CK'),
        ('missing', dict(conn=re.sub(r'inst vthdac .*\n(  .*\n)+', '', conn, 1)), 'vthdac'),
        ('crossing', dict(conn=conn.replace(' DX=WTX_DX\n', ' DX=WTX_DX_DBG\n', 1)), 'wiredtx.DX'),
        ('alwayson', dict(conn=conn.replace('EN=c_aosc_en CLK', 'EN=AOSC_EN_FLOAT CLK', 1)), 'aosc.EN'),
        ('supply', dict(conn=conn.replace('inst lna pt_lna rf_rx', 'inst lna pt_lna conv', 1)), 'lna.VDD'),
        ('iso', dict(conn=conn.replace('A=HOST_CLK ISO=island_off[2]', 'A=HOST_CLK ISO=island_off[0]', 1)), 'iso_host_clk'),
        ('iso', dict(conn=conn.replace('inst iso_wtx_dx iso_clamp wired_tx', 'inst iso_wtx_dx iso_clamp pll', 1).replace('Y>WTX_DX VDD~RAIL_wired_tx', 'Y>WTX_DX VDD~RAIL_pll', 1)), 'iso_wtx_dx'),
        ('staged', dict(mt=mt.replace('master pt_lo_lf          A/timing/generated/lo_lf.ext.spice:pt_lo_lf', 'master pt_lo_lf          staged A/timing/generated/lo_lf.ext.spice:pt_lo_lf CP VT VSS X', 1)), 'lo_lf'),
        ('alwayson', dict(conn=conn.replace('macroclamp debug fc_src', 'macroclamp debug fc_srcX', 1)), 'digital.fc_src[2]'),
        ('iso', dict(conn=conn.replace('macroclamp pll rf_tx_clk|', 'macroclamp conv rf_tx_clk|macroclamp_none|', 1)), 'digital.rf_tx_clk'),
        ('pn', dict(conn=conn.replace('rf_in_p~RF_RX_P rf_in_n~RF_RX_N', 'rf_in_p~RF_RX_N rf_in_n~RF_RX_P', 1)), 'lna'),
        ('pn', dict(conn=conn.replace('PAD_P~RF_TX_P PAD_N~RF_TX_N', 'PAD_P~RF_TX_N PAD_N~RF_TX_P', 1)), 'RF_TX_P'),
        ('pn', dict(conn=conn.replace('lo_p~LO_\\U1P lo_n~LO_\\U1N bb_p', 'lo_p~LO_QP lo_n~LO_QN bb_p', 1)), 'rxmix_i'),
        ('order', dict(conn=conn.replace('ct{0:3}=c_lna_ct[\\1]', 'ct{0,2,1,3}=c_lna_ct[{0:3}]', 1)), 'lna'),
        ('supply', dict(conn=conn.replace('IBIAS~BIAS_ctle ctle_en', 'IBIAS~BIAS_ctle ctle_en', 1).replace('inst ctle pt_ctle wired_rx\n  VDD_WIRE_SW~RAIL_wired_rx VSS~VSS', 'inst ctle pt_ctle wired_rx\n  VDD_WIRE_SW~RAIL_wired_rx VSS~AGND_RX', 1)), 'ctle.VSS'),
        ('pn', dict(conn=conn.replace('EN=c_adc_\\1_en ILEN', 'EN=c_adc_q_en ILEN', 1)), 'adc_i.EN'),
        ('ctl', dict(ct=re.sub(r'^(c_lna_en \| 1 \| 0 \| )[^|]*', r'\1(state == active) & island_on[2] ', ct, 1, re.M)), 'c_lna_en'),
        ('ctl', dict(ct=re.sub(r'^c_lna_att\s*\|\s*5', 'c_lna_att | 4', ct, 1, re.M)), 'c_lna_att'),
        ('ctl', dict(ct=re.sub(r'^c_rfdriver_mute\s*\|.*\n', '', ct, 1, re.M)), 'c_rfdriver_mute'),
        ('cfg', dict(reg=dict(reg, fields=[dict(f, bus_bits=3) if f['name'] == 'lna.match.ctrim' else f for f in reg['fields']])), 'c_lna_ct'),
        ('cfg', dict(reg=dict(reg, fields=[dict(f, default=0) if f['name'] == 'lna.match.ctrim' else f for f in reg['fields']])), 'c_lna_ct'),
        ('macro', dict(rtl={k: v for k, v in rtl.items() if k != 'por_bypass'}), 'por_bypass'),
        ('demand', dict(conn=conn.replace('inst lo_lf pt_lo_lf lo', 'inst lo_lf pt_lo_lf lo demand', 1)), 'lo_lf'),
    ]
    ok = True
    for kind, kw, needle in cases:
        got = new(kind, **kw); hit = any(needle in g for g in got)
        print(f'  selftest {kind:10s} inject -> {"detected" if hit else "MISSED"}: {got[0] if got else ""}')
        ok &= hit
    print('SELFTEST', 'PASS' if ok else 'FAIL'); return ok


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest() else 1)
    conn, mt, ct, reg, rtl, fp = load()
    R, info, inst, masters, nets, ports = check(conn, mt, ct, reg, rtl, fp)
    verbose = '-v' in sys.argv
    for k, v in R.items():
        print(f'[{k}] {len(v)}')
        for x in (v if verbose else v[:6]): print('    '+x)
        if not verbose and len(v) > 6: print(f'    ... {len(v)-6} more (-v)')
    mcl = info.pop('_macroclamp')
    for k, v in info.items(): print(f'({k}) {v}')
    if '--write' in sys.argv:
        BITS = {v: k for k, v in GROUP_NAME.items()}
        os.makedirs(os.environ.get('PT_TOP_OUT', HERE+'/generated'), exist_ok=True)
        open(os.environ.get('PT_TOP_OUT', HERE+'/generated')+'/macro_clamps.txt', 'w').write(
            '# GENERATED by check_top.py --write (CP4-1): macro inputs to AND with island_on[bit] on the first gate after the pin\n# pin island island_on_bit\n'
            + ''.join(f'{p} {g} {BITS[g]}\n' for p, g in sorted(mcl.items(), key=lambda x: (x[1], c_key(x[0])))))
    if '--write' in sys.argv: print('(analog top ports written)', write_outputs(inst, masters, nets, ports))
    mw = ROOT+'/scratch/reviews/mode-walk'; bad = 0
    if '--no-modewalk' not in sys.argv and os.path.isdir(mw):
        for s in ('top_pins.py', 'cfg_map.py', 'bias_sum.py'):
            r = subprocess.run([sys.executable, s, '--selftest'], cwd=mw, capture_output=True, text=True)
            print(f'(mode-walk {s} --selftest) {"PASS" if r.returncode == 0 else "FAIL"}'); bad += r.returncode != 0
    total = sum(len(v) for v in R.values())+bad
    print('SUMMARY ' + ' '.join(f'{k}={len(v)}' for k, v in R.items()) + f' -> {"PASS" if total == 0 else "FAIL"}')
    sys.exit(0 if total == 0 else 1)
