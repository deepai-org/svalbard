#!/usr/bin/env python3
"""Assembled-RTL check of every mapped observation selection, per chip (PT_CHIP=rf|wired, required).

Reads integration/chips/<chip>/generated/pt_chip.sv (the generated chip top: provider pad models, the real
pt_digital_macro with its PT_CHIP parameter, the black-box pt_analog_top) and the chip's connectivity
integration/chips/<chip>/chip.conn (parsed with integration/chips/check_top.py: which chip net every macro pin,
ATB leaf / group / pad switch and debug pad is bound to). For each spec/debug-controls.json:block_observation
entry whose block, islands, fields and ATB leaf exist on this chip, it generates a pt_chip test that resets the
chip, programs the entry's islands, shared-cell mode and path selection through the SPI pads, commits, and
checks the entry against the SPECIFICATION (debug-controls / ctl_ports / the conn), not the generated model:

  atb1       the conn's leaf atb1_leaf<code>: its SEL net, the SEL net of the group switch on its local bus and
             the ATB1 pad switch go high, the macro's atb1_sw is exactly that one bit (atb0 all open); with the
             node's island power-good dropped, the selection opens again.
  dbg_obs    the status source (the chip net bound to the macro's s_* / por_n / fault / fc_src pin, table
             below) is driven high and low and DBG_OBS0 must follow; OR sources one member at a time, the
             island power-good AND one switch at a time; sel = 4+obs_status index, or 37+wire_status index
             (rtl/pt_regfile.sv dbg_src; PD22 retired the WDBG_OBS pad).
  clk_obs    the source / divider reach the decoded c_clk_obs_* ports (ctl_ports.txt encodings), CLK_OBS is
             enabled and a toggle of the chip net clk_obs reaches the pad.
  wmon,      the selection reaches its decoded c_* ports (ctl_ports.txt encodings).
  bb_tap
  freq_count the source reaches the counter's cfg_source (no chip-boundary port: the counter is in the macro).
  spi        status bits reach the SPI register through the pads (power-good bits = this chip's groups).
  mode       every shared-cell mode field reaches its decoded c_* port.

Entries of blocks / islands / fields / ATB leaves that are not on this chip are listed with the reason; so are
sources tied to a constant in the conn and digital-internal sources. host_data and pad entries are bench /
payload observations and are not simulated. A pass is assembled-RTL evidence only: pt_analog_top is a black box.
Negative controls: every run also runs each --negative kind (one corrupted case each) and passes only if the
simulation catches every one; --negative <kind> runs one alone (must FAIL).
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
sys.path.insert(0, str(PROJECT/'rtl/gen'))
sys.path.insert(0, str(PROJECT/'integration/chips'))
import pt_regmap as regmap  # noqa: E402  (register addresses and field positions only)
import check_top  # noqa: E402  (the conn loaders: one connectivity source of truth)

# Status source -> (combine, macro input pins). The pins are bound to chip nets by the conn. Composition per
# rtl/pt_digital_macro.sv (analog_status / wire_analog_status / obs_extra / island_pgood).
STATUS_SOURCE = {
    'pll_tx_lock': ('or', ['s_pll_tx_lock']), 'ref_present': ('or', ['s_ref_present']),
    'refbuf_ready': ('or', ['s_refbuf_ready']), 'por_n': ('or', ['por_n']), 'monitor_fault': ('or', ['fault']),
    'adc_i_done': ('or', ['s_adc_i_done']), 'adc_q_done': ('or', ['s_adc_q_done']),
    'adc_i_overload': ('or', ['s_adc_i_ovl', 's_adc_i_b_ovl']), 'adc_q_overload': ('or', ['s_adc_q_ovl', 's_adc_q_b_ovl']),
    'aux_present': ('or', ['s_aux_present']), 'wtx_ext_present': ('or', ['s_wtx_ext_present']),
    'pll_cdr_lock': ('or', ['s_pll_cdr_lock']), 'detect_diff': ('or', ['s_detect_diff_pos', 's_detect_diff_neg']),
    'wtx_ext_data': ('or', ['s_wtx_ext_data']), 'aosc_div': ('div2', ['fc_src[4]']),
}
ISLAND_GROUP = check_top.GROUP_BIT   # supply island -> enable group bit
PG_PIN = {isl: 's_pg_'+isl for isl in ISLAND_GROUP if isl != 'wired_cap'} | {'wired_cap': 's_pg_wired_cap'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Chip:
    """The chip's conn, parsed with check_top."""
    def __init__(self, chip):
        self.chip = chip
        self.spec = check_top.CHIPS[chip]
        self.conn_path = Path(check_top.HERE)/chip/'chip.conn'
        self.inst, self.ports, _, err = check_top.parse(check_top.read_conn(str(self.conn_path)))
        assert not err, err
        self.groups = self.spec['enable_groups']                     # name -> bit
        self.islands = self.spec['islands']
        self.digital = self.inst['digital']['pins']
        self.ctl = check_top.load_ctl((Path(check_top.HERE)/'ctl_ports.txt').read_text())
    def net(self, pin):
        """Chip net of a macro pin, or None when the conn ties it to a constant / leaves it open."""
        kind, net = self.digital[pin]
        return None if net in ('VSS', 'VDD', '-') else net
    def pg_pins(self, group):
        """s_pg_* pins (with their nets) of the islands of one enable group present on this chip."""
        return [PG_PIN[i] for i in self.islands if ISLAND_GROUP[i] == self.groups[group]]
    def all_pg(self):
        return [PG_PIN[i] for i in self.islands]
    def leaf(self, bus, code):
        return self.inst.get(f'atb{bus}_leaf{code}')
    def group_switch(self, bus, local):
        for name, i in self.inst.items():
            if i['master'] == 'atb_grp' and i['pins'].get('NODE', ('', ''))[1] == local:
                return name, i
        return None, None


