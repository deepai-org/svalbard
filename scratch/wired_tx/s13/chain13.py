"""Session 13 real-chain bench for the block top pt_wiredtx8 (analog/wired_tx/wtx8_top.py).

  source : extracted pt_pll_ring_core, open loop on the regulator's output voltage, 30 ohm / 60 fF per phase route.
           ring_ver = 'layout' (as laid out 11 Nov) or 'committed' (XC0b gate moved, ringver/cmp.py); every result
           records it (ring=layout-11Nov / ring=committed-estimate).
  DUT    : pt_wiredtx8 = wtx_ser8d (extracted) + wtx_mux8 (schematic + wiring-C stand-ins, or extracted via mux_ext)
           + wtx8_aux (schematic or aux_ext).  The pad tail bias comes from the block's own DAC (main_code), the
           bias reference is an ideal 10 uA.
  load   : extracted published TX pad -> COB bond (2.82 nH pessimistic, 0.23 ohm) -> connector -> 50 mm line ->
           100 nF -> 50 ohm (as ../s12/chain.py).
Pass: ../s13/LIMITS.md (far end 0 errors / >= 200 scored bits, eye >= 0.200 V, >= 0.45 UI; oversampled rates on the line bit).

    python3 chain13.py '{"tag":"a","corner":"ss","vdd":3.15,"vring":2.69,"rate":3.125e9}'
"""
import sys, json, re, os
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 's12')); sys.path.insert(0, str(HERE.parent / 's12' / 'mux'))
import chain as CH
from chain import tools, S, I, B, C, B4, R
import m8 as M8
import cml_ser
import wtx_mux8, wtx8_top
RUNS = HERE / 'runsC'
FAST = tools.GENERATED / 'fast'
TUNE = HERE.parent / 's12' / 'tune.json'
RINGFILE = dict(layout=R.RING, committed=HERE / 'ringver' / 'ring_committed.ext.spice')
RINGLABEL = dict(layout='layout-11Nov', committed='committed-estimate')


def ring_text(ver, pess):
    keep = R.RING; R.RING = RINGFILE[ver]
    try:
        return R.ring_text(pess)
    finally:
        R.RING = keep


def tune(corner, temp, vring, band, f, pess):
    key = f'{corner}_{temp}_{vring}_{band}_{f / 1e6:.1f}_{int(pess)}'
    d = json.loads(TUNE.read_text())
    if key not in d:
        CH.tune(corner, temp, vring, band, f, pess=pess)
        d = json.loads(TUNE.read_text())
    return d[key]


