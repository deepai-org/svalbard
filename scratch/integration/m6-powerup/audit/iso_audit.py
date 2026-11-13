#!/usr/bin/env python3
"""M6(a) isolation-state audit (chip level).

Authority: the full-chip SPICE binding regenerated NOW by the maintained binder
(verification/chip_assembly/netlist.py, stage 6 of run_chip_assembly.py) from the current extracted block
netlists (chipnet/gen.py -> chipnet/pt_chip_full.spice + binding.json), plus
  rtl/pt_digital_macro.sv   port directions, en_eff decode (island gating of every effective enable)
  rtl/pt_regfile.sv         ATB switch decode and its island gating
  spec/register-map.json    per-field reset default and island gating list (generated with the RTL)
  integration/pt_provider_io.sv  provider pad cell straps (hand table below, line-checked by grep)
Why this and not pt_chip.sv / contract.json: pt_chip.sv keeps the analog side as one black box, and the contract
has no device terminals; only the binder resolves each block pin to a net AND carries the transistor terminals
needed for the diffusion (LU-02) test.  Limits are printed in the coverage section.

Rules (each can FAIL):
  K1 float      net driven only from switched island X, received by gates in another domain, with no iso_clamp
                (Y = A & !ISO) in the receiving domain, or a clamp whose ISO pin is not an isolate-high net of X
  K2 diffusion  p-diffusion whose n-well is on RAIL_X (X switched) on a net that a source outside X can pull high
                while X is off (LU-02): pad, core analog driver, another island, or an ungated register bit
  K3 switch     isw_X.EN must be island_en[bit(X)] (reset 0, weak pull-down inside); PG -> island_pgood[bit]
  K4 glue       every EN_EFF_* / ISLAND_OFF_* glue net needs an RTL driver with the same island gating
  K5 contention more than one CMOS driver instance on a net
  K6 always-on  an always-on (core) instance with a floating control gate (UNBOUND_*)
  K7 atb        ATB leaf on an island node whose switch select is not gated by that island in the RTL
                (supply-monitor taps are exempt by policy; their leaf must then have no p-diffusion on the node
                 whose well is the island rail)
  K8 pad        table of every pad's state before SPI is alive (reset asserted, and after release with defaults)

Negative controls:  --selftest  builds the "proposed clamps" overlay (an iso_clamp on every K1 net), requires K1 to
pass on it, then injects (i) one clamp with ISO wired to island_on (inverted), (ii) one clamp removed, (iii) one
switch EN forced to VDD, (iv) one ATB island gate removed, and requires each to FAIL its rule.
"""
import argparse, collections, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from netclass import parse, Classifier

