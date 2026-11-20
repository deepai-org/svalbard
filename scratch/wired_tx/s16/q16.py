"""Session-16 queue runner: python3 q16.py q16.jobs   (one simulation per runner; two runners may share the job file via claims/<tag>, owner allows TWO slots; stop with file STOPQ here: finishes the current job).
Each line {"kind":"cal"|"row", ...}; done jobs (result file present) are skipped; the job file is re-read after every job, so
lines may be appended / reordered while it runs.
  cal  "after": "<cal tag>"   run only if that cal exists and its residual is > 8 ps (second iteration, codes = its next codes).
  row  "codes_from": [cal tags]   the last existing cal of the list: residual <= 8 ps -> its codes_in (verified codes),
       else its next codes (label codes_verified=false).
Before every job: NOTICE in the log if a pad model file appears that is not in the known set (option A publication check)
or analog/pads has a new commit touching txpad.
"""
import sys, json, subprocess, os, time
from pathlib import Path
H = Path(__file__).resolve().parent
os.environ['OMP_NUM_THREADS'] = '1'
JOBS = Path(sys.argv[1]).resolve()
log = open(str(JOBS) + '.log', 'a')
KNOWN = {'tx_rt.spice', 'tx_rh.spice', 'tx_zero.spice'}
REPO = '/home/ubuntu/svalbard'
HEAD0 = subprocess.run(['git', '-C', REPO, 'log', '-1', '--format=%H', '--', 'projects/programmable_transceiver_platform/analog/pads'], capture_output=True, text=True).stdout.strip()


def W(s):
    log.write(time.strftime('%m-%d %H:%M ') + s + '\n'); log.flush()


def notice(tag):
    newm = sorted(x.name for x in Path('/home/ubuntu/svalbard/scratch/pads-core/txr/models').glob('*.spice') if x.name not in KNOWN)
    c = subprocess.run(['git', '-C', REPO, 'log', '--format=%h %s', f'{HEAD0}..HEAD', '--', 'projects/programmable_transceiver_platform/analog/pads'],
                       capture_output=True, text=True).stdout.strip()
    c = [l for l in c.split('\n') if l and 'txpad' in l.lower()]
    if newm or c:
        W(f'NOTICE before {tag}: new pad model files {newm} / pads commits {c[:3]} (option A?) - add rows with pad_file at S=1.0 and 0.6')


def cal(tag):
    f = H / 'cal' / 'res' / f'{tag}.json'
    return json.loads(f.read_text()) if f.exists() else None


done = set()
while True:
    if (H / 'STOPQ').exists():
        W('STOPQ'); break
    job = None
    for line in JOBS.read_text().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        j = json.loads(line)
        out = (H / 'cal' / 'res' if j['kind'] == 'cal' else H / 'results') / f'{j["tag"]}.json'
        if out.exists() or j['tag'] in done or (H / 'claims' / j['tag']).exists():
            continue
        if j['kind'] == 'cal' and 'after' in j:
            p = cal(j['after'])
            if p is None:
                continue                      # wait for it
            if p['residual_ok']:
                done.add(j['tag']); W(f'{j["tag"]}: not needed ({j["after"]} residual {p["worst_slot_ps"]} ps)'); continue
            j['codes'] = p['codes']
        if j['kind'] == 'row' and 'codes_from' in j:
            src = [c for c in (cal(t) for t in j['codes_from']) if c]
            if not src:
                continue
            c = src[-1]
            if len(src) < len(j['codes_from']) and not c['residual_ok']:
                continue                      # a second iteration is still due
            j['codes'] = c['codes_in'] if c['residual_ok'] else c['codes']
            j['codes_cal'] = c['tag']; j['codes_verified'] = bool(c['residual_ok']); j['cal_worst_ps'] = c['worst_slot_ps']
        (H / 'claims').mkdir(exist_ok=True)
        try:                                  # claim (several runners may share one job file)
            os.close(os.open(H / 'claims' / j['tag'], os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        except FileExistsError:
            continue
        job = j; break
    if job is None:
        W('finished (no runnable job)'); break
    tag = job['tag']; kind = job.pop('kind'); done.add(tag)
    for k in ('codes_from', 'after'):
        job.pop(k, None)
    labels = {k: job.pop(k) for k in ('codes_cal', 'codes_verified', 'cal_worst_ps', 'note') if k in job}
    notice(tag)
    W(f'start {tag} {kind}')
    script = H / ('cal16.py' if kind == 'cal' else 'chain16.py')
    t0 = time.time()
    r = subprocess.run(['python3', str(script), json.dumps(job)], capture_output=True, text=True, cwd=H)
    W(f'{int(time.time() - t0)} s ' + (r.stdout.strip().split('\n')[-1] if r.stdout.strip() else 'ERR ' + r.stderr[-600:]).replace('\n', ' ')[:900])
    res = H / 'results' / f'{tag}.json'
    if kind == 'row' and res.exists() and labels:
        o = json.loads(res.read_text()); o.update(labels); res.write_text(json.dumps(o, indent=1, default=str))
    for d in (H / 'runs' / tag).glob('*/*'):           # waveforms, decks, netlist copies are not kept
        d.unlink(missing_ok=True)
    for d in sorted((H / 'runs' / tag).glob('**/'), reverse=True):
        try:
            d.rmdir()
        except OSError:
            pass
