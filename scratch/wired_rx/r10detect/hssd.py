"""HS-pair signal detect (SD_POS|SD_NEG of pt_detect r10) against its real source.
source : differential PRBS7 source, 50 ohm per leg -> channel -> 10 mm carrier (P2) -> TT01 COB package (WIRE_RX_P/N
         geometry) -> pad_hspad (pads/generated/stress-safe-families/wired-receive-hs/physical.spice: 2 x 50 ohm
         termination to TERM_VCM 0.45 V, on-die MIM AC coupling, VBIAS 1.0 V) -> RX_P/N = HS_RX_P/N
load   : pt_detect HS_P/HS_N + 20 fF route per leg, and the CTLE input as 260 fF per leg (published pt_ctle input C
         255-267 fF; the CTLE itself is being redesigned and is not instantiated).
channel: 'flat' (package and carrier only) or 'loss' = one RC pole per leg placed for -9 dB at Nyquist (a stand-in
         for cable/board loss; the amplitude quoted is the settled (long-run) differential p-p at the pad).
sequence (det_hs_en = 1, det_clk 250 MHz, det_en at 0, stimulus from 150 ns):
   idle + interference (20 mVppd: 14 mVppd at 610 MHz + 6 mVppd at 97 MHz)  100 ns
   PRBS7 at A1, A2, A3 mVppd (default 60, 100, 200), 100 ns each (interference stays on)
   idle + interference  60 ns
Limits (C7, written before the first run): hit fraction (SD_POS|SD_NEG high) = 0 in both idle windows;
   > 0.10 at 100 mVppd and at 200 mVppd; the 60 mVppd figure is reported (threshold region, no limit).
   Response: first hit after the 100 mVppd segment starts <= 50 ns; last hit after data stops <= 12 ns.
usage (inside slot.sh): python3 hssd.py <tag> <detect netlist> <env> <rate> <flat|loss> [amps=60,100,200] [vdd=]"""
import sys; sys.path.insert(0, '/home/ubuntu/svalbard/scratch/wired_rx/r10detect')
from common import *
import bench, pkg_channel as pc, math
PAD = W.parent / 'pads/generated/stress-safe-families/wired-receive-hs/physical.spice'
ENV = dict(tt=('typical', 27, 3.3), ss=('ss', 32, 3.15), ff=('ff', 22, 3.35))
TRIM = dict(typical=6, ss=9, ff=2)                     # pads pd21-hspad-rxpath.json calibrated codes
tag, net, env, rate, chan = sys.argv[1:6]; rate = float(rate); kw = dict(a.split('=') for a in sys.argv[6:])
corner, temp, vdd = ENV[env]; vdd = float(kw.get('vdd', vdd)); amps = [float(x) for x in kw.get('amps', '60,100,200').split(',')]


def prbs7(n, seed=0x5A):
    s, out = seed, []
    for _ in range(n):
        b = ((s >> 6) ^ (s >> 5)) & 1
        out.append((s >> 6) & 1)
        s = ((s << 1) | b) & 0x7F
    return out

sub = f.parse_spice(net)
work = R10 / 'sim' / 'hssd' / f'{tag}_{env}_{vdd}_{rate:g}_{chan}'
work.mkdir(parents=True, exist_ok=True)
(work / 'pad.spice').write_text(''.join(l for l in PAD.read_text().splitlines(True) if not l.lower().startswith('.lib')))
hdr = f.sim_header(corner, temp); mim = hdr.splitlines()[1].rsplit(' ', 1)[0] + ' mimcap_' + {'typical': 'typical'}.get(corner, corner)
trim = TRIM[corner]
L = [f'VDDS vdds 0 {vdd}', 'RVDDS vdds vdd 0.2', 'CVDD vdd 0 2n', 'VTVCM tvcm 0 0.45', 'VVB vb 0 1.0', f'VTE te_d 0 {vdd}', 'RTE te_d te 200']
for k in range(4):
    L += [f'VTT{k} tt{k}_d 0 {vdd * (trim >> k & 1)}', f'RTT{k} tt{k}_d tt{k} 200']
L.append('XPAD vdd 0 vdd tvcm te tt0 tt1 tt2 tt3 vb rxp rxn pdp pdn hs_protected_pad')
m = bench.base_map()
L += [f'VEN en 0 PWL(0 0 2n {vdd})', f'VCK clk 0 PULSE(0 {vdd} 5n 0.1n 0.1n 1.9n 4n)', 'VT0 t0 0 0', 'VT1 t1 0 0', 'VS0 s0 0 0', 'VS1 s1 0 0',
      'VSRC src 0 0', 'VINJ inj 0 0', f'VHSEN hsen 0 {vdd}', 'RIB vdd ib 260k', 'VTXP txp 0 0', 'VTXN txn 0 0', 'VLP lp 0 0', 'VLN ln 0 0',
      sims.inst(sub, {**m, 'HS_P': 'rxp', 'HS_N': 'rxn'}), 'CRP rxp 0 280f', 'CRN rxn 0 280f', 'COP sdp 0 50f', 'CON sdn 0 50f']