ROOT = '/home/ubuntu/svalbard'
PROJ = ROOT+'/projects/programmable_transceiver_platform'
CHIP = HERE+'/../chipnet'
ISLAND_BIT = {'wired': 0, 'rf': 1, 'pll': 2, 'usb': 3, 'conv': 4, 'debug': 5}
BIT_ISLAND = {v: k for k, v in ISLAND_BIT.items()}
SUP = {'VDD', 'VSS'}
# Instances whose pins sit in more than one supply domain: per-port domain of the *gate* terminals.
# isw_X: EN/ISO/PG logic is on the ring side (VDD / VMAX well; island_support README section 1).
# core_bias: every control gate is in the core; BIAS_* outputs resolve through their own wells.
MIXED_GATE_DOMAIN = {'isw_': 'core', 'core_bias': 'core'}
# Provider pad cells (integration/pt_provider_io.sv; cell: gf180mcu_fd_io). name -> (cell, straps, before-SPI state)
PROVIDER_PADS = {
    'RESET_N': ('in_c', 'PU=0 PD=1', 'input, weak pull-down: die held in reset if the host is absent'),
    'SPI_SCLK': ('bi_24t', 'OE=0 IE=1 PU=0 PD=0', 'input, NO pull: floats if the host is unpowered'),
    'SPI_CS_N': ('bi_24t', 'OE=0 IE=1 PU=0 PD=0', 'input, NO pull: floats (CS_N floating low selects the SPI slave)'),
    'SPI_MOSI': ('bi_24t', 'OE=0 IE=1 PU=0 PD=0', 'input, NO pull: floats if the host is unpowered'),
    'SPI_MISO': ('bi_t', 'OE=miso_oe IE=0', 'hi-Z while CS_N=1 or reset (miso_oe=0)'),
    'H2D[9:0]': ('bi_24t x10', 'OE=0 IE=1 PU=0 PD=0', 'inputs, NO pull: 10 floating CMOS inputs if the FPGA is unconfigured'),
    'H2D_CLK': ('bi_24t', 'OE=0 IE=1 PU=0 PD=0', 'input, NO pull: floats if the FPGA is unconfigured'),
    'D2H[9:0]': ('bi_t x10', 'OE=d2h_oe', 'hi-Z (hostio.controls.d2h_enable resets 0)'),
    'D2H_CLK': ('bi_t', 'OE=d2h_oe', 'hi-Z (d2h_enable resets 0)'),
    'CLK_OBS': ('bi_24t', 'OE=clk_obs_oe IE=0', 'hi-Z (oe resets 0)'),
    'DBG_OBS0': ('bi_24t', 'OE=dbg_obs0_oe IE=0', 'hi-Z (oe resets 0)'),
    'DBG_OBS1': ('bi_24t', 'OE=dbg_obs1_oe IE=0', 'hi-Z (oe resets 0)'),
    'WCLK_OBS': ('bi_24t', 'OE=wclk_obs_oe IE=0', 'hi-Z (oe resets 0)'),
    'WDBG_OBS': ('bi_24t', 'OE=wdbg_obs_oe IE=0', 'hi-Z (oe resets 0)'),
}


# Digital-macro inputs that have NO driver in the binder's netlist (datapath/status not bound yet): source island
# per integration/pt_chip.sv + macro-contract.md.  Checked at contract level only (rule K1c).
CONTRACT_INPUTS = {
    'wire_rx_data': 'wired', 'wire_rx_valid': 'wired', 'wire_rx_clk': 'wired', 'wire_tx_clk': 'wired',
    'wire_tx_request': 'wired', 'wire_analog_status': 'wired',
    'rf_rx_sample': 'conv', 'rf_rx_valid': 'conv', 'rf_rx_clk': 'conv', 'rf_tx_clk': 'conv', 'rf_tx_request': 'conv',
    'calibration_above_target': 'conv', 'analog_status': 'pll', 'fault': 'rf',
    'host_word_clk': 'pll', 'ct_det_clk_in': 'pll', 'ct_ref_clk': 'pll', 'ct_pll_lock': 'pll', 'ref_clk': 'pll',
}


def load():
    subs = parse(CHIP+'/pt_chip_full.spice')
    C = Classifier(subs)
    b = json.load(open(CHIP+'/binding.json'))
    fp = json.load(open(CHIP+'/floorplan.json'))
    home = {p['name']: p['island'] for p in fp['placed']}
    home['digital'] = 'core'
    master = {p['name']: p['master'] for p in fp['placed']}
    users = collections.defaultdict(list)      # net -> [(inst, port, {(kind, bulk_topnet)})]
    for l in subs['pt_chip_full'][1]:
        t = l.split()
        if not t or t[0][0] != 'X':
            continue
        nodes = [x for x in t[1:] if '=' not in x]
        sub, inst = nodes[-1], t[0][1:]
        if sub not in subs:
            continue
        c = C.cls(sub) if subs[sub][1] else {}
        m = dict(zip(subs[sub][0], nodes[:-1]))
        if inst.startswith('pad_'):
            home[inst] = 'pad'
            master[inst] = sub
        for p, n in m.items():
            terms = set()
            for kind, bulk in c.get(p, ()):
                terms.add((kind, m.get(bulk, bulk) if bulk else None))
            users[n].append((inst, p, terms))
    return subs, b, home, master, users


