"""One-nanosecond startup discriminator: each tolerance separately and together."""
import hashlib
import json
import subprocess
import time
from pathlib import Path

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

O = Path('/work')
cases = [(variant+'-'+circuit, Path('/'+circuit), option)
         for circuit in ('baseline','probed')
         for variant, option in [('default',''), ('reltol','option reltol=1e-5\n'),
                                 ('abstol','option abstol=1e-14\n'),
                                 ('vntol','option vntol=1e-8\n'),
                                 ('combined','option reltol=1e-5 abstol=1e-14 vntol=1e-8\n')]]
for case, root, settings in cases:
    target = O / case
    target.mkdir(exist_ok=False)
    prior = json.loads((root / 'result.json').read_text())
    assert prior['returncode'] == 0 and not prior['timed_out']
    assert prior['source_sha256_before'] == prior['source_sha256_after']
    before = {}
    for name, expected in prior['source_sha256_before'].items():
        p = Path('/origin/frames.spice') if name == '/baseline/frames.spice' else Path(name)
        assert sha(p) == expected, str(p)
        before[str(p)] = expected
    before[str(Path(__file__))] = sha(Path(__file__))
    base = (root / 'frames.spice').read_text()
    assert sha(root / 'frames.spice') == prior['artifacts_sha256']['.spice']
    assert base.count('tran 5p 209.9n 0 5p') == 1
    assert base.count('wrdata /work/frames.dat') == 1
    deck = base.replace('tran 5p 209.9n 0 5p', settings + 'tran 5p 1n 0 5p')
    deck = deck.replace('wrdata /work/frames.dat', f'wrdata /work/{case}/frames.dat')
    assert deck.replace('tran 5p 1n 0 5p', 'tran 5p 209.9n 0 5p').replace(settings, '').replace(f'wrdata /work/{case}/frames.dat', 'wrdata /work/frames.dat') == base
    p = target / 'frames.spice'
    p.write_text(deck)
    manifest = dict(case=case, parent_deck_sha256=sha(root/'frames.spice'),
                    deck_sha256_before=sha(p), source_sha256_before=before,
                    settings=settings.strip(), requested_horizon_ns=1,
                    comparison_limit_v=1e-5,
                    scope='Matched numerical diagnostic; tighter settings alone do not establish convergence.')
    (target/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    start = time.monotonic()
    with (target/'frames.log').open('w') as log:
        try:
            run = subprocess.run(['ngspice', '-b', str(p)], stdout=log, stderr=subprocess.STDOUT, timeout=120)
            code, timeout = run.returncode, False
        except subprocess.TimeoutExpired:
            code, timeout = None, True
    after = {name: sha(Path(name)) for name in before}
    assert after == before and sha(p) == manifest['deck_sha256_before']
    result = dict(returncode=code, timed_out=timeout, elapsed_s=time.monotonic()-start,
                  source_sha256_before=before, source_sha256_after=after,
                  artifacts_sha256={ext: sha(target/('frames'+ext)) for ext in ('.spice','.log','.dat') if (target/('frames'+ext)).exists()})
    (target/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(case, code, timeout, flush=True)