def encode(field, value):
    f = regmap.FIELD_BY_NAME[field]
    if isinstance(value, str):
        assert f['values'] and value in f['values'], (field, value)
        value = f['values'].index(value)
    return value


def field_on_chip(field, chip):
    return chip in regmap.FIELD_BY_NAME[field].get('chips', [chip])


def port_expect(field, fields):
    """Decoded c_* port values a field setting must produce (integration/chips/ctl_ports.txt encodings), or a
    macro-internal probe. Unknown fields raise: nothing is skipped silently."""
    v = fields[field]
    name = lambda f: regmap.FIELD_BY_NAME[f]['values'][fields[f]]
    if field == 'debug.clk_obs.source':
        out = [('c_clk_obs_en', int(v != 0))]
        if 1 <= v <= 15:
            out.append(('c_clk_obs_s', v))
        return out
    if field == 'debug.clk_obs.divider_log2':
        return [('c_clk_obs_n', v)]
    if field == 'debug.bb_tap.mode':
        mode = name(field)
        return [('c_bb_tap_obs_en', int(mode.startswith('observe'))),
                ('c_bbfilter_obs_sel', {'observe_rx_mixer': 1, 'observe_rx_pga': 2, 'observe_rx_filter': 3,
                                        'observe_tx': 3}.get(mode, 0))]
    if field == 'consolidation.bbfilter.direction':
        mode = name('debug.bb_tap.mode') if 'debug.bb_tap.mode' in fields else 'off'
        return [('c_bbfilter_dir_tx', int(name(field) == 'tx' or mode == 'inject_tx_mixer'))]
    if field == 'debug.wmon_select.select':
        return [('c_wmon_obs_en', int(v != 0))]+([('c_wmon_sel', v-1)] if v else [])
    if field == 'consolidation.wiredtx_stage.stage':
        return [('c_wtxfb_stage_tmds', v)]
    if field in ('debug.freq_count_a.source', 'debug.freq_count_b.source'):
        return [('@digital.digital.fc'+field[-8]+'.cfg_source', v)]
    raise AssertionError(f'no port expectation for {field}')


def plan(chip, controls, block, entry):
    """Field settings, islands and checks for one entry (or the reason it is not simulated on this chip)."""
    nodes = {n['name']: n for n in controls['atb_nodes']}
    path, select = entry['path'], entry['select']
    groups = set(entry.get('islands') or []) | set(controls['block_islands'].get(block, []))
    absent = sorted(g for g in groups if g not in chip.groups)
    if absent:
        return None, f'island group(s) {absent} not on pt_{chip.chip}'
    fields, checks = {}, []
    for field, value in (entry.get('mode') or {}).items():
        if not field_on_chip(field, chip.chip):
            return None, f'mode field {field} not on pt_{chip.chip}'
        fields[field] = encode(field, value)
        groups |= set(regmap.FIELD_BY_NAME[field]['islands'])
        checks.append(('ports', field))
    if path == 'atb1':
        node = nodes[select]
        if not node.get('hardware', True):
            return None, 'ATB node has no physical leaf (hardware=false)'
        code = node['code']
        leaf = chip.leaf(1, code)
        if leaf is None:
            return None, f'no atb1_leaf{code} in pt_{chip.chip} chip.conn'
        if node['island'] and node['island'] not in chip.groups:
            return None, f'node island {node["island"]} not on pt_{chip.chip}'
        fields['debug.atb.atb1'] = code
        if node['island']:
            groups.add(node['island'])
        checks.append(('atb', code, node['island']))
    elif path == 'dbg_obs':
        if select == 'commit_toggle':
            fields['debug.dbg_obs.sel0'] = 3
            checks.append(('commit_toggle',))
        else:
            if select in controls['obs_status']:
                fields['debug.dbg_obs.sel0'] = 4+controls['obs_status'].index(select)
            else:
                fields['debug.dbg_obs.sel0'] = 37+controls['wire_status'].index(select)
            if select.startswith('island_pgood_'):
                group = select[13:]
                if group not in chip.groups:
                    return None, f'enable group {group} not on pt_{chip.chip}'
                checks.append(('status', 'and', chip.pg_pins(group)))
            elif select in STATUS_SOURCE:
                combine, pins = STATUS_SOURCE[select]
                tied = [p for p in pins if chip.net(p) is None]
                if tied:
                    return None, f'{select}: macro pin(s) {tied} tied to a constant in pt_{chip.chip} chip.conn'
                checks.append(('status', combine, pins))
            else:
                return None, f'{select}: digital-internal source (mux selection only)'
    elif path in ('clk_obs', 'wmon', 'bb_tap'):
        field = {'clk_obs': 'debug.clk_obs.source', 'wmon': 'debug.wmon_select.select', 'bb_tap': 'debug.bb_tap.mode'}[path]
        if not field_on_chip(field, chip.chip):
            return None, f'{field} not on pt_{chip.chip}'
        fields[field] = encode(field, select)
        groups |= set(regmap.FIELD_BY_NAME[field]['islands'])
        if 'divider_log2' in entry:
            fields['debug.clk_obs.divider_log2'] = entry['divider_log2']
            checks.append(('ports', 'debug.clk_obs.divider_log2'))
        checks.append(('ports', field))
        if path == 'clk_obs':
            checks.append(('clock',))
    elif path == 'freq_count':
        field = 'debug.freq_count_b.source' if select == 'cdr_ring_fbck' else 'debug.freq_count_a.source'
        fields[field] = encode(field, select)
        checks.append(('ports', field))
    elif path == 'spi':
        if select == '0x0B[0]':
            if chip.net('fault') is None:
                return None, 'fault: macro pin tied to a constant in chip.conn (D-FAULT)'
            checks.append(('spi_bit', 0x0B, 0, 'fault'))
        elif select == '0x0A[13:8]':
            checks.append(('spi_pgood',))
        elif select == '0x0D[0]':
            checks.append(('spi_por',))
        elif select == '0x00':
            checks.append(('spi_id',))
        else:
            return None, 'unsupported SPI selection'
    else:
        return None, f'{path}: bench/payload observation, not an RTL selection'
    for g in groups:
        fields['debug.island_power.'+g] = 1
    return dict(fields=fields, islands=sorted(groups), checks=checks), None