def rtl_facts():
    mac = open(PROJ+'/rtl/pt_digital_macro.sv').read()
    nc = re.sub(r'//[^\n]*', '', mac)
    hdr = nc[nc.index('module pt_digital_macro('):nc.index(');', nc.index('module pt_digital_macro('))]
    direction = {}
    cur = None
    for tok in re.split(r',', hdr.split('(', 1)[1]):
        tok = tok.strip()
        m = re.match(r'(input|output)\b', tok)
        if m:
            cur = m.group(1)
        name = re.sub(r'\[[^\]]*\]', ' ', tok).split()
        if name:
            direction[name[-1]] = cur
    en_eff = {}      # glue net name -> (index, island bit)
    for m in re.finditer(r'assign en_eff\[(\d+)\]\s*=\s*([^;]*);\s*//\s*(\S+)', mac):
        ib = re.search(r'island_on_reg\[(\d+)\]', m.group(2))
        en_eff['EN_EFF_'+m.group(3)] = (int(m.group(1)), int(ib.group(1)) if ib else None)
    reg = open(PROJ+'/rtl/pt_regfile.sv').read()
    atb = {}
    for m in re.finditer(r'assign (atb[01]_sw)\[(\d+)\]=([^;]*);', reg):
        atb[f'{m.group(1)}[{m.group(2)}]'] = sorted(set(int(x) for x in re.findall(r'island_on\[(\d+)\]', m.group(3))))
    rm = json.load(open(PROJ+'/spec/register-map.json'))
    bit = {}
    for f in rm['fields']:
        if f.get('bus') and f.get('bus_lsb') is not None:
            w = f.get('bus_bits') or f['bits']
            for k in range(w):
                bit[f"{f['bus']}_cfg[{f['bus_lsb']+k}]"] = dict(field=f['name'], islands=f['islands'],
                                                               reset=(int(f['default'] or 0) >> k) & 1 if not f.get('decode') else None)
    por_expr = re.search(r'wire rst_n\s*=\s*([^;]*);', mac).group(1).strip()
    return direction, en_eff, atb, bit, por_expr


def dig_dir(net, direction):
    return direction.get(re.sub(r'\[\d+\]$', '', net))


