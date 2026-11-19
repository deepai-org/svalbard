"""hib switch sizing: OTA input noise (tt, 5 MHz, hib = 1) and mixer supply current vs the extra-tail supply-switch width factor."""
import sys; sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/rf_rx')
from pathlib import Path
import netlists as N, tb
k = float(sys.argv[1])
src = N.ota_lownoise
def patched():
    s = src.__wrapped__() if hasattr(src, '__wrapped__') else None
N.OTAN_XTAIL_SW = k
W = Path('/home/ubuntu/svalbard/scratch/rf-rx-tia/hib') / f'k{k:g}'; W.mkdir(parents=True, exist_ok=True)
p = W / 'rxmix.spice'; N.emit(p, N.rxmix('pt_rxmix_i')); tb.SELFTEST_NETLIST['rxmix_i'] = p
_o = tb.netlist; tb.netlist = lambda w, b, v: _o(w, b, 'selftest' if b == 'rxmix_i' else v)
en = tb.ota_input_noise(W, f=5e6, hib=True) * 1e9
r = tb.rxmix_tran(W, 'selftest', block='rxmix_i', hib=True)
print('k', k, 'en nV/rtHz %.3f' % en, 'idd', r.get('idd_ma', r.get('idd_a')), 'gain', r.get('gain_db', r.get('conv_gain_db')))
