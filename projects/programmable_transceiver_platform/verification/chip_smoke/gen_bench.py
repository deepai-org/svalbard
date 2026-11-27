#!/usr/bin/env python3
"""Chip power-up smoke bench, structural part: Verilog top of one chip built ONLY from a top-level netlist.

    gen_bench.py --chip rf|wired --netlist TOP.spice --project P --macro-v MACRO.v --out DIR [--top pt_chip_top]

Every X line of the netlist's top subckt becomes one instance and every net one wire, so the bench is wired exactly as
the netlist is (a missing / misbound top-level wire changes what the bench sees). Instance kinds:
  pt_digital_macro    the real digital macro (gate-level netlist or RTL), bus pins regrouped from the netlist's bit pins;
                      VDD / VSS (grid, not netlist pins) to the top VDD / VSS nets
  provider pad cells  smoke_pads.v (behavioural, strict: an X / Z on a control pin gives X at Y / PAD)
  everything else     a generated stub module per master (smoke_stubs.v): ports = the netlist subckt pins, no behaviour
                      except: island switch PG = EN & VDD & !VSS (ISO = !PG), iso clamp Y = A & !ISO, iso_pd Y = 0 while
                      ISO, por porb = (release & vdd3v3 & !vss & ena), clockmux HOST_CLK = the bench host clock; every
                      other output pin (direction from the conn) drives 0.
Expectations (written to DIR/monitor.json) come from the conn, independently of the netlist: for every c_* bit of
ctl_ports.txt its consumer pins (inst.pin) and its macro port; every provider pad cell's pins; every stub pin the conn
binds to VDD / VSS. smoke_tb.v dumps all of them on an 'S' command (one char per bit)."""
import argparse, collections, json, os, re, sys

ap = argparse.ArgumentParser()
ap.add_argument('--chip', required=True); ap.add_argument('--netlist', required=True); ap.add_argument('--project', required=True)
ap.add_argument('--macro-v', required=True); ap.add_argument('--out', required=True); ap.add_argument('--top', default='pt_chip_top')
a = ap.parse_args()
P = a.project
sys.path.insert(0, P+'/integration/chips')
import check_top as ct
# provider pad cells (pins = their layout top-cell labels, as integration/chips/provider_io.py of a KH_CONN tree has them);
# kept here so the bench also runs on a tree without provider_io.py (a pre-KH_CONN netlist then simply fails)
CELL_PINS = {'gf180mcu_fd_io__bi_24t': 'A CS DVDD DVSS IE OE PAD PD PU SL VDD VSS Y'.split(),
             'selected_host_output': 'A CS DVDD DVSS IE OE PAD PD PDRV0 PDRV1 PU SL VDD VSS Y'.split(),
             'gf180mcu_fd_io__in_c': 'DVDD DVSS PAD PD PU VDD VSS Y'.split(),
             'gf180mcu_fd_io__asig_5p0': 'ASIG5V DVDD DVSS VDD VSS'.split(),
             'gf180mcu_fd_io__dvdd': 'DVDD DVSS VSS'.split(), 'gf180mcu_fd_io__dvss': 'DVDD DVSS VDD'.split()}
def ctl_bits():
    out = []
    for line in open(P+'/integration/chips/ctl_ports.txt'):
        if not line.strip() or line.startswith('#'): continue
        c = [x.strip() for x in line.split('|')]
        w = int(c[1]); out += [c[0]] if w == 1 else [f'{c[0]}[{k}]' for k in range(w)]
    return out

# ---------------------------------------------------------------- netlist
def spice_lines(path):
    out = []
    for raw in open(path):
        s = raw.rstrip('\n')
        if not s.strip() or s.lstrip().startswith('*'): continue
        if s.startswith('+') and out: out[-1] += ' '+s[1:]
        else: out.append(s)
    return out

