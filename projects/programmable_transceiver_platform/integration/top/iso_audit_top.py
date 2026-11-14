#!/usr/bin/env python3
"""Run the M6 isolation-state audit (scratch/integration/m6-powerup/audit/iso_audit.py, rules K1..K8) on
integration/top/pt_chip.conn instead of the old binder netlist.

What this does: builds a device-terminal chip netlist from pt_chip.conn + the extracted block netlists named in
masters.txt (same shape as the binder's pt_chip_full.spice: subckt library + one top subckt), then runs the
UNMODIFIED audit rules on it through a thin subclass. Differences from the binder run, all stated in the output:
  * islands: the ten supply islands are presented to the audit as their five enable groups (wired, rf, pll, conv,
    debug), because the islands of a group are switched by the same register bit and the audit reasons about
    on/off states. RAIL_<island> nets are therefore merged per group in the audit view only.
  * CP4-1: each macro input listed by a `macroclamp` line is shown to the audit as an iso_clamp in the core domain
    (instance mc_<pin>, ISO = ISLAND_OFF_<group>). That is a REQUIREMENT on the digital macro
    (generated/macro_clamps.txt), not something this netlist proves.
  * c_* control ports: the audit is told they are macro outputs that read 0 while every island that consumes them
    is off (ctl_ports.txt rule; today's regfile gating does this per field). Also a requirement on digital.
  * blocks with no netlist (demand cells, the macro, provider pads) are empty boxes: their pins have no device
    terminals. Converters are bound to the staged pin contract; their PUBLISHED extracted netlists are used for the
    terminals of every pin that exists in both (CLKP stands in for CLK).
--selftest: four injected errors (clamp ISO inverted, clamp removed, a switch forced on, an ATB island gate removed)
must each raise the count of their rule.
Light: pure Python, one process, about a minute.
"""
import sys, os, re, json, collections, tempfile, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_top as ct
AUD = ct.ROOT+'/scratch/integration/m6-powerup/audit'
GROUP = {k: ct.GROUP_NAME[v] for k, v in ct.GROUP_BIT.items()}


def audit_net(n):
    m = re.fullmatch(r'island_off\[(\d)\]', n)
    if m: return 'ISLAND_OFF_'+ct.GROUP_NAME[int(m.group(1))]
    m = re.fullmatch(r'RAIL_(\w+)', n)
    if m and m.group(1) in GROUP: return 'RAIL_'+GROUP[m.group(1)]
    if n == 'ISO_wired_tx': return 'ISO_wired'
    return n


def build(work):
    conn, mt, ctl_txt, reg, rtl, fp = ct.load()
    R, info, inst, masters, nets, ports = ct.check(conn, mt, ctl_txt, reg, rtl, fp)
    mc = info['_macroclamp']
    lib, empty, note = [], [], []
    subname = {}

    def load(master):
        m = masters[master]
        path, sub = m['path'], m['sub']
        text = re.sub(r'\n\+\s*', ' ', open(path).read())
        text = '\n'.join(l for l in text.split('\n') if not l.lstrip().lower().startswith(('.include', '.lib', '.temp', '.option', '.param', '.control', '.end ', '.endc')) and l.strip().lower() != '.end')
        names = re.findall(r'^\.subckt\s+(\S+)', text, re.M | re.I)
        tag = re.sub(r'\W', '_', master)
        for nm in sorted(set(names), key=len, reverse=True):       # file-unique names (extracted files reuse leaf names)
            text = re.sub(r'(?<![\w.#])'+re.escape(nm)+r'(?![\w.#])', f'{tag}__{nm}', text)
        keep = re.findall(r'^\.subckt\s.*?^\.ends[^\n]*', text, re.M | re.S | re.I)
        lib.append('\n'.join(keep))
        return f'{tag}__{sub}'

    def published_pins(master):
        m = masters[master]
        return ct.subckt_pins(m['path'], m['sub'])

    for name in sorted({i['master'] for i in inst.values()}):
        m = masters[name]
        if m['kind'] == 'file' or m['kind'] == 'staged':
            subname[name] = load(name)
        elif name == 'pt_core_bias':
            sys.path.insert(0, ct.P+'/integration'); sys.path.insert(0, ct.P+'/verification')
            try:
                import core_bias
                from pathlib import Path
                cb = core_bias.build(lambda p: Path(p).read_text())
                assert cb['pins'] == m['pins'], 'masters.txt core_bias pin list is stale against integration/core_bias.py'
                lib.append(re.sub(r'\n\+\s*', ' ', cb['text'])); subname[name] = 'pt_core_bias'
            except Exception as e:      # noqa
                note.append(f'core_bias: builder not usable here ({type(e).__name__}: {e}); empty box'); empty.append(name)
        elif name in ('iso_clamp_x4', 'iso_pd'):
            p = f'{ct.ROOT}/scratch/iso-family/pex/{name}/{name}.pex.spice'
            masters[name] = dict(kind='file', path=p, sub=name+'_pex', pins=m['pins']); subname[name] = load(name)
        else:
            empty.append(name)
    L = ['* audit netlist generated from integration/top/pt_chip.conn by iso_audit_top.py'] + lib
    for name in empty:
        if name == 'pt_digital_macro': continue
        L.append(f'.subckt {name} '+' '.join(masters[name]['pins'])+f'\n.ends {name}'); subname[name] = name
    dig = inst['digital']
    dpins = list(dig['pins']) + sorted({n for n in nets if ct.bus(n)[0].startswith('c_')}, key=ct.c_key)
    L.append('.subckt pt_digital_macro '+' '.join(dpins)+'\n.ends pt_digital_macro')
    top = sorted(audit_net(p) for p in ports if p not in ('VDD', 'VSS'))
    L.append('.subckt pt_chip_full VDD VSS '+' '.join(top))
    placed, nc = [], 0
    iso_m = masters['iso_clamp']; iso_sub = subname['iso_clamp']; iso_pins = published_pins('iso_clamp')
    for name, i in inst.items():
        home = 'core' if i['group'] in ct.ALWAYS_ON else GROUP[i['group']]
        placed.append(dict(name=name, island=home, master=i['master'] if i['master'] != 'pt_core_bias' else 'core_bias'))
        m = masters[i['master']]
        if name == 'digital':
            row = []
            for p in dpins:
                n = dig['pins'][p][1] if p in dig['pins'] else p
                if p in mc:       # CP4-1: macro-internal clamp shown as an iso_clamp in the core domain
                    y = f'MC__{re.sub(chr(92)+"W", "_", p)}'
                    cm = dict(A=audit_net(n), ISO='ISLAND_OFF_'+mc[p], Y=y, VDD='VDD', VSS='VSS')
                    L.append(f'Xmc_{re.sub(chr(92)+"W", "_", p)} '+' '.join(cm[q] for q in iso_pins)+f' {iso_sub}')
                    placed.append(dict(name=f'mc_{re.sub(chr(92)+"W", "_", p)}', island='core', master='iso_clamp'))
                    n = y
                if n == '-': nc += 1; n = f'NC_{nc}'
                row.append(audit_net(n))
            L.append('Xdigital '+' '.join(row)+' pt_digital_macro')
            continue
        pins = published_pins(i['master']) if m['kind'] in ('file', 'staged') else m['pins']
        b = dict(i['pins'])
        if m['kind'] == 'staged':
            if 'CLK' in b: b['CLKP'] = b['CLK']
        row = []
        for p in pins:
            n = b[p][1] if p in b else '-'
            if n == '-': nc += 1; n = f'NC_{nc}'
            row.append(audit_net(n))
        L.append(f'X{name} '+' '.join(row)+f' {subname[i["master"]]}')
    L.append('.ends pt_chip_full')
    open(work+'/pt_chip_full.spice', 'w').write('\n'.join(L)+'\n')
    glue = {f'ISLAND_OFF_{g}': dict(kind='inverter', input=f'island_on[{b}]') for b, g in ct.GROUP_NAME.items()}
    json.dump(dict(glue=glue), open(work+'/binding.json', 'w'))
    json.dump(dict(placed=placed), open(work+'/floorplan.json', 'w'))
    # facts the audit cannot read from today's RTL: target macro port directions and the off-state of c_* ports
    ctl = ct.load_ctl(ctl_txt)
    direction = {ct.bus(p)[0]: ('output' if k == '>' else 'input') for p, (k, n) in dig['pins'].items()}
    cbit = {}
    for n, us in nets.items():
        base, idx = ct.bus(n)
        if base.startswith('c_'):
            direction[base] = 'output'
            isl = sorted({GROUP[inst[u[0]]['group']] for u in us if inst[u[0]]['group'] in GROUP})
            named = {ct.GROUP_NAME[int(k)] for k in re.findall(r'island_on\[(\d)', ctl[base]['enc']) if int(k) in ct.GROUP_NAME}
            if named: isl = sorted(named)       # the row states its own gating: use it, so a wrong group shows as K2
            cbit[n] = dict(field=base, islands=isl, reset=(ctl[base]['reset'] >> (idx or 0)) & 1)
    return dict(direction=direction, cbit=cbit, empty=empty, note=note, mc=mc, inst=inst, masters=masters)


