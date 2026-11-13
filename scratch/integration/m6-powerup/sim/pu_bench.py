#!/usr/bin/env python3
"""M6(b) power-up / power-down / brownout bench for the always-on set, on a lumped supply model.

Stages (MANDATE "prove the bench small"):  s0 RLC only (analytic answer)  ->  s1 + extracted POR  ->
s2 + 5 extracted island switches, reset gates and island_en flops (real std cells), iso_clamp fixtures
-> s3 + pt_core_bias (bandgap/biasgen/distribution at reset values) + pt_aosc  -> s4 + provider supply-pad clamps.

Blocks are cut out of chipnet/pt_chip_full.spice (the same uniquified library the audit walks), std cells and
provider IO cells from the pinned PDK.  Run inside the pinned iic-osic-tools image (run.sh).
"""
import argparse, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
CHIP = HERE+'/../chipnet/pt_chip_full.spice'
PROJ = '/home/ubuntu/svalbard/projects/programmable_transceiver_platform'
PDK = '/foss/pdks/gf180mcuD'
ISL = ['wired', 'rf', 'pll', 'conv', 'debug']
CORNER = {'tt': ('typical', 'typical'), 'ff': ('ff', 'ff'), 'ss': ('ss', 'ss')}


def chip_subs():
    txt = open(CHIP).read()
    txt = re.sub(r'\n\+\s*', ' ', txt)
    out = {}
    for m in re.finditer(r'^\.subckt\s+(\S+)[^\n]*\n.*?^\.ends[^\n]*', txt, re.M | re.S | re.I):
        out[m.group(1)] = m.group(0)
    return out


def merge_parallel(body):
    """Collapse devices that are exactly parallel (same nodes, model and parameters) into one with m=N.
    Electrically identical; cuts the island-switch pass arrays (660-1760 identical 10 um fingers) to one element."""
    lines = body.splitlines()
    groups, order, rest = {}, [], []
    for l in lines[1:-1]:
        t = l.split()
        if t and t[0][0] in 'Xx' and not any(x.lower().startswith('m=') for x in t[1:]):
            key = ' '.join(t[1:])
            if key not in groups:
                groups[key] = [t[0], 0]; order.append(key)
            groups[key][1] += 1
        else:
            rest.append(l)
    out = [lines[0]]+rest
    for k in order:
        name, n = groups[k]
        out.append(f'{name} {k}'+(f' m={n}' if n > 1 else ''))
    return '\n'.join(out+[lines[-1]])


def closure(subs, tops):
    need, todo = [], list(tops)
    while todo:
        n = todo.pop()
        if n in need:
            continue
        need.append(n)
        for l in subs[n].splitlines()[1:]:
            t = l.split()
            if t and t[0][0] in 'Xx':
                nodes = [x for x in t[1:] if '=' not in x]
                if nodes[-1] in subs:
                    todo.append(nodes[-1])
    return need


def package():
    """Lumped supply from spec/package-channel.json + analog-architecture reduced_pdn_model."""
    pc = json.load(open(PROJ+'/spec/package-channel.json'))
    arch = json.load(open(PROJ+'/spec/analog-architecture.json'))
    n = arch['blocks']['power']['parameters']['reduced_pdn_model']['network']
    return dict(net=n, loop_l_lo=pc['pdn']['Cdie1nF_strip_0201x8_populated']['L_nH']*1e-9,
                loop_l_hi=pc['pdn']['Cdie1nF_car30mm']['L_nH']*1e-9, bond_r=0.1/8+0.1/10)


def pwl(shape, vfin, tr):
    """returns (pwl string, tstop, tmax)"""
    if shape == 'step':       # s0 only: 0.1 ns edge applied at the board node, 200 ns
        return f'0 0 0.1n {vfin}', 200e-9, None
    if shape == 'ramp':
        tail = {1e-6: 80e-3, 1e-5: 80e-3, 1e-3: 80e-3, 1.0: 0.25}[tr]
        return f'0 0 {tr:g} {vfin}', tr+tail, None
    if shape == 'short':      # ramp, simulated only through the first 300 us (oscillator running)
        return f'0 0 {tr:g} {vfin}', tr+300e-6, None
    if shape == 'down':       # ramp up 10 us, hold to 70 ms (POR released), fall in 1 ms, 5 ms off
        return f'0 0 10u {vfin} 70m {vfin} 71m 0', 76e-3, None
    if shape == 'dip2':       # brownout to 2.0 V for 1 ms, 10 us edges, after POR release
        return f'0 0 10u {vfin} 70m {vfin} 70.01m 2.0 71.01m 2.0 71.02m {vfin}', 80e-3, None
    if shape == 'dip1':       # dip to 1.0 V for 2 ms (POR re-issues reset, 17-25 ms hold)
        return f'0 0 10u {vfin} 70m {vfin} 70.01m 1.0 72.01m 1.0 72.02m {vfin}', 130e-3, None
    raise SystemExit(shape)


