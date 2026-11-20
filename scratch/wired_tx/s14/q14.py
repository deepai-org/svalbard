"""Session-14 queue runner: python3 q14.py <jobfile>  (one simulation at a time; stop with file STOPQ next to this script).
Each line: {"kind":"cal"|"row", ...}.  "codes_from": "<cal tag>" takes next_codes ("codes") of cal/res/<tag>.json;
"codes_add": [8 ints] is added afterwards (injected offset for the negative control).  Done jobs (result file present) are skipped.
"""
import sys, json, subprocess, os
from pathlib import Path
H = Path(__file__).resolve().parent
os.environ['OMP_NUM_THREADS'] = '1'
log = open(sys.argv[1] + '.log', 'a')
for line in open(sys.argv[1]):
    if (H / 'STOPQ').exists():
        break
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    j = json.loads(line); kind = j.pop('kind')
    out = (H / 'cal' / 'res' if kind == 'cal' else H / 'chain' / 'results') / f'{j["tag"]}.json'
    if out.exists():
        continue
    if 'codes_from' in j:
        f = H / 'cal' / 'res' / f'{j.pop("codes_from")}.json'
        if not f.exists():
            log.write(f'{j["tag"]}: SKIP, {f.name} missing\n'); log.flush(); continue
        j['codes'] = json.loads(f.read_text())['codes']
    if 'codes_add' in j:
        j['codes'] = [min(15, max(0, a + b)) for a, b in zip(j['codes'], j.pop('codes_add'))]
    newm = sorted(x.name for x in Path('/home/ubuntu/svalbard/scratch/pads-core/txr/models').glob('*.spice') if x.name not in ('tx_rt.spice', 'tx_rh.spice', 'tx_zero.spice'))
    if newm:
        log.write(f'NOTICE before {j["tag"]}: new pad model files {newm} (option A?) - switch rows to it, S=1.0 and 0.6\n'); log.flush()
    script = H / 'cal' / 'blkcal.py' if kind == 'cal' else H / 'chain' / 'chain14.py'
    r = subprocess.run(['python3', str(script), json.dumps(j)], capture_output=True, text=True, cwd=script.parent)
    log.write((r.stdout.strip().split('\n')[-1] if r.stdout.strip() else 'ERR ' + r.stderr[-400:]).replace('\n', ' ')[:900] + '\n'); log.flush()
    if kind == 'row':       # waveforms and decks are not kept
        for d in (H / 'chain' / 'runs' / j['tag']).glob('*/*'):
            if d.name != 'tb.sp':
                d.unlink(missing_ok=True)
log.write('finished\n')