subckt, top_ports, xs, cur = {}, None, [], None
for s in spice_lines(a.netlist):
    t = s.split()
    k = t[0].lower()
    if k == '.subckt':
        cur = t[1]; subckt[cur] = [x for x in t[2:] if '=' not in x]
        if cur == a.top: top_ports = subckt[cur]
    elif k == '.ends': cur = None
    elif cur == a.top and t[0][0] in 'Xx':
        xs.append((t[0][1:], t[1:-1], t[-1]))
assert top_ports is not None, f'no .subckt {a.top} in {a.netlist}'

# ---------------------------------------------------------------- conn (expectations, pin directions)
conn = ct.parse(ct.read_conn(f'{P}/integration/chips/{a.chip}/chip.conn'))[0]
ctl = ct.load_ctl(open(P+'/integration/chips/ctl_ports.txt').read())
kinds = collections.defaultdict(lambda: collections.defaultdict(set))     # master -> pin -> {kinds}
for n, i in conn.items():
    for p, (k, net) in i['pins'].items(): kinds[i['master']][p].add(k)

# ---------------------------------------------------------------- macro ports
src = open(a.macro_v).read()
mm = re.search(r'\bmodule\s+pt_digital_macro\b', src); assert mm, 'no module pt_digital_macro'
body = src[mm.start():]
mports = collections.OrderedDict()
for d, msb, lsb, name in re.findall(r'^\s*(input|output|inout)\s+(?:wire\s+|reg\s+)?(?:\[(\d+):(\d+)\]\s*)?(\w+)\s*[;,)]', body[:400000], re.M):
    if name not in mports: mports[name] = (d, int(msb) if msb else None)
MACRO_PWR = [p for p in ('VDD', 'VSS') if p in mports]

# ---------------------------------------------------------------- identifiers
used_ids = {}
def vid(s, pre):
    v = pre+re.sub(r'[^A-Za-z0-9_]', '_', s)
    while used_ids.get(v, s) != s: v += '_'
    used_ids[v] = s; return v
NET = {}
def net(n):
    if n not in NET: NET[n] = vid(n, 'n_')
    return NET[n]
pin_id = lambda p: 'p_'+re.sub(r'[^A-Za-z0-9_]', '_', p)

PADS = set(CELL_PINS)
V, findings = [], []
inst_of = {}
for name, nets, master in xs:
    inst_of[name] = (master, nets)

# ---------------------------------------------------------------- stubs
S = ['// GENERATED by verification/chip_smoke/gen_bench.py: one behavioural stub per netlist master. Do not edit.', '`timescale 1ns/1ps']
masters = sorted({m for _, _, m in xs if m != 'pt_digital_macro' and m not in PADS})
for m in masters:
    pins = subckt.get(m)
    if pins is None: findings.append(f'master {m} has no .subckt in the netlist'); pins = []
    ids = [pin_id(p) for p in pins]; assert len(set(ids)) == len(ids), (m, pins)
    S.append(f'module S_{re.sub(r"[^A-Za-z0-9_]", "_", m)}('+', '.join(ids)+');')
    S += [f' inout wire {x};' for x in ids]
    P2 = dict(zip(pins, ids)); out = [p for p in pins if '>' in kinds[m].get(p, ())]
    def has(*ps): return all(p in P2 for p in ps)
    for p in out:
        x = P2[p]
        if m.startswith('isw_') and has('EN', 'VDD', 'VSS'):
            pg = f"({P2['EN']} & {P2['VDD']} & ~{P2['VSS']})"
            e = pg if p == 'PG' else f'~{pg}'
        elif m.startswith('iso_clamp') and has('A', 'ISO'): e = f"{P2['A']} & ~{P2['ISO']}"
        elif m == 'iso_pd' and has('ISO'): e = f"({P2['ISO']} === 1'b0) ? 1'bz : 1'b0"
        elif m == 'por' and has('vdd3v3', 'vss', 'ena'):
            ok = f"(smoke_tb.por_release & {P2['vdd3v3']} & ~{P2['vss']} & {P2['ena']})"
            e = ok if p in ('porb', 'por_unbuf') else f'~{ok}'
        elif m == 'pt_clockmux' and p == 'HOST_CLK': e = 'smoke_tb.hclk'
        else: e = "1'b0"
        S.append(f' assign {x} = {e};')
    S.append('endmodule')