def deck(a):
    c, aux = CORNER[a.corner]
    m = f'{PDK}/libs.tech/ngspice/sm141064.ngspice'
    pk = package()
    n = pk['net']
    L = {'lo': pk['loop_l_lo'], 'hi': pk['loop_l_hi']}[a.loop]
    w, tstop, _ = pwl(a.shape, a.vfin, a.tr)
    o = [f'* M6 power-up bench stage={a.stage} corner={a.corner} temp={a.temp} shape={a.shape} tr={a.tr} vfin={a.vfin} cdie={a.cdie} inject={a.inject}',
         f'.include {PDK}/libs.tech/ngspice/design.ngspice', f'.lib {m} {c}', f'.lib {m} res_{aux}', f'.lib {m} mimcap_{aux}',
         f'.lib {m} diode_{aux}', f'.lib {m} bjt_{aux}', f'.lib {m} moscap_{aux}', f'.temp {a.temp}',
         '.option method=gear reltol=1e-3 rshunt=1e12 cshunt=1e-17 scale=1',
         # ---- supply: source ramp -> feed -> board cap -> bond loop -> die
         f'Vsrc src 0 PWL({w})',
         *(['Rdirect src board 1u'] if a.shape == 'step' else
           [f"Rfeed src f1 {n['feed_r']}", f"Lfeed f1 board {n['feed_l']}",
            f"Rbc board b1 {n['board_esr']}", f"Lbc b1 b2 {n['board_esl']}", f"Cbc b2 0 {n['board_c']}"]),
         f"Rbond board p1 {pk['bond_r']}", f'Lbond p1 VDD {L}',
         f"Cdie VDD d1 {a.cdie}", f"Rdie d1 0 {n['die_esr'] if a.esr else 1e-3}"]
    save = ['v(VDD)', 'v(board)', 'i(Lbond)']
    if a.stage == 0 and a.ring:     # supply + provider supply-pad clamps only (hot-plug inrush / overshoot)
        io = re.sub(r'\n\+\s*', ' ', open(HERE+'/fd_io.spice').read())

        def refinger(m):
            mult, w, l, nf = float(m.group(1)), float(m.group(2)), m.group(3), float(m.group(4))
            k = nf
            while w/k > 50e-6:
                k *= 2
            return f'm={mult*k:g} w={w/k:g} l={l} nf=1'
        for cell in ('dvdd', 'dvss', 'cor'):
            body = re.search(r'^\.SUBCKT gf180mcu_fd_io__%s .*?^\.ENDS' % cell, io, re.M | re.S).group(0)
            body = re.sub(r'm=(\S+) w=(\S+) l=(\S+) nf=(\S+)', refinger, body)
            o.append(re.sub(r' (as|ad|ps|pd|nrd|nrs|sa|sb|sd)=\S+', '', body))
        o += [f'Xdvdd{k} VDD 0 0 gf180mcu_fd_io__dvdd' for k in range(8)]
        o += [f'Xdvss{k} VDD 0 VDD gf180mcu_fd_io__dvss' for k in range(10)]
        o += [f'Xcor{k} VDD 0 VDD 0 gf180mcu_fd_io__cor' for k in range(4)]
        return o, save, tstop
    if a.stage == 0:
        return o, save, tstop
    subs = chip_subs()
    tops = ['gf180mcu_ocd_ip__por']
    if a.stage >= 2:
        tops += [f'isw_{i}_pex' for i in ISL]+['iso_clamp_pex']
    if a.stage >= 3:
        tops += ['pt_core_bias', 'pt_aosc']
    for s in reversed(closure(subs, tops)):
        o.append(merge_parallel(subs[s]) if s.startswith('isw_') else subs[s])
    # ---- POR
    o += ['Xpor VDD VDD por_unbuf 0 por_n por_high gf180mcu_ocd_ip__por', 'Cporb por_n 0 50f', 'Cpor por_high 0 50f']
    if a.inject == 'por_stuck':
        o[-3] = 'Xpor VDD VDD por_unbuf 0 por_n_dead por_high gf180mcu_ocd_ip__por\nRstuck por_n 0 1'
    save += ['v(por_n)']
    if a.stage == 1:
        return o, save, tstop
    # ---- reset path and island_en flops: real 5 V std cells as in the macro
    o.append(f'.include {PDK}/libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice')
    SC = 'gf180mcu_fd_sc_mcu7t5v0__'
    # RESET_N: host holds it high from the start (worst case: the POR alone must make the reset)
    o += ['Brstpad reset_n_pad 0 V=v(VDD)',
          f"Bbyp por_bypass 0 V={'v(VDD)' if a.bypass else '0'}",
          f'Xor por_n por_bypass por_ok VDD VDD 0 0 {SC}or2_1',
          f'Xand reset_n_pad por_ok rst_n VDD VDD 0 0 {SC}and2_1']
    # adversarial SCLK: the host clocks ones into the island-power bits from t=0 until 20 ms
    # (10 kHz, 1 us edges, amplitude follows VDD; 200 rising edges before the earliest POR release)
    o += ['Vck01 ck01 0 PULSE(0 1 5u 1u 1u 49u 100u)', 'Rck01 ck01 0 1meg',
          'Bclk sclk 0 V=(time<20m ? v(VDD)*v(ck01) : 0)', 'Bd d1in 0 V=v(VDD)']
    for k, i in enumerate(ISL+['biasena']):
        o.append(f'Xff_{i} d1in rst_n sclk en_{i} VDD VDD 0 0 {SC}dffrnq_1')
    save += ['v(rst_n)', 'v(sclk)', 'v(en_biasena)']
    for i in ISL:
        en = f'en_{i}'
        if a.inject == f'force_on_{i}':
            en = 'VDD'
        o += [f'Xisw_{i} VDD rail_{i} 0 {en} iso_{i} pg_{i} isw_{i}_pex',
              f'Crail_{i} rail_{i} 0 100p', f'Rrail_{i} rail_{i} 0 1meg',
              # iso fixture: an island output that floats high (10 Mohm leak to the ring) into a core clamp
              f'Rfl_{i} VDD a_{i} 10meg', f'Cfl_{i} a_{i} 0 20f']
        iso = f'iso_{i}'
        if a.inject == f'invert_iso_{i}':
            o.append(f'Xinv_{i} iso_{i} isob_{i} VDD VDD 0 0 {SC}inv_1')
            iso = f'isob_{i}'
        o += [f'Xclamp_{i} a_{i} {iso} y_{i} VDD 0 iso_clamp_pex', f'Cy_{i} y_{i} 0 20f']
        save += [f'v(en_{i})', f'v(rail_{i})', f'v(iso_{i})', f'v(pg_{i})', f'v(y_{i})']
    if a.stage == 2:
        return o, save, tstop
    # ---- core bias at its reset values, aosc
    cb = subs['pt_core_bias'].splitlines()[0].split()[2:]
    rm = json.load(open(PROJ+'/spec/register-map.json'))
    val = {}
    for f in rm['fields']:
        if f['name'].startswith(('core.biasgen', 'core.refchain')):
            nb = f.get('bus_bits') or f['bits']
            for k in range(nb):
                nm = 'C_'+f['name'].replace('.', '_')+(f'_{k}' if nb > 1 else '')
                d = int(f['default'] or 0)
                val[nm] = (1 if k < d else 0) if f.get('decode') == 'thermometer' else (d >> k) & 1
    nets, unknown = [], []
    for p in cb:
        if p in ('VDD',):
            nets.append('VDD')
        elif p == 'VSS':
            nets.append('0')
        elif p.startswith('RAIL_'):
            nets.append('rail_'+p[5:])
        elif p.startswith('ON_') or p.startswith('EN_'):
            nets.append('0')                       # island_on / effective enables reset 0
        elif p == 'C_core_biasgen_ena':
            nets.append('en_biasena')              # from a real flop (reset 0)
        elif p in val:
            nets.append('VDD' if val[p] else '0')
        elif p.startswith('C_'):
            unknown.append(p); nets.append('0')
        else:
            nets.append('cb_'+re.sub(r'\W', '_', p))   # outputs / observation nodes: left open
    o.append('Xcb '+' '.join(nets)+' pt_core_bias')
    o.append('* core_bias control pins without a register default (tied low): '+' '.join(unknown))
    o += [f"Baen aosc_en 0 V={'v(VDD)' if a.aosc else '0'}", 'Xaosc aosc_en aosc_clk aosc_atb VDD 0 pt_aosc', 'Caosc aosc_clk 0 50f']
    save += ['v(aosc_clk)', 'i(Vsrc)']
    if a.stage == 3:
        return o, save, tstop
    # ---- provider supply-pad clamps on the common ring: 8 supply cells, 10 ground cells, 4 corners
    io = open(HERE+'/fd_io.spice').read()
    io = re.sub(r'\n\+\s*', ' ', io)
    for cell in ('dvdd', 'dvss', 'cor'):
        mm = re.search(r'^\.SUBCKT gf180mcu_fd_io__%s .*?^\.ENDS' % cell, io, re.M | re.S)
        body = mm.group(0)

        def refinger(m):   # model bins: one finger per device, <= 50 um; fingers become the multiplier (same total W)
            mult, w, l, nf = float(m.group(1)), float(m.group(2)), m.group(3), float(m.group(4))
            k = nf
            while w/k > 50e-6:
                k *= 2
            return f'm={mult*k:g} w={w/k:g} l={l} nf=1'
        body = re.sub(r'm=(\S+) w=(\S+) l=(\S+) nf=(\S+)', refinger, body)
        body = re.sub(r' (as|ad|ps|pd|nrd|nrs|sa|sb|sd)=\S+', '', body)
        o.append(body)
    for k in range(8):
        o.append(f'Xdvdd{k} VDD 0 0 gf180mcu_fd_io__dvdd')
    for k in range(10):
        o.append(f'Xdvss{k} VDD 0 VDD gf180mcu_fd_io__dvss')
    for k in range(4):
        o.append(f'Xcor{k} VDD 0 VDD 0 gf180mcu_fd_io__cor')
    return o, save, tstop


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True)
    ap.add_argument('--stage', type=int, default=2)
    ap.add_argument('--corner', default='tt'); ap.add_argument('--temp', type=float, default=27)
    ap.add_argument('--shape', default='ramp'); ap.add_argument('--tr', type=float, default=1e-5)
    ap.add_argument('--vfin', type=float, default=3.3)
    ap.add_argument('--cdie', default='1n'); ap.add_argument('--esr', type=int, default=1)
    ap.add_argument('--loop', default='hi')
    ap.add_argument('--inject', default='none'); ap.add_argument('--bypass', type=int, default=0)
    ap.add_argument('--aosc', type=int, default=0)
    ap.add_argument('--tmax', default=''); ap.add_argument('--tstop', type=float, default=0)
    ap.add_argument('--saveall', type=int, default=0)
    ap.add_argument('--meters', type=int, default=0)
    ap.add_argument('--ring', type=int, default=0)
    a = ap.parse_args()
    o, save, tstop = deck(a)
    tstop = a.tstop or tstop
    step = tstop/4000
    a.tmax = a.tmax or f'{step:g}'
    if a.meters:      # per-block supply ammeters (0 V sources) for the leakage breakdown
        import re as _re
        new = []
        for l in o:
            if l.startswith('Xpor '):
                l = l.replace('Xpor VDD VDD', 'Xpor vm_por vm_por')
            elif l.startswith('Xisw_'):
                l = _re.sub(r'^(Xisw_\w+) VDD ', r'\1 vm_isw ', l)
            elif l.startswith('Xcb VDD '):
                l = l.replace('Xcb VDD ', 'Xcb vm_cb ', 1)
            elif l.startswith(('Xdvdd', 'Xdvss', 'Xcor')):
                l = l.replace(' VDD', ' vm_ring')
            elif l.startswith('Xaosc '):
                l = l.replace(' VDD 0 pt_aosc', ' vm_aosc 0 pt_aosc')
            new.append(l)
        o = new+[f'Vm_{k} VDD vm_{k} 0' for k in ('por', 'isw', 'cb', 'ring', 'aosc')]
        save += [f'i(Vm_{k})' for k in ('por', 'isw', 'cb', 'ring', 'aosc')]
    o.append('.save all' if a.saveall else '.save '+' '.join(save))
    o += ['.control', f'tran {step:g} {tstop:g} 0 {a.tmax}', 'set filetype=binary', f'write {a.name}.raw', '.endc', '.end']
    open(f'{HERE}/runs/{a.name}.sp', 'w').write('\n'.join(o)+'\n')
    json.dump(vars(a), open(f'{HERE}/runs/{a.name}.cfg.json', 'w'))


if __name__ == '__main__':
    main()
