"""Shared corner-report parser; retains historical rejection checks."""

def main(variant='commit'):
    if variant not in ('commit', 'prefix'):
        raise ValueError('Unknown corner-report variant')
    import pathlib, json, re, hashlib
    root = pathlib.Path(__file__).resolve().parents[3]
    p = root / 'projects/programmable_transceiver_platform'
    out = root / f'scratch/transceiver-block-rx-{variant}-corners'
    prior = json.loads((p / f'evidence/block-rx-{variant}-mapping.json').read_text())
    name = f'scratch/transceiver-block-rx-{variant}-mapping/mapped.v'
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == prior['sha256'][name]
    libraries = json.loads((out / 'libraries.json').read_text())
    cases = {}
    for corner in libraries:
        s = (out / (corner + '.log')).read_text()
        assert 'Error:' not in s and 'not found' not in s
        paths = {}
        for mode in (0, 1):
            for kind in ('max', 'min'):
                section = s.split(f'PATH_BEGIN {mode} {kind}\n')[1].split('PATH_END')[0]
                found = []
                for path in section.split('Startpoint:')[1:]:
                    found.append({'slack_ns': float(re.search('([-\\d.]+)\\s+slack', path)[1]), 'startpoint': path.splitlines()[0].strip(), 'endpoint': re.search('Endpoint: (.*)', path)[1]})
                paths[f'{mode}:{kind}'] = min(found, key=lambda x: x['slack_ns'])
        assert not s.split('ELECTRICAL_BEGIN')[1].split('ELECTRICAL_END')[0].strip()
        cases[corner] = paths
    assert cases['tt_025C_3v30']['1:max']['slack_ns'] == prior['paths']['1']['max']['slack_ns']
    assert cases['ss_125C_3v00']['1:max']['slack_ns'] < 0
    files = [p / 'verification' / f for f in (f'block_rx_{variant}_corners.py', f'run_block_rx_{variant}_corners.sh', f'report_block_rx_{variant}_corners.py', f'block_rx_{variant}_timing.tcl')] + list(out.glob('*.log'))
    if variant != 'commit':
        files.append(pathlib.Path(__file__).resolve())
    r = {'pass': (86 if variant == 'commit' else 84), 'status': 'available slow mixed-PVT setup screens fail', 'corners': cases, 'library_sha256': libraries, 'scope': 'Fixed nominal mapped netlist, ideal clocks/no wire RC. Mixed PVT stress screens do not define or bound the user-approved narrow operating window.', 'sha256': {str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
    (p / f'evidence/block-rx-{variant}-corners.json').write_text(json.dumps(r, indent=2) + '\n')
    print(json.dumps({c: {k: v['slack_ns'] for k, v in d.items()} for c, d in cases.items()}, indent=2))

if __name__ == '__main__':
    main()