def register_writes(fields):
    values = regmap.reset_config()
    values.update(fields)
    code = regmap.commit_code(values, regmap.reset_config(), False)
    writes = {}
    for name in fields:
        for chunk in regmap.FIELD_BY_NAME[name]['chunks']:
            writes[chunk['addr']] = 0
    for addr in writes:
        value = 0
        for name, lsb, width, reg_lsb in regmap.REGISTER_BY_ADDR[addr]['chunks']:
            value |= ((values[name] >> lsb) & ((1 << width)-1)) << reg_lsb
        writes[addr] = value
    return writes, code


def testbench(chip, cases):
    nets = {}       # forced chip net -> verilog reg
    def src(pin):
        net = chip.net(pin)
        if net not in nets:
            # a bused net is forced whole from a reg vector (iverilog cannot force a bit select)
            nets[net] = f'b_{net.split("[")[0]}[{net.split("[")[1]}' if '[' in net else f'src{len(nets)}'
        return nets[net]
    for pin in chip.all_pg():
        src(pin)
    for pin in ['por_n']+[p for _, ps in STATUS_SOURCE.values() for p in ps]:
        if chip.net(pin) is not None:
            src(pin)
    clk_net = chip.inst['debug_pads']['pins']['clk_obs'][1]
    pg = [src(p) for p in chip.all_pg()]
    por = src('por_n')
    ports = sorted({p.split('[')[0] for p in chip.ports})
    body = []
    def check_ports(tag, field, fields):
        for port, value in port_expect(field, fields):
            expr = 'dut.'+port[1:] if port.startswith('@') else 'dut.'+port
            if not port.startswith('@'):
                # every c_* row of ctl_ports.txt is a macro output port on a chip net of the same name (conn header)
                assert port in chip.ctl, f'{port} is not a control port (integration/chips/ctl_ports.txt)'
                expr = 'dut.'+port
            body.append(f'  if({expr}!=={value}) fail("{tag}: {field} -> {port[1:] if port[0] == "@" else port}");')
    for case in cases:
        tag = case['id']
        body.append(f'  // {tag}')
        body.append('  chip_reset; idle_sources;')
        for addr, value in sorted(case['writes'].items()):
            body.append(f'  spi(8\'h80,8\'h{addr:02X},16\'h{value:04X});')
        body.append('  spi(8\'h80,8\'h06,16\'h0001); spi(0,8\'h0C,0);')
        body.append(f'  if(result[15:8]!==0) fail("{tag}: commit rejected");')
        body.append('  #100;')
        for check in case['checks']:
            kind = check[0]
            if kind == 'atb':
                code, island = check[1], check[2]
                leaf = chip.leaf(1, code)['pins']
                local = leaf['BUS'][1]
                gname, grp = chip.group_switch(1, local)
                group = next(i for i, g in enumerate(regmap.ATB_GROUPS['atb1']) if code in g['codes'])
                assert grp is not None and grp['pins']['SEL'][1] == f'atb1_grp[{group}]', \
                    f'{tag}: conn local bus {local} switch {gname} is not atb1_grp[{group}] (debug-controls atb_groups)'
                pad_sel = chip.inst['atb1_pad']['pins']['SEL'][1]
                sel = leaf['SEL'][1]
                body.append(f'  if(dut.digital.atb1_sw!=={regmap.ATB_WIDTH}\'d1<<{code-1} || dut.digital.atb0_sw!==0) fail("{tag}: atb1_sw not one-hot code {code}");')
                body.append(f'  if(dut.{sel}!==1 || dut.{grp["pins"]["SEL"][1]}!==1 || dut.{pad_sel}!==1) fail("{tag}: leaf/group/pad switch not closed");')
                if island:
                    off = ' '.join(f'{src(p)}=0;' for p in chip.pg_pins(island))
                    on = ' '.join(f'{src(p)}=1;' for p in chip.pg_pins(island))
                    body.append(f'  {off} #100; if(dut.{sel}!==0 || dut.{pad_sel}!==0) fail("{tag}: leaf not opened with island off"); {on} #100;')
            elif kind == 'ports':
                check_ports(tag, check[1], case['fields'])
            elif kind == 'status':
                combine, pins = check[1], check[2]
                regs = [src(p) for p in pins]
                if combine == 'or':
                    for r in regs:
                        body.append(f'  {r}=1; #100; if(DBG_OBS0!==1) fail("{tag}: DBG_OBS0 not high ({r})"); {r}=0; #100; if(DBG_OBS0!==0) fail("{tag}: DBG_OBS0 not low ({r})");')
                elif combine == 'and':
                    body.append(f'  #100; if(DBG_OBS0!==1) fail("{tag}: DBG_OBS0 not high (all power-good)");')
                    for r in regs:
                        body.append(f'  {r}=0; #100; if(DBG_OBS0!==0) fail("{tag}: DBG_OBS0 not low ({r})"); {r}=1; #100;')
                elif combine == 'div2':
                    r = regs[0]
                    body.append(f'  prev=DBG_OBS0; {r}=1; #50; {r}=0; #50; if(DBG_OBS0!==~prev) fail("{tag}: divider did not toggle");')
                    body.append(f'  {r}=1; #50; {r}=0; #50; if(DBG_OBS0!==prev) fail("{tag}: divider did not toggle back");')
            elif kind == 'commit_toggle':
                body.append(f'  prev=DBG_OBS0; spi(8\'h80,8\'h06,16\'h0001); #100;')
                body.append(f'  if(DBG_OBS0===prev || DBG_OBS0===1\'bz || prev===1\'bz) fail("{tag}: commit toggle");')
            elif kind == 'clock':
                body.append(f'  ck=1; #50; if(CLK_OBS!==1) fail("{tag}: CLK_OBS high"); ck=0; #50; if(CLK_OBS!==0) fail("{tag}: CLK_OBS low");')
            elif kind == 'spi_bit':
                r = src(check[3])
                body.append(f'  {r}=1; #100; spi(0,8\'h{check[1]:02X},0); if(result[{check[2]}]!==1) fail("{tag}: spi bit high");')
                body.append(f'  {r}=0; #100; spi(0,8\'h{check[1]:02X},0); if(result[{check[2]}]!==0) fail("{tag}: spi bit low");')
            elif kind == 'spi_pgood':
                bits = sum(1 << b for b in chip.groups.values())
                body.append(f'  #100; spi(0,8\'h0A,0); if(result[13:8]!==6\'d{bits}) fail("{tag}: pgood bits");')
                body.append(f'  {" ".join(r+"=0;" for r in pg)} #100; spi(0,8\'h0A,0); if(result[13:8]!==0) fail("{tag}: pgood low");')
            elif kind == 'spi_por':
                body.append(f'  spi(8\'h80,8\'h0D,16\'h0003); spi(0,8\'h0D,0); if(result[0]!==0) fail("{tag}: por clear");')
                body.append(f'  {por}=0; #200; {por}=1; #200; spi(0,8\'h0D,0); if(result[0]!==1) fail("{tag}: por occurred");')
            elif kind == 'spi_id':
                body.append(f'  spi(0,8\'h00,0); if(result!==16\'h5356) fail("{tag}: id");')
        body.append(f'  $display("CASE {tag} done failures=%0d", failures);')
    top = (PROJECT/f'integration/chips/{chip.chip}/generated/pt_chip.sv').read_text()
    forces, buses = [], set()
    for n, r in nets.items():
        if '[' in n:
            buses.add(n.split('[')[0])
        else:
            forces.append(f'force dut.{n}={r};')
    regs = [r for r in nets.values() if '[' not in r]
    for base in sorted(buses):
        width = int(re.search(r'wire\s*\[(\d+):0\]\s*'+base+r'\s*;', top).group(1))+1
        forces.append(f'force dut.{base}=b_{base};')
        regs.append(f'[{width-1}:0] b_{base}')
    conns = []
    for p in ports:
        if p in ('RESET_N', 'SPI_SCLK', 'SPI_CS_N', 'SPI_MOSI', 'SPI_MISO', 'DBG_OBS0', 'CLK_OBS', 'VDD', 'VSS'):
            conns.append(f'.{p}({ {"VDD": "vdd", "VSS": "vss"}.get(p, p)})')
        else:
            conns.append(f'.{p}()')
    sv = ['`timescale 1ns/1ps', 'module tb_observation_paths;',
          ' reg reset_drive=0, sclk_drive=0, cs_drive=1, mosi_drive=0;',
          ' wire RESET_N=reset_drive, SPI_SCLK=sclk_drive, SPI_CS_N=cs_drive, SPI_MOSI=mosi_drive;',
          ' wire SPI_MISO, DBG_OBS0, CLK_OBS; supply1 vdd; supply0 vss;',
          *[f' reg {r}=0;' for r in regs], ' reg ck=0, prev; integer failures=0;',
          ' pt_chip dut('+', '.join(conns)+');',
          ' // Only nets driven by the black-box analog top (status, power-good, POR, clocks) are forced.',
          ' initial begin '+' '.join(forces)+f' force dut.{clk_net}=ck; end',
          ' reg[15:0] result;',
          ' task spi(input[7:0] command,address,input[15:0] value); reg[31:0] tx; integer i;',
          '  begin tx={command,address,value}; result=0; cs_drive=0; #100;',
          '   for(i=31;i>=0;i=i-1) begin mosi_drive=tx[i]; #200; sclk_drive=1; #200; if(i<16) result[i]=SPI_MISO; sclk_drive=0; #100; end',
          '   cs_drive=1; #100; end endtask',
          ' task fail(input [8*160:1] msg); begin failures=failures+1; $display("FAIL %0s", msg); end endtask',
          ' task chip_reset; begin reset_drive=0; #200; reset_drive=1; #200; end endtask',
          ' task idle_sources; begin '+' '.join(f'{r}=0;' for n, r in nets.items() if r not in pg and r != por)+
          ' '+' '.join(f'{r}=1;' for r in pg)+f' {por}=1; ck=0; end endtask',
          ' initial begin',
          f'  idle_sources; #50; reset_drive=1; #200;',
          '  spi(0,8\'h00,0); if(result!==16\'h5356) fail("ID");',
          *body,
          '  if(failures==0) $display("OBSERVATION_PATHS_PASS"); else $display("OBSERVATION_PATHS_FAIL %0d", failures);',
          '  $finish; end', ' initial begin #400000000; $fatal(1,"timeout"); end', 'endmodule']
    return '\n'.join(sv)+'\n'


