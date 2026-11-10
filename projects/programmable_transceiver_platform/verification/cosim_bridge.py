"""Build a Verilator/XSPICE d_cosim bridge for a delay-free digital boundary.

The SPICE digital-port order comes from the generated Verilator header and is
returned explicitly. Wide vectors are accessed bit by bit, without integer
shift truncation. All state is per-instance and survives until cleanup.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess


def checked(command, log, cwd=None):
    with Path(log).open('w') as output:
        subprocess.run(list(map(str, command)), cwd=cwd, stdout=output,
                       stderr=subprocess.STDOUT, check=True, timeout=300)


def compile_bridge(sources, top, out, ngspice_source, includes=(), defines=(), expose_outputs=None,
                   projections=None, expose_inputs=None):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    ngspice_source = Path(ngspice_source).resolve()
    obj = out/'obj'
    sources = list(map(lambda p: Path(p).resolve(), sources))
    arguments = ['verilator', '--cc', '--no-timing', '-Wno-fatal', '--unroll-count', '512',
                 '--top-module', top, '--prefix', 'Vchip', '--Mdir', obj,
                 '-CFLAGS', '-fPIC', '-CFLAGS', '-std=c++17',
                 '-CFLAGS', f'-I{ngspice_source}/src/include']
    arguments += [f'-I{Path(p).resolve()}' for p in includes]
    arguments += [f'-D{name}' for name in defines]
    arguments += sources
    checked(arguments, out/'verilate.log')
    if expose_outputs is not None or expose_inputs is not None:
        # XSPICE's A-card parser has a fixed token collection. Export only the
        # analog boundary used by this experiment, retaining the real macro as
        # the child. Unconnected observation outputs do not alter its logic.
        original_header = (obj/'Vchip.h').read_text()
        declarations, connections, found, local = [], [], set(), []
        projections = projections or {}
        projected_ports = {v[0] for v in projections.values()}
        output_widths = {}
        for direction, name, msb, lsb in re.findall(
                r'VL_(INOUT|IN|OUT)(?:8|16|64|W)?\(&([A-Za-z_][A-Za-z_0-9]*),(\d+),(\d+)(?:,\d+)?\)', original_header):
            if direction == 'INOUT':
                raise ValueError('Use an explicit split I/O adapter for inout ports')
            expose = ((expose_inputs is None or name in expose_inputs) if direction == 'IN' else
                      (expose_outputs is None or name in expose_outputs))
            if direction == 'OUT':
                output_widths[name] = int(msb)+1
            if expose:
                width = '' if int(msb) == 0 and int(lsb) == 0 else f'[{msb}:{lsb}] '
                declarations.append(('input' if direction == 'IN' else 'output')+' wire '+width+name)
                connections.append(f'.{name}({name})')
                found.add(name)
            else:
                if direction == 'IN':
                    connections.append(f'.{name}({int(msb)+1}\'d0)')
                    continue
                if name in projected_ports:
                    local.append(f'wire [{msb}:{lsb}] raw_{name};')
                    connections.append(f'.{name}(raw_{name})')
                else:
                    connections.append(f'.{name}()')
        if expose_outputs is not None and set(expose_outputs)-found:
            raise ValueError(f'Unknown output ports: {set(expose_outputs)-found}')
        if expose_inputs is not None and set(expose_inputs)-found:
            raise ValueError(f'Unknown input ports: {set(expose_inputs)-found}')
        for name, (port, bit, width) in projections.items():
            if name in found or not re.fullmatch(r'[a-zA-Z_][a-zA-Z_0-9]*', name):
                raise ValueError(f'Invalid or duplicate projected output: {name}')
            if port not in output_widths or bit < 0 or width < 1 or bit+width > output_widths[port]:
                raise ValueError(f'Invalid projected range: {name}')
            declarations.append(f'output wire [{width-1}:0] {name}')
            source = port if port in expose_outputs else f'raw_{port}'
            local.append(f'assign {name} = {source}[{bit}+:{width}];')
        adapter = out/'boundary.sv'
        adapter.write_text('`timescale 1ns/1ps\nmodule '+top+'_cosim(\n'+',\n'.join(declarations)+
                           ');\n'+'\n'.join(local)+'\n'+top+' digital('+',\n'.join(connections)+');\nendmodule\n')
        arguments[arguments.index('--top-module')+1] = top+'_cosim'
        arguments.append(adapter)
        sources.append(adapter)
        checked(arguments, out/'verilate-boundary.log')
    # VL_IN8(&name,msb,lsb), or VL_OUTW(&name,msb,lsb,word_count).
    header = (obj/'Vchip.h').read_text()
    ports = {'IN': [], 'OUT': [], 'INOUT': []}
    for direction, storage, name, msb, lsb in re.findall(
            r'VL_(INOUT|IN|OUT)(8|16|64|W)?\(&([A-Za-z_][A-Za-z_0-9]*),(\d+),(\d+)(?:,\d+)?\)', header):
        msb, lsb = int(msb), int(lsb)
        if lsb != 0:
            raise ValueError(f'Nonzero port LSB requires an explicit adapter: {name}')
        for bit in range(msb, -1, -1):
            expression = f'dut->{name}'
            offset = bit
            if storage == 'W':
                expression += f'[{bit//32}]'
                offset %= 32
            ports[direction].append((name if msb == 0 else f'{name}[{bit}]', expression, offset))
    if ports['INOUT'] or not ports['IN'] or not ports['OUT']:
        raise ValueError('Co-simulation boundary must have separate inputs and outputs, without inouts')
    inputs, outputs = ports['IN'], ports['OUT']
    if len(inputs)+len(outputs) > 256:
        raise ValueError('Select a smaller exported boundary to stay within the XSPICE A-card token limit')
    setters = []
    getters = []
    for i, (_, expression, bit) in enumerate(inputs):
        setters.append(f'case {i}: {expression} = ({expression} & ~(uint64_t(1) << {bit})) | (uint64_t(value->state == ONE) << {bit}); break;')
    for i, (_, expression, bit) in enumerate(outputs):
        getters.append(f'emit(info, state, {i}, ({expression} >> {bit}) & 1);')
    shim = out/'bridge.cpp'
    shim.write_text('''#include <cstdint>
#include <vector>
#include "verilated.h"
#include "Vchip.h"
#include "ngspice/cmtypes.h"
#include "ngspice/cosim.h"
struct State {
 VerilatedContext context;
 static VerilatedContext* single_thread(VerilatedContext* context) {
  context->threads(1);
  return context;
 }
 Vchip dut{single_thread(&context)};
 std::vector<int> previous;
 explicit State(unsigned count): previous(count, 0) {}
};
static void emit(co_info* info, State* state, unsigned index, int bit) {
 if (state->previous[index] == bit) return;
 state->previous[index] = bit;
 Digital_t value = {bit ? ONE : ZERO, STRONG};
 info->out_fn(info, index, &value);
}
static void input(co_info* info, unsigned index, Digital_t* value) {
 // ADC bridge may be unknown during an edge. Keep the previous logic state
 // until the analog signal reaches a defined level; never invent an edge.
 if (value->state == UNKNOWN) return;
 auto state = static_cast<State*>(info->handle);
 auto dut = &state->dut;
 switch (index) {
'''+'\n'.join(setters)+'''
 }
}
static void step(co_info* info) {
 auto state = static_cast<State*>(info->handle);
 auto dut = &state->dut;
 state->context.time(static_cast<uint64_t>(info->vtime * 1e12));
 dut->eval();
'''+'\n'.join(getters)+'''
}
static void cleanup(co_info* info) {
 auto state = static_cast<State*>(info->handle);
 state->dut.final();
 delete state;
 info->handle = nullptr;
}
extern "C" void Cosim_setup(co_info* info) {
'''+f''' info->in_count = {len(inputs)};
 info->out_count = {len(outputs)};
'''+''' info->inout_count = 0;
 info->handle = new State(info->out_count);
 info->step = step;
 info->in_fn = input;
 info->cleanup = cleanup;
 info->method = After_input;
}
''')
    checked(arguments+['--exe', shim, '--build', '-j', '2', '-LDFLAGS', '-shared',
                       '-o', str(out/'digital.so')], out/'build.log')
    hash_inputs = sources+[shim, Path(__file__).resolve()]
    for directory in includes:
        hash_inputs.extend(Path(directory).resolve().glob('*.svh'))
        hash_inputs.extend(Path(directory).resolve().glob('*.vh'))
    hash_inputs += [ngspice_source/'src/include/ngspice/cmtypes.h',
                    ngspice_source/'src/include/ngspice/cosim.h']
    manifest = {'top': top, 'inputs': [p[0] for p in inputs],
                'outputs': [p[0] for p in outputs], 'library': str(out/'digital.so'),
                'projections': projections or {},
                'exposed_input_ports': sorted(expose_inputs) if expose_inputs is not None else None,
                'source_hashes': {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in hash_inputs}}
    (out/'ports.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest
