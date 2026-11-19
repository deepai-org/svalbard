#!/usr/bin/env python3
"""Extracted per-chip core-bias check (D8): pt_core_bias_<chip> from integration/core_bias.py.

Netlist: the chip's composite exactly as generated (extracted bandgap / biasgen / root / banks / vref / AND
leaves, capacitance kept). Every BIAS_<consumer> sinks into its own NMOS diode (nfet_03v3 W=4 L=1, the
consumer type: README 'Bias distribution'). Supply ramp 0 -> VDD in 10 us with all island rails on VDD; the
register values of the bring-up sequence (biasgen ena, bgap_ena, coarse, idac2 = 10, bandgap sinks 7 / 3,
trim count 8) from t = 0, then ref_sel_vbg, trunk and output enables at 60 us (the interlock order).
Currents are the mean over 280-300 us.

Cases (each a separate transient):
  window   tt/ss/ff x 22/32 C x 3.15/3.35 V and tt/27 C/3.3 V: every used output 7.5-12.2 uA (README:
           7.52-12.06 uA behind the untrimmed biasgen), VBG 1.19-1.23 V
  trim     ss/32 C/3.50 V (per-chip supply trim setpoint): same limits
  off_<t>  tt/27/3.3 with trunk <t>'s dist_en = 0: its outputs <= 5 nA, every other output in the window
  rail_<t> tt/27/3.3 with trunk <t>'s island rail at 0 V (dist_en and enables high): its outputs <= 5 nA,
           every other output in the window
  en_<c>   tt/27/3.3 with one consumer's EN = 0: that output <= 5 nA, the others in the window
Negative control (must FAIL the same limits): idac2 = 0 (no root reference).

Usage: check_core_bias_chip.py --chip rf|wired [--output-dir DIR] [--jobs 1]
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
sys.path.insert(0, str(PROJECT/'integration'))
import core_bias  # noqa: E402

PDK = ROOT/'scratch/transceiver-pad-pdk/ngspice'
LO, HI, OFF = 7.5e-6, 12.2e-6, 5e-9
VBG = (1.19, 1.23)
T_EN, T_STOP, T_AVG = 60e-6, 300e-6, 280e-6


def deck(core, corner, temp, vdd, mods):
    top = core['top']
    sections = [corner, 'res_'+('typical' if corner in ('tt', 'typical') else corner)]
    lib = 'typical' if corner == 'tt' else corner
    res = 'typical' if corner == 'tt' else corner
    lines = [f'* {top} {corner} {temp} C {vdd} V {mods}', f'.include {PDK}/design.ngspice']
    lines += [f'.lib {PDK}/sm141064.ngspice {s}' for s in (lib, 'res_'+res, 'mimcap_'+res, 'diode_'+res, 'bjt_'+res, 'moscap_'+res)]
    lines += [f'.temp {temp}', '.option method=gear reltol=1e-3 rshunt=1e12', core['text']]
    del sections
    hi = f'PWL(0 0 10u {vdd})'
    late = f'PWL(0 0 {T_EN*1e6:g}u 0 {T_EN*1e6+0.1:g}u {vdd})'
    on = dict(mods.get('values', {}))
    values = {}
    fp = core['field_pins']

    def setf(field, code):
        pins = fp[field]
        for bit, pin in enumerate(pins):
            values[pin] = (code >> bit) & 1
    setf('core.biasgen.ena', 1); setf('core.biasgen.ref_sel_coarse', 1); setf('core.biasgen.ref_sel_fine', 0)
    setf('core.biasgen.idac2_source', mods.get('idac2', 10)); setf('core.biasgen.idac1_source', 0)
    setf('core.biasgen.bandgap_sink1', 7); setf('core.biasgen.bandgap_sink2', 3)
    for f in ('voltgen_source', 'voltgen_sink1', 'voltgen_sink2'):
        setf('core.biasgen.'+f, 0)
    setf('core.refchain.bgap_ena', 1)
    for bit, pin in enumerate(fp['core.refchain.bgap_trim']):
        values[pin] = 1 if bit < 8 else 0
    late_pins = set(fp['core.biasgen.ref_sel_vbg'])
    for name, pins in fp.items():
        if name.startswith('core.refchain.dist_en_'):
            trunks = [t for t, v in core['trunks'].items() if v['dist_en'] == name.rsplit('_', 1)[1]]
            for pin in pins:
                values[pin] = 0 if any(t in mods.get('dist_off', ()) for t in trunks) else 1
                late_pins.add(pin)
    values[fp['core.biasgen.ref_sel_vbg'][0]] = 1
    values.update(on)
    pins = core['pins']
    rails = {t['rail']: t for t in core['trunks'].values()}
    src = [f'VVDD VDD 0 {hi}', 'VVSS VSS 0 0']
    for pin in pins:
        if pin in ('VDD', 'VSS'):
            continue
        if pin in rails:
            trunk = next(k for k, v in core['trunks'].items() if v['rail'] == pin)
            src.append(f'V{pin} {pin} 0 ' + ('0' if trunk in mods.get('rail_off', ()) else hi))
        elif pin.startswith('ON_'):
            src.append(f'V{pin} {pin} 0 {hi}')
        elif pin.startswith('EN_'):
            consumer = pin[3:]
            src.append(f'V{pin} {pin} 0 ' + ('0' if consumer in mods.get('en_off', ()) else late))
        elif pin.startswith('BIAS_'):
            src.append(f'Vm_{pin} {pin} d_{pin} 0')
            src.append(f'XL_{pin} d_{pin} d_{pin} VSS VSS nfet_03v3 w=4u l=1u')
        elif pin in values:
            v = values[pin]
            src.append(f'V{pin} {pin} 0 ' + ((late if pin in late_pins else hi) if v else '0'))
        # observation / spare nodes stay open
    lines.append(f'Xdut {" ".join(pins)} {top}')
    lines += src
    meas = [f'.meas tran i_{p[5:]} avg i(Vm_{p}) from={T_AVG} to={T_STOP}' for p in pins if p.startswith('BIAS_')]
    meas.append(f'.meas tran vbg avg v(VBG) from={T_AVG} to={T_STOP}')
    meas.append(f'.meas tran ivdd avg i(VVDD) from={T_AVG} to={T_STOP}')
    lines += meas
    lines += [f'.tran 50n {T_STOP} 0 200n', '.end']
    return '\n'.join(lines)+'\n'


def run(out, name, text):
    d = out/name
    d.mkdir(parents=True, exist_ok=True)
    (d/'deck.spice').write_text(text)
    (d/'.spiceinit').write_text('set ngbehavior=hsa\nset ng_nomodcheck\nset num_threads=1\n')
    r = subprocess.run(['ngspice', '-b', 'deck.spice'], cwd=d, capture_output=True, text=True,
                       env={**os.environ, 'OMP_NUM_THREADS': '1'}, timeout=7200)
    log = r.stdout+r.stderr
    (d/'ngspice.log').write_text(log[-20000:])
    vals = {m[1].lower(): float(m[2]) for m in re.finditer(r'^\s*(\w+)\s*=\s*([-+0-9.eE]+)', log, re.M)}
    (d/'deck.spice').unlink()  # the generated deck is large and reproducible
    return vals


def judge(core, vals, mods):
    used = [c for cs in core['consumers'].values() for c in cs]
    off = set(mods.get('en_off', ()))
    for t in list(mods.get('dist_off', ()))+list(mods.get('rail_off', ())):
        off |= set(core['consumers'][t])
    errors = []
    for c in used:
        i = vals.get('i_'+c.lower(), float('nan'))  # i(Vm_BIAS_c): from the composite into the consumer diode
        if c in off:
            if not abs(i) <= OFF:
                errors.append(f'{c}: {i:.3e} A with its trunk/rail/EN off')
        elif not LO <= i <= HI:
            errors.append(f'{c}: {i:.3e} A outside {LO:g}-{HI:g}')
    vbg = vals.get('vbg', float('nan'))
    if not VBG[0] <= vbg <= VBG[1]:
        errors.append(f'VBG {vbg:.4f} V')
    return errors


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--chip', choices=core_bias.CHIPS, required=True)
    ap.add_argument('--output-dir', type=Path)
    ap.add_argument('--only', help='comma list of case names (debug)')
    a = ap.parse_args()
    out = (a.output_dir or ROOT/f'scratch/core-bias-{a.chip}/bias-check').resolve()
    out.mkdir(parents=True, exist_ok=True)
    sources = {}

    def read(p):
        p = Path(p)
        sources[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        return p.read_text()
    core = core_bias.build(read, a.chip)
    cases = []
    for corner in ('tt', 'ss', 'ff'):
        for temp in (22, 32):
            for vdd in (3.15, 3.35):
                cases.append((f'window_{corner}_{temp}_{vdd}', corner, temp, vdd, {}))
    cases.append(('window_tt_27_3.3', 'tt', 27, 3.3, {}))
    cases.append(('trim_ss_32_3.5', 'ss', 32, 3.5, {}))
    for t in core['trunks']:
        cases.append((f'off_{t}', 'tt', 27, 3.3, dict(dist_off=[t])))
        cases.append((f'rail_{t}', 'tt', 27, 3.3, dict(rail_off=[t])))
    for cs in core['consumers'].values():
        cases.append((f'en_{cs[0]}', 'tt', 27, 3.3, dict(en_off=[cs[0]])))
    negative = ('negative_idac2_0', 'tt', 27, 3.3, dict(idac2=0))
    cases.append(negative)
    if a.only:
        keep = set(a.only.split(','))
        cases = [c for c in cases if c[0] in keep]
    results = {}
    for name, corner, temp, vdd, mods in cases:
        vals = run(out, name, deck(core, corner, temp, vdd, mods))
        errors = judge(core, vals, mods)
        currents = {k[2:]: v for k, v in vals.items() if k.startswith('i_')}
        results[name] = dict(corner=corner, temp_c=temp, vdd=vdd, mods=mods, errors=errors,
                             vbg_v=vals.get('vbg'), ivdd_ma=-vals.get('ivdd', float('nan'))*1e3,
                             i_min_ua=min((v for k, v in currents.items() if abs(v) > OFF), default=0)*1e6,
                             i_max_ua=max(currents.values(), default=0)*1e6, currents_ua={k: round(v*1e6, 4) for k, v in currents.items()})
        print(name, 'PASS' if not errors else 'FAIL '+'; '.join(errors[:3]), flush=True)
    positives = {k: v for k, v in results.items() if not k.startswith('negative')}
    neg = results.get(negative[0])
    status = 'pass' if all(not r['errors'] for r in positives.values()) and (neg is None or neg['errors']) else 'fail'
    window = [r for k, r in positives.items() if k.startswith(('window', 'trim'))]
    report = dict(status=status, top=core['top'], chip=a.chip,
                  scope='extracted composite (C only), NMOS-diode consumers, transient start-up, per case',
                  limits=dict(on_ua=[LO*1e6, HI*1e6], off_na=OFF*1e9, vbg_v=list(VBG)),
                  summary=dict(cases=len(results), window_i_ua=[min(r['i_min_ua'] for r in window), max(r['i_max_ua'] for r in window)] if window else None,
                               vbg_v=[min(r['vbg_v'] for r in window), max(r['vbg_v'] for r in window)] if window else None,
                               ivdd_ma=[min(r['ivdd_ma'] for r in window), max(r['ivdd_ma'] for r in window)] if window else None,
                               negative_control_rejected=bool(neg and neg['errors'])),
                  results=results, source_hashes=sources, script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out/'report.json').write_text(json.dumps(report, indent=1)+'\n')
    print(json.dumps(dict(status=status, **report['summary'])))
    sys.exit(0 if status == 'pass' else 1)


if __name__ == '__main__':
    main()
