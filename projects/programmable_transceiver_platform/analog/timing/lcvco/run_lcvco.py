#!/usr/bin/env python3
"""P3-4 evaluation benches for the autonomous-RF LO (schematic-level VCO with
the analytical spiral model; extracted prescale and lo_ext netlists).
Raw decks/logs: scratch/timing/lcvco/sim.  Results: lcvco/results.json."""
import json, math, re, shutil, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import timing_flow as tf

WORK = tf.SCRATCH / 'lcvco' / 'sim'
V = 3.3

def stage():
    WORK.mkdir(parents=True, exist_ok=True)
    for f in ('lcvco.spice', 'spiral.spice'):
        shutil.copy(HERE / f, WORK / f)
    shutil.copy(tf.HERE / 'timing_cells.spice', WORK / 'timing_cells.spice')
    pp = (tf.HERE / 'polyphase.spice').read_text()
    pp = re.sub(r'^\.include.*$', '', pp, flags=re.M)
    pp = pp[:pp.index('.subckt pt_pp_lim')]           # passive network only, no limiters
    (WORK / 'pp_passive.spice').write_text(pp)
    for b in ('prescale', 'lo_ext'):
        shutil.copy(tf.SCRATCH / b / 'sim' / f'{b}.ext.spice', WORK / f'{b}.ext.spice')

def hdr(corner, temp):
    c = {'tt': 'typical', 'ss': 'ss', 'ff': 'ff'}[corner]
    return tf.header(corner, temp) + (f'.lib {tf.MODELS}/sm141064.ngspice mimcap_{c}\n'
                                      f'.lib {tf.MODELS}/sm141064.ngspice moscap_{c}\n')

def vco_core(v, vtune):
    return f"""VDD vdd 0 {v}
VDDB vddb 0 {v}
VEN en 0 {v}
VT vt 0 {vtune}
IB vdd ibias 10u
.include timing_cells.spice
.include lcvco.spice
X1 en vt ibias tp tn outp outn pre vdd vddb 0 pt_lcvco
"""

def kick():
    # small start-up kick (differential current pulse) so the simulation
    # does not wait for noise
    return 'IK tp tn pulse(0 200u 0.2n 50p 50p 0.3n 1)\n'

def tb_tune(v=V, vtune=1.65, T=40e-9):
    body = vco_core(v, vtune) + kick() + f"""CLP outp 0 50f
CLN outn 0 50f
CLR pre 0 30f
.tran 1p {T}
.measure tran per trig v(tp,tn) val=0 td={T - 10e-9} rise=1 targ v(tp,tn) val=0 td={T - 10e-9} rise=11
.measure tran tpmax max v(tp) from={T - 10e-9} to={T}
.measure tran tpmin min v(tp) from={T - 10e-9} to={T}
.measure tran tnmax max v(tn) from={T - 10e-9} to={T}
.measure tran tnmin min v(tn) from={T - 10e-9} to={T}
.measure tran icore avg i(VDD) from={T - 10e-9} to={T}
.measure tran ibuf avg i(VDDB) from={T - 10e-9} to={T}
.measure tran omax max v(outp) from={T - 10e-9} to={T}
.measure tran omin min v(outp) from={T - 10e-9} to={T}
"""
    def an(m):
        f = 10 / m['per'] if 'per' in m else None
        return dict(vtune_v=vtune, f_hz=f, tank_p_v=[m.get('tpmin'), m.get('tpmax')], tank_n_v=[m.get('tnmin'), m.get('tnmax')],
                    tank_diff_vpp=((m['tpmax'] - m['tpmin']) * 2 if 'tpmax' in m else None),
                    buf_out_v=[m.get('omin'), m.get('omax')], i_core_ma=-m.get('icore', math.nan) * 1e3,
                    i_buf_ma=-m.get('ibuf', math.nan) * 1e3, oscillates=bool(f))
    return body, an

