"""Bench for the revision-3 mux (mux9.py schematic + wiring-C stand-ins, or an extracted netlist via ext=):
ideal phases (ring-like swing, per-phase offsets, optional stop / stuck / mid-level), ideal streams or static stream
patterns, EXT data, idle; real extracted pad (pessimised) + COB bond + channel as in ../s12/mux/m8.py.

    python3 m9.py '{"tag":"a","corner":"ss","pess":true}'
"""
import sys, json, math, re
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 's12')); sys.path.insert(0, str(HERE.parent / 's12' / 'mux'))
import chain as CH
from chain import tools, S, B, C, B4
import m8 as M8
import mux9
RUNS = HERE / 'runs9'
CORN = dict(tt=dict(corner='typical', temp=27, vdd=3.3, swing=2.95, pess=False),
            ss=dict(corner='ss', temp=32, vdd=3.15, swing=2.69, pess=False),
            ssT=dict(corner='ss', temp=32, vdd=3.5, swing=3.02, pess=False),
            ff=dict(corner='ff', temp=22, vdd=3.35, swing=3.01, pess=False),
            sf=dict(corner='sf', temp=27, vdd=3.15, swing=2.75, pess=False),
            fs=dict(corner='fs', temp=27, vdd=3.15, swing=2.75, pess=False),
            ssp=dict(corner='ss', temp=32, vdd=3.15, swing=2.69, pess=True),
            sspT=dict(corner='ss', temp=32, vdd=3.5, swing=3.02, pess=True),
            ffhot=dict(corner='ff', temp=85, vdd=3.63, swing=3.27, pess=False),
            ffcold=dict(corner='ff', temp=0, vdd=3.63, swing=3.27, pess=False),
            sshot=dict(corner='ss', temp=85, vdd=2.97, swing=2.5, pess=True))