class Audit:
    def __init__(self):
        self.subs, self.b, self.home, self.master, self.users = load()
        self.direction, self.en_eff, self.atb, self.bit, self.por_expr = rtl_facts()
        self.glue = self.b['glue']
        self.chip_ports = set(self.subs['pt_chip_full'][0])
        self.removed_atb_gate = set()
        self.notes = []

    # ---- domain helpers -------------------------------------------------------------------------------------
    def rails(self, inst):
        r = set()
        for n, us in self.users.items():
            if n == 'VDD' or n.startswith('RAIL_'):
                for i, p, t in us:
                    if i == inst and any(k in ('nwell', 'pdiff') for k, _ in t):
                        r.add(n)
        return r

    def gate_domain(self, inst):
        for k, v in MIXED_GATE_DOMAIN.items():
            if inst.startswith(k):
                return v
        if self.master.get(inst, '').startswith('iso_clamp'):
            return 'core'
        if inst.startswith('pad_'):
            r = [x for x in self.rails(inst) if x.startswith('RAIL_')]
            return r[0][5:] if r else 'pad'
        return self.home.get(inst, 'core')

    def term_domain(self, inst, bulk):
        if bulk == 'VDD':
            return 'core'
        if bulk and bulk.startswith('RAIL_'):
            return bulk[5:]
        if inst.startswith('pad_'):
            return 'pad'
        return self.gate_domain(inst)      # internal well (regulated / VMAX): the instance's own domain

    def sources(self, net):
        """[(inst, port, domain, how)] able to pull the net high."""
        out = []
        if net in self.chip_ports and net not in SUP:
            out.append(('<pad>', net, 'pad', 'external'))
        if net in self.glue or net in self.en_eff:
            out.append(('digital', net, 'core', 'glue'))
        for inst, port, terms in self.users[net]:
            if inst == 'digital':
                if dig_dir(port, self.direction) == 'output':
                    out.append((inst, port, 'core', 'digital_out'))
                continue
            for kind, bulk in terms:
                if kind.startswith('pdiff'):
                    out.append((inst, port, self.term_domain(inst, bulk), 'pdiff' if kind == 'pdiff' else 'pdiff_via_R'))
        return sorted(set(out))

    def off_value(self, net, island):
        """(value when `island` is off, reset value, why) for a digital/glue-driven net; None = not provable."""
        if net in self.glue:
            g = self.glue[net]
            if g['kind'] == 'inverter':
                return 1, 1, 'ISLAND_OFF = ~island_on'
            rtl = self.en_eff.get(net)
            if rtl and rtl[1] == ISLAND_BIT.get(island):
                return 0, 0, f'en_eff[{rtl[0]}] gated by island_on[{rtl[1]}]'
            return None, 0, 'glue net without matching RTL gate'
        if net in self.bit:
            f = self.bit[net]
            if island in f['islands']:
                return 0, f['reset'], f"{f['field']} gated by {f['islands']}"
            return None, f['reset'], f"{f['field']} not gated by {island} (gating {f['islands']})"
        m = re.match(r'(atb[01]_sw\[\d+\])', net)
        if m and m.group(1) in self.atb:
            if net in self.removed_atb_gate:
                return None, 0, 'atb select ungated (injected)'
            if ISLAND_BIT.get(island) in self.atb[m.group(1)]:
                return 0, 0, 'atb select gated by island_on'
            return None, 0, 'atb select not gated by this island'
        if re.match(r'island_(en|on)\[', net):
            return 0, 0, 'island_power resets 0'
        return None, None, 'no reset/off-state rule'

    # ---- rules ------------------------------------------------------------------------------------------------
    def k1_float(self):
        fails, ok = [], []
        for net, us in sorted(self.users.items()):
            if net in SUP or net.startswith(('RAIL_', 'UNBOUND_', 'ESD_RAIL', 'ATB_ESD')) or net in self.chip_ports:
                continue
            src = self.sources(net)
            sdom = {d for _, _, d, how in src}
            if not sdom or 'core' in sdom or 'pad' in sdom:
                continue
            if any(not i.startswith('<') and self.master.get(i, '').startswith(('atb_leaf', 'atb_grp', 'atb_pad')) for i, _, _, _ in src):
                continue        # ATB local/global buses: K7
            # analog/RF nets: an iso_pd pull-down (Y ISO VSS) on the net itself is the clamp (interface row PD7)
            pd = [(i, next(n for n, uu in self.users.items() for ii, pp, _ in uu if ii == i and pp == 'ISO'))
                  for i, p, _ in us if self.master.get(i, '').startswith('iso_pd') and p == 'Y']
            good = {f'ISO_{x}' for x in sdom} | {f'ISLAND_OFF_{x}' for x in sdom}
            if pd and len(sdom) == 1 and all(n in good for _, n in pd):
                ok.append(dict(net=net, clamp=pd[0][0], iso=pd[0][1]))
                continue
            for inst, port, terms in us:
                is_gate = any(k == 'gate' for k, _ in terms) or (inst == 'digital' and dig_dir(port, self.direction) == 'input')
                if not is_gate or self.master.get(inst, '').startswith('iso_pd'):
                    continue
                rd = self.gate_domain(inst)
                if rd in sdom and len(sdom) == 1:
                    continue
                if self.master.get(inst, '').startswith('iso_clamp'):
                    iso = next(n for n, uu in self.users.items() for i, p, _ in uu if i == inst and p == 'ISO')
                    good = {f'ISO_{x}' for x in sdom} | {f'ISLAND_OFF_{x}' for x in sdom}
                    if port != 'A':
                        continue
                    if len(sdom) == 1 and iso in good:
                        ok.append(dict(net=net, clamp=inst, iso=iso))
                    else:
                        why = ('inverted polarity: island_on/island_en are 0 when the island is off, the clamp isolates on 1'
                               if re.match(r'island_(on|en)\[', iso) else 'ISO pin is not an isolate-high net of the driving island')
                        fails.append(dict(rule='K1', net=net, driver_islands=sorted(sdom), receiver=f'{inst}.{port}',
                                          receiver_domain=rd, detail=f'iso_clamp {inst} ISO={iso}: {why}'))
                    continue
                fails.append(dict(rule='K1', net=net, driver_islands=sorted(sdom), receiver=f'{inst}.{port}', receiver_domain=rd,
                                  detail='gate floats when the driving island is off (no iso_clamp)',
                                  severity='high' if rd == 'core' else 'medium'))
        # contract level: macro inputs with no driver in the netlist
        grp = collections.Counter()
        for net, us in self.users.items():
            for inst, port, _ in us:
                base = re.sub(r'\[\d+\]$', '', port)
                if inst == 'digital' and base in CONTRACT_INPUTS and not self.sources(net):
                    grp[base] += 1
        for base, n in sorted(grp.items()):
            fails.append(dict(rule='K1', net=f'{base} ({n} bit{"s" if n > 1 else ""})', driver_islands=[CONTRACT_INPUTS[base]],
                              receiver=f'digital.{base}', receiver_domain='core', severity='high', contract_level=True, bits=n,
                              detail='macro input sourced from a switched island per pt_chip.sv; not bound in the netlist and no iso_clamp exists'))
        return fails, ok

    def k2_diffusion(self):
        fails, info = [], []
        for net, us in sorted(self.users.items()):
            if net in SUP or net.startswith(('RAIL_', 'UNBOUND_')):
                continue
            src = [x for x in self.sources(net) if not self.master.get(x[0], '').startswith('atb_')]
            for inst, port, terms in us:
                if self.master.get(inst, '').startswith('atb_'):
                    continue
                for kind, bulk in sorted(terms, key=str):
                    if not kind.startswith('pdiff') or not bulk:
                        continue
                    isl = self.term_domain(inst, bulk)
                    if isl in ('core', 'pad') or isl not in ISLAND_BIT:
                        continue
                    for si, sp, sd, how in src:
                        if sd == isl or (si, sp) == (inst, port):
                            continue
                        rec = dict(rule='K2', net=net, victim=f'{inst}.{port}', well=bulk, island=isl, via=kind,
                                   source=f'{si}.{sp}', source_domain=sd)
                        if how in ('digital_out', 'glue'):
                            v, rst, why = self.off_value(net, isl)
                            rec['detail'] = why
                            if v == 0:
                                info.append(rec)
                                continue
                        elif sd == 'pad':
                            rec['detail'] = 'pad can be driven externally while the island is off'
                        else:
                            rec['detail'] = f'{sd} driver can be high while {isl} is off'
                        fails.append(rec)
        # de-duplicate
        seen, out = set(), []
        for f in fails:
            k = (f['net'], f['victim'], f['island'], f['source_domain'])
            if k not in seen:
                seen.add(k); out.append(f)
        return out, info

    def k3_switch(self):
        fails, rows = [], []
        for isl, bit in ISLAND_BIT.items():
            inst = f'isw_{isl}'
            pins = {p: n for n, us in self.users.items() for i, p, _ in us if i == inst}
            if not pins:
                if isl != 'usb':
                    fails.append(dict(rule='K3', inst=inst, detail='island switch not in the netlist'))
                continue
            row = dict(inst=inst, **pins)
            rows.append(row)
            if pins.get('EN') != f'island_en[{bit}]':
                fails.append(dict(rule='K3', inst=inst, detail=f"EN is {pins.get('EN')}, expected island_en[{bit}] (reset 0): island would not default off"))
            if pins.get('PG') != f'island_pgood[{bit}]':
                fails.append(dict(rule='K3', inst=inst, detail=f"PG is {pins.get('PG')}, expected island_pgood[{bit}]"))
            if pins.get('VISL') != f'RAIL_{isl}' or pins.get('VDD') != 'VDD':
                fails.append(dict(rule='K3', inst=inst, detail='rail pins not VDD -> RAIL_<island>'))
            row['iso_consumers'] = [f'{i}.{p}' for i, p, _ in self.users.get(pins.get('ISO', ''), []) if i != inst]
        return fails, rows

    def k4_glue(self):
        fails = []
        for net, g in sorted(self.glue.items()):
            if g['kind'] != 'state_active_decode':
                continue
            want = int(re.search(r'\[(-?\d+)\]', g['island_on']).group(1)) if g.get('island_on') else None
            rtl = self.en_eff.get(net)
            if rtl is None:
                fails.append(dict(rule='K4', net=net, detail=f"binder needs {net} ({g['field']}) but pt_digital_macro has no en_eff output for it: no driver"))
            elif rtl[1] != want:
                fails.append(dict(rule='K4', net=net, detail=f'RTL gates with island_on[{rtl[1]}], binder expects island_on[{want}]'))
        return fails

    def k5_contention(self):
        fails = []
        for net, us in sorted(self.users.items()):
            if net in SUP or net.startswith(('RAIL_', 'UNBOUND_', 'ATB', 'ESD_RAIL')) or net in self.chip_ports:
                continue
            hard = [f'{i}.{p}' for i, p, t in us if {'pdiff', 'ndiff'} <= {k for k, _ in t} and not any(k == 'gate' for k, _ in t)]
            soft = [f'{i}.{p}' for i, p, t in us if {'pdiff', 'ndiff', 'gate'} <= {k for k, _ in t}]
            dig = [f'{i}.{p}' for i, p, t in us if i == 'digital' and dig_dir(p, self.direction) == 'output']
            if dig and len(hard)+len(dig) > 1:
                fails.append(dict(rule='K5', net=net, drivers=hard+dig, detail='more than one push-pull output on the net'))
            elif dig and soft:
                fails.append(dict(rule='K5', net=net, drivers=dig+soft, detail='digital macro output shares the net with a port that has both diffusions and a gate (driver with feedback, or a transmission-gate input: check)'))
        return fails

    def k6_always_on_float(self):
        fails, per_inst = [], collections.Counter()
        for net, us in self.users.items():
            if not net.startswith('UNBOUND_'):
                continue
            for inst, port, terms in us:
                per_inst[inst] += 1
                if self.gate_domain(inst) == 'core' and any(k == 'gate' for k, _ in terms) and not any(k in ('pdiff', 'ndiff') for k, _ in terms):
                    fails.append(dict(rule='K6', inst=inst, port=port, detail='always-on block control gate is unbound (floats at power-up)'))
        return fails, dict(per_inst)

    def k7_atb(self):
        fails, rows = [], []
        for net, us in self.users.items():
            for inst, port, terms in us:
                if port != 'NODE' or not self.master.get(inst, '').startswith('atb_leaf'):
                    continue
                pins = {p: n for n, uu in self.users.items() for i, p, _ in uu if i == inst}
                others = [(i, p, t) for i, p, t in us if i != inst]
                doms = set()
                if net.startswith('RAIL_'):
                    doms.add(net[5:])
                for i, p, t in others:
                    if net in SUP or net.startswith('RAIL_'):
                        break
                    for kind, bulk in t:
                        if kind.startswith(('pdiff', 'ndiff', 'gate', 'res')):
                            doms.add(self.term_domain(i, bulk) if kind.startswith('pdiff') else self.gate_domain(i))
                doms.discard('pad')
                sel = pins.get('SEL')
                gated = [] if sel in self.removed_atb_gate else self.atb.get(sel, None)
                leaf_wells = sorted({b for k, b in terms if k.startswith('pdiff')})
                row = dict(leaf=inst, node=net, node_domains=sorted(doms), sel=sel, rtl_gate_islands=gated, leaf_pfet_wells=leaf_wells)
                rows.append(row)
                isl = [d for d in doms if d in ISLAND_BIT]
                if net.startswith('UNBOUND_'):
                    continue
                if gated is None:
                    fails.append(dict(rule='K7', leaf=inst, detail=f'select {sel} has no decode in pt_regfile.sv'))
                    continue
                for d in isl:
                    if ISLAND_BIT[d] in gated:
                        continue
                    if net.startswith('RAIL_') and all(w == 'VDD' for w in leaf_wells) and sel not in self.removed_atb_gate:
                        row['exempt'] = 'supply-monitor tap (policy: not gated); leaf wells on core VDD'
                        continue
                    fails.append(dict(rule='K7', leaf=inst, node=net, island=d, sel=sel, bus='ATB0 force' if inst.startswith('atb0') else 'ATB1 sense',
                                      detail=f'leaf on an island node but its select is not gated by island_on[{ISLAND_BIT[d]}]: '
                                             'a closed leaf connects the ATB bus/pad to diffusions in the off island'))
        return fails, rows

    def k8_pads(self):
        rows = []
        for name, (cell, straps, state) in PROVIDER_PADS.items():
            rows.append(dict(pad=name, kind='provider '+cell, rail='VDD (common ring)', straps=straps, before_spi=state))
        for net in sorted(self.chip_ports - SUP):
            us = self.users[net]
            for inst, port, terms in us:
                if not (inst.startswith('pad_') or self.master.get(inst, '').startswith('atb_pad')):
                    continue
                wells = sorted({b for k, b in terms if k.startswith('pdiff') and b})
                rails = sorted(self.rails(inst))
                core_side = sorted({f'{i}.{p}' for i, p, _ in us if i != inst})
                sw = [w for w in wells if w.startswith('RAIL_')] + [r for r in rails if r.startswith('RAIL_')]
                if self.master.get(inst, '').startswith('atb_pad'):
                    state = 'open: atb*_en resets 0 (T-gate off, wells on core VDD)'
                elif sw:
                    state = f'p-diffusion/well on {sorted(set(sw))}: an externally driven pad charges that OFF rail through the pad (back-drive)'
                elif wells:
                    state = f'hi-Z; p-diode to local {wells} (not a supply rail): pad sees only clamp leakage'
                else:
                    state = 'hi-Z; no p-diffusion on the pad net'
                rows.append(dict(pad=net, kind=self.master.get(inst, inst), inst=inst, rails=rails, pdiff_wells=wells,
                                 direct_core_connections=core_side, before_spi=state))
        return rows

    def run(self):
        k1, k1ok = self.k1_float()
        k2, k2info = self.k2_diffusion()
        k3, sw = self.k3_switch()
        k4 = self.k4_glue()
        k5 = self.k5_contention()
        k6, unb = self.k6_always_on_float()
        k7, leaves = self.k7_atb()
        pads = self.k8_pads()
        fails = k1+k2+k3+k4+k5+k6+k7
        counts = collections.Counter(f['rule'] for f in fails)
        return dict(fail=bool(fails), counts={k: counts.get(k, 0) for k in ('K1', 'K2', 'K3', 'K4', 'K5', 'K6', 'K7')},
                    fails=fails, k1_clamped_ok=k1ok, k2_gated_ok=len(k2info), switches=sw, atb_leaves=leaves, pads=pads,
                    unbound_ports_per_instance=unb, reset_expr=self.por_expr,
                    coverage=dict(instances=len({i for us in self.users.values() for i, _, _ in us}),
                                  nets=len(self.users), unbound_ports=sum(unb.values()),
                                  iso_clamp_instances=sum(1 for m in self.master.values() if m.startswith('iso_clamp'))))

    # ---- overlay / injection ------------------------------------------------------------------------------------
    def add_proposed_clamps(self):
        """An iso_clamp (core VDD) in front of every gate receiver flagged by K1; ISO = the switch's own ISO_<island>."""
        k1, _ = self.k1_float()
        cl = self.subs['iso_clamp_pex']
        C = Classifier(self.subs).cls('iso_clamp_pex')
        n = 0
        by_net = collections.defaultdict(list)
        for f in k1:
            if not f.get('contract_level'):
                by_net[f['net']].append(f)
        for net, fs in by_net.items():
            if len(fs[0]['driver_islands']) != 1:
                continue
            isl = fs[0]['driver_islands'][0]
            inst = f'isoP_{n}'; n += 1
            self.master[inst] = 'iso_clamp'; self.home[inst] = 'core'
            rx = {f['receiver'] for f in fs}
            keep, moved = [], []
            for u in self.users[net]:
                (moved if f'{u[0]}.{u[1]}' in rx else keep).append(u)
            self.users[net] = keep
            m = dict(A=net, ISO=f'ISO_{isl}', Y=net+'__iso', VDD='VDD', VSS='VSS')
            for p, nn in m.items():
                self.users[nn].append((inst, p, {(k, m.get(b, b) if b else None) for k, b in C.get(p, ())}))
            self.users[net+'__iso'] += moved
        return n

    def inject(self, what):
        kind, _, arg = what.partition('=')
        if kind == 'invert_iso':
            for n, us in list(self.users.items()):
                for u in us:
                    if u[0] == arg and u[1] == 'ISO':
                        us.remove(u)
                        isl = n.split('_', 1)[1]
                        self.users[f'island_on[{ISLAND_BIT[isl]}]'].append(u)
                        return f'{arg}.ISO moved from {n} to island_on[{ISLAND_BIT[isl]}]'
        elif kind == 'remove_clamp':
            pins = {u[1]: n for n, us in self.users.items() for u in us if u[0] == arg}
            moved = [u for u in self.users[pins['Y']] if u[0] != arg]
            for n in pins.values():
                self.users[n] = [u for u in self.users[n] if u[0] != arg]
            self.users[pins['A']] += moved
            del self.users[pins['Y']]
            return f'{arg} removed; receivers back on {pins["A"]}'
        elif kind == 'force_on':
            inst = f'isw_{arg}'
            for n, us in list(self.users.items()):
                for u in us:
                    if u[0] == inst and u[1] == 'EN':
                        us.remove(u); self.users['VDD'].append(u)
                        return f'{inst}.EN moved from {n} to VDD'
        elif kind == 'ungate_atb':
            self.removed_atb_gate.add(arg)
            return f'{arg}: island gate removed from the decode'
        raise SystemExit('unknown injection '+what)


