"""Lock time and loop margins with the r9 QVCO (extracted Kvco, band 6, VT 1.2-1.8 V: 53-85 MHz/V over ff/OPT85 ... ss/PF115)
and the extracted charge pump (98 uA at ICP = 3, all corners), behavioural loop run_loop.hop4 as lock_rc.py.
Start offset: band search picks the band whose VT at lock is nearest the VDD/2 preset; worst band step ~36 MHz -> up to
+-0.35 V from the preset (both signs). Filter as built (lock_rc.py base) over R +-25 %, C2 +-15 %."""
import sys, json
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/timing/lcvco')
import run_loop as rl
base = dict(r_ohm=10380, c1_f=5.45e-12, c2_f=489.6e-12 * 1.115, r3_ohm=1e4, c3_f=8.84e-12)
KV = dict(ff=53.1e6, OPT85=58.6e6, tt=65.7e6, ss=80.4e6, PF115=84.8e6)
out = []
for kvn, kv in KV.items():
    for n in (44, 56):
        for icp in (75e-6, 98e-6, 125e-6):
            for rs in (0.75, 1.0, 1.25):
                for cs in (0.85, 1.0, 1.15):
                    lf = dict(base, r_ohm=base['r_ohm'] * rs, r3_ohm=1e4 * rs, c2_f=base['c2_f'] * cs)
                    fc, pm = rl.loop_margins(lf, icp, kv, n)
                    t = max(rl.hop4(lf, icp, kv, n, s * kv * 0.35, t_end=150e-6)['t_lock_2deg_s'] or 1 for s in (-1, 1)) * 1e6
                    out.append(dict(kv_corner=kvn, kv=kv, n=n, icp=icp, r_scale=rs, c2_scale=cs, fc_khz=fc / 1e3, pm_deg=pm, t_lock_us=t))
json.dump(out, open('lock_r9.json', 'w'), indent=1)
for kvn in KV:
    g = [x for x in out if x['kv_corner'] == kvn]
    print(kvn, 'fc %.0f-%.0f kHz' % (min(x['fc_khz'] for x in g), max(x['fc_khz'] for x in g)), 'PM min %.1f' % min(x['pm_deg'] for x in g),
          't_lock max %.1f us (nominal filter %.1f)' % (max(x['t_lock_us'] for x in g), max(x['t_lock_us'] for x in g if x['r_scale'] == 1 and x['c2_scale'] == 1)))