def run(tag, c='ssp', rate=3.125e9, nbits=160, offs=None, duty=0.5, res=None, pad=True, mbias=1.9, post_bias=0.0, bond='pess',
        par=None, ext=None, codes=None, enm=1, enp=None, pol=0, en_main=1, en_post=None, extm=0, ovp=0, ovn=0, dx_rate=None,
        stop_at=None, static=None, mid=None, kill=None, fpat=None, stuck=None, S_=1.0, probes=(), tstop=None, interlock=True,
        vdd_ramp=None, keep=False, ic_run=True, ring=None, mc_seed=None, cload=0.45e-12, dskew=0.0, tstep=5e-12, **_):
    """static: 8 chars '0' / '1' / 'm' (mid level) = phase levels after stop_at (or from t = 0 when stop_at == 0).
    fpat: list of (n_ring_cycles, 8-bit stream pattern as LINE bits b0..b7) segments instead of PRBS.
    idle: enm = 0 (ovp = ovn = 0: both gates high; ovp = ovn = 1: both legs conduct)."""
    cc = dict(CORN[c]); corner, temp, vdd, swing, pess = cc['corner'], cc['temp'], cc['vdd'], cc['swing'], cc['pess']
    res = res or {'ss': 'ss', 'ff': 'ff'}.get(corner, 'typical')
    offs = offs or [0] * 8
    work = RUNS / tag; work.mkdir(parents=True, exist_ok=True)
    ui = 1 / rate; tq = 8 * ui
    txt = M8.wire_c(mux9.netlist(par, interlock=interlock)) if not ext else B.clean(Path(ext).read_text()).replace('/', '__')
    if pess:
        txt = B4.pess_all(txt)
    (work / 'mux.spice').write_text(txt)
    L = ['* mux9 bench', CH.pad_header(corner, temp, res)] + ([f'.param sw_stat_mismatch=1', f'.option seed={int(mc_seed)}'] if mc_seed is not None else []) + ['.include mux.spice',
         f'VDD VDD 0 {vdd}' if not vdd_ramp else f'VDD VDD 0 PWL(0 0 {vdd_ramp} {vdd})', 'VSS VSS 0 0']
    tr = 60e-12; kk = 2.197 / tr; cdu = math.sin(math.pi * (duty - 0.5)); t00 = 1e-9
    if ring:
        # real phase source: extracted pt_pll_ring_core, open loop on the regulator's output voltage.
        # ring = dict(vring=, vctrl=, band=, pess=, ver='layout' | 'committed', route=(ohm, F))
        from chain import R
        rfile = R.RING if ring.get('ver', 'layout') == 'layout' else HERE / 'ringver' / 'ring_committed.ext.spice'
        keep_ring = R.RING; R.RING = rfile
        (work / 'ring.spice').write_text(R.ring_text(ring.get('pess', False))); R.RING = keep_ring
        rr, cr = ring.get('route', (30.0, 60e-15))
        L += ['.include ring.spice'] + R.ring_lines(ring['vring'], ring['vctrl'], ring.get('band', 0), out=[f'RG{k}' for k in range(8)])
        for k in range(8):
            L += [f'RRT{k} RG{k} PH{k} {rr}', f'CRTa{k} RG{k} 0 {cr / 2}', f'CRTb{k} PH{k} 0 {cr / 2}']
    for k in range(8):
        if ring:
            break
        t0_ = t00 + k * ui + offs[k] + math.asin(cdu) / (2 * math.pi) * tq
        osc = f'{swing}*(0.5+0.5*tanh({kk * tq / (2 * math.pi):.6e}*(sin(2*3.141592653589793*(time-{t0_:.6e})/{tq:.6e})+{cdu:.6f})))'
        if kill is not None and kill[0] == k:
            src = f'{swing * kill[1]}'
        elif stop_at is not None:
            lv = {'0': 0.0, '1': swing, 'm': mid if mid is not None else swing / 2}[static[k]]
            src = f'{lv}' if stop_at == 0 else f'({osc})*(0.5-0.5*tanh((time-{stop_at:.6e})/30p))+{lv}*(0.5+0.5*tanh((time-{stop_at:.6e})/30p))'
        else:
            src = osc
        L.append(f'BPH{k} PH{k}_s 0 V={src}'); L += [f'RPH{k} PH{k}_s PH{k} 150', f'CPH{k} PH{k} 0 60f']
    if fpat:
        bits = []
        for ncyc, pat in fpat:
            bits += list(pat) * ncyc
        nbits = len(bits)
    else:
        bits = S.prbs7_bits(nbits)
    for k in range(8):
        tv = [(0.0, 1)]                                   # F = NOT(bit); start with bit 0
        for n in range(k, nbits, 8):
            tv.append((t00 + (n - 3.5) * ui + dskew, 1 - bits[n]))
        if stuck is not None and k == stuck:
            tv = [(0.0, 0)]
        L.append(S.pwl_bits(f'F{k}', f'F{k}_s', tv, vdd)); L.append(f'RF{k} F{k}_s F{k} 1000')
    tstop = tstop or (t00 + (nbits + 4) * ui)
    dxbits = None
    if dx_rate:
        nd = int((tstop - 2e-9) * dx_rate); dxbits = S.prbs7_bits(nd)
        tv = [(0.0, 0)] + [(2e-9 + i / dx_rate, b) for i, b in enumerate(dxbits)]
        L.append(S.pwl_bits('DX', 'DX_s', tv, vdd)); L += ['RDX DX_s DXI 500', 'CDX DXI 0 50f']
        # block-level override drivers: OVP = !DX & EXT, OVN = DX & EXT (ideal gates here; the real ones are in the block top)
        L += [f'BOVN OVN_s 0 V={vdd}*(0.5+0.5*tanh((v(DXI)-{vdd / 2})*8))', f'BOVP OVP_s 0 V={vdd}*(0.5-0.5*tanh((v(DXI)-{vdd / 2})*8))',
              'ROVP OVP_s OVP 300', 'ROVN OVN_s OVN 300', 'COVP OVP 0 80f', 'COVN OVN 0 80f']
    else:
        L += [f'VOVP OVP 0 {vdd * ovp}', f'VOVN OVN 0 {vdd * ovn}']
    codes = codes or [0] * 8
    for k in range(8):
        for b in range(mux9.NTR):
            L.append(f'VTR{k}_{b} TR{k}_{b} 0 {vdd * (codes[k] >> b & 1)}')
    enp = (1 if post_bias else 0) if enp is None else enp
    en_post = (1 if post_bias else 0) if en_post is None else en_post
    L += [f'VENM ENM 0 {vdd * enm}', f'VENP ENP 0 {vdd * enp}', f'VPOL POL 0 {vdd * pol}', f'VEM EN_MAIN 0 {vdd * en_main}',
          f'VEQ EN_POST 0 {vdd * en_post}', f'VEXT EXT 0 {vdd * extm}', 'CAVP AVG_P 0 2p', 'CAVN AVG_N 0 2p', 'CRUN RUN 0 20f']
    L.append('XMUX ' + ' '.join(mux9.PORTS[:-6]) + ' MAIN_P MAIN_N POST_N POST_P VDD VSS wtx_mux8')
    pr = ['MAIN_P', 'MAIN_N', 'RUN', 'AVG_P', 'AVG_N', 'PH0'] + list(probes)
    if pad:
        padt = B.clean(B.PAD.read_text())
        if S_ != 1.0:
            padt = C.scale_pad(padt, S_)
        if pess:
            padt = B4.pess_all(padt)
        (work / 'pad.spice').write_text(padt + '\n')
        ch = CH.chain_lines('blk', vdd, 0, mbias, (1.0, 1e-15), CH.BOND[bond])
        ch = [l for l in ch if not re.match(r'^(CR1|CR2|RR|XPRE|VEN|VT0|VT1|VPP|VPN|VPB|\.include tr7)', l)] + [f'VPB PPOST_BIAS 0 {post_bias}']
        if vdd_ramp:
            ch = [re.sub(r'^(VCAS \S+ 0|VDP \S+ 0|VTE \S+ 0) .*', r'\1 PWL(0 0 %g %g)' % (vdd_ramp, vdd), l) for l in ch]
        L += ch
        pr += ['PAD_P', 'PAD_N', 'FAR_P', 'FAR_N']
    else:
        L += [f'CLP MAIN_P 0 {cload}', f'CLN MAIN_N 0 {cload}', f'CLPQ POST_P 0 {cload}', f'CLNQ POST_N 0 {cload}']
    if ic_run and interlock:      # skip the detector's start-up (about 60 ns at ss pessimistic)
        L += ['.ic ' + ' '.join(f'v(xmux.DN{j})={vdd} v(xmux.DA{j})={vdd}' for j in range(4))]
    vecs = ' '.join(f'v({x})' for x in pr) + ' i(VDD)'
    L += ['.options reltol=1e-3 method=gear rshunt=1e10', f'.tran {tstep} {tstop:.6e} 0 {tstep}', '.control', f'save {vecs}',
          'set wr_singlescale', 'run', f'wrdata wave.txt {vecs}', '.endc', '.end']
    (work / 'tb.sp').write_text('\n'.join(L) + '\n')
    _, log = tools.ngspice_host(work, 'tb.sp', timeout=14000)
    if not (work / 'wave.txt').exists():
        return dict(tag=tag, ok=False, reason=log[-600:])
    w = tools.read_wrdata(work / 'wave.txt', list(pr) + ['I']); t = w['time']
    out = dict(tag=tag, c=c, rate=rate, vdd=vdd, pess=pess, codes=codes, enm=enm, pol=pol, post_bias=post_bias, extm=extm, ovp=ovp, ovn=ovn,
               stop_at=stop_at, static=static, kill=kill, S=S_, ext=ext, interlock=interlock, ring=ring, mc_seed=mc_seed,
               gate_hi=round(float(np.percentile(w['MAIN_P'], 98)), 3), gate_lo=round(float(np.percentile(w['MAIN_P'], 2)), 3),
               i_ma=round(float(-np.mean(w['I'][t > 2e-9]) * 1e3), 2), run_end=round(float(w['RUN'][-1]), 2),
               i_end_ma=round(float(-np.mean(w['I'][t > t[-1] - 2e-9]) * 1e3), 3), i_max_ma=round(float(-w['I'].min() * 1e3), 2))
    if dx_rate:
        edges = 2e-9 + np.arange(0, len(dxbits) + 1) / dx_rate
        sc = lambda v: CH.score(t, v, edges, dxbits, nper=1)
    elif not fpat and stop_at is None:
        edges = t00 + 8 * ui * np.arange(-1, nbits // 8 + 2); edges = edges[(edges > 0) & (edges < tstop)]
        sc = lambda v: CH.score(t, v, edges, bits, nper=8)
    else:
        sc = None
    if sc:
        out['gate'] = sc(w['MAIN_P'] - w['MAIN_N'])
        if pad:
            out['far'] = sc(w['FAR_P'] - w['FAR_N'])
            fr = out['far']
            out['ok'] = bool(fr.get('errors', 1) == 0 and fr.get('eye_h_v', 0) >= CH.EYE_H and fr.get('eye_w_ui', 0) >= CH.EYE_W_UI and fr.get('bits', 0) >= 200)
    if pad:
        out['pad_cm_v'] = round(float(np.mean((w['PAD_P'] + w['PAD_N'])[t > t[-1] - 4e-9]) / 2), 4)
        out['pad_diff_end_v'] = round(float(np.mean((w['PAD_P'] - w['PAD_N'])[t > t[-1] - 4e-9])), 4)
    (work / 'result.json').write_text(json.dumps(out, indent=1, default=str))
    if not keep:
        pass
    return out, w


def summ(o):
    def s(x):
        return f"{x.get('errors')}e/{x.get('bits')} H{x.get('eye_h_v')} W{x.get('eye_w_ui')}UI dj{x.get('dj_pp_ps')}" if x and 'errors' in x else str(x)[:200]
    return (f"{o['tag']}: {'PASS' if o.get('ok') else ('FAIL' if 'ok' in o else '-')} gate {s(o.get('gate'))} [{o.get('gate_lo')}..{o.get('gate_hi')} V] far {s(o.get('far'))} "
            f"I {o.get('i_ma')} mA end {o.get('i_end_ma')} mA RUN {o.get('run_end')} cm {o.get('pad_cm_v')} {o.get('reason', '')}")


if __name__ == '__main__':
    r = run(**json.loads(sys.argv[1]))
    print(summ(r[0] if isinstance(r, tuple) else r), flush=True)