L += [pc.subckt('cobp', 'WIRE_RX_P', pc.PLACES['P2']), pc.subckt('cobn', 'WIRE_RX_N', pc.PLACES['P2']), 'XCP pdp bp cobp', 'XCN pdn bn cobn']
ui = 1 / rate; tr = min(100e-12, 0.3 * ui); T0 = 150e-9
seg_t = [100e-9] + [100e-9] * len(amps) + [60e-9]
# source: open-circuit differential amplitude = 2 x pad amplitude (50 ohm source into the 50 ohm termination)
pts = [(0, 0.)]; t = T0 + seg_t[0]; marks = {'idle0': (T0, t)}
for a in amps:
    nb = int(round(seg_t[1] / ui)); marks[f'a{a:g}'] = (t, t + nb * ui)
    for b in prbs7(nb):
        pts += [(t, pts[-1][1]), (t + tr, (a * 1e-3 / 2) * (1 if b else -1))]; t += ui    # +-A/2 differential at the pad = +-A/2 open-circuit per leg
pts += [(t, pts[-1][1]), (t + tr, 0.)]; marks['idle1'] = (t, t + seg_t[-1]); tend = t + seg_t[-1]
L += [f'VSP sp 0 {sims.pwl([(a, 1.0 + v) for a, v in pts])}', f'VSN sn 0 {sims.pwl([(a, 1.0 - v) for a, v in pts])}',
      'VNA na 0 SIN(0 7m 610e6)', 'VNB nb 0 SIN(0 3m 97e6)',           # differential interference, +-10 mV total at the source = 20 mVppd o.c. -> see pad amplitude
      'ESP sp2 0 VOL=\'v(sp)+v(na)+v(nb)\'', 'ESN sn2 0 VOL=\'v(sn)-v(na)-v(nb)\'', 'RSP sp2 cp 50', 'RSN sn2 cn 50']
if chan == 'loss':
    fp = (rate / 2) / math.sqrt(10 ** (9 / 10) - 1); cc = 1 / (2 * math.pi * fp * 25.0)      # pole of 50||50 ohm with a shunt C at the far end
    L += [f'CCHP cp 0 {cc:.4g}', f'CCHN cn 0 {cc:.4g}']
L += ['CACP cp bp 100n', 'CACN cn bn 100n', 'RBP bp 0 1meg', 'RBN bn 0 1meg']
deck = '\n'.join(['* hssd', hdr, mim, '.option method=gear', '.include dut.spice', '.include pad.spice', *L, '.control',
                  f'tran 10p {tend:.5g}', 'set wr_singlescale', 'wrdata tran.txt v(rxp) v(rxn) v(pdp) v(pdn) v(sdp) v(sdn) v(clk) i(VDDS)', '.endc', '.end', ''])
log = run(work, deck, [(net, 'dut.spice')])
d = np.loadtxt(work / 'tran.txt'); t = d[:, 0]
rx = d[:, 1] - d[:, 2]; pad = d[:, 3] - d[:, 4]; hit = np.maximum(d[:, 5], d[:, 6]) > vdd / 2
r = dict(netlist=str(net), sha=f.sha256(net), env=env, vdd=vdd, rate=rate, chan=chan, rx_cm=round(float(np.mean((d[:, 1] + d[:, 2])[t > T0]) / 2), 3))
for k, (a, b) in marks.items():
    w = (t > a + 8e-9) & (t < b)
    r[k] = dict(hit_fraction=round(float(np.mean(hit[w])), 4), pad_ppd_mV=round(1e3 * float(np.percentile(pad[w], 99.5) - np.percentile(pad[w], 0.5)), 1),
                rx_ppd_mV=round(1e3 * float(np.percentile(rx[w], 99.5) - np.percentile(rx[w], 0.5)), 1))
ups = np.array(sims.crossings(t, np.maximum(d[:, 5], d[:, 6]), vdd / 2, True)); dns = np.array(sims.crossings(t, np.maximum(d[:, 5], d[:, 6]), vdd / 2, False))
a100 = marks.get('a100', list(marks.values())[2])
r['first_hit_after_100mV_ns'] = round(1e9 * float(ups[ups > a100[0]][0] - a100[0]), 2) if (ups > a100[0]).any() else None
r['last_fall_after_stop_ns'] = round(1e9 * float(dns[-1] - marks['idle1'][0]), 2) if len(dns) else None
r['iavg_mA'] = round(-1e3 * float(np.mean(d[t > T0, 8])), 3)
r['pass'] = bool(r['idle0']['hit_fraction'] == 0 and r['idle1']['hit_fraction'] == 0 and all(r[f'a{a:g}']['hit_fraction'] > .10 for a in amps if a >= 100)
                 and r['first_hit_after_100mV_ns'] is not None and r['first_hit_after_100mV_ns'] <= 50)
print(tag, json.dumps(r), flush=True)
store = R10 / 'res' / f'hssd_{tag}.json'; dd = json.loads(store.read_text()) if store.exists() else {}
dd[f'{env}_{vdd}_{rate:g}_{chan}'] = r; store.write_text(json.dumps(dd, indent=1))
