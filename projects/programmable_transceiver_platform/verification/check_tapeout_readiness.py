"""Risk-accepted tapeout readiness: four tests per block, fallbacks and debug sites.

Validates spec/tapeout-readiness.json against the block inventory and provider
site inventory, then prints per-test counts. Exit status reflects consistency,
not readiness; use --require-ready to fail while any test is still open.
"""
import json
import sys
from pathlib import Path

SPEC = Path(__file__).resolve().parents[1] / 'spec'
ROOT = Path(__file__).resolve().parents[3]
TESTS = ('safe', 'clean', 'observable', 'fallback')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load():
    return (json.loads((SPEC / 'tapeout-readiness.json').read_text()),
            json.loads((SPEC / 'analog-architecture.json').read_text()),
            json.loads((SPEC / 'contract.json').read_text()))


def assess(readiness, architecture, contract):
    core, chain = readiness['core_blocks'], readiness['chain_blocks']
    external = readiness['external_blocks']
    blocks = set(architecture['blocks'])
    covered = [*core, *chain, *external]
    require(len(covered) == len(set(covered)), 'block assigned to more than one tier')
    require(set(covered) == blocks,
            f'tier coverage mismatch: missing {sorted(blocks - set(covered))}, '
            f'unknown {sorted(set(covered) - blocks)}')
    states = set(readiness['test_states'])
    routes = readiness['fallback_routes']
    for name, entry in {**core, **chain}.items():
        require(set(entry['tests']) == set(TESTS), f'{name}: test set')
        for test, result in entry['tests'].items():
            require(result['state'] in states, f'{name}.{test}: state {result["state"]}')
            if result['state'] in ('pass', 'fail'):
                require(result['evidence'], f'{name}.{test}: {result["state"]} without evidence')
            for path in result['evidence']:
                require((ROOT / path).exists(), f'{name}.{test}: missing evidence {path}')
        if entry.get('retired'):
            require(all(r['state'] == 'retired' for r in entry['tests'].values()), f'{name}: retired block with live tests')
            continue
        if name in core:
            require(entry['tests']['fallback']['state'] in ('open', 'waived_core'),
                    f'{name}: core fallback is waived by reuse, not passed')
    for name, entry in chain.items():
        if entry.get('retired'):
            continue
        require(entry['fallback_routes'], f'{name}: no fallback route')
        for route in entry['fallback_routes']:
            require(route in routes, f'{name}: unknown route {route}')

    debug_names = set()
    for route_id, route in routes.items():
        for pad in route['pads']:
            debug_names.add(pad)
    inventory = contract['assembly_policy']['provider_site_inventory']['ordered_sites_by_side']
    edge_of = {site: edge for edge, sites in inventory.items() for site in sites}
    functional = set(contract['assembly_policy']['candidate_signal_sites'].values())
    signal_sites = {s for s in edge_of
                    if not s.split('[')[0] in ('dvdd_pads', 'dvss_pads', 'vdd_pads', 'vss_pads')}
    spare = signal_sites - functional
    sites = readiness['debug_sites']
    assigned = [d['site'] for d in sites]
    require(len(assigned) == len(set(assigned)), 'debug site assigned twice')
    require(set(assigned) == spare,
            f'debug sites must use exactly the spare sites: unassigned {sorted(spare - set(assigned))}, '
            f'invalid {sorted(set(assigned) - spare)}')
    names = [d['name'] for d in sites]
    require(len(names) == len(set(names)), 'duplicate debug signal name')
    for d in sites:
        require(edge_of[d['site']] == d['edge'], f'{d["name"]}: edge {d["edge"]} != {edge_of[d["site"]]}')
    functional_names = set(contract['assembly_policy']['candidate_signal_sites'])
    for pad in debug_names:
        require(pad in names or pad in functional_names, f'route uses unknown pad {pad}')

    reserve = readiness['reserve_area_mm2']
    require(sum(reserve['allocated'].values()) <= reserve['available'] + 1e-9, 'reserve area overspent')

    counts = {t: {s: 0 for s in states} for t in TESTS}
    live = {n: e for n, e in {**core, **chain}.items() if not e.get('retired')}
    for entry in live.values():
        for test, result in entry['tests'].items():
            counts[test][result['state']] += 1
    gaps = sorted(r for r, v in routes.items() if v.get('gap'))
    return {
        'blocks': len(live),
        'retired': sorted(n for n, e in chain.items() if e.get('retired')),
        'core': len(core),
        'chain': len(chain),
        'counts': counts,
        'debug_sites': len(sites),
        'fallback_gaps': gaps,
        'freeze_stages': {s['id']: s['state'] for s in readiness['freeze_stages']},
        'ready': all(counts[t]['open'] == 0 and counts[t]['fail'] == 0 for t in TESTS),
    }


def main():
    result = assess(*load())
    print(json.dumps(result, indent=1))
    if '--require-ready' in sys.argv and not result['ready']:
        sys.exit(1)


if __name__ == '__main__':
    main()
