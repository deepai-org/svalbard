"""Full-RC extraction (sak-pex -m 3) of each island switch and DC drop at design
current at the functional points. C-only extraction cannot see metal IR drop."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import design  # noqa: E402
import sim  # noqa: E402


def main():
    work = Path('/work')
    S = json.loads((work / 'schematic-result.json').read_text())
    workers = int(os.environ.get('WORKERS', os.cpu_count() or 2))
    sim.WORK = work / 'sims_rc'
    out = {'extraction': 'sak-pex.sh -m 3 -t 1 -r 1 -y 0 (full RC; 1 mOhm threshold/minres so sub-ohm grid segments are kept)', 'isw': {}}
    for isl, a in S['allocation'].items():
        cell = f'isw_{isl}'
        rd = work / 'pexrc' / cell
        rd.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(['sak-pex.sh', '-m', '3', '-t', '1', '-r', '1', '-y', '0', '-n', f'{cell}_rc', '-w', str(rd), str(work / 'layout' / f'{cell}.mag')],
                           capture_output=True, text=True)
        (rd / 'stage.log').write_text(r.stdout + r.stderr)
        net = rd / f'{cell}.pex.spice'
        if not net.exists():
            out['isw'][isl] = {'error': 'full-RC extraction failed', 'rc': r.returncode}
            continue
        txt = net.read_text()
        sim.OVERRIDE.clear()
        sim.OVERRIDE['isw'] = sim.load_pex(net, 'isw', ['VDD', 'VSS', 'VISL', 'EN', 'ISO', 'PG'])
        nf = S['sizes'][isl]['fingers']
        jobs = [sim.isw_drop_job(isl, nf, c, t, v, a['design_current_ma']) for c, t, v in sim.F_POINTS]
        res = sim.run_all(jobs, workers)
        drops = {k: v.get('drop') for k, v in res.items()}
        good = [x for x in drops.values() if x is not None]
        out['isw'][isl] = {'pex_sha256': hashlib.sha256(txt.encode()).hexdigest(),
                           'resistors': sum(1 for ln in txt.splitlines() if ln.startswith('R')),
                           'cases': len(drops), 'converged': len(good),
                           'drop_max_v': max(good) if good else None,
                           'drop_tt_27_3v3_v': drops.get(f'drop_{isl}_tt_27_3.3'),
                           'pass': len(good) == len(drops) and max(good) <= design.DROP_TARGET_V + 1e-6}
    (work / 'rc-result.json').write_text(json.dumps(out, indent=1))
    print('wrote /work/rc-result.json')


if __name__ == '__main__':
    main()
