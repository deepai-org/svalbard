#!/usr/bin/env python3
"""Per-block observation checklist from declared readiness, real ports and the
explicit assignment in spec/debug-controls.json:block_observation.

The assignment is validated against the catalogs (ATB node/code, leaf exists,
<=12 leaves per local bus, status names, clock-source legality, island
gating, shared-cell modes) and against analog-architecture.json output ports
(every port of every open block must be assigned, directly or explicitly via a
downstream block). Each entry is then graded by the evidence that exists:

  mapped            assignment only
  rtl_selection     check_observation_paths.py: SPI selection / status / clock
                    reaches the pt_analog_physical boundary and debug pads in
                    assembled RTL (analog macro is a black box)
  analog_fixture    an independent audit of a mixed-level fixture measured the
                    real source net at the pad (core-bias campaigns)

This report never changes ledger states; it preserves open/retired states
from tapeout-readiness.json and lists what each block still needs.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]


PATH_CATALOG = {'atb1', 'dbg_obs', 'wdbg_obs', 'clk_obs', 'wclk_obs', 'wmon', 'bb_tap', 'freq_count', 'spi',
                'host_data', 'pad'}
SUPPLY_PORTS = {'vdd', 'vss'}
# Independent audits of mixed-level fixtures that measured real source nets.
FIXTURE_AUDITS = [ROOT/'scratch/core-bias-observation-checkpointed/core-bias-audit.json',
                  ROOT/'scratch/core-bias-idac1-observation-current/spec-independent-audit.json']


def validate_mapping(controls, ledger, arch, read):
    """Static checks of block_observation. Returns (errors, per-entry info, port gaps)."""
    errors, gaps = [], {}
    mapping = controls.get('block_observation', {}).get('blocks', {})
    nodes = {n['name']: n for n in controls['atb_nodes']}
    groups = controls['atb_groups']
    for bus in ('atb0', 'atb1'):
        for group in groups[bus]:
            if len(group['codes']) > groups.get('max_leaves_per_group', 12):
                errors.append(f'{bus} group {group["name"]} has {len(group["codes"])} leaves (>12)')
    clk = controls['controls']['debug.clk_obs']['fields']['source']
    values = {'clk_obs': set(clk['values'])-set(clk.get('forbidden', [])),
              'wmon': set(controls['controls']['debug.wmon_select']['fields']['select']['values']),
              'bb_tap': {v for v in controls['controls']['debug.bb_tap']['fields']['mode']['values'] if v.startswith('observe')},
              'freq_count': set(controls['controls']['debug.freq_count_a']['fields']['source']['values'])}
    for v in values.values():
        v.discard('off')
    infos = {}
    for section in ('core_blocks', 'chain_blocks'):
        for name, block in ledger[section].items():
            if block['tests']['observable']['state'] == 'retired':
                continue
            entries = mapping.get(name)
            if not entries:
                errors.append(f'{name}: no observation assignment')
                continue
            block_islands = set(controls['block_islands'].get(name, []))
            ports = [p for p in arch.get(name, {}).get('outputs', []) if p not in SUPPLY_PORTS]
            direct, indirect = set(), set()
            for index, e in enumerate(entries):
                tag = f'{name}[{index}] {e["path"]}:{e["select"]}'
                problems = []
                if e['path'] not in PATH_CATALOG:
                    problems.append('unknown path')
                if e['path'] == 'atb1':
                    node = nodes.get(e['select'])
                    if node is None:
                        problems.append('unknown ATB node')
                    else:
                        if not node.get('hardware', True):
                            problems.append('ATB node has no physical leaf')
                        if not any(node['code'] in g['codes'] for g in groups['atb1']):
                            problems.append('ATB code in no atb1 group')
                        allowed = block_islands | set(e.get('islands') or [])
                        if node['island'] and node['island'] not in allowed:
                            problems.append(f'node island {node["island"]} not among the entry/block islands')
                elif e['path'] == 'dbg_obs' and e['select'] not in controls['obs_status'] + controls['wire_status'] + ['commit_toggle']:
                    problems.append('not an obs_status / wire_status name')   # PD22: wire_status is on DBG_OBS (codes 37+n)
                elif e['path'] in ('wdbg_obs', 'wclk_obs'):
                    problems.append('retired pad (PD22): use dbg_obs / clk_obs')
                elif e['path'] in values and e['select'] not in values[e['path']]:
                    problems.append('selection not legal for this path (forbidden, absent or not an observe mode)')
                for field, value in (e.get('mode') or {}).items():
                    group, fname = field.rsplit('.', 1)
                    spec = controls['controls'].get(group, {}).get('fields', {}).get(fname)
                    if spec is None or ('values' in spec and value not in spec['values']):
                        problems.append(f'bad mode {field}={value}')
                if not e.get('expected'):
                    problems.append('no expected bench result')
                eports = e['port'] if isinstance(e.get('port'), list) else [e['port']] if e.get('port') else []
                for port in eports:
                    if port not in arch.get(name, {}).get('outputs', []):
                        problems.append(f'port {port} is not an architecture output')
                for p in problems:
                    errors.append(f'{tag}: {p}')
                (indirect if e.get('via') else direct).update(eports)
                infos[(name, index)] = dict(problems=problems)
            unassigned = [p for p in ports if p not in direct | indirect]
            indirect_only = [p for p in ports if p in indirect and p not in direct]
            for p in unassigned:
                errors.append(f'{name}: output port {p} has no observation assignment')
            gaps[name] = dict(ports=ports, unassigned=unassigned, indirect_only=indirect_only)
    return errors, infos, gaps


def fixture_evidence(read):
    measured = {}
    for path in FIXTURE_AUDITS:
        if not path.exists():
            continue
        audit = json.loads(read(path))
        if audit.get('status') != 'pass':
            continue
        for check in audit['completed_checks']:
            if check.get('check') in ('ATB sense', 'IDAC1 SMU current'):
                code = check.get('code') if check['check'] == 'ATB sense' else check.get('atb_code')
                measured.setdefault(code, dict(audit=str(path.relative_to(ROOT)), net=check.get('net', 'IDAC1')))
    return measured


def inventory(output, require_complete=False, paths_report=None):
    sources = {}
    def read(path):
        path = Path(path).resolve()
        sources[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        return path.read_text()
    ledger = json.loads(read(PROJECT/'spec/tapeout-readiness.json'))
    controls_path = PROJECT/'spec/debug-controls.json'
    controls = json.loads(read(controls_path))
    arch = json.loads(read(PROJECT/'spec/analog-architecture.json'))['blocks']
    mapping_errors, _, port_gaps = validate_mapping(controls, ledger, arch, read)
    paths = {}
    paths_state = 'missing'
    if paths_report and paths_report.exists():
        report = json.loads(read(paths_report))
        if report.get('controls_sha256') != hashlib.sha256(controls_path.read_bytes()).hexdigest():
            paths_state = 'stale (debug-controls.json changed since the path check)'
        elif report.get('negative') or report.get('mutation'):
            paths_state = 'ignored (negative-control run)'
        else:
            paths_state = report.get('status')
            paths = {(c['block'], c['index']): c for c in report['cases']}
            paths.update({(c['block'], c['index']): dict(c, status='not_simulated') for c in report['not_simulated']})
    fixture = fixture_evidence(read)
    nodes = {n['name']: n for n in controls['atb_nodes']}
    mapping = controls.get('block_observation', {}).get('blocks', {})
    core = set(controls['core_blocks']['blocks'])
    rows, shared, missing_files = [], defaultdict(list), set()
    for section in ('core_blocks', 'chain_blocks'):
        for name, block in ledger[section].items():
            observation = block['tests']['observable']
            islands = controls['block_islands'].get(name, ['core'] if name in core else [])
            evidence = list(dict.fromkeys(block['tests']['clean'].get('evidence', [])+
                                         observation.get('evidence', [])))
            ports, resolved = set(), []
            for ref in evidence:
                path = ROOT/ref.split('#', 1)[0]
                if not path.exists():
                    missing_files.add(str(path))
                    continue
                if path.suffix != '.json':
                    continue
                document = json.loads(read(path))
                artifacts = document.get('artifact_hashes', document.get('generated_hashes', {}))
                choices = []
                for artifact in artifacts:
                    if artifact.endswith('.ext.spice'):
                        choices += [path.parent/artifact, path.parent.parent/artifact, ROOT/artifact]
                if document.get('block'):
                    choices.append(path.parent/(str(document['block'])+'.ext.spice'))
                for extraction in dict.fromkeys(p.resolve() for p in choices if p.exists()):
                    text = re.sub(r'\n\+\s*', ' ', read(extraction))
                    cells = dict(re.findall(r'^\.subckt\s+(\S+)\s+([^\n]+)', text, re.I | re.M))
                    top = document.get('top_cell')
                    if top not in cells:
                        top = 'pt_'+str(document.get('block', name))
                    if top not in cells:
                        continue  # Require an explicit top; never pick a private leaf by guesswork.
                    actual = cells[top].split()
                    ports.update(p for p in actual if 'atb' in p.lower())
                    item = dict(extraction=str(extraction.relative_to(ROOT)), top=top,
                                atb_ports=[p for p in actual if 'atb' in p.lower()])
                    if item not in resolved:
                        resolved.append(item)
                        shared[(str(extraction.relative_to(ROOT)), top)].append(name)
            candidates = [n['code'] for n in controls['atb_nodes'] if n.get('hardware', True) and
                          ((n.get('island') in islands) or (n.get('island') is None and islands == ['core']))]
            state = observation['state']
            checklist = []
            for index, e in enumerate(mapping.get(name, [])):
                tiers = ['mapped']
                case = paths.get((name, index))
                if case and case.get('status') == 'pass':
                    tiers.append('rtl_selection')
                if e['path'] == 'atb1' and e['select'] in nodes and nodes[e['select']]['code'] in fixture:
                    tiers.append('analog_fixture')
                checklist.append(dict(
                    signal=e['signal'], port=e.get('port'), path=e['path'], select=e['select'],
                    atb_code=nodes[e['select']]['code'] if e['path'] == 'atb1' and e['select'] in nodes else None,
                    mode=e.get('mode'), via=e.get('via'), islands=sorted(set(e.get('islands') or []) | set(islands) - {'core'}),
                    register_writes=(case or {}).get('register_writes'), expected=e['expected'],
                    evidence=tiers, rtl_note=(case or {}).get('reason'),
                    fixture=fixture.get(nodes[e['select']]['code']) if e['path'] == 'atb1' and e['select'] in nodes else None))
            rows.append(dict(block=name, category=section, observation_state=state,
                             checklist=checklist, port_gaps=port_gaps.get(name),
                             implementation=block.get('implementation_dir'), islands=islands,
                             domain_mapping_required=not bool(islands), extracted_atb_ports=sorted(ports),
                             extracted_cells=resolved, island_candidate_codes=candidates,
                             existing_observation_evidence=observation.get('evidence', []),
                             note=observation.get('note', ''),
                             remaining=[] if state in ('pass', 'retired') else remaining_items(checklist, port_gaps.get(name))))
    counts = dict(Counter(r['observation_state'] for r in rows))
    open_rows = [r for r in rows if r['observation_state'] not in ('pass', 'retired')]
    by_implementation = defaultdict(list)
    for row in open_rows:
        by_implementation[row['implementation']].append(row['block'])
    sources[str(Path(__file__).resolve())] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    tier_counts = Counter(max(c['evidence'], key=['mapped', 'rtl_selection', 'analog_fixture'].index)
                          for r in rows for c in r['checklist'])
    report = dict(status='open' if open_rows else 'complete',
                  mapping_errors=mapping_errors, path_check=dict(report=str(paths_report), state=paths_state),
                  entry_evidence=dict(tier_counts),
                  declared_blocks=len(rows), observation_states=counts,
                  policy='Existing pass states are reported, not independently re-signed; candidate codes are not bindings.',
                  assembly_checklist_by_implementation=dict(by_implementation), blocks=rows,
                  shared_physical_cells=[dict(extraction=path, top=top, declared_blocks=sorted(set(names)),
                                             requirement='identify mode/channel-specific observation for each declared block')
                                         for (path, top), names in shared.items() if len(set(names)) > 1],
                  atb_catalog=controls['atb_nodes'], status_catalog=controls['obs_status'],
                  wired_status_catalog=controls['wire_status'],
                  missing_referenced_files=sorted(missing_files), source_hashes=sources)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2)+'\n')
    checklist_text = ['Per-block observation checklist (generated by verification/observation_coverage.py).',
                      'Evidence tiers: mapped < rtl_selection (assembled RTL to analog boundary/pads) < analog_fixture.',
                      'Ledger states are copied from tapeout-readiness.json and are not changed by this report.', '']
    for r in rows:
        checklist_text.append(f"[{r['observation_state']}] {r['block']}  islands={','.join(r['islands']) or '-'}")
        for c in r['checklist']:
            sel = f"code {c['atb_code']}" if c['atb_code'] else c['select']
            port = ','.join(c['port']) if isinstance(c['port'], list) else c['port']
            mode = ' mode '+','.join(f'{k}={v}' for k, v in c['mode'].items()) if c['mode'] else ''
            via = f" via {c['via']}" if c['via'] else ''
            checklist_text.append(f"   - {c['signal']} [{port or 'node'}] {c['path']}:{sel}{mode}{via} "
                                  f"islands={','.join(c['islands']) or '-'} -> {c['expected']}  <{c['evidence'][-1]}>")
        for item in r['remaining']:
            checklist_text.append(f'   TODO {item}')
        checklist_text.append('')
    (output.parent/'checklist.txt').write_text('\n'.join(checklist_text)+'\n')
    print(json.dumps(dict(status=report['status'], declared_blocks=len(rows), states=counts,
                         mapping_errors=len(mapping_errors), path_check=paths_state, entry_evidence=dict(tier_counts),
                         open_by_implementation={k: len(v) for k, v in by_implementation.items()},
                         missing_referenced_files=len(missing_files), report=str(output)), indent=2))
    if mapping_errors:
        raise SystemExit('Observation assignment errors:\n'+'\n'.join(mapping_errors))
    if require_complete and open_rows:
        raise SystemExit('Per-block observation closure is incomplete')


def remaining_items(checklist, gaps):
    items = []
    if gaps and gaps['indirect_only']:
        items.append('ports observed only through downstream blocks: '+', '.join(gaps['indirect_only']))
    for c in checklist:
        if 'rtl_selection' not in c['evidence'] and c['path'] not in ('host_data', 'pad'):
            items.append(f"{c['path']}:{c['select']}: no assembled RTL selection evidence ({c['rtl_note'] or 'not run'})")
        if c['path'] in ('host_data', 'pad'):
            items.append(f"{c['path']}:{c['select']}: bench/payload observation; needs an assembled payload simulation")
        elif 'analog_fixture' not in c['evidence']:
            items.append(f"{c['path']}:{c['select']}: bind the source net in the assembled analog hierarchy and simulate to the pad")
    return items


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'scratch/observation-coverage/report.json')
    parser.add_argument('--require-complete', action='store_true')
    parser.add_argument('--paths-report', type=Path, default=ROOT/'scratch/observation-paths/report.json')
    args = parser.parse_args()
    inventory(args.output.resolve(), args.require_complete, args.paths_report.resolve())
