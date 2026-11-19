"""OTA input noise, x1 vs x2 (schematic rxmix netlist, tb.ota_input_noise), tt and ss/32/3.15 at 1 and 5 MHz."""
import sys, json
RX = '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/rf_rx'
sys.path.insert(0, RX)
from pathlib import Path
import netlists as N
import tb
S = Path('/home/ubuntu/svalbard/scratch/rf-rx-tia')
out = {}
_orig = tb.netlist
tb.netlist = lambda work, block, view: _orig(work, block, 'selftest' if block == 'rxmix_i' else view)
for x in (1, 2):
    W = S / 'w' / f'ota_x{x}'; W.mkdir(parents=True, exist_ok=True)
    N.OTAN = dict(N.OTAN, tail=240. * x, win=1200. * x); N.OTAN_XTAIL = 0.
    p = W / 'rxmix_var.spice'; N.emit(p, N.rxmix('pt_rxmix_i'))
    tb.SELFTEST_NETLIST['rxmix_i'] = p
    for c in (('typical', 27, 3.3), ('ss', 32, 3.15)):
        for f in (1e6, 5e6):
            en = tb.ota_input_noise(W, corner=c, f=f) * 1e9
            out[f'x{x} {c[0]}/{c[1]}/{c[2]} {f/1e6:g}MHz'] = round(en, 3)
            print(x, c, f, 'en nV/rtHz %.3f' % en, flush=True)
(S / 'ota_noise.json').write_text(json.dumps(out, indent=1))
