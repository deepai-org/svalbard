#!/usr/bin/env python3
"""Assembled-RTL check of every mapped observation selection.

For each spec/debug-controls.json:block_observation entry this generates a
pt_chip test (provider pad models, real SPI) that resets the chip, programs
the entry's islands, shared-cell mode and path selection through SPI, commits,
and then checks the entry against the SPECIFICATION, not the generated model:

  atb1       exactly atb1_sw[code-1], its group line and atb1_en reach the
             pt_analog_physical boundary (code from atb_nodes by name);
             the selection is re-checked open with its island switched off.
  dbg_obs /  the named status source is driven at the pt_analog_physical
  wdbg_obs   boundary (table below, from the pt_digital.sv vector comment)
             high and low and DBG_OBS0 / WDBG_OBS must follow, both ways.
  clk_obs /  the source/divider field reaches debug_cfg with its catalog
  wclk_obs   encoding, the pad enables, and a boundary toggle reaches the pad.
  wmon,      the selection field reaches debug_cfg with its catalog encoding
  bb_tap,    (the analog mux behind it is in the black-box analog macro).
  freq_count
  spi        status bits reach the SPI register through the pads.
  mode       every shared-cell mode field reaches its bus slice.

host_data and pad entries are bench/payload observations and are not
simulated here. A pass is assembled-RTL evidence only: pt_analog_physical is
a black box, so no analog source net is exercised.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
sys.path.insert(0, str(PROJECT/'rtl/gen'))
import pt_regmap as regmap  # noqa: E402  (register addresses and field positions only)

# Boundary net (pt_chip scope) carrying each status source, per the
# obs_status / wire_status order documented in rtl/pt_digital.sv.
STATUS_SOURCE = {
    'pll_lock': 'analog_status[0]', 'ref_present': 'analog_status[1]', 'bias_ready': 'analog_status[2]',
    'refbuf_ready': 'analog_status[3]', 'por_n': 'analog_status[4]', 'cdr_qualified': 'analog_status[5]',
    'cdr_loss': 'analog_status[6]', 'adc_i_done': 'analog_status[7]', 'adc_q_done': 'analog_status[8]',
    'adc_i_overload': 'analog_status[9]', 'adc_q_overload': 'analog_status[10]', 'aosc_div': 'analog_status[11]',
    'monitor_fault': 'fault', 'rf_rx_valid': 'rv', 'rf_tx_request': 'rrequest', 'wire_rx_valid': 'wv',
    'wire_tx_request': 'wrequest',
}
WIRE_SOURCE = {name: f'wire_analog_status[{i}]' for i, name in enumerate(
    ['cdr_qualified', 'cdr_loss', 'cdr_rx_state0', 'cdr_rx_state1', 'slicer_data', 'slicer_early', 'slicer_late',
     'electrical_quiet', 'usb_squelch', 'detect_event', 'detect_timeout', 'pll_lock', 'wtx_ext_data'])}
WIRE_SOURCE.update(wire_rx_valid='wv', wire_tx_request='wrequest')
PATH_FIELD = {'clk_obs': 'debug.clk_obs.source', 'wclk_obs': 'debug.wclk_obs.source', 'wmon': 'debug.wmon_select.select',
              'bb_tap': 'debug.bb_tap.mode'}
FORCED_NETS = sorted({'analog_status', 'wire_analog_status', 'fault', 'island_pgood', 'rv', 'rrequest', 'wv',
                      'wrequest', 'clk_obs', 'wclk_obs'})


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode(field, value):
    f = regmap.FIELD_BY_NAME[field]
    if isinstance(value, str):
        assert f['values'] and value in f['values'], (field, value)
        value = f['values'].index(value)
    return value


def plan(controls, block, entry):
    """Field settings, islands and checks for one entry (or a reason it is not simulated)."""
    nodes = {n['name']: n for n in controls['atb_nodes']}
    path, select = entry['path'], entry['select']
    islands = set(entry.get('islands') or []) | set(controls['block_islands'].get(block, []))
    fields, checks = {}, []
    for field, value in (entry.get('mode') or {}).items():
        fields[field] = encode(field, value)
        islands |= set(regmap.FIELD_BY_NAME[field]['islands'])
        checks.append(('slice', field, fields[field]))
    if path == 'atb1':
        node = nodes[select]
        if not node.get('hardware', True):
            return None, 'ATB node has no physical leaf (hardware=false)'
        fields['debug.atb.atb1'] = node['code']
        if node['island']:
            islands.add(node['island'])
        checks.append(('atb', node['code'], node['island']))
    elif path == 'dbg_obs':
        if select == 'commit_toggle':
            fields['debug.dbg_obs.sel0'] = 3
            checks.append(('commit_toggle',))
        else:
            index = controls['obs_status'].index(select)
            fields['debug.dbg_obs.sel0'] = 4+index
            if select.startswith('island_pgood_'):
                checks.append(('status', 'DBG_OBS0', f'island_pgood[{regmap.ISLANDS[select[13:]]}]'))
            elif select in STATUS_SOURCE:
                checks.append(('status', 'DBG_OBS0', STATUS_SOURCE[select]))
            else:
                return None, f'{select}: digital-internal source (mux selection only)'
    elif path == 'wdbg_obs':
        index = controls['wire_status'].index(select)
        fields['debug.wdbg_obs.select'] = 3+index
        if select not in WIRE_SOURCE:
            return None, f'{select}: digital-internal source'
        checks.append(('status', 'WDBG_OBS', WIRE_SOURCE[select]))
    elif path in PATH_FIELD:
        field = PATH_FIELD[path]
        fields[field] = encode(field, select)
        islands |= set(regmap.FIELD_BY_NAME[field]['islands'])
        if 'divider_log2' in entry:
            div = field.rsplit('.', 1)[0]+'.divider_log2'
            fields[div] = entry['divider_log2']
            checks.append(('slice', div, entry['divider_log2']))
        checks.append(('slice', field, fields[field]))
        if path in ('clk_obs', 'wclk_obs'):
            checks.append(('clock', path))
    elif path == 'freq_count':
        field = 'debug.freq_count_b.source' if select == 'cdr_ring_fbck' else 'debug.freq_count_a.source'
        fields[field] = encode(field, select)
        checks.append(('slice', field, fields[field]))
    elif path == 'spi':
        if select == '0x0B[0]':
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
    for island in islands:
        fields['debug.island_power.'+island] = 1
    return dict(fields=fields, islands=sorted(islands), checks=checks), None


def register_writes(fields):
    values = regmap.reset_config()
    values.update(fields)
    code = regmap.commit_code(values, regmap.reset_config(), False)
    writes = {}
    for name in fields:
        for chunk in regmap.FIELD_BY_NAME[name]['chunks']:
            writes[chunk['addr']] = 0
    for addr in writes:
        reg = regmap.REGISTER_BY_ADDR[addr]
        value = 0
        for name, lsb, width, reg_lsb in reg['chunks']:
            value |= ((values[name] >> lsb) & ((1 << width)-1)) << reg_lsb
        writes[addr] = value
    return writes, code


def slice_expr(field):
    f = regmap.FIELD_BY_NAME[field]
    bus = 'debug_cfg' if f['bus'] == 'debug' else 'analog_cfg'
    return f'dut.{bus}[{f["bus_lsb"]}+:{f["bus_bits"]}]', f['store'][1]


def testbench(cases):
    sv = ['`timescale 1ns/1ps', 'module tb_observation_paths;',
          ' reg reset_drive=0, sclk_drive=0, cs_drive=1, mosi_drive=0;',
          ' wire RESET_N=reset_drive, SPI_SCLK=sclk_drive, SPI_CS_N=cs_drive, SPI_MOSI=mosi_drive;',
          ' wire SPI_MISO; wire[9:0] D2H; wire D2H_CLK; wire DBG_OBS0,DBG_OBS1,CLK_OBS,WCLK_OBS,WDBG_OBS;',
          ' supply1 vdd; supply0 vss; wire[9:0] h2d=0; wire h2d_clk=0;',
          ' reg por=0; reg[5:0] pg=6\'b110111; reg flt=0; reg[11:0] ast=0; reg[12:0] wst=0;',
          ' reg rvx=0, rrq=0, wvx=0, wrq=0, cko=0, wcko=0, prev; integer failures=0;',
          ' pt_chip dut(.RESET_N(RESET_N),.SPI_SCLK(SPI_SCLK),.SPI_CS_N(SPI_CS_N),.SPI_MOSI(SPI_MOSI),',
          '  .SPI_MISO(SPI_MISO),.H2D(h2d),.H2D_CLK(h2d_clk),.D2H(D2H),.D2H_CLK(D2H_CLK),',
          '  .REF_IN(1\'b0),.REF_IN_N(1\'b0),.AUX_CLK_P(1\'b0),.AUX_CLK_N(1\'b0),',
          '  .WCLK_IN_P(1\'b0),.WCLK_IN_N(1\'b0),.WTX_EXT_P(1\'b0),.WTX_EXT_N(1\'b0),',
          '  .DBG_OBS0(DBG_OBS0),.DBG_OBS1(DBG_OBS1),.CLK_OBS(CLK_OBS),.WCLK_OBS(WCLK_OBS),.WDBG_OBS(WDBG_OBS),',
          '  .VDD_CORE(vdd),.VSS_CORE(vss),.VDD_HOST_A(vdd),.VSS_HOST_A(vss),.VDD_HOST_B(vdd),.VSS_HOST_B(vss),',
          '  .VDD_WIRE_A(vdd),.VSS_WIRE_A(vss),.VDD_WIRE_B(vdd),.VSS_WIRE_B(vss),',
          '  .VDD_RF(vdd),.VSS_RF(vss),.VDD_PLL(vdd),.VSS_PLL(vss));',
          ' // Only analog-macro OUTPUTS are driven (black box); no control/SPI/pad net is forced.',
          ' initial begin force dut.por_n=por; force dut.island_pgood=pg; force dut.fault=flt;',
          '  force dut.analog_status=ast; force dut.wire_analog_status=wst; force dut.rv=rvx; force dut.rrequest=rrq;',
          '  force dut.wv=wvx; force dut.wrequest=wrq; force dut.clk_obs=cko; force dut.wclk_obs=wcko; end',
          ' reg[15:0] result;',
          ' task spi(input[7:0] command,address,input[15:0] value); reg[31:0] tx; integer i;',
          '  begin tx={command,address,value}; result=0; cs_drive=0; #100;',
          '   for(i=31;i>=0;i=i-1) begin mosi_drive=tx[i]; #200; sclk_drive=1; #200; if(i<16) result[i]=SPI_MISO; sclk_drive=0; #100; end',
          '   cs_drive=1; #100; end endtask',
          ' task fail(input [8*120:1] msg); begin failures=failures+1; $display("FAIL %0s", msg); end endtask',
          ' task chip_reset; begin reset_drive=0; #200; reset_drive=1; #200; end endtask',
          ' initial begin',
          '  #50; por=1; reset_drive=1; #200;',
          '  spi(0,8\'h00,0); if(result!==16\'h5356) fail("ID");']
    def set_src(net, value):
        if net.startswith('island_pgood['):
            return f'pg[{net[13:-1]}]={value};'
        if net.startswith('analog_status['):
            return f'ast[{net[14:-1]}]={value};'
        if net.startswith('wire_analog_status['):
            return f'wst[{net[19:-1]}]={value};'
        return dict(fault='flt', rv='rvx', rrequest='rrq', wv='wvx', wrequest='wrq')[net]+f'={value};'
    for case in cases:
        tag = case['id']
        sv.append(f'  // {tag}')
        sv.append('  chip_reset; pg=6\'b110111; flt=0; ast=0; wst=0; rvx=0; rrq=0; wvx=0; wrq=0; cko=0; wcko=0;')
        for addr, value in sorted(case['writes'].items()):
            sv.append(f'  spi(8\'h80,8\'h{addr:02X},16\'h{value:04X});')
        sv.append('  spi(8\'h80,8\'h06,16\'h0001); spi(0,8\'h0C,0);')
        sv.append(f'  if(result[15:8]!==0) fail("{tag}: commit rejected");')
        sv.append('  #100;')
        for check in case['checks']:
            kind = check[0]
            if kind == 'atb':
                code, island = check[1], check[2]
                sv.append(f'  if(dut.atb1_sw!=={regmap.ATB_WIDTH}\'d1<<{code-1} || dut.atb1_en!==1 || dut.atb0_sw!==0) fail("{tag}: atb1 switch");')
                group = next(i for i, g in enumerate(regmap.ATB_GROUPS['atb1']) if code in g['codes'])
                sv.append(f'  if(dut.atb1_grp!==(1<<{group})) fail("{tag}: atb1 group");')
                if island:
                    bit = regmap.ISLANDS[island]
                    sv.append(f'  pg[{bit}]=0; #100; if(dut.atb1_sw!==0 || dut.atb1_en!==0) fail("{tag}: leaf not opened with island off"); pg[{bit}]=1; #100;')
            elif kind == 'slice':
                expr, shift = slice_expr(check[1])
                sv.append(f'  if({expr}!==({check[2]}>>{shift})) fail("{tag}: {check[1]} slice");')
            elif kind == 'status':
                pad, net = check[1], check[2]
                sv.append(f'  {set_src(net, 1)} #100; if({pad}!==1) fail("{tag}: {pad} not high");')
                sv.append(f'  {set_src(net, 0)} #100; if({pad}!==0) fail("{tag}: {pad} not low");')
            elif kind == 'commit_toggle':
                sv.append(f'  prev=DBG_OBS0; spi(8\'h80,8\'h06,16\'h0001); #100;')
                sv.append(f'  if(DBG_OBS0===prev || DBG_OBS0===1\'bz || prev===1\'bz) fail("{tag}: commit toggle");')
            elif kind == 'clock':
                pad, net = ('CLK_OBS', 'cko') if check[1] == 'clk_obs' else ('WCLK_OBS', 'wcko')
                sv.append(f'  {net}=1; #50; if({pad}!==1) fail("{tag}: {pad} high"); {net}=0; #50; if({pad}!==0) fail("{tag}: {pad} low");')
            elif kind == 'spi_bit':
                sv.append(f'  flt=1; #100; spi(0,8\'h{check[1]:02X},0); if(result[{check[2]}]!==1) fail("{tag}: spi bit high");')
                sv.append(f'  flt=0; #100; spi(0,8\'h{check[1]:02X},0); if(result[{check[2]}]!==0) fail("{tag}: spi bit low");')
            elif kind == 'spi_pgood':
                sv.append(f'  #100; spi(0,8\'h0A,0); if(result[13:8]!==6\'b110111) fail("{tag}: pgood bits");')
                sv.append(f'  pg=0; #100; spi(0,8\'h0A,0); if(result[13:8]!==0) fail("{tag}: pgood low");')
            elif kind == 'spi_por':
                sv.append(f'  spi(8\'h80,8\'h0D,16\'h0003); spi(0,8\'h0D,0); if(result[0]!==0) fail("{tag}: por clear");')
                sv.append(f'  por=0; #200; por=1; #200; spi(0,8\'h0D,0); if(result[0]!==1) fail("{tag}: por occurred");')
            elif kind == 'spi_id':
                sv.append(f'  spi(0,8\'h00,0); if(result!==16\'h5356) fail("{tag}: id");')
        sv.append(f'  $display("CASE {tag} done failures=%0d", failures);')
    sv += ['  if(failures==0) $display("OBSERVATION_PATHS_PASS"); else $display("OBSERVATION_PATHS_FAIL %0d", failures);',
           '  $finish; end', ' initial begin #200000000; $fatal(1,"timeout"); end', 'endmodule']
    return '\n'.join(sv)+'\n'


NEGATIVES = ('status_source', 'wire_source', 'atb_code', 'slice_value', 'island_gate', 'clock_pad')


def negative(cases, kind):
    """Corrupt ONE case's expectation or programming; the simulation must fail it."""
    for case in cases:
        checks = case['checks']
        for i, c in enumerate(checks):
            if kind == 'status_source' and c[0] == 'status' and c[2].startswith('analog_status['):
                k = int(c[2][14:-1])
                checks[i] = ('status', c[1], f'analog_status[{(k+1) % 12}]')
            elif kind == 'wire_source' and c[0] == 'status' and c[2].startswith('wire_analog_status['):
                k = int(c[2][19:-1])
                checks[i] = ('status', c[1], f'wire_analog_status[{(k+1) % 13}]')
            elif kind == 'atb_code' and c[0] == 'atb':
                checks[i] = ('atb', c[1]+1, c[2])
            elif kind == 'slice_value' and c[0] == 'slice' and c[2]:
                checks[i] = ('slice', c[1], c[2]-1)
            elif kind == 'island_gate' and c[0] == 'atb' and c[2]:
                island = c[2]
                bit = [a for a, r in regmap.REGISTER_BY_ADDR.items() if any(ch[0] == 'debug.island_power.'+island for ch in r['chunks'])][0]
                case['writes'][bit] = 0
            elif kind == 'clock_pad' and c[0] == 'clock':
                case['writes'] = {a: v for a, v in case['writes'].items()
                                  if not any(ch[0] == 'debug.island_power.debug' for ch in regmap.REGISTER_BY_ADDR[a]['chunks'])} | {
                                  a: 0 for a in case['writes'] if any(ch[0] == 'debug.island_power.debug' for ch in regmap.REGISTER_BY_ADDR[a]['chunks'])}
            else:
                continue
            case['id'] = 'NEG_'+kind+':'+case['id']
            return [case]
    raise AssertionError('no case for negative '+kind)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--output-dir', type=Path, default=ROOT/'scratch/observation-paths')
    ap.add_argument('--io-model', type=Path, default=ROOT/'scratch/chip-io/gf180mcu_fd_io.v')
    ap.add_argument('--mutate', help='negative control: "<block>:<index>:<field>=<value>" applied to one entry')
    ap.add_argument('--negative', choices=NEGATIVES, help='run one built-in negative control (must FAIL)')
    a = ap.parse_args()
    out = a.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out/'report.json').write_text(json.dumps(dict(status='incomplete'))+'\n')
    controls_path = PROJECT/'spec/debug-controls.json'
    controls = json.loads(controls_path.read_text())
    blocks = controls['block_observation']['blocks']
    if a.mutate:
        target, change = a.mutate.split('=', 1)[0], a.mutate.split('=', 1)[1]
        block, index, key = target.split(':')
        blocks[block][int(index)][key] = json.loads(change)
    cases, skipped = [], []
    for block, entries in blocks.items():
        for index, entry in enumerate(entries):
            tag = f'{block}:{index}:{entry["path"]}:{entry["select"]}'
            planned, reason = plan(controls, block, entry)
            if planned is None:
                skipped.append(dict(id=tag, block=block, index=index, reason=reason))
                continue
            writes, code = register_writes(planned['fields'])
            cases.append(dict(id=tag, block=block, index=index, writes=writes, model_commit_code=code, **planned))
    if a.negative:
        cases = negative(cases, a.negative)
    tb = out/'tb_observation_paths.sv'
    tb.write_text(testbench(cases))
    sources = [tb, PROJECT/'integration/pt_chip.sv', PROJECT/'integration/pt_provider_io.sv',
               *sorted((PROJECT/'rtl').glob('*.sv'))]
    compile_result = subprocess.run(['iverilog', '-g2012', '-Dfunctional', '-DPT_EXTERNAL_IO', '-I', str(PROJECT/'rtl'),
                                     '-s', 'tb_observation_paths', '-o', str(out/'paths.vvp'), *map(str, sources),
                                     str(a.io_model)], text=True, capture_output=True, timeout=600)
    (out/'compile.log').write_text(compile_result.stdout+compile_result.stderr)
    assert compile_result.returncode == 0, compile_result.stderr[-3000:]
    sim = subprocess.run(['vvp', '-n', str(out/'paths.vvp')], cwd=out, text=True, capture_output=True, timeout=3600)
    (out/'sim.log').write_text(sim.stdout+sim.stderr)
    lines = sim.stdout.splitlines()
    failures = [l[5:] for l in lines if l.startswith('FAIL ')]
    finished = 'OBSERVATION_PATHS_PASS' in lines or any(l.startswith('OBSERVATION_PATHS_FAIL') for l in lines)
    results = []
    for case in cases:
        done = any(l.startswith(f'CASE {case["id"]} done') for l in lines)
        own = [f for f in failures if f.startswith(case['id']+':')]
        results.append(dict(id=case['id'], block=case['block'], index=case['index'], islands=case['islands'],
                            register_writes={f'0x{k:02X}': f'0x{v:04X}' for k, v in sorted(case['writes'].items())},
                            checks=[list(c) for c in case['checks']], model_commit_code=case['model_commit_code'],
                            status='pass' if done and not own else 'fail', failures=own))
    status = 'pass' if finished and not failures and all(r['status'] == 'pass' for r in results) else 'fail'
    report = dict(status=status, scope='assembled RTL (pt_chip + provider pad models) selection/status/clock paths to the '
                  'pt_analog_physical boundary and debug pads; analog source nets are NOT exercised (black-box macro)',
                  mutation=a.mutate, negative=a.negative, cases=results, not_simulated=skipped,
                  forced_boundary_outputs=FORCED_NETS, controls_sha256=sha(controls_path),
                  source_hashes={str(p.relative_to(ROOT)): sha(p) for p in sources[1:]}, script_sha256=sha(__file__),
                  io_model_sha256=sha(a.io_model))
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(status=status, simulated=len(results), passed=sum(r['status'] == 'pass' for r in results),
                          not_simulated=len(skipped), failures=failures[:20], report=str(out/'report.json')), indent=2))
    if status != 'pass':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