def tb_chain(v=V, vtune=1.65, T=30e-9):
    """VCO -> buffers -> 2-stage passive RC polyphase -> 2 pF coupling -> lo_ext
    EXT inputs (external-LO passive switch path, EXT=1) with the mixer loads of
    tb_lo_ext; outputs at the mixer gate nodes LO_*."""
    loads = ''
    for n in ('ip', 'in', 'qp', 'qn'):
        loads += (f'XRX{n} rxd lo{n} rxs 0 nfet_03v3 w=5u l=0.28u m=12\n'
                  f'XTX{n} txd lo{n} txs 0 nfet_03v3 w=10u l=0.28u m=4\nCW{n} lo{n} 0 22f\n')
    body = vco_core(v, vtune) + kick() + f""".include pp_passive.spice
.include lo_ext.ext.spice
VPP vpp 0 {v}
XS1 outp outp outn outn n0 n1 n2 n3 0 pt_pp_stage
XS2 n0 n1 n2 n3 m0 m1 m2 m3 0 pt_pp_stage2
* polyphase out (0, 90, 180, 270 deg) -> coupling (MIM 2 pF) -> EXT pads (I = 0/180, Q = 90/270)
XCI1 m0 padip cap_mim_2f0_m4m5_noshield c_width=31.6u c_length=31.6u
XCI2 m2 padin cap_mim_2f0_m4m5_noshield c_width=31.6u c_length=31.6u
XCQ1 m1 padqp cap_mim_2f0_m4m5_noshield c_width=31.6u c_length=31.6u
XCQ2 m3 padqn cap_mim_2f0_m4m5_noshield c_width=31.6u c_length=31.6u
CWI padip 0 100f
CWN padin 0 100f
CWQ padqp 0 100f
CWR padqn 0 100f
VLIIP loiip 0 0
VLIIN loiin 0 0
VLIQP loiqp 0 0
VLIQN loiqn 0 0
VRXD rxd 0 1.65
VRXS rxs 0 1.65
VTXD txd 0 2.5
VTXS txs 0 1.0
VEXT ext 0 {v}
VINT int 0 0
{loads}XLO padip padin padqp padqn loiip loiin loiqp loiqn ext int loip loin loqp loqn vb vpp 0 pt_lo_ext
.tran 1p {T}
.measure tran per trig v(loip) val=2.45 td={T - 6e-9} rise=1 targ v(loip) val=2.45 td={T - 6e-9} rise=5
.measure tran lomax max v(loip) from={T - 6e-9} to={T}
.measure tran lomin min v(loip) from={T - 6e-9} to={T}
.measure tran qmax max v(loqp) from={T - 6e-9} to={T}
.measure tran qmin min v(loqp) from={T - 6e-9} to={T}
.measure tran inmax max v(loin) from={T - 6e-9} to={T}
.measure tran inmin min v(loin) from={T - 6e-9} to={T}
.measure tran tiq trig v(loip) val=2.45 td={T - 6e-9} rise=1 targ v(loqp) val=2.45 td={T - 6e-9} rise=1
.measure tran pmax max v(padip) from={T - 6e-9} to={T}
.measure tran pmin min v(padip) from={T - 6e-9} to={T}
.measure tran m0max max v(m0) from={T - 6e-9} to={T}
.measure tran m0min min v(m0) from={T - 6e-9} to={T}
.measure tran m1max max v(m1) from={T - 6e-9} to={T}
.measure tran m1min min v(m1) from={T - 6e-9} to={T}
.measure tran icore avg i(VDD) from={T - 6e-9} to={T}
.measure tran ibuf avg i(VDDB) from={T - 6e-9} to={T}
.measure tran ilo avg i(VPP) from={T - 6e-9} to={T}
"""
    def an(m):
        f = 4 / m['per'] if 'per' in m else None
        ph = ((m['tiq'] * f * 360 + 180) % 360 - 180) if f and 'tiq' in m else None
        r = dict(vtune_v=vtune, f_hz=f, lo_i_v=[m.get('lomin'), m.get('lomax')], lo_q_v=[m.get('qmin'), m.get('qmax')],
                 lo_in_v=[m.get('inmin'), m.get('inmax')],
                 rx_switch_vgs_on_v=(m['lomax'] - 1.65) if 'lomax' in m else None,
                 rx_switch_vgs_off_v=(m['lomin'] - 1.65) if 'lomin' in m else None,
                 q_minus_i_deg=ph, pad_i_vpp=(m['pmax'] - m['pmin']) if 'pmax' in m else None,
                 polyphase_out_vpp=dict(I=(m['m0max'] - m['m0min']) if 'm0max' in m else None,
                                        Q=(m['m1max'] - m['m1min']) if 'm1max' in m else None),
                 i_core_ma=-m.get('icore', math.nan) * 1e3, i_buf_ma=-m.get('ibuf', math.nan) * 1e3,
                 i_lo_ext_ma=-m.get('ilo', math.nan) * 1e3)
        r['adequate'] = bool(r['rx_switch_vgs_on_v'] is not None and r['rx_switch_vgs_on_v'] >= 0.9
                             and r['rx_switch_vgs_off_v'] <= 0.5 and ph is not None and 80 < abs(ph) < 100)
        return r
    return body, an