def deck(work, *, corner, temp, vdd, res, pess, ring, words, word_t0, tstop, rate, full, codes, main_code, post_code, en_post, pol,
         idle, idle_mode, ext, dx_bits, dx_rate, tap, mux_ext, aux_ext, ser_ext, bond, kill, S_, probes, launch, supply, par):
    tw = 40 / rate
    L = ['* pt_wiredtx8 real chain', CH.pad_header(corner, temp, res), '.include ring.spice', '.include ser.spice', '.include mux.spice',
         '.include aux.spice', '.include top.spice']
    (work / 'ring.spice').write_text(ring_text(ring['ver'], ring['pess']))
    S.PESSIMISTIC = pess
    (work / 'ser.spice').write_text(cml_ser.add_gate_r(S.dut_text(Path(ser_ext))).replace('/', '__').replace('.', '__') if False else
                                    cml_ser.add_gate_r(S.dut_text(Path(ser_ext))).replace('/', '__'))
    mtxt = M8.wire_c(wtx_mux8.netlist(par)) if not mux_ext else B.clean(Path(mux_ext).read_text()).replace('/', '__')
    atxt = wtx8_top.aux_text() if not aux_ext else B.clean(Path(aux_ext).read_text()).replace('/', '__')
    if pess:
        mtxt, atxt = B4.pess_all(mtxt), B4.pess_all(atxt)
    (work / 'mux.spice').write_text(mtxt); (work / 'aux.spice').write_text(atxt); (work / 'top.spice').write_text(wtx8_top.top())
    # supply: ideal, or through a bond + on-chip decap (supply = dict(l=, r=, c=, ripple=(vpp, f)))
    if supply:
        rip = supply.get('ripple')
        src = f'{vdd}' if not rip else f'DC {vdd} SIN({vdd} {rip[0] / 2} {rip[1]})'
        L += [f'VDDX VDDX 0 {src}', f'LVD VDDX VDDm {supply.get("l", 2.82e-9)}', f'RVD VDDm VDD {supply.get("r", 0.23)}',
              f'LVS 0 VSSm {supply.get("l", 2.82e-9)}', f'RVS VSSm VSS {supply.get("r", 0.23)}',
              f'CDEC VDD VSSd {supply.get("c", 200e-12)}', f'RDEC VSSd VSS {supply.get("esr", 1.0)}']
    else:
        L += [f'VDD VDD 0 {vdd}', 'VSS VSS 0 0']
    L += R.ring_lines(ring['vring'], ring['vctrl'], ring['band'], out=[f'RG{k}' for k in range(8)])
    rr, cr = ring.get('route', (30.0, 60e-15))
    for k in range(8):
        src = f'RG{k}'
        if kill is not None and k == kill:
            L += [f'RKILL{k} RG{k} 0 1k']; src = '0'
        L += [f'RRT{k} {src} PH{k} {rr}', f'CRTa{k} RG{k} VSS {cr / 2}', f'CRTb{k} PH{k} VSS {cr / 2}']
    L.append(S.pwl_bits('SER', 'SER_drv', [(0.0, 0), (2e-9, 1)], vdd)); L.append('RSER SER_drv SER_EN 1000')
    for i in range(40):
        tv = [(0.0, words[0][i])] + [(word_t0 + k * tw + launch * tw, w[i]) for k, w in enumerate(words)]
        L.append(S.pwl_bits(f'D{i}', f'D{i}_drv', tv, vdd)); L.append(f'RD{i} D{i}_drv D{i} 1000')
    st = dict(IDLE=idle, IDLE_MODE=idle_mode, WTX_EXT=ext, POST_POL=pol, EN_MAIN=1, EN_POST=en_post, ISLAND_OFF=0, TAP_EN=tap)
    for n, v in st.items():
        if isinstance(v, (list, tuple)):          # [(time, level), ...]
            L.append(S.pwl_bits(n, n + '_drv', [(0.0, v[0][1])] + list(v[1:]), vdd)); L.append(f'R{n} {n}_drv {n} 1000')
        else:
            L.append(f'V{n} {n} 0 {vdd * v}')
    if dx_bits is not None:
        L.append(S.pwl_bits('DX', 'DX_drv', [(0.0, 0)] + [(2e-9 + i / dx_rate, b) for i, b in enumerate(dx_bits)], vdd)); L.append('RDX DX_drv DX 500')
    else:
        L.append('VDX DX 0 0')
    for i in range(8):
        L += [f'VMC{i} MAIN_CODE{i} 0 {vdd * (main_code >> i & 1)}', f'VPC{i} POST_CODE{i} 0 {vdd * (post_code >> i & 1)}']
    for k in range(8):
        for b in range(wtx_mux8.NTR):
            L.append(f'VTR{k}_{b} TR{k}_{b} 0 {vdd * (codes[k] >> b & 1)}')
    L += ['IB VDD IBIAS 10u', 'CWCK WORD_CLK40 VSS 30f', 'CTP TAP_P VSS 25f', 'CTN TAP_N VSS 25f', 'CRUN TX_RUN VSS 20f', 'CAVP ATB_AVGP VSS 2p',
          'CAVN ATB_AVGN VSS 2p', 'RATN ATB_NBIAS ATBNX 1meg', 'CATN ATBNX VSS 1p', 'RATP ATB_PBIAS ATBPX 1meg', 'CATP ATBPX VSS 1p', 'CXD WTX_EXT_DATA VSS 20f']
    if full:
        L.append('XTOP ' + ' '.join(wtx8_top.PORTS) + ' pt_wiredtx8')
        padt = B.clean(B.PAD.read_text())
        if S_ != 1.0:
            padt = C.scale_pad(padt, S_)
        if pess:
            padt = B4.pess_all(padt)
        (work / 'pad.spice').write_text(padt + '\n')
        L += ['.include pad.spice', f'VCAS CAS_SRC 0 {vdd}', 'RCAS CAS_SRC CASCODE 50', 'VTB PTMDS_BIAS 0 0', 'VTP TMDS_P 0 0', 'VTN TMDS_N 0 0',
              'VDE2 DETECT_ENABLE 0 0', f'VDP DETECT_PBIAS 0 {vdd}', f'VTE TERM_ENABLE 0 {vdd}', 'VTV TERM_VCM 0 1.65',
              'XPAD PAD_P PAD_N VDD VSS CASCODE MAIN_P MAIN_N MAIN_BIAS POST_P POST_N POST_BIAS TMDS_P TMDS_N PTMDS_BIAS '
              'DETECT_ENABLE DETECT_PBIAS TERM_ENABLE TERM_VCM ATBPAD tx_protected_pad', 'RATB ATBPAD 0 1meg']
        pk = []
        I.pkg_chain(pk, 'P4', 0.0)
        for i, l in enumerate(pk):
            if l.startswith('LBW'):
                p = l.split(); pk[i] = f'{p[0]} {p[1]} {p[2]} {CH.BOND[bond]:.4g}'
            if l.startswith('RBW'):
                p = l.split(); pk[i] = f'{p[0]} {p[1]} {p[2]} 0.23'
        L += pk
        names = ['PH0', 'WORD_CLK40', 'MAIN_P', 'MAIN_N', 'PAD_P', 'PAD_N', 'FAR_P', 'FAR_N', 'TX_RUN', 'TAP_P', 'TAP_N', 'MAIN_BIAS'] + list(probes)
    else:       # word-clock phase pass: ring + stream macro only
        L.append('XSER ' + ' '.join(f'D{i}' for i in range(40)) + ' ' + ' '.join(f'PH{k}' for k in range(8)) + ' SER_EN '
                 + ' '.join(f'F{k}' for k in range(8)) + ' WORD_CLK40 VDD VSS wtx_ser8d')
        names = ['PH0', 'WORD_CLK40']
    isup = 'i(VDD)' if not supply else 'i(VDDX)'
    vecs = ' '.join(f'v({n})' for n in names) + ' ' + isup
    L += ['.options reltol=1e-3 method=gear interp rshunt=1e10', f'.tran 1.0e-11 {tstop:.6e} 0 4e-12', '.control', f'save {vecs}',
          'set wr_singlescale', 'run', f'wrdata wave.txt {vecs}', '.endc', '.end']
    (work / 'tb.sp').write_text('\n'.join(L) + '\n')
    return names + ['I']


