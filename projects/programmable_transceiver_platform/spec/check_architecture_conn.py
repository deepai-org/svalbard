#!/usr/bin/env python3
"""Check analog-architecture.json `chip_implementation` against the two chips' conns (integration/chips/{rf,wired}/chip.conn).

The conns are the connectivity source of truth; an instance name means the same block on both chips, so the check runs on
the union of the two instance sets. The architecture inventory keeps the functional blocks the models
and the register generator use; `chip_implementation` says which conn instances build each of them.
Passes when: every conn instance is claimed exactly once (by a block or an infrastructure group), every
pattern matches at least one conn instance, every inventory block has an entry (an empty list needs a reason
in `no_instance`), and every control_fields prefix is a block or is listed in `control_field_cells`.

    python3 spec/check_architecture_conn.py          exit 0 = in line
"""
import fnmatch, json, sys
from pathlib import Path

P = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(P / 'integration/chips'))
import check_top  # noqa: E402  (the conn parser)


def main():
    arch = json.loads((P / 'spec/analog-architecture.json').read_text())
    impl = arch['chip_implementation']
    inst, err = {}, []
    for chip in ('rf', 'wired'):
        i, _ports, _waive, perr = check_top.parse(check_top.read_conn(str(P / f'integration/chips/{chip}/chip.conn')))
        err += [f'{chip} conn: {e}' for e in perr]
        for n, v in i.items():
            # one generator, one master per chip (D8): pt_core_bias_<chip>
            per_chip = {inst[n]['master'], v['master']} == {'pt_core_bias_rf', 'pt_core_bias_wired'} if n in inst else False
            if n in inst and inst[n]['master'] != v['master'] and not per_chip: err.append(f'{n}: master {v["master"]} on pt_{chip}, {inst[n]["master"]} on the other chip')
            inst.setdefault(n, v)
    claims = {}
    for kind in ('blocks', 'infrastructure'):
        for owner, patterns in impl[kind].items():
            for pat in patterns:
                hit = fnmatch.filter(inst, pat)
                if not hit:
                    err.append(f'{kind}.{owner}: pattern {pat} matches no conn instance')
                for h in hit:
                    claims.setdefault(h, []).append(f'{kind}.{owner}')
    for name in inst:
        c = claims.get(name, [])
        if len(c) != 1:
            err.append(f'conn instance {name} ({inst[name]["master"]}) claimed {len(c)} times: {c}')
    blocks = set(arch['blocks'])
    for b in sorted(blocks - set(impl['blocks'])):
        err.append(f'inventory block {b} has no chip_implementation entry')
    for b in sorted(set(impl['blocks']) - blocks):
        err.append(f'chip_implementation names {b}, which is not an inventory block')
    for b, patterns in impl['blocks'].items():
        if not patterns and b not in impl['no_instance']:
            err.append(f'block {b} has no instance and no reason in no_instance')
        if patterns and b in impl['no_instance']:
            err.append(f'block {b} has instances and a no_instance reason')
    for prefix in sorted({c.split('.')[0] for c in arch['control_fields']} - blocks):
        cells = impl['control_field_cells'].get(prefix)
        if not cells:
            err.append(f'control_fields prefix {prefix} is neither a block nor in control_field_cells')
        else:
            for pat in cells:
                if not fnmatch.filter(inst, pat):
                    err.append(f'control_field_cells.{prefix}: {pat} matches no conn instance')
    for e in err:
        print('FAIL', e)
    print(f'architecture vs conns: {len(inst)} instances on the two chips, {len(blocks)} inventory blocks, '
          f'{sum(1 for v in impl["blocks"].values() if v)} with instances, {len(err)} problems')
    return 1 if err else 0


if __name__ == '__main__':
    sys.exit(main())
