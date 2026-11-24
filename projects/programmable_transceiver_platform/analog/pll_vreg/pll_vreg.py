#!/usr/bin/env python3
"""PDN-04: ring-PLL supply regulator `pt_pll_vreg` (pads owner, for wired RX / pll_ring).

Topology: native NMOS follower ("capacitance multiplier"), gate held at the RC-filtered island rail:
  MPASS  nfet_06v0_nvt  D=VIN G=VG S=VOUT  W = NF x 20 um, L = 1.8 um (native: Vgs ~0.1-0.45 V)
  RF     ppolyf_u_1k_6p0 VIN->VG  (~1 Mohm)      CG  thin-oxide MOS cap VG->VSS (~50 pF): gate pole ~3 kHz
  COUT   thin-oxide MOS cap VOUT->VSS (~100 pF) for the ring's GHz current pulses
  MBYP   pfet_03v3 VIN->VOUT, W 1000 um: BYP=1 shorts the regulator (ring on the raw rail, fallback)
  MBI/MBN  BYP inverter on VIN (BYP from the core register, 3.3 V)
  RATB_O 20 kohm VOUT->ATB_OUT,  RATB_G 20 kohm VG->ATB_G (ATB leaves: observe Vout/VG, force VG = set Vout)
No DC current into VG: VG = rail(avg), VOUT = rail - Vgs(I). Above the gate pole the gate is quiet and the
follower's 1/gm output holds VOUT: supply ripple reaches VOUT only through ro, Cgd and Cds.
The PLL loop (2.6 MHz BW) absorbs the slow rail tracking and the corner-dependent Vgs.
"""
import sys, json, math, subprocess
from pathlib import Path
import numpy as np
import os
W = Path(os.environ.get('PLL_VREG_WORK', str(Path(__file__).resolve().parents[4] / 'scratch/pdn04-ldo')))   # sims + caches (ring netlist copied to <W>/sch)
IMG = 'sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'
P = dict(nf=300, fw=20., l=2.7, cg_um2=15000., cout_um2=10000., wbyp=1000.)   # variant B of explore2.json; caps halved PD28 (was 30000/20000)

def netlist(p=P, name='pt_pll_vreg'):
    """v2: the gate is driven by a slow OTA that holds VOUT = k * VIN(filtered), k = R2/(R1+R2) = 0.9, i.e. a
    ~0.3 V dropout at every corner, so the native pass device stays saturated (v1, gate = filtered rail, ran
    the pass device in triode at ff: 44 mV dropout, PSRR -1.8 dB)."""
    cg_side = math.sqrt(p['cg_um2'] / 20); co_side = math.sqrt(p['cout_um2'] / 40)
    return f""".subckt {name} VIN VOUT VSS BYP ATB_OUT ATB_G
XMPASS VIN VG VOUT VSS nfet_06v0_nvt w={p['fw']}u l={p['l']}u m={p['nf']}
* reference: VIN divider 0.9 (300k / 2.7M) with ~2 pF MOS cap (~0.3 MHz); its ripple is suppressed again by the gate pole
XR1 VIN INP VSS ppolyf_u_1k_6p0 r_width=1u r_length={p.get('r1',300)}u
XR2 INP VSS VSS ppolyf_u_1k_6p0 r_width=1u r_length={p.get('r2',2700)}u
XCR VSS INP VSS VSS nfet_03v3 w=10u l=10u m=4
* OTA: NMOS pair, PMOS mirror on VIN, self-biased tail (~4 uA)
XMN1 X1 INP T VSS nfet_03v3 w=4u l=1u
XMN2 VG VOUT T VSS nfet_03v3 w=4u l=1u
XMP1 X1 X1 VIN VIN pfet_03v3 w=2u l=1u
XMP2 VG X1 VIN VIN pfet_03v3 w=2u l=1u
XMT T NB VSS VSS nfet_03v3 w=2u l=2u
XMB NB NB VSS VSS nfet_03v3 w=2u l=2u
XRB VIN NB VSS ppolyf_u_1k_6p0 r_width=1u r_length={p.get('rb',500)}u
* start-up: pulls VG up while VOUT < VIN - |Vtp| (off in regulation: Vsg = dropout 0.31-0.49 V)
XMST VG VOUT VIN VIN pfet_03v3 w=2u l=1u
XCG VSS VG VSS VSS nfet_03v3 w={cg_side:.3f}u l={cg_side:.3f}u m=20
XCO VSS VOUT VSS VSS nfet_03v3 w={co_side:.3f}u l={co_side:.3f}u m=40
XMBYP VOUT BYPN VIN VIN pfet_03v3 w=10u l=0.28u m={int(p['wbyp']/10)}
XMBIP BYPN BYP VIN VIN pfet_03v3 w=4u l=0.28u
XMBIN BYPN BYP VSS VSS nfet_03v3 w=2u l=0.28u
XRATO VOUT ATB_OUT VSS ppolyf_u_1k_6p0 r_width=1u r_length=20u
XRATG VG ATB_G VSS ppolyf_u_1k_6p0 r_width=1u r_length=20u
.ends {name}
"""

def hdr(c='typical', t=27):
    lib = {'typical': 'typical', 'ss': 'ss', 'ff': 'ff'}[c]
    r = {'typical': 'res_typical', 'ss': 'res_ss', 'ff': 'res_ff'}[c]
    return (f'.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice\n.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice {lib}\n'
            f'.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice {r}\n.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice diode_typical\n.temp {t}\n')

def run(sub, n, text, outvec):
    d = W / sub; d.mkdir(exist_ok=True)
    deck = text + f'.control\nset wr_singlescale\nrun\nwrdata /w/{n}.txt {outvec}\n.endc\n.end\n'
    cir, txt = d / f'{n}.cir', d / f'{n}.txt'
    if not (txt.exists() and cir.exists() and cir.read_text() == deck):   # reuse only the identical deck
        cir.write_text(deck); txt.unlink(missing_ok=True)
        subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--user', '1000:1000', '-e', 'HOME=/tmp', '-v', f'{d}:/w',
                        '--entrypoint', '/bin/bash', IMG, '-lc', f'cd /w && ngspice -b {n}.cir > {n}.log 2>&1'], check=True, timeout=7200)
    return np.loadtxt(txt)

def dc(c, t, vin, iload, byp=0, tag=''):
    n = f'dc{tag}_{c}_{t}_{vin}_{iload}_{byp}'
    d = hdr(c, t) + netlist() + f'VIN VIN 0 {vin}\nVB BYP 0 {3.3*byp}\nIL VOUT 0 {iload}m\nX1 VIN VOUT 0 BYP AO AG pt_pll_vreg\nRAO AO 0 1g\nRAG AG 0 1g\n.op\n'
    x = run('sch', n, d.replace('.op\n', '.dc VIN ' + f'{vin} {vin} 0.1\n'), 'v(VOUT) v(x1.VG)')
    return dict(vout=float(x[1]), vg=float(x[2]), dropout=float(vin - x[1]))

def psrr(c, t, vin, iload, tag=''):
    n = f'ac{tag}_{c}_{t}_{vin}_{iload}'
    rl = 2.8 / (iload * 1e-3)
    d = hdr(c, t) + netlist() + f'VIN VIN 0 DC {vin} AC 1\nVB BYP 0 0\nRL VOUT 0 {rl:.1f}\nX1 VIN VOUT 0 BYP AO AG pt_pll_vreg\nRAO AO 0 1g\nRAG AG 0 1g\n.ac dec 20 1e3 1e9\n'
    x = run('sch', n, d, 'vdb(VOUT)')
    f, db = x[:, 0], x[:, 1]
    pick = {f'{q/1e6:g}MHz': float(np.interp(math.log10(q), np.log10(f), db)) for q in (1e5, 1e6, 2.6e6, 10e6, 78.125e6, 156.25e6, 200e6, 1e9)}
    return dict(psrr_dB=pick, worst_10_200MHz_dB=float(db[(f >= 10e6) & (f <= 200e6)].max()))

def ring_ripple(c, t, vin, am, fm, byp, vct=1.5, T=300e-9):
    """Extracted pt_pll_ring (open loop, VCTRL fixed) on the regulator output; rail = vin + am*sin(fm)."""
    n = f'rr2_{c}_{t}_{vin}_{am}_{fm/1e6:g}_{byp}_{vct}'
    # The regulation loop is ~kHz slow: start the gate at its steady state for the ring's average current
    # (DC op with an equivalent 7 mA load), otherwise the 300 ns window sees the enable-step sag.
    vg0 = dc(c, t, vin, 7, byp)['vg']
    d = hdr(c, t) + netlist() + '.include /w/pll_ring.ext.spice\n' + f'.ic v(x1.VG)={vg0:.4f}\n'
    d += f'VIN VIN 0 sin({vin} {am} {fm} 0)\nVB BYP 0 {3.3*byp}\nX1 VIN VR 0 BYP AO AG pt_pll_vreg\nRAO AO 0 1g\nRAG AG 0 1g\n'
    d += f'VEN en 0 pwl(0 0 2n 0 2.1n 3.3)\nIB VR ibias 10u\nVREF ref 0 0\nVCT vctrl 0 {vct}\nVN4 n4 0 0\nVN8 n8 0 0\nVHOLD hold 0 0\n'
    d += 'VN5 n5 0 0\nVN10 n10 0 0\nVFT kp0 0 0\n'  # r9 ports: N5/N10 off, CDR fast-tune idle
    d += 'XR ref en n4 n8 hold ibias ph0 ph1 ph2 ph3 ph4 ph5 ph6 ph7 lock fbck refo vctrl n5 n10' + ' kp0' * 11 + ' VR VR 0 pt_pll_ring\n'
    d += ''.join(f'CP{k} ph{k} 0 20f\n' for k in range(8)) + 'CRO refo 0 20f\n.option method=gear reltol=1e-3\n'
    d += f'.tran 2p {T}\n'
    x = run('sch', n, d, 'v(ph0) v(VR)')
    tt, v, vr = x[:, 0], x[:, 1], x[:, 2]
    th = (v.max() + v.min()) / 2; k = np.where((v[:-1] < th) & (v[1:] >= th))[0]
    e = tt[k] + (th - v[k]) * (tt[k + 1] - tt[k]) / (v[k + 1] - v[k]); e = e[e > 60e-9]
    per = np.diff(e); tm = e[1:]; fi = 1 / per; f0 = fi.mean()
    A = 2 * abs(np.mean((fi - f0) * np.exp(-2j * np.pi * fm * tm))) / np.sinc(fm / f0)
    m = tt > 60e-9
    vr_rip = 2 * abs(np.mean((vr[m] - vr[m].mean()) * np.exp(-2j * np.pi * fm * tt[m])))
    beta = A / fm
    return dict(f0_MHz=float(f0 / 1e6), dev_MHz=float(A / 1e6), Kvdd_eff_MHz_per_V_of_rail=float(A / am / 1e6), vout_mean=float(vr[m].mean()),
                vout_ripple_mV=float(vr_rip * 1e3), psrr_tran_dB=float(20 * math.log10(max(vr_rip, 1e-9) / am)),
                beta_rad=float(beta), dj_pk_ps_at_625MHz=float(beta / (2 * math.pi * 625e6) * 1e12), spur_dBc=float(20 * math.log10(max(beta / 2, 1e-12))))

if __name__ == '__main__' and len(sys.argv) > 1 and sys.argv[1] == 'ring':
    out = {}
    for c, t, fm, byp in (('typical', 27, 78.125e6, 1), ('typical', 27, 78.125e6, 0), ('typical', 27, 156.25e6, 0), ('typical', 27, 10e6, 0),
                          ('ss', 32, 78.125e6, 0), ('ff', 22, 78.125e6, 0), ('typical', 27, 156.25e6, 1)):
                k = f'{c}_{t}_fm{fm/1e6:g}_byp{byp}'; out[k] = ring_ripple(c, t, 3.25, 0.06, fm, byp); print(k, out[k], flush=True)
                (W / 'ldo-ring.json').write_text(json.dumps(out, indent=1))
    sys.exit(0)

def startup(c, t, rise, rl=400.):
    n = f'su_{c}_{t}_{rise}'
    T = 20 * float(rise.rstrip('u'))
    d = hdr(c, t) + netlist() + f'VIN VIN 0 PWL(0 0 {rise} 3.25)\nVB BYP 0 0\nRL VOUT 0 {rl}\nX1 VIN VOUT 0 BYP AO AG pt_pll_vreg\nRAO AO 0 1g\nRAG AG 0 1g\n.tran {T/2000:.4g}u {T}u\n'
    x = run('sch', n, d, 'v(VOUT) v(VIN) v(x1.VG)')
    tt, vo, vi = x[:, 0], x[:, 1], x[:, 2]
    fin = vo[-1]; k = np.argmax(vo > 0.95 * fin)
    return dict(rise=rise, vout_final=float(fin), t95_us=float(tt[k] * 1e6), overshoot_mV=float((vo.max() - fin) * 1e3), vout_minus_vin_max=float((vo - vi).max()))

if __name__ == '__main__':
    out = dict(netlist=netlist(), params=P, dc={}, psrr={}, startup={}, bypass={})
    for c, t in (('typical', 27), ('ss', 32), ('ff', 22)):
        out['startup'][f'{c}_{t}'] = [startup(c, t, r) for r in ('1u', '10u')]
        out['bypass'][f'{c}_{t}'] = dc(c, t, 3.05, 8, byp=1)
    for c, t in (('typical', 27), ('ss', 32), ('ff', 22), ('ss', 22), ('ff', 32)):
        for vin in (3.05, 3.25, 3.35):
            for il in (3, 6, 8):
                out['dc'][f'{c}_{t}_{vin}_{il}'] = dc(c, t, vin, il)
        out['psrr'][f'{c}_{t}'] = psrr(c, t, 3.15, 6)
        (W / 'ldo-sch.json').write_text(json.dumps(out, indent=1)); print(c, t, out['psrr'][f'{c}_{t}']['worst_10_200MHz_dB'], out['dc'][f'{c}_{t}_3.05_6'], flush=True)