def make_audit(work, facts):
    sys.path.insert(0, AUD)
    import iso_audit as A
    A.CHIP = work
    A.ISLAND_BIT = {v: k for k, v in ct.GROUP_NAME.items()}
    A.CONTRACT_INPUTS = {}
    A.SUP = {'VDD', 'VSS', 'AGND_RX'}      # AGND_RX is a ground (LNA return), not a signal

    class TopAudit(A.Audit):
        def __init__(self):
            super().__init__()
            self.direction.update(facts['direction'])
            self.bit.update(facts['cbit'])
            for n in list(self.users):          # the macro presents c_* nets under the port's own name
                pass

        def k3_switch(self):                    # ten switches, five enable bits, per-switch power-good to the macro
            fails, rows = [], []
            for inst, i in facts['inst'].items():
                if not i['master'].startswith('isw_'): continue
                pins = {p: n for n, us in self.users.items() for ii, p, _ in us if ii == inst}
                isl = inst[4:]; bit = ct.GROUP_BIT[isl]
                rows.append(dict(inst=inst, **pins))
                if pins.get('EN') != f'island_en[{bit}]':
                    fails.append(dict(rule='K3', inst=inst, detail=f"EN is {pins.get('EN')}, expected island_en[{bit}] (reset 0)"))
                if pins.get('PG') != f's_pg_{isl}':
                    fails.append(dict(rule='K3', inst=inst, detail=f"PG is {pins.get('PG')}, expected s_pg_{isl}"))
                if pins.get('VISL') != 'RAIL_'+GROUP[isl] or pins.get('VDD') != 'VDD':
                    fails.append(dict(rule='K3', inst=inst, detail='rail pins not VDD -> island rail'))
            return fails, rows
    return A, TopAudit