NEGATIVES = ('status_source', 'wire_source', 'atb_code', 'port_value', 'island_gate', 'clock_pad')


def negative(chip, cases, kind):
    """Corrupt ONE case's expectation or programming; the simulation must fail it."""
    obs = json.loads((PROJECT/'spec/debug-controls.json').read_text())['obs_status']
    for case in cases:
        checks = case['checks']
        for i, c in enumerate(checks):
            if kind in ('status_source', 'wire_source') and c[0] == 'status' and c[1] == 'or':
                is_wire = case['fields']['debug.dbg_obs.sel0'] >= 37
                if is_wire != (kind == 'wire_source'):
                    continue
                other = next(p for n, (comb, ps) in STATUS_SOURCE.items() for p in ps
                             if comb == 'or' and p not in c[2] and chip.net(p) is not None)
                checks[i] = ('status', 'or', [other])
            elif kind == 'atb_code' and c[0] == 'atb':
                nxt = next((k for k in range(c[1]+1, 64) if chip.leaf(1, k)), None)
                if nxt is None:
                    continue
                case['fields']['debug.atb.atb1'] = nxt
                case['writes'], _ = register_writes(case['fields'])
            elif kind == 'port_value' and c[0] == 'ports' and case['fields'].get(c[1]):
                case['fields'] = dict(case['fields'])
                case['fields'][c[1]] -= 1          # programming unchanged; only the expectation moves
            elif kind == 'island_gate' and c[0] == 'atb' and c[2]:
                case['fields'] = {k: v for k, v in case['fields'].items() if k != 'debug.island_power.'+c[2]}
                case['writes'], _ = register_writes(case['fields'])
                case['fields'] = dict(case['fields'], **{'debug.atb.atb1': c[1]})
            elif kind == 'clock_pad' and c[0] == 'clock':
                case['fields'] = {k: v for k, v in case['fields'].items() if k != 'debug.island_power.debug'}
                case['writes'], _ = register_writes(case['fields'])
            else:
                continue
            case['id'] = 'NEG_'+kind+':'+case['id']
            return [case]
    raise AssertionError(f'no case on pt_{chip.chip} for negative '+kind)