# ---------------------------------------------------------------- top
T = ['// GENERATED by verification/chip_smoke/gen_bench.py from '+os.path.basename(a.netlist)+'. Do not edit.', '`timescale 1ns/1ps']
port_ids = [net(p) for p in top_ports]
T.append('module smoke_chip('+', '.join(port_ids)+');')
T += [f' inout wire {x};' for x in port_ids]
allnets = set(top_ports)
for _, nets, _ in xs: allnets |= set(nets)
T += [f' wire {net(n)};' for n in sorted(allnets - set(top_ports))]
macro_conn = {}
for name, nets, master in xs:
    iv = vid(name, 'X')
    pins = subckt.get(master, [])
    if len(pins) != len(nets):
        findings.append(f'{name} ({master}): {len(nets)} nets for {len(pins)} subckt pins'); pins = pins[:len(nets)]
    if master == 'pt_digital_macro':
        bits = collections.defaultdict(dict)
        for p, n in zip(pins, nets):
            b, i = ct.bus(p); bits[b][i] = n
        cs = []
        for b, d in bits.items():
            if b not in mports: findings.append(f'netlist macro pin {b} is not a port of the macro model'); continue
            w = mports[b][1]
            if w is None: cs.append(f'.{b}({net(d[None])})')
            else:
                v = []
                for k in range(w, -1, -1):
                    if k in d: v.append(net(d[k]))
                    else:
                        if mports[b][0] == 'input': findings.append(f'macro input {b}[{k}] has no net in the netlist')
                        v.append("1'bz")
                cs.append(f'.{b}({{{", ".join(v)}}})')
        for b, (d, w) in mports.items():
            if b not in bits and b not in MACRO_PWR:
                if d == 'input': findings.append(f'macro input {b} not in the netlist (floats)')
        cs += [f'.{p}({net(p)})' for p in MACRO_PWR]
        T.append(f' pt_digital_macro {iv}('+', '.join(cs)+');')
        macro_conn = bits
    elif master in PADS:
        T.append(f' {master} {iv}('+', '.join(f'.{p}({net(n)})' for p, n in zip(pins, nets))+');')
    else:
        T.append(f' S_{re.sub(r"[^A-Za-z0-9_]", "_", master)} {iv}('+', '.join(f'.{pin_id(p)}({net(n)})' for p, n in zip(pins, nets))+');')
T.append('endmodule')

# ---------------------------------------------------------------- monitors (expectations from the conn)
inst_v = {name: used_key for used_key, name in used_ids.items() if used_key.startswith('X')}
def stub_ref(inst, pin):
    if inst not in inst_v: return None
    m = inst_of[inst][0]
    if pin not in subckt.get(m, []): return None
    return f'smoke_tb.dut.{inst_v[inst]}.{pin if m in PADS else pin_id(pin)}'
MON = []          # dict(kind, ref (Verilog expr or None), ...)
for port in ctl_bits():
    b, i = ct.bus(port)
    mref = f'smoke_tb.dut.{inst_v.get("digital", "Xdigital")}.{b}' + ('' if i is None else f'[{i}]')
    cons = [(n, p) for n, ins in conn.items() if n != 'digital' for p, (k, nt) in ins['pins'].items() if nt == port and k == '=']
    row = ctl.get(b, {})
    MON.append(dict(kind='ctl_macro', port=port, base=b, bit=i, ref=mref if b in mports else None, consumers=len(cons)))
    for n, p in cons:
        r = stub_ref(n, p)
        if r is None: findings.append(f'consumer {n}.{p} of {port} (conn) is not in the netlist')
        MON.append(dict(kind='ctl_stub', port=port, base=b, bit=i, inst=n, pin=p, ref=r))