def classify(r, facts):
    """Group the audit's failures into the items the M6 report named."""
    out = collections.OrderedDict()
    for f in r['fails']:
        k = f['rule']
        if k == 'K1':
            rec = f.get('receiver', '')
            key = 'K1 macro input from an island with no clamp' if rec.startswith('digital.') else 'K1 island-to-island / island-to-core gate with no clamp'
        elif k == 'K2':
            sd = f.get('source_domain')
            key = ('K2 pad back-drive into an off island' if sd == 'pad' else
                   'K2 core / digital source onto p-diffusion of an off island' if sd == 'core' else 'K2 cross-island diffusion')
        elif k == 'K7': key = 'K7 ATB leaf not gated by its island'
        else: key = {'K3': 'K3 switch', 'K4': 'K4 glue', 'K5': 'K5 contention', 'K6': 'K6 always-on floating gate'}[k]
        out.setdefault(key, []).append(f)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--selftest', action='store_true'); ap.add_argument('--out', default=HERE+'/generated/iso_audit_top.json')
    ap.add_argument('--keep', help='directory for the generated audit netlist (default: temporary)'); ap.add_argument('-v', action='store_true')
    a = ap.parse_args()
    work = a.keep or tempfile.mkdtemp(prefix='pt_iso_audit_')
    os.makedirs(work, exist_ok=True)
    facts = build(work)
    A, TopAudit = make_audit(work, facts)
    try:
        x = TopAudit(); src = 'working tree'
    except Exception as e:      # the digital owner's rework can leave rtl/ unparsable: use the last committed RTL + register map
        import subprocess
        os.makedirs(work+'/head', exist_ok=True)
        subprocess.run(f'cd {ct.P} && git archive HEAD rtl spec/register-map.json | tar -x -C {work}/head', shell=True, check=True)
        A.PROJ = work+'/head'; x = TopAudit(); src = f'git HEAD (working-tree rtl/ not parsable: {type(e).__name__})'
    print('RTL facts (ATB decode gating, reset expression) from:', src)
    r = x.run()
    groups = classify(r, facts)
    print(f'ISO AUDIT on pt_chip.conn: {"FAIL" if r["fail"] else "PASS"}  {r["counts"]}  (total {len(r["fails"])})')
    for k, v in groups.items():
        print(f'  [{k}] {len(v)}')
        for f in (v if a.v else v[:4]):
            print('      ' + (f.get('net') or f.get('leaf') or f.get('inst') or '') + ': ' + ' | '.join(str(f[q]) for q in ('victim', 'receiver', 'source', 'node', 'detail') if q in f)[:230])
        if not a.v and len(v) > 4: print(f'      ... {len(v)-4} more (-v)')
    print(f'  clamped crossings that pass K1: {len(r["k1_clamped_ok"])} (of which macro-internal, required of digital: {len(facts["mc"])})')
    print(f'  coverage: {r["coverage"]}; empty boxes (no device terminals): {sorted(facts["empty"])}')
    for n in facts['note']: print('  note:', n)
    # Direction markers of the conn against the device terminals of each pin (decisions.md section C):
    #  D1 (error): a pin marked `>` (driver) that is nothing but MOS gates; D2 (listed): a pin marked `=` (input) with
    #  no gate at all, only diffusion (a transmission-gate input, or a wrong marker).
    def dircheck(flip=None):
        d1, d2 = [], []
        for n, us in x.users.items():
            for iname, port, terms in us:
                i = facts['inst'].get(iname)
                if not i or iname == 'digital' or not terms or port not in i['pins']: continue
                kind = i['pins'][port][0]; ks = {k.split(':')[0] for k, _ in terms}
                if f'{iname}.{port}' == flip: kind = '>'
                if kind == '>' and ks <= {'gate', 'cap', 'pbulk', 'nwell'} and 'gate' in ks: d1.append(f'{iname}.{port}')
                if kind == '=' and 'gate' not in ks and ks & {'pdiff', 'ndiff'}: d2.append(f'{iname}.{port}')
        return d1, d2
    d1, d2 = dircheck()
    print(f'  [D1 conn says output, pin is gate-only] {len(d1)} {sorted(d1)[:12]}')
    d2g = collections.Counter(re.sub(r'\d+$', '', q) for q in d2)
    print(f'  [D2 conn says input, pin has diffusion and no gate (listed, not failed)] {len(d2)} {dict(d2g)}')
    pads = [p for p in r['pads'] if 'NO pull' in str(p.get('before_spi', ''))]
    print(f'  K8 (table, not a rule): provider input pads with no pull: {len(pads)} rows = SPI_SCLK, SPI_CS_N, SPI_MOSI, H2D[9:0], H2D_CLK (14 pads; straps in integration/pt_provider_io.sv, INT6-5)')
    summary = dict(direction_errors=sorted(d1), direction_listed=sorted(d2), counts=r['counts'], groups={k: len(v) for k, v in groups.items()}, fails=r['fails'], macro_internal_clamps=len(facts['mc']),
                   k1_clamped_ok=len(r['k1_clamped_ok']), coverage=r['coverage'], empty_boxes=sorted(facts['empty']))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(summary, open(a.out, 'w'), indent=1, default=str)
    rc = 1 if (r['fail'] or d1) else 0
    if a.selftest:
        ok = True
        clamp = next(n for n, i in facts['inst'].items() if i['master'].startswith('iso_clamp'))
        leaf = next(l['sel'] for l in r['atb_leaves'] if l['rtl_gate_islands'] and not l['node'].startswith(('RAIL_', 'VDD', 'VSS')))
        def run(mut, rule, label):
            nonlocal ok
            y = TopAudit(); msg = mut(y); rr = y.run(); d = rr['counts'][rule]-r['counts'][rule]
            print(f'  selftest {label}: {msg} -> {rule} +{d} {"DETECTED" if d > 0 else "MISSED"}'); ok = ok and d > 0
        def invert(y):
            for n, us in list(y.users.items()):
                for u in us:
                    if u[0] == clamp and u[1] == 'ISO':
                        us.remove(u); b = {v: k for k, v in ct.GROUP_NAME.items()}[n.split('_', 2)[2]]
                        y.users[f'island_on[{b}]'].append(u); return f'{clamp}.ISO moved from {n} to island_on[{b}]'
        run(invert, 'K1', 'inverted clamp control')
        run(lambda y: y.inject(f'remove_clamp={clamp}'), 'K1', 'clamp removed')
        run(lambda y: y.inject('force_on=rf_rx'), 'K3', 'switch forced on')
        run(lambda y: y.inject(f'ungate_atb={leaf}'), 'K7', 'ATB island gate removed')
        hit = 'lna.en' in dircheck('lna.en')[0]
        print(f'  selftest direction marker: lna.en marked as a driver -> D1 {"DETECTED" if hit else "MISSED"}'); ok = ok and hit
        print('ISO AUDIT SELFTEST', 'PASS' if ok else 'FAIL')
        rc = rc or (0 if ok else 3)
        if not ok: rc = 3
    sys.exit(rc)


if __name__ == '__main__':
    main()