def summarize(r, title):
    print(f'== {title}: {"FAIL" if r["fail"] else "PASS"}  {r["counts"]}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--overlay', action='store_true', help='add the proposed iso_clamps before auditing')
    ap.add_argument('--inject', action='append', default=[])
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--out', default=HERE+'/iso_audit.json')
    a = ap.parse_args()
    if a.selftest:
        res = {}
        base = Audit(); r0 = base.run(); summarize(r0, 'as-is netlist'); res['as_is'] = r0['counts']
        o = Audit(); n = o.add_proposed_clamps(); r1 = o.run(); summarize(r1, f'overlay ({n} proposed clamps)'); res['overlay'] = r1['counts']
        left = [f for f in r1['fails'] if f['rule'] == 'K1' and not f.get('contract_level') and len(f['driver_islands']) == 1]
        print(f'   overlay: {len(r1["k1_clamped_ok"])} clamped crossings pass; K1 left = {r1["counts"]["K1"]} (contract-level macro inputs and two-island nets, which a netlist overlay cannot clamp); single-island netlist K1 left = {len(left)}')
        ok = r0['counts']['K1'] > 0 and not left and len(r1['k1_clamped_ok']) >= n
        gated_leaf = next(l['sel'] for l in r0['atb_leaves'] if l['rtl_gate_islands'] and not l['node'].startswith(('RAIL_', 'UNBOUND_')))
        for inj, rule in (('invert_iso=isoP_0', 'K1'), ('remove_clamp=isoP_1', 'K1'), ('force_on=rf', 'K3'), (f'ungate_atb={gated_leaf}', 'K7')):
            x = Audit(); x.add_proposed_clamps(); msg = x.inject(inj); r = x.run()
            delta = r['counts'][rule]-r1['counts'][rule]
            hit = [f for f in r['fails'] if f['rule'] == rule and f not in r1['fails']]
            print(f'   inject {inj}: {msg} -> {rule} +{delta}  {"DETECTED" if delta > 0 else "MISSED"}')
            for f in hit[:2]:
                print('      ', json.dumps(f)[:260])
            res[inj] = dict(rule=rule, new_fails=delta, example=hit[:1])
            ok = ok and delta > 0
        res['selftest_ok'] = ok
        json.dump(res, open(HERE+'/iso_audit_selftest.json', 'w'), indent=1)
        print('SELFTEST', 'OK' if ok else 'BROKEN')
        sys.exit(0 if ok else 3)
    A = Audit()
    if a.overlay:
        print('proposed clamps added:', A.add_proposed_clamps())
    for i in a.inject:
        print('inject:', A.inject(i))
    r = A.run()
    json.dump(r, open(a.out, 'w'), indent=1, default=str)
    summarize(r, 'audit')
    print('reset:', r['reset_expr'], '| coverage:', r['coverage'])
    sys.exit(1 if r['fail'] else 0)


if __name__ == '__main__':
    main()