def tb_prescale(v=V, vtune=1.65, T=40e-9):
    body = vco_core(v, vtune) + kick() + f""".include prescale.ext.spice
CLP outp 0 50f
CLN outn 0 50f
VPEN pen 0 {v}
VD2 d2 0 0
VD4 d4 0 0
VD8 d8 0 0
VD16 d16 0 {v}
XPS pre pen d2 d4 d8 d16 ckout vdd 0 pt_prescale
CLO ckout 0 30f
.tran 1p {T}
.measure tran per trig v(tp,tn) val=0 td={T - 14e-9} rise=1 targ v(tp,tn) val=0 td={T - 14e-9} rise=17
.measure tran pero trig v(ckout) val={v / 2} td={T - 14e-9} rise=1 targ v(ckout) val={v / 2} td={T - 14e-9} rise=2
"""
    def an(m):
        f = 16 / m['per'] if 'per' in m else None
        fo = 1 / m['pero'] if 'pero' in m else None
        return dict(vtune_v=vtune, f_vco_hz=f, f_div_hz=fo, ratio=(f / fo if f and fo else None),
                    divides_by_16=bool(f and fo and abs(f / fo / 16 - 1) < 0.01))
    return body, an

def run(name, tb, kw, corner='tt', temp=27, v=V):
    body, an = tb(v=v, **kw)
    deck = hdr(corner, temp) + body + '.end\n'
    m = tf.ngspice(WORK, name, deck)
    r = an(m)
    r.update(corner=corner, temp_c=temp, vdd_v=v, deck=f'scratch/timing/lcvco/sim/{name}.spice', netlist='schematic VCO + analytical spiral')
    if m.get('_errors'):
        r['sim_messages'] = m['_errors'][:5]
    return r

if __name__ == '__main__':
    stage()
    what = sys.argv[1] if len(sys.argv) > 1 else 'tune'
    out_p = HERE / 'results.json'
    res = json.loads(out_p.read_text()) if out_p.exists() else {}
    jobs = []
    if what == 'tune':
        jobs = [(f'tune_vt{vt}', tb_tune, dict(vtune=vt), 'tt', 27, V) for vt in (0.0, 0.8, 1.65, 2.5, 3.3)]
    elif what == 'corners':
        for c in ('tt', 'ss', 'ff'):
            for t in (22, 32):
                for v in (3.15, 3.35):
                    for vt in (0.0, 3.3):
                        jobs.append((f'c_vt{vt}_{c}_{t}_{v}', tb_tune, dict(vtune=vt), c, t, v))
    elif what == 'chain':
        vt = float(sys.argv[2])
        jobs = [(f'chain_vt{vt}', tb_chain, dict(vtune=vt), 'tt', 27, V)]
    elif what == 'prescale':
        vt = float(sys.argv[2])
        jobs = [(f'prescale_vt{vt}', tb_prescale, dict(vtune=vt), 'tt', 27, V)]
    with ThreadPoolExecutor(int(__import__("os").environ.get("LC_PAR", "2"))) as ex:
        for (name, *_), r in zip(jobs, ex.map(lambda j: run(j[0], j[1], j[2], j[3], j[4], j[5]), jobs)):
            res.setdefault(what, {})[name] = r
            print(name, json.dumps(r, default=str)[:600], flush=True)
    out_p.write_text(json.dumps(res, indent=1, default=str))
