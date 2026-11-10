#!/usr/bin/env python3
"""Verify the numerical MOSCAP overlay against the retained PDK and its integral."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

import numpy as np

from moscap_charge import overlay

ROOT = Path(__file__).resolve().parents[3]


def check(out, pdk, ngspice):
    out.mkdir(parents=True, exist_ok=True)
    (out/'.spiceinit').write_text('set ngbehavior=hs\n')
    raw = (pdk/'ngspice/sm141064.spice').read_text()
    block = re.search(r'^\.lib moscap\s*$(.*?)^\.endl moscap\s*$', raw, re.M | re.S).group(1)
    names = re.findall(r'^\.subckt (\w+)', block, re.M)
    params = {name: [float(x) for x in re.findall(r'^\.param cvar\d=([^\n]+)',
               re.search(rf'^\.subckt {name}\b.*?^\.ends', block, re.M | re.S).group(), re.M)]
              for name in names}
    native = re.sub(r'\b('+'|'.join(names)+r')\b', r'native_\1', block)
    max_ac = max_current = max_charge = 0.
    cases = 0
    def run(deck, stem):
        (out/f'{stem}.spice').write_text('\n'.join(deck)+'\n')
        result = subprocess.run([str(ngspice), '-b', f'{stem}.spice'], cwd=out,
                                text=True, capture_output=True, check=True, timeout=120)
        log = result.stdout+result.stderr
        (out/f'{stem}.log').write_text(log)
        for bad in ('Error', 'Timestep too small', 'simulation(s) aborted'):
            assert bad not in log, log[-2000:]
    for corner, factor in [('typical', 1.), ('ff', .9), ('ss', 1.1)]:
        d = ['MOSCAP charge equivalence', overlay(pdk, corner), native,
             '.options klu method=gear reltol=1e-7 abstol=1e-14 vntol=1e-9 rshunt=1e12 cshunt=1e-17']
        expected, signals = [], []
        for name in names:
            a, b, k, h = params[name]
            for m in [1, 4, 8]:
                for bias in [-3.63, -3.3, -1., -.67, 0., .3, .67, 1., 1.65, 3.3, 3.63]:
                    idx = len(expected)
                    for prefix, model in [('q', name), ('n', 'native_'+name)]:
                        d += [f'V{prefix}{idx} {prefix}{idx} 0 DC {bias} AC 1',
                              f'X{prefix}{idx} {prefix}{idx} 0 {model} c_length=1.5u c_width=5u m={m}']
                        signals.append(f'imag(i(V{prefix}{idx}))')
                    expected.append(-2*np.pi*1e9*(factor*7.5e-12*m*(a+b*np.tanh(k*bias+h))+1e-17))
        d += ['.control', 'set wr_singlescale', 'set wr_vecnames', 'set numdgt=16',
              'ac lin 1 1G 1G', 'wrdata ac-'+corner+'.dat '+' '.join(signals), 'quit', '.endc', '.end']
        run(d, 'ac-'+corner)
        values = np.loadtxt(out/f'ac-{corner}.dat', skiprows=1)[1:].reshape(-1, 2)
        errors = np.abs(values/np.array(expected)[:, None]-1)
        max_ac = max(max_ac, float(np.max(errors)))
        assert np.max(errors) < 1e-6, f'AC mismatch: {np.max(errors)}'
        cases += len(expected)
        # Nonzero initial voltage tests both charge reference and signed current.
        d = ['MOSCAP charge ramps', overlay(pdk, corner), native,
             '.options klu method=gear reltol=1e-7 abstol=1e-14 vntol=1e-9 rshunt=1e12 cshunt=1e-17']
        signals, models = [], []
        for name in names:
            for m in [1, 4, 8]:
                idx = len(models)
                for prefix, model in [('q', name), ('n', 'native_'+name)]:
                    d += [f'V{prefix}{idx} {prefix}{idx} 0 PWL(0 -3.3 1n -3.3 11n 3.3 12n 3.3 22n -3.3 23n -3.3)',
                          f'X{prefix}{idx} {prefix}{idx} 0 {model} c_length=1.5u c_width=5u m={m}']
                    signals.append(f'i(V{prefix}{idx})')
                models.append((name, m))
        d += ['.control', 'set wr_singlescale', 'set wr_vecnames', 'set numdgt=16',
              'tran 2p 23n', 'wrdata ramp-'+corner+'.dat '+' '.join(signals), 'quit', '.endc', '.end']
        run(d, 'ramp-'+corner)
        wave = np.loadtxt(out/f'ramp-{corner}.dat', skiprows=1)
        t = wave[:, 0]
        for idx, (name, m) in enumerate(models):
            a, b, k, h = params[name]
            currents = wave[:, 1+2*idx:3+2*idx]
            def charge(v):
                z = k*v+h
                return factor*7.5e-12*m*(a*v+b/k*(np.logaddexp(z, -z)-np.logaddexp(h, -h)))
            for lo, hi, v0, v1 in [(1e-9, 11e-9, -3.3, 3.3), (12e-9, 22e-9, 3.3, -3.3)]:
                use = (t >= lo)&(t <= hi)
                target = -(charge(v1)-charge(v0)+1e-17*(v1-v0))
                integral = np.trapezoid(currents[use], t[use], axis=0)
                charge_error = float(np.max(np.abs(integral/target-1)))
                max_charge = max(max_charge, charge_error)
                assert charge_error < .002, (name, m, charge_error)
                v = v0+(v1-v0)*(t-lo)/(hi-lo)
                exact = -(factor*7.5e-12*m*(a+b*np.tanh(k*v+h))+1e-17)*(v1-v0)/(hi-lo)
                interior = (t > lo+10e-12)&(t < hi-10e-12)
                error = np.max(np.abs(currents[interior]-exact[interior, None]))/np.max(np.abs(exact[interior]))
                max_current = max(max_current, float(error))
                assert error < .002, (name, m, error)
    # The real provider has nested subcircuit calls with m. Test hs multiplicity.
    d = ['Nested MOSCAP multiplier', overlay(pdk), native]
    for prefix, model in [('q', 'cap_nmos_06v0'), ('n', 'native_cap_nmos_06v0')]:
        d += [f'.subckt {prefix}nest p n', f'Xc p n {model} c_length=1.5u c_width=5u m=4',
              f'.ends {prefix}nest', f'V{prefix} {prefix} 0 DC .67 AC 1',
              f'X{prefix} {prefix} 0 {prefix}nest m=2']
    d += ['.control', 'set wr_singlescale', 'set wr_vecnames', 'set numdgt=16',
          'ac lin 1 1G 1G', 'wrdata nested.dat imag(i(Vq)) imag(i(Vn))', 'quit', '.endc', '.end']
    run(d, 'nested')
    nested = np.loadtxt(out/'nested.dat', skiprows=1)[1:]
    a, b, k, h = params['cap_nmos_06v0']
    expected = -2*np.pi*1e9*7.5e-12*8*(a+b*np.tanh(k*.67+h))
    assert np.max(np.abs(nested/expected-1)) < 1e-6
    # Exercise the actual pad at long absolute time, including rail ripple and
    # late logic transitions. The auxiliary 1 fs differentiator formerly failed
    # inside this provider cell during the joined 50 ms bring-up sequence.
    library = (pdk/'gf180mcu_fd_io.spice').read_text()
    pins = re.search(r'^\.SUBCKT gf180mcu_fd_io__bi_24t ([^\n]+)', library, re.M).group(1).split()
    binding = dict(A='A', CS='0', DVDD='VDD', DVSS='0', IE='0', OE='OE', PAD='PAD',
                   PD='0', PU='0', SL='0', VDD='VDD', VSS='0', Y='UNUSED')
    d = ['Long absolute-time provider pad test', f'.include {pdk}/ngspice/design.ngspice']
    d += [f'.lib {pdk}/ngspice/sm141064.ngspice {c}'
          for c in ('typical', 'res_typical', 'diode_typical', 'mimcap_typical')]
    d += [overlay(pdk), library,
          'VBOARD BOARD 0 PWL(0 0 1u 3.3 .05002 3.3 .050020001 3.297 .050020002 3.3 .050020003 3.299 .050020004 3.3)',
          'RBOARD BOARD VDD .0225', 'CGLOBAL VDD 0 1n',
          'VA A 0 PWL(0 0 .050020005 0 .0500200051 3.3 .050020007 3.3 .0500200071 0)',
          'VOE OE 0 PWL(0 0 .050020004 0 .0500200041 3.3)',
          'Xpad '+' '.join(binding[p] for p in pins)+' gf180mcu_fd_io__bi_24t',
          'CPAD PAD 0 5p', 'RPAD PAD 0 1g',
          '.options klu method=gear reltol=1e-3 rshunt=1e12 cshunt=1e-17',
          '.control', 'set wr_singlescale', 'set wr_vecnames', 'set numdgt=16',
          'tran 1u .05002002 0 200u', 'wrdata late-pad.dat v(VDD) v(PAD)', 'quit', '.endc', '.end']
    run(d, 'late-pad')
    late = np.loadtxt(out/'late-pad.dat', skiprows=1)
    assert np.isfinite(late).all() and late[-1, 0] >= .05002002*(1-1e-10)
    assert np.interp(.050020009, late[:, 0], late[:, 2]) > 3.15, 'late pad high missing'
    assert np.interp(.050020012, late[:, 0], late[:, 2]) < .15, 'late pad low missing'
    sources = [Path(__file__).resolve(), Path(__file__).with_name('moscap_charge.py'),
               pdk/'gf180mcu_fd_io.spice', *sorted((pdk/'ngspice').glob('*spice')), ngspice]
    report = dict(status='pass', ac_cases=cases, ramp_cases=3*8*3*2,
                  nested_effective_multiplier=8, long_absolute_time_provider_pad=True, max_ac_relative_error=max_ac,
                  max_ramp_current_relative_error=max_current, max_integrated_charge_relative_error=max_charge,
                  source_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'source_hashes'}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, default=ROOT/'scratch/moscap-charge-validation')
    p.add_argument('--pdk', type=Path, default=ROOT/'scratch/transceiver-pad-pdk')
    p.add_argument('--ngspice', type=Path, default=ROOT/'scratch/pad-ngspice47/ngspice-47/src/ngspice')
    args = p.parse_args()
    check(args.output_dir.resolve(), args.pdk.resolve(), args.ngspice.resolve())