def simulate(chip, cases, out, io_model):
    """Compile and run one bench; -> (finished, failures, lines, sources)."""
    tb = out/'tb_observation_paths.sv'
    tb.write_text(testbench(chip, cases))
    gen = PROJECT/f'integration/chips/{chip.chip}/generated'
    sources = [tb, gen/'pt_chip.sv', PROJECT/'integration/pt_provider_io.sv', *sorted((PROJECT/'rtl').glob('*.sv'))]
    compile_result = subprocess.run(['iverilog', '-g2012', '-Dfunctional', '-DPT_EXTERNAL_IO', '-I', str(PROJECT/'rtl'),
                                     '-s', 'tb_observation_paths', '-o', str(out/'paths.vvp'), *map(str, sources),
                                     str(io_model)], text=True, capture_output=True, timeout=600)
    (out/'compile.log').write_text(compile_result.stdout+compile_result.stderr)
    assert compile_result.returncode == 0, compile_result.stderr[-3000:]
    sim = subprocess.run(['vvp', '-n', str(out/'paths.vvp')], cwd=out, text=True, capture_output=True, timeout=3600)
    (out/'paths.vvp').unlink()
    lines = sim.stdout.splitlines()
    (out/'sim.log').write_text('\n'.join(lines)+'\n'+sim.stderr)
    failures = [l[5:] for l in lines if l.startswith('FAIL ')]
    finished = 'OBSERVATION_PATHS_PASS' in lines or any(l.startswith('OBSERVATION_PATHS_FAIL') for l in lines)
    return finished, failures, lines, sources


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--output-dir', type=Path, help='default scratch/observation-paths-<chip>')
    ap.add_argument('--io-model', type=Path, help='provider pad model (default: scratch/chip-io/<chip>/, from check_chip_io.py)')
    ap.add_argument('--mutate', help='negative control: "<block>:<index>:<field>=<value>" applied to one entry')
    ap.add_argument('--negative', choices=NEGATIVES, help='run only this negative control (must FAIL)')
    ap.add_argument('--no-negatives', action='store_true', help='skip the built-in negative controls')
    a = ap.parse_args()
    chip = Chip(os.environ['PT_CHIP'])
    regmap.chip_view(chip.chip)
    a.io_model = a.io_model or ROOT/f'scratch/chip-io/{chip.chip}/gf180mcu_fd_io.v'
    out = (a.output_dir or ROOT/f'scratch/observation-paths-{chip.chip}').resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out/'report.json').write_text(json.dumps(dict(status='incomplete'))+'\n')
    controls_path = PROJECT/'spec/debug-controls.json'
    controls = json.loads(controls_path.read_text())
    blocks = controls['block_observation']['blocks']
    if a.mutate:
        target, change = a.mutate.split('=', 1)
        block, index, key = target.split(':')
        blocks[block][int(index)][key] = json.loads(change)
    def planned_cases():
        cases, skipped = [], []
        for block, entries in blocks.items():
            for index, entry in enumerate(entries):
                tag = f'{block}:{index}:{entry["path"]}:{entry["select"]}'
                planned, reason = plan(chip, controls, block, entry)
                if planned is None:
                    skipped.append(dict(id=tag, block=block, index=index, reason=reason))
                    continue
                writes, code = register_writes(planned['fields'])
                assert code == 0, f'{tag}: the model rejects this configuration (commit code {code})'
                cases.append(dict(id=tag, block=block, index=index, writes=writes, model_commit_code=code, **planned))
        return cases, skipped
    cases, skipped = planned_cases()
    if a.negative:
        cases = negative(chip, cases, a.negative)
    finished, failures, lines, sources = simulate(chip, cases, out, a.io_model)
    results = []
    for case in cases:
        done = any(l.startswith(f'CASE {case["id"]} done') for l in lines)
        own = [f for f in failures if f.startswith(case['id']+':')]
        results.append(dict(id=case['id'], block=case['block'], index=case['index'], islands=case['islands'],
                            register_writes={f'0x{k:02X}': f'0x{v:04X}' for k, v in sorted(case['writes'].items())},
                            checks=[[x if not isinstance(x, list) else list(x) for x in c] for c in case['checks']],
                            status='pass' if done and not own else 'fail', failures=own))
    status = 'pass' if finished and not failures and results and all(r['status'] == 'pass' for r in results) else 'fail'
    negatives = {}
    if not (a.negative or a.mutate or a.no_negatives):
        # Every negative must be caught by the simulation itself (a FAIL line of the corrupted case).
        work = out/'negative'
        work.mkdir(exist_ok=True)
        for kind in NEGATIVES:
            neg_cases = negative(chip, planned_cases()[0], kind)
            done, neg_failures, _, _ = simulate(chip, neg_cases, work, a.io_model)
            caught = done and any(f.startswith(neg_cases[0]['id']+':') for f in neg_failures)
            negatives[kind] = dict(case=neg_cases[0]['id'], caught=caught, failures=neg_failures[:4])
        for f in work.iterdir():
            f.unlink()
        work.rmdir()
        if not all(n['caught'] for n in negatives.values()):
            status = 'fail'
    report = dict(chip=chip.chip, status=status,
                  scope=f'assembled RTL of pt_{chip.chip} (generated pt_chip + provider pad models + real macro) '
                        'selection/status/clock paths to the black-box pt_analog_top boundary and the debug pads',
                  mutation=a.mutate, negative=a.negative, negative_controls=negatives, cases=results, not_simulated=skipped,
                  controls_sha256=sha(controls_path), conn_sha256=sha(chip.conn_path),
                  source_hashes={str(p.relative_to(ROOT)): sha(p) for p in sources[1:]}, script_sha256=sha(__file__),
                  io_model_sha256=sha(a.io_model))
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(chip=chip.chip, status=status, simulated=len(results),
                          passed=sum(r['status'] == 'pass' for r in results), not_simulated=len(skipped),
                          negatives_caught=f'{sum(n["caught"] for n in negatives.values())}/{len(negatives)}',
                          failures=failures[:20], report=str(out/'report.json')), indent=2))
    if status != 'pass':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