def run(tag, rate=3.125e9, corner='ss', temp=32, vdd=3.15, vring=2.69, pess=False, ring_pess=None, ring_ver='layout', res=None, n_over=1,
        nwords=None, codes=None, main_code=160, post_code=0, en_post=0, pol=0, idle=0, idle_mode=0, ext=0, dx_rate=None, tap=0,
        mux_ext=None, aux_ext=None, ser_ext=None, bond='pess', kill=None, S_=1.0, probes=(), launch=0.25, supply=None, par=None,
        band=None, vctrl=None, stuck=None, keep=False, **_):
    ring_pess = pess if ring_pess is None else ring_pess
    res = res or {'ss': 'ss', 'ff': 'ff'}.get(corner, 'typical')
    f = rate / 8
    band = (1 if f > 480e6 else 0) if band is None else band
    if vctrl is None:
        tn = tune(corner, temp, vring, band, f, ring_pess); vctrl = tn['vctrl']
        if abs(tn['f_hz'] - f) / f > 0.02:
            return dict(tag=tag, ok=False, reason=f'ring cannot reach {f / 1e6:.1f} MHz (got {tn["f_hz"] / 1e6:.1f})')
        f = tn['f_hz']
    rate = 8 * f; tw = 40 / rate
    ser_ext = ser_ext or str(FAST / 'wtx_ser8d.ext.spice')
    codes = codes or [0] * 8
    ring = dict(ver=ring_ver, pess=ring_pess, vring=vring, vctrl=vctrl, band=band)
    tools.ngspice = lambda w, d, timeout=7200, mounts=(): tools.ngspice_host(w, d, timeout=40000)
    nline = 40 // n_over
    t_lead = 5 if not mux_ext else 5      # word periods before scoring (run detector start-up about 60 ns at ss pessimistic)
    nw = nwords or (t_lead + (200 * n_over + 39) // 40 + 4)
    ub = S.prbs7_bits(nline * nw)
    if stuck is not None:
        pass
    words = [[ub[nline * k + i // n_over] for i in range(40)] for k in range(nw)]
    common = dict(corner=corner, temp=temp, vdd=vdd, res=res, pess=pess, ring=ring, rate=rate, codes=codes, main_code=main_code, post_code=post_code,
                  en_post=en_post, pol=pol, idle=idle, idle_mode=idle_mode, ext=ext, dx_bits=None, dx_rate=dx_rate, tap=tap, mux_ext=mux_ext,
                  aux_ext=aux_ext, ser_ext=ser_ext, bond=bond, kill=kill, S_=S_, probes=probes, launch=launch, supply=supply, par=par)
    out = dict(tag=tag, target_rate=rate, n_over=n_over, corner=corner, temp=temp, vdd=vdd, vring=vring, vctrl=vctrl, band=band, pess=pess,
               ring_pess=ring_pess, ring='ring=' + RINGLABEL[ring_ver], res=res, codes=codes, main_code=main_code, post_code=post_code, en_post=en_post,
               pol=pol, mux_ext=mux_ext, aux_ext=aux_ext, ser_ext=ser_ext, kill=kill, S=S_, supply=supply, frot=wtx8_top.FROT,
               limits=dict(eye_h_v=CH.EYE_H, eye_w_ui=CH.EYE_W_UI, min_bits=CH.MIN_BITS))
    # pass 1: when does the word clock rise?
    w1 = RUNS / tag / 'phase'; w1.mkdir(parents=True, exist_ok=True)
    n1 = deck(w1, words=[[0] * 40], word_t0=1.0, tstop=2e-9 + 3 * tw, full=False, **common)
    tools.ngspice(w1, 'tb.sp')
    if not (w1 / 'wave.txt').exists():
        out.update(ok=False, reason='no waveform (phase pass)'); return _save(out)
    a = tools.read_wrdata(w1 / 'wave.txt', n1)
    ri = S.crossings(a['time'], a['WORD_CLK40'], th=vdd / 2, rising=True); ri = ri[ri > 2e-9]
    if len(ri) < 2:
        out.update(ok=False, reason='WORD_CLK40 not running'); return _save(out)
    t0w = float(ri[-1]) - (len(ri) - 1) * tw
    w2 = RUNS / tag / 'data'; w2.mkdir(parents=True, exist_ok=True)
    names = deck(w2, words=words, word_t0=t0w, tstop=t0w + (nw + 2) * tw, full=True, **common)
    tools.ngspice(w2, 'tb.sp')
    if not (w2 / 'wave.txt').exists():
        out.update(ok=False, reason='no waveform (data pass)'); return _save(out)
    w = tools.read_wrdata(w2 / 'wave.txt', names); t = w['time']
    up = S.crossings(t, w['TX_RUN'], th=vdd / 2, rising=True)
    out['t_run_ns'] = round(float(up[0]) * 1e9, 1) if len(up) else None
    ed = CH.wck_grid(t, w['WORD_CLK40'], vdd / 2, (float(up[0]) if len(up) else 3e-9) + 2 * tw)
    out['i_avg_ma'] = round(float(-np.mean(w['I'][t > ed[0]]) * 1e3), 2) if len(ed) else None
    out['main_bias_v'] = round(float(np.mean(w['MAIN_BIAS'][t > t[-1] - 10e-9])), 3)
    if len(ed) >= 6:
        for nm, a_, b_ in (('far', 'FAR_P', 'FAR_N'), ('pad', 'PAD_P', 'PAD_N'), ('gate', 'MAIN_P', 'MAIN_N')):
            out[nm] = CH.score(t, w[a_] - w[b_], ed, ub, nper=nline)
        fr = out['far']
        out['ok'] = bool(fr.get('errors', 1) == 0 and fr.get('bits', 0) >= CH.MIN_BITS and fr.get('eye_h_v', 0) >= CH.EYE_H and fr.get('eye_w_ui', 0) >= CH.EYE_W_UI)
        if tap:
            out['tap'] = CH.score(t, w['TAP_P'] - w['TAP_N'], ed, ub, nper=nline)
            out['tap_levels'] = [round(float(np.percentile(w['TAP_P'][t > ed[0]], q)), 2) for q in (1, 99)]
    else:
        out.update(ok=False, reason='word clock grid too short / RUN never rose')
    if not keep:
        (w1 / 'wave.txt').unlink(missing_ok=True)
        for f_ in ('ring.spice', 'ser.spice', 'pad.spice'):
            (w1 / f_).unlink(missing_ok=True)
    return _save(out)


def _save(out):
    (HERE / 'resultsC').mkdir(exist_ok=True)
    (HERE / 'resultsC' / f'{out["tag"]}.json').write_text(json.dumps(out, indent=1, default=str))
    return out


def summ(o):
    def s(x):
        return f"{x.get('errors')}e/{x.get('bits')} H{x.get('eye_h_v')} W{x.get('eye_w_ui')}UI dj{x.get('dj_pp_ps')}" if x and 'errors' in x else str(x)[:80]
    return (f"{o['tag']}: {'PASS' if o.get('ok') else 'FAIL'} | {o.get('ring')} | gate {s(o.get('gate'))} | far {s(o.get('far'))} | "
            f"I {o.get('i_avg_ma')} mA run@{o.get('t_run_ns')} ns bias {o.get('main_bias_v')} | {o.get('reason') or ''}")


if __name__ == '__main__':
    print(summ(run(**json.loads(sys.argv[1]))), flush=True)