mnet = {}       # net -> macro pin reference (the macro end of a pad-cell pin's net)
for b, d in macro_conn.items():
    for i, n in d.items(): mnet.setdefault(n, (b if i is None else f'{b}[{i}]'))
for name, nets, master in xs:
    if master in PADS:
        for p, n in zip(subckt.get(master, []), nets):
            MON.append(dict(kind='pad', inst=name, cell=master, pin=p, net=n, ref=stub_ref(name, p)))
            if n in mnet and p not in ('PAD',):
                MON.append(dict(kind='padlink', inst=name, cell=master, pin=p, net=n, macro=mnet[n],
                                ref=f'smoke_tb.dut.{inst_v["digital"]}.{mnet[n]}'))
for n, ins in conn.items():
    if n == 'digital' or n not in inst_of or inst_of[n][0] in PADS: continue
    for p, (k, nt) in ins['pins'].items():
        if nt in ('VDD', 'VSS'):
            MON.append(dict(kind='rail', inst=n, pin=p, want=1 if nt == 'VDD' else 0, ref=stub_ref(n, p)))
for x in ('d2h_oe', 'd2h_clk_pin', 'spi_miso', 'spi_miso_oe', 'reset_n_pad', 'por_n', 'por_bypass', 'spi_sclk', 'spi_cs_n', 'spi_mosi', 'host_word_clk'):
    MON.append(dict(kind='macro_io', pin=x, ref=f'smoke_tb.dut.{inst_v.get("digital")}.{x}' if x in mports else None))
for k in range(10):
    MON.append(dict(kind='macro_io', pin=f'd2h_pin[{k}]', ref=f'smoke_tb.dut.{inst_v.get("digital")}.d2h_pin[{k}]'))

# ---------------------------------------------------------------- bench
port_of = {p: net(p) for p in top_ports}
B = ['// GENERATED by verification/chip_smoke/gen_bench.py. Do not edit.', '`timescale 1ns/1ps', 'module smoke_tb;',
     ' reg por_release = 0, hclk = 0; reg hclk_run = 0; real hclk_half = 3.2;',
     ' always begin #(hclk_half); hclk = hclk_run ? ~hclk : 1\'b0; end']
for p in top_ports:
    x = port_of[p]
    B += [f' reg d_{x} = 0, e_{x} = 0; wire {x}; assign {x} = e_{x} ? d_{x} : 1\'bz;']
B.append(' smoke_chip dut('+', '.join(f'.{x}({x})' for x in port_ids)+');')
# gate level: break the OBS-14 ring (zero-delay loop in the functional cell models), as tb_digital_gl.sv does
if 'dring.n[0]' in src and r'\debug_cfg[60]' in src:
    dv = inst_v['digital']
    B += [' reg gl_ring = 1\'b1;', f' always @(posedge dut.{dv}.\\debug_cfg[60] ) begin',
          f'  while (dut.{dv}.\\debug_cfg[60] ) begin #6.5 gl_ring = dut.{dv}.\\debug_cfg[60] ? ~gl_ring : 1\'b1; end gl_ring = 1\'b1; end',
          f' initial force dut.{dv}.\\dring.n[0]  = gl_ring;']
refs = [m['ref'] if m['ref'] else "1'bz" for m in MON]
B.append(' task dump; begin')
for k in range(0, len(refs), 100):
    ch = refs[k:k+100]
    B.append('  $write("' + '%b' * len(ch) + '", ' + ', '.join(ch) + ');')
B.append(' end endtask')
def pid(name):
    return port_of[name]
