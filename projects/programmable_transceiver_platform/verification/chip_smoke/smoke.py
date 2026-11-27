#!/usr/bin/env python3
"""Chip-level power-up smoke test of pt_rf / pt_wired, wired from the top-level netlist (verification/chip_smoke/README.md).

    smoke.py --chip rf|wired [--tree DIR] [--netlist TOP.spice] [--macro MACRO.pnl.v] [--out DIR] [--mutate SPEC]

--tree     repository (worktree) whose project files are used: conn, ctl_ports, register map, bring-up register access, gen_netlist
           (default: the tree this script is in)
--netlist  top-level netlist; default: KH_CONN=1 integration/signoff/lvs/gen_netlist.py of --tree (the assembly's LVS
           reference). A KLayout-extracted layout netlist with the same instance / pin names also works.
--macro    digital macro Verilog (default scratch/digital-macro-baseline/<chip>/pt_digital_macro.pnl.v, gate level)
--mutate   negative control, comma-separated: 'c_port[bit]' unbinds that c_* net at its first consumer pin in a copy
           of the netlist (fresh NC net), 'pad:<PAD net>:<pin>' unbinds a pin of the pad cell on that pad,
           'swap:<inst>:<pinA>:<pinB>' exchanges the nets of two pins of one instance.
Exit 0 only with no fault. Summary: <out>/summary.json (faults listed in full, coverage, what was exercised).
"""
import argparse, collections, hashlib, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument('--chip', required=True, choices=('rf', 'wired'))
ap.add_argument('--tree'); ap.add_argument('--netlist'); ap.add_argument('--macro'); ap.add_argument('--out')
ap.add_argument('--mutate'); ap.add_argument('--keep', action='store_true', help='keep the compiled bench')
a = ap.parse_args()
ROOT = os.path.abspath(a.tree or os.path.join(HERE, '../../../..'))
P = ROOT+'/projects/programmable_transceiver_platform'
MAIN = os.environ.get('ASM_DATA', '/home/ubuntu/svalbard')      # untracked data (macro netlist, PDK cell models): main checkout
macro = a.macro or next((d+f'/scratch/digital-macro-baseline/{a.chip}/pt_digital_macro.pnl.v' for d in (ROOT, MAIN)
                         if os.path.exists(d+f'/scratch/digital-macro-baseline/{a.chip}/pt_digital_macro.pnl.v')), None)
SC = os.environ.get('SMOKE_SC', MAIN+'/scratch/integration/signoff-run/pc/pdk/ciel/gf180mcu/versions/'
                    '792ef67037d74c8c51811eab3ce23cf793491296/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog')
OUT = os.path.abspath(a.out or f'{ROOT}/scratch/chip_smoke/{a.chip}'+(f'-mut' if a.mutate else ''))
os.makedirs(OUT, exist_ok=True)
os.environ['OMP_NUM_THREADS'] = '1'
FAULTS, WARN, LOG = [], [], open(OUT+'/smoke.log', 'w')
def log(*x):
    s = ' '.join(str(y) for y in x); print(s); LOG.write(s+'\n'); LOG.flush()
def fault(check, detail): FAULTS.append(dict(check=check, detail=detail)); log('FAULT', check, detail)
def warn(check, detail): WARN.append(dict(check=check, detail=detail)); log('WARN', check, detail)
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]
t0 = time.time()

# ------------------------------------------------------------------ netlist (+ optional mutation)
nl = a.netlist
if not nl:
    nl = OUT+'/pt_chip_top.ref.spice'
    r = subprocess.run([sys.executable, P+'/integration/signoff/lvs/gen_netlist.py', nl, '--chip', a.chip],
                       env=dict(os.environ, KH_CONN='1'), capture_output=True, text=True)
    log(r.stdout.strip(), r.stderr.strip()[-400:])
    if r.returncode: sys.exit(f'gen_netlist failed: {r.stderr[-400:]}')
mutation = None
if a.mutate:
    txt = open(nl).read().split('\n'); mutation = []
    def unbind(cond, newname):
        pins = {}
        for k, l in enumerate(txt):
            t = l.split()
            if not t: continue
            if t[0].lower() == '.subckt': pins[t[1]] = t[2:]; continue
            if t[0][0] in 'Xx':
                m = t[-1]; ps = pins.get(m, [])
                for j, n in enumerate(t[1:-1]):
                    if j < len(ps) and cond(t[0][1:], m, ps[j], n):
                        t[1+j] = newname; txt[k] = ' '.join(t)
                        return f'{t[0][1:]}.{ps[j]} (was {n}) -> {newname}'
    for k, spec in enumerate(a.mutate.split(',')):
        if spec.startswith('swap:'):                # swap the nets on two pins of one instance (a misbound wire)
            _, i0, pa, pb = spec.split(':'); r = None; hold = {}
            for kk, l in enumerate(txt):
                t = l.split()
                if not t: continue
                if t[0].lower() == '.subckt': hold[t[1]] = t[2:]; continue
                if t[0][1:] == i0:
                    ps = hold[t[-1]]; x, y = 1+ps.index(pa), 1+ps.index(pb); t[x], t[y] = t[y], t[x]; txt[kk] = ' '.join(t)
                    r = f'{i0}.{pa} <-> {i0}.{pb} ({t[y]} <-> {t[x]})'; break
        elif spec.startswith('pad:'):
            _, padnet, p0 = spec.split(':')        # the pad cell whose PAD pin is on net padnet
            hold = {}
            for l in txt:
                t = l.split()
                if t and t[0].lower() == '.subckt': hold[t[1]] = t[2:]
            i0 = next((t[0][1:] for t in (l.split() for l in txt) if t and t[0][0] in 'Xx'
                       and 'PAD' in hold.get(t[-1], []) and t[1+hold[t[-1]].index('PAD')] == padnet), None)
            r = i0 and unbind(lambda i, m, p, n: i == i0 and p == p0, f'NC_smoke_mut{k}')
        else:
            r = unbind(lambda i, m, p, n: n == spec and m != 'pt_digital_macro', f'NC_smoke_mut{k}')
        assert r, f'mutation {spec}: nothing to unbind'
        mutation.append(r); log('mutation:', r)
    nl2 = OUT+'/mutated.spice'; open(nl2, 'w').write('\n'.join(txt)); nl = nl2

# ------------------------------------------------------------------ build
B = OUT+'/bench'
r = subprocess.run([sys.executable, HERE+'/gen_bench.py', '--chip', a.chip, '--netlist', nl, '--project', P, '--macro-v', macro, '--out', B],
                   capture_output=True, text=True)
log(r.stdout.strip())
if r.returncode: sys.exit('gen_bench failed: '+r.stderr[-800:])
MONJ = json.load(open(B+'/monitor.json'))
for f in MONJ['findings']: fault('structure', f)
MON = MONJ['monitors']; PORT = MONJ['ports']
r = subprocess.run(['iverilog', '-g2012', '-DFUNCTIONAL', '-DUSE_POWER_PINS', '-s', 'smoke_tb', '-o', B+'/tb.vvp',
                    SC+'/primitives.v', SC+'/gf180mcu_fd_sc_mcu7t5v0.v', macro, HERE+'/smoke_pads.v',
                    B+'/smoke_stubs.v', B+'/smoke_chip.v', B+'/smoke_tb.v'], capture_output=True, text=True)
errs = [l for l in r.stderr.split('\n') if 'error' in l.lower()]
if r.returncode or errs: sys.exit('iverilog failed:\n'+'\n'.join(errs[:20]))
log(f'built in {time.time()-t0:.0f} s')

