"""r7f bench runner (one ngspice job per invocation; call through ../../slot.sh).
usage: run7f.py TAG NETLIST REGJSON key=value ...
  keys: mode=q|h|f  f=MHz  corner=tt|ss|ss35|ff|sf|fs|pess  rcs=0|1  psel=N  words=N  d_lat=ps  lde=ps  en_off=1 s_static=1
        neg=ckp2   (G3a: CKP2 displaced by +3T/8 at the capture input)  neg=s2stuck   klu=0 (default solver)
Writes res/TAG.json (functional result + hop summary + per-element rows); waveforms are not kept."""
import sys, json, re, os, shutil, time, subprocess
from pathlib import Path
H = Path(__file__).resolve().parent
W = '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_rx'
sys.path.insert(0, W); sys.path.insert(0, str(H / 'hop'))
import capture as c, wrx_flow as wf, sims, hop
CORN = dict(tt=('typical', 27, 3.3), ss=('ss', 32, 3.15), ss35=('ss', 32, 3.5), ff=('ff', 22, 3.35), sf=('sf', 27, 3.3),
            fs=('fs', 27, 3.3), pess=('ss', 32, 3.15))
BPC = dict(q=4, h=2, f=1)


def main():
    tag, net, regf = sys.argv[1:4]
    kv = dict(a.split('=') for a in sys.argv[4:])
    mode = kv.get('mode', 'q'); bpc = BPC[mode]; f = float(kv.get('f', 625)) * 1e6; T = 1 / f
    corner = kv.get('corner', 'tt'); cmod, temp, vdd = CORN[corner]
    if 'vdd' in kv:
        vdd = float(kv['vdd'])
    words = int(kv.get('words', {4: 12, 2: 12, 1: 9}[bpc]))
    bk = dict(f=f, words=words, corner=cmod, temp=temp, vdd=vdd, rcs=int(kv.get('rcs', 0)), psel=int(kv.get('psel', 0)))
    if 'd_lat' in kv: bk['d_lat'] = float(kv['d_lat']) * 1e-12
    elif bk['rcs']: bk['d_lat'] = 0.47e-9
    if 'lde' in kv: bk['lde_delay'] = float(kv['lde']) * 1e-12
    if kv.get('en_off') == '1': bk['en_off'] = True
    if kv.get('s_static') == '1': bk['s_static'] = True
    work = H / 'sim' / tag
    if work.exists(): shutil.rmtree(work)
    work.mkdir(parents=True)
    net = Path(net).resolve()
    if corner == 'pess':
        pn = net.parent / (net.stem + '.pess.spice')
        if not pn.exists() or pn.stat().st_mtime < net.stat().st_mtime:
            subprocess.run(['python3', '/home/ubuntu/svalbard/scratch/wired_rx/r7slicer/pess.py', str(net), str(pn)], check=True, capture_output=True)
        net = pn
    reg = json.loads(Path(regf).read_text())
    elems = hop.nodes(net, reg)
    probes = hop.probe_names(elems)
    body, ctl, an = c.bench(bpc, **bk)
    if kv.get('neg') == 'ckp2':      # G3a: ring phase 2 displaced by +3T/8 at the capture input
        m = re.search(r'^VCK2 ckp2 0 PULSE\(0 (\S+) (\S+) ', body, re.M)
        body = body.replace(m.group(0), m.group(0).replace(m.group(2), f'{float(m.group(2)) + 3 * T / 8:.6e}'))
    if kv.get('neg') == 's2stuck':
        body = re.sub(r'^VS2 s2 0 .*$', 'VS2 s2 0 0', body, flags=re.M)
    ctl = ctl.splitlines()
    wr = [l for l in ctl if l.startswith('wrdata')][0]
    outs = wr.split()[2:]
    save = 'save ' + ' '.join(outs + [f'v({p})' for p in probes]) + ' vdd#branch'
    ctl = [save] + ctl + [f'wrdata probe.fifo ' + ' '.join(f'v({p})' for p in probes)]
    opt = '.option klu' if kv.get('klu', '1') == '1' else ''
    (work / 'tb.cir').write_text('\n'.join([f'* r7f {tag} {kv}', sims.sim_header(cmod, temp), opt, f'.include /gen/{net.name}', body,
                                            '.control', *ctl, '.endc', '.end']) + '\n')
    cr = hop.Crossings(work / 'probe.fifo', probes, vdd / 2); cr.start()
    t1 = time.time()
    r = wf.docker(wf.ANALOG_IMAGE, work, '/foss/tools/bin/ngspice -b tb.cir > tb.cir.log 2>&1; echo rc=$?', timeout=6 * 3600,
                  extra_mounts=[(str(net.parent), '/gen')])
    el = time.time() - t1
    if cr.t.is_alive():   # ngspice never opened the fifo: unblock the reader
        try:
            fd = os.open(str(work / 'probe.fifo'), os.O_WRONLY | os.O_NONBLOCK); os.close(fd)
        except OSError:
            pass
    cross = cr.result(60)
    if 'dumpx' in kv:
        import gzip
        gzip.open(work / 'cross.json.gz', 'wt').write(json.dumps(cross))
    log = (work / 'tb.cir.log').read_text() if (work / 'tb.cir.log').exists() else ''
    try:
        res = an(log, work / 'out.txt')
    except Exception as exc:
        res = dict(error=repr(exc)[:300], log_tail=log[-600:])
    nw = {4: 5, 2: 10, 1: 20}[bpc]
    t0 = 2e-9; t_start = t0 + (2 * nw + 6) * T
    rows = hop.analyse(cross, elems, T, corner, t_start)
    hs = hop.summary(rows, T)
    min_bits = {4: 150, 2: 120, 1: 100}[bpc]
    if bk.get('en_off'):
        ok = bool(res.get('pass_'))
    else:
        ok = bool(res.get('pass_') and (res.get('bits') or 0) >= min_bits and res.get('bit_errors') == 0 and res.get('edge_errors') == 0)
    out = dict(tag=tag, netlist=str(net), kv=kv, bench={k: v for k, v in bk.items()}, elapsed_s=round(el), docker_rc=r.returncode,
               fifo_lines=cr.nlines, fifo_err=cr.err, functional=res, functional_pass=ok, hop=hs, hop_pass=hs['pass_'],
               pass_=bool(ok and hs['pass_']), rows=rows)
    (H / 'res').mkdir(exist_ok=True)
    (H / 'res' / f'{tag}.json').write_text(json.dumps(out, indent=1, default=str))
    print(tag, json.dumps(dict(func=ok, hop=hs['pass_'], el=round(el), bits=res.get('bits'), err=res.get('bit_errors'), eerr=res.get('edge_errors'),
                               pd=res.get('pd_ok'), gear=res.get('gear_ok'), i_mA=res.get('i_mA'), fail=hs['fail'], ws=hs['worst_setup'], wh=hs['worst_hold'],
                               error=res.get('error'))), flush=True)
    if 'keep' not in kv:
        for fn in ('out.txt', 'probe.fifo'):
            if (work / fn).exists(): (work / fn).unlink()


if __name__ == '__main__':
    main()