need = ['SPI_SCLK', 'SPI_CS_N', 'SPI_MOSI', 'SPI_MISO', 'RESET_N', 'VDD', 'VSS']
for n in need: assert n in port_of, f'top port {n} missing'
B += [f' task spi(input [7:0] c, input [7:0] ad, input [15:0] v, input integer half); reg [31:0] tx; integer i; reg [15:0] r; begin',
      f'  tx = {{c, ad, v}}; r = 0; e_{pid("SPI_CS_N")} = 1; e_{pid("SPI_SCLK")} = 1; e_{pid("SPI_MOSI")} = 1;',
      f'  d_{pid("SPI_CS_N")} = 0; #(half);',
      f'  for (i = 31; i >= 0; i = i-1) begin d_{pid("SPI_MOSI")} = tx[i]; #(half); d_{pid("SPI_SCLK")} = 1; #(half); if (i < 16) r[i] = {pid("SPI_MISO")}; d_{pid("SPI_SCLK")} = 0; end',
      f'  #(half); d_{pid("SPI_CS_N")} = 1; d_{pid("SPI_MOSI")} = 0; #(half);',
      '  $display("R %b", r); end endtask']
# command loop (stdin): X cmd addr data | D port 0|1|z | W ns | O 0|1 (POR release) | H half_ns 0|1 (host clock) | S | T port (sample) | Q
B += [' reg [8*256-1:0] line; reg [8*64-1:0] pn; integer n, c1, c2, c3; reg [7:0] op; reg [7:0] vch; real hr;',
      ' initial begin', '  forever begin', '   n = $fgets(line, 32\'h8000_0000);', '   if (n == 0) $finish;',
      '   op = line[8*(n)-1 -: 8];', '   case (op)',
      '    "X": begin n = $sscanf(line, "X %d %d %d", c1, c2, c3); spi(c1, c2, c3, 50); end',
      '    "W": begin n = $sscanf(line, "W %d", c1); #(c1); $display("OK"); end',
      '    "O": begin n = $sscanf(line, "O %d", c1); por_release = c1; #1; $display("OK"); end',
      '    "H": begin n = $sscanf(line, "H %f %d", hr, c1); hclk_half = hr; hclk_run = c1; $display("OK"); end',
      '    "S": begin $write("S "); dump; $display(""); end',
      '    "C": begin n = $sscanf(line, "C %d %d", c1, c2); $write("R "); repeat (c1) begin #(c2); $write("%b%b ", {'
      + ', '.join(port_of[f'D2H[{k}]'] for k in range(9, -1, -1)) + ', ' + port_of['D2H_CLK'] + '}, {'
      + f'dut.{inst_v["digital"]}.d2h_pin, dut.{inst_v["digital"]}.d2h_clk_pin' + '}); end $display(""); end',
      '    "Q": $finish;',
      '    "D", "T": begin n = $sscanf(line, "%c %s %c", op, pn, vch);', '     case (pn)']
for p in top_ports:
    x = port_of[p]
    B.append(f'      "{x}": if (op == "T") $display("V %b", {x}); else begin e_{x} = (vch != "z"); d_{x} = (vch == "1"); #1; $display("OK"); end')
B += ['      default: $display("ERR unknown port %0s", pn);', '     endcase', '    end',
      '    default: $display("ERR bad command");', '   endcase', '   $fflush;', '  end', ' end', 'endmodule']

os.makedirs(a.out, exist_ok=True)
open(a.out+'/smoke_stubs.v', 'w').write('\n'.join(S)+'\n')
open(a.out+'/smoke_chip.v', 'w').write('\n'.join(T)+'\n')
open(a.out+'/smoke_tb.v', 'w').write('\n'.join(B)+'\n')
json.dump(dict(chip=a.chip, netlist=os.path.abspath(a.netlist), ports=port_of, monitors=MON, findings=findings,
               instances=len(xs), masters=len(masters)), open(a.out+'/monitor.json', 'w'), indent=0)
print(f'gen_bench {a.chip}: {len(xs)} instances, {len(masters)} stub masters, {len(MON)} monitored bits, {len(findings)} structural findings')
for f in findings[:40]: print('  FINDING', f)