# ------------------------------------------------------------------ simulator
class Sim:
    def __init__(s):
        s.p = subprocess.Popen(['vvp', '-n', B+'/tb.vvp'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1, cwd=B)
        s.n = 0
    def cmd(s, c):
        s.p.stdin.write(c+'\n'); s.p.stdin.flush(); s.n += 1
        while True:
            l = s.p.stdout.readline()
            if not l: raise RuntimeError(f'simulator ended at command {c!r}')
            l = l.rstrip('\n')
            if l[:2] in ('OK', 'R ', 'S ', 'V ', 'ER'):
                if l.startswith('ER'): raise RuntimeError(f'{c!r}: {l}')
                return l
            LOG.write('sim: '+l+'\n')
    def drive(s, port, v): s.cmd(f'D {PORT[port]} {v}')
    def sample(s, port): return s.cmd(f'T {PORT[port]}')[2:]
    def wait(s, ns): s.cmd(f'W {int(ns)}')
    def xfer(s, c, ad, d):
        bits = s.cmd(f'X {c} {ad} {d}')[2:]
        return int(bits, 2) if set(bits) <= set('01') else bits
    def snap(s):
        v = s.cmd('S')[2:]
        assert len(v) == len(MON), (len(v), len(MON))
        return v
    def close(s):
        try: s.p.stdin.write('Q\n'); s.p.stdin.flush(); s.p.wait(30)
        except Exception: s.p.kill()
sim = Sim()

# ------------------------------------------------------------------ register map (of --tree)
sys.path.insert(0, P+'/tools/bringup'); sys.path.insert(0, P+'/integration/chips')
import regs as R
import check_top as ct
CTL = ct.load_ctl(open(P+'/integration/chips/ctl_ports.txt').read())
FIELDS = R.FIELDS

class Spi:
    def xfer(s, c, ad, d):
        v = sim.xfer(c, ad, d)
        if isinstance(v, str):
            fault('spi_miso', f'read 0x{ad:02X}: MISO pad gave {v} (X/Z)')
            if sum(f['check'] == 'spi_miso' for f in FAULTS) >= 3: raise Abort('SPI_MISO pad not 0/1')
            return 0
        return v
regs = R.Regs(Spi(), a.chip)

# monitor index
IDX = collections.defaultdict(list)
for k, m in enumerate(MON): IDX[m['kind']].append(k)
CTLM = {}       # port bit -> macro monitor index
CTLS = collections.defaultdict(list)    # port bit -> [stub monitor index]
for k in IDX['ctl_macro']: CTLM[MON[k]['port']] = k
for k in IDX['ctl_stub']: CTLS[MON[k]['port']].append(k)
CONSUMED = [p for p in CTLM if CTLS[p]]          # c_* bits with a consumer on this chip
IOI = {MON[k]['pin']: k for k in IDX['macro_io']}
seen = collections.defaultdict(set)              # stub monitor index -> values seen while equal to the macro
conn_bad = set()

def check_conn(v, where):
    """every consumer pin equals its macro port and is 0/1; every pad link equals its macro pin; rails at level"""
    for p in CONSUMED:
        mv = v[CTLM[p]]
        for k in CTLS[p]:
            sv = v[k]
            if sv != mv or sv not in '01':
                key = (p, MON[k]['inst'], MON[k]['pin'])
                if key not in conn_bad:
                    conn_bad.add(key)
                    fault('ctl_wire', f'{where}: {p} macro={mv} at {MON[k]["inst"]}.{MON[k]["pin"]}={sv}')
            else: seen[k].add(sv)
    for k in IDX['padlink']:
        m = MON[k]; pv = v[[j for j in IDX['pad'] if MON[j]['inst'] == m['inst'] and MON[j]['pin'] == m['pin']][0]]
        if pv != v[k] or pv not in '01':
            key = ('padlink', m['inst'], m['pin'])
            if key not in conn_bad: conn_bad.add(key); fault('pad_wire', f'{where}: pad {m["inst"]}.{m["pin"]}={pv} vs macro {m["macro"]}={v[k]}')
    for k in IDX['rail']:
        m = MON[k]
        if v[k] != str(m['want']):
            key = ('rail', m['inst'], m['pin'])
            if key not in conn_bad: conn_bad.add(key); fault('rail', f'{where}: {m["inst"]}.{m["pin"]}={v[k]}, conn says {"VDD" if m["want"] else "VSS"}')

def ctl_val(v, base, side='macro'):
    """value of a c_* port (int, or None if any bit is not 0/1); side 'stub' = first consumer of each bit"""
    w = CTL[base]['width']; x = 0
    for i in range(w):
        p = base if w == 1 else f'{base}[{i}]'
        k = CTLM[p] if side == 'macro' else (CTLS[p][0] if CTLS[p] else None)
        if k is None: return None
        if v[k] not in '01': return None
        x |= int(v[k]) << i
    return x
USED_BASES = sorted({MON[CTLM[p]]['base'] for p in CONSUMED}, key=lambda b: list(CTL).index(b))

def commit():
    regs.write_reg(R.A_COMMIT, 1)
    info = regs.read(R.A_ERRINFO) >> 8
    if info:
        err = regs.read(R.A_CFGERR); regs.write_reg(R.A_CFGERR, 0x7F); regs.write_reg(R.A_COMMIT, 2)      # clear, revert shadow
        return f'ERROR_INFO=0x{info:02X} CONFIG_ERROR=0x{err:02X}'
    return None

# ================================================================== 1. power up, reset through RESET_N
log('== 1 power up')
for p, v in (('VSS', 0), ('VDD', 0), ('RESET_N', 0), ('SPI_CS_N', 1), ('SPI_SCLK', 0), ('SPI_MOSI', 0)): sim.drive(p, v)
for k in range(10): sim.drive(f'H2D[{k}]', 0)
sim.drive('H2D_CLK', 0)
sim.wait(1000)
sim.drive('VDD', 1); sim.wait(2000)
v_pwr = sim.snap()
for k in IDX['pad']:
    m = MON[k]
    if m['pin'] not in ('PAD', 'Y', 'ASIG5V') and v_pwr[k] not in '01':
        fault('pad_tie', f'pad {m["inst"]} ({m["cell"]}).{m["pin"]} = {v_pwr[k]} after power-up (net {m["net"]})')
cnt_por = 0
for k in IDX['macro_io']:
    if MON[k]['pin'] == 'por_n' and v_pwr[k] != '0': fault('por', f'por_n = {v_pwr[k]} before the POR releases')
sim.cmd('O 1'); sim.wait(2000)      # POR stub releases (its vdd3v3 / vss / ena pins must be at their levels)
v = sim.snap()
if v[IOI['por_n']] != '1': fault('por', f'por_n at the macro = {v[IOI["por_n"]]} after the POR released')
if v[IOI['reset_n_pad']] != '0': fault('reset_pad', f'RESET_N pad held low -> macro reset_n_pad = {v[IOI["reset_n_pad"]]}')
sim.drive('RESET_N', 1); sim.wait(2000)
v = sim.snap()
if v[IOI['reset_n_pad']] != '1': fault('reset_pad', f'RESET_N pad high -> macro reset_n_pad = {v[IOI["reset_n_pad"]]}')
check_conn(v, 'after reset')
v_reset0 = v

# ================================================================== 5. pads: POR_BYPASS default, input pads enabled
log('== 5 pads')
if v[IOI['por_bypass']] != '0': fault('por_bypass', f'POR_BYPASS pad open -> macro por_bypass = {v[IOI["por_bypass"]]} (pull-down must give 0)')
in_pads, out_pads = 0, 0
pads = collections.defaultdict(dict)
for k in IDX['pad']: pads[MON[k]['inst']][MON[k]['pin']] = (v[k], MON[k]['net'], MON[k]['cell'])
for inst, d in pads.items():
    cell = next(iter(d.values()))[2]
    if 'Y' not in d: continue
    ynet = d['Y'][1]
    is_in = not ynet.startswith('NC_')
    if cell.endswith('in_c'): in_pads += 1; continue
    if is_in:
        in_pads += 1
        if d['IE'][0] != '1': fault('pad_ie', f'input pad {inst}: IE = {d["IE"][0]} (net {d["IE"][1]}), Y drives {ynet}')
        if d['OE'][0] != '0': fault('pad_oe', f'input pad {inst}: OE = {d["OE"][0]} after reset')
    else:
        out_pads += 1
log(f'pads: {in_pads} input pads checked (IE = 1, OE = 0), {out_pads} output / analog pads')
for p in ('SPI_CS_N', 'SPI_SCLK', 'SPI_MOSI'): sim.drive(p, 'z')
sim.wait(500)
pulls = {p: sim.sample(p) for p in ('SPI_CS_N', 'SPI_SCLK', 'SPI_MOSI', 'RESET_N', 'POR_BYPASS')}
sim.drive('SPI_CS_N', 1); sim.drive('SPI_SCLK', 0); sim.drive('SPI_MOSI', 0)
for p, want in (('SPI_CS_N', '1'), ('SPI_SCLK', '0'), ('SPI_MOSI', '0'), ('POR_BYPASS', '0')):
    if pulls[p] != want: fault('pad_pull', f'{p} undriven reads {pulls[p]}, pad pull should give {want}')

class Abort(Exception): pass
host = {}; walk = dict(fields=0, writes=0, rejected=[]); pulls = locals().get('pulls', {}); aborted = None
try:
    # ================================================================== 2. reset values at the stub inputs
    log('== 2 reset values')
    ident = regs.read(R.A_ID); chip_id = regs.read(0xFE); h = regs.read(R.A_HASH); rs = regs.read(R.A_RESET)
    if ident != R.ID:
        fault('spi_id', f'ID = 0x{ident:04X}, want 0x{R.ID:04X}')
        raise Abort('no SPI register access through the pads')
    if chip_id != R.CHIP_ID[a.chip]: fault('chip_id', f'status.chip.id = {chip_id}, want {R.CHIP_ID[a.chip]}')
    if h != R.HASH: warn('map_hash', f'macro map hash 0x{h:04X} != register map 0x{R.HASH:04X} of {ROOT} (macro netlist and map out of step)')
    if (rs >> 2) & 1: fault('por_bypass', f'RESET_STATUS = 0x{rs:04X}: strap bit set with the pad open')
    islands = [f for f in FIELDS if f.startswith('debug.island_power.') and a.chip in FIELDS[f]['chips']]
    regs.set(**{f: 1 for f in islands}); e = commit()
    if e: fault('island_power', f'commit of island power rejected: {e}')
    sim.wait(2000)
    st = regs.read(R.A_ISLAND)
    want_isl = sum(1 << FIELDS[f]['chunks'][0]['reg_lsb'] for f in islands)
    if st & 0x3F != want_isl: fault('island_pg', f'ISLAND_STATUS = 0x{st:04X}, want power-good 0x{want_isl:02X} (switch EN -> PG -> macro path)')
    v = sim.snap(); check_conn(v, 'islands on')
    reset_bad = []
    for b in USED_BASES:
        want = CTL[b]['reset']; got = ctl_val(v, b, 'stub'); gm = ctl_val(v, b)
        if got != want:
            reset_bad.append(b)
            (fault if gm == want else warn)('reset_value', f'{b}: stub input {got} macro {gm}, documented reset {want}')
    v_isl = v
    # islands-off values (the gating rule): every consumed port reads 0 or its reset
    for b in USED_BASES:
        g0 = ctl_val(v_reset0, b, 'stub')
        if g0 not in (0, CTL[b]['reset']): warn('reset_islands_off', f'{b} = {g0} with every island off (want 0 or reset {CTL[b]["reset"]})')

    # ================================================================== 3. register walk: one field at a time
    log('== 3 field walk')
    regs.set(**{'core.biasgen.ena': 1, 'core.refchain.bgap_ena': 1}); e = commit()
    if e: fault('bias', f'bias enable commit rejected: {e}')
    regs.clocks(10)          # B54: >= 256 SCLK after bgap_ena before the interlock releases ref_sel_vbg / dist_en
    base_v = sim.snap(); check_conn(base_v, 'bias on')
    STICKY = {'core.biasgen.ena': 1, 'core.refchain.bgap_ena': 1}
    def fields_of(b):
        return [f for f in FIELDS if re.search(r'(^|[+ ,])'+re.escape(f)+r'($|[+ ,])', CTL[b]['field'])]
    PORT_FIELDS = {b: fields_of(b) for b in USED_BASES}
    FIELD_PORTS = collections.defaultdict(set)
    for b, fs in PORT_FIELDS.items():
        for f in fs: FIELD_PORTS[f].add(b)
    PREREQ = {'rfpll.state.state': {'rfpll.config.lo_mode': 2}}       # c_qvco_en family: state active AND lo_mode on-chip
    NOLEAF = R.MAP.get('chip_atb_no_leaf', {}).get(a.chip, {})
    def satisfy(setv, target):
        """add the field values the register map's commit rules require (eq / in conditions only)"""
        val = lambda g: setv[g] if g in setv else regs.get(g)
        def holds(c):
            g, op, arg = c
            if g not in FIELDS: return True
            if op == 'eq': return val(g) == arg[0]
            if op == 'in': return val(g) in arg
            if op == 'ne': return val(g) != arg[0]
            if op == 'nin': return val(g) not in arg
            return True
        for _ in range(6):
            changed = False
            for rule in R.MAP['rules']:
                trig = (all(holds(c) for c in rule.get('if_all') or []) and (any(holds(c) for c in rule['if_any']) if rule.get('if_any') else True))
                if not (rule.get('if_all') or rule.get('if_any')) or not trig: continue
                for c in rule.get('then_all') or []:
                    if c[1] in ('eq', 'in', 'ne', 'nin') and c[0] in FIELDS and not holds(c) and c[0] != target:
                        pick = c[2][0] if c[1] in ('eq', 'in') else next((y for y in legal(c[0]) if y not in c[2]), None)
                        if pick is not None: setv[c[0]] = pick; changed = True
            if not changed: break
        return setv
    SKIP = set(islands) | {f for f in FIELDS if f.startswith('debug.pgood_override.')}
    def legal(f):
        d = FIELDS[f]; w = d['bits']
        bus = {'debug.atb.atb0': 'atb0', 'debug.atb.atb1': 'atb1'}.get(f)
        if d.get('allowed'): return [x for x in d['allowed'] if not (bus and x in NOLEAF.get(bus, []))]
        lo = d.get('minimum') or 0; hi = d.get('maximum'); hi = (1 << w)-1 if hi is None else hi
        return list(range(lo, hi+1)) if hi-lo < 4096 else [lo, hi, (lo+hi)//2]
    def default(f):
        d = FIELDS[f]['default']
        if isinstance(d, str): return FIELDS[f]['values'].index(d)
        return int(d or 0)
    def candidates(f):
        L = legal(f); r = regs.get(f); w = FIELDS[f]['bits']; m = (1 << w)-1
        c = []
        vals = FIELDS[f].get('values')
        if vals and 'active' in vals: c.append(vals.index('active'))
        c += [(~r) & m, max(L), min(L)] + [r ^ (1 << k) for k in range(w)]
        out = []
        for x in c:
            if x in L and x != r and x not in out: out.append(x)
        return out
    walk = dict(fields=0, writes=0, rejected=[], unexpected=collections.defaultdict(set), no_change=[])
    def toggled(b):
        w = CTL[b]['width']
        return all(len(seen[k]) == 2 for i in range(w) for k in CTLS[b if w == 1 else f'{b}[{i}]'])
    def try_field(f, x, pre=None):
        global base_v
        setv = dict(pre or {}); setv[f] = x
        setv = satisfy(setv, f)
        regs.set(**setv); e = commit(); walk['writes'] += 1
        if e:
            regs.shadow = {ad: rv for ad, rv in regs.shadow.items()}      # shadow reverted in hardware: resync below
            for ad in {c['addr'] for g in setv for c in FIELDS[g]['chunks']}: regs.shadow[ad] = regs.read(ad)
            walk['rejected'].append(f'{f}={x}: {e}'); return False
        # read back over SPI (MISO pad): the written bits
        for g in setv:
            if FIELDS[g]['store'] is None: continue        # not stored (reads 0 by design)
            rv = 0
            for c in FIELDS[g]['chunks']:
                rv |= ((regs.read(c['addr']) >> c['reg_lsb']) & ((1 << c['width'])-1)) << c['field_lsb']
            if rv != setv[g]: fault('readback', f'{g}: wrote {setv[g]}, read back {rv} over SPI_MISO')
        v = sim.snap(); check_conn(v, f'{f}={x}')
        allowed = set().union(*(FIELD_PORTS.get(g, set()) for g in setv))
        for b in USED_BASES:
            if ctl_val(v, b) != ctl_val(base_v, b) and b not in allowed: walk['unexpected'][f].add(b)
        for b in FIELD_PORTS.get(f, ()):
            if CTL[b]['enc'] == 'direct' and ctl_val(v, b) != x and not (b in reset_bad):
                walk['no_change'].append(f'{b}: {f}={x} -> port {ctl_val(v, b)}')
        # restore
        regs.set(**{g: default(g) if g not in STICKY else STICKY[g] for g in setv}); e = commit()
        if e: fault('restore', f'restoring {list(setv)} rejected: {e}')
        v2 = sim.snap(); check_conn(v2, f'{f} restored')
        for b in USED_BASES:
            if ctl_val(v2, b) != ctl_val(base_v, b): warn('restore', f'{b} = {ctl_val(v2, b)} after restoring {f}, was {ctl_val(base_v, b)}')
        base_v = v2
        return True
    chip_fields = [f for f in FIELDS if a.chip in FIELDS[f]['chips'] and f not in SKIP]
    for f in chip_fields:
        walk['fields'] += 1
        cs = candidates(f)
        # one new value; for a multi-bit field that reaches a port, also every legal single-bit flip, so two swapped
        # bits of one bus (both driven, same value under ~reset) differ at some write
        if f in FIELD_PORTS and FIELDS[f]['bits'] > 1:
            r0 = regs.get(f); cs = cs[:1] + [x for x in cs[1:] if bin(x ^ r0).count('1') == 1]
        else: cs = cs[:1]
        for x in cs: try_field(f, x)
    # second pass: ports whose bits have not all toggled at every consumer
    for b in USED_BASES:
        if toggled(b): continue
        for f in PORT_FIELDS[b]:
            if f in SKIP or a.chip not in FIELDS[f]['chips']: continue
            L = legal(f)
            for x in candidates(f) + ([y for y in L if y != regs.get(f)] if len(L) <= 64 else []):
                try_field(f, x, PREREQ.get(f))
                if toggled(b): break
            if toggled(b): break
    for f, bs in walk['unexpected'].items():
        ind = {b for b in bs if 'rx_en_aux' in CTL[b]['enc']}      # documented through the macro's rx_en_aux decode
        if ind: walk.setdefault('indirect', {})[f] = sorted(ind)
        bs = bs - ind
        if bs: warn('side_effect', f'{f}: also changed {sorted(bs)} (not documented for this field in ctl_ports.txt)')
    for s in walk['no_change']: warn('direct_value', s)
    for s in walk['rejected']: log('rejected:', s)

    # ================================================================== 4. host link: D2H data on the output pads
    log('== 4 host link')
    d2h = [f'D2H[{k}]' for k in range(10)] + ['D2H_CLK']
    off = {p: sim.sample(p) for p in d2h}
    if any(x != 'z' for x in off.values()): fault('d2h_off', f'D2H pads driven with d2h_enable = 0: {off}')
    hl = {'hostio.controls.d2h_enable': 1}
    if 'debug.host_link.rate' in FIELDS: hl['debug.host_link.rate'] = 2        # bring-up rate div4 (HL-B6)
    regs.set(**hl); e = commit()
    if e: fault('host_link', f'd2h_enable commit rejected: {e}')
    sim.cmd('H 3.2 1')                       # host DDR clock at the clockmux HOST_CLK output (156 MHz)
    sim.wait(3000)
    v = sim.snap(); check_conn(v, 'host link enabled')
    if v[IOI['d2h_oe']] != '1': fault('host_link', f'macro d2h_oe = {v[IOI["d2h_oe"]]} after d2h_enable')
    if v[IOI['host_word_clk']] not in '01': fault('host_link', f'host_word_clk at the macro = {v[IOI["host_word_clk"]]}')
    regs.write_reg(0x01, 0); regs.write_reg(0x01, 1)      # link start: the framer sends its training quads (sequence.host_link)
    caps = sim.cmd('C 400 2')[2:].split()
    regs.write_reg(0x01, 0)
    toggles, prev, mism = collections.Counter(), None, 0
    for c in caps:
        pad, mac = c[:11], c[11:]
        if pad != mac or set(pad) - set('01'):
            mism += 1
            if mism <= 3: fault('d2h_pad', f'D2H pads {pad} vs macro d2h_pin/d2h_clk_pin {mac} (bit 10..0 = D2H[9..0], D2H_CLK)')
        if prev:
            for k in range(11):
                if pad[k] != prev[k]: toggles[(['D2H[%d]' % j for j in range(9, -1, -1)] + ['D2H_CLK'])[k]] += 1
        prev = pad
    for p in d2h:
        if toggles[p] == 0: fault('host_link', f'{p} pad never toggled during the link start (training quads)')
    host = dict(samples=len(caps), sample_ns=2, mismatches=mism, toggles=dict(toggles))
    log('host link:', host)
    sim.cmd('H 3.2 0')
    regs.set(**{'hostio.controls.d2h_enable': 0}); commit()

    # ================================================================== reset again through RESET_N: back to the reset state
    log('== reset pulse')
    regs.set(**{'core.aosc.enable': 1}); commit()
    sim.drive('RESET_N', 0); sim.wait(1000); sim.drive('RESET_N', 1); sim.wait(1000)
    v = sim.snap(); check_conn(v, 'second reset')
    for b in USED_BASES:
        if ctl_val(v, b) != ctl_val(v_reset0, b): fault('reset_again', f'{b} = {ctl_val(v, b)} after the RESET_N pulse, {ctl_val(v_reset0, b)} after the first reset')


except Abort as e:
    aborted = str(e); fault('aborted', f'remaining steps skipped: {e}')

# ================================================================== summary
sim.close()
toggled = globals().get('toggled') or (lambda b: False)
cov_ports = [b for b in USED_BASES if toggled(b)]
untoggled = {}
for b in USED_BASES:
    if b in cov_ports: continue
    w = CTL[b]['width']; bits = []
    for i in range(w):
        p = b if w == 1 else f'{b}[{i}]'
        for k in CTLS[p]:
            if len(seen[k]) < 2: bits.append(f'{i}@{MON[k]["inst"]}.{MON[k]["pin"]}:{"".join(sorted(seen[k])) or "-"}')
    untoggled[b] = bits
summary = dict(chip=a.chip, tree=ROOT, netlist=os.path.abspath(nl), netlist_sha=sha(nl), macro=macro, macro_sha=sha(macro),
               mutation=mutation, result='FAIL' if FAULTS else 'PASS', faults=FAULTS, warnings=WARN,
               coverage=dict(ctl_ports_on_chip=len(USED_BASES), ctl_bits_on_chip=len(CONSUMED),
                             consumer_pins=sum(len(CTLS[p]) for p in CONSUMED), ports_toggled_0_1=len(cov_ports),
                             untoggled=untoggled, fields_walked=walk['fields'], commits=walk['writes'], rejected=walk['rejected'], documented_indirect=walk.get('indirect', {})),
               pads=dict(input_pads_checked=in_pads, undriven_levels=pulls), host_link=host,
               aborted=aborted, sim_commands=sim.n, seconds=round(time.time()-t0))
json.dump(summary, open(OUT+'/summary.json', 'w'), indent=1)
log(f'CHIP_SMOKE {a.chip} {summary["result"]}: {len(FAULTS)} faults, {len(WARN)} warnings, {len(cov_ports)}/{len(USED_BASES)} c_* ports toggled at every consumer, {summary["seconds"]} s -> {OUT}/summary.json')
if not a.keep:
    for x in ('tb.vvp',):
        try: os.remove(B+'/'+x)
        except OSError: pass
sys.exit(1 if FAULTS else 0)
