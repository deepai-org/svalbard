#!/usr/bin/env python3
"""Census retained memory and register bits in the complete default hierarchy.

Run before memory mapping so arrays remain identifiable. This accounts for
actual state, separately from the planning ledger and physical cell area.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
IMAGE = 'svalbard/librelane-gf180-canary:2026.08'


def number(value):
    return int(value, 2) if isinstance(value, str) else int(value)


def census(out):
    assert not (out/'report.json').exists(), 'Use a fresh census directory'
    out.mkdir(parents=True, exist_ok=True)
    config_path = PROJECT/'verification/digital_hardening/config.json'
    config = json.loads(config_path.read_text())
    policy_path = PROJECT/'spec/analog-architecture.json'
    policy = json.loads(policy_path.read_text())['resource_policy']
    shutil.copytree(PROJECT/'rtl', out/'rtl')
    names = [Path(name.removeprefix('dir::')).name for name in config['VERILOG_FILES']]
    script = 'read_verilog -sv -DSYNTHESIS -I/out/rtl '+' '.join('/out/rtl/'+n for n in names)+'\n'
    script += '''hierarchy -check -top pt_digital_macro
proc
flatten
opt
memory_dff
memory_collect
opt_clean
check -assert
write_json /out/storage.json
'''
    (out/'storage.ys').write_text(script)
    identity = subprocess.run(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}'],
                              check=True, capture_output=True, text=True).stdout.strip()
    with (out/'yosys.log').open('w') as log:
        subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '6g',
                        '-v', f'{out}:/out', '--entrypoint', 'yosys', identity, '-Q', '-T', '-s', '/out/storage.ys'],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    modules = json.loads((out/'storage.json').read_text())['modules']
    arrays, registers, groups = [], [], defaultdict(lambda: dict(array_bits=0, register_bits=0))
    unrolled_arrays = defaultdict(list)
    def retained_cells(top, prefix=''):
        module = modules[top]
        aliases_by_bits = defaultdict(list)
        for name, info in module['netnames'].items():
            if not name.startswith('$'):
                aliases_by_bits[tuple(info['bits'])].append(prefix+name)
        for name, cell in module['cells'].items():
            if cell['type'] in modules:
                yield from retained_cells(cell['type'], prefix+name+'.')
            else:
                yield prefix+name, cell, aliases_by_bits
    for name, cell, aliases_by_bits in retained_cells('pt_digital_macro'):
        kind, params = cell['type'], cell['parameters']
        if kind == '$mem_v2':
            width, depth = number(params['WIDTH']), number(params['SIZE'])
            item = dict(name=name, width=width, depth=depth, bits=width*depth)
            arrays.append(item)
            group = name.rsplit('.', 1)[0]
            groups[group]['array_bits'] += item['bits']
        elif kind in ('$dff', '$adff', '$sdff', '$dffe', '$adffe', '$sdffe', '$sdffce', '$ff', '$dlatch', '$adlatch'):
            width = number(params['WIDTH'])
            # PROC cell names encode the write process; output net aliases
            # retain the architectural owner and are easier to review.
            q = cell['connections']['Q']
            aliases = aliases_by_bits[tuple(q)]
            owner = min(aliases, key=len) if aliases else name
            item = dict(name=owner, cell=name, kind=kind, bits=width)
            word = re.fullmatch(r'(.+)\[(\d+)\]', owner)
            if word:
                unrolled_arrays[word[1]].append(dict(index=int(word[2]), **item))
            else:
                registers.append(item)
                groups[owner.rsplit('.', 1)[0]]['register_bits'] += width
    # The Verilog frontend unrolls arrays whose write process has an async
    # reset branch. These are still payload storage, even as ordinary FFs.
    for name, words in unrolled_arrays.items():
        bits = sum(word['bits'] for word in words)
        arrays.append(dict(name=name, depth=len(words), widths=sorted(set(w['bits'] for w in words)),
                           bits=bits, implementation='unrolled flip-flop words'))
        groups[name.rsplit('.', 1)[0]]['array_bits'] += bits
    array_bits = sum(r['bits'] for r in arrays)
    register_bits = sum(r['bits'] for r in registers)
    cap = policy['memory_total_cap_bits']
    result = dict(status='state_census_not_physical_signoff', top='pt_digital_macro',
                  array_bits=array_bits, register_bits=register_bits, total_state_bits=array_bits+register_bits,
                  planning_total_cap_bits=cap, total_state_minus_planning_cap_bits=array_bits+register_bits-cap,
                  arrays=sorted(arrays, key=lambda r: -r['bits']),
                  registers=sorted(registers, key=lambda r: -r['bits']),
                  by_owner=dict(sorted(groups.items())),
                  image_id=identity,
                  source_hashes={str(PROJECT/'rtl'/p.name): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in (out/'rtl').iterdir() if p.is_file()},
                  metadata_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in [config_path, policy_path, Path(__file__).resolve()]},
                  artifact_hashes={'storage.json': hashlib.sha256((out/'storage.json').read_bytes()).hexdigest()},
                  note='Pre-mapping retained state; physical mapping may add/duplicate clock or data registers. Resolve cap scope explicitly.')
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ['status', 'array_bits', 'register_bits', 'total_state_bits',
                                           'planning_total_cap_bits', 'total_state_minus_planning_cap_bits']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/digital-storage')
    census(parser.parse_args().output_dir.resolve())
